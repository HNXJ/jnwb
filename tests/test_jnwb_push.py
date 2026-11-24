"""scripts/jnwb_push.sh pushes a branch only when CI ran at origin's tip of it and every run there succeeded.

The CI reads go to a local HTTP server standing in for the Actions API (`JNWB_CI_API`), and the
remote is a local bare repository, so nothing contacts GitHub or a real remote. The in-flight
helper is a stub in a fake HOME.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# Appended, not prepended: prepending would put the checkout's jnwb/ ahead of an installed copy.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))  # needed: the installed-wheel run clears pythonpath

from scripts.gates.boundary import git  # noqa: E402

PUSH = REPO_ROOT / "scripts" / "jnwb_push.sh"
CI_GATE = REPO_ROOT / "scripts" / "ci_gate.py"
OLDER_SHA = "b" * 40


def _bash() -> str:
    """Git for Windows bash; a bare `bash` can resolve to the WSL launcher."""
    if sys.platform != "win32":
        return "bash"
    git_bash = pathlib.Path("C:/Program Files/Git/usr/bin/bash.exe")
    if not git_bash.exists():
        pytest.skip("Git for Windows bash not found")
    return git_bash.as_posix()


def _git(cwd: pathlib.Path, *args: str) -> str:
    proc = git(*args, cwd=str(cwd))
    proc.check_returncode()
    return (proc.stdout or "").strip()


def _ref(bare: pathlib.Path, branch: str = "dev"):
    """The sha of the branch in the bare remote, or None when the remote lacks it."""
    proc = git("rev-parse", "-q", "--verify", f"refs/heads/{branch}", cwd=bare)
    return proc.stdout.strip() if proc.returncode == 0 else None


@pytest.fixture
def ci_api():
    """A local stand-in for the Actions runs endpoint. `state` sets the status, body and paths read."""
    state = {"status": 200, "body": b'{"workflow_runs": []}', "paths": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["paths"].append(self.path)
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(state["body"])

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield state, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _repo(tmp_path: pathlib.Path, *, remote_has_dev: bool = True, branch: str = "dev",
          message: str = "two"):
    """A jnwb-style clone on ``branch``, one commit ahead of origin's, with the suite stamp at HEAD.

    The remote's branch holds the first commit, the tip CI must have run on, unless ``remote_has_dev``
    is false. The local origin ref names that commit either way, so the wrapper has a diff to read.
    HEAD's commit message is ``message``. Returns (repo, bare, tip, head).
    """
    bin_dir = tmp_path / "home" / ".claude" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "ci_inflight.py").write_text("print(0)\n", encoding="utf-8")
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", bare.as_posix())
    repo = tmp_path / "_temp_ci"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "one")
    tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "remote", "add", "origin", bare.as_posix())
    if remote_has_dev:
        _git(repo, "push", "-q", bare.as_posix(), f"HEAD:refs/heads/{branch}")
    _git(repo, "update-ref", f"refs/remotes/origin/{branch}", tip)
    (repo / "README.md").write_text("y\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", message)
    head = _git(repo, "rev-parse", "HEAD")
    assert head != tip, "the fixture must leave HEAD ahead of origin's dev"
    (repo / ".git" / "jnwb_suite_ok").write_text(head + "\n", encoding="utf-8")
    return repo, bare, tip, head


def _run(name: str, sha: str, conclusion, status: str = "completed", run_id=None) -> dict:
    run = {"name": name, "head_sha": sha, "conclusion": conclusion, "status": status,
           "created_at": "2026-11-02T18:56:16Z"}
    if run_id is not None:
        run["id"] = run_id
    return run


def _body(runs: list) -> bytes:
    return json.dumps({"total_count": len(runs), "workflow_runs": runs}).encode("utf-8")


def _run_push(tmp_path, repo, api_url, *, override: bool = False, branch: str = "dev"):
    env = dict(os.environ)
    env["HOME"] = (tmp_path / "home").as_posix()
    env["PATH"] = os.pathsep.join([str(pathlib.Path(sys.executable).parent), env.get("PATH", "")])
    env["JNWB_CI_API"] = api_url
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    env.pop("JNWB_PUSH_OVER_RED", None)
    if override:
        env["JNWB_PUSH_OVER_RED"] = "1"
    return subprocess.run(
        [_bash(), PUSH.as_posix(), repo.as_posix(), branch], cwd=str(repo), env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, timeout=300,
    )


@pytest.mark.parametrize("order", ["success_first", "failure_first"])
def test_a_failed_run_beside_a_green_run_at_the_tip_refuses(tmp_path, ci_api, order):
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path)
    dashboard, ci = _run("dashboard", tip, "success"), _run("CI/CD", tip, "failure")
    state["body"] = _body([dashboard, ci] if order == "success_first" else [ci, dashboard])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "refusing" in out, out
    assert _ref(bare) == tip, "a refused push reached the remote"


def test_two_green_runs_at_the_tip_pass(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, tip, head = _repo(tmp_path)
    state["body"] = _body([_run("dashboard", tip, "success"), _run("CI/CD", tip, "success")])
    proc = _run_push(tmp_path, repo, url)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _ref(bare) == head, "the passing push did not reach the remote"


@pytest.mark.parametrize("order", ["older_first", "older_last"])
def test_green_runs_at_an_older_sha_do_not_authorize_the_tip(tmp_path, ci_api, order):
    """The defect of 2026-11-16: CI green at 9252d0cd passed the gate while origin/dev was fabe3c02."""
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path)
    older = [_run("CI/CD", OLDER_SHA, "success"), _run("dashboard", OLDER_SHA, "success")]
    state["body"] = _body(older if order == "older_first" else older[::-1])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert f"no run at the branch tip {tip[:8]}" in out, out
    assert _ref(bare) == tip, "green runs at an older sha let a push through"


@pytest.mark.parametrize("at_tip, older, passes", [
    ("success", "failure", True),
    ("failure", "success", False),
])
@pytest.mark.parametrize("order", ["tip_first", "older_first"])
def test_only_the_tip_decides(tmp_path, ci_api, at_tip, older, passes, order):
    state, url = ci_api
    repo, bare, tip, head = _repo(tmp_path)
    runs = [_run("CI/CD", tip, at_tip), _run("CI/CD", OLDER_SHA, older)]
    state["body"] = _body(runs if order == "tip_first" else runs[::-1])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert (proc.returncode == 0) is passes, out
    assert _ref(bare) == (head if passes else tip), out


def test_a_cancelled_run_at_the_tip_refuses(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path)
    state["body"] = _body([_run("dashboard", tip, "success"), _run("CI/CD", tip, "cancelled")])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert _ref(bare) == tip, "a push beside a cancelled run reached the remote"


@pytest.mark.parametrize("status", ["in_progress", "queued"])
def test_a_run_not_completed_at_the_tip_refuses(tmp_path, ci_api, status):
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path)
    state["body"] = _body([_run("CI/CD", tip, None, status=status), _run("dashboard", tip, "success")])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "not completed" in out, out
    assert _ref(bare) == tip, "a push beside a run still pending reached the remote"


def test_the_gate_asks_for_the_runs_at_the_tip_whatever_their_status(tmp_path, ci_api):
    """A `status=completed` filter hides a pending run from the gate, and a query without the tip
    lets the newest run of any sha decide."""
    state, url = ci_api
    repo, bare, tip, head = _repo(tmp_path)
    state["body"] = _body([_run("CI/CD", tip, "success")])
    proc = _run_push(tmp_path, repo, url)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _ref(bare) == head
    assert state["paths"], "the wrapper never read the CI stand-in"
    for path in state["paths"]:
        assert f"head_sha={tip}" in path, path
        assert "status=" not in path, path


def test_no_run_listed_refuses(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path)
    state["body"] = _body([])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert _ref(bare) == tip, "a push with no CI run listed reached the remote"


def test_a_branch_the_remote_does_not_hold_refuses(tmp_path, ci_api):
    """With no dev on origin there is no tip a run could be at, whatever runs the API lists."""
    state, url = ci_api
    repo, bare, tip, head = _repo(tmp_path, remote_has_dev=False)
    state["body"] = _body([_run("CI/CD", tip, "success"), _run("CI/CD", head, "success")])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "origin has no dev" in out, out
    assert _ref(bare) is None, "a push to a branch with no CI-read tip reached the remote"


def test_a_second_ref_matching_the_branch_name_refuses(tmp_path, ci_api):
    """`git ls-remote origin refs/heads/dev` also lists refs/heads/a/refs/heads/dev, and lists it
    first; taking the first line would read CI at that ref's commit instead of dev's tip."""
    state, url = ci_api
    repo, bare, tip, head = _repo(tmp_path)
    _git(repo, "push", "-q", bare.as_posix(), "HEAD:refs/heads/a/refs/heads/dev")
    listed = _git(repo, "ls-remote", "origin", "refs/heads/dev").splitlines()
    assert len(listed) == 2 and listed[0].startswith(head), "the fixture must list the decoy ref first"
    state["body"] = _body([_run("CI/CD", head, "success")])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "more than one ref" in out, out
    assert _ref(bare) == tip, "green CI at a decoy ref's commit let a push through"


@pytest.mark.parametrize("count", [{"total_count": 101}, {}, {"total_count": "1"}, {"total_count": None}],
                         ids=["more_than_read", "missing", "a_string", "null"])
def test_a_list_of_runs_not_known_to_be_complete_refuses(tmp_path, ci_api, count):
    """A failed run past the first page would be invisible; without a total_count that the runs
    read account for, the gate answers unreadable."""
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path)
    state["body"] = json.dumps({**count, "workflow_runs": [_run("CI/CD", tip, "success")]}).encode("utf-8")
    proc = _run_push(tmp_path, repo, url, override=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "unreadable" in out, out
    assert _ref(bare) == tip, "a partly read list of runs let a push through"


def test_the_override_pushes_a_fix_whose_message_names_the_red_run(tmp_path, ci_api):
    """The override carries the push that fixes the failing run, its message naming that run."""
    state, url = ci_api
    repo, bare, tip, head = _repo(tmp_path, message="fix: repairs CI run 43990836160")
    state["body"] = _body([_run("CI/CD", tip, "failure", run_id=43990836160),
                           _run("dashboard", tip, "success", run_id=43990836161)])
    proc = _run_push(tmp_path, repo, url, override=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "pushing anyway (JNWB_PUSH_OVER_RED=1)" in out, out
    assert _ref(bare) == head


@pytest.mark.parametrize("message", ["two", "fix: repairs CI run 4399083616", "fix: run 143990836160"],
                         ids=["no_run", "id_prefix", "id_inside_longer_number"])
def test_the_override_refuses_a_push_whose_message_names_no_red_run(tmp_path, ci_api, message):
    """The variable alone cannot bypass a failed gate; HEAD's message must name the red run."""
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path, message=message)
    state["body"] = _body([_run("CI/CD", tip, "failure", run_id=43990836160)])
    proc = _run_push(tmp_path, repo, url, override=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "pushing anyway" not in out, out
    assert "43990836160" in out, out
    assert _ref(bare) == tip, "JNWB_PUSH_OVER_RED pushed over a failed gate without naming the run"


def test_the_override_refuses_a_red_run_without_an_id(tmp_path, ci_api):
    """A red run the answer gives no id for cannot be named, so the override cannot apply."""
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path, message="fix: repairs CI run None")
    state["body"] = _body([_run("CI/CD", tip, "failure")])
    proc = _run_push(tmp_path, repo, url, override=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "pushing anyway" not in out, out
    assert _ref(bare) == tip, "the override pushed over a red run it could not name"


def test_the_override_refuses_on_main(tmp_path, ci_api):
    """Main never takes a push over red, even one whose message names the run."""
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path, branch="main", message="fix: repairs CI run 43990836160")
    state["body"] = _body([_run("CI/CD", tip, "failure", run_id=43990836160)])
    proc = _run_push(tmp_path, repo, url, override=True, branch="main")
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "pushing anyway" not in out, out
    assert _ref(bare, "main") == tip, "JNWB_PUSH_OVER_RED pushed over a failed gate on main"


