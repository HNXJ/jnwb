"""Edit a Markdown stack file one bullet at a time, preserving its line endings.

A bullet is a line starting with ``- `` together with the lines after it that start with two
spaces (its continuation lines). A bullet is addressed by an exact prefix of its first line and
must be the only bullet that prefix matches, optionally within one heading's section.

Every operation runs on an in-memory copy and is checked before anything is written; a refusal
leaves the file byte-for-byte unchanged. New text is read from a UTF-8 file, never from a shell
argument, so the shell cannot rewrite it.

Usage::

    python scripts/stack_edit.py --file F [--section H] [--dry-run] delete PREFIX [PREFIX ...]
    python scripts/stack_edit.py --file F [--section H] [--dry-run] replace PREFIX --with-file P
    python scripts/stack_edit.py --file F [--section H] [--dry-run] insert-after PREFIX --from-file P
    python scripts/stack_edit.py --file F [--section H] [--dry-run] sub PREFIX --old S --new S

Exit status is 0 on success and 2 on a refusal, with the reason on stderr.
"""

from __future__ import annotations

import argparse
import difflib
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


class StackEditError(Exception):
    """Raised when an edit would be ambiguous, malformed or unverifiable. Nothing is written."""


@dataclass
class Doc:
    """A stack file held as lines, with the newline convention it was read with."""

    lines: list
    newline: str
    path: Optional[pathlib.Path] = None
    original: bytes = field(default=b"", repr=False)

    def encode(self) -> bytes:
        out = self.newline.join(self.lines).encode("utf-8")
        check_newlines(out, self.newline)
        return out


def detect_newline(raw: bytes) -> str:
    """Return ``"\\r\\n"`` or ``"\\n"``; refuse mixed or bare-CR line endings."""
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n")
    cr = raw.count(b"\r")
    if cr != crlf:
        raise StackEditError(f"bare CR found ({cr - crlf} CR not followed by LF)")
    if crlf and crlf != lf:
        raise StackEditError(f"mixed line endings: {crlf} CRLF and {lf - crlf} bare LF")
    return "\r\n" if crlf else "\n"


def check_newlines(raw: bytes, newline: str) -> None:
    if detect_newline(raw) != newline and raw.count(b"\n"):
        raise StackEditError(f"line-ending convention changed from {newline!r}")


