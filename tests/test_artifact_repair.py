"""Unit tests for jnwb.artifact_repair -- generic trial-segmented LFP/TFR artifact
detection-and-substitution. These mirror the module's own `if __name__ == "__main__"`
synthetic self-tests, converted to pytest so they run under the standard suite.
"""
from __future__ import annotations

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


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        from jnwb import repair_lfp_trials as public_repair_lfp_trials
        from jnwb import repair_band_artifacts as public_repair_band_artifacts
        assert public_repair_lfp_trials is repair_lfp_trials
        assert public_repair_band_artifacts is repair_band_artifacts

    def test_listed_in_jnwb_all(self):
        import jnwb
        assert "repair_lfp_trials" in jnwb.__all__
        assert "repair_band_artifacts" in jnwb.__all__


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

    def test_below_min_trials_returns_input_unchanged(self):
        base = self._synthetic()[:3]
        repaired, frac, diag = repair_lfp_trials(base, min_trials=5)
        assert frac == 0.0
        assert np.array_equal(repaired, base)

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

    def test_below_min_trials_returns_input_unchanged(self):
        power, freqs, _ = self._synthetic()
        power = power[:3]
        repaired, frac = repair_band_artifacts(power, freqs)
        assert frac == {}
        assert np.array_equal(repaired, power)


class TestIntervalHelpers:
    def test_flagged_to_intervals_merges_close_runs(self):
        flagged = np.zeros(1000, dtype=bool)
        flagged[100:110] = True
        flagged[150:160] = True  # within default merge_gap_ms of the first run at fs=1000
        intervals = flagged_to_intervals(flagged, fs=1000.0, pad_ms=0.0, merge_gap_ms=100.0)
        assert len(intervals) == 1
        assert intervals[0][0] <= 100 and intervals[0][1] >= 160

    def test_interpolate_intervals_ramps_between_anchors(self):
        seg = np.zeros((20, 2))
        seg[0:5, :] = 1.0
        seg[15:, :] = 1.0
        seg[5:15, :] = 9.0  # will be interpolated away
        out = interpolate_intervals(seg, [(5, 15)])
        assert np.isclose(out[5, 0], seg[4, 0], atol=0.5)
        assert np.allclose(out[0:5], seg[0:5])
        assert np.allclose(out[15:], seg[15:])


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

    def test_importable_from_top_level(self):
        import jnwb
        assert jnwb.detect_band_outliers is detect_band_outliers
        assert jnwb.DETECTION_TAILS is DETECTION_TAILS


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

    def test_too_few_trials_returns_input_shape_unchanged(self):
        power, freqs = self._power(n_trials=3)
        avg = power.mean(axis=1)
        repaired, frac = repair_band_artifacts(avg, freqs)
        assert repaired.shape == avg.shape
        assert frac == {}
        np.testing.assert_allclose(repaired, avg)

    def test_sided_both_is_reachable_and_flags_at_least_as_much(self):
        power, freqs = self._power()
        _, frac_upper = repair_band_artifacts(power, freqs)
        _, frac_both = repair_band_artifacts(power, freqs, sided="both")
        for band in frac_upper:
            assert frac_both[band] >= frac_upper[band]
