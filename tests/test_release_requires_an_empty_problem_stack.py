"""Condition 3 of ``AGENTS.md`` section 11, as amended 2026-09-23, as a check that can fail.

The problem stack holds only problems not yet triaged, and a release requires:

  1. the problem stack exists and holds no problem row, in any section;
  2. no todo item is still required for this cycle, and every item's release is readable;
  3. the independent blocker-focused closure receipt exists, is at HEAD, and reports zero.

Every test drives the check over a constructed tree and is measured against
``test_a_compliant_tree_passes``: the compliant tree passes, and breaking exactly one thing fails.
A test that only asserted the live tree reports violations would pass against a function that
always returns one.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# `scripts/` is excluded from the wheel, and the leg that qualifies the built artifact runs this
# suite from outside the checkout, so nothing puts the repository on `sys.path` there. A
# module-scope `from scripts...` raises ModuleNotFoundError -- a collection *error*, which pytest
# reports as `Interrupted` and which can take unrelated modules down with it.
# `append`, never `insert(0, ...)`: inserting re-shadows the installed package for the whole
# session, which tests/test_the_suite_can_qualify_an_installed_copy.py forbids.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.release_gate import (  # noqa: E402
    NEXT_CYCLE,
    blocker_fixpoint_receipt,
    check_release_readiness,
    problem_rows,
    todo_release_fields,
)
HEAD = "a" * 40
DEFERRED = f"deferred-{NEXT_CYCLE}"

_PROBLEMS = """# Problem stack

## Open

| ID | Problem | Found by |
|---|---|---|
{rows}
"""

_TODOS = """# {cycle}

Items are deleted when done.

{items}
## Acceptance
"""

_RECEIPT = """# Blocker fixpoint receipt

| field | value |
|---|---|
| commit | `{commit}` |
| new release-blocking problems found | {found} |
"""


def _tree(tmp_path, *, rows=(), tail="", items=(), commit=HEAD, found=0, receipt=True):
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "problem_stack.md").write_text(
        _PROBLEMS.format(rows="\n".join(rows)) + tail, encoding="utf-8")
    (tmp_path / "artifacts" / "todo_stack.md").write_text(
        _TODOS.format(cycle=NEXT_CYCLE, items="\n".join(items)), encoding="utf-8")
    if receipt:
        (tmp_path / "artifacts" / "blocker_fixpoint_receipt.md").write_text(
            _RECEIPT.format(commit=commit, found=found), encoding="utf-8")
    return tmp_path


def _item(ident, release):
    return (f"### {ident} Something\n\nRole: jnwb-developer. Skill: none. Blocked by: none.\n"
            f"Release: {release}.\nWrites: `jnwb/x.py`.\n")


# --- the compliant tree, which every discriminator below is measured against ------------------

def test_a_compliant_tree_passes(tmp_path):
    """An empty problem table, only deferred items and a receipt at HEAD."""
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED), _item("07-02", DEFERRED)])
    assert problem_rows(root) == []
    assert check_release_readiness(root, head=HEAD) == []


# --- 1. the problem stack is empty -------------------------------------------------------------

@pytest.mark.parametrize("rows, tail", [
    (["| P-01 | a defect | a packet |"], ""),
    (["| P-01 | a defect | a packet | DEFERRED->0.2.7 | carried, with a reason |"], ""),
    (["| P-01 | a defect | a packet | ACCEPTED | cannot be retested |"], ""),
    (["| P-01 | a malformed row with one cell"], ""),
    (["|P-01|no spaces|x|"], ""),
    ([], "\n## Closed\n\n| ID | Problem | Disposition |\n|---|---|---|\n| P-C1 | done | repaired |\n"),
    ([], "\n  | P-01 | indented under prose, outside any table heading | x |\n"),
], ids=["plain", "deferred", "accepted", "malformed", "unspaced", "closed-section", "indented"])
def test_any_problem_row_fails_whatever_it_says_or_wherever_it_sits(tmp_path, rows, tail):
    root = _tree(tmp_path, rows=rows, tail=tail, items=[_item("07-01", DEFERRED)])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and v[0].startswith("1 problem row(s) remain"), v


#: Problems written in a form a row-shaped pattern does not read. Under `## Open` any line but
#: the header and separator is untriaged work, whatever its shape.
EVASIONS = {
    "bold-id": "| **P-300** | a defect | x |",
    "code-id": "| `P-300` | a defect | x |",
    "lowercase-id": "| p-300 | a defect | x |",
    "blockquoted-table": "> | ID | Problem | Found by |\n> |---|---|---|\n> | P-300 | a defect | x |",
    "bullet": "- P-300: a defect",
    "id-in-column-2": "| x | P-300 | a defect |",
    "unnumbered-row": "| | a defect | x |",
    "prose": "A defect nobody has triaged yet.",
    "second-header": "| ID | Problem | Found by |\n|---|---|---|",
}


@pytest.mark.parametrize("line", list(EVASIONS.values()), ids=list(EVASIONS))
def test_any_content_under_open_fails_step_0a(tmp_path, line):
    root = _tree(tmp_path, rows=[line], items=[_item("07-01", DEFERRED)])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "problem row(s) remain" in v[0], v


def _open_findings(root):
    from scripts.harness_gate import check_stack_form_consistency
    return [v for v in check_stack_form_consistency(root) if "## Open" in v]


@pytest.mark.parametrize("line", list(EVASIONS.values()), ids=list(EVASIONS))
def test_any_noncanonical_content_under_open_fails_gate_15(tmp_path, line):
    root = _tree(tmp_path, rows=[line], items=[_item("07-01", DEFERRED)])
    assert _open_findings(root), f"gate 15 read {line!r} under ## Open as well formed"


def test_gate_15_passes_an_empty_open_section_and_a_canonical_row(tmp_path):
    """Gate 15 checks form; a recorded, well-formed problem is STEP 0a's to refuse, not its."""
    assert _open_findings(_tree(tmp_path, items=[_item("07-01", DEFERRED)])) == []
    assert _open_findings(_tree(tmp_path, rows=["| P-300 | a defect | x |"])) == []


