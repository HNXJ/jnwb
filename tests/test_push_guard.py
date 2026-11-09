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
