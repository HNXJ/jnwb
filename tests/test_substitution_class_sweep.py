"""A sweep for the substitution class: a differently-computed result under the original label.

06-15 repaired one instance -- with ``statsmodels`` absent, every correction method except
``bonferroni`` was routed to Benjamini-Hochberg while ``parameters['correction']`` kept echoing
the request, so a run corrected one way was recorded as corrected another. 06-16 asks for the
*shape* rather than the instance, and this module is the instrument.

The shape has two halves, and a sweep that looks only at estimators sees only one of them:

* **In code.** A caller-supplied selector (a method name, an alignment, a reduction) is resolved
  through a fallback -- ``MAP.get(sel, <literal>)``, a trailing ``else`` on an ``if/elif`` chain,
  or an ``except`` handler that recomputes instead of raising -- while the label recorded for the
  result still names what was asked for.
* **In data.** A column or field is emitted under a name that denotes one vocabulary while
  carrying another. Two exports emitted a column named ``layer`` whose values were a geometric
  depth class, not the electrophysiological laminar identity the name denotes. That column is
  now ``depth_class``, and ``layer`` is no longer written.

Four scanners below are module-level functions, each driven twice: over **seeds** constructed to
carry the defect, which each must find, and over the **live tree**, whose findings must match a
reviewed baseline naming a reason for every surviving site. A sweep that has never found anything
is not evidence, so every scanner carries both a seed and a negative control -- the repaired form
of the same seed, which it must clear.

**No scanner excludes a shape to suppress a false positive.** Everything the scanners see is
either repaired or carried in an explicit baseline row with its reason; narrowing a check makes a
blind spot, and the blind spots that remain are the ones listed under "What this instrument
cannot see" in :data:`INSTRUMENT_BLIND_SPOTS`, not ones hidden inside a predicate.
"""

from __future__ import annotations

import ast
import pathlib
from collections import namedtuple
from typing import Dict, FrozenSet, List, Set, Tuple

import numpy as np
import pandas as pd
import pytest

import jnwb
from jnwb.addressing import enrich_units_dataframe
from jnwb.continuous import epoch_continuous
from jnwb.laminar import VFlipResult, label_layers
from jnwb.laminar import vflip as laminar_vflip
from jnwb.spectral import relative_power
from jnwb.statistics import _require_alternative, cluster_permutation_test

PACKAGE_ROOT = pathlib.Path(jnwb.__file__).resolve().parent


def test_the_sweep_reads_the_working_tree_and_not_an_installed_copy():
    """A script run by path imports the installed ``jnwb``; a sweep of the wrong tree is a lie."""
    # Skipped, not asserted, when the suite is qualifying an installed copy: there the sweep
    # scans the installation under test, which is correct. Which copy is under test is asserted
    # once, by tests/test_import_provenance.py, which honours JNWB_EXPECTED_PACKAGE_ROOT.
    here = pathlib.Path(__file__).resolve().parent.parent
    if here not in PACKAGE_ROOT.parents:
        pytest.skip(f"qualifying {PACKAGE_ROOT}, not this checkout")
    for module in ("addressing", "continuous", "laminar", "spectral", "statistics"):
        assert (PACKAGE_ROOT / f"{module}.py").is_file(), f"the sweep has no {module}.py to read"


# ===========================================================================
# The scanners
# ===========================================================================

Finding = namedtuple("Finding", "kind module key detail lineno")
"""A hit. ``key`` is line-number-free so a baseline survives edits elsewhere in the file."""


def _module_option_sets(tree: ast.Module) -> Dict[str, Tuple[List[str], List[object]]]:
    """Module-level ``name = {"a": ..., "b": ...}`` with all-string keys."""
    out: Dict[str, Tuple[List[str], List[object]]] = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)):
            continue
        keys, vals, ok = [], [], True
        for k, v in zip(node.value.keys, node.value.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.append(k.value)
            else:
                ok = False
            vals.append(v.value if isinstance(v, ast.Constant) else None)
        if not (ok and keys):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name):
                out[t.id] = (keys, vals)
    return out


def scan_option_set_fallbacks(source: str, module: str) -> List[Finding]:
    """``<option set>.get(selector, <string literal>)``.

    An option set is a dict literal with string keys, written inline or bound at module level.
    Looking a selector up in one with a string fallback is the substitution written as a
    mapping: an unrecognised request silently becomes a recognised one. This is the exact form
    P-31 and P-50 named -- ``_CORRECTION_METHOD_MAP.get(m_lower, "fdr_bh")``.

    Every such site is reported. Whether the substituted value reaches a result or only a
    message is a judgement, and judgements live in the baseline with their reasons, not in this
    predicate.
    """
    tree = ast.parse(source)
    option_sets = _module_option_sets(tree)
    found: List[Finding] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and len(node.args) == 2):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            continue
        default = node.args[1]
        if not (isinstance(default, ast.Constant) and isinstance(default.value, str)):
            continue
        base = func.value
        if isinstance(base, ast.Dict):
            base_name = "<inline dict literal>"
        elif isinstance(base, ast.Name) and base.id in option_sets:
            base_name = base.id
        else:
            continue
        selector = ast.unparse(node.args[0])
        found.append(
            Finding(
                kind="OPTION_SET_GET",
                module=module,
                key=(module, base_name, selector, default.value),
                detail=f"{base_name}.get({selector}, {default.value!r})",
                lineno=node.lineno,
            )
        )
    return found


