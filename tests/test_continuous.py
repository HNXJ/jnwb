"""Tests for continuous time-series operations and epoch extraction."""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

import jnwb
from jnwb.continuous import epoch_continuous


class TestEpochContinuous:
    def test_public_export(self):
        assert hasattr(jnwb, "epoch_continuous")
        assert "epoch_continuous" in jnwb.__all__
        assert jnwb.epoch_continuous is epoch_continuous

    def test_impulse_alignment(self):
        fs = 1000.0
        n_samples = 3000
        data = np.zeros(n_samples, dtype=np.float64)
        impulse_sample = 1500
        impulse_time = impulse_sample / fs  # 1.5 s
        data[impulse_sample] = 42.0

        win_s = (-0.2, 0.3)
        epochs, t_axis = epoch_continuous(
            data,
            onsets=[impulse_time],
            win_s=win_s,
            fs=fs,
        )

        assert epochs.shape == (1, int(0.5 * fs))
        assert t_axis.shape == (int(0.5 * fs),)
        np.testing.assert_allclose(t_axis[0], -0.2)
        np.testing.assert_allclose(t_axis[-1], 0.3 - 1.0 / fs)

        # Impulse must be exactly at t = 0.0 s
        zero_idx = int(np.round(0.2 * fs))
        assert t_axis[zero_idx] == 0.0
        assert epochs[0, zero_idx] == 42.0
        assert np.sum(epochs[0] != 0.0) == 1

    def test_2d_multichannel(self):
        fs = 500.0
        n_samples = 2000
        n_channels = 8
        data = np.arange(n_samples * n_channels, dtype=np.float64).reshape(n_samples, n_channels)

        onsets = [0.5, 1.0, 1.5]
        win_s = (-0.1, 0.2)
        epochs, t_axis = epoch_continuous(
            data,
            onsets,
            win_s=win_s,
            fs=fs,
        )

        n_win = int(np.round(0.3 * fs))
        assert epochs.shape == (3, n_win, n_channels)
        assert t_axis.shape == (n_win,)

        # Verify exact slice for first onset (0.5 s -> sample 250)
        expected_first = data[250 - int(0.1 * fs) : 250 + int(0.2 * fs), :]
        np.testing.assert_allclose(epochs[0], expected_first)

    def test_boundary_policy_nan(self):
        fs = 1000.0
        data = np.ones(500, dtype=np.float64)
        # Onset at sample 20 (0.02 s), window (-0.05, 0.05) -> window extends from sample -30 to 70
        epochs, t_axis = epoch_continuous(
            data,
            onsets=[0.02],
            win_s=(-0.05, 0.05),
            fs=fs,
            boundary_policy="nan",
        )
        assert epochs.shape == (1, 100)
        # Pre-boundary samples (-30 to 0 -> 30 samples) should be NaN
        assert np.all(np.isnan(epochs[0, :30]))
        # Post-boundary samples (0 to 70 -> 70 samples) should be 1.0
        assert np.all(epochs[0, 30:] == 1.0)

    def test_boundary_policy_error(self):
        fs = 1000.0
        data = np.ones(500, dtype=np.float64)
        with pytest.raises(ValueError, match="extends outside data"):
            epoch_continuous(
                data,
                onsets=[0.02],
                win_s=(-0.05, 0.05),
                fs=fs,
                boundary_policy="error",
            )

    def test_boundary_policy_drop(self):
        fs = 1000.0
        data = np.ones(2000, dtype=np.float64)
        # Onsets: 0.02 (out of bounds start -30), 1.0 (valid 950:1050), 1.98 (out of bounds end 2030)
        onsets = [0.02, 1.0, 1.98]
        epochs, t_axis = epoch_continuous(
            data,
            onsets=onsets,
            win_s=(-0.05, 0.05),
            fs=fs,
            boundary_policy="drop",
        )
        assert epochs.shape == (1, 100)
        assert np.all(epochs[0] == 1.0)

        # Test with return_indices=True
        epochs_ret, t_axis_ret, retained_idx = epoch_continuous(
            data,
            onsets=onsets,
            win_s=(-0.05, 0.05),
            fs=fs,
            boundary_policy="drop",
            return_indices=True,
        )
        assert epochs_ret.shape == (1, 100)
        assert np.array_equal(retained_idx, [1])
        np.testing.assert_allclose(epochs_ret, epochs)

    def test_rounding_and_negative_windows(self):
        fs = 1000.0
        # Check negative window: baseline before event (-0.3 to -0.1 s -> -300 to -100 samples)
        data = np.arange(1000, dtype=np.float64)
        epochs, t_axis = epoch_continuous(
            data,
            onsets=[0.5],
            win_s=(-0.3, -0.1),
            fs=fs,
        )
        assert epochs.shape == (1, 200)
        assert t_axis.shape == (200,)
        np.testing.assert_allclose(t_axis[0], -0.3)
        np.testing.assert_allclose(t_axis[-1], -0.1 - 1.0 / fs)
        # Center is at sample 500. Window [-300, -100) relative to center -> [200, 400)
        np.testing.assert_array_equal(epochs[0], data[200:400])

        # Test IEEE 754 round-half-to-even (banker's rounding) contract
        # fs = 10.0 -> 0.25 * 10 = 2.5 -> rounds to 2 (even)
        #            0.35 * 10 = 3.5 -> rounds to 4 (even)
        #            0.15 * 10 = 1.5 -> rounds to 2 (even)
        fs_sub = 10.0
        data_sub = np.arange(100, dtype=np.float64)
        epochs_sub, _ = epoch_continuous(
            data_sub,
            onsets=[0.15, 0.25, 0.35],
            win_s=(0.0, 0.2),  # 2 samples
            fs=fs_sub,
        )
        # Center indices:
        # 0.15 * 10 = 1.5 -> round to even: 2 -> slice [2:4] -> [2.0, 3.0]
        # 0.25 * 10 = 2.5 -> round to even: 2 -> slice [2:4] -> [2.0, 3.0]
        # 0.35 * 10 = 3.5 -> round to even: 4 -> slice [4:6] -> [4.0, 5.0]
        np.testing.assert_array_equal(epochs_sub[0], [2.0, 3.0])
        np.testing.assert_array_equal(epochs_sub[1], [2.0, 3.0])
        np.testing.assert_array_equal(epochs_sub[2], [4.0, 5.0])

    def test_window_edges_are_containment_bounds(self):
        """(-0.25, 0.25) s at 10 Hz holds the five samples at offsets -0.2 to 0.2 s."""
        fs = 10.0
        data = np.arange(100, dtype=np.float64)
        # Precondition: both edges are exact halves, where round-half-to-even and containment differ.
        assert -0.25 * fs == -2.5 and 0.25 * fs == 2.5
        epochs, t_axis = epoch_continuous(data, onsets=[5.0], win_s=(-0.25, 0.25), fs=fs)
        assert epochs.shape == (1, 5)
        np.testing.assert_allclose(t_axis, [-0.2, -0.1, 0.0, 0.1, 0.2])
        np.testing.assert_array_equal(epochs[0], data[48:53])

    def test_a_product_just_above_an_integer_counts_as_that_integer(self):
        fs = 100.0
        # Precondition: 0.07 * 100 is 7 plus an ulp, so a plain ceiling would give 8 samples.
        assert 0.07 * fs > 7.0
        data = np.arange(1000, dtype=np.float64)
        epochs, _ = epoch_continuous(data, onsets=[5.0], win_s=(0.0, 0.07), fs=fs)
        assert epochs.shape == (1, 7)
        np.testing.assert_array_equal(epochs[0], data[500:507])

    def test_a_window_of_three_tenths_of_a_second_at_1000_hz_has_300_samples(self):
        fs = 1000.0
        data = np.arange(1000, dtype=np.float64)
        epochs, _ = epoch_continuous(data, onsets=[0.5], win_s=(0.0, 0.3), fs=fs)
        assert epochs.shape == (1, 300)
        np.testing.assert_array_equal(epochs[0], data[500:800])

    def test_a_symmetric_window_of_whole_samples_keeps_its_length(self):
        fs = 1000.0
        # Precondition: both edges are whole samples (-100 and 100), so nothing rounds.
        assert -0.1 * fs == -100.0 and 0.1 * fs == 100.0
        data = np.arange(1000, dtype=np.float64)
        epochs, _ = epoch_continuous(data, onsets=[0.5], win_s=(-0.1, 0.1), fs=fs)
        assert epochs.shape == (1, 200)
        np.testing.assert_array_equal(epochs[0], data[400:600])

    def test_empty_onsets(self):
        fs = 1000.0
        data_1d = np.ones(500)
        epochs_1d, t_axis = epoch_continuous(data_1d, [], win_s=(-0.1, 0.2), fs=fs)
        assert epochs_1d.shape == (0, 300)
        assert t_axis.shape == (300,)

        # With return_indices=True
        epochs_ret, t_axis_ret, ret_idx = epoch_continuous(
            data_1d, [], win_s=(-0.1, 0.2), fs=fs, return_indices=True
        )
        assert epochs_ret.shape == (0, 300)
        assert ret_idx.shape == (0,)

        data_2d = np.ones((500, 4))
        epochs_2d, _ = epoch_continuous(data_2d, [], win_s=(-0.1, 0.2), fs=fs)
        assert epochs_2d.shape == (0, 300, 4)

    def test_sample_onset_units(self):
        fs = 1000.0
        data = np.arange(1000, dtype=np.float64)
        epochs, _ = epoch_continuous(
            data,
            onsets=[500],
            win_s=(-0.01, 0.01),
            fs=fs,
            onset_unit="samples",
        )
        assert epochs.shape == (1, 20)
        np.testing.assert_allclose(epochs[0], data[490:510])

    def test_invalid_arguments_raise(self):
        data = np.zeros(100)
        with pytest.raises(ValueError, match="must be positive"):
            epoch_continuous(data, [0.0], win_s=(-0.1, 0.1), fs=0.0)
        with pytest.raises(ValueError, match="strictly less"):
            epoch_continuous(data, [0.0], win_s=(0.2, 0.1), fs=1000.0)
        with pytest.raises(ValueError, match="must be a 2-tuple"):
            epoch_continuous(data, [0.0], win_s=(-0.1,), fs=1000.0)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="must be 1D or 2D"):
            epoch_continuous(np.zeros((10, 10, 10)), [0.0], win_s=(-0.1, 0.1), fs=1000.0)
        with pytest.raises(ValueError, match="Unknown boundary_policy"):
            epoch_continuous(data, [0.0], win_s=(-0.1, 0.1), fs=1000.0, boundary_policy="invalid")  # type: ignore[arg-type]
        # Validated before the empty-onsets return, so a bad unit is refused with no onsets too.
        with pytest.raises(ValueError, match="Unknown onset_unit"):
            epoch_continuous(data, [], win_s=(-0.1, 0.1), fs=1000.0, onset_unit="ms")
        with pytest.raises(ValueError, match="Unknown boundary_policy"):
            epoch_continuous(data, [], win_s=(-0.1, 0.1), fs=1000.0, boundary_policy="invalid")  # type: ignore[arg-type]

    def test_start_s_puts_sample_zero_at_the_series_start(self):
        """A series whose sample 0 is at 2 s: an onset at 3 s is one second in, sample 100."""
        data = np.arange(1000.0)
        epochs, _ = epoch_continuous(data, onsets=[3.0], win_s=(0.0, 0.1), fs=100.0, start_s=2.0)
        np.testing.assert_array_equal(epochs[0], data[100:110])

    def test_the_default_start_keeps_the_current_mapping(self):
        data = np.arange(1000.0)
        for kwargs in ({}, {"start_s": 0.0}):
            epochs, _ = epoch_continuous(data, onsets=[3.0], win_s=(0.0, 0.1), fs=100.0, **kwargs)
            np.testing.assert_array_equal(epochs[0], data[300:310])
        epochs, _ = epoch_continuous(
            data, onsets=[300.5], win_s=(0.0, 0.1), fs=100.0, onset_unit="samples"
        )
        np.testing.assert_array_equal(epochs[0], data[300:310])

    def test_a_non_finite_start_is_refused(self):
        data = np.zeros(100)
        for start in (np.nan, np.inf, -np.inf):
            with pytest.raises(ValueError, match="start_s must be finite"):
                epoch_continuous(data, [0.5], win_s=(0.0, 0.1), fs=100.0, start_s=start)
        with pytest.raises(ValueError, match="start_s must be finite"):
            epoch_continuous(data, [], win_s=(0.0, 0.1), fs=100.0, start_s=np.nan)

    def test_a_start_with_onsets_in_samples_is_refused(self):
        """Onsets in samples index data directly; a start time would move them."""
        data = np.arange(1000.0)
        with pytest.raises(ValueError, match="already index data"):
            epoch_continuous(data, [300], win_s=(0.0, 0.1), fs=100.0, onset_unit="samples",
                             start_s=2.0)


