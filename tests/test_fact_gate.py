"""The fact graph is a pure function of the tree, and the fact gate reports what it establishes.

Each case below builds the situation it is named after on a small synthetic graph or fact
source, except the two live cases, which run on this tree: the gate passes here, and a violation
planted into this tree's own graph fails it.
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

from scripts import build_fact_graph, fact_gate, harness_gate  # noqa: E402

BUILDER = REPO_ROOT / "scripts" / "build_fact_graph.py"
#: A synthetic item identifier; the todo text of each fixture declares it live or not.
ITEM = "00-01"

CONSTANTS = {
    "lifecycle": ["implemented", "identity-verified", "documented", "tested", "routed"],
    "identity tests": ["device=tests/test_switch.py"],
}
FACT_HEADER = "| ID | Domain | Predicate | Held by | Ruled |\n|---|---|---|---|---|\n"


def graph(*, routed=("op",), verified=(("tests/test_op.py", "op"),), switches=()):
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


def status(g, *holders, constants=CONSTANTS, items=(ITEM,)):
    [(_, found, reasons)] = fact_gate.evaluate([{"id": "X1", "holders": list(holders)}],
                                               constants, g, items)
    return found, reasons


def fact_source(tables=build_fact_graph.FACT_TABLES, header=FACT_HEADER, rows=None):
    """A fact source with one row per table, IDs T0, T1, ... unless ``rows`` says otherwise."""
    rows = rows or [f"| T{i} | d | p | `gate:1` | r |\n" for i in range(len(tables))]
    return "".join(f"## {t}\n\n{header}{row}\n" for t, row in zip(tables, rows))


def test_two_builds_in_separate_processes_are_byte_identical(tmp_path):
    """Different hash seeds reorder every set; the output must not follow them."""
    digests = []
    for seed in ("1", "2"):
        out = tmp_path / f"fact_graph_{seed}.json"
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run([sys.executable, str(BUILDER), "--out", str(out)], cwd=REPO_ROOT,
                              env=env, capture_output=True, text=True, timeout=300)
        assert done.returncode == 0, done.stderr
        digests.append(hashlib.sha256(out.read_bytes()).hexdigest())
    assert digests[0] == digests[1]
    assert b"\r\n" not in out.read_bytes()


def test_a_routed_operation_with_no_test_is_violated():
    assert status(graph(), "computed:lifecycle") == ("HELD", [])
    found, reasons = status(graph(verified=()), "computed:lifecycle")
    assert found == "VIOLATED"
    assert reasons == ["computed:lifecycle: op is routed but not tested"]


def test_the_lifecycle_order_is_read_from_the_constant():
    """Without `routed` in the constant, the same untested routed operation breaks nothing."""
    short = {**CONSTANTS, "lifecycle": ["implemented", "documented", "tested"]}
    assert status(graph(verified=()), "computed:lifecycle", constants=short) == ("HELD", [])


def test_a_switch_its_identity_module_does_not_reach_is_violated():
    g = graph(switches=("device",))
    found, reasons = status(g, "computed:lifecycle")
    assert found == "VIOLATED"
    assert reasons == ["computed:lifecycle: op is documented but not identity-verified"]
    g["relations"]["verifies"].append(["tests/test_switch.py", "op"])
    assert status(g, "computed:lifecycle") == ("HELD", [])


@pytest.mark.parametrize("record, reason", [
    ({"export": "op", "resolves": False}, "op.missing does not resolve on the package"),
    ({"export": None, "resolves": True}, "op.missing does not start at an export of jnwb.__all__"),
])
def test_a_routing_target_off_the_public_surface_is_violated(record, reason):
    g = graph(routed=("op.missing",))
    g["entities"]["route_target"]["op.missing"] = record
    assert status(g, "computed:routes") == ("VIOLATED", [f"computed:routes: {reason}"])
    assert status(graph(routed=("op.member",)), "computed:routes") == ("HELD", [])


@pytest.mark.parametrize("holders, reason", [
    (("gate:99",), "gate:99 does not resolve"),
    (("test:tests/test_absent.py",), "test:tests/test_absent.py does not resolve"),
    (("test:tests/test_op.py::test_absent",), "test:tests/test_op.py::test_absent does not resolve"),
    (("computed:absent",), "computed:absent is no predicate this gate evaluates"),
    ((), "names no holder"),
])
def test_a_holder_that_does_not_resolve_is_violated(holders, reason):
    assert status(graph(), *holders) == ("VIOLATED", [reason])


def test_resolving_holders_are_held():
    assert status(graph(), "gate:1", "test:tests/test_op.py::test_op") == ("HELD", [])


def test_a_todo_holder_is_unheld_only_while_its_item_is_live():
    assert status(graph(), "gate:1", f"todo:{ITEM}") == ("UNHELD", [f"held by todo {ITEM}"])
    assert status(graph(), f"todo:{ITEM}", items=()) == (
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
    found = build_fact_graph.references(source, names)
    assert found == ["Question", "events", "plot_psth", "plot_raster"]


def test_routes_are_read_from_bullet_heads_and_from_a_module_table():
    text = (
        "- `jnwb.a(x)`, `jnwb.b(x)`: returns what `jnwb.c` also returns.\n"
        "- plain bullet naming `jnwb.d`\n\n"
        "| Figure | `jnwb.vis` module |\n|---|---|\n"
        "| Canvas | `canvas` (`Canvas`, `seal`), `sidecar` |\n"
    )
    assert build_fact_graph.routing_targets(text) == ["a", "b", "vis.canvas", "vis.sidecar"]


def test_the_six_fact_tables_are_read_and_constants_beside_them():
    text = fact_source() + "## Constants\n\n| Constant | Values | Ruled |\n|---|---|---|\n| `k` | `3` | r |\n"
    facts = build_fact_graph.read_facts(text)
    build_fact_graph.require_tables(text)
    assert [(f["id"], f["table"]) for f in facts][:2] == [("T0", "Boundary"), ("T1", "Design")]
    assert facts[0]["holders"] == ["gate:1"]
    assert build_fact_graph.read_constants(text) == {"k": ["3"]}


@pytest.mark.parametrize("text, message", [
    (fact_source(header="| ID | Domain | Predicate | Held-by | Ruled |\n|---|---|---|---|---|\n"),
     "looks like a fact table"),
    (fact_source(rows=["| T0 | d | p | `gate:1` | r |\n"] * 6), "fact T0 appears in"),
    (fact_source(tables=build_fact_graph.FACT_TABLES[:5]), "not exactly"),
    (fact_source(tables=build_fact_graph.FACT_TABLES + ("Extra",),
                 rows=[f"| T{i} | d | p | `gate:1` | r |\n" for i in range(7)]), "not exactly"),
], ids=["header typo", "duplicate id", "missing table", "extra table"])
def test_a_malformed_fact_source_is_refused(tmp_path, text, message):
    path = tmp_path / "facts.md"
    path.write_bytes(text.encode("utf-8"))
    with pytest.raises(build_fact_graph.FactSourceError, match=message):
        build_fact_graph.load_facts(path)


def test_a_primary_source_whose_fact_tables_do_not_parse_is_refused_not_passed_over(tmp_path):
    primary, draft = tmp_path / "primary.md", tmp_path / "draft.md"
    draft.write_bytes(fact_source().encode("utf-8"))
    primary.write_bytes(
        fact_source(header="| ID | Domain | Claim | Held by | Ruled |\n|---|---|---|---|---|\n")
        .encode("utf-8"))
    with pytest.raises(build_fact_graph.FactSourceError, match="looks like a fact table"):
        build_fact_graph.fact_source(primary, draft)


@pytest.fixture(scope="module")
def live():
    source = build_fact_graph.fact_source()
    return source, build_fact_graph.build(None, REPO_ROOT, source)


def test_the_live_tree_has_no_violated_fact_and_counts_the_unheld(live, capsys):
    source, g = live
    _, results = fact_gate.run(facts_path=source, graph=g)
    counts = fact_gate.summary(results)
    assert counts["VIOLATED"] == 0, [r for r in results if r[1] == "VIOLATED"]
    assert counts["HELD"] > 0
    assert fact_gate.main() == 0
    assert f"UNHELD {counts['UNHELD']}" in capsys.readouterr().out


def test_a_violation_planted_in_the_live_graph_fails_the_held_lifecycle_fact(live):
    source, g = live
    planted = copy.deepcopy(g)
    routed = sorted({t for _, t in planted["relations"]["routes"]
                     if t in planted["entities"]["export"]})[0]
    planted["relations"]["verifies"] = [e for e in planted["relations"]["verifies"]
                                        if e[1] != routed]
    _, before = fact_gate.run(facts_path=source, graph=g)
    _, after = fact_gate.run(facts_path=source, graph=planted)
    held = {f for f, s, _ in before if s == "HELD"}
    violated = {f: r for f, s, r in after if s == "VIOLATED"}
    assert violated and set(violated) <= held
    assert all(f"{routed} is routed but not tested" in " ".join(r) for r in violated.values())


def test_the_harness_gate_fails_on_a_violated_fact_and_names_the_source(monkeypatch):
    results = [("X1", "VIOLATED", ["planted"]), ("X2", "UNHELD", [])]
    monkeypatch.setattr(fact_gate, "run", lambda: (REPO_ROOT / "facts.md", results))
    assert harness_gate.check_fact_predicates() == ["X1: planted"]
    assert "facts.md" in harness_gate._fact_pass_line()