def _chain_tests(node: ast.If) -> List[Tuple[str, List[str]]]:
    """Walk an ``if/elif`` chain, returning (compared expression, literals) per arm."""
    arms: List[Tuple[str, List[str]]] = []
    cur: ast.If | None = node
    while cur is not None:
        for cmp_node in [cur.test] if isinstance(cur.test, ast.Compare) else []:
            if len(cmp_node.ops) != 1:
                continue
            op = cmp_node.ops[0]
            right = cmp_node.comparators[0]
            lits: List[str] = []
            if isinstance(op, ast.Eq) and isinstance(right, ast.Constant) and isinstance(right.value, str):
                lits = [right.value]
            elif isinstance(op, ast.In) and isinstance(right, (ast.Tuple, ast.List, ast.Set)):
                lits = [e.value for e in right.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if lits:
                arms.append((ast.unparse(cmp_node.left), lits))
        nxt = cur.orelse
        cur = nxt[0] if len(nxt) == 1 and isinstance(nxt[0], ast.If) else None
    return arms


def _terminal_else(node: ast.If) -> List[ast.stmt] | None:
    """The body of the chain's final ``else``, or None if the chain ends without one."""
    cur = node
    while True:
        orelse = cur.orelse
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            cur = orelse[0]
            continue
        return orelse or None


def scan_selector_chain_fallthrough(source: str, module: str) -> List[Finding]:
    """An ``if/elif`` chain over a selector whose trailing ``else`` computes instead of raising.

    This is the same substitution as :func:`scan_option_set_fallbacks` written as control flow,
    and a sweep that looked only for ``.get(x, default)`` would not see it. The chain must test
    one expression against at least two distinct string literals -- that is what makes it a
    selector rather than an ordinary branch -- and the trailing ``else`` must neither raise nor
    be a bare ``pass``/``...``.
    """
    tree = ast.parse(source)
    found: List[Finding] = []
    seen: Set[int] = set()
    # The statement after each `if`, so a chain with no `else` can be read against what runs
    # when no arm matches.
    following: Dict[int, ast.stmt | None] = {}
    for parent in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(parent, field, None)
            if isinstance(block, list):
                for i, stmt in enumerate(block):
                    following[id(stmt)] = block[i + 1] if i + 1 < len(block) else None
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or id(node) in seen:
            continue
        arms = _chain_tests(node)
        # Only the `elif` links belong to this chain. Marking every `if` in the subtree also
        # marked chains nested inside an arm's body, and those were never scanned.
        link: ast.If | None = node
        while link is not None:
            seen.add(id(link))
            nxt = link.orelse
            link = nxt[0] if len(nxt) == 1 and isinstance(nxt[0], ast.If) else None
        if len(arms) < 2:
            continue
        subjects = {s for s, _ in arms}
        if len(subjects) != 1:
            continue
        subject = subjects.pop()
        literals = sorted({lit for _, lits in arms for lit in lits})
        if len(literals) < 2:
            continue
        else_body = _terminal_else(node)
        if else_body is None:
            # No `else`: an unmatched selector falls through to whatever follows the chain.
            # That is the shape `_resample_axis` had before its repair, and it is the same
            # substitution unless the next statement refuses.
            after = following.get(id(node))
            if isinstance(after, ast.Raise):
                continue
            found.append(
                Finding(
                    kind="CHAIN_NO_ELSE",
                    module=module,
                    key=(module, subject, tuple(literals)),
                    detail=f"if/elif on {subject} over {literals}; no else, falls through",
                    lineno=node.lineno,
                )
            )
            continue
        if any(isinstance(s, ast.Raise) for s in ast.walk(ast.Module(body=else_body, type_ignores=[]))):
            continue
        # A bare `else: pass` is NOT excluded. An earlier draft of this scanner skipped it as
        # "an empty branch, nothing computed", and a mutation of the align repair to exactly
        # `else: pass` walked straight through. Doing nothing under a selector the chain has
        # just treated as valid is the quiet form of the class -- absence of output standing
        # in for absence of input -- so it is reported like any other non-raising else.
        found.append(
            Finding(
                kind="CHAIN_ELSE",
                module=module,
                key=(module, subject, tuple(literals)),
                detail=f"if/elif on {subject} over {literals}; trailing else computes",
                lineno=else_body[0].lineno,
            )
        )
    return found


def _assigned_names(body) -> Set[str]:
    out: Set[str] = set()
    for stmt in body:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Assign):
                targets = []
                for t in sub.targets:
                    targets.extend(t.elts if isinstance(t, (ast.Tuple, ast.List)) else [t])
                out.update(t.id for t in targets if isinstance(t, ast.Name))
            elif isinstance(sub, (ast.AnnAssign, ast.AugAssign)):
                if isinstance(sub.target, ast.Name):
                    out.add(sub.target.id)
    return out


def scan_recovering_handlers(source: str, module: str) -> List[Finding]:
    """``except`` handlers that recompute a value the ``try`` body failed to produce.

    An estimator that cannot run is not a licence to return a differently-computed number under
    the requested label. A handler qualifies when it never raises and either rebinds a name the
    ``try`` body also bound, or returns a value of its own.

    A handler that warns is still reported. 06-15's own defect warned and substituted anyway, so
    "it announces itself" is not evidence that the recorded label stayed true -- it is a reason
    that belongs in a baseline row, where a reader can check it.
    """
    tree = ast.parse(source)
    found: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        try_names = _assigned_names(node.body)
        for handler in node.handlers:
            if any(isinstance(s, ast.Raise) for s in ast.walk(handler)):
                continue
            shared = sorted(try_names & _assigned_names(handler.body))
            returns = any(isinstance(s, ast.Return) and s.value is not None
                          for s in ast.walk(handler))
            if not (shared or returns):
                continue
            exc = ast.unparse(handler.type) if handler.type else "bare"
            found.append(
                Finding(
                    kind="HANDLER_RECOVERY",
                    module=module,
                    key=(module, exc, tuple(shared), returns),
                    detail=f"except {exc} rebinds {shared or '-'} returns_value={returns}",
                    lineno=handler.lineno,
                )
            )
    return found


