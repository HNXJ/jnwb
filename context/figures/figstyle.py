r"""
The template every omission-a figure draws against.

WHY THIS EXISTS
    Figures 1, 4 and 5 already share a look: Cambria text, the same five band colours, the
    same epoch shading, the same green omission-onset marker, the same trial timing. Figures
    2 and 3 had to be rebuilt from scratch and would otherwise have drifted. Putting the
    template in one module makes "identical template and colouring" a property of the code
    rather than of anyone's attention.

    This is not a figure script. It draws nothing on its own and owns no analysis. Each
    figNN_*.py imports what it needs from here.

TIMING
    Trial is fx-p1-d1-p2-d2-p3-d3-p4-d4. Presentations are 531 ms, delays 500 ms, so slot k
    opens at (k-1)*1031 ms from p1. An omission replaces one presentation with a third
    identical blank period, and the omitted slot is the middle one of the three.
"""
from __future__ import annotations

import matplotlib
import numpy as np

# ---------------------------------------------------------------- timing ----
STIM_MS, DELAY_MS = 531, 500
SLOT_PERIOD_MS = STIM_MS + DELAY_MS                     # 1031
EPOCH_ONSETS_MS = {"fx": -500, "p1": 0, "d1": 531, "p2": 1031, "d2": 1562,
                   "p3": 2062, "d3": 2593, "p4": 3093, "d4": 3624}

# Windows drawn around an omission at t = 0, in ms.
PREV_STIM = (-SLOT_PERIOD_MS, -DELAY_MS)   # p(k-1)
OMISSION = (0, STIM_MS)                    # the omitted slot
NEXT_STIM = (SLOT_PERIOD_MS, SLOT_PERIOD_MS + STIM_MS)   # p(k+1); p4 omissions have none
SLOT4_END = 897                            # last sample a p4 omission can contribute

# ---------------------------------------------------------------- colour ----
# Five bands, in the settled house set. Do not re-drift: theta 4-8, alpha 8-14,
# beta 14-30, low gamma 30-50, high gamma 50-80 Hz.
BANDS = {"Theta (4-8 Hz)": (4, 8), "Alpha (8-14 Hz)": (8, 14), "Beta (14-30 Hz)": (14, 30),
         "Low gamma (30-50 Hz)": (30, 50), "High gamma (50-80 Hz)": (50, 80)}
BAND_COLORS = ["#0000EE", "#EE0000", "#FF8C00", "#FF00FF", "#00A000"]

# Ten analysis areas, in hierarchy order. V3a/d is the inclusive label for V3, V3a and V3d.
AREA_ORDER = ["V1", "V2", "V3a/d", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]
AREA_COLORS = {"V1": "#08306B", "V2": "#2171B5", "V3a/d": "#4292C6", "V4": "#6BAED6",
               "MT": "#41AB5D", "MST": "#238B45", "TEO": "#FDAE6B", "FST": "#F16913",
               "FEF": "#D94801", "PFC": "#A63603"}
AREA_POOL = {"V3": "V3a/d", "V3a": "V3a/d", "V3d": "V3a/d"}

# Response classes. O++/O-- carry the ramp conjunction on top of the peak/trough test.
CLASS_ORDER = ["O++", "O+", "ns", "O-", "O--"]
CLASS_COLORS = {"O++": "#7A0177", "O+": "#C51B8A", "ns": "#BDBDBD",
                "O-": "#2C7FB8", "O--": "#253494"}

# Shading and markers, shared by every panel that has a time axis.
STIM_SHADE = "#F8C6C6"          # a real presentation
OMIT_SHADE = "#E7D3F0"          # the omitted slot
ONSET_COLOR = "green"           # omission onset, t = 0
FLANK_SHADE = "#EAEAEA"         # the two flanking delays used as the Q1 control

# Per-slot colours for a FULL-TRIAL time axis (p1 onset at t = 0), as opposed to the
# omission-centred shading above. p1 yellow, p2 pink, p3 green, p4 blue -- each presentation
# gets its own colour rather than one colour for "a real stimulus", so a reader can tell which
# slot a transient belongs to without reading the x-axis.
SLOT_COLORS = ["#FFF3B0", "#F6C9E0", "#BFE6C6", "#C9D6F2"]
FULL_TRIAL_WIN = (-600, 4200)


def use_house_style():
    """Cambria everywhere, vector text, sizes that survive a 2-column reduction."""
    matplotlib.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Cambria", "Georgia", "DejaVu Serif"],
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "axes.linewidth": 0.8,
        "svg.fonttype": "none",     # keep text editable in Illustrator
        "pdf.fonttype": 42,
    })


