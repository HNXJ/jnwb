"""Regression tests for CI release / PyPI trigger topology.

Production PyPI must be unreachable from a tag push alone. A published GitHub Release
(non-prerelease) is required. Duplicate upload attempts must fail loudly, not be masked.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "workflow.yml"

# 0.1.6 dual-trigger condition that caused publish-pypi on both tag push and release.
_LEGACY_DUAL_TRIGGER_IF = (
    "(github.event_name == 'release' && !github.event.release.prerelease "
    "&& github.event.action == 'published') || "
    "(github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') "
    "&& !contains(github.ref, 'rc'))"
)


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _publish_pypi_if() -> str:
    jobs = _load_workflow()["jobs"]
    condition = jobs["publish-pypi"]["if"]
    return " ".join(str(condition).split())


class TestWorkflowReleasePolicy:
    def test_publish_pypi_requires_github_release_published(self):
        condition = _publish_pypi_if()
        assert "github.event_name == 'release'" in condition
        assert "github.event.action == 'published'" in condition
        assert "!github.event.release.prerelease" in condition

    def test_tag_push_alone_cannot_reach_production_pypi(self):
        condition = _publish_pypi_if()
        assert "github.event_name == 'push'" not in condition
        assert "refs/tags/v" not in condition

    def test_prerelease_cannot_reach_production_pypi(self):
        condition = _publish_pypi_if()
        assert "!github.event.release.prerelease" in condition

    def test_legacy_dual_trigger_if_is_rejected(self):
        """Regression: 0.1.6 workflow published on tag push *and* on release."""
        condition = _publish_pypi_if()
        normalized_legacy = " ".join(_LEGACY_DUAL_TRIGGER_IF.split())
        assert condition != normalized_legacy

    def test_testpypi_needs_build_and_pypi_needs_the_push_run(self):
        """The release run does not rebuild; PyPI receives the push run's checked files.

        publish-pypi carries no `needs:` because build is skipped on a release event, and a job
        that needs a skipped job is skipped too. What orders it is its first step, which reads
        the tag push run's TestPyPI jobs (tested below).
        """
        jobs = _load_workflow()["jobs"]
        assert jobs["publish-testpypi"]["needs"] == "build"
        assert "needs" not in jobs["publish-pypi"]

    def test_a_release_run_skips_exactly_the_jobs_the_push_run_qualified(self):
        import sys

        if str(REPO_ROOT) not in sys.path:
            sys.path.append(str(REPO_ROOT))
        from scripts.release_gate import SKIPPED_ON_RELEASE, required_ci_jobs

        jobs = _load_workflow()["jobs"]
        skipped = {jid for jid, job in jobs.items()
                   if " ".join(str(job.get("if", "")).split()) == SKIPPED_ON_RELEASE}
        assert skipped == {"test", "build"}, skipped
        # Skipped on a release event is still required of the push run the gate qualifies.
        required = required_ci_jobs(root=REPO_ROOT)
        assert jobs["build"]["name"] in required and jobs["test-floors"]["name"] in required
        assert any(name.startswith("Test (Python ") for name in required), required

    def test_the_release_skip_does_not_make_a_job_optional(self):
        """Any other condition still drops a job from the required set."""
        import sys

        if str(REPO_ROOT) not in sys.path:
            sys.path.append(str(REPO_ROOT))
        from scripts.release_gate import required_ci_jobs

        workflow = (
            "jobs:\n"
            "  a:\n    name: A\n    if: github.event_name != 'release'\n    runs-on: x\n"
            "  b:\n    name: B\n    if: github.event_name == 'push'\n    runs-on: x\n"
            "  c:\n    name: C\n    runs-on: x\n"
        )
        assert sorted(required_ci_jobs(workflow)) == ["A", "C"]

    def test_tag_push_still_triggers_validation_pipeline(self):
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert re.search(r"tags:\s*\[\s*\"v\*\"\s*\]", workflow_text)
        assert "publish-pypi:" in workflow_text

    def test_every_tag_push_publishes_to_testpypi(self):
        """A final tag's push skipped TestPyPI because the condition required `rc` in the ref,
        and the non-prerelease release run skipped it too, so a final version reached PyPI
        without ever being on TestPyPI."""
        condition = _load_workflow()["jobs"]["publish-testpypi"]["if"]
        text = " ".join(str(condition).split())
        assert "(github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v'))" in text
        assert "'rc'" not in text, "a final tag's push must publish to TestPyPI as well"
        assert "workflow_dispatch" in text

    def test_the_release_event_does_not_upload_to_testpypi_again(self):
        """The tag's push run already uploaded those files; a second upload is refused."""
        text = " ".join(str(_load_workflow()["jobs"]["publish-testpypi"]["if"]).split())
        assert "release" not in text.replace("refs/tags/v", ""), text


