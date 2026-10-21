"""Gate 19 (frozen functions): verified bodies still hash to their values."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]


#: Functions whose body was independently verified and had a mutant killed; see CONTRIBUTING.md.
FROZEN_REGISTER = "artifacts/process/frozen_validated.json"


def _canonical_ast(node: Any) -> Any:
    """A nested tuple of `node` that is the same on every supported interpreter.

    `ast.dump` is not: 3.13 stopped printing fields that are None or empty, so a hash of its
    output would differ between CI legs for an unchanged body. Those fields are dropped here on
    every version, and positions are never read.
    """
    if isinstance(node, ast.AST):
        return (type(node).__name__,) + tuple(
            (name, _canonical_ast(value))
            for name, value in ast.iter_fields(node)
            if value is not None and value != []
        )
    if isinstance(node, list):
        return tuple(_canonical_ast(item) for item in node)
    return repr(node)


def _strip_docstrings(node: ast.AST) -> None:
    for sub in ast.walk(node):
        body = getattr(sub, "body", None)
        if (isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            sub.body = body[1:] or [ast.Pass()]


def frozen_body_hash(source: str, qualname: str) -> Optional[str]:
    """SHA-256 of the body of `qualname` in `source`, docstrings and comments excluded.

    Returns None when no function of that dotted name is defined at that nesting.
    """
    import hashlib

    scope: List[ast.stmt] = ast.parse(source).body
    node: Optional[ast.AST] = None
    for part in qualname.split("."):
        matches = [s for s in scope
                   if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                   and s.name == part]
        # The live binding is the LAST definition, not the first: hashing the first verifies a
        # function the import never reaches while the one that runs goes unrecorded.
        node = matches[-1] if matches else None
        if node is None:
            return None
        scope = node.body
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    _strip_docstrings(node)
    return hashlib.sha256(repr(_canonical_ast(node)).encode("utf-8")).hexdigest()


def _split_node_id(node_id: str) -> List[str]:
    """A pytest node id split on `::`, ignoring separators inside `[...]` parameters."""
    parts, depth, current = [], 0, ""
    index, text = 0, str(node_id)
    while index < len(text):
        char = text[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth = max(0, depth - 1)
        if text[index:index + 2] == "::" and depth == 0:
            parts.append(current)
            current = ""
            index += 2
            continue
        current += char
        index += 1
    parts.append(current)
    return parts


def _test_id_resolves(test_path: Path, parts: List[str]) -> bool:
    """The node id's class chain and test name exist in the file, nested as written.

    A leaf-name text search accepts `tests/test_x.py::WrongClass::test_real` whenever a
    module-level `test_real` exists, so the entry names a test that was never collected.
    Each intermediate part must be a class enclosing the next; the last part must be a
    function it encloses, or a module-level function when there is no chain.
    """
    try:
        tree = ast.parse(test_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return False
    scope: List[ast.stmt] = tree.body
    *classes, name = [part.split("[")[0] for part in parts]
    for class_name in classes:
        node = next((s for s in scope
                     if isinstance(s, ast.ClassDef) and s.name == class_name), None)
        if node is None or not class_name:
            return False
        scope = node.body
    return bool(name) and any(
        isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) and s.name == name
        for s in scope)


def check_frozen_validated(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 19 (Frozen Functions): each registered body still hashes to its verified value.

    A changed body is not verified any more, so the change either re-verifies it and records the
    new hash and commit, or removes the entry. Each entry also names the tests that killed a
    mutant of it, and those must still exist.
    """
    import json

    root = repo_root or REPO_ROOT
    path = root / FROZEN_REGISTER
    if not path.is_file():
        return [f"{FROZEN_REGISTER} is missing"]
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))["functions"]
    except (ValueError, KeyError, TypeError) as exc:
        return [f"{FROZEN_REGISTER} does not parse: {exc}"]
    if not isinstance(entries, list) or not entries:
        return [f"{FROZEN_REGISTER} lists no functions, so this gate would check nothing"]
    violations: List[str] = []
    seen = set()
    for entry in entries:
        try:
            file, qualname, digest = entry["file"], entry["qualname"], entry["sha256"]
            commit, killed_by = entry["verified_at"], entry["killed_by"]
        except (KeyError, TypeError):
            violations.append(f"malformed entry {entry!r}")
            continue
        label = f"{file}::{qualname}"
        if label in seen:
            violations.append(f"{label} is registered twice")
        seen.add(label)
        if not re.fullmatch(r"[0-9a-f]{40}", str(commit)):
            violations.append(f"{label}: verified_at {commit!r} is not a full commit")
        source_path = root / file
        actual = (frozen_body_hash(source_path.read_text(encoding="utf-8"), qualname)
                  if source_path.is_file() else None)
        if actual is None:
            violations.append(f"{label}: no such function")
        elif actual != digest:
            violations.append(f"{label}: body changed since {str(commit)[:8]} "
                              "(re-verify and record the new hash, or unfreeze it)")
        if not killed_by:
            violations.append(f"{label}: names no killing test")
        for node_id in killed_by:
            parts = _split_node_id(node_id)
            if len(parts) < 2 or not _test_id_resolves(root / parts[0], parts[1:]):
                violations.append(f"{label}: killing test {node_id} does not exist")
    return violations
