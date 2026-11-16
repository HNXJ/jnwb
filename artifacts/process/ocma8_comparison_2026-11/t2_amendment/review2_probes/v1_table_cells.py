"""Table-row cell readers; an escaped pipe does not split a cell."""

import re

_PIPE = re.compile(r"(?<!\\)\|")


def padded_cells(line):
    """Cells of a row whose outer pipes are stripped."""
    return [cell.strip() for cell in _PIPE.split(line.strip().strip("|"))]


def inner_cells(line):
    """Cells between the first and last unescaped pipe of the line as given."""
    return [cell.strip() for cell in _PIPE.split(line)[1:-1]]
