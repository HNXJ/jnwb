"""05-15: undefined statistics must not return the most significant p a test can emit.

``np.abs(nan) >= np.abs(nan)`` is False, so a non-finite observed statistic made every
null comparison False, the exceedance count 0, and the p-value ``1/(B+1)`` -- the floor of
the permutation test, i.e. maximal significance from a statistic that does not exist.

The guard for this, ``statistics._require_shuffle_inputs``, already existed and was applied
at none of these five sites. Each test below fails if its site is reverted.
"""

from __future__ import annotations

import numpy as np
import pytest

from jnwb.jrsa import jrsa
from jnwb.spectral import cross_area_coherence
from jnwb.statistics import (
    StatisticalAnalysis,
    cross_modal_comparison,
    shuffle_r2_ci,
)

BAD = [np.nan, np.inf, -np.inf]


def _floor(n_draws: int) -> float:
    """The smallest p a permutation test with ``n_draws`` draws can return."""
    return 1.0 / (n_draws + 1.0)


class TestNoFabricatedSignificance:
    @pytest.mark.parametrize("bad", BAD)
    def test_jrsa_returns_nan_not_the_p_floor(self, bad):
        """A constant input against a Gaussian one reported value nan with p 0.000999."""
        rng = np.random.default_rng(0)
        x = np.full((60, 12), 1.0)
        x[0, 0] = bad
        res = jrsa(x, rng.normal(size=(60, 12)), metric="cka", permutations=1000)
        p = np.atleast_1d(res.p)
        assert np.all(np.isnan(p)), f"expected NaN, got {p}"

    def test_jrsa_p_is_unchanged_on_finite_input(self):
        rng = np.random.default_rng(1)
        a, b = rng.normal(size=(60, 12)), rng.normal(size=(60, 12))
        res = jrsa(a, b, metric="cka", permutations=500, random_state=3)
        p = float(np.atleast_1d(res.p)[0])
        assert np.isfinite(p) and 0.0 < p <= 1.0

    @pytest.mark.parametrize("bad", BAD)
    def test_permutation_test_returns_nan_not_the_p_floor(self, bad):
        """Two all-NaN groups reported pval 0.0002 and significant=True."""
        with pytest.warns(RuntimeWarning, match="non-finite"):
            out = StatisticalAnalysis.permutation_test(
                np.full(5, bad), np.arange(5.0), n_permutations=5000
            )
        assert np.isnan(out["pval"])
        assert out["significant"] is False
        assert out["pval"] != pytest.approx(_floor(5000))

    def test_permutation_test_warns_rather_than_silently_dropping(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, np.nan])
        with pytest.warns(RuntimeWarning, match="dropped 1 non-finite"):
            out = StatisticalAnalysis.permutation_test(x, np.arange(5.0), n_permutations=200)
        assert out["n_x"] == 4

    def test_permutation_test_is_unchanged_on_finite_input(self):
        rng = np.random.default_rng(2)
        out = StatisticalAnalysis.permutation_test(
            rng.normal(size=40), rng.normal(size=40) + 3.0, n_permutations=2000
        )
        assert np.isfinite(out["pval"]) and out["pval"] > 0.0

    @pytest.mark.parametrize("bad", BAD)
    def test_shuffle_r2_ci_refuses_rather_than_reporting_the_p_floor(self, bad):
        """r2_observed was nan while p_val was 0.000999."""
        rng = np.random.default_rng(3)
        y_true = rng.integers(0, 2, 40)
        y_score = rng.normal(size=40)
        y_score[3] = bad
        with pytest.raises(ValueError, match="finite"):
            shuffle_r2_ci(y_true, y_score, n_shuffle=1000)

    @pytest.mark.parametrize("bad", BAD)
    def test_cross_area_coherence_refuses_like_its_siblings(self, bad):
        """Every band coherence was NaN while every band p sat at 1/(n_surrogates+1)."""
        rng = np.random.default_rng(4)
        a, b = rng.normal(size=4000), rng.normal(size=4000)
        a[0] = bad
        with pytest.raises(ValueError, match="finite"):
            cross_area_coherence(a, b, fs=1000.0, freq_bands="canonical", n_surrogates=100)

    def test_cross_area_coherence_is_unchanged_on_finite_input(self):
        rng = np.random.default_rng(5)
        out = cross_area_coherence(
            rng.normal(size=4000),
            rng.normal(size=4000),
            fs=1000.0,
            freq_bands="canonical",
            n_surrogates=100,
            rng=np.random.default_rng(6),
        )
        sig = np.array(list(out["band_significance"].values()))
        assert np.all(np.isfinite(sig))
        assert not np.all(sig == _floor(100)), "an unrelated pair must not be maximally significant"

    @pytest.mark.parametrize("bad", BAD)
    def test_cross_modal_comparison_refuses_rather_than_flipping_to_significant(self, bad):
        """One NaN moved lag_corrected_pvalue from 0.8322 to 0.000999 and
        significant_lag_corrected from False to True."""
        rng = np.random.default_rng(7)
        x, y = rng.normal(size=300), rng.normal(size=300)
        x[5] = bad
        with pytest.raises(ValueError, match="finite"):
            cross_modal_comparison(x, y, bin_ms=10.0, seed=2, n_permutations=1000)

    def test_cross_modal_comparison_is_unchanged_on_finite_input(self):
        rng = np.random.default_rng(8)
        out = cross_modal_comparison(
            rng.normal(size=300), rng.normal(size=300), bin_ms=10.0, seed=2, n_permutations=1000
        )
        assert np.isfinite(out["lag_corrected_pvalue"])
        assert out["lag_corrected_pvalue"] != pytest.approx(_floor(1000))

    def test_an_all_nan_input_never_reaches_the_internals(self):
        """An all-NaN input used to leak a bare KeyError('parametric')."""
        rng = np.random.default_rng(9)
        with pytest.raises(ValueError, match="finite"):
            cross_modal_comparison(
                np.full(300, np.nan), rng.normal(size=300), bin_ms=10.0, seed=2
            )