def scan_vocabulary_collisions(
    vocabularies: Dict[str, Dict[str, FrozenSet[str]]]
) -> List[Finding]:
    """One emitted name carrying two vocabularies that share no value.

    The data half of the class. A reader takes a column's name as a claim about what its values
    mean; two producers in one package emitting the same name over disjoint value sets means at
    most one of them can be telling the truth. Nothing is declared by hand here -- the expected
    vocabulary is not written down and then checked, which would only test the writing-down. The
    vocabularies are measured by executing the producers, and the collision is the finding.
    """
    found: List[Finding] = []
    for name, by_producer in sorted(vocabularies.items()):
        items = sorted(by_producer.items())
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (pa, va), (pb, vb) = items[i], items[j]
                if va and vb and not (va & vb):
                    found.append(
                        Finding(
                            kind="VOCAB_COLLISION",
                            module=name,
                            key=(name, pa, pb),
                            detail=f"{pa} emits {sorted(va)}; {pb} emits {sorted(vb)}",
                            lineno=0,
                        )
                    )
    return found


INSTRUMENT_BLIND_SPOTS = """
What this instrument cannot see, stated rather than discovered later:

1. A substitution split across two functions where neither half is locally suspicious -- the
   fallback in one, the label echo in another. The scanners find the fallback, so this is a
   blind spot only where the fallback itself is written in a form none of the three static
   scanners match.
2. A substitution chosen at runtime: a monkeypatched backend, a plugin, a dispatch through a
   registry populated at import time. Nothing static reaches these.
3. A fallback whose default is supplied by a variable rather than a literal
   (``MAP.get(sel, default)``), or a chain whose selector is compared against names rather than
   string literals.
4. On the data half, a name emitted by exactly one producer. A collision needs two, so a single
   export whose column name has always been wrong is invisible here; only a declared vocabulary
   would catch it, and a declared vocabulary tests the declaration.
5. Anything outside ``jnwb/**``: scripts, notebooks and skills are not scanned.
6. A substitution written as a branch rather than a chain or a mapping. The one instance
   found by hand and not by any scanner is ``laminar._compute_correlation_matrix``: a
   ``cond > 1e12`` test routes a near-singular covariance to ``np.linalg.pinv`` and the
   result is returned as a partial correlation with nothing saying so. Reproduced -- a
   duplicated channel yields exactly -1.0. The ``except LinAlgError`` half of the same site
   *is* seen, and carries the finding in ``ACCEPTED_HANDLER_RECOVERY``.
7. A default supplied to an attribute store rather than to an option set. The instance found
   by hand is ``compression.py``'s ``src[ts_path].attrs.get("unit", "seconds")``, which
   writes ``unit="seconds"`` onto a ``starting_time`` dataset whose source said nothing. It
   is not reported as a defect because the NWB schema fixes that attribute's value to
   ``"seconds"``, so the written value is the only legal one -- but the scanner did not see
   it, and a site where the default were *not* schema-fixed would be equally invisible.
8. A selector written as ``match``/``case``. The chain scanner reads ``if``/``elif`` only; no
   ``jnwb/`` module uses ``match`` today, so this is unmeasured rather than clear.

Chains nested inside another ``if`` arm, and chains with no ``else`` whose next statement
does not refuse, were once invisible here too; both are now scanned and seeded.
"""


# ===========================================================================
# Seeds. Every scanner is shown to find a planted instance and to clear its repair.
# ===========================================================================

SEED_OPTION_SET_DEFECT = '''
_CORRECTION_METHOD_MAP = {"fdr_bh": "fdr_bh", "bonferroni": "bonferroni", "holm": "holm"}

def _multiple_correction(p, method, alpha):
    m_lower = method.lower()
    sm_method = _CORRECTION_METHOD_MAP.get(m_lower, "fdr_bh")
    return _apply(p, sm_method, alpha)
'''

SEED_OPTION_SET_REPAIRED = '''
_CORRECTION_METHOD_MAP = {"none": None, "fdr_bh": "fdr_bh", "bonferroni": "bonferroni"}

def _multiple_correction(p, method, alpha):
    m_lower = method.lower()
    if m_lower not in _CORRECTION_METHOD_MAP:
        raise ValueError(f"Unrecognized correction method {method!r}.")
    sm_method = _CORRECTION_METHOD_MAP[m_lower]
    return _apply(p, sm_method, alpha)
'''

SEED_CHAIN_DEFECT = '''
def _reduce(arr, op_str, ax):
    if op_str == "mean":
        return arr.mean(axis=ax)
    elif op_str == "median":
        return arr.median(axis=ax)
    elif op_str == "sum":
        return arr.sum(axis=ax)
    else:
        return arr.mean(axis=ax)
'''

SEED_CHAIN_REPAIRED = '''
def _reduce(arr, op_str, ax):
    if op_str == "mean":
        return arr.mean(axis=ax)
    elif op_str == "median":
        return arr.median(axis=ax)
    elif op_str == "sum":
        return arr.sum(axis=ax)
    else:
        raise ValueError(f"Unrecognized reduction {op_str!r}.")
'''

