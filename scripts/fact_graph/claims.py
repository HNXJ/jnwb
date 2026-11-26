"""Claim-class scan (fact S8): figure labels and unit literals against the claim table."""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple
from scripts.fact_graph._base import _BACKTICKED
from scripts.fact_graph._sources import parse_source, read_source, walk_tree
from scripts.fact_graph.entities import _rel
from scripts.fact_graph.facts import _all_tables
from scripts.fact_graph.source_scans import JNWB_PACKAGE, _final

# ------------------------------------------------------------------------ claim classes (fact S8)

#: The claim table of ``docs/architecture.md``: its ``Magnitude`` and ``Direction`` rows name,
#: backticked in their third cell, the estimators a label or a returned unit may name without
#: leaving its claim class.
CLAIM_HEADER = ("Claim", "What it states", "What jnwb estimates it with",
                "What it does not license")
#: The claim-table rows whose estimators the S8 rule reads.
CLAIM_ESTIMAND_ROWS = ("Magnitude", "Direction")
#: Short names a figure label may use for an estimator, beside the estimator's own name with
#: ``_`` read as a space. A short name whose estimator is in neither estimand row is stale.
LABEL_NAMES: Dict[str, str] = {
    "psi": "phase_slope_index",
    "phase slope": "phase_slope_index",
    "granger": "granger",
    "transfer entropy": "transfer_entropy",
    "te": "transfer_entropy",
    "imaginary coherency": "imaginary_coherency",
    "icoh": "imaginary_coherency",
    "wpli": "wpli",
    "coherence": "cross_area_coherence",
}
#: The vocabulary of the two claim classes above magnitude and direction (fact S8). The delay
#: class names a time or velocity unit, or a delay word anywhere; the inference class names a
#: cause, a drive or a driver. The method name "Granger causality" (any case, also
#: "Granger-causal") is removed from the text before the inference words are matched, so the
#: direction estimator's own name does not read as a causal claim.
HIGHER_CLASS_TERMS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "delay": {"units": ("s", "ms", "sec", "seconds", "rad/Hz", "radians/Hz", "m/s", "mm/s",
                        "um/s"),
              "words": ("delay", "latency", "velocity")},
    "inference": {"words": ("cause", "causes", "caused", "causing", "causal", "causality",
                            "causation", "causally", "drive", "drives", "driven", "driving",
                            "driver", "drivers")},
}
#: The calls whose positional arguments, or whose ``label``/``title``/``xlabel``/``ylabel``
#: keyword, the label rule reads as a figure label; ``panel_title`` is the docs figures' title
#: wrapper (``scripts/figures/figure_style.py``) and ``set`` is ``Axes.set``.
LABEL_CALLEES = ("set_xlabel", "set_ylabel", "set_title", "xlabel", "ylabel", "title",
                 "panel_title", "set", "suptitle", "set_label", "text",
                 "annotate", "legend", "colorbar", "plot", "scatter", "bar", "errorbar",
                 "fill_between", "axhline", "axvline", "step", "hist")
#: The label keywords the rule reads, beside a call's first argument.
LABEL_KEYWORDS = ("label", "title", "xlabel", "ylabel")
#: The suffix that puts a call's ``unit=`` literal in the unit rule's domain.
RESULT_SUFFIX = "Result"
#: The tree the label rule leaves out: a test may name a higher class to assert a check fires.
TESTS_TREE = "tests/"
_PAREN_OR_BRACKET = re.compile(r"\(([^()]*)\)|\[([^\[\]]*)\]")
_GRANGER_METHOD = re.compile(r"granger[ -]causal(?:ity)?", re.IGNORECASE)


def read_claim_estimators(text: str) -> Dict[str, FrozenSet[str]]:
    """The estimators of the claim table's ``Magnitude`` and ``Direction`` rows: the backticked
    names of each row's third cell. Raises ValueError when the table or a row is missing, so a
    moved page can never read as an empty pass."""
    tables = [(header, rows) for _, header, rows in _all_tables(text)
              if tuple(header) == CLAIM_HEADER]
    if len(tables) != 1:
        raise ValueError(f"the page holds {len(tables)} claim tables, not exactly one")
    found: Dict[str, List[str]] = {}
    for row in tables[0][1]:
        if row and row[0] in CLAIM_ESTIMAND_ROWS:
            if len(row) < len(CLAIM_HEADER):
                raise ValueError(f"the claim table's {row[0]!r} row has {len(row)} cells, not "
                                 f"{len(CLAIM_HEADER)}: {row}")
            found[row[0]] = _BACKTICKED.findall(row[2])
    missing = [claim for claim in CLAIM_ESTIMAND_ROWS if claim not in found]
    if missing:
        raise ValueError(f"the claim table holds no {missing} row")
    return {claim: frozenset(names) for claim, names in found.items()}


