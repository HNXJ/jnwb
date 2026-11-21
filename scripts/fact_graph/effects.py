"""Effect scans: delegation (D1), side effects (D2, D3), reserved refusals, documented guesses and cache decisions."""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
# The declared signal types of fact I1, read by the signature-types scan.
from jnwb import _declarations
from scripts.fact_graph.scheme_rng import _public_callables
from scripts.fact_graph.signatures import _own_root, _own_tree, _private_helper, _public_target
from scripts.fact_graph.source_scans import JNWB_PACKAGE, _dotted, _final, _own_calls

# ------------------------------------------------------------------------ delegation (fact D1)


def _own_returns(fn: ast.AST):
    """The ``return`` values of a function's own statements, not of the functions and
    lambdas it defines."""
    pending = list(fn.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, ast.Return) and node.value is not None:
            yield node.value
        pending.extend(ast.iter_child_nodes(node))


def delegation_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the delegation rule examined, and each that tail-calls
    (``return f(...)``) two or more distinct public callables, as sorted [module.name,
    reason] pairs. One tail-call target is a delegation; two is a sequenced choice the
    signature does not name. A callable whose source cannot be read is a finding, never
    a pass."""
    callables = _public_callables(package)
    index = {id(fn): (qualname, owner) for qualname, fn, owner in callables}
    examined, found = 0, []
    for qualname, fn, owner in callables:
        examined += 1
        try:
            tree, _ = _own_tree(fn)
        except (OSError, TypeError, SyntaxError, ValueError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        targets = set()
        for value in _own_returns(_own_root(tree)):
            if not isinstance(value, ast.Call):
                continue
            target = _public_target(fn, _dotted(value.func), owner, index)
            if target is not None and target is not fn:
                gqualname, _ = index[id(target)]
                targets.add(f"{target.__module__}.{gqualname}")
        if len(targets) > 1:
            found.append([f"{fn.__module__}.{qualname}",
                          f"tail-calls {len(targets)} public callables: {sorted(targets)}"])
    return examined, sorted(found)


# ------------------------------------------------------------------------ side-effect categories (facts D2, D3)

#: The public operations with NWB side effects: the file the caller built is written,
#: copied with declared changes, or repaired once its intended form is identified.
NWB_SINKS: Tuple[str, ...] = (
    "jnwb.nwb_write.write_nwb",
    "jnwb.nwb_write.transform_nwb",
    "jnwb.nwb_write.repair_nwb",
    "jnwb.nwb_integrity.repair_ragged_index",
)

#: The public operation with caching side effects: one entry persisted under its key.
CACHE_SINKS: Tuple[str, ...] = (
    "jnwb.execution.cache_store",
)


def _reaches_sink(fn: Any, owner: Any, index: Dict[int, Any], sink_ids: set) -> Optional[bool]:
    """Whether ``fn`` is a sink or transitively calls one, through public callables and
    the private helpers of its package. None when a body in the walk cannot be read."""
    if id(fn) in sink_ids:
        return True
    queue, seen = [(fn, owner)], {id(fn)}
    while queue:
        body, body_owner = queue.pop()
        try:
            tree, _ = _own_tree(body)
        except (OSError, TypeError, SyntaxError, ValueError):
            return None
        for call in _own_calls(_own_root(tree)):
            dotted = _dotted(call.func)
            target = _public_target(body, dotted, body_owner, index)
            if target is not None:
                if id(target) in sink_ids:
                    return True
                if id(target) not in seen:
                    seen.add(id(target))
                    _, target_owner = index[id(target)]
                    queue.append((target, target_owner))
                continue
            helper = _private_helper(body, dotted, body_owner, index)
            if helper is not None and id(helper) not in seen:
                seen.add(id(helper))
                queue.append((helper, None))
    return False


def _side_effect_scan(package: Any, sinks: Sequence[str], categories: Sequence[str],
                      kind: str) -> Tuple[int, List[List[str]]]:
    """How many public callables the side-effect rule examined, and each failure, as
    sorted [module.name, reason] pairs. The domain is every public callable reaching a
    sink of ``kind``, sinks included; each carries exactly one category of the fact
    stack constant in its declaration. A categorized declaration whose key reaches no
    sink is stale. A callable or sink whose source cannot be read is a finding, never
    a pass."""
    declarations = _declarations.DECLARATIONS
    callables = _public_callables(package)
    index = {id(fn): (qualname, owner) for qualname, fn, owner in callables}
    sink_ids = set()
    examined, found = 0, []
    for key in sinks:
        module_name, _, qualname = key.rpartition(".")
        try:
            sink_ids.add(id(getattr(importlib.import_module(module_name), qualname)))
        except (ImportError, AttributeError):
            found.append([key, f"{kind} sink not readable: not checked"])
    reached = set()
    for qualname, fn, owner in callables:
        examined += 1
        key = f"{fn.__module__}.{qualname}"
        hit = _reaches_sink(fn, owner, index, sink_ids)
        if hit is None:
            found.append([key, "source unreadable: not checked"])
            continue
        if not hit:
            continue
        reached.add(key)
        declared = declarations.get(key)
        category = declared.category if declared is not None else ""
        if category not in categories:
            found.append([key, f"reaches a {kind} sink but carries no single "
                              f"{kind} category in jnwb/_declarations.py"])
    for key in sorted(declarations):
        category = declarations[key].category
        if category and category in categories and key not in reached:
            found.append([key, f"carries {kind} category {category!r} but reaches no "
                              f"{kind} sink: stale"])
    return examined, sorted(found)


def nwb_side_effects_scan(package: Any, categories: Sequence[str]) -> Tuple[int, List[List[str]]]:
    """How many public callables the NWB side-effect rule examined, and each failure."""
    return _side_effect_scan(package, NWB_SINKS, categories, "mutation")


def cache_side_effects_scan(package: Any,
                            categories: Sequence[str]) -> Tuple[int, List[List[str]]]:
    """How many public callables the cache side-effect rule examined, and each failure."""
    return _side_effect_scan(package, CACHE_SINKS, categories, "cache")


# ------------------------------------------------------------------------ reserved refusals (facts D5, D7, D9)

#: The refusal errors held back for mutation operations that cannot yet name their
#: mapping or unit: defined, exported and documented reserved, never raised.
RESERVED_ERRORS: Tuple[str, ...] = (
    "AmbiguousMappingError",
    "UndeclaredUnitError",
)


def reserved_errors_scan(package: Any, root: Path) -> Tuple[int, List[List[str]]]:
    """The two reserved refusal errors, and each missing hold, as sorted [name, reason]
    pairs. Each is defined in ``jnwb.nwb_write`` subclassing the base mutation error,
    exported in ``jnwb.__all__``, and named beside ``reserv`` in ``docs/errors.md``."""
    try:
        module = importlib.import_module("jnwb.nwb_write")
    except ImportError as exc:
        return len(RESERVED_ERRORS), [[name, f"jnwb.nwb_write not readable: {exc}"]
                                      for name in sorted(RESERVED_ERRORS)]
    base = getattr(module, "NWBMutationError", None)
    try:
        page = (root / "docs" / "errors.md").read_text(encoding="utf-8")
    except OSError:
        page = ""
    found = []
    for name in sorted(RESERVED_ERRORS):
        obj = getattr(module, name, None)
        if not inspect.isclass(obj) or base is None or not issubclass(obj, base):
            found.append([name, "not defined in jnwb.nwb_write as a mutation error"])
        if name not in getattr(package, "__all__", ()):
            found.append([name, "not exported in jnwb.__all__"])
        if name not in page or "reserv" not in page.lower():
            found.append([name, "not documented reserved in docs/errors.md"])
    return len(RESERVED_ERRORS), sorted(found)


# ------------------------------------------------------------------------ documented guesses (facts D6, D8)

#: The parameter names whose string default is a reading the tree takes for granted.
GUESS_PARAMETERS: Tuple[str, ...] = ("table", "code_column")


def _default_guess_sites(root: Path, python: Sequence[str]) -> List[Tuple[str, str, str]]:
    """Each string default of a ``table`` or ``code_column`` parameter in ``jnwb/`` as
    (parameter, default, module.qualname) triples."""
    sites = []
    for rel in python:
        if not rel.startswith(JNWB_PACKAGE):
            continue
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        module = rel[:-len(".py")].replace("/", ".")
        stack: List[str] = []

        def visit(node: ast.AST) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    stack.append(child.name)
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        slots = list(zip(child.args.args, child.args.defaults)) + list(
                            zip(child.args.kwonlyargs, child.args.kw_defaults))
                        for arg, default in slots:
                            if (arg.arg in GUESS_PARAMETERS and isinstance(default, ast.Constant)
                                    and isinstance(default.value, str)):
                                sites.append((arg.arg, default.value,
                                              f"{module}." + ".".join(stack)))
                    visit(child)
                    stack.pop()
                else:
                    visit(child)

        visit(tree)
    return sites


def _interval_preference(root: Path) -> List[str]:
    """The missing holds of the preferred-table rule: ``_resolve_interval_table`` names
    ``trials`` by membership and returns it, and no other interval name is returned as
    a literal. The ``trials``/``epochs``/``invalid_times`` census of the file inventory
    is prose about what a file holds, not a preference, and lives elsewhere."""
    try:
        tree = ast.parse((root / "jnwb" / "nwb_events.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return [["trials preferred over epochs", "jnwb/nwb_events.py not readable"]]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_resolve_interval_table":
            preferred = any(
                isinstance(sub, ast.If) and isinstance(sub.test, ast.Compare)
                and any(isinstance(op, ast.In) for op in sub.test.ops)
                and any(isinstance(part, ast.Constant) and part.value == "trials"
                        for part in ast.walk(sub.test))
                and any(isinstance(ret, ast.Return) and isinstance(ret.value, ast.Constant)
                        and ret.value.value == "trials" for ret in ast.walk(sub))
                for sub in ast.walk(node))
            literals = {ret.value.value for ret in ast.walk(node)
                        if isinstance(ret, ast.Return) and isinstance(ret.value, ast.Constant)
                        and isinstance(ret.value.value, str)}
            found = []
            if not preferred:
                found.append(["trials preferred over epochs",
                              "_resolve_interval_table names no trials preference"])
            for extra in sorted(literals - {"trials"}):
                found.append(["trials preferred over epochs",
                              f"_resolve_interval_table also returns {extra!r}"])
            return found
    return [["trials preferred over epochs", "_resolve_interval_table not found"]]


def _layout_bases(root: Path) -> List[str]:
    """The missing holds of the layout rule: ``_resolve_layout`` answers from the
    electrode count or from the shape guess, with the schema time-first rule for types
    without an electrode region, and from nothing else."""
    try:
        tree = ast.parse((root / "jnwb" / "nwb_inspect.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return [["layout from electrode count, shape guess otherwise",
                 "jnwb/nwb_inspect.py not readable"]]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_resolve_layout":
            bases = {part.value for ret in ast.walk(node)
                     if isinstance(ret, ast.Return)
                     for part in ast.walk(ret.value)
                     if isinstance(part, ast.Constant) and isinstance(part.value, str)}
            if bases != {"electrode_count", "shape", "schema"}:
                return [["layout from electrode count, shape guess otherwise",
                         f"_resolve_layout answers from {sorted(bases)}"]]
            return []
    return [["layout from electrode count, shape guess otherwise",
             "_resolve_layout not found"]]


def documented_guesses_scan(root: Path, python: Sequence[str],
                            guesses: Sequence[str]) -> Tuple[int, List[List[str]]]:
    """The guess sites the ``documented guesses`` constant covers, and each failure, as
    sorted [site, reason] pairs. A string default of a ``table`` or ``code_column``
    parameter matches a ``<parameter> default <default>: <module.qualname>`` row; the
    preferred-table and layout-basis rows are checked against the functions that read
    them. A site outside the constant is a new guess; a row no longer in the tree is
    stale."""
    rows = {guess: False for guess in guesses}
    found = []
    for parameter, default, qualname in _default_guess_sites(root, python):
        row = f"{parameter} default {default}: {qualname}"
        if row in rows:
            rows[row] = True
        else:
            found.append([row, "a defaulted name outside the documented guesses"])
    for row, holds in [("trials preferred over epochs", _interval_preference(root)),
                       ("layout from electrode count, shape guess otherwise",
                        _layout_bases(root))]:
        if row in rows:
            rows[row] = True
            found.extend(holds)
        else:
            found.append([row, "a documented guess the constant does not name"])
    for row, seen in sorted(rows.items()):
        if not seen:
            found.append([row, "a documented guess no longer in the tree: stale"])
    return len(rows), sorted(found)


# ------------------------------------------------------------------------ cache decisions (fact D10)

#: The functions through which the core would decide what to cache.
CACHE_CALLS: Tuple[str, ...] = ("cache_store", "cache_key")


def cache_decisions_scan(root: Path, python: Sequence[str]) -> Tuple[int, List[List[str]]]:
    """The ``jnwb/`` files the cache-decision rule read, and each call to the
    cache-write or cache-key function in them, as sorted [file, reason] pairs. An
    assigned name that is never called is no site."""
    examined, found = 0, []
    for rel in python:
        if not rel.startswith(JNWB_PACKAGE):
            continue
        examined += 1
        tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _final(node.func) in CACHE_CALLS:
                found.append([rel, f"line {node.lineno}: calls {_final(node.func)}"])
    return examined, sorted(found)
