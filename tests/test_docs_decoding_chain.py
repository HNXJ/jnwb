"""A diagram edge is a claim about composition, and the signatures settle it.

`docs/09_decoding_and_visual_qc.md` drew `build_inner_validation_partitions -->
nested_cv_linear_svm`, and the same screen explained in bold that the decoder takes no
`groups` argument. Its parameters are `{X, labels, n_splits, rng}`; nothing in it can
receive a partition table. A second edge on the same diagram, `nested_cv_linear_svm -->
majority_baseline / fold_majority_baseline`, was false the same way: the decoder returns a
metrics dict, and both baselines take label vectors. No test anywhere pinned a mermaid
edge, so the page could contradict its own prose indefinitely.

The check reads the arrows out of the page and settles each one against
`inspect.signature`, so it is a statement about the API rather than about the page's
wording. A prose snapshot would have broken on rewording while passing on a reversed
meaning.

**What would make each check below pass while the invariant it names is violated.**

- `test_every_drawn_composition_is_accepted_by_the_live_signature` could pass over zero
  edges: the fence regex stops matching, a page drops its diagram, or the tokenizer
  rejects every line. Held by `test_the_diagram_survey_is_not_vacuous`, which requires
  pages, edges, and function-to-function edges among them, and requires the decoding page
  to contribute one.
- It could pass by widening what an annotation means. Unwrapping a subscripted generic
  into its members is the specific bypass: `nested_cv_linear_svm` returns
  `Dict[str, Union[float, np.ndarray, dict, str]]`, so a normaliser that descended into
  the subscript would find `np.ndarray` there and accept the false edge into
  `majority_baseline(labels: np.ndarray)`. `_annotation_names` therefore reduces a
  subscripted generic to its origin and descends only through `Union`/`Optional`, which
  genuinely are alternatives. Held by `test_a_dict_return_does_not_satisfy_its_value_types`.
- It could pass by treating a missing annotation as a wildcard. `_annotation_names`
  returns the empty set for an unannotated parameter or return, which intersects nothing,
  so an unannotated signature fails the edge rather than absolving it. Held by
  `test_an_unannotated_signature_fails_closed`.
- It could pass by matching two operations on `None`. A return of nothing and the null
  half of an `Optional[...]` parameter normalise to the same token, and the shipped API
  has a live instance: `Alignment` is annotated `-> None` and `JRSAResult` takes
  `Optional[np.ndarray]`, so a plain intersection accepted an edge between two operations
  that compose in no direction. Found while mutating this module rather than by reading
  it. Held by `test_a_producer_that_returns_nothing_cannot_feed_an_optional_parameter`.
- It could pass by resolving no symbols at all, leaving every edge classified as prose.
  Held by the function-to-function floor in the vacuity test, and by
  `test_node_labels_resolve_by_head_not_by_prose`, which pins both directions: a label
  whose head names an operation resolves, and an operation named only in a trailing prose
  clause does not.
- `test_the_documented_partition_chain_executes` could pass on annotations alone while the
  frames refuse each other at the column level, which is what `pd.DataFrame` to
  `pd.DataFrame` cannot see. It runs the chain and requires the consumer to reject a raw
  trial table, so the declared dependency is the real one.
- `test_a_value_the_diagram_routes_onward_is_used_by_the_page` could pass by dropping the
  outgoing edge instead of using the value. That is not a bypass: an operation the diagram
  no longer routes onward is exempt because the page has stopped claiming it flows, and
  any edge it does draw is settled by the first test. The two close the loop between the
  prose, the picture and the worked example.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pandas as pd
import pytest

import jnwb
from jnwb._lazy_exports import OPTIONAL_SUBMODULES

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
DECODING_PAGE = DOCS / "09_decoding_and_visual_qc.md"

MERMAID = re.compile(r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
PYTHON = re.compile(r"^```python[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: Public callables, taken from the shipped symbol list rather than a list written here. An
#: optional submodule is a module, so it is never one of them, and is not imported to find out.
PUBLIC = frozenset(
    n for n in jnwb.__all__
    if n not in OPTIONAL_SUBMODULES and callable(getattr(jnwb, n, None))
)

_ARROWS = ("-.->", "==>", "-->", "---", "--x", "--o")
_CLOSERS = {"[": "]", "(": ")", "{": "}"}
_SKIP = ("graph", "flowchart", "subgraph", "end", "%%", "classdef", "style", "click", "linkstyle")


# --------------------------------------------------------------------------- parsing


def _tokenize(line: str):
    """Tokenize one mermaid line into nodes and arrows, or return None if it will not parse.

    Label text is consumed whole, so an arrow drawn *inside* a label -- `addressing:
    Channel -> Area` on `docs/01` -- is never mistaken for an edge.
    """
    tokens: list = []
    i, n = 0, len(line)
    while i < n:
        if line[i].isspace():
            i += 1
            continue
        arrow = next((a for a in _ARROWS if line.startswith(a, i)), None)
        if arrow is not None:
            tokens.append(("arrow", arrow))
            i += len(arrow)
            continue
        if line[i] == "|":  # an edge label: |text|
            close = line.find("|", i + 1)
            if close < 0:
                return None
            i = close + 1
            continue
        match = IDENT.match(line, i)
        if match is None:
            return None
        node_id, i = match.group(0), match.end()
        label = None
        if i < n and line[i] in _CLOSERS:
            closer, depth, j = _CLOSERS[line[i]], 0, i
            while j < n:
                if line[j] in _CLOSERS and _CLOSERS[line[j]] == closer:
                    depth += 1
                elif line[j] == closer:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            else:
                return None
            label, i = line[i + 1 : j], j + 1
        tokens.append(("node", node_id, label))
    return tokens


def _fence_edges(body: str):
    """Return (edges, labels, unparsed) for one mermaid fence.

    `edges` is a list of (source_id, target_id); `labels` maps a node id to its declared
    label, which mermaid lets a later line omit.
    """
    lines, unparsed = [], []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.casefold().startswith(_SKIP):
            continue
        tokens = _tokenize(line)
        if tokens is None:
            unparsed.append(line)
            continue
        lines.append(tokens)

    labels: dict[str, str] = {}
    for tokens in lines:
        for token in tokens:
            if token[0] == "node" and token[2] is not None:
                labels.setdefault(token[1], token[2])

    edges = []
    for tokens in lines:
        for a, b, c in zip(tokens, tokens[1:], tokens[2:]):
            if a[0] == "node" and b[0] == "arrow" and c[0] == "node":
                edges.append((a[1], c[1]))
    return edges, labels, unparsed


def _head_symbols(label: str) -> list[str]:
    """Public operations named in a label's head.

    The page convention is `operation: description` or `operation / operation`. Resolving
    the whole label instead would promote prose to an API claim: `docs/03`'s label
    `jrsa function: Alignment, Reduction, Metric` names the phases of one call, and
    `Alignment` happens to be a public class.
    """
    return [t for t in IDENT.findall(label.split(":", 1)[0]) if t in PUBLIC]


def _diagram_edges(page: Path):
    """Yield (source_label, source_syms, target_label, target_syms) for one page."""
    text = page.read_text(encoding="utf-8")
    for body in MERMAID.findall(text):
        edges, labels, _ = _fence_edges(body)
        for source, target in edges:
            source_label = labels.get(source, source)
            target_label = labels.get(target, target)
            yield (
                source_label,
                _head_symbols(source_label),
                target_label,
                _head_symbols(target_label),
            )


# ----------------------------------------------------------------- annotation algebra


def _names_of(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id.casefold()}
    if isinstance(node, ast.Attribute):
        return {node.attr.casefold()}  # pd.DataFrame -> dataframe
    if isinstance(node, ast.Constant):
        return {str(node.value).casefold()}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _names_of(node.left) | _names_of(node.right)
    if isinstance(node, ast.Subscript):
        base = _names_of(node.value)
        if base & {"optional", "union"}:
            slice_ = node.slice
            parts = slice_.elts if isinstance(slice_, ast.Tuple) else [slice_]
            out: set[str] = set()
            for part in parts:
                out |= _names_of(part)
            if "optional" in base:
                out.add("none")
            return out
        # A `Dict[str, np.ndarray]` is a dict. Descending into the subscript would make
        # the decoder's metrics dict satisfy a parameter that wants one of its values.
        return base
    return {ast.unparse(node).casefold()}


def _annotation_names(annotation) -> frozenset[str]:
    """Base type names an annotation denotes; empty when it denotes nothing.

    Empty is the fail-closed answer for an unannotated parameter or return: it intersects
    nothing, so the edge fails rather than being waved through.
    """
    if annotation is inspect.Parameter.empty or annotation is inspect.Signature.empty:
        return frozenset()
    if annotation is None:
        return frozenset({"none"})
    if not isinstance(annotation, str):
        annotation = getattr(annotation, "__name__", None) or str(annotation)
    try:
        tree = ast.parse(annotation.strip(), mode="eval").body
    except SyntaxError:
        return frozenset({annotation.strip().casefold()})
    return frozenset(_names_of(tree))


def _returns(name: str) -> frozenset[str]:
    return _annotation_names(inspect.signature(getattr(jnwb, name)).return_annotation)


def _parameter_names(name: str) -> frozenset[str]:
    out: set[str] = set()
    for parameter in inspect.signature(getattr(jnwb, name)).parameters.values():
        out |= _annotation_names(parameter.annotation)
    return frozenset(out)


def _edge_verdict(producer: str, consumer: str) -> str | None:
    """None when the edge composes; otherwise the reason it cannot."""
    produced = _returns(producer)
    if not produced:
        return f"{producer} declares no return annotation, so the edge cannot be settled"
    if produced == frozenset({"none"}):
        # `None` normalises the same way whether it is a return of nothing or the null
        # half of an `Optional[...]` parameter, so without this a producer that returns
        # nothing would be accepted by every consumer with an optional argument.
        return f"{producer} returns None, so no edge can lead out of it"
    if consumer.casefold() in produced:
        return None  # a "returns" edge: the target node *is* the producer's output
    accepted = _parameter_names(consumer)
    if produced & accepted:
        return None
    return (
        f"{producer} returns {sorted(produced)}; "
        f"{consumer}{inspect.signature(getattr(jnwb, consumer))} accepts "
        f"{sorted(accepted)} -- no parameter can receive it"
    )


def _function_edges():
    """Every drawn edge whose two endpoints both name public operations."""
    for page in sorted(DOCS.rglob("*.md")):
        for source_label, sources, target_label, targets in _diagram_edges(page):
            if sources and targets:
                yield page, source_label, sources, target_label, targets


# ------------------------------------------------------------------------- the checks


def test_every_drawn_composition_is_accepted_by_the_live_signature():
    """An arrow between two operations asserts the consumer can take the producer's output."""
    broken = []
    for page, source_label, sources, target_label, targets in _function_edges():
        for producer in sources:
            for consumer in targets:
                reason = _edge_verdict(producer, consumer)
                if reason is not None:
                    broken.append(
                        f"{page.relative_to(REPO_ROOT).as_posix()}: "
                        f"[{source_label}] --> [{target_label}]: {reason}"
                    )
    assert not broken, "diagram edges the signatures refuse:\n  " + "\n  ".join(broken)


