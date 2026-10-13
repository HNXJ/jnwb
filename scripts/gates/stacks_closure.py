"""Gate 15 (stack form): the generation closure and the consistency check."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
from scripts.gates.stacks_form import (
    TODO_STACK, PROBLEM_STACK, _blocked_by_none_contradictions,
    _miscounted_summaries, _stale_item_totals,
    _suspected_truncated_writes, _writes_fields,
)


#: Unescaped `|` delimits a GFM table cell. `\|` is content wherever it appears, including
#: inside a code span: GFM splits a row into cells *before* it parses inline code, which is
#: why P-29 and P-81 shipped rows whose backticked pipes silently became extra columns.
_ESCAPED_PIPE = re.compile(r"\\\|")


#: Files that are *derived*, with what invalidates each and what regenerates it. This is the
#: generation closure P-173 asked for, written down: a lane's write set can be complete,
#: correct and disjoint and still invalidate a file outside it, so disjointness alone is not
#: sufficient for concurrency. 06-47 added a parameter to `probe_geometry`'s signature and
#: `docs/api.md` went stale the moment it landed, because no lane edits that page by hand and
#: so it was in no lane's write set. The integrated suite went 25 failed, 18 of them
#: `test_every_gate_runs.py` cascading from one real gate-9 failure -- 25 masks on one defect,
#: and a count of failures is not a count of causes.
#:
#: The obligation is placed on the **integrator**, not on the write sets, and that choice was
#: measured rather than assumed: 7 of 52 live items name a path under `jnwb/` and none names
#: `docs/api.md`, so requiring them all to name it would make those 7 mutually exclusive with
#: one another and declare a maximum parallelism of one across every item that touches the
#: package. That is exactly the defect P-108 recorded for bare directories, in a new spelling.
#:
#: `tracked` distinguishes a file that must be committed in step from one generated per tree
#: and deliberately gitignored -- `artifacts/state.md` is the latter, so its absence in a
#: fresh worktree is correct and not drift.
GENERATED_FROM = (
    {
        "derived": "docs/api.md",
        "sources": ("jnwb/",),
        "generator": "scripts/generate_api_md.py",
        "verified_by": "gate 9, which regenerates the page and compares it to the committed copy",
        "tracked": True,
    },
    {
        "derived": "artifacts/state.md",
        "sources": ("<any HEAD move>",),
        "generator": "scripts/reconstruct_state.py",
        "verified_by": "gate 20, which compares the recorded HEAD with the live one when the "
                       "file is present, and `--check`, which AGENTS.md section 3 Prepare runs",
        "tracked": False,
    },
)


#: A problem row as the `## Open` table writes one: the id alone and unmarked in the first cell.
_CANONICAL_OPEN_ROW = re.compile(r"^\| P-\d+ \|")


def _row_delimiters(line: str) -> int:
    return _ESCAPED_PIPE.sub("", line).count("|")


def check_stack_form_consistency(repo_root: Optional[Path] = None) -> List[str]:
    """Gate 15 (Stack Form Consistency): the coordination stacks stay machine-readable.

    Two defects in the form of the stacks themselves, both repaired by hand during 0.2.6 and
    both recurring because nothing read the files.

    **Declared write sets must be comparable.** Two agents may run concurrently exactly when
    their `Writes` sets are provably disjoint, so a `Writes:` field naming a bare directory
    answers no question a scheduler asks. Measured at `5257e430`: 37 of 60 items named one and
    31 named the same directory, which declared a maximum parallelism of one across more than
    half the work (P-108). A glob passes, because `docs/*.md` conflicts honestly with
    `docs/api.md` while `docs/` conflicts with everything and says nothing.

    **Every problem row carries its own table's column count.** Each table in the problem stack
    is held to its own header, so a row with a missing cell, or an unescaped `|` inside a code
    span, is reported. This shipped five times in one session, when the stack had two tables of
    four columns each but not the same four.

    **`## Open` holds one table and nothing else.** The section exists, its only table has the
    header `ID | Problem | Found by` and its separator, and every other non-blank line in it is
    a row whose first cell is a bare `P-<n>`. `scripts/release_gate.py` STEP 0a reads every
    other line there as an untriaged problem; this check says which of them are not in the form
    a reader of the table can see. A well-formed row passes here, because recording a problem
    is how it gets triaged, and refusing it is the release's job.
    """
    root = repo_root or REPO_ROOT
    violations: List[str] = []

    todo_path = root / TODO_STACK
    if not todo_path.is_file():
        violations.append(f"STACK_FORM: {TODO_STACK} is missing; the sweep is broken, not the tree")
    else:
        fields = _writes_fields(todo_path.read_text(encoding="utf-8"))
        # A sweep that finds no field reports no violation, which reads exactly like a clean
        # stack. Gate 14 and gate 8 guard the same way.
        if not fields:
            violations.append(
                f"STACK_FORM: no 'Writes:' field found in {TODO_STACK}; the sweep is broken"
            )
        stack_text = todo_path.read_text(encoding="utf-8")
        for lineno, tail in _suspected_truncated_writes(stack_text):
            violations.append(
                f"STACK_FORM: {TODO_STACK}:{lineno} has a 'Writes:' field followed immediately "
                f"by more paths -- {tail}. The field is bounded at a sentence, so those entries "
                "are not being read, and a bare directory among them would be invisible to the "
                "check above. Put the whole write set in one sentence."
            )
        flagged, suppressed = _blocked_by_none_contradictions(stack_text)
        for lineno, item_id, sentence in flagged:
            violations.append(
                f"STACK_FORM: {TODO_STACK}:{lineno} item {item_id} declares 'Blocked by: none' "
                f"and its own text says it is blocked -- \"{sentence[:180]}\". A scheduler reads "
                "the field, so the item is offered as dispatchable. Record the block in the "
                "field, or reword the sentence if the block is discharged."
            )
        # Printed whether or not anything was flagged. A suppression nobody reads is how the
        # narrowing in P-125 turned a false positive into a blind spot -- one of the two cases
        # silenced there was real. These go to stdout rather than into `violations`: they are
        # not defects, and a reader has to be able to check that each narrowing was right.
        for lineno, item_id, sentence, why in suppressed:
            print(
                f"STACK_FORM note: {TODO_STACK}:{lineno} item {item_id} asserts a block and was "
                f"suppressed, {why} -- \"{sentence[:180]}\""
            )
        for lineno, phrase, asserted, ids, sentence in _miscounted_summaries(stack_text):
            violations.append(
                f"STACK_FORM: {TODO_STACK}:{lineno} a summary says '{phrase}' and then names "
                f"{len(ids)} -- {', '.join(ids)}. The count is derived from the items below it, "
                f"so prose can only drift from them: \"{sentence[:160]}\""
            )
        for lineno, phrase, asserted, live, sentence in _stale_item_totals(stack_text):
            violations.append(
                f"STACK_FORM: {TODO_STACK}:{lineno} a summary states a total of '{phrase}' and "
                f"the stack holds {live}. A total is derived from the items, so prose can only "
                f"drift from it; drop the number or name the items: \"{sentence[:160]}\""
            )
        for lineno, field in fields:
            for span in re.findall(r"`([^`\n]*)`", field):
                if span.endswith("/"):
                    violations.append(
                        f"STACK_FORM: {TODO_STACK}:{lineno} declares `{span}` in its 'Writes:' "
                        "field. A bare directory cannot be compared against another item's "
                        "write set, so the item is mutually exclusive with everything that "
                        "touches the tree. Name the files, or a glob if the item genuinely "
                        "spans them."
                    )

    problem_path = root / PROBLEM_STACK
    if not problem_path.is_file():
        violations.append(
            f"STACK_FORM: {PROBLEM_STACK} is missing; the sweep is broken, not the tree"
        )
        return violations

    header, header_line, rows, fenced = None, 0, 0, False
    for lineno, raw in enumerate(problem_path.read_text(encoding="utf-8").splitlines(), 1):
        if raw.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        line = raw.strip()
        if not line.startswith("|"):
            header = None  # a blank line or a heading ends the table
            continue
        rows += 1
        count = _row_delimiters(line)
        if header is None:
            header, header_line = count, lineno
            continue
        if count != header:
            violations.append(
                f"STACK_FORM: {PROBLEM_STACK}:{lineno} has {count} cell delimiters against the "
                f"{header} its table declares at line {header_line}. Either a cell is missing, "
                "or a `|` inside a code span was left unescaped -- GFM splits cells before it "
                r"parses inline code, so write `\|` even inside backticks."
            )
    if not rows:
        violations.append(f"STACK_FORM: no table row found in {PROBLEM_STACK}; the sweep is broken")

    from scripts.release_gate import OPEN_HEADER, open_section_content

    open_content = open_section_content(problem_path.read_text(encoding="utf-8"))
    if open_content is None:
        violations.append(
            f"STACK_FORM: {PROBLEM_STACK} has no '## Open' section, so STEP 0a cannot say whether "
            "any problem is untriaged"
        )
    for lineno, line in open_content or []:
        if not _CANONICAL_OPEN_ROW.match(line):
            violations.append(
                f"STACK_FORM: {PROBLEM_STACK}:{lineno} under '## Open' is neither the "
                f"'{' | '.join(OPEN_HEADER)}' header, its separator, nor a row whose first cell "
                f"is a bare P-<n>: {line[:80]!r}. Write the problem as a row of that table."
            )

    # The generation closure is a file that points at other files, so it goes stale without
    # erroring: a generator that is renamed or a derived path that moves leaves a declaration
    # that still reads as true. Resolve every entry against disk rather than trusting it.
    if not GENERATED_FROM:
        violations.append(
            "STACK_FORM: GENERATED_FROM is empty, so the generation closure declares nothing "
            "and this check passes vacuously"
        )
    for entry in GENERATED_FROM:
        generator = root / entry["generator"]
        if not generator.is_file():
            violations.append(
                f"STACK_FORM: GENERATED_FROM names {entry['generator']} as the generator of "
                f"{entry['derived']}, and no such file exists. A closure that points at a "
                "missing generator cannot tell an integrator what to regenerate."
            )
        derived = root / entry["derived"]
        if entry["tracked"] and not derived.is_file():
            violations.append(
                f"STACK_FORM: GENERATED_FROM declares {entry['derived']} tracked and derived, "
                f"and it is not in the tree. Either it was retired and the entry is stale, or "
                "it was lost."
            )
        for source in entry["sources"]:
            if source.startswith("<"):
                continue  # a described trigger, e.g. a HEAD move, not a path
            if not (root / source).exists():
                violations.append(
                    f"STACK_FORM: GENERATED_FROM says {entry['derived']} derives from "
                    f"{source}, which is not in the tree, so the closure is describing a "
                    "dependency that no longer exists."
                )
    return violations
