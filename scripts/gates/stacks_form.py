"""Stack-form machinery: the text helpers gate 15 reasons over."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
from scripts.stack_parse import item_spans, stack_items as _stack_items


#: The two coordination stacks gate 15 reads. Both are tracked; a missing one is a broken
#: sweep rather than a clean tree, and is reported as such.
TODO_STACK = "artifacts/todo_stack.md"
OPEN_STACK = "artifacts/open_stack.md"


def _code_span_mask(text: str) -> bytearray:
    """A byte per character, 1 where that character sits inside a code span or fenced block.

    The stacks quote their own rules, so this cannot be skipped. `artifacts/todo_stack.md`
    contains the literal ``Writes:`` inside a code span twice, where one passage states the rule it
    is asking for. A scanner that treats those as field labels starts in the middle of a span,
    has its backtick parity inverted from that point on, and pairs the gaps *between* code
    spans instead of the spans. The first version of this check did exactly that: two labels
    swallowed 12,488 and 11,377 characters to the end of the file, and it still reported zero
    violations -- not because the stack was clean, but because it was no longer looking at
    code spans at all. A run-on field is the failure this mask exists to prevent.
    """
    mask = bytearray(len(text))
    index, end = 0, len(text)
    while index < end:
        if text.startswith("```", index):
            close = text.find("```", index + 3)
            close = end if close == -1 else close + 3
            for offset in range(index, close):
                mask[offset] = 1
            index = close
            continue
        if text[index] == "`":
            close = text.find("`", index + 1)
            newline = text.find("\n", index + 1)
            # An inline span closes on its own line; a lone backtick is not a span.
            if close != -1 and (newline == -1 or close < newline):
                for offset in range(index, close + 1):
                    mask[offset] = 1
                index = close + 1
                continue
        index += 1
    return mask


def _writes_fields(text: str) -> List[Tuple[int, str]]:
    """Every `Writes:` field, as (line number, field text), bounded at its own sentence end.

    The boundary is where this check is hard, not the pattern. A field wraps across up to four
    lines, and a `.` inside a code span is content -- `docs/api.md` is a path, not two
    sentences -- so the scan ends at the first `.` outside a code span that is followed by
    whitespace, with a blank line as a backstop so a malformed field cannot run past its own
    paragraph.

    Bounding by a fixed character count instead reports prose as a violation. At 220 characters
    this named two cases, one whose text *discusses* `tests/`, and one that names the cache
    directory it exists to exclude. Both items are correct. A check that fires on prose is
    worse than no check, because it teaches its reader to dismiss the output, and that is how
    the one real violation gets waved through.
    """
    return [(lineno, field) for lineno, field, _end in _writes_field_spans(text)]


def _writes_field_spans(text: str) -> List[Tuple[int, str, int]]:
    """`_writes_fields` plus each field's end offset, which the truncation check needs.

    Split out rather than duplicated: a second copy of this scan would be a second boundary
    rule, and the two would drift. The offset is what `_suspected_truncated_writes` inspects,
    and recovering it with `text.find` instead would alias two identical fields to one site.
    """
    mask = _code_span_mask(text)
    spans: List[Tuple[int, str, int]] = []
    for label in re.finditer(r"Writes:", text):
        if mask[label.start()]:
            continue  # the rule quoted in prose, not a field declaring a write set
        index = label.end()
        paragraph = text.find("\n\n", index)
        stop = len(text) if paragraph == -1 else paragraph
        while index < stop:
            if (
                text[index] == "."
                and not mask[index]
                and (index + 1 >= stop or text[index + 1].isspace())
            ):
                break
            index += 1
        spans.append(
            (text.count("\n", 0, label.start()) + 1, text[label.end():index], index)
        )
    return spans


#: Content that continues a `Writes:` field past the point the sentence boundary stopped: a run
#: of backtick tokens, optionally joined by commas or `and`. Anything else -- a capital letter, a
#: field label, prose -- is the next sentence and not part of the field.
_CONTINUES_AS_PATHS = re.compile(r"[\s]*(?:and\s+)?`[^`\n]*`(?:[\s,]*(?:and\s+)?`[^`\n]*`)*")


def _suspected_truncated_writes(text: str) -> List[Tuple[int, str]]:
    """`Writes:` fields whose text ends immediately before more path-like tokens.

    One field read ``Writes: `jnwb/nwb_io.py`, `artifacts/goal.md`, AUTONOMY: none.`` on one line
    and ``` `docs/errors.md`, `tests/`. ``` on the next. Any parser bounded by a sentence stops
    at that full stop and never sees the last two entries, one of which was a genuine bare
    `tests/` -- the exact defect this gate exists to catch, sitting undetected inside the
    gate's own live zero.

    The boundary is **not** changed, because the replacement that was prescribed -- a run of
    backtick tokens separated only by commas and whitespace -- does not fit the data. Measured
    against the live stack, that rule read *fewer* tokens in six fields and more in none, and
    nothing at all in two: the fields legitimately interleave prose, as in
    ``Writes: a new page under `docs/*.md` (named at dispatch; ...)`` and
    ``Writes: the routed skill file and `tests/test_skills_validation.py``. Bounding at the
    next field label instead runs into free-prose bodies, which is the false-positive failure
    the boundary docstring already records.

    So instead of moving the boundary, the gate says when it might be in the wrong place. A
    field followed immediately by more backticked paths is reported for a human to read. That
    turns a silent truncation into a visible question, and needs no solution to a boundary
    problem the stack's own format does not admit.

    Measured on the live stack at the time of writing: zero fields flagged, and zero bare
    directories hidden from the sentence rule. This is a tripwire for the shape's return, not
    a repair of a live instance -- a field was repaired by hand when this was raised.
    """
    flagged: List[Tuple[int, str]] = []
    for lineno, _field, end in _writes_field_spans(text):
        after = end + 1 if end < len(text) and text[end] == "." else end
        match = _CONTINUES_AS_PATHS.match(text, after)
        if not match or not match.group(0).strip():
            continue
        tail = match.group(0)
        if not any("/" in token for token in re.findall(r"`([^`\n]*)`", tail)):
            continue  # a backticked identifier is prose continuing; only paths look truncated
        flagged.append((lineno, " ".join(tail.split())))
    return flagged


#: A present-tense assertion that the item is blocked. Deliberately shallow, and deliberately
#: not taught to parse negation: the repair sentence written to discharge a stale block
#: read "this item is no longer blocked on it", which a phrase list matches as an assertion.
#: That sentence was reworded to "that block is discharged" instead, because a phrase list that
#: tries to read polarity is a worse thing to trust than one that is obviously shallow and
#: prints what it suppressed.
_BLOCK_ASSERTIONS = (
    "blocked on",
    "blocked by",
    "is blocked",
    "blocked until",
    "waits on",
    "waiting on",
    "cannot start until",
    "needs a ruling",
    "requires a ruling",
    "awaits a ruling",
)

#: The phrase list as one alternation, longest first so `blocked until` is not read as the
#: shorter `blocked` prefix of another entry.
_ANY_BLOCK_ASSERTION = re.compile(
    "|".join(re.escape(p) for p in sorted(_BLOCK_ASSERTIONS, key=len, reverse=True))
)

#: An item id is the cycle's two-digit minor version, a hyphen and a number (`NN-NN`).
#: The lookbehind keeps the month and day of a date such as 2026-09-19 from reading as an id.
_ITEM_ID = re.compile(r"(?<![\w-])\d{2}-\d+\b")


#: A field label opens a new clause, and so closes the one before it. Used to bound a `Stop:`
#: clause, which runs to the next label and *not* to the next full stop: one stop reads
#: "Stop: ... resolved first. Then this waits on ...", so the assertion sits one sentence
#: after the key. A first draft keyed the suppression on the sentence and missed it: the first
#: attempt failed with "line" replaced by "sentence", which is the same defect again.
_FIELD_LABEL = re.compile(
    r"\b(?:Release|Role|Skill|Blocked by|Reads|Writes|Reproduce|Do|Discriminator|Accept|"
    r"AUTONOMY|Stop):"
)


def _unwrapped_spans(text: str) -> Tuple[str, List[Tuple[int, int]]]:
    """`text` unwrapped, with each sentence's `(start, end)` offsets into the unwrapped string.

    Offsets rather than substrings, because both suppressions below key on where a match sits
    relative to a clause that can begin in an earlier sentence.
    """
    flat = " ".join(text.split())
    mask = _code_span_mask(flat)
    spans, start = [], 0
    for index, char in enumerate(flat):
        if char == "." and not mask[index] and index + 1 < len(flat) and flat[index + 1] == " ":
            spans.append((start, index + 1))
            start = index + 1
    spans.append((start, len(flat)))
    return flat, [(a, b) for a, b in spans if flat[a:b].strip()]


def _stop_clause_spans(flat: str) -> List[Tuple[int, int]]:
    """Where each `Stop:` clause begins and ends in an unwrapped item body."""
    spans = []
    for stop in re.finditer(r"\bStop:", flat):
        following = _FIELD_LABEL.search(flat, stop.end())
        spans.append((stop.start(), following.start() if following else len(flat)))
    return spans


def _unwrapped_sentences(text: str) -> List[str]:
    """`text` with its hard wrapping removed, split into sentences outside code spans.

    **A physical line is not a semantic unit in this file.** A line-based version of the check
    below flagged three items and suppressed none, because the stack is hard-wrapped and both
    exclusion keys -- a `Stop:` clause and the blocking item's id -- sat on the *previous*
    physical line. Unwrapping raised recall as well as precision: it surfaced a case the
    line scan had missed entirely. The narrowing defect again, in a third guise -- a
    proxy for a unit of meaning mistaken for the unit.
    """
    flat, spans = _unwrapped_spans(text)
    return [flat[a:b].strip() for a, b in spans]


def _excise_blocked_by(body: str) -> str:
    """`body` with every `Blocked by:` declaration replaced by a space, code spans left whole.

    A declaration runs to the first newline or the first `.` outside a code span. A label quoted
    inside a code span runs only to that span's closing backtick. Cutting a quoted label to the
    next full stop removed the closing backtick, the unwrapped text then paired the orphaned
    opening backtick with the next one, and the sentences in between merged into one span whose
    suppression covered all of them.
    """
    mask = _code_span_mask(body)
    pieces, last = [], 0
    for label in re.finditer(r"Blocked by:", body):
        if label.start() < last:
            continue
        index = label.end()
        if mask[label.start()]:
            while index < len(body) and body[index] != "`":
                index += 1
        else:
            while index < len(body) and body[index] != "\n" and (
                body[index] != "." or mask[index]
            ):
                index += 1
        pieces.append(body[last:label.start()])
        pieces.append(" ")
        last = index
    pieces.append(body[last:])
    return "".join(pieces)


def _blocked_by_none_contradictions(
    text: str,
) -> Tuple[List[Tuple[int, str, str]], List[Tuple[int, str, str, str]]]:
    """Items declaring `Blocked by: none` whose own text asserts they are blocked.

    06-31 recorded `Blocked by: none` and was in fact blocked on data-access authority; a second
    case inherited that block through `Blocked by: 06-31`, unrecorded too. A third case read
    `Blocked by: none` while its body said "Blocked on one ruling" and its Accept clause said
    the problem closes only once that ruling is recorded -- and the scheduler offered it as
    dispatchable, twice. The metadata is *confidently wrong rather than absent*, which
    is why every reader trusts it.

    Returns `(flagged, suppressed)`. **Both are returned, and the caller prints the
    suppressions**, because a narrowing that is invisible is how a false positive turned
    into a blind spot: one of the two cases silenced there was real. Two suppressions are
    applied, each keyed on the match's own position rather than on the sentence it sits in:

    | Suppressed when | Why |
    |---|---|
    | a `Stop:` clause opens before the match | the field states the stop; the clause describes it |
    | every item id in the sentence has retired | the block named is discharged with its item |
    """
    live = {item_id for _lineno, item_id, _start, _end in item_spans(text)}
    flagged: List[Tuple[int, str, str]] = []
    suppressed: List[Tuple[int, str, str, str]] = []

    for lineno, item_id, body in _stack_items(text):
        field = re.search(r"Blocked by:\s*([^.\n]*)", body)
        if not field or field.group(1).strip().lower().rstrip(".") != "none":
            continue
        # Excise *every* field declaration, not just the one read above. `Blocked by: none.`
        # matches the phrase list on its own, and a first draft flagged 33 of 52 live items on
        # nothing but their own metadata. Removing only the first left a second declaration --
        # which a malformed item can carry -- readable as prose.
        prose = _excise_blocked_by(body)
        flat, spans = _unwrapped_spans(prose)
        stops = _stop_clause_spans(flat)
        for start, end in spans:
            sentence = flat[start:end].strip()
            # Every occurrence of every phrase, not the first: a sentence whose opening match
            # is suppressed can carry a real assertion afterwards, and stopping at the first
            # would let the suppression cover it.
            reason = None
            for hit in _ANY_BLOCK_ASSERTION.finditer(flat.lower(), start, end):
                at = hit.start()
                if any(a <= at < b for a, b in stops):
                    reason = "inside a `Stop:` clause"
                    continue
                named = set(_ITEM_ID.findall(sentence)) - {item_id}
                if named and not (named & live):
                    reason = f"names only retired items: {', '.join(sorted(named))}"
                    continue
                flagged.append((lineno, item_id, sentence))
                reason = None
                break
            if reason is not None:
                suppressed.append((lineno, item_id, sentence, reason))
    return flagged, suppressed


#: A count of items in summary prose, including the elided form "three more" where the noun
#: carries over from the preceding clause. Requiring the literal word "items" missed the one
#: live instance while matching two sentences that state counts about items they never list.
_ITEM_COUNT = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)\s+"
    r"(?:(?:more|further)\b\s*(?:items?\b)?|items?\b)",
    re.IGNORECASE,
)
_COUNT_VALUE = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
#: A clause break. The ids an assertion enumerates sit in its own clause, so ids beyond the
#: break belong to a different statement -- which is what separates a miscount from "it
#: assigned 16 items to five lanes ... -- the compression lane pointed at 06-24 and NN-NN".
_CLAUSE_BREAK = re.compile(r"\s--\s|;")


