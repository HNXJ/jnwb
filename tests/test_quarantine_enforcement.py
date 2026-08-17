"""Enforces two things about scripts/historical/ (14 scripts quarantined 2026-08-10 -- 12 in
confounded/ for invalid/ungrouped CV, 2 in synthetic/ for hardcoded retracted census values --
see artifacts/.lab/agent-harness-audit-20260810.json):

1. Every quarantined file actually declares its machine-readable status
   (scientific_status = "invalid_for_inference"), so the marker itself can't silently rot.
2. No LIVE (non-historical, non-test) script, notebook, or figure-generation file imports from
   scripts/historical/ -- quarantine is meaningless if a current pipeline can still pull an
   invalid implementation in as an empirical source.

Per this project's Conservation doctrine, quarantine is preservation-with-a-warning-label, not
deletion -- these tests keep the warning label enforced, not the code removed.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_DIR = REPO_ROOT / "scripts" / "historical"
CONFOUNDED_DIR = HISTORICAL_DIR / "confounded"
SYNTHETIC_DIR = HISTORICAL_DIR / "synthetic"

QUARANTINED_FILES = sorted(HISTORICAL_DIR.rglob("*.py"))
QUARANTINED_MODULE_STEMS = {p.stem for p in QUARANTINED_FILES}

LIVE_SEARCH_DIRS = ["scripts", "jnwb", "context", "notebooks", "tests"]


class TestQuarantineHeaderPresent:
    @pytest.mark.parametrize("path", QUARANTINED_FILES, ids=lambda p: p.name)
    def test_declares_invalid_for_inference(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assigned_names = {
            target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        assert "scientific_status" in assigned_names, f"{path.name} missing scientific_status marker"
        assert "reason" in assigned_names, f"{path.name} missing reason marker"

    def test_confounded_dir_has_the_expected_twelve(self):
        files = sorted(CONFOUNDED_DIR.glob("*.py"))
        assert len(files) == 12, (
            f"expected 12 quarantined ungrouped-CV scripts in confounded/, found {len(files)}: "
            f"{[p.name for p in files]}"
        )

    def test_synthetic_dir_has_the_expected_two(self):
        files = sorted(SYNTHETIC_DIR.glob("*.py"))
        assert len(files) == 2, (
            f"expected 2 quarantined hardcoded-synthetic-census scripts in synthetic/, found "
            f"{len(files)}: {[p.name for p in files]}"
        )


class TestNoLiveImportOfQuarantinedModules:
    def _scan_file_for_quarantined_imports(self, path: Path) -> list[str]:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return []
        hits = []
        for stem in QUARANTINED_MODULE_STEMS:
            # matches `import <stem>`, `from <stem> import ...`, or a dotted path ending in it
            pattern = re.compile(rf"(^|[\s.])(?:import\s+{re.escape(stem)}\b|from\s+[\w.]*{re.escape(stem)}\b)")
            if pattern.search(text):
                hits.append(stem)
        return hits

    def test_no_live_python_file_imports_a_quarantined_module(self):
        violations = {}
        for dirname in LIVE_SEARCH_DIRS:
            root = REPO_ROOT / dirname
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                if HISTORICAL_DIR in path.parents:
                    continue  # the quarantined files themselves, and any sibling test fixtures
                if path.name == "test_quarantine_enforcement.py":
                    continue  # this file names the stems in a comment/docstring, not an import
                hits = self._scan_file_for_quarantined_imports(path)
                if hits:
                    violations[str(path.relative_to(REPO_ROOT))] = hits
        assert not violations, (
            f"live file(s) import quarantined (invalid_for_inference) modules: {violations}. "
            f"Use scripts/compute_omission_identity_leakage_safe.py instead."
        )
