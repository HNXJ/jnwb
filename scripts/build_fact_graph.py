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
              a categorized key (``category`` set) is read by the side-effect scans instead;
              a callable whose source cannot be read is a finding, never a pass
   delegation  callable -> a public callable with two or more distinct tail-call
               (``return f(...)``) targets among public callables (``delegation_scan``)
   nwb_side_effects  callable -> a public callable reaching a file write, transform or
               repair sink (``NWB_SINKS``) whose declaration carries no single category of
               the ``mutation categories`` constant, or a categorized declaration whose key
               reaches no such sink (``nwb_side_effects_scan``)
   cache_side_effects  callable -> a public callable reaching the cache-write sink
               (``CACHE_SINKS``) whose declaration carries no single category of the
               ``cache categories`` constant, or a categorized declaration whose key
               reaches no such sink (``cache_side_effects_scan``)
   reserved_errors  check -> a missing hold of the two reserved refusal errors
               (``reserved_errors_scan``): defined in ``jnwb/`` and subclassing the base
               mutation error, exported, and documented reserved in ``docs/errors.md``
   documented_guesses  check -> a defaulted table or code-column name, a preferred
               interval table, or a layout basis outside the ``documented guesses``
               constant, or a constant row no longer in the tree
               (``documented_guesses_scan``)
   cache_decisions  call site -> a call to the cache-write or cache-key function in
               ``jnwb/`` (``cache_decisions_scan``); an assigned name that is never
               called is no site
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
              or base suffix (``UNIT_SUFFIXES``, ``BASE_SUFFIXES``), by keyword or position;
              past the suffixes, a value in samples or rows reaching a parameter in seconds or
              the reverse (``TIME_SUFFIXES``, ``SAMPLE_WORDS``, ``ROW_WORDS``), or a rate,
              frame or base default (``RATE_PARAMETERS``, ``FRAME_PARAMETERS``,
              ``BASE_PARAMETERS``) differing across the edge
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
import json
import os
import re
import subprocess
import sys
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

from scripts.fact_graph_parse import (  # noqa: E402, F401
    CORE_HEADER,
    FACT_TABLES,
    FactSourceError,
    METHOD_HEADER,
    PAGE_LINK,
    PITFALL_HEADER,
    REPRODUCTION_HEADER,
    _ADDRESS,
    _BACKTICKED,
    _HEADING_LINE,
    _IDENTIFIER,
    _JNWB_NAME,
    _LINE_SPAN,
    _PARENTHESISED,
    _ROUTING_LINE,
    _ROW_HEAD_END,
    _all_tables,
    load_facts,
    normalize_doi,
    read_b3_exceptions,
    read_constants,
    read_facts,
    read_references,
    reference_functions,
    reference_row_doi,
    reference_rows,
    reference_table_rows,
    require_tables,
)
from scripts.fact_graph_scans import (  # noqa: E402, F401
    DB_PACKAGE,
    HIGHER_CLASS_TERMS,
    I4_OPERATIONS,
    JNWB_PACKAGE,
    LABEL_NAMES,
    OWNED_RULES,
    PROSE_EXEMPT,
    S10_EXCUSED,
    S11_EXCUSED,
    S9_EXCUSED,
    SCANNED_FOR_RNG,
    _GRANGER_METHOD,
    _exempt,
    _passes_rng,
    _phrase,
    _prose_files,
    _public_callables,
    _reach,
    _rel,
    _resolver_call,
    _skill_files,
    _skipped_exports,
    _source_scans,
    _text_scans,
    _tracked_files,
    _tracked_python,
    _unwalked_callables,
    boundary_unit_scan,
    cache_decisions_scan,
    cache_side_effects_scan,
    choice_default_scan,
    claim_class_scan,
    db_average_violations,
    delegation_scan,
    documented_guesses_scan,
    global_seed_calls,
    immunity_scan,
    immunity_violations,
    nwb_side_effects_scan,
    owned_rule_scans,
    owned_rule_sites,
    python_prose,
    reserved_errors_scan,
    rng_scan,
    rng_violations,
    scheme_scan,
    signal_class_scan,
    signature_types_scan,
    silent_handler_sites,
    silent_handler_violations,
    skill_contract_violations,
    unit_scan,
    wrapper_scan,
)

FACT_GRAPH_PATH = REPO_ROOT / "artifacts" / "fact_graph.json"
FACT_STACK = REPO_ROOT / "artifacts" / "fact_stack.md"


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
# ------------------------------------------------------------------------ generated graph


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
    signal_examined, signal_class_findings = signal_class_scan()
    delegation_examined, delegation = delegation_scan(package)
    nwb_examined, nwb_side_effects = nwb_side_effects_scan(
        package, constants["mutation categories"])
    cache_se_examined, cache_side_effects = cache_side_effects_scan(
        package, constants["cache categories"])
    reserved_examined, reserved_errors = reserved_errors_scan(package, root)
    guesses_examined, documented_guesses = documented_guesses_scan(
        root, python, constants["documented guesses"])
    decisions_examined, cache_decisions = cache_decisions_scan(root, python)
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
            "signal_class_examined": signal_examined,
            "delegation_examined": delegation_examined,
            "nwb_side_effects_examined": nwb_examined,
            "cache_side_effects_examined": cache_se_examined,
            "reserved_examined": reserved_examined,
            "guesses_examined": guesses_examined,
            "cache_decisions_examined": decisions_examined,
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
            "signal_class": signal_class_findings,
            "delegation": delegation,
            "nwb_side_effects": nwb_side_effects,
            "cache_side_effects": cache_side_effects,
            "reserved_errors": reserved_errors,
            "documented_guesses": documented_guesses,
            "cache_decisions": cache_decisions,
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
