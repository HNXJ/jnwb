"""Condition 3 of ``AGENTS.md`` section 11, as amended 2026-09-21, as a check that can fail.

The old condition was "both stacks are empty". It was replaced because it could not terminate:
across 29 commits of the 0.2.6 cycle the open-problem count went 29 -> 101 while the item count
stayed flat, since the apparatus that discovers defects is itself the largest source of them. A
criterion that demands the record of discovered truth reach zero rewards not discovering, not
recording, and repairing the machinery that records repairs.

What replaced it is narrower in what it demands and *not* weaker in what it tolerates:

  1. every open problem carries an explicit disposition;
  2. no ``BLOCKER`` remains;
  3. no todo item is still required for this cycle;
  4. every ``DEFERRED`` names a destination and a reason;
  5. no dangling problem <-> todo reference;
  6. the independent blocker-focused closure receipt exists, is at HEAD, and reports zero.

Every test here drives the check over a constructed tree, and every one of the six is shown
**both ways** -- the compliant tree passes, and breaking exactly that one thing fails. A test
that only asserted the live tree reports violations would pass against a function that always
returns one, which is the shape this repository has spent a cycle removing.

The classification semantics and these discriminators land BEFORE any row is classified. That
ordering is the point: a criterion relaxed and then immediately applied to the existing backlog
is backlog laundering, and the process constraint in section 11 forbids it.
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
    DISPOSITIONS,
    NEXT_CYCLE,
    blocker_fixpoint_receipt,
    check_release_readiness,
    open_problem_dispositions,
    todo_release_fields,
)
HEAD = "a" * 40

_PROBLEMS = """# Problem stack

## Open

| ID | Problem | Found by | Disposition | Answered in |
|---|---|---|---|---|
{open_rows}

## Closed

| ID | Problem | Disposition | Evidence |
|---|---|---|---|
| P-C1 | something that was real | `repaired` | a commit |
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

_DEFERRED = f"DEFERRED->{NEXT_CYCLE}"
_GOOD_DEFER_REASON = (
    f"carried to {NEXT_CYCLE}: cosmetic only, changes no shipped behaviour and no evidence"
)


def _tree(tmp_path, *, open_rows=(), items=(), commit=HEAD, found=0, receipt=True):
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "problem_stack.md").write_text(
        _PROBLEMS.format(open_rows="\n".join(open_rows)), encoding="utf-8")
    (tmp_path / "artifacts" / "todo_stack.md").write_text(
        _TODOS.format(cycle=NEXT_CYCLE, items="\n".join(items)), encoding="utf-8")
    if receipt:
        (tmp_path / "artifacts" / "blocker_fixpoint_receipt.md").write_text(
            _RECEIPT.format(commit=commit, found=found), encoding="utf-8")
    return tmp_path


def _row(pid, disposition, answered="nothing further"):
    return f"| {pid} | a thing that is true | a packet | {disposition} | {answered} |"


def _item(ident, release):
    return (f"### {ident} Something\n\nRole: jnwb-developer. Skill: none. Blocked by: none.\n"
            f"Release: {release}.\nWrites: `jnwb/x.py`.\n")


# --- the compliant tree, which every discriminator below is measured against ------------------

def test_a_compliant_tree_passes(tmp_path):
    """The other side of every discriminator. Without this they would all pass vacuously."""
    root = _tree(tmp_path,
                 open_rows=[_row("P-01", _DEFERRED, _GOOD_DEFER_REASON),
                            _row("P-02", "ACCEPTED", "cannot be retested; shipped artifact")],
                 items=[_item("07-01", f"deferred-{NEXT_CYCLE}")])
    assert check_release_readiness(root, head=HEAD) == []


def test_carrying_forward_a_hundred_problems_is_not_a_violation(tmp_path):
    """The whole point of the amendment: the record is preserved, not emptied."""
    rows = [_row(f"P-{n:02d}", _DEFERRED, _GOOD_DEFER_REASON) for n in range(1, 101)]
    root = _tree(tmp_path, open_rows=rows)
    assert check_release_readiness(root, head=HEAD) == []
    assert len(open_problem_dispositions(root)) == 100


# --- 1. explicit disposition -------------------------------------------------------------------

