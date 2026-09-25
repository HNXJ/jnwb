"""Gate 15's two new readings of the todo stack: a truncated write set, and a false `none`.

Both defects are the same shape twice over -- **a check that passes for the wrong reason** --
and both were found inside checks written to catch that shape.

`Writes:` is bounded at a sentence. 06-67 split its field across a full stop, so the last two
entries were never read, and one was a genuine bare `tests/` -- the exact P-108 violation gate
15 exists to catch, sitting undetected inside the gate's own live zero (P-125). P-125 prescribed
replacing the boundary with a run of backtick tokens separated only by commas and whitespace.
**Measured against the live stack that rule is worse**: it reads fewer tokens in six fields and
more in none, because the fields legitimately interleave prose. So the boundary is kept and the
gate instead reports when the boundary may be in the wrong place.

`Blocked by:` is trusted by the scheduler. 06-31 said `none` while blocked on data-access
authority and was dispatched into a guaranteed stop twice; 06-86 said `none` while its body said
"Blocked on one ruling" (P-149, P-163). The metadata is confidently wrong rather than absent,
which is why every reader believes it.

The tests below drive both checks through broken states they construct, so a mutant that
disables either one is caught by a test that can see the difference.
"""

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # never insert(0): pyproject sets pythonpath = ["."]

from scripts.harness_gate import (  # noqa: E402
    _ANY_BLOCK_ASSERTION,
    _BLOCK_ASSERTIONS,
    _ITEM_ID,
    _blocked_by_none_contradictions,
    _miscounted_summaries,
    _stack_items,
    _stop_clause_spans,
    _suspected_truncated_writes,
    _unwrapped_sentences,
    _unwrapped_spans,
    _writes_field_spans,
    _writes_fields,
    check_stack_form_consistency,
)

TODO_STACK = ROOT / "artifacts" / "todo_stack.md"

# 06-67 exactly as the row records it: the field's last two entries sat past a full stop on the
# next physical line, and `tests/` among them is a real P-108 violation.
TRUNCATED = """\
### 06-67 Something

Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `jnwb/nwb_io.py`, `artifacts/goal.md`, AUTONOMY: none.
`docs/errors.md`, `tests/`.

Prose the item carries afterwards.
"""

REPAIRED = """\
### 06-67 Something

Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `jnwb/nwb_io.py`, `artifacts/goal.md`, `docs/errors.md`, `tests/`.

Prose the item carries afterwards.
"""

# 06-86 before it was re-marked: the field says none, the body says blocked.
CONTRADICTED = """\
### 06-86 Something

Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/evidence/0.2.6/computational_order.md`.
Blocked on one ruling: does the inventory assert `O` or Theta? The answer decides whether six
of the eight rows are defects.
"""


