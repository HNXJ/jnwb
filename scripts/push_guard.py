r"""PreToolUse hook (Bash): deny a plain `git push` from a jnwb checkout; pushes go through jnwb_push.sh.

A push that names a remote and only `_temp_` or `_temporary_` destination branches passes: it
cannot move dev or main.

A checkout is jnwb when the root holding its `.git` (a directory in a clone, a file in a linked
worktree) contains `jnwb/__init__.py` and `scripts/jnwb_push.sh`. The folder name does not count.
A command is split at `;`, `&&`, `||`, `|`, `&` and newlines, and each segment is read for:

- the executable: a shell word whose last path part is `git` or `git.exe`, after its quotes are
  removed and a backslash escape is read as the letter it escapes. `"C:/x/git.exe"`, `'/usr/bin/git'`,
  `C:\x\git.exe`, `g"i"t` and `\git` all run git. A word before it (`command`, `exec`, `env`, `xargs`)
  does not hide it. The unquoted run after a closing quote is a word too (`"a"git`).
- the global options and `push`: git's `-C`, `-c`, `--git-dir`, `--work-tree`, `--namespace` and the
  other global options, quoted or not, then the word `push`.
- the directory: a `cd`, `pushd`, `(cd ...)` or `{ cd ...; }` segment sets the directory of the
  segments after it (`~` expands to the home directory); `git -C <dir>` sets it for its own push;
  `--git-dir` and `--work-tree` (either form, quoted or not) name a checkout too; so do `GIT_DIR`,
  `GIT_WORK_TREE` and `GIT_COMMON_DIR` set as a prefix, after `env`, or by `export`, in the same or an
  earlier segment. Such an assignment is read whether or not git would see it.
- nothing is exempt: a jnwb_push.sh call is not skipped, so a push inside its arguments
  (`"$(git push ...)"`) is checked like any other.

A push is read wherever its executable starts a word: after a quote, a backtick, `$(`, `!`, `{` or a
wrapper word (`bash -c 'git push ...'`, `` `git push ...` ``). The scan is linear in the command length:
each word is read once, each quoted run's content once per nesting level (at most two), and the global
options of each executable are walked once. Not read: a `cd` or `&&` inside a quoted string
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

GIT_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR")
GIT_ENV_NAMES = "|".join(GIT_ENV)
PATH = r"(?:\"[^\"]*\"|'[^']*'|\S+)"
ENV_ASSIGN = re.compile(rf"(?<![\w.-])({GIT_ENV_NAMES})=({PATH})")
ARGS = re.compile(r"[^;&|<>\n]*")
TEMP = re.compile(r"_temp(?:orary)?_")
ALL_REFS = {"--all", "--mirror", "--tags"}
SEGMENT_SEP = re.compile(r"&&|\|\||[;&|\n]")
# Possessive quantifiers: a cd line is read once, with no backtracking over its spaces.
CD = re.compile(r"[\s({]*+(?:cd|pushd)\s++(\"[^\"]*\"|'[^']*'|[^\s;&|()]++)[\s)}]*+$")
QUOTES = "\"'"
OPERATORS = ";&|<>()`!{}"
# Global options that take their value as the next word, or as `=value` in the same word.
SEPARATE_ARG = {"-c", "--super-prefix", "--config-env"}  # lower case; -C reads as -c
EQUALS_OR_SEPARATE = {"--namespace", "--git-dir", "--work-tree"}
STEP_FLAGS = ("-C", "--git-dir", "--work-tree")
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


def _piece_end(s, j):
    """End of the shell word that starts at j: closed quoted runs, backslash escapes and plain characters.
    The word stops at whitespace, an operator, or a quote that never closes."""
    n = len(s)
    while j < n:
        c = s[j]
        if c in QUOTES:
            close = s.find(c, j + 1)
            if close < 0:
                break
            j = close + 1
        elif c == "\\":
            j += 2 if j + 1 < n else 1
        elif c.isspace() or c in OPERATORS:
            break
        else:
            j += 1
    return j


def _run_end(s, j):
    """End of the unquoted characters from j: no quote, whitespace or operator; escapes are kept."""
    n = len(s)
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2 if j + 1 < n else 1
        elif c in QUOTES or c.isspace() or c in OPERATORS:
            break
        else:
            j += 1
    return j


def _candidates(s):
    """Yield (s, start, end, memo) for each shell word of s that could be a command's executable: each
    whole word, and the unquoted run after each closing quote. The content of each closed quoted run is
    a command of its own (`bash -c 'git push'`) and is scanned the same way. Words and runs are disjoint
    within one string, and quoted runs nest at most two deep (a quote cannot sit inside a run of its own
    kind), so the scan is linear. ``memo`` is shared by the candidates of one string (see _push_end)."""
    memo = {}
    n = len(s)
    i = 0
    while i < n:
        c = s[i]
        if c in QUOTES and s.find(c, i + 1) < 0:
            i += 1  # an unclosed quote starts no word; the text after it does
            continue
        if c.isspace() or c in OPERATORS:
            i += 1
            continue
        end = _piece_end(s, i)
        yield s, i, end, memo
        j = i
        while j < end:
            c = s[j]
            if c in QUOTES:
                close = s.find(c, j + 1)
                yield from _candidates(s[j + 1:close])
                after = close + 1
                run = _run_end(s, after)
                if run > after:
                    yield s, after, run, memo
                j = after
            elif c == "\\":
                j += 2 if j + 1 < end else 1
            else:
                j += 1
        i = end


def _token(s, j):
    """(start, end) of the shell word at or after j, skipping spaces; None when an operator, the end of
    the string or a quote that never closes comes first."""
    n = len(s)
    while j < n and s[j].isspace():
        j += 1
    if j >= n or s[j] in OPERATORS:
        return None
    end = _piece_end(s, j)
    return (j, end) if end > j else None


def _is_push(word):
    """True for the word `push`, or a word that starts with it and is not a longer word (`push-x`)."""
    return word[:4].lower() == "push" and not (len(word) > 4 and (word[4].isalnum() or word[4] == "_"))


def _option(word):
    """How a word reads among git's global options: ("value", name) when the next word is its value,
    ("flag", (name, value)) for a whole option (value None when it has none), or None when the word is
    not a global option. Names are read as git reads them, any case; quotes around a name are removed."""
    d = dequote(word)
    name, eq, value = d.partition("=")
    low = name.lower()
    if low in SEPARATE_ARG and not eq:
        return ("value", name)
    if low in EQUALS_OR_SEPARATE:
        return ("flag", (name, value)) if eq else ("value", name)
    if re.fullmatch(r"--?[A-Za-z][\w-]*", name):
        return ("flag", (name, value if eq else None))
    return None


def _push_end(s, j, memo):
    """Index just after the `push` word that ends the git global options starting at j, or None. The
    result depends only on the word where the walk stands, so it is memoized per word start: options
    shared by several candidates are walked once."""
    path = []
    found = None
    while True:
        tok = _token(s, j)
        if tok is None:
            break
        a, b = tok
        if a in memo:
            found = memo[a]
            break
        path.append(a)
        word = s[a:b]
        if _is_push(word):
            found = a + 4
            break
        kind = _option(word)
        if kind is None:
            break
        if kind[0] == "value":
            nxt = _token(s, b)
            if nxt is None:
                break
            j = nxt[1]
        else:
            j = b
    for a in path:
        memo[a] = found
    return found


def _steps(s, j):
    """The (flag, value) of each -C, --git-dir and --work-tree among the global options from j to `push`."""
    steps = []
    while True:
        tok = _token(s, j)
        if tok is None:
            break
        a, b = tok
        word = s[a:b]
        if _is_push(word):
            break
        kind = _option(word)
        if kind is None:
            break
        if kind[0] == "value":
            nxt = _token(s, b)
            if nxt is None:
                break
            if kind[1] in STEP_FLAGS:
                steps.append((kind[1], s[nxt[0]:nxt[1]]))
            j = nxt[1]
        else:
            name, value = kind[1]
            if name in STEP_FLAGS and value is not None:
                steps.append((name, value))
            j = b
    return steps


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


def push_dirs(base, steps, env):
    """The directories a push names. Each `-C` steps the working directory in turn; `--git-dir`,
    `--work-tree` and the GIT_ names in `env` are resolved against the directory the `-C` steps end in,
    as git does. The directory the push runs in is always one of them."""
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
        for s, a, b, memo in _candidates(seg):
            if b >= len(s) or not s[b].isspace() or not is_git_exe(s[a:b]):
                continue
            end = _push_end(s, b, memo)
            if end is None or temp_only(ARGS.match(s, end).group()):
                continue
            if any(is_jnwb(where) for where in push_dirs(base, _steps(s, b), env)):
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
        first_git = re.search(r"\bgit\b", raw)
        if first_git and re.search(r"\bpush\b", raw[first_git.start():]):
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
