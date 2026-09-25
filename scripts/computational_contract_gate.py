#!/usr/bin/env python3
"""Computational contract gate: execution switches select, precision requests are honoured,
and every export has a recorded order.

Three checks, each run against the live tree:

  1. Execution switch. Every public callable that takes ``device``, ``backend`` or
     ``n_jobs`` hands the argument to the mechanism that decides it, and the decision is
     used. ``device`` goes to ``jnwb._backend.resolve_device``, whose answer must reach a
     branch; the answer may be discarded only when the call declares ``supports=(CPU,)``,
     because then every accelerator request is announced and the CPU is the only outcome.
     ``n_jobs`` goes to ``jnwb._parallel.parallel_map`` or ``resolve_n_jobs``. ``backend``
     goes to ``resolve_device``, or to a guard that both refuses a value and announces one.
     A dataclass field of that name is a record of what ran and selects nothing, so it is
     listed rather than checked.
  2. Precision request. Every public callable with a precision parameter (a name containing
     ``dtype`` or ``precision``) is registered in ``jnwb._precision.PRECISION_POLICY`` under
     a policy that describes a request, and the code does what that policy says: under
     ``by_request`` the parameter reaches array construction as ``dtype=`` or ``.astype``;
     under ``double_only`` it reaches a guard that raises. A request that meets neither is
     silently ignored.
  3. Recorded order. Every name in ``jnwb.__all__`` falls in exactly one of the three
     categories ``artifacts/evidence/0.2.6/computational_order.md`` partitions the surface
     into (measured, section 3; excluded because cost does not grow, section 7; cost grows
     but not measurable here, section 8), and every name the record lists is still exported.
     That scope rule is the record's own (section 1): the categories are disjoint and their
     union is ``jnwb.__all__``.

Checks 1 and 2 read source through ``ast`` and follow an argument through local aliases and
into callees inside the package. What they establish and what they do not:

* They establish that the argument is read by the deciding mechanism and that its answer
  reaches a branch. They do not establish that each branch computes on the device it names,
  nor that every accepted value is delivered; ``tests/test_execution_switch.py`` and
  ``tests/test_precision_switch.py`` hold that behaviour live, export by export.
* Aliases are tracked flow-insensitively: an argument overwritten before it reaches the
  mechanism still counts as reaching it.
* A guard counts when the argument appears in an ``if`` test and a ``raise`` or
  ``warnings.warn`` appears anywhere under that ``if``.
* Under ``by_request`` one ``dtype=`` sink on one path passes; a second path that ignores
  the request is not seen.

Exit code 0 when every check passes, 1 otherwise. A check that raises is reported ERROR and
the others still run.
"""
from __future__ import annotations

import ast
import builtins
import dataclasses
import inspect
import re
import sys
import textwrap
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
ORDER_RECORD = REPO_ROOT / "artifacts" / "evidence" / "0.2.6" / "computational_order.md"

#: Execution parameters and the mechanism kind each must reach.
EXECUTION_PARAMETERS = ("device", "backend", "n_jobs")

#: A precision parameter is any parameter whose name carries one of these words.
PRECISION_PARAMETER = re.compile(r"(?:^|_)(?:dtype|precision)(?:$|_)")

#: Libraries whose ``dtype=`` keyword constructs or converts an array.
ARRAY_LIBRARIES = frozenset({"numpy", "cupy", "jax", "jaxlib", "torch", "scipy"})

_MISSING = object()


# ----------------------------------------------------------------------------- enumeration


def public_callables(package: Any) -> List[Tuple[str, Any]]:
    """Every callable export, and every public member a class export defines itself.

    The same surface ``tests/test_execution_switch.py`` enumerates: a static method reached
    through an exported class is public API even though its name is not in ``__all__``.

    Names the package declares as lazily imported submodules are skipped without being
    imported: a module is not callable, and importing ``vis`` costs its optional plotting
    stack.
    """
    submodules = set(getattr(package, "SUBMODULES", ()))
    found: List[Tuple[str, Any]] = []
    for name in package.__all__:
        if name in submodules:
            continue
        obj = getattr(package, name, None)
        if inspect.isclass(obj):
            found.append((name, obj))
            for member in vars(obj):
                if member.startswith("_"):
                    continue
                value = getattr(obj, member, None)
                if callable(value) and not inspect.isclass(value):
                    found.append((f"{name}.{member}", value))
        elif callable(obj) and not inspect.ismodule(obj):
            found.append((name, obj))
    return found