class TestATruncatedWriteSetIsReported:
    def test_the_field_that_split_across_a_full_stop_is_flagged(self):
        assert _suspected_truncated_writes(TRUNCATED), (
            "06-67's field is followed immediately by two more paths and the check said "
            "nothing, so the gate is blind to the case P-125 recorded"
        )

    def test_the_repaired_one_line_form_is_not_flagged(self):
        assert _suspected_truncated_writes(REPAIRED) == [], (
            "the repaired field is a single sentence; flagging it would make the check fire "
            "on correct items, which teaches its reader to dismiss the output"
        )

    def test_a_field_followed_by_ordinary_prose_is_not_flagged(self):
        sample = (
            "### 06-95 Something\n\nWrites: `scripts/docs_form_gate.py` (new), "
            "`tests/test_docs_form_gate.py`.\nA contract nothing enforces decays.\n"
        )
        assert _suspected_truncated_writes(sample) == []

    def test_a_backticked_identifier_after_a_field_is_not_a_truncation(self):
        # Only path-shaped tokens look like a continued write set. A following sentence that
        # opens with a backticked function name is prose.
        sample = (
            "### 06-96 Something\n\nWrites: `jnwb/spectral.py`.\n"
            "`aggregate_to_db` ignores `how` when `aggregate_over` is None.\n"
        )
        assert _suspected_truncated_writes(sample) == []

    def test_the_sentence_rule_genuinely_cannot_see_the_truncated_entries(self):
        # The premise of the whole check. If the sentence rule already read `tests/`, the
        # tripwire would be solving a problem that does not exist.
        read = _writes_fields(TRUNCATED)[0][1]
        assert "tests/" not in read
        assert "docs/errors.md" not in read
        assert "jnwb/nwb_io.py" in read

    def test_the_live_stack_is_clean(self):
        flagged = _suspected_truncated_writes(TODO_STACK.read_text(encoding="utf-8"))
        assert flagged == [], f"a live write set is being truncated: {flagged}"

    def test_the_spans_helper_agrees_with_the_public_parser(self):
        # Both parsers must share one boundary rule. A second copy would drift, and the
        # truncation check reads the offset the shared scan returns.
        text = TODO_STACK.read_text(encoding="utf-8")
        assert _writes_fields(text) == [
            (lineno, field) for lineno, field, _end in _writes_field_spans(text)
        ]

    def test_the_end_offset_points_just_past_the_field(self):
        text = TRUNCATED
        _lineno, field, end = _writes_field_spans(text)[0]
        assert text[end - len(field):end] == field


class TestAFalseBlockedByNoneIsReported:
    def test_the_contradicted_item_is_flagged(self):
        flagged, _suppressed = _blocked_by_none_contradictions(CONTRADICTED)
        assert len(flagged) == 1, (
            "06-86 said `Blocked by: none` while its body said it was blocked, and the "
            "scheduler offered it as dispatchable -- P-149's shape"
        )
        assert flagged[0][1] == "06-86"

    def test_recording_the_block_in_the_field_clears_the_flag(self):
        repaired = CONTRADICTED.replace(
            "Blocked by: none.", "Blocked by: **a Hamm ruling on O versus Theta.**"
        )
        flagged, _suppressed = _blocked_by_none_contradictions(repaired)
        assert flagged == [], "recording the block is the repair; it must clear the finding"

    def test_the_field_declaration_alone_is_not_a_contradiction(self):
        # `Blocked by: none.` matches the phrase list on its own. A first draft flagged 33 of
        # 52 live items on nothing but their own metadata.
        sample = (
            "### 06-99 Something\n\nRole: jnwb-developer. Blocked by: none.\n"
            "Writes: `docs/index.md`.\nAn ordinary item with nothing blocking it.\n"
        )
        flagged, suppressed = _blocked_by_none_contradictions(sample)
        assert flagged == [] and suppressed == []

    def test_an_item_that_declares_a_block_is_not_scanned_at_all(self):
        declared = CONTRADICTED.replace("Blocked by: none.", "Blocked by: 06-31.")
        assert _blocked_by_none_contradictions(declared) == ([], [])

    def test_the_discharged_wording_does_not_flag(self):
        # P-163's coda: the sentence written to discharge 06-103's stale block first read
        # "this item is no longer blocked on it", which a phrase list scores as an assertion.
        # It was reworded rather than teaching the regex negation, and this pins that choice.
        sample = (
            "### 06-92 Something\n\nRole: jnwb-developer. Blocked by: none.\n"
            "Writes: `docs/errors.md`.\nThat block is discharged, and the item runs.\n"
        )
        flagged, _suppressed = _blocked_by_none_contradictions(sample)
        assert flagged == []

    def test_the_negated_form_is_deliberately_still_matched(self):
        # The converse of the test above, stated so the choice is visible rather than
        # incidental: the phrase list does NOT parse polarity, and is not meant to. A reader
        # who changes this must change the rewording convention with it.
        sample = (
            "### 06-93 Something\n\nRole: jnwb-developer. Blocked by: none.\n"
            "Writes: `docs/errors.md`.\nThis item is no longer blocked on it.\n"
        )
        flagged, _suppressed = _blocked_by_none_contradictions(sample)
        assert len(flagged) == 1, (
            "the phrase list is shallow on purpose; if it has learned to read negation, the "
            "'reword rather than teach the regex' convention in P-163 no longer applies"
        )

    def test_the_live_stack_is_clean(self):
        flagged, _suppressed = _blocked_by_none_contradictions(
            TODO_STACK.read_text(encoding="utf-8")
        )
        assert flagged == [], f"a live item contradicts its own Blocked by field: {flagged}"


