"""05-21 and 05-24: input that does not fit the contract must be refused or reported,
never quietly shortened, re-paired, or answered with a measured zero.

Each test fails when its repair is reverted.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import jnwb
from jnwb.connectivity import as_trials, bin_spikes
from jnwb.statistics import (
    cluster_permutation_test,
    paired_fire_prob_test,
    shuffle_pvalue_paired,
)


class TestNoSilentTruncationOrMispairing:
    """05-21: four entry points shortened or dropped input where a sibling refuses.

    The shared contract: the caller either gets what they asked for, or is told -- through
    `warnings`, which `-W error` and `pytest.warns` can see, not only through `logging`,
    which they cannot.
    """

    def test_ragged_trials_warn_when_they_are_truncated(self):
        segments = [np.arange(500.0), np.arange(480.0), np.arange(500.0)]
        with pytest.warns(RuntimeWarning, match="ragged trial lengths"):
            out = as_trials(segments, allow_ragged=True)
        assert out.shape == (3, 480)

    def test_ragged_truncation_is_visible_under_error_filters(self):
        """The defect was not the truncation but its invisibility: `log.warning` cannot be
        promoted to an error, so a caller running under `-W error` still got it silently.
        """
        segments = [np.arange(500.0), np.arange(480.0)]
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            with pytest.raises(RuntimeWarning):
                as_trials(segments, allow_ragged=True)

    def test_equal_length_trials_do_not_warn(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            out = as_trials([np.arange(500.0), np.arange(500.0)], allow_ragged=True)
        assert out.shape == (2, 500)

    def test_paired_fire_prob_test_refuses_unequal_lengths(self):
        """Truncating to the shorter of the two pairs trial i of one condition with trial
        i of the other. Lengths 8 and 4 returned risk_difference 0.5 over four such
        pairings; `shuffle_pvalue_paired` already refused exactly this.
        """
        target = np.array([1, 0, 1, 1, 0, 1, 1, 0], dtype=bool)
        null = np.array([0, 0, 1, 0], dtype=bool)
        with pytest.raises(ValueError, match="paired .equal length"):
            paired_fire_prob_test(
                target, null, n_shuffles=50, n_bootstrap=50, rng=np.random.default_rng(0)
            )
        with pytest.raises(ValueError, match="paired .equal length"):
            shuffle_pvalue_paired(
                target, null, n_shuffles=50, rng=np.random.default_rng(0)
            )

    def test_paired_fire_prob_test_still_runs_on_equal_lengths(self):
        target = np.array([1, 0, 1, 1, 0, 1, 1, 0], dtype=bool)
        null = np.array([0, 0, 1, 0, 0, 1, 0, 0], dtype=bool)
        res = paired_fire_prob_test(
            target, null, n_shuffles=50, n_bootstrap=50, rng=np.random.default_rng(0)
        )
        assert res["n_trials"] == 8
        assert np.isfinite(res["risk_difference"])

    @pytest.mark.parametrize("nan_policy", ["raise", "propagate", "omit"])
    @pytest.mark.parametrize("metric", ["rsa", "cka", "procrustes"])
    def test_jrsa_shape_check_does_not_depend_on_nan_policy(self, metric, nan_policy):
        """The guard lived inside the `nan_policy == 'omit'` branch, so the other two
        policies reached the per-metric `[:min(m1, m2)]` truncations: (60, 6) against
        (40, 6) returned a statistic for cka and procrustes.
        """
        rng = np.random.default_rng(0)
        x1 = rng.normal(size=(60, 6))
        x2 = rng.normal(size=(40, 6))
        with pytest.raises(ValueError, match="must have the same shape"):
            jnwb.jrsa(x1, x2, metric=metric, permutations=0, nan_policy=nan_policy)

    @pytest.mark.parametrize("nan_policy", ["raise", "propagate", "omit"])
    def test_jrsa_matching_shapes_still_run_under_every_policy(self, nan_policy):
        rng = np.random.default_rng(0)
        x1 = rng.normal(size=(40, 6))
        x2 = rng.normal(size=(40, 6))
        res = jnwb.jrsa(x1, x2, metric="cka", permutations=0, nan_policy=nan_policy)
        assert np.isfinite(res.statistic)

    def test_bin_spikes_counts_the_spike_times_it_drops(self):
        """`(s >= t0) & (s < t1)` is False for NaN, so a train of NaN spike times produced
        a confident all-zero rate with nothing discarded on the record.
        """
        spikes = np.array([0.1, 0.2, np.nan, 0.4, np.nan])
        with pytest.warns(RuntimeWarning, match="2 non-finite spike time"):
            counts = bin_spikes(spikes, (0.0, 1.0), bin_size_ms=100.0)
        assert np.sum(counts) == 3

    def test_bin_spikes_does_not_warn_on_finite_input(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            counts = bin_spikes(np.array([0.1, 0.2, 0.4]), (0.0, 1.0), bin_size_ms=100.0)
        assert np.sum(counts) == 3


class TestClusterPermutationRejectsNonEstimablePoints:
    """05-24: the entry guard tested `isnan` only, and `np.divide(..., out=zeros_like(m),
    where=se > 0)` left the pre-filled 0.0 behind wherever it did not divide.
    """

    @staticmethod
    def _data():
        rng = np.random.default_rng(0)
        X = rng.normal(size=(20, 30)) + 0.5
        return X, np.zeros_like(X)

    def test_finite_input_is_unchanged(self):
        X, Y = self._data()
        res = cluster_permutation_test(
            X, Y, paired=True, n_permutations=50, rng=np.random.default_rng(1)
        )
        assert res["stat_map"][0] == pytest.approx(3.049808976019781)

    @pytest.mark.parametrize("bad", [np.inf, -np.inf, np.nan])
    def test_inf_and_nan_are_rejected_identically(self, bad):
        """An Inf sample used to pass the guard and then drive the variance at its point
        to NaN, where the zero fill survived: that point scored 0.0 and so was guaranteed
        to join no cluster -- an infinite observation reported as no effect.
        """
        X, Y = self._data()
        X = X.copy()
        X[0, 0] = bad
        with pytest.raises(ValueError, match="NaN or infinite"):
            cluster_permutation_test(
                X, Y, paired=True, n_permutations=50, rng=np.random.default_rng(1)
            )

    def test_a_constant_non_zero_difference_is_not_estimable(self):
        """Zero standard error makes t = m/0. Where m is also zero the difference was
        observed to be exactly zero and 0.0 is the answer; where m is not, the effect is
        perfectly consistent and unbounded, and 0.0 was the most wrong answer available.
        """
        X = np.zeros((10, 20))
        Y = np.zeros((10, 20))
        X[:, 5:10] = np.random.default_rng(0).standard_normal((10, 5))
        X[:, 15] = 3.0
        with pytest.warns(RuntimeWarning, match="constant non-zero difference"):
            res = cluster_permutation_test(
                X, Y, paired=True, n_permutations=50, rng=np.random.default_rng(0)
            )
        assert np.all(res["stat_map"][:5] == 0.0), "observed zeros stay zero"
        assert np.isnan(res["stat_map"][15]), "a consistent +3.0 is not 'no effect'"

    def test_a_real_cluster_is_recovered_in_full(self):
        """Guards the fixture as much as the code. The paired fixture used to be
        `baseline.copy()` plus a constant, which has zero within-pair variance: nine of
        the ten ground-truth bins scored 0.0 and the tenth survived on float rounding, so
        `assert np.any(mask[20:30])` passed on a single bin of numerical noise.
        """
        rng = np.random.default_rng(123)
        baseline = rng.standard_normal((20, 50))
        evoked = baseline + 0.5 * rng.standard_normal((20, 50))
        evoked[:, 20:30] += 2.5
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            res = cluster_permutation_test(
                evoked, baseline, paired=True, threshold=2.0,
                n_permutations=200, rng=rng,
            )
        sig = [c for c in res["clusters"] if c["p_value"] < 0.05]
        assert len(sig) == 1
        np.testing.assert_array_equal(np.flatnonzero(sig[0]["mask"]), np.arange(20, 30))
