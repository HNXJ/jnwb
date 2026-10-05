"""One style for every documentation figure: palette, named-variable colours, text sizes, line
widths, spines and figure width.

Every page shows a figure at the full width of its column, so a figure's width decides how large
its text renders. One width for all of them makes one point size render at one pixel size on
every page: at 7.2 in shown 688 px wide, 8 pt renders at 10 px.

Nothing here is drawn from a figure's own code: a generator takes its colours, sizes and widths
from this module, and `tests/test_figure_form.py` reads the rendered figures against it.
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib.pyplot as plt
from cycler import cycler
from matplotlib import font_manager

#: Liberation Sans, which has Arial's metrics and is one file on every machine, so a figure
#: renders the same pixels on Windows and Linux. No fallback family: a machine without the font
#: stops generation (`FontMissing`) instead of drawing a different figure.
FONT = "Liberation Sans"
#: The directory holding the two font files below; `apply` registers them with Matplotlib.
FONT_DIR_ENV = "JNWB_FIGURE_FONT_DIR"
FONT_FILES = ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf")
FAMILY = [FONT]
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


class FontMissing(RuntimeError):
    """The figure font is not registered with Matplotlib."""


def register_font() -> None:
    """Register the font files in the directory `FONT_DIR_ENV` names."""
    directory = os.environ.get(FONT_DIR_ENV)
    if not directory:
        return
    for name in FONT_FILES:
        path = Path(directory) / name
        if path.is_file():
            font_manager.fontManager.addfont(str(path))


def check_font() -> None:
    """Raise `FontMissing` unless the regular and the bold file of `FONT` are the ones Matplotlib
    resolves, so a bold request cannot pass on the regular file."""
    for weight, name in zip(("normal", "bold"), FONT_FILES):
        try:
            found = font_manager.findfont(
                font_manager.FontProperties(family=FONT, weight=weight), fallback_to_default=False)
        except ValueError:
            found = ""
        if Path(found).name != name:
            raise FontMissing(
                f"font {FONT!r} ({name}) is not registered: set {FONT_DIR_ENV} to the directory "
                f"holding {', '.join(FONT_FILES)}")


def apply() -> None:
    """Set the style for the figures that follow, registering the figure font first."""
    register_font()
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
