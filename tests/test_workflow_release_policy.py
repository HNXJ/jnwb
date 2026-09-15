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

    def test_tag_push_still_triggers_validation_pipeline(self):
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert re.search(r"tags:\s*\[\s*\"v\*\"\s*\]", workflow_text)
        assert "publish-pypi:" in workflow_text

    def test_testpypi_paths_remain_available(self):
        condition = _load_workflow()["jobs"]["publish-testpypi"]["if"]
        text = " ".join(str(condition).split())
        assert "github.event.release.prerelease" in text
        assert "contains(github.ref, 'rc')" in text
        assert "workflow_dispatch" in text


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

    def test_release_gate_does_not_hardcode_the_expected_version(self):
        gate = (REPO_ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
        import jnwb

        assert jnwb.__version__ not in gate, (
            "the release gate pins the current version as a literal; it must derive the "
            "expected version from the source package so it cannot drift"
        )
        assert "def jnwb_source_version" in gate