def test_the_override_refuses_a_tip_with_no_run(tmp_path, ci_api):
    """A3: the override covers a completed red run at the tip. A tip no run covers refuses, even with it set."""
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path)
    state["body"] = _body([_run("CI/CD", OLDER_SHA, "failure"), _run("dashboard", OLDER_SHA, "success")])
    proc = _run_push(tmp_path, repo, url, override=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert f"no run at the branch tip {tip[:8]}" in out, out
    assert "pushing anyway" not in out, out
    assert _ref(bare) == tip, "the override pushed a tip that no CI run covers"


def test_the_override_refuses_a_pending_run(tmp_path, ci_api):
    """A3: a run still pending at the tip is not a red run; the override does not push over it."""
    state, url = ci_api
    repo, bare, tip, _head = _repo(tmp_path)
    state["body"] = _body([_run("CI/CD", tip, "failure"), _run("dashboard", tip, None, status="in_progress")])
    proc = _run_push(tmp_path, repo, url, override=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "not completed" in out, out
    assert "pushing anyway" not in out, out
    assert _ref(bare) == tip, "the override pushed over a run still pending at the tip"


def test_the_override_refuses_a_branch_the_remote_does_not_hold(tmp_path, ci_api):
    """A3: with no dev on origin no run can sit at its tip; the override does not push to it."""
    state, url = ci_api
    repo, bare, tip, head = _repo(tmp_path, remote_has_dev=False)
    state["body"] = _body([_run("CI/CD", tip, "success"), _run("CI/CD", head, "success")])
    proc = _run_push(tmp_path, repo, url, override=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "origin has no dev" in out, out
    assert _ref(bare) is None, "the override pushed to a branch with no CI-read tip"


@pytest.mark.parametrize("body", [b'{"message": "API rate limit exceeded"}', b"not json"])
def test_an_unreadable_response_refuses_even_with_the_override(tmp_path, ci_api, body):
    state, url = ci_api
    state["status"], state["body"] = 403, body
    repo, bare, tip, _head = _repo(tmp_path)
    proc = _run_push(tmp_path, repo, url, override=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "unreadable" in out, out
    assert _ref(bare) == tip, "an unreadable CI answer let a push through"


@pytest.mark.parametrize("tip", ["9252d0cd", "g" * 40, ""])
def test_ci_gate_refuses_a_tip_that_is_not_a_full_sha(ci_api, tip):
    """A short or malformed tip would match no run or the wrong one; the gate answers 2, unreadable."""
    state, url = ci_api
    state["body"] = _body([_run("CI/CD", OLDER_SHA, "success")])
    env = dict(os.environ)
    env["JNWB_CI_API"] = url
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    proc = subprocess.run([sys.executable, CI_GATE.as_posix(), "hnxj/jnwb", "dev", "--tip", tip],
                          env=env, capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert not state["paths"], "the gate read CI before it refused the tip"


def test_ci_gate_exits_3_for_a_red_run_and_1_for_no_run(ci_api):
    """The push wrapper overrides only exit 3 (a completed run that did not succeed), so the codes must differ."""
    state, url = ci_api
    env = dict(os.environ)
    env["JNWB_CI_API"] = url
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    red_tip = "a" * 40
    state["body"] = _body([_run("CI/CD", red_tip, "failure")])
    red = subprocess.run([sys.executable, CI_GATE.as_posix(), "hnxj/jnwb", "dev", "--tip", red_tip],
                         env=env, capture_output=True, text=True, timeout=60, check=False)
    assert red.returncode == 3, red.stdout + red.stderr
    state["body"] = _body([_run("CI/CD", OLDER_SHA, "failure")])
    none = subprocess.run([sys.executable, CI_GATE.as_posix(), "hnxj/jnwb", "dev", "--tip", red_tip],
                          env=env, capture_output=True, text=True, timeout=60, check=False)
    assert none.returncode == 1, none.stdout + none.stderr
