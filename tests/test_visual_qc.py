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


def test_plot_unit_waveforms_states_the_per_sample_spike_count():
    # Spikes dropping out at one sample shift the template's amplitude there: two spikes of
    # -100 and -50 average -75, but where the -100 spike is NaN the sample reads -50.
    spikes = np.zeros((2, 1, 30))
    spikes[0, 0, 9:12] = -100.0
    spikes[1, 0, 9:12] = -50.0
    spikes[0, 0, 10] = np.nan
    (fig,) = plot_unit_waveforms([7], {7: spikes}, channels="peak")
    trace = fig.axes[0].get_lines()[0].get_ydata()
    assert trace[[9, 10, 11]].tolist() == [-75.0, -50.0, -75.0]
    plt.close("all")
    doc = " ".join(plot_unit_waveforms.__doc__.split())
    assert "mean over the spikes that are not NaN at that sample" in doc
    assert "per-sample spike count varies" in doc


def test_plot_unit_waveforms_treats_infinite_samples_as_not_finite():
    import pytest

    for mode in ("peak", "all"):
        with pytest.raises(ValueError, match="unit 7 has an empty waveform or one with no finite"):
            plot_unit_waveforms([7], {7: np.full((4, 30), np.inf)}, channels=mode)
    template = np.zeros((4, 30))
    template[2, 10] = -100.0
    template[1] = np.inf
    with pytest.raises(ValueError, match=r"unit 7 has no finite sample on channel\(s\) \[1\]"):
        plot_unit_waveforms([7], {7: template}, channels="all")
    # An infinite sample on a channel with finite ones does not make it the peak.
    template[1] = 0.0
    template[3, 4] = np.inf
    (fig,) = plot_unit_waveforms([7], {7: template}, channels="peak")
    assert fig.axes[0].get_lines()[0].get_label() == "Channel 2"
    plt.close("all")


def test_plot_unit_waveforms_refuses_a_masked_entry():
    import pytest

    # Three spikes of -100 at sample 10 on one channel; the masked third spike is a +5000
    # outlier that np.asarray would average in, drawing (-100 - 100 + 5000) / 3 = 1600.
    spikes = np.zeros((3, 1, 30))
    spikes[:, 0, 10] = -100.0
    spikes[2, 0, 10] = 5000.0
    mask = np.zeros(spikes.shape, dtype=bool)
    mask[2] = True
    masked = np.ma.masked_array(spikes, mask=mask)
    for mode in ("peak", "all"):
        with pytest.raises(ValueError, match="unit 7 is a masked array with masked entries"):
            plot_unit_waveforms([7], {7: masked}, channels=mode)
    with pytest.raises(ValueError, match="unit 7 is a masked array"):
        plot_unit_waveforms([7], {7: np.ma.masked_array(np.zeros(30), mask=[True] + [False] * 29)})
    # The remedy reads the masked spike as missing; an unmasked masked array draws as before.
    (fig,) = plot_unit_waveforms([7], {7: masked.filled(np.nan)}, channels="peak")
    assert fig.axes[0].get_lines()[0].get_ydata()[10] == -100.0
    (fig,) = plot_unit_waveforms([7], {7: np.ma.masked_array(spikes[:2], mask=False)},
                                 channels="peak")
    assert fig.axes[0].get_lines()[0].get_ydata()[10] == -100.0
    plt.close("all")


def test_plot_peak_channel_is_the_channel_waveform_features_reports():
    from jnwb.unit_quality import waveform_features

    # Channel 0 has the larger absolute deflection (4 against 3); channel 1 the larger
    # peak-to-peak (3 - (-1.5) = 4.5 against 4). The two rules pick different channels.
    template = np.array([[-4.0, 0.0, 0.0, 0.0], [2.0, 3.0, -1.5, 0.0]])
    assert np.abs(template).max(axis=1).argmax() == 0, "fixture must split the two rules"
    reported = waveform_features(template, 30000.0)["peak_channel"]
    assert reported == 1
    (fig,) = plot_unit_waveforms([7], {7: template}, channels="peak")
    (line,) = fig.axes[0].get_lines()
    assert line.get_label() == f"Channel {reported}"
    np.testing.assert_array_equal(line.get_ydata(), template[reported])
    plt.close(fig)


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


