"""Unit tests for jnwb.statistics's paired fire-probability testing primitives
(fires_in_window, fire_indicator, paired_fire_prob_test). Plain spike-time/onset
arrays and boolean pairs in; no session or condition semantics.
"""
from __future__ import annotations

import numpy as np
import pytest

import pandas as pd

from jnwb.statistics import (
    fires_in_window, fire_indicator, paired_fire_prob_test,
    rate_in_window, shuffle_pvalue_paired, shuffle_pvalue_unpaired,
    detect_trial_cycles, assign_subblock_quartiles, shuffle_r2_ci,
    cross_modal_comparison,
    clopper_pearson, mann_whitney_p_floor, exact_sign_flip, fdr_correct,
    StatisticalAnalysis,
)


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        assert jnwb.fires_in_window is fires_in_window
        assert jnwb.fire_indicator is fire_indicator
        assert jnwb.paired_fire_prob_test is paired_fire_prob_test
        assert jnwb.rate_in_window is rate_in_window
        assert jnwb.shuffle_pvalue_paired is shuffle_pvalue_paired
        assert jnwb.shuffle_pvalue_unpaired is shuffle_pvalue_unpaired
        assert jnwb.detect_trial_cycles is detect_trial_cycles
        assert jnwb.assign_subblock_quartiles is assign_subblock_quartiles
        assert jnwb.shuffle_r2_ci is shuffle_r2_ci
        assert jnwb.cross_modal_comparison is cross_modal_comparison
        assert jnwb.clopper_pearson is clopper_pearson
        assert jnwb.exact_sign_flip is exact_sign_flip
        assert jnwb.mann_whitney_p_floor is mann_whitney_p_floor
        assert jnwb.fdr_correct is fdr_correct

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("fires_in_window", "fire_indicator", "paired_fire_prob_test",
                     "rate_in_window", "shuffle_pvalue_paired", "shuffle_pvalue_unpaired",
                     "detect_trial_cycles", "assign_subblock_quartiles", "shuffle_r2_ci",
                     "cross_modal_comparison",
                     "clopper_pearson", "exact_sign_flip", "mann_whitney_p_floor", "fdr_correct"):
            assert name in jnwb.__all__

class TestFiresInWindow:
    def test_spike_inside_window_returns_true(self):
        spikes = np.array([1.05])
        assert fires_in_window(spikes, onset_s=1.0, window_ms=(0.0, 100.0)) is True

    def test_no_spike_in_window_returns_false(self):
        spikes = np.array([5.0])
        assert fires_in_window(spikes, onset_s=1.0, window_ms=(0.0, 100.0)) is False

    def test_reversed_window_is_rejected(self):
        """INTENTIONAL BREAK (0.2.4): returned False, "did not fire", for an empty window."""
        spikes = np.array([1.0])
        with pytest.raises(ValueError, match="non-positive width"):
            fires_in_window(spikes, onset_s=1.0, window_ms=(100.0, 0.0))

    def test_exact_boundary_conditions_right_open(self):
        # Window: [1.0, 1.1) in seconds
        spikes_at_start = np.array([1.0])
        spikes_at_end = np.array([1.1])
        # Start boundary is INCLUDED
        assert fires_in_window(spikes_at_start, onset_s=1.0, window_ms=(0.0, 100.0)) is True
        # End boundary is EXCLUDED
        assert fires_in_window(spikes_at_end, onset_s=1.0, window_ms=(0.0, 100.0)) is False

    def test_adjacent_contiguous_windows_no_double_count(self):
        # Two contiguous windows: [0, 100) and [100, 200) ms relative to onset 1.0
        # A spike at 1.100 sits exactly on the boundary between window 1 and window 2
        spikes = np.array([1.1])
        in_w1 = fires_in_window(spikes, onset_s=1.0, window_ms=(0.0, 100.0))
        in_w2 = fires_in_window(spikes, onset_s=1.0, window_ms=(100.0, 200.0))
        assert in_w1 is False, "Boundary spike at upper edge of window 1 must be excluded"
        assert in_w2 is True, "Boundary spike at lower edge of window 2 must be included"


class TestRateInWindow:
    def test_rate_computation(self):
        # 2 spikes in 100ms window = 20 Hz
        spikes = np.array([1.02, 1.08])
        rate = rate_in_window(spikes, onset_s=1.0, window_ms=(0.0, 100.0))
        assert rate == pytest.approx(20.0)

    def test_exact_boundary_conditions_right_open(self):
        # Spike at start boundary is included, spike at end boundary is excluded
        spikes = np.array([1.0, 1.1])  # one at 1.0, one at 1.1
        # Window [1.0, 1.1): only the spike at 1.0 is counted (1 spike in 0.1s = 10 Hz)
        rate = rate_in_window(spikes, onset_s=1.0, window_ms=(0.0, 100.0))
        assert rate == pytest.approx(10.0)

    def test_adjacent_contiguous_windows_conservation(self):
        # Spikes at 1.0, 1.1, 1.15
        spikes = np.array([1.0, 1.1, 1.15])
        rate_w1 = rate_in_window(spikes, onset_s=1.0, window_ms=(0.0, 100.0))  # [1.0, 1.1) -> 1 spike = 10 Hz
        rate_w2 = rate_in_window(spikes, onset_s=1.0, window_ms=(100.0, 200.0))  # [1.1, 1.2) -> 2 spikes = 20 Hz
        rate_total = rate_in_window(spikes, onset_s=1.0, window_ms=(0.0, 200.0))  # [1.0, 1.2) -> 3 spikes = 15 Hz
        assert rate_w1 == pytest.approx(10.0)
        assert rate_w2 == pytest.approx(20.0)
        assert rate_total == pytest.approx(15.0)

    def test_no_spikes_is_a_zero_rate(self):
        assert rate_in_window(np.array([]), onset_s=1.0, window_ms=(0.0, 100.0)) == 0.0

    def test_reversed_or_empty_window_is_rejected(self):
        """INTENTIONAL BREAK (0.2.4): returned 0.0 Hz, a silent unit, for an undefined rate."""
        spikes = np.array([1.05])
        with pytest.raises(ValueError, match="non-positive width"):
            rate_in_window(spikes, onset_s=1.0, window_ms=(100.0, 0.0))
        with pytest.raises(ValueError, match="non-positive width"):
            rate_in_window(spikes, onset_s=1.0, window_ms=(50.0, 50.0))


class TestFireIndicator:
    def test_one_entry_per_onset(self):
        spikes = np.array([1.05, 3.5])
        onsets = np.array([1.0, 2.0, 3.0])
        out = fire_indicator(spikes, onsets, window_ms=(0.0, 600.0))
        np.testing.assert_array_equal(out, [True, False, True])


