import numpy as np
import pytest
import warnings
import jnwb as oa

def test_jrsa_nan_omission_paired():
    """Verify that nan_policy='omit' performs joint listwise exclusion of NaNs."""
    x = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
    y = np.array([10.0, np.nan, 30.0, 40.0, 50.0])
    
    # Hand-computed pearson correlation between valid pairs (1, 10), (4, 40), (5, 50) is exactly 1.0
    res = oa.jrsa(x, y, metric="pearson", nan_policy="omit", stats=False, return_input=True)
    
    # Assert correlation value is exactly 1.0 (or very close)
    assert np.isclose(res.value, 1.0)
    
    # Independently verify that the NaN-omitted inputs used for calculation match the hand-computed valid elements
    assert np.allclose(res.aligned_x1, np.array([1.0, 4.0, 5.0]))
    assert np.allclose(res.aligned_x2, np.array([10.0, 40.0, 50.0]))


def test_jrsa_preprocessing_conflict_warning():
    """Verify that simultaneous normalize=True and standardize=True raises a warning."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    
    with pytest.warns(UserWarning, match="Both normalize=True and standardize=True are enabled simultaneously"):
        oa.jrsa(x, y, metric="pearson", normalize=True, standardize=True, stats=False)


def test_jrsa_multilag_stacking():
    """Verify that passing multiple lags returns a stacked tensor of shape (n_lags, ...)."""
    rng = np.random.default_rng(42)
    x = rng.normal(0, 1, 100)
    y = rng.normal(0, 1, 100)
    
    # A single lag should work as normal (scalar similarity output)
    res_single = oa.jrsa(x, y, lag=2, stats=False)
    assert res_single.value is not None
    assert res_single.value.ndim == 0
    
    # Multi-lag should stack and compute metric over stacked dimensions
    # resulting in a 1D array of shape (3,) corresponding to the 3 lags
    res_multi = oa.jrsa(x, y, lag=[-2, 0, 3], stats=False)
    assert res_multi.value is not None
    assert res_multi.value.shape == (3,)

class TestHsicInputShapes:
    """_hsic flattened only x1, so every input that was not 2-D failed on x2 inside cdist."""

    @staticmethod
    def _hsic(u, v):
        from jnwb.jrsa import _hsic

        out = _hsic(u, v)
        return float(out[0] if isinstance(out, tuple) else out)

    def test_three_dimensional_inputs_are_flattened_per_sample(self):
        rng = np.random.default_rng(0)
        a = rng.normal(size=(20, 5, 6))
        b = rng.normal(size=(20, 5, 6))
        assert self._hsic(a, b) == pytest.approx(
            self._hsic(a.reshape(20, -1), b.reshape(20, -1))
        )

    def test_one_dimensional_inputs_are_accepted(self):
        rng = np.random.default_rng(1)
        a = rng.normal(size=20)
        assert np.isfinite(self._hsic(a, a + 0.1 * rng.normal(size=20)))

    def test_mixed_dimensionality_matches_the_flattened_pair(self):
        rng = np.random.default_rng(2)
        a = rng.normal(size=(20, 30))
        b = rng.normal(size=(20, 5, 6))
        assert self._hsic(a, b) == pytest.approx(self._hsic(a, b.reshape(20, -1)))


class TestVectorLengthMismatchSafety:
    """_pearson, _spearman, _kendall, and _cosine must raise ValueError on mismatched lengths."""

    def test_pearson_raises_on_length_mismatch(self):
        from jnwb.jrsa import _pearson
        x = np.arange(10, dtype=float)
        y = np.arange(15, dtype=float)
        with pytest.raises(ValueError, match="_pearson: vector length mismatch"):
            _pearson(x, y)

    def test_spearman_raises_on_length_mismatch(self):
        from jnwb.jrsa import _spearman
        x = np.arange(10, dtype=float)
        y = np.arange(15, dtype=float)
        with pytest.raises(ValueError, match="_spearman: vector length mismatch"):
            _spearman(x, y)

    def test_kendall_raises_on_length_mismatch(self):
        from jnwb.jrsa import _kendall
        x = np.arange(10, dtype=float)
        y = np.arange(15, dtype=float)
        with pytest.raises(ValueError, match="_kendall: vector length mismatch"):
            _kendall(x, y)

    def test_cosine_raises_on_length_mismatch(self):
        from jnwb.jrsa import _cosine
        x = np.arange(10, dtype=float)
        y = np.arange(15, dtype=float)
        with pytest.raises(ValueError, match="_cosine: vector length mismatch"):
            _cosine(x, y)

    def test_equal_length_controls(self):
        from jnwb.jrsa import _pearson, _spearman, _kendall, _cosine
        x = np.arange(10, dtype=float)
        y = x + 0.1 * np.ones(10)
        r, _, _, _, _ = _pearson(x, y)
        rho, _, _, _, _ = _spearman(x, y)
        tau, _, _, _, _ = _kendall(x, y)
        cos, _, _, _, _ = _cosine(x, y)
        assert np.isclose(r, 1.0)
        assert np.isclose(rho, 1.0)
        assert np.isclose(tau, 1.0)
        assert cos > 0.99


class TestMultipleCorrectionFallback:
    """Test _multiple_correction and delegation to StatisticalAnalysis.fdr_correct."""

    def test_multiple_correction_bh_matches_fdr_correct(self):
        from jnwb.jrsa import _multiple_correction
        from jnwb.statistics import StatisticalAnalysis
        p = np.array([0.001, 0.005, 0.01, 0.01, 0.02, 0.04, 0.04, 0.05, 0.1, 0.5, 0.8, 0.99])
        q_corr = _multiple_correction(p, method="fdr_bh", alpha=0.05)
        q_sa = StatisticalAnalysis.fdr_correct(p, method="bh")
        np.testing.assert_allclose(q_corr, q_sa, atol=1e-15)

    def test_multiple_correction_bonferroni(self):
        from jnwb.jrsa import _multiple_correction
        p = np.array([0.01, 0.05, 0.5])
        q = _multiple_correction(p, method="bonferroni", alpha=0.05)
        np.testing.assert_allclose(q, np.array([0.03, 0.15, 1.0]))



class TestRvIsCentred:
    """The RV coefficient is defined on column-centred matrices. `_rv` normalised by the
    Frobenius norm but never centred, so the Gram matrices were dominated by the common
    mean and any two representations sharing an offset looked identical: two independent
    Gaussian samples shifted by +50 returned RV = 1.0000.
    """

    def test_independent_representations_sharing_an_offset_are_not_identical(self):
        from jnwb.jrsa import _rv

        rng = np.random.default_rng(0)
        a = rng.standard_normal((100, 20)) + 50.0
        b = rng.standard_normal((100, 20)) + 50.0
        offset = float(_rv(a, b)[0])
        centred = float(_rv(a - a.mean(axis=0), b - b.mean(axis=0))[0])
        assert offset < 0.5, f"independent representations report RV = {offset:.4f}"
        assert offset == pytest.approx(centred, abs=1e-12), (
            "adding a constant offset changed RV, so the estimator is still not centred"
        )

    def test_rv_is_one_for_an_affine_image_of_the_same_representation(self):
        from jnwb.jrsa import _rv

        rng = np.random.default_rng(1)
        x = rng.standard_normal((80, 12))
        assert float(_rv(x, x)[0]) == pytest.approx(1.0, abs=1e-10)
        assert float(_rv(x, 3.0 * x + 7.0)[0]) == pytest.approx(1.0, abs=1e-10)


class TestPermutationNullShufflesObservations:
    """`_permutation_test` shuffled axis=-1 for every metric. The whole-representation
    metrics reshape to (n_observations, n_features) and ignore `axis`, so axis=-1 is their
    FEATURE axis -- and every one of them is invariant to a permutation of features, since
    a column permutation is an orthogonal transform. The null was therefore a point mass at
    the observed value and p came back as exactly 1.0 whatever the data: on independent
    60 x 12 Gaussian representations, cka, rv, hsic, distance_correlation and procrustes
    all reported p = 1.0000.
    """

    METRICS = ["cka", "rv", "hsic", "distance_correlation", "procrustes"]

    @staticmethod
    def _pair(seed=0):
        rng = np.random.default_rng(seed)
        return rng.standard_normal((60, 12)), rng.standard_normal((60, 12))

    @pytest.mark.parametrize("metric", METRICS)
    def test_the_null_is_not_a_point_mass(self, metric):
        """A point-mass null puts every draw at the observed value, so p is exactly 1.0 on
        every dataset. A live null gives p that moves with the data."""
        ps = []
        for seed in range(6):
            x1, x2 = self._pair(seed)
            res = oa.jrsa(x1, x2, metric=metric, permutations=200, bootstrap=0,
                          stats=True, seed=seed)
            ps.append(float(np.ravel(res.p)[0]))
        assert len(set(ps)) > 1, (
            f"{metric}: p was identical ({ps[0]}) on six independent datasets, so the "
            f"permutation is shuffling an axis the metric is invariant to"
        )
        # A point mass puts EVERY dataset at exactly 1.0. A single p of 1.0 is a legitimate
        # draw from a live null -- it happens with probability 1/(n_perm+1) per dataset --
        # so the discriminating statement is that most datasets are not pinned there.
        assert sum(pv == 1.0 for pv in ps) <= 1, f"{metric}: p = 1.0 on {ps}"

    @pytest.mark.parametrize("metric", METRICS)
    def test_independent_representations_do_not_report_p_exactly_one(self, metric):
        x1, x2 = self._pair()
        res = oa.jrsa(x1, x2, metric=metric, permutations=200, bootstrap=0, stats=True, seed=0)
        assert float(np.ravel(res.p)[0]) < 1.0


    @pytest.mark.parametrize("metric", METRICS)
    def test_a_linearly_related_representation_is_detected(self, metric):
        """The repair must not buy a live null by making the test powerless."""
        rng = np.random.default_rng(0)
        x1 = rng.standard_normal((60, 12))
        x2 = x1 @ rng.standard_normal((12, 12))
        res = oa.jrsa(x1, x2, metric=metric, permutations=500, bootstrap=0, stats=True, seed=0)
        related_p = float(np.ravel(res.p)[0])
        indep = oa.jrsa(*self._pair(), metric=metric, permutations=500, bootstrap=0,
                        stats=True, seed=0)
        assert related_p < 0.05, f"{metric}: related representations scored p = {related_p}"
        assert related_p < float(np.ravel(indep.p)[0])


class TestJrsaDoesNotSwallowUnknownKeywords:
    """`jrsa` forwards **kwargs to the metric, and every metric function itself ends in
    **kwargs, so nothing rejected a keyword neither of them understood. Two consequences
    were measured on the pre-repair code: `jrsa(..., seed=0)` -- the spelling every other
    seeded entry point in this package uses -- was accepted in silence while
    `random_state` stayed None, so four repeated calls returned p = 0.2736, 0.3333,
    0.2637, 0.2935 on identical input; and `jrsa(..., definitely_not_a_param=123)` was
    accepted too, so a misspelled metric option silently returned the default answer.
    """

    @staticmethod
    def _pair():
        rng = np.random.default_rng(0)
        return rng.standard_normal((60, 12)), rng.standard_normal((60, 12))

    def test_seed_is_honoured_and_not_absorbed_into_kwargs(self):
        x1, x2 = self._pair()
        ps = {
            float(np.ravel(oa.jrsa(x1, x2, metric="hsic", permutations=200, bootstrap=0,
                                   stats=True, seed=0).p)[0])
            for _ in range(4)
        }
        assert len(ps) == 1, f"seed=0 gave {len(ps)} different p-values on one dataset: {ps}"
        assert ps == {
            float(np.ravel(oa.jrsa(x1, x2, metric="hsic", permutations=200, bootstrap=0,
                                   stats=True, random_state=0).p)[0])
        }, "seed= and random_state= must name the same stream"

    def test_an_unknown_keyword_is_an_error_not_a_default_answer(self):
        x1, x2 = self._pair()
        with pytest.raises(TypeError, match="definitely_not_a_param"):
            oa.jrsa(x1, x2, metric="hsic", permutations=10, bootstrap=0, stats=True,
                    definitely_not_a_param=123)

    def test_a_metric_option_belonging_to_another_metric_is_rejected(self):
        """`kernel` is cka's option, not hsic's; it used to be dropped in silence."""
        x1, x2 = self._pair()
        with pytest.raises(TypeError, match="kernel"):
            oa.jrsa(x1, x2, metric="hsic", permutations=10, bootstrap=0, stats=True,
                    kernel="linear")

    def test_the_metrics_own_options_still_reach_it(self):
        """The guard must reject typos without disabling real options."""
        x1, x2 = self._pair()
        a = float(np.ravel(oa.jrsa(x1, x2, metric="hsic", permutations=0, bootstrap=0,
                                   stats=False, sigma=0.5).value)[0])
        b = float(np.ravel(oa.jrsa(x1, x2, metric="hsic", permutations=0, bootstrap=0,
                                   stats=False, sigma=4.0).value)[0])
        assert a != b, "sigma reached the metric but changed nothing"

    def test_passing_both_spellings_is_refused(self):
        """05-34 made `rng` canonical and routed jrsa through the package's shared alias
        resolver, so the conflict is now the same `ValueError: Conflicting values` that
        `band_power(fs=, sampling_rate=)` and the nine unit-suffixed parameters raise.
        jrsa was the only place spelling this refusal `TypeError`.
        """
        x1, x2 = self._pair()
        for kwargs in ({"seed": 0, "random_state": 1},
                       {"rng": 0, "seed": 1},
                       {"rng": 0, "random_state": 1}):
            with pytest.raises(ValueError, match="Conflicting values provided to jrsa"):
                oa.jrsa(x1, x2, metric="hsic", permutations=10, stats=True, **kwargs)

    def test_agreeing_spellings_are_not_a_conflict(self):
        x1, x2 = self._pair()
        a = oa.jrsa(x1, x2, metric="hsic", permutations=10, stats=True, rng=3, seed=3)
        b = oa.jrsa(x1, x2, metric="hsic", permutations=10, stats=True, rng=3)
        assert float(np.ravel(a.p)[0]) == float(np.ravel(b.p)[0])


# `hsic` is excluded: its *value* is not invariant to duplicating features (0.015372 ->
# 0.016030), so the premise of the test below does not hold for it.
_OBS_AXIS_0_FEATURE_INVARIANT = ["cka", "rv", "distance_correlation", "procrustes", "rsa"]


class TestBootstrapResamplesObservations:
    """`perm_axis` was computed and then ignored by both `_bootstrap` call sites,
    which hardcoded axis=-1. For the six observation-axis-0 metrics the interval therefore
    answered "how much does this depend on which columns I measured" rather than "on which
    observations I sampled"."""

    @pytest.mark.parametrize("metric", _OBS_AXIS_0_FEATURE_INVARIANT)
    def test_the_interval_is_invariant_to_duplicating_features(self, metric):
        """Duplicating every feature column leaves an observation-resampled interval
        unchanged; a feature-resampled one draws from 2p columns instead of p."""
        rng = np.random.default_rng(5)
        x = rng.normal(size=(60, 4))
        y = x * 0.6 + 0.8 * rng.normal(size=(60, 4))

        def width(a, b):
            res = oa.jrsa(a, b, metric=metric, bootstrap=2000, random_state=11)
            ci = np.asarray(res.ci).ravel()
            return float(ci[1] - ci[0])

        plain = width(x, y)
        duplicated = width(np.hstack([x, x]), np.hstack([y, y]))
        # Four of these agree to 1e-15; `rsa` to 2.4e-06, from float accumulation in the
        # RDM. A feature-axis bootstrap resamples 8 columns instead of 4 and moves the
        # width by tens of percent, so 1e-4 separates the two cases by four orders.
        assert duplicated == pytest.approx(plain, rel=1e-4)

    @pytest.mark.parametrize("metric", ["cka", "rv"])
    def test_more_observations_narrow_the_interval(self, metric):
        rng = np.random.default_rng(7)

        def width(n):
            x = rng.normal(size=(n, 4))
            y = x * 0.6 + 0.8 * rng.normal(size=(n, 4))
            res = oa.jrsa(x, y, metric=metric, bootstrap=2000, random_state=11)
            ci = np.asarray(res.ci).ravel()
            return float(ci[1] - ci[0])

        assert width(400) < width(50)


