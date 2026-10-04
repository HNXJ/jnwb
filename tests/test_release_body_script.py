"""The release notes the tag push run writes, and the check that refuses them.

`scripts/release_body.py` writes a pinned install command, the supported Python range and the
version's `CHANGELOG.md` section, then applies the release gate's body check. Each refusal is
driven here: a check that cannot refuse would let the run create a Release whose notes the
gate rejects afterwards.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "release_body.py"

# See tests/test_release_body_gate.py: `append`, and imports inside the tests' module scope
# only after it, because `scripts/` is not in the wheel.
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.release_body import build_body, changelog_section  # noqa: E402
from scripts.release_gate import check_release_body_claims, release_metadata  # noqa: E402

#: The shape of GitHub's generated notes, as the hand-written 0.2.8 body was built from.
GENERATED_NOTES = (
    "## What's Changed\n"
    "* Release 0.2.8 by @someone in https://github.com/owner/jnwb/pull/1\n\n"
    "**Full Changelog**: https://github.com/owner/jnwb/compare/v0.2.7...v0.2.8\n"
)


def _tree(tmp_path: pathlib.Path, version: str, changelog: str) -> pathlib.Path:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "widget-lib"\n'
        'requires-python = ">=3.9"\n'
        "classifiers = [\n"
        '    "Programming Language :: Python :: 3.9",\n'
        '    "Programming Language :: Python :: 3.10",\n'
        '    "Programming Language :: Python :: 3.11",\n'
        "]\n",
        encoding="utf-8",
    )
    (tmp_path / "jnwb").mkdir(exist_ok=True)
    (tmp_path / "jnwb" / "__init__.py").write_text(f"__version__ = '{version}'\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return tmp_path


CHANGELOG = (
    "# Changelog\n\n"
    "## [Unreleased]\n\n"
    "## [7.1.0] - 2026-10-01\n\n"
    "### Fixed\n\n- A widget no longer wobbles.\n\n"
    "## [7.0.0] - 2026-09-01\n\n"
    "### Added\n\n- Widgets.\n"
)


class TestTheBody:
    def test_the_runs_body_passes_the_check_and_states_what_it_must(self, tmp_path):
        root = _tree(tmp_path, "7.1.0", CHANGELOG)
        body, violations = build_body(root, "v7.1.0")
        assert violations == [] and body is not None
        assert body.startswith("```bash\npip install widget-lib==7.1.0\n```\n"), body
        assert "\nSupports Python 3.9 through 3.11.\n" in body, body
        assert body.endswith("### Fixed\n\n- A widget no longer wobbles.\n"), body
        assert "7.0.0" not in body and "Unreleased" not in body, body
        assert check_release_body_claims(body, release_metadata(root), tag_name="v7.1.0",
                                         is_prerelease=False) == []

    def test_this_repositorys_body_passes_for_its_own_tag(self):
        version = release_metadata(REPO_ROOT).version
        body, violations = build_body(REPO_ROOT, f"v{version}")
        assert violations == [], violations
        assert f"pip install jnwb=={version}" in body

    def test_a_generated_notes_body_is_refused(self, tmp_path):
        """What the run would create without the script: no install command, no range."""
        metadata = release_metadata(_tree(tmp_path, "7.1.0", CHANGELOG))
        violations = check_release_body_claims(GENERATED_NOTES, metadata, tag_name="v7.1.0",
                                               is_prerelease=False)
        assert any("no `pip install`" in v for v in violations), violations
        assert any("no Python support range" in v for v in violations), violations

    def test_a_tag_naming_another_version_is_refused(self, tmp_path):
        body, violations = build_body(_tree(tmp_path, "7.1.0", CHANGELOG), "v7.2.0")
        assert body is None
        assert any("does not name the declared version 7.1.0" in v for v in violations), violations

    def test_a_prerelease_version_is_refused(self, tmp_path):
        changelog = CHANGELOG.replace("[7.1.0]", "[7.1.0rc1]")
        body, violations = build_body(_tree(tmp_path, "7.1.0rc1", changelog), "v7.1.0rc1")
        assert body is None
        assert any("a prerelease under PEP 440" in v for v in violations), violations

    def test_a_section_that_misstates_the_python_range_is_refused(self, tmp_path):
        """The check reads the whole body, the changelog section included."""
        changelog = CHANGELOG.replace("- A widget no longer wobbles.",
                                      "- Supports Python 3.8 through 3.11.")
        body, violations = build_body(_tree(tmp_path, "7.1.0", changelog), "v7.1.0")
        assert body is None
        assert any("claims a 3.8 floor" in v for v in violations), violations

    def test_a_version_without_a_section_is_refused(self, tmp_path):
        body, violations = build_body(_tree(tmp_path, "7.2.0", CHANGELOG), "v7.2.0")
        assert body is None
        assert violations == ["CHANGELOG.md has no non-empty section headed "
                              "'## [7.2.0] - YYYY-MM-DD'"], violations

    def test_an_empty_section_is_no_section(self):
        assert changelog_section("## [1.0.0] - 2026-01-01\n\n## [0.9.0] - 2025-01-01\n- x\n",
                                 "1.0.0") is None
        assert changelog_section("## [1.0.0] - 2026-01-01\n- y\n", "1.0.0") == "- y"
        # A version that is a prefix of another is not that other's section.
        assert changelog_section("## [1.0.0.1] - 2026-01-01\n- z\n", "1.0.0") is None


class TestTheCommand:
    def _run(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                              text=True, timeout=120)

    def test_a_refused_body_exits_1_and_writes_nothing(self, tmp_path):
        (tmp_path / "tree").mkdir()
        root = _tree(tmp_path / "tree", "7.1.0", CHANGELOG)
        out = tmp_path / "body.md"
        result = self._run("--tag", "v7.2.0", "--output", str(out), "--root", str(root))
        assert result.returncode == 1, (result.stdout, result.stderr)
        assert "::error::release body:" in result.stderr, result.stderr
        assert not out.exists()

    def test_a_passing_body_is_written_with_lf_endings(self, tmp_path):
        (tmp_path / "tree").mkdir()
        root = _tree(tmp_path / "tree", "7.1.0", CHANGELOG)
        out = tmp_path / "body.md"
        result = self._run("--tag", "v7.1.0", "--output", str(out), "--root", str(root))
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert b"\r\n" not in out.read_bytes()
        assert out.read_text(encoding="utf-8") == build_body(root, "v7.1.0")[0]
