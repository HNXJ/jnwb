"""
build_granger_connectivity_grid.py — Directional Spectral Granger Causality Network Grid
Computes directional Granger causality (A -> B vs B -> A) between V1, V4, MT, FEF
using canonical jrsa(target, driver, metric="granger") engine.
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

from jnwb.jrsa import jrsa

TFR_DIR = Path("D:/workspace/data/tfr_arrays")
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_DIR = REPO_ROOT / "outputs/publication_figures"

WINDOW_MS = (-500.0, 4124.0)

def find_probe_for_area(session_prefix: str, area: str) -> str | None:
    """Find probe letter that recorded from a given area in a session."""
    pattern = f"{session_prefix}-*-{area}-*.npy"
    matches = list(TFR_DIR.glob(pattern))
    if not matches:
        return None
    stem = matches[0].stem
    parts = stem.split("-")
    return parts[-3]

def extract_overall_trace(arr: np.ndarray) -> np.ndarray:
    """Extract trial- and channel- and frequency-averaged trace. Shape: (n_times,)."""
    # Slice to speed up mmap reads
    arr_sliced = arr[::4, ::8, :, :]
    return arr_sliced.mean(axis=(0, 1, 2))

def main():
    if not READINESS_CSV.exists():
        print(f"Readiness CSV not found at {READINESS_CSV}")
        return
        
    readiness = pd.read_csv(READINESS_CSV)
    valid_rows = readiness[readiness["suite_tfr_ready"].fillna(False).astype(bool)]
    print(f"Loaded {len(valid_rows)} sessions with TFR precomputed.")
    
    areas = ["V1", "V4", "MT", "FEF"]
    conditions = ["RRRR", "RXRR"]
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Store directional influence matrices
    # di_matrices[cond] = 4x4 matrix where entry [i, j] is directionality index A_i -> A_j
    di_matrices = {}
    
    for cond in conditions:
        matrix = np.zeros((4, 4))
        count_matrix = np.zeros((4, 4))
        
        for i, area_a in enumerate(areas):
            for j, area_b in enumerate(areas):
                if i == j:
                    continue
                
                gc_values = []
                for _, row in valid_rows.iterrows():
                    prefix = row["session_prefix"]
                    probe_a = find_probe_for_area(prefix, area_a)
                    probe_b = find_probe_for_area(prefix, area_b)
                    
                    if probe_a and probe_b:
                        path_a = TFR_DIR / f"{prefix}-{probe_a}-{area_a}-{cond}.npy"
                        path_b = TFR_DIR / f"{prefix}-{probe_b}-{area_b}-{cond}.npy"
                        
                        if path_a.exists() and path_b.exists():
                            try:
                                arr_a = np.load(path_a, mmap_mode="r")
                                arr_b = np.load(path_b, mmap_mode="r")
                                
                                trace_a = extract_overall_trace(arr_a)
                                trace_b = extract_overall_trace(arr_b)
                                
                                # Compute Granger: jrsa(target, driver, metric="granger")
                                res_a_to_b = jrsa(trace_b, trace_a, metric="granger")
                                res_b_to_a = jrsa(trace_a, trace_b, metric="granger")
                                
                                val_a_to_b = res_a_to_b.statistic if hasattr(res_a_to_b, "statistic") else res_a_to_b.value
                                val_b_to_a = res_b_to_a.statistic if hasattr(res_b_to_a, "statistic") else res_b_to_a.value
                                
                                # Directionality index: positive = A drives B
                                di = val_a_to_b - val_b_to_a
                                if not np.isnan(di):
                                    gc_values.append(di)
                            except Exception as e:
                                pass
                                
                if gc_values:
                    matrix[i, j] = np.mean(gc_values)
                    count_matrix[i, j] = len(gc_values)
                    
        di_matrices[cond] = matrix
        print(f"Computed Granger Directionality matrix for condition {cond}.")

    # Plotting
    plt.style.use("classic")
    fig = plt.figure(figsize=(10, 4.5))
    gs = gridspec.GridSpec(1, 2, wspace=0.25)
    
    matplotlib.rcParams["font.sans-serif"] = "Arial"
    matplotlib.rcParams["font.family"] = "sans-serif"
    
    for c_idx, cond in enumerate(conditions):
        ax = fig.add_subplot(gs[0, c_idx])
        matrix = di_matrices.get(cond, np.zeros((4, 4)))
        
        im = ax.imshow(matrix, cmap="PuOr", vmin=-0.5, vmax=0.5, aspect="auto", interpolation="nearest")
        
        for i in range(4):
            for j in range(4):
                if i != j:
                    ax.text(j, i, f"{matrix[i, j]:+.2f}", ha="center", va="center",
                            color="white" if abs(matrix[i, j]) > 0.25 else "black", fontsize=9)
                            
        ax.set_xticks(range(4))
        ax.set_xticklabels(areas, fontsize=9)
        ax.set_yticks(range(4))
        ax.set_yticklabels(areas, fontsize=9)
        ax.set_title(f"Granger Directionality Index — {cond}\n(+ Row drives Column)", fontsize=10, fontweight="bold")
        
    cbar_ax = fig.add_axes([0.93, 0.2, 0.02, 0.6])
    fig.colorbar(im, cax=cbar_ax, label="Directionality Index (A -> B net Granger)")
    
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")
    out_svg = OUT_DIR / f"figure8_granger_connectivity_grid_{dt_suffix}.svg"
    fig.savefig(out_svg, bbox_inches="tight", dpi=200)
    print(f"Saved Granger Connectivity Grid to {out_svg}")
    
    fig.savefig(OUT_DIR / "figure8_granger_connectivity_grid.png", bbox_inches="tight", dpi=200)
    fig.savefig(OUT_DIR / "figure8_granger_connectivity_grid.svg", bbox_inches="tight")

if __name__ == "__main__":
    main()
