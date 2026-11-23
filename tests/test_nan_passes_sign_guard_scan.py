"""A sign guard on a parameter must come with a finiteness test of that parameter.

NaN compares False with everything, so ``if p <= 0: raise`` lets a NaN ``p`` through and
the function returns NaN output or an empty result instead of refusing. The scan below
walks every function under ``jnwb/`` (AST, not text) and flags a parameter that

* appears in the test of an ``if`` whose body raises, as ``p <= 0``, ``p < 0``, ``0 >= p``
  or ``0 > p`` (alone or inside ``and``/``or``), and
* is never passed, anywhere in the same function, to ``np.isfinite``, ``math.isfinite``,
  ``np.isnan``, ``math.isnan`` or one of the package's validators that refuse non-finite
  values (``FINITENESS_HELPERS``), nor compared with itself (``p != p``).

``not p > 0`` and ``not (p > 0)`` refuse NaN already and are not flagged. A parameter
annotated ``int`` cannot carry NaN and is skipped. Comparisons against a non-zero bound
(``order < 1``) are outside this rule.
"""

from __future__ import annotations

import ast
import math
import runpy
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "jnwb"

FINITENESS_CALLS = {"isfinite", "isnan"}
# Package validators that refuse a non-finite argument (read from their bodies):
# jnwb/_units.py, jnwb/unit_quality.py, jnwb/_bins.py, jnwb/spectral/_common.py,
# jnwb/spectral/_coupling.py.
FINITENESS_HELPERS = {
    "require_positive_fs",
    "_require_positive_fs",
    "_positive_finite",
    "refuse_nonfinite_times",
    "_require_finite_nonempty_trace",
    "_require_finite_nonempty_pair",
}

# (path relative to jnwb/, function, parameter) -> why the site is held rather than flagged.
# Each entry is an open defect except where the reason says the NaN is refused in the same test.
ALLOWED: dict[tuple[str, str, str], str] = {
    ("filtering.py", "bandpass_filter", "low_cut"):
        "NaN passes; scipy refuses it later with 'Wn[0] must be less than Wn[1]'.",
    ("filtering.py", "notch_filter", "freq"):
        "NaN passes; scipy refuses it later with a LinAlgError on NaN coefficients.",
    ("filtering.py", "notch_filter", "q"):
        "NaN passes; scipy refuses it later with a LinAlgError on NaN coefficients.",
    ("laminar/_zflip.py", "_check_thresholds", "n_surrogates"):
        "int(n_surrogates) in the same test raises on NaN and Inf before the sign comparison.",
    ("spectral/_psd.py", "compute_multitaper_psd", "nw"):
        "NaN passes; refused later only by an int() conversion with an unrelated message.",
    ("testing/synth.py", "synth_laminar_motif", "fs"):
        "NaN passes; refused later by the gamma pass-band check.",
    ("tfr.py", "complex_tfr", "fs"):
        "NaN passes; morlet_wavelet refuses it later.",
    ("tfr.py", "complex_tfr", "n_cycles"):
        "NaN passes; morlet_wavelet refuses it later.",
    ("tfr.py", "complex_tfr", "coi_sigma"):
        "NaN passes; refused later only by an int() conversion with an unrelated message.",
}

# Sites where a NaN once passed a sign guard: (path, function, name, held in ALLOWED).
# label_layers reads its pitch from an attribute, so the parameter rule cannot flag it; the
# coverage test checks its finiteness test directly.
KNOWN_SITES = [
    ("spectral/_reference.py", "voltage_curvature_1d", "pitch_um", False),
    ("spectral/_reference.py", "current_source_density_1d", "conductivity_s_per_m", False),
    ("statistics/_cluster.py", "cluster_permutation_test", "threshold", False),
    ("laminar/_labels.py", "label_layers", "nominal_pitch", False),
    ("filtering.py", "bandpass_filter", "fs", False),
    ("filtering.py", "notch_filter", "fs", False),
    ("continuous.py", "epoch_continuous", "fs", False),
    ("tfr.py", "complex_tfr", "fs", True),
]


def _callee(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _is_zero(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and not isinstance(node.value, bool)
        and isinstance(node.value, (int, float))
        and node.value == 0
    )


def _sign_guarded(test: ast.AST, params: set[str]) -> set[str]:
    """Parameters compared as ``p <= 0``/``p < 0``/``0 >= p``/``0 > p`` outside a ``not``."""
    found: set[str] = set()

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, op, right = node.left, node.ops[0], node.comparators[0]
            if (isinstance(op, (ast.LtE, ast.Lt)) and isinstance(left, ast.Name)
                    and _is_zero(right) and left.id in params):
                found.add(left.id)
            if (isinstance(op, (ast.GtE, ast.Gt)) and _is_zero(left)
                    and isinstance(right, ast.Name) and right.id in params):
                found.add(right.id)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(test)
    return found


def _finiteness_tested(func: ast.AST) -> set[str]:
    tested: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            name = _callee(node)
            if name in FINITENESS_CALLS or name in FINITENESS_HELPERS:
                for arg in [*node.args, *(k.value for k in node.keywords)]:
                    tested |= _names(arg)
        elif isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.NotEq):
            a, b = node.left, node.comparators[0]
            if isinstance(a, ast.Name) and isinstance(b, ast.Name) and a.id == b.id:
                tested.add(a.id)
    return tested


