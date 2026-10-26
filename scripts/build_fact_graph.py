#!/usr/bin/env python3
"""Build the fact graph: a generated graph of what the tree holds and how it connects.

Entities come from the tree itself:

  export  every name in ``jnwb.__all__``, with its kind, its signature and the execution
          switches it takes (the parameter names ``scripts/computational_contract_gate.py``
          decides, read from there)
  skipped_export  each export that is neither a class nor a function, which the callable scans
          do not examine
  page    every hand-written ``docs/**/*.md`` page (the generated ``docs/api.md`` is left out,
          as harness gate 5 leaves it out)
  skill   every ``skills/*/SKILL.md``
  route_target  every name a skill routes to, with the export its path starts from and whether
          the whole dotted path resolves on the package (``StatisticalAnalysis.fdr_correct``)
  test    every ``tests/test_*.py`` file and the test functions it defines
  gate    every entry of ``scripts/harness_gate.py`` ``GATES``, by number
  python  every tracked ``*.py`` file of the repository (``git ls-files``)
  prose   every tracked text file outside ``PROSE_EXEMPT``: ``*.md``, ``*.py`` (read for its
          comments and docstrings), ``*.ipynb`` (markdown cells and code-cell comments), ``*.txt``,
          ``*.yml`` and ``*.yaml``, and every file under ``skills/`` or ``.github/`` (``_prose_files``)
  skill_file  every tracked ``SKILL.md`` under ``skills/``
  fact    every typed row of ``artifacts/fact_stack.md``, with the holders its ``Held by``
          cell names
  reference  every DOI of the method and pitfall tables of ``docs/references.md``, with the
          section it sits under and the functions its row lists

Relations, each a sorted list of ``[source, target]`` pairs:

  implements  module file -> export it defines
  documents   page -> export it names as a whole word in a heading or a code span; prose alone
              documents nothing
  routes      skill -> target it routes. Two forms are read: a routing bullet (a line opening
              ``- `jnwb.``) routes every backticked ``jnwb.`` call in its head, before the
              "`: " that ends it, and a call after that colon is a mention; and a table whose
              header cell names a backticked ``jnwb.`` path routes the leading backticked name
              of each cell in that column, under that path (a parenthesised name is a member of
              the module before it, not a route). A route written in any other form is not seen.
  verifies    test file -> export it reaches: ``from jnwb... import NAME``, or ``NAME`` read as
              an attribute of an imported ``jnwb`` module
  cites      function -> the DOI of the method row listing it (one per backticked name in the
              row's Functions cell)
  concerns   function -> the DOI of the pitfall row naming it, the same way
  constrains  holder -> fact it holds
  global_seeds  file -> a call that seeds NumPy's or the standard library's global random state
              (``global_seed_calls``), in every tracked file
  rng_parameters  file -> a function in ``jnwb/`` or ``scripts/`` that draws from a random module
              and takes no parameter named ``rng`` (``rng_violations``)
  db_averages  file -> an average in ``jnwb/`` of a dB conversion, or of a name a dB conversion
              was assigned to in the same function (``db_average_violations``; the lexicon is the
              ``dB log forms`` and ``dB averaging forms`` constants of the fact stack)
  immunity_vocabulary  file -> a sentence of ``prose`` that holds a value of the ``immunity
              vocabulary`` constant or of ``IMMUNITY_PATTERNS`` beside a term of
              ``IMMUNITY_CONTEXT``, unless a negation (``NEGATIONS``) precedes the value in its
              clause (``immunity_scan``, ``immunity_violations``)
  skill_contracts  skill file -> a sentence, read across the lines of its paragraph, that names a
              manifest or receipt, or a plural of one, beside a ``CONTRACT_TERMS`` term, unless it
              names a ``CONTRACT_CARRIERS`` word and says the contract is carried by or extends it
              (``skill_contract_violations``)
  silent_handlers  file -> an except handler in ``jnwb/`` that swallows its exception: its body
              raises, warns, or logs a warning, error or exception, calls a function of its
              module or of a relative import (``from .x import``, ``from ..x import``) whose own
              body does, or reads the bound exception name (``silent_handler_violations``);
              a handler whose (file, function) is in ``S9_EXCUSED`` is skipped, and a listed
              key that matches no flagged handler is reported as stale
  permutation_schemes  callable -> a public callable that draws a null (a permutation, shuffle,
              circular shift, surrogate, derangement or sign flip) and names no scheme key in its
              result (``scheme_scan``, ``SCHEME_KEYS``); a callable in ``S10_EXCUSED`` is skipped
  rng_reports  callable -> a public callable that consumes randomness (a call to one of the
              ``RESOLVERS`` of ``jnwb/_rng.py``) and names no rng key in
              its result (``rng_scan``, ``RNG_KEYS``); a callable in ``S11_EXCUSED`` is skipped
              (bare arrays and tuples carry no key)
  unit_conversions  callable -> a public callable that scales a parameter by a unit factor
              (``UNIT_FACTORS``, by multiplication or division) without naming the unit:
              neither the parameter's suffix (``UNIT_SUFFIXES``) nor a ``units``/``unit`` or
              ``*_unit``/``*_units`` parameter (``unit_scan``); a callable in ``I2_UNIT_EXCUSED``
              is skipped, and a listed key that matches no flagged callable is reported as stale
  wrapper_defaults  callable -> a public callable that calls another public callable with a
              literal keyword its own signature does not name, differing from that keyword's
              default (``wrapper_scan``); a callable in ``I2_WRAPPER_EXCUSED`` is skipped, and
              a listed key that matches no flagged callable is reported as stale
  choice_defaults  callable -> a public callable (an inherited public method and a callable
              export that is no function included, ``_unwalked_callables``; the latter is
              reported as not checked) with a defaulted parameter whose name is in
              the ``B3 choice names`` constant of the fact stack, unless the parameter is a
              ``window`` whose default is a string (a taper name, outside the lexicon) or a
              row of the ``## B3 exceptions`` table of the fact stack names the callable, by
              ``module.qualname`` or bare qualname, and the parameter
              (``choice_default_scan``, with ``read_b3_exceptions`` reading the table); a
              callable whose signature cannot be read is a finding, never a pass, and a row
              that matches no defaulted lexicon parameter is reported as stale
  signature_types  callable -> a public callable taking a signal parameter (``SIGNAL_PARAMETERS``)
              that declares no input class, declares one its parameters do not show, carries a
              stale declarations key, or calls a declared callable whose class is not a subset
              of its own, directly or through private helpers of its package
              (``signature_types_scan``, read from ``jnwb/_declarations.py``);
              a callable whose source cannot be read is a finding, never a pass
  claim_class_labels  file -> a figure label, or a ``unit=`` literal of a call whose callee's
              name ends in ``Result`` in ``jnwb/``, that names a magnitude or direction
              estimand and holds a term of a higher claim class -- a delay unit (in a label,
              a compound unit anywhere and a plain one inside parentheses or brackets;
              anywhere in a unit literal) or a delay word,
              or an inference word read after the method name "Granger causality" is removed
              (``claim_class_scan``, reading the claim table of ``docs/architecture.md``);
              a short label name whose estimator is in neither row is stale
  boundary_units  call site -> a call in ``jnwb/`` whose callee is a function or method defined
              in ``jnwb/`` and whose bare-name argument reaches a parameter of a different unit
              or base suffix (``UNIT_SUFFIXES``, ``BASE_SUFFIXES``), by keyword or position
              (``boundary_unit_scan``); a call on a line an ``INTENTIONAL BREAK`` comment
              holds, or in the statement block such a comment opens, is excused and counted
              apart
  owned_rules  file -> a registered signature expression of ``OWNED_RULES`` outside its owner,
              in ``jnwb/``, ``docs/``, ``examples/`` and the skills' python fences
              (``owned_rule_scans``); a reviewed exemption is not a site
  figure_owner_calls  file -> the same sites, read in the docs figure generator and the
              plotting modules (``FIGURE_FILES``, ``FIGURE_TREES``)

The facts are the only owned part; everything else is regenerated. The output is a pure
function of the tree: sorted keys and lists, LF endings, no timestamp, and object addresses
stripped from signatures, so two builds at one commit are byte-identical.

The fact stack must hold exactly the six fact tables ruled on 2026-09-29, each once, with no
repeated fact ID; a table whose header looks like a fact table but is not exactly one is
refused, because a skipped table would drop its facts without a word.

Usage::

    python scripts/build_fact_graph.py            # write artifacts/fact_graph.json
    python scripts/build_fact_graph.py --out PATH
"""
from __future__ import annotations

import argparse
import ast
import inspect
import io
import json
import os
import re
import subprocess
import sys
import textwrap
import tokenize
import types
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
# Under JNWB_EXPECTED_PACKAGE_ROOT the checkout goes last, for `scripts`, behind the named copy.
if os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
    if str(REPO_ROOT) not in sys.path:
        sys.path.append(str(REPO_ROOT))
elif str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.computational_contract_gate import (  # noqa: E402
    EXECUTION_PARAMETERS,
    _dataclass_field,
)
# Which resolver calls make a parameter stochastic is defined once, beside the resolvers,
# and read by the rng-parameter walk and by this scan alike; the reachability wrapper below
# is shared with the S10 scan.
from jnwb._rng import RESOLVERS  # noqa: E402
# The declared signal types of fact I1, read by the signature-types scan.
from jnwb import _declarations  # noqa: E402

FACT_GRAPH_PATH = REPO_ROOT / "artifacts" / "fact_graph.json"
FACT_STACK = REPO_ROOT / "artifacts" / "fact_stack.md"
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


def routed_citation_exclusions(root: Path = REPO_ROOT) -> set:
    """The exclusion-list names: every non-blank line of the ruled list that is not its ``#``
    header. The list is ruled in ``artifacts/rulings/2026-10-13.md`` (row "Uncited routed
    exports")."""
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


# ------------------------------------------------------------------------ source scans

#: The global random state's seed, under the dotted names NumPy and the standard library export.
GLOBAL_SEEDS = ("numpy.random.seed", "random.seed")
#: Calls into the random modules that draw nothing and create no stream.
RNG_BOOKKEEPING = ("numpy.random.SeedSequence", "numpy.random.Generator",
                   "numpy.random.BitGenerator")
RNG_PARAMETER = "rng"
#: The keyword of an rng-like seed (scikit-learn's spelling). A draw seeded by it, or by a
#: parameter annotated ``SeedSequence`` (a worker's child of the caller's rng), needs no ``rng``.
RNG_LIKE_PARAMETER = "random_state"
SEED_SEQUENCE_ANNOTATION = "SeedSequence"
#: The trees whose functions take an ``rng`` parameter when they draw from a random module.
#: ``scripts/`` is outside the rule (ruled 2026-10-20).
SCANNED_FOR_RNG = ("jnwb/",)
#: The package whose averages of dB values the dB rule reads.
DB_PACKAGE = "jnwb/"
#: The context that makes a vocabulary word a claim about volume conduction or reference.
IMMUNITY_CONTEXT = (r"volume[- ]conduction", r"reference", r"zero-lag", r"zero-phase",
                    r"field spread", r"common[- ]average",
                    r"reference[- ](?:contamination|induced|electrode)", r"re-?referenc\w*",
                    r"shared[- ]reference", r"zero[- ]lag (?:leakage|mixing)")
#: The immunity vocabulary beyond the fact stack's ``immunity vocabulary`` constant.
IMMUNITY_PATTERNS = (r"\bimmun(?:e|ity)\b", r"\binsensitive to\b", r"\brobust to\b",
                     r"\bunaffected by\b", r"\beliminat(?:e|es|ed|ing)\b",
                     r"\bcomplete(?:ly)? suppress(?:es|ed|ion)?\b", r"\bfree (?:of|from)\b")
#: The words that negate a vocabulary word when they precede it in the same clause.
NEGATIONS = ("not", "no", "never", "nor", "without")
#: Clause breaks: a colon, parenthesis, comma, semicolon or spaced dash.
CLAUSE_BREAKS = r"[,;:()]|\s[—-]\s"
#: "not only", "not just" and "not merely" are no negation.
NOT_MERELY = r"\bnot (?:only|just|merely)\b"
#: The text the immunity rule reads: every tracked file with one of these suffixes, and every
#: file under the ``PROSE_ANY`` trees, outside the ``PROSE_EXEMPT`` trees and files.
PROSE_SUFFIXES = (".md", ".py", ".ipynb", ".txt", ".yml", ".yaml")
PROSE_ANY = ("skills/", ".github/")
#: The trees (ending in ``/``) and files the immunity rule does not read. The two rule files are
#: exempt because their docstrings define the vocabulary and the context.
PROSE_EXEMPT = ("tests/", "artifacts/", "scripts/build_fact_graph.py", "scripts/fact_gate.py")
#: A list item (a bullet or a number) begins a sentence of its own.
LIST_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s")
#: The package whose comments, docstrings and except handlers the text rules read.
JNWB_PACKAGE = "jnwb/"
#: The skill-contract rule's terms. A sentence naming a carrier and saying the contract is
#: carried by or extends it is exempt.
MANIFEST_TERMS = ("manifest", "receipt")
CONTRACT_TERMS = (r"contract", r"schema", r"must write", r"must produce", r"required[- ]fields",
                  r"must (?:contain|include|list|record)\b.*\bfields")
