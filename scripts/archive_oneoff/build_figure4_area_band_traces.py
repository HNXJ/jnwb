"""
Figure 4: Band-decomposed LFP traces for all areas, all sessions.

For each of the 11 cortical areas (V1, V2, V3, V3d, V3a, V4, MT, MST, TEO, FST, FEF, PFC),
loads precomputed TFR arrays from all suite_tfr_ready sessions that recorded from that area,
extracts theta/alpha/beta/gamma band power traces (channel + trial averaged), and plots
mean +/- 2*SEM across sessions.

N per area is labeled; if N=1, no SEM shading (single session trace only).

Layout: grid of subplots (4 cols, 3 rows for 11 areas + 1 legend panel).
X-axis: full sequence window (-500ms to 4124ms), epoch boundaries marked, shared across all.

Usage:
    python scripts/build_figure4_area_band_traces.py
    python scripts/build_figure4_area_band_traces.py --condition RRRR
    python scripts/build_figure4_area_band_traces.py --condition RRXR
    python scripts/build_figure4_area_band_traces.py --max-sessions 3  # smoke test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from jnwb.sequence_layout import EPOCH_ONSETS_MS

TFR_DIR = Path("D:/workspace/data/tfr_arrays")
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_DIR = REPO_ROOT / "outputs/publication_figures/figure4_area_band_traces"

FREQS_HZ = np.arange(3, 201, 2)  # 99 bins
WINDOW_MS = (-500.0, 4124.0)
BASELINE_END_MS = -400.0

# TFR array axis order (confirmed from live shape inspection 2026-07-13):
#   (n_trials, n_ch, n_freqs, n_times)
# e.g. RRRR: (111, 128, 99, 500)
TFR_AXES = dict(trials=0, ch=1, freqs=2, times=3)

# Canonical 11 cortical areas in hierarchy order (visual -> frontal)
# NOTE: V3/V3d/V3a all present; probe coverage varies per session
ALL_AREAS = ["V1", "V2", "V3", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]

# Layout: 4 cols x 4 rows = 16 cells. First 12 = areas. Cell 12 = legend. Cells 13-15 = empty.
N_COLS = 4
N_ROWS = 4

BANDS = {
    "theta":  (4.0,  8.0),
    "alpha":  (8.0,  15.0),
    "beta":   (15.0, 30.0),
    "gamma":  (30.0, 80.0),
}
BAND_COLORS = {
    "theta": "#4477AA",
    "alpha": "#EE6677",
    "beta":  "#228833",
    "gamma": "#CCBB44",
}

EPOCH_LABELS = list(EPOCH_ONSETS_MS.keys())
EPOCH_TIMES_MS = list(EPOCH_ONSETS_MS.values()) + [WINDOW_MS[1]]
EPOCH_SHADE = {"p1": "#fcee21", "p2": "#93278f", "p3": "#019147", "p4": "#000bd4"}
EPOCH_SHADE_ALPHA = 0.10


def db_normalize_trace(trace: np.ndarray, times_ms: np.ndarray) -> np.ndarray:
    """dB normalize a (n_times,) or (n_freqs, n_times) trace relative to pre-baseline."""
    baseline_mask = times_ms < BASELINE_END_MS
    if baseline_mask.sum() == 0:
        return trace
    if trace.ndim == 1:
        baseline = trace[baseline_mask].mean()
        baseline = max(baseline, 1e-12)
        return 10.0 * np.log10(trace / baseline)
    else:
        baseline = trace[:, baseline_mask].mean(axis=1, keepdims=True)
        baseline = np.where(baseline == 0, 1e-12, baseline)
        return 10.0 * np.log10(trace / baseline)


def load_session_area_band_traces(session_prefix: str, area: str,
                                   condition: str, freqs: np.ndarray,
                                   times_ms: np.ndarray) -> dict[str, np.ndarray] | None:
    """
    Load TFR for (session, area, condition), extract per-band dB-normalized traces.
    Array shape: (n_trials, n_ch, n_freqs, n_times) — confirmed from live inspection.
    Returns: {band_name: (n_times,) db-normalized mean across channels+trials}
    Returns None if TFR file not found.
    """
    pattern = f"{session_prefix}-*-{area}-{condition}.npy"
    matches = sorted(TFR_DIR.glob(pattern))
    if not matches:
        return None

    fpath = matches[0]
    try:
        arr = np.load(fpath, mmap_mode="r")  # (n_trials, n_ch, n_freqs, n_times)
    except Exception as e:
        print(f"  [WARN] Could not load {fpath}: {e}")
        return None

    if arr.ndim != 4:
        print(f"  [WARN] Unexpected shape {arr.shape} for {fpath.name}")
        return None

    # trial + channel average -> (n_freqs, n_times)
    mean_2d = arr.mean(axis=(0, 1))  # (n_freqs, n_times)

    n_freqs_arr, n_times_arr = mean_2d.shape
    times_ms_local = np.linspace(WINDOW_MS[0], WINDOW_MS[1], n_times_arr)
    freqs_local = freqs[:n_freqs_arr] if n_freqs_arr <= len(freqs) else freqs
    if n_freqs_arr != len(freqs):
        freqs_local = np.linspace(freqs[0], freqs[-1], n_freqs_arr)
    else:
        freqs_local = freqs

    db_2d = db_normalize_trace(mean_2d, times_ms_local)

    result: dict[str, np.ndarray] = {}
    for band_name, (fmin, fmax) in BANDS.items():
        fmask = (freqs_local >= fmin) & (freqs_local <= fmax)
        if fmask.sum() == 0:
            continue
        band_trace = db_2d[fmask, :].mean(axis=0)  # (n_times,)
        if len(times_ms_local) != len(times_ms):
            band_trace = np.interp(times_ms, times_ms_local, band_trace)
        result[band_name] = band_trace

    return result


def draw_epoch_decorations(ax, condition: str):
    """Add epoch shading and boundary lines."""
    omit_slots = {"RXRR": "p2", "RRXR": "p3", "RRRX": "p4"}
    omit_slot = omit_slots.get(condition)
    for label, t_start in EPOCH_ONSETS_MS.items():
        idx = EPOCH_LABELS.index(label)
        t_stop = EPOCH_TIMES_MS[idx + 1]
        if label in EPOCH_SHADE:
            ax.axvspan(t_start, t_stop, color=EPOCH_SHADE[label],
                       alpha=EPOCH_SHADE_ALPHA, zorder=0, linewidth=0)
            if label == omit_slot:
                t_mid = (t_start + t_stop) / 2
                ax.axvline(t_mid, color="gray", linewidth=1.0,
                           linestyle="--", alpha=0.6, zorder=2)
    for t_ms in EPOCH_TIMES_MS[:-1]:
        ax.axvline(t_ms, color="gray", linewidth=0.3, linestyle=":", alpha=0.4, zorder=1)
    ax.axhline(0, color="gray", linewidth=0.4, linestyle="-", alpha=0.3)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Figure 4: Band-decomposed LFP traces, all areas, all sessions."
    )
    parser.add_argument("--condition", default="RRRR",
                        help="TFR condition (default: RRRR)")
    parser.add_argument("--bands", default="theta,alpha,beta,gamma",
                        help="Comma-separated band names (default: theta,alpha,beta,gamma)")
    parser.add_argument("--max-sessions", type=int, default=None,
                        help="Limit sessions for smoke testing.")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    selected_bands = [b.strip() for b in args.bands.split(",")]

    # Load session readiness
    readiness = pd.read_csv(READINESS_CSV)
    ready = readiness[readiness["suite_tfr_ready"] == True].copy()
    if args.max_sessions:
        ready = ready.head(args.max_sessions)

    sessions = ready["session_prefix"].tolist()
    print(f"Processing {len(sessions)} sessions, condition={args.condition}")

    # Standard time axis: TFR arrays start at -1000ms and have 10ms bins (500 bins)
    n_times_default = 500
    times_ms = -1000.0 + np.arange(n_times_default) * 10.0
    # Try to get actual n_times from a real file
    sample_files = sorted(TFR_DIR.glob(f"{sessions[0]}-*-{args.condition}.npy"))
    if sample_files:
        try:
            sample = np.load(sample_files[0], mmap_mode="r")
            # shape: (n_trials, n_ch, n_freqs, n_times) -> times is axis 3
            n_times = sample.shape[3]
            times_ms = -1000.0 + np.arange(n_times) * 10.0
            print(f"  Time axis: {len(times_ms)} bins from {sample_files[0].name} (shape={sample.shape})")
        except Exception:
            pass

    freqs = FREQS_HZ

    # Collect per-area, per-band session traces: {area: {band: [n_times arrays]}}
    area_band_traces: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    area_session_counts: dict[str, int] = defaultdict(int)

    for sess_prefix in sessions:
        for area in ALL_AREAS:
            traces = load_session_area_band_traces(sess_prefix, area, args.condition,
                                                   freqs, times_ms)
            if traces is None:
                continue
            for band_name in selected_bands:
                if band_name in traces:
                    area_band_traces[area][band_name].append(traces[band_name])
            area_session_counts[area] += 1

    # Report coverage
    print("\nArea coverage:")
    for area in ALL_AREAS:
        n = area_session_counts.get(area, 0)
        print(f"  {area:6s}: {n} sessions")

    # ---- PLOT ----
    # 12 areas + 1 legend = 13 cells -> use 4x4 grid (16 cells, 3 empty at end)
    fig, axes = plt.subplots(N_ROWS, N_COLS, figsize=(16, 12),
                             sharex=True, sharey=False)
    axes_flat = axes.flatten()   # 16 cells

    plotted = 0
    for ai, area in enumerate(ALL_AREAS):
        ax = axes_flat[ai]
        n_sess = area_session_counts.get(area, 0)
        
        if n_sess == 0:
            ax.set_visible(False)
            continue

        for band_name in selected_bands:
            if band_name not in area_band_traces[area]:
                continue
            traces_list = area_band_traces[area][band_name]  # list of (n_times,)
            stack = np.stack(traces_list, axis=0)  # (n_sess, n_times)
            mean = stack.mean(axis=0)
            
            from scipy.ndimage import gaussian_filter1d
            mean_smooth = gaussian_filter1d(mean, sigma=2.0)
            color = BAND_COLORS.get(band_name, "black")

            if stack.shape[0] > 1:
                sem = stack.std(axis=0, ddof=1) / np.sqrt(stack.shape[0])
                sem_smooth = gaussian_filter1d(sem, sigma=2.0)
                ax.fill_between(times_ms, mean_smooth - 2 * sem_smooth, mean_smooth + 2 * sem_smooth,
                                color=color, alpha=0.18, zorder=2)
            ax.plot(times_ms, mean_smooth, color=color, linewidth=1.1,
                    label=band_name, zorder=3)

        draw_epoch_decorations(ax, args.condition)
        ax.set_title(f"{area}  (N={n_sess})", fontsize=9, fontweight="bold")
        ax.tick_params(axis="both", labelsize=7)
        ax.set_ylabel("Power (dB)", fontsize=7)
        ax.set_xlim(WINDOW_MS[0], WINDOW_MS[1])  # Lock zoom to focus window [-500ms, 4124ms]
        plotted += 1

    # Hide unused axes (13-15 after legend)
    for ai in range(len(ALL_AREAS) + 1, len(axes_flat)):
        axes_flat[ai].set_visible(False)

    # Legend in cell index 12 (first cell after 12 areas)
    legend_ax = axes_flat[len(ALL_AREAS)]
    legend_ax.set_visible(True)
    legend_ax.axis("off")
    handles = [plt.Line2D([0], [0], color=BAND_COLORS[b], linewidth=2, label=b)
               for b in selected_bands if b in BAND_COLORS]
    legend_ax.legend(handles=handles, loc="center", fontsize=10, title="Band", title_fontsize=10)

    # X-axis labels on bottom row only
    for col_i in range(N_COLS):
        axes[N_ROWS - 1, col_i].set_xlabel("Time (ms from sequence onset)", fontsize=8)

    fig.suptitle(
        f"Figure 4: Band-decomposed LFP power — all areas — condition={args.condition}\n"
        f"Mean ±2SEM across sessions per area. Sessions: {len(sessions)}.",
        fontsize=11
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    out_path = out_dir / f"figure4_band_traces_{args.condition}.png"
    svg_path = out_dir / f"figure4_band_traces_{args.condition}.svg"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)

    print(f"\nWrote:\n  {out_path}\n  {svg_path}")
    print(f"PNG size: {out_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