def _params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    a = func.args
    out = set()
    for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs]:
        ann = arg.annotation
        if isinstance(ann, ast.Name) and ann.id == "int":
            continue
        out.add(arg.arg)
    return out


def _own_nodes(func: ast.AST):
    """Nodes of ``func``'s body, not descending into nested functions or classes."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def scan_source(source: str, rel: str) -> tuple[int, list[tuple[str, str, str, int]]]:
    """Return (functions examined, [(rel, function, parameter, line)]) for one module."""
    tree = ast.parse(source)
    examined = 0
    flagged = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        examined += 1
        params = _params(func)
        if not params:
            continue
        tested = _finiteness_tested(func)
        for node in _own_nodes(func):
            if not isinstance(node, ast.If):
                continue
            if not any(isinstance(s, ast.Raise) for s in node.body):
                continue
            for p in sorted(_sign_guarded(node.test, params) - tested):
                flagged.append((rel, func.name, p, node.lineno))
    return examined, flagged


def scan_tree(root: Path) -> tuple[int, list[tuple[str, str, str, int]]]:
    examined = 0
    flagged = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        n, f = scan_source(path.read_text(encoding="utf-8"), rel)
        examined += n
        flagged += f
    return examined, flagged


def test_scan_flags_a_planted_unguarded_parameter(tmp_path):
    unguarded = (
        "def f(fs):\n"
        "    if fs <= 0:\n"
        "        raise ValueError('fs')\n"
        "    return fs\n"
    )
    guarded = (
        "import numpy as np\n"
        "def f(fs):\n"
        "    if not np.isfinite(fs) or fs <= 0:\n"
        "        raise ValueError('fs')\n"
        "    return fs\n"
    )
    (tmp_path / "bad.py").write_text(unguarded, encoding="utf-8")
    (tmp_path / "good.py").write_text(guarded, encoding="utf-8")

    # Precondition: the planted guard really passes NaN and the guarded one refuses it.
    bad = runpy.run_path(str(tmp_path / "bad.py"))["f"]
    assert math.isnan(bad(float("nan"))), "plant must let NaN through"
    good = runpy.run_path(str(tmp_path / "good.py"))["f"]
    with pytest.raises(ValueError):
        good(float("nan"))

    examined, flagged = scan_tree(tmp_path)
    assert examined == 2
    assert flagged == [("bad.py", "f", "fs", 2)]


def test_scan_reads_reversed_and_compound_guards_and_helpers(tmp_path):
    src = (
        "def a(x, y):\n"
        "    if y is not None and 0 > x:\n"
        "        raise ValueError\n"
        "def b(x):\n"
        "    if not x > 0:\n"
        "        raise ValueError\n"
        "def c(fs):\n"
        "    require_positive_fs(fs, 'c')\n"
        "    if fs <= 0:\n"
        "        raise ValueError\n"
        "def d(x):\n"
        "    if x != x or x < 0:\n"
        "        raise ValueError\n"
        "def e(n: int):\n"
        "    if n <= 0:\n"
        "        raise ValueError\n"
    )
    (tmp_path / "m.py").write_text(src, encoding="utf-8")
    examined, flagged = scan_tree(tmp_path)
    assert examined == 5
    assert flagged == [("m.py", "a", "x", 2)]


def _function(rel: str, name: str) -> ast.FunctionDef:
    tree = ast.parse((PACKAGE / rel).read_text(encoding="utf-8"))
    hits = [f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) and f.name == name]
    assert len(hits) == 1, f"jnwb/{rel}: expected one function {name}, found {len(hits)}"
    return hits[0]


def test_known_sites_are_tested_for_finiteness_or_held():
    _, flagged = scan_tree(PACKAGE)
    keys = {(rel, fn, p) for rel, fn, p, _ in flagged}
    for rel, fn, name, held in KNOWN_SITES:
        if held:
            assert (rel, fn, name) in keys and (rel, fn, name) in ALLOWED
        else:
            assert name in _finiteness_tested(_function(rel, fn)), f"jnwb/{rel} {fn}({name})"
            assert (rel, fn, name) not in keys


def test_no_sign_guard_in_the_package_lets_nan_through():
    examined, flagged = scan_tree(PACKAGE)
    print(f"examined {examined} functions under jnwb/; {len(flagged)} sign guards without a finiteness test")
    assert examined > 0
    keys = {(rel, fn, p) for rel, fn, p, _ in flagged}
    stale = sorted(set(ALLOWED) - keys)
    assert not stale, f"allow-list entries no longer flagged, remove them: {stale}"
    new = [s for s in flagged if (s[0], s[1], s[2]) not in ALLOWED]
    assert not new, "sign guard without a finiteness test:\n" + "\n".join(
        f"  jnwb/{rel}:{line} {fn}({p})" for rel, fn, p, line in new
    )
