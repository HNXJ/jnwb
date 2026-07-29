"""
Figure 3: Spectral 4x2 TFR panel.

Layout: 4 rows x 2 columns (col 0 = area1 default V1, col 1 = area2 default FEF).

  Row 0: TFR heatmap, omission condition (default RRXR, p3 omitted)
  Row 1: TFR heatmap, control condition (default RRRR)
  Row 2: Band traces +/-2SEM, omission condition (theta/alpha/beta/gamma)
  Row 3: Band traces +/-2SEM, control condition (theta/alpha/beta/gamma)

X-axis: full sequence time window (-500ms to 4124ms), epoch boundaries marked.
TFR arrays loaded from D:/workspace/data/tfr_arrays/ (precomputed, gate on readiness CSV).

Rows 2-3: per-trial band extraction -> mean +/- 2*SEM across trials.
Bands: theta (4-8Hz), alpha (8-15Hz), beta (15-30Hz), gamma (30-80Hz).

Usage:
    python scripts/build_figure3_spectral_4x2.py
    python scripts/build_figure3_spectral_4x2.py --session sub-C31o_ses-230823 \\
        --area1 V1 --area2 FEF --omit-cond RRXR
    python scripts/build_figure3_spectral_4x2.py --dry-run  # check paths, don't plot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
OUT_DIR = REPO_ROOT / "outputs/publication_figures/figure3_spectral_4x2"

FREQS_HZ = np.arange(3, 201, 2)   # confirmed 99 bins from sub-C31o_ses-230823 array structure
WINDOW_MS = (-500.0, 4124.0)
BASELINE_END_MS = -400.0           # pre-fx window for dB normalization

# TFR array axis order (confirmed from live shape inspection 2026-07-13):
#   (n_trials, n_ch, n_freqs, n_times)
# e.g. RRXR: (43, 128, 99, 500), RRRR: (111, 128, 99, 500)
TFR_AXES = dict(trials=0, ch=1, freqs=2, times=3)

BANDS = {
    "theta": (4.0, 8.0),
    "alpha": (8.0, 15.0),
    "beta": (15.0, 30.0),
    "gamma": (30.0, 80.0),
}
# Palette: distinct colors for each band
BAND_COLORS = {
    "theta": "#4477AA",
    "alpha": "#EE6677",
    "beta": "#228833",
    "gamma": "#CCBB44",
}

# Epoch shade colors (matching figure 2 raster grid convention)
EPOCH_SHADE = {"p1": "#fcee21", "p2": "#93278f", "p3": "#019147", "p4": "#000bd4"}
EPOCH_SHADE_ALPHA = 0.12

EPOCH_LABELS = list(EPOCH_ONSETS_MS.keys())
EPOCH_TIMES_MS = list(EPOCH_ONSETS_MS.values()) + [WINDOW_MS[1]]


def resolve_probe(session_prefix: str, area: str) -> str:
    """Find probe letter for an area from TFR file listing."""
    pattern = f"{session_prefix}-*-{area}-RRRR.npy"
    matches = sorted(TFR_DIR.glob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"No TFR file matching {pattern} in {TFR_DIR}. "
            f"Check session_readiness.csv suite_tfr_ready column."
        )
    # Extract probe letter from filename: {prefix}-{probe}-{area}-{cond}.npy
    stem = matches[0].stem  # e.g. sub-C31o_ses-230823-A-FEF-RRRR
    parts = stem.split("-")
    # prefix has hyphens; area and probe are the last 3 tokens before cond
    # structure: ...{year}{month}{day}-{probe}-{area}-{cond}
    # probe = parts[-3], area = parts[-2], cond = parts[-1]
    probe = parts[-3]
    return probe


def load_tfr(session_prefix: str, probe: str, area: str, condition: str) -> np.ndarray:
    """Load TFR array. Shape: (n_ch, n_freqs, n_times, n_trials)."""
    fpath = TFR_DIR / f"{session_prefix}-{probe}-{area}-{condition}.npy"
    if not fpath.exists():
        raise FileNotFoundError(f"TFR file not found: {fpath}")
    arr = np.load(fpath, mmap_mode="r")
    return arr


def db_normalize(arr: np.ndarray, times_ms: np.ndarray) -> np.ndarray:
    """
    dB normalize: 10*log10(power / mean_baseline_power).
    arr shape: (n_freqs, n_times) — already channel+trial averaged.
    baseline: t < BASELINE_END_MS.
    """
    baseline_mask = times_ms < BASELINE_END_MS
    if baseline_mask.sum() == 0:
        raise ValueError(f"No time bins before {BASELINE_END_MS}ms for baseline.")
    baseline = arr[:, baseline_mask].mean(axis=1, keepdims=True)
    baseline = np.where(baseline == 0, 1e-12, baseline)
    return 10.0 * np.log10(arr / baseline)


def extract_band_traces(arr: np.ndarray, freqs: np.ndarray,
                         fmin: float, fmax: float) -> np.ndarray:
    """
    Extract mean band power trace per trial.
    arr shape: (n_trials, n_ch, n_freqs, n_times)
    Returns: (n_trials, n_times) — channel- and frequency-averaged.
    """
    fmask = (freqs >= fmin) & (freqs <= fmax)
    return arr[:, :, fmask, :].mean(axis=(1, 2))  # (n_trials, n_times)


def draw_epoch_shading(ax, condition: str):
    """Shade stimulus epochs; mark omitted slot with X."""
    omit_slots = {
        "RXRR": "p2", "RRXR": "p3", "RRRX": "p4",
        "AXAB": "p2", "AAXB": "p3", "AAAX": "p4",
        "BXBA": "p2", "BBXA": "p3", "BBBX": "p4"
    }
    omit_slot = omit_slots.get(condition)
    for label, t_start in EPOCH_ONSETS_MS.items():
        idx = EPOCH_LABELS.index(label)
        t_stop = EPOCH_TIMES_MS[idx + 1]
        if label in EPOCH_SHADE:
            ax.axvspan(t_start, t_stop, color=EPOCH_SHADE[label],
                       alpha=EPOCH_SHADE_ALPHA, zorder=0, linewidth=0)
            # Mark omitted slot
            if label == omit_slot:
                t_mid = (t_start + t_stop) / 2
                ax.axvline(t_mid, color="white", linewidth=1.5, linestyle="--",
                           alpha=0.8, zorder=2)
                ax.text(t_mid, ax.get_ylim()[1] * 0.97, "X",
                        ha="center", va="top", color="white",
                        fontsize=9, fontweight="bold", zorder=3)
    # Epoch boundary lines
    for t_ms in EPOCH_TIMES_MS[:-1]:
        ax.axvline(t_ms, color="gray", linewidth=0.4, linestyle=":", alpha=0.5, zorder=1)


def plot_heatmap(ax, arr_db: np.ndarray, times_ms: np.ndarray, freqs: np.ndarray,
                 condition: str, title: str):
    """Plot trial-averaged dB-normalized TFR heatmap."""
    extent = [times_ms[0], times_ms[-1], freqs[-1], freqs[0]]
    im = ax.imshow(arr_db, aspect="auto", cmap="RdBu_r",
                   vmin=-2.0, vmax=2.0, extent=extent, origin="upper",
                   interpolation="nearest")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda y, _: f"{int(y)}Hz" if y in (4, 8, 15, 30, 80, 150) else ""))
    ax.set_xlim(WINDOW_MS[0], WINDOW_MS[1])
    ax.set_title(title, fontsize=9)
    draw_epoch_shading(ax, condition)
    return im


def plot_band_traces(ax, arr: np.ndarray, freqs: np.ndarray, times_ms: np.ndarray,
                     condition: str, title: str):
    """Plot smoothed per-band mean +/-2SEM traces."""
    from scipy.ndimage import gaussian_filter1d
    for band_name, (fmin, fmax) in BANDS.items():
        traces = extract_band_traces(arr, freqs, fmin, fmax)  # (n_trials, n_times)
        mean = traces.mean(axis=0)
        sem = traces.std(axis=0) / np.sqrt(traces.shape[0])
        # Smooth both mean and SEM traces slightly for clean visualization (sigma=2 bins = 20ms)
        mean_smooth = gaussian_filter1d(mean, sigma=2.0)
        sem_smooth = gaussian_filter1d(sem, sigma=2.0)
        
        color = BAND_COLORS[band_name]
        ax.plot(times_ms, mean_smooth, color=color, linewidth=1.2, label=band_name, zorder=3)
        ax.fill_between(times_ms, mean_smooth - 2 * sem_smooth, mean_smooth + 2 * sem_smooth,
                        color=color, alpha=0.18, zorder=2)
    draw_epoch_shading(ax, condition)
    ax.axhline(0, color="gray", linewidth=0.5, linestyle="-", alpha=0.4)
    ax.set_xlim(WINDOW_MS[0], WINDOW_MS[1])  # Keep focus window locked to [-500ms, 4124ms]
    ax.set_title(title, fontsize=9)
    ax.legend(fontsize=7, loc="upper right", framealpha=0.7)
    ax.set_ylabel("Power (dB)", fontsize=8)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Figure 3: Spectral 4x2 TFR panel (heatmaps + band traces)."
    )
    parser.add_argument("--session", default="sub-C31o_ses-230823")
    parser.add_argument("--area1", default="V1")
    parser.add_argument("--area2", default="FEF")
    parser.add_argument("--omit-cond", default="RRXR",
                        choices=["RXRR", "RRXR", "RRRX", "AXAB", "AAXB", "AAAX", "BXBA", "BBXA", "BBBX"])
    parser.add_argument("--control-cond", default="RRRR")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="Check TFR paths and print shapes without plotting.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve probes
    probe1 = resolve_probe(args.session, args.area1)
    probe2 = resolve_probe(args.session, args.area2)
    print(f"Resolved: {args.area1}={probe1}, {args.area2}={probe2}")

    # Load all 4 TFR arrays
    conditions_to_load = [(args.area1, probe1, args.omit_cond),
                          (args.area1, probe1, args.control_cond),
                          (args.area2, probe2, args.omit_cond),
                          (args.area2, probe2, args.control_cond)]

    arrays: dict[tuple, np.ndarray] = {}
    for area, probe, cond in conditions_to_load:
        arr = load_tfr(args.session, probe, area, cond)
        arrays[(area, cond)] = arr
        print(f"  Loaded {args.session}-{probe}-{area}-{cond}.npy: shape={arr.shape}")

    if args.dry_run:
        print("Dry run complete — all TFR paths resolved. Exiting without plotting.")
        return

    # Build time axis from array n_times: TFR array starts at -1000ms and has 10ms bins
    n_times = arrays[(args.area1, args.omit_cond)].shape[3]   # axis 3 = times
    times_ms = -1000.0 + np.arange(n_times) * 10.0

    freqs = FREQS_HZ  # (99,) bins as confirmed from the session

    # Pre-compute trial-averaged dB heatmaps
    def trial_avg_db(arr):
        # arr: (n_trials, n_ch, n_freqs, n_times) -> trial+channel avg -> dB
        ch_trial_avg = arr.mean(axis=(0, 1))  # (n_freqs, n_times)
        return db_normalize(ch_trial_avg, times_ms)

    fig, axes = plt.subplots(4, 2, figsize=(12, 14),
                             gridspec_kw={"height_ratios": [1.2, 1.2, 1.0, 1.0]})

    area_labels = [args.area1, args.area2]
    conditions = [args.omit_cond, args.control_cond]

    # Collect colorbars for rows 0-1
    heatmap_ims = []

    for col_i, area in enumerate(area_labels):
        # Row 0: heatmap omission
        arr_omit = arrays[(area, args.omit_cond)]
        db_omit = trial_avg_db(arr_omit)
        im0 = plot_heatmap(axes[0, col_i], db_omit, times_ms, freqs,
                           args.omit_cond,
                           f"{area} — {args.omit_cond} (omission)")
        heatmap_ims.append(im0)

        # Row 1: heatmap control
        arr_ctrl = arrays[(area, args.control_cond)]
        db_ctrl = trial_avg_db(arr_ctrl)
        im1 = plot_heatmap(axes[1, col_i], db_ctrl, times_ms, freqs,
                           args.control_cond,
                           f"{area} — {args.control_cond} (control)")
        heatmap_ims.append(im1)

        # Row 2: band traces, omission
        plot_band_traces(axes[2, col_i], arr_omit, freqs, times_ms,
                         args.omit_cond,
                         f"{area} — {args.omit_cond} bands")

        # Row 3: band traces, control
        plot_band_traces(axes[3, col_i], arr_ctrl, freqs, times_ms,
                         args.control_cond,
                         f"{area} — {args.control_cond} bands")

    # Colorbars for heatmap rows
    for col_i in range(2):
        plt.colorbar(heatmap_ims[col_i * 2], ax=axes[0, col_i],
                     label="dB re baseline", shrink=0.8, pad=0.02)
        plt.colorbar(heatmap_ims[col_i * 2 + 1], ax=axes[1, col_i],
                     label="dB re baseline", shrink=0.8, pad=0.02)

    # Shared x-axis labels on bottom row only
    for col_i in range(2):
        for row_i in range(3):
            axes[row_i, col_i].set_xlabel("")
            axes[row_i, col_i].tick_params(axis="x", labelbottom=False)
        axes[3, col_i].set_xlabel("Time (ms from sequence onset)", fontsize=9)

    fig.suptitle(
        f"Figure 3: TFR panel — {args.session}\n"
        f"{args.area1} vs {args.area2}  |  "
        f"omission={args.omit_cond}  control={args.control_cond}",
        fontsize=11
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    out_path = out_dir / f"figure3_spectral_{args.area1}_{args.area2}_{args.omit_cond}.png"
    svg_path = out_dir / f"figure3_spectral_{args.area1}_{args.area2}_{args.omit_cond}.svg"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)

    print(f"\nWrote:\n  {out_path}\n  {svg_path}")
    print(f"PNG size: {out_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
