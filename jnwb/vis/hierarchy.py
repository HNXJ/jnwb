"""
jnwb.vis.hierarchy -- Cortical hierarchy panels in pure Plotly.

- ``plot_hierarchy_regression``: a per-area metric (latency, prevalence) against hierarchy
  rank, with caller-supplied error bars and null ribbon and a least-squares line.
"""

from __future__ import annotations

import warnings
from typing import Optional, Sequence, Tuple

import numpy as np
import plotly.graph_objects as go

from .canvas import PlotlyPublicationCanvas
from .theme import COLORS, FONT_FAMILY, FONT_SIZES, configure_axis, required_text


def plot_hierarchy_regression(
    canvas: PlotlyPublicationCanvas,
    row: int,
    col: int,
    hierarchy_ranks: np.ndarray,
    values: np.ndarray,
    ci_low: np.ndarray,
    ci_high: np.ndarray,
    area_labels: Sequence[str],
    r_squared: Optional[float] = None,
    p_perm: Optional[float] = None,
    null_line: Optional[float] = None,
    null_ribbon: Optional[Tuple[float, float]] = None,
    title: Optional[str] = "Hierarchy Alignment",
    marker_color: str = "#2C3E50",
    fit_line_color: str = "#C0392B",
    *,
    y_label: str,
) -> None:
    """
    Render a cortical hierarchy regression panel with caller-supplied error bars and null.

    The error bars, ``p_perm`` and ``null_ribbon`` are drawn as given; nothing here computes them.
    A point with a non-finite rank or value is left out of the linear fit, with a UserWarning
    that counts it. A confidence interval that does not bracket its value (a percentile bootstrap
    interval can miss its estimate) is drawn as a segment between its own bounds, with no error
    bar from the value, and a UserWarning names its index.

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        hierarchy_ranks: 1D array of anatomical hierarchy ranks (e.g. 0 to 9).
        values: 1D array of values (e.g. prevalence or onset latency).
        ci_low: 1D array of lower confidence bounds.
        ci_high: 1D array of upper confidence bounds.
        area_labels: List of area names corresponding to hierarchy ranks.
        r_squared: Coefficient of determination R^2.
        p_perm: Permutation test p-value.
        null_line: Reference horizontal line (e.g. 5% alpha ceiling).
        null_ribbon: Tuple (lower, upper) for null distribution confidence interval.
        title: Panel title.
        marker_color: Hex color for area points.
        fit_line_color: Hex color for regression fit line.
        y_label: Y-axis label naming the quantity and its unit, for example
            ``"Prevalence (%)"`` or ``"Onset latency (ms)"``. Required; ``values`` can be
            either.

    Raises:
        ValueError: ``y_label`` is not a non-empty string.
    """
    required_text("y_label", y_label)
    x_axis, y_axis = canvas.get_axis_names(row, col)

    hierarchy_ranks = np.asarray(hierarchy_ranks, dtype=float)
    values = np.asarray(values, dtype=float)
    ci_low = np.asarray(ci_low, dtype=float)
    ci_high = np.asarray(ci_high, dtype=float)

    usable = np.isfinite(hierarchy_ranks) & np.isfinite(values)
    n_left_out = int(np.count_nonzero(~usable))
    if n_left_out:
        warnings.warn(
            f"plot_hierarchy_regression: {n_left_out} point(s) with a non-finite rank or value "
            "are left out of the linear fit.",
            UserWarning,
            stacklevel=2,
        )
    finite_ci = np.isfinite(values) & np.isfinite(ci_low) & np.isfinite(ci_high)
    outside_ci = finite_ci & ((values < ci_low) | (values > ci_high))
    if outside_ci.any():
        warnings.warn(
            "plot_hierarchy_regression: the confidence interval(s) at indices "
            f"{np.flatnonzero(outside_ci).tolist()} do not bracket their value; each is drawn "
            "from its own bounds, with no error bar from the value.",
            UserWarning,
            stacklevel=2,
        )

    # 1. Null permutation confidence ribbon (if provided)
    if null_ribbon is not None:
        canvas.fig.add_shape(
            type="rect",
            x0=np.nanmin(hierarchy_ranks) - 0.5,
            x1=np.nanmax(hierarchy_ranks) + 0.5,
            y0=null_ribbon[0],
            y1=null_ribbon[1],
            fillcolor="rgba(127, 140, 141, 0.15)",
            line=dict(width=0),
            layer="below",
            xref=x_axis,
            yref=y_axis,
        )

    # 2. Reference null line (e.g. 5% false-positive ceiling)
    if null_line is not None:
        canvas.fig.add_trace(
            go.Scatter(
                x=[np.nanmin(hierarchy_ranks) - 0.5, np.nanmax(hierarchy_ranks) + 0.5],
                y=[null_line, null_line],
                mode="lines",
                name="5% Reference Ceiling",
                line=dict(color="#7F8C8D", width=1.0, dash="dash"),
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # 3. Least-squares linear fit line (np.polyfit, degree 1) through the usable points
    fit_y = np.empty(0)
    if np.count_nonzero(usable) >= 3:
        fit_ranks = hierarchy_ranks[usable]
        slope, intercept = np.polyfit(fit_ranks, values[usable], 1)
        fit_x = np.linspace(np.min(fit_ranks), np.max(fit_ranks), 50)
        fit_y = slope * fit_x + intercept

        canvas.fig.add_trace(
            go.Scatter(
                x=fit_x,
                y=fit_y,
                mode="lines",
                name="Linear Fit",
                line=dict(color=fit_line_color, width=1.5),
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # 4. Data points with explicit error bars (error_y); an interval that does not bracket its
    # value has no bar from the value and is drawn as a segment between its own bounds.
    if outside_ci.any():
        seg_x, seg_y = [], []
        for i in np.flatnonzero(outside_ci):
            seg_x += [hierarchy_ranks[i], hierarchy_ranks[i], None]
            seg_y += [ci_low[i], ci_high[i], None]
        canvas.fig.add_trace(
            go.Scatter(
                x=seg_x,
                y=seg_y,
                mode="lines",
                line=dict(color=marker_color, width=1.2),
                xaxis=x_axis,
                yaxis=y_axis,
                showlegend=False,
                hoverinfo="skip",
            )
        )
    error_plus = np.where(outside_ci, 0.0, ci_high - values)
    error_minus = np.where(outside_ci, 0.0, values - ci_low)

    canvas.fig.add_trace(
        go.Scatter(
            x=hierarchy_ranks,
            y=values,
            mode="markers+text",
            text=area_labels,
            textposition="top center",
            textfont=dict(family=FONT_FAMILY, size=FONT_SIZES["annotation"], color=COLORS["text"]),
            error_y=dict(
                type="data",
                symmetric=False,
                array=error_plus,
                arrayminus=error_minus,
                visible=True,
                color=marker_color,
                thickness=1.2,
                width=3,
            ),
            marker=dict(
                size=7,
                color=marker_color,
                line=dict(width=1, color="#FFFFFF"),
            ),
            xaxis=x_axis,
            yaxis=y_axis,
            hovertemplate="Area: %{text}<br>Rank: %{x}<br>Value: %{y:.2f}<br>CI: [%{customdata[0]:.2f}, %{customdata[1]:.2f}]<extra></extra>",
            customdata=np.column_stack([ci_low, ci_high]),
            showlegend=False,
        )
    )

    # 5. Annotation for R^2 and Permutation p-value
    stat_text_parts = []
    if r_squared is not None:
        stat_text_parts.append(f"R² = {r_squared:.2f}")
    if p_perm is not None:
        stat_text_parts.append(f"p_perm = {p_perm:.4f}")

    if stat_text_parts:
        stat_str = " | ".join(stat_text_parts)
        # Placed above the highest finite level drawn: points, intervals, fit and null lines.
        drawn = [values, ci_low, ci_high, fit_y]
        if null_line is not None:
            drawn.append(np.array([null_line], dtype=float))
        if null_ribbon is not None:
            drawn.append(np.asarray(null_ribbon, dtype=float))
        levels = np.concatenate([np.ravel(d) for d in drawn])
        levels = levels[np.isfinite(levels)]
        top = float(levels.max()) if levels.size else 0.0
        canvas.fig.add_annotation(
            x=np.nanmin(hierarchy_ranks),
            y=top + 0.05 * abs(top),
            xref=x_axis,
            yref=y_axis,
            text=f"<b>{stat_str}</b>",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            font=dict(family=FONT_FAMILY, size=FONT_SIZES["annotation"], color=COLORS["text"]),
        )

    # Configure axes
    xaxis_name = "xaxis" if x_axis == "x" else f"xaxis{x_axis[1:]}"
    yaxis_name = "yaxis" if y_axis == "y" else f"yaxis{y_axis[1:]}"

    x_dict = getattr(canvas.fig.layout, xaxis_name)
    configure_axis(x_dict, title="Anatomical Hierarchy Rank", showgrid=False)
    x_dict["tickvals"] = list(hierarchy_ranks)
    x_dict["ticktext"] = [f"{r:g}" for r in hierarchy_ranks]
    x_dict["range"] = [np.nanmin(hierarchy_ranks) - 0.6, np.nanmax(hierarchy_ranks) + 0.6]

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
