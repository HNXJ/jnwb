"""
suite_07_rsa_spk_lfp.py — RSA of Spiking to LFP TFR
Loops through all valid TFR-ready sessions, generates representational similarity matrices
for LFP power matrices and population spike rates, and runs a Mantel test.
Usage:
  python scripts/suite_07_rsa_spk_lfp.py
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
from scipy.spatial.distance import pdist, squareform
from scipy.stats import pearsonr

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
import jnwb as oa

TFR_DIR = Path(os.environ.get("OMISSION_TFR_DIR", "D:/workspace/data/tfr_arrays"))
READY_CSV = Path("artifacts/data/session_readiness.csv")
CONDITION = "AAAB"

TFR_FILE_RE = re.compile(
    r"^(?P<prefix>sub-[^-]+_ses-[^-]+)-(?P<probe>[A-Z])-(?P<area>[A-Z0-9a-z]+)-(?P<cond>[A-Z0-9]+)\.npy$"
)

def mantel_test(m1: np.ndarray, m2: np.ndarray, n_perm: int = 1000) -> tuple[float, float]:
    v1 = m1[np.tril_indices(len(m1), k=-1)]
    v2 = m2[np.tril_indices(len(m2), k=-1)]
    r_obs, _ = pearsonr(v1, v2)
    
    n_ge = 0
    shuffled_m2 = m2.copy()
    idx = np.arange(len(m2))
    
    for _ in range(n_perm):
        np.random.shuffle(idx)
        shuffled_m2 = shuffled_m2[idx, :][:, idx]
        v2_perm = shuffled_m2[np.tril_indices(len(m2), k=-1)]
        r_perm, _ = pearsonr(v1, v2_perm)
        if abs(r_perm) >= abs(r_obs):
            n_ge += 1
            
    p_val = (n_ge + 1) / (n_perm + 1)
    return r_obs, p_val

def main():
    if not READY_CSV.exists() or not TFR_DIR.exists():
        print("Required catalog or TFR directory does not exist.")
        return
        
    readiness = pd.read_csv(READY_CSV)
    active_sessions = readiness[readiness["nwb_ok"].astype(bool) & readiness["sidecar_ok"].astype(bool) & readiness["suite_tfr_ready"].astype(bool)]
    print(f"Looping over {len(active_sessions)} valid TFR sessions...")
    
    out_dir = REPO_ROOT / "outputs/publication_figures/suite_rsa"
    out_dir.mkdir(parents=True, exist_ok=True)
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")

    for _, row in active_sessions.iterrows():
        prefix = row["session_prefix"]
        path = row["nwb_path"]
        
        # Find visual areas TFR files
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
            sess = oa.read(path)
            tfr_arr = np.load(tfr_path, mmap_mode="r")
            n_trials = tfr_arr.shape[0]
            
            lfp_reps = tfr_arr.reshape(n_trials, -1)
            lfp_reps = lfp_reps - lfp_reps.mean(axis=1, keepdims=True)
            lfp_reps = lfp_reps / (lfp_reps.std(axis=1, keepdims=True) + 1e-8)
            
            lfp_sim = 1.0 - squareform(pdist(lfp_reps, metric="correlation"))
            
            units_df = sess.get_units(quality="stable_plus")
            n_units = len(units_df)
            
            if n_units < 5:
                # Fall back to all units if stable_plus are sparse
                units_df = sess.get_units()
                n_units = len(units_df)
                
            if n_units == 0:
                print(f"No units found in {prefix}")
                continue
                
            epochs = sess.get_epochs(phase=2, condition=CONDITION, correct_only=True)
            onsets = epochs["start_time"].values[:n_trials]
            
            spk_reps = np.zeros((n_trials, n_units))
            for ui, (row_pos, r_row) in enumerate(units_df.iterrows()):
                spike_times = sess.get_spike_times(row_pos)
                for ti, onset in enumerate(onsets):
                    n_spk = np.sum((spike_times >= onset) & (spike_times < onset + 0.531))
                    spk_reps[ti, ui] = n_spk / 0.531
                    
            spk_sim = 1.0 - squareform(pdist(spk_reps, metric="correlation"))
            
            r_obs, p_val = mantel_test(lfp_sim, spk_sim, n_perm=500)
            print(f"{prefix} Mantel test correlation: r={r_obs:.4f}, p={p_val:.4g}")
            
            fig, axes = plt.subplots(1, 2, figsize=(14, 6))
            
            im1 = axes[0].imshow(lfp_sim, cmap="viridis", origin="lower")
            axes[0].set_title(f"LFP Spectrogram Similarity — {area}", fontsize=11, fontweight="bold")
            fig.colorbar(im1, ax=axes[0], label="Correlation")
            
            im2 = axes[1].imshow(spk_sim, cmap="viridis", origin="lower")
            axes[1].set_title(f"Spike Population Similarity\nMantel r={r_obs:.3f}, p={p_val:.2e}", fontsize=11, fontweight="bold")
            fig.colorbar(im2, ax=axes[1], label="Correlation")
            
            fig.suptitle(f"Suite 07: Representational Similarity Analysis (RSA) — {prefix} {area} ({CONDITION})", fontsize=13, fontweight="bold", y=1.02)
            plt.tight_layout()
            
            svg_path = out_dir / f"{prefix}_suite_07_rsa_spk_lfp_{dt_suffix}.svg"
            fig.savefig(svg_path, bbox_inches="tight")
            plt.close(fig)
            print(f"Saved {svg_path}")
            
            if prefix == "sub-C31o_ses-230823":
                legacy_path = out_dir / f"suite_07_rsa_spk_lfp_{dt_suffix}.svg"
                fig.savefig(legacy_path, bbox_inches="tight")
                
        except Exception as e:
            print(f"Error processing RSA for {prefix}: {e}")

if __name__ == "__main__":
    main()
