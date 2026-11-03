"""Trial-count arguments that the statistics helpers refuse instead of silently accepting.

Each bad value must raise a ValueError naming the argument and the value. The control drives a
valid value and pins its output: a refusal that fires on every input fails the control.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

from jnwb.statistics import (
    assign_subblock_quartiles,
    mann_whitney_p_floor,
    paired_fire_prob_test,
    shuffle_pvalue_paired,
    shuffle_pvalue_unpaired,
)

START_TIMES = [0.5, 0.1, 0.9, 0.3, 0.7]


def _df():
    return pd.DataFrame({"start_time": START_TIMES})


class TestAssignSubblockQuartilesRefusesBadCount:
    @pytest.mark.parametrize("n_quantiles", [0, -1])
    def test_fewer_than_one_bucket_is_refused(self, n_quantiles):
        with pytest.raises(ValueError, match=rf"n_quantiles must be an integer >= 1; got {n_quantiles}$"):
            assign_subblock_quartiles(_df(), n_quantiles=n_quantiles)

    @pytest.mark.parametrize("n_quantiles", [4.0, 4.5, True])
    def test_non_integer_is_refused(self, n_quantiles):
        with pytest.raises(ValueError, match=re.escape(f"n_quantiles must be an integer >= 1; got {n_quantiles!r}")):
            assign_subblock_quartiles(_df(), n_quantiles=n_quantiles)

    def test_valid_count_returns_pinned_buckets(self):
        # Temporal order is rows 1, 3, 0, 4, 2; with edges 0, 1, 2, 3, 5 the buckets are
        # row 1 -> 0, row 3 -> 1, row 0 -> 2, rows 4 and 2 -> 3.
        q = assign_subblock_quartiles(_df(), n_quantiles=4)
        assert set(q.tolist()) == {0, 1, 2, 3}, "fixture must fill all four buckets"
        np.testing.assert_array_equal(q, [2, 0, 3, 1, 3])


FIRES_TARGET = np.array([True, True, False, True, False, True, False, False])
FIRES_NULL = np.array([False, True, False, False, True, False, False, True])


class TestCountsBelowOneAndAlternativeAreRefused:
    @pytest.mark.parametrize("n_shuffles", [0, -1])
    def test_paired_fire_prob_test_refuses_n_shuffles_below_one(self, n_shuffles):
        assert FIRES_TARGET.sum() > 0 and FIRES_NULL.sum() > 0, "fixture must fire"
        with pytest.raises(ValueError, match=rf"paired_fire_prob_test: n_shuffles must be >= 1, got {n_shuffles}$"):
            paired_fire_prob_test(FIRES_TARGET, FIRES_NULL, n_shuffles=n_shuffles, n_bootstrap=20, rng=1)

    @pytest.mark.parametrize("n_bootstrap", [0, -1])
    def test_paired_fire_prob_test_refuses_n_bootstrap_below_one(self, n_bootstrap):
        with pytest.raises(ValueError, match=rf"paired_fire_prob_test: n_bootstrap must be >= 1, got {n_bootstrap}$"):
            paired_fire_prob_test(FIRES_TARGET, FIRES_NULL, n_shuffles=20, n_bootstrap=n_bootstrap, rng=1)

    def test_paired_fire_prob_test_valid_counts_still_run(self):
        out = paired_fire_prob_test(FIRES_TARGET, FIRES_NULL, n_shuffles=20, n_bootstrap=20, rng=1)
        assert 0.0 < out["p_value_fire_shuffle"] <= 1.0
        assert np.isfinite(out["risk_difference_ci_lo"]) and np.isfinite(out["risk_difference_ci_hi"])

    @pytest.mark.parametrize("bad", ["nonsense", "GREATERISH"])
    def test_shuffle_pvalue_paired_refuses_bad_alternative_at_one_pair(self, bad):
        with pytest.raises(ValueError, match=rf"shuffle_pvalue_paired: alternative must be .*got {re.escape(repr(bad))}"):
            shuffle_pvalue_paired(np.array([1.0]), np.array([0.0]), n_shuffles=10, rng=0, alternative=bad)

    @pytest.mark.parametrize("a, b", [([1.0], [2.0, 3.0]), ([1.0, 2.0], [3.0])])
    def test_shuffle_pvalue_unpaired_refuses_bad_alternative_below_two_values(self, a, b):
        with pytest.raises(ValueError, match=r"shuffle_pvalue_unpaired: alternative must be .*got 'nonsense'"):
            shuffle_pvalue_unpaired(np.array(a), np.array(b), n_shuffles=10, rng=0, alternative="nonsense")

    def test_fewer_than_two_values_with_valid_alternative_returns_nan(self):
        assert all(np.isnan(v) for v in shuffle_pvalue_paired(
            np.array([1.0]), np.array([0.0]), n_shuffles=10, rng=0, alternative="greater"))
        assert all(np.isnan(v) for v in shuffle_pvalue_unpaired(
            np.array([1.0]), np.array([2.0, 3.0]), n_shuffles=10, rng=0, alternative="greater"))

    @pytest.mark.parametrize("n_shuffles", [0, -1])
    def test_shuffle_pvalues_refuse_n_shuffles_below_one(self, n_shuffles):
        a, b = np.array([1.0, 2.0, 4.0]), np.array([0.0, 1.0, 2.0])
        with pytest.raises(ValueError, match=rf"shuffle_pvalue_paired: n_shuffles must be a positive integer, got {n_shuffles}$"):
            shuffle_pvalue_paired(a, b, n_shuffles=n_shuffles, rng=0)
        with pytest.raises(ValueError, match=rf"shuffle_pvalue_unpaired: n_shuffles must be a positive integer, got {n_shuffles}$"):
            shuffle_pvalue_unpaired(a, b, n_shuffles=n_shuffles, rng=0)


class TestMannWhitneyPFloorAtLargeSamples:
    def test_the_floor_below_the_float_range_is_a_float_without_overflow(self):
        # comb(1040, 520) is about 1e311, past the float maximum, so float(comb) overflowed.
        assert math.comb(1040, 520) > 10 ** 309, "fixture must pass the float range"
        floor = mann_whitney_p_floor(520, 520, alternative="greater")
        assert isinstance(floor, float)
        assert floor == float(Fraction(1, math.comb(1040, 520)))
        assert 0.0 < floor < 1e-300

    @pytest.mark.parametrize("alternative, factor", [("greater", 1), ("two-sided", 2)])
    def test_the_floor_inside_the_float_range_keeps_its_value(self, alternative, factor):
        expected = factor * float(Fraction(1, math.comb(1020, 510)))
        assert expected > 1e-306, "fixture must stay in the float range"
        np.testing.assert_allclose(mann_whitney_p_floor(510, 510, alternative=alternative),
                                   expected, rtol=1e-12)
