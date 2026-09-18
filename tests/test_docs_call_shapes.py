"""Every documented call shape must match the signature that ships.

Six documented calls had drifted far enough to raise `TypeError` on the first line a reader
would copy, and one page taught a two-step composition backwards by passing the first step's
inputs to the second step instead of its output. Executing the blocks would not have caught
them: most documentation snippets are fragments over variables the page never defines, so
they are not runnable, and an execute-everything test skips exactly the pages where the
drift is. These parse the blocks instead, which needs no fixtures and covers fragments.

What this does not check: that a documented argument's *value* makes sense, or that
positional arguments are the right objects. `build_representation_ladder(X, labels)` is
caught here only because it passes two positionals to a one-positional signature; had the
arity matched, passing a label vector where a raster belongs would still read as correct.
"""

import ast
import builtins
import inspect
import re
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")  # headless, as in the other test modules that draw

import jnwb

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted((ROOT / "docs").rglob("*.md")) + [ROOT / "README.md"]
BLOCK = re.compile(r"^```python\n(.*?)^```", re.M | re.S)


UNPARSEABLE = []


def _documented_calls():
    """Every `jnwb.<name>(...)`, and bare `<name>(...)` for names the block imports from jnwb."""
    for page in PAGES:
        for index, body in enumerate(BLOCK.findall(page.read_text(encoding="utf-8"))):
            try:
                tree = ast.parse(body)
            except SyntaxError as exc:
                UNPARSEABLE.append(
                    f"{page.relative_to(ROOT).as_posix()} block {index}: {exc.msg} "
                    f"(line {exc.lineno})"
                )
                continue
            imported = {
                alias.asname or alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("jnwb")
                for alias in node.names
            }
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                        and func.value.id == "jnwb"):
                    name = func.attr
                elif isinstance(func, ast.Name) and func.id in imported:
                    name = func.id
                else:
                    continue
                fn = getattr(jnwb, name, None)
                if not callable(fn):
                    continue
                try:
                    yield page.relative_to(ROOT).as_posix(), name, node, inspect.signature(fn)
                except (TypeError, ValueError):
                    continue


CALLS = list(_documented_calls())


def test_the_sweep_reaches_the_documentation_it_claims_to_check():
    """Without this the two tests below pass by finding nothing at all."""
    assert len(CALLS) > 100, f"only {len(CALLS)} documented jnwb calls found"
    assert len({page for page, _, _, _ in CALLS}) >= 8
    assert {"docs/05_artifact_detection_and_repair.md",
            "docs/06_spikes_psth_and_onset_dynamics.md",
            "docs/09_decoding_and_visual_qc.md"} <= {page for page, _, _, _ in CALLS}


def test_every_python_block_in_the_documentation_parses():
    """A block that stops parsing leaves this file's coverage silently.

    Writing this test, a paragraph of prose was pasted inside a fence in
    `docs/05_artifact_detection_and_repair.md`. The block became invalid Python, the sweep
    below skipped it, and every check still passed -- while the page a reader copies from
    was broken. All 113 blocks parse, so nothing has to be skipped and this asserts that
    rather than tolerating it.
    """
    assert not UNPARSEABLE, (
        "python-fenced blocks that are not valid Python, so no call in them is checked:\n  "
        + "\n  ".join(UNPARSEABLE)
    )


def test_no_documented_keyword_is_unknown_to_the_live_signature():
    wrong = []
    for page, name, node, sig in CALLS:
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            continue
        for kw in node.keywords:
            if kw.arg is not None and kw.arg not in sig.parameters:
                wrong.append(f"{page}: {name}(..., {kw.arg}=...) -- live takes "
                             f"{sorted(sig.parameters)}")
    assert not wrong, "documented keywords that raise TypeError:\n  " + "\n  ".join(wrong)


