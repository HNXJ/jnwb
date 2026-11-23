"""Who controls the randomness, and where the seed is written down.

Five functions declared `rng: Optional[np.random.Generator] = None` and then ran
`np.random.default_rng(42)` -- `default_rng(0)` in `cluster_permutation_test` -- when the
caller left it out. `None` reads as "fresh randomness", so two calls a caller believed
were independent shared a null distribution and agreed to the last digit. Reproduced at
`statistics.py:206, 720, 993, 1033, 1571` (the audit cited `206, 680, 953, 993, 1483`;
the mechanism and the five functions are exactly as reported, the line numbers were
stale). Two forwarders, `compare_groups` and the `StatisticalAnalysis.exact_sign_flip`
staticmethod, defaulted to `None` and passed it down, so they are repaired too -- without
them, omitting `rng` would have started drawing fresh entropy.

`nested_cv_linear_svm(X, labels, n_splits)` had no randomness parameter and
hardcoded `random_state=42` at `decoding.py:86, 91, 113, 124`, so nobody could ask whether
a decoding accuracy survived a different partition of the same trials.

The repair must not move a single published number at the default, which
`TestTheDefaultIsTheSeedThatWasHiding` checks by calling each function both ways.
"""

from __future__ import annotations

import inspect
import re

import numpy as np
import pytest

import jnwb
from jnwb import statistics as S
from jnwb._rng import DEFAULT_SEED, resolve_rng, sklearn_random_state
from jnwb.decoding import nested_cv_linear_svm
from jnwb.statistics import StatisticalAnalysis as SA
from jnwb.statistics import StatisticalAnalysis
from jnwb.statistics import (cluster_permutation_test,
                             paired_fire_prob_test)
from pathlib import Path
from jnwb._rng import Default
import ast
import sys
import types
import pandas as pd
from jnwb._rng import RNGLike
from jnwb.analyzers import PopulationAnalyzer, UnitAnalyzer
from jnwb.connectivity._granger import _net_surrogate_p, granger
from jnwb._rng import REQUIRED, resolve_seed_alias


@pytest.fixture
def ab():
    rng = np.random.default_rng(1)
    return rng.normal(0.4, 1.0, 25), rng.normal(0.0, 1.0, 25)


@pytest.fixture
def decodable():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(60, 8))
    y = np.array([0, 1] * 30)
    X[y == 1] += 0.45
    return X, y


# Every randomized entry point repaired here, with its own visible default.
SEEDED = (
    ("exact_sign_flip", S.exact_sign_flip, DEFAULT_SEED),
    ("StatisticalAnalysis.exact_sign_flip", SA.exact_sign_flip, DEFAULT_SEED),
    ("bootstrap_ci", SA.bootstrap_ci, DEFAULT_SEED),
    ("permutation_test", SA.permutation_test, DEFAULT_SEED),
    ("compare_groups", SA.compare_groups, DEFAULT_SEED),
    ("_bootstrap_mean_diff_ci", SA._bootstrap_mean_diff_ci, DEFAULT_SEED),
    ("cluster_permutation_test", S.cluster_permutation_test, 0),
    ("nested_cv_linear_svm", nested_cv_linear_svm, DEFAULT_SEED),
)


class TestNoRandomizedFunctionHidesItsSeed:
    """Read straight off the signature: no randomized function hides its seed."""

    @pytest.mark.parametrize("name,fn,expected", SEEDED, ids=[s[0] for s in SEEDED])
    def test_the_default_seed_is_in_the_signature(self, name, fn, expected):
        param = inspect.signature(fn).parameters["rng"]
        assert param.default is not None, (
            f"{name}: rng defaults to None, which reads as fresh randomness"
        )
        assert param.default == expected, f"{name}: rng default is {param.default!r}"

    def test_no_seed_literal_survives_in_a_function_body(self):
        """The repair is the absence of this pattern, so grep for it rather than trusting
        that the eight above are all of them."""
        from tests._sources import read_sources, unread_by

        for within in ("jnwb.statistics", "jnwb.decoding"):
            label = f"seed-literals {within}"
            for source in read_sources(label, within):
                hits = re.findall(r"default_rng\((\d+)\)", source.text)
                assert not hits, f"{source.path.name}: seed literal(s) {hits} still inside a body"
            assert unread_by(label, within) == []

    def test_the_named_constant_is_the_seed_that_was_hiding(self):
        assert DEFAULT_SEED == 42

    def test_cluster_permutation_test_keeps_its_own_different_default(self):
        """It hid `default_rng(0)`, not 42. Unifying the two would change published
        cluster p-values, so the repair exposes each at the value it already had."""
        assert inspect.signature(S.cluster_permutation_test).parameters["rng"].default == 0


class TestTheDefaultIsTheSeedThatWasHiding:
    """Calling with the default and calling with the old literal must agree exactly."""

    def test_exact_sign_flip(self, ab):
        a, b = ab
        assert S.exact_sign_flip(a - b) == S.exact_sign_flip(a - b, rng=42)

    def test_bootstrap_ci(self, ab):
        a, _ = ab
        assert SA.bootstrap_ci(a) == SA.bootstrap_ci(a, rng=42)

    def test_permutation_test(self, ab):
        a, b = ab
        assert SA.permutation_test(a, b, n_permutations=499) == SA.permutation_test(
            a, b, n_permutations=499, rng=42
        )

    def test_cluster_permutation_test(self, ab):
        a, b = ab
        one = S.cluster_permutation_test(a.reshape(5, 5), b.reshape(5, 5), n_permutations=100)
        two = S.cluster_permutation_test(a.reshape(5, 5), b.reshape(5, 5),
                                         n_permutations=100, rng=0)
        np.testing.assert_array_equal(one["max_null_stats"], two["max_null_stats"])

    def test_nested_cv_linear_svm(self, decodable):
        X, y = decodable
        one = nested_cv_linear_svm(X, y, n_splits=3)
        two = nested_cv_linear_svm(X, y, n_splits=3, rng=42)
        assert one["accuracy"] == two["accuracy"]
        np.testing.assert_array_equal(one["fold_accuracies"], two["fold_accuracies"])

    def test_an_int_seed_reaches_sklearn_unchanged(self):
        """If the int were used to seed a Generator and redrawn, the default would
        reproduce different folds than the hardcoded `random_state=42` did."""
        assert sklearn_random_state(42, func_name="t") == 42
        assert sklearn_random_state(7, func_name="t") == 7


class TestNoneNowMeansFreshEntropy:
    """It used to mean "seed 42", which is the defect. Continuous outputs only: an
    accuracy is quantized and two independent partitions can coincide."""

    def test_two_bootstrap_calls_with_none_disagree(self, ab):
        a, _ = ab
        one = SA.bootstrap_ci(a, rng=None)["bootstrap_ci"]
        two = SA.bootstrap_ci(a, rng=None)["bootstrap_ci"]
        assert one != two

    def test_two_permutation_calls_with_none_use_different_nulls(self, ab):
        a, b = ab
        seen = {SA.permutation_test(a, b, n_permutations=999, rng=None)["pval"]
                for _ in range(6)}
        assert len(seen) > 1, "rng=None still reproduces one fixed null"

    def test_but_omitting_the_argument_is_still_reproducible(self, ab):
        a, _ = ab
        assert SA.bootstrap_ci(a) == SA.bootstrap_ci(a)

    def test_sklearn_random_state_draws_none_from_fresh_entropy(self):
        """Passing None on let scikit-learn draw from NumPy's global RandomState."""
        before = np.random.get_state()[1].copy()
        seed = sklearn_random_state(None, func_name="t")
        assert isinstance(seed, int)
        np.testing.assert_array_equal(np.random.get_state()[1], before)
        assert len({sklearn_random_state(None, func_name="t") for _ in range(5)}) > 1


