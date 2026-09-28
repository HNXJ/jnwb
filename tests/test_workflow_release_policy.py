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

    def test_publish_pypi_still_needs_build(self):
        jobs = _load_workflow()["jobs"]
        assert jobs["publish-pypi"]["needs"] == "build"
        assert jobs["publish-testpypi"]["needs"] == "build"

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
    """The tag push publishes to TestPyPI, and PyPI publishes only after that succeeded. The release event is a different run from the tag push, so `needs:` cannot order
    the two jobs; the PyPI job's first step reads the push run's TestPyPI job and fails unless it
    concluded success.

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

    def test_the_gate_reads_the_testpypi_job_by_its_name(self):
        name = _load_workflow()["jobs"]["publish-testpypi"]["name"]
        gate = self._gate()
        assert gate["env"]["TESTPYPI_JOB"] == name
        # A job still running has no conclusion; it must read as pending, never as success.
        assert ("select(.name == env.TESTPYPI_JOB) | (.conclusion // \"pending\")"
                in gate["run"]), gate["run"]

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
        assert passing == ['*" success "*'], arms
        assert len(re.findall(r"\bexit 0\b", run)) == 1, "an exit 0 outside the success arm"
        failing = [pattern for pattern, body in arms if re.search(r"\bexit 1\b", body)]
        assert "*" in failing, "a conclusion other than success and pending does not fail"

    def test_waiting_for_the_push_run_ends_in_failure_after_an_hour(self):
        """A pending or absent job waits; without the deadline it would wait until the runner's
        own limit and never say why."""
        run = self._gate()["run"]
        assert "deadline=$((SECONDS + 3600))" in run
        block = re.search(r'^\s*case " \$conclusions " in\n(.*?)^\s*esac\b', run, re.M | re.S)
        waiting = re.search(r'^\s*\*" pending "\*\|"  "\)\s*\n(.*?);;', block.group(1), re.M | re.S)
        assert waiting, "the gate has no arm for a pending or absent job"
        assert re.search(r'if \[ "\$SECONDS" -ge "\$deadline" \]; then\s*\n[^\n]*\n\s*exit 1\b',
                         waiting.group(1)), waiting.group(1)


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
