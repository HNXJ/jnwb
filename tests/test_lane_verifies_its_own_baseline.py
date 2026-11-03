"""A lane must establish the tree before reading it, and a distance is not a baseline.

The worktree provisioner branches lanes behind their stated baseline. Six lanes across two
waves each found HEAD at ``5ecc12eb`` and fast-forwarded; the reported distance went 192, 213,
216, ~220, and measures 232 from this tree today. **The number is not the defect, the fixed
base is** -- at that commit ``artifacts/goal.md`` and ``artifacts/problem_stack.md`` do not
exist, cited line numbers point at unrelated code, and nothing errors. Every lane so far caught
it independently, which is luck rather than a property of the system: a packet that trusted its
baseline would have measured the 0.1.8 tree and reported against it.

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
the checker already believes (a fixture must build the case it is named after).
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# append, never insert(0): the wheel leg must keep resolving the installed copy.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

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


# --------------------------------------------------------------------------------------
# The lane's state basis is current before the lane reads it.
# --------------------------------------------------------------------------------------

VERIFY = REPO_ROOT / "scripts" / "verify_lane.py"
PUSH = REPO_ROOT / "scripts" / "jnwb_push.sh"

#: Stands in for scripts/reconstruct_state.py where a test must regenerate: the real script runs
#: the harness and reads the network. Its --check reads the HEAD row the same way the real one does.
STATE_STUB = '''\
import os, pathlib, re, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / "artifacts" / "state.md"
ROW = re.compile(r"^\\| HEAD \\| `([0-9a-f]{40})` \\|$", re.MULTILINE)


def head():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


if "--check" in sys.argv:
    match = ROW.search(STATE.read_text(encoding="utf-8")) if STATE.exists() else None
    if match is None or match.group(1) != head():
        print("ERROR: artifacts/state.md is stale")
        sys.exit(1)
    print("PASS")
    sys.exit(0)
if os.environ.get("STUB_REGENERATION") == "fail":
    print("ERROR: regeneration failed")
    sys.exit(1)
STATE.parent.mkdir(parents=True, exist_ok=True)
STATE.write_text("| HEAD | `" + head() + "` |\\n", encoding="utf-8")
print("wrote artifacts/state.md")
'''


def _state_lane(tmp_path, state_script=None):
    """A committed repository holding scripts/reconstruct_state.py: the real script unless a stand-in is given."""
    repo = tmp_path / "lane"
    (repo / "scripts").mkdir(parents=True)
    text = state_script
    if text is None:
        text = (REPO_ROOT / "scripts" / "reconstruct_state.py").read_text(encoding="utf-8")
    (repo / "scripts" / "reconstruct_state.py").write_text(text, encoding="utf-8")
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "a.txt", "scripts/reconstruct_state.py")
    _git(repo, "commit", "-q", "-m", "fixture")
    return repo


def _plant_state(repo, sha):
    """artifacts/state.md recording `sha` as its HEAD: the one row the check reads."""
    (repo / "artifacts").mkdir(exist_ok=True)
    (repo / "artifacts" / "state.md").write_text(f"| HEAD | `{sha}` |\n", encoding="utf-8")


def _run_verify(repo, *args, extra_env=None):
    env = dict(os.environ, **(extra_env or {}))
    return subprocess.run(
        [sys.executable, VERIFY.as_posix(), *args], cwd=str(repo), env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
    )


def test_a_current_state_is_reported_current(tmp_path):
    repo = _state_lane(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    _plant_state(repo, head)
    proc = _run_verify(repo, "--baseline", head, "--allow-main-tree")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "LANE OK" in proc.stdout and "state: current" in proc.stdout, proc.stdout


def test_a_stale_state_is_regenerated_then_checked_again(tmp_path):
    repo = _state_lane(tmp_path, STATE_STUB)
    head = _git(repo, "rev-parse", "HEAD")
    _plant_state(repo, "1" * 40)  # a planted HEAD that is not the tree's HEAD
    assert "1" * 40 != head
    proc = _run_verify(repo, "--baseline", head, "--allow-main-tree")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "state: regenerated" in proc.stdout, proc.stdout
    assert head in (repo / "artifacts" / "state.md").read_text(encoding="utf-8")


def test_a_missing_state_is_regenerated(tmp_path):
    """The state file is gitignored, so a fresh lane has none: the case every lane starts in."""
    repo = _state_lane(tmp_path, STATE_STUB)
    head = _git(repo, "rev-parse", "HEAD")
    assert not (repo / "artifacts" / "state.md").exists()
    proc = _run_verify(repo, "--baseline", head, "--allow-main-tree")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "state: regenerated" in proc.stdout, proc.stdout


def test_a_state_still_stale_after_regeneration_fails_by_name(tmp_path):
    repo = _state_lane(tmp_path, STATE_STUB)
    head = _git(repo, "rev-parse", "HEAD")
    _plant_state(repo, "1" * 40)
    proc = _run_verify(repo, "--baseline", head, "--allow-main-tree",
                       extra_env={"STUB_REGENERATION": "fail"})
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "LANE:" in proc.stdout and "after regeneration" in proc.stdout, proc.stdout
    assert "LANE OK" not in proc.stdout, "a lane whose state is stale may not report OK"


# --------------------------------------------------------------------------------------
# A push for a named todo item may carry only that item's Writes (and the always-writable paths).
# --------------------------------------------------------------------------------------

ITEM = "18-901"
ORIGIN_TODO = """\
# 0.2.16

