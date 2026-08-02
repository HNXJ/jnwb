r"""
Sync project skills from .agents/skills/ (git-tracked source) to .claude/skills/ (the
untracked, gitignored location Claude Code's project-skill loader actually reads).

WHY THIS EXISTS
    .agents/skills/ is checked into git; .claude/ is entirely gitignored on this repo (see
    .gitignore). Before 2026-07-31 these skills were registered via a ".claude/settings.json
    skills key pointing at .agents/skills/", which the loader does not read at all -- the
    skills were silently unloadable for weeks (artifacts/.lab/
    harness_skill_registry_repair_20260731_correction.json). The fix was a one-time manual
    copy to .claude/skills/; this script replaces that manual step so a future edit to
    .agents/skills/<name>/SKILL.md can be re-synced with one command instead of drifting.

USAGE
    python scripts/sync_claude_skills.py          # copy every .agents/skills/<name>/ dir
    python scripts/sync_claude_skills.py --check  # report drift, change nothing

Always copies .agents/skills/ -> .claude/skills/ (source of truth -> loaded copy), never the
reverse -- if you edited a skill under .claude/skills/ directly, move that edit to
.agents/skills/ first or it will be overwritten.
"""
from __future__ import annotations

import argparse
import filecmp
import os
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, ".agents", "skills")
DST = os.path.join(REPO, ".claude", "skills")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report drift, don't copy")
    args = ap.parse_args()

    names = sorted(d for d in os.listdir(SRC) if os.path.isdir(os.path.join(SRC, d)))
    changed, added, unchanged = [], [], []
    for name in names:
        src_dir, dst_dir = os.path.join(SRC, name), os.path.join(DST, name)
        if not os.path.isdir(dst_dir):
            added.append(name)
            if not args.check:
                shutil.copytree(src_dir, dst_dir)
            continue
        cmp = filecmp.dircmp(src_dir, dst_dir)
        if cmp.left_only or cmp.diff_files or cmp.right_only:
            changed.append(name)
            if not args.check:
                shutil.rmtree(dst_dir)
                shutil.copytree(src_dir, dst_dir)
        else:
            unchanged.append(name)

    # .claude/skills/ dirs with no .agents/skills/ counterpart are orphaned (e.g. the source
    # was deleted but the loaded copy wasn't) -- report, don't auto-delete.
    dst_names = set(d for d in os.listdir(DST) if os.path.isdir(os.path.join(DST, d))) \
        if os.path.isdir(DST) else set()
    orphaned = sorted(dst_names - set(names))

    verb = "would sync" if args.check else "synced"
    print(f"{verb}: {len(added)} new, {len(changed)} changed, {len(unchanged)} unchanged")
    if added:
        print("  new:", ", ".join(added))
    if changed:
        print("  changed:", ", ".join(changed))
    if orphaned:
        print("  ORPHANED in .claude/skills/ (no .agents/skills/ source -- not auto-removed):",
             ", ".join(orphaned))


if __name__ == "__main__":
    main()
