"""A laminar landmark is a property of each recording, so `jnwb.vis` gives it no default.

A crossover or boundary depth drawn by default is an empirical value no computation on the
caller's data produced, and it appears on every figure whose caller did not pass one. Read
from the source rather than by importing `jnwb.vis`, so the check runs without the `vis` extra.
"""
import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VIS = REPO_ROOT / "jnwb" / "vis"
LANDMARK_WORDS = ("crossover", "boundary", "landmark")


def numeric_landmark_defaults(source: str) -> list:
    """``(function, parameter, value)`` for each landmark parameter defaulting to a number."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        positional = args.posonlyargs + args.args
        pairs = list(zip(positional[len(positional) - len(args.defaults):], args.defaults))
        pairs += [(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]
        for arg, default in pairs:
            if not any(word in arg.arg.lower() for word in LANDMARK_WORDS):
                continue
            if isinstance(default, ast.Constant) and isinstance(default.value, (int, float)) \
                    and not isinstance(default.value, bool):
                found.append((node.name, arg.arg, default.value))
    return found


def test_no_vis_function_defaults_a_landmark_depth():
    modules = sorted(VIS.glob("*.py"))
    assert modules, "jnwb/vis has no modules; the check would pass vacuously"
    found = {p.name: numeric_landmark_defaults(p.read_text(encoding="utf-8")) for p in modules}
    assert not any(found.values()), found


def test_the_check_sees_a_numeric_landmark_default():
    assert numeric_landmark_defaults("def f(x, crossover_depth=0.405): pass") == [
        ("f", "crossover_depth", 0.405)]
    assert numeric_landmark_defaults("def f(*, boundary_um=250): pass") == [
        ("f", "boundary_um", 250)]
    assert numeric_landmark_defaults("def f(crossover_depth=None, show_boundary=True): pass") == []