class TestPairedFireProbTest:
    def test_too_few_trials_returns_nan_and_p_one(self):
        result = paired_fire_prob_test(
            np.array([True]), np.array([False]), n_shuffles=10, n_bootstrap=10,
            rng=np.random.default_rng(0),
        )
        assert np.isnan(result["risk_difference"])
        assert result["p_value_fire_shuffle"] == 1.0

    def test_all_target_none_null_has_max_risk_difference(self):
        rng = np.random.default_rng(0)
        fires_target = np.ones(20, dtype=bool)
        fires_null = np.zeros(20, dtype=bool)
        result = paired_fire_prob_test(fires_target, fires_null, n_shuffles=200, n_bootstrap=200, rng=rng)
        assert result["risk_difference"] == pytest.approx(1.0)
        assert result["p_fire_target"] == pytest.approx(1.0)
        assert result["p_fire_baseline"] == pytest.approx(0.0)
        assert result["p_value_fire_shuffle"] < 0.05

    def test_identical_arrays_give_zero_risk_difference(self):
        rng = np.random.default_rng(1)
        fires = rng.integers(0, 2, 30).astype(bool)
        result = paired_fire_prob_test(fires, fires, n_shuffles=100, n_bootstrap=100, rng=rng)
        assert result["risk_difference"] == pytest.approx(0.0)
        assert result["odds_ratio"] == pytest.approx(1.0)

    def test_returns_all_documented_keys(self):
        rng = np.random.default_rng(2)
        fires_target = rng.integers(0, 2, 15).astype(bool)
        fires_null = rng.integers(0, 2, 15).astype(bool)
        result = paired_fire_prob_test(fires_target, fires_null, n_shuffles=50, n_bootstrap=50, rng=rng)
        for key in ("p_fire_target", "p_fire_baseline", "risk_difference",
                    "risk_difference_ci_lo", "risk_difference_ci_hi", "odds_ratio",
                    "odds_ratio_ci_lo", "odds_ratio_ci_hi", "p_value_fire_shuffle", "n_trials"):
            assert key in result



class TestShufflePvaluePaired:
    def test_too_few_trials_is_undefined(self):
        """INTENTIONAL BREAK (0.2.4): returned (0.0, 1.0), which reads as a measured null result."""
        obs, p = shuffle_pvalue_paired(np.array([1.0]), np.array([2.0]), n_shuffles=10, rng=np.random.default_rng(0))
        assert np.isnan(obs) and np.isnan(p)

    def test_strong_paired_difference_is_significant_greater(self):
        rng = np.random.default_rng(0)
        a = np.full(20, 5.0)
        b = np.zeros(20)
        obs, p = shuffle_pvalue_paired(a, b, n_shuffles=500, rng=rng, alternative="greater")
        assert obs == pytest.approx(5.0)
        assert p < 0.05

    def test_identical_arrays_give_zero_observed_diff(self):
        rng = np.random.default_rng(1)
        a = rng.standard_normal(15)
        obs, p = shuffle_pvalue_paired(a, a, n_shuffles=100, rng=rng)
        assert obs == pytest.approx(0.0)


class TestShufflePvalueUnpaired:
    def test_too_few_trials_is_undefined(self):
        """INTENTIONAL BREAK (0.2.4): returned (0.0, 1.0), which reads as a measured null result."""
        obs, p = shuffle_pvalue_unpaired(np.array([1.0]), np.array([2.0]), n_shuffles=10, rng=np.random.default_rng(0))
        assert np.isnan(obs) and np.isnan(p)

    def test_strong_group_difference_is_significant(self):
        rng = np.random.default_rng(0)
        a = np.full(20, 5.0)
        b = np.zeros(20)
        obs, p = shuffle_pvalue_unpaired(a, b, n_shuffles=500, rng=rng, alternative="greater")
        assert obs == pytest.approx(5.0)
        assert p < 0.05


class TestDetectTrialCycles:
    def test_single_cluster_all_zero(self):
        df = pd.DataFrame({"start_time": [0.0, 1.0, 2.0, 3.0]})
        cycles = detect_trial_cycles(df)
        assert (cycles == 0).all()

    def test_large_gap_creates_new_cycle(self):
        df = pd.DataFrame({"start_time": [0.0, 1.0, 2.0, 1000.0, 1001.0, 1002.0]})
        cycles = detect_trial_cycles(df, gap_factor=5.0)
        assert list(cycles[:3]) == [0, 0, 0]
        assert list(cycles[3:]) == [1, 1, 1]

    def test_preserves_original_row_order(self):
        df = pd.DataFrame({"start_time": [2.0, 0.0, 1000.0, 1.0]})
        cycles = detect_trial_cycles(df, gap_factor=5.0)
        # rows 0,1,3 (times 2,0,1) are the early cluster; row 2 (time 1000) is the late one
        assert cycles[2] != cycles[0]
        assert cycles[0] == cycles[1] == cycles[3]


class TestAssignSubblockQuartiles:
    def test_splits_into_requested_number_of_buckets(self):
        df = pd.DataFrame({"start_time": np.arange(8.0)})
        q = assign_subblock_quartiles(df, n_quantiles=4)
        assert set(q.tolist()) == {0, 1, 2, 3}
        assert list(q) == sorted(q)  # start_time already sorted -> buckets in order

    def test_bucket_reflects_temporal_order_not_row_order(self):
        df = pd.DataFrame({"start_time": [3.0, 1.0, 2.0, 0.0]})
        q = assign_subblock_quartiles(df, n_quantiles=4)
        # row 3 (time 0) is earliest -> bucket 0; row 0 (time 3) is latest -> bucket 3
        assert q[3] == 0
        assert q[0] == 3


class TestShuffleR2Ci:
    def test_perfect_correlation_gives_r2_near_one(self):
        rng = np.random.default_rng(0)
        y = np.array([0] * 15 + [1] * 15, dtype=float)
        score = np.concatenate([rng.normal(0.1, 0.05, 15), rng.normal(0.9, 0.05, 15)])
        result = shuffle_r2_ci(y, score, n_shuffle=500, random_state=0)
        assert result["r2_observed"] > 0.7
        assert result["p_val"] < 0.05

    def test_returns_all_documented_keys(self):
        rng = np.random.default_rng(0)
        y = rng.integers(0, 2, 20).astype(float)
        score = rng.standard_normal(20)
        result = shuffle_r2_ci(y, score, n_shuffle=50, random_state=1)
        for key in ("r2_observed", "r2_null_ci_lo", "r2_null_ci_hi", "r2_null_mean", "p_val", "n_shuffle"):
            assert key in result

    def test_groups_uses_within_group_scheme(self):
        y = np.array([0, 1, 0, 1], dtype=float)
        score = np.array([0.1, 0.9, 0.2, 0.8])
        groups = np.array([0, 0, 1, 1])
        result = shuffle_r2_ci(y, score, groups=groups, n_shuffle=50, random_state=0)
        assert "r2_observed" in result


