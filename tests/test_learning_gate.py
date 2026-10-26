"""The process records the harness checks: the defect-class ledger, the dates files cite, and the
generated rows of the state file.

Each check is shown red on a planted case built from the instance it names and green on the live
tree. A check that reads nothing must not pass, so the examined set is asserted non-empty.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts import learning_gate as lg  # noqa: E402

# The row as it stood before the recount landed (314d7329^): two instances joined by a comma.
LEDGER_ROW_BEFORE_RECOUNT = (
    "| rewrite-drops-obligation: a rewrite of a rule file loses a rule or its timing, and the "
    "mapping calls it kept | 2 | 08-06 D1 \"before its first write\", D2 \"before and after a "
    "change\" (2026-09-29) | verifier, old-against-new reading | restored | gate proposed: 09-07 |"
)
LEDGER_HEADER = (
    "| Class | Seen | Instances | Caught by | Repair | Status |\n"
    "|---|---|---|---|---|---|\n"
)


def _tree(tmp_path: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def test_a_ledger_row_whose_seen_count_differs_from_its_instances_is_red(tmp_path):
    root = _tree(tmp_path, {"artifacts/process/defect_classes.md":
                            LEDGER_HEADER + LEDGER_ROW_BEFORE_RECOUNT + "\n"})
    assert lg.ledger_violations(root) == [
        "rewrite-drops-obligation: Seen 2, 1 instances (separate instances with ';')"]


def test_a_ledger_row_that_separates_its_instances_with_semicolons_is_green(tmp_path):
    row = LEDGER_ROW_BEFORE_RECOUNT.replace('", D2', '"; D2')
    root = _tree(tmp_path, {"artifacts/process/defect_classes.md": LEDGER_HEADER + row + "\n"})
    assert lg.ledger_rows(row) == [("rewrite-drops-obligation", 2, 2)]
    assert lg.ledger_violations(root) == []


def test_a_ledger_with_no_counted_rows_is_reported_not_passed(tmp_path):
    root = _tree(tmp_path, {"artifacts/process/defect_classes.md": LEDGER_HEADER})
    assert lg.ledger_violations(root) != []


def test_a_missing_ledger_is_reported_not_passed(tmp_path):
    assert lg.ledger_violations(tmp_path) != []


def test_a_citation_of_a_date_no_dated_file_records_is_red(tmp_path):
    """The shape of the 8482c7bc instance: a file cites a 2026-09-17 date that nothing records."""
    root = _tree(tmp_path, {
        "artifacts/rulings/2026-09-22.md": "# 2026-09-22\n",
        "artifacts/rulings/history.md": "# History\n",
        "artifacts/planned_post.md": (
            "The hypothesis ruled 2026-09-17 (`artifacts/archive/0.2.5/planned_post.md`, P0).\n"),
    })
    assert lg.citation_violations(root) == [
        "artifacts/planned_post.md cites 2026-09-17, which no dated file under "
        "artifacts/rulings/ records"]


def test_a_citation_of_a_recorded_date_or_a_history_date_is_green(tmp_path):
    root = _tree(tmp_path, {
        "artifacts/rulings/2026-09-22.md": "# 2026-09-22\n",
        "artifacts/rulings/history.md": "### Earlier record, ruled 2026-09-19\n",
        "artifacts/a.md": "Ruled 2026-09-22 and ruled 2026-09-19 (before the dated files).\n",
        # A frozen receipt is not read, so its citation of an unrecorded date is not a finding.
        "artifacts/archive/0.2.5/receipt.md": "Ruled 2026-09-17 in the archive.\n",
    })
    assert lg.citations(root) == [
        ("artifacts/a.md", "2026-09-19"),
        ("artifacts/a.md", "2026-09-22"),
        ("artifacts/rulings/history.md", "2026-09-19"),
    ]
    assert lg.citation_violations(root) == []


def test_a_tree_with_no_citation_is_reported_not_passed(tmp_path):
    root = _tree(tmp_path, {
        "artifacts/rulings/2026-09-22.md": "# 2026-09-22\n",
        "artifacts/a.md": "No dated decision here.\n",
    })
    assert lg.citation_violations(root) != []


@pytest.mark.requires_git_checkout
def test_the_live_ledger_recounts_green_and_reads_rows():
    assert lg.ledger_rows((REPO_ROOT / lg.LEDGER).read_text(encoding="utf-8"))
    assert lg.ledger_violations(REPO_ROOT) == []


@pytest.mark.requires_git_checkout
def test_every_live_citation_is_recorded_and_some_are_read():
    assert lg.citations(REPO_ROOT), "no citation read on the live tree"
    assert lg.citation_violations(REPO_ROOT) == []


def test_a_generated_row_missing_from_the_state_text_is_named():
    text = "| a | b |\n| c | d |\n"
    found = lg.unnamed_rows(text, ["| a | b |", "| e | f |"])
    assert len(found) == 1 and "| e | f |" in found[0], found


def test_an_absent_state_file_passes_as_gate_20_passes_it(tmp_path):
    assert lg.awareness_violations(tmp_path) == []


@pytest.mark.requires_git_checkout
def test_the_live_generated_rows_are_in_the_generated_state():
    from scripts import reconstruct_state

    rows = lg.generated_rows()
    assert len(rows) >= 3, f"too few generated rows read: {rows}"
    assert lg.unnamed_rows(reconstruct_state.build(), rows) == []


def test_gate_15_runs_the_ledger_and_citation_checks(monkeypatch):
    from scripts import harness_gate

    monkeypatch.setattr(harness_gate, "ledger_violations", lambda: ["SEEDED ledger row"])
    found = harness_gate._stack_and_record_checks()
    assert any("SEEDED ledger row" in v for _, violations in found for v in violations)


def test_gate_20_runs_the_state_row_check(monkeypatch):
    from scripts import harness_gate

    monkeypatch.setattr(harness_gate, "awareness_violations", lambda: ["SEEDED state row"])
    found = harness_gate._state_file_checks()
    assert any("SEEDED state row" in v for _, violations in found for v in violations)