def test_the_diagram_survey_is_not_vacuous():
    """The check above is worthless over an empty survey, so the survey is measured."""
    pages = [p for p in sorted(DOCS.rglob("*.md")) if MERMAID.search(p.read_text(encoding="utf-8"))]
    assert len(pages) >= 4, f"only {len(pages)} documentation pages yielded a mermaid fence"

    edges = [e for page in pages for e in _diagram_edges(page)]
    assert len(edges) >= 25, f"only {len(edges)} edges parsed out of {len(pages)} pages"

    function_edges = list(_function_edges())
    assert len(function_edges) >= 2, (
        f"only {len(function_edges)} edges resolved to an operation at both ends; "
        "the composition check would be running over nothing"
    )
    on_decoding_page = [e for e in function_edges if e[0] == DECODING_PAGE]
    assert on_decoding_page, (
        "the decoding page contributed no function-to-function edge; the page this module "
        "was written for is no longer covered by it"
    )

    unparsed = []
    for page in pages:
        for body in MERMAID.findall(page.read_text(encoding="utf-8")):
            unparsed += _fence_edges(body)[2]
    assert not unparsed, f"mermaid lines the tokenizer could not read: {unparsed}"


def test_a_dict_return_does_not_satisfy_its_value_types():
    """A container is not its contents; descending into the subscript is the bypass."""
    produced = _annotation_names("Dict[str, Union[float, np.ndarray, dict, str]]")
    assert produced == frozenset({"dict"}), produced
    assert "ndarray" not in produced
    assert "float" not in produced
    # Union and Optional are alternatives, so those are descended.
    assert _annotation_names("Optional[np.ndarray]") == frozenset({"ndarray", "none"})
    assert _annotation_names("Union[Mapping[str, object], None]") == frozenset(
        {"mapping", "none"}
    )
    assert _annotation_names("pd.DataFrame") == frozenset({"dataframe"})