CONTRACT_CARRIERS = ("inspect", "Result", "Provenance", "Lineage")
CARRY_WORDS = r"\b(?:extends?|extended|carried by|carries|via)\b"
#: The exceptions an optional dependency's absence raises; a handler for them alone is a fallback.
OPTIONAL_IMPORT_ERRORS = ("ImportError", "ModuleNotFoundError")
#: The logger methods that report a problem.
LOGGER_WARNINGS = ("warning", "error", "exception")
#: The except handlers the silent_handlers scan skips, by (module path, qualified function): the
#: probes and controls whose silence is the answer, each read by hand against its handler (fact S9).
#: A key that matches no flagged handler is reported as stale.
S9_EXCUSED: Dict[Tuple[str, str], str] = {
    ("jnwb/_backend.py", "_probe"): "backend probe: False when the backend will not load",
    ("jnwb/_backend.py", "jax_metal_available"): "backend probe: False when no Metal device",
    ("jnwb/_dictlike.py", "RenamedKeyDict.get"): "dict.get contract: the caller's default",
    ("jnwb/_dictlike.py", "DictAccessMixin.get"): "dict.get contract: the caller's default",
    ("jnwb/addressing.py", "enrich_units_dataframe._enrich"): "cache miss, computed next",
    ("jnwb/compression.py", "_repaired_reference"): "warns at the next line",
    ("jnwb/connectivity/_granger.py", "_adf_pvalue"): "reported as 'stationarity_not_tested'",
    ("jnwb/io.py", "_stored_seek_is_reliable"): "seek probe, same values either way",
    ("jnwb/jrsa/_backends.py", "_ensure_np"): "retry: np.asarray converts or raises",
    ("jnwb/jrsa/_result.py", "JRSAResult.__repr__"): "repr only",
    ("jnwb/jrsa/_stages.py", "_reduce_one"): "same number by percentile 50",
    ("jnwb/laminar/_xflip.py", "_window_rows"): "raise on the next line",
    ("jnwb/laminar/_xflip.py", "_homogeneous_factor"): "raise after the jitter loop",
    ("jnwb/laminar/_zflip.py", "_window_rows"): "raise on the next line",
    ("jnwb/mcp_server/nwb_tools.py", "_resolves"): "probe: no reader to name",
    ("jnwb/metadata.py", "_session_id_from_path"): "documented fallback to (raw, raw)",
    ("jnwb/nwb_validate.py", "_version"): "not installed",
    ("jnwb/nwb_write.py", "_spec_chain"): "a namespace without the type is the next namespace's turn",
    ("jnwb/nwb_write.py", "_declared_scalar"): "an undeclared attribute is not scalar; the repair refuses",
    ("jnwb/nwb_write.py", "_plan_vector_index_types.visit"): "an unreadable target is a dangling one, repointed",
    ("jnwb/vis/canvas.py", "_is_written"): "caller raises",
}


def _dotted(node: ast.AST) -> str:
    """The dotted spelling of a name or attribute chain, or ``""`` for any other expression."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))


def _final(node: ast.AST) -> str:
    """The last name of a spelling: ``mean`` for ``np.mean``."""
    return _dotted(node).rpartition(".")[2]


def _bindings(tree: ast.AST) -> Dict[str, str]:
    """Each name an import binds, mapped to the dotted path it stands for."""
    bound: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bound[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    bound[top] = top
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                bound[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return bound


def _target(node: ast.AST, bound: Dict[str, str]) -> str:
    """The dotted path a callee stands for, read through the module's own imports."""
    head, dot, rest = _dotted(node).partition(".")
    return bound.get(head, head) + dot + rest


def global_seed_calls(source: str) -> List[str]:
    """Each call that seeds the global random state, read through the module's own imports:
    ``np.random.seed``, ``random.seed``, and the same seed reached by an alias or a ``from``
    import. A seeded instance (``random.Random(0).seed``) is not the global state."""
    tree = ast.parse(source)
    bound = _bindings(tree)
    hits = sorted((node.lineno, _dotted(node.func)) for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and _target(node.func, bound) in GLOBAL_SEEDS)
    return [f"line {line}: {spelled}" for line, spelled in hits]


def _own_calls(fn: ast.AST):
    """The calls in a function's own statements, not in the functions and lambdas it defines."""
    pending = list(fn.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, ast.Call):
            yield node
        pending.extend(ast.iter_child_nodes(node))


def _parameters(fn: ast.AST) -> set:
    args = fn.args
    named = args.posonlyargs + args.args + args.kwonlyargs + [args.vararg, args.kwarg]
    return {arg.arg for arg in named if arg is not None}


def _draws(target: str) -> bool:
    """Whether a callee draws from, or constructs, a stream of NumPy's or the standard library's
    random module; bookkeeping such as ``SeedSequence`` does not."""
    return target.startswith(("numpy.random.", "random.")) and target not in RNG_BOOKKEEPING


def _seed_children(fn: ast.AST) -> set:
    """The parameters annotated ``SeedSequence``: a worker's seed, a child of the caller's rng."""
    args = fn.args
    named = args.posonlyargs + args.args + args.kwonlyargs
    return {arg.arg for arg in named
            if arg.annotation is not None and _final(arg.annotation) == SEED_SEQUENCE_ANNOTATION}


def _traces_to_caller(call: ast.Call, children: set) -> bool:
    """Whether a draw is seeded by a ``random_state`` or by a SeedSequence child of the caller."""
    seed = call.args[0] if call.args else next(
        (k.value for k in call.keywords if k.arg == "seed"), None)
    if isinstance(seed, ast.Attribute):
        return seed.attr == RNG_LIKE_PARAMETER
    return isinstance(seed, ast.Name) and (seed.id == RNG_LIKE_PARAMETER or seed.id in children)


def _workers_of_an_rng(tree: ast.AST) -> set:
    """The ids of the functions defined inside a function that takes ``rng``: workers whose own
    parameters carry seeds drawn from the caller's rng (ruled 2026-10-26)."""
    found = set()
    for outer in ast.walk(tree):
        if (isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef))
                and RNG_PARAMETER in _parameters(outer)):
            found.update(id(node) for node in ast.walk(outer) if node is not outer
                         and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
    return found


def rng_violations(source: str) -> List[str]:
    """Each function that draws from a random module and takes no parameter named ``rng``, unless
    every draw in it is seeded by a ``random_state``, by a SeedSequence child, or, in a worker
    defined inside a function that takes ``rng``, by one of the worker's own parameters. Code
    outside any function, such as a script's self-test, is not a function and is not read."""
    tree = ast.parse(source)
    bound = _bindings(tree)
    workers = _workers_of_an_rng(tree)
    found = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        draws = [call for call in _own_calls(fn) if _draws(_target(call.func, bound))]
        children = _seed_children(fn)
        if id(fn) in workers:
            children |= _parameters(fn)
        traced = all(_traces_to_caller(call, children) for call in draws)
        if draws and RNG_PARAMETER not in _parameters(fn) and not traced:
            found.append((fn.lineno, fn.name))
    return [f"line {line}: {name} draws without an rng parameter" for line, name in sorted(found)]


def _lexicon(forms: Sequence[str]) -> Tuple[set, set, set]:
    """The call names, the name suffixes and the sum numerators that a lexicon's forms name:
    ``10*log10`` names ``log10``, ``*_db`` names any name ending in ``_db``, ``sum / count``
    names the numerator ``sum``."""
    names, suffixes, numerators = set(), set(), set()
    for form in forms:
        if " / " in form:
            numerators.add(form.split(" / ")[0].strip())
        elif form.startswith("*"):
            suffixes.add(form[1:])
        else:
            names.add(form.split("*")[-1])
    return names, suffixes, numerators


def db_average_violations(source: str, constants: Dict[str, List[str]]) -> List[str]:
    """Each average in one module of a dB value: an averaging call, or a sum divided by a count,
    whose input is a dB conversion or holds a name assigned from one in the same function. A
    median of dB values is not an average, and an average taken before the log is not read here.
    The centre of a squared deviation, ``(x - mean(x)) ** 2``, is a log-space fit statistic and is
    not read either.
    """
    for key in ("dB log forms", "dB averaging forms"):
        if key not in constants:
            raise ValueError(f"the constants name no {key}")
    log_names, log_suffixes, _ = _lexicon(constants["dB log forms"])
    avg_names, _, numerators = _lexicon(constants["dB averaging forms"])
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def is_log(call: ast.Call) -> bool:
        name = _final(call.func)
        return name in log_names or any(name.endswith(suffix) for suffix in log_suffixes)

    def dB_valued(expr: ast.AST, tainted: set) -> bool:
        return any((isinstance(n, ast.Call) and is_log(n))
                   or (isinstance(n, ast.Name) and n.id in tainted) for n in ast.walk(expr))

    def averaged(node: ast.AST):
        """The inputs of an averaging node and its wording, or None."""
        if isinstance(node, ast.Call) and _final(node.func) in avg_names:
            inputs = list(node.args)
            if isinstance(node.func, ast.Attribute):
                inputs.append(node.func.value)  # the method form: ``x.mean()``
            return inputs, f"{_dotted(node.func)} over a dB value"
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                and isinstance(node.left, ast.Call) and _final(node.left.func) in numerators):
            return [node.left], f"{_dotted(node.left.func)} over a dB value divided by a count"
        return None

    def centres_a_squared_deviation(node: ast.AST) -> bool:
        """Whether an average is the centre of a squared deviation, ``(x - mean(x)) ** 2``: the
        total sum of squares of a fit statistic computed in log space, which the rule exempts."""
        sub = parents.get(node)
        power = parents.get(sub)
        return (isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Sub)
                and isinstance(power, ast.BinOp) and isinstance(power.op, ast.Pow)
                and isinstance(power.right, ast.Constant) and power.right.value == 2)

    def named_dB(fn: ast.AST) -> set:
        """The names a function assigns a dB value, to a fixpoint through other such names."""
        tainted: set = set()
        assigns = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)]
        grew = True
        while grew:
            grew = False
            for assign in assigns:
                if not dB_valued(assign.value, tainted):
                    continue
                for target in assign.targets:
                    for name in ast.walk(target):
                        if isinstance(name, ast.Name) and name.id not in tainted:
                            tainted.add(name.id)
                            grew = True
        return tainted

    scopes = [(tree, set())] + [(fn, named_dB(fn)) for fn in ast.walk(tree)
                                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))]
    found = set()
    for scope, tainted in scopes:
        for node in ast.walk(scope):
            hit = averaged(node)
            if not hit or centres_a_squared_deviation(node):
                continue
            if any(dB_valued(expr, tainted) for expr in hit[0]):
                found.add((node.lineno, hit[1]))
    return [f"line {line}: {wording}" for line, wording in sorted(found)]


def _negated(before: str) -> bool:
    """Whether a negation word occurs in the clause that ends at a vocabulary word: the text
    after the last clause break before it, with ``not only``, ``not just`` and ``not merely``
    taken out."""
    clause = re.sub(NOT_MERELY, "", re.split(CLAUSE_BREAKS, before)[-1])
    return any(re.search(rf"\b{word}\b", clause) for word in NEGATIONS)


def _paragraphs(text: str) -> List[List[Tuple[int, str]]]:
    """Each run of consecutive non-blank lines of ``text``, as (line number, stripped line). A
    list item begins a run of its own."""
    paragraphs: List[List[Tuple[int, str]]] = []
    current: List[Tuple[int, str]] = []
    for number, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(current)
                current = []
            continue
        if LIST_ITEM.match(stripped) and current:
            paragraphs.append(current)
            current = []
        current.append((number, stripped))
    if current:
        paragraphs.append(current)
    return paragraphs


def _joined(paragraph: List[Tuple[int, str]]) -> Tuple[str, List[Tuple[int, int]]]:
    """A paragraph's lines joined by spaces, and the (offset, line number) at which each line
    begins in the join."""
    joined = " ".join(line for _, line in paragraph)
    begins, position = [], 0
    for number, line in paragraph:
        begins.append((position, number))
        position += len(line) + 1
    return joined, begins


def _line_of(begins: List[Tuple[int, int]], offset: int) -> int:
    """The line number that holds an offset of a joined paragraph."""
    return max(number for begin, number in begins if begin <= offset)


def _sentence_spans(joined: str) -> List[Tuple[int, int]]:
    """The (start, end) offsets of each sentence of a paragraph. A sentence ends at ``. ``,
    ``? ``, ``! `` or ``;``; the mark is not part of it."""
    spans, start = [], 0
    for mark in re.finditer(r"\. |\? |! |;", joined):
        spans.append((start, mark.start()))
        start = mark.end()
    spans.append((start, len(joined)))
    return spans


def immunity_violations(text: str, vocabulary: Sequence[str]) -> List[str]:
    """Each sentence of ``text`` that holds a value of the immunity vocabulary beside a term of
    ``IMMUNITY_CONTEXT``, case-insensitively, where the value
    is not negated in its clause. A sentence is read across the lines of its paragraph, so a
    negation can end one line and the value start the next. ``text`` is markdown, or the
    ``python_prose`` of a module; the line reported is the line of the value."""
    if not vocabulary:
        raise ValueError("the constants name no immunity vocabulary")
    words = re.compile("|".join([re.escape(word.lower()) for word in vocabulary]
                                + list(IMMUNITY_PATTERNS)))
    found = []
    for paragraph in _paragraphs(text):
        joined, begins = _joined(paragraph)
        for start, end in _sentence_spans(joined):
            lowered = joined[start:end].lower()
            if not any(re.search(term, lowered) for term in IMMUNITY_CONTEXT):
                continue
            hits = sorted((start + hit.start(), hit.group(0)) for hit in words.finditer(lowered)
                          if not _negated(lowered[:hit.start()]))
            if hits:
                line_of_value = _line_of(begins, hits[0][0])
                found.append(f"line {line_of_value}: {', '.join(dict.fromkeys(w for _, w in hits))}")
    return found


def _code_prose(source: str) -> str:
    """A notebook code cell's comments and docstrings. A cell that does not parse, such as one
    with a magic, keeps only its whole-line comments."""
    try:
        return python_prose(source)
    except (SyntaxError, tokenize.TokenError):
        return "\n".join(line.strip().lstrip("#").strip() if line.strip().startswith("#") else ""
                         for line in source.split("\n"))


def immunity_scan(rel: str, text: str, vocabulary: Sequence[str]) -> List[str]:
    """The immunity violations of one tracked text file: a Python file's comments and docstrings,
    a notebook's markdown cells and code-cell comments (each reason names its cell), or the whole
    of any other file."""
    if rel.endswith(".ipynb"):
        found = []
        for index, cell in enumerate(json.loads(text)["cells"]):
            source = cell.get("source", "")
            source = "".join(source) if isinstance(source, list) else source
            if cell.get("cell_type") == "markdown":
                prose = source
            elif cell.get("cell_type") == "code":
                prose = _code_prose(source)
            else:
                continue
            found += [f"cell {index} {reason}" for reason in immunity_violations(prose, vocabulary)]
        return found
    if rel.endswith(".py"):
        return immunity_violations(python_prose(text), vocabulary)
    return immunity_violations(text, vocabulary)


