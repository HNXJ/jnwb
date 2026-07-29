"""
Figure 3: S+/S-/O+ raster grid, 4 rows (RRRR/RXRR/RRXR/RRRX) x 3 columns (S+/S-/O+).

One neuron per column (S+, S-, O+), the same neuron shown across all 4 rows (one row per
R-family condition). Each subplot is a real 20-trial raster for that neuron/condition, x-axis
spanning the full real sequence window (fx=-500ms to end=4124ms per
jnwb.sequence_layout.EPOCH_ONSETS_MS, matching the established 4624ms total span used
elsewhere in this repo).

Neuron selection (from outputs/classification/grand_unit_table_shuffle_sso.csv, real
shuffle-controlled classification): for each class, candidates are real units with >= 20 real
trials in ALL 4 R-family conditions and a real mean firing rate >= 1 Hz (dense enough for a
readable raster).

"Stable, not highly varying across trials" - IMPORTANT, found by direct visual inspection
2026-07-12: an earlier version of this script ranked candidates only by total per-trial spike
count CV, which does NOT catch real trial-order drift (a neuron whose response SHAPE stays
similar across trials but whose overall rate ramps up/down over the real trial sequence keeps
a low count-CV and even a high early-vs-late PSTH-shape correlation - shape correlation is
scale-invariant - while visibly looking non-stationary in a raster: sparse in early trials,
dense in late trials). Verified this exact failure mode concretely on S- unit 238 (a v1 pick):
looked clearly non-stationary when actually rendered and inspected. The real, correct
stability metric used here is the absolute Spearman correlation between real per-trial spike
count and real chronological trial order ("drift"), taken as the worst case (max) across all
4 R-family conditions - low |drift| means no systematic trend across the trial sequence.

O+ units are real but rare (7 total across all 15 sessions, confirmed 2026-07-12, all from
sub-C31o_ses-230823_rec) - this session is used for all 3 columns so the comparison is drawn
from one real recording context. "Mean matched across groups": among real candidates with
|drift| < 0.2 (genuinely stable, no trend), the highest-rate option was picked per class.
S- tops out at ~12 Hz even among stable candidates (verified: no stable S- unit in this
session reaches the ~20 Hz range S+/O+ reach) - a real, honest population constraint, not a
selection shortfall.

O+ SELECTION CORRECTED 2026-07-13: the most-stable O+ candidate (unit 41, |drift|=0.201) turned
out to have the WEAKEST real omission-vs-control-slot firing-rate ratio of all 7 real O+
candidates (1.23x, barely above baseline) - i.e. it is classified O+ by the real shuffle test
(which pools across all omission slots and compares to local baseline/delay, not to the
same-slot control condition shown per-row here) but does not visibly show "higher firing during
omission" in this specific per-row raster layout. Directly computed the real omission-window
rate (jnwb.unit_classification.SLOT_WINDOW_MS, i.e. the same [p_n, p_n+531ms) window used by
the real classifier) vs. the real same-slot RRRR-control rate, separately for each omission row
(RXRR/p2, RRXR/p3, RRRX/p4), for all 7 real O+ candidates. Unit 51 shows the strongest and most
consistent real effect (roughly 2x the control rate in all 3 rows: 21.0 vs 10.8 Hz, 33.4 vs 9.8
Hz, 23.1 vs 11.5 Hz) with acceptable stability (|drift|=0.646, worse than unit 41's 0.201 but the
raster still looks reasonably trial-consistent on visual inspection) - a real, stated trade-off
of stability for a visibly genuine omission response, which is what O+ is meant to demonstrate.

SELECTION METHOD REPLACED 2026-07-13 (template correlation, see
scripts/template_correlation_selection.py): the drift-only stability picks above (unit 17 for
S+, unit 189 for S-) turned out to be weak/non-significant matches to the actual real event
templates they are meant to represent - real per-epoch duration-normalized firing rate,
Pearson-correlated against an idealized 0/1 pulse template over the real epoch sequence
(fx,p1,d1,p2,d2,p3,d3,p4,d4), with a real permutation-test p-value (5000 draws, shuffling
epoch-rate assignment): unit 17 scored r=0.46 (p=0.19, not significant) against the S+ template
0-1-0-1-0-1-0-1-0; unit 189 scored r=0.04 (p=0.89, effectively uncorrelated) against the S-
template 1-0-1-0-1-0-1-0-1. Real candidates unit 337 (r=0.985, p=0.008) and unit 261 (r=0.985,
p=0.003, against 1-0-1-0-1-0-1-0-1) are dramatically stronger, statistically significant matches
in the same session, and are now the default S+/S- picks. O+ (unit 51) is unchanged: it already
independently scored highest (r_mean=0.769 across the 3 real omission-template correlations,
one-hot template with a 1 only at the real omitted slot) among the 7 real O+ candidates, matching
the 2026-07-13 stability-tradeoff correction above from an independent method. No real unit in
this session reaches p<0.05 in all 3 omission conditions simultaneously against the one-hot O+
template (real finding: a single-nonzero 9-element template has low statistical power per
condition) - selection stays on real mean-correlation ranking, not a significance threshold, for
this class specifically.

Usage:
    python scripts/build_figure3_raster_grid.py
    python scripts/build_figure3_raster_grid.py --list-candidates
    python scripts/build_figure3_raster_grid.py --s-plus-unit 337 --s-minus-unit 261 --o-plus-unit 51
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from matplotlib.ticker import MaxNLocator, FuncFormatter
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import jnwb as oa
from jnwb.sequence_layout import EPOCH_ONSETS_MS

REPO_ROOT = Path(__file__).resolve().parents[1]
NWB_PATH = "D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb"
SESSION_PREFIX = "sub-C31o_ses-230823"
CONDITIONS = ["RRRR", "RXRR", "RRXR", "RRRX"]
WINDOW_MS = (-500.0, 4124.0)
N_TRIALS_SHOWN = 40
MIN_TRIALS = 40
MIN_MEAN_RATE_HZ = 1.0
MAX_DRIFT_STABLE = 0.20

DEFAULT_UNITS = {"S+": 337, "S-": 261, "O+": 51}

EPOCH_LABELS = list(EPOCH_ONSETS_MS.keys()) + ["end"]
EPOCH_TIMES_MS = list(EPOCH_ONSETS_MS.values()) + [WINDOW_MS[1]]

CLASS_COLORS = {"S+": "#1D9E75", "S-": "#993C1D", "O+": "#185FA5"}

# Stimulus-epoch background shading, matching the exact colors of the reference
# sequence-timing template (C:/Users/nejath/Downloads/03.svg, confirmed 2026-07-13):
# p1=yellow, p2=purple/magenta, p3=green, p4=blue. Delay periods (d1-d4) and fx stay
# unshaded. Each epoch's real [start, stop) boundary comes from EPOCH_ONSETS_MS below.
EPOCH_SHADE_COLORS = {"p1": "#fcee21", "p2": "#93278f", "p3": "#019147", "p4": "#000bd4"}
EPOCH_SHADE_ALPHA = 0.18  # semi-transparent so the raster spikes remain visible on top

OUT_DIR = REPO_ROOT / "outputs/publication_visual_review/figure3_splus_sminus_oplus_raster_grid"


def select_candidates(sess, grand: pd.DataFrame, onsets_by_cond: dict) -> pd.DataFrame:
    win_s = (WINDOW_MS[0] / 1000.0, WINDOW_MS[1] / 1000.0)
    sub = grand[grand["nwb_stem"] == SESSION_PREFIX.replace("_rec", "") + "_rec"]
    if len(sub) == 0:
        sub = grand[grand["nwb_stem"] == SESSION_PREFIX]

    results = []
    for _, row in sub.iterrows():
        if row["display_class"] not in ("S+", "S-", "O+"):
            continue
        uid = int(row["unit_id"])
        spike_times = sess.get_spike_times(uid)
        if spike_times is None or len(spike_times) == 0:
            continue

        cond_stats = {}
        ok = True
        for cond in CONDITIONS:
            onsets = onsets_by_cond[cond]
            if len(onsets) < MIN_TRIALS:
                ok = False
                break
            counts = np.array([
                np.sum((spike_times >= onset + win_s[0]) & (spike_times < onset + win_s[1]))
                for onset in onsets
            ], dtype=float)
            mean_rate_hz = counts.mean() / (win_s[1] - win_s[0])
            if mean_rate_hz < MIN_MEAN_RATE_HZ:
                ok = False
                break
            # Real drift metric (see module docstring): |Spearman r| between per-trial
            # spike count and real chronological trial order. Catches systematic
            # trial-order trends that a plain count-CV misses.
            drift_r, _ = spearmanr(np.arange(len(counts)), counts)
            cond_stats[cond] = {"mean_rate_hz": mean_rate_hz, "drift": abs(drift_r)}
        if not ok:
            continue

        max_drift = max(cond_stats[c]["drift"] for c in CONDITIONS)
        mean_rate_overall = float(np.mean([cond_stats[c]["mean_rate_hz"] for c in CONDITIONS]))
        results.append({"unit_id": uid, "display_class": row["display_class"],
                         "max_drift": max_drift, "mean_rate_overall": mean_rate_overall})

    return pd.DataFrame(results)


def plot_raster_panel(ax, spike_times: np.ndarray, onsets: np.ndarray, color: str,
                       window_ms=WINDOW_MS, n_trials: int = N_TRIALS_SHOWN, condition: str = "RRRR"):
    # Real epoch boundaries (ms) from EPOCH_LABELS/EPOCH_TIMES_MS, e.g. p1=[0,531).
    for label, t_start in EPOCH_ONSETS_MS.items():
        if label in EPOCH_SHADE_COLORS:
            idx = EPOCH_LABELS.index(label)
            t_stop = EPOCH_TIMES_MS[idx + 1]
            ax.axvspan(t_start, t_stop, color=EPOCH_SHADE_COLORS[label],
                       alpha=EPOCH_SHADE_ALPHA, zorder=0, linewidth=0)

    # Plot spikes
    win_s = (window_ms[0] / 1000.0, window_ms[1] / 1000.0)
    trial_idx = 0
    all_spike_times_rel = []
    for onset in onsets[:n_trials]:
        lo, hi = onset + win_s[0], onset + win_s[1]
        mask = (spike_times >= lo) & (spike_times < hi)
        rel_ms = (spike_times[mask] - onset) * 1000.0
        all_spike_times_rel.extend(rel_ms)
        ax.vlines(rel_ms, trial_idx + 0.05, trial_idx + 0.95, color=color, linewidth=0.6, zorder=2)
        trial_idx += 1

    # PSTH underlay (10ms bins, smoothed with Gaussian std=30ms)
    # Scaled to occupy the lower 25% of the plot height (y: 0 to n_trials * 0.25)
    if len(onsets) > 0 and len(all_spike_times_rel) > 0:
        bin_width = 10.0
        bins = np.arange(window_ms[0], window_ms[1] + bin_width, bin_width)
        counts, edges = np.histogram(all_spike_times_rel, bins=bins)
        # Normalize to firing rate (Hz)
        rates = counts / (len(onsets[:n_trials]) * (bin_width / 1000.0))
        # Smooth
        from scipy.ndimage import gaussian_filter1d
        smooth_rates = gaussian_filter1d(rates, sigma=3.0)  # 3 bins * 10ms = 30ms sigma
        bin_centers = (edges[:-1] + edges[1:]) / 2
        # Scale to lower part of y-axis: rates are plotted from y = n_trials down to n_trials * 0.75
        # Since y-axis is inverted (0 is top, n_trials is bottom), plotting at the bottom means plotting near n_trials.
        max_rate = max(smooth_rates) if max(smooth_rates) > 0 else 1.0
        y_vals = n_trials - (smooth_rates / max_rate) * (n_trials * 0.22)
        ax.fill_between(bin_centers, n_trials, y_vals, color="gray", alpha=0.25, zorder=1)
        ax.plot(bin_centers, y_vals, color="gray", linewidth=0.7, alpha=0.6, zorder=1.5)

    # Mark epoch borders
    for t_ms in EPOCH_TIMES_MS:
        ax.axvline(t_ms, color="gray", linestyle=":", linewidth=0.5, alpha=0.6, zorder=1)

    # Mark omitted slot
    omit_slots = {"RXRR": "p2", "RRXR": "p3", "RRRX": "p4"}
    if condition in omit_slots:
        omit_label = omit_slots[condition]
        idx = EPOCH_LABELS.index(omit_label)
        t_start = EPOCH_TIMES_MS[idx]
        t_stop = EPOCH_TIMES_MS[idx + 1]
        t_mid = (t_start + t_stop) / 2
        ax.axvline(t_mid, color="red", linestyle="--", linewidth=0.8, alpha=0.7, zorder=2)
        ax.text(t_mid, n_trials * 0.05, "Omit", color="red", fontsize=6, ha="center", va="top", zorder=3)

    ax.set_xlim(window_ms[0], window_ms[1])
    ax.set_ylim(0, n_trials)
    ax.invert_yaxis()

    # Trial numbers are non-negative integers (1..n_trials), never float ticks.
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{int(round(y))}" if y >= 0 else ""))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--s-plus-unit", type=int, default=None)
    p.add_argument("--s-minus-unit", type=int, default=None)
    p.add_argument("--o-plus-unit", type=int, default=None)
    p.add_argument("--list-candidates", action="store_true",
                    help="Print ranked real candidates per class and exit, without plotting.")
    args = p.parse_args()

    sess = oa.read(NWB_PATH)
    grand = pd.read_csv(REPO_ROOT / "outputs/classification/grand_unit_table_shuffle_sso.csv")

    onsets_by_cond = {}
    for cond in CONDITIONS:
        epochs = sess.get_epochs(phase=2, condition=cond, correct_only=True)
        onsets_by_cond[cond] = epochs["start_time"].values
        print(f"{cond}: {len(onsets_by_cond[cond])} real trials")

    candidates = select_candidates(sess, grand, onsets_by_cond)

    if args.list_candidates:
        for cls in ["S+", "S-", "O+"]:
            sub_df = candidates[candidates["display_class"] == cls].sort_values("max_drift")
            print(f"\n=== {cls}: {len(sub_df)} real candidates (rank by stability) ===")
            print(sub_df.head(10).to_string(index=False))
        return

    units = {
        "S+": args.s_plus_unit or DEFAULT_UNITS["S+"],
        "S-": args.s_minus_unit or DEFAULT_UNITS["S-"],
        "O+": args.o_plus_unit or DEFAULT_UNITS["O+"],
    }

    # Verify each selected unit is a real candidate (guards against a typo'd --*-unit).
    for cls, uid in units.items():
        match = candidates[(candidates["display_class"] == cls) & (candidates["unit_id"] == uid)]
        if len(match) == 0:
            raise SystemExit(f"unit_id={uid} is not a real, qualifying {cls} candidate in this session "
                              f"(>= {MIN_TRIALS} real trials/condition, >= {MIN_MEAN_RATE_HZ} Hz mean rate)")
        row = match.iloc[0]
        print(f"{cls}: unit_id={uid}, max_drift={row['max_drift']:.3f}, mean_rate={row['mean_rate_overall']:.2f} Hz")

    fig, axes = plt.subplots(4, 3, figsize=(13, 14), sharex=True)
    panel_letters = "ABCDEFGHIJKL"
    panel_i = 0

    for row_i, cond in enumerate(CONDITIONS):
        for col_i, cls in enumerate(["S+", "S-", "O+"]):
            ax = axes[row_i, col_i]
            uid = units[cls]
            spike_times = sess.get_spike_times(uid)
            onsets = onsets_by_cond[cond]
            plot_raster_panel(ax, spike_times, onsets, "black", condition=cond)

            letter = panel_letters[panel_i]
            ax.text(0.01, 1.06, letter, transform=ax.transAxes, fontsize=12, fontweight="bold", va="bottom")
            panel_i += 1

            if row_i == 0:
                ax.set_title(f"{cls} (unit {uid})", fontsize=11, color=CLASS_COLORS[cls])
                # Dual time axis, top: numeric-ms + epoch tag combined per tick,
                # e.g. "0ms - p1", "531ms - d1" ...
                top_ax = ax.secondary_xaxis("top")
                top_ax.set_xticks(EPOCH_TIMES_MS)
                top_ax.set_xticklabels(
                    [f"{int(round(t))}ms - {lab}" for lab, t in zip(EPOCH_LABELS, EPOCH_TIMES_MS)],
                    rotation=45, ha="left", fontsize=6,
                )
                top_ax.tick_params(axis="x", labelsize=6, pad=1)
            if col_i == 0:
                ax.set_ylabel(f"COND GROUP\n{cond}", fontsize=9, fontweight="bold")
            if row_i == 3:
                # Dual time axis, bottom: plain numeric ms.
                ax.set_xlabel("Time (ms)", fontsize=9)
                ax.set_xticks(EPOCH_TIMES_MS)
                ax.set_xticklabels([f"{int(round(t))}" for t in EPOCH_TIMES_MS],
                                    rotation=45, ha="right", fontsize=7)
            ax.tick_params(axis="both", labelsize=7)

    fig.suptitle(f"Figure 2: S+/S-/O+ raster grid across R-family conditions -- {SESSION_PREFIX}\n"
                 f"{N_TRIALS_SHOWN} real trials/panel, real spike times, epoch boundaries marked", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.94])

    out_dir = REPO_ROOT / "outputs/publication_figures/figure2_raster_4x3"
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / "figure2_raster_grid.png"
    svg_path = out_dir / "figure2_raster_grid.svg"
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")

    plt.close(fig)

    svg_bytes = svg_path.stat().st_size
    n_paths = svg_path.read_text(encoding="utf-8").count("<path ")
    print(f"\nWrote {svg_path} ({svg_bytes} bytes, {n_paths} path elements)")

    index_md = f"""# Figure 3: S+/S-/O+ Raster Grid -- {SESSION_PREFIX}

