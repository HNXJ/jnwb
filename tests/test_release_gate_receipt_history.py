"""The receipt's history read follows the move to artifacts/process/.

The closure receipt was committed at its old path, and the commit that recorded its finished row
deleted that item from the todo stack. Moving the file must not hide that commit from the gate:
a read that starts at the move sees only the move, so the recording commit is never checked.
"""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.release_gate import _finished_row_history  # noqa: E402
from tests.test_release_requires_an_empty_problem_stack import (  # noqa: E402
    DEFERRED, _RECEIPT, _commit, _git, _item, _repository)

OLD = "artifacts/blocker_fixpoint_receipt.md"
NEW = "artifacts/process/blocker_fixpoint_receipt.md"


def test_the_recording_commit_before_the_move_is_read(tmp_path):
    root, passed = _repository(tmp_path)
    (root / OLD).write_text(_RECEIPT.format(commit=passed, found=0)
                            + "| finished after the pass | 99-921 |\n", encoding="utf-8")
    todo = root / "artifacts" / "todo_stack.md"
    todo.write_text(todo.read_text(encoding="utf-8").replace(_item("99-921", DEFERRED), ""),
                    encoding="utf-8")
    _commit(root, "record the closure pass and delete 99-921")
    (root / "artifacts" / "process").mkdir(parents=True)
    _git(root, "mv", OLD, NEW)
    head = _commit(root, "move the receipt to artifacts/process/")
    assert _finished_row_history(root, passed, head, {"99-921"}, {"99-921"}) == []
