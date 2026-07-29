"""
cnsplots engine vendored and adapted for jnwb.viz

Provides publication-grade multi-panel figure layout management,
statistical annotation overlays, omission-palette theme integration,
and Adobe Illustrator-compatible vector SVG post-processing (via mutool).

Original cnsplots concept by Farid Rashidi (2026).
Adapted for omission electrophysiology suite (jnwb).
"""

import os
import shutil
import subprocess
import logging
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

log = logging.getLogger(__name__)

# Omission Palette Canonical Hex Codes
OMISSION_PALETTE = {
    "gold": "#CFB87C",      # Theta / p1
    "blue": "#1565C0",      # Alpha / S1 / p1
    "violet": "#9400D3",    # Beta / S2 / p2
    "green": "#2E7D32",     # Gamma / S3 / p3
    "gray": "#757575",      # Delays / background
    "dark_bg": "#121212",
    "white": "#FFFFFF",
}

# Global SVG font setting for editable text in vector editors
plt.rcParams['svg.fonttype'] = 'none'
plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
plt.rcParams['font.family'] = 'sans-serif'


def bind_omission_palette():
    """Set Matplotlib default color cycle to canonical omission palette."""
    colors = [
        OMISSION_PALETTE["blue"],
        OMISSION_PALETTE["gold"],
        OMISSION_PALETTE["violet"],
        OMISSION_PALETTE["green"],
        OMISSION_PALETTE["gray"]
    ]
    plt.rcParams['axes.prop_cycle'] = plt.cycler(color=colors)


class MultiPanelCanvas:
    """
    Declarative multi-panel grid manager for publication figures.
    Allocates panels with automated panel lettering (A, B, C...).
    """
    def __init__(self, fig_width_mm: float = 180.0, aspect_ratio: float = 0.75, title: Optional[str] = None):
        self.fig_width_in = fig_width_mm / 25.4
        self.fig_height_in = self.fig_width_in * aspect_ratio
        self.fig = plt.figure(figsize=(self.fig_width_in, self.fig_height_in))
        self.panels: Dict[str, plt.Axes] = {}
        self.panel_counter = 0
        if title:
            self.fig.suptitle(title, fontsize=12, fontweight='bold')

    def add_panel(
        self,
        label: Optional[str] = None,
        rect: Tuple[float, float, float, float] = (0.1, 0.1, 0.8, 0.8),
        facecolor: str = 'none'
    ) -> plt.Axes:
        """
        Add a panel using normalized coordinates (left, bottom, width, height).
        Automatically assigns label 'A', 'B', 'C' if label is None.
        """
        if label is None:
            label = chr(65 + self.panel_counter)
            self.panel_counter += 1

        ax = self.fig.add_axes(rect, facecolor=facecolor)
        ax.text(
            -0.08, 1.05, label,
            transform=ax.transAxes,
            fontsize=12,
            fontweight='bold',
            va='bottom',
            ha='right'
        )
        self.panels[label] = ax
        return ax

    def add_grid_panels(self, rows: int, cols: int, labels: Optional[List[str]] = None) -> Dict[str, plt.Axes]:
        """Add grid of panels with automated labels."""
        gs = gridspec.GridSpec(rows, cols, figure=self.fig)
        idx = 0
        for r in range(rows):
            for c in range(cols):
                label = labels[idx] if labels and idx < len(labels) else chr(65 + self.panel_counter)
                self.panel_counter += 1
                ax = self.fig.add_subplot(gs[r, c])
                ax.text(
                    -0.08, 1.05, label,
                    transform=ax.transAxes,
                    fontsize=12,
                    fontweight='bold',
                    va='bottom',
                    ha='right'
                )
                self.panels[label] = ax
                idx += 1
        return self.panels


def add_stat_annotation(
    ax: plt.Axes,
    x1: float,
    x2: float,
    y: float,
    h: float,
    p_val: float,
    text: Optional[str] = None,
    color: str = "#333333"
):
    """
    Draw a statistical comparison bar between x1 and x2 at height y.
    P-value formatting: *** (p<0.001), ** (p<0.01), * (p<0.05), ns (p>=0.05).
    """
    if text is None:
        if p_val < 0.001:
            text = "***"
        elif p_val < 0.01:
            text = "**"
        elif p_val < 0.05:
            text = "*"
        else:
            text = "ns"

    ax.plot([x1, x1, x2, x2], [y, y + h, y + h, y], color=color, lw=1.0)
    ax.text((x1 + x2) * 0.5, y + h + (h * 0.2), text, ha='center', va='bottom', color=color, fontsize=9, fontweight='bold')


def savefig(
    fig: plt.Figure,
    filepath: Union[str, Path],
    dpi: int = 300,
    use_mutool: bool = True
) -> Path:
    """
    Save figure as SVG/PNG/PDF.
    If SVG and use_mutool is True, checks for 'mutool' to post-process SVG text.
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    fig.savefig(filepath, dpi=dpi, bbox_inches='tight')

    if filepath.suffix.lower() == '.svg' and use_mutool:
        mutool_path = shutil.which('mutool')
        if mutool_path:
            try:
                cmd = [mutool_path, "clean", str(filepath), str(filepath)]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                log.info(f"Successfully cleaned SVG with mutool: {filepath}")
            except Exception as e:
                log.warning(f"mutool post-processing failed, fallback to native SVG: {e}")
        else:
            log.info("mutool not found on PATH; native Matplotlib vector SVG saved cleanly.")

    return filepath