def python_prose(source: str) -> str:
    """The source with only its comments and docstrings kept, one line for each source line, so
    a line number in the result is the source's own."""
    lines = [""] * (source.count("\n") + 1)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            lines[token.start[0] - 1] = token.string.lstrip("#").strip()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first = node.body[0] if node.body else None
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            for offset, line in enumerate(first.value.value.split("\n")):
                index = first.lineno - 1 + offset
                lines[index] = f"{lines[index]} {line}".strip()
    return "\n".join(lines)


def skill_contract_violations(text: str) -> List[str]:
    """Each sentence of ``text``, read across the lines of its paragraph, that names a manifest or
    receipt, or a plural of one, beside a ``CONTRACT_TERMS`` pattern. A sentence that names a
    ``CONTRACT_CARRIERS`` word as a whole word and says the contract is carried by or extends it
    is exempt. The terms match case-insensitively; the carriers match as written."""
    found = []
    for paragraph in _paragraphs(text):
        joined, begins = _joined(paragraph)
        for start, end in _sentence_spans(joined):
            sentence = joined[start:end]
            lowered = sentence.lower()
            hits = sorted((start + hit.start(), term) for term in MANIFEST_TERMS
                          for hit in re.finditer(rf"\b{term}s?\b", lowered))
            if not hits:
                continue
            carried = (any(re.search(rf"\b{carrier}\b", sentence) for carrier in CONTRACT_CARRIERS)
                       and bool(re.search(CARRY_WORDS, lowered)))
            if any(re.search(pattern, lowered) for pattern in CONTRACT_TERMS) and not carried:
                terms = dict.fromkeys(term for _, term in hits)
                found.append(f"line {_line_of(begins, hits[0][0])}: {', '.join(terms)}")
    return found


def _is_logger_report(call: ast.Call) -> bool:
    """Whether a call is a logger's warning, error or exception: its receiver is named for a
    logger (``logger``, ``log``, ``logging``) or is a ``getLogger(...)`` call."""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in LOGGER_WARNINGS:
        return False
    receiver = func.value.func if isinstance(func.value, ast.Call) else func.value
    return "log" in _final(receiver).lower()


def _own_nodes(fn: ast.AST):
    """The nodes of a function's own statements; the functions, lambdas and classes it defines
    are skipped."""
    pending = list(fn.body)
    while pending:
        node = pending.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        pending.extend(ast.iter_child_nodes(node))


def _body_reports(fn: ast.AST, bound: Dict[str, str]) -> bool:
    """Whether a function's own body raises, calls ``warnings.warn``, or calls a logger's warning,
    error or exception."""
    return any(isinstance(node, ast.Raise)
               or (isinstance(node, ast.Call) and (_target(node.func, bound) == "warnings.warn"
                                                   or _is_logger_report(node)))
               for node in _own_nodes(fn))


def _top_defs(tree: ast.AST) -> Dict[str, ast.AST]:
    """The functions a module defines at its top level, by name."""
    return {node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _relative_imports(tree: ast.AST, path: str) -> Dict[str, Tuple[str, str]]:
    """Each name bound by ``from .module import name`` or ``from ..module import name``, at any
    level, as alias -> (the module's path without its suffix, name), resolved from ``path``."""
    bound: Dict[str, Tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level >= 1 and node.module:
            package = PurePosixPath(path).parent
            for _ in range(node.level - 1):
                package = package.parent
            base = (package / node.module.replace(".", "/")).as_posix()
            for alias in node.names:
                bound[alias.asname or alias.name] = (base, alias.name)
    return bound


def _callee_reports(name: str, defs: Dict[str, ast.AST], bound: Dict[str, str],
                    imports: Dict[str, Tuple[str, str]],
                    read: Callable[[str], Optional[str]]) -> bool:
    """Whether the function ``name`` resolves to reports in its own body: a function of this
    module, or the function a relative import names, read through ``read`` from the tracked
    file. One level only: the functions that function calls are not followed."""
    if name in defs:
        return _body_reports(defs[name], bound)
    if name not in imports:
        return False
    base, original = imports[name]
    for candidate in (f"{base}.py", f"{base}/__init__.py"):
        text = read(candidate)
        if text is not None:
            tree = ast.parse(text)
            defs_of = _top_defs(tree)
            return original in defs_of and _body_reports(defs_of[original], _bindings(tree))
    return False


def _handler_loud(handler: ast.ExceptHandler, bound: Dict[str, str],
                  callee_reports: Callable[[str], bool]) -> bool:
    """Whether a handler's body reports or uses its exception: it raises, calls ``warnings.warn``
    or a logger's warning, error or exception, calls a function that reports (``callee_reports``),
    or reads the bound exception name anywhere in its body, returned values included."""
    body = [node for stmt in handler.body for node in ast.walk(stmt)]
    if any(isinstance(node, ast.Raise) for node in body):
        return True
    if any(isinstance(node, ast.Call) and (_target(node.func, bound) == "warnings.warn"
                                           or _is_logger_report(node)) for node in body):
        return True
    if handler.name and any(isinstance(node, ast.Name) and node.id == handler.name
                            and isinstance(node.ctx, ast.Load) for node in body):
        return True
    return any(callee_reports(node.func.id) for node in body
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Name))


def _handler_owners(tree: ast.AST) -> Dict[int, str]:
    """The qualified name of the function each except handler sits in (``Class.method``,
    ``outer.inner``), by ``id`` of the handler; ``<module>`` outside any function."""
    owners: Dict[int, str] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = prefix
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}.{child.name}" if prefix else child.name
            if isinstance(child, ast.ExceptHandler):
                owners[id(child)] = prefix or "<module>"
            visit(child, name)

    visit(tree, "")
    return owners


def silent_handler_sites(source: str, path: str,
                         read: Callable[[str], Optional[str]]) -> List[Tuple[str, str]]:
    """Each except handler of one module that swallows its exception (``_handler_loud``), unless
    it catches only ``OPTIONAL_IMPORT_ERRORS``: an absent optional dependency is a documented
    fallback. A bare handler catches everything and is spelled ``(bare)``. Each violation is
    spelled by the line of its handler's first body statement, with that line's text, and paired
    with the qualified name of the function it sits in (``_handler_owners``)."""
    lines = source.split("\n")
    tree = ast.parse(source)
    bound = _bindings(tree)
    defs = _top_defs(tree)
    imports = _relative_imports(tree, path)
    owners = _handler_owners(tree)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            spelled, caught = "(bare)", set()
        else:
            spelled = ast.unparse(node.type)
            names = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
            caught = {_final(name) for name in names}
        if caught and caught <= set(OPTIONAL_IMPORT_ERRORS):
            continue
        if _handler_loud(node, bound, lambda name: _callee_reports(
                name, defs, bound, imports, read)):
            continue
        first = node.body[0].lineno
        found.append((first, spelled, lines[first - 1].strip(), owners[id(node)]))
    return [(function, f"line {first}: except {spelled}: {text}")
            for first, spelled, text, function in sorted(found)]


def silent_handler_violations(source: str, path: str,
                              read: Callable[[str], Optional[str]]) -> List[str]:
    """The violations ``silent_handler_sites`` reports, spelled without their function."""
    return [text for _, text in silent_handler_sites(source, path, read)]