def _parameters(obj: Any) -> List[str]:
    try:
        return list(inspect.signature(obj).parameters)
    except (TypeError, ValueError):
        return []


def _dataclass_field(obj: Any, param: str) -> bool:
    return (
        inspect.isclass(obj)
        and dataclasses.is_dataclass(obj)
        and param in {f.name for f in dataclasses.fields(obj)}
    )


def _function_of(obj: Any) -> Optional[Callable]:
    """The Python function whose body receives ``obj``'s arguments."""
    target = obj.__init__ if inspect.isclass(obj) else obj
    target = getattr(target, "__func__", target)
    try:
        target = inspect.unwrap(target)
    except ValueError:
        return None
    return target if inspect.isfunction(target) else None


# ------------------------------------------------------------------------------ AST units


class _Unit:
    """One function body, with what is needed to resolve the names it calls."""

    def __init__(self, node: ast.AST, fn_globals: Dict[str, Any], owner: Any,
                 local_imports: Dict[str, str]):
        self.node = node
        self.globals = fn_globals
        self.owner = owner
        self.local_imports = dict(local_imports)
        self.parents: Dict[ast.AST, ast.AST] = {}
        self.nested: Dict[str, ast.AST] = {}
        for parent in ast.walk(node):
            for child in ast.iter_child_nodes(parent):
                self.parents[child] = parent
        for sub in ast.walk(node):
            if sub is node:
                continue
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.nested.setdefault(sub.name, sub)
            elif isinstance(sub, ast.Import):
                for alias in sub.names:
                    local = alias.asname or alias.name.split(".")[0]
                    self.local_imports[local] = alias.name if alias.asname else local
            elif isinstance(sub, ast.ImportFrom) and sub.module and not sub.level:
                for alias in sub.names:
                    self.local_imports[alias.asname or alias.name] = f"{sub.module}.{alias.name}"
        self.calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]

    @property
    def key(self) -> int:
        return id(self.node)

    def params(self) -> List[str]:
        args = self.node.args
        return [a.arg for a in (*args.posonlyargs, *args.args)]

    def keyword_params(self) -> Set[str]:
        args = self.node.args
        return {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}


_UNIT_CACHE: Dict[Any, Optional[_Unit]] = {}


def _owner_of(fn: Callable) -> Any:
    module = sys.modules.get(fn.__module__)
    parts = fn.__qualname__.split(".")[:-1]
    if not parts or "<locals>" in parts or module is None:
        return None
    obj: Any = module
    for part in parts:
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj if inspect.isclass(obj) else None


def _unit_of(fn: Callable) -> Optional[_Unit]:
    if fn in _UNIT_CACHE:
        return _UNIT_CACHE[fn]
    unit = None
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except (OSError, TypeError, SyntaxError):
        tree = None
    if tree is not None:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                unit = _Unit(node, fn.__globals__, _owner_of(fn), {})
                break
    _UNIT_CACHE[fn] = unit
    return unit


def _names(expr: Optional[ast.AST]) -> Set[str]:
    if expr is None:
        return set()
    return {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)}


def _contains(expr: Optional[ast.AST], aliases: Set[str]) -> bool:
    return bool(_names(expr) & aliases)


_CONTAINER_DISPLAYS = (ast.Dict, ast.List, ast.Tuple, ast.Set, ast.DictComp, ast.ListComp,
                       ast.SetComp, ast.GeneratorExp)
_CONTAINER_BUILTINS = (dict, list, tuple, set, frozenset)


