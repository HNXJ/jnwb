"""The ontology is a pure function of the tree, and the fact gate reports what it establishes.

Each case below builds the situation it is named after on a small synthetic ontology, except the
two live cases, which run on this tree: the gate passes here, and a violation planted into this
tree's own ontology fails it.
"""

from __future__ import annotations

import copy
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts import build_ontology, harness_gate, ontology_gate  # noqa: E402

BUILDER = REPO_ROOT / "scripts" / "build_ontology.py"
#: A synthetic item identifier; the todo text of each fixture declares it live or not.
ITEM = "00-01"

CONSTANTS = {
    "lifecycle": ["implemented", "identity-verified", "documented", "tested", "routed"],
    "identity tests": ["device=tests/test_switch.py"],
}


def ontology(*, routed=("op",), verified=(("tests/test_op.py", "op"),), switches=()):
    """One export `op`, documented; routed and reached by tests as the caller says."""
    return {
        "entities": {
            "export": {"op": {"kind": "function", "signature": "(x)", "switches": list(switches)}},
            "route_target": {t: {"export": "op", "resolves": True} for t in routed},
            "test": {"tests/test_op.py": ["test_op"], "tests/test_switch.py": ["test_switch"]},
            "gate": {"1": "check_one"},
        },
        "relations": {
            "implements": [["jnwb/op.py", "op"]],
            "documents": [["docs/op.md", "op"]],
            "routes": [["jnwb-demo", t] for t in routed],
            "verifies": [list(v) for v in verified],
            "constrains": [],
        },
    }


def fact(*holders):
    return {"id": "X1", "holders": list(holders)}


def status(onto, *holders, constants=CONSTANTS, items=(ITEM,)):
    [(_, found, reasons)] = ontology_gate.evaluate([fact(*holders)], constants, onto, items)
    return found, reasons


def test_two_builds_in_separate_processes_are_byte_identical(tmp_path):
    """Different hash seeds reorder every set; the output must not follow them."""
    digests = []
    for seed in ("1", "2"):
        out = tmp_path / f"ontology_{seed}.json"
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run([sys.executable, str(BUILDER), "--out", str(out)], cwd=REPO_ROOT,
                              env=env, capture_output=True, text=True, timeout=300)
        assert done.returncode == 0, done.stderr
        digests.append(hashlib.sha256(out.read_bytes()).hexdigest())
    assert digests[0] == digests[1]
    assert b"\r\n" not in out.read_bytes()


def test_a_routed_operation_with_no_test_is_violated():
    assert status(ontology(), "computed:lifecycle") == ("HELD", [])
    found, reasons = status(ontology(verified=()), "computed:lifecycle")
    assert found == "VIOLATED"
    assert reasons == ["computed:lifecycle: op is routed but not tested"]


def test_the_lifecycle_order_is_read_from_the_constant():
    """Without `routed` in the constant, the same untested routed operation breaks nothing."""
    short = {**CONSTANTS, "lifecycle": ["implemented", "documented", "tested"]}
    assert status(ontology(verified=()), "computed:lifecycle", constants=short) == ("HELD", [])


def test_a_switch_its_identity_module_does_not_reach_is_violated():
    onto = ontology(switches=("device",))
    found, reasons = status(onto, "computed:lifecycle")
    assert found == "VIOLATED"
    assert reasons == ["computed:lifecycle: op is documented but not identity-verified"]
    onto["relations"]["verifies"].append(["tests/test_switch.py", "op"])
    assert status(onto, "computed:lifecycle") == ("HELD", [])


def test_a_routing_target_that_does_not_resolve_is_violated():
    onto = ontology(routed=("op.missing",))
    onto["entities"]["route_target"]["op.missing"]["resolves"] = False
    found, reasons = status(onto, "computed:lifecycle")
    assert found == "VIOLATED"
    # The first state found holding past the gap is named; here it is its export's documentation.
    assert reasons == ["computed:lifecycle: op.missing is documented but not implemented"]


