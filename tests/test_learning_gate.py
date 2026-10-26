"""The process records the harness checks: the defect-class ledger, the dates files cite, and the
generated rows of the state file.

Each check is shown red on a planted case built from the instance it names and green on the live
tree. A check that reads nothing must not pass, so the examined set is asserted non-empty.
"""

from __future__ import annotations

import pathlib
import subprocess
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
def test_the_live_generated_rows_are_in_the_generated_state(monkeypatch):
    import urllib.error
    import urllib.request

    from scripts import reconstruct_state

    rows = lg.generated_rows()
    assert len(rows) >= 3, f"too few generated rows read: {rows}"

    def unreachable(request, timeout=None):
        raise urllib.error.URLError("tests do not reach the network")

    monkeypatch.setattr(urllib.request, "urlopen", unreachable)
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


def _need_commit(rev: str) -> None:
    """Skip where a shallow clone (CI's checkout) lacks the commit the test replays."""
    if subprocess.run(["git", "-C", str(REPO_ROOT), "cat-file", "-e", f"{rev}^{{commit}}"],
                      capture_output=True).returncode:
        pytest.skip(f"commit {rev} is not in this clone's history")


def _git_text(rev: str, path: str) -> str:
    done = subprocess.run(["git", "-C", str(REPO_ROOT), "show", f"{rev}:{path}"],
                          capture_output=True, check=True)
    return done.stdout.decode("utf-8")


MAPPING_PATH = "artifacts/evidence/0.2.9/mapping.md"
DRAFT_PATH = "artifacts/evidence/0.2.9/draft.md"
OLD_RULES = "## 1. Loop\n\nRun the check before its first write.\n"
MAPPING_TABLE = (
    "# Mapping\n\n"
    "Old file: `AGENTS.md` at `aaaaaaa` (3 words by `wc -w`). Draft:\n"
    f"`{DRAFT_PATH}`.\n\n"
    "| # | Old location | Rule or statement (condensed) | Disposition | Where now |\n"
    "|---|---|---|---|---|\n"
    "| 1 | §1 | Run the check | rule | draft §1 |\n"
)


def _mapping_tree(tmp_path: pathlib.Path, draft: str) -> pathlib.Path:
    return _tree(tmp_path, {MAPPING_PATH: MAPPING_TABLE, DRAFT_PATH: draft})


def test_a_draft_that_drops_an_obligation_word_is_red(tmp_path):
    root = _mapping_tree(tmp_path, "## 1. Loop\n\nRun the check first.\n")
    tables, clauses, found = lg.mapping_check(root, read_old=lambda rev, path: OLD_RULES)
    assert (tables, clauses) == (1, 1), (tables, clauses)
    assert len(found) == 1 and "before its first write" in found[0], found


def test_a_draft_that_keeps_the_obligation_words_is_green(tmp_path):
    root = _mapping_tree(tmp_path, OLD_RULES)
    assert lg.mapping_check(root, read_old=lambda rev, path: OLD_RULES) == (1, 1, [])


def test_an_old_file_that_cannot_be_read_is_red_not_passed(tmp_path):
    root = _mapping_tree(tmp_path, OLD_RULES)
    found = lg.mapping_check(root, read_old=lambda rev, path: None)[2]
    assert found and "cannot be read" in found[0], found


def test_a_mapping_table_that_names_no_draft_is_red_not_passed(tmp_path):
    root = _tree(tmp_path, {MAPPING_PATH: MAPPING_TABLE.replace("Draft:", "Draft unnamed:")})
    found = lg.mapping_check(root, read_old=lambda rev, path: OLD_RULES)[2]
    assert found and "names no draft" in found[0], found


def test_a_tree_with_no_mapping_table_examines_none_and_says_so(tmp_path):
    root = _tree(tmp_path, {"artifacts/a.md": "No table here.\n"})
    assert lg.mapping_check(root, read_old=lambda rev, path: "") == (0, 0, [])


@pytest.mark.requires_git_checkout
def test_the_mapping_table_of_commit_8482c7bc_is_red_for_the_two_clauses_it_dropped(tmp_path):
    table = "artifacts/evidence/0.2.8/agents_md_mapping.md"
    draft = "artifacts/evidence/0.2.8/agents_md_draft.md"
    _need_commit("8482c7bc")
    root = _tree(tmp_path, {table: _git_text("8482c7bc", table),
                            draft: _git_text("8482c7bc", draft)})
    tables, clauses, found = lg.mapping_check(root)
    assert tables == 1 and clauses > 0, (tables, clauses)
    assert any("before its first write" in v for v in found), found
    assert any("before and after a change" in v for v in found), found


def test_a_row_that_names_a_forbidden_phrase_yields_it():
    row = '| Pooling | "never pooled" | rule | Forbidden: "pool across them without namespacing" |'
    assert lg.forbidden_in(row) == ["pool across them without namespacing"]
    assert lg.forbidden_in("| Pooling | rule |") == []


@pytest.mark.requires_git_checkout
def test_a_pooling_phrase_named_by_a_row_is_red_on_commit_b0119d07():
    _need_commit("b0119d07")
    phrase = lg.forbidden_in('Forbidden: "pool across them without namespacing"')[0]
    found = lg.forbidden_violations([("artifacts/rulings/fixture.md", phrase)], rev="b0119d07")
    assert any(v.startswith("b0119d07:AGENTS.md:") for v in found), found


def test_a_forbidden_phrase_in_a_tracked_file_is_red_and_an_archived_one_is_not(tmp_path):
    phrase = "pool across them without namespacing"
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    _tree(tmp_path, {"docs/page.md": f"Do {phrase}.\n",
                     "artifacts/archive/0.2.5/old.md": f"{phrase}\n"})
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    found = lg.forbidden_violations([("artifacts/rulings/fixture.md", phrase)], root=tmp_path)
    assert len(found) == 1 and found[0].startswith("docs/page.md:"), found


@pytest.mark.requires_git_checkout
def test_the_live_tree_holds_no_forbidden_phrase_and_no_mapping_drop():
    assert lg.forbidden_violations(lg.forbidden_sources(REPO_ROOT)) == []
    assert lg.mapping_check(REPO_ROOT)[2] == []


def test_gate_15_pass_line_names_what_it_examined(monkeypatch):
    from scripts import harness_gate

    monkeypatch.setattr(harness_gate, "examined_counts", lambda: (3, 41, 2))
    line = harness_gate._stack_and_record_pass_line()
    assert line.startswith("PASS:") and "3 mapping tables" in line, line
    assert "2 forbidden phrases" in line, line


@pytest.mark.requires_git_checkout
def test_the_newest_dev_run_row_is_named_but_not_compared_by_gate_20(tmp_path):
    rows = lg.generated_rows()
    assert rows and not any("Newest CI run" in row for row in rows), rows
    for ci_value in ("unknown", "RED: `" + "a" * 12 + "` failure"):
        state = "\n".join(rows) + f"\n| Newest CI run on `dev` | {ci_value} |\n"
        assert lg.awareness_violations(_tree(tmp_path, {"artifacts/state.md": state})) == []
