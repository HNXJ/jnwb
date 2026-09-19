"""Nothing new may join the package without a caller, and the exceptions must say why.

The stack item behind this file asked for "zero unreferenced module-level symbols in
jnwb/". That target is not reachable and should not be: three of the symbols with no
caller inside this repository have live callers in a downstream consumer, verified by
grep over that tree rather than inferred from its absence here.

So the criterion is an allowlist with reasons instead of a count. A symbol nothing
reaches is either listed below with the evidence that it is wanted, or it is dead and
this fails.

The scan is deliberately generous about what counts as a reference -- any occurrence of
the name in jnwb/, tests/, examples/, docs/, skills/ or scripts/ outside its own
definition, including inside a docstring or a skill file. A symbol that survives that is
genuinely unreached.
"""

import ast
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "jnwb"
SEARCH_DIRS = ("jnwb", "tests", "examples", "docs", "skills", "scripts")
SUFFIXES = (".py", ".md", ".txt", ".yml", ".yaml")

# name -> why it stays. Adding a line here is a claim that something wants the symbol;
# make it one a reader can check.
ALLOWED = {
    "compare_old_new_criteria": (
        "Downstream: jnwb_ext/unit_inclusion.py imports it and "
        "classify_units_omission_inclusion_v1.py calls it. Promoted out of that repo "
        "2026-08-23, which is what its docstring means by 'downstream unit inclusion "
        "curation pipelines'."
    ),
    "old_new_summary_table": (
        "Downstream: same importer and pipeline as compare_old_new_criteria, called "
        "with group_cols=('area', 'quality_tier')."
    ),
    # coef_rows was exempted here as reachable only from downstream repositories. 05-83
    # measured that swapping its ci_lo for its ci_hi changed a returned number and survived
    # the whole suite, so tests/test_estimator_values_are_pinned.py now calls it and the
    # exemption is spent. The downstream callers are still real; they are no longer the
    # only ones.
    "MADELANE_VIOLET": "Palette member; MADELANE_GOLD from the same set is used.",
    "MADELANE_WHITE": "Palette member; MADELANE_GOLD from the same set is used.",
    "MADELANE_GRAY": "Palette member; MADELANE_GOLD from the same set is used.",
    "MADELANE_TEAL": "Palette member; MADELANE_GOLD from the same set is used.",
    "MADELANE_ORANGE": "Palette member; MADELANE_GOLD from the same set is used.",
}


WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SELF = Path(__file__).resolve()


def _corpus_counts():
    """Every identifier-shaped token in the search corpus, counted once.

    This file is excluded: listing a name in ALLOWED is an exemption, not a use, and
    counting it would make every entry look reached the moment it was written down.
    """
    total = Counter()
    for d in SEARCH_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not (p.is_file() and p.suffix in SUFFIXES):
                continue
            if "__pycache__" in p.parts or p.resolve() == SELF:
                continue
            total.update(WORD.findall(p.read_text(encoding="utf-8", errors="replace")))
    return total


def _module_level(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node.lineno
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    yield t.id, node.lineno
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            yield node.target.id, node.lineno


@pytest.fixture(scope="module")
def unreferenced():
    total = _corpus_counts()
    found = {}
    for py in sorted(PKG.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        for name, lineno in _module_level(py):
            if name.startswith("__") and name.endswith("__"):
                continue
            # one occurrence is the definition itself
            if total[name] - 1 <= 0:
                found[name] = f"{py.relative_to(ROOT).as_posix()}:{lineno}"
    return found


def test_no_unlisted_symbol_is_unreachable(unreferenced):
    extra = {n: where for n, where in unreferenced.items() if n not in ALLOWED}
    assert not extra, (
        "module-level symbols nothing reaches, and not listed in ALLOWED: "
        + ", ".join(f"{n} ({w})" for n, w in sorted(extra.items()))
        + ". Either give it a caller, delete it, or add it to ALLOWED with the evidence "
        "that something outside this repository wants it."
    )


def test_the_allowlist_has_not_outlived_its_entries(unreferenced):
    """An entry that has since gained a caller is stale and should be dropped."""
    stale = sorted(set(ALLOWED) - set(unreferenced))
    assert not stale, (
        f"these are referenced now and no longer need an exemption: {stale}"
    )


def test_every_exemption_states_a_reason():
    for name, reason in ALLOWED.items():
        assert len(reason) > 40, f"{name}'s exemption does not say anything checkable"
