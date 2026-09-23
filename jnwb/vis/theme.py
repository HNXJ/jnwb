"""
jnwb.vis.theme -- Publication-grade styling, colorblind-safe palettes, and typography for Plotly.

Enforces Nature / Neuron / Science publication standards:
- Pure white canvas backgrounds
- Hairline axes spines (0.75-1.0 px) in neutral dark gray/black
- Strict sans-serif typography (Helvetica/Arial)
- Colorblind-accessible discrete palettes (Paul Tol, Okabe-Ito, Nature Muted)
- Continuous colormaps (Magma, Viridis, Plasma, Cividis, RdBu_r)
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence
import plotly.graph_objects as go


# ==============================================================================
# 1. Colorblind-Safe Palettes & Scientific Accents
# ==============================================================================

# Paul Tol Muted (Qualitative 8-color palette, colorblind safe)
TOL_MUTED = [
    "#88CCEE",  # Cyan
    "#44AA99",  # Teal
    "#117733",  # Green
    "#332288",  # Indigo
    "#DDCC77",  # Sand
    "#999933",  # Olive
    "#CC6677",  # Rose
    "#882255",  # Wine
    "#AA4499",  # Purple
]

# Okabe-Ito (Universal colorblind-safe palette)
OKABE_ITO = [
    "#E69F00",  # Orange
    "#56B4E9",  # Sky Blue
    "#009E73",  # Bluish Green
    "#F0E442",  # Yellow
    "#0072B2",  # Blue
    "#D55E00",  # Vermilion
    "#CC79A7",  # Reddish Purple
    "#000000",  # Black
]

# Nature Scientific Accents (High-contrast publication palette)
NATURE_ACCENTS = [
    "#2C3E50",  # Midnight Blue / Neutral Dark
    "#C0392B",  # Crimson / Strong Accent (the condition of interest)
    "#2980B9",  # Royal Blue / Reference Condition
    "#27AE60",  # Emerald Green
    "#8E44AD",  # Wisteria Purple
    "#D35400",  # Rust Orange
    "#7F8C8D",  # Slate Gray / Baseline / Control
]

COLOR_PALETTES: Dict[str, List[str]] = {
    "tol_muted": TOL_MUTED,
    "okabe_ito": OKABE_ITO,
    "nature": NATURE_ACCENTS,
}


# ==============================================================================
# 2. Typography & Sizing Constants
# ==============================================================================

FONT_FAMILY = "Helvetica, Arial, DejaVu Sans, sans-serif"

# Font size hierarchy (CSS pixels for 96 DPI screen / print export)
FONT_SIZES = {
    "tick": 10,       # 7.5 pt print
    "axis_label": 11, # 8.5 pt print
    "title": 12,      # 9.0 pt print
    "panel_tag": 14,  # 10.5 pt bold print
    "annotation": 10, # 7.5 pt print
}

COLORS = {
    "bg": "#FFFFFF",
    "paper_bg": "#FFFFFF",
    "text": "#1A1A1A",
    "text_muted": "#555555",
    "spine": "#2C3E50",
    "grid": "#F0F3F4",
    "zero_line": "#7F8C8D",
    "crossover": "#C0392B",
}


# ==============================================================================
# 3. Theme Application Helpers
# ==============================================================================

def get_publication_layout_template() -> go.layout.Template:
    """Construct a Plotly Template adhering to Nature/Neuron publication guidelines."""
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family=FONT_FAMILY, size=FONT_SIZES["tick"], color=COLORS["text"]),
        paper_bgcolor=COLORS["paper_bg"],
        plot_bgcolor=COLORS["bg"],
        margin=dict(l=50, r=30, t=30, b=40, pad=2),
        hoverlabel=dict(
            bgcolor="white",
            font_size=FONT_SIZES["annotation"],
            font_family=FONT_FAMILY,
            font_color=COLORS["text"],
        ),
        xaxis=dict(
            showline=True,
            linewidth=1.0,
            linecolor=COLORS["spine"],
            ticks="outside",
            ticklen=4,
            tickwidth=1.0,
            tickcolor=COLORS["spine"],
            tickfont=dict(size=FONT_SIZES["tick"]),
            title=dict(font=dict(size=FONT_SIZES["axis_label"], color=COLORS["text"])),
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(
            showline=True,
            linewidth=1.0,
            linecolor=COLORS["spine"],
            ticks="outside",
            ticklen=4,
            tickwidth=1.0,
            tickcolor=COLORS["spine"],
            tickfont=dict(size=FONT_SIZES["tick"]),
            title=dict(font=dict(size=FONT_SIZES["axis_label"], color=COLORS["text"])),
            showgrid=False,
            zeroline=False,
        ),
    )
    return template


def apply_publication_theme(fig: go.Figure) -> go.Figure:
    """Apply publication template and default font/margins to a Plotly figure."""
    fig.layout.template = get_publication_layout_template()
    return fig


def configure_axis(
    axis_dict: Dict[str, Any],
    title: str | None = None,
    showgrid: bool = False,
    zeroline: bool = False,
    zerolinecolor: str = COLORS["zero_line"],
    zerolinewidth: float = 0.75,
) -> Dict[str, Any]:
    """Configure standard publication parameters on an axis dictionary."""
    axis_dict.update({
        "showline": True,
        "linewidth": 1.0,
        "linecolor": COLORS["spine"],
        "ticks": "outside",
        "ticklen": 4,
        "tickwidth": 1.0,
        "tickcolor": COLORS["spine"],
        "tickfont": dict(family=FONT_FAMILY, size=FONT_SIZES["tick"], color=COLORS["text"]),
        "showgrid": showgrid,
        "gridcolor": COLORS["grid"],
        "gridwidth": 0.5,
        "zeroline": zeroline,
        "zerolinecolor": zerolinecolor,
        "zerolinewidth": zerolinewidth,
    })
    if title is not None:
        axis_dict["title"] = dict(
            text=title,
            font=dict(family=FONT_FAMILY, size=FONT_SIZES["axis_label"], color=COLORS["text"]),
        )
    return axis_dict
