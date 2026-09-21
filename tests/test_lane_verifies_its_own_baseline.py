"""A lane must establish the tree before reading it, and a distance is not a baseline.

The worktree provisioner branches lanes behind their stated baseline. Six lanes across two
waves each found HEAD at ``5ecc12eb`` and fast-forwarded; the reported distance went 192, 213,
216, ~220, and measures 232 from this tree today. **The number is not the defect, the fixed
base is** -- at that commit ``artifacts/goal.md`` and ``artifacts/problem_stack.md`` do not
exist, cited line numbers point at unrelated code, and nothing errors. Every lane so far caught
it independently, which is luck rather than a property of the system: a packet that trusted its
baseline would have measured the 0.1.8 tree and reported against it (P-28, P-153).

Two things are pinned here that prose could not enforce:

* **A distance is refused outright.** A packet quoting "216 commits behind" names a figure that
  was already stale when written -- one packet stated 213 against a baseline two commits later
  than the figure was measured from, and the lane measured 216. Only the commit is stable.
* **The two drift directions are told apart.** HEAD behind the baseline is the provisioning
  defect and wants a fast-forward; HEAD ahead of it is a stale packet, where a fast-forward
  would do nothing. Reporting one as the other sends the lane to run a no-op and believe it
  fixed something, which is the confident-wrong-answer class this repository keeps producing.
  The first draft of the checker did exactly that: it printed "0 commit(s) ahead of HEAD" for a
  baseline that was 232 commits *behind*, and advised a merge.

The behind-direction fixture is a real two-commit repository rather than a mock, because the
condition under test is what git reports about ancestry, and a mock would agree with whatever
the checker already believes (P-144's family: a fixture must build the case it is named after).
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# append, never insert(0): the wheel leg must keep resolving the installed copy.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.verify_lane import check, in_linked_worktree  # noqa: E402


def _git(cwd: pathlib.Path, *args: str) -> str:
    proc = subprocess.run(
        ("git",) + args, cwd=str(cwd), capture_output=True, text=True, check=True
    )
    return (proc.stdout or "").strip()


@pytest.fixture
def two_commit_repo(tmp_path):
    """A repository with two commits, so `older` is a real ancestor of `newer`.

    Returns (path, older_sha, newer_sha) with the working tree checked out at `older`, which is
    the state a mis-provisioned lane is actually in.
    """
    repo = tmp_path / "lane"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "one")
    older = _git(repo, "rev-parse", "HEAD")
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "two")
    newer = _git(repo, "rev-parse", "HEAD")
    assert older != newer
    _git(repo, "checkout", "-q", older)
    assert _git(repo, "rev-parse", "HEAD") == older
    return repo, older, newer


# --------------------------------------------------------------------------------------
# A distance is not a baseline.
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("distance", ["192", "213", "216", "232", "0"])
def test_a_commit_count_is_refused_as_a_baseline(distance):
    problems = check(distance, allow_main_tree=True)
    assert problems, f"{distance!r} was accepted as a baseline"
    assert "is a distance, not a commit" in problems[0], problems


def test_the_refusal_explains_why_a_distance_cannot_work():
    problems = check("216", allow_main_tree=True)
    assert "stale the moment the dispatcher commits again" in problems[0]


def test_a_branch_name_is_refused_because_a_ref_moves():
    """Two lanes given the same ref can start from different trees."""
    problems = check("dev", allow_main_tree=True)
    assert problems
    assert "not an object name" in problems[0], problems


# --------------------------------------------------------------------------------------
# The two drift directions call for opposite actions and must be told apart.
# --------------------------------------------------------------------------------------

def test_a_tree_behind_its_baseline_is_named_as_the_provisioning_defect(two_commit_repo):
    repo, older, newer = two_commit_repo
    problems = check(newer, allow_main_tree=True, cwd=repo)
    assert problems, "a tree one commit behind its baseline passed"
    message = problems[0]
    assert "BEHIND" in message, message
    assert "1 commit(s) BEHIND" in message, message
    assert "provisioning defect" in message, message
    assert f"git merge --ff-only {newer}" in message, message
    assert "reset --hard" in message, "the rule against reset must travel with the advice"


def test_a_tree_ahead_of_its_baseline_is_named_as_a_stale_packet(two_commit_repo):
    repo, older, newer = two_commit_repo
    _git(repo, "checkout", "-q", newer)
    problems = check(older, allow_main_tree=True, cwd=repo)
    assert problems
    message = problems[0]
    assert "AHEAD" in message, message
    assert "stale packet" in message, message
    assert "a fast-forward would do nothing" in message, message


def test_the_two_directions_do_not_share_a_message(two_commit_repo):
    """The defect the first draft had: one message served both, advising a no-op merge."""
    repo, older, newer = two_commit_repo
    behind = check(newer, allow_main_tree=True, cwd=repo)[0]
    _git(repo, "checkout", "-q", newer)
    ahead = check(older, allow_main_tree=True, cwd=repo)[0]
    assert behind != ahead
    assert ("merge --ff-only" in behind) and ("merge --ff-only" not in ahead), (
        "a fast-forward must be advised only in the direction where it does something"
    )


def test_a_tree_at_its_baseline_passes(two_commit_repo):
    """The negative case, without which every assertion above is satisfied by always failing."""
    repo, older, _newer = two_commit_repo
    assert check(older, allow_main_tree=True, cwd=repo) == []


def test_a_baseline_absent_from_the_tree_is_reported_as_absent(two_commit_repo):
    repo, _older, _newer = two_commit_repo
    problems = check("0" * 40, allow_main_tree=True, cwd=repo)
    assert problems
    assert "not an object in this tree" in problems[0], problems


# --------------------------------------------------------------------------------------
# Isolation: a fan-out must not land in the main checkout.
# --------------------------------------------------------------------------------------

def test_the_main_checkout_is_refused_by_default(two_commit_repo):
    repo, older, _newer = two_commit_repo
    problems = check(older, cwd=repo)  # allow_main_tree defaults to False
    assert any("main checkout" in p for p in problems), problems
    assert any("exactly one writable agent" in p for p in problems), problems


def test_the_main_checkout_can_be_permitted_deliberately(two_commit_repo):
    """An integrator that is knowingly the single writer is not blocked."""
    repo, older, _newer = two_commit_repo
    assert check(older, allow_main_tree=True, cwd=repo) == []


def test_a_fresh_repository_is_detected_as_not_a_linked_worktree(two_commit_repo):
    repo, _older, _newer = two_commit_repo
    assert in_linked_worktree(repo) is False


def test_this_checkout_is_classified_without_raising():
    """Whichever tree the suite runs in, the classifier must answer rather than throw.

    The installed-wheel leg runs outside a git tree entirely, where `git rev-parse` fails; the
    check must read that as "not a linked worktree" rather than propagating.
    """
    assert in_linked_worktree(REPO_ROOT) in (True, False)
    assert in_linked_worktree(pathlib.Path(__file__).parent) in (True, False)
