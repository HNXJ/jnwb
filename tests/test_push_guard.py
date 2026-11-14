"""scripts/push_guard.py denies a plain `git push` in a jnwb checkout, whatever its folder, and lets jnwb_push.sh through."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "push_guard.py"


def make_checkout(root: Path, jnwb: bool = True) -> Path:
    """A git checkout at root; with jnwb, it carries the content markers the guard reads."""
    (root / ".git").mkdir(parents=True)
    if jnwb:
        (root / "jnwb").mkdir()
        (root / "jnwb" / "__init__.py").write_text("", encoding="utf-8")
        (root / "scripts").mkdir()
        (root / "scripts" / "jnwb_push.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    return root


def run_guard(raw: str) -> str:
    out = subprocess.run([sys.executable, str(GUARD)], input=raw.encode("utf-8"), capture_output=True,
                         timeout=30, check=True).stdout.decode("utf-8")
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else "allow"


def decide(command: str, cwd: Path | str) -> str:
    return run_guard(json.dumps({"tool_name": "Bash", "tool_input": {"command": command},
                                 "cwd": Path(cwd).as_posix()}))


def test_a_plain_push_in_a_jnwb_checkout_is_denied_under_any_name(tmp_path):
    clone = make_checkout(tmp_path / "_temp_integ")
    assert decide("git push origin dev", clone) == "deny"
    assert decide(f'git -C "{clone.as_posix()}" push origin dev', tmp_path) == "deny"
    assert decide("git push origin dev", clone / "jnwb") == "deny"


@pytest.mark.skipif(os.name != "nt", reason="Git Bash drive paths exist only on Windows")
def test_a_git_bash_drive_path_names_the_same_checkout(tmp_path):
    clone = make_checkout(tmp_path / "_temp_msys")
    posix = clone.as_posix()
    msys = "/" + posix[0].lower() + posix[2:]
    assert decide(f"cd {msys} && git push origin dev", tmp_path) == "deny"
    assert decide(f"git -C {msys} push origin dev", tmp_path) == "deny"


def test_a_folder_named_jnwb_without_jnwb_content_is_not_denied(tmp_path):
    plain = make_checkout(tmp_path / "jnwb", jnwb=False)
    assert decide("git push origin dev", plain) == "allow"


def test_a_chain_with_the_wrapper_is_denied_when_another_segment_pushes(tmp_path):
    clone = make_checkout(tmp_path / "_temp_chain")
    other = make_checkout(tmp_path / "other", jnwb=False)
    wrapper = f'bash "{clone.as_posix()}/scripts/jnwb_push.sh" "{clone.as_posix()}" dev </dev/null'
    assert decide(wrapper, clone) == "allow"
    for sep in ("; ", " && ", " || ", " | ", "\n"):
        assert decide(wrapper + sep + "git push origin dev", clone) == "deny", repr(sep)
    assert decide(wrapper + "; git push origin _temp_a", clone) == "allow"
    assert decide(f'cd "{clone.as_posix()}" && git push origin dev', tmp_path) == "deny"
    assert decide(f'cd "{other.as_posix()}" && git push origin dev', clone) == "allow"


def run_guard_full(raw: bytes) -> dict:
    """The hook's whole reply. The guard must exit 0 and write nothing to stderr, whatever it reads."""
    proc = subprocess.run([sys.executable, str(GUARD)], input=raw, capture_output=True, timeout=30)
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert proc.stderr == b"", proc.stderr.decode("utf-8", "replace")
    return json.loads(proc.stdout.decode("utf-8")) if proc.stdout.strip() else {}


@pytest.mark.parametrize("raw", [
    b"not json, git push origin dev",
    b"\xff\xfe git push origin dev",
    json.dumps({"tool_input": ["git push origin dev"]}).encode("utf-8"),
])
def test_an_unreadable_payload_that_names_a_push_is_denied_with_a_message(raw):
    out = run_guard_full(raw)
    deny = out["hookSpecificOutput"]
    assert deny["permissionDecision"] == "deny", raw
    assert "could not read" in deny["permissionDecisionReason"], raw


@pytest.mark.parametrize("raw", [
    b"",
    b"not json, git status",
    b"[]",
    b'{"tool_input": ["git status"]}',
])
def test_an_unreadable_payload_that_names_no_push_is_let_through(raw):
    assert run_guard_full(raw) == {}, raw


