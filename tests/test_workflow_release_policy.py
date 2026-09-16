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