def _tracked_files(root: Path) -> List[str]:
    """Every tracked file of the repository, as sorted posix paths."""
    listed = subprocess.run(["git", "-C", str(root), "ls-files"],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    return sorted(line for line in listed.stdout.splitlines() if line)


def _exempt(path: str) -> bool:
    """Whether a path is a ``PROSE_EXEMPT`` file, or lies under a ``PROSE_EXEMPT`` tree. A file
    name matches only itself, so a sibling such as ``scripts/fact_gate_rules.py`` is read."""
    return any(path == entry or (entry.endswith("/") and path.startswith(entry))
               for entry in PROSE_EXEMPT)


def _prose_files(tracked: Sequence[str]) -> List[str]:
    """The text files the immunity rule reads: every tracked file with a ``PROSE_SUFFIXES``
    suffix and every file under a ``PROSE_ANY`` tree, unless ``_exempt``."""
    return [path for path in tracked
            if not _exempt(path)
            and (path.endswith(PROSE_SUFFIXES) or path.startswith(PROSE_ANY))]


def _skill_files(tracked: Sequence[str]) -> List[str]:
    """Every tracked ``SKILL.md`` under ``skills/``."""
    return [path for path in tracked
            if path.startswith("skills/") and path.rsplit("/", 1)[-1] == "SKILL.md"]


def _text_scans(root: Path, prose: Sequence[str], skill_files: Sequence[str],
                python: Sequence[str], constants: Dict[str, List[str]]):
    """Each text rule's violations as sorted [file, reason] pairs."""
    if "immunity vocabulary" not in constants:
        raise ValueError("the constants name no immunity vocabulary")
    scans: Dict[str, List[List[str]]] = {"immunity_vocabulary": [], "skill_contracts": [],
                                         "silent_handlers": []}
    for rel in prose:
        text = (root / rel).read_text(encoding="utf-8")
        scans["immunity_vocabulary"].extend(
            [rel, reason] for reason in immunity_scan(rel, text, constants["immunity vocabulary"]))
    for rel in skill_files:
        text = (root / rel).read_text(encoding="utf-8")
        scans["skill_contracts"].extend([rel, reason] for reason in skill_contract_violations(text))
    package = {rel: (root / rel).read_text(encoding="utf-8")
               for rel in python if rel.startswith(JNWB_PACKAGE)}
    flagged = set()
    for rel, text in package.items():
        for function, reason in silent_handler_sites(text, rel, package.get):
            flagged.add((rel, function))
            if (rel, function) not in S9_EXCUSED:
                scans["silent_handlers"].append([rel, reason])
    for rel, function in sorted(S9_EXCUSED):
        if (rel, function) not in flagged:
            scans["silent_handlers"].append(
                [rel, f"S9_EXCUSED lists {function}, which no flagged handler matches: stale"])
    return {name: sorted(pairs) for name, pairs in scans.items()}


def _tracked_python(root: Path) -> List[str]:
    """Every tracked Python file of the repository, as sorted posix paths."""
    listed = subprocess.run(["git", "-C", str(root), "ls-files", "--", "*.py"],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    return sorted(line for line in listed.stdout.splitlines() if line)


def _source_scans(root: Path, python: Sequence[str], constants: Dict[str, List[str]]):
    """Each scan's violations as sorted [file, reason] pairs."""
    scans: Dict[str, List[List[str]]] = {"global_seeds": [], "rng_parameters": [],
                                         "db_averages": []}
    for rel in python:
        text = (root / rel).read_text(encoding="utf-8")
        if rel.startswith(JNWB_PACKAGE):  # S5 reads the package; tests/ is outside it
            scans["global_seeds"].extend([rel, reason] for reason in global_seed_calls(text))
        if rel.startswith(SCANNED_FOR_RNG):
            scans["rng_parameters"].extend([rel, reason] for reason in rng_violations(text))
        if rel.startswith(DB_PACKAGE):
            scans["db_averages"].extend(
                [rel, reason] for reason in db_average_violations(text, constants))
    return {name: sorted(pairs) for name, pairs in scans.items()}


# ------------------------------------------------------------------------ scheme scan (fact S10)

#: The draws the scheme rule reads as a null: a permutation or shuffle, the package's label
#: permutation, a circular shift (``np.roll``), a surrogate and a derangement. A sign flip (a
#: ``choice`` between -1 and +1) is the paired permutation null the docstrings name.
NULL_DRAWS = ("permutation", "shuffle", "permuted", "permute_labels", "roll", "_surrogate_source",
              "_random_derangement")
#: The keys a result names its exchangeability scheme under: ``scheme`` (label permutation),
#: ``surrogate_scheme`` (surrogates and circular shifts), ``null`` (the execution record of
#: ``jrsa``), ``null_method`` (``xflip``) and ``exchangeability_scheme`` (``coherence_bias_floor``).
SCHEME_KEYS = ("scheme", "surrogate_scheme", "null", "null_method", "exchangeability_scheme")
#: The calls whose keywords are keys of a result: ``update``, ``dict`` and a class constructor.
RESULT_CALLS = ("update", "dict")
#: The callables the scheme rule excuses, by (module, qualified name), each with its reason. A
#: listed callable that no longer draws an unnamed null is reported as stale.
S10_EXCUSED: Dict[Tuple[str, str], str] = {
    ("jnwb.wavemap", "wavemap_resolution_sweep"):
        "a unit subsample for the stability sweep: its units are returned and no null is compared",
    ("jnwb.permutation", "permute_labels"):
        "returns a bare label array: no key can be carried",
    ("jnwb.statistics._analysis", "StatisticalAnalysis.exact_sign_flip"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "exact_sign_flip"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "shuffle_pvalue_paired"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "shuffle_pvalue_unpaired"):
        "returns a bare tuple: no key can be carried",
}


def _public_callables(package: Any) -> List[Tuple[str, Any, Any]]:
    """Each callable the package exports, and each public method of an exported class, as
    (qualified name, function, owning class or None), in sorted order. An exported submodule
    is no callable and is not imported: one behind an optional extra raises on import."""
    found = []
    submodules = set(getattr(package, "SUBMODULES", ()))
    for name in sorted(set(package.__all__) - submodules):
        obj = getattr(package, name, None)
        if inspect.isclass(obj):
            for mname, meth in sorted(vars(obj).items()):
                if mname.startswith("_"):
                    continue
                fn = meth.__func__ if isinstance(meth, (staticmethod, classmethod)) else meth
                if inspect.isfunction(fn):
                    found.append((f"{name}.{mname}", fn, obj))
        elif inspect.isfunction(obj):
            found.append((name, obj, None))
    return found


def _skipped_exports(package: Any) -> List[str]:
    """Each export the callable walk does not examine: neither a class nor a function, and not a
    submodule. A constant is counted here rather than dropped without a word."""
    submodules = set(getattr(package, "SUBMODULES", ()))
    return [name for name in sorted(set(package.__all__) - submodules)
            if not inspect.isclass(getattr(package, name, None))
            and not inspect.isfunction(getattr(package, name, None))]


def _sign_flip(call: ast.Call) -> bool:
    """A ``choice`` between -1 and +1: the sign flip of a paired permutation null."""
    if _final(call.func) != "choice" or not call.args:
        return False
    options = ast.unparse(call.args[0])
    return bool(re.search(r"-1(?:\.0)?\b", options)
                and re.search(r"(?<![\w.-])1(?:\.0)?\b", options))


def _draw(call: ast.Call) -> Optional[str]:
    """The name of the null draw a call makes, or None."""
    final = _final(call.func)
    if final in NULL_DRAWS:
        return final
    return "sign flip" if _sign_flip(call) else None


def _result_keys(tree: ast.AST) -> set:
    """The string keys a body sets: dict literals, subscript stores, and the keywords of a call
    that builds a result (``RESULT_CALLS`` and capitalised constructors). A keyword of any other
    call is an argument to it, not a key of a result."""
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys |= {k.value for k in node.keys
                     if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                keys.add(node.slice.value)
        elif isinstance(node, ast.Call):
            final = _final(node.func)
            if final in RESULT_CALLS or final[:1].isupper():
                keys |= {kw.arg for kw in node.keywords if kw.arg}
    return keys


def _callee(fn: Any, dotted_name: str, owner: Any) -> Any:
    """The jnwb function a dotted callee name stands for, read through the function's module
    globals, or through its owning class for ``self.`` and ``cls.``; None for anything else."""
    head, _, rest = dotted_name.partition(".")
    if head in ("self", "cls"):
        obj = getattr(owner, rest, None) if owner is not None and rest else None
    else:
        obj = fn.__globals__.get(head)
        for part in filter(None, rest.split(".")):
            obj = getattr(obj, part, None)
    if isinstance(obj, (staticmethod, classmethod)):
        obj = obj.__func__
    module = getattr(obj, "__module__", None) or ""
    if inspect.isfunction(obj) and (module == "jnwb" or module.startswith("jnwb.")):
        return obj
    return None


def _reach(fn: Any, owner: Any, seen: set, depth: int = 0,
           draw: Callable[[ast.Call], Optional[str]] = None) -> Tuple[set, set]:
    """The draws and result keys of a function and of the jnwb functions it reaches by name.
    ``draw`` names the consuming call (``_draw`` for null draws, ``_resolver_call`` for
    randomness); the default keeps the S10 scan's behaviour. Raises OSError when the source
    cannot be read."""
    if draw is None:
        draw = _draw
    key = (fn.__module__, fn.__qualname__)
    if key in seen or depth > 8:
        return set(), set()
    seen.add(key)
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    draws, keys = set(), _result_keys(tree)
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        drawn = draw(call)
        if drawn is not None:
            draws.add(drawn)
        target = _callee(fn, _dotted(call.func), owner)
        if target is not None:
            more_draws, more_keys = _reach(target, owner, seen, depth + 1, draw)
            draws |= more_draws
            keys |= more_keys
    return draws, keys


def scheme_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the scheme rule examined, and each that draws a null without a
    scheme key among its results (``SCHEME_KEYS``), as sorted [module.name, reason] pairs. A key
    set by a jnwb function that a callable reaches counts for that callable. A callable whose
    source cannot be read is a finding, never a pass."""
    examined, found, flagged = 0, [], set()
    for qualname, fn, owner in _public_callables(package):
        examined += 1
        try:
            draws, keys = _reach(fn, owner, set())
        except (OSError, TypeError, SyntaxError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        if not draws or keys & set(SCHEME_KEYS):
            continue
        site = (fn.__module__, qualname)
        flagged.add(site)
        if site not in S10_EXCUSED:
            found.append([f"{fn.__module__}.{qualname}",
                          f"draws {', '.join(sorted(draws))} and names no scheme key"])
    for module, qualname in sorted(S10_EXCUSED):
        if (module, qualname) not in flagged:
            found.append([f"{module}.{qualname}",
                          "S10_EXCUSED lists it, but it draws no unnamed null: stale"])
    return examined, sorted(found)


# ------------------------------------------------------------------------ rng scan (fact S11)

#: The keys a result reports the randomness it ran on under. ``surrogate_seed_entropy``
#: is the entropy that rebuilds the draws (None only when a Generator was passed in place,
#: whose position is not recoverable, or where the site documents otherwise);
#: ``xflip_surrogate_seed_entropy`` is that entropy forwarded through curation; ``seed``,
#: ``louvain_seed`` and ``umap_seed`` are the int seeds that ran; ``rng`` and
#: ``random_state`` echo the rng input (an int seed, a Generator, or None).
RNG_KEYS = ("surrogate_seed_entropy", "xflip_surrogate_seed_entropy", "seed",
            "louvain_seed", "umap_seed", "rng", "random_state")
#: The callables the rng rule excuses, by (module, qualified name), each with its reason. A
#: bare array or tuple carries no key: reshaping one to carry it is a public API choice, not
#: a repair. A listed callable that no longer consumes unnamed randomness is stale.
S11_EXCUSED: Dict[Tuple[str, str], str] = {
    ("jnwb.permutation", "permute_labels"):
        "returns a bare label array: no key can be carried",
    ("jnwb.statistics._analysis", "StatisticalAnalysis.exact_sign_flip"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "exact_sign_flip"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "shuffle_pvalue_paired"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.statistics._tests", "shuffle_pvalue_unpaired"):
        "returns a bare tuple: no key can be carried",
    ("jnwb.viz", "resample_onsets"):
        "returns a bare onset array: no key can be carried",
}


#: The numeric factors a silent unit change scales by, in any spelling: ``1000`` and ``1e3``,
#: ``1000000`` and ``1e6``, ``0.001`` and ``1e-3``, and ``1e-6``.
UNIT_FACTORS = frozenset({1000.0, 0.001, 1000000.0, 1e-06})
#: A parameter carrying one of these suffixes names its unit, so scaling it is not silent.
UNIT_SUFFIXES = ("_ms", "_s", "_sec", "_hz", "_um", "_mm", "_uv", "_mv", "_v", "_us")
#: The callables the unit rule excuses, by (module, qualified name), each with its reason.
#: A listed callable that scales no parameter by a unit factor is reported as stale.
I2_UNIT_EXCUSED: Dict[Tuple[str, str], str] = {
    ("jnwb.laminar._vflip2", "vflip2"):
        "contact_spacing is declared in micrometres in the docstring and converted to the "
        "millimetres the computation uses; no value crosses the boundary in a changed unit",
    ("jnwb.laminar._xflip", "xflip"):
        "contact_spacing is declared in micrometres in the docstring and converted to the "
        "millimetres the computation uses; no value crosses the boundary in a changed unit",
}
#: The callables the wrapper rule excuses, by (module, qualified name), each with its reason.
#: Empty: no silent default change on the live tree is excused. A listed callable that passes
#: no literal over a default is reported as stale.
I2_WRAPPER_EXCUSED: Dict[Tuple[str, str], str] = {}


# ------------------------------------------------------------------------ signature types (fact I1)

#: The signal class each spike or LFP parameter name carries. Only these names put a
#: callable in the scan's domain: a generic name (``x``, ``signal1``, ``signals``) may take
#: either class depending on the call, so it declares nothing. Each side lists the names
#: the tree uses for it, read off the public signatures.
SIGNAL_PARAMETERS: Dict[str, str] = {
    "spike_times": "spikes",
    "spike_times1": "spikes",
    "spike_times2": "spikes",
    "spike_data": "spikes",
    "unit_spike_times": "spikes",
    "spike_waveforms": "spikes",
    "lfp": "lfp",
    "lfp_trace": "lfp",
    "lfp_data": "lfp",
    "lfp_matrix": "lfp",
    "lfp_area1": "lfp",
    "lfp_area2": "lfp",
    "lfp_phase": "lfp",
    "lfp_timestamps": "lfp",
}


def _signal_classes(parameters: set) -> Tuple[FrozenSet[str], List[str]]:
    """The signal classes a signature's parameter names show, and the sorted names that
    show them. A parameter outside ``SIGNAL_PARAMETERS`` shows none."""
    names = sorted(name for name in parameters if name in SIGNAL_PARAMETERS)
    return frozenset(SIGNAL_PARAMETERS[name] for name in names), names


def signature_types_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the signature-types rule examined, and each whose declared
    signal contract fails (``jnwb/_declarations.py`` ``DECLARATIONS``, read here at call
    time), as sorted [module.name, reason] pairs. A callable is in the domain when a
    parameter name is in ``SIGNAL_PARAMETERS``; it fails when it declares no input class,
    declares one that misses a class its parameters show (a declaration may name more, for
    an input whose parameter name is generic), or -- both declared -- calls another public
    callable whose class is not a subset of its own. A declarations key no in-domain
    callable carries is stale. A callable whose source cannot be read is a finding, never
    a pass."""
    declarations = _declarations.DECLARATIONS
    callables = _public_callables(package)
    index = {id(fn): (qualname, owner) for qualname, fn, owner in callables}
    domain = {}
    examined, found = 0, []
    for qualname, fn, owner in callables:
        examined += 1
        try:
            parameters = set(inspect.signature(fn).parameters)
        except (TypeError, ValueError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        classes, _ = _signal_classes(parameters)
        if not classes:
            continue
        domain[(fn.__module__, qualname)] = (fn, owner, classes)
        key = f"{fn.__module__}.{qualname}"
        declared = declarations.get(key)
        if declared is None:
            found.append([key, "takes signal parameters but declares no input class"])
        elif not set(classes) <= set(declared.input_class):
            found.append([key,
                          f"declares input class {sorted(declared.input_class)} but its "
                          f"signal parameters show {sorted(classes)}"])
    domain_keys = {f"{module}.{qualname}" for module, qualname in domain}
    for key in sorted(declarations):
        if key not in domain_keys:
            found.append([key, "DECLARATIONS lists it, but it takes no signal "
                               "parameter: stale"])
    for (module, qualname), (fn, owner, _) in sorted(domain.items()):
        declared = declarations.get(f"{module}.{qualname}")
        if declared is None:
            continue
        # A public operation reaches another through its private helpers too: the walk
        # follows every private function of the same package it calls, once each.
        queue, seen = [(fn, owner, f"{module}.{qualname}")], {id(fn)}
        while queue:
            body, body_owner, via = queue.pop()
            try:
                tree, first = _own_tree(body)
            except (OSError, TypeError, SyntaxError, ValueError):
                found.append([f"{module}.{qualname}", f"source of {via} unreadable: not checked"])
                continue
            for call in _own_calls(_own_root(tree)):
                dotted = _dotted(call.func)
                target = _public_target(body, dotted, body_owner, index)
                if target is None:
                    helper = _private_helper(body, dotted, body_owner, index)
                    if helper is not None and id(helper) not in seen:
                        seen.add(id(helper))
                        queue.append((helper, None, f"{helper.__module__}.{helper.__qualname__}"))
                    continue
                if target is fn:
                    continue
                gqualname, _ = index[id(target)]
                gkey = f"{target.__module__}.{gqualname}"
                gdeclared = declarations.get(gkey)
                if gdeclared is None:
                    continue
                if not set(gdeclared.input_class) <= set(declared.input_class):
                    found.append([f"{module}.{qualname}",
                                  f"{via} line {first + call.lineno - 1}: calls {gkey} with "
                                  f"declared class {sorted(gdeclared.input_class)} outside its "
                                  f"declared class {sorted(declared.input_class)}"])
    return examined, sorted(found)


def _private_helper(fn: Any, dotted: str, owner: Any, index: Dict[int, Any]) -> Optional[Any]:
    """The private function of ``fn``'s top-level package a dotted callee name stands for,
    resolved as ``_public_target`` resolves; None for a public callable or anything else."""
    head, _, rest = dotted.partition(".")
    if head in ("self", "cls"):
        obj = getattr(owner, rest, None) if owner is not None and rest else None
    else:
        obj = fn.__globals__.get(head)
        for part in filter(None, rest.split(".")):
            obj = getattr(obj, part, None)
    if isinstance(obj, (staticmethod, classmethod)):
        obj = obj.__func__
    if not inspect.isfunction(obj) or id(obj) in index:
        return None
    same_package = obj.__module__.split(".")[0] == fn.__module__.split(".")[0]
    return obj if same_package and obj.__name__.startswith("_") else None


def _is_unit_factor(node: ast.AST) -> bool:
    """Whether a node is a literal spelling of a unit factor: ``1000``, ``1e3``, ``0.001``,
    ``1e-3``, ``1e6``, ``1e-6`` or ``1000000``."""
    return (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool) and float(node.value) in UNIT_FACTORS)


def _declares_unit(parameters: set) -> bool:
    """Whether a function's parameters name the unit: ``units``, ``unit``, or a name ending
    in ``_unit`` or ``_units``."""
    return any(name in ("units", "unit") or name.endswith(("_unit", "_units"))
               for name in parameters)


def _own_tree(fn: Any) -> Tuple[ast.AST, int]:
    """The parsed source of ``fn`` with its first line number in its file. Raises OSError when
    the source cannot be read and SyntaxError when it does not parse."""
    lines, first = inspect.getsourcelines(fn)
    return ast.parse(textwrap.dedent("".join(lines))), first


def _own_root(tree: ast.AST) -> ast.AST:
    """The node whose own statements a scan reads: the defined function when the source holds
    one definition, else the whole tree (a callable assigned to a name)."""
    if len(tree.body) == 1 and isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
        return tree.body[0]
    return tree


def _keyword_literal(node: ast.AST) -> Tuple[bool, Any]:
    """Whether a keyword value is a literal constant, or a tuple or list of them, with the
    value it carries."""
    if isinstance(node, ast.Constant):
        return True, node.value
    if isinstance(node, (ast.Tuple, ast.List)) and all(
            isinstance(elt, ast.Constant) for elt in node.elts):
        return True, tuple(elt.value for elt in node.elts)
    return False, None


def _differs(first: Any, second: Any) -> bool:
    """Whether two values differ. A comparison that does not resolve, such as an elementwise
    one over an array default, counts as different rather than silently passing."""
    try:
        return bool(first != second)
    except Exception:  # noqa: BLE001 - any unresolvable comparison is a finding
        return True


def _public_target(fn: Any, dotted: str, owner: Any, index: Dict[int, Any]) -> Optional[Any]:
    """The public callable a dotted callee name stands for, read through the function's module
    globals, or through its owning class for ``self.`` and ``cls.``; None for anything else.
    Membership in the public index decides, so a planted package resolves like the live one."""
    head, _, rest = dotted.partition(".")
    if head in ("self", "cls"):
        obj = getattr(owner, rest, None) if owner is not None and rest else None
    else:
        obj = fn.__globals__.get(head)
        for part in filter(None, rest.split(".")):
            obj = getattr(obj, part, None)
    if isinstance(obj, (staticmethod, classmethod)):
        obj = obj.__func__
    return obj if inspect.isfunction(obj) and id(obj) in index else None


def unit_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the unit rule examined, and each that scales a parameter by
    a unit factor (``UNIT_FACTORS``, by multiplication or division) without naming the unit:
    neither the parameter's suffix (``UNIT_SUFFIXES``) nor a ``units``/``unit`` or
    ``*_unit``/``*_units`` parameter, as sorted [module.name, reason] pairs. A callable whose
    source cannot be read is a finding, never a pass."""
    examined, found, flagged = 0, [], set()
    for qualname, fn, owner in _public_callables(package):
        examined += 1
        try:
            parameters = set(inspect.signature(fn).parameters)
            tree, first = _own_tree(fn)
        except (OSError, TypeError, SyntaxError, ValueError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        if _declares_unit(parameters):
            continue
        for node in _own_nodes(_own_root(tree)):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div))):
                continue
            for side, other in ((node.left, node.right), (node.right, node.left)):
                if (isinstance(side, ast.Name) and side.id in parameters
                        and _is_unit_factor(other)
                        and not side.id.endswith(UNIT_SUFFIXES)):
                    flagged.add((fn.__module__, qualname))
                    if (fn.__module__, qualname) not in I2_UNIT_EXCUSED:
                        found.append([
                            f"{fn.__module__}.{qualname}",
                            f"line {first + node.lineno - 1}: scales parameter {side.id!r} "
                            f"by {other.value:g} and names no unit"])
    for module, qualname in sorted(I2_UNIT_EXCUSED):
        if (module, qualname) not in flagged:
            found.append([f"{module}.{qualname}",
                          "I2_UNIT_EXCUSED lists it, but it scales no parameter "
                          "by a unit factor: stale"])
    return examined, sorted(found)


def wrapper_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the wrapper rule examined, and each that calls another public
    callable with a literal keyword (an ``ast.Constant``, or a tuple or list of them) its own
    signature does not name, differing from that keyword's default, as sorted [module.name,
    reason] pairs. A callable whose source cannot be read is a finding, never a pass."""
    callables = _public_callables(package)
    index = {id(fn): (qualname, owner) for qualname, fn, owner in callables}
    examined, found, flagged = 0, [], set()
    for qualname, fn, owner in callables:
        examined += 1
        try:
            own = set(inspect.signature(fn).parameters)
            tree, first = _own_tree(fn)
        except (OSError, TypeError, SyntaxError, ValueError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        for call in _own_calls(_own_root(tree)):
            target = _public_target(fn, _dotted(call.func), owner, index)
            if target is None or target is fn:
                continue
            gqualname, _ = index[id(target)]
            defaults = inspect.signature(target).parameters
            for keyword in call.keywords:
                if not keyword.arg or keyword.arg in own:
                    continue
                gparam = defaults.get(keyword.arg)
                if gparam is None or gparam.default is inspect.Parameter.empty:
                    continue
                literal, value = _keyword_literal(keyword.value)
                if not literal or not _differs(value, gparam.default):
                    continue
                site = (fn.__module__, qualname)
                flagged.add(site)
                if site not in I2_WRAPPER_EXCUSED:
                    found.append([
                        f"{fn.__module__}.{qualname}",
                        f"line {first + call.lineno - 1}: passes {keyword.arg}={value!r} "
                        f"to {target.__module__}.{gqualname}, "
                        f"whose default is {gparam.default!r}"])
    for module, qualname in sorted(I2_WRAPPER_EXCUSED):
        if (module, qualname) not in flagged:
            found.append([f"{module}.{qualname}",
                          "I2_WRAPPER_EXCUSED lists it, but it passes no literal "
                          "over a default: stale"])
    return examined, sorted(found)


def _unwalked_callables(package: Any) -> List[Tuple[str, Any, Any]]:
    """What ``_public_callables`` leaves out, in its form: each public method an exported class
    inherits from a class of the same package rather than defines, and each callable export
    that is neither a function nor a class (a ``functools.partial``, a callable instance)."""
    found = []
    submodules = set(getattr(package, "SUBMODULES", ()))
    top = getattr(package, "__name__", "").split(".")[0]
    for name in sorted(set(package.__all__) - submodules):
        obj = getattr(package, name, None)
        if inspect.isclass(obj):
            for base in obj.__mro__[1:]:
                if base.__module__.split(".")[0] != top:
                    continue
                for mname, meth in sorted(vars(base).items()):
                    if mname.startswith("_") or mname in vars(obj):
                        continue
                    fn = meth.__func__ if isinstance(meth, (staticmethod, classmethod)) else meth
                    if inspect.isfunction(fn) and not any(
                            mname in vars(b) for b in obj.__mro__[1:obj.__mro__.index(base)]):
                        found.append((f"{name}.{mname}", fn, obj))
        elif callable(obj) and not inspect.isfunction(obj):
            found.append((name, obj, None))
    return found


def choice_default_scan(package: Any, names: Sequence[str],
                        exceptions: Sequence[Dict[str, str]]) -> Tuple[int, List[List[str]]]:
    """How many public callables the B3 rule examined, and each with a defaulted parameter
    whose name is in the choice-name lexicon ``names``, as sorted [module.name, reason] pairs.
    A ``window`` whose default is a string names a taper, not a time span, and sits outside
    the lexicon. A row of ``exceptions`` whose Operation is the callable's ``module.qualname``
    or its bare qualname, and whose Parameter is the parameter's name, keeps the default. A
    callable whose signature cannot be read is a finding, never a pass, and a row that matches
    no defaulted lexicon parameter is reported as stale."""
    lexicon, excused = set(names), {(row["Operation"], row["Parameter"]) for row in exceptions}
    examined, found, defaulted = 0, [], set()
    for qualname, fn, owner in _public_callables(package) + _unwalked_callables(package):
        examined += 1
        key = f"{getattr(fn, '__module__', None) or getattr(package, '__name__', '')}.{qualname}"
        if not (inspect.isfunction(fn) or inspect.ismethod(fn)):
            found.append([key, f"a {type(fn).__name__}, not a function: not checked"])
            continue
        try:
            parameters = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            found.append([key, "signature unreadable: not checked"])
            continue
        for pname, parameter in parameters.items():
            if pname not in lexicon or parameter.default is inspect.Parameter.empty:
                continue
            if pname == "window" and isinstance(parameter.default, str):
                continue
            defaulted.add((key, pname))
            defaulted.add((qualname, pname))
            if (key, pname) in excused or (qualname, pname) in excused:
                continue
            found.append([key, f"parameter {pname!r} defaults to {parameter.default!r}"])
    for operation, pname in sorted(excused):
        if (operation, pname) not in defaulted:
            found.append([operation,
                          f"the exceptions table names {pname!r} of {operation}, "
                          "which no defaulted lexicon parameter matches: stale"])
    return examined, sorted(found)


def _resolver_call(call: ast.Call) -> Optional[str]:
    """The name of the rng resolver a call reaches for (``RESOLVERS`` of the rng-parameter
    walk), or None. The walk defines which parameters are stochastic by use; the scan reads
    its rule table rather than retyping it."""
    final = _final(call.func)
    return final if final in RESOLVERS else None


def rng_scan(package: Any) -> Tuple[int, List[List[str]]]:
    """How many public callables the rng rule examined, and each that consumes randomness
    without an rng key among its results (``RNG_KEYS``), as sorted [module.name, reason]
    pairs. A key set by a jnwb function that a callable reaches counts for that callable,
    so forwarders whose target reports are not findings. A callable whose source cannot be
    read is a finding, never a pass."""
    examined, found, flagged = 0, [], set()
    for qualname, fn, owner in _public_callables(package):
        examined += 1
        try:
            draws, keys = _reach(fn, owner, set(), draw=_resolver_call)
        except (OSError, TypeError, SyntaxError):
            found.append([f"{fn.__module__}.{qualname}", "source unreadable: not checked"])
            continue
        if not draws or keys & set(RNG_KEYS):
            continue
        site = (fn.__module__, qualname)
        flagged.add(site)
        if site not in S11_EXCUSED:
            found.append([f"{fn.__module__}.{qualname}",
                          f"consumes randomness ({', '.join(sorted(draws))}) "
                          "and reports no rng key"])
    for module, qualname in sorted(S11_EXCUSED):
        if (module, qualname) not in flagged:
            found.append([f"{module}.{qualname}",
                          "S11_EXCUSED lists it, but it consumes no unnamed randomness: stale"])
    return examined, sorted(found)


# ------------------------------------------------------------------------ claim classes (fact S8)

#: The claim table of ``docs/architecture.md``: its ``Magnitude`` and ``Direction`` rows name,
#: backticked in their third cell, the estimators a label or a returned unit may name without
#: leaving its claim class.
CLAIM_HEADER = ("Claim", "What it states", "What jnwb estimates it with",
                "What it does not license")
#: The claim-table rows whose estimators the S8 rule reads.
CLAIM_ESTIMAND_ROWS = ("Magnitude", "Direction")
#: Short names a figure label may use for an estimator, beside the estimator's own name with
#: ``_`` read as a space. A short name whose estimator is in neither estimand row is stale.
LABEL_NAMES: Dict[str, str] = {
    "psi": "phase_slope_index",
    "phase slope": "phase_slope_index",
    "granger": "granger",
    "transfer entropy": "transfer_entropy",
    "te": "transfer_entropy",
    "imaginary coherency": "imaginary_coherency",
    "icoh": "imaginary_coherency",
    "wpli": "wpli",
    "coherence": "cross_area_coherence",
}
#: The vocabulary of the two claim classes above magnitude and direction (fact S8). The delay
#: class names a time or velocity unit, or a delay word anywhere; the inference class names a
#: cause, a drive or a driver. The method name "Granger causality" (any case, also
#: "Granger-causal") is removed from the text before the inference words are matched, so the
#: direction estimator's own name does not read as a causal claim.
HIGHER_CLASS_TERMS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "delay": {"units": ("s", "ms", "sec", "seconds", "rad/Hz", "radians/Hz", "m/s", "mm/s",
                        "um/s"),
              "words": ("delay", "latency", "velocity")},
    "inference": {"words": ("cause", "causes", "caused", "causing", "causal", "causality",
                            "causation", "causally", "drive", "drives", "driven", "driving",
                            "driver", "drivers")},
}
#: The calls whose positional arguments, or whose ``label``/``title``/``xlabel``/``ylabel``
#: keyword, the label rule reads as a figure label; ``panel_title`` is the docs figures' title
#: wrapper (``docs/figure_style.py``) and ``set`` is ``Axes.set``.
LABEL_CALLEES = ("set_xlabel", "set_ylabel", "set_title", "xlabel", "ylabel", "title",
                 "panel_title", "set", "suptitle", "set_label", "text",
                 "annotate", "legend", "colorbar", "plot", "scatter", "bar", "errorbar",
                 "fill_between", "axhline", "axvline", "step", "hist")
#: The label keywords the rule reads, beside a call's first argument.
LABEL_KEYWORDS = ("label", "title", "xlabel", "ylabel")
#: The suffix that puts a call's ``unit=`` literal in the unit rule's domain.
RESULT_SUFFIX = "Result"
#: The tree the label rule leaves out: a test may name a higher class to assert a check fires.
TESTS_TREE = "tests/"
_PAREN_OR_BRACKET = re.compile(r"\(([^()]*)\)|\[([^\[\]]*)\]")
_GRANGER_METHOD = re.compile(r"granger[ -]causal(?:ity)?", re.IGNORECASE)


def read_claim_estimators(text: str) -> Dict[str, FrozenSet[str]]:
    """The estimators of the claim table's ``Magnitude`` and ``Direction`` rows: the backticked
    names of each row's third cell. Raises ValueError when the table or a row is missing, so a
    moved page can never read as an empty pass."""
    tables = [(header, rows) for _, header, rows in _all_tables(text)
              if tuple(header) == CLAIM_HEADER]
    if len(tables) != 1:
        raise ValueError(f"the page holds {len(tables)} claim tables, not exactly one")
    found: Dict[str, List[str]] = {}
    for row in tables[0][1]:
        if row and row[0] in CLAIM_ESTIMAND_ROWS:
            if len(row) < len(CLAIM_HEADER):
                raise ValueError(f"the claim table's {row[0]!r} row has {len(row)} cells, not "
                                 f"{len(CLAIM_HEADER)}: {row}")
            found[row[0]] = _BACKTICKED.findall(row[2])
    missing = [claim for claim in CLAIM_ESTIMAND_ROWS if claim not in found]
    if missing:
        raise ValueError(f"the claim table holds no {missing} row")
    return {claim: frozenset(names) for claim, names in found.items()}


def _phrase(pattern: str, ignorecase: bool = True) -> re.Pattern:
    """A whole-word pattern for a name or term; a space in it matches a run of whitespace or
    hyphens."""
    body = re.escape(pattern).replace("\\ ", r"[\s-]+").replace(" ", r"[\s-]+")
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE if ignorecase else 0)


def _higher_class_terms(text: str, units_anywhere: bool) -> List[str]:
    """The higher-class terms ``text`` holds, each spelled ``class: 'term'``. A delay unit
    counts anywhere in a unit literal; in a label, a compound unit (one with ``/``) counts
    anywhere and a plain one inside parentheses or brackets; a delay word counts anywhere; an
    inference word counts after the method name Granger causality is removed."""
    delay, inference = HIGHER_CLASS_TERMS["delay"], HIGHER_CLASS_TERMS["inference"]
    found: List[str] = []
    bracketed = " ".join(m.group(1) if m.group(1) is not None else m.group(2)
                         for m in _PAREN_OR_BRACKET.finditer(text))
    for unit in delay["units"]:
        scope = text if units_anywhere or "/" in unit else bracketed
        if _phrase(unit, ignorecase=False).search(scope):
            found.append(f"delay term {unit!r}")
    found += [f"delay term {word!r}" for word in delay["words"] if _phrase(word).search(text)]
    causal = _GRANGER_METHOD.sub(" ", text)
    found += [f"inference term {word!r}" for word in inference["words"]
              if _phrase(word).search(causal)]
    return found


def _estimator_patterns(estimators: FrozenSet[str]) -> Dict[str, List[re.Pattern]]:
    """Each estimator's whole-word patterns: its own name with ``_`` read as a space, plus the
    short names ``LABEL_NAMES`` gives it. A short name whose estimator is outside ``estimators``
    is reported as stale by ``claim_class_scan`` and matches nothing here."""
    patterns: Dict[str, List[re.Pattern]] = {}
    for estimator in sorted(estimators):
        pats = [_phrase(estimator.replace("_", " "))]
        pats += [_phrase(name) for name, target in LABEL_NAMES.items() if target == estimator]
        patterns[estimator] = pats
    return patterns


def _literal_text(node: ast.AST, names: Optional[Dict[str, str]] = None) -> Optional[str]:
    """The text of a string constant: a plain literal, the literal parts of an f-string, a sum
    of such parts, or a name ``names`` binds to one. Anything else, and an empty join, is no
    label text."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value for part in node.values
                       if isinstance(part, ast.Constant) and isinstance(part.value, str))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _literal_text(node.left, names), _literal_text(node.right, names)
        if left is not None or right is not None:
            return (left or "") + (right or "")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _literal_text(node.left, names)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "format"):
        return _literal_text(node.func.value, names)
    if isinstance(node, (ast.List, ast.Tuple, ast.IfExp)):
        elements = node.elts if not isinstance(node, ast.IfExp) else [node.body, node.orelse]
        parts = [_literal_text(element, names) for element in elements]
        if any(part is not None for part in parts):
            return " | ".join(part for part in parts if part is not None)
    if isinstance(node, ast.Name) and names:
        return names.get(node.id)
    return None


def _bound_names(tree: ast.AST) -> Dict[str, str]:
    """Each name an assignment anywhere in a module binds to string text, mapped to every such
    text joined, so a term in any binding is read wherever the name is used. A name bound to
    another name takes that name's text; chains resolve up to the module's assignment count."""
    assignments = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            assignments.append((node.targets, node.value))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
            assignments.append(([node.target], node.value))
    names: Dict[str, str] = {}
    for _ in range(len(assignments) + 1):
        bound: Dict[str, List[str]] = {}
        for targets, value in assignments:
            text = _literal_text(value, names)
            if text is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    bound.setdefault(target.id, []).append(text)
        resolved = {name: " | ".join(texts) for name, texts in bound.items()}
        if resolved == names:
            break
        names = resolved
    return names


def _label_sites(tree: ast.Module) -> List[Tuple[int, str]]:
    """Each label of one module as (line, text): string text passed as a positional argument or
    as a ``LABEL_KEYWORDS`` keyword to a call whose final name is in ``LABEL_CALLEES``. A name
    counts as every text an assignment in the module binds it to."""
    names = _bound_names(tree)
    sites = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _final(node.func) in LABEL_CALLEES):
            continue
        for arg in list(node.args) + [kw.value for kw in node.keywords
                                      if kw.arg in LABEL_KEYWORDS]:
            text = _literal_text(arg, names)
            if text:
                sites.append((arg.lineno, text))
    return sites


def _unit_sites(tree: ast.AST) -> List[Tuple[int, str, str]]:
    """Each ``unit=`` string of one module as (line, callee name, text), for a call whose
    callee's name ends in ``RESULT_SUFFIX``; a name counts as every text the module binds it
    to."""
    names = _bound_names(tree)
    sites = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _final(node.func).endswith(RESULT_SUFFIX)):
            continue
        for keyword in node.keywords:
            text = _literal_text(keyword.value, names) if keyword.arg == "unit" else None
            if text is not None:
                sites.append((keyword.value.lineno, _final(node.func), text))
    return sites


def _defining_modules(estimators: FrozenSet[str]) -> Dict[str, str]:
    """Each estimator and the dotted name of the module that defines it, resolved on the
    checkout's ``jnwb.<estimator>`` with ``inspect.getmodule``; an estimator the package does
    not export names no module here."""
    import jnwb  # the checkout, as every scan of the imported package reads

    modules: Dict[str, str] = {}
    for estimator in sorted(estimators):
        obj = getattr(jnwb, estimator, None)
        module = inspect.getmodule(obj) if obj is not None else None
        if module is not None and getattr(module, "__name__", ""):
            modules[estimator] = module.__name__
    return modules


def claim_class_scan(root: Path, python: Sequence[str]) -> Tuple[Dict[str, int],
                                                                 List[List[str]]]:
    """How many figure labels and ``unit=`` literals the S8 rule examined, by source, and each
    that names a magnitude or direction estimand while holding a term of a higher claim class,
    as sorted [file, reason] pairs.

    The estimators come from the claim table of ``docs/architecture.md`` under ``root``: the
    backticked names of its ``Magnitude`` and ``Direction`` rows. A missing table or row raises,
    never an empty pass. A label is a string constant passed as a call's first argument or as a
    ``LABEL_KEYWORDS`` keyword to a call whose attribute name is in ``LABEL_CALLEES``, in every
    tracked Python file outside ``tests/``; a unit literal is a ``unit=`` string of a call whose
    callee's name ends in ``Result``, in every tracked file under ``jnwb/``. A unit literal is a
    finding only in a module that defines an estimand's estimator: the module
    ``inspect.getmodule`` names for ``jnwb.<estimator>`` of the checkout, or one whose own
    top-level definitions name an estimator.
    """
    page = root / "docs" / "architecture.md"
    if not page.is_file():
        raise ValueError(f"{_rel(page, root)} is missing: no claim table to read")
    estimators = read_claim_estimators(page.read_text(encoding="utf-8"))
    licensed = estimators["Magnitude"] | estimators["Direction"]
    found = [["scripts/build_fact_graph.py",
              f"LABEL_NAMES names {name!r}, whose estimator {estimator!r} is in neither "
              "estimand row: stale"]
             for name, estimator in sorted(LABEL_NAMES.items()) if estimator not in licensed]
    patterns = _estimator_patterns(licensed)
    module_of = _defining_modules(licensed)
    examined = {"labels": 0, "units": 0}
    for rel in python:
        if rel.startswith(TESTS_TREE):
            continue
        source = (root / rel).read_text(encoding="utf-8")
        tree = ast.parse(source)
        dotted = rel[:-len(".py")].replace("/", ".")
        tops = {node.name for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        owned = sorted(est for est in licensed
                       if module_of.get(est) == dotted or est in tops)
        for line, text in _label_sites(tree):
            examined["labels"] += 1
            named = sorted(name for name, pats in patterns.items()
                           if any(pattern.search(text) for pattern in pats))
            if not named:
                continue
            for term in _higher_class_terms(text, units_anywhere=False):
                found.append([rel, f"line {line}: {text!r} names {', '.join(named)} and holds "
                                   f"the {term}"])
        if not rel.startswith(JNWB_PACKAGE):
            continue
        for line, callee, unit in _unit_sites(tree):
            examined["units"] += 1
            if not owned:
                continue
            for term in _higher_class_terms(unit, units_anywhere=True):
                found.append([rel, f"line {line}: {callee} unit {unit!r} in the module of "
                                   f"{', '.join(owned)} holds the {term}"])
    return examined, sorted(found)


# ------------------------------------------------------------------------ named units (fact I3)

#: The base suffixes the boundary rule reads beside the unit suffixes: index provenance,
#: 0- or 1-based.
BASE_SUFFIXES = ("_idx", "_index", "_0based", "_1based")
#: The suffixes a boundary edge compares: a unit suffix or a base suffix.
BOUNDARY_SUFFIXES = UNIT_SUFFIXES + BASE_SUFFIXES
#: Suffixes that spell the same unit or base, mapped to the one an edge compares.
SUFFIX_ALIASES = {"_sec": "_s", "_index": "_idx"}
#: The comment that states an intentional break at its change site, excusing the edges on its
#: line or in the statement it stands above.
BREAK_MARK = "INTENTIONAL BREAK"


def _boundary_suffix(name: str) -> Optional[str]:
    """The longest suffix of ``BOUNDARY_SUFFIXES`` a name ends with, compared
    case-insensitively and read through ``SUFFIX_ALIASES``; None when it carries none."""
    lowered = name.lower()
    for suffix in sorted(BOUNDARY_SUFFIXES, key=len, reverse=True):
        if lowered.endswith(suffix):
            return SUFFIX_ALIASES.get(suffix, suffix)
    return None


def _boundary_definitions(tree: ast.AST) -> Dict[str, List[Tuple[Tuple[str, ...],
                                                                 FrozenSet[str]]]]:
    """Each function or method name defined in one module, mapped to its distinct parameter
    lists: the ordered positional parameters, without the receiver of a method that is not a
    ``staticmethod`` whatever its name, and every parameter's name. A name defined twice with
    the same lists appears once."""
    receivers = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for method in node.body:
                if (isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and "staticmethod" not in {_final(d) for d in method.decorator_list}):
                    receivers.add(method)
    definitions: Dict[str, List[Tuple[Tuple[str, ...], FrozenSet[str]]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        positional = [a.arg for a in list(args.posonlyargs) + list(args.args)]
        skip = 1 if node in receivers and positional else 0
        names = positional[skip:] + [a.arg for a in args.kwonlyargs]
        entry = (tuple(positional[skip:]), frozenset(names))
        lists = definitions.setdefault(node.name, [])
        if entry not in lists:
            lists.append(entry)
    return definitions


def _break_regions(source: str, tree: ast.AST) -> List[Tuple[int, int]]:
    """The line spans an ``INTENTIONAL BREAK`` comment excuses: its own line when it trails
    code, and the next statement when it stands alone -- only the header of a compound
    statement, so a comment above a ``def`` or a block never excuses the body."""
    lines = source.splitlines()
    regions: List[Tuple[int, int]] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (SyntaxError, tokenize.TokenError):
        return regions
    spans: Dict[int, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            body = getattr(node, "body", None)
            end = body[0].lineno - 1 if isinstance(body, list) and body else node.end_lineno
            spans[node.lineno] = max(spans.get(node.lineno, node.lineno), end)
    for token in tokens:
        if not (token.type == tokenize.COMMENT and BREAK_MARK in token.string):
            continue
        line = token.start[0]
        if lines[line - 1][:token.start[1]].strip():
            regions.append((line, line))
            continue
        following = [start for start in spans if start > line]
        if following:
            start = min(following)
            regions.append((start, spans[start]))
    return regions


def boundary_unit_scan(root: Path, python: Sequence[str]) -> Tuple[Dict[str, int],
                                                                   List[List[str]]]:
    """How many boundary edges the I3 rule examined, and each call in ``jnwb/`` that passes a
    bare name whose suffix differs from the callee parameter's suffix, as sorted
    [path:line, reason] pairs.

    A definition is every function or method defined in a tracked ``.py`` file under
    ``jnwb/``, by name, with its parameter names in order (``_boundary_definitions``). A call
    whose callee -- a bare name or an attribute's own name, ``g`` in ``C().g`` -- names a
    definition is read by
    its arguments: an argument whose value is a bare ``Name`` whose suffix
    (``BOUNDARY_SUFFIXES``, longest match) differs from the parameter's suffix at the same
    keyword or position is a finding. A name defined more than once with different parameter
    lists is skipped for positional arguments only; an argument that is an expression is the
    conversion, not examined. A call on a line an ``INTENTIONAL BREAK`` comment holds, or in
    the statement such a comment stands above (``_break_regions``), is excused and counted
    apart.
    """
    files = [rel for rel in python if rel.startswith(JNWB_PACKAGE)]
    definitions: Dict[str, List[Tuple[Tuple[str, ...], FrozenSet[str]]]] = {}
    trees: Dict[str, ast.AST] = {}
    for rel in files:
        trees[rel] = ast.parse((root / rel).read_text(encoding="utf-8"))
        for name, lists in _boundary_definitions(trees[rel]).items():
            definitions.setdefault(name, []).extend(lists)
    examined: Dict[str, int] = {"edges": 0, "excused": 0}
    found: List[List[str]] = []
    for rel in files:
        regions = _break_regions((root / rel).read_text(encoding="utf-8"), trees[rel])
        excused = lambda line: any(start <= line <= end for start, end in regions)  # noqa: E731
        for node in ast.walk(trees[rel]):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            callee = func.attr if isinstance(func, ast.Attribute) else _final(func)
            lists = definitions.get(callee)
            if lists is None:
                continue
            for keyword in node.keywords:
                param, value = keyword.arg, keyword.value
                if param is None or not isinstance(value, ast.Name):
                    continue
                if not any(param in names for _, names in lists):
                    continue
                psuffix, vsuffix = _boundary_suffix(param), _boundary_suffix(value.id)
                if psuffix is None or vsuffix is None:
                    continue
                examined["edges"] += 1
                if psuffix == vsuffix or excused(value.lineno):
                    if psuffix != vsuffix:
                        examined["excused"] += 1
                    continue
                found.append([f"{rel}:{value.lineno}",
                              f"{value.id} ({vsuffix}) reaches {callee}({param}) ({psuffix})"])
            if len(lists) != 1:
                continue  # ambiguous: positional arguments are skipped
            positional = lists[0][0]
            for index, arg in enumerate(node.args):
                if index >= len(positional) or not isinstance(arg, ast.Name):
                    continue
                psuffix, vsuffix = _boundary_suffix(positional[index]), _boundary_suffix(arg.id)
                if psuffix is None or vsuffix is None:
                    continue
                examined["edges"] += 1
                if psuffix == vsuffix or excused(arg.lineno):
                    if psuffix != vsuffix:
                        examined["excused"] += 1
                    continue
                found.append([f"{rel}:{arg.lineno}",
                              f"{arg.id} ({vsuffix}) reaches "
                              f"{callee}({positional[index]}) ({psuffix})"])
    return examined, sorted(found)


# ----------------------------------------------------------------------- owned rules

#: Each rule with its owner (module path, qualified name) and the signature expression the scan
#: matches; that expression outside its owner is a retyped rule.
OWNED_RULES: Tuple[Tuple[str, str, str, str], ...] = (
    ("dB aggregation", "jnwb/spectral/_decibels.py", "aggregate_to_db",
     "10 * log10 of an average, or to_db of an average"),
    ("R2", "jnwb/_spread.py", "r_squared", "1 - A / B"),
    ("robust z, MAD with a mean-absolute-deviation fallback", "jnwb/artifact_detection.py",
     "_robust_z_zero_fallback", "a MAD scale and mean(abs(d)) * 1.253314 in one function"),
    ("robust z, MAD with a standard-deviation fallback", "jnwb/laminar_curation.py",
     "_robust_z_std_fallback", "a MAD scale and a standard deviation in one function"),
    ("FDR", "jnwb/statistics/_analysis.py", "StatisticalAnalysis.fdr_correct",
     "false_discovery_control(...)"),
    ("Clopper-Pearson", "jnwb/statistics/_tests.py", "clopper_pearson",
     "beta.ppf whose first argument divides by 2"),
    ("percentile bootstrap", "jnwb/_spread.py", "percentile_interval",
     "a percentile interval: two levels in a list, or two calls on one array"),
    ("robust z, MAD with an absolute floor of 1e-9", "jnwb/artifact_repair.py",
     "_floored_robust_z", "a MAD scale floored by np.where(s < 1e-9, 1e-9, s)"),
    ("robust z, pooled MAD scale, zero-guarded at the call site", "jnwb/artifact_repair.py",
     "_pooled_robust_z", "a residual over 1.4826 * scale"),
    ("modified z, 0.6745 over the median deviation", "jnwb/unit_quality.py",
     "_modified_z", "0.6745 * deviation over the median of the deviation"),
)
#: R2 matches that are not a coefficient of determination, each read by hand:
#: (module path, enclosing function, expression text) -> reason.
R2_EXEMPT: Dict[Tuple[str, str, str], str] = {
    ("docs/generate_figures.py", "_inches_axes", "1 - (top + height) / h"):
        "the figure fraction of an axes' bottom edge, measured from the top",
    ("jnwb/jrsa/_inference.py", "_one_sided_parametric_p", "1.0 - p2 / 2.0"):
        "the one-sided p-value on the side away from the effect",
    ("jnwb/statistics/_tests.py", "clopper_pearson", "1.0 - alpha / 2.0"):
        "the upper Beta quantile of the Clopper-Pearson interval",
    ("jnwb/testing/synth.py", "synth_laminar_motif",
     "1.0 - (ch - c_crossover) / max(n_channels - 1 - c_crossover, 1.0)"):
        "a linear weight across the channels of a synthetic laminar profile",
    ("jnwb/unit_quality.py", "refractory_contamination",
     "1.0 - 2.0 * n_v * total / ((tau_r - tau_c) * n * n)"):
        "the discriminant of the quadratic in the refractory-period contamination estimate",
    ("jnwb/vis/canvas.py", "PlotlyPublicationCanvas._compute_domains",
     "1.0 - row_y_top_px[r] / H"):
        "a plotly domain coordinate of a row's top edge",
    ("jnwb/vis/canvas.py", "PlotlyPublicationCanvas._compute_domains",
     "1.0 - (row_y_top_px[r] + row_heights_px[r]) / H"):
        "a plotly domain coordinate of a row's bottom edge",
}
#: Percentile intervals that are not bootstraps, each read by hand, keyed as R2_EXEMPT.
PERCENTILE_EXEMPT: Dict[Tuple[str, str, str], str] = {
    ("jnwb/statistics/_regression.py", "shuffle_r2_ci", "np.percentile(null, 2.5)"):
        "a shuffle null interval, not a bootstrap",
    ("jnwb/statistics/_regression.py", "shuffle_r2_ci", "np.percentile(null, 97.5)"):
        "a shuffle null interval, not a bootstrap",
}
REVIEWED_EXEMPT: Dict[str, Dict[Tuple[str, str, str], str]] = {
    "R2": R2_EXEMPT,
    "percentile bootstrap": PERCENTILE_EXEMPT,
}
#: Modules whose figure functions are read: the docs figure generators and the plotting modules.
FIGURE_FILES = ("docs/generate_figures.py", "jnwb/visual_qc.py")
FIGURE_TREES = ("jnwb/vis/",)
#: Code the scan reads, as (tree prefix, suffix): the package, the docs generators, the examples
#: (scripts and notebooks) and the skills' python fences.
OWNED_SCOPE = (("jnwb/", ".py"), ("docs/", ".py"), ("examples/", ".py"), ("examples/", ".ipynb"),
               ("skills/", ".md"))
_PYTHON_FENCE = re.compile(r"^```python[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
_MAGIC_LINE = re.compile(r"^\s*[%!]")
_AVERAGING = ("mean", "nanmean", "average")
_PERCENTILES = ("percentile", "nanpercentile")
_MAD = ("median", "nanmedian")
_MEAN_AD = ("mean", "nanmean")
_SD = ("std", "nanstd")


def _is_number(node: ast.AST, values: Tuple[float, ...]) -> bool:
    return (isinstance(node, ast.Constant) and not isinstance(node.value, bool)
            and node.value in values)


def _scopes(tree: ast.AST) -> Dict[ast.AST, str]:
    """Each node's innermost enclosing function or class, by qualified name (``""`` at module
    level)."""
    scope: Dict[ast.AST, str] = {}

    def visit(node: ast.AST, qualname: str) -> None:
        for child in ast.iter_child_nodes(node):
            scope[child] = qualname
            inner = qualname
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                inner = f"{qualname}.{child.name}" if qualname else child.name
            visit(child, inner)

    visit(tree, "")
    return scope


def _averages(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Call) and _final(n.func) in _AVERAGING for n in ast.walk(node))


def _statistic_of_abs(node: ast.AST, statistics: Tuple[str, ...], constant: float,
                      name: str) -> bool:
    """Whether ``node`` is ``statistic(abs(...)) * scale``, the scale being ``constant`` or the
    name ``name``."""
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult)):
        return False
    for call, scale in ((node.left, node.right), (node.right, node.left)):
        if (isinstance(call, ast.Call) and _final(call.func) in statistics and call.args
                and any(isinstance(n, ast.Call) and _final(n.func) == "abs"
                        for n in ast.walk(call.args[0]))
                and (_is_number(scale, (constant,))
                     or (isinstance(scale, ast.Name) and scale.id == name))):
            return True
    return False


def _db_nodes(tree: ast.AST, parents: Dict[ast.AST, ast.AST]):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        times = parents.get(node)
        if _final(node.func) == "to_db" and _averages(node.args[0]):
            yield node
        elif (_final(node.func) == "log10" and _averages(node.args[0])
              and isinstance(times, ast.BinOp) and isinstance(times.op, ast.Mult)
              and (_is_number(times.left, (10, 20)) or _is_number(times.right, (10, 20)))):
            yield node


def _r2_nodes(tree: ast.AST):
    for node in ast.walk(tree):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub)
                and _is_number(node.left, (1,))
                and isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Div)):
            yield node


def _mad_scopes(tree: ast.AST, scope: Dict[ast.AST, str]) -> set:
    """The functions that take a MAD scale, read as ``median(abs(d)) * 1.4826``."""
    return {scope.get(node, "") for node in ast.walk(tree)
            if _statistic_of_abs(node, _MAD, 1.4826, "MAD_SCALE")}


def _robust_z_nodes(tree: ast.AST, scope: Dict[ast.AST, str]):
    """The fallbacks of a robust z: the mean-absolute-deviation scale and a standard deviation,
    read in a function that also takes a MAD scale."""
    mad_scopes = _mad_scopes(tree, scope)
    for node in ast.walk(tree):
        if scope.get(node, "") not in mad_scopes:
            continue
        if _statistic_of_abs(node, _MEAN_AD, 1.253314, "MEAN_AD_SCALE"):
            yield node, "robust z, MAD with a mean-absolute-deviation fallback"
        elif isinstance(node, ast.Call) and _final(node.func) in _SD:
            yield node, "robust z, MAD with a standard-deviation fallback"


def _floor_nodes(tree: ast.AST, scope: Dict[ast.AST, str]):
    """The 1e-9 floor of a MAD scale, ``np.where(s < 1e-9, 1e-9, s)``, in a function that
    takes one."""
    mad_scopes = _mad_scopes(tree, scope)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _final(node.func) == "where" and len(node.args) == 3
                and scope.get(node, "") in mad_scopes):
            continue
        test, floor, kept = node.args
        if (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Lt)
                and _is_number(test.comparators[0], (1e-9,)) and _is_number(floor, (1e-9,))
                and ast.unparse(kept) == ast.unparse(test.left)):
            yield node


def _pooled_nodes(tree: ast.AST):
    """A residual over ``1.4826 * scale``: the normal-consistent MAD of a pooled scale."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                and isinstance(node.right, ast.BinOp) and isinstance(node.right.op, ast.Mult)
                and (_is_number(node.right.left, (1.4826,))
                     or _is_number(node.right.right, (1.4826,)))):
            yield node


