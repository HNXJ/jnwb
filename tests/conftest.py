"""Suite-wide configuration.

A test marked ``requires_git_checkout`` reads this repository's own git data: tracked files,
ignore rules, the index's line endings, the HEAD commit. A source export (``git archive``, the
archive GitHub serves for a tag, a deposit made from one) has no ``.git``, so those tests skip
there instead of failing on a ``git`` call. In a clone or a linked worktree ``.git`` exists and
they run; a broken git installation then still fails them.

Mark a module with ``pytestmark = pytest.mark.requires_git_checkout`` when every test in it reads
git data, otherwise mark the tests that do. A test that builds its own repository in a temporary
directory needs no mark.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARK = "requires_git_checkout"


def is_git_checkout(root: Path = ROOT) -> bool:
    """True in a clone or a linked worktree, where ``.git`` is a directory or a file."""
    return (root / ".git").exists()


@pytest.fixture
def git_checkout_probe():
    """:func:`is_git_checkout`, for a test that exercises it without importing this file."""
    return is_git_checkout


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", f"{MARK}: reads this repository's git data; skipped where there is no .git"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if is_git_checkout():
        return
    skip = pytest.mark.skip(reason=f"no .git under {ROOT}: a source export has no git data")
    for item in items:
        if item.get_closest_marker(MARK) is not None:
            item.add_marker(skip)