def test_a_problem_stack_with_no_open_section_fails_both(tmp_path):
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)])
    stack = root / "artifacts" / "problem_stack.md"
    stack.write_text(stack.read_text(encoding="utf-8").replace("## Open", "## Triage"),
                     encoding="utf-8")
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "## Open" in v[0], v
    assert _open_findings(root), "gate 15 passed a problem stack with no ## Open section"


def test_a_missing_problem_stack_fails(tmp_path):
    """A condition satisfied by deleting its own evidence is worse than none."""
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)])
    (root / "artifacts" / "problem_stack.md").unlink()
    assert problem_rows(root) is None
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "problem_stack.md is missing" in v[0], v


# --- 2. no required item remains ---------------------------------------------------------------

def test_an_item_still_required_this_cycle_fails(tmp_path):
    root = _tree(tmp_path, items=[_item("06-99", "required-0.2.6")])
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "06-99" in x for x in v)


def test_an_item_with_no_release_field_fails(tmp_path):
    root = _tree(tmp_path, items=["### 06-98 Something\n\nRole: jnwb-developer.\n"])
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "06-98" in x for x in v), \
        "an item with no Release: field read as deferred rather than as unclassified"


@pytest.mark.parametrize("ident", ["06-01", "06-99", "06-100", "06-113", "07-5"])
def test_an_item_id_of_any_digit_width_is_counted(tmp_path, ident):
    """A two-digit pattern once made every three-digit item invisible to this check."""
    root = _tree(tmp_path, items=[_item(ident, "required-0.2.6")])
    assert [i for i, _, _ in todo_release_fields(root)] == [ident]
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and ident in x for x in v), \
        f"item {ident} was invisible to the release check"


def _nested(depth, parent_release="Release: deferred-0.2.7.\n", child_release="required-0.2.6"):
    return (f"### 99-900 A parent\n\n{parent_release}\n"
            f"{depth} 99-901 A nested item\n\nRelease: {child_release}.\n")


@pytest.mark.parametrize("depth", ["##", "###", "####", "#####", "######"])
def test_a_required_item_is_seen_at_any_heading_depth(tmp_path, depth):
    """Only `### ` was read, so an item one level deeper was invisible and its `Release:` field
    was read as its parent's, which kept the parent deferred and the release check clean."""
    root = _tree(tmp_path, items=[_nested(depth)])
    fields = {i: r for i, _, r in todo_release_fields(root)}
    assert fields == {"99-900": DEFERRED, "99-901": "required-0.2.6"}
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "99-901" in x for x in v), v


def test_a_parent_does_not_inherit_a_nested_items_release_field(tmp_path):
    root = _tree(tmp_path, items=[_nested("####", parent_release="", child_release=DEFERRED)])
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "99-900" in x for x in v), v


def test_an_item_stating_two_release_values_is_required(tmp_path):
    root = _tree(tmp_path, items=[_item("99-901", DEFERRED) + "Release: required-0.2.6.\n"])
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "99-901" in x for x in v), v


@pytest.mark.parametrize("second", [
    "**Release:** required-0.2.6.",
    "  Release: required-0.2.6.",
    "release: required-0.2.6.",
    "1. Release: required-0.2.6.",
    "| Scope | Release: required-0.2.6. |",
    "<b>Release:</b> required-0.2.6.",
])
def test_a_deferred_item_with_a_noncanonical_second_release_line_fails_closed(tmp_path, second):
    """Only the canonical line was read, so a second value in any other form went unseen."""
    root = _tree(tmp_path, items=[_item("99-901", DEFERRED) + second + "\n"])
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "99-901" in x for x in v), v
    assert any("cannot be read" in x and "99-901" in x for x in v), v