class TestOneSpellingAcceptsASeedOrAGenerator:
    """The package was split between `rng: Generator` and `seed: int`."""

    def test_an_int_and_an_equivalent_generator_agree(self, ab):
        a, _ = ab
        seeded, passed = SA.bootstrap_ci(a, rng=7), SA.bootstrap_ci(a, rng=np.random.default_rng(7))
        # The numbers agree; only the seed can be reported, a Generator's position cannot.
        assert (seeded.pop("surrogate_seed_entropy"), passed.pop("surrogate_seed_entropy")) == \
               (7, None)
        assert seeded == passed

    def test_a_generator_is_used_in_place_not_restarted(self, ab):
        """Passing one Generator to two calls must advance a single stream, or a caller
        looping over calls would draw the same null every time."""
        a, _ = ab
        gen = np.random.default_rng(3)
        first = SA.bootstrap_ci(a, rng=gen)["bootstrap_ci"]
        second = SA.bootstrap_ci(a, rng=gen)["bootstrap_ci"]
        assert first != second

    @pytest.mark.parametrize("bad", ["42", 3.5, [1], {"seed": 1}])
    def test_a_wrong_type_is_refused_and_names_the_caller(self, bad, ab):
        a, _ = ab
        with pytest.raises(TypeError, match="bootstrap_ci: rng must be an int seed"):
            SA.bootstrap_ci(a, rng=bad)

    def test_a_float_seed_is_refused_rather_than_truncated(self):
        with pytest.raises(TypeError):
            resolve_rng(2.7, func_name="t")

    def test_a_bool_is_not_an_int_seed_here(self):
        """`True` is an `int` in Python; accepting it would silently mean seed 1."""
        with pytest.raises(TypeError):
            resolve_rng(True, func_name="t")
        with pytest.raises(TypeError):
            sklearn_random_state(False, func_name="t")

    def test_resolve_rng_returns_a_generator_for_each_accepted_type(self):
        gen = np.random.default_rng(5)
        assert resolve_rng(gen, func_name="t") is gen
        assert isinstance(resolve_rng(5, func_name="t"), np.random.Generator)
        assert isinstance(resolve_rng(None, func_name="t"), np.random.Generator)
        assert isinstance(resolve_rng(np.int64(5), func_name="t"), np.random.Generator)

    def test_equal_int_seeds_give_equal_streams(self):
        assert resolve_rng(11, func_name="t").normal(size=5).tolist() == \
               resolve_rng(11, func_name="t").normal(size=5).tolist()


class TestNestedCvPartitionIsControllable:
    """Two different seeds give two different fold assignments."""

    def test_two_seeds_give_different_folds(self, decodable):
        X, y = decodable
        folds = {tuple(np.round(nested_cv_linear_svm(X, y, n_splits=3, rng=s)
                                ["fold_accuracies"], 10))
                 for s in (0, 1, 2, 3, 7, 42)}
        assert len(folds) > 1, "the partition does not respond to rng at all"

    def test_the_same_seed_repeats_exactly(self, decodable):
        X, y = decodable
        a = nested_cv_linear_svm(X, y, n_splits=3, rng=13)
        b = nested_cv_linear_svm(X, y, n_splits=3, rng=13)
        np.testing.assert_array_equal(a["fold_accuracies"], b["fold_accuracies"])
        assert a["accuracy"] == b["accuracy"]

    def test_a_generator_is_accepted_too(self, decodable):
        X, y = decodable
        res = nested_cv_linear_svm(X, y, n_splits=3, rng=np.random.default_rng(4))
        assert np.isfinite(res["accuracy"])

    def test_two_generators_give_different_folds(self, decodable):
        """A Generator is turned into an int seed for scikit-learn; a conversion that
        ignored the Generator would give every one the same folds."""
        X, y = decodable
        folds = {tuple(np.round(nested_cv_linear_svm(
            X, y, n_splits=3, rng=np.random.default_rng(s))["fold_accuracies"], 10))
                 for s in (0, 1, 2, 3, 7, 42)}
        assert len(folds) > 1, "the partition does not respond to the Generator"

    def test_two_generators_give_different_permutation_plans(self):
        labels, groups = [0, 1] * 8, [0] * 8 + [1] * 8
        a, b = (jnwb.build_permutation_plan(labels, groups, n_permutations=3,
                                            rng=np.random.default_rng(s)) for s in (1, 2))
        assert a["seed"] != b["seed"]
        assert list(a["draw_manifest"]["label_digest"]) != list(b["draw_manifest"]["label_digest"])

    def test_rng_is_a_parameter_at_all(self):
        """The signature was `(X, labels, n_splits)`."""
        assert "rng" in inspect.signature(nested_cv_linear_svm).parameters

    def test_the_insufficient_trials_branch_still_returns_its_status(self):
        """Adding a parameter must not disturb the early return."""
        X = np.random.default_rng(0).normal(size=(3, 4))
        res = nested_cv_linear_svm(X, np.array([0, 1, 1]), n_splits=3)
        assert res["status"] == "insufficient_trials_for_cv"
        assert np.isnan(res["accuracy"])


# The directed estimators resolved `rng` through a private helper that mapped
# `None` to seed 0 (recorded as `seed=None`), refused a Generator and truncated 2.7 to 2.
_DG = np.random.default_rng(5)
_DX = _DG.normal(size=(2, 400))
_DY = 0.1 * np.roll(_DX, 2, axis=1) + _DG.normal(size=(2, 400))  # weak, so no p sits at its floor
DIRECTED = {
    "granger": lambda rng: jnwb.granger(_DX, _DY, order=2, n_surrogates=29, rng=rng),
    "granger_spectral": lambda rng: jnwb.granger_spectral(
        _DX, _DY, fs=100.0, order=2, n_freqs=32, n_surrogates=29, rng=rng,
        bands={"a": (2.0, 12.0), "b": (14.0, 26.0), "c": (28.0, 45.0)}),
    "phase_slope_index": lambda rng: jnwb.phase_slope_index(
        _DX, _DY, fs=100.0, bands={"a": (5.0, 14.0), "b": (16.0, 30.0)}, n_surrogates=29,
        rng=rng),
    "transfer_entropy": lambda rng: jnwb.transfer_entropy(_DX, _DY, n_surrogates=29, rng=rng),
}


def _null_of(res):
    """Every surrogate-derived number the result carries. The coupling p of phase_slope_index
    is one: at few surrogates the per-band p values sit on a coarse grid and can agree across
    seeds, so the coupling p is what tells two nulls apart."""
    return (res.p_x_to_y, res.p_y_to_x, res.p_net,
            tuple(sorted((k, v.get("p_surrogate")) for k, v in (res.per_band or {}).items())),
            res.diagnostics.get("p_coupling_surrogate"),
            tuple(sorted((k, v) for k, v in res.diagnostics.get("surrogates", {}).items())))


@pytest.mark.parametrize("name", sorted(DIRECTED))
class TestDirectedEstimatorsHonourRng:
    def test_none_draws_a_fresh_null_each_call(self, name):
        runs = [DIRECTED[name](None) for _ in range(4)]
        entropies = {r.params["surrogate_seed_entropy"] for r in runs}
        assert len(entropies) == 4 and all(isinstance(e, int) for e in entropies)
        assert len({_null_of(r) for r in runs}) > 1, "rng=None still draws one fixed null"

    def test_the_recorded_entropy_reproduces_the_null(self, name):
        first = DIRECTED[name](None)
        again = DIRECTED[name](first.params["surrogate_seed_entropy"])
        assert _null_of(again) == _null_of(first)

    def test_an_int_seed_is_recorded_and_keeps_its_stream(self, name, monkeypatch):
        """An int seed draws `default_rng(seed)`, the stream it has always drawn: the null
        of a `default_rng(0)` Generator consumed in place, as the helper did before."""
        res = DIRECTED[name](0)
        assert res.params["seed"] == 0 and res.params["surrogate_seed_entropy"] == 0
        import jnwb._rng
        import jnwb.connectivity

        # patched where the estimator looks the name up
        monkeypatch.setattr(inspect.getmodule(getattr(jnwb, name)), "_surrogate_rng",
                            jnwb._rng.surrogate_rng)
        assert _null_of(res) == _null_of(DIRECTED[name](np.random.default_rng(0)))

    def test_a_generator_records_the_child_seed_that_reproduces_p(self, name):
        """A Generator gives up one draw; the surrogates run on it and the result records it,
        so re-running from the recorded seed alone reproduces every p."""
        gen = np.random.default_rng(7)
        first, second = DIRECTED[name](gen), DIRECTED[name](gen)
        ref = np.random.default_rng(7)
        child = [int(ref.integers(0, 2**63 - 1)) for _ in range(2)]
        assert first.params["surrogate_seed_entropy"] == child[0]
        assert second.params["surrogate_seed_entropy"] == child[1]
        again = DIRECTED[name](first.params["surrogate_seed_entropy"])
        assert _null_of(again) == _null_of(first)
        assert _null_of(second) != _null_of(first)

    def test_a_float_is_refused_rather_than_truncated(self, name):
        with pytest.raises(TypeError, match=f"{name}: rng must be an int seed"):
            DIRECTED[name](2.7)


