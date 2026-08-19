"""
build_suite_lfp_power_traces.py — 4x4 Condition x Area LFP Power Traces Suite
Generates SVG/PNG figure suites with 4 rows (Conditions: RRRR, RXRR, RRXR, RRRX)
x 4 columns (Areas: V1, V3d/a, TEO, PFC) showing 1D baseline-normalized dB power change
traces across 5 canonical bands with SEM shaded error bounds.
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
OUT_DIR = REPO_ROOT / "outputs/publication_figures/suite_tfr"
GROUP_OUT_DIR = REPO_ROOT / "outputs/publication_figures"

FREQS_HZ = np.arange(3, 201, 2)  # 99 bins
WINDOW_MS = (-500.0, 4124.0)
BASELINE_END_MS = -400.0

TARGET_AREAS = ["V1", "V3d/a", "TEO", "PFC"]
CONDITIONS = ["RRRR", "RXRR", "RRXR", "RRRX"]

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

OMIT_SLOT_MAP = {"RXRR": "p2", "RRXR": "p3", "RRRX": "p4"}

def resolve_area_file(prefix: str, area_label: str, cond: str) -> Path | None:
    """Find precomputed TFR npy file matching area_label (e.g. V3d/a matches V3, V3a, V3d)."""
    possible_areas = [area_label]
    if area_label == "V3d/a":
        possible_areas = ["V3", "V3a", "V3d"]
        
    for area in possible_areas:
        pattern = f"{prefix}-*-{area}-{cond}.npy"
        matches = list(TFR_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None

def extract_band_trace_db(arr: np.ndarray, freqs: np.ndarray, fmin: float, fmax: float, times_ms: np.ndarray) -> np.ndarray:
    """Extract trial-averaged, dB-normalized trace for a specific frequency band."""
    fmask = (freqs >= fmin) & (freqs <= fmax)
    # Slice memory-mapped array to optimize I/O
    arr_sliced = arr[::4, ::8, fmask, :]  # (n_trials_sub, n_ch_sub, n_freqs_sub, n_times)
    trace_ch_fr = arr_sliced.mean(axis=(1, 2))  # (n_trials_sub, n_times)
    trace_mean = trace_ch_fr.mean(axis=0)  # (n_times,)
    
    # dB normalize relative to pre-baseline
    baseline_mask = times_ms < BASELINE_END_MS
    baseline = trace_mean[baseline_mask].mean()
    baseline = max(baseline, 1e-12)
    return 10.0 * np.log10(trace_mean / baseline)

def plot_4x4_grid(traces_dict: dict, title: str, out_path_svg: Path, out_path_png: Path):
    """Plot 4x4 Condition x Area grid of LFP power traces."""
    times_ms = np.linspace(WINDOW_MS[0], WINDOW_MS[1], 500)
    
    plt.style.use("classic")
    fig = plt.figure(figsize=(15, 12))
    gs = gridspec.GridSpec(4, 4, wspace=0.15, hspace=0.25)
    
    matplotlib.rcParams["font.sans-serif"] = "Arial"
    matplotlib.rcParams["font.family"] = "sans-serif"
    
    for r_idx, cond in enumerate(CONDITIONS):
        omit_slot = OMIT_SLOT_MAP.get(cond)
        
        for c_idx, area_label in enumerate(TARGET_AREAS):
            ax = fig.add_subplot(gs[r_idx, c_idx])
            
            sub_data = traces_dict.get((cond, area_label), {})
            has_data = False
            
            for band_name, color in BAND_COLORS.items():
                band_traces = sub_data.get(band_name, [])
                if len(band_traces) == 0:
                    continue
                    
                has_data = True
                band_arr = np.array(band_traces)  # shape (n_sessions, n_times) or (1, n_times)
                mean = band_arr.mean(axis=0)
                sem = band_arr.std(axis=0) / np.sqrt(band_arr.shape[0]) if band_arr.shape[0] > 1 else np.zeros_like(mean)
                
                # Smooth traces slightly for clean visualization
                mean_smooth = gaussian_filter1d(mean, sigma=2.0)
                sem_smooth = gaussian_filter1d(sem, sigma=2.0) if band_arr.shape[0] > 1 else np.zeros_like(mean)
                
                ax.plot(times_ms, mean_smooth, color=color, linewidth=1.2, label=band_name, zorder=3)
                if band_arr.shape[0] > 1 and sem_smooth.max() > 0:
                    ax.fill_between(times_ms, mean_smooth - sem_smooth, mean_smooth + sem_smooth,
                                    color=color, alpha=0.15, zorder=2)
                                    
            if not has_data:
                ax.text(0.5, 0.5, "No Data", ha="center", va="center", color="gray", fontsize=10)
                
            ax.set_xlim(WINDOW_MS[0], WINDOW_MS[1])
            ax.set_ylim(-3.5, 3.5)
            ax.axhline(0, color="gray", linewidth=0.5, linestyle="-", alpha=0.5, zorder=1)
            ax.set_title(f"{cond} — {area_label}", fontsize=10, fontweight="bold")
            
            # Epoch background shading
            for label, t_start in EPOCH_ONSETS_MS.items():
                idx_ep = EPOCH_LABELS.index(label)
                t_stop = EPOCH_TIMES_MS[idx_ep + 1]
                if label in EPOCH_SHADE:
                    ax.axvspan(t_start, t_stop, color=EPOCH_SHADE[label],
                               alpha=EPOCH_SHADE_ALPHA, zorder=0, linewidth=0)
                    if label == omit_slot:
                        t_mid = (t_start + t_stop) / 2
                        ax.axvline(t_mid, color="red", linewidth=1.2, linestyle="--", alpha=0.8, zorder=2)
                        ax.text(t_mid, 3.0, "X", ha="center", va="top", color="red", fontsize=10, fontweight="bold", zorder=3)
                        
            # Grid
            for t_ms in EPOCH_TIMES_MS[:-1]:
                ax.axvline(t_ms, color="gray", linewidth=0.4, linestyle=":", alpha=0.5, zorder=1)
                
            # Hide redundant labels
            if r_idx < 3:
                ax.xaxis.set_tick_params(labelbottom=False)
            else:
                ax.set_xlabel("Time (ms)", fontsize=8)
            if c_idx > 0:
                ax.yaxis.set_tick_params(labelleft=False)
            else:
                ax.set_ylabel("Power (dB)", fontsize=8)
                
            if r_idx == 0 and c_idx == 0 and has_data:
                ax.legend(loc="upper right", fontsize=7, framealpha=0.7)
                
    fig.suptitle(title, fontsize=13, fontweight="bold", y=0.98)
    fig.savefig(out_path_svg, bbox_inches="tight", dpi=200)
    fig.savefig(out_path_png, bbox_inches="tight", dpi=200)
    plt.close(fig)

def main():
    if not READINESS_CSV.exists() or not TFR_DIR.exists():
        print("Required catalog or TFR directory does not exist.")
        return
        
    readiness = pd.read_csv(READINESS_CSV)
    valid_rows = readiness[readiness["suite_tfr_ready"].fillna(False).astype(bool)]
    print(f"Loaded {len(valid_rows)} sessions with TFR precomputed.")
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    GROUP_OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    times_ms = np.linspace(WINDOW_MS[0], WINDOW_MS[1], 500)
    
    # Store group-level traces
    group_traces = {(cond, area): {band: [] for band in BANDS} for cond in CONDITIONS for area in TARGET_AREAS}
    
    # Process per session
    for _, row in valid_rows.iterrows():
        prefix = row["session_prefix"]
        session_traces = {(cond, area): {band: [] for band in BANDS} for cond in CONDITIONS for area in TARGET_AREAS}
        has_any_session_data = False
        
        for cond in CONDITIONS:
            for area_label in TARGET_AREAS:
                fpath = resolve_area_file(prefix, area_label, cond)
                if fpath and fpath.exists():
                    try:
                        arr = np.load(fpath, mmap_mode="r")
                        has_any_session_data = True
                        for band_name, (fmin, fmax) in BANDS.items():
                            trace_db = extract_band_trace_db(arr, FREQS_HZ, fmin, fmax, times_ms)
                            session_traces[(cond, area_label)][band_name].append(trace_db)
                            group_traces[(cond, area_label)][band_name].append(trace_db)
                    except Exception as e:
                        print(f"Error loading {fpath.name}: {e}")
                        
        if has_any_session_data:
            dt_suffix = datetime.datetime.now().strftime("%y%m%d")
            out_svg = OUT_DIR / f"{prefix}_suite_lfp_power_traces_{dt_suffix}.svg"
            out_png = OUT_DIR / f"{prefix}_suite_lfp_power_traces_{dt_suffix}.png"
            plot_4x4_grid(session_traces, f"LFP Band Power Traces — {prefix}", out_svg, out_png)
            
            # Save canonical filename alias
            plot_4x4_grid(session_traces, f"LFP Band Power Traces — {prefix}",
                          OUT_DIR / f"{prefix}_suite_lfp_power_traces.svg",
                          OUT_DIR / f"{prefix}_suite_lfp_power_traces.png")
            print(f"Generated LFP power trace suite for session: {prefix}")
            
    # Generate Group-Level Average Suite
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")
    group_svg = GROUP_OUT_DIR / f"figure_lfp_power_traces_4x4_{dt_suffix}.svg"
    group_png = GROUP_OUT_DIR / f"figure_lfp_power_traces_4x4_{dt_suffix}.png"
    plot_4x4_grid(group_traces, "Group Average LFP Band Power Traces (4x4 Condition x Area)", group_svg, group_png)
    plot_4x4_grid(group_traces, "Group Average LFP Band Power Traces (4x4 Condition x Area)",
                  GROUP_OUT_DIR / "figure_lfp_power_traces_4x4.svg",
                  GROUP_OUT_DIR / "figure_lfp_power_traces_4x4.png")
    print(f"Generated Group Average LFP power trace suite at {group_svg.name}")

if __name__ == "__main__":
    main()
