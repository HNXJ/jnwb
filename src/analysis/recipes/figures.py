"""Preview figure generation for analysis recipes.

These are analysis preview figures, not manuscript-final figures.
Use Plotly for interactive HTML outputs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

# Optional plotly import with graceful fallback
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from src.analysis.lfp.lfp_constants import GOLD, VIOLET, GRAY, SLATE


def _save_or_warn(fig: Any, out_html: Path | str, title: str) -> bool:
    """Save figure to HTML if plotly available, else warn."""
    if not PLOTLY_AVAILABLE:
        import warnings
        warnings.warn(f"Plotly not available, cannot save figure: {title}")
        return False
    
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    
    fig.update_layout(title=title)
    fig.write_html(out_html)
    return True


def plot_spike_rate_preview(
    rate_result: dict[str, dict[str, np.ndarray]],
    out_html: Path | str,
    title: str = "Spike Rate Preview",
    time_axis_ms: np.ndarray | None = None,
) -> bool:
    """Plot spike rate preview figure.
    
    Parameters
    ----------
    rate_result : Output from run_spike_rate with "mean_rate_hz" and "sem_rate_hz"
    out_html : Destination path for HTML figure
    title : Figure title
    time_axis_ms : Optional time axis in milliseconds
    
    Returns
    -------
    True if figure saved, False if plotly unavailable
    
    Output:
    - Interactive Plotly HTML with mean ± SEM across units
    - One trace per condition
    """
    if not PLOTLY_AVAILABLE:
        return _save_or_warn(None, out_html, title)
    
    fig = go.Figure()
    
    # Plot mean ± SEM for each condition
    for condition, data in rate_result.items():
        mean_rate = data.get("mean_rate_hz")
        sem_rate = data.get("sem_rate_hz")
        
        if mean_rate is None or mean_rate.size == 0:
            continue
        
        # Average across units for population PSTH
        pop_mean = np.mean(mean_rate, axis=0)  # (time,)
        pop_sem = np.mean(sem_rate, axis=0) if sem_rate is not None else np.zeros_like(pop_mean)
        
        # Generate time axis if not provided
        if time_axis_ms is None:
            t = np.arange(len(pop_mean))
        else:
            t = time_axis_ms[:len(pop_mean)]
        
        # Add trace
        fig.add_trace(go.Scatter(
            x=t,
            y=pop_mean,
            mode='lines',
            name=condition,
            line=dict(width=2),
            fillcolor='rgba(0,100,80,0.2)',
            fill='tonexty' if len(fig.data) > 1 else None,
        ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Time (ms)",
        yaxis_title="Firing Rate (Hz)",
        template="plotly_white",
        hovermode="x unified",
    )
    
    return _save_or_warn(fig, out_html, title)


def plot_tfr_preview(
    tfr_result: dict[str, dict[str, np.ndarray]],
    out_html: Path | str,
    title: str = "TFR Preview",
    channel_idx: int = 0,
    trial_idx: int = 0,
) -> bool:
    """Plot TFR preview figure.
    
    Parameters
    ----------
    tfr_result : Output from run_tfr with "power_db"
    out_html : Destination path for HTML figure
    title : Figure title
    channel_idx : Which channel to show (default 0)
    trial_idx : Which trial to show (default 0, -1 for trial average)
    
    Returns
    -------
    True if figure saved, False if plotly unavailable
    
    Output:
    - Interactive Plotly heatmap
    - One subplot per condition
    """
    if not PLOTLY_AVAILABLE:
        return _save_or_warn(None, out_html, title)
    
    conditions = list(tfr_result.keys())
    n_conditions = len(conditions)
    
    if n_conditions == 0:
        return False
    
    # Create subplots
    fig = make_subplots(
        rows=1,
        cols=min(n_conditions, 4),
        subplot_titles=conditions[:4],
        shared_yaxes=True,
    )
    
    for i, condition in enumerate(conditions[:4]):  # Max 4 conditions
        data = tfr_result[condition]
        power_db = data.get("power_db")
        freqs = data.get("freqs")
        times_ms = data.get("times_ms")
        
        if power_db is None or power_db.size == 0:
            continue
        
        # Extract single trial or average
        if trial_idx < 0:
            # Average across trials
            power_display = np.mean(power_db[:, channel_idx, :, :], axis=0)  # (freqs, time)
        else:
            power_display = power_db[trial_idx, channel_idx, :, :]  # (freqs, time)
        
        # Add heatmap
        fig.add_trace(
            go.Heatmap(
                z=power_display,
                x=times_ms if times_ms is not None else np.arange(power_display.shape[1]),
                y=freqs if freqs is not None else np.arange(power_display.shape[0]),
                colorscale="Viridis",
                colorbar=dict(title="dB"),
                name=condition,
            ),
            row=1,
            col=i+1,
        )
    
    fig.update_layout(
        title=title,
        height=400,
        width=300 * min(n_conditions, 4),
    )
    
    fig.update_xaxes(title_text="Time (ms)")
    fig.update_yaxes(title_text="Frequency (Hz)")
    
    return _save_or_warn(fig, out_html, title)


def plot_band_power_preview(
    band_power_result: dict[str, dict[str, np.ndarray]],
    out_html: Path | str,
    title: str = "Band Power Preview",
    band_name: str = "gamma_M",
    channel_idx: int = 0,
) -> bool:
    """Plot band power preview figure.
    
    Parameters
    ----------
    band_power_result : Output from run_band_power
    out_html : Destination path for HTML figure
    title : Figure title
    band_name : Which band to plot (e.g., "gamma_M", "beta")
    channel_idx : Which channel to show (default 0)
    
    Returns
    -------
    True if figure saved, False if plotly unavailable
    """
    if not PLOTLY_AVAILABLE:
        return _save_or_warn(None, out_html, title)
    
    fig = go.Figure()
    
    for condition, bands in band_power_result.items():
        if band_name not in bands:
            continue
        
        power = bands[band_name]  # (trials, channels, time)
        if power.size == 0:
            continue
        
        # Average across trials, single channel
        power_display = np.mean(power[:, channel_idx, :], axis=0)  # (time,)
        
        fig.add_trace(go.Scatter(
            y=power_display,
            mode='lines',
            name=condition,
        ))
    
    fig.update_layout(
        title=f"{title}: {band_name}",
        xaxis_title="Time (samples)",
        yaxis_title="Power",
        template="plotly_white",
    )
    
    return _save_or_warn(fig, out_html, title)


def plot_Y_tensor_heatmap(
    Y_result: dict[str, Any],
    out_html: Path | str,
    title: str = "Y Tensor Preview",
    epoch_idx: int = 0,
    layer_idx: int = 0,
) -> bool:
    """Plot Y tensor as area x band heatmap.
    
    Parameters
    ----------
    Y_result : Output from build_Y_tensor with "Y" array
    out_html : Destination path for HTML figure
    title : Figure title
    epoch_idx : Which epoch/period to show
    layer_idx : Which layer to show
    
    Returns
    -------
    True if figure saved, False if plotly unavailable
    
    Output:
    - Heatmap: areas (rows) x bands (columns)
    """
    if not PLOTLY_AVAILABLE:
        return _save_or_warn(None, out_html, title)
    
    Y = Y_result.get("Y")
    coords = Y_result.get("coords", {})
    
    if Y is None or Y.size == 0:
        return False
    
    # Y shape: (bands, areas, epochs, layers)
    # Extract slice: (bands, areas)
    Y_slice = Y[:, :, epoch_idx, layer_idx]
    
    bands = coords.get("band", [f"B{i}" for i in range(Y.shape[0])])
    areas = coords.get("area", [f"A{i}" for i in range(Y.shape[1])])
    epochs = coords.get("epoch", [f"E{i}" for i in range(Y.shape[2])])
    layers = coords.get("layer", [f"L{i}" for i in range(Y.shape[3])])
    
    fig = go.Figure(data=go.Heatmap(
        z=Y_slice,
        x=areas,
        y=bands,
        colorscale="RdBu_r",
        zmid=0,
        colorbar=dict(title="Power"),
    ))
    
    fig.update_layout(
        title=f"{title}: {epochs[epoch_idx]}, {layers[layer_idx]}",
        xaxis_title="Area",
        yaxis_title="Band",
        template="plotly_white",
    )
    
    return _save_or_warn(fig, out_html, title)


def plot_H_harmony_heatmap(
    H_result: dict[str, Any],
    out_html: Path | str,
    title: str = "H Harmony Preview",
    band_idx: int = 0,
    epoch_idx: int = 0,
    layer_idx: int = 0,
) -> bool:
    """Plot H harmony matrix as area x area heatmap.
    
    Parameters
    ----------
    H_result : Output from build_H_harmony with "H" array
    out_html : Destination path for HTML figure
    title : Figure title
    band_idx : Which band
    epoch_idx : Which epoch
    layer_idx : Which layer
    
    Returns
    -------
    True if figure saved, False if plotly unavailable
    
    Output:
    - Heatmap: areas (rows) x areas (columns)
    - Diagonal is self-similarity (should be 1)
    - Symmetric matrix
    """
    if not PLOTLY_AVAILABLE:
        return _save_or_warn(None, out_html, title)
    
    H = H_result.get("H")
    coords = H_result.get("coords", {})
    
    if H is None or H.size == 0:
        return False
    
    # H shape: (bands, epochs, layers, areas, areas)
    # Extract slice: (areas, areas)
    H_slice = H[band_idx, epoch_idx, layer_idx, :, :]
    
    bands = coords.get("band", [f"B{i}" for i in range(H.shape[0])])
    epochs = coords.get("epoch", [f"E{i}" for i in range(H.shape[1])])
    layers = coords.get("layer", [f"L{i}" for i in range(H.shape[2])])
    areas = coords.get("area", [f"A{i}" for i in range(H.shape[3])])
    
    fig = go.Figure(data=go.Heatmap(
        z=H_slice,
        x=areas,
        y=areas,
        colorscale="Blues",
        zmin=0,
        zmax=1,
        colorbar=dict(title="Harmony"),
    ))
    
    fig.update_layout(
        title=f"{title}: {bands[band_idx]}, {epochs[epoch_idx]}, {layers[layer_idx]}",
        xaxis_title="Area (to)",
        yaxis_title="Area (from)",
        template="plotly_white",
    )
    
    return _save_or_warn(fig, out_html, title)
