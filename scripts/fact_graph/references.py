"""References page reader: the method, pitfall and reproduction tables."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from scripts.stack_parse import cells as _cells
from scripts.fact_graph._base import REPO_ROOT, _BACKTICKED

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
        cells = _cells(line)
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


def routed_citation_exclusions(root: Path = REPO_ROOT) -> set:
    """The exclusion-list names: every non-blank line of the recorded list that is not its ``#``
    header (``artifacts/evidence/0.2.14/routed_citation_exclusions.txt``)."""
    path = root / "artifacts" / "evidence" / "0.2.14" / "routed_citation_exclusions.txt"
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")}


def uncited_routed_heads(graph: Dict[str, Any]) -> List[str]:
    """The distinct routed exports with no ``cites`` edge, in sorted order: each routing target
    that is a public function (export kind function/class) and uncited, reduced to the head of
    its dotted path. A class is cited through any of its methods."""
    exports = graph["entities"].get("export", {})
    targets = graph["entities"].get("route_target", {})
    cited = {name for name, _ in graph["relations"].get("cites", [])}
    cited |= {name.split(".")[0] for name in cited if "." in name}
    return sorted({target.split(".")[0] for target in targets
                   if exports.get(targets[target].get("export"), {}).get("kind")
                   in ("function", "class")
                   and target not in cited})