class TestPermutationPWins:
    """`if p_raw is None` let the metric's own cell-wise parametric p pre-empt the
    permutation p that had already been computed. `oa.jrsa(..., metric="rsa")` returned the
    identical value at permutations=10 and permutations=2000 -- it was
    `rdm_similarity(v1, v2, "spearman")[1]`, which rsa.py:167 states is not a valid test
    of RDM relatedness."""

    PARAMETRIC_METRICS = ["rsa", "pearson", "spearman", "kendall"]

    @pytest.mark.parametrize("metric", PARAMETRIC_METRICS)
    def test_p_responds_to_the_permutation_count(self, metric):
        rng = np.random.default_rng(3)
        a = rng.normal(size=(40, 6))
        b = rng.normal(size=(40, 6))
        low = float(np.atleast_1d(oa.jrsa(a, b, metric=metric, permutations=10, random_state=2).p)[0])
        high = float(np.atleast_1d(oa.jrsa(a, b, metric=metric, permutations=2000, random_state=2).p)[0])
        assert low != pytest.approx(high, abs=1e-12), (
            f"{metric}: p did not move between 10 and 2000 permutations, so it is not a "
            "permutation p"
        )

    def test_the_reported_p_is_not_the_parametric_one(self):
        from jnwb.rsa import rdm, rdm_similarity

        rng = np.random.default_rng(3)
        a = rng.normal(size=(40, 6))
        b = rng.normal(size=(40, 6))
        parametric = rdm_similarity(rdm(a), rdm(b), "spearman")[1]
        reported = float(np.atleast_1d(oa.jrsa(a, b, metric="rsa", permutations=2000, random_state=2).p)[0])
        assert reported != pytest.approx(parametric, abs=1e-12)

    def test_p_is_a_valid_probability_and_respects_the_permutation_floor(self):
        rng = np.random.default_rng(4)
        a = rng.normal(size=(40, 6))
        b = rng.normal(size=(40, 6))
        for perms in (10, 200, 2000):
            p = float(np.atleast_1d(oa.jrsa(a, b, metric="rsa", permutations=perms, random_state=2).p)[0])
            assert 1.0 / (perms + 1.0) <= p <= 1.0

    def test_permutations_zero_still_returns_the_parametric_p(self):
        from jnwb.rsa import rdm, rdm_similarity

        rng = np.random.default_rng(3)
        a = rng.normal(size=(40, 6))
        b = rng.normal(size=(40, 6))
        parametric = rdm_similarity(rdm(a), rdm(b), "spearman")[1]
        res = oa.jrsa(a, b, metric="rsa", permutations=0, random_state=2)
        assert float(np.atleast_1d(res.p)[0]) == pytest.approx(parametric)


