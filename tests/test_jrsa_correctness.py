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

class TestLagShiftsTheObservationAxis:
    """`lag` rolled the last axis for every metric. For the six whose observations lie on
    axis 0 that axis holds features, which they are invariant to, so a lag sweep of a
    delayed copy returned one value under every label."""

    AXIS0 = ["cka", "rv", "rsa", "procrustes", "distance_correlation", "hsic"]

    @staticmethod
    def _delayed_copy(n=60, k=6, delay=3):
        rng = np.random.default_rng(0)
        x = rng.standard_normal((n, k))
        return x, np.roll(x, delay, axis=0) + 0.1 * rng.standard_normal((n, k))

    @staticmethod
    def _overlap(x, y, lag, axis):
        n, k = x.shape[axis], abs(lag)
        head, tail = np.arange(n - k), np.arange(k, n)
        if lag >= 0:
            return np.take(x, tail, axis=axis), np.take(y, head, axis=axis)
        return np.take(x, head, axis=axis), np.take(y, tail, axis=axis)

    @pytest.mark.parametrize("metric", AXIS0)
    def test_a_lag_equals_the_overlap_of_the_observations_by_hand(self, metric):
        x, y = self._delayed_copy()
        swept = np.asarray(oa.jrsa(x, y, metric=metric, lag=[0, -3, 4], stats=False).value, float)
        by_hand = [float(oa.jrsa(*self._overlap(x, y, l, 0), metric=metric, stats=False).value)
                   for l in (0, -3, 4)]
        np.testing.assert_allclose(swept, by_hand, rtol=1e-12)
        single = float(oa.jrsa(x, y, metric=metric, lag=-3, stats=False).value)
        np.testing.assert_allclose(single, by_hand[1], rtol=1e-12)
        assert abs(swept[1] - swept[0]) > 1e-3 * max(abs(swept[1]), 1e-12), swept

    @pytest.mark.parametrize("metric", ["cka", "rv", "rsa", "distance_correlation"])
    def test_the_true_delay_realigns_a_delayed_copy(self, metric):
        """cka, rv, rsa and dcor are 1 for identical representations; lag -3 undoes the delay."""
        x, y = self._delayed_copy()
        v = np.asarray(oa.jrsa(x, y, metric=metric, lag=[0, -3], stats=False).value, float)
        assert v[1] > 0.9 and v[0] < 0.7, v

    def test_a_paired_metric_still_lags_the_last_axis(self):
        rng = np.random.default_rng(1)
        a = rng.standard_normal((3, 80))
        b = np.roll(a, 2, axis=-1)
        v = float(oa.jrsa(a, b, metric="pearson", lag=-2, stats=False).value)
        ref = float(oa.jrsa(*self._overlap(a, b, -2, -1), metric="pearson", stats=False).value)
        np.testing.assert_allclose(v, ref, rtol=1e-12)
        np.testing.assert_allclose(v, 1.0, rtol=1e-12)


