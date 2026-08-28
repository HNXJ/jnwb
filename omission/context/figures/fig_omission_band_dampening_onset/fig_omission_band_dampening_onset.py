r"""
Two-panel figure over scripts/aggregate_omission_band_dampening_onset.py's output:

  (a) MAGNITUDE barplot -- per area (x), one bar per band (grouped, house band colours):
      mean session-level dB re baseline in the p2 window (1031-1562 ms from p1) during RXRR
      (p2 omitted). Bars for cells that do NOT survive BH correction (q_bh > 0.05) are drawn
      at reduced alpha with a hatch, not hidden -- a non-significant cell is a result, not a
      gap (see project doctrine: "a valid null is a result").

  (b) ONSET-TIMING panel -- per area x band with a reliable cluster (omission_onset_ms not
      null), a point at the dampening onset (ms from p1) with its bootstrap 95% CI whisker,
      grouped by area, coloured by band, areas ordered top-to-bottom by their EARLIEST
      reliable band onset (so "which area goes down sooner" reads directly off the y-axis
      order). Each area's own real-stimulus response onset (RRRR, the causal floor) is drawn
      as a black diamond -- every dampening point must fall at or to the right of it; any cell
      the aggregation script flagged causality_ok=False is marked with a red outline and
      annotated, not hidden.

STATUS: exploratory, not yet a numbered fig0N_*.py -- same convention as
fig_v1_omission_band_dynamics/ (own docstring: "not wired into the manuscript figure
pipeline"). Uses figstyle (house colours/fonts) and reads the aggregation script's CSVs
directly; draws nothing on its own and computes no statistic itself.

OUTPUT
    svg/fig_omission_band_dampening_onset.svg/.png
"""
from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.dirname(HERE)
REPO = os.path.dirname(FIGDIR)
REPO = os.path.dirname(REPO)
sys.path.insert(0, FIGDIR)
from figstyle import (use_house_style, save, AREA_ORDER, AREA_COLORS,  # noqa: E402
                      BAND_COLORS, AREA_POOL)

BANDS = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]
BAND_LABELS = {"theta": "Theta (4-8)", "alpha": "Alpha (8-14)", "beta": "Beta (14-30)",
              "low_gamma": "Low-γ (30-50)", "high_gamma": "High-γ (50-80)"}
BAND_COLOR = dict(zip(BANDS, BAND_COLORS))

MAG_CSV = os.path.join(REPO, "outputs", "classification", "omission_band_dampening_magnitude.csv")
ONSET_CSV = os.path.join(REPO, "outputs", "classification", "omission_band_dampening_onset.csv")
SVG_DIR = os.path.join(HERE, "svg")

Q_ALPHA = 0.05


def panel_magnitude(ax, mag):
    mag = mag.copy()
    mag["area"] = mag["area"].map(lambda a: AREA_POOL.get(a, a))
    areas = [a for a in AREA_ORDER if a in mag["area"].unique()]
    x = np.arange(len(areas))
    width = 0.15
    for bi, band in enumerate(BANDS):
        vals, sig = [], []
        for area in areas:
            cell = mag[(mag.area == area) & (mag.band == band)]
            if cell.empty:
                vals.append(np.nan)
                sig.append(False)
                continue
            vals.append(float(cell["mean_db"].iloc[0]))
            sig.append(bool(cell["q_bh"].iloc[0] <= Q_ALPHA) if pd.notna(cell["q_bh"].iloc[0]) else False)
        xpos = x + (bi - 2) * width
        for xi, v, s in zip(xpos, vals, sig):
            if np.isnan(v):
                continue
            ax.bar(xi, v, width=width * 0.92, color=BAND_COLOR[band],
                  alpha=1.0 if s else 0.30, edgecolor="black",
                  linewidth=0.5, hatch=None if s else "//", zorder=3)
    ax.axhline(0, color="black", lw=0.8, zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels(areas, fontsize=9)
    ax.set_ylabel("Mean dB re baseline\n(p2 window, RXRR)", fontsize=9)
    ax.set_title("(a) Band power change during omission, by area\n"
                 "solid = q$_{BH}$ ≤ 0.05; hatched/faint = not significant", fontsize=9.5)
    handles = [Patch(facecolor=BAND_COLOR[b], edgecolor="black", label=BAND_LABELS[b])
              for b in BANDS]
    ax.legend(handles=handles, fontsize=7, ncol=5, loc="upper center",
             bbox_to_anchor=(0.5, -0.18), frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def panel_onset(ax, onset):
    rows = onset[onset.omission_onset_ms.notna()].copy()
    if rows.empty:
        ax.text(0.5, 0.5, "no area x band cell had a reliable cluster onset",
               ha="center", va="center", transform=ax.transAxes)
        return
    earliest = rows.groupby("area")["omission_onset_ms"].min().to_dict()
    areas_with_onset = sorted(earliest, key=lambda a: earliest[a])
    y_of_area = {a: i for i, a in enumerate(areas_with_onset)}

    for _, r in rows.iterrows():
        y = y_of_area[r.area] + (BANDS.index(r.band) - 2) * 0.13
        lo, hi = r.omission_onset_ci_lo_ms, r.omission_onset_ci_hi_ms
        xerr = None
        if pd.notna(lo) and pd.notna(hi):
            xerr = [[max(r.omission_onset_ms - lo, 0)], [max(hi - r.omission_onset_ms, 0)]]
        ax.errorbar([r.omission_onset_ms], [y], xerr=xerr, fmt="o",
                   color=BAND_COLOR[r.band], ecolor=BAND_COLOR[r.band], elinewidth=1.0,
                   capsize=2, markersize=5.5, zorder=4)
        if pd.notna(r.stim_response_onset_ms):
            ax.plot([r.stim_response_onset_ms], [y], marker="D", color="0.55",
                   markersize=4.0, zorder=3)

    ax.set_yticks([y_of_area[a] for a in areas_with_onset])
    ax.set_yticklabels(areas_with_onset, fontsize=9)
    ax.invert_yaxis()   # earliest (top of the sorted list) drawn at the top
    ax.axvline(1031, color="0.5", ls=":", lw=1.0, zorder=1)
    ax.text(1031, -0.7, "p2 onset", color="0.5", fontsize=7, ha="center", va="bottom")
    ax.set_xlabel("Time from p1 onset (ms)", fontsize=9)
    ax.set_title("(b) Omission-dampening onset (RXRR-RRRR paired difference) by area,\n"
                 "earliest band first  --  ● = onset (95% bootstrap CI); "
                 "◇ grey = RRRR-alone response onset (diagnostic only)", fontsize=9.5)
    handles = [Patch(facecolor=BAND_COLOR[b], edgecolor="black", label=BAND_LABELS[b])
              for b in BANDS]
    ax.legend(handles=handles, fontsize=7, ncol=5, loc="upper center",
             bbox_to_anchor=(0.5, -0.14), frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def main():
    use_house_style()
    mag = pd.read_csv(MAG_CSV)
    onset = pd.read_csv(ONSET_CSV)

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.6))
    panel_magnitude(axes[0], mag)
    panel_onset(axes[1], onset)

    suptitle = ("Omission-triggered band-power dampening: magnitude and onset timing, per area "
               "(onset = paired RXRR-RRRR difference, causally floored at p2 onset by design)")
    fig.suptitle(suptitle, fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.94])

    out = save(fig, SVG_DIR, "fig_omission_band_dampening_onset", dpi=200)
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
