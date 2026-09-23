"""Gate 2 must tell a second checkout apart from a second skill tree.

Recorded as P-27. Gate 2 globs ``SKILL.md`` off the filesystem rather than off the git index, so
every agent worktree under ``.claude/worktrees/`` read as a duplicate skill tree. It failed early:
the harness gate aborted at gate 2 and gates 3 through 13 never ran, turning one false positive
into twelve unrun checks and a red suite for the whole duration of any fan-out.

The repair must not be "ignore what git ignores". A duplicate skill tree that is merely untracked
is still a tree an agent can read, which is exactly the hazard gate 2 exists to catch. So these
tests are a pair, and the pair is the point: the worktree must pass and the plain duplicate must
still fail. A repair that only satisfies the first is a hole.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
# Appended, never prepended: `tests/test_the_suite_can_qualify_an_installed_copy.py` requires that
# no test module put the checkout ahead of the package under test, so the suite can be run against
# an installed copy. `scripts/` ships in no wheel, so appending is enough to import the gate.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

import scripts.harness_gate as harness_gate  # noqa: E402
from scripts.harness_gate import (  # noqa: E402
    EPHEMERAL_ROOT_DIRS,
    TOOL_ROOT_DIRS,
    _is_checkout_of,
    check_root_allowlist,
    check_skill_tree_uniqueness,
)

_GIT_ENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")}


def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=jnwb-test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, env=_GIT_ENV,
    )


def _repository(root: pathlib.Path) -> pathlib.Path:
    """A real repository with one commit, so `git worktree add` has something to check out."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "commit", "-q", "--allow-empty", "-m", "init")
    return root


def _worktree(repo: pathlib.Path, where: str) -> pathlib.Path:
    """A real linked worktree of ``repo`` at ``repo / where``."""
    target = repo / where
    target.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", "--detach", str(target))
    return target


def _shaped_like_a_checkout(dot_git: pathlib.Path) -> bool:
    """The predicate gate 2 used before 06-137, kept here only to prove each counterfeit below
    would have fooled it. A case that fails this is not a discriminator for that defect."""
    if dot_git.is_dir():
        return (dot_git / "HEAD").is_file()
    if dot_git.is_file():
        return dot_git.read_text(encoding="utf-8").startswith("gitdir:")
    return False


def _tree_with_a_skill(root: pathlib.Path, where: str) -> pathlib.Path:
    """Write a canonical skills/ tree plus one SKILL.md at ``where``, and return the second."""
    canonical = root / "skills" / "jnwb-canonical"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text("# canonical\n", encoding="utf-8")

    second = root / where
    second.mkdir(parents=True)
    skill = second / "SKILL.md"
    skill.write_text("# second\n", encoding="utf-8")
    return skill


def test_a_plain_duplicate_tree_still_fails(tmp_path):
    """The hazard gate 2 was built for. Nothing below may weaken this."""
    _tree_with_a_skill(tmp_path, "docs/skills/jnwb-elsewhere")

    violations = check_skill_tree_uniqueness(tmp_path)

    assert len(violations) == 1, violations
    assert "docs/skills/jnwb-elsewhere/SKILL.md" in violations[0]


def test_an_untracked_duplicate_tree_still_fails(tmp_path):
    """Untracked is not the test. An agent reads the filesystem, not the index."""
    _tree_with_a_skill(tmp_path, "scratch/skills/jnwb-untracked")
    (tmp_path / ".gitignore").write_text("scratch/\n", encoding="utf-8")

    violations = check_skill_tree_uniqueness(tmp_path)

    assert len(violations) == 1, violations
    assert "scratch/skills/jnwb-untracked/SKILL.md" in violations[0]


def test_a_linked_worktree_of_this_repository_does_not_fail(tmp_path):
    """The case the exemption exists for, built by ``git worktree add`` rather than by hand.

    Until 06-137 this fixture wrote ``gitdir: /elsewhere/...`` into a file and required the gate
    to excuse it: the missing-``gitdir:`` counterfeit below, named after a worktree.
    """
    repo = _repository(tmp_path / "repo")
    worktree = _worktree(repo, ".claude/worktrees/agent-a")
    skill = _tree_with_a_skill(repo, ".claude/worktrees/agent-a/skills/jnwb-canonical")

    assert (worktree / ".git").is_file() and skill.is_file()
    assert check_skill_tree_uniqueness(repo) == []


def _zero_byte_head(repo: pathlib.Path):
    (repo / "docs" / ".git").mkdir(parents=True)
    (repo / "docs" / ".git" / "HEAD").write_bytes(b"")
    return repo / "docs" / ".git", "docs/skills/dup"


