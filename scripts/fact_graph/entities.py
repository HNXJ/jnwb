"""Graph entities: exports, pages, routes, tests and documents of the tree."""

from __future__ import annotations

import ast
import inspect
import re
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from scripts.computational_contract_gate import _dataclass_field
from scripts.fact_graph._base import _ADDRESS, _BACKTICKED, _HEADING_LINE, _IDENTIFIER, _JNWB_NAME, _LINE_SPAN, _PARENTHESISED, _ROUTING_LINE, _ROW_HEAD_END
from scripts.fact_graph.facts import _all_tables

# ------------------------------------------------------------------------ generated graph


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _kind(obj: Any) -> str:
    if isinstance(obj, types.ModuleType):
        return "module"
    if inspect.isclass(obj):
        return "class"
    if callable(obj):
        return "function"
    return "constant"


def _signature(obj: Any) -> Optional[str]:
    if not callable(obj) or isinstance(obj, types.ModuleType):
        return None
    try:
        return _ADDRESS.sub("", str(inspect.signature(obj)))
    except (TypeError, ValueError):
        return None


def _package_rel(path: Path, package: Any) -> str:
    """``path`` relative to the directory holding the package, so ``jnwb/<module>.py`` whether
    the package is the source tree or an installed copy in site-packages."""
    return path.resolve().relative_to(Path(package.__file__).resolve().parent.parent).as_posix()


def _module_file(obj: Any, package: Any, root: Path) -> str:
    """The source file that defines ``obj``; the package's own ``__init__`` when unknown."""
    target = obj if isinstance(obj, types.ModuleType) else sys.modules.get(
        getattr(obj, "__module__", "") or "")
    location = getattr(target, "__file__", None) or package.__file__
    try:
        return _package_rel(Path(location), package)
    except ValueError:
        return _package_rel(Path(package.__file__), package)


def _exports(package: Any, root: Path, switches: Sequence[str]):
    exports: Dict[str, Dict[str, Any]] = {}
    implements: List[List[str]] = []
    for name in sorted(package.__all__):
        try:
            obj = getattr(package, name)
        except ImportError:
            # A subpackage behind an optional extra: recorded from its source, so the graph is
            # the same whichever extras the building interpreter has.
            source = Path(package.__file__).parent / name / "__init__.py"
            if not source.is_file():
                raise
            exports[name] = {"kind": "module", "signature": None, "switches": []}
            implements.append([_package_rel(source, package), name])
            continue
        signature = _signature(obj)
        params: List[str] = []
        if signature is not None:
            try:
                params = list(inspect.signature(obj).parameters)
            except (TypeError, ValueError):
                params = []
        exports[name] = {
            "kind": _kind(obj),
            "signature": signature,
            # A dataclass field of a switch's name records what ran and selects nothing; the
            # computational contract gate draws the same line.
            "switches": [p for p in switches if p in params and not _dataclass_field(obj, p)],
        }
        implements.append([_module_file(obj, package, root), name])
    return exports, implements


def _pages(root: Path) -> List[Path]:
    from scripts.harness_gate import GENERATED_REFERENCE

    return [p for p in sorted((root / "docs").rglob("*.md")) if p.name != GENERATED_REFERENCE]


def _documents(pages: Sequence[Path], names: Sequence[str], root: Path) -> List[List[str]]:
    """Each page and each export it names in a heading or a code span on one line. Prose alone
    documents nothing: a name that only the running text mentions is not a documented export.
    Spans are paired within a line, so one fenced block cannot shift the pairs after it."""
    edges = []
    for page in pages:
        marked: List[str] = []
        for line in page.read_text(encoding="utf-8").splitlines():
            if _HEADING_LINE.match(line):
                marked.append(line)
            marked.extend(_LINE_SPAN.findall(line))
        words = set(re.findall(r"\b\w+\b", "\n".join(marked)))
        edges.extend([_rel(page, root), n] for n in names if n in words)
    return edges


def routing_targets(text: str) -> List[str]:
    """Every name ``text`` routes, without the ``jnwb.`` prefix, in the two forms read."""
    targets = []
    for line in text.splitlines():
        if not _ROUTING_LINE.match(line):
            continue
        end = _ROW_HEAD_END.search(line)
        head = line[: end.start() + 1] if end else line
        for span in _BACKTICKED.findall(head):
            match = _JNWB_NAME.match(span)
            if match:
                targets.append(match.group(1).rstrip("."))
    for _, header, rows in _all_tables(text):
        for column, cell in enumerate(header):
            prefix = next((m.group(1) for m in map(_JNWB_NAME.match, _BACKTICKED.findall(cell))
                           if m), None)
            if prefix is None:
                continue
            for row in rows:
                if column >= len(row):
                    continue
                for span in _BACKTICKED.findall(_PARENTHESISED.sub("", row[column])):
                    if _IDENTIFIER.match(span):
                        targets.append(f"{prefix}.{span}")
    return targets


