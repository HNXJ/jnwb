"""`scripts/obligation_diff.py` lists the obligations a rule-file rewrite drops or loosens.

The fixtures are the two rewrites that review caught by reading old against new: a lane check
that lost "before its first write", and a suite row that lost "before and after a change".
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# `scripts` exists only in a checkout; appended, never inserted, so the package under test
# stays whichever installation the session selected.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts.obligation_diff import clauses, compare, main  # noqa: E402

OLD = """# Rules

| `tests/` | The suite; run it before and after a change (§6) |

A lane confirms it is not in the main checkout **before its first write**: `verify_lane.py`
refuses the main tree unless `--allow-main-tree` names the caller.

Never push to `main` without a ruling.
"""


def _kinds(old: str, new: str) -> dict[str, str]:
    return {clause: kind for kind, clause, _ in compare(old, new)}


def test_a_rewrite_that_keeps_every_clause_lists_nothing():
    moved = "\n".join(reversed(OLD.splitlines()))
    assert clauses(OLD), "the fixture must hold clauses"
    assert compare(OLD, OLD) == []
    assert compare(OLD, moved) == []


def test_a_lost_timing_word_is_listed_as_timing_lost():
    new = OLD.replace("**before its first write**: ", "")
    kinds = _kinds(OLD, new)
    lost = [c for c, k in kinds.items() if k == "timing lost"]
    assert lost and all("first write" in c for c in lost), kinds


def test_a_dropped_row_is_listed_as_dropped():
    new = OLD.replace("| `tests/` | The suite; run it before and after a change (§6) |", "")
    kinds = _kinds(OLD, new)
    assert kinds.get("run it before and after a change (§6)") == "dropped", kinds


def test_a_reworded_clause_that_keeps_its_timing_is_listed_but_does_not_block():
    new = OLD.replace("Never push to `main` without a ruling.",
                      "Never push to `main` without a dated ruling.")
    assert _kinds(OLD, new) == {"never push to main without a ruling": "reworded"}


def test_the_command_fails_on_a_base_it_cannot_read(capsys):
    assert main(["--base", "0" * 40, "AGENTS.md"]) == 1
    assert "no clauses read" in capsys.readouterr().out
