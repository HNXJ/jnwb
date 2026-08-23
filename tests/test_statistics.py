"""Unit tests for jnwb.statistics's paired fire-probability testing primitives
(fires_in_window, fire_indicator, paired_fire_prob_test), promoted 2026-08-23 from
omission.jnwb_ext.unit_inclusion (99%-jnwb-sufficiency normalization). Plain spike-time/onset
arrays and boolean pairs in; no session or condition semantics.
"""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.statistics import fires_in_window, fire_indicator, paired_fire_prob_test


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        assert jnwb.fires_in_window is fires_in_window
        assert jnwb.fire_indicator is fire_indicator
        assert jnwb.paired_fire_prob_test is paired_fire_prob_test

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("fires_in_window", "fire_indicator", "paired_fire_prob_test"):
            assert name in jnwb.__all__

    def test_omission_unit_inclusion_delegates_to_jnwb(self):
        ui = pytest.importorskip("omission.jnwb_ext.unit_inclusion")
        assert ui.fires_in_window is fires_in_window
        assert ui.fire_indicator is fire_indicator
        assert ui.paired_fire_prob_test is paired_fire_prob_test


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
