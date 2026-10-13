"""The dashboard workflow publishes what the build wrote, from main, without a forced orphan.

Static checks read .github/workflows/dashboard.yml as YAML. The check script runs on temporary
site directories. Each refusal must exit 1 and name what it refused, so a missing script (exit 2)
cannot pass a refusal test.
"""

import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "dashboard.yml"
CHECK = REPO / "scripts" / "check_dashboard_build.py"
SHA = "0123456789abcdef0123456789abcdef01234567"
PUBLISH = "git push origin HEAD:gh-pages"
# The repository's Actions policy (Settings, Actions, General) admits only these.
ALLOWED_ACTIONS = ("HNXJ/", "actions/", "github/", "pypa/gh-action-pypi-publish@")


def _workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers(doc):
    # PyYAML (YAML 1.1) reads the bare key `on` as the boolean True.
    return doc["on"] if "on" in doc else doc[True]


def _job(doc):
    jobs = doc["jobs"]
    assert len(jobs) == 1, f"expected one job, found {sorted(jobs)}"
    return next(iter(jobs.values()))


def _step_index(steps, needle):
    hits = [i for i, s in enumerate(steps) if needle in str(s.get("run", ""))]
    assert len(hits) == 1, f"expected one step running {needle!r}, found {hits}"
    return hits[0]


def _publish_index(steps):
    return _step_index(steps, PUBLISH)


def test_triggers_are_push_to_main_and_manual_dispatch_only():
    on = _triggers(_workflow())
    assert set(on) == {"push", "workflow_dispatch"}
    assert set(on["push"]) == {"branches"}
    assert on["push"]["branches"] == ["main"]


def test_a_manual_run_publishes_only_from_main():
    """workflow_dispatch can run on any branch; the job guard keeps other branches off gh-pages."""
    assert _job(_workflow()).get("if") == "github.ref == 'refs/heads/main'"


def test_contents_write_is_granted_on_the_job_only():
    doc = _workflow()
    assert (doc.get("permissions") or {}).get("contents") != "write"
    assert _job(doc)["permissions"] == {"contents": "write"}


def test_concurrency_queues_runs_without_cancelling():
    assert _workflow()["concurrency"] == {"group": "dashboard", "cancel-in-progress": False}


def test_publish_is_a_non_orphan_non_forced_push_of_the_site_from_the_source_sha():
    steps = _job(_workflow())["steps"]
    run = steps[_publish_index(steps)]["run"]
    lines = [line.strip() for line in run.splitlines()]
    # Non-orphan: the commit sits on the existing gh-pages history.
    assert "git fetch origin gh-pages" in lines
    assert 'git worktree add --detach "$RUNNER_TEMP/pages" origin/gh-pages' in lines
    assert "--orphan" not in run
    # Not forced: no --force, -f or +refspec on the push.
    push = [line for line in lines if line.startswith("git push")]
    assert push == [PUBLISH]
    # The old files go and only the build's files come in.
    remove = lines.index("git rm -r -q --ignore-unmatch .")
    copy = lines.index('cp -a "$RUNNER_TEMP/site/." .')
    assert remove < copy
    assert any(line.startswith("git commit") and "$GITHUB_SHA" in line for line in lines)


def test_every_action_in_every_workflow_is_one_the_repository_allows():
    """A disallowed action fails the run at startup, before any job reports."""
    used = []
    workflows = REPO / ".github" / "workflows"
    for path in sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")]):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job in doc["jobs"].values():
            if "uses" in job:  # a reusable workflow
                used.append((path.name, job["uses"]))
            used += [(path.name, s["uses"]) for s in job.get("steps", []) if "uses" in s]
    assert used, "no workflow step uses an action; the scan read nothing"
    # GitHub matches owner names without case; local actions (./) stay in the repository.
    allowed = tuple(prefix.lower() for prefix in ALLOWED_ACTIONS) + ("./",)
    refused = [(name, uses) for name, uses in used if not uses.lower().startswith(allowed)]
    assert not refused, refused


def test_build_runs_before_the_check_and_the_check_before_publish():
    steps = _job(_workflow())["steps"]
    build = _step_index(steps, "scripts/build_dashboard.py")
    check = _step_index(steps, "scripts/check_dashboard_build.py")
    publish = _publish_index(steps)
    assert build < check < publish


def test_check_step_is_given_the_site_and_the_source_sha():
    steps = _job(_workflow())["steps"]
    run = steps[_step_index(steps, "scripts/check_dashboard_build.py")]["run"]
    assert "site" in run
    assert "$GITHUB_SHA" in run or "${{ github.sha }}" in run


def _site(tmp_path, *, data_commit=SHA, drop=()):
    site = tmp_path / "site"
    site.mkdir()
    files = {
        "index.html": "<!doctype html>",
        "app.js": "",
        "data.json": json.dumps({"generated": {"commit": data_commit, "date": "2026-10-12"}}),
    }
    for name, text in files.items():
        if name not in drop:
            (site / name).write_text(text, encoding="utf-8")
    return site


def _run_check(site, sha=SHA):
    return subprocess.run(
        [sys.executable, str(CHECK), str(site), sha],
        capture_output=True, text=True, cwd=REPO, timeout=120,
    )


def test_check_passes_a_complete_site_whose_commit_matches(tmp_path):
    proc = _run_check(_site(tmp_path))
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_check_refuses_a_site_missing_data_json(tmp_path):
    proc = _run_check(_site(tmp_path, drop=("data.json",)))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "data.json" in proc.stdout + proc.stderr


def test_check_refuses_a_data_commit_that_is_not_the_source_sha(tmp_path):
    proc = _run_check(_site(tmp_path, data_commit="f" * 40))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "commit" in (proc.stdout + proc.stderr).lower()


def test_the_built_data_is_validated_with_jsonschema_between_check_and_publish():
    steps = _job(_workflow())["steps"]
    hits = [i for i, s in enumerate(steps) if "data.schema.json" in str(s.get("run", ""))]
    assert len(hits) == 1, f"expected one step validating against the schema, found {hits}"
    run = steps[hits[0]]["run"]
    assert "jsonschema" in run and "pip install" in run, "the step must install jsonschema"
    assert "$RUNNER_TEMP/site/data.json" in run, "the step must validate the built data.json"
    assert _step_index(steps, "scripts/check_dashboard_build.py") < hits[0] < _publish_index(steps)