def test_an_unclassified_problem_fails(tmp_path):
    root = _tree(tmp_path, open_rows=[_row("P-01", "UNCLASSIFIED")])
    v = check_release_readiness(root, head=HEAD)
    assert v and "no valid disposition" in v[0] and "P-01" in v[0]


@pytest.mark.parametrize("bogus", ["blocker", "Deferred", "WONTFIX", "", "`BLOCKER`"])
def test_a_disposition_outside_the_declared_set_fails(tmp_path, bogus):
    """Case and backticks included: a near-miss spelling must not read as a valid disposition."""
    root = _tree(tmp_path, open_rows=[_row("P-01", bogus, _GOOD_DEFER_REASON)])
    v = check_release_readiness(root, head=HEAD)
    assert v and "no valid disposition" in v[0]


# --- 2. no blocker remains ---------------------------------------------------------------------

def test_one_blocker_fails(tmp_path):
    root = _tree(tmp_path, open_rows=[_row("P-07", "BLOCKER", "06-01 will fix it")],
                 items=[_item("06-01", f"deferred-{NEXT_CYCLE}")])
    v = check_release_readiness(root, head=HEAD)
    assert any("release-blocking problem(s) remain" in x and "P-07" in x for x in v)


def test_a_blocker_in_a_test_file_blocks_exactly_as_hard_as_one_in_the_package(tmp_path):
    """Path is not a classifier. P-174 is why: a mutant in a test file disabled the check that
    would have caught it, and made four green suite runs mean less than they said."""
    root = _tree(tmp_path, open_rows=[
        "| P-174 | a mutant in `tests/test_docs_links.py` disabled the check | git status "
        "| BLOCKER | 06-113 |"], items=[_item("06-113", f"deferred-{NEXT_CYCLE}")])
    v = check_release_readiness(root, head=HEAD)
    assert any("P-174" in x for x in v)


# --- 3. no required item remains ---------------------------------------------------------------

def test_an_item_still_required_this_cycle_fails(tmp_path):
    root = _tree(tmp_path, items=[_item("06-99", "required-0.2.6")])
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "06-99" in x for x in v)


def test_an_item_with_no_release_field_fails(tmp_path):
    root = _tree(tmp_path)
    (root / "artifacts" / "todo_stack.md").write_text(
        _TODOS.format(cycle=NEXT_CYCLE,
                      items="### 06-98 Something\n\nRole: jnwb-developer.\n"), encoding="utf-8")
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "06-98" in x for x in v), \
        "an item with no Release: field read as deferred rather than as unclassified"


# --- 4. a deferral must say where and why ------------------------------------------------------

def test_a_deferral_with_no_destination_fails(tmp_path):
    root = _tree(tmp_path, open_rows=[_row("P-01", _DEFERRED, "later, probably, somehow ok yes")])
    v = check_release_readiness(root, head=HEAD)
    assert any("destination and reason" in x for x in v)


def test_a_deferral_with_a_destination_but_no_reason_fails(tmp_path):
    root = _tree(tmp_path, open_rows=[_row("P-01", _DEFERRED, NEXT_CYCLE)])
    v = check_release_readiness(root, head=HEAD)
    assert any("destination and reason" in x for x in v)


# --- 5. no dangling reference ------------------------------------------------------------------

def test_a_blocker_pointing_at_a_nonexistent_item_fails(tmp_path):
    root = _tree(tmp_path, open_rows=[_row("P-01", "BLOCKER", "06-77 owns it")])
    v = check_release_readiness(root, head=HEAD)
    assert any("dangling" in x and "06-77" in x for x in v)


def test_an_item_citing_a_nonexistent_problem_fails(tmp_path):
    root = _tree(tmp_path, items=[
        f"### 07-02 Something\n\nRole: jnwb-developer.\nRelease: deferred-{NEXT_CYCLE}.\n"
        "P-999. That row does not exist.\n"])
    v = check_release_readiness(root, head=HEAD)
    assert any("dangling" in x and "P-999" in x for x in v)


# --- 6. the closure receipt --------------------------------------------------------------------

