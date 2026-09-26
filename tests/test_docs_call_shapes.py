"""Every documented call shape must match the signature that ships.

Six documented calls had drifted far enough to raise `TypeError` on the first line a reader
would copy, and one page taught a two-step composition backwards by passing the first step's
inputs to the second step instead of its output. Executing the blocks would not have caught
them: most documentation snippets are fragments over variables the page never defines, so
they are not runnable, and an execute-everything test skips exactly the pages where the
drift is. These parse the blocks instead, which needs no fixtures and covers fragments.

**Why this module's coverage is asserted rather than described.** The first version of it
was green while ten documented-call defects were found by hand (P-84), for three recorded
reasons and a fourth found while repairing them -- all coverage rather than logic. The three:
the positional check compared
`len(node.args) > len(slots)` and so never saw a call with *too few* arguments; the collector
required the receiver to be the bare name `jnwb`, so every `jnwb.visual_qc.f(...)` was
skipped outright; and `docs/10_operation_specifications.md` contains no ```python fence at
all, so the page documenting the most operations was not in the corpus. The fourth is at
`_collect_jnwb_imports`, and it was found only because reintroducing P-78 as a discriminator
did not fail: fixing the three recorded causes was not sufficient to catch it.
A docstring claiming otherwise is what let all of this stand. `COVERED_PAGES`, `CALL_FORMS`,
`SPEC_ROW_COUNT` and
`SPEC_STRATEGIES` below are the claim, they are literals, and the tests compare the live
sweep against them in both directions -- a page that drops out of reach fails, and a page
that comes into reach without being declared fails too.

Those four constants are deliberately *not* computed from the corpus. A statement derived
from the thing it describes is satisfied by anything, including the empty corpus: that is the
shape of defect this module exists to catch, so it must not be the shape of its own guard.

What this still does not check: that a documented argument's *value* makes sense, or that a
positional argument is the right kind of object. `plot_noise_vs_signal(lfp_segments,
spike_trains)` passed two positionals to a `(units_df, figsize=...)` signature and bound
cleanly; `assign_quality_tier(quality="good", ...)` names three real parameters and passes
scalars where Series belong. Both were real defects and neither is a call *shape*. The
signature is the oracle here, and the signature does not carry those facts.
"""

import ast
import builtins
import importlib
import inspect
import re
from collections import Counter
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")  # headless, as in the other test modules that draw

import jnwb

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted((ROOT / "docs").rglob("*.md")) + [ROOT / "README.md"]
BLOCK = re.compile(r"^```python\n(.*?)^```", re.M | re.S)


# --- the coverage claim ------------------------------------------------------------------
# Literals, checked below. Never derive these from the sweep they describe.

#: Pages on which the fenced-block sweep resolves at least one call to a live jnwb callable.
COVERED_PAGES = frozenset({
    "README.md",
    "docs/02_paths_addressing_metadata.md",
    "docs/03_representational_similarity_jrsa.md",
    "docs/04_spectral_analysis_and_tfr.md",
    "docs/05_artifact_detection_and_repair.md",
    "docs/06_spikes_psth_and_onset_dynamics.md",
    "docs/07_statistical_inference_and_nulls.md",
    "docs/08_directed_connectivity_and_information.md",
    "docs/09_decoding_and_visual_qc.md",
    "docs/common_mistakes.md",
    "docs/errors.md",
    "docs/index.md",
    "docs/quickstart.md",
    "docs/vis.md",
})

#: Receiver shapes the collector resolves. The third and fourth were added by 06-100; before
#: it, a call reached through a submodule or through an aliased import was silently dropped.
FORM_TOP = "jnwb.<name>(...)"
FORM_DOTTED = "jnwb.<module>.<name>(...) and deeper"
FORM_IMPORTED = "<name>(...) where the block imports <name> from jnwb"
FORM_IMPORTED_ATTR = "<alias>.<name>(...) where the block imports <alias> from jnwb"
#: How many of each the documentation holds, as a ratchet rather than a bare presence flag.
#: Presence alone is too weak: P-78 was a *partial* under-reach -- three `stats.<name>(...)`
#: calls were collected and two on the same page were not, so a check asking only whether
#: the form occurs at all would have stayed green over the defect that was there.
CALL_FORMS = {
    FORM_TOP: 147,
    FORM_DOTTED: 8,
    FORM_IMPORTED: 10,
    FORM_IMPORTED_ATTR: 5,
}

