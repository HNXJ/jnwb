#!/usr/bin/env python3
"""Build the fact graph: a generated graph of what the tree holds and how it connects.

Entities come from the tree itself:

  export  every name in ``jnwb.__all__``, with its kind, its signature and the execution
          switches it takes (the parameter names ``scripts/computational_contract_gate.py``
          decides, read from there)
  page    every hand-written ``docs/**/*.md`` page (the generated ``docs/api.md`` is left out,
          as harness gate 5 leaves it out)
  skill   every ``skills/*/SKILL.md``
  route_target  every name a skill routes to, with the export its path starts from and whether
          the whole dotted path resolves on the package (``StatisticalAnalysis.fdr_correct``)
  test    every ``tests/test_*.py`` file and the test functions it defines
  gate    every entry of ``scripts/harness_gate.py`` ``GATES``, by number
  fact    every typed row of the fact source, with the holders its ``Held by`` cell names

Relations, each a sorted list of ``[source, target]`` pairs:

  implements  module file -> export it defines
  documents   page -> export it names as a whole word (the rule of harness gate 5)
  routes      skill -> target it routes. Two forms are read: a routing bullet (a line opening
              ``- `jnwb.``) routes every backticked ``jnwb.`` call in its head, before the
              "`: " that ends it, and a call after that colon is a mention; and a table whose
              header cell names a backticked ``jnwb.`` path routes the leading backticked name
              of each cell in that column, under that path (a parenthesised name is a member of
              the module before it, not a route). A route written in any other form is not seen.
  verifies    test file -> export it reaches: ``from jnwb... import NAME``, or ``NAME`` read as
              an attribute of an imported ``jnwb`` module
  constrains  holder -> fact it holds

The facts are the only owned part; everything else is regenerated. The output is a pure
function of the tree: sorted keys and lists, LF endings, no timestamp, and object addresses
stripped from signatures, so two builds at one commit are byte-identical.

The fact source must hold exactly the six fact tables ruled on 2026-09-29, each once, with no
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
import json
import re
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.computational_contract_gate import (  # noqa: E402
    EXECUTION_PARAMETERS,
    _dataclass_field,
)

FACT_GRAPH_PATH = REPO_ROOT / "artifacts" / "fact_graph.json"
FACT_STACK = REPO_ROOT / "artifacts" / "fact_stack.md"
#: Read while the fact stack holds no typed table, and named in every report that reads it.
FACT_DRAFT = REPO_ROOT / "artifacts" / "evidence" / "0.2.8" / "fact_stack_typed_draft.md"
FACT_HEADER = ("ID", "Domain", "Predicate", "Held by", "Ruled")
FACT_TABLES = ("Boundary", "Design", "Identity", "Science", "Skills", "Release")
CONSTANT_HEADER = ("Constant", "Values", "Ruled")

_ADDRESS = re.compile(r" at 0x[0-9A-Fa-f]+")
_BACKTICKED = re.compile(r"`([^`]+)`")
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


def read_facts(text: str) -> List[Dict[str, Any]]:
    """The typed fact rows of ``text``: one dict per row, with its table and its holders.

    Raises ``FactSourceError`` on a fact-like header that is not the fact header, a row of the
    wrong width, or a fact ID used twice.
    """
    facts: List[Dict[str, Any]] = []
    seen: Dict[str, str] = {}
    for table, header, rows in _all_tables(text):
        if tuple(header) != FACT_HEADER:
            if _fact_like(header):
                raise FactSourceError(f"section {table!r}: the table header {header} looks "
                                      f"like a fact table and is not {list(FACT_HEADER)}")
            continue
        for row in rows:
            if len(row) != len(FACT_HEADER):
                raise FactSourceError(f"{table}: a fact row has {len(row)} cells, not "
                                      f"{len(FACT_HEADER)}: {row}")
            fact_id, domain, predicate, held_by, ruled = row
            fact_id = fact_id.strip("`")
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


def fact_source(primary: Path = FACT_STACK, draft: Path = FACT_DRAFT) -> Path:
    """``primary`` when it holds a fact table, else ``draft``.

    A primary whose fact-like tables do not parse is refused, never passed over: read_facts
    raises on it before the draft is considered.
    """
    if primary.is_file() and read_facts(primary.read_text(encoding="utf-8")):
        return primary
    if draft.is_file():
        return draft
    raise FactSourceError(f"no fact table in {primary}, and no draft at {draft}")


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


def _module_file(obj: Any, package: Any, root: Path) -> str:
    """The source file that defines ``obj``; the package's own ``__init__`` when unknown."""
    target = obj if isinstance(obj, types.ModuleType) else sys.modules.get(
        getattr(obj, "__module__", "") or "")
    location = getattr(target, "__file__", None) or package.__file__
    try:
        return _rel(Path(location), root)
    except ValueError:
        return _rel(Path(package.__file__), root)


def _exports(package: Any, root: Path, switches: Sequence[str]):
    exports: Dict[str, Dict[str, Any]] = {}
    implements: List[List[str]] = []
    for name in sorted(package.__all__):
        obj = getattr(package, name)
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
    edges = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        words = set(re.findall(r"\b\w+\b", text))
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
        edges.extend([skill, target]
                     for target in sorted(set(routing_targets(path.read_text(encoding="utf-8")))))
    return skills, edges


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

    source = facts_path or fact_source()
    facts = load_facts(source)

    exports, implements = _exports(package, root, EXECUTION_PARAMETERS)
    names = sorted(exports)
    pages = _pages(root)
    skills, routes = _routes(root)
    tests, verifies = _tests(root, names)
    constrains = sorted([holder, fact["id"]] for fact in facts for holder in fact["holders"])

    return {
        "head": _head(root),
        "fact_source": _rel(source, root),
        "entities": {
            "export": exports,
            "page": [_rel(p, root) for p in pages],
            "skill": skills,
            "route_target": _route_targets(package, exports, routes),
            "test": tests,
            "gate": _gates(),
            "fact": {f["id"]: {"table": f["table"], "holders": f["holders"]} for f in facts},
        },
        "relations": {
            "implements": sorted(implements),
            "documents": sorted(_documents(pages, names, root)),
            "routes": sorted(routes),
            "verifies": sorted(verifies),
            "constrains": constrains,
        },
    }


def dumps(graph: Dict[str, Any]) -> str:
    return json.dumps(graph, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _checkout_jnwb():
    """This tree's jnwb; a copy in site-packages would be described silently."""
    import jnwb

    location = Path(jnwb.__file__).resolve()
    if REPO_ROOT.resolve() not in location.parents:
        raise RuntimeError(f"imported jnwb from {location}, not from this tree ({REPO_ROOT})")
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
