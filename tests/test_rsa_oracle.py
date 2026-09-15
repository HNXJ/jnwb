"""0.2.4-04: RDM / RSA checked against direct formulas and the pre-delegation estimand.

Failures these tests discriminate:

- a zero-variance condition got correlation distance 0 (declared identical to every
  other condition) instead of an undefined distance;
- ``jrsa(metric="rsa")`` then returned a finite similarity where its pre-delegation
  ``pdist`` + ``spearmanr`` implementation returned NaN;
- non-symmetric or nonzero-diagonal matrices, and condensed vectors of impossible
  length, were compared without complaint;
- a zero vector under ``'cosine'`` reported similarity 0;
- ``device`` accepted any string and did nothing.
"""

import warnings

import numpy as np
import pytest
from scipy.spatial.distance import pdist, squareform
from scipy.stats import spearmanr

import jnwb


def _features(n=9, d=14, seed=0):
    return np.random.default_rng(seed).normal(size=(n, d))


def _direct(X, metric):
    n = X.shape[0]
    out = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = X[i], X[j]
            if metric == "correlation":
                out.append(1.0 - np.corrcoef(a, b)[0, 1])
            elif metric == "cosine":
                out.append(1.0 - a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
            elif metric == "euclidean":
                out.append(np.sqrt(np.sum((a - b) ** 2)))
            elif metric == "cityblock":
                out.append(np.sum(np.abs(a - b)))
    return np.array(out)


class TestRdmAgainstDirectFormulas:
    @pytest.mark.parametrize("metric", ["correlation", "cosine", "euclidean", "cityblock"])
    def test_condensed_matches_direct_formula(self, metric):
        X = _features()
        assert np.allclose(jnwb.rdm(X, metric=metric), _direct(X, metric), rtol=1e-12, atol=1e-12)

    @pytest.mark.parametrize("n", [2, 3, 10])
    def test_full_and_condensed_are_the_same_matrix(self, n):
        X = _features(n=n)
        v = jnwb.rdm(X)
        M = jnwb.rdm(X, condensed=False)
        assert v.shape == (n * (n - 1) // 2,)
        assert np.array_equal(M, M.T)
        assert np.all(np.diag(M) == 0.0)
        assert np.array_equal(squareform(M), v)

    def test_trailing_dimensions_are_flattened_per_condition(self):
        X = np.random.default_rng(1).normal(size=(6, 3, 4))
        assert np.array_equal(jnwb.rdm(X), jnwb.rdm(X.reshape(6, 12)))

    def test_integer_and_float32_inputs_compute_in_float64(self):
        X = np.random.default_rng(2).integers(0, 50, size=(7, 9))
        assert jnwb.rdm(X).dtype == np.float64
        assert np.array_equal(jnwb.rdm(X.astype(np.float32)), jnwb.rdm(X.astype(np.float64)))


class TestUndefinedDistances:
    def test_zero_variance_condition_is_rejected_under_correlation(self):
        X = _features()
        X[3] = 2.0
        with pytest.raises(ValueError, match="undefined"):
            jnwb.rdm(X, metric="correlation")

    def test_zero_norm_condition_is_rejected_under_cosine(self):
        X = _features()
        X[3] = 0.0
        with pytest.raises(ValueError, match="undefined"):
            jnwb.rdm(X, metric="cosine")

    def test_zero_variance_condition_is_fine_where_the_metric_is_defined(self):
        X = _features()
        X[3] = 2.0
        assert np.allclose(jnwb.rdm(X, metric="euclidean"), _direct(X, "euclidean"))

    def test_undocumented_alias_is_not_claimed(self):
        with pytest.raises(ValueError):
            jnwb.rdm(_features(), metric="manhattan")


class TestRdmSimilarityRejectsNonRdms:
    def test_non_symmetric_matrix(self):
        M = jnwb.rdm(_features(), condensed=False)
        M[0, 1] += 1.0
        with pytest.raises(ValueError, match="not symmetric"):
            jnwb.rdm_similarity(M, jnwb.rdm(_features(seed=1), condensed=False))

    def test_nonzero_diagonal(self):
        M = jnwb.rdm(_features(), condensed=False)
        np.fill_diagonal(M, 1.0)
        with pytest.raises(ValueError, match="nonzero diagonal"):
            jnwb.rdm_similarity(M, jnwb.rdm(_features(seed=1), condensed=False))

    @pytest.mark.parametrize("length", [0, 2, 7, 11])
    def test_impossible_condensed_length(self, length):
        with pytest.raises(ValueError, match=r"not N\(N-1\)/2"):
            jnwb.rdm_similarity(np.arange(length, dtype=float), np.arange(length, dtype=float))

    def test_zero_rdm_under_cosine_is_undefined_not_zero(self):
        rho, p = jnwb.rdm_similarity(np.zeros(36), jnwb.rdm(_features()), metric="cosine")
        assert np.isnan(rho) and np.isnan(p)


class TestRdmSimilarityValues:
    def test_diagonal_is_excluded_and_forms_agree(self):
        X1, X2 = _features(), _features(seed=3)
        full = jnwb.rdm_similarity(jnwb.rdm(X1, condensed=False), jnwb.rdm(X2, condensed=False))
        mixed = jnwb.rdm_similarity(jnwb.rdm(X1, condensed=False), jnwb.rdm(X2))
        oracle = spearmanr(pdist(X1, "correlation"), pdist(X2, "correlation"))
        assert full == pytest.approx((oracle.statistic, oracle.pvalue), rel=1e-12)
        assert mixed == pytest.approx(full, rel=1e-12)

    @pytest.mark.parametrize("metric", ["spearman", "pearson", "kendall", "cosine"])
    def test_self_similarity_is_the_maximum(self, metric):
        v = jnwb.rdm(_features())
        assert jnwb.rdm_similarity(v, v, metric=metric)[0] == pytest.approx(1.0, abs=1e-12)


class TestJrsaPreservesHistoricalEstimand:
    """Oracle: the implementation jrsa used before delegating to jnwb.rsa (50e646aa)."""

    @staticmethod
    def _historical(x1, x2):
        return spearmanr(pdist(x1, "correlation"), pdist(x2, "correlation"))

    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_matches_pre_delegation_formula(self, seed):
        x1, x2 = _features(n=12, seed=seed), _features(n=12, seed=seed + 10)
        res = jnwb.jrsa(x1, x2, metric="rsa", stats=False)
        assert float(res.value) == pytest.approx(self._historical(x1, x2).statistic, rel=1e-12)

    def test_zero_variance_condition_gives_nan_as_it_historically_did(self):
        x1, x2 = _features(n=12), _features(n=12, seed=5)
        x1[4] = 1.0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert np.isnan(self._historical(x1, x2).statistic)
        assert np.isnan(float(jnwb.jrsa(x1, x2, metric="rsa", stats=False).value))


class TestRdmDevice:
    def test_unrecognised_device_is_rejected(self):
        with pytest.raises(ValueError, match="unrecognised device"):
            jnwb.rdm(_features(), device="bogus")

    def test_cuda_request_is_announced_and_computes_the_cpu_result(self):
        X = _features()
        with pytest.warns(RuntimeWarning):
            out = jnwb.rdm(X, device="cuda")
        assert np.array_equal(out, jnwb.rdm(X))