@pytest.mark.parametrize("form", [
    "git --git-dir={clone}/.git push origin dev",
    "git --git-dir {clone}/.git push origin dev",
    "git --work-tree={clone} push origin dev",
    "git --work-tree {clone} push origin dev",
    "git --git-dir={clone}/.git --work-tree={clone} push origin dev",
    "git -c core.quotepath=off --git-dir={clone}/.git push origin dev",
    "git -C {elsewhere} --git-dir={clone}/.git push origin dev",
])
def test_a_push_naming_a_jnwb_checkout_by_git_dir_or_work_tree_is_denied(tmp_path, form):
    clone = make_checkout(tmp_path / "_temp_gitdir")
    elsewhere = make_checkout(tmp_path / "elsewhere", jnwb=False)
    command = form.format(clone=clone.as_posix(), elsewhere=elsewhere.as_posix())
    assert decide(command, elsewhere) == "deny", command
    assert decide(command, clone) == "deny", command


def test_a_git_dir_or_work_tree_outside_jnwb_and_a_non_push_pass(tmp_path):
    clone = make_checkout(tmp_path / "_temp_neg")
    other = make_checkout(tmp_path / "elsewhere", jnwb=False)
    assert decide(f"git --git-dir={other.as_posix()}/.git push origin dev", tmp_path) == "allow"
    assert decide(f"git --work-tree {other.as_posix()} push origin dev", tmp_path) == "allow"
    assert decide(f"git --git-dir={clone.as_posix()}/.git status", tmp_path) == "allow"


def test_a_push_of_temp_branches_only_passes(tmp_path):
    clone = make_checkout(tmp_path / "_temp_refs")
    assert decide("git push origin _temp_a _temp_b </dev/null", clone) == "allow"
    assert decide("git push -u origin +refs/heads/_temp_a:refs/heads/_temporary_a", clone) == "allow"
    assert decide("git push origin _temp_a dev", clone) == "deny"
    assert decide("git push origin _temp_a:dev", clone) == "deny"
    assert decide("git push origin", clone) == "deny"
    assert decide("git push --all origin _temp_a", clone) == "deny"
    assert decide("git push origin _temp_a && git push origin dev", clone) == "deny"


def test_pushes_elsewhere_and_other_git_commands_pass(tmp_path):
    clone = make_checkout(tmp_path / "_temp_other_refs")
    other = make_checkout(tmp_path / "other", jnwb=False)
    assert decide("git push origin dev", other) == "allow"
    assert decide(f'git -C "{other.as_posix()}" push', clone) == "allow"
    assert decide("git status", clone) == "allow"