def _resolve(unit: _Unit, expr: ast.AST) -> Optional[Tuple[str, Any]]:
    """What a callee expression names: ``("obj", x)``, ``("ast", node)`` or ``("mod", str)``."""
    if isinstance(expr, ast.Name):
        if expr.id in unit.nested:
            return ("ast", unit.nested[expr.id])
        if expr.id in unit.local_imports:
            return ("mod", unit.local_imports[expr.id])
        if expr.id in ("self", "cls") and unit.owner is not None:
            return ("obj", unit.owner)
        value = unit.globals.get(expr.id, _MISSING)
        if value is _MISSING:
            value = getattr(builtins, expr.id, _MISSING)
        return None if value is _MISSING else ("obj", value)
    if isinstance(expr, ast.Attribute):
        base = _resolve(unit, expr.value)
        if base is None:
            return None
        kind, value = base
        if kind == "mod":
            return ("mod", f"{value}.{expr.attr}")
        if kind == "obj":
            try:
                return ("obj", getattr(value, expr.attr))
            except Exception:
                return None
    return None


def _library_root(resolved: Optional[Tuple[str, Any]]) -> str:
    if resolved is None:
        return ""
    kind, value = resolved
    if kind == "mod":
        return str(value).split(".")[0]
    if kind == "obj":
        module = value.__name__ if inspect.ismodule(value) else getattr(value, "__module__", "")
        return str(module or "").split(".")[0]
    return ""


