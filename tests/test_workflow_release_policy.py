"""Regression tests for CI release / PyPI trigger topology.

Production PyPI is reached only from a `v*` tag push naming a final release, and only after
that run uploaded to TestPyPI and verified the upload from there. The same run then creates the
GitHub Release, its notes checked before it is created. No other event reaches PyPI.
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
    def test_publish_pypi_runs_only_on_a_v_tag_push(self):
        condition = _publish_pypi_if()
        assert condition.startswith(
            "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v') && "), condition
        assert " || " not in condition, condition
        assert "release" not in condition.replace("refs/tags/v", ""), condition
        assert "workflow_dispatch" not in condition and "inputs." not in condition, condition

    def test_no_published_release_triggers_the_workflow(self):
        """A second publishing path is a second run that can reach PyPI."""
        triggers = _load_workflow()[True]
        assert "release" not in triggers, sorted(triggers)
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "github.event.release" not in text
        assert "event_name == 'release'" not in text and "event_name != 'release'" not in text

    def test_prerelease_cannot_reach_production_pypi(self):
        """publish-pypi runs only when the verify job says the tag names a final release."""
        assert _publish_pypi_if().endswith(
            " && needs.verify-testpypi.outputs.final == 'true'"), _publish_pypi_if()
        verify = _load_workflow()["jobs"]["verify-testpypi"]
        assert verify["outputs"] == {"final": "${{ steps.kind.outputs.final }}"}, verify.get("outputs")

    def test_the_final_release_rule_agrees_with_pep_440(self):
        """The regex the `kind` step applies, against `packaging`'s own reading. A rule that
        admitted `rc`, `a`, `b` or `dev` would publish a prerelease to PyPI."""
        import subprocess

        from packaging.version import Version

        step = next(s for s in _load_workflow()["jobs"]["verify-testpypi"]["steps"]
                    if s.get("id") == "kind")
        assert " ".join(str(step["env"]["TAG"]).split()) == "${{ github.ref_name }}", step["env"]
        pattern = re.search(r'\[\[ "\$version" =~ (\S+) \]\]', step["run"]).group(1)
        assert 'echo "final=$final" >> "$GITHUB_OUTPUT"' in step["run"], step["run"]
        cases = ["0.2.9", "1.0", "10.20.30", "0.2.9.post1", "0.2.9rc1", "0.2.9a1", "0.2.9b2",
                 "0.2.9.dev3", "0.2.9rc1.post1", "0.2.9.post1.dev1", "1!0.2.9"]
        for version in cases:
            matched = re.fullmatch(pattern, version)
            # Not final by PEP 440 must never match; the epoch spelling may be refused too.
            assert bool(matched) <= (not Version(version).is_prerelease), version
            if "!" not in version:
                assert bool(matched) == (not Version(version).is_prerelease), version
        # The same pattern as bash reads it, off Windows, where `bash` can be the WSL launcher.
        import sys

        if sys.platform == "win32":
            return
        try:
            out = subprocess.run(
                ["bash", "-c",
                 f'for v in "$@"; do if [[ "$v" =~ {pattern} ]]; then echo "$v"; fi; done',
                 "_", *cases], capture_output=True, text=True, timeout=30)
        except (FileNotFoundError, OSError):
            return
        assert out.returncode == 0, out.stderr
        assert out.stdout.split() == ["0.2.9", "1.0", "10.20.30", "0.2.9.post1"], out.stdout

    @staticmethod
    def _bash():
        """A POSIX bash, or None. On Windows a bare `bash` can resolve to the WSL launcher in
        System32 ahead of PATH, so Git's own bash is looked up next to `git`."""
        import shutil
        import sys

        if sys.platform != "win32":
            return shutil.which("bash")
        git = shutil.which("git")
        # git.exe sits in Git\cmd, Git\bin or Git\mingw64\bin; bash in Git\usr\bin or Git\bin.
        for base in (Path(git).resolve().parents if git else ()):
            for candidate in (base / "usr" / "bin" / "bash.exe", base / "bin" / "bash.exe"):
                if candidate.is_file():
                    return str(candidate)
        return None

    def test_the_kind_step_run_in_bash_says_final_only_for_a_final_tag(self, tmp_path):
        """The step itself, not its regex: a `final=true` inserted before the output line, or
        a branch that never reaches `final=true`, passes a test that only reads the pattern."""
        import os
        import subprocess

        import pytest

        bash = self._bash()
        if bash is None:
            pytest.skip("no bash on this machine")
        step = next(s for s in _load_workflow()["jobs"]["verify-testpypi"]["steps"]
                    if s.get("id") == "kind")
        assert set(step["env"]) == {"TAG"}, step["env"]
        script = tmp_path / "kind.sh"
        script.write_bytes(step["run"].encode("utf-8"))
        expected = {"v0.2.9": "true", "v1.0": "true", "v0.2.9.post1": "true",
                    "v0.2.9rc1": "false", "v0.2.9a1": "false", "v0.2.9b1": "false",
                    "v0.2.9.dev1": "false"}
        for tag, final in expected.items():
            output = tmp_path / f"output_{tag}"
            output.write_bytes(b"")
            env = dict(os.environ, TAG=tag, GITHUB_OUTPUT=output.as_posix())
            result = subprocess.run([bash, script.as_posix()], env=env, capture_output=True,
                                    text=True, timeout=60)
            assert result.returncode == 0, (tag, result.stderr)
            lines = output.read_text(encoding="utf-8").splitlines()
            assert lines == [f"final={final}"], (tag, lines)

    def test_legacy_dual_trigger_if_is_rejected(self):
        """Regression: 0.1.6 workflow published on tag push *and* on release."""
        condition = _publish_pypi_if()
        normalized_legacy = " ".join(_LEGACY_DUAL_TRIGGER_IF.split())
        assert condition != normalized_legacy

    def test_testpypi_needs_build_and_pypi_needs_the_verification(self):
        """PyPI waits for the TestPyPI upload and its verification in the same run, and through
        them for the build and every test leg."""
        jobs = _load_workflow()["jobs"]
        assert jobs["publish-testpypi"]["needs"] == "build"
        assert jobs["verify-testpypi"]["needs"] == "publish-testpypi"
        assert jobs["publish-pypi"]["needs"] == "verify-testpypi"

    def test_every_test_leg_and_the_build_are_unconditional_and_required(self):
        import sys

        if str(REPO_ROOT) not in sys.path:
            sys.path.append(str(REPO_ROOT))
        from scripts.release_gate import required_ci_jobs

        jobs = _load_workflow()["jobs"]
        for jid in ("qualified", "test", "test-floors", "build"):
            assert "if" not in jobs[jid], (jid, jobs[jid].get("if"))
        required = required_ci_jobs(root=REPO_ROOT)
        assert jobs["build"]["name"] in required and jobs["test-floors"]["name"] in required
        assert any(name.startswith("Test (Python ") for name in required), required

    def test_any_condition_makes_a_job_optional_and_none_keeps_it_required(self):
        """No condition is special-cased: the release-event skip no longer exists, so a job
        carrying it is conditional like any other."""
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
        assert sorted(required_ci_jobs(workflow)) == ["C"]

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