def test_a_missing_receipt_fails(tmp_path):
    root = _tree(tmp_path, receipt=False)
    v = check_release_readiness(root, head=HEAD)
    assert any("blocker_fixpoint_receipt" in x for x in v)


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
    """The narrowing that makes condition 3 terminate at all, pinned as behaviour.

    A closure pass that discovers fifty 0.2.7-quality observations and zero blockers must
    still close the release. If this ever fails, the fixpoint has silently widened back to
    the form that could not terminate.
    """
    rows = [_row(f"P-{n:02d}", _DEFERRED, _GOOD_DEFER_REASON) for n in range(1, 51)]
    root = _tree(tmp_path, open_rows=rows, found=0)
    assert check_release_readiness(root, head=HEAD) == []


# --- absence must not read as compliance -------------------------------------------------------

def test_a_missing_problem_stack_does_not_pass(tmp_path):
    """Every block in gate 8 was once ``if <file>.exists():`` with no else, so an empty
    directory passed. A condition satisfied by deleting its own evidence is worse than none."""
    (tmp_path / "artifacts").mkdir(parents=True)
    (tmp_path / "artifacts" / "todo_stack.md").write_text(
        _TODOS.format(cycle=NEXT_CYCLE, items=""), encoding="utf-8")
    v = check_release_readiness(tmp_path, head=HEAD)
    assert v, "a tree with no problem stack at all passed the release check"


# --- the live tree -----------------------------------------------------------------------------

def test_the_live_stacks_are_readable_by_the_parsers():
    """Not an emptiness assertion. A formatting change that silently reduced either file to
    zero rows would otherwise read as a satisfied release condition."""
    assert todo_release_fields(REPO_ROOT), "the todo stack parsed to zero items"
    assert open_problem_dispositions(REPO_ROOT), "the problem stack parsed to zero open rows"


def test_every_live_open_row_parses_to_a_disposition_cell():
    """A row whose cell count is wrong yields ``MALFORMED`` rather than a silent skip."""
    rows = open_problem_dispositions(REPO_ROOT)
    malformed = [pid for pid, disp, _ in rows if disp == "MALFORMED"]
    assert not malformed, f"open rows that do not parse to five columns: {malformed}"


def test_the_live_closed_rows_use_only_declared_dispositions():
    """Checks every closed row's disposition cell, backticked or not.

    The previous form of this test matched only ``` `disposition` ``` in backticks, so rows
    written without them were invisible to it -- and three such rows were written during 0.2.6.
    """
    text = (REPO_ROOT / "artifacts" / "problem_stack.md").read_text(encoding="utf-8")
    closed = text.split("\n## Closed\n", 1)
    assert len(closed) == 2, "the problem stack has no Closed section"
    allowed = {"repaired", "accepted", "not-a-defect"}
    unknown = []
    for line in closed[1].splitlines():
        if not line.startswith("| P-"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)]
        if len(cells) != 6:
            unknown.append(f"{cells[1]}: {len(cells) - 2} columns")
            continue
        if cells[3].strip("`").lower() not in allowed:
            unknown.append(f"{cells[1]}: {cells[3][:30]!r}")
    assert not unknown, f"closed rows with an undeclared disposition: {unknown}"


def test_the_receipt_parser_reads_nothing_from_an_absent_receipt():
    commit, found = blocker_fixpoint_receipt(pathlib.Path("/nonexistent-tree"))
    assert commit is None and found is None


def test_the_declared_dispositions_are_exactly_the_three_ruled():
    assert set(DISPOSITIONS) == {"BLOCKER", f"DEFERRED->{NEXT_CYCLE}", "ACCEPTED"}


@pytest.mark.parametrize("ident", ["06-01", "06-99", "06-100", "06-113", "07-5"])
def test_an_item_id_of_any_digit_width_is_counted(tmp_path, ident):
    """P-175. The parsers matched ``\\d\\d-\\d\\d``, which requires EXACTLY two digits after the
    hyphen. Ids passed three digits at 06-100, so eleven items were invisible to the release
    gate's own emptiness check -- including 06-101, an unresolved human ruling. A release check
    that cannot see part of the stack it is checking reports emptiness it has not established.
    """
    root = _tree(tmp_path, items=[_item(ident, "required-0.2.6")])
    assert [i for i, _, _ in todo_release_fields(root)] == [ident]
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and ident in x for x in v), \
        f"item {ident} was invisible to the release check"


