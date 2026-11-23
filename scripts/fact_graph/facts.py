"""Fact stack reader: the owned tables, the constants and the B3 exceptions."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from scripts.stack_parse import cells as _cells
from scripts.fact_graph._base import B3_EXCEPTIONS_HEADER, B3_EXCEPTIONS_HEADING, CONSTANTS_HEADING, CONSTANT_HEADER, FACT_HEADER, FACT_TABLES, FactSourceError, _BACKTICKED
from scripts.fact_graph._sources import read_source

# ------------------------------------------------------------------------ owned tables


def _all_tables(text: str) -> List[Tuple[str, List[str], List[List[str]]]]:
    """Every markdown table of ``text`` as (section heading, header cells, body rows)."""
    found = []
    heading = ""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            heading = line[3:].strip()
        if line.lstrip().startswith("|"):
            header = _cells(line)
            rows: List[List[str]] = []
            i += 2  # the header and its separator
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            found.append((heading, header, rows))
            continue
        i += 1
    return found


def _fact_like(header: Sequence[str]) -> bool:
    return bool(header) and (header[0].strip("`") == "ID" or "Held by" in header
                             or "Predicate" in header)


def _fact_region(text: str) -> List[str]:
    """The section headings from the first fact table's heading up to ``Constants``."""
    headings = [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]
    start = next((i for i, h in enumerate(headings) if h in FACT_TABLES), None)
    if start is None:
        return []
    end = next((i for i in range(start, len(headings)) if headings[i] == CONSTANTS_HEADING),
               len(headings))
    return headings[start:end]


def read_facts(text: str) -> List[Dict[str, Any]]:
    """The typed fact rows of ``text``: one dict per row, with its table and its holders.

    Raises ``FactSourceError`` on a fact-like header that is not the fact header; on a section
    between the first fact table and ``Constants`` that is not one of ``FACT_TABLES``, or a
    table there whose header is not the fact header, whatever its header says; on a row of the
    wrong width; on an empty fact ID; and on a fact ID used twice.
    """
    region = _fact_region(text)
    strays = [h for h in region if h not in FACT_TABLES]
    if strays:
        raise FactSourceError(f"sections {strays} sit among the fact tables and are not one of "
                              f"{list(FACT_TABLES)}")
    facts: List[Dict[str, Any]] = []
    seen: Dict[str, str] = {}
    for table, header, rows in _all_tables(text):
        if tuple(header) != FACT_HEADER:
            if _fact_like(header) or table in region:
                raise FactSourceError(f"section {table!r}: the table header {header} is not "
                                      f"the fact header {list(FACT_HEADER)}")
            continue
        for row in rows:
            if len(row) != len(FACT_HEADER):
                raise FactSourceError(f"{table}: a fact row has {len(row)} cells, not "
                                      f"{len(FACT_HEADER)}: {row}")
            fact_id, domain, predicate, held_by, ruled = row
            fact_id = fact_id.strip("`").strip()
            if not fact_id:
                raise FactSourceError(f"{table}: a fact row has an empty ID: {row}")
            if fact_id in seen:
                raise FactSourceError(f"fact {fact_id} appears in {seen[fact_id]} and {table}")
            seen[fact_id] = table
            facts.append({
                "id": fact_id,
                "table": table,
                "domain": domain,
                "predicate": predicate,
                "held_by": held_by,
                "holders": _BACKTICKED.findall(held_by),
                "ruled": ruled,
            })
    return facts


def require_tables(text: str) -> None:
    """The fact tables of ``text`` are exactly ``FACT_TABLES``, each once."""
    names = [table for table, header, _ in _all_tables(text) if tuple(header) == FACT_HEADER]
    if sorted(names) != sorted(FACT_TABLES):
        raise FactSourceError(f"the fact tables are {names}, not exactly {list(FACT_TABLES)}")


def load_facts(path: Path) -> List[Dict[str, Any]]:
    """The facts of ``path``, refused unless it holds the six tables and parses cleanly."""
    text = path.read_text(encoding="utf-8")
    facts = read_facts(text)
    require_tables(text)
    return facts


def read_constants(text: str) -> Dict[str, List[str]]:
    """The constant rows of ``text``: name -> its backticked values, in the order written."""
    constants: Dict[str, List[str]] = {}
    for _, header, rows in _all_tables(text):
        if tuple(header) != CONSTANT_HEADER:
            continue
        for row in rows:
            constants[row[0].strip("`")] = _BACKTICKED.findall(row[1])
    return constants


