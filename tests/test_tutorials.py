"""Every tutorial under examples/tutorials/ must run top to bottom."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TUTORIAL_DIR = REPO_ROOT / "examples" / "tutorials"
TUTORIALS = sorted(
    p for p in TUTORIAL_DIR.glob("[0-9][0-9]_*.py")
)


def test_there_are_tutorials_to_run():
    assert TUTORIALS, f"no numbered tutorials in {TUTORIAL_DIR}"


@pytest.mark.parametrize("path", TUTORIALS, ids=lambda p: p.name)
def test_tutorial_executes(path: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    res = subprocess.run(
        [sys.executable, str(path)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
