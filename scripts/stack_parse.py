"""The one reader of the coordination stacks: headings, items and their Release fields.

Gate 15 and gate 17 (`scripts/harness_gate.py`), STEP 0a (`scripts/release_gate.py`) and the
stack editor (`scripts/stack_edit.py`) read headings through this module, so an item one of them
finds is found by each of them: at any heading depth, and in each HTML heading form the stacks
have used. Standard library only.
"""

from __future__ import annotations

import html
import re
from typing import List, NamedTuple, Optional, Tuple

#: A Markdown heading of any depth: at most three spaces, one or more ``#``, then whitespace or
#: the end of the line. ``group(2)`` is the title, or None when there is none.
HEADING = re.compile(r"^ {0,3}(#+)(?:[ \t]+(.*?))?[ \t]*$")
#: A heading inside a blockquote or a list item still renders as a heading.
CONTAINED_HEADING = re.compile(
    r"^[ \t]*(?:(?:>|[-*+]|\d+[.)])[ \t]*)+(#+)(?:[ \t]+(.*?))?[ \t]*$")
#: The first line of an HTML heading element. The element may run over several lines.
HTML_OPEN = re.compile(r"^\s*<h([1-6])\b[^>]*>", re.IGNORECASE)
#: How many lines one HTML heading element may span. An element that does not close within this
#: many lines is not a heading, and its lines stay body text.
HTML_HEADING_MAX_LINES = 4
#: A setext underline, which makes the line above it a heading.
SETEXT_UNDERLINE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
#: An item heading: the id, then whitespace and a title, or the end of the line.
ITEM_HEADING = re.compile(r"^(\d\d-\d+)(?:[ \t]+(.*))?$")
#: Anything that starts like an item id once leading markup is dropped, and is not an ISO date.
#: A heading of this shape that `ITEM_HEADING` does not read is a violation, never a skip.
ITEM_SHAPED = re.compile(r"^[\s*_`\[(#]*\d+-\d+(?!\d|-\d)")
#: The heading depth the stack writes items at (``### <id> <title>``). An unreadable section at
#: this depth or deeper that lists work is reported, not skipped.
ITEM_DEPTH = 3
#: A list entry, marked or quoted.
LIST_ITEM = re.compile(r"^[ \t]*(?:>[ \t]*)*(?:[-*+]|\d+[.)])[ \t]+\S")
#: The canonical Release line; its value is read from this form only. Detection is looser.
RELEASE_VALUE = re.compile(r"^Release:\s*(.*)$")
#: Searched anywhere in a line, so a field in a table cell or wrapped in HTML tags is seen too.
RELEASE_ANY = re.compile(r"(?<![\w-])Release(?:[*_`]|</?\w+[^>]*>)*\s*:", re.IGNORECASE)
#: A `Release` label whose colon is an entity, at the start of a line. It renders as the field.
_ENCODED_COLON = re.compile(r"^(Release)(?:&#0*58;|&#x0*3a;|&colon;)", re.IGNORECASE)


class Section(NamedTuple):
    """A heading and the lines under it, up to the next heading of any depth."""

    title: Optional[str]
    level: int
    lineno: int  # 1-based line of the heading; the title line for a setext heading
    body: List[str]
    enclosing: Optional[str]  # id of the item a subsection belongs to, else None


def _field_line(line: str) -> str:
    """``line`` with an entity-encoded colon in a line-initial `Release` label read as a colon.

    Only at the start of a line. A label quoted in prose, as the stack's own account of this form
    quotes it, is not a field, and reading it as one made a bullet's text a release value.
    """
    return _ENCODED_COLON.sub(r"\1:", line)