SEED_NESTED_CHAIN_DEFECT = '''
def _reduce(arr, op_str, ax, exact):
    if exact:
        if op_str == "mean":
            return arr.mean(axis=ax)
        elif op_str == "median":
            return arr.median(axis=ax)
        else:
            return arr.mean(axis=ax)
    return arr
'''

SEED_NESTED_CHAIN_REPAIRED = SEED_NESTED_CHAIN_DEFECT.replace(
    "        else:\n            return arr.mean(axis=ax)\n",
    "        else:\n            raise ValueError(op_str)\n",
)

SEED_NO_ELSE_DEFECT = '''
def _resample_axis(x, align, n):
    if align == "linear":
        x = _interp(x, n, kind="linear")
    elif align == "cubic":
        x = _interp(x, n, kind="cubic")
    return x
'''

SEED_NO_ELSE_REPAIRED = '''
def _resample_axis(x, align, n):
    if align == "linear":
        x = _interp(x, n, kind="linear")
    elif align == "cubic":
        x = _interp(x, n, kind="cubic")
    else:
        raise ValueError(align)
    return x
'''

SEED_NO_ELSE_REFUSED_AFTER = '''
def _resample_axis(x, align, n):
    if align == "linear":
        return _interp(x, n, kind="linear")
    elif align == "cubic":
        return _interp(x, n, kind="cubic")
    raise ValueError(align)
'''

SEED_HANDLER_DEFECT = '''
def correct(p, method, alpha):
    try:
        from statsmodels.stats.multitest import multipletests
        _, q, _, _ = multipletests(p, alpha=alpha, method=method)
    except ImportError:
        q = _benjamini_hochberg(p, alpha)
    return q
'''

SEED_HANDLER_REPAIRED = '''
def correct(p, method, alpha):
    try:
        from statsmodels.stats.multitest import multipletests
        _, q, _, _ = multipletests(p, alpha=alpha, method=method)
    except ImportError as exc:
        raise ImportError(f"correction={method!r} requires statsmodels.") from exc
    return q
'''


class TestTheInstrumentDetectsASeededInstance:
    """A scanner that has never found anything is indistinguishable from one pointed nowhere."""

    def test_option_set_scanner_finds_the_planted_p31_defect(self):
        found = scan_option_set_fallbacks(SEED_OPTION_SET_DEFECT, "seed")
        assert [f.detail for f in found] == [
            '_CORRECTION_METHOD_MAP.get(m_lower, \'fdr_bh\')'
        ], found

    def test_option_set_scanner_clears_the_repaired_form(self):
        assert scan_option_set_fallbacks(SEED_OPTION_SET_REPAIRED, "seed") == []

    def test_chain_scanner_finds_the_planted_reduction_fallthrough(self):
        found = scan_selector_chain_fallthrough(SEED_CHAIN_DEFECT, "seed")
        assert len(found) == 1, found
        assert found[0].key == ("seed", "op_str", ("mean", "median", "sum"))

    def test_chain_scanner_clears_the_repaired_form(self):
        assert scan_selector_chain_fallthrough(SEED_CHAIN_REPAIRED, "seed") == []

    def test_chain_scanner_finds_a_chain_nested_in_an_if_body(self):
        """Every `if` below the outer one used to be marked seen, so this was never read."""
        found = scan_selector_chain_fallthrough(SEED_NESTED_CHAIN_DEFECT, "seed")
        assert [f.key for f in found] == [("seed", "op_str", ("mean", "median"))], found
        assert scan_selector_chain_fallthrough(SEED_NESTED_CHAIN_REPAIRED, "seed") == []

    def test_chain_scanner_finds_a_chain_with_no_else(self):
        """The shape `_resample_axis` had before its repair: an unmatched selector falls
        through and the input is returned as though it had been resampled."""
        found = scan_selector_chain_fallthrough(SEED_NO_ELSE_DEFECT, "seed")
        assert [(f.kind, f.key) for f in found] == [
            ("CHAIN_NO_ELSE", ("seed", "align", ("cubic", "linear")))], found
        assert scan_selector_chain_fallthrough(SEED_NO_ELSE_REPAIRED, "seed") == []
        assert scan_selector_chain_fallthrough(SEED_NO_ELSE_REFUSED_AFTER, "seed") == []

    def test_handler_scanner_finds_the_planted_statsmodels_substitution(self):
        found = scan_recovering_handlers(SEED_HANDLER_DEFECT, "seed")
        assert len(found) == 1, found
        assert found[0].key == ("seed", "ImportError", ("q",), False)

    def test_handler_scanner_clears_the_repaired_form(self):
        assert scan_recovering_handlers(SEED_HANDLER_REPAIRED, "seed") == []

    def test_vocabulary_scanner_finds_a_planted_collision(self):
        found = scan_vocabulary_collisions({
            "layer": {
                "a.geometric": frozenset({"Deep", "Superficial", "Unknown"}),
                "b.laminar": frozenset({"superficial", "input", "deep", "na"}),
            }
        })
        assert len(found) == 1, found
        assert found[0].key == ("layer", "a.geometric", "b.laminar")

    def test_vocabulary_scanner_clears_an_overlapping_pair(self):
        assert scan_vocabulary_collisions({
            "layer": {
                "a": frozenset({"deep", "superficial"}),
                "b": frozenset({"deep", "input", "na"}),
            }
        }) == []

    def test_every_scanner_is_exercised_by_a_seed(self):
        """A scanner added without a seed would otherwise sweep the tree unproven."""
        scanners = {"OPTION_SET_GET", "CHAIN_ELSE", "CHAIN_NO_ELSE", "HANDLER_RECOVERY",
                    "VOCAB_COLLISION"}
        seeded = set()
        seeded.update(f.kind for f in scan_option_set_fallbacks(SEED_OPTION_SET_DEFECT, "s"))
        seeded.update(f.kind for f in scan_selector_chain_fallthrough(SEED_CHAIN_DEFECT, "s"))
        seeded.update(f.kind for f in scan_selector_chain_fallthrough(SEED_NO_ELSE_DEFECT, "s"))
        seeded.update(f.kind for f in scan_recovering_handlers(SEED_HANDLER_DEFECT, "s"))
        seeded.update(f.kind for f in scan_vocabulary_collisions(
            {"layer": {"a": frozenset({"x"}), "b": frozenset({"y"})}}))
        assert seeded == scanners


