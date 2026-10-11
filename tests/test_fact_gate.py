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
        # The builder run by path imports this checkout, whichever copy the suite is testing.
        env = {k: v for k, v in os.environ.items() if k != "JNWB_EXPECTED_PACKAGE_ROOT"}
        env["PYTHONHASHSEED"] = seed
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


def test_a_todo_holder_naming_a_roadmap_row_is_unheld():
    roadmap = ("| ID | Theme | Defect | Waits | Release |\n|---|---|---|---|---|\n"
               "| 12-09 | a theme | a defect | a reason | deferred-99.0.0 |\n")
    items = fact_gate.live_items(f"### {ITEM} An item\n", roadmap)
    assert status(graph(), "todo:12-09", items=items) == ("UNHELD", ["held by todo 12-09"])


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


@pytest.mark.parametrize("target, expected", [
    ("vis.canvas", True),
    ("vis.canvas.PlotlyPublicationCanvas", True),
    ("vis.canvas.no_such_name", False),
    ("vis.no_such_module", False),
])
def test_a_target_behind_a_missing_extra_resolves_from_source(target, expected):
    class ExtraMissing:
        __file__ = str(REPO_ROOT / "jnwb" / "__init__.py")

        def __getattr__(self, name):
            raise ImportError("an optional extra is not installed")

    record = build_fact_graph._route_targets(ExtraMissing(), {}, [["skill", target]])
    assert record[target]["resolves"] is expected


def test_a_module_file_is_named_the_same_from_an_installed_copy(tmp_path):
    installed = tmp_path / "site-packages" / "jnwb"
    installed.mkdir(parents=True)
    (installed / "__init__.py").write_text("", encoding="utf-8")
    (installed / "inspect_mod.py").write_text("", encoding="utf-8")
    package = type("Installed", (), {"__file__": str(installed / "__init__.py")})()
    module = type(sys)("jnwb.inspect_mod")
    module.__file__ = str(installed / "inspect_mod.py")
    assert build_fact_graph._module_file(module, package, REPO_ROOT) == "jnwb/inspect_mod.py"


def test_an_export_behind_a_missing_extra_is_recorded_from_its_source():
    class ExtraMissing:
        __file__ = str(REPO_ROOT / "jnwb" / "__init__.py")
        __all__ = ["vis"]

        def __getattr__(self, name):
            raise ImportError("an optional extra is not installed")

    exports, implements = build_fact_graph._exports(ExtraMissing(), REPO_ROOT, [])
    assert exports["vis"] == {"kind": "module", "signature": None, "switches": []}
    assert implements == [["jnwb/vis/__init__.py", "vis"]]


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


SEVENTH = "## Tooling\n\n| Key | Area | Claim | Holder | When |\n|---|---|---|---|---|\n| X9 | d | p | h | r |\n\n"
CONSTANTS_SECTION = "## Constants\n\n| Constant | Values | Ruled |\n|---|---|---|\n| `k` | `3` | r |\n"


@pytest.mark.parametrize("text, message", [
    (fact_source(header="| ID | Domain | Predicate | Held-by | Ruled |\n|---|---|---|---|---|\n"),
     "is not the fact header"),
    (fact_source(rows=["| T0 | d | p | `gate:1` | r |\n"] * 6), "fact T0 appears in"),
    (fact_source(rows=["| | d | p | `gate:1` | r |\n"] + [
        f"| T{i} | d | p | `gate:1` | r |\n" for i in range(1, 6)]), "empty ID"),
    (fact_source(tables=build_fact_graph.FACT_TABLES[:5]), "not exactly"),
    (fact_source(tables=build_fact_graph.FACT_TABLES + ("Extra",),
                 rows=[f"| T{i} | d | p | `gate:1` | r |\n" for i in range(7)]), "not one of"),
    (fact_source() + SEVENTH + CONSTANTS_SECTION, "not one of"),
    (fact_source() + SEVENTH.replace("## Tooling\n\n", "") + CONSTANTS_SECTION,
     "is not the fact header"),
], ids=["header typo", "duplicate id", "empty id", "missing table", "extra fact table",
        "seventh section with an untriggering header", "second table inside a fact section"])
