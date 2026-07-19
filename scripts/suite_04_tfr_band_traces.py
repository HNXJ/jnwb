"""
suite_04_tfr_band_traces.py — 1D TFR Band Power Traces with SEM
Loops through all valid TFR sessions dynamically, resolves available visual/frontal
TFR files, and generates 1D Theta/Alpha/Beta/Gamma/High-Gamma power traces with SEM and sig markers.
Usage:
  python scripts/suite_04_tfr_band_traces.py
"""

from __future__ import annotations
import os
import sys
import re
from pathlib import Path
import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import ttest_1samp

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
import jnwb as oa

TFR_DIR = Path(os.environ.get("OMISSION_TFR_DIR", "D:/workspace/data/tfr_arrays"))
READY_CSV = Path("artifacts/data/session_readiness.csv")
CONDITION = "AAAB"

BANDS = {
    "Theta": (4.0, 8.0),
    "Alpha": (8.0, 15.0),
    "Beta": (15.0, 30.0),
    "Gamma": (30.0, 80.0),
    "High-Gamma": (80.0, 150.0),
}
BAND_COLORS = {
    "Theta": "#4477AA",
    "Alpha": "#EE6677",
    "Beta": "#228833",
    "Gamma": "#CCBB44",
    "High-Gamma": "#AA3377",
}

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
            arr = np.load(tfr_path, mmap_mode="r")
            n_trials, n_channels, n_freqs, n_times = arr.shape
            
            freqs = np.arange(3, 201, 2) if n_freqs == 99 else np.linspace(3, 201, n_freqs)
            times = (-1000.0 + np.arange(n_times) * 10.0) if n_times == 500 else np.linspace(-1000, 2000, n_times)
            
            trial_channel_db = arr - np.mean(arr[:, :, :, :20], axis=3, keepdims=True)
            obs_db = trial_channel_db.reshape(-1, n_freqs, n_times)
            n_obs = obs_db.shape[0]
            
            fig, ax = plt.subplots(figsize=(12, 7))
            
            for band_name, (fmin, fmax) in BANDS.items():
                fmask = (freqs >= fmin) & (freqs <= fmax)
                if fmask.sum() == 0:
                    continue
                    
                obs_band_traces = obs_db[:, fmask, :].mean(axis=1)
                mean_trace = obs_band_traces.mean(axis=0)
                sem_trace = obs_band_traces.std(axis=0) / np.sqrt(n_obs)
                
                ax.plot(times, mean_trace, color=BAND_COLORS[band_name], label=band_name, linewidth=1.5)
                ax.fill_between(times, mean_trace - sem_trace, mean_trace + sem_trace, color=BAND_COLORS[band_name], alpha=0.15)
                
                t_stats, p_vals = ttest_1samp(obs_band_traces, 0, axis=0)
                sig_times = times[p_vals < 0.05]
                if len(sig_times) > 0:
                    ax.plot(sig_times, np.full_like(sig_times, -1.8 - 0.2 * list(BANDS.keys()).index(band_name)), "|", color=BAND_COLORS[band_name], alpha=0.6, markersize=3)
                    
            for t_val in [0.0, 1031.0, 2062.0, 3093.0]:
                if times[0] <= t_val <= times[-1]:
                    ax.axvline(t_val, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
                    
            ax.set_title(f"Suite 04: Band-Decomposed 1D Power Traces — {prefix} {area} ({CONDITION})", fontsize=12, fontweight="bold")
            ax.set_xlabel("Time from trial onset (ms)")
            ax.set_ylabel("Power relative to baseline (dB)")
            ax.legend(loc="upper right")
            ax.grid(True, linestyle=":", alpha=0.5)
            
            svg_path = out_dir / f"{prefix}_suite_04_tfr_band_traces_{dt_suffix}.svg"
            fig.savefig(svg_path, bbox_inches="tight")
            plt.close(fig)
            print(f"Saved {svg_path}")
        except Exception as e:
            print(f"Error processing {tfr_path.name}: {e}")

if __name__ == "__main__":
    main()
