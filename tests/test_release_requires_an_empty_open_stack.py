"""Condition 3 of ``AGENTS.md`` section 11, as amended 2026-09-23, as a check that can fail.

The open stack holds only problems not yet triaged, and a release requires:

  0. the working tree has no uncommitted change;
  1. the open stack exists and holds no table data row, in any section; prose does not count;
  2. no todo item is still required for this cycle, and every item's release is readable; this
     cycle's release step, which completes only after the tag, is not required; no line in a
     section that does not hold the release open marks work required for this cycle;
  3. the independent blocker-focused closure receipt exists and reports zero, and its commit is
     HEAD or an ancestor that differs from HEAD only in the receipt and the todo stack, and no
     item held open at the receipt's commit carries another release at HEAD or is gone without
     the receipt recording it as finished;
  4. the committed peak-memory record names the version the tree declares.

Every test drives the check over a constructed tree and is measured against
``test_a_compliant_tree_passes``: the compliant tree passes, and breaking exactly one thing fails.
A test that only asserted the live tree reports violations would pass against a function that
always returns one.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
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
    RELEASE_CYCLE,
    ROADMAP_PATH,
    blocker_fixpoint_receipt,
    check_release_readiness,
    roadmap_rows,
    todo_release_fields,
)
HEAD = "a" * 40
DEFERRED = f"deferred-{NEXT_CYCLE}"
REQUIRED = f"required-{RELEASE_CYCLE}"
RELEASE_STEP = f"release-step-{RELEASE_CYCLE}"
# A cycle past the next one, for a deferral that skips a cycle. Derived, like DEFERRED, so the
# cases keep their meaning when the declared version moves.
AFTER_NEXT = "{}.{}.{}".format(*(int(p) + (i == 2) for i, p in enumerate(NEXT_CYCLE.split("."))))
# The release before this one, derived the same way: the tag a constructed tree is released from.
PREVIOUS_CYCLE = "{}.{}.{}".format(*(int(p) - (i == 2) for i, p in enumerate(RELEASE_CYCLE.split("."))))

_OPEN = """# Open stack

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

# The publication jobs, and one non-publication job that may continue on error, as the live
# workflow has them. A publication job is one whose step uses the PyPI publish action.
_PUBLISH_STEP = "      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33\n"
_WORKFLOW = f"""name: CI
on: [push]
jobs:
  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - run: echo test
  publish-testpypi:
    name: Publish to TestPyPI
    needs: test
    runs-on: ubuntu-latest
    environment:
      name: testpypi
    steps:
{_PUBLISH_STEP}  publish-pypi:
    name: Publish to PyPI
    needs: test
    runs-on: ubuntu-latest
    environment:
      name: pypi
    steps:
{_PUBLISH_STEP}  test-pandas3:
    name: pandas 3
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - run: echo pandas
"""


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=jnwb-test", "-c",
         "user.email=test@example.invalid", "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True, check=True).stdout.strip()


