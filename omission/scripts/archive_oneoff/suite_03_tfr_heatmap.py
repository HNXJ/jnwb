"""
suite_03_tfr_heatmap.py — TFR Spectrogram Heatmap with Permutation stats
Loops through all valid NWB sessions that have precomputed TFR arrays,
automatically discovers target visual/frontal areas and probe mappings,
and outputs 2D baseline-normalized dB power spectrogram heatmaps with sig contours.
Usage:
  python scripts/suite_03_tfr_heatmap.py
"""

from __future__ import annotations
import os
import sys
import re
from pathlib import Path
import datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import ttest_1samp
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
import omission as oa

TFR_DIR = Path(os.environ.get("OMISSION_TFR_DIR", "D:/workspace/data/tfr_arrays"))
READY_CSV = Path("artifacts/data/session_readiness.csv")
CONDITION = "AAAB"
WINDOW_MS = (-500.0, 4124.0)

TFR_FILE_RE = re.compile(
    r"^(?P<prefix>sub-[^-]+_ses-[^-]+)-(?P<probe>[A-Z])-(?P<area>[A-Z0-9a-z]+)-(?P<cond>[A-Z0-9]+)\.npy$"
)

def main():
    if not READY_CSV.exists() or not TFR_DIR.exists():
        print("Required catalog or TFR directory does not exist.")
        return
        
    readiness = pd.read_csv(READY_CSV)
    active_sessions = readiness[readiness["nwb_ok"].astype(bool) & readiness["sidecar_ok"].astype(bool) & readiness["suite_tfr_ready"].astype(bool)]
    print(f"Looping over {len(active_sessions)} valid TFR sessions...")
    
    out_dir = REPO_ROOT / "outputs/publication_figures/suite_tfr"
    out_dir.mkdir(parents=True, exist_ok=True)
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")

    for _, row in active_sessions.iterrows():
        prefix = row["session_prefix"]
        
        # Locate V1 or other visual TFR file for this session prefix
        tfr_files = list(TFR_DIR.glob(f"{prefix}-*-V1-{CONDITION}.npy"))
        if not tfr_files:
            # Fall back to any visual area (V2, V4, MT, etc.)
            for area_lbl in ["V2", "V4", "MT", "TEO", "FEF", "PFC"]:
                tfr_files = list(TFR_DIR.glob(f"{prefix}-*-{area_lbl}-{CONDITION}.npy"))
                if tfr_files:
                    break
                    
        if not tfr_files:
            print(f"Skipping {prefix}: no matching TFR arrays found for {CONDITION}.")
            continue
            
        tfr_path = tfr_files[0]
        match = TFR_FILE_RE.match(tfr_path.name)
        if not match:
            continue
            
        probe_letter = match.group("probe")
        area = match.group("area")
        
        print(f"Processing {prefix} — Area: {area}, Probe: {probe_letter} using file {tfr_path.name}")
        
        try:
            # Shape: (n_trials, n_channels, n_freqs, n_times)
            arr = np.load(tfr_path, mmap_mode="r")
            
            # Trial + channel mean
            mean_power = np.mean(arr, axis=(0, 1)) # (n_freqs, n_times)
            
            # Baseline dB normalization against pre-stimulus [-500, 0] ms (first 20 time bins)
            baseline = np.mean(mean_power[:, :20], axis=1, keepdims=True)
            mean_db = mean_power - baseline
            
            n_freqs, n_times = mean_db.shape
            freqs = np.arange(3, 201, 2) if n_freqs == 99 else np.linspace(3, 201, n_freqs)
            times = (-1000.0 + np.arange(n_times) * 10.0) if n_times == 500 else np.linspace(-1000, 2000, n_times)
            
            # Calculate pixel-wise t-statistic and p-value against 0
            trial_channel_db = arr - np.mean(arr[:, :, :, :20], axis=3, keepdims=True)
            flat_trials = trial_channel_db.reshape(-1, n_freqs, n_times)
            
            t_stats, p_vals = ttest_1samp(flat_trials, 0, axis=0)
            sig_mask = p_vals < 0.05
            
            fig, ax = plt.subplots(figsize=(10, 6))
            vmax = np.percentile(np.abs(mean_db), 98)
            im = ax.pcolormesh(times, freqs, mean_db, shading="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
            
            # Draw contours around significant regions
            ax.contour(times, freqs, sig_mask, levels=[0.5], colors="black", linewidths=0.8, linestyles="--")
            
            # Timeline decorators
            for t_val in [0.0, 1031.0, 2062.0, 3093.0]:
                if times[0] <= t_val <= times[-1]:
                    ax.axvline(t_val, color="black", linestyle=":", linewidth=0.8, alpha=0.5)
                    
            ax.set_title(f"Suite 03: 2D Spectrogram — {prefix} {area} ({CONDITION}) with Sig Outlines", fontsize=12, fontweight="bold")
            ax.set_xlabel("Time from trial onset (ms)")
            ax.set_ylabel("Frequency (Hz)")
            fig.colorbar(im, label="Power (dB)")
            
            svg_path = out_dir / f"{prefix}_suite_03_tfr_heatmap_{dt_suffix}.svg"
            fig.savefig(svg_path, bbox_inches="tight")
            plt.close(fig)
            print(f"Saved {svg_path}")
        except Exception as e:
            print(f"Error processing {tfr_path.name}: {e}")

if __name__ == "__main__":
    main()
