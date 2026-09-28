"""Edit a Markdown stack file one bullet at a time, preserving its line endings.

A bullet is a line starting with ``- `` together with the non-blank lines after it that start
with two spaces (its continuation lines). It ends at a blank line, a heading line (up to three
spaces, one to six ``#``, then whitespace or end of line) or any other line. A bullet is addressed by an exact prefix of its first line; the prefix must be
delimited (it may not stop inside a token, so ``- A-2`` never matches ``- A-20``) and must match
exactly one bullet, optionally within one heading's section.

Every operation runs on an in-memory copy and is checked before anything is written. The result
goes to a temporary file in the same directory, is verified in bytes, and replaces the original
with ``os.replace``; a refusal leaves the file unchanged. New text is read from a UTF-8 file,
never from a shell argument, so the shell cannot rewrite it.

Whole headed items, field lines and table rows are not bullets and are out of reach.

Usage::

    python scripts/stack_edit.py --file F [--section H] [--dry-run] delete PREFIX [PREFIX ...]
    python scripts/stack_edit.py --file F [--section H] [--dry-run] replace PREFIX --with-file P
    python scripts/stack_edit.py --file F [--section H] [--dry-run] insert-after PREFIX --from-file P
    python scripts/stack_edit.py --file F [--section H] [--dry-run] sub PREFIX --old S --new S

``--section`` takes a heading's text, optionally with its ``#`` marks (``"## Title"``), which
then also fixes its level. Exit status is 0 on success and 2 on a refusal, with the reason on
stderr.
"""

from __future__ import annotations

import argparse
import difflib
import os
import pathlib
import re
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_HEADING_LIKE = re.compile(r"^ {0,3}#{1,6}(\s|$)")
_THEMATIC_BREAK = re.compile(r"^ {0,3}-(?: *-){2,} *$")
_TOKEN = re.compile(r"[\w-]")


class StackEditError(Exception):
    """Raised when an edit would be ambiguous, malformed or unverifiable. Nothing is written."""


@dataclass
class Doc:
    """A stack file held as lines, with the newline convention it was read with."""

    lines: list
    newline: str
    path: Optional[pathlib.Path] = None
    original: bytes = field(default=b"", repr=False)
    # Consecutive delete() calls re-resolve every prefix against the lines before the first of
    # them, so a later prefix never matches a bullet that only became unique after a deletion.
    _deletes: list = field(default_factory=list, repr=False)
    _delete_base: Optional[list] = field(default=None, repr=False)
    _delete_result: Optional[list] = field(default=None, repr=False)

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


def _is_fence(line: str) -> bool:
    return line.lstrip().startswith("```")


def _is_bullet(line: str) -> bool:
    return line.startswith("- ") and not _THEMATIC_BREAK.match(line)


def _is_continuation(line: str) -> bool:
    return line.startswith("  ") and line.strip() != "" and not _HEADING_LIKE.match(line)


def _fenced(lines: Sequence[str]) -> list:
    """Per line, whether it sits inside a fenced code block (fence lines included)."""
    inside, out = False, []
    for line in lines:
        if _is_fence(line):
            out.append(True)
            inside = not inside
        else:
            out.append(inside)
    return out


def _parse_heading(text: str) -> tuple:
    text = text.strip()
    m = re.match(r"^(#{1,6})\s+(.*?)\s*$", text)
    if m:
        return len(m.group(1)), m.group(2)
    return None, text


def section_range(lines: Sequence[str], heading: Optional[str]) -> tuple:
    """Line range ``[start, stop)`` under ``heading``, up to the next heading of its level or higher."""
    if heading is None:
        return 0, len(lines)
    want_level, want = _parse_heading(heading)
    fenced = _fenced(lines)
    heads = []
    for i, line in enumerate(lines):
        m = _HEADING.match(line)
        if m and not fenced[i]:
            heads.append((i, len(m.group(1)), m.group(2)))
    hits = [
        (i, lvl) for i, lvl, text in heads
        if text == want and (want_level is None or lvl == want_level)
    ]
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
    """Index one past the last continuation line of the bullet starting at ``i``.

    Refuses when the next non-blank line after the bullet is indented (by a space or a tab)
    without being a two-space continuation, for example after one or more blank lines: whether
    that line belongs to the bullet is ambiguous, and guessing would delete or keep text the
    caller did not name. An indented heading line ends the bullet.
    """
    j = i + 1
    while j < len(lines) and _is_continuation(lines[j]):
        j += 1
    k = j
    while k < len(lines) and lines[k].strip() == "":
        k += 1
    if k < len(lines) and lines[k][:1] in (" ", "\t") and not _HEADING_LIKE.match(lines[k]):
        raise StackEditError(
            f"bullet at line {i + 1} is followed by an indented line that is not a two-space "
            f"continuation (line {k + 1}); its extent is ambiguous"
        )
    return j


