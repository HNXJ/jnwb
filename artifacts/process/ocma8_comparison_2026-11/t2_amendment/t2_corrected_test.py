"""CORRECTED table-row behaviour: an escaped pipe inside a cell must not change the rows or cells read.

One test per legacy site, through the public entry point that calls it. The escaped cell may keep
its backslash or not; the other cells must keep their values. Each test first asserts the reading
of the same row with no pipe, which the baseline already gives. Expected: FAIL on the baseline at
every site, PASS on a tree whose readers honour escaped pipes. Run as in t2_preserved_test.py.
"""
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_fact_graph  # noqa: E402
import docs_form_gate  # noqa: E402
import learning_gate  # noqa: E402
import reconstruct_state  # noqa: E402
import release_gate  # noqa: E402

METHOD_HEADER = ("Reference", "Result implemented", "Functions")


def test_build_fact_graph_fact_row_with_escaped_pipe_is_one_fact():
    # build_fact_graph: the table reader read_facts (its site at the module's table splitter).
    head = "## Boundary\n\n| ID | Domain | Predicate | Held by | Ruled |\n|---|---|---|---|---|\n"
    with_pipe = head + r"| `F9` | boundary | the value \| other holds | `mod.a` | 2026-01-02 |" + "\n"
    without = head + "| `F9` | boundary | the value or other holds | `mod.a` | 2026-01-02 |\n"
    assert r"\|" in with_pipe  # fixture holds an escaped pipe
    assert len(build_fact_graph.read_facts(without)) == 1
    facts = build_fact_graph.read_facts(with_pipe)
    assert len(facts) == 1, facts
    fact = facts[0]
    assert fact["predicate"] in (r"the value \| other holds", "the value | other holds"), fact["predicate"]
    assert (fact["id"], fact["domain"], fact["held_by"], fact["holders"], fact["ruled"]) == (
        "F9", "boundary", "`mod.a`", ["mod.a"], "2026-01-02")


def test_build_fact_graph_reference_row_with_escaped_pipe_has_three_cells():
    # build_fact_graph: the reference-row reader reference_table_rows (its inline split).
    head = "## Methods\n\n| Reference | Result implemented | Functions |\n|---|---|---|\n"
    with_pipe = head + r"| [Smith 2001](https://doi.org/10.1000/x1) | A \| B | `fn_a` |" + "\n"
    without = head + "| [Smith 2001](https://doi.org/10.1000/x1) | A or B | `fn_a` |\n"
    assert r"\|" in with_pipe
    assert len(build_fact_graph.reference_table_rows(without)) == 1
    rows = build_fact_graph.reference_table_rows(with_pipe)
    assert len(rows) == 1, rows
    header, section, reference, result, functions = rows[0]
    assert (header, section, reference, functions) == (
        METHOD_HEADER, "Methods", "[Smith 2001](https://doi.org/10.1000/x1)", "`fn_a`")
    assert result in (r"A \| B", "A | B"), result


def test_learning_gate_ledger_row_with_escaped_pipe_counts_the_same_instances():
    # learning_gate: the ledger reader ledger_rows.
    head = "| Class | Seen | Instances |\n|---|---|---|\n"
    with_pipe = head + r"| cls:alpha | 2 | a \| b; c |" + "\n"
    without = head + "| cls:alpha | 2 | a - b; c |\n"
    assert r"\|" in with_pipe
    assert learning_gate.ledger_rows(without) == [("cls", 2, 2)]
    assert learning_gate.ledger_rows(with_pipe) == [("cls", 2, 2)]


def test_release_gate_roadmap_row_with_escaped_pipe_is_one_row():
    # release_gate: the roadmap-row reader roadmap_rows (its site at the module's cell reader).
    head = "| ID | Theme | Defect | Waits | Release |\n|---|---|---|---|---|\n"
    with_pipe = head + r"| 01-5 | Theme \| part | defect one | waits on one | deferred-90.0.0 |" + "\n"
    without = head + "| 01-5 | Theme or part | defect one | waits on one | deferred-90.0.0 |\n"
    assert r"\|" in with_pipe
    assert release_gate.roadmap_rows(without) == ([("01-5", "deferred-90.0.0")], [])
    assert release_gate.roadmap_rows(with_pipe) == ([("01-5", "deferred-90.0.0")], [])


def test_docs_form_gate_vocabulary_row_with_escaped_pipe_keeps_three_cells():
    # docs_form_gate: the vocabulary reader parse_vocabulary (its inline split).
    head = "## Vocabulary\n\n| Concept | Preferred | Superseded |\n|---|---|---|\n"
    with_pipe = head + r"| normalisation | `normalize` | `normalise` \| `normalised` |" + "\n"
    without = head + "| normalisation | `normalize` | `normalise` / `normalised` |\n"
    assert r"\|" in with_pipe
    expected = [("normalisation", ("normalize",), ("normalise", "normalised"))]
    assert [(r.concept, r.preferred, r.superseded) for r in docs_form_gate.parse_vocabulary(without)] == expected
    assert [(r.concept, r.preferred, r.superseded) for r in docs_form_gate.parse_vocabulary(with_pipe)] == expected


def test_reconstruct_state_defect_row_with_escaped_pipe_in_status_is_closed(tmp_path):
    # reconstruct_state: the defect-class reader open_defect_classes (its inline split).
    head = "| Class | Seen | a | b | c | Status |\n|---|---|---|---|---|---|\n"
    without = tmp_path / "without.md"
    without.write_text(head + "| alpha:R1 | 3 | a | b | c | repaired see note |\n", encoding="utf-8")
    with_pipe = tmp_path / "with_pipe.md"
    with_pipe.write_text(head + r"| alpha:R1 | 3 | a | b | c | repaired \| see note |" + "\n", encoding="utf-8")
    assert r"\|" in with_pipe.read_text(encoding="utf-8")  # fixture holds an escaped pipe
    assert reconstruct_state.open_defect_classes(without) == "none"
    assert reconstruct_state.open_defect_classes(with_pipe) == "none"