def test_a_malformed_fact_source_is_refused(tmp_path, text, message):
    path = tmp_path / "facts.md"
    path.write_bytes(text.encode("utf-8"))
    with pytest.raises(build_fact_graph.FactSourceError, match=message):
        build_fact_graph.load_facts(path)


@pytest.fixture(scope="module")
def live():
    source = build_fact_graph.FACT_STACK
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


PARTITION_CONSTANTS = {**CONSTANTS, "k": ["3"]}


def skill_graph(routes):
    """Shipped skills, each with the routing targets it names, as the graph records them."""
    return {
        "entities": {"skill": sorted(routes)},
        "relations": {"routes": [[skill, t] for skill in sorted(routes) for t in routes[skill]]},
    }


def partition_status(routes, constants=PARTITION_CONSTANTS):
    return status(skill_graph(routes), "computed:partition", constants=constants)


def exclusive_to(routes, skill):
    """The targets `skill` routes that no other domain skill routes; the router is outside."""
    others = {t for s, ts in routes.items() if s not in ("jnwb", skill) for t in ts}
    return sorted(set(routes[skill]) - others)


def test_a_domain_skill_with_two_exclusive_operations_is_violated():
    routes = {
        "jnwb": ["a", "x"],
        "jnwb-two": ["x", "y"],
        "jnwb-three": ["p", "q", "r"],
    }
    assert exclusive_to(routes, "jnwb-two") == ["x", "y"], "fixture must give jnwb-two two exclusive operations"
    assert exclusive_to(routes, "jnwb-three") == ["p", "q", "r"]
    assert partition_status(routes) == (
        "VIOLATED", ["computed:partition: jnwb-two owns 2 exclusive operations, fewer than 3"])


def test_every_domain_skill_with_three_exclusive_operations_is_held():
    routes = {
        "jnwb": ["a", "p", "x"],
        "jnwb-one": ["p", "q", "r"],
        "jnwb-two": ["x", "y", "z"],
    }
    assert [len(exclusive_to(routes, s)) for s in ("jnwb-one", "jnwb-two")] == [3, 3]
    assert partition_status(routes) == ("HELD", [])


def test_an_operation_two_domain_skills_route_breaks_the_partition():
    routes = {"jnwb-one": ["p", "q", "r", "shared"], "jnwb-two": ["x", "y", "z", "shared"]}
    assert [len(exclusive_to(routes, s)) for s in ("jnwb-one", "jnwb-two")] == [3, 3], (
        "fixture must meet the floor, so only the shared operation can fail it")
    assert partition_status(routes) == (
        "VIOLATED", ["computed:partition: shared is routed by jnwb-one, jnwb-two"])


def test_the_floor_is_read_from_the_k_constant():
    routes = {"jnwb-one": ["p", "q"], "jnwb-two": ["x", "y"]}
    assert [len(exclusive_to(routes, s)) for s in ("jnwb-one", "jnwb-two")] == [2, 2]
    assert partition_status(routes) == ("VIOLATED", [
        "computed:partition: jnwb-one owns 2 exclusive operations, fewer than 3",
        "computed:partition: jnwb-two owns 2 exclusive operations, fewer than 3"])
    assert partition_status(routes, constants={**CONSTANTS, "k": ["2"]}) == ("HELD", [])


def test_a_domain_skill_that_routes_nothing_is_violated():
    routes = {"jnwb": ["a"], "jnwb-one": ["p", "q", "r"], "jnwb-silent": []}
    assert exclusive_to(routes, "jnwb-silent") == []
    assert partition_status(routes) == (
        "VIOLATED", ["computed:partition: jnwb-silent owns 0 exclusive operations, fewer than 3"])
    assert partition_status({"jnwb": ["a"]}) == (
        "VIOLATED", ["computed:partition: the graph names no domain skill"])


