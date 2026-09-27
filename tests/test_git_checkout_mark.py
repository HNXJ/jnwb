"""The ``requires_git_checkout`` mark skips only where there is no ``.git``."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import MARK, ROOT, is_git_checkout


def test_a_clone_and_a_linked_worktree_count_as_checkouts(tmp_path: Path) -> None:
    assert not is_git_checkout(tmp_path), "a directory with no .git is an export"
    (tmp_path / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    assert is_git_checkout(tmp_path), "a linked worktree's .git is a file"
    other = tmp_path / "clone"
    (other / ".git").mkdir(parents=True)
    assert is_git_checkout(other)


@pytest.mark.requires_git_checkout
def test_a_marked_test_runs_in_a_checkout(request: pytest.FixtureRequest) -> None:
    """Collected here only when the hook left it alone, which it must in a checkout."""
    assert is_git_checkout()
    assert (ROOT / ".git").exists()
    assert not [m for m in request.node.iter_markers("skip")], "a checkout skipped a marked test"


def test_the_mark_is_registered(pytestconfig: pytest.Config) -> None:
    assert any(line.startswith(f"{MARK}:") for line in pytestconfig.getini("markers"))