#: `docs/10_operation_specifications.md` documents call shapes in a markdown table rather
#: than in a fence, so it needs its own collector. These are its data rows and the three
#: ways a row is resolved to something with parameters.
SPEC_PAGE = "docs/10_operation_specifications.md"
SPEC_ROW_COUNT = 11
STRATEGY_SIGNATURE = "the Operation names a callable in the Module Location"
STRATEGY_CALL_FORMS = "the Input column holds call forms against a named class"
STRATEGY_MODULE_UNION = "the Operation names a module; any of its callables may own the name"
SPEC_STRATEGIES = frozenset({STRATEGY_SIGNATURE, STRATEGY_CALL_FORMS, STRATEGY_MODULE_UNION})


UNPARSEABLE = []


def _receiver_chain(func):
    """`['jnwb', 'visual_qc', 'plot_x']` for `jnwb.visual_qc.plot_x`, else None."""
    parts, node = [], func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return list(reversed(parts))


def _collect_jnwb_imports(tree, into):
    """Add `{bound name: (module, original name)}` for each `from jnwb... import ...`.

    Accumulated per *page*, not per block. A documentation page imports once near the top
    and then uses the name in every later fence, so rebuilding this map per block made every
    such call invisible -- which is how `stats.exploratory_compare(..., rng=...)` (P-78)
    stayed green: the import is in the fence at `docs/07:23-49` and the call is in the one
    at `:59-70`.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("jnwb"):
            for alias in node.names:
                into[alias.asname or alias.name] = (node.module, alias.name)
    return into


def _resolve_root(root, imported):
    """The live object a receiver's leftmost name refers to, and the form label, or None."""
    if root == "jnwb":
        return jnwb, FORM_TOP
    if root in imported:
        module, original = imported[root]
        obj = None
        try:
            obj = getattr(importlib.import_module(module), original, None)
        except ImportError:
            obj = None
        if obj is None:  # re-exported at the top level but not where the page imports it
            obj = getattr(jnwb, original, None)
        return (obj, FORM_IMPORTED) if obj is not None else None
    return None


def _documented_calls():
    """Every call in a ```python fence whose receiver resolves into the installed package."""
    for page in PAGES:
        rel = page.relative_to(ROOT).as_posix()
        imported = {}
        for index, body in enumerate(BLOCK.findall(page.read_text(encoding="utf-8"))):
            try:
                tree = ast.parse(body)
            except SyntaxError as exc:
                UNPARSEABLE.append(f"{rel} block {index}: {exc.msg} (line {exc.lineno})")
                continue
            _collect_jnwb_imports(tree, imported)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                parts = _receiver_chain(node.func)
                if parts is None:
                    continue
                resolved = _resolve_root(parts[0], imported)
                if resolved is None:
                    continue
                obj, form = resolved
                # `jnwb.f` is one attribute past the root; anything longer went through a
                # submodule or a class, which is the branch P-84 cause (b) did not have.
                if form is FORM_TOP and len(parts) > 2:
                    form = FORM_DOTTED
                elif form is FORM_IMPORTED and len(parts) > 1:
                    form = FORM_IMPORTED_ATTR
                for attr in parts[1:]:
                    obj = getattr(obj, attr, None)
                    if obj is None:
                        break
                if not callable(obj):
                    continue
                try:
                    sig = inspect.signature(obj)
                except (TypeError, ValueError):
                    continue
                if next(iter(sig.parameters), None) in ("self", "cls"):
                    # An unbound method reached through its class. The documented call is on
                    # an instance, so the receiver supplies the first parameter and binding
                    # the documented arguments against this signature would be off by one.
                    continue
                yield rel, ".".join(parts), node, sig, form


CALLS = list(_documented_calls())
OBSERVED_PAGES = frozenset(page for page, _, _, _, _ in CALLS)
OBSERVED_FORMS = Counter(form for _, _, _, _, form in CALLS)