def _commit(root, message):
    _git(root, "add", "--all")
    _git(root, "commit", "-q", "--allow-empty", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _roadmap(*rows):
    return "# Roadmap\n\n| ID | Theme | Defect | Waits | Release |\n|---|---|---|---|---|\n" + "".join(
        f"{r}\n" for r in rows)


def _tree(tmp_path, *, rows=(), tail="", items=(), commit=HEAD, found=0, receipt=True,
          recorded=RELEASE_CYCLE, fragments=(), roadmap=_roadmap(), workflow=_WORKFLOW):
    """The stacks and receipt, committed: STEP 0a reads them from HEAD, not the working copy.
    ``commit`` is what the receipt records; ``HEAD`` is passed as the head it is checked against.
    ``recorded`` is the version the peak-memory record names, ``None`` for no record.
    ``artifacts/changelog.d/`` holds its README and each name in ``fragments``.
    ``roadmap`` is the roadmap's text, ``None`` for no roadmap. ``workflow`` is the CI workflow's
    text, ``None`` for no workflow file. The repository opens with the previous release, tagged
    ``v<PREVIOUS_CYCLE>`` with a record that holds no operation, so the growth check has a release
    to compare with and nothing to report."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "jnwb").mkdir(exist_ok=True)
    (tmp_path / "artifacts" / "benchmarks" / "performance").mkdir(parents=True, exist_ok=True)
    (tmp_path / "jnwb" / "__init__.py").write_text(f"__version__ = '{PREVIOUS_CYCLE}'\n",
                                                   encoding="utf-8")
    (tmp_path / "artifacts" / "benchmarks" / "performance" / "peak_memory.json").write_text(
        _record(PREVIOUS_CYCLE, {}), encoding="utf-8")
    _commit(tmp_path, "the previous release")
    _git(tmp_path, "tag", f"v{PREVIOUS_CYCLE}")
    if roadmap is not None:
        (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)
        (tmp_path / "artifacts" / "roadmap.md").write_text(roadmap, encoding="utf-8")
    (tmp_path / "artifacts" / "changelog.d").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "changelog.d" / "README.md").write_text("# Fragments\n", encoding="utf-8")
    for name in fragments:
        (tmp_path / "artifacts" / "changelog.d" / name).write_text("- a change\n", encoding="utf-8")
    (tmp_path / "artifacts" / "benchmarks" / "performance").mkdir(parents=True, exist_ok=True)
    (tmp_path / "jnwb").mkdir(exist_ok=True)
    (tmp_path / "jnwb" / "__init__.py").write_text(f"__version__ = '{RELEASE_CYCLE}'\n",
                                                   encoding="utf-8")
    record = tmp_path / "artifacts" / "benchmarks" / "performance" / "peak_memory.json"
    if recorded is not None:
        record.write_text(_record(recorded, {}), encoding="utf-8")
    else:
        record.unlink(missing_ok=True)
    (tmp_path / "artifacts" / "open_stack.md").write_text(
        _OPEN.format(rows="\n".join(rows)) + tail, encoding="utf-8")
    (tmp_path / "artifacts" / "todo_stack.md").write_text(
        _TODOS.format(cycle=NEXT_CYCLE, items="\n".join(items)), encoding="utf-8")
    if workflow is not None:
        (tmp_path / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".github" / "workflows" / "workflow.yml").write_text(workflow, encoding="utf-8")
    if receipt:
        (tmp_path / "artifacts" / "process").mkdir(parents=True, exist_ok=True)
        (tmp_path / "artifacts" / "process" / "blocker_fixpoint_receipt.md").write_text(
            _RECEIPT.format(commit=commit, found=found), encoding="utf-8")
    _commit(tmp_path, "the tree")
    return tmp_path


def _item(ident, release):
    return (f"### {ident} Something\n\nRole: jnwb-developer. Skill: none. Blocked by: none.\n"
            f"Release: {release}.\nWrites: `jnwb/x.py`.\n")


# --- the compliant tree, which every discriminator below is measured against ------------------

def test_a_compliant_tree_passes(tmp_path):
    """An open stack with no table row, only deferred items and a receipt at HEAD."""
    from scripts.release_gate import open_rows

    root = _tree(tmp_path, items=[_item("07-01", DEFERRED), _item("07-02", DEFERRED)])
    assert open_rows(root) == []
    assert check_release_readiness(root, head=HEAD) == []


def test_table_data_rows_count_rows_and_not_prose():
    """A table data row is a table line that is neither its header nor a separator. A line with
    a pipe in prose is not a table line."""
    from scripts.release_gate import table_data_rows

    text = "# Open\n\nProse with a | pipe.\n\n| ID | P |\n|---|---|\n| a | b |\n"
    assert table_data_rows(text) == [(7, "| a | b |")]


# --- 1. the open stack holds no table row -------------------------------------------------------------

@pytest.mark.parametrize("rows, tail", [
    (["| P-01 | a defect | a packet |"], ""),
    (["| P-01 | a defect | a packet | DEFERRED->0.2.7 | carried, with a reason |"], ""),
    (["| P-01 | a defect | a packet | ACCEPTED | cannot be retested |"], ""),
    (["| P-01 | a malformed row with one cell"], ""),
    (["|P-01|no spaces|x|"], ""),
    ([], "\n## Closed\n\n| ID | Problem | Disposition |\n|---|---|---|\n| P-C1 | done | repaired |\n"),
    ([], "\n  | P-01 | indented under prose, outside any table heading | x |\n"),
], ids=["plain", "deferred", "accepted", "malformed", "unspaced", "closed-section", "indented"])
def test_any_table_row_fails_whatever_it_says_or_wherever_it_sits(tmp_path, rows, tail):
    root = _tree(tmp_path, rows=rows, tail=tail, items=[_item("07-01", DEFERRED)])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and v[0].startswith("1 table row(s) remain"), v


#: Table data rows written in a form a row-shaped pattern does not read. Each one is a row.
EVASIONS = {
    "bold-id": "| **P-300** | a defect | x |",
    "code-id": "| `P-300` | a defect | x |",
    "lowercase-id": "| p-300 | a defect | x |",
    "blockquoted-table": "> | ID | Problem | Found by |\n> |---|---|---|\n> | P-300 | a defect | x |",
    "id-in-column-2": "| x | P-300 | a defect |",
    "unnumbered-row": "| | a defect | x |",
}

#: Text the rule does not count: prose, a bullet, and a bare header with its separator.
NOT_ROWS = {
    "bullet": "- P-300: a defect",
    "prose": "A defect nobody has triaged yet.",
    "second-header": "| ID | Problem | Found by |\n|---|---|---|",
}

@pytest.mark.parametrize("line", list(EVASIONS.values()), ids=list(EVASIONS))
def test_any_table_data_row_fails_step_0a_whatever_its_cells_say(tmp_path, line):
    root = _tree(tmp_path, rows=[line], items=[_item("07-01", DEFERRED)])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "table row(s) remain" in v[0], v


@pytest.mark.parametrize("line", list(NOT_ROWS.values()), ids=list(NOT_ROWS))
def test_prose_and_a_bare_header_pass_step_0a(tmp_path, line):
    """The rule counts table data rows, not sections: a line that is not a row does not count."""
    root = _tree(tmp_path, rows=[line], items=[_item("07-01", DEFERRED)])
    assert check_release_readiness(root, head=HEAD) == []


def test_an_open_stack_with_no_open_section_passes_step_0a(tmp_path):
    """STEP 0a counts table rows, not sections: a stack of prose with no table row passes."""
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)])
    (root / "artifacts" / "open_stack.md").write_text(
        "# Open stack\n\nNothing open, and no table row.\n", encoding="utf-8")
    _commit(root, "replace the open stack with prose")
    assert check_release_readiness(root, head=HEAD) == []


def test_a_missing_open_stack_fails(tmp_path):
    """A condition satisfied by deleting its own evidence is worse than none."""
    from scripts.release_gate import open_rows

    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)])
    (root / "artifacts" / "open_stack.md").unlink()
    _commit(root, "delete the open stack")
    assert open_rows(root) is None
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "open_stack.md is missing" in v[0], v


# --- 2. no required item remains ---------------------------------------------------------------

@pytest.mark.parametrize("name", ["stray.fixed.md", "notes.txt", ".keep"])
def test_a_fragment_left_in_changelog_d_fails(tmp_path, name):
    """A fragment still in artifacts/changelog.d/ is a change the assembled release notes do not carry."""
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)], fragments=[name])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "artifacts/changelog.d/" in v[0] and f"artifacts/changelog.d/{name}" in v[0], v


def test_an_item_still_required_this_cycle_fails(tmp_path):
    root = _tree(tmp_path, items=[_item("06-99", "required-0.2.6")])
    v = check_release_readiness(root, head=HEAD)
    assert any("still required" in x and "06-99" in x for x in v)


@pytest.mark.parametrize("release", [f"deferred-{AFTER_NEXT}", f"deferred-{RELEASE_CYCLE}"])
def test_an_item_deferred_to_any_cycle_but_the_next_fails(tmp_path, release):
    """Only the next cycle's stack carries deferred work; any other `deferred-*` is not deferred."""
    root = _tree(tmp_path, items=[_item("99-903", release), _item("99-904", DEFERRED)])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "1 todo item(s) are still required" in v[0] and "99-903" in v[0], v


def test_this_cycles_release_step_is_not_required(tmp_path):
    """A release step completes only after the tag, so STEP 0a cannot wait for it."""
    root = _tree(tmp_path, items=[_item("99-910", RELEASE_STEP), _item("99-911", DEFERRED)])
    assert check_release_readiness(root, head=HEAD) == []


@pytest.mark.parametrize("release", [
    f"release-step-{NEXT_CYCLE}",
    "release-step-",
    "release-step",
    f"release-step-{RELEASE_CYCLE}-rc1",
    f"Release-step-{RELEASE_CYCLE}",
])
def test_a_release_step_for_any_other_cycle_or_in_any_other_form_is_required(tmp_path, release):
    root = _tree(tmp_path, items=[_item("99-912", release), _item("99-913", RELEASE_STEP)])
    v = check_release_readiness(root, head=HEAD)
    assert (len(v) == 1 and "1 todo item(s) are still required" in v[0] and "99-912" in v[0]
            and f"[{release}]" in v[0]), v


def test_a_required_item_beside_a_release_step_still_fails(tmp_path):
    root = _tree(tmp_path, items=[_item("99-914", RELEASE_STEP),
                                  _item("99-915", f"required-{RELEASE_CYCLE}")])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "1 todo item(s) are still required" in v[0], v
    assert "99-915" in v[0] and "99-914" not in v[0], v


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


def _nested(depth, parent_release=f"Release: {DEFERRED}.\n", child_release="required-0.2.6"):
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
    _commit(root, "a release field before the first heading")
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


#: Bullets that mark themselves required, in the two forms the stack writes a bullet's release.
REQUIRED_BULLETS = {
    "value-form": f"- P-900: a defect.\n  {REQUIRED}: it blocks the release.\n",
    "prose-form": f"- P-900: a defect. Required for {RELEASE_CYCLE} (classified): it blocks.\n",
    "earlier-cycle": "- P-900: a defect.\n  required-0.0.1: written for a cycle before this one.\n",
    "bold": f"- P-900: a defect. **Required for {RELEASE_CYCLE}**: it blocks.\n",
    "bold-word": f"- P-900: a defect. **Required** for {RELEASE_CYCLE}: it blocks.\n",
    "underscored": f"- P-900: a defect. _Required_ for {RELEASE_CYCLE}: it blocks.\n",
    "tab-separated": f"- P-900: a defect. Required\tfor\t{RELEASE_CYCLE}: it blocks.\n",
    "wrapped": f"- P-900: a defect. Required\n  for {RELEASE_CYCLE}: it blocks.\n",
    "wrapped-unindented": f"- P-900: a defect. Required for\n{RELEASE_CYCLE}: it blocks.\n",
    "backticked": f"- P-900: a defect. `Required` for {RELEASE_CYCLE}: it blocks.\n",
}


@pytest.mark.parametrize("bullet", list(REQUIRED_BULLETS.values()), ids=list(REQUIRED_BULLETS))
@pytest.mark.parametrize("host", ["deferred", "release-step", "deferred-subsection"])
def test_a_required_bullet_inside_an_item_that_does_not_hold_the_release_fails(
        tmp_path, bullet, host):
    """The item's own field read deferred, so the bullet it carried was invisible. What would pass
    while that still holds: reading the marker only in the item's first body paragraph, or only
    in an item and not in its subsection."""
    release = RELEASE_STEP if host == "release-step" else DEFERRED
    body = "\n#### More findings\n\n" + bullet if host == "deferred-subsection" else "\n" + bullet
    root = _tree(tmp_path, items=[_item("99-960", release) + body, _item("99-961", DEFERRED)])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "mark work required" in v[0] and f"99-960 [{release}]" in v[0], v
    assert "99-961" not in v[0], v


def test_a_required_bullet_outside_any_item_fails(tmp_path):
    root = _tree(tmp_path, items=[_item("99-961", DEFERRED),
                                  "## Out of scope\n\n" + REQUIRED_BULLETS["prose-form"]])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "mark work required" in v[0] and "'Out of scope'" in v[0], v


def test_a_required_bullet_inside_a_held_item_is_condition_2s_alone(tmp_path):
    """The item already holds the release; its bullets add no second violation."""
    root = _tree(tmp_path, items=[_item("99-962", REQUIRED) + "\n" + REQUIRED_BULLETS["value-form"]])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "still required" in v[0] and "99-962" in v[0], v


@pytest.mark.parametrize("line", [
    f"- P-900: a defect.\n  required-{NEXT_CYCLE}: next cycle's work.\n",
    "- P-900: the PSI clause is required, in another item.\n",
    "- P-900: a machine-required literal.\n",
], ids=["later-cycle", "prose-pointer", "hyphenated-word"])
def test_a_deferred_bullet_that_names_no_required_release_passes(tmp_path, line):
    root = _tree(tmp_path, items=[_item("99-963", DEFERRED) + "\n" + line])
    assert check_release_readiness(root, head=HEAD) == []


def test_a_section_at_item_depth_that_lists_work_without_an_id_or_release_fails(tmp_path):
    """Neither an id nor a field, so the parser skipped it as prose and its work had no release."""
    root = _tree(tmp_path, items=[_item("99-964", DEFERRED),
                                  "### Leftover work\n\n- P-901: a defect nobody filed.\n"])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "cannot be read" in v[0] and "'Leftover work'" in v[0], v


def test_a_listed_structure_section_or_item_subsection_is_not_unfiled_work(tmp_path):
    """The stack's own structure sits above item depth; an item's subsection is the item's."""
    root = _tree(tmp_path, items=[
        "## Out of scope\n\n- Raw-data conversion.\n",
        _item("99-965", DEFERRED) + "\n#### Notes\n\n- a note on the item.\n",
    ])
    assert check_release_readiness(root, head=HEAD) == []


def test_a_required_item_message_names_its_whole_title(tmp_path):
    """The message cut each title at 34 characters, so the item it named was not findable from it."""
    title = "Make the release gate name the whole item title it refers to in its message"
    root = _tree(tmp_path, items=[f"### 99-970 {title}\n\nRelease: {REQUIRED}.\n"])
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and f"99-970 {title}" in v[0], v


# --- 3. the closure receipt --------------------------------------------------------------------

def test_a_missing_receipt_fails(tmp_path):
    root = _tree(tmp_path, receipt=False)
    v = check_release_readiness(root, head=HEAD)
    assert v and all("blocker_fixpoint_receipt" in x for x in v), v


# --- 0. the evidence is what HEAD commits ------------------------------------------------------

def test_an_uncommitted_edit_cannot_pass_a_commit_whose_stack_holds_required_items(tmp_path):
    """The committed stack holds a required item; the working copy deletes it and adds a receipt
    at HEAD. Reading the working copy reported no violation at all. What would pass while the
    working copy is still read: checking only that some violation is reported, because the
    uncommitted-change refusal alone would supply one."""
    root = _tree(tmp_path, items=[_item("99-940", REQUIRED), _item("99-941", DEFERRED)],
                 receipt=False)
    head = _git(root, "rev-parse", "HEAD")
    todo = root / "artifacts" / "todo_stack.md"
    todo.write_text(todo.read_text(encoding="utf-8").replace(_item("99-940", REQUIRED), ""),
                    encoding="utf-8")
    _record_receipt(root, head)
    v = check_release_readiness(root, head=head)
    assert any("still required" in x and "99-940" in x for x in v), v
    assert any("receipt" in x and "missing at HEAD" in x for x in v), v
    dirty = [x for x in v if "uncommitted changes" in x]
    assert len(dirty) == 1 and "artifacts/todo_stack.md" in dirty[0], v
    assert "artifacts/process/blocker_fixpoint_receipt.md" in dirty[0], v
    assert "open_stack" not in dirty[0], v


def test_an_open_row_committed_at_head_is_seen_when_the_working_copy_drops_it(tmp_path):
    root = _tree(tmp_path, rows=["| P-950 | a defect | x |"], items=[_item("07-01", DEFERRED)])
    stack = root / "artifacts" / "open_stack.md"
    stack.write_text(stack.read_text(encoding="utf-8").replace("| P-950 | a defect | x |", ""),
                     encoding="utf-8")
    v = check_release_readiness(root, head=HEAD)
    assert any("table row(s) remain" in x and "P-950" in x for x in v), v


@pytest.mark.parametrize("path", ["open_stack.md", "todo_stack.md",
                                  "process/blocker_fixpoint_receipt.md"])
def test_an_uncommitted_change_to_any_file_step_0a_reads_is_named(tmp_path, path):
    """A compliant committed tree fails on an uncommitted edit to any one of the three files,
    even an edit that changes no verdict, and only that file is named."""
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)])
    assert check_release_readiness(root, head=HEAD) == []
    target = root / "artifacts" / path
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "uncommitted changes: artifacts/" + path + "." in v[0], v


