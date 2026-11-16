"""The one markdown table-row splitter. A pipe preceded by a backslash does not split a cell.

By default a row's outer pipes are removed. ``keep_outer=True`` keeps them, so the first and last
segments are the ones outside the row. Which lines are rows stays with each reader.
"""

import re


def split_cells(line: str, *, keep_outer: bool = False) -> list[str]:
    """The stripped cells of ``line``, split on its unescaped pipes; an escaped pipe stays inside."""
    body = line if keep_outer else line.strip().strip("|")
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", body)]
