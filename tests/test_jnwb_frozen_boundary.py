"""Guards the jnwb/ freeze boundary (CLAUDE.md, 2026-08-19): jnwb/ is frozen and must remain
importable and usable with zero dependency on omission/, except two explicitly authorized,
call-time-only exceptions (multi-area probe splitting in addressing.py, PSI delegation in
jrsa.py -- both need this project's area/band-naming conventions and were judged not worth
duplicating into jnwb/ for a single call site each).

This is the automated guarantee behind the freeze: a human reading CLAUDE.md's freeze policy is
not a technical guarantee that no new jnwb/ change quietly reintroduces an omission/ coupling.
These tests are.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JNWB_DIR = REPO_ROOT / "jnwb"

# (path relative to jnwb/, fully-qualified module imported) -- the ONLY omission-side imports
# jnwb/ may contain, and only as lazy, function-body-local imports. Any other omission import
# anywhere under jnwb/, or either of these two outside a function body, fails the freeze.
AUTHORIZED_EXCEPTIONS = {
    ("addressing.py", "omission.jnwb_ext.sequence_layout"),
    ("jrsa.py", "omission.jnwb_ext.connectivity"),
}


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
            "jnwb/ imports from omission/ outside the two documented, explicitly authorized "
            "exceptions (see CLAUDE.md's freeze policy and AUTHORIZED_EXCEPTIONS in this test). "
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

    def test_jnwb_importable_without_omission_on_sys_path(self):
        # The strongest guarantee: `import jnwb` succeeds in a subprocess where any import of
        # omission (or a submodule of it) is made to fail, simulating omission/ not existing at
        # all. This only exercises jnwb/__init__.py's own import graph -- it does not call into
        # the two lazy exceptions, which only run on their specific multi-area/PSI code paths.
        script = (
            "import sys\n"
            "class _BlockOmission:\n"
            "    def find_module(self, name, path=None):\n"
            "        if name == 'omission' or name.startswith('omission.'):\n"
            "            raise ImportError('omission/ blocked for this test')\n"
            "        return None\n"
            "sys.meta_path.insert(0, _BlockOmission())\n"
            f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
            "import jnwb\n"
            "print('JNWB_IMPORT_OK', jnwb.__version__)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=60,
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
