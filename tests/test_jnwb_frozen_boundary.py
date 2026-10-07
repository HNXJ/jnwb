"""Guards the jnwb/ LAYERING boundary: jnwb/ must remain importable and usable with zero
dependency on any project folder. As of 2026-09-03 there are no exceptions -- jnwb/ imports
nothing from omission/ -- so its scientific behaviour cannot depend on whether a project
package happens to be installed.

Naming note (corrected 2026-09-09): this file is called "frozen_boundary" and its docstring
used to claim it enforced the jnwb/ edit freeze. It never did, and could not -- nothing here
looks at whether jnwb/ was edited. It enforces the dependency DIRECTION. The edit freeze was
lifted on 2026-09-09; this boundary is unaffected and still live, because it never rested
on the freeze.

A human reading a policy is not a technical guarantee that no new jnwb/ change quietly
reintroduces a project coupling. These tests are.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from scripts import harness_gate
from scripts.harness_gate import check_frozen_boundary

REPO_ROOT = Path(__file__).resolve().parent.parent
JNWB_DIR = REPO_ROOT / "jnwb"
TESTS_DIR = REPO_ROOT / "tests"

# The import scan is `check_frozen_boundary` in scripts/harness_gate.py, and the only omission-side
# imports jnwb/ may contain are its `AUTHORIZED_JNWB_EXCEPTIONS`, each a lazy, function-body-local
# import. Any other omission import anywhere under jnwb/, whether or not inside a function body,
# fails it.
#
# That set is EMPTY. addressing.py's exception was removed 2026-09-03: importing the
# project's parser meant jnwb resolved probe areas differently depending on whether omission
# happened to be importable, so installing a project package silently changed which cortical
# area a unit was assigned to. addressing.py now carries no area vocabulary at all: it only
# splits the label on comma or slash and trims whitespace, preserving every label as written.
# jrsa.py's exception went with the connectivity promotion on 2026-08-23.


class TestJnwbFrozenBoundary:
    def test_no_unauthorized_omission_imports(self):
        violations = check_frozen_boundary(JNWB_DIR)
        assert not violations, (
            "jnwb/ imports from omission/ (see AUTHORIZED_JNWB_EXCEPTIONS in "
            "scripts/harness_gate.py). Either this is a new coupling that needs Hamm's explicit "
            "authorization before it can land, or a listed exception is no longer lazy:\n"
            + "\n".join(violations)
        )

    def test_the_scan_finds_imports_at_both_levels_and_holds_exceptions_lazy(
        self, tmp_path, monkeypatch
    ):
        """jnwb/ has no omission import and no exception, so the scan passes by finding nothing.

        It would keep passing if it stopped finding anything. Exercise it on a tree that has
        imports at module level and inside a function body, then with two of them authorized:
        the lazy one is accepted, the module-level one still fails.
        """
        (tmp_path / "m.py").write_text(
            "import omission.alpha\n"
            "from omission.beta import thing\n"
            "import numpy\n"
            "def f():\n"
            "    import omission.gamma\n",
            encoding="utf-8",
        )
        assert sorted(check_frozen_boundary(tmp_path)) == [
            "UNAUTHORIZED_IMPORT: m.py:1 imports 'omission.alpha'",
            "UNAUTHORIZED_IMPORT: m.py:2 imports 'omission.beta'",
            "UNAUTHORIZED_IMPORT: m.py:5 imports 'omission.gamma'",
        ]
        monkeypatch.setattr(
            harness_gate,
            "AUTHORIZED_JNWB_EXCEPTIONS",
            {("m.py", "omission.alpha"), ("m.py", "omission.gamma")},
        )
        assert sorted(check_frozen_boundary(tmp_path)) == [
            "NON_LAZY_IMPORT: m.py:1 imports 'omission.alpha' at module level",
            "UNAUTHORIZED_IMPORT: m.py:2 imports 'omission.beta'",
        ]

    def test_jnwb_test_suite_does_not_import_omission(self):
        """The suite that guards the freeze must itself run without omission/ present.

        omission/ is untracked (2026-09-03), so a CI checkout contains only jnwb. A single
        `from omission... import ...` in tests/ therefore turns `pytest tests/` red on every
        run while still passing on any developer machine that has omission checked out --
        which is exactly what happened between 2026-09-03 and 2026-09-04. Project-side tests
        belong in omission/tests/.
        """
        violations = check_frozen_boundary(TESTS_DIR)
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
