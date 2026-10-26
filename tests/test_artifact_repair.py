"""Unit tests for jnwb.artifact_repair -- generic trial-segmented LFP/TFR artifact
detection-and-substitution. These mirror the module's own `if __name__ == "__main__"`
synthetic self-tests, converted to pytest so they run under the standard suite.
"""
from __future__ import annotations

import inspect

import numpy as np
import pytest

from jnwb.artifact_repair import (
    repair_lfp_trials,
    detect_band_outliers,
    DETECTION_TAILS,
    repair_band_artifacts,
    flagged_to_intervals,
    interpolate_intervals,
    DEFAULT_BANDS,
)


class TestRepairLfpTrials:
    def _synthetic(self, seed=0):
        rng = np.random.default_rng(seed)
        n_trials, n_channels, n_times = 20, 8, 200
        t = np.arange(n_times)
        evoked = 5.0 * np.exp(-((t - 60) ** 2) / (2 * 15.0 ** 2))
        base = evoked[None, None, :] + rng.normal(0, 1.0, size=(n_trials, n_channels, n_times))
        return base

    def test_injected_cross_channel_spike_is_flagged_and_substituted(self):
        base = self._synthetic()
        base[7, :, 100] += 40.0  # cross-channel synchronous spike
        repaired, frac, diag = repair_lfp_trials(base, times_ms=None, reward_window_ms=None)
        assert diag["n_flagged_cells"] >= 1
        assert np.abs(repaired[7, :, 100] - base[7, :, 100]).max() > 1.0

    def test_unflagged_trial_is_untouched(self):
        base = self._synthetic()
        base[7, :, 100] += 40.0
        repaired, _, _ = repair_lfp_trials(base, times_ms=None, reward_window_ms=None)
        assert np.allclose(repaired[0], base[0])

    def test_reward_window_exclusion(self):
        base = self._synthetic()
        base[7, :, 100] += 40.0
        times_ms = np.linspace(0, 199, base.shape[-1])
        repaired, _, _ = repair_lfp_trials(
            base, times_ms=times_ms, reward_window_ms=(90.0, 110.0))
        assert np.allclose(repaired[7, :, 100], base[7, :, 100])

    def test_reward_window_none_disables_exclusion_by_default_arg(self):
        # reward_window_ms defaults to a non-None value; passing None explicitly must not error.
        base = self._synthetic()
        repaired, frac, diag = repair_lfp_trials(base, reward_window_ms=None)
        assert diag["reward_window_ms"] is None
        assert diag["reward_excluded_cells"] == 0

    def test_nonfinite_segments_raise_value_error_naming_the_count(self):
        base = self._synthetic()
        base[3, 2, 50] = np.nan
        base[4, 0, 7] = np.inf
        with pytest.raises(ValueError, match=r"contains 2 NaN or Inf"):
            repair_lfp_trials(base)

    def test_below_min_trials_raises_naming_the_minimum_and_the_count(self):
        base = self._synthetic()[:4]
        with pytest.raises(ValueError, match=r"at least 5 trials.*got 4"):
            repair_lfp_trials(base)

    def test_exactly_five_trials_still_run(self):
        rng = np.random.default_rng(2)
        seg = rng.standard_normal((5, 4, 100))
        seg[2, :, 50] += 40.0  # cross-channel synchronous spike
        repaired, _, diag = repair_lfp_trials(seg)
        assert diag["n_flagged_cells"] > 0
        assert np.abs(repaired[2, :, 50] - seg[2, :, 50]).max() > 1.0

    def test_rejects_non_3d_input(self):
        with pytest.raises(ValueError):
            repair_lfp_trials(np.zeros((5, 5)))