class TestTestPyPIBeforePyPI:
    """The tag push publishes to TestPyPI and verifies the upload from there, and PyPI publishes
    only after both succeeded. The release event is a different run from the tag push, so
    `needs:` cannot order the jobs; the PyPI job's first step reads the push run's two TestPyPI
    jobs and fails unless both concluded success.

    What would pass while the order is broken: a gate step that exists but runs after the upload,
    carries `continue-on-error` or an `if:`, looks for a job name the TestPyPI job no longer has,
    reads another tag or commit, or exits 0 on a conclusion other than success.
    """

    @staticmethod
    def _steps():
        return _load_workflow()["jobs"]["publish-pypi"]["steps"]

    @classmethod
    def _gate(cls):
        gates = [s for s in cls._steps() if "TESTPYPI_JOB" in (s.get("env") or {})]
        assert len(gates) == 1, f"expected one TestPyPI gate in publish-pypi, found {len(gates)}"
        return gates[0]

    def test_the_gate_runs_before_anything_is_uploaded(self):
        steps = self._steps()
        uploads = [i for i, s in enumerate(steps) if "pypi-publish" in str(s.get("uses", ""))]
        assert len(uploads) == 1, uploads
        assert steps.index(self._gate()) == 0 < uploads[0], [s.get("name") for s in steps]

    def test_nothing_before_the_upload_can_be_skipped_or_forgiven(self):
        job = _load_workflow()["jobs"]["publish-pypi"]
        assert not job.get("continue-on-error"), "publish-pypi is continue-on-error"
        steps = self._steps()
        upload = next(i for i, s in enumerate(steps) if "pypi-publish" in str(s.get("uses", "")))
        for step in steps[:upload + 1]:
            assert "if" not in step and not step.get("continue-on-error"), step.get("name")

    # A job still running has no conclusion and a job not listed yet has none either; both read
    # as pending, never as success. Two jobs of one name cannot say which one uploaded, so a
    # failed upload beside a successful namesake reads as ambiguous rather than as success.
    _ONE_JOB = ('[.jobs[] | select(.name == env.{})] | if length == 0 then "pending" '
                'elif length == 1 then (.[0].conclusion // "pending") else "ambiguous" end')

    def test_the_gate_reads_the_testpypi_job_by_its_name(self):
        name = _load_workflow()["jobs"]["publish-testpypi"]["name"]
        gate = self._gate()
        assert gate["env"]["TESTPYPI_JOB"] == name
        assert self._ONE_JOB.format("TESTPYPI_JOB") in gate["run"], gate["run"]

    def test_no_two_jobs_share_a_name(self):
        """The gate reads jobs by name; a second job named like the upload would be read too."""
        names = [job.get("name", jid) for jid, job in _load_workflow()["jobs"].items()]
        assert len(names) == len(set(names)), sorted(names)

    def test_the_gate_outputs_the_run_that_passed(self):
        gate = self._gate()
        run = gate["run"]
        assert gate.get("id") == "testpypi", gate.get("id")
        assert re.search(r'if \[ "\$pair" = "success\+success" \] && \[ -z "\$matched" \]; then'
                         r'\s*\n\s*matched="\$run"\s*\n\s*fi', run), run
        block = re.search(r'^\s*case " \$conclusions " in\n(.*?)^\s*esac\b', run, re.M | re.S)
        success = re.search(r'^\s*\*" success\+success "\*\)\s*\n(.*?);;', block.group(1),
                            re.M | re.S)
        assert success and 'echo "run_id=$matched" >> "$GITHUB_OUTPUT"' in success.group(1), run

    def test_pypi_receives_the_files_testpypi_received(self):
        """The release run rebuilds; its files are not the ones verified on TestPyPI. The
        artifact comes from the push run the gate matched, and each file's sha256 must equal
        TestPyPI's record of it before the upload."""
        steps = self._steps()
        upload = next(i for i, s in enumerate(steps) if "pypi-publish" in str(s.get("uses", "")))
        downloads = [i for i, s in enumerate(steps)
                     if "download-artifact" in str(s.get("uses", ""))]
        assert len(downloads) == 1 and downloads[0] < upload, downloads
        with_ = steps[downloads[0]]["with"]
        gate_id = self._gate()["id"]
        assert with_.get("run-id") == f"${{{{ steps.{gate_id}.outputs.run_id }}}}", with_
        assert with_.get("github-token") == "${{ github.token }}", with_
        checks = [s for s in steps[downloads[0] + 1:upload]
                  if "https://test.pypi.org/pypi/jnwb/$version/json" in str(s.get("run", ""))]
        assert len(checks) == 1, "no step compares the files with TestPyPI before the upload"
        step = checks[0]
        run = step["run"]
        assert " ".join(str(step["env"]["TAG"]).split()) == "${{ github.event.release.tag_name }}"
        assert "set -euo pipefail" in run and 'version="${TAG#v}"' in run, run
        assert "select(.filename == $name) | .digests.sha256" in run, run
        assert 'have=$(sha256sum "$file" | cut -d\' \' -f1)' in run, run
        assert re.search(r'if \[ -z "\$want" \] \|\| \[ "\$want" != "\$have" \]; then\s*\n'
                         r'[^\n]*\n\s*exit 1\b', run), run
        assert re.search(r'if \[ "\$count" -eq 0 \] \|\| \[ "\$count" -ne "\$remote" \]; then'
                         r'\s*\n[^\n]*\n\s*exit 1\b', run), run

    def test_the_gate_reads_this_releases_tag_push_run(self):
        gate = self._gate()
        env = {k: " ".join(str(v).split()) for k, v in gate["env"].items()}
        assert env["TAG"] == "${{ github.event.release.tag_name }}", env
        assert env["SHA"] == "${{ github.sha }}", env
        assert "event=push&head_sha=$SHA" in gate["run"]
        assert ('select(.head_branch == env.TAG and .path == ".github/workflows/workflow.yml")'
                in gate["run"]), gate["run"]
        permissions = _load_workflow()["jobs"]["publish-pypi"]["permissions"]
        assert permissions.get("actions") == "read", permissions

    def test_only_success_lets_the_gate_pass(self):
        """The `case` over the conclusions: its one exiting-0 arm matches `success` alone."""
        run = self._gate()["run"]
        assert "set -euo pipefail" in run
        block = re.search(r'^\s*case " \$conclusions " in\n(.*?)^\s*esac\b', run, re.M | re.S)
        assert block, "the gate no longer decides by a case over the conclusions"
        arms = re.findall(r"^\s*([^\s(][^\n]*?)\)[ \t]*\n(.*?);;", block.group(1), re.M | re.S)
        assert arms, "the gate has no case arms; this test is stale"
        passing = [pattern for pattern, body in arms if re.search(r"\bexit 0\b", body)]
        assert passing == ['*" success+success "*'], arms
        assert len(re.findall(r"\bexit 0\b", run)) == 1, "an exit 0 outside the success arm"
        failing = [pattern for pattern, body in arms if re.search(r"\bexit 1\b", body)]
        assert "*" in failing, "a conclusion other than success and pending does not fail"

    def test_waiting_for_the_push_run_ends_in_failure_after_an_hour(self):
        """A pending or absent job waits; without the deadline it would wait until the runner's
        own limit and never say why."""
        run = self._gate()["run"]
        assert "deadline=$((SECONDS + 3600))" in run
        block = re.search(r'^\s*case " \$conclusions " in\n(.*?)^\s*esac\b', run, re.M | re.S)
        waiting = re.search(r'^\s*\*pending\*\|"  "\)\s*\n(.*?);;', block.group(1), re.M | re.S)
        assert waiting, "the gate has no arm for a pending or absent job"
        assert re.search(r'if \[ "\$SECONDS" -ge "\$deadline" \]; then\s*\n[^\n]*\n\s*exit 1\b',
                         waiting.group(1)), waiting.group(1)

    # --- the verification of the upload from TestPyPI -------------------------------------

    @staticmethod
    def _verify_job():
        jobs = _load_workflow()["jobs"]
        verify = [j for j in jobs.values() if isinstance(j, dict)
                  and "test.pypi.org/simple" in " ".join(str(s.get("run", "")) for s in j["steps"])]
        assert len(verify) == 1, f"expected one job installing from TestPyPI, found {len(verify)}"
        return verify[0]

    def test_the_verify_job_runs_after_the_upload_and_only_after_it(self):
        assert self._verify_job()["needs"] == "publish-testpypi"

    def test_the_verify_job_installs_the_tags_version_from_testpypi(self):
        job = self._verify_job()
        step = next(s for s in job["steps"] if "test.pypi.org/simple" in str(s.get("run", "")))
        run = step["run"]
        assert " ".join(str(step["env"]["TAG"]).split()) == "${{ github.ref_name }}", step["env"]
        assert 'version="${TAG#v}"' in run and '"jnwb==$version"' in run, run
        # Only the candidate comes from TestPyPI; its dependencies resolve on the default index,
        # where no upload to TestPyPI can stand in for them.
        assert re.search(r"pip download --no-cache-dir --no-deps --only-binary :all: \\\n\s*"
                         r'--index-url https://test.pypi.org/simple/ "jnwb==\$version" '
                         r"-d /tmp/candidate;", run), run
        assert "extra-index-url" not in run, run
        assert run.count("test.pypi.org") == 1, run
        assert '/tmp/testpypi_env/bin/pip install --no-cache-dir "${wheels[0]}"\n' in run, run
        assert re.search(r'--expected-version "\$version"', run), run
        # A fresh environment, and the import resolved outside the checkout.
        assert "python -m venv /tmp/testpypi_env" in run and "cd /tmp" in run, run
        assert '--not-under "$GITHUB_WORKSPACE"' in run, run

    def test_the_verify_job_retries_the_install_a_bounded_number_of_times(self):
        run = next(str(s["run"]) for s in self._verify_job()["steps"]
                   if "test.pypi.org/simple" in str(s.get("run", "")))
        loop = re.search(r"for attempt in \$\(seq 1 (\d+)\); do\n(.*?)\n\s*done", run, re.S)
        assert loop, run
        assert f'if [ "$attempt" -eq {loop.group(1)} ]' in loop.group(2), loop.group(2)
        assert re.search(r"\bexit 1\b", loop.group(2)), loop.group(2)

    def test_the_pypi_gate_requires_the_verify_job_to_succeed(self):
        gate = self._gate()
        assert gate["env"]["VERIFY_JOB"] == self._verify_job()["name"]
        assert self._ONE_JOB.format("VERIFY_JOB") in gate["run"], gate["run"]
        assert 'pair="${upload:-pending}+${verify:-pending}"' in gate["run"], gate["run"]
        assert 'conclusions="$conclusions $pair"' in gate["run"], gate["run"]

    def test_the_verify_job_checks_the_installed_environment(self):
        """`pip check` in the venv under test, between the install and the smoke script: a
        dependency the wheel declares but cannot satisfy fails the verification."""
        run = next(str(s["run"]) for s in self._verify_job()["steps"]
                   if "test.pypi.org/simple" in str(s.get("run", "")))
        lines = [line.strip() for line in run.splitlines()]
        install = lines.index('/tmp/testpypi_env/bin/pip install --no-cache-dir "${wheels[0]}"')
        smoke = next(i for i, line in enumerate(lines) if "smoke_installed.py" in line)
        assert "/tmp/testpypi_env/bin/pip check" in lines[install + 1:smoke], lines

    def test_the_build_job_and_the_verify_job_run_the_same_smoke_script(self):
        jobs = _load_workflow()["jobs"]
        script = '"$GITHUB_WORKSPACE/scripts/smoke_installed.py"'
        for name, job in (("build", jobs["build"]), ("verify", self._verify_job())):
            runs = [str(s.get("run", "")) for s in job["steps"] if script in str(s.get("run", ""))]
            assert len(runs) == 1, f"the {name} job does not run {script} once"
            assert "--expected-version" in runs[0] and "cd /tmp" in runs[0], runs[0]
            assert any("actions/checkout" in str(s.get("uses", "")) for s in job["steps"]), name
        assert (REPO_ROOT / "scripts" / "smoke_installed.py").is_file()

    # Status functions that let a job or step run after something it depends on failed.
    _RUNS_AFTER_FAILURE = re.compile(r"\b(?:always|cancelled|failure)\s*\(")

    def test_no_job_the_pypi_gate_waits_on_can_be_forgiven(self):
        """A `continue-on-error` job concludes success when it fails, so the gate would read a
        failed upload or verification, or a failed job either depends on, as a pass. An `if:`
        with `always()`, `!cancelled()` or `failure()` runs a job after its dependency failed,
        which forgives that failure the same way."""
        jobs = _load_workflow()["jobs"]
        gate = self._gate()["env"]
        by_name = {job.get("name"): jid for jid, job in jobs.items() if isinstance(job, dict)}
        pending = [by_name[gate["TESTPYPI_JOB"]], by_name[gate["VERIFY_JOB"]]]
        seen = set()
        while pending:
            jid = pending.pop()
            if jid in seen:
                continue
            seen.add(jid)
            job = jobs[jid]
            assert not job.get("continue-on-error"), f"{jid} is continue-on-error"
            assert not self._RUNS_AFTER_FAILURE.search(str(job.get("if", ""))), (jid, job["if"])
            for step in job["steps"]:
                assert not step.get("continue-on-error"), f"{jid}: {step.get('name')!r}"
                assert not self._RUNS_AFTER_FAILURE.search(str(step.get("if", ""))), (
                    jid, step.get("name"), step["if"])
            needs = job.get("needs") or []
            pending.extend([needs] if isinstance(needs, str) else needs)
        assert {"publish-testpypi", "build", "test", "test-floors"} <= seen, seen

    def test_the_status_function_check_sees_each_form(self):
        for condition in ("${{ always() }}", "${{ !cancelled() }}", "failure() || success()",
                          "!cancelled() && github.event_name == 'push'"):
            assert self._RUNS_AFTER_FAILURE.search(condition), condition
        assert not self._RUNS_AFTER_FAILURE.search("github.event_name == 'push'")