def _routes(root: Path) -> Tuple[List[str], List[List[str]]]:
    skills, edges = [], []
    for path in sorted((root / "skills").glob("*/SKILL.md")):
        skill = path.parent.name
        skills.append(skill)
        parts = [path.read_text(encoding="utf-8")]
        refdir = path.parent / "references"
        if refdir.is_dir():
            parts += [p.read_text(encoding="utf-8") for p in sorted(refdir.glob("*.md"))]
        edges.extend([skill, target]
                     for target in sorted(set(routing_targets("\n".join(parts)))))
    return skills, edges


def resolves_in_source(package_dir: Path, target: str) -> bool:
    """Whether ``target`` names a module under ``package_dir``, or a top-level name one defines.

    Used when importing the target fails because an optional extra is not installed: the
    module then exists on disk but cannot be imported, and the graph must not depend on which
    extras the building interpreter has.
    """
    parts = target.split(".")
    base = package_dir
    for index, part in enumerate(parts):
        if (base / part).is_dir() and (base / part / "__init__.py").is_file():
            base = base / part
            continue
        if (base / f"{part}.py").is_file():
            rest = parts[index + 1:]
            return not rest or (len(rest) == 1 and rest[0] in _top_level_names(base / f"{part}.py"))
        return index > 0 and index == len(parts) - 1 and part in _top_level_names(base / "__init__.py")
    return True


def _top_level_names(path: Path) -> set:
    names = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                names.update(n.id for n in ast.walk(t) if isinstance(n, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


def _route_targets(package: Any, exports: Dict[str, Any], routes: Sequence[Sequence[str]]):
    targets = {}
    for target in sorted({t for _, t in routes}):
        head = target.split(".")[0]
        obj: Any = package
        try:
            for part in target.split("."):
                obj = getattr(obj, part)
            resolves = True
        except AttributeError:
            resolves = False
        except ImportError:
            resolves = resolves_in_source(Path(package.__file__).parent, target)
        targets[target] = {"export": head if head in exports else None, "resolves": resolves}
    return targets


def _is_jnwb(module: Optional[str]) -> bool:
    return bool(module) and (module == "jnwb" or module.startswith("jnwb."))


def references(source: str, names: Sequence[str]) -> List[str]:
    """The names of ``names`` a test module reaches through an import of ``jnwb``.

    Reached: a name imported from ``jnwb`` or a submodule, or read as an attribute anywhere in
    a chain rooted at an imported ``jnwb`` module (``jnwb.NAME``, ``jnwb.sub.NAME``, ``O.NAME``
    after ``import jnwb.sub as O`` or ``from jnwb import sub as O``).
    """
    wanted = set(names)
    nodes = list(ast.walk(ast.parse(source)))  # walked once, read twice
    aliases = set()
    found = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_jnwb(alias.name):
                    aliases.add(alias.asname or "jnwb")
        elif isinstance(node, ast.ImportFrom) and _is_jnwb(node.module):
            for alias in node.names:
                if alias.name in wanted:
                    found.add(alias.name)
                else:  # a submodule, or a private helper; its attributes may be exports
                    aliases.add(alias.asname or alias.name)
    for node in nodes:
        if not isinstance(node, ast.Attribute):
            continue
        chain = []
        value: ast.AST = node
        while isinstance(value, ast.Attribute):
            chain.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name) and value.id in aliases:
            found.update(attr for attr in chain if attr in wanted)
    return sorted(found)


def test_functions(source: str) -> List[str]:
    """Each test function of a module, qualified by its class when it has one."""
    found = []
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test"):
            found.append(node.name)
        elif isinstance(node, ast.ClassDef):
            found.extend(f"{node.name}::{item.name}" for item in node.body
                         if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and item.name.startswith("test"))
    return found


def _tests(root: Path, names: Sequence[str]):
    tests: Dict[str, List[str]] = {}
    verifies: List[List[str]] = []
    for path in sorted((root / "tests").glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        rel = _rel(path, root)
        tests[rel] = sorted(test_functions(source))
        verifies.extend([rel, n] for n in references(source, names))
    return tests, verifies