class TestRepairBandArtifacts:
    def _synthetic(self, seed=0):
        rng = np.random.default_rng(seed)
        freqs = np.arange(3, 201, 2, dtype=float)
        n_trials, n_channels, n_times = 20, 4, 50
        alpha_sel = (freqs >= 8) & (freqs < 14)
        evoked_t = 2.0 + 1.0 * np.exp(-((np.arange(n_times) - 25) ** 2) / (2 * 6.0 ** 2))
        power = 5.0 + rng.normal(0, 0.3, size=(n_trials, n_channels, freqs.size, n_times))
        power[:, :, alpha_sel, :] += evoked_t[None, None, None, :]
        return power, freqs, alpha_sel

    def test_band_confined_spike_is_flagged_and_substituted(self):
        power, freqs, alpha_sel = self._synthetic()
        power[3, :, alpha_sel, 30] += 30.0
        repaired, frac = repair_band_artifacts(power, freqs, band_ranges=DEFAULT_BANDS)
        assert frac.get("Alpha(8-14Hz)", 0.0) > 0
        assert np.abs(repaired[3, :, alpha_sel, 30] - power[3, :, alpha_sel, 30]).max() > 1.0

    def test_other_trials_and_bands_untouched(self):
        power, freqs, alpha_sel = self._synthetic()
        power[3, :, alpha_sel, 30] += 30.0
        repaired, _ = repair_band_artifacts(power, freqs, band_ranges=DEFAULT_BANDS)
        assert np.allclose(repaired[0], power[0])
        assert np.allclose(repaired[3, :, ~alpha_sel, :], power[3, :, ~alpha_sel, :])

    def test_below_min_trials_raises_naming_the_minimum_and_the_count(self):
        power, freqs, _ = self._synthetic()
        with pytest.raises(ValueError, match=r"at least 5 trials.*got 4"):
            repair_band_artifacts(power[:4], freqs)

    def test_exactly_five_trials_still_repair_a_planted_spike(self):
        power, freqs, alpha_sel = self._synthetic()
        power = power[:5]
        power[3, :, alpha_sel, 30] += 30.0
        repaired, frac = repair_band_artifacts(power, freqs, band_ranges=DEFAULT_BANDS)
        assert frac.get("Alpha(8-14Hz)", 0.0) > 0
        assert np.abs(repaired[3, :, alpha_sel, 30] - power[3, :, alpha_sel, 30]).max() > 1.0


class TestIntervalHelpers:
    def test_flagged_to_intervals_merges_close_runs(self):
        flagged = np.zeros(1000, dtype=bool)
        flagged[100:110] = True
        flagged[150:160] = True  # within default merge_gap_ms of the first run at fs=1000
        intervals = flagged_to_intervals(flagged, fs=1000.0, pad_ms=0.0, merge_gap_ms=100.0)
        assert len(intervals) == 1
        assert intervals[0][0] <= 100 and intervals[0][1] >= 160

    def test_empty_flagged_array_gives_the_same_empty_result_as_no_flags(self):
        empty = np.zeros(0, dtype=bool)
        assert empty.size == 0, "fixture must be empty"
        no_flags = flagged_to_intervals(np.zeros(5, dtype=bool), fs=1000.0)
        assert no_flags == []
        assert flagged_to_intervals(empty, fs=1000.0) == no_flags

    def test_interpolate_intervals_ramps_between_anchors(self):
        seg = np.zeros((20, 2))
        seg[0:5, :] = 1.0
        seg[15:, :] = 1.0
        seg[5:15, :] = 9.0  # will be interpolated away
        out = interpolate_intervals(seg, [(5, 15)])
        assert np.isclose(out[5, 0], seg[4, 0], atol=0.5)
        assert np.allclose(out[0:5], seg[0:5])
        assert np.allclose(out[15:], seg[15:])

    def test_one_sample_interval_at_left_edge_is_repaired(self):
        # A one-sample interval on the first sample used to be clipped to nothing and skipped.
        seg = np.array([[100.0], [1.0], [2.0], [3.0]])
        out = interpolate_intervals(seg, [(0, 1)])
        assert out[0, 0] == 1.0, out[:, 0]
        assert np.allclose(out[1:], seg[1:])

    def test_one_sample_interval_at_right_edge_is_repaired(self):
        # Same for the last sample: it is held to the last good sample.
        seg = np.array([[1.0], [2.0], [3.0], [100.0]])
        out = interpolate_intervals(seg, [(3, 4)])
        assert out[3, 0] == 3.0, out[:, 0]
        assert np.allclose(out[:3], seg[:3])


