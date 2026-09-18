"""05-34 and 05-35: who controls the randomness, and where the seed is written down.

05-35. Five functions declared `rng: Optional[np.random.Generator] = None` and then ran
`np.random.default_rng(42)` -- `default_rng(0)` in `cluster_permutation_test` -- when the
caller left it out. `None` reads as "fresh randomness", so two calls a caller believed
were independent shared a null distribution and agreed to the last digit. Reproduced at
`statistics.py:206, 720, 993, 1033, 1571` (the audit cited `206, 680, 953, 993, 1483`;
the mechanism and the five functions are exactly as reported, the line numbers were
stale). Two forwarders, `compare_groups` and the `StatisticalAnalysis.exact_sign_flip`
staticmethod, defaulted to `None` and passed it down, so they are repaired too -- without
them, omitting `rng` would have started drawing fresh entropy.

05-34. `nested_cv_linear_svm(X, labels, n_splits)` had no randomness parameter and
hardcoded `random_state=42` at `decoding.py:86, 91, 113, 124`, so nobody could ask whether
a decoding accuracy survived a different partition of the same trials.

The repair must not move a single published number at the default, which
`TestTheDefaultIsTheSeedThatWasHiding` checks by calling each function both ways.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import numpy as np
import pytest

import jnwb
from jnwb import statistics as S
from jnwb._rng import DEFAULT_SEED, resolve_rng, sklearn_random_state
from jnwb.decoding import nested_cv_linear_svm
from jnwb.statistics import StatisticalAnalysis as SA


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
    """05-35 acceptance, read straight off the signature."""

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
        for mod in ("statistics.py", "decoding.py"):
            src = (Path(jnwb.__file__).parent / mod).read_text(encoding="utf-8")
            hits = re.findall(r"default_rng\((\d+)\)", src)
            assert not hits, f"{mod}: seed literal(s) {hits} still inside a body"

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

    def test_sklearn_random_state_passes_none_through(self):
        assert sklearn_random_state(None, func_name="t") is None


class TestOneSpellingAcceptsASeedOrAGenerator:
    """The package was split between `rng: Generator` and `seed: int`."""

    def test_an_int_and_an_equivalent_generator_agree(self, ab):
        a, _ = ab
        assert SA.bootstrap_ci(a, rng=7) == SA.bootstrap_ci(a, rng=np.random.default_rng(7))

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
    """05-34's discriminator: two different seeds give two different fold assignments."""

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

    def test_rng_is_a_parameter_at_all(self):
        """The signature was `(X, labels, n_splits)`."""
        assert "rng" in inspect.signature(nested_cv_linear_svm).parameters

    def test_the_insufficient_trials_branch_still_returns_its_status(self):
        """Adding a parameter must not disturb the early return."""
        X = np.random.default_rng(0).normal(size=(3, 4))
        res = nested_cv_linear_svm(X, np.array([0, 1, 1]), n_splits=3)
        assert res["status"] == "insufficient_trials_for_cv"
        assert np.isnan(res["accuracy"])
