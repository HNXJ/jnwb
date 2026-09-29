"""One style for every documentation figure: font family, size tiers and figure width.

Every page shows a figure at the full width of its column, so a figure's width decides how large
its text renders. One width for all of them makes one point size render at one pixel size on
every page: at 7.2 in shown 688 px wide, 7.5 pt renders at 10 px.
"""
from __future__ import annotations

import matplotlib.pyplot as plt

FAMILY = "sans-serif"
#: Size tiers, in points: panel titles, axis labels, and everything smaller (ticks, legends,
#: annotations).
TITLE = 9.5
LABEL = 8.5
SMALL = 7.5
#: Figure width in inches, and the resolution the PNG is written at.
WIDTH = 7.2
DPI = 180

RC = {
    "font.family": FAMILY,
    "font.size": LABEL,
    "axes.titlesize": TITLE,
    "axes.labelsize": LABEL,
    "xtick.labelsize": SMALL,
    "ytick.labelsize": SMALL,
    "legend.fontsize": SMALL,
    "figure.titlesize": TITLE,
    "axes.linewidth": 0.8,
    "axes.facecolor": "none",
    "figure.facecolor": "none",
    "savefig.transparent": True,
}


def apply() -> None:
    """Set the family, the size tiers and a transparent background for the figures that follow."""
    plt.rcParams.update(RC)
