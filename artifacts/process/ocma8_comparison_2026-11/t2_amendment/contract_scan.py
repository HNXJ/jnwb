"""Tracked markdown table lines at the T2 baseline that hold characters the rubric rulings turn on.

Usage: python contract_scan.py <baseline tree>
Counts, over `git ls-files` (text files), the table-like lines (stripped of a blockquote lead, starting with
`|`) that hold: whitespace other than space and tab that `str.strip()` removes (U+00A0, U+2003, U+000B,
U+000C and the rest of `str.isspace`), a backslash not followed by a pipe, more than two escaped pipes, a run
of two or more spaces inside a cell. Prints one line per class with line and file counts and up to three
examples. A known positive is checked first on a built line.
"""
import re
import subprocess
import sys

ODD_WS = re.compile(r"[^\S \t\r\n]")
LONE_BSL = re.compile(r"\\(?!\|)")
ESC = re.compile(r"\\\|")
INNER_RUN = re.compile(r"\S {2,}\S")
CLASSES = {
    "odd whitespace (not space or tab)": lambda s: bool(ODD_WS.search(s)),
    "backslash not before a pipe": lambda s: bool(LONE_BSL.search(s)),
    "more than two escaped pipes": lambda s: len(ESC.findall(s)) > 2,
    "run of spaces inside a cell": lambda s: any(INNER_RUN.search(c.strip(" ")) for c in s.split("|")),
}


def table_line(line):
    body = line.lstrip()
    while body.startswith(">"):
        body = body[1:].lstrip()
    return body if body.startswith("|") else None


def main(argv):
    positive = "| a\u00a0| C:\\dir | x\\|y\\|z\\|w | two  spaces |"
    assert all(test(positive) for test in CLASSES.values()), "known positive not detected"
    assert not any(test("| a | b |") for test in CLASSES.values()), "known negative detected"
    tree = argv[0]
    names = subprocess.run(["git", "-C", tree, "ls-files", "-z"], capture_output=True, stdin=subprocess.DEVNULL,
                           check=True).stdout.decode("utf-8").split("\0")
    hits = {name: [] for name in CLASSES}
    n_lines = n_files = 0
    for name in filter(None, names):
        try:
            with open(f"{tree}/{name}", encoding="utf-8", newline="") as handle:
                lines = handle.read().split("\n")
        except (UnicodeDecodeError, OSError):
            continue
        rows = [(i + 1, t) for i, t in ((i, table_line(line.rstrip("\r"))) for i, line in enumerate(lines)) if t]
        n_lines += len(rows)
        n_files += bool(rows)
        for number, text in rows:
            for label, test in CLASSES.items():
                if test(text):
                    hits[label].append((name, number, text))
    print(f"table-like lines={n_lines} files={n_files}")
    for label, found in hits.items():
        files = sorted({name for name, _, _ in found})
        md_scripts = sum(name.endswith(".md") for name in files)
        print(f"{label}: lines={len(found)} files={len(files)} (.md files={md_scripts})")
        for name, number, text in found[:3]:
            print(f"   {name}:{number}: {text[:110]!a}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
