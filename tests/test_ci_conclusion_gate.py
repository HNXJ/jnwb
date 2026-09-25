"""The release gate must resolve CI for the exact commit it is qualifying.

Before 06-108 it did not resolve CI at all: ``grep -niE "gh run|workflow|actions|conclusion"
scripts/release_gate.py`` returned one hit at 30c425cf, a ``# 4. Workflows`` heading inside
the wheel smoke script with nothing to do with GitHub Actions. Measured the same day, the
pipeline at that commit concluded ``failure``, as it had on all twelve most recent pushes to
``dev`` -- four of six matrix legs red. The gate would have authorised the tag.

Two properties are tested first-class, because each names a way the check could pass for the
wrong reason:

* **The commit, not the branch.** A check reading the branch's latest run would go green
  while a different commit was being tagged.
* **Per leg, not in aggregate, and "could not tell" is not "green".** At 30c425cf the job
  ``Build & Validate Distribution`` is ``needs: test`` and therefore reported ``skipped``,
  not ``failure`` -- so "no job concluded failure" was already false-green there. And an
  absent ``gh``, an unauthenticated one, a missing run or a run still executing must each be
  distinguishable and none may read as a pass.

Nothing here reaches the network. Every case is a fixture of the JSON the two ``gh``
invocations return, driven through the real code by a stub runner.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import textwrap

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# `scripts/` is excluded from the wheel, and the leg that qualifies the built artifact runs this
# suite from outside the checkout, so nothing puts the repository on `sys.path` there. A
# module-scope `from scripts...` raises ModuleNotFoundError -- a collection *error*, which pytest
# reports as `Interrupted` and which can take unrelated modules down with it.
# `append`, never `insert(0, ...)`: inserting re-shadows the installed package for the whole
# session, which tests/test_the_suite_can_qualify_an_installed_copy.py forbids.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.release_gate import (  # noqa: E402
    CI_FAILED,
    CI_UNRESOLVED,
    CI_VERIFIED,
    CI_WORKFLOW_PATH,
    SKIP_CI_ENV,
    check_ci_conclusion,
    evaluate_ci_jobs,
    format_leg_table,
    required_ci_jobs,
    select_run_for_commit,
)

SHA = "a" * 40
OTHER_SHA = "b" * 40
RUN_ID = 12345

#: A workflow deliberately unlike this repository's: different job names, a two-axis matrix
#: with different values, one conditional job. A rule that hardcoded jnwb's real leg names
#: could not pass against this.
OTHER_WORKFLOW = textwrap.dedent("""
    name: Other
    on: [push]
    jobs:
      verify:
        name: Verify (${{ matrix.toolchain }} / ${{ matrix.arch }})
        strategy:
          matrix:
            toolchain: [ "stable", "nightly" ]
            arch: [ "x64" ]
        steps:
          - run: echo hi
      package:
        name: Package It
        needs: verify
        steps:
          - run: echo hi
      ship:
        name: Ship It
        needs: package
        if: github.event_name == 'release'
        steps:
          - run: echo hi
