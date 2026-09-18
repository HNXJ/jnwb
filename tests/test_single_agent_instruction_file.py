"""`AGENTS.md` is the only repository-level instruction file.

A second rule set at the root is not a backup, it is a fork: two files that drift until an
agent reads whichever one it was pointed at. `CLAUDE.md` was 215 bytes saying "the rules are
in AGENTS.md", and `AGENTS.md` said back that `CLAUDE.md` "carries phase and policy" -- a
claim about a file that carried a pointer. Both are gone; this keeps them gone.

A contributor's own ignored `CLAUDE.md` is their business, so the check is about *tracked*
state, not about what sits in a working directory.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Root-level filenames that assistants and agent harnesses read as instructions.
ASSISTANT_INSTRUCTION_FILES = [
    "CLAUDE.md",
    "GEMINI.md",
    "COPILOT.md",
    ".cursorrules",
    ".windsurfrules",
]


def _tracked_root_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", ":(top)*"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    names = {line for line in result.stdout.splitlines() if "/" not in line}
    assert "AGENTS.md" in names, (
        "git ls-files did not report AGENTS.md at the root; this test is not reading the "
        "repository it thinks it is"
    )
    return names


def test_agents_md_is_the_only_tracked_root_instruction_file() -> None:
    tracked = _tracked_root_files()
    extra = sorted(name for name in ASSISTANT_INSTRUCTION_FILES if name in tracked)
    assert not extra, (
        f"{extra} are tracked at the repository root alongside AGENTS.md. A rule that is not "
        f"in AGENTS.md is not a rule of this repository; delete the file rather than "
        f"maintaining a second copy."
    )


def test_a_local_claude_md_is_ignored_rather_than_forbidden() -> None:
    """Ignored, so a contributor's own copy neither lands in the repository nor trips a gate."""
    result = subprocess.run(
        ["git", "check-ignore", "-v", "CLAUDE.md"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        "CLAUDE.md is not git-ignored, so a local copy can be committed by accident: "
        f"{result.stderr.strip() or result.stdout.strip()}"
    )
    assert ".gitignore" in result.stdout, f"unexpected ignore source: {result.stdout.strip()}"

    from scripts.harness_gate import ALLOWED_ROOT_FILES

    assert "CLAUDE.md" in ALLOWED_ROOT_FILES, (
        "the root-freeze gate would reject a contributor's own ignored CLAUDE.md; it is "
        "permitted locally and untracked, which is the point of ignoring it"
    )


@pytest.mark.parametrize(
    "rel", ["AGENTS.md", "scripts/harness_gate.py", "tests/test_jnwb_frozen_boundary.py"]
)
def test_no_live_surface_cites_a_file_that_is_no_longer_tracked(rel: str) -> None:
    """The prose that pointed at `CLAUDE.md` for policy has to point somewhere real."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    for line in text.splitlines():
        if "CLAUDE.md" not in line:
            continue
        # The gate's allowlist entry names it deliberately, and says so on the next lines.
        assert "ALLOWED_ROOT_FILES" in text and rel == "scripts/harness_gate.py", (
            f"{rel} still cites CLAUDE.md as a source of rules: {line.strip()}"
        )


def test_agents_md_states_that_it_is_the_only_one() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "only repository-level" in text, (
        "AGENTS.md does not say it is the only repository-level instruction file, which is "
        "the rule the deleted CLAUDE.md carried"
    )
