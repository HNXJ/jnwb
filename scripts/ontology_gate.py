#!/usr/bin/env python3
"""Ontology gate: every typed fact is HELD, VIOLATED or UNHELD on the generated ontology.

The facts are read from the fact source ``scripts/build_ontology.py`` names, and the constants
they use from the same file. Each fact's ``Held by`` cell names its holders:

  ``gate:N``          resolves when harness gate N exists
  ``test:PATH``       resolves when that test module exists; ``test:PATH::NAME`` when that test
                      function (``Class::name`` inside a class, or a whole ``Class``) exists
  ``computed:NAME``   a predicate below, evaluated on the ontology
  ``todo:ITEM``       the fact is UNHELD, and ITEM must be a live todo item

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

Exit code 0 when no fact is VIOLATED, 1 otherwise.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_ontology  # noqa: E402

TODO_PATH = REPO_ROOT / "artifacts" / "todo_stack.md"
_ITEM_HEADING = re.compile(r"^### (\d{2}-\d{2,3})\b", re.M)

HELD, VIOLATED, UNHELD = "HELD", "VIOLATED", "UNHELD"


def live_items(todo_text: str) -> List[str]:
    return _ITEM_HEADING.findall(todo_text)


# ------------------------------------------------------------------------ computed predicates


def _states(ontology: Dict[str, Any],
            constants: Dict[str, List[str]]) -> Dict[str, Dict[str, Optional[bool]]]:
    """Each name's value for every state of the ``lifecycle`` constant; None where a state
    does not apply (``identity-verified`` without an execution switch).

    A dotted routing target (``Class.method``) is implemented when its export exists and the
    whole path resolves; it is documented, tested and identity-verified as its export is.
    """
    order = constants["lifecycle"]
    identity = dict(value.split("=", 1) for value in constants["identity tests"])
    exports = ontology["entities"]["export"]
    targets = ontology["entities"]["route_target"]
    rel = ontology["relations"]
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


def lifecycle(ontology: Dict[str, Any], constants: Dict[str, List[str]]) -> List[str]:
    """Each name holding a lifecycle state while an earlier applicable state fails."""
    order = constants["lifecycle"]
    found = []
    for name, state in _states(ontology, constants).items():
        for i, later in enumerate(order):
            missing = [s for s in order[:i] if state[s] is False]
            if state[later] and missing:
                found.append(f"{name} is {later} but not {', '.join(missing)}")
                break
    return found


COMPUTED: Dict[str, Callable[[Dict[str, Any], Dict[str, List[str]]], List[str]]] = {
    "lifecycle": lifecycle,
}


# ------------------------------------------------------------------------ evaluation


def _resolves(holder: str, ontology: Dict[str, Any]) -> bool:
    kind, _, target = holder.partition(":")
    entities = ontology["entities"]
    if kind == "gate":
        return target in entities["gate"]
    if kind == "test":
        path, _, name = target.partition("::")
        functions = entities["test"].get(path)
        if functions is None:
            return False
        return not name or any(f == name or f.startswith(name + "::") for f in functions)
    return False


def evaluate(facts: Sequence[Dict[str, Any]], constants: Dict[str, List[str]],
             ontology: Dict[str, Any], items: Sequence[str]) -> List[Tuple[str, str, List[str]]]:
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
                    cache[target] = COMPUTED[target](ontology, constants)
                reasons.extend(f"computed:{target}: {v}" for v in cache[target])
            elif not _resolves(holder, ontology):
                reasons.append(f"{holder} does not resolve")
        if reasons:
            results.append((fact["id"], VIOLATED, reasons))
        elif pending:
            results.append((fact["id"], UNHELD, [f"held by todo {i}" for i in pending]))
        else:
            results.append((fact["id"], HELD, []))
    return results


def run(package: Any = None, root: Path = REPO_ROOT, facts_path: Optional[Path] = None,
        todo_path: Path = TODO_PATH, ontology: Optional[Dict[str, Any]] = None):
    """Build the ontology (unless given) and evaluate every fact of the fact source."""
    source = facts_path or build_ontology.fact_source()
    text = source.read_text(encoding="utf-8")
    if ontology is None:
        ontology = build_ontology.build(package, root, source)
    results = evaluate(build_ontology.read_facts(text), build_ontology.read_constants(text),
                       ontology, live_items(todo_path.read_text(encoding="utf-8")))
    return source, results


def summary(results: Sequence[Tuple[str, str, List[str]]]) -> Dict[str, int]:
    return {status: sum(1 for _, s, _ in results if s == status)
            for status in (HELD, UNHELD, VIOLATED)}


def main() -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")
    source, results = run(build_ontology._checkout_jnwb())
    print(f"=== Ontology gate (facts from {source.relative_to(REPO_ROOT).as_posix()}) ===")
    for fact_id, status, reasons in results:
        print(f"{status}: {fact_id}" + (f" ({'; '.join(reasons)})" if status == UNHELD else ""))
        if status == VIOLATED:
            for reason in reasons:
                print(f"  - {reason}")
    counts = summary(results)
    print(", ".join(f"{status} {n}" for status, n in counts.items()))
    return 1 if counts[VIOLATED] else 0


if __name__ == "__main__":
    sys.exit(main())