@pytest.mark.parametrize("hidden", [
    "> ### 99-902 A quoted item\n>\n> Release: required-0.2.6.\n",
    "- ### 99-902 A listed item\n\n  Release: required-0.2.6.\n",
    "99-902 A setext item with no field\n===\n\nBody text.\n",
    "99-902 A setext item with no field\n---\n\nBody text.\n",
    "<h3>99-902 An HTML item with no field</h3>\n\nBody text.\n",
])
def test_a_contained_heading_after_a_deferred_item_is_read_as_an_item(tmp_path, hidden):
    """A heading in a blockquote or list item was body text of the deferred item above it."""
    root = _tree(tmp_path, items=[_item("99-901", DEFERRED) + "\n" + hidden])
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "99-902" in x for x in v), v
    assert not any("99-901" in x for x in v), v


def test_a_release_field_before_the_first_heading_fails_closed(tmp_path):
    root = _tree(tmp_path, items=[_item("99-901", DEFERRED)])
    todo = root / "artifacts" / "todo_stack.md"
    todo.write_text("Release: required-0.2.6.\n\n" + todo.read_text(encoding="utf-8"),
                    encoding="utf-8")
    v = check_release_readiness(root, head=HEAD)
    assert any("before the first heading" in x for x in v), v


@pytest.mark.parametrize("heading", [
    "### 99-901: A colon after the id",
    "#### 9-901 One digit before the hyphen",
    "### **99-901** A bold id",
    "##### 99-901a A suffixed id",
    "#### A heading with no id",
])
def test_an_item_whose_id_cannot_be_read_fails_closed(tmp_path, heading):
    """A section STEP 0a cannot identify is reported, never skipped as prose."""
    root = _tree(tmp_path, items=[f"{heading}\n\nRelease: required-0.2.6.\n"])
    v = check_release_readiness(root, head=HEAD)
    assert any("cannot be read" in x and heading.lstrip("# ")[:20] in x for x in v), v


@pytest.mark.parametrize("heading", ["### 99-901: A colon", "#### 99-901a A suffix"])
def test_an_item_shaped_heading_fails_closed_without_a_release_field(tmp_path, heading):
    """A readable id with no field reads as required; an unreadable one must not read as prose."""
    root = _tree(tmp_path, items=[f"{heading}\n\nRole: jnwb-developer.\n"])
    v = check_release_readiness(root, head=HEAD)
    assert any("cannot be read" in x and heading.lstrip("# ") in x for x in v), v


def test_headings_that_are_not_items_add_no_violation(tmp_path):
    root = _tree(tmp_path, items=[
        "## W9-W10. A group heading\n",
        "### 2026-09-23 A dated note\n\nNo field here.\n",
        _item("07-01", DEFERRED) + "\n#### Notes\n\nProse only.\n",
    ])
    assert check_release_readiness(root, head=HEAD) == []


# --- 3. the closure receipt --------------------------------------------------------------------

def test_a_missing_receipt_fails(tmp_path):
    root = _tree(tmp_path, receipt=False)
    v = check_release_readiness(root, head=HEAD)
    assert v and all("blocker_fixpoint_receipt" in x for x in v), v


def test_a_receipt_from_a_different_commit_fails(tmp_path):
    """A closure pass that ran against other bytes is not evidence about these bytes."""
    root = _tree(tmp_path, commit="b" * 40)
    v = check_release_readiness(root, head=HEAD)
    assert any("did not run against the tree being released" in x for x in v)


def test_a_receipt_reporting_new_blockers_fails(tmp_path):
    root = _tree(tmp_path, found=2)
    v = check_release_readiness(root, head=HEAD)
    assert any("found 2 new release-blocking" in x for x in v)


def test_the_fixpoint_is_new_blockers_and_not_new_observations(tmp_path):
    """A closure pass that files fifty deferred observations and zero blockers still closes."""
    root = _tree(tmp_path, items=[_item(f"07-{n}", DEFERRED) for n in range(1, 51)], found=0)
    assert check_release_readiness(root, head=HEAD) == []


def test_the_receipt_parser_reads_nothing_from_an_absent_receipt():
    commit, found = blocker_fixpoint_receipt(pathlib.Path("/nonexistent-tree"))
    assert commit is None and found is None


# --- the live tree -----------------------------------------------------------------------------

def test_the_live_problem_stack_has_no_problem_row():
    """Every finding is repaired, shown false, or moved into the todo stack."""
    assert problem_rows(REPO_ROOT) == []


def test_the_live_item_count_agrees_between_both_parsers():
    """Both readers share one parser, so the raw count of id-led headings at any depth is the
    independent side; the live stack must also hold no section that looks like an item but
    cannot be read, and must parse to at least one item."""
    from scripts.release_gate import remaining_todo_items, unparseable_todo_headings
    text = (REPO_ROOT / "artifacts" / "todo_stack.md").read_text(encoding="utf-8")
    raw = re.findall(r"^ {0,3}#+[ \t]+\d\d-\d+(?:[ \t]|$)", text, re.M)
    assert len(raw) > 0, "the todo stack parsed to zero items"
    assert len(remaining_todo_items(REPO_ROOT)) == len(todo_release_fields(REPO_ROOT)) == len(raw)
    assert unparseable_todo_headings(REPO_ROOT) == []
