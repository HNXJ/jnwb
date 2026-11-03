"""Every parameter the package hands to its RNG resolvers is annotated with what they accept.

The parameters are found by use, not by name: a parameter is stochastic when a function
passes it, as its first argument, to one of the resolvers in ``jnwb._rng``. A walk over the
names ``rng`` and ``seed`` reaches only the parameters spelled that way.
"""
from __future__ import annotations

import ast
import inspect
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

import jnwb
from jnwb._rng import DEFAULT_SEED, RNGLike
from jnwb.analyzers import PopulationAnalyzer, UnitAnalyzer
from jnwb.connectivity._granger import _net_surrogate_p, granger
from jnwb.statistics import StatisticalAnalysis

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # the installed-wheel run clears pythonpath

from scripts import build_fact_graph  # noqa: E402

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
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
    draws, _ = build_fact_graph._reach(planted_bootstrap_without_rng, None, set(),
                                       draw=build_fact_graph._resolver_call)
    assert "surrogate_rng" in draws, "the fixture must reach the bootstrap's draw"
    examined, found = build_fact_graph.rng_scan(_scanned_package(planted_bootstrap_without_rng))
    assert examined == 1
    reported = _reported_by_name(found)
    assert set(reported) == {"planted_bootstrap_without_rng"}, found
    assert "bootstrap_ci" in reported["planted_bootstrap_without_rng"]


def test_a_drawing_callee_given_its_rng_by_keyword_or_position_is_not_flagged(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
    examined, found = build_fact_graph.rng_scan(
        _scanned_package(planted_bootstrap_with_rng, planted_bootstrap_positional_rng))
    assert examined == 2
    assert found == [], "an rng passed to the drawing callee is not a finding"


def test_a_literal_zero_count_draws_nothing_so_its_call_is_not_flagged(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
    draws, _ = build_fact_graph._reach(planted_granger_with_no_null, None, set(),
                                       draw=build_fact_graph._resolver_call)
    assert draws, "the fixture must reach granger's draw"
    examined, found = build_fact_graph.rng_scan(_scanned_package(planted_granger_with_no_null))
    assert examined == 1
    assert found == [], found


def test_a_count_that_is_not_a_literal_zero_still_needs_an_rng(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
    examined, found = build_fact_graph.rng_scan(_scanned_package(planted_granger_with_a_null))
    assert examined == 1
    assert set(_reported_by_name(found)) == {"planted_granger_with_a_null"}, found


def test_a_generator_passed_by_position_under_a_suffixed_name_is_not_flagged(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
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