class TestStatisticsRNG:
    def test_unchanged_historical_default_determinism(self):
        data = np.array([1.2, 2.5, 3.1, 4.8, 5.2, 6.0])
        res1 = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=500)
        res2 = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=500)
        assert res1["bootstrap_ci"] == res2["bootstrap_ci"]
        assert res1["bootstrap_std"] == res2["bootstrap_std"]

        res_perm1 = StatisticalAnalysis.permutation_test(data, data + 1.0, n_permutations=500)
        res_perm2 = StatisticalAnalysis.permutation_test(data, data + 1.0, n_permutations=500)
        assert res_perm1["pval"] == res_perm2["pval"]

    def test_global_rng_state_untouched(self):
        state_before = np.random.get_state()

        data = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=100)
        StatisticalAnalysis.permutation_test(data, data * 1.5, n_permutations=100)
        StatisticalAnalysis.compare_groups(data, data + 2.0, n_bootstrap=100)

        state_after = np.random.get_state()
        assert state_before[0] == state_after[0]
        assert np.array_equal(state_before[1], state_after[1])
        assert state_before[2] == state_after[2]

    def test_custom_independent_generators(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        rng1 = np.random.default_rng(100)
        rng2 = np.random.default_rng(200)

        res1 = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=1000, rng=rng1)
        res2 = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=1000, rng=rng2)
        assert res1["bootstrap_std"] != res2["bootstrap_std"]

        res3 = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=1000, rng=np.random.default_rng(100))
        assert res1["bootstrap_std"] == res3["bootstrap_std"]

    def test_invalid_rng_type_raises_type_error(self):
        """An int for `rng` moved from "rejected" to "a seed".

        This used to assert that `bootstrap_ci(data, rng=42)` raises, while the same
        function ran `np.random.default_rng(42)` whenever `rng` was omitted. The strict
        path was the explicit one and the lax path was the default one, which is backwards;
        and the module-level `exact_sign_flip` already accepted `int | Generator | None`,
        so the siblings disagreed about the same argument. What must still raise is a type
        that names no stream at all.
        """
        data = np.array([1.0, 2.0, 3.0])
        for bad in ("not_an_rng", 3.5, [1, 2], {"seed": 1}):
            with pytest.raises(TypeError, match="rng must be an int seed"):
                StatisticalAnalysis.bootstrap_ci(data, rng=bad)
            with pytest.raises(TypeError, match="rng must be an int seed"):
                StatisticalAnalysis.permutation_test(data, data, rng=bad)
            with pytest.raises(TypeError, match="rng must be an int seed"):
                StatisticalAnalysis.compare_groups(data, data, rng=bad)

    def test_an_int_is_a_seed_and_agrees_with_the_generator_it_names(self):
        data = np.array([1.0, 2.0, 3.0])
        seeded = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=500, rng=42)
        passed = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=500,
                                                  rng=np.random.default_rng(42))
        # The numbers agree; only the seed can be reported, a Generator's position cannot.
        assert (seeded.pop("surrogate_seed_entropy"), passed.pop("surrogate_seed_entropy")) == \
               (42, None)
        assert seeded == passed


class TestRngReportedInResult:
    """Fact S11: a result reports the randomness it ran on."""

    def test_permutation_test_reports_its_seed_and_none_for_a_generator(self):
        g1 = np.array([0.0, 0.1, 0.2, 0.3])
        g2 = np.array([1.0, 1.1, 1.2, 1.3])
        assert StatisticalAnalysis.permutation_test(
            g1, g2, n_permutations=50, rng=1)["surrogate_seed_entropy"] == 1
        gen = np.random.default_rng(1)
        assert StatisticalAnalysis.permutation_test(
            g1, g2, n_permutations=50, rng=gen)["surrogate_seed_entropy"] is None

    def test_bootstrap_ci_and_compare_groups_report_their_seed(self):
        rng = np.random.default_rng(4)
        data = rng.normal(size=30)
        assert StatisticalAnalysis.bootstrap_ci(
            data, n_bootstrap=50, rng=2)["surrogate_seed_entropy"] == 2
        res = StatisticalAnalysis.compare_groups(data, rng.normal(size=30), rng=2)
        assert res["surrogate_seed_entropy"] == 2

    def test_cluster_permutation_test_reports_its_seed_and_scheme(self):
        rng = np.random.default_rng(0)
        X, Y = rng.normal(size=(8, 6)), rng.normal(size=(8, 6))
        res = cluster_permutation_test(X, Y, n_permutations=10, rng=3)
        assert res["surrogate_seed_entropy"] == 3
        assert res["scheme"] == "global"

    def test_paired_fire_prob_test_reports_its_seed_and_sign_flip(self):
        rng = np.random.default_rng(6)
        target = rng.random(40) < 0.6
        null = rng.random(40) < 0.4
        res = paired_fire_prob_test(target, null, n_shuffles=50, n_bootstrap=50, rng=5)
        assert np.isfinite(res["p_value_fire_shuffle"]), "the fixture must draw a null"
        assert res["scheme"] == "sign_flip"
        assert res["surrogate_seed_entropy"] == 5


"""The documented RNG convention, held against the live signatures.

Two convention texts prescribed `rng: Optional[Union[np.random.Generator, int]] = None`.
Measured against the package: 19 of 23 `rng` parameters on the public API deliberately do
not present `None`, because putting the seed in the signature **was** the repair --
five functions declared `rng=None` and then ran `np.random.default_rng(42)` with no way for
a caller to learn the seed, so two calls a caller believed were independent shared one null.
`jnwb/_rng.py` records it. The prose was stale; the signatures are correct.

The prose edit alone has a shelf life, so this module pins the two to each other.

**Independence.** The documented form is stated here as a literal (`OLD_FORM`,
`PRESENTS_NONE`, `FRESH_ENTROPY`) and separately parsed off the prose. Neither is derived
from `inspect.signature`. A check that read its expected value out of the same introspection
it validates would agree with itself under every corruption, which is the defect class this
cycle keeps producing.

**The one deviation, and its repair.** `cross_area_coherence` used to
declare `rng=None` and resolve it to `np.random.SeedSequence(42)`. It was never a
survivor -- the defect was a *silent* fixed seed, and this function always disclosed the
entropy through `surrogate_seed_entropy` in its return value -- but a caller still could not
read the stream off the signature, which is where this repository's convention puts it. The
signature now says `rng: RNGLike = DEFAULT_SEED`. A bare call is unchanged, because
`default_rng(42)` and `default_rng(SeedSequence(42))` are the same stream; an explicit
`rng=None` now means fresh OS entropy, as it does everywhere else in the package.

**Why these tests exist beside the silent-fixed-seed tests earlier in this file.** Those tests
could not see the deviation, for three independent reasons, each closed by a different
assertion here -- and each still open for the next one:

1. Its `SEEDED` tuple is hand-maintained and never named `cross_area_coherence`, so its
   signature check never covered it. Closed by `test_exactly_these_three_present_none`,
   which enumerates every `rng` parameter from `jnwb.__all__` rather than from a list a
   contributor must remember to extend, and by `test_the_walk_reaches_the_rng_parameters`,
   which fails if that enumeration ever collapses.
2. Its body scan reads only `statistics.py` and `decoding.py`, and this function lives in
   `spectral.py`. Closed by the same walk, which is module-agnostic: it reaches whatever
   the public API exports, wherever it is defined.
3. Its regex `default_rng\\((\\d+)\\)` cannot match `default_rng(seed_sequence)` however many
   modules it scans. Closed by
   `test_cross_area_coherence_draws_the_stream_its_signature_advertises`, which establishes
   the stream by *calling the function*, so no spelling of the source evades it.

**What would make each check below pass while the rule it names is violated.**

- The public-symbol walk yields nothing, so "every rng parameter conforms" is vacuous.
  Held by `test_the_walk_reaches_the_rng_parameters`, which requires the known count.
- The prose scan reads an empty or missing file and finds no stale form. Held by
  `test_the_prose_files_are_readable_and_nonempty`.
- The stale-form matcher never matches anything, so no text can ever fail it. Held by
  `test_the_stale_form_matcher_can_fire`, which runs it against the string it hunts.
- The exception list is read as a tolerance ("at most three may present None"), so a new
  `rng=None` slips in. Held by `test_exactly_these_three_present_none`, an equality: under
  a subset assertion in either direction the drift survives.
- `cross_area_coherence` regresses to `rng=None` and nothing notices, because the
  equality above is edited to re-admit it. Held by
  `test_cross_area_coherence_shows_its_seed_in_the_signature`, which names the function
  directly and reads its default, so re-admitting it to `PRESENTS_NONE` does not silence
  this one; and by
  `test_cross_area_coherence_draws_the_stream_its_signature_advertises`, which would fail
  on the numbers even if every signature assertion were deleted.
- A name is added to `FRESH_ENTROPY` and is reported as verified without ever being
  called, because the probe dispatch falls through to another function. Held by
  `test_every_fresh_entropy_function_has_its_own_probe`. This one is not hypothetical:
  the first version of this module had that fallback, and the mutant that added
  `cross_area_coherence` to `FRESH_ENTROPY` survived until the dispatch was made explicit.
"""