# ===========================================================================
# The live tree
# ===========================================================================

def _live_findings(scanner) -> List[Finding]:
    out: List[Finding] = []
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        module = path.relative_to(PACKAGE_ROOT).as_posix()
        out.extend(scanner(path.read_text(encoding="utf-8"), module))
    return out


def test_the_sweep_reaches_the_whole_package():
    """A scan over an empty file list is a live zero that means nothing."""
    modules = list(PACKAGE_ROOT.rglob("*.py"))
    assert len(modules) > 30, f"only {len(modules)} modules scanned"
    assert (PACKAGE_ROOT / "jrsa.py") in modules


# Reviewed, one row per surviving site, keyed without line numbers. A new site fails the test
# rather than being absorbed. "Accepted" here means the recorded label stays true on the
# fallback path, which is the whole of the class: a fallback is not a defect, a fallback whose
# result is filed under the request's name is.
ACCEPTED_OPTION_SET_GET = {
    ("_backend.py", "<inline dict literal>", "prefer", "CuPy or PyTorch"):
        "The substituted string names the library that was searched for, inside a "
        "RuntimeWarning's text. It is not a result and is filed under no label.",
}

# A trailing `else` that computes is not a substitution when the selector cannot reach it:
# an out-of-domain value is rejected before the chain runs, so the `else` is the exhaustive
# final branch rather than a default. Each row names the validator, and
# ``test_every_accepted_chain_else_has_a_validator_that_really_rejects`` drives it -- the
# reason is proven by execution, not asserted in a comment.
ACCEPTED_CHAIN_ELSE = {
    ("continuous.py", "boundary_policy", ("drop", "error")):
        "boundary_policy is checked against ('nan', 'error', 'drop') and raises; the else "
        "is the 'nan' branch.",
    ("jrsa.py", "alternative", ("greater", "two-sided")):
        "REPAIRED BY THIS SWEEP: alternative is now checked against jrsa.ALTERNATIVES at "
        "the top of _p_from_null and raises; the else is the 'less' branch.",
    ("laminar.py", "orientation", ("auto", "superficial_to_deep")):
        "orientation is checked against valid_orientations and raises; the else is the "
        "'deep_to_superficial' branch.",
    ("spectral.py", "model", ("mean_of_ratios", "ratio_of_means")):
        "model is checked against RELATIVE_POWER_MODELS and raises; the else is the "
        "'log_ratio' branch.",
    ("statistics.py", "alt", ("greater", "less")):
        "alt is the return of _require_alternative, which normalizes and raises; the else "
        "is the two-sided branch.",
    ("statistics.py", "tail", ("greater", "less")):
        "tail is checked against ('both', 'greater', 'less') and raises; the else is the "
        "'both' branch.",
    ("statistics.py", "alt", ("greater", "two-sided")):
        "exact_sign_flip checks alt against ('two-sided', 'greater', 'less') and raises; the "
        "else is the 'less' branch. Two sites (exact enumeration, Monte Carlo) share this key; "
        "both sit inside an `if n <= 20` arm, which hid them until nested chains were scanned.",
}

