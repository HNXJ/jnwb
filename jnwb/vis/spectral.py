"""
jnwb.vis.spectral -- Spectral modulation and directed connectivity panels in pure Plotly.

- ``plot_spectral_modulation_matrix``: an area x frequency-band matrix with significance
  markers from a caller-supplied mask.
- ``plot_granger_spectra``: Granger spectra for both directions of a pair, with
  caller-supplied null ribbons.

No statistic is computed here: every mask, interval and null is a caller input.
"""

from __future__ import annotations

from typing import Optional, Sequence

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

    Raises:
        ValueError: ``delta_db_matrix`` does not have shape [len(areas), len(bands)] or holds no
            finite value, or ``sig_mask`` does not have that shape or holds a non-finite cell.
    """
    x_axis, y_axis = canvas.get_axis_names(row, col)

    delta_db_matrix = np.asarray(delta_db_matrix, dtype=float)
    if delta_db_matrix.shape != (len(areas), len(bands)):
        raise ValueError(
            f"plot_spectral_modulation_matrix: delta_db_matrix shape {delta_db_matrix.shape} does not match "
            f"areas and bands; expected ({len(areas)}, {len(bands)})."
        )
    if sig_mask is not None and np.shape(sig_mask) != (len(areas), len(bands)):
        raise ValueError(
            f"plot_spectral_modulation_matrix: sig_mask shape {np.shape(sig_mask)} does not match "
            f"areas and bands; expected ({len(areas)}, {len(bands)})."
        )
    if sig_mask is not None and not np.isfinite(np.asarray(sig_mask, dtype=float)).all():
        raise ValueError(
            "plot_spectral_modulation_matrix: sig_mask holds a non-finite cell; a NaN would be "
            "marked significant. Pass a boolean mask."
        )

    # Symmetric scale around zero, from the finite values only (a NaN is drawn as a gap)
    finite_abs = np.where(np.isfinite(delta_db_matrix), np.abs(delta_db_matrix), np.nan)
    if np.isnan(finite_abs).all():
        raise ValueError(
            "plot_spectral_modulation_matrix: delta_db_matrix holds no finite value; the colour range "
            "needs at least one."
        )
    vmax = float(np.nanpercentile(finite_abs, 98))
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

    Raises:
        ValueError: ``gc_ff`` or ``gc_fb`` does not have the shape of ``freqs``, or
            ``null_ribbon`` is not [len(freqs), 2].
    """
    x_axis, y_axis = canvas.get_axis_names(row, col)

    freqs = np.asarray(freqs, dtype=float)
    gc_ff = np.asarray(gc_ff, dtype=float)
    gc_fb = np.asarray(gc_fb, dtype=float)
    for name, series in (("gc_ff", gc_ff), ("gc_fb", gc_fb)):
        if series.shape != freqs.shape:
            raise ValueError(
                f"plot_granger_spectra: {name} shape {series.shape} does not match freqs shape "
                f"{freqs.shape}; pass one value per frequency."
            )

    # 1. Null ribbon (if provided)
    if null_ribbon is not None:
        null_ribbon = np.asarray(null_ribbon, dtype=float)
        if null_ribbon.shape != (freqs.shape[0], 2):
            raise ValueError(
                f"plot_granger_spectra: null_ribbon shape {null_ribbon.shape} does not match freqs shape "
                f"{freqs.shape}; expected {(freqs.shape[0], 2)}, one [lower, upper] pair per frequency."
            )
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