def _summary_regions(text: str) -> List[Tuple[int, int]]:
    """The spans of `todo_stack.md` that are prose ABOUT items rather than an item body.

    A count inside an item is that item's own statement about its work. A count in a batch
    preamble is a summary of the items below it, and is derived data stored as prose.
    """
    starts = [start for _lineno, _item_id, start, _end in item_spans(text)]
    heads = [m.start() for m in re.finditer(r"^## ", text, re.MULTILINE)]
    regions: List[Tuple[int, int]] = []
    cursor = 0
    for start in starts:
        if start > cursor:
            regions.append((cursor, start))
        following = [h for h in heads if h > start]
        cursor = following[0] if following else len(text)
    if cursor < len(text):
        regions.append((cursor, len(text)))
    return regions


def _miscounted_summaries(text: str) -> List[Tuple[int, str, int, List[str], str]]:
    """Summary sentences whose stated item count disagrees with the ids they enumerate.

    Batch 0 opened with "Six items wait on a human ruling ... 06-13, 06-18, NN-NN,
    NN-NN, NN-NN and NN-NN". Four waited, not six; three of the six named had closed earlier
    the same day; and none of the four gated more than one item, so the sentence named a
    binding constraint that no longer bound. Every number in it is recomputable from the
    fields below it, so storing it as prose could only ever drift, and re-deriving it by hand
    is a fix with a shelf life.

    **"Recompute each count a summary asserts" is not mechanically reliable in general** --
    a first attempt counted every id in the sentence and flagged 2 of 2 as false positives,
    because one sentence carries several counts each governing its own list, and because
    "it assigned 16 items to five lanes, and 14 of those 16 were retired" states counts about
    items it never enumerates. What *is* reliable is the enumerated form, which is the shape
    the earlier instance had: a count, then the ids, within one clause.

    Measured on the live stack: 1 flagged, and it was real -- "three more are blocked on
    authority Hamm holds: 06-31 and NN-NN on the corpus grant, NN-NN and NN-NN on a ruling
    and that grant respectively" names four. A stricter variant requiring the ids to form a
    contiguous run flagged exactly the same sentence, so it buys no separation and is not
    used.

    The corollary is that a summary asserting a count **without** naming the items cannot be
    checked at all. Batch 0's "three items Hamm must decide" was such a claim, and was two.
    It was rewritten to name them rather than checked by a second mechanism, so the prose is
    now in a form this one rule covers.
    """
    flagged: List[Tuple[int, str, int, List[str], str]] = []
    for start, end in _summary_regions(text):
        base = text.count("\n", 0, start) + 1
        flat, spans = _unwrapped_spans(text[start:end])
        for a, b in spans:
            sentence = flat[a:b].strip()
            counts = list(_ITEM_COUNT.finditer(sentence))
            for index, counted in enumerate(counts):
                word = counted.group(1).lower()
                asserted = _COUNT_VALUE.get(word, int(word) if word.isdigit() else None)
                if asserted is None:
                    continue
                stop = counts[index + 1].start() if index + 1 < len(counts) else len(sentence)
                brk = _CLAUSE_BREAK.search(sentence, counted.end(), stop)
                span = sentence[counted.end():brk.start() if brk else stop]
                ids = sorted(set(_ITEM_ID.findall(span)))
                if ids and asserted != len(ids):
                    flagged.append((base, counted.group(0).strip(), asserted, ids, sentence))
    return flagged


