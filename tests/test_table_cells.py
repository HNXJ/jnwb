"""One Markdown table-cell splitter: ``scripts/stack_parse.py`` ``cells``.

An escaped pipe (``\\|``) belongs to its cell. Before the shared splitter, four table readers split
every pipe, so a cell holding a literal pipe read as two cells there; only the dashboard's reader
honoured the escape.
"""

from scripts import build_fact_graph, stack_parse


def test_outer_pipes_are_optional_and_dropped():
    assert stack_parse.cells("| a | b |") == ["a", "b"]
    assert stack_parse.cells("a | b |") == ["a", "b"]
    assert stack_parse.cells("| a | b") == ["a", "b"]


def test_empty_cells_are_kept():
    assert stack_parse.cells("|  |  |") == ["", ""]
    assert stack_parse.cells("| a || b |") == ["a", "", "b"]


def test_escaped_pipe_stays_in_its_cell_raw():
    row = "| a \\| b | c |"
    assert "\\|" in row, "fixture must hold an escaped pipe"
    assert stack_parse.cells(row) == ["a \\| b", "c"]


def test_escaped_pipe_at_the_end_of_a_row():
    assert stack_parse.cells("| a \\| | c |") == ["a \\|", "c"]
    assert stack_parse.cells("| a \\|") == ["a \\|"]


def test_a_table_reader_keeps_an_escaped_pipe_in_its_cell():
    text = "## Facts\n\n| ID | Claim |\n|---|---|\n| F1 | a \\| b |\n"
    assert "\\|" in text, "fixture must hold an escaped pipe"
    assert build_fact_graph._all_tables(text) == [("Facts", ["ID", "Claim"], [["F1", "a \\| b"]])]
