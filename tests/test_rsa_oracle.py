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
from scipy.spatial.distance import cosine as cosine_distance
from scipy.stats import kendalltau, pearsonr, spearmanr

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


class TestSimilarityMetricsAgainstScipy:
    """Each similarity metric must be the estimator it names.

    ``pearson``, ``kendall`` and ``cosine`` were only range-checked (0 <= r <= 1),
    so returning Spearman for all four, or computing cosine over the wrong axis,
    passed. These pin each coefficient and its p-value to a SciPy oracle.
    """

    @staticmethod
    def _pair():
        return jnwb.rdm(_features(seed=0)), jnwb.rdm(_features(seed=5))

    def test_pearson_matches_scipy(self):
        a, b = self._pair()
        expected = pearsonr(a, b)
        got = jnwb.rdm_similarity(a, b, metric="pearson")
        assert got[0] == pytest.approx(expected[0], abs=1e-12)
        assert got[1] == pytest.approx(expected[1], abs=1e-12)

    def test_spearman_matches_scipy(self):
        a, b = self._pair()
        expected = spearmanr(a, b)
        got = jnwb.rdm_similarity(a, b, metric="spearman")
        assert got[0] == pytest.approx(expected[0], abs=1e-12)
        assert got[1] == pytest.approx(expected[1], abs=1e-12)

    def test_kendall_matches_scipy(self):
        a, b = self._pair()
        expected = kendalltau(a, b)
        got = jnwb.rdm_similarity(a, b, metric="kendall")
        assert got[0] == pytest.approx(expected[0], abs=1e-12)
        assert got[1] == pytest.approx(expected[1], abs=1e-12)

    def test_cosine_is_a_similarity_and_reports_no_p_value(self):
        a, b = self._pair()
        got = jnwb.rdm_similarity(a, b, metric="cosine")
        assert got[0] == pytest.approx(1.0 - cosine_distance(a, b), abs=1e-12)
        assert np.isnan(got[1]), "cosine has no null distribution; p must not be fabricated"

    def test_the_four_metrics_are_not_substituted_for_one_another(self):
        a, b = self._pair()
        values = [
            jnwb.rdm_similarity(a, b, metric=m)[0]
            for m in ("pearson", "spearman", "kendall", "cosine")
        ]
        assert len({round(v, 9) for v in values}) == 4, f"metrics collapsed: {values}"


class TestRdmInvariantsHoldForEveryAcceptedMetric:
    """``rdm`` documents pass-through to ``pdist`` for any metric it accepts, so a
    pdist oracle would be circular. What is not delegated is the wrapper's own
    contract -- condensed length, symmetry, zero diagonal, float64, and the
    correspondence between the two forms -- and that was only checked for the
    default metric.
    """

    METRICS = [
        "correlation", "cosine", "euclidean", "cityblock", "sqeuclidean",
        "chebyshev", "hamming", "jaccard", "minkowski", "braycurtis",
        "canberra", "seuclidean",
    ]

    @staticmethod
    def _positive(n=7, d=11, seed=0):
        # Strictly positive: braycurtis and canberra are undefined at the origin.
        return np.abs(np.random.default_rng(seed).normal(size=(n, d))) + 0.5

    @pytest.mark.parametrize("metric", METRICS)
    def test_both_forms_agree_and_carry_no_fabricated_geometry(self, metric):
        X = self._positive()
        condensed = jnwb.rdm(X, metric=metric)
        full = jnwb.rdm(X, metric=metric, condensed=False)
        assert condensed.shape == (7 * 6 // 2,)
        assert condensed.dtype == np.float64
        assert np.array_equal(full, full.T)
        assert np.all(np.diag(full) == 0.0)
        assert np.allclose(squareform(full), condensed, rtol=1e-12, atol=1e-12)

    # hamming and jaccard treat continuous features as categorical, so with no exact
    # ties every pair differs in every coordinate and the RDM is constant. Rank
    # similarity is then undefined, which is a property of the input, not a defect.
    VARYING = [m for m in METRICS if m not in ("hamming", "jaccard")]

    @pytest.mark.parametrize("metric", VARYING)
    def test_self_similarity_is_the_maximum_for_every_metric(self, metric):
        rdm = jnwb.rdm(self._positive(), metric=metric)
        assert jnwb.rdm_similarity(rdm, rdm, metric="spearman")[0] == pytest.approx(1.0)
        assert jnwb.rdm_similarity(rdm, rdm, metric="cosine")[0] == pytest.approx(1.0)

    @pytest.mark.parametrize("metric", ["hamming", "jaccard"])
    def test_a_constant_rdm_is_undefined_not_perfectly_similar(self, metric):
        """The degenerate case must not be reported as rho = 1.0."""
        rdm = jnwb.rdm(self._positive(), metric=metric)
        assert len(np.unique(rdm)) == 1
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rho, p = jnwb.rdm_similarity(rdm, rdm, metric="spearman")
        assert np.isnan(rho) and np.isnan(p)

    def test_two_conditions_give_the_single_defined_distance(self):
        assert jnwb.rdm(self._positive(n=2)).shape == (1,)

    def test_fewer_than_two_conditions_is_rejected(self):
        with pytest.raises(ValueError, match="at least 2 conditions"):
            jnwb.rdm(self._positive(n=1))

    def test_non_finite_features_are_rejected(self):
        X = self._positive()
        X[0, 0] = np.nan
        with pytest.raises(ValueError, match="non-finite"):
            jnwb.rdm(X)

    def test_an_unknown_metric_is_rejected(self):
        with pytest.raises(ValueError, match="(?i)metric"):
            jnwb.rdm(self._positive(), metric="not_a_metric")