@pytest.mark.parametrize("command", [
    "git --no-pager push origin dev",
    "git -P push origin dev",
    "git -p push origin dev",
    "git --no-optional-locks push origin dev",
    "git --no-pager --no-optional-locks push origin dev",
    "git.exe push origin dev",
    "git.exe --no-pager push origin dev",
])
def test_a_push_with_another_global_option_or_git_exe_is_denied_in_a_jnwb_checkout(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_spellings")
    assert decide(command, clone) == "deny", command


@pytest.mark.parametrize("command", [
    'git --no-pager -C "{clone}" push origin dev',
    'git.exe -C "{clone}" push origin dev',
    'git -P --git-dir="{clone}/.git" push origin dev',
])
def test_a_push_with_another_global_option_or_git_exe_naming_a_jnwb_checkout_is_denied(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_spellings_dir")
    elsewhere = make_checkout(tmp_path / "elsewhere", jnwb=False)
    command = command.format(clone=clone.as_posix())
    assert decide(command, elsewhere) == "deny", command


def test_a_push_with_another_global_option_or_git_exe_that_is_temp_only_or_elsewhere_passes(tmp_path):
    clone = make_checkout(tmp_path / "_temp_spellings_allow")
    other = make_checkout(tmp_path / "other", jnwb=False)
    assert decide("git --no-pager push origin _temp_a", clone) == "allow"
    assert decide("git.exe push origin _temp_a _temp_b", clone) == "allow"
    assert decide("git --no-pager push origin dev", other) == "allow"
    assert decide("git.exe push origin dev", other) == "allow"
    assert decide("git --no-pager status", clone) == "allow"
    assert decide("git.exe status", clone) == "allow"


@pytest.mark.parametrize("command", [
    "git --namespace foo push origin dev",
    "git --namespace=foo push origin dev",
    "GIT push origin dev",
    "git.EXE push origin dev",
])
def test_namespace_and_case_spellings_cannot_bypass_guard(tmp_path, command):
    clone = make_checkout(tmp_path / "_temp_namespace")
    assert decide(command, clone) == "deny", command


# ---- 17-143: `jnwb_push.sh <dir> --tag vX.Y.Z` and the artifacts-only stack checks ---------------
#
# CI reads go to the local stand-in server of test_jnwb_push.py (`ci_api`); the remote is a local bare
# repository. The scaffold commit holds the real verify_lane.py and two stand-ins for the stack checks
# (gate 15 and the item-length test), so each refusal below is caused by the case under test.

from tests.test_jnwb_push import OLDER_SHA, _body, _git, _run, ci_api  # noqa: F401  (fixture)

PUSH_SH = Path(__file__).resolve().parents[1] / "scripts" / "jnwb_push.sh"
VERIFY_LANE = Path(__file__).resolve().parents[1] / "scripts" / "verify_lane.py"
TODO_WITH_ITEM = """# 0.2.17

### 17-900 A demo item

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: {writes}
- 17-900: demo.
"""
PASS_STUB = "import sys\nsys.exit(0)\n"
FAIL_STUB = "import sys\nprint('stub gate failed')\nsys.exit(1)\n"
ITEM_TEST_PASS = "def test_ok():\n    assert True\n"
ITEM_TEST_FAIL = "def test_ok():\n    assert False\n"


def _bash_path() -> str:
    if sys.platform != "win32":
        return "bash"
    git_bash = Path("C:/Program Files/Git/usr/bin/bash.exe")
    if not git_bash.exists():
        pytest.skip("Git for Windows bash not found")
    return git_bash.as_posix()


def _remote_ref(bare: Path, ref: str):
    proc = subprocess.run(["git", "rev-parse", "-q", "--verify", ref], cwd=str(bare),
                          capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _scaffold(tmp_path: Path, *, writes: str = "`artifacts/todo_stack.md`",
              gate_stub: str = PASS_STUB, item_test: str = ITEM_TEST_PASS):
    """A clone whose origin dev and main both hold the scaffold; returns (repo, bare, home)."""
    home = tmp_path / "home"
    (home / ".claude" / "bin").mkdir(parents=True)
    (home / ".claude" / "bin" / "ci_inflight.py").write_text("print(0)\n", encoding="utf-8")
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", bare.as_posix())
    repo = tmp_path / "_temp_stack"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/dev")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "remote", "add", "origin", bare.as_posix())
    (repo / "scripts").mkdir()
    (repo / "scripts" / "verify_lane.py").write_bytes(VERIFY_LANE.read_bytes())
    (repo / "scripts" / "harness_gate.py").write_text(gate_stub, encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_stack_item_length.py").write_text(item_test, encoding="utf-8")
    (repo / "artifacts").mkdir()
    (repo / "artifacts" / "todo_stack.md").write_text(TODO_WITH_ITEM.format(writes=writes),
                                                      encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "scaffold")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-q", bare.as_posix(), "HEAD:refs/heads/dev", "HEAD:refs/heads/main")
    _git(repo, "update-ref", "refs/remotes/origin/dev", head)
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    return repo, bare, home


def _wrapper(repo: Path, home: Path, api_url: str, *args: str, extra_env: dict | None = None):
    env = dict(os.environ)
    env["HOME"] = home.as_posix()
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])
    env["JNWB_CI_API"] = api_url
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    env.pop("JNWB_PUSH_OVER_RED", None)
    env.update(extra_env or {})
    return subprocess.run([_bash_path(), PUSH_SH.as_posix(), repo.as_posix(), *args],
                          cwd=str(repo), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=600)


def _commit_artifacts_only(repo: Path, text: str = "\n- note 17-900\n") -> None:
    todo = repo / "artifacts" / "todo_stack.md"
    todo.write_text(todo.read_text(encoding="utf-8") + text, encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "stack edit")


def test_tag_push_refuses_when_the_newest_main_run_is_not_at_the_tip(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    state["body"] = _body([_run("CI/CD", OLDER_SHA, "success")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "refusing" in out and "tip" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None, "a tag reached the remote without a run at its tip"


def test_tag_push_refuses_when_a_main_run_at_the_tip_failed(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    state["body"] = _body([_run("CI/CD", tip, "failure")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "refusing" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None


def test_tag_push_refuses_an_unreadable_main_answer(tmp_path, ci_api):
    state, url = ci_api
    state["status"], state["body"] = 403, b'{"message": "API rate limit exceeded"}'
    repo, bare, home = _scaffold(tmp_path)
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "unreadable" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None


@pytest.mark.parametrize("name", ["0.2.17", "v0.2", "v0.2.17-rc1", "release-1"])
def test_tag_name_must_be_vX_Y_Z(tmp_path, ci_api, name):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    state["body"] = _body([_run("CI/CD", tip, "success")])
    proc = _wrapper(repo, home, url, "--tag", name)
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "vX.Y.Z" in out, out
    assert _remote_ref(bare, "refs/tags/" + name) is None


def test_tag_push_pushes_the_tag_at_main_tip_when_the_tip_runs_succeeded(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    state["body"] = _body([_run("CI/CD", tip, "success"), _run("dashboard", tip, "success")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _remote_ref(bare, "refs/tags/v0.2.17") == tip


def test_tag_push_refuses_to_move_an_existing_tag(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    old_tip = _git(repo, "rev-parse", "origin/main")
    _git(repo, "push", "-q", bare.as_posix(), f"{old_tip}:refs/tags/v0.2.17")
    _commit_artifacts_only(repo, "\n- main moved\n")
    new_tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-q", bare.as_posix(), "HEAD:refs/heads/main")
    _git(repo, "update-ref", "refs/remotes/origin/main", new_tip)
    state["body"] = _body([_run("CI/CD", new_tip, "success")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "already exists" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") == old_tip, "an existing tag was moved"


def test_artifacts_only_push_refuses_a_bare_directory_in_writes(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path, writes="`artifacts`")
    _commit_artifacts_only(repo)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", head, "success")])
    proc = _wrapper(repo, home, url, "dev", "--item", "17-900")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "bare directory" in out, out
    assert _remote_ref(bare, "refs/heads/dev") != head, "a refused artifacts-only push reached the remote"


def test_artifacts_only_push_with_a_file_in_writes_passes(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    _commit_artifacts_only(repo)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", head, "success")])
    proc = _wrapper(repo, home, url, "dev", "--item", "17-900")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _remote_ref(bare, "refs/heads/dev") == head


def test_artifacts_only_push_refuses_when_the_stack_gate_fails(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path, gate_stub=FAIL_STUB)
    _commit_artifacts_only(repo)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", head, "success")])
    proc = _wrapper(repo, home, url, "dev", "--item", "17-900")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "stack gate" in out, out
    assert _remote_ref(bare, "refs/heads/dev") != head


def test_tag_push_refuses_when_the_tip_has_no_successful_CI_CD_run(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    state["body"] = _body([_run("dashboard", tip, "success")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "CI/CD" in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None, "a tag reached the remote without a CI/CD run"


def test_the_override_does_not_reach_a_tag_push(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    tip = _git(repo, "rev-parse", "origin/main")
    state["body"] = _body([_run("CI/CD", tip, "failure"), _run("dashboard", tip, "success")])
    proc = _wrapper(repo, home, url, "--tag", "v0.2.17", extra_env={"JNWB_PUSH_OVER_RED": "1"})
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "pushing anyway" not in out, out
    assert _remote_ref(bare, "refs/tags/v0.2.17") is None, "the override pushed a tag"


def test_a_push_whose_diff_cannot_be_read_is_refused(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path)
    _commit_artifacts_only(repo)
    _git(repo, "update-ref", "-d", "refs/remotes/origin/dev")
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", head, "success")])
    proc = _wrapper(repo, home, url, "dev")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert "git diff" in out, out
    assert _remote_ref(bare, "refs/heads/dev") != head


def test_artifacts_only_push_refuses_when_the_item_length_test_fails(tmp_path, ci_api):
    state, url = ci_api
    repo, bare, home = _scaffold(tmp_path, item_test=ITEM_TEST_FAIL)
    _commit_artifacts_only(repo)
    head = _git(repo, "rev-parse", "HEAD")
    state["body"] = _body([_run("CI/CD", head, "success")])
    proc = _wrapper(repo, home, url, "dev", "--item", "17-900")
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, out
    assert _remote_ref(bare, "refs/heads/dev") != head