class TestATagPushReusesTheDevRunOfItsCommit:
    """A `v*` tag push skips the test and floors legs' steps when a dev push run of this workflow
    at the same commit concluded success; the build always runs, so what is published is built
    and checked in the tag's own run.

    What would pass while that is broken: a lookup that accepts a failed or unfinished run, a run
    of another commit or branch, or runs on main, pull requests or dev pushes; a failed lookup
    read as a match; a leg step that runs regardless or skips unconditionally; or a build that
    skips too, leaving TestPyPI files no job in the run built.
    """

    LEGS = ("test", "test-floors")

    @staticmethod
    def _find_step():
        job = _load_workflow()["jobs"]["qualified"]
        steps = [s for s in job["steps"] if s.get("id") == "find"]
        assert len(steps) == 1, job["steps"]
        return job, steps[0]

    def test_only_a_tag_push_looks_for_a_passed_dev_run(self):
        job, step = self._find_step()
        assert job["outputs"] == {"run_id": "${{ steps.find.outputs.run_id }}"}, job["outputs"]
        env = {k: " ".join(str(v).split()) for k, v in step["env"].items()}
        assert env["SHA"] == "${{ github.sha }}", env
        assert env["EVENT_REF"] == "${{ github.event_name }}:${{ github.ref }}", env
        run = step["run"]
        block = re.search(r'^\s*case "\$EVENT_REF" in\n(.*?)^\s*esac\b', run, re.M | re.S)
        assert block, run
        arms = re.findall(r"^\s*([^\s(][^\n]*?)\)[ \t]*\n", block.group(1), re.M)
        assert arms == ["push:refs/tags/v*"], arms
        before = run[:block.start()]
        assert 'run_id=""' in before and "gh api" not in before, before

    def test_the_run_it_accepts_is_a_successful_dev_push_of_this_commit(self):
        run = self._find_step()[1]["run"]
        assert "actions/runs?event=push&branch=dev&head_sha=$SHA&status=success" in run, run
        for clause in ('.head_sha == env.SHA', '.head_branch == "dev"',
                       '.path == ".github/workflows/workflow.yml"', '.conclusion == "success"'):
            assert clause in run, clause

    def test_a_failed_lookup_runs_the_tests(self):
        run = self._find_step()[1]["run"]
        assert "set -e" not in run.replace("set -euo", ""), "a failed lookup must not end the job"
        assert re.search(r'if ! run_id=\$\(gh api .*?\); then\n(?:[^\n]*\n)*?\s*run_id=""\n\s*fi',
                         run, re.S), run
        assert 'echo "run_id=$run_id" >> "$GITHUB_OUTPUT"' in run, run

    def test_each_leg_skips_its_steps_exactly_when_a_run_matched(self):
        jobs = _load_workflow()["jobs"]
        for jid in self.LEGS:
            job = jobs[jid]
            assert job["needs"] == "qualified", (jid, job.get("needs"))
            assert job["env"]["QUALIFIED_BY"] == "${{ needs.qualified.outputs.run_id }}", jid
            report, *work = job["steps"]
            assert report["if"] == "env.QUALIFIED_BY != ''" and "$QUALIFIED_BY" in report["run"]
            for step in work:
                condition = " ".join(str(step.get("if", "")).split())
                assert re.fullmatch(r"(?:.+ && )?env\.QUALIFIED_BY == ''", condition), (
                    jid, step.get("name") or step.get("uses"), condition)

    def test_the_build_runs_in_full_on_every_push(self):
        build = _load_workflow()["jobs"]["build"]
        assert "QUALIFIED_BY" not in str(build) and "qualified" not in str(build.get("if")), build
        assert all("if" not in step for step in build["steps"]), [
            s.get("name") for s in build["steps"] if "if" in s]


