"""PreToolUse hook (Bash): deny a plain `git push` from a jnwb checkout; pushes go through jnwb_push.sh.

A push that names a remote and only `_temp_` or `_temporary_` destination branches passes: it
cannot move dev or main.

Wire it in `.claude/settings.json` under hooks.PreToolUse with matcher "Bash":
    python <repo>/scripts/push_guard.py
Moved here from jarness's global git_guard on 2026-10-28. Reads the hook payload on stdin.
Exit 0 with a deny decision on stdout for a plain push; exit 0 and no output otherwise.
"""
import json
import re
import sys

PUSH = re.compile(r"\bgit\s+(?:-C\s+(\"[^\"]*\"|'[^']*'|\S+)\s+)?(?:-c\s+\S+\s+)*push\b([^;&|<>\n]*)")
TEMP = re.compile(r"_temp(?:orary)?_")
ALL_REFS = {"--all", "--mirror", "--tags"}


def temp_only(args):
    """True when ``args`` (the words after ``push``) name a remote and only temporary branches."""
    words = args.split()
    if ALL_REFS & set(words):
        return False
    refspecs = [w for w in words if not w.startswith("-")][1:]
    dests = [r.lstrip("+").split(":")[-1].removeprefix("refs/heads/") for r in refspecs]
    return bool(dests) and all(TEMP.match(d) for d in dests)


def verdict(payload):
    """Return the deny reason for a plain `git push` run in or at a jnwb checkout, else None."""
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if "jnwb_push.sh" in cmd:
        return None
    for m in PUSH.finditer(cmd):
        where = (m.group(1) or payload.get("cwd") or "").strip("\"'").replace("\\", "/")
        if re.search(r"(?:^|/)jnwb(?:/|$)", where) and not temp_only(m.group(2)):
            return ("plain `git push` in jnwb skips the suite stamp and CI checks; run "
                    "`bash <repo>/scripts/jnwb_push.sh <repo> dev </dev/null`.")
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    reason = verdict(payload)
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
