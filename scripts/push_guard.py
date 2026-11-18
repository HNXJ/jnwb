r"""PreToolUse hook (Bash): deny a plain `git push` from a jnwb checkout; pushes go through jnwb_push.sh.

A push that names a remote and only `_temp_` or `_temporary_` destination branches passes: it
cannot move dev or main.

A checkout is jnwb when the root holding its `.git` (a directory in a clone, a file in a linked
worktree) contains `jnwb/__init__.py` and `scripts/jnwb_push.sh`. The folder name does not count.
A command is split at `;`, `&&`, `||`, `|`, `&` and newlines, and each segment is read for:

- the executable: a shell word whose last path part is `git` or `git.exe`, after its quotes are
  removed and a backslash escape is read as the letter it escapes. `"C:/x/git.exe"`, `'/usr/bin/git'`,
  `C:\x\git.exe`, `g"i"t` and `\git` all run git. A word before it (`command`, `exec`, `env`, `xargs`)
  does not hide it.
- the directory: a `cd`, `pushd`, `(cd ...)` or `{ cd ...; }` segment sets the directory of the
  segments after it (`~` expands to the home directory); `git -C <dir>` sets it for its own push;
  `--git-dir` and `--work-tree` (either form, quoted or not) name a checkout too; so do `GIT_DIR`,
  `GIT_WORK_TREE` and `GIT_COMMON_DIR` set as a prefix, after `env`, or by `export`, in the same or an
  earlier segment. Such an assignment is read whether or not git would see it.
- nothing is exempt: a jnwb_push.sh call is not skipped, so a push inside its arguments
  (`"$(git push ...)"`) is checked like any other.

A push is read wherever it starts a word: after a quote, a backtick, `$(`, `!`, `{` or a wrapper word
(`bash -c 'git push ...'`, `` `git push ...` ``). Not read: a `cd` or `&&` inside a quoted string
(`bash -c "cd X && git push"`), since the split cuts there and the push runs in the outer directory;
and a command or path that a substitution or variable builds (`$(which git)`, `$GIT`, `eval`). The
guard reads text, not a shell. A payload that cannot be read or interpreted is denied with a message: the
guard cannot tell what it would push.

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

PATH = r"(?:\"[^\"]*\"|'[^']*'|\S+)"
QUOTE = r"[\"']?"
GLOBAL = rf"(?:{QUOTE}--namespace{QUOTE}(?:=|\s+){PATH}|{QUOTE}-C{QUOTE}\s+{PATH}|{QUOTE}-c{QUOTE}\s+{PATH}|{QUOTE}--super-prefix{QUOTE}\s+{PATH}|{QUOTE}--config-env{QUOTE}\s+{PATH}|{QUOTE}--git-dir{QUOTE}(?:=|\s+){PATH}|{QUOTE}--work-tree{QUOTE}(?:=|\s+){PATH}|{QUOTE}--?[A-Za-z][\w-]*{QUOTE}(?:={PATH})?)"
# A word ends at a character that opens a command or a quote: whitespace, quotes, operators, grouping,
# backtick, `!` and braces. The plain-character class excludes the backslash, so only the escape branch
# consumes one and the matcher never splits it two ways.
WORD_EDGE = r"\s\"';&|<>()`!{}"
WORD = rf"(?:\"[^\"\n]*\"|'[^'\n]*'|\\.?|[^{WORD_EDGE}\\])+"
# A push is read at every position where a word can start after one of those characters, so a push nested
# in a quote, a backtick or a wrapper word (`bash -c 'git push ...'`) is found. The zero-width lookahead
# lets matches overlap, which a consuming pattern would not.
WORD_START = rf"(?<![^{WORD_EDGE}])"
PUSH = re.compile(rf"{WORD_START}(?=(?P<exe>{WORD})\s+(?P<glob>(?:{GLOBAL}\s+)*)push\b(?P<args>[^;&|<>\n]*))",
                  re.IGNORECASE)
GLOBAL_OPT = re.compile(rf"{QUOTE}(-C|--git-dir|--work-tree){QUOTE}(?:=|\s+)({PATH})|{QUOTE}-c{QUOTE}\s+{PATH}")
GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")
GIT_ENV_NAMES = "|".join(GIT_ENV)
ENV_ASSIGN = re.compile(rf"(?<![\w.-])({GIT_ENV_NAMES})=({PATH})")
TEMP = re.compile(r"_temp(?:orary)?_")
ALL_REFS = {"--all", "--mirror", "--tags"}
SEGMENT_SEP = re.compile(r"&&|\|\||[;&|\n]")
CD = re.compile(r"\s*[({]*\s*(?:cd|pushd)\s+(\"[^\"]*\"|'[^']*'|[^\s;&|()]+)\s*[)}]*\s*$")
JNWB_MARKERS = ("jnwb/__init__.py", "scripts/jnwb_push.sh")
DENY = ("plain `git push` in jnwb skips the suite stamp and CI checks; run "
        "`bash <repo>/scripts/jnwb_push.sh <repo> dev </dev/null`.")
UNREADABLE = "push_guard could not read the hook payload ({}); a command it cannot check is denied."


def temp_only(args):
    """True when ``args`` (the words after ``push``) name a remote and only temporary branches."""
    words = args.split()
    if ALL_REFS & set(words):
        return False
    refspecs = [w for w in words if not w.startswith("-")][1:]
    dests = [r.lstrip("+").split(":")[-1].removeprefix("refs/heads/") for r in refspecs]
    return bool(dests) and all(TEMP.match(d) for d in dests)


MSYS_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")


def dequote(word):
    """The word with each matched pair of quotes removed; an unpaired quote stays."""
    return re.sub(r"\"([^\"]*)\"|'([^']*)'",
                  lambda m: m.group(1) if m.group(1) is not None else m.group(2), word)


def is_git_exe(word):
    """True when a shell word runs git: its last path part is git or git.exe, quoted or not. The
    backslash is read both as a path separator and as an escape, so `g\\it` also runs git."""
    flat = dequote(word)
    names = (re.split(r"[\\/]", flat)[-1], re.split(r"[\\/]", flat.replace("\\", ""))[-1])
    return any(name.lower().removesuffix(".exe") == "git" for name in names)


def unquote(word):
    """The path a shell word names: quotes removed and `~` expanded; on Windows a Git Bash `/c/...`
    becomes `C:/...`."""
    word = dequote(word)
    if word == "~" or word.startswith(("~/", "~\\")):
        word = os.path.expanduser(word)
    word = word.replace("\\", "/")
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


def push_dirs(base, global_text, env):
    """The directories a push names. Each `-C` steps the working directory in turn; `--git-dir`,
    `--work-tree` and the GIT_ names in `env` are resolved against the directory the `-C` steps end in,
    as git does. The directory the push runs in is always one of them."""
    steps = [(m.group(1), m.group(2)) for m in GLOBAL_OPT.finditer(global_text) if m.group(1)]
    where = base
    for flag, path in steps:
        if flag == "-C":
            where = under(where, unquote(path))
    named = [under(where, unquote(path)) for flag, path in steps if flag != "-C"]
    named += [under(where, unquote(env[name])) for name in GIT_ENV if name in env]
    return [where, *named]


def verdict(payload):
    """Return the deny reason for a plain `git push` in a jnwb checkout, else None."""
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    base = payload.get("cwd") or ""
    env = {}
    for seg in SEGMENT_SEP.split(cmd):
        env.update(ENV_ASSIGN.findall(seg))
        cd = CD.match(seg)
        if cd:
            base = under(base, unquote(cd.group(1)))
            continue
        for m in PUSH.finditer(seg):
            if not is_git_exe(m.group("exe")) or temp_only(m.group("args")):
                continue
            if any(is_jnwb(where) for where in push_dirs(base, m.group("glob"), env)):
                return DENY
    return None


def decide(raw):
    """Deny reason for the raw payload text (None when the push is allowed). Unreadable stdin is
    denied with a message. A payload that does not interpret as a Bash call is denied when its text
    names a git push, so such a push never passes unchecked, and any other command is let through."""
    if raw is None:
        return UNREADABLE.format("stdin unreadable")
    try:
        return verdict(json.loads(raw))
    except Exception as exc:
        if re.search(r"\bgit\b[\s\S]*\bpush\b", raw):
            return UNREADABLE.format(type(exc).__name__)
        return None


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except Exception:  # missing or closed stdin
        raw = None
    reason = decide(raw)
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