class TestTestPyPIBeforePyPI:
    """The tag push publishes to TestPyPI, verifies the upload from there, and only then
    publishes to PyPI, in one run: `needs:` orders the jobs, and PyPI receives this run's
    artifact, each file checked against TestPyPI's hash before the upload.

    What would pass while the order is broken: a download from another run, a hash check that
    runs after the upload, carries `continue-on-error` or an `if:`, or reads another tag.
    """

    @staticmethod
    def _steps():
        return _load_workflow()["jobs"]["publish-pypi"]["steps"]

    def test_nothing_before_the_upload_can_be_skipped_or_forgiven(self):
        job = _load_workflow()["jobs"]["publish-pypi"]
        assert not job.get("continue-on-error"), "publish-pypi is continue-on-error"
        steps = self._steps()
        uploads = [i for i, s in enumerate(steps) if "pypi-publish" in str(s.get("uses", ""))]
        assert len(uploads) == 1, uploads
        for step in steps[:uploads[0] + 1]:
            assert "if" not in step and not step.get("continue-on-error"), step.get("name")

    def test_no_two_jobs_share_a_name(self):
        """Job names are what the release gate reads of a run; two alike cannot be told apart."""
        names = [job.get("name", jid) for jid, job in _load_workflow()["jobs"].items()]
        assert len(names) == len(set(names)), sorted(names)

    def test_pypi_receives_the_files_testpypi_received(self):
        """The artifact is this run's, the one build stored and publish-testpypi uploaded, and
        each file's sha256 must equal TestPyPI's record of it before the upload."""
        jobs = _load_workflow()["jobs"]
        stored = [s for s in jobs["build"]["steps"] if "upload-artifact" in str(s.get("uses", ""))]
        assert len(stored) == 1, stored
        name = stored[0]["with"]["name"]
        for jid in ("publish-testpypi", "publish-pypi"):
            got = [s for s in jobs[jid]["steps"] if "download-artifact" in str(s.get("uses", ""))]
            assert len(got) == 1, (jid, got)
            # Exactly a name and a path: a run-id, token or repository fetches another run's.
            assert got[0]["with"] == {"name": name, "path": "dist/"}, (jid, got[0]["with"])
        steps = self._steps()
        upload = next(i for i, s in enumerate(steps) if "pypi-publish" in str(s.get("uses", "")))
        download = next(i for i, s in enumerate(steps)
                        if "download-artifact" in str(s.get("uses", "")))
        assert download < upload, [s.get("name") for s in steps]
        checks = [s for s in steps[download + 1:upload]
                  if "https://test.pypi.org/pypi/jnwb/$version/json" in str(s.get("run", ""))]
        assert len(checks) == 1, "no step compares the files with TestPyPI before the upload"
        step = checks[0]
        run = step["run"]
        assert " ".join(str(step["env"]["TAG"]).split()) == "${{ github.ref_name }}", step["env"]
        assert "set -euo pipefail" in run and 'version="${TAG#v}"' in run, run
        assert "select(.filename == $name) | .digests.sha256" in run, run
        assert 'have=$(sha256sum "$file" | cut -d\' \' -f1)' in run, run
        assert re.search(r'if \[ -z "\$want" \] \|\| \[ "\$want" != "\$have" \]; then\s*\n'
                         r'[^\n]*\n\s*exit 1\b', run), run
        assert re.search(r'if \[ "\$count" -eq 0 \] \|\| \[ "\$count" -ne "\$remote" \]; then'
                         r'\s*\n[^\n]*\n\s*exit 1\b', run), run

    def test_pypi_publishes_through_the_pypi_environment_with_trusted_publishing(self):
        """The environment carries the approval rule; trusted publishing needs the OIDC token
        and nothing more."""
        job = _load_workflow()["jobs"]["publish-pypi"]
        assert job["environment"] == {"name": "pypi", "url": "https://pypi.org/p/jnwb"}, job
        assert job["permissions"] == {"id-token": "write", "contents": "read"}, job["permissions"]
        upload = [s for s in self._steps() if "pypi-publish" in str(s.get("uses", ""))][0]
        assert "password" not in (upload.get("with") or {}), upload
        assert "repository-url" not in (upload.get("with") or {}), upload

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

    def test_the_pypi_upload_needs_the_verify_job(self):
        jobs = _load_workflow()["jobs"]
        assert self._verify_job() == jobs["verify-testpypi"]
        assert jobs["publish-pypi"]["needs"] == "verify-testpypi"

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

    def test_no_job_the_pypi_upload_needs_can_be_forgiven(self):
        """A `continue-on-error` job concludes success when it fails, so `needs:` would read a
        failed upload or verification, or a failed job either depends on, as a pass. An `if:`
        with `always()`, `!cancelled()` or `failure()` runs a job after its dependency failed,
        which forgives that failure the same way."""
        jobs = _load_workflow()["jobs"]
        pending = ["publish-pypi"]
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
        assert {"verify-testpypi", "publish-testpypi", "build", "test", "test-floors"} <= seen, seen

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
        """Of the two other jobs that raise it, one reads Actions runs and nothing more, and the
        one that creates the GitHub Release writes contents and nothing more."""
        jobs = _load_workflow()["jobs"]
        raised = {
            name: job["permissions"]
            for name, job in jobs.items()
            if isinstance(job, dict) and "permissions" in job
        }
        assert set(raised) == {"publish-testpypi", "publish-pypi", "qualified",
                               "github-release"}, raised
        assert raised.pop("qualified") == {"actions": "read", "contents": "read"}
        assert raised.pop("github-release") == {"contents": "write"}
        for name, permissions in raised.items():
            assert permissions.get("id-token") == "write", (name, permissions)

    def test_one_run_per_ref(self):
        concurrency = _load_workflow().get("concurrency")
        assert concurrency, "no concurrency group; overlapping runs are possible again"
        assert "github.ref" in concurrency["group"], concurrency

    def test_a_run_that_can_publish_is_never_cancelled_mid_upload(self):
        """Cancelling a tag run is the failure this is meant to prevent."""
        cancel = " ".join(str(_load_workflow()["concurrency"]["cancel-in-progress"]).split())
        assert cancel == "${{ !startsWith(github.ref, 'refs/tags/') }}", cancel
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


