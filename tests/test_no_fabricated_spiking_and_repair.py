"""A measured zero, an extrapolated spike, a fabricated label, an artifact
used as its own repair reference, and a protection reported but never applied.

Each test fails when its repair is reverted.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest
from scipy.signal import hilbert

from jnwb.addressing import map_peak_channel_to_area
from jnwb.artifact_repair import interpolate_intervals, repair_lfp_trials
from jnwb.spiking import (
    classify_response_significance,
    compute_response_metrics,
    phase_locking_index,
)
from jnwb.viz import raster_psth


class TestNoFabricatedCertaintyAtOneTrial:
    """One trial has no dispersion to measure. `sem` returned exactly 0.0 and
    `response_zscore` returned 0.0, so `classify_response_significance` reported
    confidence 'none' with pvalue 1.0 -- where the two-trial case correctly reported
    'undefined' and NaN.
    """

    def test_raster_psth_sem_is_undefined_for_one_trial(self):
        spikes = np.array([0.01, 0.02, 0.03, 0.06, 0.07])
        _, mean, sem = raster_psth(spikes, [0.0], win_ms=(0, 100), bin_ms=50)
        assert np.all(np.isfinite(mean)), "the rate itself is measurable from one trial"
        assert np.all(np.isnan(sem)), "the dispersion is not"

    def test_raster_psth_sem_is_measured_for_two_trials(self):
        spikes = np.array([0.01, 0.02, 0.03, 1.01, 1.05, 1.07])
        _, _, sem = raster_psth(spikes, [0.0, 1.0], win_ms=(0, 100), bin_ms=50)
        assert np.all(np.isfinite(sem))

    def test_one_trial_and_two_trials_classify_the_same_way(self):
        spike_times = np.array([0.201, 0.205, 0.210, 0.215, 0.220])
        one = compute_response_metrics(
            spike_times,
            np.array([0.2]),
            baseline_window=(-0.2, 0.0),
            response_window=(0.0, 0.1),
        )
        two = compute_response_metrics(
            spike_times,
            np.array([0.2, 1.2]),
            baseline_window=(-0.2, 0.0),
            response_window=(0.0, 0.1),
        )
        assert np.isnan(one["response_zscore"])
        assert np.isnan(two["response_zscore"])
        assert (
            classify_response_significance(one)["confidence"]
            == classify_response_significance(two)["confidence"]
            == "undefined"
        )

    def test_zero_spikes_are_undefined_not_at_baseline(self):
        """No spikes is a measurable count but an unmeasurable z. The spike-count gate
        answers first ('low'), and the z itself must still be NaN rather than 0.0.
        """
        metrics = compute_response_metrics(
            np.array([]),
            np.array([0.2, 1.2]),
            baseline_window=(-0.2, 0.0),
            response_window=(0.0, 0.1),
        )
        assert metrics["response_count"] == 0
        assert np.isnan(metrics["response_zscore"])
        assert classify_response_significance(metrics)["is_significant"] is False


class TestPhaseLockingExcludesOutOfRangeSpikes:
    """`np.interp` clamps, so every spike outside the LFP window received the
    identical endpoint phase. Ten spikes 500 s past the end of a 10 s recording reported
    rayleigh_z 10.0 -- exactly n, the maximal resultant -- with p = 0.0.
    """

    @staticmethod
    def _phase(n=10000, fs=1000.0, f0=10.0):
        t = np.arange(n) / fs
        return t, np.angle(hilbert(np.sin(2 * np.pi * f0 * t)))

    def test_all_out_of_range_spikes_give_no_locking(self):
        t, phase = self._phase()
        with pytest.warns(RuntimeWarning, match="outside the LFP window"):
            res = phase_locking_index(np.linspace(500.0, 500.9, 10), phase, t)
        assert res["n_spikes"] == 0
        assert res["n_spikes_outside_lfp_window"] == 10
        assert np.isnan(res["rayleigh_pvalue"]) and np.isnan(res["rayleigh_z"])

    def test_out_of_range_spikes_do_not_inflate_the_resultant(self):
        """Half in, half out reported p = 0.0234 where the five in-range spikes alone
        give p = 0.8335.
        """
        t, phase = self._phase()
        in_range = np.linspace(1.0, 2.0, 5)
        mixed = np.concatenate([in_range, np.linspace(500.0, 500.4, 5)])
        with pytest.warns(RuntimeWarning, match="outside the LFP window"):
            mixed_res = phase_locking_index(mixed, phase, t)
        clean_res = phase_locking_index(in_range, phase, t)
        assert mixed_res["rayleigh_z"] == pytest.approx(clean_res["rayleigh_z"])
        assert mixed_res["rayleigh_pvalue"] == pytest.approx(clean_res["rayleigh_pvalue"])
        assert mixed_res["n_spikes"] == 5

    def test_fully_in_range_input_does_not_warn(self):
        t, phase = self._phase()
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            res = phase_locking_index(np.linspace(1.0, 9.0, 50), phase, t)
        assert res["n_spikes_outside_lfp_window"] == 0
        assert res["n_spikes"] == 50


class TestAreaLookupDoesNotFabricate:
    """`group_name` is the probe label, not an anatomical area."""

    def test_a_table_without_an_area_column_returns_no_area(self):
        electrodes = pd.DataFrame(
            {
                "group_name": ["probeA"] * 4,
                "x": [0.0] * 4,
                "y": [0.0] * 4,
                "z": [0.0, 1.0, 2.0, 3.0],
            }
        )
        assert map_peak_channel_to_area(0, electrodes) is None

    @pytest.mark.parametrize("column", ["location", "area"])
    def test_a_real_area_column_is_still_read(self, column):
        electrodes = pd.DataFrame(
            {
                "group_name": ["probeA"] * 4,
                column: ["V1", "V1", "V2", "V2"],
                "z": [0.0, 1.0, 2.0, 3.0],
            }
        )
        assert map_peak_channel_to_area(0, electrodes) == "V1"
        assert map_peak_channel_to_area(3, electrodes) == "V2"


class TestInterpolateIntervalsDoesNotPropagate:
    """`s = max(s, 1)` and `e = min(e, n - 1)` pulled the anchors *inside* the
    flagged region whenever the interval touched an edge, so the artifact became its own
    repair reference: [100, 0, 0, 100, 100, 100, 0, 0, 0, 100] over (0, 10) came back as
    ten copies of 100.
    """

    SIGNAL = np.array([100.0, 0.0, 0.0, 100.0, 100.0, 100.0, 0.0, 0.0, 0.0, 100.0])

    def test_a_whole_span_interval_is_refused_not_fabricated(self):
        seg = self.SIGNAL.reshape(-1, 1)
        with pytest.warns(RuntimeWarning, match="no clean sample"):
            out = interpolate_intervals(seg.copy(), [(0, 10)])
        np.testing.assert_array_equal(out.ravel(), self.SIGNAL)

    def test_a_left_edge_interval_holds_the_first_clean_sample(self):
        seg = self.SIGNAL.reshape(-1, 1)
        out = interpolate_intervals(seg.copy(), [(0, 3)]).ravel()
        assert np.all(out[0:3] == 100.0)
        np.testing.assert_array_equal(out[3:], self.SIGNAL[3:])

    def test_a_right_edge_interval_holds_the_last_clean_sample(self):
        seg = self.SIGNAL.reshape(-1, 1)
        out = interpolate_intervals(seg.copy(), [(6, 10)]).ravel()
        np.testing.assert_array_equal(out[:6], self.SIGNAL[:6])
        assert np.all(out[6:] == 100.0)

    def test_an_interior_interval_interpolates_between_its_neighbours(self):
        seg = np.array([0.0, 0.0, 99.0, 99.0, 4.0, 0.0]).reshape(-1, 1)
        out = interpolate_intervals(seg.copy(), [(2, 4)]).ravel()
        np.testing.assert_allclose(out, [0.0, 0.0, 4.0 / 3.0, 8.0 / 3.0, 4.0, 0.0])


class TestRepairLfpTrialsDoesNotAssertUnappliedProtection:
    """`exclude_window_ms` was dropped when `times_ms` was None, while the
    diagnostics echoed it back with reward_excluded_cells 0 and an empty warnings list.
    """

    @pytest.mark.parametrize("window_arg", ["exclude_window_ms", "reward_window_ms"])
    def test_a_window_without_a_time_axis_raises(self, window_arg):
        segments = np.random.default_rng(0).normal(size=(5, 1, 200))
        with pytest.raises(ValueError, match="without times_ms"):
            repair_lfp_trials(segments, times_ms=None, **{window_arg: (90.0, 110.0)})

    def test_both_arguments_together_still_work(self):
        segments = np.random.default_rng(0).normal(size=(5, 1, 200))
        segments[2, 0, 100] = 500.0
        times_ms = np.linspace(0.0, 200.0, 200)
        _, _, diagnostics = repair_lfp_trials(
            segments, times_ms=times_ms, exclude_window_ms=(90.0, 110.0)
        )
        assert diagnostics["exclude_window_ms"] == (90.0, 110.0)
        assert "reward_excluded_cells" in diagnostics

    def test_neither_argument_still_works(self):
        segments = np.random.default_rng(0).normal(size=(5, 1, 200))
        repaired, _, diagnostics = repair_lfp_trials(segments)
        assert repaired.shape == segments.shape
        assert diagnostics["exclude_window_ms"] is None