def test_the_skill_partition_needs_the_k_constant():
    with pytest.raises(ValueError, match="name no k"):
        partition_status({"jnwb-one": ["p"]}, constants=CONSTANTS)


def test_the_live_tree_gives_every_domain_skill_its_floor_of_exclusive_operations(live):
    source, g = live
    constants = build_fact_graph.read_constants(source.read_text(encoding="utf-8"))
    counts = fact_gate.exclusive_counts(g)
    assert counts, "no domain skill was read from the live graph"
    assert set(counts) == set(g["entities"]["skill"]) - {"jnwb"}
    assert fact_gate.partition(g, constants) == [], counts
    _, results = fact_gate.run(facts_path=source, graph=g)
    assert {f: s for f, s, _ in results}["K1"] == "HELD"


GLOBAL_SEEDED = "import numpy as np\n\ndef f():\n    np.random.seed(0)\n    return np.random.rand()\n"
GLOBAL_SEEDED_FROM_IMPORT = "from random import seed\n\nseed(3)\n"
GENERATOR_ONLY = (
    "import random\nimport numpy as np\n\n"
    "def f(rng):\n    return rng.integers(4)\n\n"
    "local = random.Random(0)\nlocal.seed(5)\nrng = np.random.default_rng(0)\n"
)
UNNAMED_RNG = "import numpy as np\n\ndef f(x):\n    return np.random.default_rng(0).normal(size=x)\n"
NAMED_RNG = "import numpy as np\n\ndef f(x, rng):\n    return rng.normal(size=x)\n"
DB_AVERAGE = "import numpy as np\n\ndef f(p):\n    return np.mean(10 * np.log10(p))\n"
DB_AVERAGE_BY_NAME = ("import numpy as np\n\ndef f(p):\n    db = 10 * np.log10(p)\n"
                      "    return np.nanmean(db, axis=0)\n")
DB_SUM_OVER_COUNT = "import numpy as np\n\ndef f(p):\n    return np.sum(10 * np.log10(p)) / p.size\n"
DB_MEDIAN = "import numpy as np\n\ndef f(p):\n    return np.median(10 * np.log10(p))\n"
RAW_AVERAGE_THEN_LOG = "import numpy as np\n\ndef f(p):\n    m = np.mean(p)\n    return 10 * np.log10(m)\n"
LIVE_CONSTANTS = build_fact_graph.read_constants(build_fact_graph.FACT_STACK.read_text(encoding="utf-8"))
SCAN_RELATIONS = ("global_seeds", "rng_parameters", "db_averages")


def scanned(python=("jnwb/a.py", "scripts/b.py"), **relations):
    """A graph whose files are read, holding the scan relations the caller names."""
    return {"entities": {"python": list(python)},
            "relations": {name: relations.get(name, []) for name in SCAN_RELATIONS}}


def test_a_global_seed_call_is_violated():
    assert "np.random.seed(0)" in GLOBAL_SEEDED, "fixture must seed the global state"
    assert build_fact_graph.global_seed_calls(GLOBAL_SEEDED) == ["line 4: np.random.seed"]
    assert "seed(3)" in GLOBAL_SEEDED_FROM_IMPORT, "fixture must call the imported seed"
    assert build_fact_graph.global_seed_calls(GLOBAL_SEEDED_FROM_IMPORT) == ["line 3: seed"]


@pytest.mark.parametrize("source, spelled", [
    ("import numpy.random as nr\nnr.seed(1)\n", "nr.seed"),
    ("from numpy import random as npr\nnpr.seed(1)\n", "npr.seed"),
    ("from numpy.random import seed as s\ns(1)\n", "s"),
    ("import random as r\nr.seed(1)\n", "r.seed"),
])
def test_a_global_seed_reached_through_an_alias_is_violated(source, spelled):
    assert f"{spelled}(1)" in source, "fixture must call the seed"
    assert build_fact_graph.global_seed_calls(source) == [f"line 2: {spelled}"]


