"""Shipped source cites no repository process state: rulings, stack rows or roadmap ids.

A reader of ``jnwb/`` has the code and its docs, not the repository's planning files, so a
comment that cites one points nowhere.
"""
from __future__ import annotations

import re
from pathlib import Path

import jnwb

PACKAGE = Path(jnwb.__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESS_ID = re.compile(
    r"\bruled\b|\bruling\b|\bhamm\b|\bharness\b|fact stack|^\s*Important\b"
    r"|\broadmap\b|todo stack|problem stack|open stack"
    r"|\bP-\d{2,3}\b|\b(?:IA|IB)-\d+\b",
    re.IGNORECASE | re.MULTILINE,
)
SCRIPT_TEST_PROCESS = re.compile(r"\b(?:ruled|rulings?|hamm)\b", re.IGNORECASE)
STACK_TEST_FILES = frozenset({
    "test_fact_gate.py",
    "test_harness_adversarial_gates.py",
    "test_learning_gate.py",
    "test_obligation_diff.py",
    "test_shipped_code_names_no_process_ids.py",
    "test_skill_symbol_coverage.py",
    "test_stack_metadata_contradictions.py",
    "test_state_reconstruction.py",
})
ALLOWED_SCRIPT_PATTERNS = {
    "scripts/learning_gate.py": (),  # reads "Ruled <date>" citations in artifacts/
    "scripts/build_fact_graph.py": (
        "FACT_HEADER =",
        "CONSTANT_HEADER =",
        "fact_id, domain, predicate, held_by, ruled = row",
        '"ruled": ruled,',
    ),
    "scripts/gates/stacks_form.py": (
        '"needs a ruling",',
        '"requires a ruling",',
        '"awaits a ruling",',
    ),
    "scripts/gates/stacks_pointers.py": ("ROLE_PLACEHOLDERS =",),
    "scripts/obligation_diff.py": ("DEFAULT_FILES =",),
}


def _hits(text: str) -> list[int]:
    return [n for n, line in enumerate(text.splitlines(), 1) if PROCESS_ID.search(line)]


def _is_allowed_script_or_test_hit(rel: str, line: str) -> bool:
    if (
        rel == "tests/test_ontology.py"
        and '("ses-2607", "mm_depth", "probeA", "omission", "Hamm")' in line
    ):
        return True
    if rel in ALLOWED_SCRIPT_PATTERNS:
        patterns = ALLOWED_SCRIPT_PATTERNS[rel]
        return not patterns or any(pat in line for pat in patterns)
    return False


def test_shipped_source_cites_no_process_ids():
    files = sorted(PACKAGE.rglob("*.py"))
    assert len(files) > 20, "the scan must read the package"
    found = [f"{p.relative_to(PACKAGE).as_posix()}:{n}"
             for p in files for n in _hits(p.read_text(encoding="utf-8"))]
    assert not found, found


def test_tests_and_scripts_carry_no_process_vocabulary_outside_stack_readers():
    files = sorted((REPO_ROOT / "tests").glob("*.py"))
    for pattern in ("*.py", "*.sh", "*.js"):
        files.extend(sorted((REPO_ROOT / "scripts").rglob(pattern)))
    found = []
    for path in files:
        if path.parent == REPO_ROOT / "tests" and path.name in STACK_TEST_FILES:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if (
                SCRIPT_TEST_PROCESS.search(line)
                and not _is_allowed_script_or_test_hit(rel, line)
            ):
                found.append(f"{rel}:{lineno}: {line.strip()}")
    assert not found, found


def test_the_pattern_finds_each_kind_and_passes_plain_code():
    for line in ("# ruled 2026-10-18", "# see roadmap 15-19", "# P-335", "# IA-3",
                 "# the todo stack row", "# Hamm", "# read by a harness",
                 "# the fact stack's", "    Important Scientific Invariants:"):
        assert _hits(line) == [1], line
    assert _hits("x = rule_of_thumb(p_value)\n# a P-value test") == []
