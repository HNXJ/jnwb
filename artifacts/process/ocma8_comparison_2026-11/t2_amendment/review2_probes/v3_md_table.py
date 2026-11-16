"""Cell splitter for markdown table rows (escaped pipes stay in the cell)."""

import re


def cells(line, outer=False):
    pieces = re.split(r"(?<!\\)\|", line if outer else line.strip().strip("|"))
    if outer:
        pieces = pieces[1:-1]
    return [piece.strip() for piece in pieces]
