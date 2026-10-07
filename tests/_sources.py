"""The jnwb source files a source scan must read, and a record of what each scan read.

A scan that lists its files itself (`jnwb/*.py`, one module's `inspect.getsource`) keeps passing
after a package split moves definitions out of what it reads, and passes on less. A scan reads
through `read_sources(label)`, which records a file when the scan takes its `.text`; the scan's
coverage test runs it and asserts `unread_by(label) == []`, comparing the record against
`public_definition_files`: every file that defines a function or class reachable as a public
name -- from the `__all__` of `jnwb` or of any public module, or as a public attribute of one.

A public module is one with no path component starting with a single underscore; `__init__`
and `__main__` count as their package's. A module whose optional dependency is missing is read
statically: its `__all__` literal, else its top-level public defs.

Limit: a scan that takes `.text` and then discards it on its content (`if "x" in text:
continue`) is recorded as having read the file. Only a filter applied before `.text` shows.
The axis-hop scan in `test_axis_convention_matches_the_specification.py` runs one parametrized
test per file, so it checks its declared file list only: a skip inside that test's body passes.
"""

from __future__ import annotations

import ast
import functools
import importlib
import inspect
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "jnwb"


def _path_of(within: str) -> Path:
    """The directory of dotted package `within`, or the file of dotted module `within`."""
    parts = within.split(".")
    if parts[0] != "jnwb":
        raise ValueError(f"{within!r} is not a jnwb module")
    base = PACKAGE.joinpath(*parts[1:])
    if base.is_dir():
        return base
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    raise ValueError(f"{within!r} names no module or package under {PACKAGE}")


def source_files(within: str = "jnwb") -> List[Path]:
    """Every `.py` file of the module or package `within`, recursively, sorted."""
    path = _path_of(within)
    return sorted(path.rglob("*.py")) if path.is_dir() else [path]


class Source:
    """One file a scan may read; taking `.text` records it as read under the scan's label."""

    def __init__(self, path: Path, label: str):
        self.path = path
        self._label = label

    @property
    def text(self) -> str:
        _RECORDED[_key(self._label)].add(self.path.resolve())
        return self.path.read_text(encoding="utf-8")


# Keyed by (label, the running test), so a coverage test sees only the scan it ran itself: a
# record left by another test with the same label cannot stand in for a scan that was dropped.
_RECORDED: Dict[tuple, Set[Path]] = {}


def _key(label: str) -> tuple:
    return label, os.environ.get("PYTEST_CURRENT_TEST", "").split(" ")[0]


def read_sources(label: str, within: str = "jnwb") -> Iterator[Source]:
    """The files of `within` for the scan named `label`; starts that scan's record afresh."""
    _RECORDED[_key(label)] = set()
    for path in source_files(within):
        yield Source(path, label)


