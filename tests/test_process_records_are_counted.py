"""Two hand-kept records, checked by recount instead of by reading.

The defect-class ledger's `Seen` is a count of its `Instances` cell, and a ruling a file cites by
date is recorded under that date. Both drifted by hand before: a row said 2 and listed its two
instances as one, and a citation named a ruling its dated file lacked.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "artifacts" / "process" / "defect_classes.md"
RULINGS = ROOT / "artifacts" / "rulings"
#: Receipts are dated and frozen; they cite what was true when written.
FROZEN = ("artifacts/evidence/", "artifacts/archive/", "artifacts/benchmarks/")
CITATION = re.compile(r"\b[Rr]uled (?:on )?(20\d\d-\d\d-\d\d)")


def _ledger_mismatches(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not cells[1].isdigit():
            continue
        instances = [p for p in re.split(r";\s*", cells[2]) if p]
        if int(cells[1]) != len(instances):
            out.append(f"{cells[0].split(':')[0]}: Seen {cells[1]}, {len(instances)} instances")
    return out


def _uncited_dates(files: dict[str, str], dated: set[str], history: str) -> list[str]:
    """A cited date with no dated file, unless it predates the dated files and history holds it."""
    first = min(dated)
    out = []
    for name, text in files.items():
        for date in sorted(set(CITATION.findall(text))):
            if date in dated or (date < first and date in history):
                continue
            out.append(f"{name} cites a ruling of {date}, recorded nowhere under artifacts/rulings/")
    return out


def test_the_defect_ledger_counts_its_instances():
    rows = _ledger_mismatches(LEDGER.read_text(encoding="utf-8"))
    assert not rows, f"Seen differs from the instances listed (separate instances with ';'): {rows}"


def test_the_ledger_recount_sees_the_drift_it_was_written_for():
    old = ("| rewrite-drops-obligation: x | 2 | 08-06 D1 \"before its first write\", D2 \"before "
           "and after a change\" (2026-09-29) | verifier | restored | open |")
    assert _ledger_mismatches(old) == ["rewrite-drops-obligation: Seen 2, 1 instances"]
    assert _ledger_mismatches("| a: x | 2 | one; two | v | r | s |") == []


def test_every_cited_ruling_date_is_recorded():
    dated = {p.stem for p in RULINGS.glob("20*.md")}
    assert len(dated) > 10, f"only {len(dated)} dated rulings files found"
    history = (RULINGS / "history.md").read_text(encoding="utf-8")
    files = {
        p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "artifacts").rglob("*.md"))
        if not p.relative_to(ROOT).as_posix().startswith(FROZEN)
    }
    assert any(CITATION.search(t) for t in files.values()), "no citation found; the pattern is wrong"
    missing = _uncited_dates(files, dated, history)
    assert not missing, "\n".join(missing)


def test_the_citation_check_refuses_an_unrecorded_date():
    dated = {"2026-09-22", "2026-10-17"}
    assert _uncited_dates({"a.md": "Ruled 2026-10-16."}, dated, "") == [
        "a.md cites a ruling of 2026-10-16, recorded nowhere under artifacts/rulings/"]
    assert _uncited_dates({"a.md": "ruled 2026-09-19"}, dated, "2026-09-19") == []
    assert _uncited_dates({"a.md": "ruled 2026-09-19"}, dated, "") != []
    assert _uncited_dates({"a.md": "Ruled 2026-10-17"}, dated, "") == []