def _phrase(pattern: str, ignorecase: bool = True) -> re.Pattern:
    """A whole-word pattern for a name or term; a space in it matches a run of whitespace or
    hyphens."""
    body = re.escape(pattern).replace("\\ ", r"[\s-]+").replace(" ", r"[\s-]+")
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE if ignorecase else 0)


def _higher_class_terms(text: str, units_anywhere: bool) -> List[str]:
    """The higher-class terms ``text`` holds, each spelled ``class: 'term'``. A delay unit
    counts anywhere in a unit literal; in a label, a compound unit (one with ``/``) counts
    anywhere and a plain one inside parentheses or brackets; a delay word counts anywhere; an
    inference word counts after the method name Granger causality is removed."""
    delay, inference = HIGHER_CLASS_TERMS["delay"], HIGHER_CLASS_TERMS["inference"]
    found: List[str] = []
    bracketed = " ".join(m.group(1) if m.group(1) is not None else m.group(2)
                         for m in _PAREN_OR_BRACKET.finditer(text))
    for unit in delay["units"]:
        scope = text if units_anywhere or "/" in unit else bracketed
        if _phrase(unit, ignorecase=False).search(scope):
            found.append(f"delay term {unit!r}")
    found += [f"delay term {word!r}" for word in delay["words"] if _phrase(word).search(text)]
    causal = _GRANGER_METHOD.sub(" ", text)
    found += [f"inference term {word!r}" for word in inference["words"]
              if _phrase(word).search(causal)]
    return found


def _estimator_patterns(estimators: FrozenSet[str]) -> Dict[str, List[re.Pattern]]:
    """Each estimator's whole-word patterns: its own name with ``_`` read as a space, plus the
    short names ``LABEL_NAMES`` gives it. A short name whose estimator is outside ``estimators``
    is reported as stale by ``claim_class_scan`` and matches nothing here."""
    patterns: Dict[str, List[re.Pattern]] = {}
    for estimator in sorted(estimators):
        pats = [_phrase(estimator.replace("_", " "))]
        pats += [_phrase(name) for name, target in LABEL_NAMES.items() if target == estimator]
        patterns[estimator] = pats
    return patterns


