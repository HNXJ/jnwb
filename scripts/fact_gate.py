#!/usr/bin/env python3
"""Fact gate: every typed fact is HELD, VIOLATED or UNHELD on the generated fact graph.

The facts are read from ``artifacts/fact_stack.md``, and the constants they use from the same
file. Each fact's ``Held by`` cell names its holders:

  ``gate:N``          resolves when harness gate N exists
  ``test:PATH``       resolves when that test module exists; ``test:PATH::NAME`` when that test
                      function (``Class::name`` inside a class, or a whole ``Class``) exists
  ``computed:NAME``   a predicate below, evaluated on the fact graph
  ``todo:ITEM``       the fact is UNHELD, and ITEM must be a live todo item: one in the
                      todo stack or a readable row of ``artifacts/roadmap.md``

A fact is VIOLATED when a computed predicate is false, a holder does not resolve, a ``todo:``
names no live item, or it names no holder at all; UNHELD when it names a live ``todo:`` item;
HELD otherwise. VIOLATED fails the gate. A ``gate:`` or ``test:`` holder is resolved, not run:
the harness and the suite run those, so a fact held by a failing gate reads HELD here while the
harness around it fails.

Computed predicates:

  lifecycle   each export, and each routing target, passes through the states of the
              ``lifecycle`` constant in order: a state holds only when every earlier one holds.
              ``implemented`` the name is in ``jnwb.__all__``; ``identity-verified`` every
              execution switch it takes is named in the ``identity tests`` constant and that
              module reaches it (vacuous without a switch); ``documented`` a hand-written page
              names it; ``tested`` a test module reaches it; ``routed`` a skill routes to it.
              Reaching is an import from ``jnwb`` or an attribute of the imported package, so a
              test that reaches an operation only through a string or ``getattr`` does not count.
              A dotted target counts as documented, tested and identity-verified when its export
              does.
  routes      every routing target starts at an export of ``jnwb.__all__`` and its whole dotted
              path resolves on the package. Only the two routing forms the graph builder reads
              are seen.
  partition   no routed operation belongs to two shipped domain skills (every skill but the
              router, ``jnwb``), and each owns at least ``k`` of them. A router row naming an
              operation does not share it with the domain skill that owns it.
   routed_citations  every routing target that is a public function (export kind
               function/class) is cited by a reference: it has a ``cites`` edge. Utility
               exports are listed like the rest; no name is excluded.

  global_seeds     no tracked file seeds the global random state (the graph's ``global_seeds``)
  rng_parameters   every function in ``jnwb/`` or ``scripts/`` that draws from a random module
                   takes an ``rng`` parameter (the graph's ``rng_parameters``)
  db_averages      no average in ``jnwb/`` takes a dB value (the graph's ``db_averages``)
  immunity_vocabulary  no sentence of a tracked text file outside ``PROSE_EXEMPT`` (the trees
                   ``tests/`` and ``artifacts/``, and the two rule files) (a page, a script's
                   comment or docstring, a notebook cell, any file under
                   ``skills/`` or ``.github/``) holds the ``immunity vocabulary`` constant or the
                   graph's immunity patterns beside a term of ``IMMUNITY_CONTEXT``, unless a
                   negation (``not``, ``no``, ``never``, ``nor``, ``without``) precedes the value
                   in its clause (the graph's ``immunity_vocabulary``); the gate prints the file
                   count it examined
  skill_contracts  no sentence of a skill names a manifest or receipt, or a plural, beside a
                   contract, schema, must-write, must-produce, required-fields or "must contain,
                   include, list or record ... fields" term, unless it names inspect, Result, Provenance or Lineage and says the
                   contract is carried by or extends it (the graph's ``skill_contracts``)
  silent_handlers  no except handler in ``jnwb/`` swallows its exception: its body raises,
                   warns, or logs a warning, error or exception, calls a function of its module
                   or of a relative import whose own body does, or reads the bound exception
                   name; a handler for ImportError or ModuleNotFoundError alone is exempt (the
                   graph's ``silent_handlers``)
  permutation_schemes  no public callable draws a null (a permutation, shuffle, circular shift,
                   surrogate, derangement or sign flip) without a scheme key in its result (the
                   graph's ``permutation_schemes``); an examined count of zero is a failure
  rng_reports  no public callable consumes randomness (a call to one of the ``RESOLVERS``
                   of ``jnwb/_rng.py``) without an rng key in its result
                   (the graph's ``rng_reports``); an examined count of zero is a failure

Exit code 0 when no fact is VIOLATED, 1 otherwise.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
# Under JNWB_EXPECTED_PACKAGE_ROOT the checkout goes last, so the copy it names wins.
if os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
    if str(REPO_ROOT) not in sys.path:
        sys.path.append(str(REPO_ROOT))
elif str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_fact_graph  # noqa: E402
from scripts.release_gate import ROADMAP_PATH as _ROADMAP, roadmap_rows  # noqa: E402
from scripts.stack_parse import parse_todo_stack  # noqa: E402

TODO_PATH = REPO_ROOT / "artifacts" / "todo_stack.md"
ROADMAP_PATH = REPO_ROOT / _ROADMAP

HELD, VIOLATED, UNHELD = "HELD", "VIOLATED", "UNHELD"

Graph = Dict[str, Any]
Constants = Dict[str, List[str]]


def live_items(todo_text: str, roadmap_text: str = "") -> List[str]:
    """Item ids in the todo stack, read by the shared stack parser at every heading form, then those
    of the roadmap's readable rows."""
    return ([i for i, _, _ in parse_todo_stack(todo_text)[0]]
            + [i for i, _ in roadmap_rows(roadmap_text)[0]])