class TestTheInstalledSmokeScript:
    """The script the build job and the TestPyPI verification both run. Each check is driven
    to its failure: a check that cannot fail passes an installed package it should refuse.

    The checkout goes on ``PYTHONPATH`` so ``import jnwb`` resolves to it. A directory ahead of
    it holds an ``omission`` stand-in: one that raises ``ModuleNotFoundError`` makes the
    package absent whatever this environment has installed, and an empty one makes it present.
    """

    SCRIPT = REPO_ROOT / "scripts" / "smoke_installed.py"

    @classmethod
    def _run(cls, tmp_path, *args, omission_present=False):
        import os
        import subprocess
        import sys

        shadow = tmp_path / "shadow"
        shadow.mkdir(exist_ok=True)
        (shadow / "omission.py").write_text(
            "" if omission_present else 'raise ModuleNotFoundError("absent in this test")\n',
            encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(shadow), str(REPO_ROOT)])
        return subprocess.run([sys.executable, str(cls.SCRIPT), *args], cwd=tmp_path, env=env,
                              capture_output=True, text=True, timeout=300)

    def test_a_wrong_version_fails(self, tmp_path):
        result = self._run(tmp_path, "--expected-version", "0.0.0.dev999")
        assert result.returncode != 0, result.stdout
        assert "FAIL: installed jnwb is" in result.stderr, result.stderr
        assert "expected 0.0.0.dev999" in result.stderr, result.stderr

    def test_a_package_imported_from_the_checkout_fails(self, tmp_path):
        probe = self._run(tmp_path, "--expected-version", "0.0.0.dev999")
        version = re.search(r"^Installed jnwb version: (\S+)$", probe.stdout, re.M).group(1)
        result = self._run(tmp_path, "--expected-version", version, "--not-under", str(REPO_ROOT))
        assert result.returncode != 0, result.stdout
        assert "FAIL: installed jnwb is" not in result.stderr, result.stderr
        assert "FAIL: jnwb was imported from" in result.stderr, result.stderr
        assert f"inside {REPO_ROOT}" in result.stderr, result.stderr

    def test_an_importable_omission_fails(self, tmp_path):
        result = self._run(tmp_path, "--expected-version", "0.0.0.dev999",
                           omission_present=True)
        assert result.returncode != 0, result.stdout
        assert "RuntimeError: omission is unexpectedly importable!" in result.stderr, (
            result.stderr)
        assert "Installed jnwb version" not in result.stdout, result.stdout

    def test_an_absent_omission_passes_that_check(self, tmp_path):
        """The stand-in really does make the package absent, so the three failures above are
        each the check named, not an import error before it."""
        result = self._run(tmp_path, "--expected-version", "0.0.0.dev999")
        assert "PASS: omission is strictly absent and unimportable" in result.stdout, (
            result.stdout, result.stderr)


