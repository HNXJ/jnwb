"""PreToolUse hook (Bash): deny a plain `git push` from a jnwb checkout; pushes go through jnwb_push.sh.

A push that names a remote and only `_temp_` or `_temporary_` destination branches passes: it
cannot move dev or main.

A checkout is jnwb when the root holding its `.git` (a directory in a clone, a file in a linked
worktree) contains `jnwb/__init__.py` and `scripts/jnwb_push.sh`. The folder name does not count.
A command is split at `;`, `&&`, `||`, `|`, `&` and newlines. A `cd <dir>` segment sets the directory
of the segments after it, `git -C <dir>` sets it for its own push, and a segment that starts with a
jnwb_push.sh call is the wrapper and passes. An unreadable payload is denied only when its text names
a git push.

Wire it in `.claude/settings.json` under hooks.PreToolUse with matcher "Bash":
    python <repo>/scripts/push_guard.py
Moved here from jarness's global git_guard on 2026-10-28. Reads the hook payload on stdin.
Exit 0 with a deny decision on stdout for a plain push; exit 0 and no output otherwise.
"""
import json
import os
import re
import sys
from pathlib import Path

PUSH = re.compile(r"\bgit\s+(?:-C\s+(\"[^\"]*\"|'[^']*'|\S+)\s+)?(?:-c\s+\S+\s+)*push\b([^;&|<>\n]*)")
TEMP = re.compile(r"_temp(?:orary)?_")
ALL_REFS = {"--all", "--mirror", "--tags"}
SEGMENT_SEP = re.compile(r"&&|\|\||[;&|\n]")
CD = re.compile(r"\s*cd\s+(\"[^\"]*\"|'[^']*'|[^\s;&|]+)\s*$")
WRAPPER = re.compile(r"\s*(?:(?:bash|sh)\s+)?\S*jnwb_push\.sh\b")
JNWB_MARKERS = ("jnwb/__init__.py", "scripts/jnwb_push.sh")
DENY = ("plain `git push` in jnwb skips the suite stamp and CI checks; run "
        "`bash <repo>/scripts/jnwb_push.sh <repo> dev </dev/null`.")


def temp_only(args):
    """True when ``args`` (the words after ``push``) name a remote and only temporary branches."""
    words = args.split()
    if ALL_REFS & set(words):
        return False
    refspecs = [w for w in words if not w.startswith("-")][1:]
    dests = [r.lstrip("+").split(":")[-1].removeprefix("refs/heads/") for r in refspecs]
    return bool(dests) and all(TEMP.match(d) for d in dests)


MSYS_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")


def unquote(word):
    """The path a shell word names; on Windows a Git Bash `/c/...` becomes `C:/...`."""
    word = word.strip("\"'").replace("\\", "/")
    return MSYS_DRIVE.sub(lambda m: m.group(1).upper() + ":", word) if os.name == "nt" else word


def under(base, where):
    """``where`` resolved against ``base`` when it is relative; ``base`` when ``where`` is empty."""
    if not where:
        return base
    return where if os.path.isabs(where) else os.path.join(base, where)


def is_jnwb(path):
    """True when the nearest checkout at or above ``path`` carries the jnwb content markers."""
    here = Path(os.path.abspath(path))
    root = next((d for d in (here, *here.parents) if (d / ".git").exists()), None)
    return root is not None and all((root / m).is_file() for m in JNWB_MARKERS)


def verdict(payload):
    """Return the deny reason for a plain `git push` in a jnwb checkout, else None."""
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    base = payload.get("cwd") or ""
    for seg in SEGMENT_SEP.split(cmd):
        cd = CD.match(seg)
        if cd:
            base = under(base, unquote(cd.group(1)))
            continue
        if WRAPPER.match(seg):
            continue
        for m in PUSH.finditer(seg):
            where = under(base, unquote(m.group(1) or ""))
            if is_jnwb(where) and not temp_only(m.group(2)):
                return DENY
    return None


def decide(raw):
    """Deny reason for the raw payload text, else None. A payload that does not parse is denied
    only when its text names a git push, so the guard never lets such a push through unchecked."""
    try:
        return verdict(json.loads(raw))
    except Exception as exc:
        if re.search(r"\bgit\b[\s\S]*\bpush\b", raw):
            return f"push_guard could not read this command ({type(exc).__name__}); a push it cannot check is denied."
        return None


def main():
    reason = decide(sys.stdin.buffer.read().decode("utf-8", "replace"))
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
