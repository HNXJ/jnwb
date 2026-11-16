r"""Scan a tree's tracked text files for table rows whose last cell ends in an escaped pipe.

Usage: python terminal_form_scan.py <tree>

A table-like line starts, after spaces, tabs and `>`, with a pipe. Forms counted on the stripped line:
  open   ends with `\|` and the character before the backslash is not itself an escape context (`...v\|`)
  tight  ends with `\||`
  spaced ends with `\|` + spaces/tabs + `|`
Also counts table-like lines holding any `\|`. Prints every open and tight hit as path:line.
"""
import pathlib
import re
import subprocess
import sys

tree = pathlib.Path(sys.argv[1]).resolve()
names = subprocess.run(["git", "-C", str(tree), "ls-files", "-z"], check=True, capture_output=True,
                       stdin=subprocess.DEVNULL).stdout.decode("utf-8").split("\0")
BSL = chr(92)
SPACED = re.compile(re.escape(BSL) + r"\|[ \t]+\|$")
files = lines = escaped = spaced = 0
hits = []
for name in names:
    if not name or not name.lower().endswith((".md", ".txt", ".rst", ".toml", ".yml", ".yaml", ".csv")):
        continue
    path = tree / name
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    files += 1
    for number, line in enumerate(text.splitlines(), 1):
        body = line.lstrip(" \t>").strip()
        if not body.startswith("|"):
            continue
        lines += 1
        if BSL + "|" in body:
            escaped += 1
        if body.endswith(BSL + "||"):
            hits.append(("tight", name, number, body[-60:]))
        elif body.endswith(BSL + "|"):
            hits.append(("open", name, number, body[-60:]))
        elif SPACED.search(body):
            spaced += 1
print(f"SCAN tree={tree} files={files} table_like_lines={lines} with_escaped_pipe={escaped} "
      f"spaced={spaced} open={sum(h[0] == 'open' for h in hits)} tight={sum(h[0] == 'tight' for h in hits)}")
for kind, name, number, tail in hits:
    print(f"  {kind} {name}:{number} ...{tail!r}")
