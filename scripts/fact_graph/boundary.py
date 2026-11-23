"""Boundary-unit scan (fact I3): units, bases, rates and frames across call edges."""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple
from scripts.fact_graph._sources import parse_source, read_source, walk_tree
from scripts.fact_graph.scheme_rng import UNIT_SUFFIXES
from scripts.fact_graph.source_scans import JNWB_PACKAGE, _final

# ------------------------------------------------------------------------ named units (fact I3)

#: The base suffixes the boundary rule reads beside the unit suffixes: index provenance,
#: 0- or 1-based.
BASE_SUFFIXES = ("_idx", "_index", "_0based", "_1based")
#: The suffixes a boundary edge compares: a unit suffix or a base suffix.
BOUNDARY_SUFFIXES = UNIT_SUFFIXES + BASE_SUFFIXES
#: Suffixes that spell the same unit or base, mapped to the one an edge compares.
SUFFIX_ALIASES = {"_sec": "_s", "_index": "_idx"}
#: The comment that states an intentional break at its change site, excusing the edges on its
#: line or in the statement it stands above.
BREAK_MARK = "INTENTIONAL BREAK"
#: The sample-rate parameters the boundary rule reads: names that carry a rate but no unit
#: suffix. The rate a value carries is the numeric default its own parameter declares; a
#: value reaching a parameter declaring another rate changes rate with no conversion.
RATE_PARAMETERS = ("fs", "sampling_rate", "sample_rate")
#: The frame parameters the boundary rule reads: the frame a value carries is the string
#: default its own parameter declares.
FRAME_PARAMETERS = ("coordinate_frame",)
#: The base parameters the boundary rule reads: the base a value carries is the numeric
#: default its own parameter declares (0-based or 1-based).
BASE_PARAMETERS = ("index_base",)
#: The time suffixes among ``UNIT_SUFFIXES``, read against the count words below: a value
#: in samples or rows reaching a parameter in seconds, or the reverse, changes quantity
#: with no conversion on the way.
TIME_SUFFIXES = ("_ms", "_s", "_sec", "_us")
#: The words a sample count travels under; ``ROW_WORDS`` is the other base.
SAMPLE_WORDS = ("_sample", "_samples")
#: The words a row count travels under.
ROW_WORDS = ("_row", "_rows")


def _boundary_suffix(name: str) -> Optional[str]:
    """The longest suffix of ``BOUNDARY_SUFFIXES`` a name ends with, compared
    case-insensitively and read through ``SUFFIX_ALIASES``; None when it carries none."""
    lowered = name.lower()
    for suffix in sorted(BOUNDARY_SUFFIXES, key=len, reverse=True):
        if lowered.endswith(suffix):
            return SUFFIX_ALIASES.get(suffix, suffix)
    return None


def _implicit_domain(name: str) -> Optional[str]:
    """The unsuffixed domain ``name`` spells -- ``rate``, ``frame`` or ``base`` -- or None.
    A name outside the three tables spells nothing and is not guessed."""
    if name in RATE_PARAMETERS:
        return "rate"
    if name in FRAME_PARAMETERS:
        return "frame"
    if name in BASE_PARAMETERS:
        return "base"
    return None


def _quantity_kind(name: str) -> Optional[str]:
    """The quantity ``name`` carries -- ``time``, ``samples`` or ``rows`` -- or None. A
    suffix the rule reads decides time; the count words decide the other two."""
    lowered = name.lower()
    if lowered.endswith(SAMPLE_WORDS):
        return "samples"
    if lowered.endswith(ROW_WORDS):
        return "rows"
    if lowered.endswith(TIME_SUFFIXES):
        return "time"
    return None


def _literal_defaults(fn: ast.AST) -> Dict[str, Tuple[str, Any]]:
    """Each parameter of ``fn`` with a numeric or string literal default, as
    ``name -> (kind, value)``. ``None``, booleans and any other default spell nothing
    and are not read."""
    args = fn.args
    positional = list(args.posonlyargs) + list(args.args)
    entries: Dict[str, Tuple[str, Any]] = {}
    aligned = positional[len(positional) - len(args.defaults):] if args.defaults else []
    for param, default in list(zip(aligned, args.defaults)) + list(
            zip(args.kwonlyargs, args.kw_defaults)):
        if (isinstance(default, ast.Constant)
                and isinstance(default.value, (int, float, str))
                and not isinstance(default.value, bool)):
            kind = "number" if isinstance(default.value, (int, float)) else "string"
            entries[param.arg] = (kind, default.value)
    return entries