@pytest.mark.parametrize("change", ["untracked", "modified", "staged", "deleted", "renamed"])
def test_an_uncommitted_change_anywhere_in_the_tree_fails(tmp_path, change):
    """Only the three stack files were checked, so uncommitted code passed under a receipt at
    HEAD and would have been built into the release. What would pass while that still holds: a
    check that sees only tracked modifications, or only untracked files."""
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)])
    code = root / "jnwb" / "x.py"
    if change != "untracked":
        code.parent.mkdir(exist_ok=True)
        code.write_text("x = 1\n", encoding="utf-8")
        _commit(root, "code")
    assert check_release_readiness(root, head=HEAD) == []
    if change == "deleted":
        code.unlink()
    elif change == "renamed":
        _git(root, "mv", "jnwb/x.py", "jnwb/y.py")
    else:
        code.parent.mkdir(exist_ok=True)
        code.write_text("x = 2\n", encoding="utf-8")
        if change == "staged":
            _git(root, "add", "jnwb/x.py")
    v = check_release_readiness(root, head=HEAD)
    named = "jnwb/x.py, jnwb/y.py." if change == "renamed" else "jnwb/x.py."
    assert len(v) == 1 and "uncommitted changes: " + named in v[0], v


def test_a_git_status_that_fails_is_not_read_as_a_clean_tree(tmp_path, monkeypatch):
    """A failed `git status` read as clean survived every other test in this file."""
    import scripts.release_gate as gate

    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)])
    real = subprocess.run

    def status_fails(cmd, *args, **kwargs):
        if list(cmd[:2]) == ["git", "status"]:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: index file corrupt")
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(gate.subprocess, "run", status_fails)
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and v[0].startswith("git cannot report whether the working tree"), v


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_an_edit_hidden_from_git_status_by_an_index_flag_fails(tmp_path, flag):
    """`git status` does not report a file marked assume-unchanged or skip-worktree, so an edit to
    one read as a clean tree."""
    root = _tree(tmp_path, items=[_item("99-950", DEFERRED)])
    _git(root, "update-index", flag, "jnwb/__init__.py")
    (root / "jnwb" / "__init__.py").write_text("__version__ = 'edited'\n", encoding="utf-8")
    dirty = [x for x in check_release_readiness(root, head=HEAD) if "uncommitted changes" in x]
    assert len(dirty) == 1 and "jnwb/__init__.py" in dirty[0], dirty