class TestTheSuppressionsAreVisibleAndCorrect:
    def test_a_match_inside_a_stop_clause_is_suppressed_and_reported(self):
        sample = (
            "### 06-90 Something\n\nRole: jnwb-developer. Blocked by: none.\n"
            "Writes: `docs/index.md`.\n"
            "Stop: if the page turns out to be blocked on a ruling, stop and record it.\n"
        )
        flagged, suppressed = _blocked_by_none_contradictions(sample)
        assert flagged == []
        assert len(suppressed) == 1
        assert "Stop:" in suppressed[0][3]

    def test_a_stop_clause_covers_a_later_sentence_too(self):
        # 06-89 reads "Stop: ... resolved first. Then this waits on 06-77 ...", so the
        # assertion sits one sentence after the key. A draft keyed on the sentence missed it --
        # P-163's attempt-1 failure with "line" replaced by "sentence".
        sample = (
            "### 06-89 Something\n\nRole: docs-harness. Blocked by: none.\n"
            "Writes: `docs/index.md`.\n"
            "Stop: the composition depends on an index-space defect being resolved first. Then\n"
            "this waits on 06-31 and says so.\n"
        )
        flagged, suppressed = _blocked_by_none_contradictions(sample)
        assert flagged == []
        assert suppressed and "Stop:" in suppressed[0][3], (
            "the assertion is in the stop clause but a sentence after the key, and it was "
            "read as a live contradiction"
        )

    def test_a_stop_clause_ends_at_the_next_field_label(self):
        # Otherwise a Stop: anywhere in an item would suppress everything after it.
        flat, _spans = _unwrapped_spans(
            "Stop: something. Accept: the item closes. It is blocked on a ruling."
        )
        (start, end), = _stop_clause_spans(flat)
        assert flat[start:end].strip() == "Stop: something."
        assert "blocked on" not in flat[start:end]

    def test_an_assertion_after_a_closed_stop_clause_still_flags(self):
        sample = (
            "### 06-94 Something\n\nRole: jnwb-developer. Blocked by: none.\n"
            "Writes: `docs/index.md`.\n"
            "Stop: if the file is absent, stop.\n"
            "Accept: the page publishes.\n"
            "It is blocked on a ruling nobody has made.\n"
        )
        flagged, _suppressed = _blocked_by_none_contradictions(sample)
        assert len(flagged) == 1, (
            "the Stop: clause ended at `Accept:`, so the later assertion is live and must not "
            "be covered by the earlier suppression"
        )

    def test_a_match_naming_only_retired_items_is_suppressed_and_reported(self):
        sample = (
            "### 06-91 Something\n\nRole: jnwb-developer. Blocked by: none.\n"
            "Writes: `docs/agents.md`.\nThis was blocked by 06-9999 until that item landed.\n"
        )
        flagged, suppressed = _blocked_by_none_contradictions(sample)
        assert flagged == []
        assert len(suppressed) == 1
        assert "06-9999" in suppressed[0][3], "the reason must name what it suppressed"

    def test_naming_a_live_item_is_not_suppressed(self):
        # The discriminator for the suppression above: the same sentence naming an item that
        # still exists is a real contradiction.
        sample = (
            "### 06-91 Something\n\nRole: jnwb-developer. Blocked by: none.\n"
            "Writes: `docs/agents.md`.\nThis is blocked by 06-92 until that item lands.\n"
            "\n### 06-92 Another\n\nRole: jnwb-developer. Blocked by: 06-91.\n"
            "Writes: `docs/other.md`.\n"
        )
        flagged, _suppressed = _blocked_by_none_contradictions(sample)
        assert len(flagged) == 1
        assert flagged[0][2] == "This is blocked by 06-92 until that item lands."

    def test_a_second_field_declaration_is_not_read_as_prose(self):
        # Every `Blocked by:` declaration is excised, not only the first. A draft removed one
        # and a malformed item carrying two flagged itself on its own metadata.
        sample = (
            "### 06-93 Something\n\nRole: jnwb-developer. Blocked by: none.\n"
            "Writes: `docs/agents.md`. Blocked by: none.\nAn ordinary item.\n"
        )
        assert _blocked_by_none_contradictions(sample) == ([], [])

    def test_every_suppression_reason_is_a_nonempty_string(self):
        _flagged, suppressed = _blocked_by_none_contradictions(
            TODO_STACK.read_text(encoding="utf-8")
        )
        for _lineno, _item, _sentence, why in suppressed:
            assert why and why.strip(), "a suppression with no stated reason cannot be read"

    def test_the_gate_prints_a_suppression(self, tmp_path, capsys):
        # The narrowing must be visible in the gate's OWN output, not only through the helper.
        # P-125 silenced two "false positives" and one of them was real.
        #
        # Driven through a constructed tree rather than the live stack, because the live stack
        # currently suppresses nothing -- asserting against it would pass with the printing
        # deleted, which is the defect shape this whole file exists to catch.
        (tmp_path / "artifacts").mkdir()
        (tmp_path / "artifacts" / "todo_stack.md").write_text(
            "### 06-90 Something\n\nRole: jnwb-developer. Blocked by: none.\n"
            "Writes: `docs/index.md`.\n"
            "Stop: if the page turns out to be blocked on a ruling, stop and record it.\n",
            encoding="utf-8",
        )
        (tmp_path / "artifacts" / "problem_stack.md").write_text(
            "| ID | Problem | Disposition | Evidence |\n|---|---|---|---|\n"
            "| P-01 | a row | repaired | evidence |\n",
            encoding="utf-8",
        )
        violations = check_stack_form_consistency(repo_root=tmp_path)
        printed = capsys.readouterr().out
        assert printed.count("STACK_FORM note:") == 1, (
            "a suppressed assertion produced no note, so the narrowing is invisible"
        )
        assert "06-90" in printed and "Stop:" in printed
        assert not any("Blocked by: none" in v for v in violations), (
            "the suppressed case must not also be reported as a violation"
        )

    def test_the_gate_reports_a_contradiction_it_does_not_suppress(self, tmp_path):
        # The other direction, so the test above cannot pass by suppressing everything.
        (tmp_path / "artifacts").mkdir()
        (tmp_path / "artifacts" / "todo_stack.md").write_text(CONTRADICTED, encoding="utf-8")
        (tmp_path / "artifacts" / "problem_stack.md").write_text(
            "| ID | Problem | Disposition | Evidence |\n|---|---|---|---|\n"
            "| P-01 | a row | repaired | evidence |\n",
            encoding="utf-8",
        )
        violations = check_stack_form_consistency(repo_root=tmp_path)
        assert any("06-86" in v and "Blocked by: none" in v for v in violations), (
            f"the gate did not report the contradiction: {violations}"
        )