def _gitdir_to_nowhere(repo: pathlib.Path):
    missing = repo.parent / "no-such-admin-dir"
    (repo / ".claude").mkdir()
    (repo / ".claude" / ".git").write_text(f"gitdir: {missing.as_posix()}\n", encoding="utf-8")
    assert not missing.exists()
    return repo / ".claude" / ".git", ".claude/skills/dup"


def _unrelated_repository(repo: pathlib.Path):
    (repo / ".claude").mkdir()
    _git(repo / ".claude", "init", "-q")
    return repo / ".claude" / ".git", ".claude/skills/dup"


def _worktree_without_commondir(repo: pathlib.Path):
    worktree = _worktree(repo, ".claude/worktrees/agent-a")
    (repo / ".git" / "worktrees" / "agent-a" / "commondir").unlink()
    return worktree / ".git", ".claude/worktrees/agent-a/skills/dup"


def _nested_clone(repo: pathlib.Path):
    clone = repo / "docs" / "clone"
    _git(repo, "clone", "-q", str(repo), str(clone))
    return clone / ".git", "docs/clone/skills/dup"


def _empty_directory(repo: pathlib.Path):
    (repo / "docs" / ".git").mkdir(parents=True)
    return repo / "docs" / ".git", "docs/skills/dup"


def _file_without_gitdir(repo: pathlib.Path):
    (repo / "docs").mkdir()
    (repo / "docs" / ".git").write_text("not a gitdir pointer\n", encoding="utf-8")
    return repo / "docs" / ".git", "docs/skills/dup"


@pytest.mark.parametrize(
    "build, fools_shape",
    [
        pytest.param(_zero_byte_head, True, id="A-zero-byte-HEAD"),
        pytest.param(_gitdir_to_nowhere, True, id="B-gitdir-to-a-missing-path"),
        pytest.param(_unrelated_repository, True, id="C-unrelated-git-init"),
        pytest.param(_worktree_without_commondir, True, id="D1-worktree-commondir-deleted"),
        pytest.param(_nested_clone, True, id="nested-clone"),
        pytest.param(_empty_directory, False, id="empty-dir"),
        pytest.param(_file_without_gitdir, False, id="file-without-gitdir"),
    ],
)
def test_a_git_entry_that_is_not_a_worktree_of_this_repository_stays_in_scope(tmp_path, build, fools_shape):
    """The other half of the pair. Each case is built exactly as named, inside a real repository.

    A shape test accepted the first five (``fools_shape``): a directory holding ``HEAD``, or a
    file starting ``gitdir:``. git accepts none of them as a worktree of the root's repository.
    A nested clone has its own object store, so it is a second tree an agent can read rather than
    this one seen twice, and git cannot tell a clone of this repository from an unrelated one.
    The root is a real repository so that a rejection comes from comparing against it, not from
    a root git cannot read.
    """
    repo = _repository(tmp_path / "repo")
    dot_git, where = build(repo)
    _tree_with_a_skill(repo, where)

    assert _shaped_like_a_checkout(dot_git) is fools_shape, "the fixture is not the case it names"
    violations = check_skill_tree_uniqueness(repo)

    assert len(violations) == 1, violations
    assert f"{where}/SKILL.md" in violations[0] and "DUPLICATE_SKILL_TREE" in violations[0]


def test_a_duplicate_inside_a_nested_checkout_is_still_that_checkouts_business(tmp_path):
    """Gate 2 declines the whole nested worktree, including a bad tree within it.

    That is correct rather than a gap: the nested checkout runs its own gate 2 over itself, and a
    gate that reported another checkout's defects would report them against the wrong repository.
    """
    repo = _repository(tmp_path / "repo")
    _worktree(repo, ".claude/worktrees/agent-a")
    _tree_with_a_skill(repo, ".claude/worktrees/agent-a/docs/skills/jnwb-elsewhere")

    assert check_skill_tree_uniqueness(repo) == []


def test_without_git_nothing_is_excused_and_the_gate_says_why(tmp_path, monkeypatch):
    """git unavailable is an unknown, reported as one, never answered from the entry's shape."""
    repo = _repository(tmp_path / "repo")
    _worktree(repo, ".claude/worktrees/agent-a")
    _tree_with_a_skill(repo, ".claude/worktrees/agent-a/skills/jnwb-canonical")

    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(harness_gate.subprocess, "run", no_git)
    violations = check_skill_tree_uniqueness(repo)

    assert len(violations) == 2, violations
    assert ".claude/worktrees/agent-a/skills/jnwb-canonical/SKILL.md" in violations[0]
    assert violations[1].startswith("GIT_UNAVAILABLE")


