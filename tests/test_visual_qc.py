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
    # Single-channel spikes are (n_spikes, 1, n_samples).
    waveforms = {uid: np.random.default_rng(uid).normal(size=(30, 1, 82)) for uid in unit_ids}

    figs = plot_unit_waveforms(unit_ids, waveforms, max_units_per_page=12, channels="peak")

    # 14 units at 12/page -> 2 pages
    assert len(figs) == 2
    assert len(figs[0].axes) == 12
    assert len(figs[1].axes) == 2
    (line,) = figs[0].axes[0].get_lines()
    np.testing.assert_allclose(line.get_ydata(), waveforms[0][:, 0, :].mean(axis=0))
    assert len(figs[0].axes[0].collections) == 1  # the ±1 SD band across spikes
    for fig in figs:
        plt.close(fig)


def test_plot_unit_waveforms_draws_channels_unaveraged_and_refuses_a_missing_unit():
    import pytest

    # The peak is a -100 trough on channel 2; channel 0 carries a smaller, positive +60, so
    # a signed maximum would pick channel 0 and a channel mean would draw -25.
    template = np.zeros((4, 30))
    template[2, 10] = -100.0
    template[0, 5] = 60.0
    (peak_fig,) = plot_unit_waveforms([7], {7: template}, channels="peak")
    (line,) = peak_fig.axes[0].get_lines()
    assert line.get_ydata().min() == -100.0
    assert line.get_label() == "Channel 2"
    # Spikes average to the template; the first spike alone is flat.
    spikes = np.stack([np.zeros_like(template), 2 * template])
    (spike_fig,) = plot_unit_waveforms([7], {7: spikes}, channels="peak")
    assert spike_fig.axes[0].get_lines()[0].get_ydata().min() == -100.0
    (all_fig,) = plot_unit_waveforms([7], {7: np.stack([template] * 3)}, channels="all")
    assert len(all_fig.axes[0].get_lines()) == 4
    assert min(ln.get_ydata().min() for ln in all_fig.axes[0].get_lines()) == -100.0
    # A NaN channel is ignored when choosing the peak.
    with_nan = template.copy()
    with_nan[1] = np.nan
    (nan_fig,) = plot_unit_waveforms([7], {7: with_nan}, channels="peak")
    assert nan_fig.axes[0].get_lines()[0].get_label() == "Channel 2"
    plt.close("all")

    with pytest.raises(KeyError, match=r"\[8\]"):
        plot_unit_waveforms([7, 8], {7: template}, channels="peak")
    with pytest.raises(ValueError, match="3-D"):
        plot_unit_waveforms([7], {7: np.stack([template] * 3)})
    with pytest.raises(ValueError, match="channels='peak'"):
        plot_unit_waveforms([7], {7: template})
    for mode in ("peak", "all"):
        for empty in (np.full((4, 30), np.nan), np.zeros((0, 30))):
            with pytest.raises(ValueError, match="unit 7"):
                plot_unit_waveforms([7], {7: empty}, channels=mode)
    with pytest.raises(ValueError, match="unit 7"):
        plot_unit_waveforms([7], {7: np.zeros((0, 4, 30))}, channels="peak")
    plt.close("all")


def test_plot_unit_waveforms_ignores_nan_samples_across_spikes_and_refuses_dead_channels():
    import pytest

    template = np.zeros((4, 30))
    template[2, 10] = -100.0
    template[0, 5] = 60.0
    # One NaN sample, at the peak, in one of three spikes: the other two still give -100.
    spikes = np.stack([template] * 3)
    spikes[0, 2, 10] = np.nan
    (fig,) = plot_unit_waveforms([7], {7: spikes}, channels="peak")
    line = fig.axes[0].get_lines()[0]
    assert line.get_label() == "Channel 2"
    assert line.get_ydata()[10] == -100.0
    assert np.isfinite(line.get_ydata()).all()
    (band,) = fig.axes[0].collections
    # The ±1 SD band covers the peak sample too; a NaN spread would leave a gap at x = 10.
    assert 10 in np.concatenate([p.vertices[:, 0] for p in band.get_paths()])
    # Every sample is finite in some spike, so the spike mean is finite everywhere.
    holes = np.ones((2, 4, 30))
    holes[0, :, ::2] = np.nan
    holes[1, :, 1::2] = np.nan
    (holes_fig,) = plot_unit_waveforms([7], {7: holes}, channels="all")
    assert all(np.isfinite(ln.get_ydata()).all() for ln in holes_fig.axes[0].get_lines())
    plt.close("all")

    # channels='all' draws every channel, so a channel with no finite sample is refused.
    dead = template.copy()
    dead[1] = np.nan
    with pytest.raises(ValueError, match=r"unit 7 has no finite sample on channel\(s\) \[1\]"):
        plot_unit_waveforms([7], {7: dead}, channels="all")
    plt.close("all")


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


def _stability_bars(stable):
    units = _units_df(n=len(stable)).drop(columns=["stable_plus"]).assign(is_stable=stable)
    fig = plot_unit_quality_distribution(units)
    ax = fig.axes[5]
    bars = [(t.get_text(), int(p.get_height())) for t, p in zip(ax.get_xticklabels(), ax.patches)]
    plt.close(fig)
    return bars


def test_stability_bars_are_labelled_by_their_own_class():
    # value_counts() orders by count, so a positional label swaps the classes whenever
    # stable units outnumber unstable ones, and names a lone class after the wrong one.
    assert _stability_bars([True] * 7 + [False] * 3) == [("Unstable", 3), ("Stable", 7)]
    assert _stability_bars([True] * 5) == [("Unstable", 0), ("Stable", 5)]


def test_a_unit_of_unknown_stability_is_in_neither_bar_and_counted_in_the_title():
    stable = pd.array([True, True, False, pd.NA, pd.NA], dtype="boolean")
    assert _stability_bars(stable) == [("Unstable", 1), ("Stable", 2)]
    units = _units_df(n=5).drop(columns=["stable_plus"]).assign(is_stable=stable)
    fig = plot_unit_quality_distribution(units)
    assert "2 unknown" in fig.axes[5].get_title()
    plt.close(fig)


def test_quality_distribution_skips_an_absent_metric_panel():
    units = _units_df().drop(columns=["waveform_duration"])
    fig = plot_unit_quality_distribution(units)
    assert "absent" in fig.axes[2].get_title()
    assert "n=20" in fig.axes[0].get_title()
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
