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
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "workflow.yml"
CEILING = 40
CI_RUFF = "0.16.10"  # the ruff version the 0.2.17 qualification recorded (env_pip_freeze.txt)


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


def test_one_ci_job_installs_the_pinned_ruff_and_runs_the_c901_ceiling_unskipped():
    """_ruff() skips where ruff is absent, and no CI job installed it, so the ceiling never ran in
    CI. Exactly one job must install the pinned ruff and run the same check over jnwb/, in steps
    that carry no `if:`, so neither can be skipped."""
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    hits = []
    for jid, job in jobs.items():
        steps = [s for s in job.get("steps", []) if isinstance(s, dict)]
        installs = [i for i, s in enumerate(steps)
                    if f'"ruff=={CI_RUFF}"' in " ".join(str(s.get("run", "")).split())]
        checks = [i for i, s in enumerate(steps)
                  if "ruff check" in str(s.get("run", "")) and "--select C901" in str(s.get("run", ""))]
        if installs or checks:
            hits.append((jid, steps, installs, checks))
    assert len(hits) == 1, [(jid, installs, checks) for jid, _, installs, checks in hits]
    jid, steps, installs, checks = hits[0]
    assert installs and checks and installs[0] <= checks[0], (jid, installs, checks)
    step = steps[checks[0]]
    script = " ".join(str(step["run"]).replace("\\\n", " ").split())
    assert script.index(f'"ruff=={CI_RUFF}"') < script.index("ruff check"), script
    command = script[script.index("ruff check"):]
    assert "jnwb/" in command.split(), command
    assert "--config pyproject.toml" in command, command
    for index in {installs[0], checks[0]}:
        assert "if" not in steps[index], (jid, steps[index].get("name"))