#: A numeral immediately followed by "item"/"items". The lookbehind keeps the digits after the
#: hyphen of an item id, a problem row or a date, and those after a decimal point, a thousands
#: comma or a section sign, from reading as a count.
_NUMERAL_ITEMS = re.compile(r"(?<![\w.,\xa7-])(\d+)\s+items?\b", re.IGNORECASE)
#: What makes that count a claim about the whole stack rather than about a subset of it.
_TOTAL_BEFORE = re.compile(r"(?:\bof\s+the|\ball(?:\s+of\s+the|\s+the)?)\s+$", re.IGNORECASE)
_TOTAL_AFTER = re.compile(r"\s+(?:below\b|in\s+(?:this|the)\s+stack\b)", re.IGNORECASE)


def _inside_quotation(sentence: str, at: int) -> bool:
    """Whether offset `at` sits inside a double-quoted span: a report of what a line once said."""
    before = sentence[:at]
    opened = before.count("\N{LEFT DOUBLE QUOTATION MARK}")
    closed = before.count("\N{RIGHT DOUBLE QUOTATION MARK}")
    return before.count('"') % 2 == 1 or opened > closed


def _stale_item_totals(text: str) -> List[Tuple[int, str, int, int, str]]:
    """Summary sentences stating a total number of items that differs from the live count.

    The dispatch map read "37 of the 57 items below" while the stack held 52, and before that
    "45 of the 74 items below" through twenty revisions of the stack as it shrank to 57. Neither
    names an id, so `_miscounted_summaries` has nothing to count them against; the total is
    checkable only against the stack itself, which is the count of `### 06-NN` headers.

    A total is a numeral directly before "items", outside code spans and quotations, in a
    summary region, whose clause names no item id, and which is marked as the whole stack:
    preceded by "of the", "all", "all the" or "all of the", or followed by "below" or "in
    this/the stack". Run over every revision of the stack, this flagged the two stale totals
    above and nothing else. Two unmarked counts in the same history, "It assigned 16 items to
    five lanes" and "24 items declared `tests/`", are statements about a subset, and a
    quotation of an earlier total (the map once read "45 of the 74 items below") is history
    rather than a claim; none of the three is flagged.

    Not caught, by design: number words ("fifty-seven items"), an adjective between the numeral
    and the noun ("57 open items"), a total phrased without a marker ("the stack holds 57
    items"), counts inside an item body, and the subset numeral in "37 of the 57".
    """
    live = len(item_spans(text))
    stale: List[Tuple[int, str, int, int, str]] = []
    for start, end in _summary_regions(text):
        base = text.count("\n", 0, start) + 1
        flat, spans = _unwrapped_spans(text[start:end])
        mask = _code_span_mask(flat)
        for a, b in spans:
            sentence = flat[a:b]
            for counted in _NUMERAL_ITEMS.finditer(sentence):
                if mask[a + counted.start()] or _inside_quotation(sentence, counted.start()):
                    continue
                if not (
                    _TOTAL_BEFORE.search(sentence[:counted.start()])
                    or _TOTAL_AFTER.match(sentence, counted.end())
                ):
                    continue
                brk = _CLAUSE_BREAK.search(sentence, counted.end())
                if _ITEM_ID.search(sentence[counted.end():brk.start() if brk else len(sentence)]):
                    continue  # an enumerated count is `_miscounted_summaries`'s to check
                asserted = int(counted.group(1))
                if asserted != live:
                    stale.append((base, counted.group(0), asserted, live, sentence.strip()))
    return stale