class TestDetectBandOutliers:
    """The detection rule, exposed so its tail is a stated argument rather than a buried detail."""

    @staticmethod
    def _trace(n_trials=20, n_times=30):
        rng = np.random.default_rng(11)
        shared = np.linspace(1.0, 2.0, n_times)          # common evoked shape
        return shared[None, :] + rng.normal(0, 0.01, (n_trials, n_times))

    def test_flags_nothing_on_clean_data(self):
        flagged, scale = detect_band_outliers(self._trace())
        assert not flagged.any()
        assert scale > 0.0

    def test_flags_injected_increase(self):
        trace = self._trace()
        trace[3, 10] += 5.0
        flagged, _ = detect_band_outliers(trace)
        assert flagged[3, 10]
        assert flagged.sum() == 1

    def test_upper_ignores_decrease_but_both_flags_it(self):
        """The drift that motivated exposing this: a two-sided test eats genuine decreases."""
        trace = self._trace()
        trace[4, 12] -= 5.0
        upper, _ = detect_band_outliers(trace, sided="upper")
        both, _ = detect_band_outliers(trace, sided="both")
        assert not upper[4, 12], "one-sided detector must not flag a power decrease"
        assert both[4, 12], "two-sided detector does flag it -- hence the warning"

    def test_zero_scale_on_degenerate_input(self):
        flagged, scale = detect_band_outliers(np.ones((10, 5)))
        assert scale == 0.0
        assert not flagged.any()

    def test_invalid_sided_rejected(self):
        with pytest.raises(ValueError, match="sided must be one of"):
            detect_band_outliers(self._trace(), sided="lower")

    def test_tails_constant_is_documented_pair(self):
        assert DETECTION_TAILS == ("upper", "both")


class TestRepairBandArtifactsShapeContract:
    """3-D (channel-averaged) input is accepted so nobody has to fork the rule to use it."""

    @staticmethod
    def _power(n_trials=20, n_ch=6, n_freqs=40, n_times=25):
        rng = np.random.default_rng(5)
        freqs = np.linspace(2.0, 100.0, n_freqs)
        power = np.abs(rng.normal(10.0, 1.0, (n_trials, n_ch, n_freqs, n_times)))
        if n_trials > 7:                               # cross-channel spike, one trial/time
            power[7, :, :, 12] += 80.0
        return power, freqs

    def test_3d_input_returns_3d_and_agrees_with_4d_flagging(self):
        power, freqs = self._power()
        rep4, frac4 = repair_band_artifacts(power, freqs)
        rep3, frac3 = repair_band_artifacts(power.mean(axis=1), freqs)
        assert rep4.shape == power.shape
        assert rep3.shape == power.mean(axis=1).shape
        # Detection runs on the channel-averaged trace in both paths, so flagging must match.
        assert frac3 == frac4

    def test_3d_path_actually_repairs(self):
        power, freqs = self._power()
        avg = power.mean(axis=1)
        repaired, frac = repair_band_artifacts(avg, freqs)
        assert not np.allclose(repaired, avg)
        assert any(v > 0 for v in frac.values())

    def test_bad_ndim_rejected(self):
        with pytest.raises(ValueError, match="power must be"):
            repair_band_artifacts(np.ones((5, 5)), np.linspace(2, 100, 5))

    def test_too_few_trials_raises_for_3d_input_too(self):
        power, freqs = self._power(n_trials=3)
        avg = power.mean(axis=1)
        with pytest.raises(ValueError, match=r"at least 5 trials.*got 3"):
            repair_band_artifacts(avg, freqs)

    def test_sided_both_is_reachable_and_flags_at_least_as_much(self):
        power, freqs = self._power()
        _, frac_upper = repair_band_artifacts(power, freqs)
        _, frac_both = repair_band_artifacts(power, freqs, sided="both")
        assert frac_upper, "the default bands must report a flagged fraction for each band"
        for band in frac_upper:
            assert frac_both[band] >= frac_upper[band]