class TestTheTagPushCreatesTheRelease:
    """After the PyPI upload the same run creates the GitHub Release, its notes written by
    `scripts/release_body.py` and refused by the body check before `gh release create` runs.

    What would pass while that is broken: a release job that runs before or without the upload,
    a check step that is skipped or forgiven, notes created from another file than the one
    checked, or a Release created with notes GitHub generates.
    """

    BODY_SCRIPT = "python scripts/release_body.py --tag \"$TAG\" --output \"$RUNNER_TEMP/release_body.md\""

    @staticmethod
    def _job():
        return _load_workflow()["jobs"]["github-release"]

    def test_the_release_follows_the_pypi_upload_in_the_tag_push_run(self):
        job = self._job()
        assert job["needs"] == "publish-pypi", job.get("needs")
        condition = " ".join(str(job["if"]).split())
        assert condition == "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')"
        assert not job.get("continue-on-error")

    def test_the_notes_are_checked_before_the_release_is_created(self):
        steps = self._job()["steps"]
        runs = [str(s.get("run", "")) for s in steps]
        write = [i for i, r in enumerate(runs) if self.BODY_SCRIPT in r]
        create = [i for i, r in enumerate(runs) if "gh release create" in r]
        assert len(write) == 1 and len(create) == 1 and write[0] < create[0], runs
        for step in steps[:create[0] + 1]:
            assert "if" not in step and not step.get("continue-on-error"), step.get("name")
        for i in (write[0], create[0]):
            assert " ".join(str(steps[i]["env"]["TAG"]).split()) == "${{ github.ref_name }}"
        command = " ".join(runs[create[0]].replace("\\\n", " ").split())
        assert command == ('gh release create "$TAG" --verify-tag --title "$TAG" '
                           '--notes-file "$RUNNER_TEMP/release_body.md"'), command
        assert steps[create[0]]["env"]["GH_TOKEN"] == "${{ github.token }}"
        assert any("actions/checkout" in str(s.get("uses", "")) for s in steps[:write[0]])

    def test_no_job_that_can_write_leaves_its_token_in_the_checkout(self):
        """`actions/checkout` stores the job's token in `.git/config` unless told not to; in a
        job with `contents: write` any later step could push with it."""
        jobs = _load_workflow()["jobs"]
        writers = [jid for jid, job in jobs.items()
                   if "write" in (job.get("permissions") or {}).get("contents", "")]
        assert writers == ["github-release"], writers
        for jid in writers:
            checkouts = [s for s in jobs[jid]["steps"]
                         if "actions/checkout" in str(s.get("uses", ""))]
            assert checkouts, jid
            for step in checkouts:
                assert (step.get("with") or {}).get("persist-credentials") is False, (jid, step)

    def test_the_notes_are_checked_before_anything_reaches_pypi(self):
        """A body the check refuses stops the run while PyPI is still untouched."""
        steps = _load_workflow()["jobs"]["verify-testpypi"]["steps"]
        checks = [s for s in steps if self.BODY_SCRIPT in str(s.get("run", ""))]
        assert len(checks) == 1, [s.get("name") for s in steps]
        assert checks[0]["if"] == "steps.kind.outputs.final == 'true'", checks[0].get("if")
        assert not checks[0].get("continue-on-error")
        kind = next(i for i, s in enumerate(steps) if s.get("id") == "kind")
        assert steps.index(checks[0]) > kind

    def test_the_contributing_steps_describe_this_order(self):
        """Steps 4 to 6 of "Releasing" are what a maintainer follows; a step that still says to
        publish a Release by hand would have them do what the workflow no longer reads."""
        text = (REPO_ROOT / ".github" / "CONTRIBUTING.md").read_text(encoding="utf-8")
        section = re.search(r"^## Releasing\n(.*?)^## ", text, re.M | re.S).group(1)
        steps = dict(re.findall(r"^([4-6])\. (.*?)(?=^\d\. |^\*\*|\Z)", section, re.M | re.S))
        assert sorted(steps) == ["4", "5", "6"], sorted(steps)
        four, five = (" ".join(steps[k].split()) for k in ("4", "5"))
        assert "`publish-testpypi`" in four and "`verify-testpypi`" in four, four
        assert "`scripts/release_body.py`" in four, four
        assert "`publish-pypi` needs `verify-testpypi`" in five, five
        assert "this run's distribution artifact" in five and "`pypi` environment" in five, five
        assert "`github-release`" in five and "`check_release_body_claims`" in five, five
        assert "`gh release create`" in five and "for a final version only" in five, five
        jobs = _load_workflow()["jobs"]
        for job_id in re.findall(r"`([a-z]+(?:-[a-z]+)+)`", four + five):
            assert job_id in jobs, job_id
        assert "release: published" not in section and "Create a **GitHub Release**" not in section

    def test_the_body_script_exists_and_reuses_the_release_gates_check(self):
        source = (REPO_ROOT / "scripts" / "release_body.py").read_text(encoding="utf-8")
        assert "from scripts.release_gate import" in source, source[:400]
        for name in ("check_release_body_claims", "release_metadata"):
            assert re.search(rf"^\s+{name},$", source, re.M), name