class TestASummaryCountAgreesWithWhatItNames:
    """P-133: a canonical summary inside the stack went stale and nothing errored.

    Batch 0 opened with "Six items wait on a human ruling ... 06-13, 06-18, 06-67, 06-84,
    06-85 and 06-92". Four waited; three of the six named had closed earlier the same day; and
    none of the four gated more than one item, so the sentence named a binding constraint that
    no longer bound. Every number in it is recomputable from the fields below it, so re-deriving
    it by hand is a fix with a shelf life.
    """

    # P-133's own sentence, as the row records it.
    STALE = (
        "## Batch 0. Goal and authority\n\n"
        "Six items wait on a human ruling: 06-13, 06-18, 06-67, 06-84 and 06-85.\n\n"
        "### 06-13 Something\n\nRole: human ruling. Blocked by: none.\nWrites: `docs/a.md`.\n"
    )

    def test_a_count_that_disagrees_with_its_list_is_flagged(self):
        flagged = _miscounted_summaries(self.STALE)
        assert len(flagged) == 1, f"the miscount was not seen: {flagged}"
        _lineno, phrase, asserted, ids, _sentence = flagged[0]
        assert asserted == 6 and len(ids) == 5, (phrase, asserted, ids)

    def test_a_count_that_agrees_is_not_flagged(self):
        agreeing = self.STALE.replace("Six items", "Five items")
        assert _miscounted_summaries(agreeing) == []

    def test_a_count_inside_an_item_body_is_not_a_summary(self):
        # A count inside an item is that item's statement about its own work; only prose ABOUT
        # items is derived data. Without this the check would read every item's Do: clause.
        inside = (
            "## Batch 0\n\n### 06-13 Something\n\nRole: jnwb-developer. Blocked by: none.\n"
            "Writes: `docs/a.md`.\nDo: reconcile six items -- 06-01, 06-02 -- by hand.\n"
        )
        assert _miscounted_summaries(inside) == []

    def test_a_count_with_no_ids_is_not_flagged(self):
        # A summary asserting a count without naming the items cannot be checked. Batch 0's
        # "three items Hamm must decide" was such a claim, and was two; it was rewritten to
        # name them rather than checked by a second mechanism.
        vague = (
            "## Batch 0\n\nWhat remains is three items Hamm must decide.\n\n"
            "### 06-13 A\n\nRole: human ruling. Blocked by: none.\nWrites: `docs/a.md`.\n"
        )
        assert _miscounted_summaries(vague) == []

    def test_ids_beyond_a_clause_break_belong_to_another_statement(self):
        # "it assigned 16 items to five lanes ... -- the compression lane pointed at 06-24 and
        # 06-51" is not a miscount. A first draft flagged it, and one like it, as 2 of 2 false
        # positives.
        other_clause = (
            "## Batch 0\n\nIt assigned 16 items to five lanes -- the compression lane "
            "pointed at 06-24 and 06-51.\n\n"
            "### 06-13 A\n\nRole: human ruling. Blocked by: none.\nWrites: `docs/a.md`.\n"
        )
        assert _miscounted_summaries(other_clause) == []

    def test_the_elided_form_is_counted(self):
        # "three more are blocked" carries the noun over from the preceding clause. Requiring
        # the literal word "items" missed the one live instance on the real stack.
        elided = (
            "## Batch 0\n\nTwo items are ruling items -- 06-13 and 06-67 -- and three more "
            "are blocked on authority: 06-31, 06-32, 06-86 and 06-99.\n\n"
            "### 06-13 A\n\nRole: human ruling. Blocked by: none.\nWrites: `docs/a.md`.\n"
        )
        flagged = _miscounted_summaries(elided)
        assert len(flagged) == 1, f"the elided count was not read: {flagged}"
        assert flagged[0][2] == 3 and len(flagged[0][3]) == 4

    def test_each_count_governs_only_its_own_list(self):
        # The sentence above carries two counts. The first is correct and must not absorb the
        # second's ids -- a draft that let it do so reported the correct count as a miscount.
        elided = (
            "## Batch 0\n\nTwo items are ruling items -- 06-13 and 06-67 -- and three more "
            "are blocked on authority: 06-31, 06-32 and 06-86.\n\n"
            "### 06-13 A\n\nRole: human ruling. Blocked by: none.\nWrites: `docs/a.md`.\n"
        )
        assert _miscounted_summaries(elided) == []

    def test_the_live_stack_agrees_with_itself(self):
        flagged = _miscounted_summaries(TODO_STACK.read_text(encoding="utf-8"))
        assert flagged == [], f"a live summary disagrees with the items it names: {flagged}"

    def test_the_gate_reports_a_miscount(self, tmp_path):
        (tmp_path / "artifacts").mkdir()
        (tmp_path / "artifacts" / "todo_stack.md").write_text(self.STALE, encoding="utf-8")
        (tmp_path / "artifacts" / "problem_stack.md").write_text(
            "| ID | Problem | Disposition | Evidence |\n|---|---|---|---|\n"
            "| P-01 | a row | repaired | evidence |\n",
            encoding="utf-8",
        )
        violations = check_stack_form_consistency(repo_root=tmp_path)
        assert any("a summary says" in v for v in violations), violations


