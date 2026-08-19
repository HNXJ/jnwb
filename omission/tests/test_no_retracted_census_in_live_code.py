"""Sol/Hamm Handout 2 acceptance test 4: searching executable current code for 421, 8597, or
4.90% must produce either zero hits or explicitly historical fixtures that cannot enter an
empirical pipeline.

context/docs/CONTEXT.md Section 8 retracts this figure (421/8597 O+ units = 4.90%, the
synthetic census) explicitly. Before 2026-08-10 it was live and unlabeled in
notebooks/reproducibility_master_pipeline.py (asserted + printed "PASS"), jnwb/
unit_classification.py's docstring, scripts/build_oplusplus_census.py's output receipt, and
scripts/generate_publication_figures.py's hardcoded arrays -- see
artifacts/.lab/agent-harness-audit-20260810.json, claim-p0-stale-census-in-executable-code.
This test is the permanent regression guard.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Directories where the retracted numbers are EXPECTED to still appear -- explicitly historical/
# quarantined locations, or documentation/receipts that reference the retraction itself (not an
# empirical pipeline). Everything else must be clean.
ALLOWED_DIRS = {
    "scripts/historical",
    "notebooks/historical",
    "scripts/archive_oneoff",
    "context/archive",
    "context/draft-assets",
    "legacy",
    "docs",  # the audit report itself cites the numbers as receipts, not as live claims
    "artifacts",  # .lab graph nodes and data receipts that document the retraction
}

# Live directories actually swept for the retracted values.
LIVE_SEARCH_DIRS = ["jnwb", "scripts", "notebooks", "tests"]

RETRACTED_PATTERNS = [
    re.compile(r"\b421\b"),
    re.compile(r"\b8597\b"),
    re.compile(r"4\.90%?"),
]


def _is_allowed(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    return any(rel.startswith(allowed) for allowed in ALLOWED_DIRS)


def _find_hits(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in RETRACTED_PATTERNS:
            if pattern.search(line):
                hits.append(f"{lineno}: {line.strip()}")
                break
    return hits


class TestNoRetractedCensusValuesLive:
    def test_no_python_file_outside_historical_dirs_contains_retracted_census(self):
        violations: dict[str, list[str]] = {}
        for dirname in LIVE_SEARCH_DIRS:
            root = REPO_ROOT / dirname
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                if _is_allowed(path):
                    continue
                hits = _find_hits(path)
                # Explanatory comments ABOUT the removal (e.g. "421/8597=4.90% figure was
                # removed") are fine -- only flag if the file does NOT also explain itself.
                if hits and not any(
                    marker in "\n".join(hits).lower()
                    for marker in ("retract", "removed", "quarantin", "synthetic")
                ):
                    violations[str(path.relative_to(REPO_ROOT))] = hits
        assert not violations, (
            f"live (non-historical) file(s) contain the retracted 421/8597/4.90% census values "
            f"without an explanatory retraction marker: {violations}"
        )

    def test_no_notebook_outside_historical_dirs_contains_retracted_census(self):
        violations: dict[str, list[str]] = {}
        for dirname in LIVE_SEARCH_DIRS:
            root = REPO_ROOT / dirname
            if not root.is_dir():
                continue
            for path in root.rglob("*.ipynb"):
                if _is_allowed(path):
                    continue
                hits = _find_hits(path)
                if hits:
                    violations[str(path.relative_to(REPO_ROOT))] = hits[:3]
        assert not violations, (
            f"live (non-historical) notebook(s) contain the retracted 421/8597/4.90% census "
            f"values: {violations}"
        )

    def test_known_quarantined_files_are_exactly_where_expected(self):
        # Sanity check the allowlist itself isn't accidentally hiding something that should be
        # live -- these specific files are EXPECTED to still contain the numbers (as forensic
        # evidence / retraction documentation), confirming the quarantine move actually happened.
        expected_historical = [
            REPO_ROOT / "notebooks" / "historical" / "reproducibility_master_pipeline.py",
            REPO_ROOT / "scripts" / "historical" / "synthetic" / "generate_publication_figures.py",
        ]
        for path in expected_historical:
            assert path.is_file(), f"expected quarantined file missing: {path}"
            assert _find_hits(path), f"{path} no longer contains the retracted numbers -- was it edited unexpectedly?"