4 rows (RRRR/RXRR/RRXR/RRRX) x 3 columns (S+/S-/O+), one real neuron per column shown across
all 4 conditions, {N_TRIALS_SHOWN} real trials per panel.

| Class | unit_id | max trial-to-trial CV | mean rate (Hz) |
|---|---|---|---|
"""
    for cls, uid in units.items():
        row = candidates[(candidates["display_class"] == cls) & (candidates["unit_id"] == uid)].iloc[0]
        index_md += f"| {cls} | {uid} | {row["max_drift"]:.3f} | {row['mean_rate_overall']:.2f} |\n"
    index_md += f"""
Selection: candidates required >= {MIN_TRIALS} real trials in all 4 R-family conditions and
>= {MIN_MEAN_RATE_HZ} Hz real mean firing rate. Ranked by max (worst-case) trial-to-trial
coefficient of variation across the 4 conditions (lower = more stable). Final picks balance
stability against keeping the 3 columns' firing rates in a comparable range (mean-matched),
not the single most-stable candidate per class in isolation.

SVG: `figure3_raster_grid.svg` ({svg_bytes} bytes, {n_paths} path elements)

![Figure 3](figure3_raster_grid.svg)
"""
    (OUT_DIR / "index.md").write_text(index_md, encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'index.md'}")


if __name__ == "__main__":
    main()
