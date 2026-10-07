"""Every parameter the package hands to its RNG resolvers is annotated with what they accept.

The parameters are found by use, not by name: a parameter is stochastic when a function
passes it, as its first argument, to one of the resolvers in ``jnwb._rng``. A walk over the
names ``rng`` and ``seed`` reaches only the parameters spelled that way.
"""
from __future__ import annotations

import ast
from pathlib import Path

import jnwb

PACKAGE = Path(jnwb.__file__).resolve().parent

#: The resolvers, each taking an int, a Generator or None (``resolve_seed_alias`` takes two).
RESOLVERS = {"resolve_rng": 1, "surrogate_rng": 1, "recorded_rng": 1,
             "sklearn_random_state": 1, "resolve_seed_alias": 2}


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