def test_a_non_boolean_stability_flag_raises_instead_of_plotting_every_unit_stable():
    import pytest

    # astype(bool) read every non-empty string as True, so "no" drew as Stable.
    text = _units_df(n=3).drop(columns=["stable_plus"]).assign(is_stable=["yes", "no", "yes"])
    with pytest.raises(ValueError, match=r"'is_stable'.*non-boolean values.*'no'"):
        plot_unit_quality_distribution(text)
    text = _units_df(n=3).drop(columns=["is_stable"]).assign(stable_plus=["stable", "x", "y"])
    with pytest.raises(ValueError, match="'stable_plus'"):
        plot_unit_quality_distribution(text)
    # 0 and 1 are not booleans, so an integer flag is refused rather than read by its truth value.
    ints = _units_df(n=3).drop(columns=["stable_plus"]).assign(is_stable=[1, 0, 1])
    with pytest.raises(ValueError, match="'is_stable'"):
        plot_unit_quality_distribution(ints)
    plt.close("all")
    # Python booleans in an object column, with one unit missing, are real booleans and count.
    stable = pd.Series([True, None, False, True], dtype=object)
    assert _stability_bars(stable) == [("Unstable", 1), ("Stable", 2)]


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


def _comparison(snr_mean, good_rate):
    return pd.DataFrame(
        {
            "session_id": [f"s{i}" for i in range(len(snr_mean))],
            "snr_mean": snr_mean,
            "total_units": [10] * len(snr_mean),
            "snr_good_rate": good_rate,
        }
    )


def _guide(ax, label_part):
    (line,) = [ln for ln in ax.get_lines() if label_part in ln.get_label()]
    return line


def test_guide_lines_and_colour_cutoffs_come_from_arguments():
    from matplotlib.colors import to_rgba

    fig = plot_unit_quality_distribution(_units_df(), snr_threshold=2.5, quality_threshold=0.7)
    snr_ax, quality_ax, area_ax = fig.axes[1], fig.axes[3], fig.axes[4]
    assert _guide(snr_ax, "Threshold").get_xdata()[0] == 2.5
    assert "2.5" in _guide(snr_ax, "Threshold").get_label()
    assert _guide(quality_ax, "threshold").get_xdata()[0] == 0.7
    assert "0.7" in _guide(quality_ax, "threshold").get_label()
    assert _guide(area_ax, "threshold").get_ydata()[0] == 0.7
    plt.close(fig)

    # 1.5 passes the default 1.0 but not a cut-off of 2.0; 0.3 fails 0.5 but passes 0.2.
    # 60 % passes the default 50 but not 70; 22 % fails the default 25 but passes 20.
    fig = compare_session_quality(
        _comparison([1.5, 0.3], [0.6, 0.22]),
        snr_good=2.0, snr_fair=0.2, rate_good=70, rate_fair=20,
    )
    snr_ax, rate_ax = fig.axes[0], fig.axes[2]
    assert [p.get_facecolor()[:3] for p in snr_ax.patches] == [to_rgba("orange")[:3]] * 2
    assert [p.get_facecolor()[:3] for p in rate_ax.patches] == [to_rgba("orange")[:3]] * 2
    assert _guide(snr_ax, "2.0").get_ydata()[0] == 2.0
    assert _guide(rate_ax, "70").get_ydata()[0] == 70
    plt.close(fig)


def test_an_undefined_session_is_drawn_as_unknown_and_the_rate_axis_names_its_threshold():
    from matplotlib.colors import to_rgba

    fig = compare_session_quality(_comparison([2.0, np.nan], [np.nan, 0.6]), rate_threshold=3.0)
    snr_ax, rate_ax = fig.axes[0], fig.axes[2]
    red = to_rgba("red")[:3]
    assert snr_ax.patches[1].get_facecolor()[:3] != red
    assert rate_ax.patches[0].get_facecolor()[:3] != red
    assert [t.get_position()[0] for t in snr_ax.texts if t.get_text() == "unknown"] == [1]
    assert [t.get_position()[0] for t in rate_ax.texts if t.get_text() == "unknown"] == [0]
    assert rate_ax.get_ylabel() == "% Units with SNR > 3.0"
    plt.close(fig)


def test_duration_and_voltage_units_are_arguments():
    fig = plot_unit_quality_distribution(_units_df(), duration_unit="ms")
    assert fig.axes[2].get_xlabel() == "Waveform Duration (ms)"
    plt.close(fig)
    fig = plot_noise_vs_signal(_units_df(), duration_unit="ms")
    assert fig.axes[1].get_xlabel() == "Waveform Duration (ms)"
    plt.close(fig)
    (fig,) = plot_unit_waveforms([0], {0: np.sin(np.linspace(0, 6, 40))}, voltage_unit="mV")
    assert fig.axes[0].get_ylabel() == "Voltage (mV)"
    plt.close(fig)
