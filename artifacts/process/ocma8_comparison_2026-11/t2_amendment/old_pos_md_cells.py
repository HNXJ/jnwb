"""Throwaway control: the one markdown row splitter, escaped pipes kept inside a cell."""

import re


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:-1]]
