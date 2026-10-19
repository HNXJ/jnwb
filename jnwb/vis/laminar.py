"""
jnwb.vis.laminar -- Laminar electrophysiology panels in pure Plotly.

- ``plot_spectrolaminar_map``: relative power over frequency x depth.
- ``plot_opposing_gradients``: gamma and alpha/beta power against depth, with caller-supplied
  intervals and crossover depth.
- ``plot_csd``: a current source density depth x time profile with layer boundaries.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np
import plotly.graph_objects as go

from ..laminar._vflip import CANONICAL_VFLIP_BANDS
from .canvas import PlotlyPublicationCanvas
from .theme import COLORS, FONT_FAMILY, FONT_SIZES, checked_colorbar_label, configure_axis

_DEPTH_AXIS_TITLES = {
    "mm": "Cortical Depth (mm)",
    "um": "Cortical Depth (μm)",
    "relative": "Relative Depth (0=Pia, 1=WM)",
}


def _depth_axis_title(depth_unit: str) -> str:
    """Axis title for ``depth_unit``; the unit is declared by the caller, never read off the data."""
    if not isinstance(depth_unit, str) or depth_unit not in _DEPTH_AXIS_TITLES:
        raise ValueError(f"depth_unit must be 'mm', 'um' or 'relative'; got {depth_unit!r}")
    return _DEPTH_AXIS_TITLES[depth_unit]


def _hz_band_text(argument: str, band) -> str:
    """The Hz range a legend names, e.g. ``'8–30 Hz'``; refuses a band that is not two finite
    numbers with low < high."""
    values = np.asarray(band)
    if values.shape != (2,) or values.dtype.kind not in "iuf":
        raise ValueError(
            f"plot_opposing_gradients: {argument} must be two numbers (low, high) in Hz; got {band!r}."
        )
    low, high = (float(v) for v in values)
    if not (np.isfinite(low) and np.isfinite(high) and low < high):
        raise ValueError(
            f"plot_opposing_gradients: {argument} must be two finite numbers with low < high, in Hz; "
            f"got {band!r}."
        )
    return f"{low:g}–{high:g} Hz"


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
    *,
    depth_unit: str,
) -> None:
    """
    Render a 2D spectrolaminar relative power map (Mendoza-Halliday et al. 2024).

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        rel_power: 2D array of shape [n_freqs, n_depths] or [n_depths, n_freqs], holding
            fractions in [0, 1], for example power normalised across contacts per frequency.
            The colour scale is fixed to [0, 1]. ``jnwb.relative_power`` returns a ratio to
            baseline, which is unbounded, and is not this input. NaN values are drawn as gaps;
            infinite values raise.
        freqs: 1D array of frequencies (Hz).
        depths: 1D array of cortical depths, in ``depth_unit``.
        crossover_depth: Depth of the gamma/alpha-beta crossover, computed from this
            recording (for example with ``jnwb.vflip``), in the units of ``depths``. No
            marker is drawn when None; there is no default value because the depth is
            a property of each recording, not a constant.
        cmap: Plotly colormap name (default 'Magma').
        log_freq: If True, set frequency axis to log scale.
        title: Panel title.
        colorbar_title: Title for colorbar.
        depth_unit: Unit of ``depths``: ``'mm'``, ``'um'`` or ``'relative'`` (0 = pia,
            1 = white matter). Required; it labels the depth axis. Depths are drawn as given:
            ``'relative'`` values outside [0, 1] are channels above the pia or below the
            white matter.

    Raises:
        ValueError: ``depth_unit`` is not one of the three units, ``rel_power`` is empty, square
            (its orientation is not stated) or does not match ``freqs`` and ``depths``,
            ``rel_power`` holds an infinite value, or a finite value of ``rel_power`` lies
            outside [0, 1].
    """
    depth_title = _depth_axis_title(depth_unit)
    x_axis, y_axis = canvas.get_axis_names(row, col)

    rel_power = np.asarray(rel_power, dtype=float)
    freqs = np.asarray(freqs, dtype=float)
    depths = np.asarray(depths, dtype=float)
    if rel_power.size == 0:
        raise ValueError("rel_power is empty; pass one fraction in [0, 1] per frequency and depth.")

    # Ensure shape is [depths, freqs] for heatmap display (x=freqs, y=depths)
    fits_freq_depth = rel_power.shape == (len(freqs), len(depths))
    fits_depth_freq = rel_power.shape == (len(depths), len(freqs))
    if fits_freq_depth and fits_depth_freq:
        raise ValueError(
            f"plot_spectrolaminar_map: rel_power is square {rel_power.shape} for {len(freqs)} freqs and "
            f"{len(depths)} depths, so its orientation cannot be read from the shape; pass non-square "
            "data, or transpose it to [n_depths, n_freqs] yourself."
        )
    if fits_freq_depth:
        z_data = rel_power.T
    elif fits_depth_freq:
        z_data = rel_power
    else:
        raise ValueError(
            f"rel_power shape {rel_power.shape} does not match freqs ({len(freqs)}) and depths ({len(depths)})."
        )
    if np.isinf(z_data).any():
        raise ValueError(
            "rel_power holds infinite values; plot_spectrolaminar_map draws NaN as a gap and "
            "refuses +inf and -inf on its fixed [0, 1] colour scale."
        )
    finite = z_data[np.isfinite(z_data)]
    if finite.size and (finite.min() < 0.0 or finite.max() > 1.0):
        raise ValueError(
            "plot_spectrolaminar_map expects rel_power as fractions in [0, 1] (the colour scale "
            f"is fixed to that range); got values in [{finite.min():.3g}, {finite.max():.3g}]. "
            "jnwb.relative_power returns an unbounded ratio to baseline, or dB for "
            "model='log_ratio'; normalise across contacts per frequency before plotting."
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
    *,
    depth_unit: str,
    gamma_band: Tuple[float, float] = CANONICAL_VFLIP_BANDS["high"],
    alphabeta_band: Tuple[float, float] = CANONICAL_VFLIP_BANDS["low"],
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
        depths: 1D array of cortical depths, in ``depth_unit``.
        crossover_depth: Crossover depth computed from this recording, in the units of
            ``depths``; no marker when None.
        ci_gamma: [n_depths, 2] array of [ci_lower, ci_upper] for gamma.
        ci_alphabeta: [n_depths, 2] array of [ci_lower, ci_upper] for alpha/beta.
        gamma_color: Hex color for gamma profile.
        alphabeta_color: Hex color for alpha/beta profile.
        title: Panel title.
        depth_unit: Unit of ``depths``: ``'mm'``, ``'um'`` or ``'relative'`` (0 = pia,
            1 = white matter). Required; it labels the depth axis. Depths are drawn as given:
            ``'relative'`` values outside [0, 1] are channels above the pia or below the
            white matter.
        gamma_band: Frequency band of the gamma profile, (low, high) in Hz; the legend names it.
            Defaults to the vFLIP high band.
        alphabeta_band: Frequency band of the alpha/beta profile, (low, high) in Hz; the legend
            names it. Defaults to the vFLIP low band.

    Raises:
        ValueError: ``depth_unit`` is not one of the three units, a profile's shape is not
            the shape of ``depths``, or a band is not two finite numbers with low < high.
    """
    depth_title = _depth_axis_title(depth_unit)
    gamma_text = _hz_band_text("gamma_band", gamma_band)
    alphabeta_text = _hz_band_text("alphabeta_band", alphabeta_band)
    x_axis, y_axis = canvas.get_axis_names(row, col)

    gamma_power = np.asarray(gamma_power, dtype=float)
    alphabeta_power = np.asarray(alphabeta_power, dtype=float)
    depths = np.asarray(depths, dtype=float)
    for name, profile in (("gamma_power", gamma_power), ("alphabeta_power", alphabeta_power)):
        if profile.shape != depths.shape:
            raise ValueError(
                f"plot_opposing_gradients: {name} shape {profile.shape} does not match depths shape "
                f"{depths.shape}; pass one value per depth."
            )

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
            name=f"Gamma ({gamma_text})",
            line=dict(color=gamma_color, width=1.5),
            xaxis=x_axis,
            yaxis=y_axis,
            hovertemplate=f"Gamma ({gamma_text}): %{{x:.3f}}<br>Depth: %{{y:.3f}}<extra></extra>",
        )
    )
    canvas.fig.add_trace(
        go.Scatter(
            x=alphabeta_power,
            y=depths,
            mode="lines",
            name=f"Alpha/Beta ({alphabeta_text})",
            line=dict(color=alphabeta_color, width=1.5),
            xaxis=x_axis,
            yaxis=y_axis,
            hovertemplate=f"Alpha/Beta ({alphabeta_text}): %{{x:.3f}}<br>Depth: %{{y:.3f}}<extra></extra>",
        )
    )

    # Layer 4 crossover dashed reference line
    if crossover_depth is not None and np.min(depths) <= crossover_depth <= np.max(depths):
        x_max = np.nanmax([np.nanmax(gamma_power), np.nanmax(alphabeta_power)]) * 1.05
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
    title: Optional[str] = None,
    colorbar_title: Optional[str] = None,
    *,
    value_unit: str,
    depth_unit: str,
) -> None:
    """
    Render a depth x time profile, such as current source density, with layer boundaries.

    The function draws either current source density (``jnwb.current_source_density_1d``,
    A/m³) or voltage curvature (``jnwb.voltage_curvature_1d``, V/m²) and cannot tell them
    apart, so the caller names the quantity (``title``, ``colorbar_title``) and its unit
    (``value_unit``).

    Args:
        canvas: PlotlyPublicationCanvas instance.
        row: Grid row index.
        col: Grid column index.
        csd_matrix: 2D array of shape [n_depths, n_times], in ``value_unit``.
        time_ms: 1D array of time points relative to event (ms).
        depths: 1D array of cortical depths, in ``depth_unit``.
        layer_boundaries: Dictionary mapping layer names (e.g. 'L4', 'L5/6') to depth coordinates.
        cmap: Diverging colormap name (default 'RdBu_r' where blue is sink, red is source).
        title: Panel title, for example ``"Current Source Density"``. None draws no title.
        colorbar_title: Name of the quantity on the colorbar, for example ``"CSD"``; the
            colorbar reads ``"<colorbar_title> (<value_unit>)"``. None labels it with
            ``value_unit`` alone. A blank title, or one that names ``value_unit``, raises: the
            unit is written once, by ``value_unit``.
        value_unit: Unit of ``csd_matrix``, for example ``"A/m³"`` or ``"V/m²"``. Required;
            it labels the colorbar and the hover text.
        depth_unit: Unit of ``depths``: ``'mm'``, ``'um'`` or ``'relative'`` (0 = pia,
            1 = white matter). Required; it labels the depth axis. Depths are drawn as given:
            ``'relative'`` values outside [0, 1] are channels above the pia or below the
            white matter.

    Raises:
        ValueError: ``value_unit`` is not a non-empty string, ``colorbar_title`` is blank or
            names ``value_unit``, ``depth_unit`` is not one of the three units, or ``csd_matrix``
            does not have shape [len(depths), len(time_ms)] or holds no finite value.
    """
    colorbar_label = checked_colorbar_label(colorbar_title, value_unit)
    depth_title = _depth_axis_title(depth_unit)
    x_axis, y_axis = canvas.get_axis_names(row, col)

    csd_matrix = np.asarray(csd_matrix, dtype=float)
    time_ms = np.asarray(time_ms, dtype=float)
    depths = np.asarray(depths, dtype=float)
    if csd_matrix.shape != (len(depths), len(time_ms)):
        raise ValueError(
            f"plot_csd: csd_matrix shape {csd_matrix.shape} does not match depths and time_ms; "
            f"expected ({len(depths)}, {len(time_ms)})."
        )

    # Robust symmetric scale centered at 0, from the finite values only (a NaN is drawn as a gap)
    finite_abs = np.where(np.isfinite(csd_matrix), np.abs(csd_matrix), np.nan)
    if np.isnan(finite_abs).all():
        raise ValueError("plot_csd: csd_matrix holds no finite value; the colour range needs at least one.")
    vmax = float(np.nanpercentile(finite_abs, 98))
    vmin = -vmax

    cb_cfg = canvas.get_colorbar_config(row, col, title=colorbar_label)
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
        hovertemplate=(
            f"Time: %{{x:.1f}} ms<br>Depth: %{{y:.3f}} {depth_unit}<br>Value: %{{z:.2e}} {value_unit}"
            "<extra></extra>"
        ),
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