ACCEPTED_HANDLER_RECOVERY = {
    ("analyzers.py", "Exception", ("acg",), False):
        "The handler sets acg = None. Absence, not a plausible substitute.",
    ("analyzers.py", "Exception",
     ("X_gpu", "device_used", "explained_variance", "explained_variance_ratio",
      "gpu_success", "projection", "s", "total_variance", "u", "vt"), True):
        "cupy -> torch -> CPU SVD. The path is recorded: device_used and gpu_success are "
        "rebound by the handler and device_used is returned, so the label follows the value.",
    ("gpu_pca.py", "Exception", ("S_np", "V_np", "proj_np"), False):
        "GPU SVD -> NumPy SVD, announced by warn_device_fallback, which is jnwb's declared "
        "mechanism for saying that a CPU and GPU path may disagree numerically.",
    ("trajectory.py", "Exception", ("S_np", "V_np", "proj_np"), False):
        "Same GPU -> NumPy SVD fallback, same announcement.",
    ("spectral.py", "Exception", ("frequencies", "pxx"), False):
        "GPU Welch -> scipy.signal.welch, announced by warn_device_fallback. Two sites "
        "(harmonic_analysis, spectral_tilt) share this key.",
    ("spectral.py", "Exception", ("computed",), False):
        "GPU coherence -> CPU wholesale; the handler rebinds device_used = 'cpu', so the "
        "recorded device follows the value.",
    ("jrsa.py", "ImportError", ("x1", "x2"), False):
        "OPEN, carried deliberately: align='linear'/'cubic' falls back to 'downsample' when "
        "scipy is absent while parameters['align'] echoes the request. Latent -- jrsa() "
        "requires x1 and x2 to have identical shapes, so _align_dimensions never resamples. "
        "The reachable half of the same function is repaired below "
        "(test_an_unrecognised_align_raises_rather_than_resampling_silently). Two sites "
        "(linear, cubic) share this key.",
    ("jrsa.py", "AttributeError", (), True):
        "cupy.median -> cupy.percentile(50) inside _reduce_one. The 50th percentile with "
        "linear interpolation IS the median; same number, different call. The label stays "
        "true.",
    ("jrsa.py", "ImportError", ("arr_cpu",), False):
        "scipy.signal.detrend(type='linear') -> degree-1 polyfit subtraction. Both are the "
        "least-squares linear detrend; scipy's own implementation is the same normal equations.",
    ("jrsa.py", "ImportError", ("arr",), False):
        "Same detrend equivalence on the non-GPU path.",
    ("jrsa.py", "(RuntimeError, TypeError, ValueError)", ("a",), False):
        "tensor.numpy() -> np.asarray(tensor) inside _ensure_np. A conversion of the same "
        "data, not a second way of computing it.",
    ("laminar.py", "np.linalg.LinAlgError", ("theta",), False):
        "OPEN, carried deliberately: a singular covariance is pseudo-inverted and the result "
        "is returned as a partial correlation with no indication. Reproduced -- a rank-2 "
        "channel pair yields exactly -1.0, a plausible and wrong number. Nearly unreachable "
        "because the cond > 1e12 branch above the try already routes to pinv; that branch is "
        "the same substitution written without an exception, and neither is this item's "
        "named scope. Proposed as a new problem row.",
    ("nam.py", "ImportError", ("_BaseModule", "_TORCH_AVAILABLE"), False):
        "Module-level torch import guard. It sets _TORCH_AVAILABLE = False -- the label is "
        "exactly what the handler writes down.",

    # --- handlers that return rather than rebind -----------------------------------------
    # A returned *absence* is the opposite of this class, not an instance of it: NaN, None,
    # False, an error dict and an `accepted=False` result all decline to answer. The class
    # needs a plausible answer filed under the request's name.
    ("_backend.py", "(ImportError, OSError, RuntimeError, AttributeError)", (), True):
        "gpu_available returns False when the probe cannot run. A declared absence.",
    ("_dictlike.py", "KeyError", (), True):
        "dict-like .get returns the caller's own default. The caller named the fallback.",
    ("_parallel.py", "ImportError", (), True):
        "joblib absent -> serial list comprehension over the same fn. Same results by the "
        "same function; only the scheduling differs, and n_jobs describes scheduling.",
    ("addressing.py", "(ValueError, TypeError, OverflowError)", (), True):
        "_resolve_electrode_row returns (None, None) when the channel will not resolve. "
        "Absence, and every caller maps it to 'Unknown'.",
    ("addressing.py", "Exception", (), True):
        "Returns None on a failed area lookup. Absence.",
    ("compression.py", "Exception", (), True):
        "Returns (False, '<ExcType>: msg') from a verification helper -- a reported failure "
        "carrying its own cause.",
    ("connectivity.py", "Exception", (), True):
        "Returns float('nan'). Absence, and NaN propagates rather than reading as a value.",
    ("io.py", "Exception", (), True):
        "_stored_seek_is_reliable returns False when its zipfile probe raises, so a stored "
        "entry is read forward, the path that needs no seek. Same bytes either way; only time "
        "differs.",
    ("jrsa.py", "ImportError", (), True):
        "statsmodels absent -> warns and returns NaN for Granger causality. It declines "
        "rather than substituting another estimator, which is 06-15's repair in this module.",
    ("mcp_server/event_tools.py", "IntervalTableNotFoundError", (), True):
        "Returns {'error': ..., 'error_type': 'PathNotFound'}. A declared failure.",
    ("mcp_server/event_tools.py", "AmbiguousIntervalTableError", (), True):
        "Returns {'error': ..., 'error_type': 'AmbiguousPath'}. A declared failure.",
    ("mcp_server/event_tools.py", "(ColumnNotFoundError, InvalidOnsetValueError)", (), True):
        "Returns {'error': ..., 'error_type': 'ParseError'}. A declared failure.",
    ("mcp_server/event_tools.py", "Exception", (), True):
        "Returns {'error': ..., 'error_type': 'Unknown'} -- names the failure as unknown "
        "rather than answering.",
    ("mcp_server/nwb_tools.py", "Exception", (), True):
        "Returns {'error': ..., 'error_type': 'ParseError'}. A declared failure.",
    ("metadata.py", "ValueError", (), True):
        "Session-id parse falls back to (raw, raw) -- the unparsed input returned as itself, "
        "not a fabricated identifier.",
    ("nwb_inspect.py", "TypeError", (), True):
        "Returns None when a value will not introspect. Absence.",
    ("spectral.py", "Exception", (), True):
        "Returns AperiodicFitResult(accepted=False) with every estimate None -- the "
        "declared refusal shape, which is what a non-identifiable fit is supposed to emit.",
}


def _baseline_check(findings: List[Finding], accepted: Dict[tuple, str], kind: str):
    keys = {f.key for f in findings}
    unexplained = sorted(k for k in keys if k not in accepted)
    assert not unexplained, (
        f"{kind}: new substitution-class site(s) with no reviewed reason:\n  "
        + "\n  ".join(f"{k}  (line {min(f.lineno for f in findings if f.key == k)})"
                      for k in unexplained)
        + "\n\nEither repair the site so the recorded label stays true, or add a row to the "
          "baseline in tests/test_substitution_class_sweep.py saying why it already does."
    )
    stale = sorted(k for k in accepted if k not in keys)
    assert not stale, (
        f"{kind}: baseline row(s) matching nothing in the tree -- a baseline that outlives its "
        f"site is a check that cannot fail: {stale}"
    )


