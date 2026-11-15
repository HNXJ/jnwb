"""Answer-key helper for the OCMA-8 pilot (jnwb 17-103): path pointers of CONTRIBUTING.md that do not resolve.

Usage: pilot_key.py <tree> [<contributing path>]
A path pointer is a backticked token that names a file or folder by path (it holds `/` or ends in a known
suffix). `path:line` and `path:a-b` forms are checked against the file's line count. Globs, placeholders
(`<...>`, `X.Y.Z`), URLs, option strings and tokens with spaces are skipped and counted. Prints one line per
unresolved pointer and a summary; exit 0 always (it measures, it does not gate).
"""
import re
import sys
from pathlib import Path

SUFFIX = (".py", ".md", ".toml", ".yml", ".yaml", ".json", ".sh", ".cfg", ".txt", ".csv", ".cff", ".in", ".js")
tree = Path(sys.argv[1])
doc = Path(sys.argv[2]) if len(sys.argv) > 2 else tree / ".github" / "CONTRIBUTING.md"
lines = doc.read_text(encoding="utf-8").splitlines()
checked = skipped = 0
bad = []
fence = False
for no, line in enumerate(lines, 1):
    if line.lstrip().startswith("```"):
        fence = not fence
        continue
    if fence:
        continue
    for tok in re.findall(r"`([^`\n]+)`", line):
        t = tok.strip()
        m = re.fullmatch(r"([^\s:]+?)(?::(\d+)(?:-(\d+))?)?", t)
        if not m:
            skipped += 1
            continue
        path, a, b = m.group(1), m.group(2), m.group(3)
        if not ("/" in path or path.endswith(SUFFIX)):
            continue
        if any(c in path for c in "*<>{}$=()[]\\") or path.startswith(("http", "-", "/", "~")) or "X.Y" in path:
            skipped += 1
            continue
        checked += 1
        target = tree / path.rstrip("/")
        if not target.exists():
            bad.append((no, t, "missing"))
            continue
        if a and target.is_file():
            n = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
            if int(b or a) > n:
                bad.append((no, t, f"line beyond {n}"))
for no, t, why in bad:
    print(f"UNRESOLVED {doc.name}:{no} `{t}` ({why})")
print(f"SUMMARY checked={checked} skipped={skipped} unresolved={len(bad)}")