def _literal_text(node: ast.AST, names: Optional[Dict[str, str]] = None) -> Optional[str]:
    """The text of a string constant: a plain literal, the literal parts of an f-string, a sum
    of such parts, or a name ``names`` binds to one. Anything else, and an empty join, is no
    label text."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value for part in node.values
                       if isinstance(part, ast.Constant) and isinstance(part.value, str))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _literal_text(node.left, names), _literal_text(node.right, names)
        if left is not None or right is not None:
            return (left or "") + (right or "")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _literal_text(node.left, names)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "format"):
        return _literal_text(node.func.value, names)
    if isinstance(node, (ast.List, ast.Tuple, ast.IfExp)):
        elements = node.elts if not isinstance(node, ast.IfExp) else [node.body, node.orelse]
        parts = [_literal_text(element, names) for element in elements]
        if any(part is not None for part in parts):
            return " | ".join(part for part in parts if part is not None)
    if isinstance(node, ast.Name) and names:
        return names.get(node.id)
    return None


def _bound_names(tree: ast.AST) -> Dict[str, str]:
    """Each name an assignment anywhere in a module binds to string text, mapped to every such
    text joined, so a term in any binding is read wherever the name is used. A name bound to
    another name takes that name's text; chains resolve up to the module's assignment count."""
    assignments = []
    for node in walk_tree(tree):
        if isinstance(node, ast.Assign):
            assignments.append((node.targets, node.value))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
            assignments.append(([node.target], node.value))
    names: Dict[str, str] = {}
    for _ in range(len(assignments) + 1):
        bound: Dict[str, List[str]] = {}
        for targets, value in assignments:
            text = _literal_text(value, names)
            if text is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    bound.setdefault(target.id, []).append(text)
        resolved = {name: " | ".join(texts) for name, texts in bound.items()}
        if resolved == names:
            break
        names = resolved
    return names


def _label_sites(tree: ast.Module) -> List[Tuple[int, str]]:
    """Each label of one module as (line, text): string text passed as a positional argument or
    as a ``LABEL_KEYWORDS`` keyword to a call whose final name is in ``LABEL_CALLEES``. A name
    counts as every text an assignment in the module binds it to."""
    names = _bound_names(tree)
    sites = []
    for node in walk_tree(tree):
        if not (isinstance(node, ast.Call) and _final(node.func) in LABEL_CALLEES):
            continue
        for arg in list(node.args) + [kw.value for kw in node.keywords
                                      if kw.arg in LABEL_KEYWORDS]:
            text = _literal_text(arg, names)
            if text:
                sites.append((arg.lineno, text))
    return sites


def _unit_sites(tree: ast.AST) -> List[Tuple[int, str, str]]:
    """Each ``unit=`` string of one module as (line, callee name, text), for a call whose
    callee's name ends in ``RESULT_SUFFIX``; a name counts as every text the module binds it
    to."""
    names = _bound_names(tree)
    sites = []
    for node in walk_tree(tree):
        if not (isinstance(node, ast.Call) and _final(node.func).endswith(RESULT_SUFFIX)):
            continue
        for keyword in node.keywords:
            text = _literal_text(keyword.value, names) if keyword.arg == "unit" else None
            if text is not None:
                sites.append((keyword.value.lineno, _final(node.func), text))
    return sites


def _defining_modules(estimators: FrozenSet[str]) -> Dict[str, str]:
    """Each estimator and the dotted name of the module that defines it, resolved on the
    checkout's ``jnwb.<estimator>`` with ``inspect.getmodule``; an estimator the package does
    not export names no module here."""
    import jnwb  # the checkout, as every scan of the imported package reads

    modules: Dict[str, str] = {}
    for estimator in sorted(estimators):
        obj = getattr(jnwb, estimator, None)
        module = inspect.getmodule(obj) if obj is not None else None
        if module is not None and getattr(module, "__name__", ""):
            modules[estimator] = module.__name__
    return modules


def claim_class_scan(root: Path, python: Sequence[str]) -> Tuple[Dict[str, int],
                                                                 List[List[str]]]:
    """How many figure labels and ``unit=`` literals the S8 rule examined, by source, and each
    that names a magnitude or direction estimand while holding a term of a higher claim class,
    as sorted [file, reason] pairs.

    The estimators come from the claim table of ``docs/architecture.md`` under ``root``: the
    backticked names of its ``Magnitude`` and ``Direction`` rows. A missing table or row raises,
    never an empty pass. A label is a string constant passed as a call's first argument or as a
    ``LABEL_KEYWORDS`` keyword to a call whose attribute name is in ``LABEL_CALLEES``, in every
    tracked Python file outside ``tests/``; a unit literal is a ``unit=`` string of a call whose
    callee's name ends in ``Result``, in every tracked file under ``jnwb/``. A unit literal is a
    finding only in a module that defines an estimand's estimator: the module
    ``inspect.getmodule`` names for ``jnwb.<estimator>`` of the checkout, or one whose own
    top-level definitions name an estimator.
    """
    page = root / "docs" / "architecture.md"
    if not page.is_file():
        raise ValueError(f"{_rel(page, root)} is missing: no claim table to read")
    estimators = read_claim_estimators(page.read_text(encoding="utf-8"))
    licensed = estimators["Magnitude"] | estimators["Direction"]
    found = [["scripts/build_fact_graph.py",
              f"LABEL_NAMES names {name!r}, whose estimator {estimator!r} is in neither "
              "estimand row: stale"]
             for name, estimator in sorted(LABEL_NAMES.items()) if estimator not in licensed]
    patterns = _estimator_patterns(licensed)
    module_of = _defining_modules(licensed)
    examined = {"labels": 0, "units": 0}
    for rel in python:
        if rel.startswith(TESTS_TREE):
            continue
        tree = parse_source(read_source(root / rel))
        dotted = rel[:-len(".py")].replace("/", ".")
        tops = {node.name for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        owned = sorted(est for est in licensed
                       if module_of.get(est) == dotted or est in tops)
        for line, text in _label_sites(tree):
            examined["labels"] += 1
            named = sorted(name for name, pats in patterns.items()
                           if any(pattern.search(text) for pattern in pats))
            if not named:
                continue
            for term in _higher_class_terms(text, units_anywhere=False):
                found.append([rel, f"line {line}: {text!r} names {', '.join(named)} and holds "
                                   f"the {term}"])
        if not rel.startswith(JNWB_PACKAGE):
            continue
        for line, callee, unit in _unit_sites(tree):
            examined["units"] += 1
            if not owned:
                continue
            for term in _higher_class_terms(unit, units_anywhere=True):
                found.append([rel, f"line {line}: {callee} unit {unit!r} in the module of "
                                   f"{', '.join(owned)} holds the {term}"])
    return examined, sorted(found)