class _Analysis:
    """Follows one argument from a public signature into the package's own callees."""

    def __init__(self, scope: Sequence[str]):
        self.scope = tuple(scope)
        from jnwb import _backend, _parallel

        self.resolve_device = _backend.resolve_device
        self.parallel_map = _parallel.parallel_map
        self.resolve_n_jobs = _parallel.resolve_n_jobs
        self.cpu = _backend.CPU
        self._memo: Dict[Tuple[int, str, str], bool] = {}

    # -- aliases -------------------------------------------------------------------------

    def _reads(self, unit: _Unit, expr: ast.AST, aliases: Set[str]) -> bool:
        """Whether ``expr``'s value is the argument itself or a conversion of it.

        A container holding the argument is a record of it, and the result of a function
        in scope is a new value that function decided; neither carries the argument on, so
        the walk does not descend into them. Without this, a guard on an unrelated record
        (a parameter dict, a backend context) counted as a guard on the argument.
        """
        if isinstance(expr, ast.Name):
            return expr.id in aliases
        if isinstance(expr, _CONTAINER_DISPLAYS):
            return False
        if isinstance(expr, ast.Call):
            resolved = _resolve(unit, expr.func)
            if resolved is not None and resolved[0] == "obj":
                value = resolved[1]
                if any(value is c for c in _CONTAINER_BUILTINS):
                    return False
                if (inspect.isfunction(value) or inspect.isclass(value)
                        or inspect.ismethod(value)) and self._in_scope(value):
                    return False
            if resolved is not None and resolved[0] == "ast":
                return False
        return any(self._reads(unit, child, aliases) for child in ast.iter_child_nodes(expr))

    def _aliases(self, unit: _Unit, start: Iterable[str]) -> Set[str]:
        """Names bound, anywhere in the body, to the argument or a conversion of it."""
        found = set(start)
        changed = True
        while changed:
            changed = False
            for node in ast.walk(unit.node):
                if isinstance(node, ast.Assign):
                    targets, value = node.targets, node.value
                elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                    targets, value = [node.target], node.value
                elif isinstance(node, ast.NamedExpr):
                    targets, value = [node.target], node.value
                else:
                    continue
                if value is None or not self._reads(unit, value, found):
                    continue
                for target in targets:
                    for name in _names(target):
                        if name not in found:
                            found.add(name)
                            changed = True
        return found

    # -- callees -------------------------------------------------------------------------

    def _in_scope(self, fn: Any) -> bool:
        module = getattr(fn, "__module__", "") or ""
        return any(module == s or module.startswith(s + ".") for s in self.scope)

    def _callee(self, unit: _Unit, call: ast.Call) -> Optional[Tuple[_Unit, int]]:
        """The package-internal body a call enters, and the positional offset of its args."""
        resolved = _resolve(unit, call.func)
        if resolved is None:
            return None
        kind, value = resolved
        if kind == "ast":
            return _Unit(value, unit.globals, unit.owner, unit.local_imports), 0
        if kind != "obj":
            return None
        offset = 0
        if inspect.ismethod(value):
            value, offset = value.__func__, 1
        elif (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
              and call.func.value.id == "self" and unit.owner is not None):
            static = inspect.getattr_static(unit.owner, call.func.attr, None)
            offset = 0 if isinstance(static, staticmethod) else 1
        if inspect.isclass(value):
            if not self._in_scope(value):
                return None
            value, offset = value.__init__, 1
        fn = _function_of(value)
        if fn is None or not self._in_scope(fn):
            return None
        callee = _unit_of(fn)
        return (callee, offset) if callee is not None else None

    def _mapped(self, unit: _Unit, aliases: Set[str]) -> Iterable[Tuple[_Unit, str]]:
        """Every (callee, parameter) pair that receives one of ``aliases``."""
        for call in unit.calls:
            entered = self._callee(unit, call)
            if entered is None:
                continue
            callee, offset = entered
            positional = callee.params()
            for i, arg in enumerate(call.args):
                if isinstance(arg, ast.Starred):
                    break
                if _contains(arg, aliases) and i + offset < len(positional):
                    yield callee, positional[i + offset]
            accepted = callee.keyword_params()
            for kw in call.keywords:
                if kw.arg is not None and kw.arg in accepted and _contains(kw.value, aliases):
                    yield callee, kw.arg

    # -- guards --------------------------------------------------------------------------

    def _guarded(self, unit: _Unit, aliases: Set[str], what: str) -> bool:
        for node in ast.walk(unit.node):
            if not isinstance(node, ast.If) or not _contains(node.test, aliases):
                continue
            for inner in ast.walk(node):
                if what == "raise" and isinstance(inner, ast.Raise):
                    return True
                if what == "warn" and isinstance(inner, ast.Call):
                    resolved = _resolve(unit, inner.func)
                    if resolved == ("obj", warnings.warn) or resolved == ("mod", "warnings.warn"):
                        return True
        return False

    # -- execution -----------------------------------------------------------------------

    def _slot(self, call: ast.Call, fn: Callable, name: str) -> Optional[ast.AST]:
        position = list(inspect.signature(fn).parameters).index(name)
        if position < len(call.args) and not any(
                isinstance(a, ast.Starred) for a in call.args[:position + 1]):
            return call.args[position]
        for kw in call.keywords:
            if kw.arg == name:
                return kw.value
        return None

    def _cpu_only(self, unit: _Unit, call: ast.Call) -> bool:
        for kw in call.keywords:
            if kw.arg != "supports" or not isinstance(kw.value, (ast.Tuple, ast.List)):
                continue
            values = []
            for element in kw.value.elts:
                if isinstance(element, ast.Constant):
                    values.append(element.value)
                else:
                    resolved = _resolve(unit, element)
                    values.append(resolved[1] if resolved and resolved[0] == "obj" else None)
            return bool(values) and all(v == self.cpu for v in values)
        return False

    def _answer_decides(self, unit: _Unit, call: ast.Call) -> bool:
        """Whether the value a mechanism returns reaches a branch."""
        node: ast.AST = call
        while True:
            parent = unit.parents.get(node)
            if parent is None or isinstance(parent, ast.stmt) and not isinstance(
                    parent, (ast.If, ast.While, ast.Assert, ast.Assign, ast.AnnAssign)):
                break
            if isinstance(parent, (ast.Compare, ast.BoolOp, ast.UnaryOp)):
                return True
            if isinstance(parent, (ast.If, ast.While, ast.IfExp, ast.Assert)) and parent.test is node:
                return True
            if isinstance(parent, (ast.Assign, ast.AnnAssign)):
                targets = parent.targets if isinstance(parent, ast.Assign) else [parent.target]
                bound: Set[str] = set()
                for target in targets:
                    bound |= _names(target)
                return self._decides(unit, self._aliases(unit, bound))
            node = parent
        return False

    def _decides(self, unit: _Unit, aliases: Set[str]) -> bool:
        """Whether a resolved value is branched on here or in a callee that receives it."""
        if not aliases:
            return False
        for node in ast.walk(unit.node):
            if isinstance(node, ast.Compare) and _contains(node, aliases):
                return True
            if isinstance(node, (ast.If, ast.While, ast.IfExp, ast.Assert)) and _contains(
                    node.test, aliases):
                return True
            if isinstance(node, ast.Subscript) and _contains(node.slice, aliases):
                return True
        for callee, param in self._mapped(unit, aliases):
            key = (callee.key, param, "decides")
            if key in self._memo:
                if self._memo[key]:
                    return True
                continue
            self._memo[key] = False
            result = self._decides(callee, self._aliases(callee, {param})) or self.routes(
                callee, param, "device")
            self._memo[key] = result
            if result:
                return True
        return False

    def routes(self, unit: _Unit, param: str, kind: str) -> bool:
        """Whether ``param`` reaches the mechanism ``kind`` requires, with its answer used."""
        key = (unit.key, param, kind)
        if key in self._memo:
            return self._memo[key]
        self._memo[key] = False
        aliases = self._aliases(unit, {param})
        result = False
        for call in unit.calls:
            resolved = _resolve(unit, call.func)
            target = resolved[1] if resolved and resolved[0] == "obj" else None
            if kind in ("device", "backend") and target is self.resolve_device:
                if _contains(self._slot(call, target, "device"), aliases) and (
                        self._answer_decides(unit, call)
                        or (isinstance(unit.parents.get(call), ast.Expr)
                            and self._cpu_only(unit, call))):
                    result = True
            elif kind == "n_jobs" and target is self.parallel_map:
                if _contains(self._slot(call, target, "n_jobs"), aliases):
                    result = True
            elif kind == "n_jobs" and target is self.resolve_n_jobs:
                if _contains(self._slot(call, target, "n_jobs"), aliases) and \
                        self._answer_decides(unit, call):
                    result = True
            if result:
                break
        if not result:
            result = any(self.routes(callee, p, kind) for callee, p in self._mapped(unit, aliases))
        if not result and kind == "backend":
            result = self._guarded(unit, aliases, "raise") and self._guarded(unit, aliases, "warn")
        self._memo[key] = result
        return result

    # -- precision -----------------------------------------------------------------------

    def refuses(self, unit: _Unit, param: str) -> bool:
        """Whether a precision request reaches a guard that raises, here or in a callee."""
        key = (unit.key, param, "refuses")
        if key in self._memo:
            return self._memo[key]
        self._memo[key] = False
        aliases = self._aliases(unit, {param})
        result = self._guarded(unit, aliases, "raise") or any(
            self.refuses(callee, p) for callee, p in self._mapped(unit, aliases))
        self._memo[key] = result
        return result

    def honours(self, unit: _Unit, param: str) -> bool:
        """Whether a precision request reaches array construction as ``dtype=`` or ``.astype``."""
        key = (unit.key, param, "honours")
        if key in self._memo:
            return self._memo[key]
        self._memo[key] = False
        aliases = self._aliases(unit, {param})
        result = False
        for call in unit.calls:
            func = call.func
            if isinstance(func, ast.Attribute) and func.attr == "astype":
                if any(_contains(a, aliases) for a in call.args) or any(
                        kw.arg == "dtype" and _contains(kw.value, aliases) for kw in call.keywords):
                    result = True
                    break
            if any(kw.arg == "dtype" and _contains(kw.value, aliases) for kw in call.keywords):
                if _library_root(_resolve(unit, func)) in ARRAY_LIBRARIES:
                    result = True
                    break
        if not result:
            result = any(self.honours(callee, p) for callee, p in self._mapped(unit, aliases))
        self._memo[key] = result
        return result


