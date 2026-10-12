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


def _is_landmark(name: str) -> bool:
    return any(word in name.lower() for word in LANDMARK_WORDS)


def _number(node: ast.AST):
    """The number a literal node holds, a signed one included, or None for any other node."""
    sign = 1
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        sign = -1 if isinstance(node.op, ast.USub) else 1
        node = node.operand
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return sign * node.value
    return None


def _fallbacks(node: ast.AST) -> list:
    """``(landmark, operand)`` for ``x if x is None else y`` (either branch) and ``x or y``, where
    ``x`` is a landmark name and ``y`` is what it falls back to."""
    if isinstance(node, ast.IfExp) and isinstance(node.test, ast.Compare):
        test = node.test
        if len(test.ops) == 1 and isinstance(test.ops[0], (ast.Is, ast.IsNot)) \
                and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value is None \
                and isinstance(test.left, ast.Name) and _is_landmark(test.left.id):
            return [(test.left.id, node.body), (test.left.id, node.orelse)]
        return []
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        return [(v.id, other) for v in node.values
                if isinstance(v, ast.Name) and _is_landmark(v.id) for other in node.values]
    return []


def numeric_landmark_defaults(source: str) -> list:
    """``(function, name, value)`` for each landmark parameter defaulting to a number, and for each
    landmark name a function body falls back to a number from."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        positional = args.posonlyargs + args.args
        pairs = list(zip(positional[len(positional) - len(args.defaults):], args.defaults))
        pairs += [(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]
        for arg, default in pairs:
            value = _number(default)
            if _is_landmark(arg.arg) and value is not None:
                found.append((node.name, arg.arg, value))
        for inner in ast.walk(node):
            for name, operand in _fallbacks(inner):
                value = _number(operand)
                if value is not None:
                    found.append((node.name, name, value))
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


def test_the_check_sees_a_negative_landmark_default():
    assert numeric_landmark_defaults("def f(x, crossover_depth=-0.405): pass") == [
        ("f", "crossover_depth", -0.405)]


def test_the_check_sees_a_landmark_fallback_to_a_number_in_the_body():
    for body in ("crossover_depth = crossover_depth if crossover_depth is not None else 0.405",
                 "crossover_depth = 0.405 if crossover_depth is None else crossover_depth",
                 "crossover_depth = crossover_depth or 0.405"):
        found = numeric_landmark_defaults(f"def f(crossover_depth=None):\n    {body}\n")
        assert found == [("f", "crossover_depth", 0.405)], body


def test_the_check_passes_a_landmark_fallback_to_a_name():
    assert numeric_landmark_defaults(
        "def f(crossover_depth=None, other=None):\n"
        "    crossover_depth = crossover_depth if crossover_depth is not None else other\n") == []
