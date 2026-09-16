"""05-34, second half: one spelling for the random-number argument.

The package spelled one concept four ways. Reproduced across `jnwb.__all__`: 19 callables
carried an RNG-ish parameter, under `rng` (8), `seed` (7), `random_state` (3) and
`random_seed` (1, a `Provenance` field rather than a randomized function).

Two corrections to the audit. It counted "10 spellings across 19 functions", which merges
two different parameters: the *source* of randomness (`rng`/`seed`/`random_state`) and the
*number of resamples* (`n_surrogates` 7, `n_permutations` 3, `n_shuffles` 3, plus the
singletons `permutations`, `n_shuffle`, `n_bootstrap` and `bootstrap` -- 11 distinct names,
not 10). Only the first group is unified here; renaming resample counts is not what 05-34
asks for and they are genuinely different parameters.

`rng` is canonical because the unified argument accepts a `Generator` as well as an int,
and `seed` would misname a Generator. This overrides a comment in `jrsa` asserting that
`seed` was "the package-wide spelling" -- that was true of 7 functions against 8 spelling
it `rng`, before the argument's type widened.

Every rename keeps the old spelling as a keyword-only alias, keeps the canonical parameter
at its original position so positional callers are unaffected, and keeps its original
default visible in the signature, which 05-35 requires.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

import jnwb
from jnwb._rng import Default, REQUIRED, resolve_seed_alias


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
        """05-35's requirement survives the rename: `Default` reports the value it
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
            except (ValueError, TypeError):
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

    @pytest.mark.parametrize("bad", ["a Generator", None, 2.5, True])
    def test_it_is_the_one_function_that_cannot_take_a_generator(self, bad):
        """Its product is a manifest of integer per-draw seeds, `rng + i`. A Generator
        cannot name one and fresh entropy would make the manifest unreproducible, so it
        refuses both explicitly instead of failing inside the loop on `seed + i`.
        """
        if bad == "a Generator":
            bad = np.random.default_rng(0)
        labels, groups = np.array([0, 1] * 10), np.arange(20) // 2
        with pytest.raises(TypeError, match="must be an int base seed"):
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