class TestTheUnwrappingIsNotALineScan:
    def test_a_hard_wrapped_sentence_becomes_one_sentence(self):
        # A physical line is not a semantic unit in this file. The line-based first attempt
        # flagged 3 and suppressed 0 because both exclusion keys sat on the previous line.
        wrapped = "It is blocked on one\nthing only: what happens when\nthe caller says nothing."
        assert _unwrapped_sentences(wrapped) == [
            "It is blocked on one thing only: what happens when the caller says nothing."
        ]

    def test_a_full_stop_inside_a_code_span_does_not_split(self):
        assert _unwrapped_sentences("Writes: `docs/api.md` and nothing else.") == [
            "Writes: `docs/api.md` and nothing else."
        ]

    def test_spans_index_the_unwrapped_string(self):
        flat, spans = _unwrapped_spans("One thing. Two things.")
        assert [flat[a:b].strip() for a, b in spans] == ["One thing.", "Two things."]

    def test_no_span_is_empty(self):
        flat, spans = _unwrapped_spans("A. B.  \n\n  C.")
        assert all(flat[a:b].strip() for a, b in spans)


class TestTheHelpersReadTheRealStack:
    def test_an_item_id_is_read_in_any_cycle_and_a_date_is_not(self):
        assert _ITEM_ID.findall("ruled 2026-09-19; after 07-02 (06-40), not 2026-09-25") == [
            "07-02", "06-40"]

    def test_every_item_is_found(self):
        text = TODO_STACK.read_text(encoding="utf-8")
        items = _stack_items(text)
        assert len(items) == len(re.findall(r"^### \d{2}-\d+", text, re.MULTILINE))
        assert items, "the sweep found no item, which reads exactly like a clean stack"

    def test_item_ids_are_unique(self):
        ids = [item_id for _lineno, item_id, _body in
               _stack_items(TODO_STACK.read_text(encoding="utf-8"))]
        assert len(ids) == len(set(ids)), f"duplicate item id: {sorted(set(ids) ^ set(ids))}"

    def test_an_item_body_stops_at_the_next_item(self):
        _lineno, item_id, body = _stack_items(
            "### 06-01 A\n\nfirst body.\n\n### 06-02 B\n\nsecond body.\n"
        )[0]
        assert item_id == "06-01"
        assert "second body" not in body

    @pytest.mark.parametrize("phrase", _BLOCK_ASSERTIONS)
    def test_every_phrase_is_reachable_through_the_alternation(self, phrase):
        # A phrase shadowed by a shorter alternative would sit in the list looking effective.
        match = _ANY_BLOCK_ASSERTION.search(phrase)
        assert match and match.group(0) == phrase, (
            f"{phrase!r} is not matched whole; a shorter entry is shadowing it"
        )

    def test_the_gate_passes_on_the_live_tree(self):
        assert check_stack_form_consistency() == []