def _boundary_default_lists(tree: ast.AST) -> Dict[str, List[Dict[str, Tuple[str, Any]]]]:
    """Each function or method name defined in one module, mapped to one literal-default
    map per definition (``_literal_defaults``), in definition order."""
    found: Dict[str, List[Dict[str, Tuple[str, Any]]]] = {}
    for node in walk_tree(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.setdefault(node.name, []).append(_literal_defaults(node))
    return found


def _enclosing_defaults(tree: ast.AST) -> Dict[int, Dict[str, Tuple[str, Any]]]:
    """Each call of one module, by ``id``, mapped to the literal defaults of the
    innermost function definition holding it, or to no map outside any definition."""
    found: Dict[int, Dict[str, Tuple[str, Any]]] = {}
    pending: List[Tuple[ast.AST, Dict[str, Tuple[str, Any]]]] = [(tree, {})]
    while pending:
        node, current = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            current = _literal_defaults(node)
        if isinstance(node, ast.Call):
            found[id(node)] = current
        pending.extend((child, current) for child in ast.iter_child_nodes(node))
    return found


#: The literal kind the default rule requires of each unsuffixed domain: a rate and a
#: base are numbers, a frame is a string.
_DOMAIN_KIND = {"rate": "number", "frame": "string", "base": "number"}


def _implicit_edge(callee: str, param: str, value: ast.Name, site: str, line: int,
                   caller: Dict[str, Tuple[str, Any]],
                   callee_maps: List[Dict[str, Tuple[str, Any]]],
                   excused: Callable[[int], bool], examined: Dict[str, int],
                   found: List[List[str]]) -> None:
    """One argument of a boundary call under the unsuffixed rule: a value whose name
    carries a quantity kind (``TIME_SUFFIXES``, ``SAMPLE_WORDS``, ``ROW_WORDS``) reaching
    a parameter carrying another is a finding; else, when both names spell the same rate,
    frame or base domain and both declare a literal default of its kind, differing
    defaults are a finding. An expression is the conversion, not examined; a missing or
    non-literal default spells nothing and is not guessed. ``examined`` counts a quantity
    edge only on a mismatch, and a default edge on every comparison."""
    vkind, pkind = _quantity_kind(value.id), _quantity_kind(param)
    if vkind is not None and pkind is not None and vkind != pkind:
        examined["edges"] += 1
        if excused(line):
            examined["excused"] += 1
        else:
            found.append([site, f"{value.id} ({vkind}) reaches {callee}({param}) ({pkind})"])
        return
    domain = _implicit_domain(param)
    if domain is None or _implicit_domain(value.id) != domain:
        return
    want = _DOMAIN_KIND[domain]
    carried = caller.get(value.id)
    if carried is None or carried[0] != want:
        return
    declared = [mapping.get(param) for mapping in callee_maps]
    if any(item is None or item[0] != want for item in declared):
        return
    if len({item[1] for item in declared}) != 1:
        return  # ambiguous: the edge may reach either spelling
    examined["edges"] += 1
    if carried[1] == declared[0][1]:
        return
    if excused(line):
        examined["excused"] += 1
    else:
        found.append([site, f"{value.id} ({domain} {carried[1]!r}) reaches "
                            f"{callee}({param}) ({domain} {declared[0][1]!r})"])


def _boundary_definitions(tree: ast.AST) -> Dict[str, List[Tuple[Tuple[str, ...],
                                                                 FrozenSet[str]]]]:
    """Each function or method name defined in one module, mapped to its distinct parameter
    lists: the ordered positional parameters, without the receiver of a method that is not a
    ``staticmethod`` whatever its name, and every parameter's name. A name defined twice with
    the same lists appears once."""
    receivers = set()
    for node in walk_tree(tree):
        if isinstance(node, ast.ClassDef):
            for method in node.body:
                if (isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and "staticmethod" not in {_final(d) for d in method.decorator_list}):
                    receivers.add(method)
    definitions: Dict[str, List[Tuple[Tuple[str, ...], FrozenSet[str]]]] = {}
    for node in walk_tree(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        positional = [a.arg for a in list(args.posonlyargs) + list(args.args)]
        skip = 1 if node in receivers and positional else 0
        names = positional[skip:] + [a.arg for a in args.kwonlyargs]
        entry = (tuple(positional[skip:]), frozenset(names))
        lists = definitions.setdefault(node.name, [])
        if entry not in lists:
            lists.append(entry)
    return definitions


def _break_regions(source: str, tree: ast.AST) -> List[Tuple[int, int]]:
    """The line spans an ``INTENTIONAL BREAK`` comment excuses: its own line when it trails
    code, and the next statement when it stands alone -- only the header of a compound
    statement, so a comment above a ``def`` or a block never excuses the body."""
    lines = source.splitlines()
    regions: List[Tuple[int, int]] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (SyntaxError, tokenize.TokenError):
        return regions
    spans: Dict[int, int] = {}
    for node in walk_tree(tree):
        if isinstance(node, ast.stmt):
            body = getattr(node, "body", None)
            end = body[0].lineno - 1 if isinstance(body, list) and body else node.end_lineno
            spans[node.lineno] = max(spans.get(node.lineno, node.lineno), end)
    for token in tokens:
        if not (token.type == tokenize.COMMENT and BREAK_MARK in token.string):
            continue
        line = token.start[0]
        if lines[line - 1][:token.start[1]].strip():
            regions.append((line, line))
            continue
        following = [start for start in spans if start > line]
        if following:
            start = min(following)
            regions.append((start, spans[start]))
    return regions


def boundary_unit_scan(root: Path, python: Sequence[str]) -> Tuple[Dict[str, int],
                                                                   List[List[str]]]:
    """How many boundary edges the I3 rule examined, and each call in ``jnwb/`` that passes a
    bare name whose suffix differs from the callee parameter's suffix, as sorted
    [path:line, reason] pairs.

    A definition is every function or method defined in a tracked ``.py`` file under
    ``jnwb/``, by name, with its parameter names in order (``_boundary_definitions``). A call
    whose callee -- a bare name or an attribute's own name, ``g`` in ``C().g`` -- names a
    definition is read by
    its arguments: an argument whose value is a bare ``Name`` whose suffix
    (``BOUNDARY_SUFFIXES``, longest match) differs from the parameter's suffix at the same
    keyword or position is a finding. A name defined more than once with different parameter
    lists is skipped for positional arguments only; an argument that is an expression is the
    conversion, not examined. Past the suffixes, one argument whose quantity kinds
    (``TIME_SUFFIXES``, ``SAMPLE_WORDS``, ``ROW_WORDS``) differ, or whose rate, frame or
    base defaults (``RATE_PARAMETERS``, ``FRAME_PARAMETERS``, ``BASE_PARAMETERS``) differ
    across the edge, is a finding too (``_implicit_edge``). A call on a line an
    ``INTENTIONAL BREAK`` comment holds, or in
    the statement such a comment stands above (``_break_regions``), is excused and counted
    apart.
    """
    files = [rel for rel in python if rel.startswith(JNWB_PACKAGE)]
    definitions: Dict[str, List[Tuple[Tuple[str, ...], FrozenSet[str]]]] = {}
    callee_maps: Dict[str, List[Dict[str, Tuple[str, Any]]]] = {}
    trees: Dict[str, ast.AST] = {}
    for rel in files:
        trees[rel] = parse_source(read_source(root / rel))
        for name, lists in _boundary_definitions(trees[rel]).items():
            definitions.setdefault(name, []).extend(lists)
        for name, maps in _boundary_default_lists(trees[rel]).items():
            callee_maps.setdefault(name, []).extend(maps)
    examined: Dict[str, int] = {"edges": 0, "excused": 0}
    found: List[List[str]] = []
    for rel in files:
        regions = _break_regions(read_source(root / rel), trees[rel])
        excused = lambda line: any(start <= line <= end for start, end in regions)  # noqa: E731
        callers = _enclosing_defaults(trees[rel])
        for node in walk_tree(trees[rel]):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            callee = func.attr if isinstance(func, ast.Attribute) else _final(func)
            lists = definitions.get(callee)
            if lists is None:
                continue
            caller = callers.get(id(node), {})
            maps = callee_maps.get(callee, [])
            for keyword in node.keywords:
                param, value = keyword.arg, keyword.value
                if param is None or not isinstance(value, ast.Name):
                    continue
                if not any(param in names for _, names in lists):
                    continue
                psuffix, vsuffix = _boundary_suffix(param), _boundary_suffix(value.id)
                if psuffix is None or vsuffix is None:
                    _implicit_edge(callee, param, value, f"{rel}:{value.lineno}",
                                   value.lineno, caller, maps, excused, examined, found)
                    continue
                examined["edges"] += 1
                if psuffix == vsuffix or excused(value.lineno):
                    if psuffix != vsuffix:
                        examined["excused"] += 1
                    continue
                found.append([f"{rel}:{value.lineno}",
                              f"{value.id} ({vsuffix}) reaches {callee}({param}) ({psuffix})"])
            if len(lists) != 1:
                continue  # ambiguous: positional arguments are skipped
            positional = lists[0][0]
            for index, arg in enumerate(node.args):
                if index >= len(positional) or not isinstance(arg, ast.Name):
                    continue
                psuffix, vsuffix = _boundary_suffix(positional[index]), _boundary_suffix(arg.id)
                if psuffix is None or vsuffix is None:
                    _implicit_edge(callee, positional[index], arg, f"{rel}:{arg.lineno}",
                                   arg.lineno, caller, maps, excused, examined, found)
                    continue
                examined["edges"] += 1
                if psuffix == vsuffix or excused(arg.lineno):
                    if psuffix != vsuffix:
                        examined["excused"] += 1
                    continue
                found.append([f"{rel}:{arg.lineno}",
                              f"{arg.id} ({vsuffix}) reaches "
                              f"{callee}({positional[index]}) ({psuffix})"])
    return examined, sorted(found)
