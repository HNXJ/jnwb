import matplotlib
matplotlib.use("Agg")  # headless test environment, no display needed

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from jnwb.visual_qc import (
    plot_unit_waveforms,
    plot_unit_quality_distribution,
    plot_noise_vs_signal,
    compare_session_quality,
)


def _units_df(n=20, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "session_id": [1] * n,
            "firing_rate": rng.uniform(1, 20, n),
            "snr": rng.uniform(0.2, 3.0, n),
            "waveform_duration": rng.uniform(200, 800, n),
            "quality": rng.uniform(0, 2, n),
            "area": rng.choice(["V1", "PFC", "FEF"], n),
            "is_stable": rng.choice([True, False], n),
            "stable_plus": rng.choice([True, False], n),
        }
    )


def test_plot_unit_waveforms_paginates_and_plots_mean_std():
    unit_ids = list(range(14))
    waveforms = {uid: np.random.default_rng(uid).normal(size=(30, 82)) for uid in unit_ids}

    figs = plot_unit_waveforms(unit_ids, waveforms, max_units_per_page=12)

    # 14 units at 12/page -> 2 pages
    assert len(figs) == 2
    assert len(figs[0].axes) == 12
    assert len(figs[1].axes) == 2
    for fig in figs:
        plt.close(fig)


def test_plot_unit_waveforms_handles_missing_unit_gracefully():
    figs = plot_unit_waveforms([0, 1], {0: np.zeros((5, 10))}, max_units_per_page=12)
    assert len(figs) == 1
    assert len(figs[0].axes) == 2
    plt.close(figs[0])


def test_plot_unit_quality_distribution_returns_populated_figure():
    units = _units_df()
    fig = plot_unit_quality_distribution(units)

    assert isinstance(fig, plt.Figure)
    # 2x3 grid of panels declared in the implementation
    assert len(fig.axes) == 6
    plt.close(fig)


def test_plot_unit_quality_distribution_session_filter_reduces_data():
    units = pd.concat(
        [_units_df(n=10, seed=1).assign(session_id=1), _units_df(n=10, seed=2).assign(session_id=2)],
        ignore_index=True,
    )
    fig = plot_unit_quality_distribution(units, session_ids=[1])
    # Firing-rate panel title embeds n= count; must reflect the filtered subset only
    fr_title = fig.axes[0].get_title()
    assert "n=10" in fr_title
    plt.close(fig)


def test_plot_noise_vs_signal_returns_2x2_figure():
    units = _units_df()
    fig = plot_noise_vs_signal(units)
    assert isinstance(fig, plt.Figure)
    assert len(fig.axes) == 4
    plt.close(fig)


def test_compare_session_quality_bars_match_session_count():
    comparison = pd.DataFrame(
        {
            "session_id": ["230823", "260629", "230630"],
            "snr_mean": [1.5, 0.8, 0.3],
            "total_units": [120, 95, 40],
            "snr_good_rate": [0.6, 0.3, 0.1],
        }
    )
    fig = compare_session_quality(comparison)
    assert isinstance(fig, plt.Figure)
    assert len(fig.axes) == 3
    # Bar count in the SNR panel must match the number of sessions
    assert len(fig.axes[0].patches) == 3
    plt.close(fig)
