"""A release commit must contain ``main``: ``main_ancestry_violations`` over real git repositories.

The compliant repository (``dev`` is ``main`` plus a commit) passes; the diverged one (``main``
carries a commit ``dev`` lacks) fails. A check that always returned no violation would pass the
first case, and one that always returned a violation would pass the second, so both are asserted.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.release_gate import main_ancestry_violations  # noqa: E402


def _git(root: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   cwd=root, check=True, capture_output=True)


def _commit(root: pathlib.Path, name: str) -> None:
    (root / name).write_text(name, encoding="utf-8")
    _git(root, "add", name)
    _git(root, "commit", "-m", name)


def _repo(tmp_path: pathlib.Path, main_extra: bool) -> pathlib.Path:
    _git(tmp_path, "init", "-b", "main")
    _commit(tmp_path, "base")
    _git(tmp_path, "checkout", "-b", "dev")
    _commit(tmp_path, "dev_work")
    if main_extra:
        _git(tmp_path, "checkout", "main")
        _commit(tmp_path, "main_only")
        _git(tmp_path, "checkout", "dev")
    return tmp_path


def test_a_release_commit_that_contains_main_passes(tmp_path):
    assert main_ancestry_violations(_repo(tmp_path, main_extra=False)) == []


def test_a_release_commit_missing_a_commit_on_main_fails(tmp_path):
    violations = main_ancestry_violations(_repo(tmp_path, main_extra=True))
    assert len(violations) == 1 and "not an ancestor" in violations[0]


def _release_merge(tmp_path: pathlib.Path, dev_absorbs_main: bool) -> pathlib.Path:
    """``dev`` merged into ``main`` with a merge commit, as a release does; HEAD is that merge."""
    root = _repo(tmp_path, main_extra=True)
    if dev_absorbs_main:
        _git(root, "merge", "--no-ff", "-m", "dev takes main", "main")
    _git(root, "checkout", "main")
    _git(root, "merge", "--no-ff", "-m", "release", "dev")
    return root


def test_a_release_merge_whose_dev_contains_the_old_main_passes(tmp_path):
    assert main_ancestry_violations(_release_merge(tmp_path, dev_absorbs_main=True)) == []


def test_a_release_merge_whose_dev_lacks_a_commit_of_the_old_main_fails(tmp_path):
    violations = main_ancestry_violations(_release_merge(tmp_path, dev_absorbs_main=False))
    assert len(violations) == 1
    assert "old main" in violations[0] and "not an ancestor" in violations[0]


def test_a_repository_with_no_main_is_refused_as_unknown(tmp_path):
    _git(tmp_path, "init", "-b", "trunk")
    _commit(tmp_path, "base")
    violations = main_ancestry_violations(tmp_path)
    assert len(violations) == 1 and "unknown" in violations[0]
