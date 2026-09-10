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
