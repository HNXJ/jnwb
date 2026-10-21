"""Shipped source cites no repository process state: rulings, stack rows or roadmap ids.

A reader of ``jnwb/`` has the code and its docs, not the repository's planning files, so a
comment that cites one points nowhere.
"""
from __future__ import annotations

import re
from pathlib import Path

import jnwb

PACKAGE = Path(jnwb.__file__).resolve().parent
PROCESS_ID = re.compile(
    r"\bruled\b|\bruling\b|\broadmap\b|todo stack|problem stack|open stack"
    r"|\bP-\d{2,3}\b|\b(?:IA|IB)-\d+\b",
    re.IGNORECASE,
)


def _hits(text: str) -> list[int]:
    return [n for n, line in enumerate(text.splitlines(), 1) if PROCESS_ID.search(line)]


def test_shipped_source_cites_no_process_ids():
    files = sorted(PACKAGE.rglob("*.py"))
    assert len(files) > 20, "the scan must read the package"
    found = [f"{p.relative_to(PACKAGE).as_posix()}:{n}"
             for p in files for n in _hits(p.read_text(encoding="utf-8"))]
    assert not found, found


def test_the_pattern_finds_each_kind_and_passes_plain_code():
    for line in ("# ruled 2026-10-18", "# see roadmap 15-19", "# P-335", "# IA-3",
                 "# the todo stack row"):
        assert _hits(line) == [1], line
    assert _hits("x = rule_of_thumb(p_value)\n# a P-value test") == []