@pytest.mark.parametrize("job, where", [
    ("publish-testpypi", "job"),
    ("publish-pypi", "job"),
    ("publish-testpypi", "step"),
], ids=["testpypi-job", "pypi-job", "testpypi-step"])
def test_a_publication_job_that_continues_on_error_fails(tmp_path, job, where):
    """A failed upload would read as a passing release, with `continue-on-error` on the job or on
    its publish step. The default workflow's pandas 3 job may continue on error, and passes."""
    if where == "job":
        workflow = _WORKFLOW.replace(f"  {job}:\n", f"  {job}:\n    continue-on-error: true\n", 1)
    else:
        workflow = _WORKFLOW.replace(_PUBLISH_STEP,
                                     _PUBLISH_STEP + "        continue-on-error: true\n", 1)
    root = _tree(tmp_path, items=[_item("99-951", DEFERRED)], workflow=workflow)
    hits = [x for x in check_release_readiness(root, head=HEAD) if "continues on error" in x]
    assert len(hits) == 1 and job in hits[0], hits


@pytest.mark.parametrize("where", ["twine-step", "reusable-job"])
def test_a_publication_that_continues_on_error_is_refused_beyond_the_pypi_action(tmp_path, where):
    """Condition 6 knew only the PyPI action, so a `twine upload` step or a job that calls a
    reusable workflow could continue on error and let a failed upload read as a release."""
    if where == "twine-step":
        extra = ("  publish-twine:\n"
                 "    needs: test\n"
                 "    runs-on: ubuntu-latest\n"
                 "    steps:\n"
                 "      - name: Upload\n"
                 "        continue-on-error: true\n"
                 "        run: python -m twine upload dist/*\n")
        job = "publish-twine"
    else:
        extra = ("  publish-reusable:\n"
                 "    needs: test\n"
                 "    continue-on-error: true\n"
                 "    uses: ./.github/workflows/publish.yml\n")
        job = "publish-reusable"
    root = _tree(tmp_path, items=[_item("99-953", DEFERRED)], workflow=_WORKFLOW + extra)
    hits = [x for x in check_release_readiness(root, head=HEAD) if "continues on error" in x]
    assert len(hits) == 1 and job in hits[0], hits


def test_a_twine_check_that_continues_on_error_is_not_a_publication(tmp_path):
    """`twine check` validates a built distribution and uploads nothing; only `twine upload`
    publishes, so a check job may continue on error without refusing the release."""
    extra = ("  check-dist:\n"
             "    needs: test\n"
             "    runs-on: ubuntu-latest\n"
             "    steps:\n"
             "      - name: Check\n"
             "        continue-on-error: true\n"
             "        run: python -m twine check dist/*\n")
    root = _tree(tmp_path, items=[_item("99-954", DEFERRED)], workflow=_WORKFLOW + extra)
    assert not [x for x in check_release_readiness(root, head=HEAD) if "continues on error" in x]


def test_a_tree_with_no_workflow_at_head_fails(tmp_path):
    root = _tree(tmp_path, items=[_item("99-952", DEFERRED)], workflow=None)
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and ".github/workflows/workflow.yml" in v[0], v


def _repository(tmp_path):
    """A committed compliant tree with no receipt yet: the commit the closure pass runs against."""
    root = _tree(tmp_path, items=[_item("99-920", DEFERRED), _item("99-921", DEFERRED)],
                 receipt=False)
    _git(root, "init", "-q")
    return root, _commit(root, "the tree the closure pass reads")


def _record_receipt(root, commit, found=0, finished=None):
    """``finished``, when given, is the receipt's `finished after the pass` cell."""
    text = _RECEIPT.format(commit=commit, found=found)
    if finished is not None:
        text += f"| finished after the pass | {finished} |\n"
    (root / "artifacts" / "process").mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / "process" / "blocker_fixpoint_receipt.md").write_text(text, encoding="utf-8")