def test_the_live_item_count_agrees_between_both_parsers():
    """Two parsers counted the live stack differently for days and neither was cross-checked.

    Both now read through one parser, so their agreement alone is a tautology. The raw count of
    id-led headings at any depth is the independent side, and the live stack must hold no
    section that looks like an item but cannot be read.
    """
    from scripts.release_gate import remaining_todo_items, unparseable_todo_headings
    text = (REPO_ROOT / "artifacts" / "todo_stack.md").read_text(encoding="utf-8")
    raw = re.findall(r"^ {0,3}#+[ \t]+\d\d-\d+(?:[ \t]|$)", text, re.M)
    assert len(remaining_todo_items(REPO_ROOT)) == len(todo_release_fields(REPO_ROOT)) == len(raw)
    assert unparseable_todo_headings(REPO_ROOT) == []


def _nested(depth, parent_release="Release: deferred-0.2.7.\n", child_release="required-0.2.6"):
    return (f"### 99-900 A parent\n\n{parent_release}\n"
            f"{depth} 99-901 A nested item\n\nRelease: {child_release}.\n")


@pytest.mark.parametrize("depth", ["##", "###", "####", "#####", "######"])
def test_a_required_item_is_seen_at_any_heading_depth(tmp_path, depth):
    """Only `### ` was read, so an item one level deeper was invisible and its `Release:` field
    was read as its parent's, which kept the parent deferred and the release check clean."""
    root = _tree(tmp_path, items=[_nested(depth)])
    fields = {i: r for i, _, r in todo_release_fields(root)}
    assert fields == {"99-900": f"deferred-{NEXT_CYCLE}", "99-901": "required-0.2.6"}
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "99-901" in x for x in v), v


def test_a_parent_does_not_inherit_a_nested_items_release_field(tmp_path):
    """The other direction: a parent with no field read the deferred value of the item below."""
    root = _tree(tmp_path, items=[_nested("####", parent_release="",
                                          child_release=f"deferred-{NEXT_CYCLE}")])
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "99-900" in x for x in v), v


def test_an_item_stating_two_release_values_is_required(tmp_path):
    root = _tree(tmp_path, items=[_item("99-901", f"deferred-{NEXT_CYCLE}")
                                  + "Release: required-0.2.6.\n"])
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
    root = _tree(tmp_path, items=[_item("99-901", f"deferred-{NEXT_CYCLE}") + second + "\n"])
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
    root = _tree(tmp_path, items=[_item("99-901", f"deferred-{NEXT_CYCLE}") + "\n" + hidden])
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "99-902" in x for x in v), v
    assert not any("99-901" in x for x in v), v


def test_a_release_field_before_the_first_heading_fails_closed(tmp_path):
    root = _tree(tmp_path, items=[_item("99-901", f"deferred-{NEXT_CYCLE}")])
    assert check_release_readiness(root, head=HEAD) == []
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
    """The other side of the fail-closed check, measured on a tree that is otherwise compliant."""
    root = _tree(tmp_path, items=[
        "## W9-W10. A group heading\n",
        "### 2026-09-23 A dated note\n\nNo field here.\n",
        _item("07-01", f"deferred-{NEXT_CYCLE}") + "\n#### Notes\n\nProse only.\n",
    ])
    assert check_release_readiness(root, head=HEAD) == []


@pytest.mark.parametrize(
    "cell, expected",
    [
        ("Repaired 2026-09-20, closed by 06-83.", ["06-83"]),
        ("Answered in 06-13; ruled 2026-09-19.", ["06-13"]),
        ("06-94 closed 2026-09-20 and 06-98 retired", ["06-94", "06-98"]),
        ("2026-09-21", []),
        ("06-36", ["06-36"]),
        ("06-100", ["06-100"]),
        ("07-5", ["07-5"]),
    ],
)
def test_an_iso_date_is_not_read_as_an_item_reference(cell, expected):
    """A repair date next to an item id produced a dangling reference to the date.

    ``\\b(\\d\\d-\\d+)\\b`` matched ``09-20`` inside ``2026-09-20``. Measured live at 30c425cf:
    P-56's cell yielded ``['06-83', '09-20']`` and P-69's ``['06-94', '09-20']``, so
    dispositioning either row BLOCKER would have reported a reference to an item that never
    existed. The gate errs toward failing, so it hid nothing -- but the obvious repair is the
    trap. Two narrowings that look right and are not:

    * ``\\b(0\\d-\\d+)\\b`` -- ``09`` also begins with a zero, so it matches the date fragment
      identically. Measured: it changes the result on none of the four failing cases.
    * ``\\d\\d-\\d\\d`` -- that is P-175, which made eleven three-digit items invisible.

    This is the parametrization that distinguishes all three, which is why it enumerates both
    real ids and real dates rather than asserting on the live stack alone.
    """
    from scripts.release_gate import _ITEM_REF
    assert sorted(set(_ITEM_REF.findall(cell))) == sorted(expected)


