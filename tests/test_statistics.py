"""Unit tests for jnwb.statistics's paired fire-probability testing primitives
(fires_in_window, fire_indicator, paired_fire_prob_test), promoted 2026-08-23 from
omission.jnwb_ext.unit_inclusion (99%-jnwb-sufficiency normalization). Plain spike-time/onset
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

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("fires_in_window", "fire_indicator", "paired_fire_prob_test",
                     "rate_in_window", "shuffle_pvalue_paired", "shuffle_pvalue_unpaired",
                     "detect_trial_cycles", "assign_subblock_quartiles", "shuffle_r2_ci"):
            assert name in jnwb.__all__

    def test_omission_unit_inclusion_delegates_to_jnwb(self):
        ui = pytest.importorskip("omission.jnwb_ext.unit_inclusion")
        assert ui.fires_in_window is fires_in_window
        assert ui.fire_indicator is fire_indicator
        assert ui.paired_fire_prob_test is paired_fire_prob_test

    def test_omission_unit_classification_delegates_to_jnwb(self):
        uc = pytest.importorskip("omission.jnwb_ext.unit_classification")
        assert uc._rate_in_window is rate_in_window
        assert uc._shuffle_pvalue_paired is shuffle_pvalue_paired
        assert uc._shuffle_pvalue_unpaired is shuffle_pvalue_unpaired

    def test_omission_identity_delegates_to_jnwb(self):
        oi = pytest.importorskip("omission.jnwb_ext.omission_identity")
        assert oi.detect_trial_cycles is detect_trial_cycles
        assert oi.assign_subblock_quartiles is assign_subblock_quartiles
        assert oi.shuffle_r2_ci is shuffle_r2_ci


class TestFiresInWindow:
    def test_spike_inside_window_returns_true(self):
        spikes = np.array([1.05])
        assert fires_in_window(spikes, onset_s=1.0, window_ms=(0.0, 100.0)) is True

    def test_no_spike_in_window_returns_false(self):
        spikes = np.array([5.0])
        assert fires_in_window(spikes, onset_s=1.0, window_ms=(0.0, 100.0)) is False

    def test_empty_or_reversed_window_returns_false(self):
        spikes = np.array([1.0])
        assert fires_in_window(spikes, onset_s=1.0, window_ms=(100.0, 0.0)) is False


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
        assert result["p_fire_pre_omission_baseline"] == pytest.approx(0.0)
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
        for key in ("p_fire_target", "p_fire_pre_omission_baseline", "risk_difference",
                    "risk_difference_ci_lo", "risk_difference_ci_hi", "odds_ratio",
                    "odds_ratio_ci_lo", "odds_ratio_ci_hi", "p_value_fire_shuffle", "n_trials"):
            assert key in result


class TestRateInWindow:
    def test_counts_spikes_in_window_as_rate(self):
        spikes = np.array([1.05, 1.10, 1.20])
        rate = rate_in_window(spikes, onset_s=1.0, window_ms=(0.0, 200.0))
        assert rate == pytest.approx(3.0 / 0.2)

    def test_empty_or_reversed_window_returns_zero(self):
        assert rate_in_window(np.array([1.0]), onset_s=1.0, window_ms=(100.0, 0.0)) == 0.0


class TestShufflePvaluePaired:
    def test_too_few_trials_returns_zero_and_p_one(self):
        obs, p = shuffle_pvalue_paired(np.array([1.0]), np.array([2.0]), n_shuffles=10, rng=np.random.default_rng(0))
        assert obs == 0.0
        assert p == 1.0

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
    def test_too_few_trials_returns_zero_and_p_one(self):
        obs, p = shuffle_pvalue_unpaired(np.array([1.0]), np.array([2.0]), n_shuffles=10, rng=np.random.default_rng(0))
        assert obs == 0.0
        assert p == 1.0

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
