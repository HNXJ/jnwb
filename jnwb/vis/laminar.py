"""
jnwb.vis.laminar -- Publication-grade laminar electrophysiology primitives in pure Plotly.

Implements Motif 1 (Mendoza-Halliday 2024, Westerberg 2024, Buzsáki 2019):
- 2D Spectrolaminar relative power maps (radical-sign motif, 1-150 Hz x depth)
- Opposing laminar power gradients (Gamma vs. Alpha/Beta with L4 crossover and CI ribbons)
- Current Source Density (CSD) profiles with zero-crossing contour lines and layer boundaries
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import plotly.graph_objects as go

from .canvas import PlotlyPublicationCanvas
from .theme import COLORS, FONT_FAMILY, FONT_SIZES, configure_axis


def plot_spectrolaminar_map(
    canvas: PlotlyPublicationCanvas,
    row: int,
    col: int,
    rel_power: np.ndarray,
    freqs: np.ndarray,
    depths: np.ndarray,
    crossover_depth: Optional[float] = None,
    cmap: str = "Magma",
    log_freq: bool = True,
    title: Optional[str] = "Spectrolaminar Power Map",
    colorbar_title: str = "Relative Power",
) -> None:
    """
    Render a 2D spectrolaminar relative power map (Mendoza-Halliday et al. 2024).

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        rel_power: 2D array of shape [n_freqs, n_depths] or [n_depths, n_freqs].
        freqs: 1D array of frequencies (Hz).
        depths: 1D array of cortical depths (normalized 0.0-1.0 or micrometers).
        crossover_depth: Depth of the gamma/alpha-beta crossover, computed from this
            recording (for example with ``jnwb.vflip``), in the units of ``depths``. No
            marker is drawn when None; there is no default value because the depth is
            a property of each recording, not a constant.
        cmap: Plotly colormap name (default 'Magma').
        log_freq: If True, set frequency axis to log scale.
        title: Panel title.
        colorbar_title: Title for colorbar.
    """
    x_axis, y_axis = canvas.get_axis_names(row, col)

    rel_power = np.asarray(rel_power, dtype=float)
    freqs = np.asarray(freqs, dtype=float)
    depths = np.asarray(depths, dtype=float)

    # Ensure shape is [depths, freqs] for heatmap display (x=freqs, y=depths)
    if rel_power.shape == (len(freqs), len(depths)):
        z_data = rel_power.T
    elif rel_power.shape == (len(depths), len(freqs)):
        z_data = rel_power
    else:
        raise ValueError(
            f"rel_power shape {rel_power.shape} does not match freqs ({len(freqs)}) and depths ({len(depths)})."
        )

    # Heatmap trace
    cb_cfg = canvas.get_colorbar_config(row, col, title=colorbar_title)
    heatmap = go.Heatmap(
        x=freqs,
        y=depths,
        z=z_data,
        colorscale=cmap,
        zmin=0.0,
        zmax=1.0,
        colorbar=cb_cfg,
        xaxis=x_axis,
        yaxis=y_axis,
        hovertemplate="Freq: %{x:.1f} Hz<br>Depth: %{y:.3f}<br>P_rel: %{z:.3f}<extra></extra>",
    )
    canvas.fig.add_trace(heatmap)

    # Configure axes
    xaxis_name = "xaxis" if x_axis == "x" else f"xaxis{x_axis[1:]}"
    yaxis_name = "yaxis" if y_axis == "y" else f"yaxis{y_axis[1:]}"

    x_dict = getattr(canvas.fig.layout, xaxis_name)
    configure_axis(x_dict, title="Frequency (Hz)")
    if log_freq:
        x_dict["type"] = "log"
        # Standard electrophysiology log-frequency ticks
        tick_vals = [1, 2, 4, 8, 16, 32, 64, 128]
        valid_ticks = [tv for tv in tick_vals if np.min(freqs) <= tv <= np.max(freqs)]
        if valid_ticks:
            x_dict["tickvals"] = valid_ticks
            x_dict["ticktext"] = [str(tv) for tv in valid_ticks]

    y_dict = getattr(canvas.fig.layout, yaxis_name)
    depth_title = "Cortical Depth (μm)" if np.max(depths) > 2.0 else "Relative Depth (0=Pia, 1=WM)"
    configure_axis(y_dict, title=depth_title)
    # Typically depth increases from surface (0) downward
    y_dict["autorange"] = "reversed"

    # Layer 4 crossover dashed reference line
    if crossover_depth is not None and np.min(depths) <= crossover_depth <= np.max(depths):
        line_trace = go.Scatter(
            x=[np.min(freqs), np.max(freqs)],
            y=[crossover_depth, crossover_depth],
            mode="lines",
            line=dict(color=COLORS["crossover"], width=1.2, dash="dash"),
            xaxis=x_axis,
            yaxis=y_axis,
            showlegend=False,
            hoverinfo="skip",
        )
        canvas.fig.add_trace(line_trace)

        # L4 crossover annotation
        canvas.fig.add_annotation(
            x=np.max(freqs),
            y=crossover_depth,
            xref=x_axis,
            yref=y_axis,
            text=f"<b>Crossover ({crossover_depth:g})</b>",
            showarrow=False,
            xanchor="right",
            yanchor="bottom",
            font=dict(family=FONT_FAMILY, size=FONT_SIZES["annotation"], color=COLORS["crossover"]),
        )

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


def plot_opposing_gradients(
    canvas: PlotlyPublicationCanvas,
    row: int,
    col: int,
    gamma_power: np.ndarray,
    alphabeta_power: np.ndarray,
    depths: np.ndarray,
    crossover_depth: Optional[float] = None,
    ci_gamma: Optional[np.ndarray] = None,
    ci_alphabeta: Optional[np.ndarray] = None,
    gamma_color: str = "#C0392B",
    alphabeta_color: str = "#2980B9",
    title: Optional[str] = "Opposing Laminar Gradients",
) -> None:
    """
    Render opposing gamma vs. alpha/beta laminar power gradients with caller-supplied intervals.

    The intervals in ``ci_gamma`` and ``ci_alphabeta`` are drawn as given; nothing here
    computes them.

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        gamma_power: 1D array of normalized gamma power along depth.
        alphabeta_power: 1D array of normalized alpha/beta power along depth.
        depths: 1D array of cortical depths.
        crossover_depth: Crossover depth computed from this recording, in the units of
            ``depths``; no marker when None.
        ci_gamma: [n_depths, 2] array of [ci_lower, ci_upper] for gamma.
        ci_alphabeta: [n_depths, 2] array of [ci_lower, ci_upper] for alpha/beta.
        gamma_color: Hex color for gamma profile.
        alphabeta_color: Hex color for alpha/beta profile.
        title: Panel title.
    """
    x_axis, y_axis = canvas.get_axis_names(row, col)

    gamma_power = np.asarray(gamma_power, dtype=float)
    alphabeta_power = np.asarray(alphabeta_power, dtype=float)
    depths = np.asarray(depths, dtype=float)

    # Gamma CI envelope (fill='tonexty')
    if ci_gamma is not None:
        ci_gamma = np.asarray(ci_gamma, dtype=float)
        # Lower bound
        canvas.fig.add_trace(
            go.Scatter(
                x=ci_gamma[:, 0],
                y=depths,
                mode="lines",
                line=dict(width=0),
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )
        # Upper bound with fill
        canvas.fig.add_trace(
            go.Scatter(
                x=ci_gamma[:, 1],
                y=depths,
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(192, 57, 43, 0.15)",
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Alpha/Beta CI envelope
    if ci_alphabeta is not None:
        ci_alphabeta = np.asarray(ci_alphabeta, dtype=float)
        canvas.fig.add_trace(
            go.Scatter(
                x=ci_alphabeta[:, 0],
                y=depths,
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
                x=ci_alphabeta[:, 1],
                y=depths,
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(41, 128, 185, 0.15)",
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Main profiles
    canvas.fig.add_trace(
        go.Scatter(
            x=gamma_power,
            y=depths,
            mode="lines",
            name="Gamma (50–150 Hz)",
            line=dict(color=gamma_color, width=1.5),
            xaxis=x_axis,
            yaxis=y_axis,
            hovertemplate="Gamma: %{x:.3f}<br>Depth: %{y:.3f}<extra></extra>",
        )
    )
    canvas.fig.add_trace(
        go.Scatter(
            x=alphabeta_power,
            y=depths,
            mode="lines",
            name="Alpha/Beta (10–30 Hz)",
            line=dict(color=alphabeta_color, width=1.5),
            xaxis=x_axis,
            yaxis=y_axis,
            hovertemplate="Alpha/Beta: %{x:.3f}<br>Depth: %{y:.3f}<extra></extra>",
        )
    )

    # Layer 4 crossover dashed reference line
    if crossover_depth is not None and np.min(depths) <= crossover_depth <= np.max(depths):
        x_max = max(np.max(gamma_power), np.max(alphabeta_power)) * 1.05
        canvas.fig.add_trace(
            go.Scatter(
                x=[0, x_max],
                y=[crossover_depth, crossover_depth],
                mode="lines",
                line=dict(color=COLORS["crossover"], width=1.0, dash="dash"),
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Configure axes
    xaxis_name = "xaxis" if x_axis == "x" else f"xaxis{x_axis[1:]}"
    yaxis_name = "yaxis" if y_axis == "y" else f"yaxis{y_axis[1:]}"

    x_dict = getattr(canvas.fig.layout, xaxis_name)
    configure_axis(x_dict, title="Normalized Power (a.u.)", showgrid=True)

    y_dict = getattr(canvas.fig.layout, yaxis_name)
    depth_title = "Cortical Depth (μm)" if np.max(depths) > 2.0 else "Relative Depth (0=Pia, 1=WM)"
    configure_axis(y_dict, title=depth_title)
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


def plot_csd(
    canvas: PlotlyPublicationCanvas,
    row: int,
    col: int,
    csd_matrix: np.ndarray,
    time_ms: np.ndarray,
    depths: np.ndarray,
    layer_boundaries: Optional[Dict[str, float]] = None,
    cmap: str = "RdBu_r",
    title: Optional[str] = "Current Source Density (CSD)",
    colorbar_title: str = "CSD (mV/mm²)",
) -> None:
    """
    Render a Current Source Density (CSD) depth x time profile with layer boundaries.

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        csd_matrix: 2D array of shape [n_depths, n_times].
        time_ms: 1D array of time points relative to event (ms).
        depths: 1D array of cortical depths.
        layer_boundaries: Dictionary mapping layer names (e.g. 'L4', 'L5/6') to depth coordinates.
        cmap: Diverging colormap name (default 'RdBu_r' where blue is sink, red is source).
        title: Panel title.
        colorbar_title: Title for colorbar.
    """
    x_axis, y_axis = canvas.get_axis_names(row, col)

    csd_matrix = np.asarray(csd_matrix, dtype=float)
    time_ms = np.asarray(time_ms, dtype=float)
    depths = np.asarray(depths, dtype=float)

    # Robust symmetric scale centered at 0
    vmax = float(np.percentile(np.abs(csd_matrix), 98))
    vmin = -vmax

    cb_cfg = canvas.get_colorbar_config(row, col, title=colorbar_title)
    heatmap = go.Heatmap(
        x=time_ms,
        y=depths,
        z=csd_matrix,
        colorscale=cmap,
        zmin=vmin,
        zmax=vmax,
        colorbar=cb_cfg,
        xaxis=x_axis,
        yaxis=y_axis,
        hovertemplate="Time: %{x:.1f} ms<br>Depth: %{y:.3f}<br>CSD: %{z:.2e}<extra></extra>",
    )
    canvas.fig.add_trace(heatmap)

    # Layer boundary lines and labels
    if layer_boundaries:
        for layer_name, layer_depth in layer_boundaries.items():
            if np.min(depths) <= layer_depth <= np.max(depths):
                canvas.fig.add_trace(
                    go.Scatter(
                        x=[np.min(time_ms), np.max(time_ms)],
                        y=[layer_depth, layer_depth],
                        mode="lines",
                        line=dict(color="#2C3E50", width=0.8, dash="dot"),
                        xaxis=x_axis,
                        yaxis=y_axis,
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
                canvas.fig.add_annotation(
                    x=np.min(time_ms) + 5,
                    y=layer_depth,
                    xref=x_axis,
                    yref=y_axis,
                    text=f"<b>{layer_name}</b>",
                    showarrow=False,
                    xanchor="left",
                    yanchor="bottom",
                    font=dict(family=FONT_FAMILY, size=FONT_SIZES["annotation"], color="#2C3E50"),
                )

    # Zero-time line
    if np.min(time_ms) <= 0 <= np.max(time_ms):
        canvas.fig.add_trace(
            go.Scatter(
                x=[0, 0],
                y=[np.min(depths), np.max(depths)],
                mode="lines",
                line=dict(color="#1A1A1A", width=1.0, dash="dash"),
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Configure axes
    xaxis_name = "xaxis" if x_axis == "x" else f"xaxis{x_axis[1:]}"
    yaxis_name = "yaxis" if y_axis == "y" else f"yaxis{y_axis[1:]}"

    x_dict = getattr(canvas.fig.layout, xaxis_name)
    configure_axis(x_dict, title="Time from onset (ms)")

    y_dict = getattr(canvas.fig.layout, yaxis_name)
    depth_title = "Cortical Depth (μm)" if np.max(depths) > 2.0 else "Relative Depth (0=Pia, 1=WM)"
    configure_axis(y_dict, title=depth_title)
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