def parse(raw: bytes, path: Optional[pathlib.Path] = None) -> Doc:
    newline = detect_newline(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StackEditError(f"not UTF-8: {exc}") from exc
    return Doc(text.split(newline), newline, path, raw)


def load(path) -> Doc:
    path = pathlib.Path(path)
    return parse(path.read_bytes(), path)


def _is_bullet(line: str) -> bool:
    return line.startswith("- ")


def _is_continuation(line: str) -> bool:
    return line.startswith("  ")


def _fenced(lines: Sequence[str]) -> list:
    """Per line, whether it sits inside a fenced code block (fence lines included)."""
    inside, out = False, []
    for line in lines:
        if line.lstrip().startswith("```"):
            out.append(True)
            inside = not inside
        else:
            out.append(inside)
    return out


def _norm_heading(text: str) -> str:
    return text.strip().lstrip("#").strip()


def section_range(lines: Sequence[str], heading: Optional[str]) -> tuple:
    """Line range ``[start, stop)`` under ``heading``, up to the next heading of its level or higher."""
    if heading is None:
        return 0, len(lines)
    want = _norm_heading(heading)
    fenced = _fenced(lines)
    heads = []
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m and not fenced[i]:
            heads.append((i, len(m.group(1)), m.group(2)))
    hits = [(i, lvl) for i, lvl, text in heads if text == want]
    if len(hits) != 1:
        raise StackEditError(f"section {heading!r} matches {len(hits)} headings, need exactly 1")
    start, level = hits[0]
    stop = len(lines)
    for i, lvl, _ in heads:
        if i > start and lvl <= level:
            stop = i
            break
    return start + 1, stop


def unit_end(lines: Sequence[str], i: int) -> int:
    """Index one past the last continuation line of the bullet starting at ``i``."""
    j = i + 1
    while j < len(lines) and _is_continuation(lines[j]):
        j += 1
    return j


def find(lines: Sequence[str], prefix: str, section: Optional[str] = None) -> tuple:
    """Return ``(start, stop)`` of the one bullet whose first line starts with ``prefix``."""
    if not prefix:
        raise StackEditError("empty prefix")
    lo, hi = section_range(lines, section)
    fenced = _fenced(lines)
    bullets, others = [], []
    for i in range(lo, hi):
        if fenced[i] or not lines[i].startswith(prefix):
            continue
        (bullets if _is_bullet(lines[i]) else others).append(i)
    where = f" in section {section!r}" if section is not None else ""
    if others:
        kind = "a continuation line" if _is_continuation(lines[others[0]]) else "a non-bullet line"
        raise StackEditError(
            f"prefix {prefix!r} matches {kind}{where} (line {others[0] + 1}); "
            "address the bullet by its first line"
        )
    if len(bullets) != 1:
        lines_1 = [i + 1 for i in bullets]
        raise StackEditError(
            f"prefix {prefix!r} matches {len(bullets)} bullets{where} at lines {lines_1}, need exactly 1"
        )
    i = bullets[0]
    return i, unit_end(lines, i)


def read_bullets(path) -> list:
    """Read replacement text: UTF-8, one or more bullets, each with optional continuation lines."""
    raw = pathlib.Path(path).read_bytes()
    detect_newline(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StackEditError(f"{path}: not UTF-8: {exc}") from exc
    new = text.replace("\r\n", "\n").split("\n")
    while new and new[-1] == "":
        new.pop()
    if not new:
        raise StackEditError(f"{path}: no text")
    if not _is_bullet(new[0]):
        raise StackEditError(f"{path}: first line must start with '- ': {new[0]!r}")
    for n, line in enumerate(new[1:], start=2):
        if not (_is_bullet(line) or _is_continuation(line)):
            raise StackEditError(
                f"{path}: line {n} is neither a bullet nor a two-space continuation: {line!r}"
            )
    return new


def _splice(doc: Doc, start: int, stop: int, new: list) -> None:
    before = list(doc.lines)
    doc.lines[start:stop] = new
    expected = before[:start] + new + before[stop:]
    if doc.lines != expected:
        raise StackEditError("postcondition failed: lines outside the edit changed")


def delete(doc: Doc, prefix: str, section: Optional[str] = None) -> None:
    start, stop = find(doc.lines, prefix, section)
    _splice(doc, start, stop, [])
    try:
        find(doc.lines, prefix, section)
    except StackEditError:
        return
    raise StackEditError(f"postcondition failed: {prefix!r} still matches after delete")


def replace(doc: Doc, prefix: str, new: list, section: Optional[str] = None) -> None:
    start, stop = find(doc.lines, prefix, section)
    _splice(doc, start, stop, list(new))
    if doc.lines[start:start + len(new)] != list(new):
        raise StackEditError("postcondition failed: replacement not in place")


def insert_after(doc: Doc, prefix: str, new: list, section: Optional[str] = None) -> None:
    start, stop = find(doc.lines, prefix, section)
    anchor = doc.lines[start:stop]
    _splice(doc, stop, stop, list(new))
    if doc.lines[start:stop] != anchor or doc.lines[stop:stop + len(new)] != list(new):
        raise StackEditError("postcondition failed: insertion not directly after the anchor bullet")


def sub(doc: Doc, prefix: str, old: str, new: str, section: Optional[str] = None) -> None:
    if not old:
        raise StackEditError("empty --old")
    for s in (old, new):
        if "\n" in s or "\r" in s:
            raise StackEditError("--old and --new must not contain line breaks")
    start, stop = find(doc.lines, prefix, section)
    unit = doc.lines[start:stop]
    count = sum(line.count(old) for line in unit)
    if count != 1:
        raise StackEditError(f"{old!r} occurs {count} times in the bullet, need exactly 1")
    edited = [line.replace(old, new) for line in unit]
    _splice(doc, start, stop, edited)
    after = sum(line.count(old) for line in doc.lines[start:stop])
    if after != new.count(old):
        raise StackEditError("postcondition failed: substitution count")


def diff(doc: Doc) -> str:
    before = parse(doc.original).lines if doc.original else []
    name = str(doc.path) if doc.path else "stack"
    return "\n".join(
        difflib.unified_diff(before, doc.lines, f"a/{name}", f"b/{name}", lineterm="")
    )


def edit(path, ops: Sequence[Callable[[Doc], None]], dry_run: bool = False) -> Doc:
    """Apply ``ops`` in order to ``path``; write once, only if every op and check passes."""
    doc = load(path)
    for op in ops:
        op(doc)
    out = doc.encode()
    if dry_run:
        return doc
    path = pathlib.Path(path)
    if path.read_bytes() != doc.original:
        raise StackEditError(f"{path} changed on disk during the edit")
    path.write_bytes(out)
    written = path.read_bytes()
    if written != out:
        raise StackEditError(f"{path}: bytes on disk differ from the bytes written")
    check_newlines(written, doc.newline)
    return doc


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--file", required=True, help="stack file to edit")
    p.add_argument("--section", help="restrict matching to the lines under this heading")
    p.add_argument("--dry-run", action="store_true", help="print a unified diff, write nothing")
    cmds = p.add_subparsers(dest="cmd", required=True)
    d = cmds.add_parser("delete", help="delete bullets with their continuation lines")
    d.add_argument("prefixes", nargs="+")
    r = cmds.add_parser("replace", help="replace a bullet with the bullets in a file")
    r.add_argument("prefix")
    r.add_argument("--with-file", required=True)
    i = cmds.add_parser("insert-after", help="insert bullets after a bullet and its continuation")
    i.add_argument("prefix")
    i.add_argument("--from-file", required=True)
    s = cmds.add_parser("sub", help="replace one substring inside a bullet")
    s.add_argument("prefix")
    s.add_argument("--old", required=True)
    s.add_argument("--new", required=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    sec = args.section
    try:
        if args.cmd == "delete":
            ops = [lambda d, p=p: delete(d, p, sec) for p in args.prefixes]
        elif args.cmd == "replace":
            new = read_bullets(args.with_file)
            ops = [lambda d: replace(d, args.prefix, new, sec)]
        elif args.cmd == "insert-after":
            new = read_bullets(args.from_file)
            ops = [lambda d: insert_after(d, args.prefix, new, sec)]
        else:
            ops = [lambda d: sub(d, args.prefix, args.old, args.new, sec)]
        doc = edit(args.file, ops, dry_run=args.dry_run)
    except (StackEditError, OSError) as exc:
        print(f"stack_edit: refused: {exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        sys.stdout.flush()
        sys.stdout.buffer.write((diff(doc) + "\n").encode("utf-8"))
        sys.stdout.flush()
    else:
        print(f"stack_edit: {args.cmd} ok ({len(doc.original)} -> {len(doc.encode())} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
