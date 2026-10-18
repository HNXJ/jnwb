"""List the obligations a rewrite of a rule file drops or loosens, for an old-against-new reading.

A rewrite that keeps a rule's wording but drops its timing ("before its first write" becoming
"confirm the tree") reads as kept in a mapping table. This script reads each rule file at a base
commit and in the working tree, splits both into clauses, and reports every old clause that
carries an obligation word and has no exact counterpart in the new text:

* ``dropped``: no new clause shares half its words;
* ``timing lost``: the closest new clause lacks a timing word the old one had;
* ``reworded``: the closest new clause keeps the timing words; listed for the reader.

A clause moved to another listed file counts as kept. The reader decides each listed clause; the
exit code is 1 while any clause is dropped or has lost its timing.

Usage::

    python scripts/obligation_diff.py --base <commit>
    python scripts/obligation_diff.py --base <commit> AGENTS.md .github/CONTRIBUTING.md
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = ("AGENTS.md", ".github/CONTRIBUTING.md", "artifacts/rulings/standing.md")

OBLIGATION = re.compile(
    r"\b(never|must|only|always|before|after|until|first|once|stops?|refuses?|requires?|"
    r"required|needs?)\b")
TIMING = {"before", "after", "until", "first", "once", "then", "while", "when"}
SPLIT = re.compile(r"(?<=[.;:!?])\s+|\s*\|\s*|\n+")
WORD = re.compile(r"[a-z0-9_]+")


def clauses(text: str) -> list[str]:
    """Normalized clauses: lowercase, markdown emphasis and code marks removed, spaces collapsed."""
    text = re.sub(r"[*`]+", "", text.lower())
    out = []
    for part in SPLIT.split(text):
        part = re.sub(r"^[-#>\s\d.)]+", "", " ".join(part.split())).rstrip(".;:")
        if len(WORD.findall(part)) >= 3:
            out.append(part)
    return out


def _words(clause: str) -> set[str]:
    return set(WORD.findall(clause))


def compare(old: str, new: str) -> list[tuple[str, str, str]]:
    """(kind, old clause, closest new clause) for each old obligation with no exact counterpart."""
    new_clauses = clauses(new)
    exact = set(new_clauses)
    new_words = [(_words(c), c) for c in new_clauses]
    report = []
    for clause in clauses(old):
        if clause in exact or not OBLIGATION.search(clause):
            continue
        words = _words(clause)
        score, best = max(((len(words & w) / len(words | w), c) for w, c in new_words),
                          default=(0.0, ""))
        if score < 0.5:
            report.append(("dropped", clause, best))
        elif (words & TIMING) - _words(best):
            report.append(("timing lost", clause, best))
        else:
            report.append(("reworded", clause, best))
    return report


def _at(base: str, path: str) -> str:
    done = subprocess.run(["git", "-C", str(ROOT), "show", f"{base}:{path}"],
                          capture_output=True, text=True, encoding="utf-8")
    return done.stdout if done.returncode == 0 else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="commit the rewrite started from")
    parser.add_argument("files", nargs="*", default=list(DEFAULT_FILES))
    args = parser.parse_args(argv)
    old = "\n".join(_at(args.base, f) for f in args.files)
    new = "\n".join((ROOT / f).read_text(encoding="utf-8") for f in args.files
                    if (ROOT / f).exists())
    if not clauses(old):
        print(f"no clauses read at {args.base} in {args.files}")
        return 1
    report = compare(old, new)
    for kind, before, after in report:
        print(f"{kind}: {before}\n    closest: {after or '(none)'}")
    blocking = sum(kind != "reworded" for kind, _, _ in report)
    print(f"{len(clauses(old))} old clauses read; {len(report)} listed, {blocking} dropped or "
          f"lost timing")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
