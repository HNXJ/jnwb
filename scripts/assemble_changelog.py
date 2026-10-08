"""Assemble the files under ``artifacts/changelog.d/`` into a release section of ``CHANGELOG.md``.

Each change writes its own file, ``artifacts/changelog.d/<name>.<category>.md``, holding one or more
top-level ``- `` bullets. Two changes made in parallel therefore touch two different files and
merge without conflict, where two edits under ``## [Unreleased]`` collide on the same lines.

At release, ``python scripts/assemble_changelog.py --version X.Y.Z --date YYYY-MM-DD`` inserts
``## [X.Y.Z] - YYYY-MM-DD`` directly below ``## [Unreleased]``, one ``### <Category>`` block per
category present in ``CATEGORIES`` order, fragments sorted by file name within a block, and then
deletes the fragments it consumed. ``--dry-run`` prints the section and changes nothing.

Every existing byte of ``CHANGELOG.md`` is kept: the new section is an insertion, never an edit.
The script refuses a version that already has a section, and refuses while ``[Unreleased]``
still carries hand-written lines, because merging those with the fragments would have to choose
an order for them.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
FRAGMENT_DIR = REPO_ROOT / "artifacts" / "changelog.d"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

#: Fragment category -> section heading, in the order the sections are written.
CATEGORIES: Dict[str, str] = {
    "breaking": "Breaking",
    "added": "Added",
    "changed": "Changed",
    "deprecated": "Deprecated",
    "removed": "Removed",
    "fixed": "Fixed",
    "security": "Security",
    "documentation": "Documentation",
}

#: Files in the fragment directory that are not fragments.
NOT_FRAGMENTS = frozenset({"README.md"})

UNRELEASED = "## [Unreleased]"
_VERSION = re.compile(r"^\d+(\.\d+)+((a|b|rc)\d+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FragmentError(ValueError):
    """A fragment, or the changelog it would be assembled into, cannot be used as it is."""


def read_fragments(directory: Path) -> List[Tuple[str, str, Path]]:
    """``(category, text, path)`` for each fragment, sorted by category order then file name.

    A file that does not parse as a fragment raises rather than being skipped: a misnamed
    fragment that is silently ignored is a change that never reaches the release notes.
    """
    if not directory.is_dir():
        return []
    found: List[Tuple[int, str, str, str, Path]] = []
    order = list(CATEGORIES)
    for path in sorted(directory.iterdir()):
        if path.name in NOT_FRAGMENTS or path.name.startswith("."):
            continue
        parts = path.name.split(".")
        if not path.is_file() or len(parts) < 3 or parts[-1] != "md" or not parts[0]:
            raise FragmentError(
                f"{path.name}: a fragment is named <name>.<category>.md, with <category> one of "
                f"{', '.join(order)}"
            )
        category = parts[-2]
        if category not in CATEGORIES:
            raise FragmentError(
                f"{path.name}: unknown category {category!r}; expected one of {', '.join(order)}"
            )
        text = path.read_bytes().decode("utf-8")
        if "\r" in text:
            raise FragmentError(f"{path.name}: use LF line endings, as CHANGELOG.md does")
        body = text.rstrip("\n").lstrip("\n")
        if not body.strip():
            raise FragmentError(f"{path.name}: the fragment is empty")
        if not body.startswith("- "):
            raise FragmentError(f"{path.name}: a fragment starts with a top-level '- ' bullet")
        if re.search(r"^#", body, flags=re.MULTILINE):
            raise FragmentError(f"{path.name}: a fragment carries no headings")
        found.append((order.index(category), path.name, category, body + "\n", path))
    found.sort(key=lambda item: (item[0], item[1]))
    return [(category, text, path) for _, _, category, text, path in found]


def render_section(version: str, date: str, fragments: Sequence[Tuple[str, str, Path]]) -> str:
    """The release section, ending with the blank line that separates it from the next one."""
    if not _VERSION.match(version):
        raise FragmentError(f"{version!r} is not a version such as 0.2.8")
    if not _DATE.match(date):
        raise FragmentError(f"{date!r} is not a date in YYYY-MM-DD form")
    if not fragments:
        raise FragmentError("there are no fragments to assemble")
    out = [f"## [{version}] - {date}\n\n"]
    current: Optional[str] = None
    for category, text, _ in fragments:
        if category != current:
            if current is not None:
                out.append("\n")
            out.append(f"### {CATEGORIES[category]}\n\n")
            current = category
        out.append(text)
    out.append("\n")
    return "".join(out)


def assemble(changelog: str, version: str, date: str,
             fragments: Sequence[Tuple[str, str, Path]]) -> str:
    """``changelog`` with the release section for ``fragments`` inserted below ``[Unreleased]``."""
    if re.search(rf"^## \[{re.escape(version)}\]", changelog, flags=re.MULTILINE):
        raise FragmentError(f"CHANGELOG.md already has a section for {version}")
    head, marker, rest = changelog.partition(UNRELEASED + "\n")
    if not marker:
        raise FragmentError(f"CHANGELOG.md has no '{UNRELEASED}' line")
    end = rest.find("\n## ")
    body, tail = (rest, "") if end == -1 else (rest[:end + 1], rest[end + 1:])
    if body.strip():
        raise FragmentError(
            f"'{UNRELEASED}' carries hand-written lines; move them into fragments first"
        )
    section = render_section(version, date, fragments)
    return head + marker + "\n" + section + tail


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True)
    parser.add_argument("--date", required=True, help="release date, YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="print the section only")
    parser.add_argument("--changelog", type=Path, default=CHANGELOG)
    parser.add_argument("--fragments", type=Path, default=FRAGMENT_DIR)
    args = parser.parse_args(argv)
    try:
        fragments = read_fragments(args.fragments)
        original = args.changelog.read_bytes().decode("utf-8")
        updated = assemble(original, args.version, args.date, fragments)
    except FragmentError as exc:
        print(f"assemble_changelog: {exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        sys.stdout.write(render_section(args.version, args.date, fragments))
        return 0
    args.changelog.write_bytes(updated.encode("utf-8"))
    if args.changelog.read_bytes().decode("utf-8") != updated:
        print("assemble_changelog: CHANGELOG.md did not read back as written", file=sys.stderr)
        return 1
    for _, _, path in fragments:
        path.unlink()
    print(f"assembled {len(fragments)} fragments into [{args.version}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