def test_the_sweep_reaches_exactly_the_pages_it_claims_to_reach():
    """The corpus claim, checked in both directions rather than described in prose.

    Under-reach is the P-84 failure: a page silently leaves the corpus and every check stays
    green. Over-reach matters too -- a page that starts being checked without being declared
    means the declaration is no longer the thing anyone reads it as.
    """
    assert OBSERVED_PAGES == COVERED_PAGES, (
        "the sweep no longer covers what this module declares:\n"
        f"  declared but not reached: {sorted(COVERED_PAGES - OBSERVED_PAGES)}\n"
        f"  reached but not declared: {sorted(OBSERVED_PAGES - COVERED_PAGES)}"
    )
    assert len(CALLS) > 150, f"only {len(CALLS)} documented jnwb calls found"


def test_every_declared_call_form_is_exercised_by_the_documentation():
    """A receiver shape the collector stops resolving would otherwise cost nothing.

    Dropping the dotted branch turns `jnwb.visual_qc.f(...)` back into a skip and no
    assertion below notices, because a call that is never collected is never wrong.
    """
    declared, observed = set(CALL_FORMS), set(OBSERVED_FORMS)
    assert observed == declared, (
        "the call forms this module declares are not the ones it exercises:\n"
        f"  declared but unexercised: {sorted(declared - observed)}\n"
        f"  exercised but undeclared: {sorted(observed - declared)}"
    )
    thin = {form: (OBSERVED_FORMS[form], floor)
            for form, floor in CALL_FORMS.items() if OBSERVED_FORMS[form] < floor}
    assert not thin, (
        "fewer calls resolve through these receiver shapes than this module declares, so "
        "some are being skipped: " + "; ".join(
            f"{form}: {got} < {floor}" for form, (got, floor) in sorted(thin.items()))
        + ". If the documentation genuinely lost calls, lower the literal deliberately."
    )


def test_every_python_block_in_the_documentation_parses():
    """A block that stops parsing leaves this file's coverage silently.

    Writing this test, a paragraph of prose was pasted inside a fence in
    `docs/05_artifact_detection_and_repair.md`. The block became invalid Python, the sweep
    below skipped it, and every check still passed -- while the page a reader copies from
    was broken. Every block parses, so nothing has to be skipped and this asserts that
    rather than tolerating it.
    """
    assert not UNPARSEABLE, (
        "python-fenced blocks that are not valid Python, so no call in them is checked:\n  "
        + "\n  ".join(UNPARSEABLE)
    )


def test_no_documented_keyword_is_unknown_to_the_live_signature():
    wrong = []
    for page, name, node, sig, _ in CALLS:
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            continue
        for kw in node.keywords:
            if kw.arg is not None and kw.arg not in sig.parameters:
                wrong.append(f"{page}: {name}(..., {kw.arg}=...) -- live takes "
                             f"{sorted(sig.parameters)}")
    assert not wrong, "documented keywords that raise TypeError:\n  " + "\n  ".join(wrong)


