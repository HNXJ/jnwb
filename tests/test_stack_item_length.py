"""Every `###` item of the todo stack holds at most eight lines.

`artifacts/todo_stack.md` states the limit in its "How this stack is executed" section: an item
holds one defect and one check, in at most eight lines. A line is counted from the item's heading
to its last non-blank line, both included, and the count stops at the next section heading. Items
are found by the sweep the stack gate uses, so this test and the gate read one item boundary.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # never insert(0): pyproject sets pythonpath = ["."]

from scripts.harness_gate import _stack_items  # noqa: E402

TODO_STACK = ROOT / "artifacts" / "todo_stack.md"
LIMIT = 8
_SECTION_HEADING = re.compile(r"#{1,2} ")


def item_length(item_text):
    """Lines from the heading to the last non-blank line, both included."""
    kept = [item_text.splitlines()[0]]
    for line in item_text.splitlines()[1:]:
        if _SECTION_HEADING.match(line):
            break
        kept.append(line)
    return max(index for index, line in enumerate(kept) if line.strip()) + 1


def over_limit(text):
    return [
        (item_id, item_length(body))
        for _lineno, item_id, body in _stack_items(text)
        if item_length(body) > LIMIT
    ]


class TestAnItemHoldsAtMostEightLines:
    def test_every_live_item_holds_at_most_eight_lines(self):
        text = TODO_STACK.read_text(encoding="utf-8")
        assert _stack_items(text), "the sweep found no item, which reads exactly like a clean stack"
        offenders = over_limit(text)
        assert not offenders, "items over 8 lines: " + ", ".join(
            f"{item_id} ({lines} lines)" for item_id, lines in offenders
        )

    def test_a_planted_nine_line_item_is_reported_by_its_id(self):
        planted = "### 06-01 Eight\n" + "x\n" * 7 + "\n### 06-02 Nine\n" + "x\n" * 8 + "\n"
        assert item_length(_stack_items(planted)[0][2]) == 8, "fixture must build an eight-line item"
        assert over_limit(planted) == [("06-02", 9)]