def _modified_nodes(tree: ast.AST):
    """``0.6745 * d / median(d)``: the modified z-score of a deviation, with no fallback."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                and isinstance(node.left, ast.BinOp) and isinstance(node.left.op, ast.Mult)
                and (_is_number(node.left.left, (0.6745,))
                     or _is_number(node.left.right, (0.6745,)))
                and isinstance(node.right, ast.Call) and _final(node.right.func) in _MAD):
            yield node


def _owned_nodes(source: str) -> List[Tuple[int, str, str, str]]:
    """Each node in one module that matches a registered expression, as (line, enclosing
    function, rule, expression text), before owners and exemptions are removed."""
    tree = ast.parse(source)
    bound = _bindings(tree)
    scope = _scopes(tree)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    found = [(node, "dB aggregation") for node in _db_nodes(tree, parents)]
    found += [(node, "R2") for node in _r2_nodes(tree)]
    found += list(_robust_z_nodes(tree, scope))
    found += [(node, "robust z, MAD with an absolute floor of 1e-9")
              for node in _floor_nodes(tree, scope)]
    found += [(node, "robust z, pooled MAD scale, zero-guarded at the call site")
              for node in _pooled_nodes(tree)]
    found += [(node, "modified z, 0.6745 over the median deviation")
              for node in _modified_nodes(tree)]
    found += [(node, "FDR") for node in ast.walk(tree)
              if isinstance(node, ast.Call) and _target(node.func, bound).endswith(
                  "false_discovery_control")]
    found += [(node, "Clopper-Pearson") for node in ast.walk(tree)
              if isinstance(node, ast.Call) and node.args
              and _target(node.func, bound).endswith("beta.ppf")
              and any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
                      and _is_number(n.right, (2,)) for n in ast.walk(node.args[0]))]
    pairs: Dict[Tuple[str, str], List[ast.AST]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _final(node.func) in _PERCENTILES
                and len(node.args) >= 2):
            continue
        if isinstance(node.args[1], (ast.List, ast.Tuple)):
            if len(node.args[1].elts) == 2:
                found.append((node, "percentile bootstrap"))
        else:
            pairs.setdefault((scope.get(node, ""), ast.unparse(node.args[0])), []).append(node)
    found += [(node, "percentile bootstrap") for group in pairs.values()
              if len(group) >= 2 for node in group]
    return [(node.lineno, scope.get(node, ""), rule, ast.unparse(node)) for node, rule in found]


def owned_rule_sites(path: str, source: str) -> List[str]:
    """Reasons for each registered expression in one module that sits outside its owner and is
    not a reviewed exemption. Raises ``SyntaxError`` on source it cannot parse."""
    owners = {rule: (owner, name) for rule, owner, name, _ in OWNED_RULES}
    reasons = []
    for line, function, rule, text in sorted(_owned_nodes(source)):
        owner, name = owners[rule]
        if (path, function) == (owner, name):
            continue
        if (path, function, text) in REVIEWED_EXEMPT.get(rule, {}):
            continue
        reasons.append(f"line {line}: {function or '<module>'} evaluates {rule} ({text}) "
                       f"outside its owner {owner}:{name}")
    return reasons


def _owned_units(rel: str, text: str) -> List[Tuple[str, str]]:
    """Python sources of one tracked file, each with the prefix its reasons carry: the file,
    each notebook code cell, or each skill python fence."""
    if rel.endswith(".py"):
        return [("", text)]
    if rel.endswith(".ipynb"):
        units = []
        for index, cell in enumerate(json.loads(text)["cells"], 1):
            if cell.get("cell_type") == "code":
                lines = "".join(cell["source"]).splitlines()
                units.append((f"cell {index}, ", "\n".join(
                    line for line in lines if not _MAGIC_LINE.match(line))))
        return units
    return [(f"fence {index}, ", match.group(1))
            for index, match in enumerate(_PYTHON_FENCE.finditer(text), 1)]


def owned_rule_scans(root: Path, tracked: Sequence[str]) -> Tuple[Dict[str, int],
                                                                  Dict[str, List[List[str]]]]:
    """Violations as sorted [file, reason] pairs under ``owned_rules`` and ``figure_owner_calls``,
    and what was examined: python units and figure functions. A unit that cannot be read or
    parsed is a violation, not a skip."""
    examined = {"units": 0, "figure_functions": 0}
    owned: List[List[str]] = []
    figures: List[List[str]] = []
    for rel in tracked:
        if not any(rel.startswith(prefix) and rel.endswith(suffix)
                   for prefix, suffix in OWNED_SCOPE):
            continue
        figure = rel in FIGURE_FILES or rel.startswith(FIGURE_TREES)
        try:
            units = _owned_units(rel, (root / rel).read_text(encoding="utf-8"))
        except (ValueError, KeyError) as error:
            owned.append([rel, f"cannot be read ({error})"])
            continue
        for prefix, source in units:
            try:
                reasons = owned_rule_sites(rel, source)
                functions = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                for n in ast.walk(ast.parse(source))) if figure else 0
            except SyntaxError as error:
                owned.append([rel, f"{prefix}cannot be parsed ({error.msg})"])
                continue
            examined["units"] += 1
            examined["figure_functions"] += functions
            owned.extend([rel, f"{prefix}{reason}"] for reason in reasons)
            if figure:
                figures.extend([rel, f"{prefix}{reason}"] for reason in reasons)
    return examined, {"owned_rules": sorted(owned), "figure_owner_calls": sorted(figures)}


# ------------------------------------------------------------------------ generated graph


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _kind(obj: Any) -> str:
    if isinstance(obj, types.ModuleType):
        return "module"
    if inspect.isclass(obj):
        return "class"
    if callable(obj):
        return "function"
    return "constant"


def _signature(obj: Any) -> Optional[str]:
    if not callable(obj) or isinstance(obj, types.ModuleType):
        return None
    try:
        return _ADDRESS.sub("", str(inspect.signature(obj)))
    except (TypeError, ValueError):
        return None


def _package_rel(path: Path, package: Any) -> str:
    """``path`` relative to the directory holding the package, so ``jnwb/<module>.py`` whether
    the package is the source tree or an installed copy in site-packages."""
    return path.resolve().relative_to(Path(package.__file__).resolve().parent.parent).as_posix()


def _module_file(obj: Any, package: Any, root: Path) -> str:
    """The source file that defines ``obj``; the package's own ``__init__`` when unknown."""
    target = obj if isinstance(obj, types.ModuleType) else sys.modules.get(
        getattr(obj, "__module__", "") or "")
    location = getattr(target, "__file__", None) or package.__file__
    try:
        return _package_rel(Path(location), package)
    except ValueError:
        return _package_rel(Path(package.__file__), package)