def test_no_documented_call_passes_more_positionals_than_the_signature_accepts():
    wrong = []
    for page, name, node, sig, _ in CALLS:
        if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values()):
            continue
        slots = [p for p in sig.parameters.values()
                 if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                               inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        if len(node.args) > len(slots):
            wrong.append(f"{page}: {name} is given {len(node.args)} positional arguments; "
                         f"the signature accepts {len(slots)} ({sorted(sig.parameters)})")
    assert not wrong, "documented calls that raise TypeError:\n  " + "\n  ".join(wrong)


def test_every_documented_call_binds_against_the_live_signature():
    """The two checks above are one-sided; `bind` is the whole arity contract.

    `len(node.args) > len(slots)` cannot see a call that supplies too *few* arguments, which
    is how `build_time_resolved_matrix(spike_matrices)` stayed green against a signature
    requiring `(session, area, epochs_df)` (P-71). `Signature.bind` is the same rule the
    interpreter applies at the call site, so missing required arguments, surplus
    positionals and unknown keywords all fail here rather than only two of the three.
    """
    wrong = []
    for page, name, node, sig, _ in CALLS:
        if any(isinstance(a, ast.Starred) for a in node.args):
            continue  # `f(*args)`: the arity is not in the text
        if any(kw.arg is None for kw in node.keywords):
            continue  # `f(**kwargs)`: likewise
        try:
            sig.bind(*[_ARG] * len(node.args), **{kw.arg: _ARG for kw in node.keywords})
        except TypeError as exc:
            wrong.append(
                f"{page}: {name}({len(node.args)} positional, "
                f"{sorted(kw.arg for kw in node.keywords)} by keyword) -- {exc}; "
                f"live signature is {sig}"
            )
    assert not wrong, "documented calls that raise TypeError:\n  " + "\n  ".join(wrong)


#: Stands in for a documented argument. Only its presence is checked, never its type -- see
#: the module docstring on what that leaves uncovered.
_ARG = object()


# --- the operation specification table ----------------------------------------------------
# `docs/10` documents more operations than any other page and carries no ```python fence, so
# the sweep above cannot see it. Its Input & Shapes column is the call shape.

CODE_SPAN = re.compile(r"`([^`]+)`")
#: `lfp_matrix`, or `mode: str = "fixed"` -- the parameter name is what precedes the colon.
SPEC_PARAM = re.compile(r"^([a-z_][A-Za-z0-9_]*)\s*(?::|$)")
#: `clopper_pearson(k, n, alpha)` written inside the Input column instead of a name list.
SPEC_CALL = re.compile(r"^[a-z_][A-Za-z0-9_]*\(.*\)$")


def _spec_table_rows():
    """Data rows of the operation table, as `(operation, module_cell, input_cell)`."""
    text = (ROOT / SPEC_PAGE).read_text(encoding="utf-8")
    # The operation table is the one under this heading; section 1 carries other tables.
    heading = "\n## 2. Operation Specifications\n"
    assert text.count(heading) == 1, f"{SPEC_PAGE} lost its operation-table heading"
    text = text.split(heading, 1)[1]
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        body = line.strip().strip("|")
        if set(body) <= set("-| "):
            continue  # the |---|---| separator
        cells = [c.strip() for c in body.split("|")]
        if cells[0] == "Operation":
            continue  # the header
        rows.append((cells[0], cells[1], cells[2]))
    return rows


def _module_union(module):
    """Every parameter name of every callable the module itself defines."""
    names = set()
    for attr, obj in vars(module).items():
        if attr.startswith("_") or not callable(obj):
            continue
        if getattr(obj, "__module__", None) != module.__name__:
            continue
        try:
            names |= set(inspect.signature(obj).parameters)
        except (TypeError, ValueError):
            continue
    return names


def _resolve_spec_row(operation, module_cell, input_cell):
    """`(strategy, accepted names, signature or None, call forms)` for one table row."""
    op_spans = CODE_SPAN.findall(operation)
    mod_spans = CODE_SPAN.findall(module_cell)
    module = None
    if mod_spans:
        try:
            module = importlib.import_module(mod_spans[0])
        except ImportError:
            module = None
    if module is None:
        return None

    target = getattr(module, op_spans[0], None) if op_spans else None
    if callable(target):
        try:
            sig = inspect.signature(target)
        except (TypeError, ValueError):
            sig = None
        if sig is not None:
            return STRATEGY_SIGNATURE, set(sig.parameters), sig, []

    calls = [s for s in CODE_SPAN.findall(input_cell) if SPEC_CALL.match(s)]
    if calls and len(mod_spans) > 1:
        owner = getattr(module, mod_spans[1], None)
        if owner is not None:
            return STRATEGY_CALL_FORMS, set(), None, [(owner, c) for c in calls]

    return STRATEGY_MODULE_UNION, _module_union(module), None, []


def _documented_spec_names(input_cell):
    return [m.group(1) for m in
            (SPEC_PARAM.match(s) for s in CODE_SPAN.findall(input_cell)) if m]


SPEC_ROWS = _spec_table_rows()
SPEC_RESOLVED = [(op, mod, inp, _resolve_spec_row(op, mod, inp))
                 for op, mod, inp in SPEC_ROWS]


def test_the_specification_table_is_in_the_corpus_and_every_row_resolves():
    """P-84 cause (c): this page held two of the ten defects and was never read at all.

    A row that stops resolving is the same failure one row at a time -- it silently stops
    being checked -- so an unresolved row fails here rather than being skipped.
    """
    assert len(SPEC_ROWS) == SPEC_ROW_COUNT, (
        f"{SPEC_PAGE} has {len(SPEC_ROWS)} operation rows; this module is written against "
        f"{SPEC_ROW_COUNT}. Add the row's parameters to the check before updating the count."
    )
    unresolved = [op for op, _, _, r in SPEC_RESOLVED if r is None]
    assert not unresolved, f"specification rows that resolve to nothing: {unresolved}"
    used = frozenset(r[0] for _, _, _, r in SPEC_RESOLVED if r is not None)
    assert used == SPEC_STRATEGIES, (
        "the row-resolution strategies this module declares are not the ones it uses:\n"
        f"  declared but unused: {sorted(SPEC_STRATEGIES - used)}\n"
        f"  used but undeclared: {sorted(used - SPEC_STRATEGIES)}"
    )


def test_no_specification_row_documents_a_parameter_that_does_not_exist():
    """`probe_geom`, `corr_matrix`, `coords`, `n_times` and `cross_spec` all lived here."""
    wrong = []
    for operation, _, input_cell, resolved in SPEC_RESOLVED:
        if resolved is None:
            continue
        strategy, accepted, _, _ = resolved
        if strategy is STRATEGY_CALL_FORMS:
            continue
        for name in _documented_spec_names(input_cell):
            if name not in accepted:
                wrong.append(f"{SPEC_PAGE}: {operation} documents an input `{name}` that is "
                             f"not a parameter of what it names ({sorted(accepted)})")
    assert not wrong, "specification inputs that do not exist:\n  " + "\n  ".join(wrong)


def test_no_specification_row_omits_a_parameter_the_call_requires():
    """The zflip row documented a `cross_spec` that does not exist and no `fs`, which the
    signature requires. Renaming the first without adding the second still leaves a reader
    unable to make the documented call."""
    wrong = []
    for operation, _, input_cell, resolved in SPEC_RESOLVED:
        if resolved is None or resolved[0] is not STRATEGY_SIGNATURE:
            continue
        sig = resolved[2]
        documented = set(_documented_spec_names(input_cell))
        required = [p.name for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty
                    and p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                                   inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                   inspect.Parameter.KEYWORD_ONLY)]
        missing = [r for r in required if r not in documented]
        if missing:
            wrong.append(f"{SPEC_PAGE}: {operation} requires {missing}, which the Input & "
                         f"Shapes column does not document (it documents "
                         f"{sorted(documented)})")
    assert not wrong, "required parameters absent from the table:\n  " + "\n  ".join(wrong)