class TestCrossModalComparison:
    def test_none_inputs_return_error(self):
        result = cross_modal_comparison(None, np.zeros(5))
        assert "error" in result

    def test_too_few_samples_return_error(self):
        result = cross_modal_comparison(np.array([1.0, 2.0]), np.array([1.0, 2.0]))
        assert "error" in result

    def test_perfectly_correlated_1d_signals(self):
        tfr = np.arange(10, dtype=float)
        spikes = np.arange(10, dtype=float)
        result = cross_modal_comparison(tfr, spikes)
        assert result["n_samples"] == 10
        assert result["correlation"]["parametric"]["statistic"] == pytest.approx(1.0, abs=1e-6)

    def test_reduces_3d_tfr_and_2d_spikes_to_1d(self):
        rng = np.random.default_rng(0)
        tfr = rng.standard_normal((4, 20, 3))   # freq x time x trials
        spikes = rng.standard_normal((20, 3))   # time x trials
        result = cross_modal_comparison(tfr, spikes)
        assert result["n_samples"] == 20
        assert "correlation" in result

    def test_default_bin_ms_none_reports_zero_lag_explicitly(self):
        tfr = np.arange(10, dtype=float)
        spikes = np.arange(10, dtype=float)
        result = cross_modal_comparison(tfr, spikes)
        assert result["lag_ms"] == 0.0
        assert result["lfp_leads_spikes"] is False

    def test_lag_sweep_recovers_known_shift_lfp_lags_spikes(self):
        # spikes[i] == tfr[i + shift]: the pattern appears in spikes first, in tfr `shift`
        # samples later -- tfr/LFP lags spikes, so lag_ms is positive and lfp_leads_spikes is
        # False. Verified empirically before writing this assertion (not assumed from doc prose).
        rng = np.random.default_rng(1)
        base = rng.standard_normal(200)
        bin_ms = 10.0
        shift_samples = 5
        tfr = base[:-shift_samples]
        spikes = base[shift_samples:]
        result = cross_modal_comparison(tfr, spikes, lag_range_ms=(-200, 200), bin_ms=bin_ms)
        assert result["lag_ms"] == pytest.approx(shift_samples * bin_ms)
        assert result["lfp_leads_spikes"] is False
        assert result["correlation"]["parametric"]["statistic"] == pytest.approx(1.0, abs=1e-6)

    def test_lag_sweep_recovers_known_shift_lfp_leads_spikes(self):
        # tfr[i] == spikes[i + shift]: the pattern appears in tfr first -- tfr/LFP leads
        # spikes, so lag_ms is negative and lfp_leads_spikes is True.
        rng = np.random.default_rng(4)
        base = rng.standard_normal(200)
        bin_ms = 10.0
        shift_samples = 5
        tfr = base[shift_samples:]
        spikes = base[:-shift_samples]
        result = cross_modal_comparison(tfr, spikes, lag_range_ms=(-200, 200), bin_ms=bin_ms)
        assert result["lag_ms"] == pytest.approx(-shift_samples * bin_ms)
        assert result["lfp_leads_spikes"] is True
        assert result["correlation"]["parametric"]["statistic"] == pytest.approx(1.0, abs=1e-6)

    def test_lag_sweep_zero_lag_when_signals_aligned(self):
        rng = np.random.default_rng(2)
        base = rng.standard_normal(100)
        result = cross_modal_comparison(base, base, lag_range_ms=(-100, 100), bin_ms=10.0)
        assert result["lag_ms"] == 0.0
        assert result["correlation"]["parametric"]["statistic"] == pytest.approx(1.0, abs=1e-6)


class TestClopperPearson:
    def test_known_values(self):
        # 0 successes out of 10 at alpha=0.05
        # lower bound is 0, upper bound is 1 - (alpha/2)**(1/n) = 1 - 0.025**0.1
        lo, hi = clopper_pearson(0, 10, alpha=0.05)
        assert lo == 0.0
        expected_hi = 1.0 - (0.025) ** 0.1
        assert hi == pytest.approx(expected_hi, abs=1e-6)

        # 10 successes out of 10 at alpha=0.05
        lo, hi = clopper_pearson(10, 10, alpha=0.05)
        assert hi == 1.0
        expected_lo = 0.025 ** 0.1
        assert lo == pytest.approx(expected_lo, abs=1e-6)

        # 5 out of 10 at alpha=0.05 (symmetric around 0.5)
        lo, hi = clopper_pearson(5, 10, alpha=0.05)
        assert 0.0 < lo < 0.5 < hi < 1.0
        assert (0.5 - lo) == pytest.approx(hi - 0.5, abs=1e-6)

    def test_statistical_analysis_method_equivalence(self):
        res1 = clopper_pearson(3, 10, alpha=0.10)
        res2 = StatisticalAnalysis.clopper_pearson(3, 10, alpha=0.10)
        res3 = StatisticalAnalysis.clopper_pearson_ci(3, 10, alpha=0.10)
        assert res1 == res2 == res3

    def test_invalid_inputs_raise_value_error(self):
        with pytest.raises(ValueError, match="n must be >= 1"):
            clopper_pearson(0, 0)
        with pytest.raises(ValueError, match="n must be >= 1"):
            clopper_pearson(0, -5)
        with pytest.raises(ValueError, match="k must satisfy 0 <= k <= n"):
            clopper_pearson(-1, 10)
        with pytest.raises(ValueError, match="k must satisfy 0 <= k <= n"):
            clopper_pearson(11, 10)
        with pytest.raises(ValueError, match="alpha must be in"):
            clopper_pearson(5, 10, alpha=0.0)
        with pytest.raises(ValueError, match="alpha must be in"):
            clopper_pearson(5, 10, alpha=1.0)
        with pytest.raises(ValueError, match="alpha must be in"):
            clopper_pearson(5, 10, alpha=-0.05)
        with pytest.raises(ValueError, match="k and n must be exact integers"):
            clopper_pearson(2.5, 10)


