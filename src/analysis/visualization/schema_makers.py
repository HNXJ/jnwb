# -*- coding: utf-8 -*-
"""Graphical schema makers for spike-band and moving-window correlation visualizations.

This module provides dummy-data visualization schemas that define what future
real-data analyses should look like. No biological claims. No real data processing.

All outputs are labeled: SCHEMA_ONLY_DUMMY_DATA
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np

# Try Plotly first, fall back to matplotlib
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    warnings.warn("Plotly not available, schemas will use matplotlib backend")

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# Canonical spectral bands for schemas
CANONICAL_BANDS: tuple[str, ...] = (
    "delta", "theta", "alpha", "beta_L", "beta_H", "gamma_L", "gamma_M", "gamma_H"
)

# Schema warning constants
SCHEMA_WARNING = "SCHEMA_ONLY_DUMMY_DATA"
CORRELATION_NOT_CAUSALITY = "correlation_not_causality"
LAGGED_NOT_CAUSAL = "lagged_correlation_not_causality"


def make_dummy_spike_band_correlation_data(
    *,
    n_trials: int = 80,
    n_time: int = 300,
    bands: tuple[str, ...] = ("delta", "theta", "alpha", "beta_L", "beta_H", "gamma_L", "gamma_M"),
    seed: int = 0,
) -> dict[str, Any]:
    """Create synthetic trial/time spike-rate and band-power arrays for visual schema testing only.

    Parameters
    ----------
    n_trials : int
        Number of synthetic trials (default 80)
    n_time : int
        Number of time points per trial (default 300)
    bands : tuple[str, ...]
        Spectral band names to generate
    seed : int
        Random seed for reproducibility

    Returns
    -------
    dict with keys:
        "spike_rate": ndarray, shape (n_trials, n_time)
            Arbitrary Hz-like dummy values
        "band_power": ndarray, shape (n_bands, n_trials, n_time)
            Arbitrary normalized dummy values
        "time_ms": ndarray, shape (n_time,)
            Time axis in milliseconds (-500 to +1000 ms)
        "bands": tuple[str, ...]
            Band names
        "metadata": dict
            Schema status, units, warnings

    Status: SCHEMA_ONLY_DUMMY_DATA
    """
    rng = np.random.default_rng(seed)

    # Synthetic time axis: -500ms to +1000ms (1.5s at 2ms resolution)
    time_ms = np.linspace(-500, 1000, n_time)

    # Synthetic spike rate: base rate + trial variability + time modulation
    base_rate = 10.0  # Hz-like
    trial_variability = rng.normal(0, 2, n_trials)
    time_modulation = 5 * np.sin(2 * np.pi * time_ms / 1000)  # 1 Hz modulation

    spike_rate = np.zeros((n_trials, n_time))
    for t in range(n_trials):
        spike_rate[t, :] = base_rate + trial_variability[t] + time_modulation
        # Add trial-specific noise
        spike_rate[t, :] += rng.normal(0, 1, n_time)

    # Ensure non-negative rates
    spike_rate = np.maximum(spike_rate, 0)

    # Synthetic band power: different frequency characteristics per band
    n_bands = len(bands)
    band_power = np.zeros((n_bands, n_trials, n_time))

    for b, band in enumerate(bands):
        # Each band has different baseline and modulation
        base_power = 1.0 + 0.5 * np.sin(b)  # Different per band

        for t in range(n_trials):
            # Band-specific time modulation
            freq = 0.5 + 0.1 * b  # Different frequency per band
            phase = 2 * np.pi * rng.random()
            modulation = 0.3 * np.sin(2 * np.pi * freq * time_ms / 1000 + phase)

            # Trial-specific scaling
            trial_scale = 1.0 + 0.2 * rng.normal()

            band_power[b, t, :] = base_power * trial_scale + modulation
            band_power[b, t, :] += rng.normal(0, 0.1, n_time)

    # Normalize to [0, 1] range for visualization clarity
    for b in range(n_bands):
        bmin, bmax = band_power[b].min(), band_power[b].max()
        if bmax > bmin:
            band_power[b] = (band_power[b] - bmin) / (bmax - bmin)

    return {
        "spike_rate": spike_rate.astype(np.float32),
        "band_power": band_power.astype(np.float32),
        "time_ms": time_ms.astype(np.float32),
        "bands": bands,
        "metadata": {
            "schema_warning": SCHEMA_WARNING,
            "status": "SCHEMA_ONLY_DUMMY_DATA",
            "spike_rate_units": "arbitrary_Hz_like_dummy",
            "band_power_units": "arbitrary_normalized_dummy",
            "n_trials": n_trials,
            "n_time": n_time,
            "time_range_ms": [float(time_ms[0]), float(time_ms[-1])],
            "seed": seed,
            "correlation_not_causality": True,
        }
    }


def _compute_dummy_correlations(spike_rate: np.ndarray, band_power: np.ndarray) -> dict:
    """Compute dummy correlations for schema visualization.

    Parameters
    ----------
    spike_rate : ndarray, shape (n_trials, n_time)
    band_power : ndarray, shape (n_bands, n_trials, n_time)

    Returns
    dict with correlation arrays for schema plotting.
    """
    n_bands = band_power.shape[0]
    n_trials, n_time = spike_rate.shape

    # Flatten trial x time for overall correlation
    spike_flat = spike_rate.flatten()

    corr_by_band = np.zeros(n_bands)
    for b in range(n_bands):
        band_flat = band_power[b].flatten()
        # Pearson correlation
        if np.std(spike_flat) > 0 and np.std(band_flat) > 0:
            corr_by_band[b] = np.corrcoef(spike_flat, band_flat)[0, 1]
        else:
            corr_by_band[b] = 0.0

    # Rolling window correlation across time (averaged across trials)
    window_size = 20
    n_windows = n_time - window_size + 1
    rolling_corr = np.zeros((n_bands, n_windows))

    for b in range(n_bands):
        for w in range(n_windows):
            w_start = w
            w_end = w + window_size
            # Average across trials for this window
            spike_window = spike_rate[:, w_start:w_end].mean(axis=1)
            band_window = band_power[b, :, w_start:w_end].mean(axis=1)

            if np.std(spike_window) > 0 and np.std(band_window) > 0:
                rolling_corr[b, w] = np.corrcoef(spike_window, band_window)[0, 1]
            else:
                rolling_corr[b, w] = 0.0

    return {
        "corr_by_band": corr_by_band.astype(np.float32),
        "rolling_corr": rolling_corr.astype(np.float32),
        "window_size": window_size,
        "n_windows": n_windows,
    }


def plot_neuron_band_correlation_density_schema(
    data: dict,
    *,
    neuron_id: str = "dummy_unit_001",
    area: str = "V1",
    channel: str = "probe0_ch000",
    out_html: str | None = None,
    title: str | None = None,
) -> dict:
    """Plot schema for one neuron's spike-rate correlation density against LFP band power.

    Intended real future input:
      spike_rate: trial x time
      band_power: band x trial x time

    Visualization grammar:
      Panel A: schematic metadata card: neuron, area, channel, trial/time shape.
      Panel B: per-band correlation density or violin/strip plot.
      Panel C: band x time heatmap of rolling spike-band correlation.
      Panel D: scatter-density example for selected band.

    Parameters
    ----------
    data : dict
        Output from make_dummy_spike_band_correlation_data()
    neuron_id : str
        Identifier for display
    area : str
        Brain area for display
    channel : str
        LFP channel for display
    out_html : str | None
        Path to save HTML output
    title : str | None
        Custom title

    Returns
    -------
    dict with figure object and metadata
    """
    spike_rate = data["spike_rate"]
    band_power = data["band_power"]
    time_ms = data["time_ms"]
    bands = data["bands"]

    n_trials, n_time = spike_rate.shape
    n_bands = len(bands)

    # Compute correlations
    corrs = _compute_dummy_correlations(spike_rate, band_power)

    if title is None:
        title = f"Spike-Band Correlation Schema: {neuron_id}"

    fig_dict = {
        "title": title,
        "schema_warning": SCHEMA_WARNING,
        "correlation_not_causality": CORRELATION_NOT_CAUSALITY,
        "panels": {},
        "metadata": {
            "neuron_id": neuron_id,
            "area": area,
            "channel": channel,
            "n_trials": n_trials,
            "n_time": n_time,
            "bands": bands,
        }
    }

    if PLOTLY_AVAILABLE:
        # Create Plotly figure with subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "A: Metadata Card",
                "B: Per-Band Correlation",
                "C: Rolling Correlation Heatmap",
                "D: Example Scatter (Alpha Band)"
            ),
            specs=[
                [{"type": "table"}, {"type": "xy"}],
                [{"type": "heatmap"}, {"type": "xy"}]
            ],
            vertical_spacing=0.15,
            horizontal_spacing=0.1,
        )

        # Panel A: Metadata table
        metadata_table = go.Table(
            header=dict(values=["Property", "Value"], fill_color="lightgray"),
            cells=dict(values=[
                ["SCHEMA_STATUS", "Neuron ID", "Area", "Channel", "Trials", "Time Points", "Bands"],
                [f"{SCHEMA_WARNING}", neuron_id, area, channel, n_trials, n_time, len(bands)]
            ])
        )
        fig.add_trace(metadata_table, row=1, col=1)

        # Panel B: Per-band correlation bar
        fig.add_trace(
            go.Bar(x=list(bands), y=corrs["corr_by_band"], name="Correlation (r)"),
            row=1, col=2
        )
        fig.update_yaxes(title_text="Pearson r", row=1, col=2)

        # Panel C: Rolling correlation heatmap
        rolling_time_ms = time_ms[:corrs["n_windows"]]
        fig.add_trace(
            go.Heatmap(
                z=corrs["rolling_corr"],
                x=rolling_time_ms,
                y=list(bands),
                colorscale="RdBu",
                zmid=0,
                name="Rolling r"
            ),
            row=2, col=1
        )
        fig.update_xaxes(title_text="Time (ms)", row=2, col=1)
        fig.update_yaxes(title_text="Band", row=2, col=1)

        # Panel D: Scatter for alpha band (if available)
        alpha_idx = None
        for i, b in enumerate(bands):
            if "alpha" in b.lower():
                alpha_idx = i
                break
        if alpha_idx is None:
            alpha_idx = min(2, n_bands - 1)  # Default to third band or last

        spike_flat = spike_rate.flatten()
        alpha_flat = band_power[alpha_idx].flatten()

        fig.add_trace(
            go.Scatter(
                x=spike_flat[::10],  # Subsample for clarity
                y=alpha_flat[::10],
                mode="markers",
                marker=dict(size=3, opacity=0.5),
                name=f"{bands[alpha_idx]} band"
            ),
            row=2, col=2
        )
        fig.update_xaxes(title_text="Spike Rate (dummy Hz)", row=2, col=2)
        fig.update_yaxes(title_text="Band Power (norm)", row=2, col=2)

        # Add schema warning annotation
        fig.add_annotation(
            text=f"⚠️ {SCHEMA_WARNING}<br>{CORRELATION_NOT_CAUSALITY}",
            xref="paper", yref="paper",
            x=0.5, y=-0.15,
            showarrow=False,
            font=dict(color="red", size=10),
            align="center"
        )

        fig.update_layout(
            title=title,
            height=700,
            showlegend=False,
        )

        fig_dict["figure"] = fig

        # Save if requested
        if out_html:
            Path(out_html).parent.mkdir(parents=True, exist_ok=True)
            fig.write_html(out_html)
            fig_dict["html_path"] = out_html

    else:
        # Matplotlib fallback - return schema description
        fig_dict["backend"] = "matplotlib_not_implemented"
        fig_dict["note"] = "Plotly not available, schema defined but not rendered"

    return fig_dict


def make_dummy_moving_window_progression_data(
    *,
    n_windows: int = 80,
    n_lags: int = 41,
    sources: tuple[str, ...] = ("V1_spike", "V4_spike", "PFC_spike", "V1_alpha", "V4_gamma", "PFC_beta"),
    seed: int = 1,
) -> dict[str, Any]:
    """Create synthetic moving-window lagged correlation data for visual schema testing.

    Parameters
    ----------
    n_windows : int
        Number of time windows (default 80)
    n_lags : int
        Number of lag bins (default 41, centered at 0)
    sources : tuple[str, ...]
        Source signal labels
    seed : int
        Random seed for reproducibility

    Returns
    -------
    dict with keys:
        "corr": ndarray, shape (n_sources, n_targets, n_windows, n_lags)
            Dummy lagged correlation values
        "time_ms": ndarray, shape (n_windows,)
            Window center times in ms
        "lags_ms": ndarray, shape (n_lags,)
            Lag values in ms (negative = source lags target)
        "sources": tuple[str, ...]
        "targets": tuple[str, ...]
        "metadata": dict
            Schema status, lag convention, warnings

    Lag Convention:
        Positive lag: source leads target (source activity precedes target)
        Negative lag: source lags target (source activity follows target)
        Zero lag: simultaneous correlation

    Status: SCHEMA_ONLY_DUMMY_DATA
    """
    rng = np.random.default_rng(seed)

    n_sources = len(sources)
    n_targets = n_sources  # Square matrix for all pairs

    # Time windows: -1000ms to +2000ms
    time_ms = np.linspace(-1000, 2000, n_windows)

    # Lags: -200ms to +200ms
    lags_ms = np.linspace(-200, 200, n_lags)

    # Generate synthetic correlation structure
    corr = np.zeros((n_sources, n_targets, n_windows, n_lags))

    for s in range(n_sources):
        for t in range(n_targets):
            if s == t:
                # Self-correlation: peak at lag 0
                for w in range(n_windows):
                    # Gaussian centered at lag 0
                    corr[s, t, w, :] = np.exp(-(lags_ms / 50) ** 2)
                    # Add time-varying modulation
                    corr[s, t, w, :] *= (0.5 + 0.5 * np.sin(2 * np.pi * w / n_windows))
            else:
                # Cross-correlation: random lag structure
                # Some pairs have positive lag lead, some negative
                lead_source = rng.choice([True, False])
                peak_lag_idx = rng.integers(n_lags // 3, 2 * n_lags // 3)

                for w in range(n_windows):
                    # Smooth peak at some lag
                    lag_spread = 30 + 20 * rng.random()
                    corr[s, t, w, :] = 0.3 * np.exp(-((lags_ms - lags_ms[peak_lag_idx]) / lag_spread) ** 2)

                    # Add noise
                    corr[s, t, w, :] += rng.normal(0, 0.1, n_lags)

    # Clip to reasonable correlation range
    corr = np.clip(corr, -1, 1)

    return {
        "corr": corr.astype(np.float32),
        "time_ms": time_ms.astype(np.float32),
        "lags_ms": lags_ms.astype(np.float32),
        "sources": sources,
        "targets": sources,  # Same as sources for all-pairs
        "metadata": {
            "schema_warning": SCHEMA_WARNING,
            "status": "SCHEMA_ONLY_DUMMY_DATA",
            "lag_convention": {
                "positive_lag": "source leads target (precedes)",
                "negative_lag": "source lags target (follows)",
                "zero_lag": "simultaneous",
            },
            "n_windows": n_windows,
            "n_lags": n_lags,
            "time_range_ms": [float(time_ms[0]), float(time_ms[-1])],
            "lag_range_ms": [float(lags_ms[0]), float(lags_ms[-1])],
            "seed": seed,
            "lagged_correlation_not_causality": LAGGED_NOT_CAUSAL,
        }
    }


def plot_moving_window_correlation_progression_schema(
    data: dict,
    *,
    selected_pairs: tuple[tuple[str, str], ...] | None = None,
    out_html: str | None = None,
    title: str | None = None,
) -> dict:
    """Plot schema for moving-window correlation / lead-lag progression.

    Visualization grammar:
      Panel A: source-target lag heatmap: time × lag
      Panel B: peak-lag trajectory over time for selected pairs
      Panel C: source-target correlation matrix at selected time frames
      Panel D: frame-strip timeline with epoch labels

    Parameters
    ----------
    data : dict
        Output from make_dummy_moving_window_progression_data()
    selected_pairs : tuple[tuple[str, str], ...] | None
        Source-target pairs to highlight. If None, selects first 3.
    out_html : str | None
        Path to save HTML output
    title : str | None
        Custom title

    Returns
    -------
    dict with figure object and metadata
    """
    corr = data["corr"]
    time_ms = data["time_ms"]
    lags_ms = data["lags_ms"]
    sources = data["sources"]
    metadata = data["metadata"]

    n_sources = len(sources)
    n_windows = len(time_ms)
    n_lags = len(lags_ms)

    # Select pairs if not provided
    if selected_pairs is None:
        selected_pairs = []
        for i in range(min(3, n_sources)):
            for j in range(min(3, n_sources)):
                if i != j:
                    selected_pairs.append((sources[i], sources[j]))
        selected_pairs = tuple(selected_pairs[:4])  # Max 4 pairs

    if title is None:
        title = "Moving-Window Lagged Correlation Schema"

    fig_dict = {
        "title": title,
        "schema_warning": SCHEMA_WARNING,
        "lagged_correlation_not_causality": LAGGED_NOT_CAUSAL,
        "lag_convention": metadata["lag_convention"],
        "panels": {},
        "metadata": {
            "selected_pairs": selected_pairs,
            "n_windows": n_windows,
            "n_lags": n_lags,
        }
    }

    if PLOTLY_AVAILABLE:
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "A: Time × Lag Heatmap",
                "B: Peak-Lag Trajectory",
                "C: Correlation Matrix (selected window)",
                "D: Frame Timeline"
            ),
            specs=[
                [{"type": "heatmap"}, {"type": "xy"}],
                [{"type": "heatmap"}, {"type": "xy"}]
            ],
            vertical_spacing=0.15,
            horizontal_spacing=0.1,
        )

        # Get first selected pair indices
        pair = selected_pairs[0] if selected_pairs else (sources[0], sources[1] if n_sources > 1 else sources[0])
        s_idx = sources.index(pair[0])
        t_idx = sources.index(pair[1])

        # Panel A: Time x Lag heatmap for selected pair
        fig.add_trace(
            go.Heatmap(
                z=corr[s_idx, t_idx, :, :].T,  # (lags, windows) -> transpose for (windows, lags)
                x=time_ms,
                y=lags_ms,
                colorscale="RdBu",
                zmid=0,
                colorbar=dict(title="r"),
                name=f"{pair[0]} → {pair[1]}"
            ),
            row=1, col=1
        )
        fig.update_xaxes(title_text="Time (ms)", row=1, col=1)
        fig.update_yaxes(title_text="Lag (ms)", row=1, col=1)

        # Panel B: Peak-lag trajectory for selected pairs
        colors = ["blue", "green", "red", "purple"]
        for p_idx, (s_name, t_name) in enumerate(selected_pairs[:4]):
            s_i = sources.index(s_name)
            t_i = sources.index(t_name)

            # Find peak lag at each window
            peak_lags = np.zeros(n_windows)
            for w in range(n_windows):
                peak_idx = np.argmax(np.abs(corr[s_i, t_i, w, :]))
                peak_lags[w] = lags_ms[peak_idx]

            fig.add_trace(
                go.Scatter(
                    x=time_ms,
                    y=peak_lags,
                    mode="lines+markers",
                    name=f"{s_name} → {t_name}",
                    line=dict(color=colors[p_idx % len(colors)])
                ),
                row=1, col=2
            )

        fig.update_xaxes(title_text="Time (ms)", row=1, col=2)
        fig.update_yaxes(title_text="Peak Lag (ms)", row=1, col=2)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=2)

        # Panel C: Correlation matrix at selected window (middle)
        mid_window = n_windows // 2
        # Use lag 0 for matrix visualization
        lag0_idx = n_lags // 2
        corr_matrix = corr[:, :, mid_window, lag0_idx]

        fig.add_trace(
            go.Heatmap(
                z=corr_matrix,
                x=list(sources),
                y=list(sources),
                colorscale="RdBu",
                zmid=0,
                colorbar=dict(title="r (lag=0)"),
            ),
            row=2, col=1
        )

        # Panel D: Frame timeline with epoch labels
        # Simplified timeline visualization
        epochs = [
            ("Pre-fix", -1000, -200, "lightgray"),
            ("Fix", -200, 0, "lightblue"),
            ("Stim", 0, 500, "lightgreen"),
            ("Post", 500, 2000, "lightyellow"),
        ]

        for epoch_name, t_start, t_end, color in epochs:
            fig.add_vrect(
                x0=t_start, x1=t_end,
                fillcolor=color, opacity=0.3,
                layer="below", line_width=0,
                row=2, col=2
            )
            fig.add_annotation(
                x=(t_start + t_end) / 2,
                y=0.9,
                text=epoch_name,
                showarrow=False,
                row=2, col=2
            )

        # Add time axis
        fig.add_trace(
            go.Scatter(
                x=time_ms,
                y=np.zeros_like(time_ms),
                mode="lines",
                line=dict(color="black"),
                showlegend=False
            ),
            row=2, col=2
        )
        fig.update_xaxes(title_text="Time (ms)", row=2, col=2)
        fig.update_yaxes(visible=False, row=2, col=2)

        # Add lag convention annotation
        lag_conv = metadata["lag_convention"]
        lag_text = f"Lag Convention:<br>+ = {lag_conv['positive_lag']}<br>- = {lag_conv['negative_lag']}"

        fig.add_annotation(
            text=f"⚠️ {SCHEMA_WARNING}<br>{LAGGED_NOT_CAUSAL}<br><br>{lag_text}",
            xref="paper", yref="paper",
            x=0.5, y=-0.15,
            showarrow=False,
            font=dict(color="red", size=10),
            align="center"
        )

        fig.update_layout(
            title=title,
            height=800,
        )

        fig_dict["figure"] = fig

        if out_html:
            Path(out_html).parent.mkdir(parents=True, exist_ok=True)
            fig.write_html(out_html)
            fig_dict["html_path"] = out_html

    else:
        fig_dict["backend"] = "matplotlib_not_implemented"
        fig_dict["note"] = "Plotly not available, schema defined but not rendered"

    return fig_dict


def write_schema_gallery(
    out_dir: str = "outputs/publication_figures/schema_dummies",
) -> dict:
    """Create all dummy schema plots and write gallery files.

    Parameters
    ----------
    out_dir : str
        Output directory for schema files

    Returns
    -------
    dict with manifest of created files
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    manifest = {
        "phase": "GRAPHICAL_SCHEMA_LAYER",
        "schema_only_dummy_data": True,
        "claim_status": "no_biological_claim",
        "created_at": None,
        "schemas": [],
        "warnings": [
            "SCHEMA_ONLY_DUMMY_DATA",
            "Correlation does not imply causality.",
            "Lagged correlation is not directionality proof.",
            "Dummy data are synthetic.",
        ]
    }

    created_files = []

    # Schema 1: Spike-Band Correlation
    print("Creating spike-band correlation schema...")
    spike_data = make_dummy_spike_band_correlation_data(seed=42)
    spike_result = plot_neuron_band_correlation_density_schema(
        spike_data,
        neuron_id="dummy_V1_unit_001",
        area="V1",
        channel="probe0_ch032",
        out_html=str(out_path / "spike_band_correlation_density_schema.html"),
        title="Schema: Neuron-Spectral Band Correlation Density"
    )

    manifest["schemas"].append({
        "schema_id": "spike_band_correlation_density",
        "html_path": str(out_path / "spike_band_correlation_density_schema.html"),
        "future_real_inputs": {
            "spike_rate": "trial x time",
            "band_power": "band x trial x time"
        },
        "dummy_data_shape": {
            "spike_rate": list(spike_data["spike_rate"].shape),
            "band_power": list(spike_data["band_power"].shape),
        },
        "status": "SCHEMA_ONLY_DUMMY_DATA"
    })
    created_files.append("spike_band_correlation_density_schema.html")

    # Schema 2: Moving-Window Progression
    print("Creating moving-window progression schema...")
    window_data = make_dummy_moving_window_progression_data(seed=123)
    window_result = plot_moving_window_correlation_progression_schema(
        window_data,
        selected_pairs=(("V1_spike", "V4_gamma"), ("PFC_beta", "V1_alpha")),
        out_html=str(out_path / "moving_window_correlation_progression_schema.html"),
        title="Schema: Moving-Window Lead-Lag Progression"
    )

    manifest["schemas"].append({
        "schema_id": "moving_window_correlation_progression",
        "html_path": str(out_path / "moving_window_correlation_progression_schema.html"),
        "future_real_inputs": {
            "corr": "source x target x window x lag"
        },
        "dummy_data_shape": {
            "corr": list(window_data["corr"].shape),
        },
        "lag_convention": window_data["metadata"]["lag_convention"],
        "status": "SCHEMA_ONLY_DUMMY_DATA"
    })
    created_files.append("moving_window_correlation_progression_schema.html")

    # Create index HTML
    index_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Graphical Schema Gallery — SCHEMA_ONLY_DUMMY_DATA</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .warning {{ background: #ffcccc; padding: 20px; border: 2px solid red; margin-bottom: 30px; }}
        .schema-card {{ border: 1px solid #ccc; padding: 20px; margin: 20px 0; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; }}
        code {{ background: #f4f4f4; padding: 2px 5px; }}
    </style>
</head>
<body>
    <div class="warning">
        <h1>⚠️ SCHEMA_ONLY_DUMMY_DATA</h1>
        <p><strong>This gallery contains synthetic dummy data for visualization schema testing only.</strong></p>
        <p>These plots demonstrate intended visualization grammar for future real-data analyses.</p>
        <p><strong>No biological claims. No real NWB data. Correlation ≠ Causality.</strong></p>
    </div>

    <h1>Graphical Schema Gallery</h1>
    <p><strong>Phase:</strong> GRAPHICAL_SCHEMA_LAYER</p>
    <p><strong>Status:</strong> Dummy data visualization schemas</p>

    <div class="schema-card">
        <h2>Schema 1: Spike-Band Correlation Density</h2>
        <p>Visualizes correlation between spike rate and LFP band power across trials and time.</p>
        <p><strong>Future inputs:</strong> <code>spike_rate[trial, time]</code>, <code>band_power[band, trial, time]</code></p>
        <p><a href="spike_band_correlation_density_schema.html">View Schema →</a></p>
    </div>

    <div class="schema-card">
        <h2>Schema 2: Moving-Window Lead-Lag Progression</h2>
        <p>Visualizes how lagged correlations evolve across time windows.</p>
        <p><strong>Future inputs:</strong> <code>corr[source, target, window, lag]</code></p>
        <p><strong>Lag convention:</strong> Positive lag = source leads target (precedes)</p>
        <p><a href="moving_window_correlation_progression_schema.html">View Schema →</a></p>
    </div>

    <hr>
    <p><small>Generated: {np.datetime64('now').astype(str)} | Status: {SCHEMA_WARNING}</small></p>
</body>
</html>
"""

    index_path = out_path / "schema_gallery_index.html"
    index_path.write_text(index_html, encoding='utf-8')
    created_files.append("schema_gallery_index.html")
    manifest["index_html"] = str(index_path)

    # Save manifest
    manifest["created_at"] = str(np.datetime64('now'))
    manifest["created_files"] = created_files

    manifest_path = out_path / "schema_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\nSchema gallery created in: {out_path}")
    print(f"Files: {created_files}")
    print(f"Manifest: {manifest_path}")

    return manifest


if __name__ == "__main__":
    # Run gallery creation when executed directly
    write_schema_gallery()