# ------------------------------------------------------------------------ computed predicates


def _states(graph: Graph, constants: Constants) -> Dict[str, Dict[str, Optional[bool]]]:
    """Each name's value for every state of the ``lifecycle`` constant; None where a state
    does not apply (``identity-verified`` without an execution switch)."""
    order = constants["lifecycle"]
    identity = dict(value.split("=", 1) for value in constants["identity tests"])
    exports = graph["entities"]["export"]
    targets = graph["entities"]["route_target"]
    rel = graph["relations"]
    documented = {name for _, name in rel["documents"]}
    reached: Dict[str, set] = {}
    for test, name in rel["verifies"]:
        reached.setdefault(name, set()).add(test)
    routed = {target for _, target in rel["routes"]}

    def export_of(name: str) -> Optional[str]:
        if name in exports:
            return name
        return targets.get(name, {}).get("export")

    def implemented(name: str) -> bool:
        return name in exports or bool(export_of(name) and targets[name]["resolves"])

    def identity_verified(name: str) -> Optional[bool]:
        switches = exports.get(export_of(name) or "", {}).get("switches", [])
        if not switches:
            return None
        found = reached.get(export_of(name) or "", set())
        return all(s in identity and identity[s] in found for s in switches)

    tests = {
        "implemented": implemented,
        "identity-verified": identity_verified,
        "documented": lambda n: export_of(n) in documented,
        "tested": lambda n: bool(reached.get(export_of(n) or "")),
        "routed": lambda n: n in routed,
    }
    unknown = [state for state in order if state not in tests]
    if unknown:
        raise ValueError(f"the lifecycle constant names states no predicate evaluates: {unknown}")
    return {name: {state: tests[state](name) for state in order}
            for name in sorted(set(exports) | routed)}


def lifecycle(graph: Graph, constants: Constants) -> List[str]:
    """Each name holding a lifecycle state while an earlier applicable state fails."""
    order = constants["lifecycle"]
    found = []
    for name, state in _states(graph, constants).items():
        for i, later in enumerate(order):
            missing = [s for s in order[:i] if state[s] is False]
            if state[later] and missing:
                found.append(f"{name} is {later} but not {', '.join(missing)}")
                break
    return found


def routes(graph: Graph, constants: Constants) -> List[str]:
    """Each routing target that does not start at an export or does not resolve."""
    found = []
    for target, record in sorted(graph["entities"]["route_target"].items()):
        if record["export"] is None:
            found.append(f"{target} does not start at an export of jnwb.__all__")
        elif not record["resolves"]:
            found.append(f"{target} does not resolve on the package")
    return found


ROUTER_SKILL = "jnwb"


def _owners(graph: Graph) -> Dict[str, set]:
    """Each routed target and the domain skills that route it."""
    domain = [skill for skill in graph["entities"]["skill"] if skill != ROUTER_SKILL]
    owners: Dict[str, set] = {}
    for skill, target in graph["relations"]["routes"]:
        if skill in domain:
            owners.setdefault(target, set()).add(skill)
    return owners


def exclusive_counts(graph: Graph) -> Dict[str, int]:
    """Each domain skill's count of routed targets that no other domain skill routes."""
    domain = [skill for skill in graph["entities"]["skill"] if skill != ROUTER_SKILL]
    owners = _owners(graph)
    counts = {skill: 0 for skill in domain}
    for owning in owners.values():
        if len(owning) == 1:
            counts[next(iter(owning))] += 1
    return counts