class TestTheLiveTreeMatchesTheReviewedBaseline:

    def test_option_set_fallbacks(self):
        _baseline_check(_live_findings(scan_option_set_fallbacks),
                        ACCEPTED_OPTION_SET_GET, "OPTION_SET_GET")

    def test_selector_chain_fallthrough(self):
        _baseline_check(_live_findings(scan_selector_chain_fallthrough),
                        ACCEPTED_CHAIN_ELSE, "CHAIN_ELSE")

    def test_recovering_handlers(self):
        _baseline_check(_live_findings(scan_recovering_handlers),
                        ACCEPTED_HANDLER_RECOVERY, "HANDLER_RECOVERY")

    @pytest.mark.parametrize("selector,call", [
        ("continuous.boundary_policy", lambda: epoch_continuous(
            np.arange(500.0), np.array([0.1, 0.3]), win_s=(-0.02, 0.02), fs=1000.0,
            boundary_policy="bogus")),
        ("laminar.orientation", lambda: laminar_vflip(
            np.ones((10, 6)), np.linspace(1.0, 100.0, 6), contact_spacing=50.0,
            orientation="bogus")),
        ("spectral.model", lambda: relative_power(
            np.array([1.0, 2.0]), np.array([1.0, 1.0]), model="bogus")),
        ("statistics.alternative", lambda: _require_alternative("bogus", "sweep")),
        ("statistics.exact_sign_flip.alt", lambda: jnwb.exact_sign_flip(
            np.array([0.1, -0.2, 0.3]), alternative="bogus")),
        ("statistics.tail", lambda: cluster_permutation_test(
            np.ones((6, 4)), np.zeros((6, 4)), n_permutations=10, tail="bogus")),
        ("jrsa.alternative", lambda: jnwb.jrsa(
            np.random.default_rng(0).normal(size=(8, 20)),
            np.random.default_rng(1).normal(size=(8, 20)),
            adim=-1, metric="pearson", stats="permutation", permutations=20,
            alternative="bogus")),
    ])
    def test_every_accepted_chain_else_has_a_validator_that_really_rejects(
            self, selector, call):
        """A baseline row saying "validated upstream" that is never run is a proxy.

        Each accepted CHAIN_ELSE row claims the trailing ``else`` is unreachable from an
        out-of-domain selector. That claim is what makes the row an acceptance rather than a
        deferral, so it is driven here. If a validator is ever loosened, the corresponding
        ``else`` becomes a live substitution and this test is what says so.
        """
        with pytest.raises((ValueError, TypeError, NotImplementedError)):
            call()


# ===========================================================================
# The data half: measured vocabularies
# ===========================================================================

def _units_and_electrodes():
    electrodes = pd.DataFrame({
        "id": [0, 1, 2],
        "x": [0.0, 0.0, 0.0],
        "y": [0.0, 0.0, 0.0],
        "z": [200.0, 1800.0, 400.0],
        "location": ["V1", "V1", "V1"],
        "depth_unit": ["um", "um", "um"],
    }).set_index("id")
    units = pd.DataFrame({"peak_channel_id": [0, 1, 2], "quality": [1.0, 1.0, 0.0]})
    return units, electrodes


def _laminar_layer_vocabulary() -> FrozenSet[str]:
    n_ch = 24
    pitch = 50.0
    frame = pd.DataFrame({
        "x": np.zeros(n_ch),
        "y": np.zeros(n_ch),
        "z": np.arange(n_ch, dtype=float) * pitch,
        "channel_id": [f"ch_{i}" for i in range(n_ch)],
    })
    geom = jnwb.probe_geometry(frame, units="um", nominal_pitch=pitch)
    accepted = VFlipResult(
        crossover_contact=10.0,
        crossover_depth_um=10.0 * pitch,
        support_score=10.0,
        profile=np.zeros(n_ch),
        low_peak_contact=18,
        high_peak_contact=2,
        orientation="superficial_to_deep",
        accepted=True,
        rejection_reason=None,
        n_channels=n_ch,
        n_missing=0,
    )
    return frozenset(label_layers(accepted, geom, granular_thickness_um=400.0).values())


GEOMETRIC_VOCABULARY = frozenset({"Deep", "Superficial", "Unknown"})

ENRICH = "addressing.enrich_units_dataframe"


def _enrich_both_paths() -> Tuple[pd.DataFrame, pd.DataFrame]:
    units, electrodes = _units_and_electrodes()
    with_elec = enrich_units_dataframe(units, electrodes, depth_unit="um")
    without_elec = enrich_units_dataframe(units.drop(columns=["peak_channel_id"]), None)
    return with_elec, without_elec


def _emitted(frames: Tuple[pd.DataFrame, ...], column: str) -> FrozenSet[str]:
    """Every value ``column`` carries across ``frames``; empty when no frame has the column."""
    return frozenset().union(*(f[column].astype(str) for f in frames if column in f.columns))


def measured_vocabularies() -> Dict[str, Dict[str, FrozenSet[str]]]:
    """Execute every producer of a depth or layer name and record what it actually emits.

    One producer's two paths are one vocabulary: they are disjoint by construction (the
    absent-electrode path can only say 'Unknown'), which is not a collision between producers.
    """
    frames = _enrich_both_paths()
    return {
        "depth_class": {
            ENRICH: _emitted(frames, "depth_class"),
        },
        "layer": {
            # Measured rather than omitted, so a ``layer`` written again would collide below.
            ENRICH: _emitted(frames, "layer"),
            "laminar.label_layers": _laminar_layer_vocabulary(),
        },
    }