def test_an_unannotated_signature_fails_closed():
    """A missing annotation must not read as "accepts anything"."""
    assert _annotation_names(inspect.Parameter.empty) == frozenset()
    assert not (_annotation_names(inspect.Parameter.empty) & frozenset({"dataframe"}))


def test_a_producer_that_returns_nothing_cannot_feed_an_optional_parameter():
    """`None` means two things once normalised, and only one of them is a value.

    Measured on the shipped API: `Alignment` is annotated `-> None` and `JRSAResult`
    declares `Optional[np.ndarray]` parameters, so a naive set intersection matched them
    on `none` and accepted an edge between two operations that compose in no direction.
    """
    assert _returns("Alignment") == frozenset({"none"})
    assert "none" in _parameter_names("JRSAResult")
    assert _edge_verdict("Alignment", "JRSAResult") is not None


def test_node_labels_resolve_by_head_not_by_prose():
    """Both directions: an operation in the head resolves, one in a trailing clause does not."""
    assert "assign_outer_folds" in _head_symbols("assign_outer_folds: leave-one-group-out")
    assert _head_symbols("majority_baseline / fold_majority_baseline") == [
        "majority_baseline",
        "fold_majority_baseline",
    ]
    # `Alignment` is a real public class and a real English word; `docs/03` uses the word.
    assert "Alignment" in PUBLIC
    assert _head_symbols("jrsa function: Alignment, Reduction, Metric") == ["jrsa"]
    assert _head_symbols("Trial table: trial_id, session, analysis, slot_key, cycle") == []