REPO_ROOT = Path(__file__).resolve().parents[1]


CONTRIBUTING = REPO_ROOT / ".github" / "CONTRIBUTING.md"


SPEC_PAGE = REPO_ROOT / "docs" / "10_operation_specifications.md"


PROSE_FILES = (CONTRIBUTING, SPEC_PAGE)



# --- the documented convention, stated here and nowhere derived from introspection ------

#: The form both texts used to prescribe. Re-adopting it reintroduces the silent fixed seed.
OLD_FORM = re.compile(
    r"rng:\s*Optional\[\s*Union\[\s*(?:np\.random\.)?Generator\s*,\s*int\s*\]\s*\]\s*=\s*None"
)



#: Every public `rng` parameter whose default presents `None` to the caller.
PRESENTS_NONE = frozenset({"cross_modal_comparison", "jrsa", "xflip"})



#: Of those, the ones where `None` resolves to fresh OS entropy, which is the contract.
#: These are now the same set: after the repair no public default presents `None` for any
#: other reason, and the two names are kept apart because they mean different things and
#: a future divergence should be visible rather than an edit to one frozenset.
FRESH_ENTROPY = frozenset({"cross_modal_comparison", "jrsa", "xflip"})



#: The key `cross_area_coherence` discloses the entropy it used through. Still populated
#: after the repair -- the disclosure was the one part of the old behaviour worth keeping.
DISCLOSURE_KEY = "surrogate_seed_entropy"



#: The seed `cross_area_coherence` has always used, now visible in its signature.
COHERENCE_DEFAULT_SEED = 42



EXPECTED_TOTAL = 35




def _public_callables():
    for name in sorted(jnwb.__all__):
        obj = getattr(jnwb, name, None)
        if obj is None:
            continue
        if inspect.isclass(obj):
            for mname, meth in sorted(vars(obj).items()):
                if mname.startswith("_"):
                    continue
                fn = meth.__func__ if isinstance(meth, (staticmethod, classmethod)) else meth
                if callable(fn):
                    yield f"{name}.{mname}", fn
        elif callable(obj):
            yield name, obj




def _rng_parameters():
    """(qualname, default) for every `rng` parameter on the public API."""
    out = []
    for qualname, fn in _public_callables():
        try:
            sig = inspect.signature(fn)
        except ValueError:
            continue
        param = sig.parameters.get("rng")
        if param is not None:
            out.append((qualname, param.default))
    return out




def _presents_none(default) -> bool:
    """What `inspect.signature` shows the caller.

    `jnwb._rng.Default` reports the value it stands for, so `Default(None)` renders as
    `None` in the signature without being `None`. A reader sees `rng=None` either way, so
    the convention is about what is rendered.
    """
    return default is not inspect.Parameter.empty and repr(default) == "None"




def _coherence_inputs():
    seed = np.random.default_rng(13)
    return seed.normal(size=4000), seed.normal(size=4000)




COHERENCE_KW = dict(fs=1000.0, n_surrogates=10, freq_bands="canonical")




# --- the checks that keep the checks honest ---------------------------------------------


def test_the_walk_reaches_the_rng_parameters():
    rows = _rng_parameters()
    assert len(rows) == EXPECTED_TOTAL, (
        f"expected {EXPECTED_TOTAL} rng parameters on the public API, walked {len(rows)}. "
        "If the API genuinely changed, update EXPECTED_TOTAL; if the walk broke, every "
        "other assertion in this module just became vacuous."
    )




def test_the_prose_files_are_readable_and_nonempty():
    for path in PROSE_FILES:
        assert path.is_file(), f"{path.name} is named as a convention text and is gone"
        assert len(path.read_text(encoding="utf-8")) > 500, f"{path.name} is empty or truncated"




def test_the_stale_form_matcher_can_fire():
    """A matcher that cannot match makes every prose check below trivially green."""
    assert OLD_FORM.search("rng: Optional[Union[np.random.Generator, int]] = None")
    assert OLD_FORM.search("rng: Optional[Union[Generator, int]] = None")
    assert not OLD_FORM.search("rng: RNGLike = DEFAULT_SEED")




# --- acceptance 1: no convention text prescribes a form the package does not use --------


@pytest.mark.parametrize("path", PROSE_FILES, ids=lambda p: p.name)
def test_no_convention_text_prescribes_the_retired_form(path):
    text = path.read_text(encoding="utf-8")
    hits = [
        f"line {i}: {ln.strip()}"
        for i, ln in enumerate(text.splitlines(), 1)
        if OLD_FORM.search(ln) and "testing.synth" not in ln
    ]
    assert not hits, (
        f"{path.name} still prescribes `rng: Optional[Union[Generator, int]] = None`, the form "
        f"that the silent-seed repair removed: {hits}"
    )




# --- acceptance 2 and 3: documented exception set == live signatures --------------------


def test_exactly_these_three_present_none():
    """Equality, not a ceiling. A tolerance in either direction lets drift through, and
    this enumeration is what covers the functions a hand-maintained list would omit."""
    live = {q for q, d in _rng_parameters() if _presents_none(d)}
    assert live == set(PRESENTS_NONE), (
        f"the set of public rng parameters presenting None has moved.\n"
        f"  documented: {sorted(PRESENTS_NONE)}\n"
        f"  live      : {sorted(live)}\n"
        "Update this module and both convention texts together, or the prose is stale again."
    )




def test_the_others_show_the_seed_they_will_use():
    others = [(q, d) for q, d in _rng_parameters() if not _presents_none(d)]
    assert len(others) == EXPECTED_TOTAL - len(PRESENTS_NONE)
    for qualname, default in others:
        if default is inspect.Parameter.empty:
            continue  # no default at all: the caller must choose, which is also explicit
        value = default.value if isinstance(default, Default) else default
        assert isinstance(value, (int, np.integer)) or repr(default) == "<required>", (
            f"{qualname}: rng default {default!r} neither shows a seed nor demands one"
        )




def test_the_spec_page_names_every_function_whose_rng_default_is_none():
    """Parsed off the prose, compared against the literals above -- two independent sources."""
    text = SPEC_PAGE.read_text(encoding="utf-8")
    expected = set(FRESH_ENTROPY)
    named = {n for n in expected if f"`{n}`" in text}
    assert named == expected, (
        "the RNG section of the specification page no longer names every function whose "
        f"rng default is None; missing {sorted(expected - named)}"
    )




# --- acceptance 2: each exception checked, not asserted ---------------------------------


