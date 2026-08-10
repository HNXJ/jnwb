"""Guards the skill-tree consolidation done 2026-08-10 (artifacts/.lab/
agent-harness-audit-20260810.json, P1 item): .claude/skills/ is now the single tracked
canonical skill source. .agents/skills/ was retired because the previous two-tree design (one
tracked+stale, one loaded+gitignored+current) had already drifted 348 of ~450 combined lines
apart on one skill alone, with no automated check to catch it.

These tests are the automated check that was missing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SKILLS = REPO_ROOT / ".claude" / "skills"
AGENTS_SKILLS = REPO_ROOT / ".agents" / "skills"


def _git_tracked_files(root: Path) -> set[Path]:
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", "--", str(root.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {REPO_ROOT / line for line in result.stdout.splitlines() if line}


class TestSingleCanonicalSkillTree:
    def test_agents_skills_no_longer_exists(self):
        # The old "reference/source" tree -- if this reappears (e.g. someone re-adds it out of
        # habit), the exact drift risk the audit found is back.
        assert not AGENTS_SKILLS.exists(), (
            ".agents/skills/ has reappeared -- this repo now has exactly one skill tree "
            "(.claude/skills/, tracked directly). Do not recreate .agents/skills/; if a skill "
            "needs updating, edit .claude/skills/<name>/SKILL.md."
        )

    def test_claude_skills_dir_exists_and_nonempty(self):
        assert CLAUDE_SKILLS.is_dir(), ".claude/skills/ is missing -- the canonical skill source is gone"
        names = [p.name for p in CLAUDE_SKILLS.iterdir() if p.is_dir()]
        assert len(names) >= 10, f"expected at least 10 skills, found {len(names)}: {names}"

    def test_claude_skills_are_git_tracked(self):
        # The whole point of the consolidation: .claude/skills/ must be trackable, not
        # gitignored. If .gitignore regresses, every SKILL.md becomes invisible to git history
        # and PR review again, silently.
        tracked = _git_tracked_files(CLAUDE_SKILLS)
        assert tracked, (
            ".claude/skills/ contains no git-tracked files -- check .gitignore has not "
            "regressed to ignoring .claude/skills/ again (see the '!.claude/skills/**' "
            "negation pattern)."
        )
        # Spot-check a specific, known skill file is actually tracked, not just "some file".
        core_skill = CLAUDE_SKILLS / "jnwb-core" / "SKILL.md"
        assert core_skill in tracked, f"{core_skill.relative_to(REPO_ROOT)} exists but is not git-tracked"

    def test_every_skill_directory_has_a_skill_md(self):
        missing = [
            p.name for p in CLAUDE_SKILLS.iterdir()
            if p.is_dir() and not (p / "SKILL.md").is_file()
        ]
        assert not missing, f"skill directories missing SKILL.md: {missing}"
