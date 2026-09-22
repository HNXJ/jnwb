"""
jnwb.vis.state_space -- Publication-grade population state-space geometry, RSA, and decoding in pure Plotly.

Implements Motif 5 (Fiser 2023, Garrett 2025, Grand Draft 2026):
- Population state-space trajectories (2D/3D PCA/GPFA with time arrows and condition markers)
- Representational Similarity Matrices (RSM) with hierarchical clustering dendrograms
- Cross-validated decoding time courses with cluster-based permutation test significance bars
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import plotly.graph_objects as go

from .canvas import PlotlyPublicationCanvas
from .theme import COLORS, FONT_FAMILY, FONT_SIZES, configure_axis


def plot_decoding_timecourse(
    canvas: PlotlyPublicationCanvas,
    row: int,
    col: int,
    time_ms: np.ndarray,
    accuracy: np.ndarray,
    ci_low: Optional[np.ndarray] = None,
    ci_high: Optional[np.ndarray] = None,
    chance_level: float = 0.5,
    sig_clusters: Optional[Sequence[Tuple[float, float]]] = None,
    trace_color: str = "#2C3E50",
    title: Optional[str] = "Population Decoding Accuracy",
    y_label: str = "Accuracy",
) -> None:
    """
    Render a cross-validated decoding time course with CI ribbon and cluster permutation bars.

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        time_ms: 1D array of time points relative to onset.
        accuracy: 1D array of decoding accuracy over time.
        ci_low: 1D array of lower confidence bounds.
        ci_high: 1D array of upper confidence bounds.
        chance_level: Theoretical chance level (e.g. 0.5 for binary classification).
        sig_clusters: List of (t_start, t_end) tuples for statistically significant time clusters.
        trace_color: Hex color for accuracy curve.
        title: Panel title.
        y_label: Label for y-axis.
    """
    x_axis, y_axis = canvas.get_axis_names(row, col)

    time_ms = np.asarray(time_ms, dtype=float)
    accuracy = np.asarray(accuracy, dtype=float)

    # 1. Chance level dashed line
    canvas.fig.add_trace(
        go.Scatter(
            x=[np.min(time_ms), np.max(time_ms)],
            y=[chance_level, chance_level],
            mode="lines",
            name=f"Chance ({chance_level * 100:.0f}%)",
            line=dict(color="#7F8C8D", width=1.0, dash="dash"),
            xaxis=x_axis,
            yaxis=y_axis,
            showlegend=True,
            hoverinfo="skip",
        )
    )

    # 2. CI Envelope (fill='tonexty')
    if ci_low is not None and ci_high is not None:
        ci_low = np.asarray(ci_low, dtype=float)
        ci_high = np.asarray(ci_high, dtype=float)

        canvas.fig.add_trace(
            go.Scatter(
                x=time_ms,
                y=ci_low,
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
                x=time_ms,
                y=ci_high,
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(44, 62, 80, 0.15)",
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # 3. Main accuracy curve
    canvas.fig.add_trace(
        go.Scatter(
            x=time_ms,
            y=accuracy,
            mode="lines",
            name="Decoder Accuracy",
            line=dict(color=trace_color, width=1.5),
            xaxis=x_axis,
            yaxis=y_axis,
            hovertemplate="Time: %{x:.1f} ms<br>Accuracy: %{y:.3f}<extra></extra>",
        )
    )

    # 4. Cluster-based permutation test significance bars along the x-axis
    if sig_clusters:
        y_bar = chance_level * 0.75  # Position bar near bottom
        for t0, t1 in sig_clusters:
            canvas.fig.add_shape(
                type="line",
                x0=t0,
                x1=t1,
                y0=y_bar,
                y1=y_bar,
                line=dict(color="#C0392B", width=3.0),
                xref=x_axis,
                yref=y_axis,
            )
        canvas.fig.add_annotation(
            x=sig_clusters[0][0],
            y=y_bar,
            xref=x_axis,
            yref=y_axis,
            text="<b>p < 0.05 (Cluster)</b>",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            font=dict(family=FONT_FAMILY, size=FONT_SIZES["annotation"], color="#C0392B"),
        )

    # Configure axes
    xaxis_name = "xaxis" if x_axis == "x" else f"xaxis{x_axis[1:]}"
    yaxis_name = "yaxis" if y_axis == "y" else f"yaxis{y_axis[1:]}"

    x_dict = getattr(canvas.fig.layout, xaxis_name)
    configure_axis(x_dict, title="Time from onset (ms)", showgrid=False)

    y_dict = getattr(canvas.fig.layout, yaxis_name)
    configure_axis(y_dict, title=y_label, showgrid=True)

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


def plot_rsm_heatmap(
    canvas: PlotlyPublicationCanvas,
    row: int,
    col: int,
    rsm_matrix: np.ndarray,
    condition_labels: Sequence[str],
    cmap: str = "Viridis",
    title: Optional[str] = "Representational Similarity Matrix (RSM)",
    colorbar_title: str = "Dissimilarity",
) -> None:
    """
    Render a Representational Similarity Matrix (RSM / RDM) heatmap.

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        rsm_matrix: 2D symmetric array of shape [n_conditions, n_conditions].
        condition_labels: List of condition names.
        cmap: Colormap name.
        title: Panel title.
        colorbar_title: Title for colorbar.
    """
    x_axis, y_axis = canvas.get_axis_names(row, col)

    rsm_matrix = np.asarray(rsm_matrix, dtype=float)

    cb_cfg = canvas.get_colorbar_config(row, col, title=colorbar_title)
    heatmap = go.Heatmap(
        x=condition_labels,
        y=condition_labels,
        z=rsm_matrix,
        colorscale=cmap,
        colorbar=cb_cfg,
        xaxis=x_axis,
        yaxis=y_axis,
        hovertemplate="Cond 1: %{y}<br>Cond 2: %{x}<br>Dissimilarity: %{z:.3f}<extra></extra>",
    )
    canvas.fig.add_trace(heatmap)

    # Configure axes
    xaxis_name = "xaxis" if x_axis == "x" else f"xaxis{x_axis[1:]}"
    yaxis_name = "yaxis" if y_axis == "y" else f"yaxis{y_axis[1:]}"

    x_dict = getattr(canvas.fig.layout, xaxis_name)
    configure_axis(x_dict)

    y_dict = getattr(canvas.fig.layout, yaxis_name)
    configure_axis(y_dict)
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
