"""scripts/push_guard.py denies a plain `git push` in a jnwb checkout and lets jnwb_push.sh through."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "push_guard.py"


def decide(command: str, cwd: str) -> str:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    out = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload), capture_output=True,
                         text=True, timeout=30, check=True).stdout
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else "allow"


def test_a_plain_push_in_jnwb_is_denied_and_the_wrapper_is_not():
    assert decide("git push origin dev </dev/null", "work/jnwb") == "deny"
    assert decide('git -C "work\\jnwb" push origin dev', "work/elsewhere") == "deny"
    assert decide("bash work/jnwb/scripts/jnwb_push.sh work/jnwb dev </dev/null", "work/jnwb") == "allow"


def test_pushes_elsewhere_and_other_git_commands_pass():
    assert decide("git push origin dev", "work/other") == "allow"
    assert decide("git -C work/other push", "work/jnwb") == "allow"
    assert decide("git status", "work/jnwb") == "allow"