def partition(graph: Graph, constants: Constants) -> List[str]:
    """Each operation two domain skills route, and each domain skill owning fewer than ``k``
    exclusive operations; no domain skill at all is itself a failure, never an empty pass."""
    if "k" not in constants:
        raise ValueError("the constants name no k, the skill-partition floor")
    floor = int(constants["k"][0])
    counts = exclusive_counts(graph)
    if not counts:
        return ["the graph names no domain skill"]
    shared = [f"{target} is routed by {', '.join(sorted(owning))}"
              for target, owning in sorted(_owners(graph).items()) if len(owning) > 1]
    return shared + [f"{skill} owns {count} exclusive operations, fewer than {floor}"
                     for skill, count in sorted(counts.items()) if count < floor]


def global_seeds(graph: Graph, constants: Constants) -> List[str]:
    """Each call, in any tracked file, that seeds the global random state."""
    if not graph["entities"].get("python"):
        return ["the graph reads no python file"]
    return [f"{path}: {reason}" for path, reason in graph["relations"]["global_seeds"]]


def rng_parameters(graph: Graph, constants: Constants) -> List[str]:
    """Each function in ``jnwb/`` or ``scripts/`` that draws from a random module and takes no
    parameter named ``rng``."""
    python = graph["entities"].get("python", [])
    if not any(path.startswith(build_fact_graph.SCANNED_FOR_RNG) for path in python):
        return ["the graph reads no jnwb or scripts python file"]
    return [f"{path}: {reason}" for path, reason in graph["relations"]["rng_parameters"]]


def db_averages(graph: Graph, constants: Constants) -> List[str]:
    """Each average in ``jnwb/`` of a dB value, or of a name a dB conversion was assigned to."""
    python = graph["entities"].get("python", [])
    if not any(path.startswith(build_fact_graph.DB_PACKAGE) for path in python):
        return ["the graph reads no jnwb python file"]
    return [f"{path}: {reason}" for path, reason in graph["relations"]["db_averages"]]


def immunity_vocabulary(graph: Graph, constants: Constants) -> List[str]:
    """Each sentence of a tracked text file in scope that holds the immunity vocabulary beside a
    context term."""
    if not graph["entities"].get("prose"):
        return ["the graph reads no prose file"]
    return [f"{path}: {reason}" for path, reason in graph["relations"]["immunity_vocabulary"]]


def scope_line(graph: Graph) -> str:
    """The number of text files the immunity rule examined, and the trees it exempts."""
    return (f"immunity_vocabulary examined {len(graph['entities'].get('prose', []))} text files; "
            f"exempt: {', '.join(build_fact_graph.PROSE_EXEMPT)}")


def skill_contracts(graph: Graph, constants: Constants) -> List[str]:
    """Each skill sentence that names a manifest or receipt, or a plural, beside a contract term,
    unless a carrier is named and the sentence says the contract is carried by or extends it."""
    if not graph["entities"].get("skill_file"):
        return ["the graph reads no skill file"]
    return [f"{path}: {reason}" for path, reason in graph["relations"]["skill_contracts"]]


def silent_handlers(graph: Graph, constants: Constants) -> List[str]:
    """Each except handler in ``jnwb/`` that swallows its exception."""
    python = graph["entities"].get("python", [])
    if not any(path.startswith(build_fact_graph.JNWB_PACKAGE) for path in python):
        return ["the graph reads no jnwb python file"]
    return [f"{path}: {reason}" for path, reason in graph["relations"]["silent_handlers"]]


def permutation_schemes(graph: Graph, constants: Constants) -> List[str]:
    """Each public callable that draws a null without a scheme key in its result, and the
    failure of a scan that examined no callable."""
    if not graph["entities"].get("scheme_examined"):
        return ["the graph examined no public callable, so no scheme could be checked"]
    return [f"{name}: {reason}" for name, reason in graph["relations"]["permutation_schemes"]]


def rng_reports(graph: Graph, constants: Constants) -> List[str]:
    """Each public callable that consumes randomness without an rng key in its result, and
    the failure of a scan that examined no callable."""
    if not graph["entities"].get("rng_examined"):
        return ["the graph examined no public callable, so no rng report could be checked"]
    return [f"{name}: {reason}" for name, reason in graph["relations"]["rng_reports"]]


def routed_citations(graph: Graph, constants: Constants) -> List[str]:
    """Each routing target that is a public function (export kind function/class) and has no
    ``cites`` edge, with the skills that route it. Utility exports are listed like the rest;
    no name is excluded."""
    exports = graph["entities"].get("export", {})
    targets = graph["entities"].get("route_target", {})
    if not targets:
        return ["the graph has no routing targets, so no citation could be checked"]
    cited = {name for name, _ in graph["relations"].get("cites", [])}
    # A class is cited through any of its methods (`StatisticalAnalysis.fdr_correct`).
    cited |= {name.split(".")[0] for name in cited if "." in name}
    skills: Dict[str, List[str]] = {}
    for skill, target in graph["relations"].get("routes", []):
        skills.setdefault(target, []).append(skill)
    found = []
    for target in sorted(targets):
        head = targets[target].get("export")
        if head is None or exports.get(head, {}).get("kind") not in ("function", "class"):
            continue
        if target in cited:
            continue
        found.append(f"{target}: routed by {', '.join(sorted(skills.get(target, [])))} "
                     "and cites no reference")
    return found