class TestMannWhitneyPFloor:
    def test_known_floors(self):
        # n1=3, n2=3: comb(6, 3) = 20.
        # one-sided: 1/20 = 0.05. two-sided: 2/20 = 0.10
        assert mann_whitney_p_floor(3, 3, alternative="two-sided") == pytest.approx(0.10, abs=1e-12)
        assert mann_whitney_p_floor(3, 3, alternative="greater") == pytest.approx(0.05, abs=1e-12)
        assert mann_whitney_p_floor(3, 3, alternative="less") == pytest.approx(0.05, abs=1e-12)

        # n1=1, n2=1: comb(2, 1) = 2.
        # one-sided: 1/2 = 0.5. two-sided: min(1.0, 2/2) = 1.0
        assert mann_whitney_p_floor(1, 1, alternative="two-sided") == pytest.approx(1.0, abs=1e-12)
        assert mann_whitney_p_floor(1, 1, alternative="greater") == pytest.approx(0.5, abs=1e-12)

        # n1=4, n2=6: comb(10, 4) = 210.
        assert mann_whitney_p_floor(4, 6, alternative="two-sided") == pytest.approx(2.0 / 210.0, abs=1e-12)
        assert mann_whitney_p_floor(4, 6, alternative="greater") == pytest.approx(1.0 / 210.0, abs=1e-12)

    def test_symmetry_in_n1_n2(self):
        assert mann_whitney_p_floor(4, 7) == mann_whitney_p_floor(7, 4)

    def test_statistical_analysis_method_equivalence(self):
        assert StatisticalAnalysis.mann_whitney_p_floor(3, 5) == mann_whitney_p_floor(3, 5)

    def test_invalid_inputs_raise_value_error(self):
        with pytest.raises(ValueError, match="Sample sizes must be >= 1"):
            mann_whitney_p_floor(0, 5)
        with pytest.raises(ValueError, match="Sample sizes must be >= 1"):
            mann_whitney_p_floor(5, 0)
        with pytest.raises(ValueError, match="Sample sizes must be >= 1"):
            mann_whitney_p_floor(-1, 5)
        with pytest.raises(ValueError, match="alternative must be"):
            mann_whitney_p_floor(3, 3, alternative="invalid_tail")


class TestExactSignFlip:
    def test_tiny_direct_enumeration_n3(self):
        # diffs = [1.0, 2.0, 3.0]
        # 2^3 = 8 combinations:
        # sum of signs:
        # +++: 6 (mean 2)
        # ++-: 0 (mean 0)
        # +-+:-2 (mean -2/3)
        # +--:-4 (mean -4/3)
        # -++: 4 (mean 4/3)
        # -+-: 2 (mean 2/3)
        # --+: 0 (mean 0)
        # ---:-6 (mean -2)
        # obs_mean = 2.0.
        # greater (mean >= 2.0): only +++ -> 1/8 = 0.125
        # less (mean <= 2.0): all 8 -> 8/8 = 1.0
        # two-sided (|mean| >= 2.0): +++ and --- -> 2/8 = 0.25
        obs, p_two, p_floor = exact_sign_flip([1.0, 2.0, 3.0], alternative="two-sided")
        assert obs == pytest.approx(2.0, abs=1e-12)
        assert p_two == pytest.approx(0.25, abs=1e-12)
        assert p_floor == pytest.approx(0.25, abs=1e-12)

        obs, p_gt, p_floor_gt = exact_sign_flip([1.0, 2.0, 3.0], alternative="greater")
        assert p_gt == pytest.approx(0.125, abs=1e-12)
        assert p_floor_gt == pytest.approx(0.125, abs=1e-12)

        obs, p_lt, _ = exact_sign_flip([1.0, 2.0, 3.0], alternative="less")
        assert p_lt == pytest.approx(1.0, abs=1e-12)

    def test_direct_enumeration_with_zeros_and_ties(self):
        # diffs with zero and ties
        diffs = np.array([0.0, 2.0, -2.0, 4.0])
        # n = 4, 16 permutations
        obs, p_val, p_floor = exact_sign_flip(diffs, alternative="two-sided")
        assert obs == pytest.approx(1.0, abs=1e-12)
        assert p_floor == pytest.approx(2.0 / 16.0, abs=1e-12)

        # Independent enumeration check
        all_means = []
        for i in range(16):
            s = np.array([1.0 if (i >> b) & 1 else -1.0 for b in range(4)])
            all_means.append(np.mean(s * diffs))
        all_means = np.array(all_means)
        expected_p = float(np.mean(np.abs(all_means) >= abs(obs) - 1e-12))
        assert p_val == pytest.approx(expected_p, abs=1e-12)

    def test_exact_sign_flip_n1(self):
        obs, p_val, p_floor = exact_sign_flip([5.0], alternative="two-sided")
        assert obs == 5.0
        assert p_val == 1.0  # |+5| >= 5 and |-5| >= 5
        assert p_floor == 1.0

        obs, p_gt, _ = exact_sign_flip([5.0], alternative="greater")
        assert p_gt == 0.5  # only +5 >= 5

    def test_n_greater_than_20_monte_carlo(self):
        rng = np.random.default_rng(123)
        # N = 25 (> 20)
        diffs = rng.normal(loc=1.0, scale=0.2, size=25)  # all positive -> strongly significant
        obs, p_val, p_floor = exact_sign_flip(diffs, alternative="two-sided", n_mc=1000, rng=42)
        assert obs == pytest.approx(np.mean(diffs), abs=1e-12)
        # With all positive differences, null sign flips will rarely match obs
        assert p_val < 0.01
        assert p_floor == pytest.approx(1.0 / 1001.0, abs=1e-12)

    def test_statistical_analysis_method_equivalence(self):
        res1 = exact_sign_flip([1.0, 2.0, 3.0])
        res2 = StatisticalAnalysis.exact_sign_flip([1.0, 2.0, 3.0])
        assert res1 == res2

    def test_invalid_inputs_raise_value_error(self):
        with pytest.raises(ValueError, match="diffs cannot be empty"):
            exact_sign_flip([])
        with pytest.raises(ValueError, match="finite numerical values"):
            exact_sign_flip([1.0, np.nan, 2.0])
        with pytest.raises(ValueError, match="finite numerical values"):
            exact_sign_flip([1.0, np.inf, 2.0])
        with pytest.raises(ValueError, match="alternative must be"):
            exact_sign_flip([1.0, 2.0], alternative="invalid")


class TestFDRCorrect:
    def test_standalone_matches_statistical_analysis(self):
        p_vals = [0.001, 0.01, 0.04, 0.05, 0.2]
        q1 = fdr_correct(p_vals)
        q2 = StatisticalAnalysis.fdr_correct(p_vals)
        np.testing.assert_allclose(q1, q2)

    def test_empty_input(self):
        q = fdr_correct([])
        assert len(q) == 0

    def test_monotonicity_and_bounds(self):
        p_vals = np.array([0.005, 0.01, 0.02, 0.03, 0.05, 0.1, 0.8])
        q = fdr_correct(p_vals)
        assert np.all(q >= p_vals)
        assert np.all(q <= 1.0)

    # By hand, m = 3. BH: sorted p 0.001, 0.04, 0.2 scale by 3/1, 3/2, 3/3 to 0.003, 0.06, 0.2,
    # already monotone. BY multiplies BH by 1 + 1/2 + 1/3 = 11/6.
    UNSORTED_P = [0.04, 0.001, 0.2]

    @pytest.mark.parametrize("correct", [fdr_correct, StatisticalAnalysis.fdr_correct])
    def test_q_values_come_back_in_input_order(self, correct):
        np.testing.assert_allclose(correct(self.UNSORTED_P), [0.06, 0.003, 0.2], rtol=1e-12)

    @pytest.mark.parametrize("correct", [fdr_correct, StatisticalAnalysis.fdr_correct])
    def test_by_is_benjamini_yekutieli_and_not_bh(self, correct):
        by = correct(self.UNSORTED_P, method="by")
        np.testing.assert_allclose(by, [0.11, 0.0055, 0.2 * 11 / 6], rtol=1e-12)
        assert not np.allclose(by, correct(self.UNSORTED_P, method="bh"))