def _probe_xflip():
    # Thirty surrogates put each p-value on a 1/31 grid, and two fresh draws coincide on
    # about 3% of pairs (measured: 30 distinct p-value sets in 40 calls). Up to three
    # further calls are compared, so a false alarm needs four coincident draws, while a
    # fixed seed still repeats on every call.
    data = np.random.default_rng(11).normal(size=(12, 3000))
    first = dict(jnwb.xflip(data, n_surrogates=30, rng=None).p_values)
    for _ in range(3):
        later = dict(jnwb.xflip(data, n_surrogates=30, rng=None).p_values)
        if later != first:
            break
    return first, later




def _probe_jrsa():
    seed = np.random.default_rng(11)
    a, b = seed.normal(size=(40, 6)), seed.normal(size=(40, 6))
    # These p-values fall on about thirty likely values, and two fresh draws coincide on
    # about 4% of pairs (measured: 32 distinct in 200 calls; seen on CI). Up to three
    # further calls are compared, as for xflip.
    first = np.asarray(jnwb.jrsa(a, b, stats=True, permutations=200, null="iid", rng=None).p).tolist()
    for _ in range(3):
        later = np.asarray(jnwb.jrsa(a, b, stats=True, permutations=200, null="iid", rng=None).p).tolist()
        if later != first:
            break
    return first, later




def _probe_cross_modal_comparison():
    seed = np.random.default_rng(11)
    u, v = seed.normal(size=300), seed.normal(size=300)
    key = "lag_corrected_pvalue"
    # Eleven lags rather than the default 101: the null loop's cost is lags x permutations,
    # and the lag count does not change what is asserted. Two fresh calls then coincide on
    # about one pair in twenty (measured: 24 distinct p-values in 40 calls), so four calls a
    # side make an exact agreement by chance about one in 10**5.
    return tuple(
        tuple(jnwb.cross_modal_comparison(u, v, lag_range_ms=(-50, 50), bin_ms=10.0,
                                          rng=None)[key] for _ in range(4))
        for _side in range(2)
    )




#: One probe per function. A name without its own probe is not exercised, so the mapping is
#: explicit rather than a dispatch with a fallback branch.
FRESH_PROBES = {
    "cross_modal_comparison": _probe_cross_modal_comparison,
    "jrsa": _probe_jrsa,
    "xflip": _probe_xflip,
}




def test_every_fresh_entropy_function_has_its_own_probe():
    """Caught by mutation: the earlier form dispatched on the name with a trailing `else`,
    so adding a name to `FRESH_ENTROPY` re-ran `cross_modal_comparison` under the new
    name and passed without ever calling the function it claimed to test."""
    assert set(FRESH_PROBES) == set(FRESH_ENTROPY), (
        "FRESH_ENTROPY and FRESH_PROBES disagree; a name without a probe would be reported "
        f"as verified without being called: {set(FRESH_ENTROPY) ^ set(FRESH_PROBES)}"
    )




@pytest.mark.parametrize("name", sorted(FRESH_PROBES))
def test_none_really_means_fresh_entropy(name):
    """Two calls with `rng=None` must disagree, or `None` is a fixed seed in disguise."""
    one, two = FRESH_PROBES[name]()
    assert one != two, (
        f"{name}: two rng=None calls agreed exactly, so None resolves to a fixed seed"
    )




def test_cross_area_coherence_draws_the_stream_its_signature_advertises():
    """The successor to the test that pinned the deviation.

    Its predecessor asserted the *deviation* -- that `rng=None` resolved to a fixed seed --
    by calling the function twice. That technique is the point, and it is the only one of
    these assertions that survives every rewrite of the source, so it is kept and pointed
    at the convention instead. A repair that only moved the literal would have left the
    predecessor green while its name went false; this one fails on the numbers.

    Three facts, none of them read off the source:

    1. A bare call and an explicit `rng=42` produce the same surrogates, so the number in
       the signature is the number the body uses. A body that ignored its parameter and
       kept `SeedSequence(42)` internally would also pass this one -- which is why (2)
       exists.
    2. An explicit `rng=7` produces *different* surrogates, so the parameter is actually
       reaching the generator rather than being decorative.
    3. `rng=None` now draws fresh entropy per call, which is what the signature's `None`
       means everywhere else in the package, and the entropy it drew still reaches the
       caller through `surrogate_seed_entropy`.
    """
    a, b = _coherence_inputs()

    bare = jnwb.cross_area_coherence(a, b, **COHERENCE_KW)
    explicit = jnwb.cross_area_coherence(
        a, b, rng=COHERENCE_DEFAULT_SEED, **COHERENCE_KW
    )
    assert bare["band_significance"] == explicit["band_significance"], (
        f"a bare call and rng={COHERENCE_DEFAULT_SEED} disagree, so the seed in the "
        "signature is not the seed the body uses -- the signature is decorative"
    )
    assert bare[DISCLOSURE_KEY] == COHERENCE_DEFAULT_SEED, (
        f"{DISCLOSURE_KEY} no longer reports the default seed; the disclosure that made "
        "the old deviation survivable must survive its repair"
    )

    other = jnwb.cross_area_coherence(a, b, rng=7, **COHERENCE_KW)
    assert other[DISCLOSURE_KEY] == 7
    assert other["band_significance"] != bare["band_significance"], (
        "rng=7 and the default seed produced identical surrogates, so the rng parameter "
        "is not reaching the generator at all"
    )

    # With 10 surrogates a band's p-value takes one of 11 values, and two fresh draws gave the
    # same five values in 2 of 3000 trials; with 200 surrogates no pair agreed in 300 trials.
    fresh = dict(COHERENCE_KW, n_surrogates=200)
    one = jnwb.cross_area_coherence(a, b, rng=None, **fresh)
    two = jnwb.cross_area_coherence(a, b, rng=None, **fresh)
    assert one["band_significance"] != two["band_significance"], (
        "two rng=None calls agreed exactly, so None still resolves to a fixed seed -- the "
        "the silent-seed defect, now in the place the repair was supposed to clear"
    )
    assert one[DISCLOSURE_KEY] != two[DISCLOSURE_KEY], (
        f"rng=None reported the same {DISCLOSURE_KEY} twice; fresh entropy that is not "
        "disclosed per call cannot be reproduced afterwards"
    )
    assert one[DISCLOSURE_KEY] is not None and two[DISCLOSURE_KEY] is not None




def test_cross_area_coherence_shows_its_seed_in_the_signature():
    """This was a strict xfail until the repair landed.

    Named separately from the equality in `test_exactly_these_three_present_none` on
    purpose: re-admitting `cross_area_coherence` to `PRESENTS_NONE` would silence that one
    and not this one.
    """
    default = inspect.signature(jnwb.cross_area_coherence).parameters["rng"].default
    assert not _presents_none(default), (
        "cross_area_coherence presents rng=None again; the repair has regressed and the "
        "signature no longer reports the stream a bare call draws"
    )
    value = default.value if isinstance(default, Default) else default
    assert value == COHERENCE_DEFAULT_SEED, (
        f"the visible default moved from {COHERENCE_DEFAULT_SEED} to {value!r}. Changing "
        "it changes every published number from a bare call; it is a constant, not a knob"
    )


"""Every parameter the package hands to its RNG resolvers is annotated with what they accept.

The parameters are found by use, not by name: a parameter is stochastic when a function
passes it, as its first argument, to one of the resolvers in ``jnwb._rng``. A walk over the
names ``rng`` and ``seed`` reaches only the parameters spelled that way.
"""


if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # the installed-wheel run clears pythonpath



from scripts import build_fact_graph  # noqa: E402


from scripts.fact_graph import signatures  # noqa: E402



PACKAGE = Path(jnwb.__file__).resolve().parent



#: The resolvers, each taking an int, a Generator or None (``resolve_seed_alias`` takes two).
from jnwb._rng import RESOLVERS  # noqa: E402




def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None




def _resolved_parameters():
    """(module, function, parameter, annotation source or None) for every parameter passed
    to a resolver by the function that declares it."""
    rows = []
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = fn.args
            params = {a.arg: a for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call) or _call_name(call) not in RESOLVERS:
                    continue
                for arg in call.args[:RESOLVERS[_call_name(call)]]:
                    if isinstance(arg, ast.Name) and arg.id in params:
                        ann = params[arg.id].annotation
                        rows.append((path.relative_to(PACKAGE).as_posix(), fn.name, arg.id,
                                     None if ann is None else ast.unparse(ann)))
    return sorted(set(rows))




