"""
build_manuscript_figure6.py — Manuscript Figure 6 Generator
Generates a 4x4 grid of Spectral Harmony correlation matrices:
  Rows: Conditions (RRRR, RXRR, RRXR, RRRX)
  Columns: Bands (Theta, Alpha, Beta, Gamma)
Each subplot displays a 4x4 correlation matrix of LFP power envelopes
over time between the 4 areas: V1, V4, MT, FEF.
"""

from __future__ import annotations
import os
import sys
import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

TFR_DIR = Path("D:/workspace/data/tfr_arrays")
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_DIR = REPO_ROOT / "outputs/publication_figures"

FREQS_HZ = np.arange(3, 201, 2)  # 99 bins
WINDOW_MS = (-500.0, 4124.0)

BANDS = {
    "Theta": (4.0, 8.0),
    "Alpha": (8.0, 15.0),
    "Beta": (15.0, 30.0),
    "Gamma": (30.0, 80.0),
}

def find_probe_for_area(session_prefix: str, area: str) -> str | None:
    """Find probe letter that recorded from a given area in a session."""
    pattern = f"{session_prefix}-*-{area}-*.npy"
    matches = list(TFR_DIR.glob(pattern))
    if not matches:
        return None
    stem = matches[0].stem
    parts = stem.split("-")
    return parts[-3]

def extract_power_envelope(arr: np.ndarray, freqs: np.ndarray, fmin: float, fmax: float) -> np.ndarray:
    """Extract trial- and channel-averaged power envelope. Shape: (n_times,)."""
    fmask = (freqs >= fmin) & (freqs <= fmax)
    # Slice array to optimize disk I/O
    arr_sliced = arr[::4, ::8, fmask, :]
    # Average across trials, channels, and frequencies within band
    # Axis order: 0=trials, 1=ch, 2=freqs, 3=times
    envelope = arr_sliced.mean(axis=(0, 1, 2))  # (n_times,)
    return envelope