def test_every_call_form_written_into_the_specification_table_binds():
    wrong = []
    for operation, _, _, resolved in SPEC_RESOLVED:
        if resolved is None or resolved[0] is not STRATEGY_CALL_FORMS:
            continue
        for owner, source in resolved[3]:
            node = ast.parse(source, mode="eval").body
            fn = getattr(owner, node.func.id, None)
            if fn is None or not callable(fn):
                wrong.append(f"{SPEC_PAGE}: {operation} documents `{source}`, and "
                             f"{owner.__name__} has no `{node.func.id}`")
                continue
            sig = inspect.signature(fn)
            try:
                sig.bind(*[_ARG] * len(node.args),
                         **{kw.arg: _ARG for kw in node.keywords})
            except TypeError as exc:
                wrong.append(f"{SPEC_PAGE}: {operation} documents `{source}` -- {exc}; "
                             f"live signature is {sig}")
    assert not wrong, "specification call forms that raise:\n  " + "\n  ".join(wrong)


@pytest.mark.parametrize("field", ["phase_gradient", "wpli_profile"])
def test_the_spec_page_does_not_document_zflip_fields_that_do_not_exist(field):
    """The operation table named two `zflip` result fields that were never on the result.

    `docs/02` states the correct contract, so the two pages contradicted each other and the
    wrong one was the only documentation those estimators had. The table was section 9.2 of
    `docs/11_extending_and_development.md` when this was written and is now
    `docs/10_operation_specifications.md`, a page of its own.
    """
    from jnwb.laminar import ZFlipResult

    live = set(getattr(ZFlipResult, "__dataclass_fields__", {}))
    assert field not in live, (
        f"{field} exists now; this test is asserting the wrong direction and should be "
        "replaced by one that checks the documentation mentions it"
    )
    text = (ROOT / SPEC_PAGE).read_text(encoding="utf-8")
    # A word match: `synth_phase_gradient` names a builder, not the field.
    assert not re.search(rf"\b{field}\b", text), (
        f"the spec page documents ZFlipResult.{field}, which is not a field of the "
        f"result; "
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