def read_b3_exceptions(text: str) -> List[Dict[str, str]]:
    """The rows of the ``## B3 exceptions`` table of ``text``, one dict per row with its five
    cells. Raises ``FactSourceError`` when the section is absent, holds more than one table,
    or its header is not the exceptions header: a skipped or malformed table would drop rows
    without a word."""
    tables = [(header, rows) for heading, header, rows in _all_tables(text)
              if heading == B3_EXCEPTIONS_HEADING]
    if len(tables) != 1:
        raise FactSourceError(f"the fact source holds {len(tables)} {B3_EXCEPTIONS_HEADING} "
                              "sections, not exactly one")
    header, rows = tables[0]
    if tuple(header) != B3_EXCEPTIONS_HEADER:
        raise FactSourceError(f"{B3_EXCEPTIONS_HEADING}: the table header {header} is not "
                              f"{list(B3_EXCEPTIONS_HEADER)}")
    for row in rows:
        if len(row) != len(B3_EXCEPTIONS_HEADER):
            raise FactSourceError(f"{B3_EXCEPTIONS_HEADING}: a row has {len(row)} cells, not "
                                  f"{len(B3_EXCEPTIONS_HEADER)}: {row}")
    entries = [dict(zip(B3_EXCEPTIONS_HEADER, row)) for row in rows]
    for entry in entries:
        # The table backticks names, as every table of the fact stack does.
        entry["Operation"] = entry["Operation"].strip("`")
        entry["Parameter"] = entry["Parameter"].strip("`")
    return entries


#: A backticked line cite of an Evidence cell: ``path:N`` or ``path:N-M``, or the continuation
#: ``:N`` / ``:N-M``, which takes the path of the last ``path:`` cite before it in the cell.
_CITE = re.compile(r"([\w./-]+\.\w+)?:(\d+)(?:-(\d+))?")


def _literal_forms(default: str) -> List[str]:
    """The spellings of a Default cell in source: a string literal in either quote style,
    anything else as written."""
    try:
        value = ast.literal_eval(default)
    except (ValueError, SyntaxError):
        return [default]
    return [f"'{value}'", f'"{value}"'] if isinstance(value, str) else [default]


def b3_exception_cites(text: str, root: Path) -> Tuple[int, List[str]]:
    """(cites examined, findings) for the line cites of the ``## B3 exceptions`` Evidence cells.

    A ``path:N`` or ``path:N-M`` cite holds when one line of ``N..M`` (``N`` alone without a
    range) of ``root/path`` carries both the row's parameter name and its default literal,
    each as a whole token. Every such cite of a row is checked on its own, so one stale cite
    among several makes the row a finding. A continuation cite ``:N`` cites the body that
    carries the row's reason, where the default need not appear; it holds when its lines exist
    in the file of the cite before it. A missing file, a line past the end, a range that runs
    backwards, or a continuation with no path before it is a finding.
    """
    examined, found = 0, []
    for row in read_b3_exceptions(text):
        param = row["Parameter"]
        forms = _literal_forms(row["Default"].strip("`"))
        name = re.compile(rf"(?<!\w){re.escape(param)}(?!\w)")
        literal = re.compile("|".join(rf"(?<![\w.]){re.escape(f)}(?![\w.])" for f in forms))
        path, lines = None, None
        for span in _BACKTICKED.findall(row["Evidence"]):
            match = _CITE.fullmatch(span)
            if not match:
                continue
            examined += 1
            where = f"{row['Operation']} {param}: `{span}`"
            if match.group(1):
                path = match.group(1)
                file = root / path
                lines = read_source(file).splitlines() if file.is_file() else None
                if lines is None:
                    found.append(f"{where} names no file")
                    continue
            elif path is None:
                found.append(f"{where} continues no path cite")
                continue
            if lines is None:
                continue  # the path cite it continues names no file, already a finding
            first = int(match.group(2))
            last = int(match.group(3) or first)
            if not 1 <= first <= last <= len(lines):
                found.append(f"{where} cites lines past {len(lines)} or runs backwards")
                continue
            if match.group(1) and not any(name.search(line) and literal.search(line)
                                          for line in lines[first - 1:last]):
                found.append(f"{where} holds no line with {param} and the default "
                             f"{row['Default']}")
    return examined, found