def test_a_receipt_at_an_ancestor_followed_only_by_the_receipt_and_todo_stack_passes(tmp_path):
    """A committed receipt cannot name its own commit, so it names the one before it."""
    root, passed = _repository(tmp_path)
    _record_receipt(root, passed)
    todo = root / "artifacts" / "todo_stack.md"
    todo.write_text(todo.read_text(encoding="utf-8").replace(_item("99-921", DEFERRED), ""),
                    encoding="utf-8")
    head = _commit(root, "record the closure pass")
    assert _git(root, "diff", "--name-only", passed, head).split() == [
        "artifacts/process/blocker_fixpoint_receipt.md", "artifacts/todo_stack.md"]
    assert check_release_readiness(root, head=head) == []


@pytest.mark.parametrize("later", [False, True], ids=["with-the-receipt", "in-a-later-commit"])
def test_a_code_change_after_the_receipt_commit_fails(tmp_path, later):
    root, passed = _repository(tmp_path)
    _record_receipt(root, passed)
    if later:
        _commit(root, "record the closure pass")
    (root / "jnwb").mkdir(exist_ok=True)
    (root / "jnwb" / "x.py").write_text("x = 1\n", encoding="utf-8")
    head = _commit(root, "a change the closure pass never read")
    v = check_release_readiness(root, head=head)
    assert len(v) == 1 and "1 file(s) other than the receipt" in v[0] and "jnwb/x.py" in v[0], v


def test_a_receipt_commit_off_heads_history_fails(tmp_path):
    root, _ = _repository(tmp_path)
    trunk = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    _git(root, "checkout", "-q", "-b", "side")
    elsewhere = _commit(root, "a commit HEAD never descends from")
    _git(root, "checkout", "-q", trunk)
    _record_receipt(root, elsewhere)
    head = _commit(root, "record a closure pass from another history")
    v = check_release_readiness(root, head=head)
    assert len(v) == 1 and "is not an ancestor of HEAD" in v[0], v


def test_a_receipt_commit_the_repository_does_not_know_fails(tmp_path):
    root, _ = _repository(tmp_path)
    _record_receipt(root, "b" * 40)
    head = _commit(root, "record a closure pass against an unknown commit")
    v = check_release_readiness(root, head=head)
    assert len(v) == 1 and "does not know" in v[0], v


def _relabel(tmp_path, before, after, finished=None):
    """Violations once the receipt names a commit whose stack holds ``before`` and the commit
    recording it leaves ``after``. ``None`` leaves the stack out of that commit. ``finished`` is
    the receipt's `finished after the pass` cell, or no such row when ``None``."""
    todo = tmp_path / "artifacts" / "todo_stack.md"
    root = _tree(tmp_path, items=before or (), receipt=False)
    _git(root, "init", "-q")
    for step, items in enumerate((before, after)):
        if items is None:
            todo.unlink(missing_ok=True)
        else:
            todo.write_text(_TODOS.format(cycle=NEXT_CYCLE, items="\n".join(items)),
                            encoding="utf-8")
        if step == 0:
            passed = _commit(root, "the tree the closure pass reads")
            _record_receipt(root, passed, finished=finished)
    return check_release_readiness(root, head=_commit(root, "record the closure pass"))


@pytest.mark.parametrize("was, now", [
    (REQUIRED, DEFERRED),
    (REQUIRED, RELEASE_STEP),
    (f"deferred-{RELEASE_CYCLE}", DEFERRED),
], ids=["required-to-deferred", "required-to-release-step", "wrong-cycle-to-deferred"])
def test_relabelling_a_held_item_after_the_receipt_fails(tmp_path, was, now):
    """The closure pass judged what stays required; a later commit may delete, not relabel."""
    v = _relabel(tmp_path, [_item("99-930", was), _item("99-931", DEFERRED)],
                 [_item("99-930", now), _item("99-931", DEFERRED)])
    assert len(v) == 1 and "held open" in v[0] and f"99-930: {was} -> {now}" in v[0], v
    assert "99-931" not in v[0], v


def test_a_held_item_the_receipt_records_as_finished_may_be_deleted(tmp_path):
    assert _relabel(tmp_path, [_item("99-930", REQUIRED), _item("99-931", DEFERRED)],
                    [_item("99-931", DEFERRED)], finished="99-930") == []


@pytest.mark.parametrize("finished", [None, "", "none", "99-933", "99-9300", "x99-930"],
                         ids=["no-row", "empty", "none", "another-id", "longer-id", "prefixed"])
def test_a_held_item_deleted_without_the_receipt_recording_it_fails(tmp_path, finished):
    """A deletion alone read as done, so a dropped required item passed as a finished one. What
    would pass while that still holds: a receipt row that names some id, or an id containing
    this one, being read as covering it."""
    v = _relabel(tmp_path, [_item("99-930", REQUIRED), _item("99-931", DEFERRED)],
                 [_item("99-931", DEFERRED)], finished=finished)
    gone = [x for x in v if "gone at HEAD" in x]
    assert len(gone) == 1 and gone[0].endswith(": 99-930"), v
    # A row naming an id that was never held is refused as well, and says so.
    others = [x for x in v if x not in gone]
    if finished in ("99-933", "99-9300"):  # id-shaped; "x99-930" is no id and is not read
        assert others, f"the receipt names {finished!r}, which was never held, and nothing refused it"
    assert all("not held open" in x for x in others), v


def _later_row(tmp_path, *, row_in_first, delete_in_first, row_later=None, delete_later=False):
    """A closure pass at R over two held items, then the commit recording the receipt, then
    optionally a second commit. Returns the violations at the last commit."""
    before = [_item("99-930", REQUIRED), _item("99-931", DEFERRED)]
    root = _tree(tmp_path, items=before, receipt=False)
    todo = root / "artifacts" / "todo_stack.md"
    passed = _commit(root, "the tree the closure pass reads")
    left = [_item("99-931", DEFERRED)]
    _record_receipt(root, passed, finished=row_in_first)
    if delete_in_first:
        todo.write_text(_TODOS.format(cycle=NEXT_CYCLE, items="\n".join(left)), encoding="utf-8")
    head = _commit(root, "record the closure pass")
    if row_later is not None or delete_later:
        if row_later is not None:
            _record_receipt(root, passed, finished=row_later)
        if delete_later:
            todo.write_text(_TODOS.format(cycle=NEXT_CYCLE, items="\n".join(left)),
                            encoding="utf-8")
        head = _commit(root, "a later commit")
    return check_release_readiness(root, head=head)


def test_a_finished_row_written_with_the_deletion_in_the_receipts_commit_passes(tmp_path):
    assert _later_row(tmp_path, row_in_first="99-930", delete_in_first=True) == []