# ── 06-44: no key may assert a correction it did not apply ────────────────────
#
# These names are written out here on purpose. They are NOT read from
# `jnwb.statistics` -- not from the keys the exploratory wrappers strip, not from any
# tuple or map inside the module. A case set generated by the structure under test
# cannot reach a value that structure is missing, which is the failure recorded as P-50.
#
# Fragments rather than the two names 06-44 reported, so that a newly invented
# `pval_corrected`, `bonferroni_p` or `p_adjusted` is caught by the same assertion
# instead of needing this list extended.
_CORRECTION_NAME_FRAGMENTS = (
    "fdr", "corrected", "adjusted", "bonferroni", "holm", "sidak", "qval", "q_value",
)

# Keys that do assert a correction and are entitled to, because
# `test_confirmatory_q_values_are_the_bh_transform` proves the correction happened.
_ENTITLED_CORRECTION_KEYS = frozenset({"q_parametric", "q_nonparametric", "q_matrix"})


def _name_asserts_a_correction(key: str) -> bool:
    low = key.lower()
    return low.startswith("q_") or any(frag in low for frag in _CORRECTION_NAME_FRAGMENTS)


def _walk_keys(obj, prefix=""):
    """Every key in a result, including keys of nested dicts.

    A defect can hide one level down as ``result['parametric']['fdr_pval']``; a top-level
    scan would report the result clean.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield prefix + str(k), str(k)
            yield from _walk_keys(v, prefix + str(k) + ".")


class TestNoKeyAssertsAnUncorrectedCorrection:
    """06-44. A key whose name asserts a correction must not carry an uncorrected value.

    What would make these pass while the invariant is violated: running them only on the
    ``exploratory_*`` wrappers. Those wrappers strip keys on the way out, so a badly named
    key reintroduced in ``compare_groups`` would be popped before any assertion saw it.
    The raw producers are therefore asserted directly, and the wrappers separately.
    """

    RNG = np.random.default_rng(0)
    G1 = np.random.default_rng(11).normal(0.0, 1.0, 40)
    G2 = np.random.default_rng(12).normal(1.4, 1.0, 40)
    X = np.random.default_rng(13).normal(size=60)
    Y = 0.6 * X + np.random.default_rng(14).normal(size=60) * 0.8
    GROUPS = {
        "a": np.random.default_rng(15).normal(0.0, 1.0, 30),
        "b": np.random.default_rng(16).normal(1.0, 1.0, 30),
        "c": np.random.default_rng(17).normal(2.0, 1.0, 30),
    }
    HYP = "group 1 differs from group 2"

    def _raw_producers(self):
        return {
            "compare_groups": StatisticalAnalysis.compare_groups(self.G1, self.G2),
            "compare_groups(paired=True)": StatisticalAnalysis.compare_groups(
                self.G1, self.G2, paired=True
            ),
            "compare_multiple_groups": StatisticalAnalysis.compare_multiple_groups(self.GROUPS),
            "correlate": StatisticalAnalysis.correlate(self.X, self.Y),
        }

    def _wrappers(self):
        return {
            "exploratory_compare": StatisticalAnalysis.exploratory_compare(self.G1, self.G2),
            "exploratory_correlate": StatisticalAnalysis.exploratory_correlate(self.X, self.Y),
            "exploratory_multi": StatisticalAnalysis.exploratory_multi(self.GROUPS),
            "confirmatory_compare": StatisticalAnalysis.confirmatory_compare(
                self.G1, self.G2, hypothesis=self.HYP
            ),
        }

    def test_the_walker_actually_reaches_the_keys(self):
        """Guard against a vacuous pass: a walker returning nothing satisfies every
        assertion below without inspecting anything."""
        seen = [path for path, _ in _walk_keys(self._raw_producers()["compare_groups"])]
        assert len(seen) >= 20, f"walker reached only {len(seen)} keys: {seen}"
        assert "parametric.pval" in seen, seen
        assert "multiple_comparison.applied" in seen, seen

    def test_the_detector_would_recognise_the_reported_names(self):
        """Guard against a vacuous pass: a detector that recognises nothing also passes."""
        for name in ("fdr_pval_parametric", "fdr_pval_nonparametric", "pval_corrected",
                     "bonferroni_p", "p_adjusted", "q_parametric"):
            assert _name_asserts_a_correction(name), name
        for name in ("pval", "parametric", "non_parametric", "multiple_comparison",
                     "statistic", "significant_parametric", "mean_diff_ci"):
            assert not _name_asserts_a_correction(name), name

    @pytest.mark.parametrize("where", ["compare_groups", "compare_groups(paired=True)",
                                       "compare_multiple_groups", "correlate"])
    def test_raw_producers_return_no_correction_asserting_key(self, where):
        result = self._raw_producers()[where]
        offenders = [
            path for path, leaf in _walk_keys(result)
            if _name_asserts_a_correction(leaf) and leaf not in _ENTITLED_CORRECTION_KEYS
        ]
        assert not offenders, (
            f"{where} returns {offenders}: a key whose name asserts a correction, from a "
            f"function that applies none."
        )

    @pytest.mark.parametrize("where", ["exploratory_compare", "exploratory_correlate",
                                       "exploratory_multi", "confirmatory_compare"])
    def test_wrappers_return_no_unentitled_correction_asserting_key(self, where):
        result = self._wrappers()[where]
        offenders = [
            path for path, leaf in _walk_keys(result)
            if _name_asserts_a_correction(leaf) and leaf not in _ENTITLED_CORRECTION_KEYS
        ]
        assert not offenders, f"{where} returns {offenders}"

    def test_confirmatory_q_values_are_the_bh_transform(self):
        """The anti-mirror check: the two entitled keys must carry corrected values.

        Benjamini-Hochberg over a family of two is written out here rather than obtained
        from ``fdr_correct``, so this fails if ``confirmatory_compare`` is ever changed to
        mirror its raw p-values under the ``q_`` names -- which is the shape 06-44 reports.
        """
        res = StatisticalAnalysis.confirmatory_compare(self.G1, self.G2, hypothesis=self.HYP)
        p_param = res["parametric"]["pval"]
        p_nonparam = res["non_parametric"]["pval"]
        lo, hi = sorted((p_param, p_nonparam))
        # Without this guard the fixture could drift to one where BH leaves both p-values
        # untouched, and every assertion below would hold for a mirroring implementation.
        assert 2.0 * lo < hi, (
            f"fixture no longer discriminates: BH over ({lo}, {hi}) does not move the "
            f"smaller p, so a mirroring implementation would pass this test"
        )
        if p_param < p_nonparam:
            assert res["q_parametric"] == pytest.approx(2.0 * p_param)
            assert res["q_nonparametric"] == pytest.approx(p_nonparam)
            assert res["q_parametric"] != pytest.approx(p_param)
        else:
            assert res["q_nonparametric"] == pytest.approx(2.0 * p_nonparam)
            assert res["q_parametric"] == pytest.approx(p_param)
            assert res["q_nonparametric"] != pytest.approx(p_nonparam)

    def test_no_wrapper_silently_strips_a_badly_named_key(self):
        """The strip must not become a place defects go to hide.

        ``exploratory_compare`` used to pop ``fdr_pval_parametric`` and
        ``fdr_pval_nonparametric`` -- names nothing in the package assigns. Popping a
        wrongly named key is indistinguishable from never producing one, so the wrapper
        would have concealed a reintroduction in ``compare_groups`` from every assertion
        made on the wrapper's own return.
        """
        import inspect

        import jnwb.statistics as statistics_module

        src = inspect.getsource(statistics_module)
        assert "fdr_pval_parametric" not in src, (
            "jnwb/statistics.py still names a key no code path assigns; a reader takes "
            "the name for a returned value, which is what 06-44 was reported as"
        )
        assert "fdr_pval_nonparametric" not in src


# ── 06-45: the caller names the primary test ──────────────────────────────────

class TestCallerNamesThePrimaryTest:
    """06-45. How many tests were performed must be the caller's to declare.

    A pre-registered family budget is a statement about tests performed. Filtering a dual
    result on the way out would satisfy every key-presence assertion below while still
    performing two tests, so ``test_the_unselected_test_is_never_executed`` checks the
    call and not the return.
    """

    G1 = np.random.default_rng(21).normal(0.0, 1.0, 40)
    G2 = np.random.default_rng(22).normal(1.3, 1.0, 40)
    GROUPS = {
        "a": np.random.default_rng(23).normal(0.0, 1.0, 25),
        "b": np.random.default_rng(24).normal(1.0, 1.0, 25),
        "c": np.random.default_rng(25).normal(2.0, 1.0, 25),
    }

    def _call(self, func_name, test):
        if func_name == "compare_groups":
            return StatisticalAnalysis.compare_groups(self.G1, self.G2, test=test)
        if func_name == "compare_multiple_groups":
            return StatisticalAnalysis.compare_multiple_groups(self.GROUPS, test=test)
        if func_name == "exploratory_compare":
            return StatisticalAnalysis.exploratory_compare(self.G1, self.G2, test=test)
        if func_name == "exploratory_multi":
            return StatisticalAnalysis.exploratory_multi(self.GROUPS, test=test)
        raise AssertionError(func_name)

    def _call_with_no_test_argument(self, func_name):
        """Deliberately omits ``test=``. Passing ``test="both"`` here would exercise the
        argument and not the default, so a changed default would go unnoticed -- which is
        what this test did until mutant N2 walked through it."""
        if func_name == "compare_groups":
            return StatisticalAnalysis.compare_groups(self.G1, self.G2)
        if func_name == "compare_multiple_groups":
            return StatisticalAnalysis.compare_multiple_groups(self.GROUPS)
        if func_name == "exploratory_compare":
            return StatisticalAnalysis.exploratory_compare(self.G1, self.G2)
        if func_name == "exploratory_multi":
            return StatisticalAnalysis.exploratory_multi(self.GROUPS)
        raise AssertionError(func_name)

    ALL = ["compare_groups", "compare_multiple_groups",
           "exploratory_compare", "exploratory_multi"]

    @pytest.mark.parametrize("func_name", ALL)
    def test_the_parameter_exists_and_defaults_to_both(self, func_name):
        """The signature, not the docstring: 06-45 reports that no parameter selects."""
        import inspect

        target = getattr(StatisticalAnalysis, func_name)
        param = inspect.signature(target).parameters.get("test")
        assert param is not None, f"{func_name} still has no test= parameter"
        assert param.kind is param.KEYWORD_ONLY, (
            f"{func_name}: test must be keyword-only, or it captures a positional "
            f"argument callers already pass"
        )
        assert param.default == "both", (
            f"{func_name}: the default must stay 'both'; changing it is a behaviour "
            f"change that belongs in CHANGELOG.md"
        )

    @pytest.mark.parametrize("func_name", ALL)
    def test_default_is_unchanged_dual_reporting(self, func_name):
        """Called without ``test=``: the existing behaviour of every caller that predates
        this parameter."""
        result = self._call_with_no_test_argument(func_name)
        assert "parametric" in result
        assert "non_parametric" in result
        assert "significant_parametric" in result
        assert "significant_nonparametric" in result

    @pytest.mark.parametrize("func_name", ALL)
    def test_passing_both_explicitly_matches_passing_nothing(self, func_name):
        assert set(self._call_with_no_test_argument(func_name)) == set(self._call(func_name, "both"))

    @pytest.mark.parametrize("func_name", ALL)
    def test_naming_parametric_returns_none_of_the_other_test(self, func_name):
        """06-45's own discriminator: a call naming one test that returns the other's
        keys must fail."""
        result = self._call(func_name, "parametric")
        assert "parametric" in result
        assert "non_parametric" not in result
        assert "significant_parametric" in result
        assert "significant_nonparametric" not in result

    @pytest.mark.parametrize("func_name", ALL)
    def test_naming_nonparametric_returns_none_of_the_other_test(self, func_name):
        result = self._call(func_name, "nonparametric")
        assert "non_parametric" in result
        assert "parametric" not in result
        assert "significant_nonparametric" in result
        assert "significant_parametric" not in result

    @pytest.mark.parametrize("func_name", ["compare_groups", "compare_multiple_groups"])
    def test_the_result_records_how_many_tests_were_spent(self, func_name):
        assert self._call(func_name, "both")["multiple_comparison"]["n_tests"] == 2
        assert self._call(func_name, "parametric")["multiple_comparison"]["n_tests"] == 1
        assert self._call(func_name, "nonparametric")["multiple_comparison"]["n_tests"] == 1

    @pytest.mark.parametrize("func_name", ALL)
    @pytest.mark.parametrize("bad", ["", "para", "non_parametric", "BOTH", None, 1, True])
    def test_an_unrecognised_test_name_is_refused(self, func_name, bad):
        """No silent fallback to 'both'. An unrecognised name that quietly ran two tests
        would be the same substitution class as P-50."""
        with pytest.raises(ValueError, match="test must be one of"):
            self._call(func_name, bad)

    @pytest.mark.parametrize(
        "test,skipped_callable,partner",
        [
            ("parametric", "mannwhitneyu", "nonparametric"),
            ("nonparametric", "ttest_ind", "parametric"),
        ],
    )
    def test_the_unselected_test_is_never_executed(
        self, monkeypatch, test, skipped_callable, partner
    ):
        """The count of tests performed, not the count of keys returned.

        The sabotage is asserted live before it is relied on: with the estimator patched
        to raise, ``test='both'`` must raise. Without that half, a patch that silently
        failed to attach would make this test pass against an implementation that
        computes both tests and filters the result.
        """
        import jnwb.statistics as statistics_module

        def boom(*args, **kwargs):
            raise AssertionError(f"{skipped_callable} was called for test={test!r}")

        monkeypatch.setattr(statistics_module.stats, skipped_callable, boom)

        with pytest.raises(AssertionError, match=skipped_callable):
            StatisticalAnalysis.compare_groups(self.G1, self.G2, test="both")
        with pytest.raises(AssertionError, match=skipped_callable):
            StatisticalAnalysis.compare_groups(self.G1, self.G2, test=partner)

        result = StatisticalAnalysis.compare_groups(self.G1, self.G2, test=test)
        assert "parametric" in result or "non_parametric" in result

    def test_selecting_one_test_does_not_change_that_test_s_numbers(self):
        """Selection must not be a different estimator wearing the same name."""
        both = StatisticalAnalysis.compare_groups(self.G1, self.G2)
        only_p = StatisticalAnalysis.compare_groups(self.G1, self.G2, test="parametric")
        only_np = StatisticalAnalysis.compare_groups(self.G1, self.G2, test="nonparametric")
        assert only_p["parametric"] == both["parametric"]
        assert only_np["non_parametric"] == both["non_parametric"]

    def test_confirmatory_still_gets_both_p_values_for_its_family(self):
        """``confirmatory_compare`` corrects across the two dual p-values, so it must keep
        requesting both whatever this parameter now permits."""
        res = StatisticalAnalysis.confirmatory_compare(
            self.G1, self.G2, hypothesis="group 1 differs from group 2"
        )
        assert "parametric" in res and "non_parametric" in res
        assert "q_parametric" in res and "q_nonparametric" in res


# ── The caller names the correlation ─────────────────────────────────────────

class TestCallerNamesTheCorrelation:
    """`correlate` and `exploratory_correlate` take `method=`, so the number of correlations
    performed is the caller's to declare.

    What would pass while the invariant is violated: computing both and filtering the return.
    Every key assertion holds for that, so `test_the_unnamed_correlation_is_never_computed`
    checks the call, and it first proves its sabotage is live.
    """

    X = np.random.default_rng(31).normal(size=70)
    Y = np.exp(0.8 * X) + np.random.default_rng(32).normal(size=70) * 0.3
    FUNCS = ["correlate", "exploratory_correlate"]

    @staticmethod
    def _call(func_name, *args, **kwargs):
        return getattr(StatisticalAnalysis, func_name)(*args, **kwargs)

    @pytest.mark.parametrize("func_name", FUNCS)
    def test_the_parameter_is_keyword_only_and_defaults_to_both(self, func_name):
        import inspect

        param = inspect.signature(getattr(StatisticalAnalysis, func_name)).parameters.get("method")
        assert param is not None, f"{func_name} has no method= parameter"
        assert param.kind is param.KEYWORD_ONLY
        assert param.default == "both"

    @pytest.mark.parametrize("func_name", FUNCS)
    def test_both_is_the_scipy_pair_and_equals_passing_nothing(self, func_name):
        """Value-identical to the dual report: each statistic is scipy's own, and passing
        nothing is the same result as naming "both" (a changed default would split them)."""
        from scipy import stats as sps

        silent = self._call(func_name, self.X, self.Y)
        named = self._call(func_name, self.X, self.Y, method="both")
        assert silent == named
        r, p = sps.pearsonr(self.X, self.Y)
        rho, p_rho = sps.spearmanr(self.X, self.Y)
        assert silent["parametric"]["statistic"] == float(r)
        assert silent["parametric"]["pval"] == float(p)
        assert silent["non_parametric"]["statistic"] == float(rho)
        assert silent["non_parametric"]["pval"] == float(p_rho)
        # The exploratory wrapper strips the multiple_comparison block; the producer keeps it.
        if func_name == "correlate":
            assert silent["multiple_comparison"]["n_tests"] == 2

    @pytest.mark.parametrize("func_name", FUNCS)
    @pytest.mark.parametrize(
        "method, kept, dropped",
        [("pearson", "parametric", "non_parametric"),
         ("spearman", "non_parametric", "parametric")],
    )
    def test_naming_one_returns_only_its_statistic(self, func_name, method, kept, dropped):
        both = self._call(func_name, self.X, self.Y)
        one = self._call(func_name, self.X, self.Y, method=method)
        assert one[kept] == both[kept], "naming one must not change its numbers"
        assert dropped not in one
        flag = {"parametric": "significant_parametric",
                "non_parametric": "significant_nonparametric"}
        assert flag[kept] in one and flag[dropped] not in one
        if func_name == "correlate":
            assert one["multiple_comparison"]["n_tests"] == 1

    @pytest.mark.parametrize(
        "method, skipped, partner",
        [("pearson", "spearmanr", "spearman"), ("spearman", "pearsonr", "pearson")],
    )
    def test_the_unnamed_correlation_is_never_computed(self, monkeypatch, method, skipped, partner):
        import jnwb.statistics as statistics_module

        def boom(*args, **kwargs):
            raise AssertionError(f"{skipped} was called for method={method!r}")

        monkeypatch.setattr(statistics_module.stats, skipped, boom)
        with pytest.raises(AssertionError, match=skipped):
            StatisticalAnalysis.correlate(self.X, self.Y, method=partner)
        with pytest.raises(AssertionError, match=skipped):
            StatisticalAnalysis.correlate(self.X, self.Y)
        StatisticalAnalysis.correlate(self.X, self.Y, method=method)

    @pytest.mark.parametrize("func_name", FUNCS)
    @pytest.mark.parametrize("bad", ["", "Pearson", "kendall", "parametric", "BOTH", None, 1, True])
    def test_an_unknown_method_is_refused(self, func_name, bad):
        with pytest.raises(ValueError, match="method must be one of"):
            self._call(func_name, self.X, self.Y, method=bad)

    def test_an_unknown_method_is_refused_even_when_there_is_too_little_data(self):
        """The insufficient-sample return must not swallow a misspelt method."""
        with pytest.raises(ValueError, match="method must be one of"):
            StatisticalAnalysis.correlate([1.0, 2.0], [2.0, 1.0], method="kendall")


# ── 06-46: permutation_test is a flat shuffle and must say so ─────────────────

def _confounded_grouped_design():
    """Two sessions, zero true condition effect, conditions unbalanced across sessions.

    The marginal difference between the conditions is entirely session artifact, so a
    shuffle that ignores sessions must find it and one that respects them must not.
    """
    rng = np.random.default_rng(789)
    s0_a = rng.normal(0.0, 0.5, 12)
    s0_b = rng.normal(0.0, 0.5, 4)
    s1_a = rng.normal(6.0, 0.5, 4)
    s1_b = rng.normal(6.0, 0.5, 12)
    x = np.concatenate([s0_a, s1_a])
    y = np.concatenate([s0_b, s1_b])
    groups = np.concatenate([[0] * 12 + [1] * 4, [0] * 4 + [1] * 12])
    return x, y, groups


class TestPermutationTestIsFlatAndSaysSo:
    """06-46. A caller reading only this method's own documentation must not be able to
    apply it to grouped data believing it is correct."""

    def test_a_flat_shuffle_and_a_within_group_shuffle_disagree_materially(self):
        """The premise, measured. Without this the docstring assertion below would be
        guarding a claim nobody checked.
        """
        import jnwb

        x, y, groups = _confounded_grouped_design()

        flat = StatisticalAnalysis.permutation_test(
            x, y, n_permutations=2000, rng=np.random.default_rng(0)
        )

        values = np.concatenate([x, y])
        labels = np.array(["A"] * len(x) + ["B"] * len(y))
        observed = values[labels == "A"].mean() - values[labels == "B"].mean()
        wrng = np.random.default_rng(0)
        null = np.empty(2000)
        for i in range(2000):
            perm = jnwb.permute_labels(labels, groups=groups, scheme="within_group", rng=wrng)
            null[i] = values[perm == "A"].mean() - values[perm == "B"].mean()
        p_within = (1 + int(np.sum(np.abs(null) >= abs(observed)))) / 2001.0

        assert flat["observed_difference"] == pytest.approx(observed)
        # The true condition effect is zero, so the flat result is a false positive.
        assert flat["significant"], "flat shuffle should falsely find the session artifact"
        assert p_within > 0.05, "within-group shuffle should not reject a true null"
        # Not merely a different p: a differently shaped null.
        assert null.std() < 0.5 * flat["perm_std"], (
            f"null widths {null.std()} vs {flat['perm_std']} are not materially different"
        )

    def test_either_it_accepts_grouping_or_its_docstring_refuses_grouped_data(self):
        """Written as an implication so that adding grouping later does not make this
        test wrong -- it makes the first branch true instead.

        What would make a weaker version of this pass while the invariant is violated:
        checking for the word 'group'. The unrepaired docstring read "difference between
        two groups", so ``"group" in doc`` was already true and said nothing about nesting.
        The fragments below are therefore phrases that only a real refusal contains.
        """
        import inspect

        sig = inspect.signature(StatisticalAnalysis.permutation_test)
        if "groups" in sig.parameters or "scheme" in sig.parameters:
            pytest.skip("permutation_test now accepts grouping; the docstring rule is moot")

        doc = inspect.getdoc(StatisticalAnalysis.permutation_test) or ""
        low = doc.lower()
        assert "do not use it on grouped or nested data" in low, (
            "the docstring must refuse grouped data in words, not merely describe a shuffle"
        )
        assert "permute_labels" in doc, (
            "the docstring must name the tool that does handle grouping"
        )
        assert "within_group" in doc
        assert "nested" in low

    def test_the_refusal_is_reachable_from_the_object_a_caller_inspects(self):
        """``help()`` and ``?`` read ``__doc__`` on the underlying function."""
        import inspect

        doc = inspect.getdoc(StatisticalAnalysis.permutation_test)
        assert doc is not None and len(doc) > 200
        assert doc == inspect.getdoc(StatisticalAnalysis.__dict__["permutation_test"].__func__)


@pytest.mark.filterwarnings("ignore")
@pytest.mark.parametrize(
    "groups",
    [
        {"a": np.ones(5), "b": np.ones(5), "c": np.ones(5)},
        {"a": np.array([]), "b": np.arange(5.0), "c": np.arange(5.0) + 1},
    ],
    ids=["identical-constant", "one-empty"],
)
def test_a_multi_group_comparison_with_no_test_reports_nan(groups):
    """ANOVA and Kruskal-Wallis with no estimate are NaN, not statistic 0.0 and p 1.0."""
    res = StatisticalAnalysis.exploratory_multi(groups)
    for block in ("parametric", "non_parametric"):
        assert np.isnan(res[block]["statistic"]) and np.isnan(res[block]["pval"])
    assert np.isnan(res["parametric"]["effect_size"])
    assert np.isnan(res["parametric"]["df_between"]) and np.isnan(res["parametric"]["df_within"])
    assert res["group_sizes"] == [len(g) for g in groups.values()]
    assert res["significant_parametric"] is False and res["significant_nonparametric"] is False
    # A defined ANOVA keeps its integer degrees of freedom.
    defined = StatisticalAnalysis.exploratory_multi(
        {"a": np.arange(5.0), "b": np.arange(5.0) + 1, "c": np.arange(5.0) + 3}
    )["parametric"]
    assert (defined["df_between"], defined["df_within"]) == (2, 12)
    assert type(defined["df_between"]) is int and type(defined["df_within"]) is int


@pytest.mark.filterwarnings("ignore")
def test_one_observation_per_group_has_no_anova_but_an_eta_squared_of_one():
    """With one value per group every deviation lies between groups, so the ANOVA has no
    within-group variance to test against while eta_squared is 1.0; the changelog entry for the
    no-estimate case says so rather than calling eta_squared NaN."""
    import pathlib

    res = StatisticalAnalysis.compare_multiple_groups(
        {"a": np.array([1.0]), "b": np.array([2.0]), "c": np.array([4.0])}
    )["parametric"]
    assert np.isnan(res["statistic"]) and np.isnan(res["pval"])
    assert np.isnan(res["df_between"]) and np.isnan(res["df_within"])
    assert res["effect_size_name"] == "eta_squared" and res["effect_size"] == 1.0

    changelog = (pathlib.Path(__file__).resolve().parents[1] / "CHANGELOG.md").read_text(
        encoding="utf-8")
    entry = changelog.split("  - `compare_multiple_groups` and `exploratory_multi`", 1)[1]
    entry = entry.split("\n  - ", 1)[0]
    assert "`eta_squared` is 1.0" in " ".join(entry.split()), entry

