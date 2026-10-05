"""One style for every documentation figure: palette, named-variable colours, text sizes, line
widths, spines and figure width.

Every page shows a figure at the full width of its column, so a figure's width decides how large
its text renders. One width for all of them makes one point size render at one pixel size on
every page: at 7.2 in shown 688 px wide, 8 pt renders at 10 px.

Nothing here is drawn from a figure's own code: a generator takes its colours, sizes and widths
from this module, and `tests/test_figure_form.py` reads the rendered figures against it.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
from cycler import cycler

#: Arial first. The later families only draw where Arial is not installed.
FAMILY = ["Arial", "DejaVu Sans"]
#: Size tiers, in points: panel titles, axis labels, and everything smaller (ticks, legends,
#: annotations). The panel letter is the largest text on a figure.
LETTER = 11.0
TITLE = 10.0
LABEL = 9.0
SMALL = 8.0
#: Every text size on a figure lies in this range, in points.
TEXT_RANGE_PT = (8.0, 11.0)
#: Figure width in inches, and the resolution the PNG is written at.
WIDTH = 7.2
DPI = 180

#: Series colours in the order a categorical comparison takes them.
SERIES = ("#1565c0", "#ff9800", "#00acc1", "#e53935")
#: The highlight that marks a window or band over them, by theme. The dark theme draws #cfb87c;
#: on the light page that colour reaches 1.94, so the light theme draws the same hue darkened
#: until it reaches 2.0, the bar for a fixed colour. Each is read against its own page.
THEMES = {"light": {"highlight": "#cdb577"}, "dark": {"highlight": "#cfb87c"}}
HIGHLIGHT = {theme: colours["highlight"] for theme, colours in THEMES.items()}
#: Reference lines, noise and the veil over excluded data: a colour that is no series.
NEUTRAL = "#888888"

#: One colour per named variable, in every figure that draws the variable.
VARIABLE = {
    "observed": SERIES[3],
    "truth": SERIES[1],
    "fitted": SERIES[0],
    "smoothed": SERIES[2],
    "baseline": SERIES[2],
}
#: One colour per cortical area, separable under protan, deutan and tritan simulation.
AREA = {"V1": SERIES[0], "V2": SERIES[1], "V3": SERIES[2]}

#: Data line widths, in points: a reference or thin trace, a data trace, an emphasised fit.
LINE_RANGE_PT = (1.2, 1.8)
LW_THIN = 1.2
LW = 1.5
LW_THICK = 1.8
#: The outline of a bar or histogram patch: an edge, not a data line.
EDGE = 0.6

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
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.unicode_minus": True,
    "axes.prop_cycle": cycler(color=list(SERIES)),
    "lines.linewidth": LW,
    "axes.facecolor": "none",
    "figure.facecolor": "none",
    "savefig.transparent": True,
}


def apply() -> None:
    """Set the style for the figures that follow."""
    plt.rcParams.update(RC)


def num(value: float, spec: str = ".2f") -> str:
    """`value` formatted by `spec` with a true minus sign (U+2212) for a negative number."""
    return format(value, spec).replace("-", "−")


def panel_title(ax, letter: str, text: str, **kw):
    """Left-aligned panel title with its bold letter set outside it, to its left."""
    title = ax.set_title(text, loc="left", pad=8, **kw)
    ax.annotate(letter, xy=(0, 1), xycoords=title, xytext=(-4, 0), textcoords="offset points",
                ha="right", va="top", fontsize=LETTER, fontweight="bold")
    return title