def mark_omission_axis(ax, win=(-1500, 1500), next_stim=True, flanks=False):
    """Shade the epochs and mark omission onset on a time axis in ms from the omitted slot."""
    ax.axvspan(*PREV_STIM, color=STIM_SHADE, alpha=0.40, zorder=0)
    ax.axvspan(*OMISSION, color=OMIT_SHADE, alpha=0.50, zorder=0)
    if flanks:
        ax.axvspan(PREV_STIM[1], OMISSION[0], color=FLANK_SHADE, alpha=0.6, zorder=0)
        ax.axvspan(OMISSION[1], OMISSION[1] + DELAY_MS, color=FLANK_SHADE, alpha=0.6, zorder=0)
    if next_stim and win[1] > NEXT_STIM[0]:
        ax.axvspan(NEXT_STIM[0], min(NEXT_STIM[1], win[1]), color=STIM_SHADE,
                   alpha=0.20, zorder=0)
    ax.axvline(0, color=ONSET_COLOR, ls="--", lw=1.5, zorder=4)
    ax.set_xlim(*win)


def full_trial_ticks():
    """Tick positions and labels at every epoch boundary, p1-aligned (t = 0)."""
    order = ["fx", "p1", "d1", "p2", "d2", "p3", "d3", "p4", "d4"]
    ticks = [EPOCH_ONSETS_MS[o] for o in order] + [EPOCH_ONSETS_MS["d4"] + 500]
    labels = [f"{EPOCH_ONSETS_MS[o]:.0f}ms - {o}" for o in order] + \
        [f"{EPOCH_ONSETS_MS['d4'] + 500:.0f}ms - end"]
    return ticks, labels


def mark_full_trial_axis(ax, win=FULL_TRIAL_WIN, omit_slot=None):
    """Shade the four presentation slots on a p1-aligned full-trial time axis.

    `omit_slot` (2, 3 or 4) marks that slot as omitted -- a dashed red line labelled "Omit"
    instead of a slot colour, since in an omission trial that period is visually identical to
    a delay and colouring it the same as a real presentation would misrepresent the display.
    """
    for k in range(4):
        if omit_slot == k + 1:
            continue
        a, b = EPOCH_ONSETS_MS[f"p{k + 1}"], EPOCH_ONSETS_MS[f"d{k + 1}"]
        ax.axvspan(a, b, color=SLOT_COLORS[k], alpha=0.9, zorder=0)
    if omit_slot:
        mid = EPOCH_ONSETS_MS[f"p{omit_slot}"]
        ax.axvline(mid, color="red", ls="--", lw=1.3, zorder=4)
        ax.text(mid, 0.98, "Omit", color="red", fontsize=7, ha="center", va="top",
               transform=ax.get_xaxis_transform(), zorder=5)
    ax.set_xlim(*win)


def grating_strip(width=700, height=60, cycles=12):
    """The drifting-grating screen strip drawn above spectrograms and rasters."""
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    xx, yy = np.meshgrid(x, y)
    return 0.5 + 0.5 * np.sin(2 * np.pi * cycles * (xx + 0.55 * yy))


def clopper_pearson(k, n, alpha=0.05):
    """Exact binomial interval. Proportions here get this, never a bootstrap."""
    from scipy import stats as sst
    k, n = int(k), int(n)
    if n == 0:
        return (np.nan, np.nan)
    lo = 0.0 if k == 0 else sst.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else sst.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return (float(lo), float(hi))


def stat_bracket(ax, x1, x2, y, h, result, use="p_holm", color="#333333"):
    """Draw a significance bracket between x1 and x2 from a figstats.Result.

    Reads `result.p_holm` by default -- the family-wise correction figstats.py's own docs
    say "the headline claims use" -- not the raw p, so a panel can never show a more
    optimistic number than the table it sits beside. Appends "dagger" when the result's
    `unit` is not session/animal, matching the table's own descriptive-only marker, so a
    per-unit or per-channel result can't read as a population claim on the figure either.
    """
    from figstats import INFERENTIAL_UNITS
    p = getattr(result, use)
    if not np.isfinite(p):
        text = "--"
    elif p < 0.001:
        text = "***"
    elif p < 0.01:
        text = "**"
    elif p < 0.05:
        text = "*"
    else:
        text = "ns"
    if result.unit not in INFERENTIAL_UNITS:
        text += "†"
    ax.plot([x1, x1, x2, x2], [y, y + h, y + h, y], color=color, lw=1.0)
    ax.text((x1 + x2) * 0.5, y + h, text, ha="center", va="bottom", color=color,
            fontsize=9, fontweight="bold")
    return text


def save(fig, fig_dir, name, dpi=300, clean_svg=True):
    """Every panel is written as both SVG (for assembly) and PNG (for quick review).

    When `mutool` is on PATH, the SVG is cleaned after writing -- byte-level only, no
    visual change, text stays editable (svg.fonttype is already "none"). Silently skipped
    when mutool isn't available, which is the common case (e.g. CI).
    """
    import os
    os.makedirs(fig_dir, exist_ok=True)
    svg = os.path.join(fig_dir, name + ".svg")
    fig.savefig(svg)
    fig.savefig(os.path.join(fig_dir, name + ".png"), dpi=dpi)
    if clean_svg:
        import shutil
        import subprocess
        import logging
        mutool = shutil.which("mutool")
        if mutool:
            try:
                subprocess.run([mutool, "clean", svg, svg], check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except Exception as e:
                logging.getLogger(__name__).warning(
                    f"mutool cleanup failed for {svg}, keeping native SVG: {e}")
    return svg
