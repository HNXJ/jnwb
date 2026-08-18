r"""
ARCHIVED 2026-08-14 (already self-documented HISTORICAL as of 2026-08-10 below). Moved to
scripts/archive_oneoff/ as part of the scripts/jnwb consolidation pass; kept for forensic
value, not for use -- running it is a no-op regardless (SRC no longer exists).

HISTORICAL as of 2026-08-10 -- there is no longer a two-tree sync to run.

WHAT THIS SCRIPT USED TO DO
    Synced .agents/skills/ (git-tracked source) to .claude/skills/ (previously untracked,
    gitignored). That two-tree design was the actual problem: the audit at
    artifacts/.lab/agent-harness-audit-20260810.json found the two trees had already drifted
    348 of ~450 combined lines apart on labyrinth-protocol alone, with .agents/skills/ (the
    supposed "source of truth") containing STALE content -- pre-2026-08-08 D:-drive paths that
    .claude/skills/ (the loaded, actually-edited copy) had long since moved past. Whoever was
    editing skills was editing .claude/skills/ directly, because that's what the harness loads;
    nothing was editing .agents/skills/, so "source of truth" had become a documentation fiction
    this sync script would have reinforced by overwriting the newer content with the stale copy.

WHAT CHANGED (2026-08-10)
    .claude/skills/ is now un-gitignored and tracked directly (see .gitignore). .agents/skills/
    was deleted (recoverable via git history; its content was superseded by .claude/skills/ in
    every case checked). There is exactly one skill location now. This script is kept for its
    forensic value (the drift it was meant to prevent is exactly what happened) but running it
    would do nothing useful -- SRC no longer exists.

USAGE (historical)
    python scripts/sync_claude_skills.py          # copy every .agents/skills/<name>/ dir
    python scripts/sync_claude_skills.py --check  # report drift, change nothing
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