def _exports(package: Any, root: Path, switches: Sequence[str]):
    exports: Dict[str, Dict[str, Any]] = {}
    implements: List[List[str]] = []
    for name in sorted(package.__all__):
        try:
            obj = getattr(package, name)
        except ImportError:
            # A subpackage behind an optional extra: recorded from its source, so the graph is
            # the same whichever extras the building interpreter has.
            source = Path(package.__file__).parent / name / "__init__.py"
            if not source.is_file():
                raise
            exports[name] = {"kind": "module", "signature": None, "switches": []}
            implements.append([_package_rel(source, package), name])
            continue
        signature = _signature(obj)
        params: List[str] = []
        if signature is not None:
            try:
                params = list(inspect.signature(obj).parameters)
            except (TypeError, ValueError):
                params = []
        exports[name] = {
            "kind": _kind(obj),
            "signature": signature,
            # A dataclass field of a switch's name records what ran and selects nothing; the
            # computational contract gate draws the same line.
            "switches": [p for p in switches if p in params and not _dataclass_field(obj, p)],
        }
        implements.append([_module_file(obj, package, root), name])
    return exports, implements


def _pages(root: Path) -> List[Path]:
    from scripts.harness_gate import GENERATED_REFERENCE

    return [p for p in sorted((root / "docs").rglob("*.md")) if p.name != GENERATED_REFERENCE]