class TestRepairDoesNotSubstituteAwayTheEvokedResponse:
    """The detector is cross-channel synchrony, and an evoked response is synchronous
    across channels by construction, so it was flagged exactly like an artifact. The
    substitution then replaced each trial's own deflection with the cross-trial median of
    the same deflection: the trial average survived, so nothing looked wrong, while the
    single-trial variability many analyses rest on was destroyed. Measured with the guard
    disabled, the correlation between the true single-trial amplitude and the repaired peak
    fell from 0.9996 to 0.4607 and the across-trial SD at the peak fell from 8.27 to 3.64,
    while the mean moved only from 29.33 to 28.59.
    """

    PEAK = 150

    @staticmethod
    def _evoked(seed=0, n_trials=40, n_channels=16, n_times=500):
        rng = np.random.default_rng(seed)
        t = np.arange(n_times)
        amplitude = rng.normal(1.0, 0.35, size=n_trials)
        evoked = np.exp(-0.5 * ((t - 150) / 8.0) ** 2) * 30.0
        seg = rng.standard_normal((n_trials, n_channels, n_times))
        seg += amplitude[:, None, None] * evoked[None, None, :]
        return seg, amplitude, (t - 100).astype(float)

    def test_single_trial_amplitude_survives_the_repair(self):
        seg, amplitude, times = self._evoked()
        repaired, _, diag = repair_lfp_trials(seg, times_ms=times)
        r = np.corrcoef(amplitude, repaired[:, :, self.PEAK].mean(axis=1))[0, 1]
        assert r > 0.95, f"single-trial amplitude correlation fell to {r:.4f}"
        assert diag["n_time_locked_samples_protected"] > 0
        assert any("time_locked" in w for w in diag["warnings"])

    def test_disabling_the_guard_reproduces_the_damage(self):
        """Pins that the guard is what protects the response, not some other change."""
        seg, amplitude, times = self._evoked()
        repaired, _, diag = repair_lfp_trials(seg, times_ms=times, max_trial_fraction=None)
        r = np.corrcoef(amplitude, repaired[:, :, self.PEAK].mean(axis=1))[0, 1]
        assert r < 0.7
        assert diag["n_time_locked_samples_protected"] == 0

    def test_a_rare_artifact_is_still_repaired(self):
        """The guard must not buy the response back by refusing to repair anything."""
        rng = np.random.default_rng(1)
        seg = rng.standard_normal((40, 16, 500))
        for trial in (5, 11, 29):
            seg[trial, :, 300:305] += 80.0
        repaired, _, diag = repair_lfp_trials(seg)
        assert np.abs(seg[:, :, 302]).max() > 70.0
        assert np.abs(repaired[:, :, 302]).max() < 10.0
        assert diag["n_flagged_cells"] > 0
        assert diag["n_time_locked_samples_protected"] == 0

    def test_the_per_sample_flagged_fraction_is_reported(self):
        seg, _, times = self._evoked()
        _, _, diag = repair_lfp_trials(seg, times_ms=times)
        assert diag["max_fraction_trials_flagged_at_a_sample"] > 0.5
        assert diag["max_trial_fraction"] == 0.5


def test_the_per_trial_robust_z_is_the_floored_owner_call():
    assert "_floored_robust_z(segments, med_t)" in inspect.getsource(repair_lfp_trials)


def test_the_band_robust_z_is_the_pooled_owner_call():
    assert "_pooled_robust_z(resid, scale)" in inspect.getsource(detect_band_outliers)


def test_repair_lfp_trials_keeps_its_robust_z_on_a_fixed_input():
    """A constant channel has a zero MAD: the 1e-9 floor keeps its z at 0, not NaN."""
    segments = np.random.default_rng(21).normal(size=(12, 3, 200))
    segments[2, 1, 50:60] += 40.0
    segments[:, 2, :] = 0.0
    times = np.arange(200) * 1.0
    _, _, diag = repair_lfp_trials(segments, times_ms=times)
    assert diag["n_flagged_cells"] == 0
    np.testing.assert_allclose(diag["synchrony_z_max"], 2.9797563375532956, rtol=1e-12)
    repaired, frac, diag = repair_lfp_trials(segments, times_ms=times, z_thresh=2.0)
    assert diag["n_flagged_cells"] == 10
    np.testing.assert_allclose(frac, 0.004166666666666667, rtol=1e-12)
    np.testing.assert_allclose(repaired.sum(), 377.38092678317275, rtol=1e-12)
    np.testing.assert_allclose(np.abs(repaired).max(), 41.63158249260414, rtol=1e-12)


def test_detect_band_outliers_keeps_its_pooled_scale_on_a_fixed_input():
    band = np.random.default_rng(5).normal(size=(10, 60))
    band[3, 20:24] += 9.0
    flagged, scale = detect_band_outliers(band)
    assert int(flagged.sum()) == 4
    np.testing.assert_allclose(scale, 0.5836889404957837, rtol=1e-12)
    flat, flat_scale = detect_band_outliers(np.full((6, 9), 2.5))
    assert not flat.any() and flat_scale == 0.0