class TestLagComparesTheOverlapOnly:
    """The lag was circular, so a lag wrapped the end of each series onto its start: on a
    trended series the realigning lag of a delayed copy gave r well below 1."""

    @staticmethod
    def _trended_delay(n=300, delay=10):
        rng = np.random.default_rng(3)
        x = np.linspace(0.0, 5.0, n) + 0.2 * rng.standard_normal(n)
        y = np.concatenate([rng.standard_normal(delay), x[:-delay]])   # y[t] = x[t - delay]
        return x, y

    def test_the_realigning_lag_of_a_trended_delayed_copy_is_exactly_one(self):
        x, y = self._trended_delay()
        res = oa.jrsa(x, y, metric="pearson", lag=-10, stats=False)
        np.testing.assert_allclose(float(res.value), 1.0, rtol=1e-12)
        assert res.execution["n_overlap"] == 290

    def test_several_lags_record_each_overlap(self):
        x, y = self._trended_delay()
        res = oa.jrsa(x, y, metric="pearson", lag=[0, -10, 7], stats=False)
        assert res.execution["n_overlap"] == [300, 290, 293]

    @pytest.mark.parametrize("lag", [-4, 4])
    @pytest.mark.parametrize("metric, null, axis", [
        ("pearson", "circular_shift", -1), ("cka", "iid", 0),
    ])
    def test_the_null_runs_on_the_shortened_series(self, metric, null, axis, lag):
        rng = np.random.default_rng(4)
        shape = (120,) if axis == -1 else (120, 5)
        x = rng.standard_normal(shape)
        y = np.roll(x, 4, axis=0 if axis == 0 else -1) + rng.standard_normal(shape)
        lagged = oa.jrsa(x, y, metric=metric, lag=lag, permutations=99, rng=0, null=null,
                         return_null=True)
        a, b = (x[:-4], y[4:]) if lag < 0 else (x[4:], y[:-4])
        by_hand = oa.jrsa(a, b, metric=metric, permutations=99, rng=0, null=null,
                          return_null=True)
        np.testing.assert_allclose(float(lagged.value), float(by_hand.value), rtol=1e-12)
        np.testing.assert_allclose(lagged.null_distribution, by_hand.null_distribution, rtol=1e-12)
        assert float(lagged.p) == float(by_hand.p)

    def test_the_bootstrap_runs_on_the_shortened_series(self):
        rng = np.random.default_rng(5)
        x = rng.standard_normal(120)
        y = np.roll(x, 4) + rng.standard_normal(120)
        lagged = oa.jrsa(x, y, metric="pearson", lag=-4, permutations=0, bootstrap=19,
                         null="iid", rng=0)
        by_hand = oa.jrsa(x[:-4], y[4:], metric="pearson", permutations=0, bootstrap=19,
                          null="iid", rng=0)
        np.testing.assert_allclose(lagged.ci, by_hand.ci, rtol=1e-12)

    @pytest.mark.parametrize("lag", [np.int64(-4), np.array(-4), np.array([-4]), [np.int64(-4)]])
    def test_a_numpy_integer_lag_is_one_lag(self, lag):
        x, y = self._trended_delay()
        res = oa.jrsa(x, y, metric="pearson", lag=lag, stats=False)
        ref = oa.jrsa(x, y, metric="pearson", lag=-4, stats=False)
        np.testing.assert_allclose(float(res.value), float(ref.value), rtol=1e-12)
        assert res.execution["n_overlap"] == 296

    @pytest.mark.parametrize("lag", [50, -50, 80])
    def test_a_lag_with_no_overlap_raises(self, lag):
        x = np.random.default_rng(0).standard_normal(50)
        with pytest.raises(ValueError, match="no overlap"):
            oa.jrsa(x, x, metric="pearson", lag=lag, stats=False)


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

    # The guard must reject typos without disabling real options. Every option a metric
    # declares, with two values that must give different output. Passing the keyword check is not evidence the option is read: the histogram TE
    # declared `k` and never used it, so k=1, 2 and 5 all returned 0.040111.
    _OPTIONS = {
        ("rsa", "rdm_metric"): ("correlation", "euclidean"),
        ("hsic", "sigma"): (0.5, 4.0),
        ("mutual_information", "bins"): (4, 16),
        ("transfer_entropy_histogram_nats", "bins"): (4, 10),
        ("granger_ssr_ftest", "max_lag"): (1, 5),
        ("phase_slope", "fs"): (100.0, 200.0),
        ("phase_slope", "nperseg"): (64, 256),
        ("phase_slope", "noverlap"): (0, 48),
        ("phase_slope", "bands"): ((5.0, 15.0), (20.0, 40.0)),
        ("phase_slope", "jackknife"): (True, False),
    }
    # `kernel` has one legal value; any other raises, which is tested where cka is.
    _SINGLE_VALUED = {("cka", "kernel")}

    def test_the_table_covers_every_declared_option(self):
        from jnwb.jrsa import _METRIC_DISPATCH, _metric_kwargs

        declared = {(m, k) for m, fn in _METRIC_DISPATCH.items() for k in _metric_kwargs(fn)}
        assert declared == set(self._OPTIONS) | self._SINGLE_VALUED

    @pytest.mark.parametrize("metric,option", sorted(_OPTIONS))
    def test_every_declared_option_changes_the_output(self, metric, option):
        rng = np.random.default_rng(3)
        if metric in ("rsa", "hsic"):
            x1, x2 = rng.standard_normal((30, 8)), rng.standard_normal((30, 8))
        else:
            x2 = rng.normal(size=2000)
            x1 = 0.6 * np.r_[0.0, 0.0, 0.0, x2[:-3]] + rng.normal(size=2000)
        base = {"fs": 100.0, "nperseg": 128, "bands": (10.0, 30.0)} if metric == "phase_slope" else {}
        out = []
        for value in self._OPTIONS[(metric, option)]:
            kw = {**base, option: value}
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                r = oa.jrsa(x1, x2, metric=metric, permutations=0, **kw)
            out.append(np.array([np.nan if a is None else float(np.ravel(a)[0])
                                 for a in (r.value, r.statistic, r.p)]))
        assert not np.array_equal(out[0], out[1], equal_nan=True), (
            f"{metric}: {option} passed the keyword check and changed nothing: {out}")

    def test_the_histogram_te_refuses_a_history_length(self):
        with pytest.raises(TypeError, match=r"\['k'\]"):
            oa.jrsa(np.arange(50.0), np.arange(50.0)[::-1],
                    metric="transfer_entropy_histogram_nats", k=2, stats=False)

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
        # null='iid': the paired metrics' default rotates the 6-sample last axis, whose six
        # rotations can all exceed the observed value and pin p at 1.0 at any count.
        low = float(np.atleast_1d(oa.jrsa(a, b, metric=metric, permutations=10, random_state=2,
                                          null="iid").p)[0])
        high = float(np.atleast_1d(oa.jrsa(a, b, metric=metric, permutations=2000,
                                           random_state=2, null="iid").p)[0])
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
        # Per lag, on each lag's own sign. The fixture needs lags of both signs: with one
        # sign throughout, taking every lag's side from the first lag would pass too.
        g = np.random.default_rng(11)
        s = g.normal(size=400)
        u = -s + 1.5 * np.roll(s, 2) + 0.3 * g.normal(size=400)
        base = oa.jrsa(s, u, metric="pearson", lag=[0, 1, 2, 3], rng=0, **kw)
        v, pb = np.asarray(base.value), np.asarray(base.p)
        assert (v > 0).any() and (v < 0).any(), v
        for alt, on_side in (("greater", v > 0), ("less", v < 0)):
            lagged = oa.jrsa(s, u, metric="pearson", lag=[0, 1, 2, 3], alternative=alt, rng=0,
                             **kw)
            np.testing.assert_allclose(np.asarray(lagged.p),
                                       np.where(on_side, pb / 2, 1 - pb / 2), rtol=1e-12)

    def test_an_upper_tail_f_test_refuses_a_one_sided_request(self):
        """The SSR F-test p is upper-tail already; halving it would be wrong."""
        with pytest.raises(ValueError, match="granger_ssr_ftest") as err:
            oa.jrsa(self.x1, self.x2, metric="granger_ssr_ftest", alternative="less",
                    permutations=0)
        # The message says why, not only that.
        assert "upper-tail F-test" in str(err.value) and "halving" in str(err.value)