def _documents(pages: Sequence[Path], names: Sequence[str], root: Path) -> List[List[str]]:
    """Each page and each export it names in a heading or a code span on one line. Prose alone
    documents nothing: a name that only the running text mentions is not a documented export.
    Spans are paired within a line, so one fenced block cannot shift the pairs after it."""
    edges = []
    for page in pages:
        marked: List[str] = []
        for line in page.read_text(encoding="utf-8").splitlines():
            if _HEADING_LINE.match(line):
                marked.append(line)
            marked.extend(_LINE_SPAN.findall(line))
        words = set(re.findall(r"\b\w+\b", "\n".join(marked)))
        edges.extend([_rel(page, root), n] for n in names if n in words)
    return edges


def routing_targets(text: str) -> List[str]:
    """Every name ``text`` routes, without the ``jnwb.`` prefix, in the two forms read."""
    targets = []
    for line in text.splitlines():
        if not _ROUTING_LINE.match(line):
            continue
        end = _ROW_HEAD_END.search(line)
        head = line[: end.start() + 1] if end else line
        for span in _BACKTICKED.findall(head):
            match = _JNWB_NAME.match(span)
            if match:
                targets.append(match.group(1).rstrip("."))
    for _, header, rows in _all_tables(text):
        for column, cell in enumerate(header):
            prefix = next((m.group(1) for m in map(_JNWB_NAME.match, _BACKTICKED.findall(cell))
                           if m), None)
            if prefix is None:
                continue
            for row in rows:
                if column >= len(row):
                    continue
                for span in _BACKTICKED.findall(_PARENTHESISED.sub("", row[column])):
                    if _IDENTIFIER.match(span):
                        targets.append(f"{prefix}.{span}")
    return targets