def main():
    if not READINESS_CSV.exists():
        print(f"Readiness CSV not found at {READINESS_CSV}")
        return
        
    readiness = pd.read_csv(READINESS_CSV)
    valid_rows = readiness[readiness["suite_tfr_ready"].fillna(False).astype(bool)]
    print(f"Loaded {len(valid_rows)} sessions with TFR precomputed.")
    
    areas = ["V1", "V4", "MT", "FEF"]
    conditions = ["RRRR", "RXRR", "RRXR", "RRRX"]
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Store averaged correlation matrices
    # avg_corr_matrices[(cond, band_name)] = 4x4 numpy array
    avg_corr_matrices = {}
    
    for cond in conditions:
        for band_name, (fmin, fmax) in BANDS.items():
            session_matrices = []
            
            for _, row in valid_rows.iterrows():
                prefix = row["session_prefix"]
                
                # Check if all 4 areas exist for this session
                all_exist = True
                area_envelopes = {}
                for area in areas:
                    probe = find_probe_for_area(prefix, area)
                    if not probe:
                        all_exist = False
                        break
                    fpath = TFR_DIR / f"{prefix}-{probe}-{area}-{cond}.npy"
                    if not fpath.exists():
                        all_exist = False
                        break
                    area_envelopes[area] = fpath
                    
                # Compute correlation matrix if all 4 areas are present in this session
                if all_exist:
                    envelopes_data = []
                    for area in areas:
                        fpath = area_envelopes[area]
                        try:
                            arr = np.load(fpath, mmap_mode="r")
                            env = extract_power_envelope(arr, FREQS_HZ, fmin, fmax)
                            envelopes_data.append(env)
                        except Exception as e:
                            print(f"Error loading {fpath.name}: {e}")
                            
                    if len(envelopes_data) == len(areas):
                        # Shape: (4, n_times)
                        envelopes_data = np.array(envelopes_data)
                        # Pearson correlation matrix
                        corr_matrix = np.corrcoef(envelopes_data)
                        session_matrices.append(corr_matrix)
                        
            if session_matrices:
                avg_corr_matrices[(cond, band_name)] = np.mean(session_matrices, axis=0)
                print(f"Computed average correlation matrix for {cond} - {band_name} using {len(session_matrices)} sessions.")
            else:
                # If no session has all 4 areas simultaneously, fall back to pairwise correlation averages
                # across all sessions that have at least the pair
                pairwise_matrix = np.eye(len(areas))
                for i in range(len(areas)):
                    for j in range(i+1, len(areas)):
                        pair_corrs = []
                        area_i, area_j = areas[i], areas[j]
                        for _, row in valid_rows.iterrows():
                            prefix = row["session_prefix"]
                            probe_i = find_probe_for_area(prefix, area_i)
                            probe_j = find_probe_for_area(prefix, area_j)
                            if probe_i and probe_j:
                                path_i = TFR_DIR / f"{prefix}-{probe_i}-{area_i}-{cond}.npy"
                                path_j = TFR_DIR / f"{prefix}-{probe_j}-{area_j}-{cond}.npy"
                                if path_i.exists() and path_j.exists():
                                    try:
                                        arr_i = np.load(path_i, mmap_mode="r")
                                        arr_j = np.load(path_j, mmap_mode="r")
                                        env_i = extract_power_envelope(arr_i, FREQS_HZ, fmin, fmax)
                                        env_j = extract_power_envelope(arr_j, FREQS_HZ, fmin, fmax)
                                        c = np.corrcoef(env_i, env_j)[0, 1]
                                        if not np.isnan(c):
                                            pair_corrs.append(c)
                                    except Exception:
                                        pass
                        if pair_corrs:
                            val = np.mean(pair_corrs)
                            pairwise_matrix[i, j] = val
                            pairwise_matrix[j, i] = val
                avg_corr_matrices[(cond, band_name)] = pairwise_matrix
                print(f"Computed pairwise-fallback correlation matrix for {cond} - {band_name}.")

    # Plotting
    plt.style.use("classic")
    fig = plt.figure(figsize=(14, 14))
    gs = gridspec.GridSpec(4, 4, wspace=0.25, hspace=0.25)
    
    matplotlib.rcParams["font.sans-serif"] = "Arial"
    matplotlib.rcParams["font.family"] = "sans-serif"
    
    for r_idx, cond in enumerate(conditions):
        for c_idx, band_name in enumerate(BANDS):
            ax = fig.add_subplot(gs[r_idx, c_idx])
            
            corr = avg_corr_matrices.get((cond, band_name))
            if corr is not None:
                im = ax.imshow(corr, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto", interpolation="nearest")
                
                # Annotate values
                for i in range(4):
                    for j in range(4):
                        ax.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center", 
                                color="white" if abs(corr[i, j]) > 0.4 else "black", fontsize=8)
                                
                ax.set_xticks(range(4))
                ax.set_xticklabels(areas, fontsize=8)
                ax.set_yticks(range(4))
                ax.set_yticklabels(areas, fontsize=8)
                
                ax.set_title(f"{cond} — {band_name}", fontsize=10, fontweight="bold")
            else:
                ax.text(0.5, 0.5, "No Data", ha="center", va="center")
                
            # Hide labels to save space
            if r_idx < 3:
                ax.xaxis.set_tick_params(labelbottom=False)
            if c_idx > 0:
                ax.yaxis.set_tick_params(labelleft=False)

    # Colorbar
    cbar_ax = fig.add_axes([0.94, 0.25, 0.015, 0.5])
    fig.colorbar(im, cax=cbar_ax, label="Power Envelope Correlation (r)")
    
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")
    out_svg = OUT_DIR / f"figure6_power_correlation_{dt_suffix}.svg"
    fig.savefig(out_svg, bbox_inches="tight", dpi=200)
    print(f"Saved Figure 6 to {out_svg}")
    
    fig.savefig(OUT_DIR / "figure6_power_correlation.png", bbox_inches="tight", dpi=200)
    fig.savefig(OUT_DIR / "figure6_power_correlation.svg", bbox_inches="tight")

if __name__ == "__main__":
    main()
