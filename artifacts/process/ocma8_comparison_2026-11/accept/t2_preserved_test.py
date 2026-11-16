"""PRESERVED: table-row behaviour of six jnwb scripts at baseline ac995dd, each read at its own entry point.
Run: cwd = tree under test; python -m pytest <abs path to this file> -q -p no:cacheprovider --basetemp=<dir outside the tree>
"""
import sys
from pathlib import Path

import pytest

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_dashboard  # noqa: E402
import build_fact_graph  # noqa: E402
import docs_form_gate  # noqa: E402
import learning_gate  # noqa: E402
import reconstruct_state  # noqa: E402
import release_gate  # noqa: E402
from build_fact_graph import FactSourceError  # noqa: E402

SCRIPTS = (build_dashboard, build_fact_graph, docs_form_gate, learning_gate,
           reconstruct_state, release_gate)
METHOD_HEADER = ("Reference", "Result implemented", "Functions")


def _write(tmp_path, text, name="fixture.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_scripts_load_from_the_tree_under_test():
    for module in SCRIPTS:
        assert Path(module.__file__).resolve().parent == (ROOT / "scripts").resolve(), module.__name__


# build_dashboard: the roadmap reader, whose table splitter honours escaped pipes.
ROADMAP_HEAD = "| ID | Theme | Defect | Waits | Release |\n|---|---|---|---|---|\n"
DASH_ROW = "| 01-1 | Tuning (validation) | defect text | waits on fixture | deferred-0.3.0 |"


def test_dashboard_deferred_row_keeps_its_last_cell(tmp_path, monkeypatch):
    monkeypatch.setattr(build_dashboard, "ROADMAP", _write(tmp_path, ROADMAP_HEAD + DASH_ROW + "\n"))
    assert DASH_ROW.count("|") == 6  # fixture: five cells
    assert build_dashboard.deferred_section() == [{
        "id": "01-1", "theme": "Tuning", "defect": "defect text", "waits": "waits on fixture",
        "release": "deferred-0.3.0", "label": "not started"}]


def test_dashboard_row_with_trailing_empty_cell_has_six_cells(tmp_path, monkeypatch):
    row = DASH_ROW + "  |"
    monkeypatch.setattr(build_dashboard, "ROADMAP", _write(tmp_path, ROADMAP_HEAD + row + "\n"))
    assert row.count("|") == 7  # fixture: six cells, the last one empty
    assert build_dashboard.deferred_section() == []


def test_dashboard_malformed_roadmap_lines_are_left_out(tmp_path, monkeypatch):
    text = ROADMAP_HEAD + (
        "01-2 | Tuning (validation) | defect text | waits on fixture | deferred-0.3.0 |\n"  # no leading pipe
        "| 01-3 | Tuning (validation) | defect text | deferred-0.3.0 |\n"  # four cells
        "| 01-4 | Tuning (validation) | defect text | waits on fixture | deferred-0.3.0 |\n")
    monkeypatch.setattr(build_dashboard, "ROADMAP", _write(tmp_path, text))
    assert [row["id"] for row in build_dashboard.deferred_section()] == ["01-4"]


ESCAPED_ROW = r"| 01-5 | Tuning \| part (validation) | defect \| text | waits on fixture | deferred-0.3.0 |"


def test_dashboard_escaped_pipe_does_not_split_a_cell(tmp_path, monkeypatch):
    monkeypatch.setattr(build_dashboard, "ROADMAP", _write(tmp_path, ROADMAP_HEAD + ESCAPED_ROW + "\n"))
    assert ESCAPED_ROW.count(r"\|") == 2  # fixture: two escaped pipes
    rows = build_dashboard.deferred_section()
    assert len(rows) == 1, f"escaped pipe split the row: {rows}"
    row = rows[0]
    assert (row["id"], row["waits"], row["release"]) == ("01-5", "waits on fixture", "deferred-0.3.0")
    assert row["theme"] in (r"Tuning \| part", "Tuning | part"), row["theme"]
    assert row["defect"] in (r"defect \| text", "defect | text"), row["defect"]


REFERENCES_TEXT = (
    "# References\n\n"
    "| Reference | Result implemented | Functions |\n"
    "|---|---|---|\n"
    "| Smith 2001 [paper](https://doi.org/10.1000/x1) | Result A | `fn_a` |\n"
    "| Jones 2002 (no link) | Result B | `fn_b` |\n"
    "\nPitfalls prose.\n")


def test_dashboard_references_rows_and_their_urls(tmp_path, monkeypatch):
    monkeypatch.setattr(build_dashboard, "REFERENCES", _write(tmp_path, REFERENCES_TEXT, "references.md"))
    assert build_dashboard.references_section() == [
        {"text": "Smith 2001 [paper](https://doi.org/10.1000/x1)", "url": "https://doi.org/10.1000/x1"},
        {"text": "Jones 2002 (no link)", "url": None}]


# build_fact_graph: the table readers and the reference-row reader.
FACT_HEAD = "| ID | Domain | Predicate | Held by | Ruled |\n|---|---|---|---|---|\n"
FACT_ROW = "| `F1` | boundary | the rule holds | `mod.a`, `mod.b` | 2026-01-02 |"


def _facts(*rows):
    return "## Boundary\n\n" + FACT_HEAD + "".join(row + "\n" for row in rows)


def _methods(*rows):
    return ("## Methods\n\n| Reference | Result implemented | Functions |\n|---|---|---|\n"
            + "".join(row + "\n" for row in rows))


def test_fact_row_keeps_its_last_cell():
    assert FACT_ROW.count("|") == 6  # fixture: five cells
    assert build_fact_graph.read_facts(_facts(FACT_ROW)) == [{
        "id": "F1", "table": "Boundary", "domain": "boundary", "predicate": "the rule holds",
        "held_by": "`mod.a`, `mod.b`", "holders": ["mod.a", "mod.b"], "ruled": "2026-01-02"}]


def test_constants_keep_the_values_cell():
    text = ("## Constants\n\n| Constant | Values | Ruled |\n|---|---|---|\n"
            "| `N_BINS` | `8`, `16` | 2026-01-02 |\n")
    assert build_fact_graph.read_constants(text) == {"N_BINS": ["8", "16"]}


def test_fact_row_with_trailing_empty_cell_has_six_cells():
    with pytest.raises(FactSourceError, match=r"a fact row has 6 cells, not 5"):
        build_fact_graph.read_facts(_facts(FACT_ROW + "  |"))


def test_fact_row_with_too_few_cells_is_refused():
    with pytest.raises(FactSourceError, match=r"a fact row has 4 cells, not 5"):
        build_fact_graph.read_facts(_facts("| `F1` | boundary | the rule holds | `mod.a` |"))


def test_fact_row_without_leading_pipe_ends_the_table_unread():
    text = _facts(FACT_ROW, "F2 | boundary | not a row | `mod.b` | 2026-01-03")
    assert [fact["id"] for fact in build_fact_graph.read_facts(text)] == ["F1"]


def test_reference_row_keeps_its_functions_cell():
    text = _methods("| [Smith 2001](https://doi.org/10.1000/x1) | Result A | `fn_a`, `fn_b` |")
    assert build_fact_graph.reference_table_rows(text) == [(
        METHOD_HEADER, "Methods", "[Smith 2001](https://doi.org/10.1000/x1)", "Result A", "`fn_a`, `fn_b`")]


def test_reference_row_with_trailing_empty_cell_is_refused():
    with pytest.raises(AssertionError, match=r"does not have three cells"):
        build_fact_graph.reference_table_rows(_methods("| [Smith 2001](u) | Result A | `fn_a` |  |"))


def test_reference_rows_skip_lines_that_are_not_rows():
    text = _methods("Ref | Result A | `fn_a`", "|---|---|---|", "| [Smith 2001](u) | Result A | `fn_a` |")
    assert [row[2] for row in build_fact_graph.reference_table_rows(text)] == ["[Smith 2001](u)"]


def test_reference_row_with_too_few_cells_is_refused():
    with pytest.raises(AssertionError, match=r"does not have three cells"):
        build_fact_graph.reference_table_rows(_methods("| [Smith 2001](u) | Result A |"))


# learning_gate: the defect-ledger reader.
LEDGER_HEAD = "| Class | Seen | Instances |\n|---|---|---|\n"


def test_ledger_row_keeps_its_instances_cell():
    assert learning_gate.ledger_rows(LEDGER_HEAD + "| cls:alpha | 3 | a; b; c |\n") == [("cls", 3, 3)]


def test_ledger_row_with_too_few_cells_and_non_numeric_seen_are_left_out():
    text = LEDGER_HEAD + "| cls:alpha | 3 | a; b; c |\n| cls:gamma | 2 |\n| cls:beta | x | none |\n"
    assert learning_gate.ledger_rows(text) == [("cls", 3, 3)]


# release_gate: the roadmap-row reader and the open-stack table reader.
RM_ROW = "| 01-1 | Theme one | defect one | waits on one | deferred-90.0.0 |"


def test_roadmap_row_keeps_its_release_cell():
    assert release_gate.roadmap_rows(ROADMAP_HEAD + RM_ROW + "\n") == ([("01-1", "deferred-90.0.0")], [])


def test_roadmap_row_with_trailing_empty_cell_is_refused():
    rows, refused = release_gate.roadmap_rows(ROADMAP_HEAD + RM_ROW + "  |\n")
    assert rows == []
    assert len(refused) == 1 and "is not a readable row" in refused[0], refused


def test_roadmap_malformed_lines_are_refused_or_skipped():
    text = ROADMAP_HEAD + ("01-3 | Theme | defect | waits | deferred-90.0.0\n"
                           "| 01-4 | Theme | defect | deferred-90.0.0 |\n")
    rows, refused = release_gate.roadmap_rows(text)
    assert rows == []
    assert len(refused) == 2, refused
    assert "is id-shaped outside the table" in refused[0], refused[0]
    assert "is not a readable row" in refused[1], refused[1]


def test_open_stack_row_keeps_a_last_cell_that_is_not_a_rule():
    text = "| ID | Note |\n|---|---|\n| - | none yet |\n| P-1 | open |\n"
    assert release_gate.table_data_rows(text) == [(3, "| - | none yet |"), (4, "| P-1 | open |")]


def test_one_column_table_has_a_header_and_a_rule():
    assert release_gate.table_data_rows("| Item |\n|---|\n| x |\n") == [(3, "| x |")]


def test_blockquoted_table_rows_are_table_rows():
    assert release_gate.table_data_rows("> | ID | Note |\n> |---|---|\n> | 01 | x |\n") == [(3, "> | 01 | x |")]


def test_prose_with_pipes_is_not_a_table_row():
    text = ("Some prose | with a pipe\n| ID | Note |\n|---|---|\n| 01 | x |\n| 02 |\n"
            "prose after | table\n")
    assert release_gate.table_data_rows(text) == [(4, "| 01 | x |"), (5, "| 02 |")]


# docs_form_gate: the vocabulary table, read by its own inline split.
VOC_HEAD = "# Contract\n\n## Vocabulary\n\n| Concept | Preferred | Superseded |\n|---|---|---|\n"


def _vocab(text):
    return [(row.concept, row.preferred, row.superseded) for row in docs_form_gate.parse_vocabulary(text)]


def test_vocabulary_row_keeps_its_superseded_cell():
    assert _vocab(VOC_HEAD + "| normalisation | `normalize` | `normalise` |\n| spike | `spike` | `spk` |\n") == [
        ("normalisation", ("normalize",), ("normalise",)), ("spike", ("spike",), ("spk",))]


def test_vocabulary_row_with_trailing_empty_cell_has_four_cells():
    assert _vocab(VOC_HEAD + "| spike | `spike` | `spk` |  |\n") == []


def test_vocabulary_malformed_rows_are_left_out():
    text = VOC_HEAD + ("| normalisation | `normalize` | `normalise` |\n"
                       "spike | `spike` | `spk`\n"  # no leading pipe
                       "| spike | `spike` |\n")  # two cells
    assert _vocab(text) == [("normalisation", ("normalize",), ("normalise",))]


# reconstruct_state: the defect-class ledger, read by its own inline split.
DEFECT_HEAD = "| Class | Seen | a | b | c | Status |\n|---|---|---|---|---|---|\n"


def _defect_file(tmp_path, *rows):
    return _write(tmp_path, DEFECT_HEAD + "".join(row + "\n" for row in rows), "defect_classes.md")


def test_defect_row_keeps_its_status_cell(tmp_path):
    path = _defect_file(tmp_path, "| alpha:R1 | 3 | a | b | c | open |")
    assert reconstruct_state.open_defect_classes(path) == "alpha (seen 3)"


def test_closed_defect_row_is_left_out(tmp_path):
    path = _defect_file(tmp_path, "| alpha:R1 | 3 | a | b | c | open |",
                        "| beta:R2 | 2 | a | b | c | repaired 2026-11-01 |")
    assert reconstruct_state.open_defect_classes(path) == "alpha (seen 3)"


def test_defect_row_with_trailing_empty_cell_reads_that_cell_as_status(tmp_path):
    path = _defect_file(tmp_path, "| gamma:R3 | 1 | a | b | c | repaired |  |")
    assert reconstruct_state.open_defect_classes(path) == "gamma (seen 1)"


def test_defect_rows_with_too_few_cells_are_left_out(tmp_path):
    path = _defect_file(tmp_path, "| eps:R5 | 4 | a | repaired |", "| zeta:R6 | 5 | a | b | open |")
    assert reconstruct_state.open_defect_classes(path) == "none"


# Added 2026-11-15 (T2 coverage): preserved behaviour that the 31 tests above did not reach.
# Strip-convention readers and the slice-convention dashboard, at their entry points.

DASH_OPEN = "| 01-1 | Tuning (validation) | defect text | waits on fixture | deferred-0.3.0"
DASH_DOUBLE = DASH_ROW + "|"


def test_dashboard_deferred_row_without_trailing_pipe_is_left_out(tmp_path, monkeypatch):
    monkeypatch.setattr(build_dashboard, "ROADMAP", _write(tmp_path, ROADMAP_HEAD + DASH_OPEN + "\n"))
    assert DASH_OPEN.count("|") == 5  # fixture: five cells, no trailing pipe
    assert build_dashboard.deferred_section() == []


def test_dashboard_deferred_row_ending_double_pipe_is_left_out(tmp_path, monkeypatch):
    monkeypatch.setattr(build_dashboard, "ROADMAP", _write(tmp_path, ROADMAP_HEAD + DASH_DOUBLE + "\n"))
    assert DASH_DOUBLE.endswith("||")  # fixture: no space between the last two pipes
    assert build_dashboard.deferred_section() == []


ORDER_HEAD = ("### `jnwb.fx`\n\n| spec | parameter | sizes | median times (ms) | exp | r2 | t-span "
              "| achieved | admissible | cls | gap |\n|---|---|---|---|---|---|---|---|---|---|---|\n")
ORDER_ROW = "| `fx.f` | `n` | 8, 16 | 1.5, 3.0 | 1.02 | 0.99 | 8-16 | O(n) | O(n) | A | 0 |"
ORDER_OPEN = "| `fx.f` | `n` | 8, 16 | 1.5, 3.0 | 1.02 | 0.99 | 8-16 | O(n) | O(n) | A | 0"
ORDER_DOUBLE = ORDER_ROW + "|"


def _order(monkeypatch, tmp_path, row):
    monkeypatch.setattr(build_dashboard, "ORDER_RECORD",
                        _write(tmp_path, ORDER_HEAD + row + "\n", "computational_order.md"))
    return build_dashboard.order_section()


def test_dashboard_order_row_keeps_its_cells(tmp_path, monkeypatch):
    assert ORDER_ROW.count("|") == 12  # fixture: eleven cells
    assert _order(monkeypatch, tmp_path, ORDER_ROW) == [{
        "export": "fx.f", "order": "O(n)", "evidence": "`n`: exponent 1.02, admissible O(n)",
        "module": "jnwb.fx"}]


def test_dashboard_order_row_without_trailing_pipe_is_refused(tmp_path, monkeypatch):
    assert ORDER_OPEN.count("|") == 11  # fixture: eleven cells, no trailing pipe
    with pytest.raises(ValueError, match=r"a row has 10 cells, not 11"):
        _order(monkeypatch, tmp_path, ORDER_OPEN)


def test_dashboard_order_row_ending_double_pipe_is_refused(tmp_path, monkeypatch):
    assert ORDER_DOUBLE.endswith("||")  # fixture: no space between the last two pipes
    with pytest.raises(ValueError, match=r"a row has 12 cells, not 11"):
        _order(monkeypatch, tmp_path, ORDER_DOUBLE)


STUDY_HEAD = "# References\n\n| Reference | Result reproduced | Receipt |\n|---|---|---|\n"
STUDY_ROW = "| Smith 2001 | Result A | `tests/test_a.py::test_one`"


def _studies(monkeypatch, tmp_path, row):
    """The studies cards of validations_section(); the other card builders are held to nothing."""
    monkeypatch.setattr(build_dashboard, "REFERENCES",
                        _write(tmp_path, STUDY_HEAD + row + "\n", "references.md"))
    monkeypatch.setattr(build_dashboard, "_receipt", lambda path, card: path.name)
    monkeypatch.setattr(build_dashboard, "_git", lambda *args: "a" * 40)
    monkeypatch.setattr(build_dashboard, "CALIBRATION_RECEIPTS", ())
    monkeypatch.setattr(build_dashboard, "_performance_cards", lambda: [])
    monkeypatch.setattr(build_dashboard, "_frozen_card", lambda: {"id": "frozen"})
    monkeypatch.setattr(build_dashboard, "_closure_card", lambda: {"id": "closure"})
    monkeypatch.setattr(build_dashboard, "VALIDATION_HTML", tmp_path / "no_html")
    cards = build_dashboard.validations_section()
    return [(card["id"], card["title"], card["fields"])
            for card in cards if card["id"].startswith("studies-")]


def test_dashboard_studies_row_keeps_its_receipt_cell(tmp_path, monkeypatch):
    assert (STUDY_ROW + " |").count("|") == 4  # fixture: three cells
    assert _studies(monkeypatch, tmp_path, STUDY_ROW + " |") == [(
        "studies-1", "Smith 2001", {"result": "Result A", "tests": ["test_a.py::test_one"]})]


def test_dashboard_studies_row_without_trailing_pipe_is_refused(tmp_path, monkeypatch):
    assert STUDY_ROW.count("|") == 3  # fixture: three cells, no trailing pipe
    with pytest.raises(ValueError, match=r"a studies row has 2 cells, not 3"):
        _studies(monkeypatch, tmp_path, STUDY_ROW)


def test_dashboard_studies_row_ending_double_pipe_is_refused(tmp_path, monkeypatch):
    assert (STUDY_ROW + " ||").endswith("||")  # fixture: no space between the last two pipes
    with pytest.raises(ValueError, match=r"a studies row has 4 cells, not 3"):
        _studies(monkeypatch, tmp_path, STUDY_ROW + " ||")


MAPPING_PREAMBLE = "Old file: `docs/old.md` at `abc1234`\nDraft: `docs/draft.md`\n\n"
MAPPING_BODY = "|---|---|\n| `a` | `b` |\n"


def _mapping_tables(tmp_path, header):
    (tmp_path / "artifacts").mkdir()
    _write(tmp_path / "artifacts", MAPPING_PREAMBLE + header + "\n" + MAPPING_BODY, "x.md")
    return learning_gate.mapping_tables(tmp_path)


def test_mapping_table_with_old_location_and_where_now_is_found(tmp_path):
    assert _mapping_tables(tmp_path, "| Old location | Where now |") == [(
        "artifacts/x.md", "abc1234", "docs/old.md", "docs/draft.md")]


def test_mapping_header_without_where_now_is_refused(tmp_path):
    header = "| Old location | Where |"
    assert "Where now" not in header  # fixture: the header lacks its second name
    assert _mapping_tables(tmp_path, header) == []


def test_mapping_header_without_trailing_pipe_is_found(tmp_path):
    assert _mapping_tables(tmp_path, "| Old location | Where now") == [(
        "artifacts/x.md", "abc1234", "docs/old.md", "docs/draft.md")]


FACT_OPEN = "| `F1` | boundary | the rule holds | `mod.a`, `mod.b` | 2026-01-02"
FACT_DOUBLE = FACT_ROW + "|"
FACT_F1 = {"id": "F1", "table": "Boundary", "domain": "boundary", "predicate": "the rule holds",
           "held_by": "`mod.a`, `mod.b`", "holders": ["mod.a", "mod.b"], "ruled": "2026-01-02"}


def test_fact_row_without_trailing_pipe_keeps_its_last_cell():
    assert FACT_OPEN.count("|") == 5  # fixture: five cells, no trailing pipe
    assert build_fact_graph.read_facts(_facts(FACT_OPEN)) == [FACT_F1]


def test_fact_row_ending_double_pipe_keeps_its_last_cell():
    assert FACT_DOUBLE.endswith("||")  # fixture: no space between the last two pipes
    assert build_fact_graph.read_facts(_facts(FACT_DOUBLE)) == [FACT_F1]


REF_ROW = "| [Smith 2001](https://doi.org/10.1000/x1) | Result A | `fn_a`"
REF_ENTRY = (METHOD_HEADER, "Methods", "[Smith 2001](https://doi.org/10.1000/x1)", "Result A", "`fn_a`")


def test_reference_row_without_trailing_pipe_keeps_its_functions_cell():
    assert REF_ROW.count("|") == 3  # fixture: three cells, no trailing pipe
    assert build_fact_graph.reference_table_rows(_methods(REF_ROW)) == [REF_ENTRY]


def test_reference_row_ending_double_pipe_keeps_its_functions_cell():
    assert (REF_ROW + " ||").endswith("||")  # fixture: no space between the last two pipes
    assert build_fact_graph.reference_table_rows(_methods(REF_ROW + " ||")) == [REF_ENTRY]


LEDGER_OPEN = "| cls:alpha | 3 | a; b; c"


def test_ledger_row_without_trailing_pipe_keeps_its_instances_cell():
    assert LEDGER_OPEN.count("|") == 3  # fixture: three cells, no trailing pipe
    assert learning_gate.ledger_rows(LEDGER_HEAD + LEDGER_OPEN + "\n") == [("cls", 3, 3)]


def test_ledger_row_ending_double_pipe_keeps_its_instances_cell():
    assert (LEDGER_OPEN + " ||").endswith("||")  # fixture: no space between the last two pipes
    assert learning_gate.ledger_rows(LEDGER_HEAD + LEDGER_OPEN + " ||\n") == [("cls", 3, 3)]


RM_OPEN = "| 01-1 | Theme one | defect one | waits on one | deferred-90.0.0"


def test_roadmap_row_without_trailing_pipe_keeps_its_release_cell():
    assert RM_OPEN.count("|") == 5  # fixture: five cells, no trailing pipe
    assert release_gate.roadmap_rows(ROADMAP_HEAD + RM_OPEN + "\n") == ([("01-1", "deferred-90.0.0")], [])


def test_roadmap_row_ending_double_pipe_keeps_its_release_cell():
    assert (RM_ROW + "|").endswith("||")  # fixture: no space between the last two pipes
    assert release_gate.roadmap_rows(ROADMAP_HEAD + RM_ROW + "|\n") == ([("01-1", "deferred-90.0.0")], [])


def test_table_row_without_trailing_pipe_is_a_data_row():
    text = "| ID | Note |\n|---|---|\n| P-1 | open\n"
    assert text.splitlines()[2].count("|") == 2  # fixture: two cells, no trailing pipe
    assert release_gate.table_data_rows(text) == [(3, "| P-1 | open")]


def test_table_row_ending_double_pipe_is_a_data_row():
    text = "| ID | Note |\n|---|---|\n| P-1 | open ||\n"
    assert text.splitlines()[2].endswith("||")  # fixture: no space between the last two pipes
    assert release_gate.table_data_rows(text) == [(3, "| P-1 | open ||")]


VOC_OPEN = "| spike | `spike` | `spk`"


def test_vocabulary_row_without_trailing_pipe_keeps_its_superseded_cell():
    assert VOC_OPEN.count("|") == 3  # fixture: three cells, no trailing pipe
    assert _vocab(VOC_HEAD + VOC_OPEN + "\n") == [("spike", ("spike",), ("spk",))]


def test_vocabulary_row_ending_double_pipe_keeps_its_superseded_cell():
    assert (VOC_OPEN + " ||").endswith("||")  # fixture: no space between the last two pipes
    assert _vocab(VOC_HEAD + VOC_OPEN + " ||\n") == [("spike", ("spike",), ("spk",))]


def test_defect_row_without_trailing_pipe_keeps_its_status_cell(tmp_path):
    path = _defect_file(tmp_path, "| alpha:R1 | 3 | a | b | c | open")
    assert reconstruct_state.open_defect_classes(path) == "alpha (seen 3)"


def test_defect_row_ending_double_pipe_keeps_its_status_cell(tmp_path):
    path = _defect_file(tmp_path, "| beta:R2 | 2 | a | b | c | repaired ||")
    assert path.read_text(encoding="utf-8").endswith("repaired ||\n")  # fixture: a closed status
    assert reconstruct_state.open_defect_classes(path) == "none"