def test_sliding_windows_are_refused_and_the_loop_is_named():
    """`sliding=True` was accepted and ignored: value and p were identical to
    `sliding=False`, with no warning. It is refused, and the message names the loop."""
    rng = np.random.default_rng(0)
    x1 = rng.normal(size=(6, 8, 40))
    x2 = x1 + rng.normal(size=(6, 8, 40))
    with pytest.raises(NotImplementedError, match=r"sliding=True.*window=\(s, s \+ w\)"):
        oa.jrsa(x1, x2, metric="pearson", window=(10, 30), sliding=True, stats=False)
    oa.jrsa(x1, x2, metric="pearson", window=(10, 30), sliding=False, stats=False)


class TestDirectedMetricsStateTheDirectionTheyMeasure:
    """The SSR F-test and histogram TE measure x2 -> x1, the reverse of
    `connectivity.granger(X, Y).x_to_y`, while `phase_slope` is positive when x1 leads.
    No public text said so; the docstring now does, and this holds it to the numbers."""

    @staticmethod
    def _lead_lag():
        rng = np.random.default_rng(0)
        lead = rng.normal(size=2000)
        # One sample: the histogram TE conditions on one past sample of each series, so a
        # longer lead would leave it nothing to see in either direction.
        lag = 0.9 * np.r_[0.0, lead[:-1]] + 0.4 * rng.normal(size=2000)
        return lead, lag

    @pytest.mark.parametrize("metric", ["granger_ssr_ftest", "transfer_entropy_histogram_nats"])
    def test_the_x2_to_x1_metrics_are_large_when_x2_leads(self, metric):
        lead, lag = self._lead_lag()
        x2_leads = float(oa.jrsa(lag, lead, metric=metric, stats=False).value)
        x1_leads = float(oa.jrsa(lead, lag, metric=metric, stats=False).value)
        assert x2_leads > 2 * x1_leads, (x2_leads, x1_leads)
        g = oa.granger(lead, lag)
        assert g.x_to_y > g.y_to_x, "connectivity.granger no longer reads x_to_y as X -> Y"

    def test_phase_slope_is_positive_when_x1_leads(self):
        lead, lag = self._lead_lag()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            assert float(oa.jrsa(lead, lag, metric="phase_slope", stats=False).value) > 0

    def test_the_docstring_says_so(self):
        doc = " ".join(oa.jrsa.__doc__.split())
        assert ("``granger_ssr_ftest`` and ``transfer_entropy_histogram_nats`` measure "
                "x2 -> x1") in doc
        assert "``phase_slope`` is positive when x1 leads x2" in doc


