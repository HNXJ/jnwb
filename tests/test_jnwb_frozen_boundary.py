"""Guards the jnwb/ LAYERING boundary: jnwb/ must remain importable and usable with zero
dependency on any project folder. As of 2026-09-03 there are no exceptions -- jnwb/ imports
nothing from omission/ -- so its scientific behaviour cannot depend on whether a project
package happens to be installed.

Naming note (corrected 2026-09-09): this file is called "frozen_boundary" and its docstring
used to claim it enforced the jnwb/ edit freeze. It never did, and could not -- nothing here
looks at whether jnwb/ was edited. It enforces the dependency DIRECTION. The edit freeze was
lifted on 2026-09-09 (see CLAUDE.md); this boundary is unaffected and still live, because it
never rested on the freeze.

A human reading a policy is not a technical guarantee that no new jnwb/ change quietly
reintroduces a project coupling. These tests are.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JNWB_DIR = REPO_ROOT / "jnwb"
TESTS_DIR = REPO_ROOT / "tests"

# (path relative to jnwb/, fully-qualified module imported) -- the ONLY omission-side imports
# jnwb/ may contain, and only as lazy, function-body-local imports. Any other omission import
# anywhere under jnwb/, whether or not inside a function body, fails the freeze.
#
# This set is now EMPTY. addressing.py's exception was removed 2026-09-03: importing the
# project's parser meant jnwb resolved probe areas differently depending on whether omission
# happened to be importable, so installing a project package silently changed which cortical
# area a unit was assigned to. addressing.py now carries no area vocabulary at all: it only
# splits the label on comma or slash and trims whitespace, preserving every label as written.
# jrsa.py's exception went with the connectivity promotion on 2026-08-23.
AUTHORIZED_EXCEPTIONS: set = set()


def _iter_py_files():
    for p in JNWB_DIR.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def _omission_imports(tree: ast.Module):
    """Yield (lineno, module_name, is_module_level) for every omission/-side import in tree."""
    module_level_nodes = set(id(n) for n in tree.body)
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names = [node.module]
        for name in names:
            if name == "omission" or name.startswith("omission."):
                yield node.lineno, name, id(node) in module_level_nodes


class TestJnwbFrozenBoundary:
    def test_no_unauthorized_omission_imports(self):
        violations = []
        for f in _iter_py_files():
            rel = f.relative_to(JNWB_DIR).as_posix()
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for lineno, modname, _module_level in _omission_imports(tree):
                if (rel, modname) not in AUTHORIZED_EXCEPTIONS:
                    violations.append(f"jnwb/{rel}:{lineno} imports {modname!r}")
        assert not violations, (
            "jnwb/ imports from omission/ (see CLAUDE.md's freeze policy and AUTHORIZED_EXCEPTIONS in this test). "
            "Either this is a new coupling that needs Hamm's explicit authorization before it "
            "can land, or AUTHORIZED_EXCEPTIONS needs updating alongside it:\n"
            + "\n".join(violations)
        )

    def test_authorized_exceptions_are_lazy_not_module_level(self):
        # Both authorized exceptions must be call-time imports inside a function body, never
        # at module level -- `import jnwb` alone must never require omission/ to exist.
        violations = []
        for relname, modname in AUTHORIZED_EXCEPTIONS:
            f = JNWB_DIR / relname
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for lineno, found_mod, module_level in _omission_imports(tree):
                if found_mod == modname and module_level:
                    violations.append(f"jnwb/{relname}:{lineno} imports {modname!r} at module level")
        assert not violations, (
            "An authorized omission/ import is no longer lazy -- this breaks the guarantee that "
            "jnwb/ is importable without omission/ present:\n" + "\n".join(violations)
        )

    def test_jnwb_test_suite_does_not_import_omission(self):
        """The suite that guards the freeze must itself run without omission/ present.

        omission/ is untracked (2026-09-03), so a CI checkout contains only jnwb. A single
        `from omission... import ...` in tests/ therefore turns `pytest tests/` red on every
        run while still passing on any developer machine that has omission checked out --
        which is exactly what happened between 2026-09-03 and 2026-09-04. Project-side tests
        belong in omission/tests/.
        """
        violations = []
        for f in TESTS_DIR.rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for lineno, modname, _ in _omission_imports(tree):
                violations.append(f"tests/{f.relative_to(TESTS_DIR).as_posix()}:{lineno} "
                                  f"imports {modname!r}")
        assert not violations, (
            "The jnwb test suite imports a project package, so it cannot run on a checkout "
            "that has only jnwb (i.e. CI). Move these tests into omission/tests/:\n"
            + "\n".join(violations)
        )

    def test_jnwb_importable_without_omission_on_sys_path(self):
        # The strongest guarantee: `import jnwb` succeeds in a subprocess where any import of
        # omission (or a submodule of it) is made to fail, simulating omission/ not existing at
        # all. This only exercises jnwb/__init__.py's own import graph -- it does not call into
        # the two lazy exceptions, which only run on their specific multi-area/PSI code paths.
        script = (
            "import sys\n"
            "class _BlockOmission:\n"
            "    def find_spec(self, fullname, path=None, target=None):\n"
            "        if fullname == 'omission' or fullname.startswith('omission.'):\n"
            "            raise ImportError('omission/ blocked for this test')\n"
            "        return None\n"
            "sys.meta_path.insert(0, _BlockOmission())\n"
            "import jnwb\n"
            "print('JNWB_IMPORT_OK', jnwb.__version__)\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0 and "JNWB_IMPORT_OK" in result.stdout, (
            "`import jnwb` failed with omission/ blocked from sys.path -- jnwb/ is not actually "
            f"standalone, breaking the freeze guarantee.\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_jnwb_all_symbols_resolve(self):
        # Completeness check: every name jnwb/__init__.py declares in __all__ must actually be
        # bound on the package -- a frozen library with a dangling __all__ entry is not complete.
        import jnwb
        missing = [name for name in jnwb.__all__ if not hasattr(jnwb, name)]
        assert not missing, f"jnwb.__all__ names not actually bound on the package: {missing}"
