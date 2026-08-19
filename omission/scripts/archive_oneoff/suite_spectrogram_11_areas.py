"""
Spectrogram across 11 brain areas:
Generates 12-condition average spectrogram plots across the 11 canonical areas.
Loops through all valid TFR-ready sessions, maps target visual/frontal areas dynamically,
and outputs panel spectrograms per session prefix.
Usage:
  python scripts/suite_spectrogram_11_areas.py
"""

from __future__ import annotations
import os
import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
import omission as oa

TFR_DIR = Path(os.environ.get("OMISSION_TFR_DIR", "D:/workspace/data/tfr_arrays"))
READY_CSV = Path("artifacts/data/session_readiness.csv")
OUT_DIR = Path("outputs/connectivity/spectrogram_11_areas")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CANONICAL_AREAS_11 = ["V1", "V2", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]
CONDITIONS_12 = ["AAAB", "AXAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", "RRRR", "RXRR", "RRXR", "RRRX"]

def _load_readiness() -> pd.DataFrame:
    df = pd.read_csv(READY_CSV)
    return df[df["nwb_ok"].astype(bool) & df["sidecar_ok"].astype(bool) & df["suite_tfr_ready"].astype(bool)].copy()

def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    
    readiness = _load_readiness()
    print(f"TFR ready sessions: {len(readiness)}")
    
    if len(readiness) == 0:
        print("No TFR ready sessions found.")
        return
        
    summary_data = []

    for _, row in readiness.iterrows():
        prefix = row["session_prefix"]
        tfr_files = list(TFR_DIR.glob(f"{prefix}-*.npy"))
        if not tfr_files:
            continue
            
        print(f"Processing session spectrograms for: {prefix}")
        
        # Parse available areas and probes
        area_probes = {}
        for f in tfr_files:
            parts = f.stem.split("-")
            probe = parts[-3]
            area = parts[-2]
            area_probes[area] = probe
            
        # Iterate canonical areas
        for area in CANONICAL_AREAS_11:
            arr_area = area
            is_dual_v3 = False
            slice_idx = None
            
            if area not in area_probes:
                if area in ("V3d", "V3a") and "V3" in area_probes:
                    arr_area = "V3"
                    is_dual_v3 = True
                    slice_idx = 0 if area == "V3d" else 1
                else:
                    continue
                    
            probe = area_probes[arr_area]
            
            fig, axes = plt.subplots(3, 4, figsize=(18, 12), sharex=True, sharey=True)
            fig.suptitle(f"Trial-Averaged Spectrogram — {prefix} {area}", fontsize=16, fontweight="bold")
            
            for c_idx, cond in enumerate(CONDITIONS_12):
                ax = axes[c_idx // 4, c_idx % 4]
                tfr_path = TFR_DIR / f"{prefix}-{probe}-{arr_area}-{cond}.npy"
                if not tfr_path.exists():
                    ax.text(0.5, 0.5, f"{cond}\nMissing", ha="center", va="center", color="red")
                    ax.set_title(cond, fontsize=10, fontweight="bold")
                    continue
                    
                try:
                    arr = np.load(tfr_path, mmap_mode="r")
                    if is_dual_v3 and slice_idx is not None:
                        if slice_idx == 0:
                            arr = arr[:, :64, :, :]
                        else:
                            arr = arr[:, 64:128, :, :]
                            
                    mean_power = np.mean(arr, axis=(0, 1))
                    baseline = np.mean(mean_power[:, :20], axis=1, keepdims=True)
                    mean_db = mean_power - baseline
                    
                    n_freqs, n_time = mean_db.shape
                    freqs = np.arange(3, 201, 2) if n_freqs == 99 else np.linspace(1, 150, n_freqs)
                    times = (-1000.0 + np.arange(n_time) * 10.0) if n_time == 500 else np.linspace(-1000, 2000, n_time)
                    
                    vmax = np.percentile(np.abs(mean_db), 98)
                    im = ax.pcolormesh(times, freqs, mean_db, shading="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
                    
                    for t_val in [0.0, 1031.0, 2062.0, 3093.0]:
                        ax.axvline(t_val, color="white", linestyle="--", linewidth=0.8, alpha=0.6)
                        
                    ax.set_title(cond, fontsize=10, fontweight="bold")
                    if c_idx % 4 == 0:
                        ax.set_ylabel("Freq (Hz)")
                    if c_idx >= 8:
                        ax.set_xlabel("Time from p1 (ms)")
                        
                    summary_data.append({
                        "session_prefix": prefix,
                        "area": area,
                        "condition": cond,
                        "mean_db_overall": float(mean_db.mean()),
                    })
                    
                except Exception as e:
                    warnings.warn(f"Failed to process {tfr_path.name}: {e}")
                    ax.text(0.5, 0.5, f"{cond}\nError", ha="center", va="center", color="red")
                    ax.set_title(cond, fontsize=10, fontweight="bold")
                    
            plt.tight_layout(rect=[0, 0, 1, 0.96])
            fig_path = OUT_DIR / f"{prefix}_{area}_spectrogram_12_conditions.png"
            plt.savefig(fig_path, dpi=120, bbox_inches="tight")
            plt.close()
            print(f"Spectrogram saved: {fig_path}")
            
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(OUT_DIR.parent / "spectrogram_11_areas_summary.csv", index=False)
    print(f"Spectrogram summary saved: {OUT_DIR.parent / 'spectrogram_11_areas_summary.csv'}")

if __name__ == "__main__":
    main()