def _plain(markup: str) -> str:
    """Heading text with its tags dropped, its entities read and its whitespace collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", markup)).split())


def _html_heading_at(lines: List[str], i: int) -> Optional[Tuple[int, str, int]]:
    """``(level, title, last line index)`` for the HTML heading element opening at ``lines[i]``.

    The element closes at the end of its last line. None when no heading opens there, or when
    the element does not close within HTML_HEADING_MAX_LINES lines.
    """
    opened = HTML_OPEN.match(lines[i])
    if opened is None:
        return None
    level = opened.group(1)
    element = re.compile(
        rf"^\s*<h{level}\b[^>]*>(.*?)</h{level}\s*>\s*$", re.IGNORECASE | re.DOTALL)
    for last in range(i, min(len(lines), i + HTML_HEADING_MAX_LINES)):
        match = element.match("\n".join(lines[i:last + 1]))
        if match:
            return int(level), _plain(match.group(1)), last
    return None


def located_sections(text: str) -> List[Section]:
    """Every section of stack text, in order; the text before the first heading is one with
    title None and level 0.

    A section is a heading and the lines up to the next heading of any depth. Its enclosing
    item is the nearest item heading above it whose level is shallower, so a subsection of an
    item names that item, and a section at the item's own depth or shallower does not.
    """
    lines = text.splitlines()
    raw: List[list] = [[None, 0, 0, []]]
    i = 0
    while i < len(lines):
        line = lines[i]
        body = raw[-1][3]
        heading = HEADING.match(line) or CONTAINED_HEADING.match(line)
        html_heading = None if heading else _html_heading_at(lines, i)
        if heading:
            raw.append([(heading.group(2) or "").strip(), len(heading.group(1)), i + 1, []])
        elif html_heading:
            level, title, last = html_heading
            raw.append([title, level, i + 1, []])
            i = last + 1
            continue
        elif SETEXT_UNDERLINE.match(line) and body and body[-1].strip():
            title = body.pop().strip()
            raw.append([title, 1 if line.strip()[0] == "=" else 2, i, []])
        else:
            body.append(line)
        i += 1
    out: List[Section] = []
    open_items: List[Tuple[str, int]] = []
    for title, level, lineno, body in raw:
        while open_items and level <= open_items[-1][1]:
            open_items.pop()
        item = ITEM_HEADING.match(title) if title is not None else None
        enclosing = open_items[-1][0] if open_items and not item else None
        out.append(Section(title, level, lineno, body, enclosing))
        if item:
            open_items.append((item.group(1), level))
    return out


def sections(text: str) -> List[Tuple[Optional[str], int, List[str], Optional[str]]]:
    """``(title, level, body, enclosing item id)`` for each section; see `located_sections`."""
    return [(s.title, s.level, s.body, s.enclosing) for s in located_sections(text)]


def item_spans(text: str) -> List[Tuple[int, str, int, int]]:
    """``(line number, id, start offset, end offset)`` for every item, at any heading depth.

    An item runs from its heading to the next item heading, or to the end of the text. A
    subsection, and any other heading between two items, belongs to the item above it.
    """
    starts = [0]
    for line in text.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    items = [s for s in located_sections(text)
             if s.title is not None and ITEM_HEADING.match(s.title)]
    spans = []
    for k, item in enumerate(items):
        start = starts[item.lineno - 1]
        end = starts[items[k + 1].lineno - 1] if k + 1 < len(items) else len(text)
        spans.append((item.lineno, ITEM_HEADING.match(item.title).group(1), start, end))
    return spans


def stack_items(text: str) -> List[Tuple[int, str, str]]:
    """Every item as (line number, id, item text including its heading), at any heading depth."""
    return [(lineno, ident, text[start:end]) for lineno, ident, start, end in item_spans(text)]


def section_release(body: List[str]) -> Tuple[str, Optional[str]]:
    """``(value, first noncanonical line)`` for a section's own ``Release:`` field.

    ``MISSING`` when it has none, every distinct value joined when it states more than one, and
    ``NONCANONICAL`` when any of its ``Release:`` lines is not in the canonical form, so that none
    of these reads as deferred. An entity-encoded colon (``Release&#58;``) reads as a colon.
    """
    lines = [_field_line(line) for line in body]
    values = [m.group(1).strip().rstrip(".").strip()
              for m in map(RELEASE_VALUE.match, lines) if m]
    # Capture to end of line and strip one trailing sentence period. Stopping at the first `.`
    # would truncate `deferred-0.2.7` to `deferred-0`, and the truncated value compares unequal
    # to the deferred marker -- so every deferred item would read as still required.
    distinct = list(dict.fromkeys(values))
    value = ("MISSING" if not distinct else distinct[0] if len(distinct) == 1
             else "CONFLICTING: " + " / ".join(distinct))
    noncanonical = [raw.strip() for raw, line in zip(body, lines)
                    if RELEASE_ANY.search(line) and not RELEASE_VALUE.match(line)]
    return ("NONCANONICAL", noncanonical[0]) if noncanonical else (value, None)


def parse_todo_stack(text: str) -> Tuple[List[Tuple[str, str, str]], List[str]]:
    """``(items, unparseable)`` read from todo-stack text.

    A section is an item when its heading reads as an id, at any depth, in any of the heading
    forms above. Its release is the section's own field (see `section_release`). ``unparseable``
    names each section that is item-shaped, or carries a ``Release:`` field, but whose id cannot
    be read, and each item whose release cannot be read. The caller reports these as violations:
    an item the parser cannot read is still work, and skipping it would report emptiness that was
    not established.

    A section at item depth that is not inside an item and lists work, but has neither an id nor
    a ``Release:`` field, is unparseable too: its list is work the stack gives no release.
    """
    items: List[Tuple[str, str, str]] = []
    unparseable: List[str] = []
    for title, level, body, enclosing in sections(text):
        has_field = any(RELEASE_ANY.search(_field_line(line)) for line in body)
        item = ITEM_HEADING.match(title) if title is not None else None
        if item:
            value, noncanonical = section_release(body)
            if noncanonical:
                unparseable.append(
                    f"item {item.group(1)} has a Release: line not written 'Release: <value>' "
                    f"at the start of a line, so its release cannot be read: "
                    f"{noncanonical[:60]!r}")
            items.append((item.group(1), (item.group(2) or "").strip(), value))
        elif title is None:
            if has_field:
                unparseable.append("a Release: field appears before the first heading")
        elif has_field or ITEM_SHAPED.match(title):
            unparseable.append(f"heading {title[:60]!r} is item-shaped or carries a Release: "
                               "field, but no item id can be read from it")
        elif (level >= ITEM_DEPTH and enclosing is None
              and any(LIST_ITEM.match(line) for line in body)):
            unparseable.append(f"heading {title[:60]!r} sits at item depth outside any item and "
                               "lists work, but has no item id and no Release: field")
    return items, unparseable