""")

#: Matrix axes are expanded in sorted-key order (``arch`` before ``toolchain``), so the
#: substitution is by name and the template's own ordering is preserved.
OTHER_REQUIRED = [
    "Verify (stable / x64)",
    "Verify (nightly / x64)",
    "Package It",
]


def _job(name: str, conclusion: str = "success", status: str = "completed") -> dict:
    return {"name": name, "status": status, "conclusion": conclusion}


def _all_green() -> list:
    return [_job(name) for name in OTHER_REQUIRED] + [_job("Ship It", "skipped")]


class StubRunner:
    """Answers the two ``gh`` calls from canned stdout, and records what was asked.

    Fixture-driven on purpose: a test that calls GitHub tests GitHub's availability, and is
    green or red for reasons that have nothing to do with this code.
    """

    def __init__(self, list_stdout="", view_stdout="", list_rc=0, view_rc=0, raises=None):
        self.list_stdout, self.view_stdout = list_stdout, view_stdout
        self.list_rc, self.view_rc = list_rc, view_rc
        self.raises = raises
        self.calls: list[list[str]] = []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        if self.raises is not None:
            raise self.raises
        if args[:3] == ["gh", "run", "list"]:
            return subprocess.CompletedProcess(args, self.list_rc, self.list_stdout, "boom")
        return subprocess.CompletedProcess(args, self.view_rc, self.view_stdout, "boom")


def _runner(jobs, *, run_sha=SHA, run_status="completed", view_sha=None, list_payload=None):
    runs = list_payload if list_payload is not None else [{
        "databaseId": RUN_ID, "headSha": run_sha, "status": run_status,
        "conclusion": "failure", "workflowName": "Other",
    }]
    view = {"jobs": jobs, "headSha": run_sha if view_sha is None else view_sha,
            "conclusion": "failure"}
    return StubRunner(list_stdout=json.dumps(runs), view_stdout=json.dumps(view))


def _outcome(**kwargs):
    return check_ci_conclusion(SHA, required=OTHER_REQUIRED, runner=_runner(**kwargs))


# --------------------------------------------------------------------------------------
# The seven verdicts
# --------------------------------------------------------------------------------------

def test_all_required_legs_success_is_the_only_pass():
    outcome = _outcome(jobs=_all_green())
    assert outcome.status == CI_VERIFIED, outcome
    assert outcome.violations == []
    assert str(RUN_ID) in outcome.detail


def test_one_leg_failure_fails():
    jobs = _all_green()
    jobs[1] = _job(OTHER_REQUIRED[1], "failure")
    outcome = _outcome(jobs=jobs)
    assert outcome.status == CI_FAILED
    assert any("nightly" in v and "failure" in v for v in outcome.violations), outcome.violations


def test_one_leg_cancelled_fails():
    jobs = _all_green()
    jobs[0] = _job(OTHER_REQUIRED[0], "cancelled")
    outcome = _outcome(jobs=jobs)
    assert outcome.status == CI_FAILED
    assert any("cancelled" in v for v in outcome.violations), outcome.violations


def test_one_leg_skipped_fails():
    """The measured 30c425cf shape: the ``needs:`` job never ran, so it is not red.

    A rule phrased as "no required leg concluded failure" passes this fixture. That is why
    the rule is phrased as "every required leg concluded success".
    """
    jobs = _all_green()
    jobs[2] = _job("Package It", "skipped")
    outcome = _outcome(jobs=jobs)
    assert outcome.status == CI_FAILED
    assert any("Package It" in v and "skipped" in v for v in outcome.violations), outcome.violations
    assert not any(leg[2] == "failure" for leg in outcome.legs), (
        "the fixture must contain no 'failure' leg, or it does not discriminate")


def test_leg_absent_from_the_run_fails():
    outcome = _outcome(jobs=[j for j in _all_green() if j["name"] != "Package It"])
    assert outcome.status == CI_FAILED
    assert any("Package It" in v and "absent" in v for v in outcome.violations), outcome.violations


def test_no_run_for_the_sha_is_unresolved_not_pass():
    outcome = check_ci_conclusion(SHA, required=OTHER_REQUIRED, runner=StubRunner(
        list_stdout=json.dumps([])))
    assert outcome.status == CI_UNRESOLVED
    assert SHA[:12] in outcome.detail


def test_run_in_progress_is_unresolved_not_pass():
    outcome = _outcome(jobs=_all_green(), run_status="in_progress")
    assert outcome.status == CI_UNRESOLVED
    assert "in_progress" in outcome.detail


def test_leg_still_running_is_unresolved_not_pass():
    jobs = _all_green()
    jobs[0] = _job(OTHER_REQUIRED[0], "", status="in_progress")
    outcome = _outcome(jobs=jobs)
    assert outcome.status == CI_UNRESOLVED
    assert any("has not concluded" in v for v in outcome.violations), outcome.violations


def test_malformed_json_is_unresolved_not_pass():
    listed = check_ci_conclusion(SHA, required=OTHER_REQUIRED,
                                 runner=StubRunner(list_stdout="{not json"))
    assert listed.status == CI_UNRESOLVED and "unreadable JSON" in listed.detail

    runner = _runner(jobs=_all_green())
    runner.view_stdout = "]]]"
    viewed = check_ci_conclusion(SHA, required=OTHER_REQUIRED, runner=runner)
    assert viewed.status == CI_UNRESOLVED and "unreadable JSON" in viewed.detail


# --------------------------------------------------------------------------------------
# It must be the commit under qualification, not whatever run came back
# --------------------------------------------------------------------------------------

def test_a_run_for_a_different_commit_is_never_accepted():
    """The branch-tip failure mode: green run, wrong commit."""
    outcome = check_ci_conclusion(SHA, required=OTHER_REQUIRED, runner=_runner(
        jobs=_all_green(), run_sha=OTHER_SHA))
    assert outcome.status == CI_UNRESOLVED, outcome
    assert "no workflow run has head commit" in outcome.detail


def test_the_sha_is_re_checked_on_the_second_gh_call():
    outcome = check_ci_conclusion(SHA, required=OTHER_REQUIRED, runner=_runner(
        jobs=_all_green(), view_sha=OTHER_SHA))
    assert outcome.status == CI_UNRESOLVED
    assert "reports head" in outcome.detail


def test_the_commit_is_passed_to_gh_and_the_newest_matching_run_is_chosen():
    runner = _runner(jobs=_all_green(), list_payload=[
        {"databaseId": 1, "headSha": SHA, "status": "completed", "workflowName": "Other"},
        {"databaseId": 99, "headSha": SHA, "status": "completed", "workflowName": "Other"},
        {"databaseId": 50, "headSha": OTHER_SHA, "status": "completed", "workflowName": "Other"},
    ])
    check_ci_conclusion(SHA, required=OTHER_REQUIRED, runner=runner)
    assert SHA in runner.calls[0], runner.calls[0]
    assert "99" in runner.calls[1], runner.calls[1]


def test_select_run_for_commit_rejects_a_non_list_payload():
    run, reason = select_run_for_commit(SHA, json.dumps({"headSha": SHA}))
    assert run is None and "expected a list" in reason


# --------------------------------------------------------------------------------------
# Tooling failure modes: each distinguishable, none a pass
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize("raises, fragment", [
    (FileNotFoundError(), "not on PATH"),
    (subprocess.TimeoutExpired(cmd="gh", timeout=1.0), "failed"),
    (OSError("network is unreachable"), "failed"),
])
def test_tooling_failures_are_unresolved_and_named(raises, fragment):
    outcome = check_ci_conclusion(SHA, required=OTHER_REQUIRED,
                                  runner=StubRunner(raises=raises))
    assert outcome.status == CI_UNRESOLVED
    assert fragment in outcome.detail, outcome.detail


def test_unauthenticated_gh_is_unresolved_and_names_the_exit_code():
    outcome = check_ci_conclusion(SHA, required=OTHER_REQUIRED,
                                  runner=StubRunner(list_stdout="", list_rc=4))
    assert outcome.status == CI_UNRESOLVED
    assert "exited 4" in outcome.detail and "boom" in outcome.detail


def test_an_empty_required_set_is_unresolved_rather_than_vacuously_true():
    outcome = check_ci_conclusion(SHA, required=[], runner=StubRunner())
    assert outcome.status == CI_UNRESOLVED
    assert "vacuously" in outcome.detail


# --------------------------------------------------------------------------------------
# The required set is derived from the workflow, not written down
# --------------------------------------------------------------------------------------

def test_required_jobs_expand_the_matrix_and_exclude_conditional_jobs():
    assert sorted(required_ci_jobs(OTHER_WORKFLOW)) == sorted(OTHER_REQUIRED)
    assert "Ship It" not in required_ci_jobs(OTHER_WORKFLOW)


def test_this_repository_requires_every_matrix_leg_and_the_build_job():
    required = required_ci_jobs(root=REPO_ROOT)
    import tomllib
    import yaml

    workflow = yaml.safe_load((REPO_ROOT / CI_WORKFLOW_PATH).read_text(encoding="utf-8"))
    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]
    expected = len(matrix["os"]) * len(matrix["python-version"])
    assert len(required) == expected + 1, required
    assert "Build & Validate Distribution" in required

    # Derived, not asserted against a literal: every supported interpreter in pyproject.toml
    # must appear in a required leg, so adding 3.15 to the classifiers without adding the CI
    # leg cannot leave the leg unrequired and unnoticed.
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    for version in matrix["python-version"]:
        assert any(str(version) in name for name in required), version
    assert project["name"] == "jnwb"


def test_an_unreadable_workflow_is_unresolved_rather_than_an_empty_requirement(tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / CI_WORKFLOW_PATH).write_text("jobs: [ this is not a mapping", encoding="utf-8")
    with pytest.raises(Exception):
        required_ci_jobs(root=tmp_path)


def test_evaluate_ci_jobs_rejects_a_payload_with_no_jobs_array():
    verdict = evaluate_ci_jobs(OTHER_REQUIRED, {"conclusion": "success"})
    assert verdict.failures == [] and verdict.unresolved
    assert "no readable `jobs` array" in verdict.unresolved[0]


def test_leg_table_renders_every_job_including_the_ones_not_required():
    outcome = _outcome(jobs=_all_green())
    rendered = "\n".join(format_leg_table(outcome.legs))
    for name in OTHER_REQUIRED + ["Ship It"]:
        assert name in rendered


# --------------------------------------------------------------------------------------
# The gate wiring: the override exists, is loud, and is not the default
# --------------------------------------------------------------------------------------

def test_the_skip_override_is_not_enabled_by_default(monkeypatch):
    monkeypatch.delenv(SKIP_CI_ENV, raising=False)
    import os
    assert os.environ.get(SKIP_CI_ENV) != "1"


def test_step_0e_exits_on_a_non_verified_outcome_and_says_so_loudly():
    """Read the wiring, because the alternative is running the whole gate to test one branch.

    What is asserted is the property that failed at 30c425cf: the only status the gate treats
    as a pass is CI_VERIFIED, and the non-pass path calls sys.exit unless the named override
    is set.
    """
    source = (REPO_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
    step = source.partition("=== STEP 0e")[2].partition("=== STEP 1")[0]
    assert step, "STEP 0e is absent from release_gate.main()"
    assert "CI_VERIFIED" in step and "sys.exit(1)" in step
    assert "SKIP_CI_ENV" in step, "the override must be the named constant, not a literal"
    assert SKIP_CI_ENV == "JNWB_SKIP_CI_CHECK"
    assert "check_ci_conclusion" in step
    # STEP 0e must precede the expensive suite, or a red pipeline costs a full local run
    # before anyone is told.
    assert source.index("=== STEP 0e") < source.index("=== STEP 1")
