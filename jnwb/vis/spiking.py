"""
jnwb.vis.spiking -- Raster, PSTH and population heatmap panels in pure Plotly.

- ``plot_multi_condition_raster_psth``: a multi-condition raster (WebGL ``Scattergl``) above a
  PSTH with mean +/- 1.96 SEM ribbons across trials.
- ``plot_sorted_heatmap``: a units x time response heatmap in a caller-supplied row order.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import plotly.graph_objects as go

from .canvas import PlotlyPublicationCanvas
from .theme import COLORS, FONT_FAMILY, FONT_SIZES, configure_axis


def plot_multi_condition_raster_psth(
    canvas: PlotlyPublicationCanvas,
    row_raster: int,
    col_raster: int,
    row_psth: int,
    col_psth: int,
    st: np.ndarray,
    onsets: Dict[str, np.ndarray],
    win_ms: Tuple[float, float] = (-250.0, 531.0),
    colors: Optional[Dict[str, str]] = None,
    stim_dur_ms: float = 250.0,
    bin_ms: float = 10.0,
    max_raster_trials: int = 150,
    title: Optional[str] = "Unit Spiking Activity",
) -> None:
    """
    Render synchronized multi-condition raster and PSTH panels.

    The PSTH ribbon is mean +/- 1.96 SEM across trials, a normal approximation with its lower
    bound clipped at 0 Hz, and is drawn only for a condition with more than one trial. It is not
    a bootstrap interval.

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row_raster: Grid row for raster panel.
        col_raster: Grid column for raster panel.
        row_psth: Grid row for PSTH panel.
        col_psth: Grid column for PSTH panel.
        st: 1D array of spike timestamps (seconds).
        onsets: Dict mapping condition name to 1D array of onset timestamps (seconds).
        win_ms: Window relative to onset in ms (start_ms, end_ms).
        colors: Dict mapping condition name to hex color.
        stim_dur_ms: Stimulus duration in ms for shaded event box.
        bin_ms: Bin width for PSTH in ms.
        max_raster_trials: Maximum trials to plot per condition in raster.
        title: Title for the combined panel.
    """
    st = np.asarray(st, dtype=float)
    x_rast, y_rast = canvas.get_axis_names(row_raster, col_raster)
    x_psth, y_psth = canvas.get_axis_names(row_psth, col_psth)

    default_palette = ["#2980B9", "#C0392B", "#27AE60", "#8E44AD", "#D35400"]
    if colors is None:
        colors = {cond: default_palette[i % len(default_palette)] for i, cond in enumerate(onsets.keys())}

    # Synchronize x-axes between raster and PSTH
    xaxis_psth_name = "xaxis" if x_psth == "x" else f"xaxis{x_psth[1:]}"
    xaxis_rast_name = "xaxis" if x_rast == "x" else f"xaxis{x_rast[1:]}"
    getattr(canvas.fig.layout, xaxis_rast_name)["matches"] = x_psth
    getattr(canvas.fig.layout, xaxis_rast_name)["showticklabels"] = False

    # PSTH time bins
    edges = np.arange(win_ms[0], win_ms[1] + bin_ms, bin_ms)
    centers = edges[:-1] + bin_ms / 2.0

    current_trial_offset = 0

    for cond_name, cond_onsets in onsets.items():
        cond_onsets = np.asarray(cond_onsets, dtype=float)
        if len(cond_onsets) == 0:
            continue

        color = colors.get(cond_name, "#2C3E50")

        # 1. Raster data extraction
        n_trials = min(len(cond_onsets), max_raster_trials)
        selected_onsets = cond_onsets[:n_trials]

        raster_x: List[float] = []
        raster_y: List[float] = []

        # PSTH rate calculation
        counts = np.zeros((len(cond_onsets), edges.size - 1))

        for i, t0 in enumerate(cond_onsets):
            trial_spikes = (st[(st >= t0 + win_ms[0] / 1000.0) & (st < t0 + win_ms[1] / 1000.0)] - t0) * 1000.0
            counts[i], _ = np.histogram(trial_spikes, bins=edges)

            if i < n_trials:
                for spk in trial_spikes:
                    raster_x.append(spk)
                    raster_y.append(current_trial_offset + i + 1)

        # Plot raster spikes via WebGL Scattergl for performance
        if raster_x:
            canvas.fig.add_trace(
                go.Scattergl(
                    x=raster_x,
                    y=raster_y,
                    mode="markers",
                    name=cond_name,
                    marker=dict(
                        symbol="line-ns",
                        size=4,
                        color=color,
                        line=dict(width=1.0, color=color),
                    ),
                    xaxis=x_rast,
                    yaxis=y_rast,
                    legendgroup=cond_name,
                    showlegend=False,
                    hovertemplate=f"{cond_name}<br>Time: %{{x:.1f}} ms<br>Trial: %{{y}}<extra></extra>",
                )
            )

        current_trial_offset += n_trials + 2

        # 2. PSTH mean and a +/- 1.96 SEM ribbon
        rate_hz = counts / (bin_ms / 1000.0)
        mean_rate = rate_hz.mean(axis=0)

        if len(cond_onsets) > 1:
            sem_rate = rate_hz.std(axis=0, ddof=1) / np.sqrt(len(cond_onsets))
            ci_low = np.maximum(0, mean_rate - 1.96 * sem_rate)
            ci_high = mean_rate + 1.96 * sem_rate

            # CI lower bound
            canvas.fig.add_trace(
                go.Scatter(
                    x=centers,
                    y=ci_low,
                    mode="lines",
                    line=dict(width=0),
                    xaxis=x_psth,
                    yaxis=y_psth,
                    legendgroup=cond_name,
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            # CI upper bound with fill
            # Hex to rgba conversion
            hex_c = color.lstrip("#")
            r, g, b = tuple(int(hex_c[k:k+2], 16) for k in (0, 2, 4))
            rgba_fill = f"rgba({r}, {g}, {b}, 0.20)"

            canvas.fig.add_trace(
                go.Scatter(
                    x=centers,
                    y=ci_high,
                    mode="lines",
                    line=dict(width=0),
                    fill="tonexty",
                    fillcolor=rgba_fill,
                    xaxis=x_psth,
                    yaxis=y_psth,
                    legendgroup=cond_name,
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

        # Main PSTH rate line
        canvas.fig.add_trace(
            go.Scatter(
                x=centers,
                y=mean_rate,
                mode="lines",
                name=cond_name,
                line=dict(color=color, width=1.5),
                xaxis=x_psth,
                yaxis=y_psth,
                legendgroup=cond_name,
                showlegend=True,
                hovertemplate=f"{cond_name}<br>Time: %{{x:.1f}} ms<br>Rate: %{{y:.1f}} Hz<extra></extra>",
            )
        )

    # Shaded stimulus window in both panels
    if stim_dur_ms > 0:
        for (xa, ya) in [(x_rast, y_rast), (x_psth, y_psth)]:
            canvas.fig.add_vrect(
                x0=0,
                x1=stim_dur_ms,
                fillcolor="rgba(127, 140, 141, 0.12)",
                layer="below",
                line_width=0,
                xref=xa,
                yref=ya,
            )

    # Configure axes
    yaxis_rast_name = "yaxis" if y_rast == "y" else f"yaxis{y_rast[1:]}"
    y_rast_dict = getattr(canvas.fig.layout, yaxis_rast_name)
    configure_axis(y_rast_dict, title="Trials", showgrid=False)
    y_rast_dict["range"] = [0, current_trial_offset + 1]

    yaxis_psth_name = "yaxis" if y_psth == "y" else f"yaxis{y_psth[1:]}"
    y_psth_dict = getattr(canvas.fig.layout, yaxis_psth_name)
    configure_axis(y_psth_dict, title="Firing Rate (spikes/s)", showgrid=True)

    x_psth_dict = getattr(canvas.fig.layout, xaxis_psth_name)
    configure_axis(x_psth_dict, title="Time from onset (ms)", showgrid=False)
    x_psth_dict["range"] = [win_ms[0], win_ms[1]]

    # Title annotation
    if title:
        x_dom, y_dom = canvas.get_domain(row_raster, col_raster)
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


def plot_sorted_heatmap(
    canvas: PlotlyPublicationCanvas,
    row: int,
    col: int,
    rate_matrix: np.ndarray,
    time_ms: np.ndarray,
    sort_idx: Optional[np.ndarray] = None,
    category_labels: Optional[Sequence[str]] = None,
    cmap: str = "Viridis",
    title: Optional[str] = "Sorted Population Responses",
    colorbar_title: str = "Rate (Δz)",
) -> None:
    """
    Render a sorted population response heatmap (N units x time points).

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        rate_matrix: 2D array of shape [n_units, n_times].
        time_ms: 1D array of time points relative to event.
        sort_idx: Optional 1D sorting indices (e.g. by latency or response category).
        category_labels: Optional labels for unit groups.
        cmap: Colormap name.
        title: Panel title.
        colorbar_title: Title for colorbar.
    """
    x_axis, y_axis = canvas.get_axis_names(row, col)

    rate_matrix = np.asarray(rate_matrix, dtype=float)
    time_ms = np.asarray(time_ms, dtype=float)

    if sort_idx is not None:
        rate_matrix = rate_matrix[sort_idx, :]

    n_units = rate_matrix.shape[0]
    unit_indices = np.arange(1, n_units + 1)

    cb_cfg = canvas.get_colorbar_config(row, col, title=colorbar_title)
    heatmap = go.Heatmap(
        x=time_ms,
        y=unit_indices,
        z=rate_matrix,
        colorscale=cmap,
        colorbar=cb_cfg,
        xaxis=x_axis,
        yaxis=y_axis,
        hovertemplate="Time: %{x:.1f} ms<br>Unit: %{y}<br>Rate: %{z:.2f}<extra></extra>",
    )
    canvas.fig.add_trace(heatmap)

    # Configure axes
    xaxis_name = "xaxis" if x_axis == "x" else f"xaxis{x_axis[1:]}"
    yaxis_name = "yaxis" if y_axis == "y" else f"yaxis{y_axis[1:]}"

    x_dict = getattr(canvas.fig.layout, xaxis_name)
    configure_axis(x_dict, title="Time from onset (ms)")

    y_dict = getattr(canvas.fig.layout, yaxis_name)
    configure_axis(y_dict, title=f"Units (N = {n_units})")
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