def test_a_finished_row_written_after_the_receipts_commit_fails(tmp_path):
    """A row added later names deletions the closure pass never saw. What would pass while that
    holds: reading the row only at HEAD, which is where it was written."""
    v = _later_row(tmp_path, row_in_first=None, delete_in_first=True, row_later="99-930")
    assert len(v) == 1 and "changed in 2 commit(s)" in v[0], v


def test_a_finished_item_deleted_in_a_later_commit_fails(tmp_path):
    v = _later_row(tmp_path, row_in_first="99-930", delete_in_first=False, delete_later=True)
    assert len(v) == 1 and "does not delete" in v[0] and v[0].endswith(": 99-930"), v


def test_a_finished_row_naming_an_item_not_held_at_the_receipt_fails(tmp_path):
    v = _later_row(tmp_path, row_in_first="99-930, 99-931", delete_in_first=True)
    assert len(v) == 1 and "not held open" in v[0] and v[0].endswith(": 99-931"), v


def _merged(tmp_path, *, receipt_on_main):
    """The receipt and the deletion recorded on a side branch and merged back. With
    ``receipt_on_main`` the trunk records the same receipt too, so the merge is clean."""
    before = [_item("99-930", REQUIRED), _item("99-931", DEFERRED)]
    root = _tree(tmp_path, items=before, receipt=False)
    todo = root / "artifacts" / "todo_stack.md"
    passed = _commit(root, "the tree the closure pass reads")
    trunk = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    _git(root, "checkout", "-q", "-b", "side")
    _record_receipt(root, passed, finished="99-930")
    todo.write_text(_TODOS.format(cycle=NEXT_CYCLE, items=_item("99-931", DEFERRED)),
                    encoding="utf-8")
    _commit(root, "record the closure pass on a side branch")
    _git(root, "checkout", "-q", trunk)
    if receipt_on_main:
        _record_receipt(root, passed, finished="99-930")
    _commit(root, "the trunk moves on")
    _git(root, "-c", "core.editor=true", "merge", "-q", "--no-ff", "--no-edit", "side")
    return check_release_readiness(root, head=_git(root, "rev-parse", "HEAD"))


def test_a_receipt_recorded_on_one_side_of_a_merge_is_one_write(tmp_path):
    """The merge takes the side branch's receipt; it writes none of its own."""
    assert _merged(tmp_path, receipt_on_main=False) == []


def test_a_receipt_recorded_on_both_sides_of_a_merge_is_two_writes(tmp_path):
    """Git's default history simplification follows one side of the merge and counts one."""
    v = _merged(tmp_path, receipt_on_main=True)
    assert len(v) == 1 and "changed in 2 commit(s)" in v[0], v


@pytest.mark.parametrize("first", ["trunk", "side"])
def test_a_merge_that_records_the_receipt_deletes_only_what_every_parent_still_held(tmp_path,
                                                                                    first):
    """The side branch deletes the item and the merge writes the receipt naming it. Against the
    trunk alone the merge deletes it; against the side it deletes nothing. Which parent is first
    is only the order the merge was made in, so both orders must refuse it."""
    before = [_item("99-930", REQUIRED), _item("99-931", DEFERRED)]
    root = _tree(tmp_path, items=before, receipt=False)
    todo = root / "artifacts" / "todo_stack.md"
    passed = _commit(root, "the tree the closure pass reads")
    trunk = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    _git(root, "checkout", "-q", "-b", "side")
    todo.write_text(_TODOS.format(cycle=NEXT_CYCLE, items=_item("99-931", DEFERRED)),
                    encoding="utf-8")
    _commit(root, "the side branch deletes the item")
    _git(root, "checkout", "-q", trunk)
    _commit(root, "the trunk moves on")
    if first == "side":
        _git(root, "checkout", "-q", "side")
    _git(root, "merge", "-q", "--no-ff", "--no-commit", "side" if first == "trunk" else trunk)
    _record_receipt(root, passed, finished="99-930")
    head = _commit(root, "the merge records the closure pass")
    assert len(_git(root, "rev-list", "--no-walk", "--parents", head).split()) == 3
    v = check_release_readiness(root, head=head)
    assert len(v) == 1 and "does not delete" in v[0] and v[0].endswith(": 99-930"), v


def test_a_peak_memory_record_for_another_version_fails(tmp_path):
    """The version is bumped in the commit that refreshes the record; a record naming another
    version was not refreshed for this release."""
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)], recorded="0.0.1")
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "was taken for jnwb 0.0.1" in v[0], v
    assert f"HEAD declares {RELEASE_CYCLE}" in v[0], v


def test_a_missing_peak_memory_record_fails(tmp_path):
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)], recorded=None)
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "peak_memory.json is missing at HEAD" in v[0], v


def test_the_peak_memory_record_is_read_as_committed(tmp_path):
    """A refreshed record left uncommitted is not the one the release carries."""
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)], recorded="0.0.1")
    (root / "artifacts" / "benchmarks" / "performance" / "peak_memory.json").write_text(
        f'{{"jnwb_version": "{RELEASE_CYCLE}"}}\n', encoding="utf-8")
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 2 and any("was taken for jnwb 0.0.1" in x for x in v), v


# --- the record may not grow past the bound since the previous release without a reason -----------

def _record(version, operations):
    """A peak-memory record as ``scripts/measure_peak_memory.py`` writes it: name -> added MiB."""
    return json.dumps({"jnwb_version": version, "unit": "MiB", "operations": {
        name: {"peak_mib": added + 100.0, "added_mib": added, "added_is": "exact"}
        for name, added in operations.items()}}, indent=2) + "\n"


def _changelog(*sections):
    """A CHANGELOG.md with each (version, body) as a dated section, after ``[Unreleased]``."""
    return "# Changelog\n\n## [Unreleased]\n\n" + "".join(
        f"## [{version}] - 2026-10-19\n\n{body}\n\n" for version, body in sections)


def _growth_tree(tmp_path, *, before, after, changelog=None, tag=True, before_dir=None):
    """Two commits. The previous release declares PREVIOUS_CYCLE with the record ``before`` (a dict
    of name -> added MiB, or None for no record), in ``before_dir`` when given, and is tagged
    ``v<PREVIOUS_CYCLE>`` unless ``tag`` is False. HEAD declares RELEASE_CYCLE with the record
    ``after`` and CHANGELOG.md ``changelog`` when given."""
    _git(tmp_path, "init", "-q")
    perf = tmp_path / "artifacts" / "benchmarks" / "performance"
    perf.mkdir(parents=True, exist_ok=True)
    (tmp_path / "jnwb").mkdir(exist_ok=True)
    (tmp_path / "jnwb" / "__init__.py").write_text(f"__version__ = '{PREVIOUS_CYCLE}'\n",
                                                   encoding="utf-8")
    if before is not None:
        where = tmp_path / before_dir if before_dir is not None else perf
        where.mkdir(parents=True, exist_ok=True)
        (where / "peak_memory.json").write_text(_record(PREVIOUS_CYCLE, before), encoding="utf-8")
    _commit(tmp_path, "the previous release")
    if tag:
        _git(tmp_path, "tag", f"v{PREVIOUS_CYCLE}")
    (tmp_path / "jnwb" / "__init__.py").write_text(f"__version__ = '{RELEASE_CYCLE}'\n",
                                                   encoding="utf-8")
    (perf / "peak_memory.json").write_text(_record(RELEASE_CYCLE, after), encoding="utf-8")
    if changelog is not None:
        # Bytes, not text: a text-mode write on Windows commits CRLF, and a CRLF heading never matches.
        (tmp_path / "CHANGELOG.md").write_bytes(changelog.encode("utf-8"))
    _commit(tmp_path, "the release")
    return tmp_path


