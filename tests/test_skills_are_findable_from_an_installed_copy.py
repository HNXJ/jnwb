"""An installed copy has to be able to say where the skills are.

`MANIFEST.in` grafts `skills/` and includes `AGENTS.md`, and its comment said that without
them "the sdist ships a library whose README tells an agent to read AGENTS.md, and no
AGENTS.md". The mechanism does not produce that outcome for anyone who installs: `packages.find`
is `include = ["jnwb*"]`, so `pip install jnwb-0.2.4.tar.gz` writes `jnwb/` into site-packages
and discards `skills/` and `AGENTS.md` -- verified by doing exactly that into a clean 3.12
environment, which yields `jnwb/` and `jnwb-0.2.4.dist-info/` and nothing else. Only someone who
unpacks the tarball by hand receives them, and 11 of the skills' 12 repository-relative links
point into `docs/`, which the sdist prunes.

Ruled 2026-09-16: one canonical tree, skills in the sdist, no duplicate tree under `jnwb/` to
force them into the wheel, and the discovery gap closed with a machine-readable pointer. These
tests hold the pointer honest and keep the second tree from appearing.
"""

from __future__ import annotations

import re
import subprocess
import tarfile
from pathlib import Path

import pytest

import jnwb

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def test_the_package_carries_a_pointer_to_the_skills() -> None:
    assert isinstance(jnwb.SKILLS_URL, str) and jnwb.SKILLS_URL
    assert "SKILLS_URL" in jnwb.__all__, "the pointer is not part of the public surface"


def test_the_pointer_names_the_tag_for_this_version_not_a_branch() -> None:
    """A branch pointer hands an agent skills written against a different API.

    Derived from `__version__` rather than compared to a literal, so a version bump moves it.
    """
    assert f"/tree/v{jnwb.__version__}/" in jnwb.SKILLS_URL, jnwb.SKILLS_URL
    assert jnwb.SKILLS_URL.endswith("/skills")
    assert "/tree/main/" not in jnwb.SKILLS_URL


def test_the_pointer_is_built_from_the_version_rather_than_written_down() -> None:
    """Read from the source: a literal that happens to match today would pass the test above."""
    source = (ROOT / "jnwb" / "__init__.py").read_text(encoding="utf-8")
    line = next(
        (l for l in source.splitlines() if l.startswith("SKILLS_URL")), None
    )
    assert line, "SKILLS_URL is no longer defined at module level in jnwb/__init__.py"
    assert "__version__" in line, f"the version is hardcoded into the pointer: {line}"


def test_the_pointer_addresses_the_repository_the_documentation_names() -> None:
    documented = (ROOT / "docs" / "agents.md").read_text(encoding="utf-8")
    match = re.search(r"https://github\.com/([^/]+/[^/]+)/tree/", documented)
    assert match, "docs/agents.md no longer links to a GitHub tree"
    assert f"github.com/{match.group(1)}/tree/" in jnwb.SKILLS_URL, (
        f"the pointer and the documentation name different repositories: {jnwb.SKILLS_URL}"
    )


def test_the_documented_example_shows_the_live_value() -> None:
    """The example in docs/agents.md is a literal, so it goes stale on a version bump."""
    documented = (ROOT / "docs" / "agents.md").read_text(encoding="utf-8")
    assert f"'{jnwb.SKILLS_URL}'" in documented, (
        f"docs/agents.md shows a SKILLS_URL that is not the live one ({jnwb.SKILLS_URL})"
    )


def test_the_documentation_states_that_pip_install_does_not_deliver_the_skills() -> None:
    """The claim the old MANIFEST.in comment got wrong, now stated where a reader will see it.

    The negation is what matters. `pip install` appears in this page for other reasons, so a
    test for the phrase alone passes on a page that says the opposite.
    """
    documented = (ROOT / "docs" / "agents.md").read_text(encoding="utf-8")
    assert "SKILLS_URL" in documented
    sentences = [s for s in re.split(r"(?<=[.:])\s", documented) if "pip install" in s]
    assert sentences, "docs/agents.md no longer mentions pip install at all"
    assert any("does not deliver" in s for s in sentences), (
        f"nothing states that an install does not deliver the skills: {sentences}"
    )