class TestTheDataHalfOfTheClass:
    """The geometric depth class, measured by execution rather than by reading call sites."""

    def test_the_measured_vocabularies_are_what_the_producers_really_emit(self):
        with_elec, without_elec = _enrich_both_paths()
        assert set(with_elec["depth_class"]) == {"Deep", "Superficial"}
        assert set(without_elec["depth_class"]) == {"Unknown"}
        vocab = measured_vocabularies()
        assert vocab["depth_class"][ENRICH] == GEOMETRIC_VOCABULARY
        assert vocab["layer"]["laminar.label_layers"] <= {"superficial", "input", "deep", "na"}

    def test_depth_class_carries_the_geometric_vocabulary_and_no_layer_is_emitted(self):
        """The geometric class is emitted under a name that says what it is.

        ``enrich_units_dataframe`` thresholds electrode depth once; ``label_layers`` emits the
        electrophysiological laminar identity. The two share no value, so the geometric class
        is emitted as ``depth_class`` and never as ``layer``, which leaves the name ``layer`` to
        one vocabulary and the collision scan with nothing to find.
        """
        with_elec, without_elec = _enrich_both_paths()
        for out in (with_elec, without_elec):
            assert set(out["depth_class"]) <= GEOMETRIC_VOCABULARY
            assert not set(out["depth_class"]) & _laminar_layer_vocabulary()
            assert "layer" not in out.columns
        assert list(with_elec["depth_class"]) == ["Superficial", "Deep", "Superficial"]

        collisions = scan_vocabulary_collisions(measured_vocabularies())
        assert collisions == [], collisions

    def test_the_absent_electrode_path_is_unknown_and_not_a_plausible_label(self):
        """No electrodes at all still yields a populated column, and its value is 'Unknown'."""
        _, out = _enrich_both_paths()
        assert set(out["depth_class"]) == {"Unknown"}, (
            "'Unknown' is the honest value here and must stay one; a geometric or laminar "
            "label on a table with no electrode geometry would be the class outright."
        )


# ===========================================================================
# The repaired sites, driven through the public API
# ===========================================================================

class TestTheRepairsFoundByThisSweep:

    def _pair(self):
        rng = np.random.default_rng(0)
        return rng.normal(size=(8, 40)), rng.normal(size=(8, 40))

    def test_an_unrecognised_reduction_raises_rather_than_averaging_silently(self):
        """Live hit, reachable from ``jrsa()``: a mistyped reduction was silently a mean.

        Before the repair, ``reduction={"aligned": "medain"}`` returned the *mean*-reduced
        value while ``result.parameters['reduction']`` echoed ``'medain'`` -- 06-15's shape
        exactly, in the same module, on the public path rather than latently.
        """
        x1, x2 = self._pair()
        with pytest.raises(ValueError, match="medain"):
            jnwb.jrsa(x1, x2, adim=-1, reduction={"aligned": "medain"},
                      metric="pearson", stats="none")

    def test_the_named_reductions_still_differ_from_each_other(self):
        """The repair must not have collapsed the ops it was protecting."""
        x1, x2 = self._pair()
        vals = {}
        for op in ("mean", "median", "sum", "max", "min"):
            r = jnwb.jrsa(x1, x2, adim=-1, reduction={"aligned": op},
                          metric="pearson", stats="none")
            vals[op] = float(np.asarray(r.value, dtype=float).ravel()[0])
        assert vals["mean"] != vals["median"], vals
        assert vals["max"] != vals["min"], vals

    def test_an_unrecognised_align_raises_rather_than_resampling_silently(self):
        """Latent hit, the same structural status P-31 had.

        ``_resample_axis``'s ``if/elif`` chain over ``align`` ended without an ``else``, so an
        unrecognised value returned both arrays untouched while ``_align_dimensions`` appended
        the axis to ``aligned_axes`` -- a claim that an alignment happened. Latent because
        ``jrsa()`` rejects unequal shapes before ``_align_dimensions`` can resample anything;
        reached here through the private function, which is where the defect lives.
        """
        from jnwb.jrsa import _align_dimensions
        rng = np.random.default_rng(0)
        a1, a2 = rng.normal(size=(8, 40)), rng.normal(size=(8, 25))
        with pytest.raises(ValueError, match="bogus"):
            _align_dimensions(a1, a2, {"aligned": 1}, "bogus", "fraction", False)

    def test_a_recognised_align_still_aligns(self):
        from jnwb.jrsa import _align_dimensions
        rng = np.random.default_rng(0)
        a1, a2 = rng.normal(size=(8, 40)), rng.normal(size=(8, 25))
        o1, o2, axes = _align_dimensions(a1, a2, {"aligned": 1}, "downsample", "fraction", False)
        assert o1.shape == o2.shape == (8, 25)
        assert axes == (1,)

    def test_aligned_axes_is_never_claimed_without_a_resample(self):
        """The claim that made the silent no-op plausible."""
        from jnwb.jrsa import _align_dimensions
        rng = np.random.default_rng(0)
        a1, a2 = rng.normal(size=(8, 40)), rng.normal(size=(8, 40))
        o1, o2, axes = _align_dimensions(a1, a2, {"aligned": 1}, "downsample", "fraction", False)
        assert axes == ()