# ---------------------------------------------------------------------------------- checks


#: Modules whose functions an argument is followed into.
DEFAULT_SCOPE = ("jnwb",)


def check_execution_switch(callables: Sequence[Tuple[str, Any]],
                           scope: Sequence[str] = DEFAULT_SCOPE) -> Tuple[List[str], List[str]]:
    """Check 1. Returns (violations, records)."""
    analysis = _Analysis(scope)
    violations: List[str] = []
    records: List[str] = []
    for name, obj in callables:
        for param in _parameters(obj):
            if param not in EXECUTION_PARAMETERS:
                continue
            if _dataclass_field(obj, param):
                records.append(f"{name}.{param}")
                continue
            fn = _function_of(obj)
            unit = _unit_of(fn) if fn is not None else None
            if unit is None:
                violations.append(f"{name}: `{param}` is taken but its source cannot be read, "
                                  "so what it selects is unknown")
                continue
            if not analysis.routes(unit, param, param):
                mechanism = {
                    "device": "resolve_device with its answer branched on (or supports=(CPU,))",
                    "backend": "resolve_device, or a guard that refuses and announces",
                    "n_jobs": "parallel_map or resolve_n_jobs",
                }[param]
                violations.append(f"{name}: `{param}` is accepted and selects nothing; it never "
                                  f"reaches {mechanism}")
    return violations, records