def test_no_documented_call_passes_more_positionals_than_the_signature_accepts():
    wrong = []
    for page, name, node, sig in CALLS:
        if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values()):
            continue
        slots = [p for p in sig.parameters.values()
                 if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                               inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        if len(node.args) > len(slots):
            wrong.append(f"{page}: {name} is given {len(node.args)} positional arguments; "
                         f"the signature accepts {len(slots)} ({sorted(sig.parameters)})")
    assert not wrong, "documented calls that raise TypeError:\n  " + "\n  ".join(wrong)


@pytest.mark.parametrize("field", ["phase_gradient", "wpli_profile"])
def test_docs_11_does_not_document_zflip_fields_that_do_not_exist(field):
    """Section 9.2 named two `zflip` result fields that were never on the result.

    `docs/02` states the correct contract, so the two pages contradicted each other and the
    wrong one was the only documentation those estimators had.
    """
    from jnwb.laminar import ZFlipResult

    live = set(getattr(ZFlipResult, "__dataclass_fields__", {}))
    assert field not in live, (
        f"{field} exists now; this test is asserting the wrong direction and should be "
        "replaced by one that checks the documentation mentions it"
    )
    text = (ROOT / "docs" / "11_extending_and_development.md").read_text(encoding="utf-8")
    assert field not in text, (
        f"docs/11 documents ZFlipResult.{field}, which is not a field of the result; "
        f"the live fields are {sorted(live)}"
    )


# --- executing the blocks that can be executed -------------------------------------------

BUILTINS = set(dir(builtins))
#: Extensions that mean the block opens a recording, so it needs data rather than only the
#: package. Matched by the file the block names, not by its position on the page.
DATA_SUFFIXES = (".nwb", ".npz")
#: MkDocs includes the tutorial scripts into ```python fences with this directive. It is
#: valid Python by accident -- `(- -8) < (- - "path")` -- so it parses and then raises.
INCLUDE_DIRECTIVE = "--8<--"


def _free_names(tree):
    """Names the block reads without binding. Empty means it needs nothing from a reader."""
    bound, used = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            (bound if isinstance(node.ctx, (ast.Store, ast.Del)) else used).add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bound |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
            if hasattr(node, "args"):
                bound |= {a.arg for a in node.args.args + node.args.kwonlyargs}
        elif isinstance(node, ast.comprehension):
            bound |= {t.id for t in ast.walk(node.target) if isinstance(t, ast.Name)}
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars:
                    bound |= {t.id for t in ast.walk(item.optional_vars)
                              if isinstance(t, ast.Name)}
    return used - bound - BUILTINS


def _runnable_blocks():
    """Blocks that need nothing but the installed package: no free names, no data, no include."""
    out = []
    for page in PAGES:
        for index, body in enumerate(BLOCK.findall(page.read_text(encoding="utf-8"))):
            if INCLUDE_DIRECTIVE in body or any(s in body for s in DATA_SUFFIXES):
                continue
            try:
                tree = ast.parse(body)
            except SyntaxError:
                continue  # already failed by test_every_python_block_in_the_documentation_parses
            if not _free_names(tree):
                out.append(pytest.param(body, id=f"{page.relative_to(ROOT).as_posix()}#{index}"))
    return out


RUNNABLE = _runnable_blocks()


def test_the_documentation_still_contains_blocks_a_reader_can_run():
    """Without this, tightening the runnable filter to zero blocks would read as success."""
    assert len(RUNNABLE) >= 12, f"only {len(RUNNABLE)} runnable documentation blocks found"


@pytest.mark.parametrize("block", RUNNABLE)
def test_runnable_documentation_blocks_execute_outside_the_checkout(block, tmp_path,
                                                                   monkeypatch):
    """Runs each self-contained block with the working directory outside the repository.

    The working directory matters: the suite runs from the repository root with
    `pythonpath = ["."]`, so a block that reaches for a relative path finds the checkout and
    passes for a reason a reader installing from PyPI does not have. Running from a
    temporary directory removes that.

    This overlaps `test_readme_smoke.py::test_readme_quickstart_blocks_execute` on README's
    blocks deliberately: that one runs them in the tree, this one outside it, and a
    difference between the two is the defect.
    """
    monkeypatch.chdir(tmp_path)
    exec(compile(block, "documentation", "exec"), {"__name__": "__doc_block__"})  # noqa: S102