COMPUTED: Dict[str, Callable[[Graph, Constants], List[str]]] = {
    "lifecycle": lifecycle,
    "routes": routes,
    "partition": partition,
    "routed_citations": routed_citations,
    "global_seeds": global_seeds,
    "rng_parameters": rng_parameters,
    "db_averages": db_averages,
    "immunity_vocabulary": immunity_vocabulary,
    "skill_contracts": skill_contracts,
    "silent_handlers": silent_handlers,
    "permutation_schemes": permutation_schemes,
    "rng_reports": rng_reports,
}


# ------------------------------------------------------------------------ evaluation


def _resolves(holder: str, graph: Graph) -> bool:
    kind, _, target = holder.partition(":")
    entities = graph["entities"]
    if kind == "gate":
        return target in entities["gate"]
    if kind == "test":
        path, _, name = target.partition("::")
        functions = entities["test"].get(path)
        if functions is None:
            return False
        return not name or any(f == name or f.startswith(name + "::") for f in functions)
    return False


def evaluate(facts: Sequence[Dict[str, Any]], constants: Constants, graph: Graph,
             items: Sequence[str]) -> List[Tuple[str, str, List[str]]]:
    """Each fact as (id, status, reasons). Each computed predicate runs once."""
    cache: Dict[str, List[str]] = {}
    results = []
    for fact in facts:
        reasons: List[str] = []
        pending: List[str] = []
        holders = fact["holders"]
        if not holders:
            reasons.append("names no holder")
        for holder in holders:
            kind, _, target = holder.partition(":")
            if kind == "todo":
                if target in items:
                    pending.append(target)
                else:
                    reasons.append(f"todo:{target} is not a live item")
            elif kind == "computed":
                if target not in COMPUTED:
                    reasons.append(f"computed:{target} is no predicate this gate evaluates")
                    continue
                if target not in cache:
                    cache[target] = COMPUTED[target](graph, constants)
                reasons.extend(f"computed:{target}: {v}" for v in cache[target])
            elif not _resolves(holder, graph):
                reasons.append(f"{holder} does not resolve")
        if reasons:
            results.append((fact["id"], VIOLATED, reasons))
        elif pending:
            results.append((fact["id"], UNHELD, [f"held by todo {i}" for i in pending]))
        else:
            results.append((fact["id"], HELD, []))
    return results


def run(package: Any = None, root: Path = REPO_ROOT, facts_path: Optional[Path] = None,
        todo_path: Path = TODO_PATH, graph: Optional[Graph] = None,
        roadmap_path: Path = ROADMAP_PATH):
    """Build the fact graph (unless given) and evaluate every fact of the fact source. A missing
    roadmap holds no item, so a ``todo:`` holder naming one is VIOLATED."""
    source = facts_path or build_fact_graph.FACT_STACK
    facts = build_fact_graph.load_facts(source)
    constants = build_fact_graph.read_constants(source.read_text(encoding="utf-8"))
    if graph is None:
        graph = build_fact_graph.build(package, root, source)
    roadmap = roadmap_path.read_text(encoding="utf-8") if roadmap_path.is_file() else ""
    results = evaluate(facts, constants, graph,
                       live_items(todo_path.read_text(encoding="utf-8"), roadmap))
    return source, results


def summary(results: Sequence[Tuple[str, str, List[str]]]) -> Dict[str, int]:
    return {status: sum(1 for _, s, _ in results if s == status)
            for status in (HELD, UNHELD, VIOLATED)}


def main() -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")
    package = build_fact_graph._checkout_jnwb()
    graph = build_fact_graph.build(package, REPO_ROOT, build_fact_graph.FACT_STACK)
    source, results = run(package, graph=graph)
    print(f"=== Fact gate (facts from {source.relative_to(REPO_ROOT).as_posix()}) ===")
    for fact_id, status, reasons in results:
        print(f"{status}: {fact_id}" + (f" ({'; '.join(reasons)})" if status == UNHELD else ""))
        if status == VIOLATED:
            for reason in reasons:
                print(f"  - {reason}")
    print(scope_line(graph))
    counts = summary(results)
    print(", ".join(f"{status} {n}" for status, n in counts.items()))
    return 1 if counts[VIOLATED] else 0


if __name__ == "__main__":
    sys.exit(main())
