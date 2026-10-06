"""The jnwb source files a source scan must read.

A scan that lists its files itself (`jnwb/*.py`, one module's `inspect.getsource`) keeps passing
after a package split moves definitions out of what it reads, and passes on less. Scans list
their files with `source_files` and assert `unread(...) == []`, which compares what they read
against `public_definition_files`: every file that defines a function or class reachable as a
public name, from `jnwb.__all__` or as an attribute of a public module.
"""

from __future__ import annotations

import ast
import functools
import importlib
import inspect
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

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
    return [path for path in candidates
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
    path = path.resolve()
    return path if path.is_relative_to(PACKAGE) else None


@functools.lru_cache(maxsize=None)
def _public_definitions() -> Dict[Path, frozenset]:
    import jnwb
    from jnwb._api_surface import MODULE_DISPOSITION

    imported_from = Path(jnwb.__file__).resolve().parent
    if imported_from != PACKAGE:
        raise AssertionError(f"jnwb was imported from {imported_from}, not {PACKAGE}")
    reached: Dict[Path, Set[str]] = {}

    def add(label: str, obj: object) -> None:
        if not (inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj)
                or callable(getattr(obj, "__wrapped__", None))):
            return
        path = _defining_file(obj)
        if path is not None:
            reached.setdefault(path, set()).add(label)

    for name in jnwb.__all__:
        add(f"jnwb.{name}", getattr(jnwb, name))
    for dotted, disposition in sorted(MODULE_DISPOSITION.items()):
        if disposition != "public" or dotted == "__init__":
            continue
        module = importlib.import_module(f"jnwb.{dotted}")
        for name, obj in vars(module).items():
            if not name.startswith("_"):
                add(f"jnwb.{dotted}.{name}", obj)
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
