"""Report Markdown prose sentences longer than a word limit (17-129).

Usage: python sentence_length_17-129.py [--limit N] FILE [FILE ...]

Prints one line per long sentence, ``file:line: N words: <start of sentence>``,
then one ``file: K over N`` line per file. Exit 1 when any sentence is over the
limit, else 0.

How prose is found. Lines are read in order and these are dropped: front
matter (a ``---`` block opening on line 1), fenced code (``` or ~~~, indented
or not, up to the matching fence), table rows (first non-blank character
``|``), ATX headings (``#``), display math (``$$`` lines), horizontal rules
(``---``, ``***``), HTML lines (first character ``<``), and lines indented
four or more spaces that do not continue a paragraph or list item. The
remaining lines form paragraphs; a blank line, a dropped line or a list marker
(``-``, ``*``, ``+``, ``1.``) starts a new one.

Each paragraph is joined into one string, so a code span or link may cross a
line break. In it, an inline code span becomes one mark that counts as no word
but can start a sentence, ``[text](url)`` keeps only ``text``, a bare URL is
deleted, and emphasis markers are deleted. A sentence ends at ``.``, ``!`` or
``?`` (an optional closing bracket or quote after it) followed by whitespace,
except after an abbreviation (``e.g.``, ``i.e.``, ``etc.``, ``vs.``, ``cf.``,
``al.``) or before a lowercase letter that follows a single-letter token. A
word is a whitespace token holding an ASCII letter or digit. Each sentence is
reported at the line it starts on.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LIMIT = 40

_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_RULE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_EMPH = re.compile(r"\*\*|__|(?<!\w)[*_]|[*_](?!\w)")
_END = re.compile(r"[.!?][)\"']?\s+")
_ABBREV = {"e.g.", "i.e.", "etc.", "vs.", "cf.", "al."}
_WORD = re.compile(r"[A-Za-z0-9]")
#: An inline code span becomes this mark.
CODE = "§"


def paragraphs(text: str) -> list[list[tuple[int, str]]]:
    """Prose paragraphs as lists of (1-based line number, line text)."""
    lines = text.splitlines()
    out: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    start = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                start = j + 1
                break

    def flush() -> None:
        nonlocal current
        if current:
            out.append(current)
        current = []

    fence: str | None = None
    for i in range(start, len(lines)):
        line = lines[i]
        stripped = line.strip()
        m = _FENCE.match(line)
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            flush()
            fence = m.group(1)
            continue
        if (
            not stripped
            or stripped.startswith(("|", "#", "$$", "<"))
            or _RULE.match(line)
            or (line.startswith("    ") and not current)
        ):
            flush()
            continue
        if _LIST.match(line):
            flush()
            line = _LIST.sub("", line, count=1)
        current.append((i + 1, line.strip()))
    flush()
    return out


def _blank(m: re.Match, keep: str = "") -> str:
    """Replace a match by ``keep`` padded with spaces to the match's length."""
    return keep + " " * (len(m.group(0)) - len(keep))


def clean(s: str) -> str:
    """Strip markup from a joined paragraph, keeping every character offset."""
    s = _INLINE_CODE.sub(lambda m: _blank(m, CODE), s)
    s = _LINK.sub(lambda m: _blank(m, m.group(1)), s)
    s = _URL.sub(_blank, s)
    return _EMPH.sub(_blank, s)


def _split(text: str) -> list[tuple[int, str]]:
    """(start offset, sentence) for each sentence in ``text``."""
    parts: list[tuple[int, str]] = []
    begin = 0
    for m in _END.finditer(text):
        token = text[:m.start() + 1].split()[-1].lower() if text[:m.start() + 1].split() else ""
        nxt = text[m.end():m.end() + 1]
        if token in _ABBREV or (nxt.islower() and len(token.rstrip(".!?")) <= 1):
            continue
        parts.append((begin, text[begin:m.end()]))
        begin = m.end()
    parts.append((begin, text[begin:]))
    return [(off, " ".join(s.split())) for off, s in parts if s.strip()]


def sentences(text: str) -> list[tuple[int, str]]:
    """(start line, sentence) for every prose sentence in ``text``."""
    result: list[tuple[int, str]] = []
    for para in paragraphs(text):
        joined = ""
        starts: list[tuple[int, int]] = []  # (offset in joined, line number)
        for lineno, raw in para:
            if joined:
                joined += " "
            starts.append((len(joined), lineno))
            joined += raw
        for offset, sentence in _split(clean(joined)):
            lineno = max(ln for off, ln in starts if off <= offset)
            result.append((lineno, sentence))
    return result


def word_count(sentence: str) -> int:
    return sum(1 for tok in sentence.split() if _WORD.search(tok))


def long_sentences(path: Path, limit: int = LIMIT) -> list[tuple[int, int, str]]:
    """(line, words, sentence) for each sentence in ``path`` over ``limit`` words."""
    text = path.read_text(encoding="utf-8")
    return [(ln, n, s) for ln, s in sentences(text) if (n := word_count(s)) > limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=LIMIT)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    total = 0
    summary = []
    for path in args.files:
        hits = long_sentences(path, args.limit)
        for ln, n, s in hits:
            print(f"{path.as_posix()}:{ln}: {n} words: {s[:90]}")
        summary.append(f"{path.as_posix()}: {len(hits)} over {args.limit}")
        total += len(hits)
    for line in summary:
        print(line)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