def _accepts_what_resolvers_accept(annotation: str | None) -> bool:
    if annotation is None or annotation in {"RNGLike", "Any"}:
        return True
    has_none = "None" in annotation or annotation.startswith("Optional[")
    return "int" in annotation and "Generator" in annotation and has_none




def test_the_walk_reaches_parameters_not_spelled_rng():
    rows = _resolved_parameters()
    found = {(m, f, p) for m, f, p, _ in rows}
    assert ("testing/synth.py", "build_canonical_tutorial_nwb", "seed") in found
    assert ("testing/nwb_fixtures.py", "_synthetic_lfp", "seed") in found
    assert len(rows) >= 40, f"the walk found only {len(rows)} resolved parameters"




def test_every_resolved_parameter_is_annotated_with_what_the_resolver_accepts():
    wrong = [r for r in _resolved_parameters() if not _accepts_what_resolvers_accept(r[3])]
    assert not wrong, f"annotated narrower than an int, a Generator or None: {wrong}"




#: Resolver arguments that are not a parameter of the calling function, so the walk above
#: does not reach them, each with where its value comes from. A new one fails the test below
#: until it is traced here.
UNWALKED = {
    ("connectivity/_network.py", "directed_network", "kwargs['rng']"):
        "the estimator's rng, forwarded through **kwargs; its annotation is checked below",
    ("connectivity/_network.py", "directed_network", "kwargs['seed']"):
        "the estimator's seed, forwarded through **kwargs",
    ("connectivity/_network.py", "directed_network", "given"):
        "kwargs['rng'] or kwargs['seed'], the two rows above",
    ("jrsa/__init__.py", "jrsa", "Default(None)"):
        "the alias slot of resolve_seed_alias(rng, ...), whose rng is walked",
    ("jrsa/__init__.py", "jrsa", "kwargs.pop(_alias)"):
        "the spellings random_state and seed, accepted through **kwargs",
    ("jrsa/__init__.py", "jrsa", "random_state"):
        "a local, the result of resolve_seed_alias(rng, ...)",
    ("viz.py", "resample_onsets",
     "resolve_seed_alias(rng, random_state, alias_name='random_state', "
     "func_name='resample_onsets')"):
        "a nested resolver call, whose arguments rng and random_state are walked",
}




def _unwalked_arguments():
    found = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = fn.args
            params = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call) or _call_name(call) not in RESOLVERS:
                    continue
                for arg in call.args[:RESOLVERS[_call_name(call)]]:
                    if not (isinstance(arg, ast.Name) and arg.id in params):
                        found.add((path.relative_to(PACKAGE).as_posix(), fn.name,
                                   ast.unparse(arg)))
    return found




def test_every_resolver_argument_the_walk_skips_is_traced():
    """Four resolver calls (`directed_network` twice, `jrsa`, `resample_onsets`) pass a
    value that is not a parameter name, which the walk skipped in silence."""
    assert _unwalked_arguments() == set(UNWALKED)




def test_the_parameters_behind_the_unwalked_arguments_accept_what_the_resolvers_accept():
    import inspect

    from jnwb.connectivity._network import DIRECTED_METHODS
    from jnwb.viz import resample_onsets

    # directed_network forwards rng and seed to the estimator it runs; each declares both.
    checked = [(estimator, ("rng", "seed")) for estimator in set(DIRECTED_METHODS.values())]
    checked += [(jnwb.jrsa, ("rng",)), (resample_onsets, ("rng", "random_state"))]
    for fn, names in checked:
        signature = inspect.signature(fn)
        for name in names:
            annotation = signature.parameters[name].annotation
            text = annotation if isinstance(annotation, str) else inspect.formatannotation(annotation)
            assert _accepts_what_resolvers_accept(text), (fn.__name__, name, text)




def test_the_fixture_options_seed_is_annotated_as_the_resolver_accepts():
    # The field reaches the resolver through ``_synthetic_lfp``; the walk above sees only
    # parameters passed directly.
    from jnwb.testing.nwb_fixtures import SynthNWBBuildOptions

    assert SynthNWBBuildOptions.__annotations__["seed"] == "RNGLike"




# ------------------------------------------------- psth: the rng its bootstrap interval draws on


def _psth_fixture():
    """Spikes and trial onsets from a fixed generator: 40 trials, so the interval varies."""
    gen = np.random.default_rng(7)
    onsets = np.sort(gen.uniform(0.0, 50.0, 40))
    spikes = np.sort(gen.uniform(0.0, 60.0, 900))
    return spikes, onsets




def test_a_bare_psth_call_keeps_the_interval_it_always_gave():
    spikes, onsets = _psth_fixture()
    bare = UnitAnalyzer.psth(spikes, onsets, 10, window_ms=(-100, 200))
    seeded = UnitAnalyzer.psth(spikes, onsets, 10, window_ms=(-100, 200), rng=DEFAULT_SEED)
    assert bare["bootstrap_ci"]["surrogate_seed_entropy"] == DEFAULT_SEED, (
        "the bare call must draw the default seed")
    np.testing.assert_array_equal(bare["bootstrap_ci"]["bootstrap_ci"],
                                  seeded["bootstrap_ci"]["bootstrap_ci"])
    np.testing.assert_allclose(bare["bootstrap_ci"]["bootstrap_ci"],
                               (13.833333333333334, 18.083333333333332), rtol=1e-12)




def test_two_seeds_give_two_intervals_and_no_rng_gives_fresh_entropy():
    spikes, onsets = _psth_fixture()
    first, second = (UnitAnalyzer.psth(spikes, onsets, 10, window_ms=(-100, 200), rng=seed)
                     for seed in (1, 2))
    assert not np.array_equal(first["bootstrap_ci"]["bootstrap_ci"],
                              second["bootstrap_ci"]["bootstrap_ci"]), (
        "two seeds must give two intervals")
    fresh = [UnitAnalyzer.psth(spikes, onsets, 10, window_ms=(-100, 200), rng=None)
             ["bootstrap_ci"]["surrogate_seed_entropy"] for _ in range(2)]
    assert fresh[0] != fresh[1], "rng=None must draw fresh entropy on each call"




# ------------------------------------------------- compare_criteria: the rng its interval draws on


def _criteria_fixture():
    """Two unit populations from a fixed generator: firing rates of 30 and 25 units."""
    gen = np.random.default_rng(11)
    units1 = pd.DataFrame({"firing_rate": gen.gamma(2.0, 3.0, 30)})
    units2 = pd.DataFrame({"firing_rate": gen.gamma(2.0, 4.0, 25)})
    return units1, units2




