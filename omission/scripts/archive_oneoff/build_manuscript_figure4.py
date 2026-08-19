"""
build_manuscript_figure4.py — Manuscript Figure 4 Generator
Generates a 2x2 grid of time-frequency spectrogram heatmaps:
  Row 0: V1 (RRRR left, RXRR right)
  Row 1: FEF (RRRR left, RXRR right)
Averaged across all valid sessions where suite_tfr_ready = True.
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
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS

TFR_DIR = Path("D:/workspace/data/tfr_arrays")
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_DIR = REPO_ROOT / "outputs/publication_figures"

FREQS_HZ = np.arange(3, 201, 2)  # 99 bins
WINDOW_MS = (-500.0, 4124.0)
BASELINE_END_MS = -400.0

EPOCH_LABELS = list(EPOCH_ONSETS_MS.keys())
EPOCH_TIMES_MS = list(EPOCH_ONSETS_MS.values()) + [WINDOW_MS[1]]
EPOCH_SHADE = {"p1": "#fcee21", "p2": "#93278f", "p3": "#019147", "p4": "#000bd4"}
EPOCH_SHADE_ALPHA = 0.10

def find_probe_for_area(session_prefix: str, area: str) -> str | None:
    """Find probe letter that recorded from a given area in a session."""
    pattern = f"{session_prefix}-*-{area}-*.npy"
    matches = list(TFR_DIR.glob(pattern))
    if not matches:
        return None
    stem = matches[0].stem
    parts = stem.split("-")
    return parts[-3]

def db_normalize(arr: np.ndarray, times_ms: np.ndarray) -> np.ndarray:
    """dB normalize arr shape (n_freqs, n_times) relative to baseline < -400ms."""
    baseline_mask = times_ms < BASELINE_END_MS
    if baseline_mask.sum() == 0:
        return arr
    baseline = arr[:, baseline_mask].mean(axis=1, keepdims=True)
    baseline = np.where(baseline == 0, 1e-12, baseline)
    return 10.0 * np.log10(arr / baseline)

def main():
    if not READINESS_CSV.exists():
        print(f"Readiness CSV not found at {READINESS_CSV}")
        return
        
    readiness = pd.read_csv(READINESS_CSV)
    # Filter sessions where suite_tfr_ready = True
    valid_rows = readiness[readiness["suite_tfr_ready"].fillna(False).astype(bool)]
    print(f"Loaded {len(valid_rows)} sessions with TFR precomputed.")
    
    areas = ["V1", "FEF"]
    conditions = ["RRRR", "RXRR"]
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load and average spectrograms per (area, condition)
    avg_spectrograms = {}
    times_ms = np.linspace(WINDOW_MS[0], WINDOW_MS[1], 500)
    
    for area in areas:
        for cond in conditions:
            specs = []
            for _, row in valid_rows.iterrows():
                prefix = row["session_prefix"]
                probe = find_probe_for_area(prefix, area)
                if not probe:
                    continue
                fpath = TFR_DIR / f"{prefix}-{probe}-{area}-{cond}.npy"
                if fpath.exists():
                    try:
                        arr = np.load(fpath, mmap_mode="r")  # (n_trials, n_ch, n_freqs, n_times)
                        # Slice array to optimize disk I/O (downsample trials and channels)
                        arr_sliced = arr[::4, ::8, :, :]
                        # Average over trials and channels
                        arr_mean = arr_sliced.mean(axis=(0, 1))  # (n_freqs, n_times)
                        # Normalize
                        arr_db = db_normalize(arr_mean, times_ms)
                        specs.append(arr_db)
                    except Exception as e:
                        print(f"Error loading {fpath.name}: {e}")
            if specs:
                avg_spectrograms[(area, cond)] = np.mean(specs, axis=0)
                print(f"Computed average spectrogram for {area} - {cond} using {len(specs)} sessions.")
            else:
                print(f"No TFR data found for {area} - {cond}")
                
    # Plotting
    plt.style.use("classic")
    fig = plt.figure(figsize=(10, 8))
    gs = gridspec.GridSpec(2, 2, wspace=0.15, hspace=0.22)
    
    # Enable transparency and sans-serif fonts
    matplotlib.rcParams["font.sans-serif"] = "Arial"
    matplotlib.rcParams["font.family"] = "sans-serif"
    
    axs = {}
    for r_idx, area in enumerate(areas):
        for c_idx, cond in enumerate(conditions):
            ax = fig.add_subplot(gs[r_idx, c_idx])
            axs[(area, cond)] = ax
            
            arr_db = avg_spectrograms.get((area, cond))
            if arr_db is not None:
                extent = [times_ms[0], times_ms[-1], FREQS_HZ[-1], FREQS_HZ[0]]
                im = ax.imshow(arr_db, aspect="auto", cmap="RdBu_r",
                               vmin=-2.0, vmax=2.0, extent=extent, origin="upper",
                               interpolation="nearest")
                
                # Setup y-axis log-like ticks
                ax.set_yscale("log")
                ax.yaxis.set_major_formatter(mticker.FuncFormatter(
                    lambda y, _: f"{int(y)}" if y in (4, 8, 15, 30, 80, 150) else ""))
                ax.set_yticks([4, 8, 15, 30, 80, 150])
                
                ax.set_xlim(WINDOW_MS[0], WINDOW_MS[1])
                ax.set_title(f"{area} — {cond}", fontsize=11, fontweight="bold")
                
                # Draw epoch shading
                omit_slot = "p2" if cond == "RXRR" else None
                for label, t_start in EPOCH_ONSETS_MS.items():
                    idx = EPOCH_LABELS.index(label)
                    t_stop = EPOCH_TIMES_MS[idx + 1]
                    if label in EPOCH_SHADE:
                        ax.axvspan(t_start, t_stop, color=EPOCH_SHADE[label],
                                   alpha=EPOCH_SHADE_ALPHA, zorder=0, linewidth=0)
                        # Mark omitted slot
                        if label == omit_slot:
                            t_mid = (t_start + t_stop) / 2
                            ax.axvline(t_mid, color="white", linewidth=1.5, linestyle="--", alpha=0.8, zorder=2)
                            ax.text(t_mid, FREQS_HZ[0] * 1.5, "X", ha="center", va="bottom", color="white",
                                    fontsize=10, fontweight="bold", zorder=3)
                                    
                # Add grid lines
                for t_ms in EPOCH_TIMES_MS[:-1]:
                    ax.axvline(t_ms, color="gray", linewidth=0.4, linestyle=":", alpha=0.5, zorder=1)
            else:
                ax.text(0.5, 0.5, "No Data", ha="center", va="center")
                
            # Hide labels to save space
            if r_idx == 0:
                ax.xaxis.set_tick_params(labelbottom=False)
            else:
                ax.set_xlabel("Time (ms)", fontsize=9)
            if c_idx == 1:
                ax.yaxis.set_tick_params(labelleft=False)
            else:
                ax.set_ylabel("Frequency (Hz)", fontsize=9)
                
    # Add a single colorbar
    cbar_ax = fig.add_axes([0.92, 0.25, 0.02, 0.5])
    fig.colorbar(im, cax=cbar_ax, label="Power Change (dB)")
    
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")
    out_svg = OUT_DIR / f"figure4_tfr_spectrograms_{dt_suffix}.svg"
    fig.savefig(out_svg, bbox_inches="tight", dpi=200)
    print(f"Saved Figure 4 to {out_svg}")
    
    # Save standard name alias as well for easy access
    fig.savefig(OUT_DIR / "figure4_tfr_spectrograms.png", bbox_inches="tight", dpi=200)
    fig.savefig(OUT_DIR / "figure4_tfr_spectrograms.svg", bbox_inches="tight")

if __name__ == "__main__":
    main()
