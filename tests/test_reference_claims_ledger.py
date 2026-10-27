"""Every claim cell of the references page has one line in the reference claims ledger.

`docs/references.md` states a claim in the second column of each body row of each table: the
result jnwb implements, the topic a core text gives, the result a study reproduces, or the
pitfall a paper states. `artifacts/evidence/0.2.14/reference_claims_ledger.md` gives each such
cell one line with its verdict and the source it was read from. This module recounts the cells
with the page's own table reader and requires one ledger line per cell, no line for a cell the
page lacks, and summary counts that agree with the lines.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[1]))  # needed: wheel run clears pythonpath

from scripts.build_fact_graph import reference_table_rows  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "references.md"
LEDGER = ROOT / "artifacts" / "evidence" / "0.2.14" / "reference_claims_ledger.md"

VERDICTS = ("confirmed", "reworded", "cut", "kept", "unrecorded")
#: The author-year of a reference cell: everything through its first "(YYYY)".
YEAR_KEY = re.compile(r"^(.*?\(\d{4}[a-z]?\))")
#: A ledger body row: five cells between pipes.
LEDGER_ROW = re.compile(r"^\|(.+)\|$")
#: A summary bullet, such as "- cut: 60".
SUMMARY = re.compile(r"^- ([a-z ]+): (\d+)$", re.MULTILINE)


def claim_cells(page: str) -> dict[tuple[str, str], str]:
    """``{(section, author-year): claim}`` for every claim cell on the page."""
    cells: dict[tuple[str, str], str] = {}
    for _, section, reference, claim, _ in reference_table_rows(page):
        match = YEAR_KEY.match(reference)
        assert match, f"no author-year in a reference cell: {reference[:60]}"
        key = (section, match.group(1))
        assert key not in cells, f"two claim cells share the key {key}"
        cells[key] = claim
    return cells


def _body_cells(line: str) -> list[str] | None:
    match = LEDGER_ROW.match(line.rstrip("\r\n"))
    if not match:
        return None
    cells = [cell.strip() for cell in match.group(1).split("|")]
    if len(cells) != 5 or cells[0] == "Section" or set(cells[0]) <= {"-"}:
        return None
    return cells


def ledger_entries(ledger: str) -> list[tuple[tuple[str, str], str, str, str]]:
    """``(key, column, verdict, source)`` for each body row of the ledger's table."""
    entries = []
    for line in ledger.splitlines():
        cells = _body_cells(line)
        if cells:
            section, reference, column, verdict, source = cells
            entries.append(((section, reference), column, verdict, source))
    return entries


def ledger_problems(page: str, ledger: str) -> list[str]:
    cells = claim_cells(page)
    entries = ledger_entries(ledger)
    keys = [key for key, *_ in entries]
    problems = [f"no ledger line for {key}" for key in cells if key not in keys]
    problems += [f"a ledger line for a cell the page lacks: {key}"
                 for key in keys if key not in cells]
    problems += [f"{keys.count(key)} ledger lines for {key}"
                 for key in dict.fromkeys(keys) if keys.count(key) > 1]
    problems += [f"column {column!r} is not claim: {key}"
                 for key, column, _, _ in entries if column != "claim"]
    problems += [f"verdict {verdict!r} is not one of {VERDICTS}: {key}"
                 for key, _, verdict, _ in entries if verdict not in VERDICTS]
    problems += [f"no source read: {key}" for key, _, _, source in entries if not source]
    return problems


def summary_problems(page: str, ledger: str) -> list[str]:
    counted = {name: int(n) for name, n in SUMMARY.findall(ledger)}
    entries = ledger_entries(ledger)
    problems = []
    cells = len(claim_cells(page))
    if counted.get("claim cells") != cells:
        problems.append(f"claim cells: the summary says {counted.get('claim cells')}, "
                        f"the page has {cells}")
    for verdict in VERDICTS:
        lines = sum(1 for _, _, v, _ in entries if v == verdict)
        if counted.get(verdict) != lines:
            problems.append(f"{verdict}: the summary says {counted.get(verdict)}, "
                            f"the ledger has {lines} lines")
    return problems


@pytest.fixture(scope="module")
def page() -> str:
    return PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ledger() -> str:
    return LEDGER.read_text(encoding="utf-8")


def test_the_page_reader_finds_claim_cells_to_recount(page):
    # A reader that matched nothing would make the checks below pass vacuously.
    cells = claim_cells(page)
    assert len(cells) >= 20, f"only {len(cells)} claim cells recounted; the table reader is wrong"


def test_every_claim_cell_has_one_ledger_line(page, ledger):
    assert ledger_entries(ledger), "the ledger has no body rows; the line reader is wrong"
    assert ledger_problems(page, ledger) == []


def test_the_summary_counts_agree_with_the_lines(page, ledger):
    assert SUMMARY.findall(ledger), "the ledger has no summary lines"
    assert summary_problems(page, ledger) == []


def test_a_dropped_or_repeated_line_is_reported(page, ledger):
    assert ledger_problems(page, ledger) == []
    lines = ledger.splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if _body_cells(line))
    dropped = "".join(lines[:index] + lines[index + 1:])
    assert any(p.startswith("no ledger line for") for p in ledger_problems(page, dropped)), (
        "a dropped ledger line went unnoticed")
    repeated = "".join(lines + [lines[index]])
    assert any("ledger lines for" in p for p in ledger_problems(page, repeated)), (
        "a repeated ledger line went unnoticed")
