"""Changelog fragments: one file per change, assembled into ``CHANGELOG.md`` at release.

Two claims carry the design, and each has a test built from its own case:

* two changes made on parallel branches merge without conflict, where two edits under
  ``## [Unreleased]`` do not -- the control is the point, since a merge test that cannot fail
  says nothing about the layout;
* the assembled text equals the hand-written form of a past release, byte for byte, with the
  section placed where the release process puts it.

The fragments for the past releases are split out of ``CHANGELOG.md`` here, one per top-level
bullet, and numbered from zero within each category. Numbering restarts per category so the
order of the ``###`` blocks has to come from the assembler's category order, not from the
file names.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Appended, not prepended: prepending would put the checkout's jnwb/ ahead of an installed copy.
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts.assemble_changelog import (  # noqa: E402
    CATEGORIES,
    FragmentError,
    assemble,
    main,
    read_fragments,
)
from scripts.release_gate import unreleased_entry_lines  # noqa: E402

CHANGELOG_TEXT = (ROOT / "CHANGELOG.md").read_bytes().decode("utf-8")
HEADING_TO_CATEGORY = {heading: category for category, heading in CATEGORIES.items()}


def _split_release(text: str, version: str):
    """``(changelog without the section, section, fragments)`` for one released version."""
    lines = text.splitlines(keepends=True)
    unreleased = lines.index("## [Unreleased]\n")
    start = next(i for i, line in enumerate(lines) if line.startswith(f"## [{version}] - "))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    header = "".join(lines[:unreleased + 1]) + "\n"
    section = "".join(lines[start:end])
    older = "".join(lines[end:])

    fragments = []
    category = None
    for line in lines[start + 1:end]:
        if line.startswith("### "):
            category = HEADING_TO_CATEGORY[line[4:].strip()]
            fragments.append([category, []])
        elif line.startswith("- "):
            fragments.append([category, [line]])
        elif fragments and fragments[-1][1]:
            fragments[-1][1].append(line)
    bullets = [(cat, "".join(body)) for cat, body in fragments if body]
    return header + older, header + section + older, bullets


def _write_fragments(directory: Path, bullets) -> None:
    directory.mkdir()
    counts = {}
    # Written in reverse so that nothing depends on creation order.
    numbered = []
    for category, body in bullets:
        n = counts.get(category, 0)
        counts[category] = n + 1
        numbered.append((f"{n:03d}.{category}.md", body.rstrip("\n") + "\n"))
    for name, body in reversed(numbered):
        (directory / name).write_bytes(body.encode("utf-8"))


@pytest.mark.parametrize("version, date", [("0.2.6.1", "2026-09-25"), ("0.1.8", "2026-09-11")])
def test_assembly_reproduces_a_hand_written_release(tmp_path, version, date):
    without, expected, bullets = _split_release(CHANGELOG_TEXT, version)
    assert len({cat for cat, _ in bullets}) >= 2, "the case needs more than one category"
    assert without != expected
    _write_fragments(tmp_path / "changelog.d", bullets)

    assembled = assemble(without, version, date, read_fragments(tmp_path / "changelog.d"))

    assert assembled == expected


def test_the_release_gate_reads_the_assembled_file(tmp_path):
    changelog = "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-09-01\n\n### Added\n\n- old\n"
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / "a.fixed.md").write_bytes(b"- a fix\n")
    assembled = assemble(changelog, "0.1.1", "2026-09-02", read_fragments(tmp_path / "changelog.d"))
    assert unreleased_entry_lines(assembled) == []
    assert re.search(r"^## \[0\.1\.1\] - 2026-09-02\s*$", assembled, re.MULTILINE)
    assert assembled.endswith("## [0.1.0] - 2026-09-01\n\n### Added\n\n- old\n")


_GIT_ENV = {k: v for k, v in os.environ.items()
            if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")}


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), "-c", "user.name=jnwb-test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=", "-c", "core.autocrlf=false", *args],
        capture_output=True, text=True, env=_GIT_ENV,
    )


def _two_branches(repo: Path, change_a, change_b) -> subprocess.CompletedProcess:
    """Apply ``change_a`` and ``change_b`` on two branches off one commit; merge b into a."""
    assert _git(repo.parent, "init", "-q", str(repo)).returncode == 0
    (repo / "CHANGELOG.md").write_bytes(
        b"# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-09-01\n\n### Added\n\n- old\n")
    for step in (("add", "CHANGELOG.md"), ("commit", "-q", "-m", "base"),
                 ("branch", "-M", "base"), ("checkout", "-q", "-b", "b")):
        assert _git(repo, *step).returncode == 0, step
    change_b(repo)
    assert _git(repo, "add", "-A").returncode == 0
    assert _git(repo, "commit", "-q", "-m", "b").returncode == 0
    assert _git(repo, "checkout", "-q", "-b", "a", "base").returncode == 0
    change_a(repo)
    assert _git(repo, "add", "-A").returncode == 0
    assert _git(repo, "commit", "-q", "-m", "a").returncode == 0
    return _git(repo, "merge", "--no-edit", "b")


def _fragment(name, text):
    def write(repo: Path) -> None:
        (repo / "changelog.d").mkdir(exist_ok=True)
        (repo / "changelog.d" / name).write_bytes(text.encode("utf-8"))
    return write


def _under_unreleased(text):
    def write(repo: Path) -> None:
        path = repo / "CHANGELOG.md"
        old = path.read_bytes().decode("utf-8")
        path.write_bytes(old.replace("## [Unreleased]\n", f"## [Unreleased]\n\n{text}\n", 1)
                         .encode("utf-8"))
    return write


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


@needs_git
def test_two_parallel_fragments_merge_without_conflict(tmp_path):
    repo = tmp_path / "repo"
    merged = _two_branches(repo, _fragment("gamma.added.md", "- gamma\n"),
                           _fragment("delta.fixed.md", "- delta\n"))
    assert merged.returncode == 0, merged.stdout + merged.stderr

    changelog = (repo / "CHANGELOG.md").read_bytes().decode("utf-8")
    assembled = assemble(changelog, "0.1.1", "2026-09-02", read_fragments(repo / "changelog.d"))
    assert "### Added\n\n- gamma\n\n### Fixed\n\n- delta\n\n## [0.1.0]" in assembled


@needs_git
def test_the_same_two_changes_written_under_unreleased_conflict(tmp_path):
    """The control: without fragments, the same parallel work collides."""
    merged = _two_branches(tmp_path / "repo", _under_unreleased("- gamma"),
                           _under_unreleased("- delta"))
    assert merged.returncode != 0
    assert "CONFLICT" in merged.stdout + merged.stderr


def test_a_released_version_is_refused():
    with pytest.raises(FragmentError, match="already has a section"):
        assemble(CHANGELOG_TEXT, "0.2.7", "2026-09-29", [("added", "- x\n", Path("x"))])


def test_hand_written_unreleased_lines_are_refused():
    changelog = "# Changelog\n\n## [Unreleased]\n\n- pending\n\n## [0.1.0] - 2026-09-01\n"
    with pytest.raises(FragmentError, match="hand-written"):
        assemble(changelog, "0.1.1", "2026-09-02", [("added", "- x\n", Path("x"))])


@pytest.mark.parametrize("name, body, message", [
    ("note.md", "- x\n", "is named"),
    ("note.improved.md", "- x\n", "unknown category"),
    ("note.added.md", "\n\n", "empty"),
    ("note.added.md", "plain prose\n", "bullet"),
    ("note.added.md", "- x\n\n### Fixed\n", "headings"),
    ("note.added.md", "- x\r\n", "LF"),
])
def test_a_malformed_fragment_raises_rather_than_being_skipped(tmp_path, name, body, message):
    (tmp_path / name).write_bytes(body.encode("utf-8"))
    with pytest.raises(FragmentError, match=message):
        read_fragments(tmp_path)


def test_the_command_writes_the_section_and_consumes_its_fragments(tmp_path, capsys):
    changelog = tmp_path / "CHANGELOG.md"
    original = b"# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-09-01\n\n### Added\n\n- old\n"
    changelog.write_bytes(original)
    fragments = tmp_path / "changelog.d"
    fragments.mkdir()
    (fragments / "a.added.md").write_bytes(b"- new\n")
    (fragments / "README.md").write_bytes(b"How to write a fragment.\n")
    common = ["--version", "0.1.1", "--date", "2026-09-02",
              "--changelog", str(changelog), "--fragments", str(fragments)]

    assert main([*common, "--dry-run"]) == 0
    assert changelog.read_bytes() == original
    assert (fragments / "a.added.md").exists()
    assert capsys.readouterr().out == "## [0.1.1] - 2026-09-02\n\n### Added\n\n- new\n\n"

    assert main(common) == 0
    assert changelog.read_bytes() == (
        b"# Changelog\n\n## [Unreleased]\n\n## [0.1.1] - 2026-09-02\n\n### Added\n\n- new\n\n"
        b"## [0.1.0] - 2026-09-01\n\n### Added\n\n- old\n")
    assert sorted(p.name for p in fragments.iterdir()) == ["README.md"]