def _routes(root: Path) -> Tuple[List[str], List[List[str]]]:
    skills, edges = [], []
    for path in sorted((root / "skills").glob("*/SKILL.md")):
        skill = path.parent.name
        skills.append(skill)
        parts = [path.read_text(encoding="utf-8")]
        refdir = path.parent / "references"
        if refdir.is_dir():
            parts += [p.read_text(encoding="utf-8") for p in sorted(refdir.glob("*.md"))]
        edges.extend([skill, target]
                     for target in sorted(set(routing_targets("\n".join(parts)))))
    return skills, edges


def resolves_in_source(package_dir: Path, target: str) -> bool:
    """Whether ``target`` names a module under ``package_dir``, or a top-level name one defines.

    Used when importing the target fails because an optional extra is not installed: the
    module then exists on disk but cannot be imported, and the graph must not depend on which
    extras the building interpreter has.
    """
    parts = target.split(".")
    base = package_dir
    for index, part in enumerate(parts):
        if (base / part).is_dir() and (base / part / "__init__.py").is_file():
            base = base / part
            continue
        if (base / f"{part}.py").is_file():
            rest = parts[index + 1:]
            return not rest or (len(rest) == 1 and rest[0] in _top_level_names(base / f"{part}.py"))
        return index > 0 and index == len(parts) - 1 and part in _top_level_names(base / "__init__.py")
    return True


def _top_level_names(path: Path) -> set:
    names = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                names.update(n.id for n in ast.walk(t) if isinstance(n, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


def _route_targets(package: Any, exports: Dict[str, Any], routes: Sequence[Sequence[str]]):
    targets = {}
    for target in sorted({t for _, t in routes}):
        head = target.split(".")[0]
        obj: Any = package
        try:
            for part in target.split("."):
                obj = getattr(obj, part)
            resolves = True
        except AttributeError:
            resolves = False
        except ImportError:
            resolves = resolves_in_source(Path(package.__file__).parent, target)
        targets[target] = {"export": head if head in exports else None, "resolves": resolves}
    return targets


def _is_jnwb(module: Optional[str]) -> bool:
    return bool(module) and (module == "jnwb" or module.startswith("jnwb."))


def references(source: str, names: Sequence[str]) -> List[str]:
    """The names of ``names`` a test module reaches through an import of ``jnwb``.

    Reached: a name imported from ``jnwb`` or a submodule, or read as an attribute anywhere in
    a chain rooted at an imported ``jnwb`` module (``jnwb.NAME``, ``jnwb.sub.NAME``, ``O.NAME``
    after ``import jnwb.sub as O`` or ``from jnwb import sub as O``).
    """
    wanted = set(names)
    tree = ast.parse(source)
    aliases = set()
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_jnwb(alias.name):
                    aliases.add(alias.asname or "jnwb")
        elif isinstance(node, ast.ImportFrom) and _is_jnwb(node.module):
            for alias in node.names:
                if alias.name in wanted:
                    found.add(alias.name)
                else:  # a submodule, or a private helper; its attributes may be exports
                    aliases.add(alias.asname or alias.name)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        chain = []
        value: ast.AST = node
        while isinstance(value, ast.Attribute):
            chain.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name) and value.id in aliases:
            found.update(attr for attr in chain if attr in wanted)
    return sorted(found)


def test_functions(source: str) -> List[str]:
    """Each test function of a module, qualified by its class when it has one."""
    found = []
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test"):
            found.append(node.name)
        elif isinstance(node, ast.ClassDef):
            found.extend(f"{node.name}::{item.name}" for item in node.body
                         if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and item.name.startswith("test"))
    return found


def _tests(root: Path, names: Sequence[str]):
    tests: Dict[str, List[str]] = {}
    verifies: List[List[str]] = []
    for path in sorted((root / "tests").glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        rel = _rel(path, root)
        tests[rel] = sorted(test_functions(source))
        verifies.extend([rel, n] for n in references(source, names))
    return tests, verifies


def _gates() -> Dict[str, str]:
    from scripts import harness_gate

    gates = {}
    for number, run, _ in harness_gate.GATES:
        # A gate adapted by `_one` closes over the check it runs; name that check.
        inner = inspect.getclosurevars(run).nonlocals.get("check", run)
        gates[str(number)] = getattr(inner, "__name__", repr(inner))
    return gates


def _head(root: Path) -> Optional[str]:
    done = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    head = done.stdout.strip()
    return head if done.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", head) else None


def build(package: Any = None, root: Path = REPO_ROOT,
          facts_path: Optional[Path] = None) -> Dict[str, Any]:
    """The fact graph of the tree at ``root`` as a JSON-ready dict."""
    if package is None:
        import jnwb as package

    source = facts_path or FACT_STACK
    facts = load_facts(source)
    python = _tracked_python(root)
    tracked = _tracked_files(root)
    prose, skill_files = _prose_files(tracked), _skill_files(tracked)
    fact_text = source.read_text(encoding="utf-8")
    constants = read_constants(fact_text)
    if "B3 choice names" not in constants:
        raise ValueError("the constants name no B3 choice names")
    exceptions = read_b3_exceptions(fact_text)
    scans = {**_source_scans(root, python, constants),
             **_text_scans(root, prose, skill_files, python, constants)}

    exports, implements = _exports(package, root, EXECUTION_PARAMETERS)
    names = sorted(exports)
    pages = _pages(root)
    skills, routes = _routes(root)
    tests, verifies = _tests(root, names)
    constrains = sorted([holder, fact["id"]] for fact in facts for holder in fact["holders"])
    schemes_examined, schemes = scheme_scan(package)
    rng_examined, rng_violations = rng_scan(package)
    units_examined, unit_conversions = unit_scan(package)
    wrappers_examined, wrapper_defaults = wrapper_scan(package)
    signatures_examined, signature_types = signature_types_scan(package)
    choices_examined, choice_defaults = choice_default_scan(
        package, constants["B3 choice names"], exceptions)
    claim_examined, claim_labels = claim_class_scan(root, python)
    boundary_examined, boundary_edges = boundary_unit_scan(root, python)
    owned_examined, owned_relations = owned_rule_scans(root, tracked)
    references, cites, concerns = read_references(
        (root / "docs" / "references.md").read_text(encoding="utf-8"))

    return {
        "head": _head(root),
        "fact_source": _rel(source, root),
        "entities": {
            "export": exports,
            "skipped_export": _skipped_exports(package),
            "page": [_rel(p, root) for p in pages],
            "python": python,
            "prose": prose,
            "skill_file": skill_files,
            "skill": skills,
            "route_target": _route_targets(package, exports, routes),
            "test": tests,
            "gate": _gates(),
            "fact": {f["id"]: {"table": f["table"], "holders": f["holders"]} for f in facts},
            "reference": references,
            "scheme_examined": schemes_examined,
            "rng_examined": rng_examined,
            "unit_examined": units_examined,
            "wrapper_examined": wrappers_examined,
            "signature_examined": signatures_examined,
            "choice_examined": choices_examined,
            "claim_examined": claim_examined,
            "boundary_examined": boundary_examined,
            "owned_rule_examined": owned_examined["units"],
            "figure_examined": owned_examined["figure_functions"],
        },
        "relations": {
            "implements": sorted(implements),
            "documents": sorted(_documents(pages, names, root)),
            "routes": sorted(routes),
            "verifies": sorted(verifies),
            "cites": cites,
            "concerns": concerns,
            "constrains": constrains,
            "permutation_schemes": schemes,
            "rng_reports": rng_violations,
            "unit_conversions": unit_conversions,
            "wrapper_defaults": wrapper_defaults,
            "signature_types": signature_types,
            "choice_defaults": choice_defaults,
            "claim_class_labels": claim_labels,
            "boundary_units": boundary_edges,
            **owned_relations,
            **scans,
        },
    }


def dumps(graph: Dict[str, Any]) -> str:
    return json.dumps(graph, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _checkout_jnwb():
    """This tree's jnwb, or the copy under ``JNWB_EXPECTED_PACKAGE_ROOT`` when a run names an
    installed copy deliberately; any other copy would be described silently."""
    import os

    import jnwb

    location = Path(jnwb.__file__).resolve()
    expected = Path(os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") or REPO_ROOT).resolve()
    if expected not in location.parents:
        raise RuntimeError(f"imported jnwb from {location}, not from {expected}")
    return jnwb


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=FACT_GRAPH_PATH)
    args = parser.parse_args(argv)
    text = dumps(build(_checkout_jnwb()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(text.encode("utf-8"))
    print(f"wrote {args.out} ({len(text.encode('utf-8'))} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
