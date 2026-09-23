"""
jnwb.vis.spectral -- Publication-grade spectral modulation and functional connectivity in pure Plotly.

Implements Motif 4 (Bastos 2020, Mendoza-Halliday 2024, Westerberg 2024):
- Area x Frequency Band modulation matrices with significance markers from a caller-supplied mask
- Directed Granger causality spectra for both directions of a pair, with caller-supplied null ribbons

No statistic is computed here: every mask, interval and null is a caller input.
- Phase-Amplitude Coupling (PAC) comodulograms
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import plotly.graph_objects as go

from .canvas import PlotlyPublicationCanvas
from .theme import COLORS, FONT_FAMILY, FONT_SIZES, configure_axis


def plot_spectral_modulation_matrix(
    canvas: PlotlyPublicationCanvas,
    row: int,
    col: int,
    delta_db_matrix: np.ndarray,
    areas: Sequence[str],
    bands: Sequence[str],
    sig_mask: Optional[np.ndarray] = None,
    cmap: str = "RdBu_r",
    title: Optional[str] = "Spectral Modulation (ΔdB)",
    colorbar_title: str = "ΔdB",
) -> None:
    """
    Render an Area x Band spectral modulation matrix with significance markers from ``sig_mask``.

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        delta_db_matrix: 2D array of shape [n_areas, n_bands].
        areas: List of area names.
        bands: List of frequency band names (e.g. ['θ', 'α', 'β', 'low γ', 'high γ']).
        sig_mask: Boolean 2D array of cells to mark, computed by the caller (for example
            ``jnwb.fdr_correct`` q-values at or below 0.05).
        cmap: Diverging colormap name (default 'RdBu_r' centered at 0).
        title: Panel title.
        colorbar_title: Title for colorbar.
    """
    x_axis, y_axis = canvas.get_axis_names(row, col)

    delta_db_matrix = np.asarray(delta_db_matrix, dtype=float)

    # Symmetric scale around zero
    vmax = float(np.percentile(np.abs(delta_db_matrix), 98))
    vmin = -vmax

    cb_cfg = canvas.get_colorbar_config(row, col, title=colorbar_title)
    heatmap = go.Heatmap(
        x=bands,
        y=areas,
        z=delta_db_matrix,
        colorscale=cmap,
        zmin=vmin,
        zmax=vmax,
        colorbar=cb_cfg,
        xaxis=x_axis,
        yaxis=y_axis,
        hovertemplate="Area: %{y}<br>Band: %{x}<br>ΔdB: %{z:.2f}<extra></extra>",
    )
    canvas.fig.add_trace(heatmap)

    # Annotate significant cells (asterisk or border)
    if sig_mask is not None:
        sig_mask = np.asarray(sig_mask, dtype=bool)
        for i, area in enumerate(areas):
            for j, band in enumerate(bands):
                if sig_mask[i, j]:
                    canvas.fig.add_annotation(
                        x=band,
                        y=area,
                        xref=x_axis,
                        yref=y_axis,
                        text="<b>*</b>",
                        showarrow=False,
                        font=dict(size=14, color="#FFFFFF" if abs(delta_db_matrix[i, j]) > vmax * 0.4 else "#1A1A1A"),
                    )

    # Configure axes
    xaxis_name = "xaxis" if x_axis == "x" else f"xaxis{x_axis[1:]}"
    yaxis_name = "yaxis" if y_axis == "y" else f"yaxis{y_axis[1:]}"

    x_dict = getattr(canvas.fig.layout, xaxis_name)
    configure_axis(x_dict, title="Frequency Band")

    y_dict = getattr(canvas.fig.layout, yaxis_name)
    configure_axis(y_dict, title="Cortical Area")
    y_dict["autorange"] = "reversed"

    if title:
        x_dom, y_dom = canvas.get_domain(row, col)
        canvas.fig.add_annotation(
            text=f"<b>{title}</b>",
            xref="paper",
            yref="paper",
            x=(x_dom[0] + x_dom[1]) / 2.0,
            y=y_dom[1] + 0.015,
            xanchor="center",
            yanchor="bottom",
            showarrow=False,
            font=dict(family=FONT_FAMILY, size=FONT_SIZES["title"], color=COLORS["text"]),
        )


def plot_granger_spectra(
    canvas: PlotlyPublicationCanvas,
    row: int,
    col: int,
    freqs: np.ndarray,
    gc_ff: np.ndarray,
    gc_fb: np.ndarray,
    null_ribbon: Optional[np.ndarray] = None,
    ff_label: str = "A → B",
    fb_label: str = "B → A",
    title: Optional[str] = "Directed Granger Causality",
) -> None:
    """
    Render directed Granger causality spectra with shuffle null confidence ribbons.

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        freqs: 1D array of frequencies (Hz).
        gc_ff: 1D array of Granger causality in the first direction (A to B).
        gc_fb: 1D array of Granger causality in the reverse direction (B to A).
        null_ribbon: [n_freqs, 2] array of [ci_lower, ci_upper] for shuffle null.
        ff_label: Legend label for the first-direction trace; name the areas here.
        fb_label: Legend label for the reverse-direction trace.
        title: Panel title.
    """
    x_axis, y_axis = canvas.get_axis_names(row, col)

    freqs = np.asarray(freqs, dtype=float)
    gc_ff = np.asarray(gc_ff, dtype=float)
    gc_fb = np.asarray(gc_fb, dtype=float)

    # 1. Null ribbon (if provided)
    if null_ribbon is not None:
        null_ribbon = np.asarray(null_ribbon, dtype=float)
        canvas.fig.add_trace(
            go.Scatter(
                x=freqs,
                y=null_ribbon[:, 0],
                mode="lines",
                line=dict(width=0),
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )
        canvas.fig.add_trace(
            go.Scatter(
                x=freqs,
                y=null_ribbon[:, 1],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(127, 140, 141, 0.15)",
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # 2. First-direction trace
    canvas.fig.add_trace(
        go.Scatter(
            x=freqs,
            y=gc_ff,
            mode="lines",
            name=ff_label,
            line=dict(color="#C0392B", width=1.5),
            xaxis=x_axis,
            yaxis=y_axis,
            hovertemplate="Freq: %{x:.1f} Hz<br>" + ff_label + ": %{y:.4f}<extra></extra>",
        )
    )

    # 3. Reverse-direction trace
    canvas.fig.add_trace(
        go.Scatter(
            x=freqs,
            y=gc_fb,
            mode="lines",
            name=fb_label,
            line=dict(color="#2980B9", width=1.5),
            xaxis=x_axis,
            yaxis=y_axis,
            hovertemplate="Freq: %{x:.1f} Hz<br>" + fb_label + ": %{y:.4f}<extra></extra>",
        )
    )

    # Configure axes
    xaxis_name = "xaxis" if x_axis == "x" else f"xaxis{x_axis[1:]}"
    yaxis_name = "yaxis" if y_axis == "y" else f"yaxis{y_axis[1:]}"

    x_dict = getattr(canvas.fig.layout, xaxis_name)
    configure_axis(x_dict, title="Frequency (Hz)", showgrid=False)

    y_dict = getattr(canvas.fig.layout, yaxis_name)
    configure_axis(y_dict, title="Granger Causality", showgrid=True)

    if title:
        x_dom, y_dom = canvas.get_domain(row, col)
        canvas.fig.add_annotation(
            text=f"<b>{title}</b>",
            xref="paper",
            yref="paper",
            x=(x_dom[0] + x_dom[1]) / 2.0,
            y=y_dom[1] + 0.015,
            xanchor="center",
            yanchor="bottom",
            showarrow=False,
            font=dict(family=FONT_FAMILY, size=FONT_SIZES["title"], color=COLORS["text"]),
        )
