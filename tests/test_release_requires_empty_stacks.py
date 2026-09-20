"""Condition 3 of the release acceptance in ``AGENTS.md`` §11, as a check that can fail.

A release requires ``artifacts/todo_stack.md`` to hold no item and ``artifacts/problem_stack.md``
to hold no open problem. The check lives in ``scripts/release_gate.py`` rather than in
``harness_gate.py`` because both stacks are non-empty for almost all of a cycle: a gate that
fails every day teaches people to skip it.

These tests drive the check over constructed trees. Asserting only that the live tree currently
reports violations would pass just as well against a function that always returns one.
"""

from __future__ import annotations

import pathlib

from scripts.release_gate import (
    PROBLEM_DISPOSITIONS,
    check_stacks_are_empty,
    open_problems,
    remaining_todo_items,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_EMPTY_PROBLEM_STACK = """# Problem stack

## Open

| ID | Problem | Found by | Answered in |
|---|---|---|---|

## Closed

| ID | Problem | Disposition | Evidence |
|---|---|---|---|
| P-C1 | something that was real | `repaired` | a commit |
"""

_EMPTY_TODO_STACK = """# 0.2.7

Items are deleted when done.

## Acceptance
"""


def _write_stacks(root: pathlib.Path, problems: str, todos: str) -> None:
    (root / "artifacts").mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / "problem_stack.md").write_text(problems, encoding="utf-8")
    (root / "artifacts" / "todo_stack.md").write_text(todos, encoding="utf-8")


def test_two_empty_stacks_pass(tmp_path: pathlib.Path):
    _write_stacks(tmp_path, _EMPTY_PROBLEM_STACK, _EMPTY_TODO_STACK)
    assert check_stacks_are_empty(tmp_path) == []


def test_one_open_problem_fails(tmp_path: pathlib.Path):
    problems = _EMPTY_PROBLEM_STACK.replace(
        "|---|---|---|---|\n\n## Closed",
        "|---|---|---|---|\n| P-01 | the thing is broken | a packet | nowhere |\n\n## Closed",
    )
    _write_stacks(tmp_path, problems, _EMPTY_TODO_STACK)
    violations = check_stacks_are_empty(tmp_path)
    assert violations, "an open problem did not fail the release check"
    assert "P-01" in violations[0]


def test_a_closed_problem_does_not_fail(tmp_path: pathlib.Path):
    """The ``## Closed`` section carries rows shaped exactly like open ones."""
    problems = _EMPTY_PROBLEM_STACK.replace(
        "| P-C1 | something that was real | `repaired` | a commit |",
        "| P-C1 | something that was real | `repaired` | a commit |\n"
        "| P-02 | accepted, cannot be repaired | `accepted` | a shipped artifact |",
    )
    _write_stacks(tmp_path, problems, _EMPTY_TODO_STACK)
    assert check_stacks_are_empty(tmp_path) == []


def test_one_remaining_todo_item_fails(tmp_path: pathlib.Path):
    todos = _EMPTY_TODO_STACK.replace(
        "## Acceptance", "### 07-01 Something not yet done\n\nRole: jnwb-developer.\n\n## Acceptance"
    )
    _write_stacks(tmp_path, _EMPTY_PROBLEM_STACK, todos)
    violations = check_stacks_are_empty(tmp_path)
    assert violations, "a remaining todo item did not fail the release check"
    assert "07-01" in violations[0]


def test_a_missing_problem_stack_fails_rather_than_passing(tmp_path: pathlib.Path):
    """Absence must not read as emptiness.

    Every block in gate 8 was once ``if <file>.exists():`` with no else, so an empty directory
    passed. A condition that is satisfied by deleting its own evidence is worse than no check.
    """
    (tmp_path / "artifacts").mkdir(parents=True)
    (tmp_path / "artifacts" / "todo_stack.md").write_text(_EMPTY_TODO_STACK, encoding="utf-8")
    violations = check_stacks_are_empty(tmp_path)
    assert violations and "missing" in violations[0]


def test_the_live_problem_stack_uses_only_the_declared_dispositions():
    text = (REPO_ROOT / "artifacts" / "problem_stack.md").read_text(encoding="utf-8")
    quoted = set(__import__("re").findall(r"^\| P-[^|]+\|[^|]+\|\s*`([^`]+)`\s*\|", text, __import__("re").M))
    unknown = sorted(quoted - set(PROBLEM_DISPOSITIONS))
    assert not unknown, f"disposition outside the declared set: {unknown}"


def test_the_live_stacks_are_readable_by_the_check():
    """Not an emptiness assertion -- both are non-empty mid-cycle, which is correct.

    This asserts only that the parsers find the live files and return something structured, so a
    formatting change that silently reduced either to zero rows is caught here rather than
    reading as a satisfied release condition.
    """
    assert remaining_todo_items(REPO_ROOT), "the todo stack parsed to zero items"
    assert open_problems(REPO_ROOT), "the problem stack parsed to zero open problems"