def check_precision_request(callables: Sequence[Tuple[str, Any]],
                            policy: Optional[Dict[str, str]] = None,
                            scope: Sequence[str] = DEFAULT_SCOPE) -> Tuple[List[str], List[str]]:
    """Check 2. Returns (violations, the precision parameters found)."""
    from jnwb import _precision

    registry = _precision.PRECISION_POLICY if policy is None else policy
    requestable = {_precision.BY_REQUEST, _precision.DOUBLE_ONLY}
    analysis = _Analysis(scope)
    violations: List[str] = []
    found: List[str] = []
    for name, obj in callables:
        for param in _parameters(obj):
            if not PRECISION_PARAMETER.search(param):
                continue
            found.append(f"{name}.{param}")
            dotted = f"{getattr(obj, '__module__', '')}.{getattr(obj, '__qualname__', name)}"
            stated = registry.get(dotted)
            if stated is None:
                violations.append(f"{name}: takes `{param}` and states no precision policy "
                                  f"({dotted} is not in PRECISION_POLICY)")
                continue
            if stated not in requestable:
                violations.append(f"{name}: takes `{param}` but its stated policy is {stated!r}, "
                                  "which ignores a request; expected 'by_request' or 'double_only'")
                continue
            fn = _function_of(obj)
            unit = _unit_of(fn) if fn is not None else None
            if stated == _precision.BY_REQUEST and (unit is None or not analysis.honours(unit, param)):
                violations.append(f"{name}: stated 'by_request', but `{param}` never reaches array "
                                  "construction as dtype= or .astype")
            if stated == _precision.DOUBLE_ONLY and (unit is None or not analysis.refuses(unit, param)):
                violations.append(f"{name}: stated 'double_only', but `{param}` never reaches a "
                                  "guard that raises")
    return violations, found


def _sections(text: str) -> Dict[str, str]:
    """Top-level sections by number, each with its heading line first."""
    found: Dict[str, str] = {}
    matches = list(re.finditer(r"^## (\d+)\. .*$", text, flags=re.M))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        found[match.group(1)] = text[match.start():end]
    return found


def _first_cells(section: str) -> List[str]:
    """The backticked first cell of every table row in a section, without a ``[...]`` suffix."""
    names = []
    for line in section.splitlines():
        match = re.match(r"^\|\s*`([^`]+)`\s*\|", line)
        if match:
            names.append(match.group(1).split("[")[0].strip())
    return names


#: The record's categories: section number, the start of its heading, and a short name.
ORDER_CATEGORIES = (
    ("3", "Measured order", "measured"),
    ("7", "Exports excluded", "excluded"),
    ("8", "Exports whose cost grows", "unmeasurable"),
)