def test_the_documented_partition_chain_executes():
    """Matching annotations do not prove the frames compose; the columns decide that."""
    trials = pd.DataFrame(
        {
            "trial_id": range(12),
            "session": ["s1"] * 12,
            "analysis": ["a"] * 12,
            "slot_key": ["k"] * 12,
            "cycle": [0, 1, 2] * 4,
        }
    )
    outer = jnwb.assign_outer_folds(trials, group_col="cycle")
    partitions = jnwb.build_inner_validation_partitions(outer)

    assert {"inner_role", "inner_fold", "outer_fold", "trial_id"} <= set(partitions.columns)
    assert {"inner_train", "inner_validation"} <= set(partitions["inner_role"].unique())

    # The declared dependency is real: the consumer needs a column only the producer adds.
    with pytest.raises(KeyError):
        jnwb.build_inner_validation_partitions(trials)


def _page_assignments(page: Path):
    """(name, operation) for every `name = jnwb.<operation>(...)` in the page's fences."""
    for body in PYTHON.findall(page.read_text(encoding="utf-8")):
        try:
            tree = ast.parse(body)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            func = node.value.func
            if not isinstance(func, ast.Attribute):
                continue
            root = func
            while isinstance(root, ast.Attribute):
                root = root.value
            if not (isinstance(root, ast.Name) and root.id == "jnwb"):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and func.attr in PUBLIC:
                    yield target.id, func.attr


def _page_loaded_names(page: Path) -> set[str]:
    loaded: set[str] = set()
    for body in PYTHON.findall(page.read_text(encoding="utf-8")):
        try:
            tree = ast.parse(body)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                loaded.add(node.id)
    return loaded


def test_a_value_the_diagram_routes_onward_is_used_by_the_page():
    """If the picture says the value flows on, the worked example has to show it flowing."""
    routed_onward = {
        symbol
        for _, sources, _, _ in (
            (a, b, c, d) for a, b, c, d in _diagram_edges(DECODING_PAGE)
        )
        for symbol in sources
    }
    assignments = list(_page_assignments(DECODING_PAGE))
    assert len(assignments) >= 5, (
        f"only {len(assignments)} jnwb assignments parsed out of the decoding page; "
        "this check would be running over nothing"
    )
    loaded = _page_loaded_names(DECODING_PAGE)

    dropped = [
        f"`{name} = jnwb.{operation}(...)` is never read, and the diagram draws an edge "
        f"out of {operation}"
        for name, operation in assignments
        if operation in routed_onward and name not in loaded
    ]
    assert not dropped, (
        "the page computes a value, says it flows onward, and drops it:\n  "
        + "\n  ".join(dropped)
    )