def test_compare_criteria_rng_is_keyword_only_and_defaults_to_the_seed_it_always_used():
    parameter = inspect.signature(PopulationAnalyzer.compare_criteria).parameters["rng"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default == DEFAULT_SEED




def test_a_bare_compare_criteria_call_keeps_the_numbers_it_always_gave():
    units1, units2 = _criteria_fixture()
    stats = PopulationAnalyzer.compare_criteria(units1, units2)["statistics"]
    assert stats["surrogate_seed_entropy"] == DEFAULT_SEED
    np.testing.assert_allclose(stats["mean_diff_ci"]["bootstrap_ci"],
                               (-4.445697201599825, 0.49427253947459815), rtol=1e-12)
    np.testing.assert_allclose(stats["parametric"]["pval"], 0.14857336952830863, rtol=1e-12)
    np.testing.assert_allclose(stats["non_parametric"]["pval"], 0.3227460897170271, rtol=1e-12)




def test_compare_criteria_two_seeds_give_two_intervals():
    units1, units2 = _criteria_fixture()
    first, second = [PopulationAnalyzer.compare_criteria(units1, units2, rng=seed)
                     ["statistics"]["mean_diff_ci"]["bootstrap_ci"] for seed in (1, 2)]
    assert first != second, "two seeds must give two intervals"




def test_compare_criteria_rng_none_draws_fresh_entropy_on_each_call():
    units1, units2 = _criteria_fixture()
    fresh = [PopulationAnalyzer.compare_criteria(units1, units2, rng=None)["statistics"]
             ["surrogate_seed_entropy"] for _ in range(2)]
    assert fresh[0] != fresh[1], "rng=None must draw fresh entropy on each call"




# ------------------------------------------------- the rng scan follows calls into a drawing callee


def planted_bootstrap_without_rng(x):
    """The pre-fix psth shape: a drawing callee's result nested in the caller's, no rng passed."""
    return {"ci": StatisticalAnalysis.bootstrap_ci(x)}




def planted_bootstrap_with_rng(x, rng):
    return {"ci": StatisticalAnalysis.bootstrap_ci(x, rng=rng)}




def planted_bootstrap_positional_rng(x, rng):
    return {"ci": StatisticalAnalysis.bootstrap_ci(x, np.mean, 10000, 0.95, rng)}




def planted_granger_with_no_null(x, y):
    """A drawing callee whose count is the literal 0: it draws no null, so it needs no rng."""
    return {"gc": granger(x, y, n_surrogates=0)}




def planted_granger_with_a_null(x, y):
    return {"gc": granger(x, y, n_surrogates=5)}




def planted_surrogate_rng_by_position(x, y, rng):
    """The generator reaches ``_net_surrogate_p`` by position, under the name ``surrogate_rng``."""
    return {"p": _net_surrogate_p(x, y, 2, 5, rng, "zscore")}




def _scanned_package(*functions):
    """A stand-in for the package: each planted function is exported under its own name."""
    return types.SimpleNamespace(__all__=[f.__name__ for f in functions],
                                 **{f.__name__: f for f in functions})




def _reported_by_name(found):
    return {name.rpartition(".")[2]: reason for name, reason in found}




def test_a_drawing_callee_reached_without_an_rng_argument_is_flagged(monkeypatch):
    monkeypatch.setattr(signatures, "S11_EXCUSED", {})
    draws, _ = build_fact_graph._reach(planted_bootstrap_without_rng, None, set(),
                                       draw=build_fact_graph._resolver_call)
    assert "surrogate_rng" in draws, "the fixture must reach the bootstrap's draw"
    examined, found = build_fact_graph.rng_scan(_scanned_package(planted_bootstrap_without_rng))
    assert examined == 1
    reported = _reported_by_name(found)
    assert set(reported) == {"planted_bootstrap_without_rng"}, found
    assert "bootstrap_ci" in reported["planted_bootstrap_without_rng"]




def test_a_drawing_callee_given_its_rng_by_keyword_or_position_is_not_flagged(monkeypatch):
    monkeypatch.setattr(signatures, "S11_EXCUSED", {})
    examined, found = build_fact_graph.rng_scan(
        _scanned_package(planted_bootstrap_with_rng, planted_bootstrap_positional_rng))
    assert examined == 2
    assert found == [], "an rng passed to the drawing callee is not a finding"




def test_a_literal_zero_count_draws_nothing_so_its_call_is_not_flagged(monkeypatch):
    monkeypatch.setattr(signatures, "S11_EXCUSED", {})
    draws, _ = build_fact_graph._reach(planted_granger_with_no_null, None, set(),
                                       draw=build_fact_graph._resolver_call)
    assert draws, "the fixture must reach granger's draw"
    examined, found = build_fact_graph.rng_scan(_scanned_package(planted_granger_with_no_null))
    assert examined == 1
    assert found == [], found




def test_a_count_that_is_not_a_literal_zero_still_needs_an_rng(monkeypatch):
    monkeypatch.setattr(signatures, "S11_EXCUSED", {})
    examined, found = build_fact_graph.rng_scan(_scanned_package(planted_granger_with_a_null))
    assert examined == 1
    assert set(_reported_by_name(found)) == {"planted_granger_with_a_null"}, found




def test_a_generator_passed_by_position_under_a_suffixed_name_is_not_flagged(monkeypatch):
    monkeypatch.setattr(signatures, "S11_EXCUSED", {})
    examined, found = build_fact_graph.rng_scan(_scanned_package(planted_surrogate_rng_by_position))
    assert examined == 1
    assert found == [], found




def test_a_parameter_named_with_a_generator_suffix_takes_the_rng_without_an_annotation():
    def takes_a_suffixed(x, surrogate_rng):
        return x

    with_rng = ast.parse("takes_a_suffixed(x, g)", mode="eval").body
    without_rng = ast.parse("takes_a_suffixed(x)", mode="eval").body
    assert build_fact_graph._passes_rng(with_rng, "takes_a_suffixed", takes_a_suffixed)
    assert not build_fact_graph._passes_rng(without_rng, "takes_a_suffixed", takes_a_suffixed)




def test_a_parameter_annotated_as_a_generator_takes_the_rng_whatever_its_name():
    def takes_a_generator(x, gen: RNGLike = DEFAULT_SEED):
        return x

    with_gen = ast.parse("takes_a_generator(x, g)", mode="eval").body
    without_gen = ast.parse("takes_a_generator(x)", mode="eval").body
    assert build_fact_graph._passes_rng(with_gen, "takes_a_generator", takes_a_generator)
    assert not build_fact_graph._passes_rng(without_gen, "takes_a_generator", takes_a_generator)


"""One spelling for the random-number argument.

The package spelled one concept four ways. Reproduced across `jnwb.__all__`: 19 callables
carried an RNG-ish parameter, under `rng` (8), `seed` (7), `random_state` (3) and
`random_seed` (1, a `Provenance` field rather than a randomized function).

Two corrections to the audit. It counted "10 spellings across 19 functions", which merges
two different parameters: the *source* of randomness (`rng`/`seed`/`random_state`) and the
*number of resamples* (`n_surrogates` 7, `n_permutations` 3, `n_shuffles` 3, plus the
singletons `permutations`, `n_shuffle`, `n_bootstrap` and `bootstrap` -- 11 distinct names,
not 10). Only the first group is unified here; renaming resample counts is not asked for, and
they are genuinely different parameters.

`rng` is canonical because the unified argument accepts a `Generator` as well as an int,
and `seed` would misname a Generator. This overrides a comment in `jrsa` asserting that
`seed` was "the package-wide spelling" -- that was true of 7 functions against 8 spelling
it `rng`, before the argument's type widened.

Every rename keeps the old spelling as a keyword-only alias, keeps the canonical parameter
at its original position so positional callers are unaffected, and keeps its original
default visible in the signature, as the RNG convention requires.
"""




# (function name, old spelling, the default it had before the rename)
RENAMED = [
    ("granger", "seed", 0),
    ("granger_spectral", "seed", 0),
    ("phase_slope_index", "seed", 0),
    ("transfer_entropy", "seed", 0),
    ("zflip", "seed", 0),
    ("cross_modal_comparison", "seed", None),
    ("shuffle_r2_ci", "random_state", 42),
    ("build_permutation_plan", "seed", REQUIRED),
    ("resample_onsets", "random_state", 42),
]



# Entry points that already spelled it `rng` and must keep doing so.
ALREADY_RNG = [
    "cluster_permutation_test", "cross_area_coherence", "exact_sign_flip",
    "paired_fire_prob_test", "permute_labels", "shuffle_pvalue_paired",
    "shuffle_pvalue_unpaired", "xflip",
]




class TestOneSpellingAcrossThePublicApi:

    @pytest.mark.parametrize("name,old,default", RENAMED, ids=[r[0] for r in RENAMED])
    def test_the_canonical_parameter_is_rng(self, name, old, default):
        params = inspect.signature(getattr(jnwb, name)).parameters
        assert "rng" in params, f"{name} still has no rng parameter"

    @pytest.mark.parametrize("name,old,default", RENAMED, ids=[r[0] for r in RENAMED])
    def test_the_old_spelling_survives_as_a_keyword_only_alias(self, name, old, default):
        params = inspect.signature(getattr(jnwb, name)).parameters
        assert old in params, f"{name}: the {old} alias was dropped"
        assert params[old].kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{name}: {old} must be keyword-only so it cannot be passed positionally "
            f"into the slot that now belongs to another argument"
        )

    @pytest.mark.parametrize("name,old,default", RENAMED, ids=[r[0] for r in RENAMED])
    def test_the_original_default_is_still_visible(self, name, old, default):
        """The visible-default requirement survives the rename: `Default` reports the value it
        stands for, so `help()` and `inspect.signature` still show `rng=0`."""
        shown = inspect.signature(getattr(jnwb, name)).parameters["rng"].default
        assert shown == default, f"{name}: rng default shows {shown!r}, was {default!r}"
        assert repr(shown) == repr(default)

    @pytest.mark.parametrize("name", ALREADY_RNG)
    def test_the_functions_that_were_already_right_are_unchanged(self, name):
        assert "rng" in inspect.signature(getattr(jnwb, name)).parameters

    def test_no_public_function_still_spells_it_seed_or_random_state_only(self):
        """The acceptance criterion, swept rather than listed, so the next function
        added under an old spelling fails here."""
        offenders = []
        for name in jnwb.__all__:
            obj = getattr(jnwb, name)
            if not callable(obj) or isinstance(obj, type):
                continue
            try:
                params = inspect.signature(obj).parameters
            except ValueError:
                continue
            legacy = {"seed", "random_state", "random_seed"} & set(params)
            if legacy and "rng" not in params:
                offenders.append((name, sorted(legacy)))
        assert not offenders, f"still spelled without an rng canonical: {offenders}"