def check_region(lines: Sequence[str], start: int, stop: int) -> None:
    """Refuse unless ``lines[start:stop]`` parses as whole bullets with no fence line."""
    i = start
    while i < stop:
        if not _is_bullet(lines[i]):
            raise StackEditError(f"line {i + 1} is not a bullet: {lines[i]!r}")
        j = unit_end(lines, i)
        for k in range(i, j):
            if _is_fence(lines[k]):
                raise StackEditError(f"line {k + 1} is a code fence inside a bullet")
        i = j


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
        kind = "a continuation line" if lines[others[0]].startswith("  ") else "a non-bullet line"
        raise StackEditError(
            f"prefix {prefix!r} matches {kind}{where} (line {others[0] + 1}); "
            "address the bullet by its first line"
        )
    if _TOKEN.match(prefix[-1]):
        for i in bullets:
            nxt = lines[i][len(prefix):len(prefix) + 1]
            if nxt and _TOKEN.match(nxt):
                raise StackEditError(
                    f"prefix {prefix!r} stops inside a token at line {i + 1} "
                    f"({lines[i][:len(prefix) + 12]!r}); end it at a delimiter such as ':'"
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
    check_region(new, 0, len(new))
    return new


def _delete_spans(lines: list, targets: Sequence[tuple]) -> None:
    """Delete the bullets named by ``(prefix, section)`` pairs, all resolved against ``lines``."""
    spans = sorted(find(lines, p, s) + (p,) for p, s in targets)
    for (_, stop_a, pa), (start_b, _, pb) in zip(spans, spans[1:]):
        if start_b < stop_a:
            raise StackEditError(f"prefixes {pa!r} and {pb!r} address the same bullet")
    for start, stop, p in spans:
        fences = [k + 1 for k in range(start, stop) if _is_fence(lines[k])]
        if fences:
            raise StackEditError(
                f"bullet {p!r} holds a code fence at line {fences[0]}; deleting it would "
                "re-fence the lines after it"
            )
    for start, stop, _ in reversed(spans):
        del lines[start:stop]


def delete_many(doc: Doc, prefixes: Sequence[str], section: Optional[str] = None) -> None:
    """Delete several bullets, each resolved against the lines as they were before any deletion."""
    _delete_spans(doc.lines, [(p, section) for p in prefixes])
    doc._deletes, doc._delete_base, doc._delete_result = [], None, None


def delete(doc: Doc, prefix: str, section: Optional[str] = None) -> None:
    """Delete one bullet; consecutive calls on one doc behave as a single :func:`delete_many`."""
    if doc._delete_result is None or doc.lines != doc._delete_result:
        doc._deletes, doc._delete_base = [], list(doc.lines)
    targets = doc._deletes + [(prefix, section)]
    lines = list(doc._delete_base)
    _delete_spans(lines, targets)
    doc.lines[:] = lines
    doc._deletes, doc._delete_result = targets, list(lines)


def replace(doc: Doc, prefix: str, new: list, section: Optional[str] = None) -> None:
    start, stop = find(doc.lines, prefix, section)
    doc.lines[start:stop] = list(new)
    check_region(doc.lines, start, start + len(new))


def insert_after(doc: Doc, prefix: str, new: list, section: Optional[str] = None) -> None:
    _, stop = find(doc.lines, prefix, section)
    doc.lines[stop:stop] = list(new)
    check_region(doc.lines, stop, stop + len(new))


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
    doc.lines[start:stop] = [line.replace(old, new) for line in unit]
    check_region(doc.lines, start, stop)


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
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(out)
        written = pathlib.Path(tmp).read_bytes()
        if written != out:
            raise StackEditError(f"{tmp}: bytes on disk differ from the bytes written")
        check_newlines(written, doc.newline)
        if path.read_bytes() != doc.original:
            raise StackEditError(f"{path} changed on disk during the edit")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
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
            ops = [lambda d: delete_many(d, args.prefixes, sec)]
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