class TestAlternativeWithoutPermutations:
    """With no permutation null, `alternative` used to be echoed in `parameters` while the
    reported p stayed the metric's two-sided one, and a misspelt alternative was accepted."""

    rng = np.random.default_rng(3)
    x1 = rng.normal(size=(15, 8))
    x2 = -x1 + 0.4 * rng.normal(size=(15, 8))      # r = -0.949

    @pytest.mark.parametrize("kw", [{}, {"permutations": 0}, {"stats": False},
                                    {"lag": [0, 1], "permutations": 0}])
    def test_a_misspelt_alternative_raises_before_anything_is_computed(self, kw):
        with pytest.raises(ValueError, match="alternative 'GREATER'"):
            oa.jrsa(self.x1, self.x2, metric="pearson", alternative="GREATER", rng=0, **kw)
        # Refused ahead of the metric, which is checked later in the pipeline.
        with pytest.raises(ValueError, match="alternative"):
            oa.jrsa(self.x1, self.x2, metric="bogus", alternative="GREATER", **kw)

    @pytest.mark.parametrize("kw", [{"permutations": 0}, {"stats": False}])
    def test_a_one_sided_alternative_halves_the_parametric_p_on_its_side(self, kw):
        from scipy import stats as sps

        r, p2 = sps.pearsonr(self.x1.ravel(), self.x2.ravel())
        two = oa.jrsa(self.x1, self.x2, metric="pearson", rng=0, **kw)
        assert float(two.value) == pytest.approx(r) and r < -0.9
        assert float(two.p) == pytest.approx(p2, rel=1e-9)
        less = oa.jrsa(self.x1, self.x2, metric="pearson", alternative="less", rng=0, **kw)
        greater = oa.jrsa(self.x1, self.x2, metric="pearson", alternative="greater", rng=0,
                          **kw)
        assert float(less.p) == pytest.approx(p2 / 2, rel=1e-9) and float(less.p) < 1e-50
        assert float(greater.p) == 1.0 - p2 / 2
        # Per lag, on each lag's own sign.
        lagged = oa.jrsa(self.x1, self.x2, metric="pearson", lag=[0, 3], alternative="greater",
                         rng=0, **kw)
        base = oa.jrsa(self.x1, self.x2, metric="pearson", lag=[0, 3], rng=0, **kw)
        v, pb = np.asarray(base.value), np.asarray(base.p)
        expected = np.where(v > 0, pb / 2, 1 - pb / 2)
        np.testing.assert_allclose(np.asarray(lagged.p), expected, rtol=1e-12)

    def test_an_upper_tail_f_test_refuses_a_one_sided_request(self):
        """The SSR F-test p is upper-tail already; halving it would be wrong."""
        with pytest.raises(ValueError, match="granger_ssr_ftest") as err:
            oa.jrsa(self.x1, self.x2, metric="granger_ssr_ftest", alternative="less",
                    permutations=0)
        # The message says why, not only that.
        assert "upper-tail F-test" in str(err.value) and "halving" in str(err.value)