class TestTimeAxisNullKeepsAutocorrelation:
    """The permutation null of the paired metrics shuffled single time samples, which are
    exchangeable only when independent. On independent AR(1) pairs at phi = 0.9 it rejected
    at p <= 0.05 for 0.505 of pairs (pearson, n = 300, 200 pairs). Since 0.2.6.1 the
    default is a circular shift, and `null='iid'` must be named."""

    @staticmethod
    def _ar1_pairs(n_pairs, n=200, phi=0.9, seed=0, burn=100):
        from scipy.signal import lfilter

        e = np.random.default_rng(seed).standard_normal((n_pairs, 2, n + burn))
        return lfilter([1.0], [1.0, -phi], e, axis=-1)[..., burn:]

    # cosine runs the same null as pearson at a tenth of the cost, which buys enough pairs
    # to separate 0.05 from 0.08; zero-mean stationary series make it a correlation.
    @pytest.mark.parametrize("null, block_len, rejects_too_often", [
        (None, None, False),
        ("block", 50, False),
        ("iid", None, True),
    ])
    def test_false_positive_rate_on_independent_ar1_pairs(self, null, block_len, rejects_too_often):
        ps = np.array([
            float(oa.jrsa(x, y, metric="cosine", permutations=39, rng=i, correction="none",
                          null=null, block_len=block_len).p)
            for i, (x, y) in enumerate(self._ar1_pairs(300))
        ])
        fpr = float(np.mean(ps <= 0.05))
        assert (fpr > 0.08) is rejects_too_often, f"null={null!r}: FPR {fpr:.3f}"

    def test_the_default_still_detects_coupled_series(self):
        """A null that never rejects would pass the false-positive test."""
        x, y = self._ar1_pairs(1, n=300, seed=1)[0]
        res = oa.jrsa(x, 2.0 * x + y, metric="pearson", permutations=199, rng=0)  # r = 0.73
        assert float(res.p) <= 0.01, float(res.p)

    @pytest.mark.parametrize("metric", ["pearson", "cka"])
    def test_the_block_null_detects_coupled_series(self, metric):
        """The block false-positive test above also passes for a null that never rejects:
        one that keeps the blocks in their original order returns the observed value on
        every draw and p = 1. Ten 30-sample blocks of a coupled AR(1) pair must reject."""
        if metric == "pearson":
            x, y = self._ar1_pairs(1, n=300, seed=1)[0]
            y = 2.0 * x + y                                   # r = 0.73
        else:
            a, b = self._ar1_pairs(4, n=300, seed=2).transpose(1, 2, 0)  # (time, units)
            x, y = a, a + 0.5 * b                             # cka = 0.75
        res = oa.jrsa(x, y, metric=metric, permutations=199, rng=0,
                      null="block", block_len=30, return_null=True)
        assert float(res.p) <= 0.01, float(res.p)
        assert len(np.unique(np.round(res.null_distribution, 12))) > 50

    def test_a_short_axis_cannot_report_p_below_one_in_n(self):
        """x2 = x1 puts the observed value above every rotation, so the exact p is 1/6 on a
        6-sample axis. Drawing shifts from 1..n-1 left the identity out and reported
        1 / (permutations + 1) = 0.001."""
        x = np.random.default_rng(0).standard_normal(6)
        p = float(oa.jrsa(x, x, metric="cosine", permutations=999, rng=0).p)
        assert 0.12 < p < 0.22, p

    def test_the_default_rotates_the_time_axis_of_every_row(self):
        """(trials, time): the shift runs along time, the same for every row. Rotating the
        two-row trial axis instead leaves two distinct surrogates and p near 1/2."""
        pairs = self._ar1_pairs(2, n=300, seed=1)
        x, y = pairs[:, 0], pairs[:, 1]
        res = oa.jrsa(x, 2.0 * x + y, metric="pearson", permutations=199, rng=0, return_null=True)
        assert float(res.p) <= 0.01, float(res.p)
        assert len(np.unique(np.round(res.null_distribution, 12))) > 50

    def test_every_row_gets_the_same_shift(self):
        """Two identical rows against themselves: under one shift per draw each surrogate
        equals the 1-D correlation of the row with one rotation of itself. A shift drawn
        per row pairs different rotations and lands off that set."""
        a = np.random.default_rng(2).standard_normal(30)
        rotations = np.array([np.corrcoef(a, np.roll(a, k))[0, 1] for k in range(30)])
        x = np.vstack([a, a])
        null = oa.jrsa(x, x, metric="pearson", permutations=99, rng=0,
                       return_null=True).null_distribution
        off = np.min(np.abs(null[:, None] - rotations[None, :]), axis=1)
        assert np.max(off) < 1e-9, np.max(off)

    def test_row_metrics_warn_on_the_default_null_and_iid_silences_it(self):
        """cka and rv on (time, units) with the default axis-0 permutation rejected every
        one of 40 independent AR(1) pairs; the default stays for 0.2.6.1 and warns."""
        rng = np.random.default_rng(5)
        a, b = rng.normal(size=(40, 6)), rng.normal(size=(40, 6))
        with pytest.warns(UserWarning, match="null='circular_shift' or null='block'") as rec:
            default = oa.jrsa(a, b, metric="cka", permutations=49, bootstrap=20, rng=3)
        ours = [r for r in rec if "null='circular_shift' or null='block'" in str(r.message)]
        assert len(ours) == 1 and ours[0].filename == __file__, [r.filename for r in ours]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            named = oa.jrsa(a, b, metric="cka", permutations=49, bootstrap=20, rng=3, null="iid")
            oa.jrsa(a, b, metric="cka", stats=False)          # no null formed, no warning
            oa.jrsa(a, b, metric="cka", permutations=0)
            oa.jrsa(a[:, 0], b[:, 0], metric="pearson", permutations=19, rng=0)
        assert float(named.p) == float(default.p)
        np.testing.assert_array_equal(named.ci, default.ci)

    @pytest.mark.parametrize("null, block_len", [
        (None, None), ("circular_shift", None), ("block", 10),
    ])
    def test_a_paired_metric_bootstrap_needs_iid_named(self, null, block_len):
        x, y = self._ar1_pairs(1, n=60)[0]
        with pytest.raises(ValueError, match="bootstrap.*null='iid'"):
            oa.jrsa(x, y, metric="pearson", bootstrap=20, rng=0, null=null, block_len=block_len)

    def test_a_paired_metric_bootstrap_with_iid_named_keeps_the_0_2_6_numbers(self):
        # Values computed by jnwb 0.2.6 with the same call minus `null`. The interval differs
        # across BLAS builds in the last bits; a different resampling scheme differs far more.
        rng = np.random.default_rng(0)
        x = rng.normal(size=80)
        y = 0.5 * x + rng.normal(size=80)
        res = oa.jrsa(x, y, metric="pearson", permutations=99, bootstrap=200, rng=3, null="iid")
        assert float(res.p) == 0.01
        np.testing.assert_allclose(res.ci, [0.20568213024810308, 0.5753485564085722],
                                   rtol=1e-12, atol=0)

    @pytest.mark.parametrize("metric, kwargs, recorded", [
        ("pearson", {}, "circular_shift"),
        ("pearson", {"null": "iid"}, "iid"),
        ("pearson", {"null": "block", "block_len": 10}, "block"),
        ("rsa", {}, "iid"),
        ("pearson", {"stats": False}, None),
    ])
    def test_the_result_records_the_scheme_that_ran(self, metric, kwargs, recorded):
        x, y = self._ar1_pairs(1, n=60)[0]
        if metric == "rsa":
            x, y = x.reshape(12, 5), y.reshape(12, 5)
        res = oa.jrsa(x, y, metric=metric, permutations=9, rng=0, **kwargs)
        assert res.execution["null"] == recorded
        assert res.execution["null_block_len"] == kwargs.get("block_len")
        assert res.parameters["null"] == kwargs.get("null")

    @pytest.mark.parametrize("kwargs", [
        {"null": "shuffle"},
        {"null": "IID"},
        {"null": "block"},
        {"null": "block", "block_len": 0},
        {"null": "block", "block_len": 2.5},
        {"null": "circular_shift", "block_len": 10},
        {"block_len": 10},
        {"null": "block", "block_len": 31},
    ])
    def test_an_invalid_null_raises(self, kwargs):
        x, y = self._ar1_pairs(1, n=60)[0]
        with pytest.raises(ValueError, match="null|block"):
            oa.jrsa(x, y, metric="pearson", permutations=9, rng=0, **kwargs)
