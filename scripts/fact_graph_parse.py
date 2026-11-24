"""Parsers of the fact stack and the references page, read by ``scripts/build_fact_graph.py``.

Moved from that file without change; the driver re-exports the names the tests and
``scripts/fact_gate.py`` read.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple


FACT_HEADER = ("ID", "Domain", "Predicate", "Held by", "Ruled")
FACT_TABLES = ("Boundary", "Design", "Identity", "Science", "Skills", "Release")
CONSTANT_HEADER = ("Constant", "Values", "Ruled")
#: The exceptions table of fact B3, the one agent-editable part of the fact stack; it sits
#: after ``Constants`` and its rows excuse one defaulted choice parameter of one callable.
B3_EXCEPTIONS_HEADING = "B3 exceptions"
B3_EXCEPTIONS_HEADER = ("Operation", "Parameter", "Default", "Reason", "Evidence")
#: The section that ends the fact tables; every section between the first fact table and it
#: must be a fact table.
CONSTANTS_HEADING = "Constants"

_ADDRESS = re.compile(r" at 0x[0-9A-Fa-f]+")
_BACKTICKED = re.compile(r"`([^`]+)`")
_HEADING_LINE = re.compile(r"#{1,6}[ \t]")
_LINE_SPAN = re.compile(r"`([^`\n]+)`")
_ROUTING_LINE = re.compile(r"^- `jnwb\.")
_ROW_HEAD_END = re.compile(r"`:\s")
_JNWB_NAME = re.compile(r"^jnwb\.([A-Za-z_][\w.]*)")
_IDENTIFIER = re.compile(r"^[A-Za-z_]\w*$")
_PARENTHESISED = re.compile(r"\([^)]*\)")


class FactSourceError(ValueError):
    """The fact source is malformed; nothing built from it could be trusted."""


# ------------------------------------------------------------------------ owned tables


def _cells(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


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


# ------------------------------------------------------------------------ references page


#: A method table's functions implement the row's result; a pitfall table's are those its
#: pitfall concerns. A core-text table's are the functions that follow the book. A reproduction
#: table's third cell is its receipt, so only the method and pitfall tables enter the graph. No
#: other table header is allowed, so a new form cannot escape either check.
#: ``tests/test_references_resolve.py`` imports this parser, so one parser exists.
METHOD_HEADER = ("Reference", "Result implemented", "Functions")
PITFALL_HEADER = ("Reference", "Pitfall stated", "Functions it concerns")
CORE_HEADER = ("Reference", "What jnwb follows from it", "Functions")
REPRODUCTION_HEADER = ("Reference", "Result reproduced", "Receipt")
#: The tables whose functions enter the fact graph.
FUNCTION_HEADERS = (METHOD_HEADER, PITFALL_HEADER)
#: A DOI link on the references page. The target may hold one level of balanced parentheses,
#: as Markdown allows and the SICI-style DOI of Torrence & Compo (1998) needs.
PAGE_LINK = re.compile(r"\[doi:([^\]]+)\]\(https://doi\.org/((?:[^()\s]|\([^()\s]*\))+)\)")


def normalize_doi(doi: str) -> str:
    """DOIs compare case-insensitively; a sentence may end right after one."""
    return doi.rstrip(".,").lower()


def reference_table_rows(text: str) -> List[Tuple[Tuple[str, ...], str, str, str, str]]:
    """``(header, section, reference, result, functions)`` for every body row of every
    references table, under the ``##`` heading each table sits under."""
    rows = []
    header = None
    section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0] == "Reference":
            header = tuple(cells)
            assert header in (*FUNCTION_HEADERS, CORE_HEADER, REPRODUCTION_HEADER), (
                f"unknown table header: {line}")
            continue
        assert len(cells) == 3, f"a references row does not have three cells: {line[:80]}"
        assert header is not None, f"a references row sits under no header: {line[:80]}"
        rows.append((header, section, cells[0], cells[1], cells[2]))
    return rows


def reference_rows(text: str, header: Optional[Tuple[str, ...]] = None
                   ) -> List[Tuple[str, str, str]]:
    """``(reference, result, functions)`` for the rows under ``header``, or, with none, for the
    method and pitfall rows: the tables whose third cell lists functions."""
    wanted = FUNCTION_HEADERS if header is None else (header,)
    return [(reference, result, functions)
            for under, _, reference, result, functions in reference_table_rows(text)
            if under in wanted]


def reference_row_doi(reference_cell: str) -> str:
    """The row's DOI, lowercased; the link text and the link target naming the same DOI is
    checked in ``tests/test_references_resolve.py``."""
    links = PAGE_LINK.findall(reference_cell)
    assert len(links) == 1, f"a row must carry exactly one DOI link: {reference_cell[:80]}"
    return normalize_doi(links[0][0])


def reference_functions(functions_cell: str) -> List[str]:
    """Every backticked name of a Functions cell, in the order written."""
    return _BACKTICKED.findall(functions_cell)


def read_references(text: str) -> Tuple[Dict[str, Dict[str, Any]], List[List[str]],
                                        List[List[str]]]:
    """The references page as (reference entities, ``cites`` edges, ``concerns`` edges).

    Each method row cites its DOI from every function its Functions cell lists; each pitfall
    row concerns it instead. A DOI named twice keeps its first section and merges the
    functions of both rows, in the order written.
    """
    references: Dict[str, Dict[str, Any]] = {}
    cited, concerned = set(), set()
    for header, section, reference, _, functions in reference_table_rows(text):
        if header not in FUNCTION_HEADERS:
            continue  # a core text or a reproduction names no graph edge
        doi = reference_row_doi(reference)
        names = reference_functions(functions)
        entry = references.setdefault(doi, {"section": section, "functions": []})
        entry["functions"].extend(n for n in names if n not in entry["functions"])
        edges = cited if header == METHOD_HEADER else concerned
        edges.update((name, doi) for name in names)
    return (references, [list(pair) for pair in sorted(cited)],
            [list(pair) for pair in sorted(concerned)])