class TestInstalledArtifactVerification:
    """0.2.4-03/-13: the artifact must be exercised as installed, not as a checkout.

    The tutorials are the only end-to-end consumers of the public API, and they are the
    surface where a packaging omission (a subpackage excluded from the wheel) or a
    source-tree-only import would actually show up. Running them with the repository on
    ``PYTHONPATH`` cannot detect either, so CI must run them against the installed wheel.
    """

    def _build_steps(self) -> list:
        return _load_workflow()["jobs"]["build"]["steps"]

    def _tutorial_step(self) -> dict:
        steps = [
            s for s in self._build_steps()
            if "tutorials" in s.get("name", "").lower()
        ]
        assert steps, (
            "the distribution job runs no tutorial step; the wheel would ship unverified "
            "end-to-end"
        )
        assert len(steps) == 1, f"expected one tutorial step, found {[s['name'] for s in steps]}"
        return steps[0]

    def test_distribution_job_runs_tutorials_against_installed_wheel(self):
        run = self._tutorial_step()["run"]
        assert "clean_env" in run, "tutorials must run on the clean-venv interpreter"
        assert "examples/tutorials" in run, "tutorial sources must be the executed scripts"

    def test_tutorial_step_cannot_import_from_the_checkout(self):
        run = self._tutorial_step()["run"]
        assert "unset PYTHONPATH" in run, (
            "PYTHONPATH must be cleared, otherwise the checkout can satisfy `import jnwb` "
            "and the step proves nothing about the wheel"
        )
        assert "cd /tmp" in run, "the CWD must be outside the repository"

    def test_tutorial_step_runs_after_the_wheel_is_installed(self):
        names = [s.get("name", "") for s in self._build_steps()]
        install = next(i for i, n in enumerate(names) if "clean virtualenv" in n.lower())
        tutorials = next(i for i, n in enumerate(names) if "tutorials" in n.lower())
        assert install < tutorials, "tutorials must run after the wheel is installed"

    def test_release_gate_also_runs_tutorials_against_the_installed_wheel(self):
        gate = (REPO_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
        assert "STEP 8" in gate, "the local release gate must mirror the CI tutorial check"
        assert 'k != "PYTHONPATH"' in gate, (
            "the release gate must strip PYTHONPATH before running tutorials"
        )

    @staticmethod
    def _pinned_version_literals(source):
        """Every string literal in `source` whose VALUE is exactly a version string.

        A pin is a literal the gate could compare against. A version that merely appears
        inside prose is not: `scripts/release_gate.py` legitimately contains the comment
        "# 7. 0.2.4 additions: wpli, zflip, rdm" inside the smoke script it generates, and
        the log line "No numbered tutorials found; 0.2.4-03 cannot be verified." naming an
        internal item code. This guard used to scan the whole file as one string, so both
        of those failed it the moment the version became exactly `0.2.4`; they had passed
        only because `0.2.4rc1` is not a substring of either.
        """
        import ast

        return {
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }

    def test_release_gate_does_not_hardcode_the_expected_version(self):
        import jnwb

        source = (REPO_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
        assert jnwb.__version__ not in self._pinned_version_literals(source), (
            "the release gate pins the current version as a literal; it must derive the "
            "expected version from the source package so it cannot drift"
        )
        assert "def jnwb_source_version" in source

    def test_the_version_pin_guard_would_catch_a_real_pin(self):
        """The guard is only worth having if narrowing it did not defang it."""
        assert "9.9.9" in self._pinned_version_literals('EXPECTED_VERSION = "9.9.9"')
        assert "9.9.9" in self._pinned_version_literals('assert v == "9.9.9"')
        assert "9.9.9" not in self._pinned_version_literals("x = 1  # 9.9.9 additions")
        assert "9.9.9" not in self._pinned_version_literals(
            'log.error("tutorials missing; 9.9.9-03 cannot be verified")'
        )


class TestShippedReleaseMetadataMatchesTheRelease:
    """`jnwb.__status__` and `jnwb.__release_date__` are shipped inside the wheel, so a stale
    value is a false claim in the artifact rather than a stale note in the repository. Both
    drifted during 0.2.4: the package still called itself a Release Candidate after the
    version became final, and carried a release date two days before its own changelog entry.
    Nothing checked either, so nothing caught it.
    """

    @staticmethod
    def _changelog_date(version):
        import re

        text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        m = re.search(r"^## \[" + re.escape(version) + r"\] - (\d{4}-\d{2}-\d{2})\s*$",
                      text, re.MULTILINE)
        assert m, f"CHANGELOG.md has no dated heading for {version}"
        return m.group(1)

    def test_release_date_matches_the_changelog_entry_for_this_version(self):
        import jnwb

        assert jnwb.__release_date__ == self._changelog_date(jnwb.__version__)

    def test_status_agrees_with_the_packaging_classifier(self):
        import jnwb

        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        classifiers = [
            line.split("::")[-1].strip().strip('",')
            for line in pyproject.splitlines()
            if "Development Status ::" in line
        ]
        assert len(classifiers) == 1, classifiers
        # The classifier is spelled "4 - Beta"; the maturity word is what must agree.
        maturity = classifiers[0].split("-")[-1].strip()
        assert jnwb.__status__.lower() == maturity.lower(), (
            f"jnwb.__status__ is {jnwb.__status__!r} but the wheel is classified "
            f"{classifiers[0]!r}"
        )

    def test_a_prerelease_marker_does_not_survive_into_a_final_version(self):
        import jnwb

        final = not any(m in jnwb.__version__ for m in ("rc", "a", "b", "dev"))
        if final:
            assert "candidate" not in jnwb.__status__.lower(), (
                "the version is final but the package still calls itself a release candidate"
            )



class TestPublishCapablePipelineHygiene:
    """Three gaps on a pipeline that can upload to PyPI, each reproduced before repair.

    No workflow-level ``permissions``, so every job inherited the repository default while
    two of them ask for ``id-token: write``. No ``concurrency``, so two pushes in quick
    succession ran overlapping publish-capable pipelines. And ``workflow_dispatch`` defaulted
    to ``testpypi``, so pressing Run workflow without reading the form published.
    """

    def test_a_least_privilege_floor_is_declared_at_the_workflow_level(self):
        permissions = _load_workflow().get("permissions")
        assert permissions == {"contents": "read"}, permissions

    def test_only_the_publish_jobs_raise_that_floor(self):
        jobs = _load_workflow()["jobs"]
        raised = {
            name: job["permissions"]
            for name, job in jobs.items()
            if isinstance(job, dict) and "permissions" in job
        }
        assert set(raised) == {"publish-testpypi", "publish-pypi"}, raised
        for name, permissions in raised.items():
            assert permissions.get("id-token") == "write", (name, permissions)

    def test_one_run_per_ref(self):
        concurrency = _load_workflow().get("concurrency")
        assert concurrency, "no concurrency group; overlapping runs are possible again"
        assert "github.ref" in concurrency["group"], concurrency

    def test_a_tags_push_and_release_runs_do_not_share_a_group(self):
        """The release run waits on the push run's TestPyPI job; sharing a group, whichever
        started second would queue behind the other and the wait would time out. Pushes to one
        branch still share a group, so the later still cancels the earlier."""
        group = " ".join(_load_workflow()["concurrency"]["group"].split())
        assert group == "${{ github.workflow }}-${{ github.event_name }}-${{ github.ref }}", group

    def test_a_run_that_can_publish_is_never_cancelled_mid_upload(self):
        """Cancelling a tag or release run is the failure this is meant to prevent."""
        cancel = str(_load_workflow()["concurrency"]["cancel-in-progress"])
        assert "refs/tags/" in cancel and "release" in cancel, cancel
        assert cancel.strip().lower() not in {"true", "${{ true }}"}, cancel

    def test_a_manual_dispatch_publishes_nothing_by_default(self):
        target = _load_workflow()[True]["workflow_dispatch"]["inputs"]["target"]
        assert target["default"] == "none", target
        assert set(target["options"]) == {"none", "testpypi"}, target

    def test_the_default_really_does_reach_no_publish_job(self):
        """The condition, not just the default: `none` must satisfy neither publish job."""
        jobs = _load_workflow()["jobs"]
        for name in ("publish-testpypi", "publish-pypi"):
            condition = " ".join(str(jobs[name]["if"]).split())
            assert "inputs.target == 'none'" not in condition, (name, condition)
        testpypi = " ".join(str(jobs["publish-testpypi"]["if"]).split())
        assert "inputs.target == 'testpypi'" in testpypi, testpypi
        assert "workflow_dispatch" not in " ".join(str(jobs["publish-pypi"]["if"]).split())

    def test_every_third_party_action_is_pinned_to_a_commit(self):
        """A branch ref on a step holding `id-token: write` is whatever that branch becomes."""
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        uses = re.findall(r"^\s*uses:\s*(\S+)", text, re.M)
        assert len(uses) >= 6, f"only {len(uses)} actions found; the sweep is wrong"
        publishers = [u for u in uses if "pypi-publish" in u]
        assert len(publishers) == 2, publishers
        for ref in publishers:
            _, _, version = ref.partition("@")
            assert re.fullmatch(r"[0-9a-f]{40}", version), (
                f"{ref} is not pinned to a commit; a mutable ref can be moved under a step "
                f"that mints an OIDC token for this project"
            )

    def test_each_pin_records_which_version_it_is(self):
        """A bare 40-hex string nobody can read is a pin that never gets updated."""
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        pinned = re.findall(r"uses:\s*\S*pypi-publish@[0-9a-f]{40}\s*#\s*(v[\d.]+)", text)
        assert len(pinned) == 2, f"a pin carries no version comment: {pinned}"
        assert len(set(pinned)) == 1, f"the two publish jobs pin different versions: {pinned}"