def check_recorded_order(exports: Sequence[str], record_text: str) -> Tuple[List[str], Dict[str, int]]:
    """Check 3. Returns (violations, per-category counts of exports)."""
    violations: List[str] = []
    sections = _sections(record_text)
    members: Dict[str, Set[str]] = {}
    for number, heading, label in ORDER_CATEGORIES:
        section = sections.get(number)
        if section is None or not section.startswith(f"## {number}. {heading}"):
            violations.append(f"the order record has no section '## {number}. {heading}'; its "
                              "partition cannot be read, so no export is known to be covered")
            continue
        members[label] = set(_first_cells(section))
        if not members[label]:
            violations.append(f"section {number} of the order record lists no export")
    if violations:
        return violations, {}
    live = set(exports)
    for name in sorted(live):
        homes = [label for label, names in members.items() if name in names]
        if not homes:
            violations.append(f"{name}: exported with no recorded order (in none of "
                              f"{', '.join(label for _, _, label in ORDER_CATEGORIES)})")
        elif len(homes) > 1:
            violations.append(f"{name}: recorded in more than one category ({', '.join(homes)})")
    for label, names in members.items():
        for name in sorted(names - live):
            violations.append(f"{name}: the order record lists it as {label}, but it is not in "
                              "jnwb.__all__")
    counts = {label: len(names & live) for label, names in members.items()}
    return violations, counts


# ---------------------------------------------------------------------------------- runner


def _checkout_jnwb():
    """This tree's jnwb, for the command line. A copy in site-packages would be measured
    silently, so the checkout goes first and the import is verified to have used it."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import jnwb

    root = REPO_ROOT.resolve()
    location = Path(jnwb.__file__).resolve()
    if root not in location.parents:
        raise RuntimeError(f"imported jnwb from {location}, not from this tree ({root})")
    return jnwb


def run_checks(package: Any) -> List[Tuple[str, List[str], str]]:
    """Every check on ``package``, as (name, violations, pass line). A raise is caught.

    The caller chooses the package: the command line passes this checkout's, and the suite
    passes whichever installation it was pointed at.
    """
    results: List[Tuple[str, List[str], str]] = []

    def execution():
        violations, records = check_execution_switch(public_callables(package))
        return violations, (
            "PASS: every device, backend and n_jobs argument reaches the mechanism that decides "
            f"it (records, which select nothing: {', '.join(sorted(records)) or 'none'}).")

    def precision():
        violations, found = check_precision_request(public_callables(package))
        return violations, (
            "PASS: every precision parameter is registered under a request policy and the code "
            f"does what the policy says ({', '.join(sorted(found)) or 'none found'}).")

    def order():
        violations, counts = check_recorded_order(
            list(package.__all__), ORDER_RECORD.read_text(encoding="utf-8"))
        summary = ", ".join(f"{label} {n}" for label, n in counts.items())
        return violations, (
            f"PASS: all {len(package.__all__)} exports of jnwb.__all__ have a recorded order "
            f"category ({summary}).")

    for name, check in (("execution switch", execution), ("precision request", precision),
                        ("recorded order", order)):
        try:
            violations, pass_line = check()
            results.append((name, violations, pass_line))
        except Exception as exc:  # one broken check must not hide the others
            results.append((name, [f"ERROR: {type(exc).__name__}: {exc}"], "ERROR"))
    return results


def main() -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")
    print("=== Computational contract ===")
    failed = []
    for name, violations, pass_line in run_checks(_checkout_jnwb()):
        if not violations:
            print(pass_line)
            continue
        failed.append(name)
        errored = violations and violations[0].startswith("ERROR:")
        print(f"{'ERROR' if errored else 'FAIL'}: {name}:")
        for violation in violations:
            print(f"  - {violation}")
    if failed:
        print(f"OVERALL: FAIL. failed: {', '.join(failed)}.")
        return 1
    print("ALL COMPUTATIONAL CONTRACT CHECKS PASSED. 3 of 3 checks executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
