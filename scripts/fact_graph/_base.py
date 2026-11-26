"""Shared paths and constants of the fact graph builder."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

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
