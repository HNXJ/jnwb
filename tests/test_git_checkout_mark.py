"""The ``requires_git_checkout`` mark skips only where there is no ``.git``."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARK = "requires_git_checkout"


def test_a_clone_and_a_linked_worktree_count_as_checkouts(
    tmp_path: Path, git_checkout_probe
) -> None:
    assert not git_checkout_probe(tmp_path), "a directory with no .git is an export"
    (tmp_path / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    assert git_checkout_probe(tmp_path), "a linked worktree's .git is a file"
    other = tmp_path / "clone"
    (other / ".git").mkdir(parents=True)
    assert git_checkout_probe(other)


@pytest.mark.requires_git_checkout
def test_a_marked_test_runs_in_a_checkout(
    request: pytest.FixtureRequest, git_checkout_probe
) -> None:
    """Collected here only when the hook left it alone, which it must in a checkout."""
    assert git_checkout_probe(ROOT)
    assert not list(request.node.iter_markers("skip")), "a checkout skipped a marked test"


def test_the_hook_skips_marked_tests_exactly_when_there_is_no_git(
    request: pytest.FixtureRequest, git_checkout_probe
) -> None:
    """Unmarked, so a hook that skipped everything could not hide this test with the rest."""
    marked = [item for item in request.session.items if item.get_closest_marker(MARK)]
    assert marked, "no collected test carries the mark"
    skipped = [item for item in marked if item.get_closest_marker("skip")]
    assert len(skipped) == (0 if git_checkout_probe(ROOT) else len(marked)), [
        item.nodeid for item in skipped
    ]


def test_the_mark_is_registered(pytestconfig: pytest.Config) -> None:
    assert any(line.startswith(f"{MARK}:") for line in pytestconfig.getini("markers"))
