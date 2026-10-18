"""Tests draw random inputs from a seeded generator, never from numpy's global RNG.

A draw from the unseeded global generator changes a test's input on every run, so a test can
pass for months and then fail on an unlucky draw. Read with ``ast``, so source text inside a
string (a fixture that writes a file) is not a call.
"""
import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent
GLOBAL_DRAWS = {
    "rand", "randn", "randint", "random", "random_sample", "uniform", "normal", "choice",
    "permutation", "shuffle", "poisson", "exponential", "standard_normal", "binomial",
    "beta", "gamma", "multivariate_normal", "laplace", "lognormal",
}


def _global_draws(tree: ast.AST) -> list[tuple[int, str]]:
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        inner = node.func.value
        if (node.func.attr in GLOBAL_DRAWS and isinstance(inner, ast.Attribute)
                and inner.attr == "random" and isinstance(inner.value, ast.Name)
                and inner.value.id in {"np", "numpy"}):
            hits.append((node.lineno, f"np.random.{node.func.attr}"))
    return hits


def test_no_test_draws_from_the_global_generator():
    files = sorted(TESTS.rglob("test_*.py"))
    assert len(files) > 100, "the scan must read the suite"
    found = [f"{p.relative_to(TESTS)}:{line} {name}"
             for p in files
             for line, name in _global_draws(ast.parse(p.read_text(encoding="utf-8")))]
    assert not found, "use np.random.default_rng(<seed>):\n" + "\n".join(found)


def test_the_scan_finds_a_global_draw_and_skips_one_in_a_string():
    src = 'import numpy as np\nx = np.random.randn(3)\nS = "np.random.rand()"\n'
    assert _global_draws(ast.parse(src)) == [(2, "np.random.randn")]