def test_the_item_reference_pattern_rejects_both_known_wrong_narrowings():
    """Pins the two rejected candidates so neither can be reintroduced as a simplification."""
    import re

    from scripts.release_gate import _ITEM_REF

    dated = "Repaired 2026-09-20, closed by 06-83."
    assert re.findall(r"\b(\d\d-\d+)\b", dated) == ["09-20", "06-83"], \
        "the original pattern no longer reproduces the defect; this test's premise is stale"
    assert re.findall(r"\b(0\d-\d+)\b", dated) == ["09-20", "06-83"], \
        "the 0\\d narrowing no longer reproduces the defect; this test's premise is stale"
    assert _ITEM_REF.findall(dated) == ["06-83"]
    # And the P-175 direction, so a later narrowing cannot trade one defect for the other.
    assert _ITEM_REF.findall("06-100") == ["06-100"]


def test_a_deferred_problem_pointing_at_a_dead_item_fails(tmp_path):
    """Condition 5 must inspect every open row, not only the `BLOCKER` ones.

    The guard in `check_release_readiness` read `if disp == "BLOCKER" and ref not in
    live_items`. Condition 2 requires zero `BLOCKER` rows, so the loop body could not execute
    in the one state where the release qualifies: the check reported zero dangling references
    unconditionally, and 21 real ones sat in the live stack while it did.

    `test_a_blocker_pointing_at_a_nonexistent_item_fails` could not catch that. Its row is a
    `BLOCKER`, so condition 2 fails the tree by itself and the assertion is satisfied whatever
    condition 5 does. This tree is compliant in every other respect -- zero blockers, every
    disposition declared, a good deferral reason, a valid receipt -- so the *only* thing that
    can fail it is condition 5 reading a deferred row.
    """
    root = _tree(
        tmp_path,
        open_rows=[_row("P-01", _DEFERRED, f"{_GOOD_DEFER_REASON}; 06-77 carries it")],
        items=[_item("07-01", f"deferred-{NEXT_CYCLE}")],
    )
    violations = check_release_readiness(root, head=HEAD)
    assert any("dangling" in v for v in violations), (
        "a deferred problem naming an item that is not in the stack was not reported; "
        f"condition 5 is not reading non-blocker rows. Violations: {violations}"
    )
    assert any("06-77" in v for v in violations), (
        f"the dangling reference was reported without naming the dead item: {violations}"
    )


@pytest.mark.parametrize("answered", [
    "07-77",
    f"{_GOOD_DEFER_REASON}. Claimed by 07-77; 07-70 closed",
])
def test_an_ownership_claim_on_a_dead_item_fails_even_beside_a_retirement_word(
        tmp_path, answered):
    """The ownership path had no discriminator: disabling it passed every test here.

    A bare pointer and a `claimed by` phrase are ownership claims, and an owner must be live
    however the rest of the cell reads. The other-mention path accepts a dead id once the cell
    says something was retired, so without the ownership path the second cell passes, and the
    first is reported only as a passing mention rather than as the owner it is.
    """
    root = _tree(tmp_path, open_rows=[_row("P-01", _DEFERRED, answered)],
                 items=[_item("07-01", f"deferred-{NEXT_CYCLE}")])
    violations = check_release_readiness(root, head=HEAD)
    assert any("claims owner 07-77" in v for v in violations), violations


def test_a_deferred_problem_pointing_at_a_live_item_passes(tmp_path):
    """The other side, so the test above cannot pass by failing every tree.

    A deferral is granted on the condition that its evidence is preserved for the next cycle,
    which is what a resolvable pointer establishes. Naming a live item must therefore be clean.
    """
    root = _tree(
        tmp_path,
        open_rows=[_row("P-01", _DEFERRED, f"{_GOOD_DEFER_REASON}; 07-01 carries it")],
        items=[_item("07-01", f"deferred-{NEXT_CYCLE}")],
    )
    assert check_release_readiness(root, head=HEAD) == []