class TestTheAliasMeansTheSameThing:

    def test_granger_agrees_across_spellings(self):
        g = np.random.default_rng(0)
        x = g.normal(size=400)
        y = np.roll(x, 3) * 0.6 + g.normal(size=400) * 0.4
        by_rng = jnwb.granger(x, y, order=4, n_surrogates=20, rng=5)
        by_seed = jnwb.granger(x, y, order=4, n_surrogates=20, seed=5)
        assert by_rng.p_x_to_y == by_seed.p_x_to_y
        assert by_rng.x_to_y == by_seed.x_to_y

    def test_resample_onsets_agrees_across_spellings(self):
        onsets = np.arange(50.0)
        np.testing.assert_array_equal(
            jnwb.resample_onsets(onsets, target_n=17, rng=9),
            jnwb.resample_onsets(onsets, target_n=17, random_state=9),
        )

    def test_shuffle_r2_ci_agrees_across_spellings(self):
        g = np.random.default_rng(1)
        y = g.normal(size=80)
        s = y * 0.7 + g.normal(size=80) * 0.5
        assert jnwb.shuffle_r2_ci(y, s, n_shuffle=200, rng=4) == \
               jnwb.shuffle_r2_ci(y, s, n_shuffle=200, random_state=4)

    def test_the_canonical_name_is_still_positional_where_it_was(self):
        """`granger(..., seed)` was positional-or-keyword; a caller passing it
        positionally must land on `rng`, not on the argument after it."""
        params = list(inspect.signature(jnwb.granger).parameters)
        # At HEAD the positional list was
        # [X, Y, order, max_lag, criterion, Z, ridge, detrend, n_surrogates, seed, time_axis]
        # -- `seed` at index 9. `rng` must occupy that slot, with `time_axis` after it.
        assert params.index("rng") == 9, params
        assert params[10] == "time_axis", params
        assert params.index("seed") > params.index("time_axis"), (
            "the alias must sit after the positional block, not inside it"
        )




class TestConflictingSpellingsRaise:

    def test_granger_refuses_two_different_values(self):
        g = np.random.default_rng(0)
        x, y = g.normal(size=300), g.normal(size=300)
        with pytest.raises(ValueError, match="Conflicting values provided to granger"):
            jnwb.granger(x, y, order=4, n_surrogates=5, rng=1, seed=2)

    def test_agreeing_values_are_not_a_conflict(self):
        g = np.random.default_rng(0)
        x = g.normal(size=400)
        y = np.roll(x, 3) * 0.6 + g.normal(size=400) * 0.4
        both = jnwb.granger(x, y, order=4, n_surrogates=20, rng=5, seed=5)
        one = jnwb.granger(x, y, order=4, n_surrogates=20, rng=5)
        assert both.p_x_to_y == one.p_x_to_y

    def test_resample_onsets_refuses_two_different_values(self):
        with pytest.raises(ValueError, match="Conflicting values"):
            jnwb.resample_onsets(np.arange(20.0), target_n=5, rng=1, random_state=2)

    def test_jrsa_refuses_every_pair_of_its_three_spellings(self):
        g = np.random.default_rng(0)
        x = g.normal(size=120)
        y = x * 0.5 + g.normal(size=120) * 0.2
        for kwargs in ({"rng": 0, "seed": 1}, {"rng": 0, "random_state": 1},
                       {"seed": 0, "random_state": 1}):
            with pytest.raises(ValueError, match="Conflicting values provided to jrsa"):
                jnwb.jrsa(x, y, metric="pearson", permutations=10, stats=True, **kwargs)

    def test_the_message_names_the_spellings_the_caller_actually_used(self):
        """Neither name in the message may be one the caller never wrote."""
        g = np.random.default_rng(0)
        x = g.normal(size=120)
        y = x * 0.5 + g.normal(size=120) * 0.2
        with pytest.raises(ValueError) as exc:
            jnwb.jrsa(x, y, metric="pearson", permutations=10, stats=True,
                      seed=1, random_state=2)
        assert "rng=" not in str(exc.value), str(exc.value)
        assert "random_state=2" in str(exc.value) and "seed=1" in str(exc.value)




class TestARequiredParameterStaysRequired:
    """`build_permutation_plan.seed` had no default. Both spellings need one so either
    may be omitted, so the requirement moved into the resolver."""

    def test_omitting_both_raises_and_names_both(self):
        with pytest.raises(TypeError, match="requires rng .*alias seed"):
            jnwb.build_permutation_plan(np.array([0, 1] * 10), np.arange(20) // 2,
                                        n_permutations=5)

    def test_either_spelling_satisfies_it(self):
        labels, groups = np.array([0, 1] * 10), np.arange(20) // 2
        a = jnwb.build_permutation_plan(labels, groups, n_permutations=5, seed=3)
        b = jnwb.build_permutation_plan(labels, groups, n_permutations=5, rng=3)
        assert str(a) == str(b)

    @pytest.mark.parametrize("bad", [2.5, True])
    def test_a_float_or_bool_base_seed_is_refused(self, bad):
        """A Generator or None becomes one int base seed that the plan returns; a float or
        bool is refused rather than truncated inside the loop on `seed + i`."""
        labels, groups = np.array([0, 1] * 10), np.arange(20) // 2
        with pytest.raises(TypeError, match="rng must be an int seed"):
            jnwb.build_permutation_plan(labels, groups, n_permutations=3, rng=bad)

    def test_the_manifest_records_the_arithmetic_it_documents(self):
        labels, groups = np.array([0, 1] * 10), np.arange(20) // 2
        plan = jnwb.build_permutation_plan(labels, groups, n_permutations=4, rng=5)
        assert list(plan["draw_manifest"]["seed"]) == [5, 6, 7, 8]




class TestTheDefaultSentinelItself:

    def test_it_reports_the_value_it_stands_for(self):
        assert repr(Default(0)) == "0"
        assert repr(Default(None)) == "None"
        assert Default(42) == 42
        assert Default(0) == Default(0)

    def test_it_is_distinguishable_from_the_value(self):
        """This is the whole point: `None` cannot mark "not supplied" for an argument
        whose `None` means fresh entropy."""
        assert isinstance(Default(None), Default)
        assert not isinstance(None, Default)

    def test_an_explicit_none_is_not_the_default(self):
        assert resolve_seed_alias(None, Default(0), alias_name="seed", func_name="f") is None
        assert resolve_seed_alias(Default(0), Default(0), alias_name="seed",
                                  func_name="f") == 0

    def test_the_alias_wins_when_the_canonical_was_not_supplied(self):
        assert resolve_seed_alias(Default(0), 9, alias_name="seed", func_name="f") == 9

    def test_a_generator_on_both_sides_is_not_a_conflict(self):
        gen = np.random.default_rng(1)
        assert resolve_seed_alias(gen, gen, alias_name="seed", func_name="f") is gen

    def test_two_different_generators_are_a_conflict(self):
        with pytest.raises(ValueError, match="Conflicting values"):
            resolve_seed_alias(np.random.default_rng(1), np.random.default_rng(2),
                               alias_name="seed", func_name="f")
