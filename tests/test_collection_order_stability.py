"""P-12: an ad-hoc pytest subset must not crash the interpreter.

The measured defect. `unittest.mock.patch.dict(sys.modules, ...)` restores by
`sys.modules.clear()` followed by `update(original)`, so every module imported *inside*
the block is evicted on exit. `tests/test_analyzers_coverage.py` blocked cupy that way to
reach the PyTorch fallback in `PopulationAnalyzer.population_trajectory`; that fallback
performs the process's first `import torch`, putting 730 `torch*` entries into
`sys.modules`, and the restore removed all 730 while torch's C extensions stayed loaded in
the process. The next `import torch` -- `jnwb/_backend.py:76`, reached from
`tests/test_backend.py::TestCapabilityProbes` -- re-executed `torch/__init__.py` against an
already-initialised `torch._C` and took an access violation (0xC0000005).

The full suite never saw it because collecting all of `tests/` imports torch and cupy
before any test runs, so both are in the dict `patch.dict` saved and restores. Only a
subset that does not collect that importer is exposed. That is the whole of P-12's
"collection-order fragility": not an ordering hazard in pytest, and not a property of
torch, but one test mutating process-global state destructively.

`test_the_minimal_subset_survives` is the phenomenon itself, run in a subprocess.
`test_no_test_module_clears_sys_modules` is the recurrence gate, and reads calls rather
than text so a sentence like the one above cannot satisfy or trip it.
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"

# Bisected from the two-module subset recorded against 0.2.5. The true minimum is one test
# from each class, but it is not a reliable witness: measured over 8 runs it crashed 7
# times, because with only one probe test the re-import sometimes completes and the
# access violation lands during interpreter shutdown instead. These two classes crashed
# 8 times out of 8, so the assertions below mean what they say on a single run.
CRASHING_SUBSET = [
    "tests/test_analyzers_coverage.py::TestPopulationAnalyzerTrajectory",
    "tests/test_backend.py::TestCapabilityProbes",
]
SUBSET_SIZE = 7


def _run_pytest(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )


class TestTheSubsetThatUsedToCrash:
    def test_the_selector_collects_the_tests_it_names(self):
        """A selector that collects nothing also exits non-zero, and would make the
        crash test below pass for the wrong reason -- or fail for it."""
        done = _run_pytest(["--collect-only", *CRASHING_SUBSET])
        assert done.returncode == 0, done.stdout + done.stderr
        assert f"{SUBSET_SIZE} tests collected" in done.stdout, done.stdout

    def test_the_subset_survives_in_isolation(self):
        """Exit 0 and every test passing. A segfault gives 3221225477 on Windows and 139
        under a POSIX shell, and can arrive after pytest has already printed its summary,
        so the returncode is checked as well as the summary -- neither alone is enough."""
        done = _run_pytest(CRASHING_SUBSET)
        assert done.returncode == 0, (
            f"running {CRASHING_SUBSET} in isolation exited {done.returncode}; "
            f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}"
        )
        assert f"{SUBSET_SIZE} passed" in done.stdout, done.stdout


class TestNoTestDestroysSysModules:
    """`patch.dict(sys.modules, ...)` cannot be made safe by being used carefully: its
    restore clears the dict unconditionally, so it silently evicts anything imported
    inside the block, whether or not the author expected an import there."""

    @staticmethod
    def _sys_modules_patch_dict_calls(tree: ast.AST) -> list[int]:
        hits = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "dict"):
                continue
            owner = func.value
            owner_name = getattr(owner, "id", None) or getattr(owner, "attr", None)
            if owner_name != "patch":
                continue
            if not node.args:
                continue
            first = node.args[0]
            target = ast.unparse(first)
            if target in ("sys.modules", "modules"):
                hits.append(node.lineno)
        return hits

    def test_the_detector_sees_a_planted_call_and_not_a_sentence(self):
        """A live zero proves nothing about a detector. Give it one of each."""
        planted = ast.parse(
            "import sys\n"
            "from unittest.mock import patch\n"
            "with patch.dict(sys.modules, {'cupy': None}):\n"
            "    pass\n"
        )
        assert self._sys_modules_patch_dict_calls(planted) == [3]

        prose = ast.parse('"""Do not call patch.dict(sys.modules, {...}) here."""\n')
        assert self._sys_modules_patch_dict_calls(prose) == []

    def test_no_test_module_clears_sys_modules(self):
        offenders = []
        checked = 0
        for path in sorted(TESTS_DIR.glob("test_*.py")):
            checked += 1
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for lineno in self._sys_modules_patch_dict_calls(tree):
                offenders.append(f"{path.name}:{lineno}")

        assert checked > 1, "no test modules were read; this test checks nothing"
        assert offenders == [], (
            "patch.dict on sys.modules restores with clear()+update(), evicting every "
            "module imported inside the block; a later re-import of an extension module "
            "whose C state is still loaded crashes the interpreter. Block the single "
            "import by name and restore that one key instead. Offenders: "
            + "; ".join(offenders)
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
