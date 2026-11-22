"""jnwb/ stays under the McCabe complexity ceiling that pyproject.toml configures for ruff (C901).

The check runs ruff with the project configuration; where ruff is not installed it skips and says
so. The configured ceiling is read too, so raising it is a visible change rather than a silent pass.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tomllib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
CEILING = 40


def _ruff() -> list:
    if shutil.which("ruff"):
        return ["ruff"]
    probe = subprocess.run([sys.executable, "-m", "ruff", "--version"], capture_output=True)
    if probe.returncode == 0:
        return [sys.executable, "-m", "ruff"]
    pytest.skip("ruff is not installed, so the C901 ceiling over jnwb/ cannot be checked here")


def test_pyproject_adds_c901_at_the_ceiling_without_narrowing_the_default_rules():
    lint = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["ruff"]["lint"]
    assert "C901" in lint["extend-select"], lint
    assert "select" not in lint, "a `select` list replaces ruff's default rules; use extend-select"
    assert lint["mccabe"]["max-complexity"] == CEILING, lint["mccabe"]


def test_no_function_in_jnwb_exceeds_the_complexity_ceiling():
    done = subprocess.run(
        [*_ruff(), "check", "--select", "C901", "--no-cache", "--output-format", "concise",
         "--config", str(PYPROJECT), "jnwb/"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "All checks passed" in done.stdout, done.stdout + done.stderr
