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

from scripts.harness_gate import (  # noqa: E402
    EPHEMERAL_ROOT_DIRS,
    TOOL_ROOT_DIRS,
    check_root_allowlist,
    check_skill_tree_uniqueness,
)


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


@pytest.mark.parametrize(
    "dot_git_is_a_file",
    [pytest.param(True, id="linked-worktree"), pytest.param(False, id="nested-clone")],
)
def test_a_nested_checkout_does_not_fail(tmp_path, dot_git_is_a_file):
    """A linked worktree carries a ``.git`` file; a clone carries a ``.git`` directory."""
    skill = _tree_with_a_skill(tmp_path, ".claude/worktrees/agent-a/skills/jnwb-canonical")
    checkout_root = tmp_path / ".claude" / "worktrees" / "agent-a"

    if dot_git_is_a_file:
        (checkout_root / ".git").write_text("gitdir: /elsewhere/.git/worktrees/agent-a\n", encoding="utf-8")
    else:
        (checkout_root / ".git").mkdir()

    assert skill.is_file(), "the fixture must actually place a SKILL.md inside the checkout"
    assert check_skill_tree_uniqueness(tmp_path) == []


def test_a_duplicate_inside_a_nested_checkout_is_still_that_checkouts_business(tmp_path):
    """Gate 2 declines the whole nested checkout, including a bad tree within it.

    That is correct rather than a gap: the nested checkout runs its own gate 2 over itself, and a
    gate that reported another checkout's defects would report them against the wrong repository.
    """
    _tree_with_a_skill(tmp_path, ".claude/worktrees/agent-a/docs/skills/jnwb-elsewhere")
    (tmp_path / ".claude" / "worktrees" / "agent-a" / ".git").write_text("gitdir: x\n", encoding="utf-8")

    assert check_skill_tree_uniqueness(tmp_path) == []


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
    before gates 5 through 13. Three packets reported the same red suite independently.
    """
    if dot_git_is_a_file:
        (tmp_path / ".git").write_text("gitdir: /elsewhere/.git/worktrees/agent-a\n", encoding="utf-8")
    else:
        (tmp_path / ".git").mkdir()

    assert [v for v in check_root_allowlist(tmp_path) if ".git" in v] == []


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
        assert (root / ".git").exists(), f"{root} is a worktree with no .git entry"
