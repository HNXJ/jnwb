"""Checks that the public surface matches the manifest in artifacts/process/public_surface.json."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

import jnwb

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "artifacts" / "process" / "public_surface.json"


def load_manifest() -> dict[str, list[str]]:
    """Return the recorded lists of symbols, modules and skills."""
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def live_symbols() -> list[str]:
    """Return the names in ``jnwb.__all__``."""
    return list(jnwb.__all__)


def live_modules() -> list[str]:
    """Return the names of tracked .py files and packages directly under jnwb/."""
    listed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "jnwb"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    modules: set[str] = set()
    for path in listed.splitlines():
        parts = path.split("/")[1:]
        if len(parts) == 1 and parts[0].endswith(".py"):
            # `__init__` is a .py file directly under jnwb/, so it is listed like the others.
            modules.add(parts[0][: -len(".py")])
        elif len(parts) == 2 and parts[1] == "__init__.py":
            modules.add(parts[0])
    return sorted(modules)


def live_skills(skills_dir: Path = REPO_ROOT / "skills") -> list[str]:
    """Return the directories directly under ``skills/`` that hold a SKILL.md."""
    return sorted(
        entry.name
        for entry in skills_dir.iterdir()
        if entry.is_dir() and (entry / "SKILL.md").is_file()
    )


def surface_difference(
    name: str, manifest_entries: list[str], live_entries: list[str]
) -> str | None:
    """Describe the entries added to or removed from one list, or return None when they agree."""
    recorded, live = set(manifest_entries), set(live_entries)
    added = sorted(live - recorded)
    removed = sorted(recorded - live)
    if not added and not removed:
        return None
    lines = [f"{name} differs from artifacts/process/public_surface.json"]
    lines += [f"  added to the live {name}: {entry}" for entry in added]
    lines += [f"  removed from the live {name}: {entry}" for entry in removed]
    return "\n".join(lines)


def assert_surface_matches(name: str, manifest_entries: list[str], live_entries: list[str]) -> None:
    """Fail with a message that names each added and each removed entry."""
    difference = surface_difference(name, manifest_entries, live_entries)
    assert difference is None, difference


@pytest.mark.requires_git_checkout
def test_live_surface_matches_the_manifest():
    """Symbols, modules and skills each equal the recorded manifest."""
    manifest = load_manifest()
    differences = [
        difference
        for difference in (
            surface_difference("symbols", manifest["symbols"], live_symbols()),
            surface_difference("modules", manifest["modules"], live_modules()),
            surface_difference("skills", manifest["skills"], live_skills()),
        )
        if difference is not None
    ]
    assert not differences, "\n".join(differences)


def test_a_planted_extra_symbol_fails_naming_it(monkeypatch):
    """A symbol exported but absent from the manifest fails and is named."""
    manifest = load_manifest()
    monkeypatch.setattr(jnwb, "__all__", list(jnwb.__all__) + ["planted_symbol"])
    assert "planted_symbol" in jnwb.__all__
    assert "planted_symbol" not in manifest["symbols"]
    with pytest.raises(AssertionError, match="planted_symbol"):
        assert_surface_matches("symbols", manifest["symbols"], live_symbols())


def test_a_planted_removed_skill_fails_naming_it(tmp_path):
    """A skill directory missing from the live tree fails and is named."""
    manifest = load_manifest()
    removed = manifest["skills"][-1]
    for name in manifest["skills"]:
        if name == removed:
            continue
        (tmp_path / name).mkdir()
        (tmp_path / name / "SKILL.md").write_text("", encoding="utf-8")
    assert removed not in live_skills(tmp_path)
    with pytest.raises(AssertionError, match=re.escape(f"removed from the live skills: {removed}")):
        assert_surface_matches("skills", manifest["skills"], live_skills(tmp_path))


def test_the_manifest_lists_are_sorted_unique_and_non_empty():
    """Each recorded list is non-empty, sorted and free of repeated entries."""
    manifest = load_manifest()
    for name in ("symbols", "modules", "skills"):
        entries = manifest[name]
        assert entries, f"{name} is empty"
        assert entries == sorted(entries), f"{name} is not sorted"
        repeats = sorted({entry for entry in entries if entries.count(entry) > 1})
        assert not repeats, f"{name} repeats {repeats}"