def _growth(root):
    from scripts.release_gate import peak_memory_growth_violations
    return peak_memory_growth_violations(root)


KEY = "jrsa_200x40_200perm"


def test_thirty_percent_and_six_mib_fails(tmp_path):
    root = _growth_tree(tmp_path, before={KEY: 20.0}, after={KEY: 26.0})
    assert 26.0 - 20.0 > 0.20 * 20.0 and 26.0 - 20.0 >= 5.0, "the fixture must exceed both bounds"
    v = _growth(root)
    assert len(v) == 1, v
    assert KEY in v[0] and "20.0" in v[0] and "26.0" in v[0] and "30.0%" in v[0], v
    assert f"name the operation in CHANGELOG.md's {RELEASE_CYCLE} section" in v[0], v


def test_thirty_percent_and_four_mib_passes(tmp_path):
    root = _growth_tree(tmp_path, before={KEY: 13.5}, after={KEY: 17.5})
    assert 17.5 - 13.5 > 0.20 * 13.5 and 17.5 - 13.5 < 5.0, "over the fraction, under the floor"
    assert _growth(root) == []


def test_fifteen_percent_and_fifty_mib_passes(tmp_path):
    root = _growth_tree(tmp_path, before={KEY: 333.5}, after={KEY: 383.5})
    assert 383.5 - 333.5 >= 5.0 and 383.5 - 333.5 <= 0.20 * 333.5, "over the floor, under the fraction"
    assert _growth(root) == []


def test_thirty_percent_and_six_mib_with_the_operation_in_the_declared_section_passes(tmp_path):
    from scripts.release_body import changelog_section
    changelog = _changelog((RELEASE_CYCLE, f"- `{KEY}` keeps one more block of trials: +6 MiB."))
    assert KEY in changelog_section(changelog, RELEASE_CYCLE), "the fixture must name the key"
    root = _growth_tree(tmp_path, before={KEY: 20.0}, after={KEY: 26.0}, changelog=changelog)
    assert _growth(root) == []


def test_a_reason_in_another_versions_section_does_not_count(tmp_path):
    from scripts.release_body import changelog_section
    changelog = _changelog((RELEASE_CYCLE, "- Peak memory measured again."),
                           (PREVIOUS_CYCLE, f"- `{KEY}` keeps one more block of trials."))
    assert KEY not in changelog_section(changelog, RELEASE_CYCLE), "the key is in the wrong section"
    root = _growth_tree(tmp_path, before={KEY: 20.0}, after={KEY: 26.0}, changelog=changelog)
    v = _growth(root)
    assert len(v) == 1 and KEY in v[0], v


def test_a_longer_operation_name_in_the_section_is_not_a_reason(tmp_path):
    from scripts.release_body import changelog_section
    changelog = _changelog((RELEASE_CYCLE, f"- `{KEY}_v2` keeps one more block of trials."))
    assert KEY in changelog_section(changelog, RELEASE_CYCLE), "the fixture must contain the prefix"
    root = _growth_tree(tmp_path, before={KEY: 20.0}, after={KEY: 26.0}, changelog=changelog)
    v = _growth(root)
    assert len(v) == 1 and KEY in v[0], v


def test_no_previous_tag_fails_closed(tmp_path):
    root = _growth_tree(tmp_path, before={KEY: 20.0}, after={KEY: 20.0}, tag=False)
    assert _git(root, "tag", "--list") == "", "the fixture must carry no tag"
    v = _growth(root)
    assert len(v) == 1 and "no release tag" in v[0] and RELEASE_CYCLE in v[0], v


def test_a_previous_tag_without_the_record_fails_closed(tmp_path):
    from scripts.release_gate import PEAK_MEMORY_PATH
    root = _growth_tree(tmp_path, before=None, after={KEY: 20.0})
    assert _git(root, "tag", "--list") == f"v{PREVIOUS_CYCLE}", "the fixture must be tagged"
    absent = subprocess.run(["git", "-C", str(root), "cat-file", "-e",
                             f"v{PREVIOUS_CYCLE}:{PEAK_MEMORY_PATH}"], capture_output=True)
    assert absent.returncode != 0, "the fixture must leave the record out of the tag"
    v = _growth(root)
    assert len(v) == 1 and f"v{PREVIOUS_CYCLE}" in v[0] and "absent" in v[0], v


def test_a_previous_release_with_the_record_at_its_old_path_is_compared(tmp_path):
    """Releases up to v0.2.12 kept the record one directory up."""
    from scripts.release_gate import PEAK_MEMORY_PATH_BEFORE_0_2_13
    root = _growth_tree(tmp_path, before={KEY: 20.0}, after={KEY: 26.0},
                        before_dir="artifacts/benchmarks")
    kept = subprocess.run(["git", "-C", str(root), "cat-file", "-e",
                           f"v{PREVIOUS_CYCLE}:{PEAK_MEMORY_PATH_BEFORE_0_2_13}"], capture_output=True)
    assert kept.returncode == 0, "the fixture must hold the record at the old path"
    v = _growth(root)
    assert len(v) == 1 and KEY in v[0] and "30.0%" in v[0], v


def test_an_operation_added_or_removed_is_not_reported(tmp_path):
    before, after = {"old_op": 10.0, KEY: 20.0}, {"new_op": 900.0, KEY: 20.0}
    root = _growth_tree(tmp_path, before=before, after=after)
    assert set(before) ^ set(after) == {"old_op", "new_op"}, "the fixture must add and remove one"
    assert _growth(root) == []


def test_the_readiness_gate_reports_the_growth(tmp_path):
    """The growth check sits in STEP 0a's condition 4, so a violation refuses the release."""
    root = _growth_tree(tmp_path, before={KEY: 20.0}, after={KEY: 26.0})
    v = check_release_readiness(root)
    assert any(KEY in x and "CHANGELOG.md" in x for x in v), v


def test_the_gate_reads_the_record_the_instrument_writes():
    from scripts.measure_peak_memory import RECORD_PATH
    from scripts.release_gate import PEAK_MEMORY_PATH

    assert RECORD_PATH.relative_to(REPO_ROOT).as_posix() == PEAK_MEMORY_PATH