@pytest.mark.parametrize("holders, reason", [
    (("gate:99",), "gate:99 does not resolve"),
    (("test:tests/test_absent.py",), "test:tests/test_absent.py does not resolve"),
    (("test:tests/test_op.py::test_absent",), "test:tests/test_op.py::test_absent does not resolve"),
    (("computed:absent",), "computed:absent is no predicate this gate evaluates"),
    ((), "names no holder"),
])
def test_a_holder_that_does_not_resolve_is_violated(holders, reason):
    assert status(ontology(), *holders) == ("VIOLATED", [reason])


def test_resolving_holders_are_held():
    assert status(ontology(), "gate:1", "test:tests/test_op.py::test_op") == ("HELD", [])


def test_a_todo_holder_is_unheld_only_while_its_item_is_live():
    assert status(ontology(), "gate:1", f"todo:{ITEM}") == ("UNHELD", [f"held by todo {ITEM}"])
    assert status(ontology(), f"todo:{ITEM}", items=()) == (
        "VIOLATED", [f"todo:{ITEM} is not a live item"])


def test_a_test_reaches_an_export_only_through_an_import_of_the_package():
    source = (
        "import jnwb.ontology as O\n"
        "from jnwb import events\n"
        "from jnwb import vis as V\n"
        "import jnwb\n"
        "O.Question()\n"
        "V.plot_raster\n"
        "jnwb.vis.plot_psth\n"
        "names = ['Result']\n"
    )
    names = ["Question", "events", "plot_raster", "plot_psth", "Result"]
    found = build_ontology.references(source, names)
    assert found == ["Question", "events", "plot_psth", "plot_raster"]


def test_facts_and_constants_are_read_from_their_tables():
    text = (
        "## Science\n\n| ID | Domain | Predicate | Held by | Ruled |\n|---|---|---|---|---|\n"
        f"| S1 | outputs | a claim | `gate:1`, `todo:{ITEM}` | today |\n\n"
        "## Constants\n\n| Constant | Values | Ruled |\n|---|---|---|\n"
        "| `k` | `3` | today |\n"
    )
    [row] = build_ontology.read_facts(text)
    assert (row["id"], row["table"], row["holders"]) == ("S1", "Science", ["gate:1", f"todo:{ITEM}"])
    assert build_ontology.read_constants(text) == {"k": ["3"]}


@pytest.fixture(scope="module")
def live():
    source = build_ontology.fact_source()
    return source, build_ontology.build(None, REPO_ROOT, source)


def test_the_live_tree_has_no_violated_fact_and_counts_the_unheld(live, capsys):
    source, onto = live
    _, results = ontology_gate.run(facts_path=source, ontology=onto)
    counts = ontology_gate.summary(results)
    assert counts["VIOLATED"] == 0, [r for r in results if r[1] == "VIOLATED"]
    assert counts["HELD"] > 0
    assert ontology_gate.main() == 0
    assert f"UNHELD {counts['UNHELD']}" in capsys.readouterr().out


def test_a_violation_planted_in_the_live_ontology_fails_the_held_lifecycle_fact(live):
    source, onto = live
    planted = copy.deepcopy(onto)
    routed = sorted({t for _, t in planted["relations"]["routes"]
                     if t in planted["entities"]["export"]})[0]
    planted["relations"]["verifies"] = [e for e in planted["relations"]["verifies"]
                                        if e[1] != routed]
    _, before = ontology_gate.run(facts_path=source, ontology=onto)
    _, after = ontology_gate.run(facts_path=source, ontology=planted)
    held = {f for f, s, _ in before if s == "HELD"}
    violated = {f: r for f, s, r in after if s == "VIOLATED"}
    assert violated and set(violated) <= held
    assert all(f"{routed} is routed but not tested" in " ".join(r) for r in violated.values())


def test_the_harness_gate_fails_on_a_violated_fact(monkeypatch):
    monkeypatch.setattr(ontology_gate, "run",
                        lambda: (None, [("X1", "VIOLATED", ["planted"]), ("X2", "UNHELD", [])]))
    assert harness_gate.check_fact_predicates() == ["X1: planted"]