### 18-901 Fixture item

Writes: `scripts/a.py`, `tests/**/*.py`.
- Fixture body.

### 18-902 Fixture neighbour

Writes: `scripts/b.py`.
- Fixture body.
"""
#: The local commit deletes the finished item, as a real push does: the Writes must still be read
#: from the target, where the item still stands.
FINISHED_TODO = """\
# 0.2.16

### 18-902 Fixture neighbour

Writes: `scripts/b.py`.
- Fixture body.
"""


def _bash():
    """Git for Windows bash; a bare `bash` can resolve to the WSL launcher."""
    if sys.platform != "win32":
        return "bash"
    git_bash = pathlib.Path("C:/Program Files/Git/usr/bin/bash.exe")
    if not git_bash.exists():
        pytest.skip("Git for Windows bash not found")
    return git_bash.as_posix()


def _push_lane(tmp_path, change):
    """A bare origin at dev holding ORIGIN_TODO, and a clone one local commit past it.

    `change(repo)` edits the clone and returns the paths it changed. A passing suite stamp is planted
    at the local HEAD, so the only gate left to decide is the item's Writes. The remote is a local
    bare repository: nothing contacts GitHub, and the CI helpers are stubs in a fake HOME.
    """
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", bare.as_posix())
    repo = tmp_path / "clone"
    (repo / "artifacts").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / "artifacts" / "todo_stack.md").write_text(ORIGIN_TODO, encoding="utf-8")
    (repo / "scripts" / "a.py").write_text("A = 1\n", encoding="utf-8")
    (repo / "scripts" / "b.py").write_text("B = 1\n", encoding="utf-8")
    # The push runs the checker the repository carries, so the clone carries the real one.
    (repo / "scripts" / "verify_lane.py").write_text(VERIFY.read_text(encoding="utf-8"),
                                                     encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/dev")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "artifacts/todo_stack.md", "scripts/a.py", "scripts/b.py",
         "scripts/verify_lane.py")
    _git(repo, "commit", "-q", "-m", "origin state")
    _git(repo, "remote", "add", "origin", bare.as_posix())
    _git(repo, "push", "-q", "origin", "dev")
    origin_sha = _git(repo, "rev-parse", "HEAD")
    changed = change(repo)
    _git(repo, "add", "--", *changed)
    _git(repo, "commit", "-q", "-m", "local change")
    head = _git(repo, "rev-parse", "HEAD")
    (repo / ".git" / "jnwb_suite_ok").write_text(head, encoding="utf-8")
    bindir = tmp_path / "home" / ".claude" / "bin"
    bindir.mkdir(parents=True)
    (bindir / "ci_inflight.py").write_text("print(0)\n", encoding="utf-8")
    (bindir / "ci_last_conclusion.py").write_text('print("success")\n', encoding="utf-8")
    return repo, bare, origin_sha, head


def _run_push(tmp_path, repo, *args):
    env = dict(os.environ)
    env["HOME"] = (tmp_path / "home").as_posix()
    env["PATH"] = os.pathsep.join([str(pathlib.Path(sys.executable).parent), env.get("PATH", "")])
    env.pop("JNWB_PUSH_OVER_RED", None)
    return subprocess.run(
        [_bash(), PUSH.as_posix(), repo.as_posix(), "dev", *args], cwd=str(repo), env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, timeout=300,
    )


def test_a_push_for_an_item_refuses_a_path_outside_its_writes(tmp_path):
    def change(repo):
        (repo / "scripts" / "a.py").write_text("A = 2\n", encoding="utf-8")
        (repo / "scripts" / "other.py").write_text("O = 1\n", encoding="utf-8")
        (repo / "scripts" / "b.py").write_text("B = 2\n", encoding="utf-8")
        return ["scripts/a.py", "scripts/other.py", "scripts/b.py"]

    repo, bare, origin_sha, _head = _push_lane(tmp_path, change)
    proc = _run_push(tmp_path, repo, "--item", ITEM)
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    listed = [line.strip() for line in proc.stdout.splitlines()]
    assert "scripts/other.py" in listed and "scripts/b.py" in listed, out
    assert "scripts/a.py" not in listed, "a path inside the Writes was named as outside"
    assert _git(bare, "rev-parse", "refs/heads/dev") == origin_sha, "a refused push reached the remote"


def test_a_push_for_an_item_passes_a_diff_inside_its_writes(tmp_path):
    def change(repo):
        (repo / "scripts" / "a.py").write_text("A = 2\n", encoding="utf-8")
        (repo / "tests" / "sub").mkdir(parents=True)
        (repo / "tests" / "sub" / "test_c.py").write_text(
            "def test_c():\n    assert True\n", encoding="utf-8")
        (repo / "artifacts" / "changelog.d").mkdir(parents=True)
        (repo / "artifacts" / "changelog.d" / "fixture.fixed.md").write_text(
            "- Fixture.\n", encoding="utf-8")
        (repo / "artifacts" / "todo_stack.md").write_text(FINISHED_TODO, encoding="utf-8")
        return ["scripts/a.py", "tests/sub/test_c.py",
                "artifacts/changelog.d/fixture.fixed.md", "artifacts/todo_stack.md"]

    repo, bare, _origin_sha, head = _push_lane(tmp_path, change)
    proc = _run_push(tmp_path, repo, "--item", ITEM)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert f"Writes of {ITEM}" in proc.stdout, "the check ran but named nothing it examined: " + out
    assert _git(bare, "rev-parse", "refs/heads/dev") == head, out


def test_a_push_for_several_items_joins_their_writes(tmp_path):
    def change(repo):
        (repo / "scripts" / "a.py").write_text("A = 2\n", encoding="utf-8")
        (repo / "scripts" / "b.py").write_text("B = 2\n", encoding="utf-8")
        return ["scripts/a.py", "scripts/b.py"]

    repo, bare, _origin_sha, head = _push_lane(tmp_path, change)
    proc = _run_push(tmp_path, repo, "--item", f"{ITEM},18-902")
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert _git(bare, "rev-parse", "refs/heads/dev") == head, out


def test_a_push_for_an_unknown_item_is_refused_by_name(tmp_path):
    def change(repo):
        (repo / "scripts" / "a.py").write_text("A = 2\n", encoding="utf-8")
        return ["scripts/a.py"]

    repo, bare, origin_sha, _head = _push_lane(tmp_path, change)
    proc = _run_push(tmp_path, repo, "--item", "18-999")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "18-999" in proc.stdout, out
    assert _git(bare, "rev-parse", "refs/heads/dev") == origin_sha, "a refused push reached the remote"


def test_a_push_without_an_item_is_unchanged(tmp_path):
    """No --item: the Writes check is off, so a path outside any item's Writes still pushes."""
    def change(repo):
        (repo / "scripts" / "a.py").write_text("A = 2\n", encoding="utf-8")
        (repo / "scripts" / "other.py").write_text("O = 1\n", encoding="utf-8")
        return ["scripts/a.py", "scripts/other.py"]

    repo, bare, _origin_sha, head = _push_lane(tmp_path, change)
    proc = _run_push(tmp_path, repo)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert _git(bare, "rev-parse", "refs/heads/dev") == head, out