def unread_by(label: str, within: str = "jnwb") -> List[str]:
    """The files `public_definition_files(within)` lists whose text scan `label` did not take
    in the running test."""
    if _key(label) not in _RECORDED:
        raise AssertionError(f"no scan named {label!r} has read through read_sources in this test")
    return unread(_RECORDED[_key(label)], within)


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(REPO_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_public(dotted: str) -> bool:
    return not any(part.startswith("_") and not part.startswith("__")
                   for part in dotted.split("."))


def _top_level_class_files(cls: type) -> List[Path]:
    """Files under the package of `cls.__module__` with a top-level `class` of that name.

    A class re-exported from a package `__init__` may keep the package path as `__module__`
    while its definition lives in a submodule, so the module's own file is not enough.
    """
    module = sys.modules.get(cls.__module__)
    module_file = Path(getattr(module, "__file__", "") or "")
    if not module_file.is_file():
        return []
    module_file = module_file.resolve()
    candidates = (sorted(module_file.parent.rglob("*.py")) if module_file.name == "__init__.py"
                  else [module_file])
    name = cls.__qualname__.split(".")[0]
    return [_in_checkout(path) for path in candidates
            if any(isinstance(node, ast.ClassDef) and node.name == name
                   for node in ast.parse(path.read_text(encoding="utf-8")).body)]


def _defining_file(obj: object) -> Optional[Path]:
    """The file under jnwb/ that defines `obj`, or None for an object jnwb did not define."""
    if inspect.isclass(obj):
        if not str(getattr(obj, "__module__", "")).startswith("jnwb"):
            return None
        found = _top_level_class_files(obj)
        if len(found) != 1:
            raise AssertionError(
                f"{obj.__module__}.{obj.__qualname__}: expected one defining file, found {found}")
        return found[0]
    function = inspect.unwrap(obj) if callable(obj) else obj
    code = getattr(function, "__code__", None)
    if code is None:
        return None
    path = Path(code.co_filename)
    if not path.is_file():
        return None
    path = _in_checkout(path.resolve())
    return path if path.is_relative_to(PACKAGE) else None


def _static_public_names(path: Path) -> Set[str]:
    """`__all__` as written in the file, else its top-level public defs."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)):
            return set(ast.literal_eval(node.value))
    return {node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and not node.name.startswith("_")}


@functools.lru_cache(maxsize=None)
def _imported_package() -> Path:
    """The directory of the imported jnwb: this checkout's, or an installed copy that
    `JNWB_EXPECTED_PACKAGE_ROOT` names, whose files map to the same paths here."""
    import jnwb

    imported_from = Path(jnwb.__file__).resolve().parent
    expected = os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT")
    if imported_from != PACKAGE and (expected is None
                                     or Path(expected).resolve() != imported_from.parent):
        raise AssertionError(f"jnwb was imported from {imported_from}, not {PACKAGE}")
    return imported_from


def _in_checkout(path: Path) -> Path:
    """`path` under the imported package, as the same path under this checkout's."""
    imported = _imported_package()
    if imported == PACKAGE or not path.is_relative_to(imported):
        return path
    mapped = PACKAGE / path.relative_to(imported)
    if not mapped.is_file():
        raise AssertionError(f"the installed {path} has no counterpart {mapped} in this checkout")
    return mapped


@functools.lru_cache(maxsize=None)
def _public_definitions() -> Dict[Path, frozenset]:
    _imported_package()
    reached: Dict[Path, Set[str]] = {}

    def add(label: str, obj: object) -> None:
        if not (inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj)
                or callable(getattr(obj, "__wrapped__", None))):
            return
        path = _defining_file(obj)
        if path is not None:
            reached.setdefault(path, set()).add(label)

    for path in source_files():
        dotted = _module_name(path)
        if not _is_public(dotted):
            continue
        try:
            module = importlib.import_module(dotted)
        except ImportError:
            # An optional dependency is missing; the file's own public defs stand for it.
            defined = {node.name for node in ast.parse(path.read_text(encoding="utf-8")).body
                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            names = _static_public_names(path) & defined
            if names:
                reached.setdefault(path.resolve(), set()).update(f"{dotted}.{n}" for n in names)
            continue
        names = set(getattr(module, "__all__", ())) | {n for n in vars(module)
                                                       if not n.startswith("_")}
        for name in names:
            if hasattr(module, name):
                add(f"{dotted}.{name}", getattr(module, name))
    return {path: frozenset(labels) for path, labels in reached.items()}


def public_definition_files(within: str = "jnwb") -> List[Path]:
    """Every file of `within` that defines a function or class reachable as a public name."""
    root = _path_of(within)
    return sorted(path for path in _public_definitions()
                  if path == root or (root.is_dir() and path.is_relative_to(root)))


def unread(scanned: Iterable[Path], within: str = "jnwb") -> List[str]:
    """The files `public_definition_files(within)` lists that `scanned` does not, repo-relative."""
    read = {Path(path).resolve() for path in scanned}
    return [path.relative_to(REPO_ROOT).as_posix()
            for path in public_definition_files(within) if path not in read]
