"""scripts/jnwb_push.sh pushes only when every completed CI run at the newest SHA succeeded.

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
PUSH = REPO_ROOT / "scripts" / "jnwb_push.sh"
OLDER_SHA = "b" * 40

#: The helper the wrapper used to call, with its first-completed-run logic, against the same API.
#: The unfixed wrapper runs it, so the planted cases reproduce the old decision on this fixture.
STUB_HELPER = '''\
import json, os, sys, urllib.request
base = os.environ["JNWB_CI_API"]
repo, branch = sys.argv[1], sys.argv[2]
url = f"{base}/repos/{repo}/actions/runs?branch={branch}&status=completed&per_page=20"
data = json.load(urllib.request.urlopen(url, timeout=30))
runs = [x for x in data["workflow_runs"] if x["conclusion"] not in ("cancelled", "skipped")]
print("none -" if not runs else f"{runs[0]['conclusion']} {runs[0]['head_sha'][:8]}")
'''


def _bash() -> str:
    """Git for Windows bash; a bare `bash` can resolve to the WSL launcher."""
    if sys.platform != "win32":
        return "bash"
    git_bash = pathlib.Path("C:/Program Files/Git/usr/bin/bash.exe")
    if not git_bash.exists():
        pytest.skip("Git for Windows bash not found")
    return git_bash.as_posix()


def _git(cwd: pathlib.Path, *args: str) -> str:
    proc = subprocess.run(("git",) + args, cwd=str(cwd), capture_output=True, text=True, check=True)
    return (proc.stdout or "").strip()


def _ref(bare: pathlib.Path):
    """The sha of dev in the bare remote, or None when the remote has no dev."""
    proc = subprocess.run(("git", "rev-parse", "-q", "--verify", "refs/heads/dev"), cwd=str(bare),
                          capture_output=True, text=True)
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


def _repo(tmp_path: pathlib.Path):
    """A jnwb-style clone on dev whose origin/dev is HEAD, so the push has no artifacts-only diff to stamp."""
    bin_dir = tmp_path / "home" / ".claude" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "ci_inflight.py").write_text("print(0)\n", encoding="utf-8")
    (bin_dir / "ci_last_conclusion.py").write_text(STUB_HELPER, encoding="utf-8")
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", bare.as_posix())
    repo = tmp_path / "_temp_ci"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/dev")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "one")
    _git(repo, "remote", "add", "origin", bare.as_posix())
    _git(repo, "update-ref", "refs/remotes/origin/dev", "HEAD")
    return repo, bare


def _run(name: str, sha: str, conclusion: str) -> dict:
    return {"name": name, "head_sha": sha, "conclusion": conclusion, "status": "completed",
            "created_at": "2026-11-02T18:56:16Z"}


def _body(runs: list) -> bytes:
    return json.dumps({"total_count": len(runs), "workflow_runs": runs}).encode("utf-8")


def _run_push(tmp_path, repo, api_url, *, override: bool = False):
    env = dict(os.environ)
    env["HOME"] = (tmp_path / "home").as_posix()
    env["PATH"] = os.pathsep.join([str(pathlib.Path(sys.executable).parent), env.get("PATH", "")])
    env["JNWB_CI_API"] = api_url
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    env.pop("JNWB_PUSH_OVER_RED", None)
    if override:
        env["JNWB_PUSH_OVER_RED"] = "1"
    return subprocess.run(
        [_bash(), PUSH.as_posix(), repo.as_posix(), "dev"], cwd=str(repo), env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, timeout=300,
    )


@pytest.mark.parametrize("order", ["success_first", "failure_first"])
def test_a_failed_run_beside_a_green_run_at_the_newest_sha_refuses(tmp_path, ci_api, order):
    state, url = ci_api
    repo, bare = _repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    dashboard, ci = _run("dashboard", head, "success"), _run("CI/CD", head, "failure")
    state["body"] = _body([dashboard, ci] if order == "success_first" else [ci, dashboard])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "refusing" in out, out
    assert _ref(bare) is None, "a refused push reached the remote"


def test_two_green_runs_at_the_newest_sha_pass(tmp_path, ci_api):
    state, url = ci_api
    repo, bare = _repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("dashboard", head, "success"), _run("CI/CD", head, "success")])
    proc = _run_push(tmp_path, repo, url)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _ref(bare) == head, "the passing push did not reach the remote"


@pytest.mark.parametrize("newest, older, passes", [
    ("success", "failure", True),
    ("failure", "success", False),
])
def test_only_the_newest_sha_decides(tmp_path, ci_api, newest, older, passes):
    state, url = ci_api
    repo, bare = _repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", head, newest), _run("CI/CD", OLDER_SHA, older)])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert (proc.returncode == 0) is passes, out
    assert (_ref(bare) == head) is passes, out


def test_a_cancelled_run_at_the_newest_sha_refuses(tmp_path, ci_api):
    state, url = ci_api
    repo, bare = _repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("dashboard", head, "success"), _run("CI/CD", head, "cancelled")])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert _ref(bare) is None, "a push beside a cancelled run reached the remote"


def test_no_completed_run_listed_refuses(tmp_path, ci_api):
    state, url = ci_api
    repo, bare = _repo(tmp_path)
    state["body"] = _body([])
    proc = _run_push(tmp_path, repo, url)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert _ref(bare) is None, "a push with no CI run listed reached the remote"


def test_the_override_pushes_over_a_red_run(tmp_path, ci_api):
    state, url = ci_api
    repo, bare = _repo(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", head, "failure"), _run("dashboard", head, "success")])
    proc = _run_push(tmp_path, repo, url, override=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "pushing anyway (JNWB_PUSH_OVER_RED=1)" in out, out
    assert _ref(bare) == head


@pytest.mark.parametrize("body", [b'{"message": "API rate limit exceeded"}', b"not json"])
def test_an_unreadable_response_refuses_even_with_the_override(tmp_path, ci_api, body):
    state, url = ci_api
    state["status"], state["body"] = 403, body
    repo, bare = _repo(tmp_path)
    proc = _run_push(tmp_path, repo, url, override=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert "unreadable" in out, out
    assert _ref(bare) is None, "an unreadable CI answer let a push through"
