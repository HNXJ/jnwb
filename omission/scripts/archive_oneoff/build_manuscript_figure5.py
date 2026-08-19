"""
build_manuscript_figure5.py — Manuscript Figure 5 Generator
Generates a 4x2 grid of 1D band traces showing power changes over time:
  Rows: V1, V4, MT, FEF
  Columns: RRRR, RXRR
Traces plotted for 5 bands: Theta, Alpha, Beta, Low Gamma, High Gamma.
Shaded regions show +/- SEM across sessions.
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
from scipy.ndimage import gaussian_filter1d

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS

TFR_DIR = Path("D:/workspace/data/tfr_arrays")
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_DIR = REPO_ROOT / "outputs/publication_figures"

FREQS_HZ = np.arange(3, 201, 2)  # 99 bins
WINDOW_MS = (-500.0, 4124.0)
BASELINE_END_MS = -400.0

BANDS = {
    "Theta": (4.0, 8.0),
    "Alpha": (8.0, 15.0),
    "Beta": (15.0, 30.0),
    "Low Gamma": (30.0, 60.0),
    "High Gamma": (60.0, 120.0),
}
BAND_COLORS = {
    "Theta": "#E5A93C",      # Gold
    "Alpha": "#2274A5",      # Blue
    "Beta": "#7D5BA6",       # Violet
    "Low Gamma": "#4F8F00",  # Green
    "High Gamma": "#7E8082", # Gray
}

EPOCH_LABELS = list(EPOCH_ONSETS_MS.keys())
EPOCH_TIMES_MS = list(EPOCH_ONSETS_MS.values()) + [WINDOW_MS[1]]
EPOCH_SHADE = {"p1": "#fcee21", "p2": "#93278f", "p3": "#019147", "p4": "#000bd4"}
EPOCH_SHADE_ALPHA = 0.08

def find_probe_for_area(session_prefix: str, area: str) -> str | None:
    """Find probe letter that recorded from a given area in a session."""
    pattern = f"{session_prefix}-*-{area}-*.npy"
    matches = list(TFR_DIR.glob(pattern))
    if not matches:
        return None
    stem = matches[0].stem
    parts = stem.split("-")
    return parts[-3]

def extract_band_trace_db(arr: np.ndarray, freqs: np.ndarray, fmin: float, fmax: float, times_ms: np.ndarray) -> np.ndarray:
    """Extract trial-averaged, dB-normalized trace for a specific frequency band."""
    fmask = (freqs >= fmin) & (freqs <= fmax)
    # Slice array to optimize disk I/O
    arr_sliced = arr[::4, ::8, fmask, :]
    # Average across channels and frequencies within the band
    trace_ch_fr = arr_sliced.mean(axis=(1, 2))  # (n_trials, n_times)
    trace_mean = trace_ch_fr.mean(axis=0)  # (n_times,)
    
    # dB normalize
    baseline_mask = times_ms < BASELINE_END_MS
    baseline = trace_mean[baseline_mask].mean()
    baseline = max(baseline, 1e-12)
    return 10.0 * np.log10(trace_mean / baseline)

def main():
    if not READINESS_CSV.exists():
        print(f"Readiness CSV not found at {READINESS_CSV}")
        return
        
    readiness = pd.read_csv(READINESS_CSV)
    valid_rows = readiness[readiness["suite_tfr_ready"].fillna(False).astype(bool)]
    print(f"Loaded {len(valid_rows)} sessions with TFR precomputed.")
    
    areas = ["V1", "V4", "MT", "FEF"]
    conditions = ["RRRR", "RXRR"]
    times_ms = np.linspace(WINDOW_MS[0], WINDOW_MS[1], 500)
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Structure: group_traces[(area, cond)][band_name] = list of 1D arrays per session
    group_traces = {}
    for area in areas:
        for cond in conditions:
            group_traces[(area, cond)] = {band: [] for band in BANDS}
            
            for _, row in valid_rows.iterrows():
                prefix = row["session_prefix"]
                probe = find_probe_for_area(prefix, area)
                if not probe:
                    continue
                fpath = TFR_DIR / f"{prefix}-{probe}-{area}-{cond}.npy"
                if fpath.exists():
                    try:
                        arr = np.load(fpath, mmap_mode="r")  # (n_trials, n_ch, n_freqs, n_times)
                        for band, (fmin, fmax) in BANDS.items():
                            trace_db = extract_band_trace_db(arr, FREQS_HZ, fmin, fmax, times_ms)
                            group_traces[(area, cond)][band].append(trace_db)
                    except Exception as e:
                        print(f"Error loading {fpath.name}: {e}")
                        
            print(f"Loaded {area} - {cond} traces for {len(group_traces[(area, cond)]['Theta'])} sessions.")

    # Plotting
    plt.style.use("classic")
    fig = plt.figure(figsize=(12, 14))
    gs = gridspec.GridSpec(4, 2, wspace=0.15, hspace=0.25)
    
    matplotlib.rcParams["font.sans-serif"] = "Arial"
    matplotlib.rcParams["font.family"] = "sans-serif"
    
    for r_idx, area in enumerate(areas):
        for c_idx, cond in enumerate(conditions):
            ax = fig.add_subplot(gs[r_idx, c_idx])
            
            for band_name, color in BAND_COLORS.items():
                traces = group_traces[(area, cond)][band_name]
                if not traces:
                    continue
                    
                traces = np.array(traces)  # (n_sessions, n_times)
                mean = traces.mean(axis=0)
                sem = traces.std(axis=0) / np.sqrt(traces.shape[0])
                
                # Causal exponential/gaussian smooth
                mean_smooth = gaussian_filter1d(mean, sigma=2.0)
                sem_smooth = gaussian_filter1d(sem, sigma=2.0)
                
                ax.plot(times_ms, mean_smooth, color=color, linewidth=1.3, label=band_name, zorder=3)
                ax.fill_between(times_ms, mean_smooth - sem_smooth, mean_smooth + sem_smooth,
                                color=color, alpha=0.15, zorder=2)
                                
            ax.set_xlim(WINDOW_MS[0], WINDOW_MS[1])
            ax.set_ylim(-3.5, 3.5)
            ax.axhline(0, color="gray", linewidth=0.5, linestyle="-", alpha=0.5, zorder=1)
            ax.set_title(f"{area} — {cond}", fontsize=11, fontweight="bold")
            
            # Draw epoch shading
            omit_slot = "p2" if cond == "RXRR" else None
            for label, t_start in EPOCH_ONSETS_MS.items():
                idx = EPOCH_LABELS.index(label)
                t_stop = EPOCH_TIMES_MS[idx + 1]
                if label in EPOCH_SHADE:
                    ax.axvspan(t_start, t_stop, color=EPOCH_SHADE[label],
                               alpha=EPOCH_SHADE_ALPHA, zorder=0, linewidth=0)
                    if label == omit_slot:
                        t_mid = (t_start + t_stop) / 2
                        ax.axvline(t_mid, color="red", linewidth=1.0, linestyle="--", alpha=0.8, zorder=2)
                        
            # Grid
            for t_ms in EPOCH_TIMES_MS[:-1]:
                ax.axvline(t_ms, color="gray", linewidth=0.4, linestyle=":", alpha=0.5, zorder=1)
                
            # Hide labels
            if r_idx < 3:
                ax.xaxis.set_tick_params(labelbottom=False)
            else:
                ax.set_xlabel("Time (ms)", fontsize=9)
            if c_idx == 1:
                ax.yaxis.set_tick_params(labelleft=False)
            else:
                ax.set_ylabel("Power Change (dB)", fontsize=9)
                
            if r_idx == 0 and c_idx == 0:
                ax.legend(loc="upper right", fontsize=8, framealpha=0.7)
                
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")
    out_svg = OUT_DIR / f"figure5_band_traces_{dt_suffix}.svg"
    fig.savefig(out_svg, bbox_inches="tight", dpi=200)
    print(f"Saved Figure 5 to {out_svg}")
    
    fig.savefig(OUT_DIR / "figure5_band_traces.png", bbox_inches="tight", dpi=200)
    fig.savefig(OUT_DIR / "figure5_band_traces.svg", bbox_inches="tight")

if __name__ == "__main__":
    main()