class TestTickClock:
    def test_public_export(self):
        assert "TickClock" in jnwb.__all__
        assert "derive_tick_clock" in jnwb.__all__
        assert hasattr(jnwb, "TickClock") and hasattr(jnwb, "derive_tick_clock")

    def test_the_clock_is_frozen_and_maps_ticks_to_seconds(self):
        clock = jnwb.TickClock(tick_step=24.0, tick_rate=30000.0, first_tick=1000.0, offset_s=2.5)
        assert clock.fs_hz == pytest.approx(1250.0, rel=1e-12)
        np.testing.assert_allclose(clock.seconds([1000.0, 31000.0]), [2.5, 3.5], rtol=1e-12, atol=0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            clock.offset_s = 0.0

    def test_a_synthetic_clock_recovers_its_tick_rate_and_offset(self):
        tick_step, tick_rate, first_tick, offset_s = 24.0, 30000.0, 1000.0, 2.5
        ticks = first_tick + tick_step * np.arange(4000)
        spike_span_s = (ticks[-1] - ticks[0]) / tick_rate
        spikes = offset_s + spike_span_s * np.linspace(0.0, 1.0, 500)
        assert np.unique(np.diff(ticks)).tolist() == [tick_step], "fixture must step uniformly"
        assert spikes.max() - spikes.min() == pytest.approx(spike_span_s, rel=1e-12)
        segments = [ticks[:1000], ticks[1000:2500], ticks[2500:]]
        clock = jnwb.derive_tick_clock(segments, spikes)
        np.testing.assert_allclose(
            [clock.tick_step, clock.tick_rate, clock.first_tick, clock.offset_s],
            [tick_step, tick_rate, first_tick, offset_s], rtol=1e-12, atol=0)
        assert clock.fs_hz == pytest.approx(tick_rate / tick_step, rel=1e-12)

    def test_spike_times_may_be_one_array_or_several(self):
        ticks = 24.0 * np.arange(2000)
        spikes = np.linspace(0.5, 0.5 + (ticks[-1] - ticks[0]) / 30000.0, 300)
        segments = [ticks[:700], ticks[700:]]
        one = jnwb.derive_tick_clock(segments, spikes)
        several = jnwb.derive_tick_clock(segments, [spikes[:120], spikes[120:]])
        assert one.tick_rate == pytest.approx(30000.0, rel=1e-12)
        assert several == one

    def test_the_excerpt_clock_matches_the_pinned_values(self):
        pytest.importorskip("pynwb", reason="reading the excerpt needs pynwb")
        root = Path(__file__).resolve().parents[1]
        excerpt = root / "examples" / "data" / "dandi000253_excerpt.nwb"
        script = root / "examples" / "tutorials" / "09_open_data.py"
        spec = importlib.util.spec_from_file_location("open_data_tutorial_clock", script)
        tutorial = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = tutorial
        try:
            spec.loader.exec_module(tutorial)
            data = tutorial.read_excerpt(excerpt)
        finally:
            sys.modules.pop(spec.name, None)
        assert data["trains"], "the excerpt holds no spike trains, so the clock is underdetermined"
        segments = [data["lfp"][name]["ticks"] for name in ("start", "window", "end")]
        assert all(seg.size > 1 for seg in segments), "every LFP segment needs samples"
        clock = jnwb.derive_tick_clock(segments, data["trains"])
        # Pinned from the tutorial's derive_clock at commit 37775ce4, on the committed excerpt.
        np.testing.assert_allclose(
            [clock.tick_step, clock.tick_rate, clock.first_tick, clock.offset_s],
            [24.0, 29999.967941591047, 0.0, 3.569168801852582], rtol=1e-12, atol=0)

    def test_no_segments_is_refused(self):
        with pytest.raises(ValueError, match="derive_tick_clock.*tick_segments"):
            jnwb.derive_tick_clock([], [1.0, 2.0])

    def test_an_empty_segment_is_refused(self):
        with pytest.raises(ValueError, match="derive_tick_clock.*empty"):
            jnwb.derive_tick_clock([np.arange(3.0) * 24.0, np.array([])], [1.0, 2.0])

    def test_a_segment_that_is_not_one_dimensional_is_refused(self):
        with pytest.raises(ValueError, match="derive_tick_clock.*1-D"):
            jnwb.derive_tick_clock([np.zeros((3, 2))], [1.0, 2.0])

    def test_a_step_that_differs_within_a_segment_is_refused(self):
        with pytest.raises(ValueError, match="derive_tick_clock.*uniform") as refused:
            jnwb.derive_tick_clock([np.array([0.0, 24.0, 48.0, 50.0])], [1.0, 2.0])
        assert "2.0" in str(refused.value) and "24.0" in str(refused.value), str(refused.value)

    def test_a_step_that_differs_across_segments_is_refused(self):
        first = np.arange(5) * 24.0
        second = 200.0 + np.arange(5) * 12.0
        with pytest.raises(ValueError, match="derive_tick_clock.*uniform") as refused:
            jnwb.derive_tick_clock([first, second], [1.0, 2.0])
        assert "[12.0, 24.0]" in str(refused.value), str(refused.value)

    def test_segments_with_no_step_are_refused(self):
        with pytest.raises(ValueError, match="derive_tick_clock.*uniform"):
            jnwb.derive_tick_clock([np.array([0.0]), np.array([24.0])], [1.0, 2.0])

    def test_decreasing_ticks_are_refused(self):
        ticks = np.array([72.0, 48.0, 24.0, 0.0])
        assert np.unique(np.diff(ticks)).tolist() == [-24.0], "fixture must step uniformly down"
        with pytest.raises(ValueError, match="derive_tick_clock: the tick step is -24.0"):
            jnwb.derive_tick_clock([ticks], [1.0, 2.0])

    def test_non_finite_ticks_are_refused(self):
        ticks = np.array([0.0, 24.0, np.nan, 72.0])
        with pytest.raises(ValueError, match="derive_tick_clock.*non-finite"):
            jnwb.derive_tick_clock([ticks], [1.0, 2.0])

    def test_fewer_than_two_spikes_are_refused(self):
        ticks = [24.0 * np.arange(10)]
        with pytest.raises(ValueError, match="derive_tick_clock.*two"):
            jnwb.derive_tick_clock(ticks, [1.0])
        with pytest.raises(ValueError, match="derive_tick_clock.*two"):
            jnwb.derive_tick_clock(ticks, [])

    def test_non_finite_spikes_are_refused(self):
        with pytest.raises(ValueError, match="derive_tick_clock.*non-finite"):
            jnwb.derive_tick_clock([24.0 * np.arange(10)], [1.0, np.inf])

    def test_a_zero_spike_span_is_refused(self):
        with pytest.raises(ValueError, match="derive_tick_clock.*zero span"):
            jnwb.derive_tick_clock([24.0 * np.arange(10)], [1.0, 1.0])
