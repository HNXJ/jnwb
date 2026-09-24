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
    statistic. With these values it does for both the unpaired mean difference and the
    identity sign flip, and the p-value fell to a third of the exact one (unpaired) or to
    its floor (paired). Separated groups make the exact p a count of two draws."""

    X = np.array([17.9, 10.5, 12.3])
    Y = np.array([7.0, 5.7, 5.1])
    D = np.array([1.53, 2.55, 2.07, 2.9, 1.42])

    @pytest.mark.parametrize("alternative, exact", [("two-sided", 0.1), ("greater", 0.05)])
    def test_unpaired(self, alternative: str, exact: float):
        _, p = shuffle_pvalue_unpaired(
            self.X, self.Y, N_SHUFFLES, np.random.default_rng(0), alternative=alternative
        )
        assert p == pytest.approx(exact, abs=0.02), (p, exact)
        _, p_neg = shuffle_pvalue_unpaired(
            -self.X, -self.Y, N_SHUFFLES, np.random.default_rng(0),
            alternative="less" if alternative == "greater" else alternative,
        )
        assert p_neg == pytest.approx(exact, abs=0.02), (p_neg, exact)

    def test_permutation_test(self):
        from jnwb import StatisticalAnalysis

        p = StatisticalAnalysis.permutation_test(self.X, self.Y, n_permutations=N_SHUFFLES, rng=0)["pval"]
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
