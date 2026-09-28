"""The two shuffle p-values, held to an oracle instead of to an incidental guard.

05-54 proposed that collapsing both `shuffle_pvalue_paired` and `shuffle_pvalue_unpaired`
to the floor `1/(n_shuffles + 1)` survives the suite. It does not: the mutant dies against
`tests/test_api_consistency.py::TestAlternativeAndAlpha::test_case_and_whitespace_are_folded_not_ignored`,
through its closing `assert plain[1] != two[1]`. That is a case-folding test, and a folding
inequality is not evidence that a p-value is a rank. The coverage is real and incidental,
and it disappears the moment that guard is relaxed.

The oracles here are independent of the estimators under test. For the paired statistic,
`exact_sign_flip` enumerates all 2^N sign flips for N <= 20 and is itself pinned against a
separate enumeration in `tests/test_statistics.py`. For the unpaired statistic, this file
enumerates every C(n_a + n_b, n_a) label assignment directly.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from jnwb.statistics import exact_sign_flip, shuffle_pvalue_paired, shuffle_pvalue_unpaired

N_SHUFFLES = 4999
FLOOR = 1.0 / (N_SHUFFLES + 1.0)


def _paired_pair(effect: float, n: int = 14, seed: int = 3):
    """A paired sample with a known mean difference and enough spread to leave a rank."""
    rng = np.random.default_rng(seed)
    b = rng.normal(0.0, 1.0, size=n)
    a = b + effect + rng.normal(0.0, 1.0, size=n)
    return a, b


def _exhaustive_unpaired_p(a, b, alternative: str) -> float:
    """Every label assignment, enumerated. C(10, 5) = 252 splits."""
    pooled = np.concatenate([a, b])
    n_a = len(a)
    obs = float(np.mean(a) - np.mean(b))
    total = np.sum(pooled)
    stats = []
    for idx in itertools.combinations(range(len(pooled)), n_a):
        left = pooled[list(idx)].sum()
        stats.append(left / n_a - (total - left) / (len(pooled) - n_a))
    null = np.asarray(stats)
    if alternative == "greater":
        return float(np.mean(null >= obs))
    if alternative == "less":
        return float(np.mean(null <= obs))
    return float(np.mean(np.abs(null) >= abs(obs)))


class TestThePairedPValueIsTheRankItClaimsToBe:
    @pytest.mark.parametrize("alternative", ["two-sided", "greater"])
    def test_it_approximates_the_exact_sign_flip_enumeration(self, alternative: str):
        a, b = _paired_pair(effect=0.2)
        obs, p = shuffle_pvalue_paired(
            a, b, n_shuffles=N_SHUFFLES, rng=np.random.default_rng(11),
            alternative=alternative,
        )
        exact_obs, exact_p, _ = exact_sign_flip(a - b, alternative=alternative)

        assert obs == pytest.approx(exact_obs)
        # Monte Carlo over 4999 draws of a 2^14 null: three standard errors is ~0.02 here.
        assert p == pytest.approx(exact_p, abs=0.02), (p, exact_p)

    def test_the_value_is_neither_the_floor_nor_one(self):
        """A collapse to `1/(n+1)` and a collapse to 1 are both constants; a rank is not."""
        a, b = _paired_pair(effect=0.2)
        _, p = shuffle_pvalue_paired(
            a, b, n_shuffles=N_SHUFFLES, rng=np.random.default_rng(11), alternative="greater"
        )
        assert FLOOR < p < 1.0, p

    def test_a_larger_effect_gives_a_smaller_p(self):
        """The ordering a rank must have, which no constant can reproduce."""
        ps = []
        for effect in (0.0, 0.2, 0.4, 0.8):
            a, b = _paired_pair(effect=effect)
            _, p = shuffle_pvalue_paired(
                a, b, n_shuffles=N_SHUFFLES, rng=np.random.default_rng(11),
                alternative="greater",
            )
            ps.append(p)
        assert ps == sorted(ps, reverse=True), ps
        assert ps[0] > 0.1 and ps[-1] == pytest.approx(FLOOR), ps


class TestTheUnpairedPValueIsTheRankItClaimsToBe:
    @staticmethod
    def _groups(separation: float):
        return (
            np.array([0.0, 1.0, 2.0, 3.0, 4.0]) + separation,
            np.array([0.5, 1.5, 2.5, 3.5, 4.5]),
        )

    @pytest.mark.parametrize("alternative", ["two-sided", "greater"])
    def test_it_approximates_an_exhaustive_label_enumeration(self, alternative: str):
        a, b = self._groups(separation=1.5)
        obs, p = shuffle_pvalue_unpaired(
            a, b, n_shuffles=N_SHUFFLES, rng=np.random.default_rng(5),
            alternative=alternative,
        )
        exact = _exhaustive_unpaired_p(a, b, alternative)

        assert obs == pytest.approx(float(np.mean(a) - np.mean(b)))
        assert p == pytest.approx(exact, abs=0.02), (p, exact)

    def test_the_value_is_neither_the_floor_nor_one(self):
        a, b = self._groups(separation=1.5)
        _, p = shuffle_pvalue_unpaired(
            a, b, n_shuffles=N_SHUFFLES, rng=np.random.default_rng(5), alternative="greater"
        )
        assert FLOOR < p < 1.0, p

    def test_a_larger_separation_gives_a_smaller_p(self):
        ps = []
        for separation in (0.0, 1.0, 2.0, 10.0):
            a, b = self._groups(separation)
            _, p = shuffle_pvalue_unpaired(
                a, b, n_shuffles=N_SHUFFLES, rng=np.random.default_rng(5),
                alternative="greater",
            )
            ps.append(p)
        assert ps == sorted(ps, reverse=True), ps
        assert ps[0] > 0.1, ps


class TestADrawThatReproducesTheObservedSplitCountsItself:
    """Recomputing the observed split in shuffled order can land an ulp below the observed
    statistic. With these values it does for both the unpaired mean difference (after the
    pooled values are centred) and the identity sign flip, and without the tie width the
    p-value falls well below the exact one (unpaired) or to its floor (paired). Separated
    groups make the exact p a count of two draws. The unpaired cases also run at a common
    offset of 1e9, where a statistic taken from the uncentred values drops p to its floor."""

    X = np.array([14.9, 18.9, 19.3])
    Y = np.array([4.8, 5.9, 4.6])
    D = np.array([1.53, 2.55, 2.07, 2.9, 1.42])

    @pytest.mark.parametrize("offset", [0.0, 1e9])
    @pytest.mark.parametrize("alternative, exact", [("two-sided", 0.1), ("greater", 0.05)])
    def test_unpaired(self, alternative: str, exact: float, offset: float):
        _, p = shuffle_pvalue_unpaired(
            self.X + offset, self.Y + offset, N_SHUFFLES, np.random.default_rng(0),
            alternative=alternative,
        )
        assert p == pytest.approx(exact, abs=0.02), (p, exact)
        _, p_neg = shuffle_pvalue_unpaired(
            -self.X - offset, -self.Y - offset, N_SHUFFLES, np.random.default_rng(0),
            alternative="less" if alternative == "greater" else alternative,
        )
        assert p_neg == pytest.approx(exact, abs=0.02), (p_neg, exact)

    @pytest.mark.parametrize("offset", [0.0, 1e9])
    def test_permutation_test(self, offset: float):
        from jnwb import StatisticalAnalysis

        p = StatisticalAnalysis.permutation_test(
            self.X + offset, self.Y + offset, n_permutations=N_SHUFFLES, rng=0
        )["pval"]
        assert p == pytest.approx(0.1, abs=0.02), p

    @pytest.mark.parametrize("alternative, exact", [("two-sided", 2 / 32), ("greater", 1 / 32)])
    def test_paired(self, alternative: str, exact: float):
        _, p = shuffle_pvalue_paired(
            self.D, np.zeros_like(self.D), N_SHUFFLES, np.random.default_rng(0), alternative=alternative
        )
        assert p == pytest.approx(exact, abs=0.015), (p, exact)
        _, p_neg = shuffle_pvalue_paired(
            -self.D, np.zeros_like(self.D), N_SHUFFLES, np.random.default_rng(0),
            alternative="less" if alternative == "greater" else alternative,
        )
        assert p_neg == pytest.approx(exact, abs=0.015), (p_neg, exact)


class TestACommonOffsetLeavesThePValueUnchanged:
    """A difference of means does not see a common offset, so neither may the tie width.
    Scaled by the raw values, the width at an offset of 1e9 times the spread counted
    genuinely different splits as ties: p 0.538 against 0.487 at offset 0."""

    @staticmethod
    def _p(name: str, offset: float) -> float:
        from jnwb import StatisticalAnalysis

        rng = np.random.default_rng(1000)
        x = rng.normal(1.5 / np.sqrt(1000), 1.0, 1000) + offset
        y = rng.normal(0.0, 1.0, 1000) + offset
        if name == "permutation_test":
            return StatisticalAnalysis.permutation_test(x, y, n_permutations=1000, rng=0)["pval"]
        func = shuffle_pvalue_unpaired if name == "unpaired" else shuffle_pvalue_paired
        return func(x, y, 1000, np.random.default_rng(0))[1]

    @pytest.mark.parametrize("name", ["unpaired", "permutation_test", "paired"])
    def test_offset_1e9(self, name: str):
        p0 = self._p(name, 0.0)
        assert 0.05 < p0 < 0.95, p0
        assert self._p(name, 1e9) == p0


class TestTheTieRuleCountsRoundOffAndNothingWider:
    """The one rule every null above and below counts draws with."""

    def test_a_draw_an_ulp_below_counts_and_one_a_part_in_1e12_below_does_not(self):
        from jnwb.permutation import _count_at_least_as_extreme

        obs = 0.3
        null = np.array([np.nextafter(obs, 0.0), obs * (1 - 1e-12), obs])
        assert _count_at_least_as_extreme(null, obs, "greater") == 2
        assert _count_at_least_as_extreme(-null, -obs, "less") == 2
        assert _count_at_least_as_extreme(-null, obs, "two-sided") == 2

    def test_the_sorted_count_for_every_element_is_the_rule_applied_to_each(self):
        from jnwb.permutation import _count_at_least_as_extreme, _count_each_at_least_as_extreme

        rng = np.random.default_rng(2)
        for _ in range(100):
            v = rng.integers(-3, 4, size=int(rng.integers(1, 40))) / 3.0
            v = np.where(rng.random(v.size) < 0.4, np.nextafter(v, np.inf), v)
            for atol in (0.0, 1e-9):
                expected = [_count_at_least_as_extreme(v, x, "greater", atol=atol) for x in v]
                assert _count_each_at_least_as_extreme(v, atol=atol).tolist() == expected

    def test_untied_data_count_what_a_bare_comparison_counts(self):
        from jnwb.permutation import _count_at_least_as_extreme

        rng = np.random.default_rng(0)
        for _ in range(200):
            null = rng.normal(size=1000)
            obs = float(rng.normal())
            assert _count_at_least_as_extreme(null, obs, "greater") == int(np.sum(null >= obs))
            assert _count_at_least_as_extreme(null, obs, "two-sided") == int(
                np.sum(np.abs(null) >= abs(obs))
            )


class TestEveryNullCountsTheDrawsThatReproduceTheObservedStatistic:
    """Each null below has draws that reproduce the observed statistic with its terms summed
    in another order. Counted with a bare comparison, the ones landing an ulp below were
    skipped and p came out too small; each case is held to an exact p. Where every draw
    reproduces the statistic the exact p is 1.0 and is compared exactly."""

    def test_jrsa_with_ties_in_x1(self):
        # x1 is binary, so r is increasing in the sum of x2 over x1 == 1. The observed sum is
        # 4 + 5 + 6 = 15, the largest, reached by 3! * 3! of the 720 orderings: p = 0.05.
        from jnwb.jrsa import jrsa

        x1 = np.array([0.0, 0, 0, 1, 1, 1])
        x2 = np.array([2.0, 1, 3, 4, 5, 6])
        sums = [sum(c) for c in itertools.combinations(x2, 3)]
        exact = float(np.mean(np.array(sums) >= 15))
        assert exact == 0.05
        res = jrsa(x1, x2, metric="pearson", permutations=N_SHUFFLES, alternative="greater",
                   rng=0, correction="none", null="iid")
        assert float(res.p) == pytest.approx(exact, abs=0.01), float(res.p)

    def test_shuffle_r2_ci_with_tied_scores(self):
        # Scores k / 3 with integer k: r^2 is increasing in |8 * S1 - 4 * K|, S1 the sum of
        # k over the four positions labelled 1 and K the total, so the exact p is a count
        # over the 70 placements in integers.
        from jnwb.statistics import shuffle_r2_ci

        k = np.array([2, 3, 2, 2, 0, 2, 2, 2])
        y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        dev = [abs(8 * sum(c) - 4 * k.sum()) for c in itertools.combinations(k, 4)]
        obs_dev = abs(8 * k[4:].sum() - 4 * k.sum())
        exact = float(np.mean(np.array(dev) >= obs_dev))
        p = shuffle_r2_ci(y, k / 3.0, n_shuffle=N_SHUFFLES, rng=0)["p_val"]
        assert p == pytest.approx(exact, abs=0.01), (p, exact)

    def test_cross_modal_comparison_with_periodic_spikes(self):
        # Period 10 and eleven searched lags: every circular shift of the spike train puts
        # some searched lag in phase, so every draw reaches the observed |r| = 1.
        from jnwb.statistics import cross_modal_comparison

        spikes = (np.arange(400) % 10 == 0).astype(float)
        tfr = 3.0 * np.roll(spikes, 2) + 1.0
        res = cross_modal_comparison(tfr, spikes, lag_range_ms=(-50, 50), bin_ms=10,
                                     n_permutations=500, rng=0)
        assert res["lag_corrected_pvalue"] == 1.0

    def test_cluster_permutation_test_when_a_row_of_x_equals_a_row_of_y(self):
        # One point, so the cluster statistic is the Welch t where |t| > 2 and the null is
        # every split of the eight rows. Swapping the two equal rows reproduces a split.
        from scipy import stats as sps

        from jnwb.statistics import cluster_permutation_test

        X = np.array([[3.8], [2.5], [4.1], [2.5]])
        Y = np.array([[1.9], [-0.1], [1.4], [2.5]])
        pooled = np.concatenate([X, Y])[:, 0]
        obs = abs(sps.ttest_ind(X[:, 0], Y[:, 0], equal_var=False).statistic)
        null = []
        for idx in itertools.combinations(range(8), 4):
            rest = [i for i in range(8) if i not in idx]
            t = abs(sps.ttest_ind(pooled[list(idx)], pooled[rest], equal_var=False).statistic)
            null.append(t if t > 2.0 else 0.0)
        exact = float(np.mean(np.array(null) >= obs * (1 - 1e-9)))
        res = cluster_permutation_test(X, Y, n_permutations=N_SHUFFLES,
                                       rng=np.random.default_rng(0))
        p = res["clusters"][0]["p_value"]
        assert p == pytest.approx(exact, abs=0.01), (p, exact)

    @staticmethod
    def _one_side_identical(n_times: int, identical: str):
        rng = np.random.default_rng(1)
        common = rng.normal(size=n_times)
        varied = rng.normal(size=(8, n_times)) + 0.8 * np.roll(common, -1)[None, :]
        same = np.tile(common, (8, 1))
        return (same, varied) if identical == "x" else (varied, same)

    def test_granger_when_the_target_trials_are_identical(self):
        # A trial permutation of X pairs the same eight trials with the same Y trial.
        from jnwb.connectivity import granger

        x, y = self._one_side_identical(200, identical="y")
        assert granger(x, y, order=2, n_surrogates=200, rng=0).p_x_to_y == 1.0

    def test_granger_spectral_when_the_target_trials_are_identical(self):
        from jnwb.connectivity import granger_spectral

        x, y = self._one_side_identical(200, identical="y")
        res = granger_spectral(x, y, fs=100.0, order=2, n_surrogates=100, rng=0,
                               bands={"a": (5.0, 20.0), "b": (20.0, 45.0)})
        assert res.p_x_to_y == 1.0
        assert [band["p_surrogate"] for band in res.per_band.values()] == [1.0, 1.0]

    @staticmethod
    def _uncoupled_identical_target(n_trials=40, coupling=0.0, n_times=2000):
        # Weak coupling, so GC sits near zero while its logs stay of order one: a draw that
        # reproduces it rounds at the scale of the log ratio, far beyond 100 eps of GC.
        rng = np.random.default_rng(n_trials + n_times)
        common = rng.normal(size=n_times)
        x = rng.normal(size=(n_trials, n_times)) + coupling * np.roll(common, -1)[None, :]
        return x, np.tile(common, (n_trials, 1))

    def test_granger_when_the_coupling_is_zero(self):
        # A width relative to GC alone gave p_x_to_y 0.0198 here, where the exact p is 1;
        # at coupling 0.01 and 200 samples, 100 eps of |x_to_y| + |y_to_x| gave p_net 0.733.
        from jnwb.connectivity import granger

        x, y = self._uncoupled_identical_target()
        assert granger(x, y, order=2, n_surrogates=100, rng=0).p_x_to_y == 1.0
        assert granger(y, x, order=2, n_surrogates=100, rng=0).p_y_to_x == 1.0
        x, y = self._uncoupled_identical_target(coupling=0.01, n_times=200)
        assert granger(x, y, order=2, n_surrogates=100, rng=0).p_net == 1.0

    def test_granger_spectral_when_the_coupling_is_zero(self):
        from jnwb.connectivity import granger_spectral

        x, y = self._uncoupled_identical_target()
        res = granger_spectral(x, y, fs=100.0, order=2, n_surrogates=100, rng=0,
                               bands={"lo": (2.0, 20.0), "hi": (20.0, 45.0)})
        assert res.p_x_to_y == 1.0
        assert [band["p_surrogate"] for band in res.per_band.values()] == [1.0, 1.0]
        swapped = granger_spectral(y, x, fs=100.0, order=2, n_surrogates=100, rng=0)
        assert swapped.p_y_to_x == 1.0

    def test_phase_slope_index_when_the_source_trials_are_identical(self):
        # The surrogate permutes the trials of Y against one repeated X trial.
        from jnwb.connectivity import phase_slope_index

        x, y = self._one_side_identical(256, identical="x")
        assert phase_slope_index(x, y, fs=100.0, n_surrogates=200, rng=0).p_net == 1.0
        res = phase_slope_index(x, y, fs=100.0, n_surrogates=200, rng=0,
                                bands={"a": (5.0, 20.0), "b": (20.0, 45.0)})
        assert res.p_net == 1.0
        assert [band["p_surrogate"] for band in res.per_band.values()] == [1.0, 1.0]

    def test_phase_slope_index_when_the_slope_cancels_to_round_off(self):
        # Y pairs x + h with x - h, so the summed cross-spectrum is real and every PSI is
        # zero in exact arithmetic while each trial's term is not. A trial permutation only
        # reorders that sum: the exact p is 1. A width relative to the observed value alone
        # gave 0.085 for the full band and 0.035, 0.05 and 0.095 for the bands and total.
        from jnwb.connectivity import phase_slope_index

        rng = np.random.default_rng(0)
        common = rng.normal(size=512)
        h = rng.normal(size=(4, 512))
        x, y = np.tile(common, (8, 1)), np.vstack([common + h, common - h])
        full = phase_slope_index(x, y, fs=100.0, n_surrogates=200, rng=0)
        assert abs(full.net) < 1e-15
        assert full.p_net == 1.0
        res = phase_slope_index(x, y, fs=100.0, n_surrogates=200, rng=0,
                                bands={"a": (5.0, 20.0), "b": (20.0, 45.0)})
        assert res.p_net == 1.0
        assert [band["p_surrogate"] for band in res.per_band.values()] == [1.0, 1.0]

    def test_phase_slope_index_widths_scale_with_the_bin_pair_count(self, monkeypatch):
        # Measured round-off sits near 1e-16, below 100 eps whatever the scale, so the
        # scale is pinned on a statistic whose draws fall short by a set amount: 5 * 100 eps
        # in band a and 10 * 100 eps in the total, both inside 100 eps per bin pair and
        # outside 100 eps.
        from jnwb import connectivity
        from jnwb.permutation import _TIE_RTOL

        rng = np.random.default_rng(0)
        x, y = rng.normal(size=(8, 512)), rng.normal(size=(8, 512))
        bands = {"a": (5.0, 20.0), "b": (20.0, 45.0)}
        shortfall = 5 * _TIE_RTOL
        observed = {}

        def statistic(fx, fy, idx, weights=None):
            first = int(idx[0])
            if first not in observed:
                observed[first] = 0.3 if not observed else -0.2
                return observed[first]
            return observed[first] - shortfall

        monkeypatch.setattr(connectivity, "_psi_from_spectra", statistic)
        res = connectivity.phase_slope_index(x, y, fs=100.0, n_surrogates=50, rng=0,
                                             bands=bands, jackknife=False)
        assert min(band["n_freq_bins"] for band in res.per_band.values()) > 11
        assert res.per_band["a"]["p_surrogate"] == 1.0
        assert res.p_net == 1.0

    def test_xflip_channel_permutation_at_six_channels(self):
        # Exact p over all 720 channel orders, a draw tying the observed contrast when it
        # agrees to nine digits; permutations inside the two blocks reorder the sums.
        from jnwb.laminar import _optimal_contiguous_partition, xflip

        rng = np.random.default_rng(96)
        a = rng.uniform(-0.2, 0.9, size=(6, 6))
        corr = (a + a.T) / 2
        corr[:3, :3] += 0.5
        corr[3:, 3:] += 0.5
        corr = np.clip(corr, -1.0, 1.0)
        np.fill_diagonal(corr, 1.0)
        obs = _optimal_contiguous_partition(corr, 2, 2)[2]
        qs = np.array([
            _optimal_contiguous_partition(corr[np.ix_(p, p)], 2, 2)[2]
            for p in map(list, itertools.permutations(range(6)))
        ])
        exact = float(np.mean(qs >= obs - 1e-9 * abs(obs)))
        res = xflip(corr, n_surrogates=N_SHUFFLES, rng=0, is_corr_matrix=True)
        assert res.p_values["omnibus"] == pytest.approx(exact, abs=0.015), (
            res.p_values["omnibus"], exact)
        # The boundary p compares the contrast of the two blocks beside the cut.
        from jnwb.laminar import _compute_contrast

        (b,) = res.boundaries
        lbl = (np.arange(6) >= b).astype(int)
        local = np.array([
            _compute_contrast(corr[np.ix_(p, p)], lbl)
            for p in map(list, itertools.permutations(range(6)))
        ])
        local_obs = _compute_contrast(corr, lbl)
        exact_b = float(np.mean(local >= local_obs - 1e-9 * abs(local_obs)))
        assert res.p_values[f"boundary_{b}"] == pytest.approx(exact_b, abs=0.015), (
            res.p_values[f"boundary_{b}"], exact_b)

    def test_xflip_when_the_contrast_cancels_to_round_off(self):
        # Within and between means are equal in exact arithmetic, so Q is 5.6e-17 of residue
        # and the draws that tie it differ from it by round-off of a correlation, not of Q:
        # only the absolute floor of the width counts them. Exact p over all 720 orders,
        # a tie meaning agreement to 1e-12 absolute: 0.911 omnibus, 0.600 at the boundary,
        # against 0.800 and 0.522 with a width relative to Q alone.
        from jnwb.laminar import _compute_contrast, _optimal_contiguous_partition, xflip

        corr = np.array([
            [1.0, 0.3, 0.7, 0.7, 0.7, 0.7],
            [0.3, 1.0, 0.1, 0.3, 0.7, 0.1],
            [0.7, 0.1, 1.0, 0.7, 0.3, 0.7],
            [0.7, 0.3, 0.7, 1.0, 0.7, 0.1],
            [0.7, 0.7, 0.3, 0.7, 1.0, 0.7],
            [0.7, 0.1, 0.7, 0.1, 0.7, 1.0],
        ])
        orders = [list(p) for p in itertools.permutations(range(6))]
        obs = _optimal_contiguous_partition(corr, 2, 2)[2]
        assert 0 < abs(obs) < 1e-15
        qs = np.array([_optimal_contiguous_partition(corr[np.ix_(p, p)], 2, 2)[2] for p in orders])
        exact = float(np.mean(qs >= obs - 1e-12))
        res = xflip(corr, n_surrogates=N_SHUFFLES, rng=0, is_corr_matrix=True)
        assert res.p_values["omnibus"] == pytest.approx(exact, abs=0.015), (
            res.p_values["omnibus"], exact)
        (b,) = res.boundaries
        lbl = (np.arange(6) >= b).astype(int)
        local = np.array([_compute_contrast(corr[np.ix_(p, p)], lbl) for p in orders])
        exact_b = float(np.mean(local >= _compute_contrast(corr, lbl) - 1e-12))
        assert res.p_values[f"boundary_{b}"] == pytest.approx(exact_b, abs=0.015), (
            res.p_values[f"boundary_{b}"], exact_b)


class TestTheIncidentalGuardIsStillThere:
    """If the folding test's guard is ever relaxed, this file is what remains."""

    def test_the_folding_test_still_carries_the_inequality_it_carried(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "tests" / "test_api_consistency.py").read_text(
            encoding="utf-8"
        )
        assert "assert plain[1] != two[1]" in source, (
            "the guard that incidentally covered the p-value collapse is gone; the tests "
            "above are now the only thing holding it"
        )
