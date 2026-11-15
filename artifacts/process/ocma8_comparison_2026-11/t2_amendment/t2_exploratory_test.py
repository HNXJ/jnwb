"""EXPLORATORY: two compatibility findings for rows without a leading pipe, which baseline reads as rows.

The tracked input holds no such row, so a stricter unified parser is allowed; either result is reported as is.
Run: cwd = tree under test; python -m pytest <abs path to this file> -q -p no:cacheprovider --basetemp=<dir outside the tree>
"""
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import learning_gate  # noqa: E402
import reconstruct_state  # noqa: E402

LEDGER_HEAD = "| Class | Seen | Instances |\n|---|---|---|\n"
DEFECT_HEAD = "| Class | Seen | a | b | c | Status |\n|---|---|---|---|---|---|\n"


def _write(tmp_path, text, name="fixture.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _defect_file(tmp_path, *rows):
    return _write(tmp_path, DEFECT_HEAD + "".join(row + "\n" for row in rows), "defect_classes.md")


# learning_gate: the defect-ledger reader.
def test_ledger_row_without_leading_pipe_is_read_as_baseline_does():
    assert learning_gate.ledger_rows(LEDGER_HEAD + "cls:delta | 1 | a\n") == [("cls", 1, 1)]


# reconstruct_state: the defect-class ledger.
def test_defect_row_without_leading_pipe_is_read_as_baseline_does(tmp_path):
    path = _defect_file(tmp_path, "delta:R4 | 2 | a | b | c | open")
    assert reconstruct_state.open_defect_classes(path) == "delta (seen 2)"