def test_the_manifest_comment_describes_what_the_manifest_does() -> None:
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    # Directives, not the raw text: this comment block quotes the directives it explains, and
    # commenting `graft skills` out would leave the phrase in the file.
    directives = [
        line.strip() for line in manifest.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert "graft skills" in directives, "the sdist no longer carries the skills at all"
    assert "include AGENTS.md" in directives, "the sdist no longer carries AGENTS.md"
    assert "SKILLS_URL" in manifest, (
        "the comment does not say how an installed copy finds the skills"
    )
    assert "site-packages and discards" in manifest, (
        "the comment does not state that an install drops skills/ and AGENTS.md"
    )


def test_there_is_exactly_one_skill_tree() -> None:
    """The ruling's hard constraint, and harness gate 2's: no copy under jnwb/.

    Scanned over tracked files rather than the working directory: a local `.venv` carries
    other packages' skill trees, and those are not this repository's problem.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "*SKILL.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    assert tracked, "git ls-files found no SKILL.md at all; this test would pass vacuously"
    # `artifacts/skills/` holds the skills about working on this repository; `artifacts/` is
    # pruned from the sdist, and no name may appear in both places.
    trees = {Path(name).parts[0] for name in tracked if not name.startswith("artifacts/skills/")}
    assert trees == {"skills"}, f"tracked SKILL.md files live outside skills/: {sorted(trees)}"
    shipped = {Path(name).parts[1] for name in tracked if name.startswith("skills/")}
    internal = {Path(name).parts[2] for name in tracked if name.startswith("artifacts/skills/")}
    assert not shipped & internal, f"one skill has two homes: {sorted(shipped & internal)}"
    assert not [name for name in tracked if name.startswith("jnwb/")], (
        "a second skill tree exists under jnwb/"
    )


def test_nothing_in_the_runtime_reads_a_skill() -> None:
    """The reason the wheel does not need them; if this changes, the ruling has to be revisited."""
    readers = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "jnwb").rglob("*.py")
        if "SKILL.md" in path.read_text(encoding="utf-8")
    ]
    assert not readers, f"a jnwb/ module opens a skill file: {readers}"

    # The pointer is the only thing in the package that mentions the tree at all.
    mentions = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "jnwb").rglob("*.py")
        if "/skills" in path.read_text(encoding="utf-8")
    ]
    assert mentions == ["jnwb/__init__.py"], (
        f"jnwb/ refers to the skills tree somewhere other than SKILLS_URL: {mentions}"
    )


#: Only an sdist of the version under test says anything about the current MANIFEST.in.
#: `dist/` in a working checkout collects old builds -- this one held 0.1.1 and 0.1.3, whose
#: manifests predate the graft, and matching the newest file by name would have tested those.
CURRENT_SDIST = ROOT / "dist" / f"jnwb-{jnwb.__version__}.tar.gz"


@pytest.mark.skipif(not CURRENT_SDIST.exists(), reason="no sdist of this version in dist/")
def test_a_built_sdist_carries_every_skill() -> None:
    """If a build of this version is present, the graft must actually have taken.

    Skipped in a bare checkout and live in CI's installed-wheel leg, which runs after
    `python -m build` has filled `dist/` -- so the graft is checked against a real archive on
    every push, without the suite building one itself.
    """
    expected = {path.parent.name for path in SKILLS.glob("*/SKILL.md")}
    with tarfile.open(CURRENT_SDIST, "r:gz") as archive:
        names = archive.getnames()
    shipped = {
        name.split("/")[2] for name in names
        if name.endswith("SKILL.md") and name.count("/") >= 3
    }
    assert shipped == expected, f"sdist carries {sorted(shipped)}, repository has {sorted(expected)}"
    assert any(name.endswith("/AGENTS.md") for name in names), "the sdist has no AGENTS.md"
