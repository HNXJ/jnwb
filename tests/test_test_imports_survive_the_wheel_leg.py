"""A test module may not import, at module scope, a repository path the wheel does not ship.

P-168. ``tests/test_state_reconstruction.py`` imported ``scripts.reconstruct_state`` at module
scope. ``scripts*`` is excluded from the wheel, and the leg at
``.github/workflows/workflow.yml`` that qualifies the built artifact runs this suite from
outside the repository with ``-o pythonpath=`` and ``--import-mode=importlib``, so nothing puts
the checkout on ``sys.path``. The import raised ``ModuleNotFoundError`` during *collection*,
which pytest reports as ``Interrupted`` -- not a skip, and not confined to the offending module.

Two properties of that defect are why this file derives its answer instead of listing it:

* It was **masked**. In the full alphabetical run, ``test_dependency_floors_are_installable.py``
  sorts earlier and appends the repository root to ``sys.path`` as a side effect, so every later
  module inherits it. The four offenders measured at 0.2.6 all collected fine in the full run
  and all failed in isolation. A rename of one unrelated file would have fired them.
* Nothing compared the set of paths the tests import against the set of paths the wheel ships.
  A hand-maintained list of exempt modules would have been written at the moment the four were
  known and would have gone stale the same way -- P-15 and the narrowing defect at once.

So the shipped set is read out of ``pyproject.toml``'s own ``include``/``exclude`` patterns
through setuptools, the imports are read out of the test modules' syntax trees, and the two are
compared. The self-checks below exist because the failure mode of a derived check is deriving
nothing and passing: an empty shipped set, or an AST walk that matches no import, would satisfy
the comparison silently.
"""

from __future__ import annotations

import ast
import pathlib
import sys
import tomllib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"
PYPROJECT = REPO_ROOT / "pyproject.toml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "workflow.yml"

# The one-line repair, quoted in the failure message so a reader does not have to find it.
_REPAIR = (
    "add, above the import:\n"
    "    if str(REPO_ROOT) not in sys.path:\n"
    "        sys.path.append(str(REPO_ROOT))\n"
    "and mark the import `# noqa: E402`. `append`, never `insert` -- `insert(0, ...)` "
    "re-shadows the installed package for the whole session, which is what "
    "tests/test_the_suite_can_qualify_an_installed_copy.py forbids."
)


def _shipped_top_level_packages() -> set[str]:
    """Top-level package names the wheel ships, per pyproject's own find directives."""
    from setuptools import find_namespace_packages, find_packages

    find = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["setuptools"][
        "packages"
    ]["find"]
    discovered = set(
        find_packages(
            where=str(REPO_ROOT), include=find["include"], exclude=find["exclude"]
        )
    ) | set(
        find_namespace_packages(
            where=str(REPO_ROOT), include=find["include"], exclude=find["exclude"]
        )
    )
    return {name.split(".")[0] for name in discovered}


def _module_scope_imports(tree: ast.Module) -> list[tuple[str, int]]:
    """``(top_level_name, lineno)`` for every import executed when the module is imported.

    Module-level ``if`` / ``try`` / ``with`` bodies count: their contents run at import time, so
    an import hidden in one fails collection exactly like a bare import. Only relative imports
    are skipped, since they resolve within the ``tests`` package itself.
    """
    found: list[tuple[str, int]] = []

    def walk(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.Import):
                found.extend((alias.name.split(".")[0], node.lineno) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    found.append((node.module.split(".")[0], node.lineno))
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                for attribute in ("body", "orelse", "finalbody"):
                    walk(getattr(node, attribute, None) or [])
                for handler in getattr(node, "handlers", None) or []:
                    walk(handler.body)

    walk(tree.body)
    return found


def _sys_path_extension_lines(tree: ast.Module) -> list[int]:
    """Line numbers of module-scope ``sys.path.append`` / ``.insert`` calls.

    Matched in the syntax tree rather than by substring: the same words appear in this
    repository inside docstrings, in generated source written to ``tmp_path``, and in string
    literals that other tests scan for. A substring check would accept all of those and is the
    kind of proxy P-37 collects.
    """
    lines: list[int] = []

    def walk(body: list[ast.stmt]) -> None:
        for node in body:
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                func = inner.func
                if not isinstance(func, ast.Attribute) or func.attr not in {
                    "append",
                    "insert",
                }:
                    continue
                target = func.value
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr == "path"
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "sys"
                ):
                    lines.append(node.lineno)
            if isinstance(node, (ast.If, ast.Try, ast.With)):
                for attribute in ("body", "orelse", "finalbody"):
                    walk(getattr(node, attribute, None) or [])
                for handler in getattr(node, "handlers", None) or []:
                    walk(handler.body)

    walk(tree.body)
    return lines