def test_a_generator_and_a_local_instance_are_held():
    assert "default_rng(0)" in GENERATOR_ONLY and "local.seed(5)" in GENERATOR_ONLY, (
        "fixture must build a generator and seed a local instance")
    assert build_fact_graph.global_seed_calls(GENERATOR_ONLY) == []


def test_a_global_seed_anywhere_in_the_tree_is_violated_and_an_unread_tree_is_not_a_pass():
    seeded = [["tests/t.py", "line 2: np.random.seed"]]
    assert status(scanned(global_seeds=seeded), "computed:global_seeds") == (
        "VIOLATED", ["computed:global_seeds: tests/t.py: line 2: np.random.seed"])
    assert status(scanned(), "computed:global_seeds") == ("HELD", [])
    assert status(scanned(python=()), "computed:global_seeds") == (
        "VIOLATED", ["computed:global_seeds: the graph reads no python file"])


def test_a_consumer_without_an_rng_parameter_is_violated():
    assert "default_rng(0)" in UNNAMED_RNG, "fixture must draw from a numpy generator"
    assert build_fact_graph.rng_violations(UNNAMED_RNG) == [
        "line 3: f draws without an rng parameter"]
    assert "rng.normal" in NAMED_RNG, "fixture must draw from the generator it takes"
    assert build_fact_graph.rng_violations(NAMED_RNG) == []


def test_the_rng_rule_is_read_from_the_jnwb_and_scripts_files():
    violated = [["scripts/s.py", "line 3: f draws without an rng parameter"]]
    assert status(scanned(rng_parameters=violated), "computed:rng_parameters") == (
        "VIOLATED", ["computed:rng_parameters: scripts/s.py: line 3: f draws without an rng parameter"])
    assert status(scanned(), "computed:rng_parameters") == ("HELD", [])
    assert status(scanned(python=("docs/x.py",)), "computed:rng_parameters") == (
        "VIOLATED", ["computed:rng_parameters: the graph reads no jnwb or scripts python file"])


@pytest.mark.parametrize("source, expected", [
    (DB_AVERAGE, ["line 4: np.mean over a dB value"]),
    (DB_AVERAGE_BY_NAME, ["line 5: np.nanmean over a dB value"]),
    (DB_SUM_OVER_COUNT, ["line 4: np.sum over a dB value divided by a count"]),
])
def test_an_average_of_dB_values_is_violated(source, expected):
    assert "log10" in source, "fixture must convert to dB"
    assert build_fact_graph.db_average_violations(source, LIVE_CONSTANTS) == expected


@pytest.mark.parametrize("source", [DB_MEDIAN, RAW_AVERAGE_THEN_LOG])
def test_a_median_of_dB_values_and_an_average_of_raw_power_are_not_flagged(source):
    assert "log10" in source, "fixture must convert to dB"
    assert build_fact_graph.db_average_violations(source, LIVE_CONSTANTS) == []


def test_the_dB_rule_is_read_from_the_jnwb_files():
    flagged = [["jnwb/a.py", "line 4: np.mean over a dB value"]]
    assert status(scanned(db_averages=flagged), "computed:db_averages") == (
        "VIOLATED", ["computed:db_averages: jnwb/a.py: line 4: np.mean over a dB value"])
    assert status(scanned(), "computed:db_averages") == ("HELD", [])
    assert status(scanned(python=("scripts/s.py",)), "computed:db_averages") == (
        "VIOLATED", ["computed:db_averages: the graph reads no jnwb python file"])


def test_the_live_graph_reads_the_python_files_the_scans_need(live):
    _, g = live
    python = g["entities"]["python"]
    assert python and any(p.startswith("jnwb/") for p in python), "the graph read no jnwb file"