def test_a_duplicate_under_dot_claude_that_is_not_a_checkout_still_fails(tmp_path):
    """The reason ``.claude`` is not in EPHEMERAL_ROOT_DIRS.

    ``.claude/skills/`` is a real location an agent reads skills from. Excusing the whole
    directory would have been the smaller edit and would have opened exactly the hole gate 2
    exists to close.
    """
    _tree_with_a_skill(tmp_path, ".claude/skills/jnwb-canonical")

    violations = check_skill_tree_uniqueness(tmp_path)

    assert len(violations) == 1, violations
    assert ".claude/skills/jnwb-canonical/SKILL.md" in violations[0]


def test_dot_claude_is_a_tool_dir_not_an_ephemeral_one():
    """Pins the split, so a later tidy-up cannot merge the two sets and reopen the hole."""
    assert TOOL_ROOT_DIRS == {".claude"}
    assert not (TOOL_ROOT_DIRS & EPHEMERAL_ROOT_DIRS)


def test_gate_4_tolerates_the_tool_directory(tmp_path):
    """Gate 4 failed on ``.claude`` only once gate 2 stopped aborting ahead of it."""
    (tmp_path / ".claude" / "worktrees").mkdir(parents=True)

    assert [v for v in check_root_allowlist(tmp_path) if ".claude" in v] == []


@pytest.mark.parametrize(
    "dot_git_is_a_file",
    [pytest.param(True, id="linked-worktree"), pytest.param(False, id="ordinary-clone")],
)
def test_gate_4_accepts_dot_git_whichever_type_it_is(tmp_path, dot_git_is_a_file):
    """`.git` is the checkout marker, and its type varies by checkout kind.

    Allowlisted only as a directory, it made gate 4 reject every linked worktree and abort
    before gates 5 through 13. Three packets reported the same red suite independently. Both
    checkouts are real: gate 4 allowlists the root's own `.git` by name, and the fixture named
    after a worktree was a hand-written `gitdir:` file until 06-137.
    """
    repo = _repository(tmp_path / "repo")
    root = _worktree(repo, str(tmp_path / "agent-a")) if dot_git_is_a_file else repo

    assert (root / ".git").is_file() is dot_git_is_a_file
    assert [v for v in check_root_allowlist(root) if ".git" in v] == []


def test_gate_4_still_rejects_an_unknown_root_file(tmp_path):
    """The `.git` exemption is one name, not a widening of the file allowlist."""
    (tmp_path / "leftover.txt").write_text("x", encoding="utf-8")

    assert any("leftover.txt" in v for v in check_root_allowlist(tmp_path))


def test_gate_4_still_rejects_an_unknown_root_directory(tmp_path):
    """The allowlist widened by exactly one name, not into a policy of tolerance."""
    (tmp_path / "sneaky").mkdir()

    violations = check_root_allowlist(tmp_path)

    assert any("sneaky" in v for v in violations), violations


def test_the_live_repository_passes_even_while_worktrees_exist():
    """The regression itself: this must hold whether or not a fan-out is running right now."""
    assert check_skill_tree_uniqueness(REPO_ROOT) == []


def test_every_live_worktree_is_a_real_checkout():
    """Guards the assumption the skip rests on, so it cannot rot silently.

    If the fan-out ever created worktree directories without a ``.git`` entry, the skip above
    would stop firing and gate 2 would fail again -- but for a reason nothing here explains.
    """
    listed = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if listed.returncode != 0:
        pytest.skip("git worktree list unavailable")

    roots = [
        pathlib.Path(line.split(" ", 1)[1])
        for line in listed.stdout.splitlines()
        if line.startswith("worktree ")
    ]
    nested = [r for r in roots if r.resolve() != REPO_ROOT and REPO_ROOT in r.resolve().parents]
    for root in nested:
        # `git worktree list` keeps reporting a worktree whose directory has been deleted until
        # `git worktree prune` succeeds, and on Windows the prune can fail on a locked admin file
        # while the checkout itself is long gone. A listing entry is not the invariant; a
        # directory on disk is. One that no longer exists holds no SKILL.md and is no hazard.
        if not root.exists():
            continue
        # The gate rests on `_is_checkout_of`, so this guard rests on the same predicate: a guard
        # on a weaker one (`.exists()`, then the shape of the entry) passed while the gate failed.
        assert _is_checkout_of(root, REPO_ROOT), (
            f"git does not report {root} as a worktree of this repository, so gate 2 would not skip it"
        )