def test_only_the_unrecorded_one_of_two_deleted_items_is_named(tmp_path):
    v = _relabel(tmp_path, [_item("99-930", REQUIRED), _item("99-934", REQUIRED),
                            _item("99-931", DEFERRED)],
                 [_item("99-931", DEFERRED)], finished="99-934")
    assert len(v) == 1 and "1 todo item(s)" in v[0] and v[0].endswith(": 99-930"), v


def test_an_unchanged_held_item_is_condition_2s_to_refuse(tmp_path):
    items = [_item("99-930", REQUIRED), _item("99-931", DEFERRED)]
    v = _relabel(tmp_path, items, items)
    assert len(v) == 1 and "still required" in v[0] and "99-930" in v[0], v


def test_an_item_added_after_the_receipt_is_judged_by_condition_2(tmp_path):
    assert _relabel(tmp_path, [_item("99-930", REQUIRED)], [_item("99-932", DEFERRED)],
                    finished="99-930") == []


@pytest.mark.parametrize("absent", ["receipt", "head"])
def test_a_todo_stack_absent_at_either_commit_fails(tmp_path, absent):
    items = [_item("99-931", DEFERRED)]
    v = _relabel(tmp_path, None if absent == "receipt" else items,
                 None if absent == "head" else items)
    where = "the receipt's commit" if absent == "receipt" else "at HEAD"
    assert any("does not exist" in x and where in x for x in v), v


def test_a_todo_stack_unreadable_at_the_receipt_commit_fails(tmp_path):
    v = _relabel(tmp_path, [f"### 99-930: A colon\n\nRelease: {REQUIRED}.\n"],
                 [_item("99-930", DEFERRED)])
    assert len(v) == 1 and "cannot be read" in v[0] and "receipt's commit" in v[0], v


def test_a_missing_todo_stack_fails(tmp_path):
    """Deleting the stack must not read as zero required items."""
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)])
    (root / "artifacts" / "todo_stack.md").unlink()
    _commit(root, "delete the todo stack")
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "todo_stack.md is missing" in v[0], v


def _roadmap_row(ident="12-09", waits="a reason", release=f"deferred-{AFTER_NEXT}"):
    return f"| {ident} | a theme | a defect | {waits} | {release} |"


def test_a_readable_roadmap_row_deferred_past_this_cycle_passes(tmp_path):
    root = _tree(tmp_path, items=[_item("07-01", DEFERRED)], roadmap=_roadmap(_roadmap_row()))
    assert check_release_readiness(root, head=HEAD) == []


def test_a_roadmap_row_deferred_to_this_cycle_is_refused(tmp_path):
    root = _tree(tmp_path, roadmap=_roadmap(_roadmap_row(release=f"deferred-{RELEASE_CYCLE}")))
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and f"not later than {RELEASE_CYCLE}" in v[0], v


def test_a_roadmap_id_also_in_the_todo_stack_is_refused(tmp_path):
    root = _tree(tmp_path, items=[_item("12-09", DEFERRED)], roadmap=_roadmap(_roadmap_row()))
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "12-09 is also in artifacts/todo_stack.md" in v[0], v


@pytest.mark.parametrize("row", [
    f"| 12-09 | a theme | a defect | deferred-{AFTER_NEXT} |",
    _roadmap_row(waits=""),
    _roadmap_row(ident="12-9a"),
], ids=["no-waits-cell", "empty-waits", "bad-id"])
def test_an_unreadable_roadmap_row_is_refused(tmp_path, row):
    root = _tree(tmp_path, roadmap=_roadmap(row))
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "is not a readable row" in v[0], v


@pytest.mark.parametrize("marker", [
    "Required for 0.2.11",
    "required-0.2.11",
], ids=["prose-marker", "release-marker"])
def test_a_roadmap_row_marking_work_required_is_refused(marker):
    rows, refused = roadmap_rows(_roadmap(f"| 12-09 | a theme | {marker} | a reason | "
                                          f"deferred-{AFTER_NEXT} |"))
    assert len(rows) == 1 and len(refused) == 1 and "marks work required" in refused[0], refused


def test_a_roadmap_id_repeated_inside_the_roadmap_is_refused():
    row = _roadmap_row()
    rows, refused = roadmap_rows(_roadmap(row, row))
    assert len(rows) == 2 and refused == ["12-09 appears twice"], refused


def test_the_live_roadmap_parses_without_refusal():
    """The committed roadmap, read by the parser STEP 0a runs, against the live todo stack."""
    text = (REPO_ROOT / ROADMAP_PATH).read_text(encoding="utf-8")
    stack_ids = {ident for ident, _, _ in todo_release_fields(REPO_ROOT)}
    refused = roadmap_rows(text, stack_ids)[1]
    assert refused == [], refused


def test_a_missing_roadmap_fails(tmp_path):
    """Deleting the roadmap must not read as no deferred work."""
    root = _tree(tmp_path, roadmap=None)
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and "roadmap.md is missing at HEAD" in v[0], v


def test_a_roadmap_edit_after_the_receipt_commit_is_stale(tmp_path):
    """The closure pass judged the roadmap too, so only the receipt and the todo stack may follow."""
    root, passed = _repository(tmp_path)
    _record_receipt(root, passed)
    (root / "artifacts" / "roadmap.md").write_text(_roadmap(_roadmap_row()), encoding="utf-8")
    head = _commit(root, "a roadmap row the closure pass never read")
    v = check_release_readiness(root, head=head)
    assert len(v) == 1 and "1 file(s) other than the receipt" in v[0] and "roadmap.md" in v[0], v


def test_a_receipt_cannot_be_tied_to_an_unresolved_head(tmp_path):
    root = _tree(tmp_path)
    v = check_release_readiness(root, head=None)
    assert len(v) == 1 and "HEAD could not be resolved" in v[0], v


@pytest.mark.parametrize("found", [1, 2])
def test_a_receipt_reporting_new_blockers_fails(tmp_path, found):
    root = _tree(tmp_path, found=found)
    v = check_release_readiness(root, head=HEAD)
    assert len(v) == 1 and f"found {found} new release-blocking" in v[0], v


def test_the_fixpoint_is_new_blockers_and_not_new_observations(tmp_path):
    """A closure pass that files fifty deferred observations and zero blockers still closes."""
    root = _tree(tmp_path, items=[_item(f"07-{n}", DEFERRED) for n in range(1, 51)], found=0)
    assert check_release_readiness(root, head=HEAD) == []


def test_the_receipt_parser_reads_nothing_from_an_absent_receipt():
    commit, found = blocker_fixpoint_receipt(pathlib.Path("/nonexistent-tree"))
    assert commit is None and found is None


# --- the live tree -----------------------------------------------------------------------------

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