def _unshipped_repo_paths() -> set[str]:
    """Top-level directories that exist in the checkout and are absent from the wheel."""
    shipped = _shipped_top_level_packages()
    return {
        entry.name
        for entry in REPO_ROOT.iterdir()
        if entry.is_dir()
        and not entry.name.startswith(".")
        and entry.name not in shipped
        and entry.name not in sys.stdlib_module_names
    }


def _offenders() -> list[tuple[str, int, str]]:
    unshipped = _unshipped_repo_paths()
    rows: list[tuple[str, int, str]] = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        extensions = _sys_path_extension_lines(tree)
        for name, lineno in _module_scope_imports(tree):
            if name not in unshipped:
                continue
            # The extension must run *before* the import, not merely exist in the file.
            if not any(line < lineno for line in extensions):
                rows.append((path.name, lineno, name))
    return rows


# --------------------------------------------------------------------------------------------
# Self-checks. Each one fails if this file's derivation has quietly stopped deriving anything.
# --------------------------------------------------------------------------------------------


def test_the_shipped_set_is_actually_derived():
    shipped = _shipped_top_level_packages()
    assert shipped, "no packages discovered; the find directives were not read"
    assert "jnwb" in shipped, f"jnwb is not in the shipped set: {sorted(shipped)}"


def test_scripts_is_not_shipped_so_this_invariant_is_live():
    """If ``scripts/`` ever ships, this whole file is asserting a premise that no longer holds.

    That is a packaging-boundary change, and it should surface as this test failing rather than
    as every check above passing for a reason that has gone away.
    """
    assert "scripts" not in _shipped_top_level_packages(), (
        "scripts/ is now shipped in the wheel; P-168's premise has changed and "
        "tests/test_test_imports_survive_the_wheel_leg.py must be revisited"
    )


def test_the_import_walk_finds_the_imports_it_is_meant_to_police():
    """A walk that matches nothing would make every comparison below vacuous."""
    importers = [
        path.name
        for path in sorted(TESTS_DIR.glob("test_*.py"))
        if any(
            name == "scripts"
            for name, _ in _module_scope_imports(ast.parse(path.read_text(encoding="utf-8")))
        )
    ]
    assert len(importers) >= 2, (
        f"the module-scope import walk found {len(importers)} modules importing `scripts`; "
        "this suite is known to contain many, so the walk has stopped working"
    )


def test_the_sys_path_walk_finds_the_calls_it_is_meant_to_credit():
    """The converse: a walk that credits nothing would flag every module as an offender."""
    crediting = [
        path.name
        for path in sorted(TESTS_DIR.glob("test_*.py"))
        if _sys_path_extension_lines(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert len(crediting) >= 2, (
        f"the sys.path walk credited {len(crediting)} modules; this suite is known to contain "
        "many that append the repository root, so the walk has stopped working"
    )


def test_the_qualification_leg_still_clears_pythonpath():
    """The premise, pinned to the workflow rather than assumed from memory.

    If ``-o pythonpath=`` is ever dropped from the leg, the checkout is back on ``sys.path``,
    this file's invariant becomes unnecessary -- and, worse, the leg stops qualifying the wheel.
    Either way a human should look, so this fails instead of relaxing.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "-o pythonpath=" in workflow, (
        "the wheel-qualification leg no longer clears pytest's pythonpath; the suite may be "
        "testing the checkout while reporting on the wheel"
    )


# --------------------------------------------------------------------------------------------
# The invariant.
# --------------------------------------------------------------------------------------------


def test_no_test_module_imports_an_unshipped_path_without_reaching_for_it():
    offenders = _offenders()
    if offenders:
        listing = "\n".join(
            f"  {name}:{lineno} imports `{package}`, which the wheel does not ship"
            for name, lineno, package in offenders
        )
        pytest.fail(
            "these test modules fail collection in the wheel-qualification leg, where the "
            "checkout is not on sys.path. In the full run they are masked by an earlier "
            "module's sys.path.append, so the suite looks green:\n"
            f"{listing}\n\nFor each, {_REPAIR}"
        )
