"""The fact graph is a pure function of the tree, and the fact gate reports what it establishes.

Each case below builds the situation it is named after on a small synthetic graph or fact
source, except the two live cases, which run on this tree: the gate passes here, and a violation
planted into this tree's own graph fails it.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
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


REFERENCES_FIXTURE = (
    "## Methods\n\n"
    "| Reference | Result implemented | Functions |\n"
    "|---|---|---|\n"
    "| Doe, J. (2020). A method with several words. "
    "[doi:10.1000/method](https://doi.org/10.1000/method) "
    "| The result this row implements takes several words | `op`, `other` |\n"
    "\n"
    "## Pitfalls\n\n"
    "| Reference | Pitfall stated | Functions it concerns |\n"
    "|---|---|---|\n"
    "| Roe, J. (2021). A pitfall with several words. "
    "[doi:10.1000/pitfall](https://doi.org/10.1000/pitfall) "
    "| The pitfall this row states takes several words | `op` |\n"
)


def test_a_method_row_and_a_pitfall_row_yield_reference_cites_and_concerns():
    references, cites, concerns = build_fact_graph.read_references(REFERENCES_FIXTURE)
    assert references == {
        "10.1000/method": {"section": "Methods", "functions": ["op", "other"]},
        "10.1000/pitfall": {"section": "Pitfalls", "functions": ["op"]},
    }
    assert cites == [["op", "10.1000/method"], ["other", "10.1000/method"]]
    assert concerns == [["op", "10.1000/pitfall"]]


def cited_graph(cites):
    """The ``graph`` fixture with the ``cites`` edges the caller names."""
    g = graph()
    g["relations"]["cites"] = [list(edge) for edge in cites]
    return g


def test_a_routed_function_with_no_citation_is_flagged():
    found, reasons = status(cited_graph([]), "computed:routed_citations")
    assert found == "VIOLATED"
    assert reasons == ["computed:routed_citations: op: routed by jnwb-demo and cites no reference"]


def test_a_routed_function_with_a_citation_is_held():
    assert status(cited_graph([["op", "10.1000/method"]]),
                   "computed:routed_citations") == ("HELD", [])


def test_a_graph_with_no_routing_targets_is_not_held():
    g = cited_graph([])
    g["entities"]["route_target"] = {}
    assert status(g, "computed:routed_citations")[0] == "VIOLATED"


def test_a_routed_export_outside_the_exclusion_list_is_flagged():
    g = cited_graph([])
    assert ["jnwb-demo", "op"] in g["relations"]["routes"], "the planted export must be routed"
    assert all(name != "op" for name, _ in g["relations"].get("cites", [])), (
        "the planted export must have no cites edge")
    assert "op" not in build_fact_graph.routed_citation_exclusions(), (
        "the planted export must not be on the exclusion list")
    found, reasons = status(g, "computed:routed_citations")
    assert found == "VIOLATED"
    assert reasons == ["computed:routed_citations: op: routed by jnwb-demo and cites no reference"]


def test_a_routed_export_on_the_exclusion_list_is_held_without_a_citation(monkeypatch):
    g = cited_graph([])
    assert ["jnwb-demo", "op"] in g["relations"]["routes"], "the planted export must be routed"
    assert all(name != "op" for name, _ in g["relations"].get("cites", [])), (
        "the planted export must have no cites edge")
    monkeypatch.setattr(build_fact_graph, "routed_citation_exclusions", lambda *a, **k: {"op"})
    assert status(g, "computed:routed_citations") == ("HELD", [])


def test_the_exclusion_list_holds_78_names_beside_its_header():
    excluded = build_fact_graph.routed_citation_exclusions()
    assert len(excluded) == 78, sorted(excluded)
    assert all(name and not name.startswith("#") for name in excluded)


def test_the_exclusion_list_covers_every_live_uncited_routed_export(live):
    _, g = live
    uncited = build_fact_graph.uncited_routed_heads(g)
    assert uncited, "the live graph must hold uncited routed exports"
    excluded = build_fact_graph.routed_citation_exclusions()
    assert set(uncited) <= excluded, sorted(set(uncited) - excluded)
    assert fact_gate.routed_citations(g, CONSTANTS) == []


def test_every_live_citation_names_an_export(live):
    import jnwb

    _, g = live
    cites = g["relations"]["cites"]
    assert cites, "the live graph cites no reference"
    assert cites == sorted(cites), "the live cites edges are not sorted"
    exports = g["entities"]["export"]
    references = g["entities"]["reference"]
    for name, doi in cites:
        head = name.split(".")[0]
        assert head in exports, f"{name} cites doi:{doi} but {head} is no export"
        obj = jnwb
        for part in name.split("."):
            obj = getattr(obj, part)
        assert doi in references, f"{name} cites doi:{doi}, which the graph names no reference for"


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


def test_the_fact_gate_reads_the_items_the_stack_parser_reads_at_every_heading_form():
    """The gate read `###` headings only, so an item at another depth or in the HTML form named no
    live item, while STEP 0a counted it. Both read the one parser."""
    from scripts.stack_parse import parse_todo_stack
    text = ("### 12-01 An item\n\n#### 12-03 Nested\n\n## 12-04 Second level\n\n"
            "<h3>12-05 HTML</h3>\n")
    assert fact_gate.live_items(text) == ["12-01", "12-03", "12-04", "12-05"]
    assert fact_gate.live_items(text) == [i for i, _, _ in parse_todo_stack(text)[0]]


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


LIVE_IMMUNITY = LIVE_CONSTANTS["immunity vocabulary"]
IMMUNITY_TEXT = "Reduced sensitivity is immune to volume conduction.\n"
IMMUNITY_NEAR_MISS = ("Immune cells were counted in the lab.\n"
                      "The result is immune to noise; volume conduction is excluded.\n")
IMMUNITY_PYTHON = (
    "def f(x):\n"
    '    """Reduced sensitivity to zero-phase coupling; immune to volume conduction."""\n'
    "    # complete suppression of the reference signal\n"
    "    immune = x  # no volume conduction here\n"
    "    return immune\n"
)


@pytest.mark.parametrize("text, expected", [
    (IMMUNITY_TEXT, ["line 1: immune"]),
    ("Complete suppression follows zero-phase coupling.\n", ["line 1: complete suppression"]),
])
def test_an_immune_sentence_beside_a_context_term_is_violated(text, expected):
    assert "volume conduction" in text or "zero-phase" in text, "fixture must name a context term"
    assert build_fact_graph.immunity_violations(text, LIVE_IMMUNITY) == expected


def test_an_immune_word_about_something_else_is_not_flagged():
    assert "immune" in IMMUNITY_NEAR_MISS.lower(), "fixture must name the vocabulary"
    assert build_fact_graph.immunity_violations(IMMUNITY_NEAR_MISS, LIVE_IMMUNITY) == []


@pytest.mark.parametrize("text, expected", [
    ("It does not confer immunity to volume conduction.\n", []),
    ("It is immune to volume conduction.\n", ["line 1: immune"]),
    ("No cell is clean, but the signal is immune to volume conduction.\n", ["line 1: immune"]),
])
def test_a_value_negated_in_its_clause_passes_and_an_asserted_one_fails(text, expected):
    assert build_fact_graph.immunity_violations(text, LIVE_IMMUNITY) == expected


@pytest.mark.parametrize("text, expected", [
    ("It does not\nconfer immunity to volume conduction.\n", []),
    ("It is\nimmune to volume conduction.\n", ["line 2: immune"]),
])
def test_a_negation_ending_one_line_reaches_the_value_on_the_next(text, expected):
    assert build_fact_graph.immunity_violations(text, LIVE_IMMUNITY) == expected


def test_a_comment_or_docstring_is_prose_and_code_is_not():
    assert "immune = x" in IMMUNITY_PYTHON, "fixture must hold a code identifier"
    prose = build_fact_graph.python_prose(IMMUNITY_PYTHON)
    assert prose.count("\n") == IMMUNITY_PYTHON.count("\n"), "prose must keep the line numbers"
    assert "immune = x" not in prose
    assert build_fact_graph.immunity_violations(prose, LIVE_IMMUNITY) == [
        "line 2: immune", "line 3: complete suppression"]


def test_the_immunity_rule_needs_its_vocabulary_constant():
    with pytest.raises(ValueError, match="immunity vocabulary"):
        build_fact_graph.immunity_violations(IMMUNITY_TEXT, [])


@pytest.mark.parametrize("text, expected", [
    ("It does not hold: the signal is immune to volume conduction.\n", ["line 1: immune"]),
    ("The filter (not the reference) is immune to volume conduction.\n", ["line 1: immune"]),
])
def test_a_colon_or_parenthesis_ends_a_negation_clause(text, expected):
    assert build_fact_graph.immunity_violations(text, LIVE_IMMUNITY) == expected


def test_a_list_item_is_its_own_sentence():
    text = "- It does not\n- confer immunity to volume conduction.\n"
    assert build_fact_graph.immunity_violations(text, LIVE_IMMUNITY) == ["line 2: immunity"]


@pytest.mark.parametrize("text", [
    "It is not only immune to volume conduction.\n",
    "It is not just immune to volume conduction.\n",
    "It is not merely immune to volume conduction.\n",
])
def test_not_only_not_just_and_not_merely_are_no_negation(text):
    assert build_fact_graph.immunity_violations(text, LIVE_IMMUNITY) == ["line 1: immune"]


@pytest.mark.parametrize("text, expected", [
    ("The estimate is robust to volume conduction.\n", ["line 1: robust to"]),
    ("The estimate is insensitive to field spread.\n", ["line 1: insensitive to"]),
    ("Coupling is unaffected by common-average referencing.\n", ["line 1: unaffected by"]),
    ("The method eliminates reference contamination.\n", ["line 1: eliminates"]),
    ("The filter completely suppresses volume conduction.\n", ["line 1: completely suppresses"]),
    ("Estimates are free of volume conduction.\n", ["line 1: free of"]),
    ("Coupling is immune to re-referencing.\n", ["line 1: immune"]),
])
def test_the_repaired_vocabulary_is_violated_beside_a_context_term(text, expected):
    assert build_fact_graph.immunity_violations(text, LIVE_IMMUNITY) == expected


IMMUNITY_NOTEBOOK = json.dumps({"cells": [
    {"cell_type": "markdown", "source": ["Reduced sensitivity is\n", "immune to volume conduction.\n"]},
    {"cell_type": "code", "source": ["x = 1  # immune to volume conduction\n", "y = 2\n"]},
]})


def test_a_script_comment_and_a_notebook_cell_are_prose():
    script = "x = 1  # immune to volume conduction\n"
    assert build_fact_graph.immunity_scan("scripts/s.py", script, LIVE_IMMUNITY) == ["line 1: immune"]
    assert build_fact_graph.immunity_scan("examples/n.ipynb", IMMUNITY_NOTEBOOK, LIVE_IMMUNITY) == [
        "cell 0 line 2: immune", "cell 1 line 1: immune"]


def test_the_scan_reads_every_tracked_text_file_outside_tests_and_artifacts():
    tracked = ["AGENTS.md", "CHANGELOG.md", "README.md", "docs/a.md", ".github/workflows/w.yml",
               "examples/n.ipynb", "jnwb/a.py", "notes/a.txt", "scripts/s.py", "skills/x/SKILL.md",
               "skills/x/run.sh", "data/x.csv", "tests/t.py", "tests/t.md", "artifacts/a.md"]
    assert build_fact_graph._prose_files(tracked) == [
        "AGENTS.md", "CHANGELOG.md", "README.md", "docs/a.md", ".github/workflows/w.yml",
        "examples/n.ipynb", "jnwb/a.py", "notes/a.txt", "scripts/s.py", "skills/x/SKILL.md",
        "skills/x/run.sh"]


def test_the_two_rule_files_are_exempt_but_a_sibling_rule_file_is_still_scanned():
    tracked = ["scripts/build_fact_graph.py", "scripts/fact_gate.py", "scripts/fact_gate_rules.py",
               "scripts/gates/stacks_form.py", "scripts/fact_gate.py.bak.md"]
    assert build_fact_graph._prose_files(tracked) == [
        "scripts/fact_gate_rules.py", "scripts/gates/stacks_form.py", "scripts/fact_gate.py.bak.md"]


def test_the_gate_prints_the_examined_count_and_the_exempt_trees():
    assert fact_gate.scope_line(text_scanned()) == (
        "immunity_vocabulary examined 2 text files; exempt: tests/, artifacts/, "
        "scripts/build_fact_graph.py, scripts/fact_gate.py")


@pytest.mark.parametrize("text, expected", [
    ("The skill must write a manifest that lists each contract field.\n", ["line 1: manifest"]),
    ("The receipt has required fields for each run.\n", ["line 1: receipt"]),
    ("A MANIFEST must produce the schema.\n", ["line 1: manifest"]),
])
def test_a_skill_naming_a_manifest_beside_a_contract_is_violated(text, expected):
    assert build_fact_graph.skill_contract_violations(text) == expected


@pytest.mark.parametrize("text", [
    "The contract is carried by the Result, whose manifest lists the fields.\n",
    "The receipt contract extends Lineage, so its manifest lists only new fields.\n",
    "Write the manifest to the output folder.\n",
])
def test_a_skill_naming_a_carrier_or_no_contract_is_not_flagged(text):
    assert build_fact_graph.skill_contract_violations(text) == []


@pytest.mark.parametrize("text, expected", [
    ("Each call returns a Result whose manifest lists the contract fields.\n", ["line 1: manifest"]),
    ("Use inspect to read the receipt, whose schema the contract defines.\n", ["line 1: receipt"]),
])
def test_a_carrier_exempts_a_sentence_only_when_it_extends_or_carries_the_contract(text, expected):
    assert build_fact_graph.skill_contract_violations(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Each run writes receipts that the contract defines.\n", ["line 1: receipt"]),
    ("The receipt must contain the run fields.\n", ["line 1: receipt"]),
    ("The receipt lists required-fields for each run.\n", ["line 1: receipt"]),
    ("A receipt must include the fields of each run.\n", ["line 1: receipt"]),
    ("The manifests must produce each contract.\n", ["line 1: manifest"]),
])
def test_plurals_and_field_triggers_are_read(text, expected):
    assert build_fact_graph.skill_contract_violations(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("The skill defines a manifest\nthat lists the contract fields.\n", ["line 1: manifest"]),
    ("The skill defines a manifest that\nlists the contract fields.\n", ["line 1: manifest"]),
])
def test_a_sentence_wrapped_across_lines_is_read_whole(text, expected):
    assert build_fact_graph.skill_contract_violations(text) == expected


SILENT_HANDLER = ("def f(p):\n    try:\n        return int(p)\n"
                  "    except ValueError:\n        return None\n")
SILENT_DEBUG = ("import logging\nlogger = logging.getLogger(__name__)\n\ndef f(p):\n"
                "    try:\n        return int(p)\n    except ValueError:\n"
                "        logger.debug('bad')\n        return None\n")
SILENT_BARE = "def f(p):\n    try:\n        return int(p)\n    except:\n        return None\n"
SILENT_MIXED_IMPORT = "try:\n    import scipy\nexcept (ImportError, OSError):\n    scipy = None\n"
KEPT_ON_SELF = ("def f(p):\n    try:\n        return int(p)\n    except ValueError as exc:\n"
                      "        self.error = exc\n    return None\n")
WARNED_HANDLER = ("import warnings\n\ndef f(p):\n    try:\n        return int(p)\n"
                  "    except ValueError:\n        warnings.warn('bad')\n        return None\n")
LOGGED_HANDLER = ("import logging\nlogger = logging.getLogger(__name__)\n\ndef f(p):\n"
                  "    try:\n        return int(p)\n    except ValueError:\n"
                  "        logger.warning('bad')\n        return None\n")
RAISED_HANDLER = ("def f(p):\n    try:\n        return int(p)\n    except ValueError as exc:\n"
                  "        raise RuntimeError('bad') from exc\n")
OPTIONAL_IMPORT = "try:\n    import scipy\nexcept ImportError:\n    scipy = None\n"
MISSING_MODULE = "try:\n    import scipy\nexcept ModuleNotFoundError:\n    scipy = None\n"
KEPT_READ = ("def f(p):\n    try:\n        return int(p)\n    except ValueError as exc:\n"
             "        self.error = exc\n    return self.error\n")
KEPT_IN_CONTAINER_READ = ("def f(p):\n    try:\n        return int(p)\n"
                          "    except ValueError as exc:\n        FAILURES[p] = exc\n"
                          "    return FAILURES\n")
KEPT_IN_CONTAINER_UNRETURNED = ("def f(p):\n    try:\n        return int(p)\n"
                            "    except ValueError as exc:\n        FAILURES[p] = exc\n"
                            "    return None\n")


SILENT_BOUND_UNUSED = ("def f(p):\n    try:\n        return int(p)\n"
                       "    except ValueError as exc:\n        return None\n")
USES_IN_RETURN = ("def f(p):\n    try:\n        return int(p)\n    except ValueError as exc:\n"
                  "        return {'error': str(exc)}\n")
SAME_MODULE_REPORTS = ("import warnings\n\ndef _fallback(p):\n    warnings.warn('bad')\n"
                       "    return None\n\ndef f(p):\n    try:\n        return int(p)\n"
                       "    except ValueError:\n        return _fallback(p)\n")
SAME_MODULE_SILENT = ("import warnings\n\ndef _fallback(p):\n    return None\n\n"
                      "def f(p):\n    try:\n        return int(p)\n    except ValueError:\n"
                      "        return _fallback(p)\n")
SAME_MODULE_RAISES = ("def _fallback(p):\n    raise ValueError(p)\n\ndef f(p):\n    try:\n"
                      "        return int(p)\n    except ValueError:\n        return _fallback(p)\n")
TWO_LEVELS = ("import warnings\n\ndef _inner(p):\n    warnings.warn('bad')\n    return None\n\n"
              "def _outer(p):\n    return _inner(p)\n\ndef f(p):\n    try:\n        return int(p)\n"
              "    except ValueError:\n        return _outer(p)\n")
IMPORTED_CALL = ("from .helpers import fallback\n\ndef f(p):\n    try:\n        return int(p)\n"
                 "    except ValueError:\n        return fallback(p)\n")
ALIASED_CALL = ("from .helpers import fallback as fb\n\ndef f(p):\n    try:\n        return int(p)\n"
                "    except ValueError:\n        return fb(p)\n")
HELPERS_REPORT = {"jnwb/pkg/helpers.py": "import logging\n\nlog = logging.getLogger(__name__)\n\n"
                  "def fallback(p):\n    log.error('bad')\n    return None\n"}
HELPERS_SILENT = {"jnwb/pkg/helpers.py": "def fallback(p):\n    return None\n"}
LEVEL_TWO_CALL = ("from ..helpers import fallback\n\ndef f(p):\n    try:\n        return int(p)\n"
                  "    except ValueError:\n        return fallback(p)\n")
LEVEL_TWO_HELPERS = {"jnwb/helpers.py": HELPERS_REPORT["jnwb/pkg/helpers.py"]}


def handlers_in(source, read=None):
    """The silent handlers of a module at ``jnwb/pkg/a.py``, whose relative imports read ``read``."""
    return build_fact_graph.silent_handler_violations(source, "jnwb/pkg/a.py", (read or {}).get)


@pytest.mark.parametrize("source, expected", [
    (SILENT_HANDLER, ["line 5: except ValueError: return None"]),
    (SILENT_DEBUG, ["line 8: except ValueError: logger.debug('bad')"]),
    (SILENT_BARE, ["line 5: except (bare): return None"]),
    (SILENT_MIXED_IMPORT, ["line 4: except (ImportError, OSError): scipy = None"]),
    (SILENT_BOUND_UNUSED, ["line 5: except ValueError: return None"]),
])
def test_a_silent_handler_is_violated(source, expected):
    assert handlers_in(source) == expected


@pytest.mark.parametrize("source, read, expected", [
    (SAME_MODULE_SILENT, {}, ["line 10: except ValueError: return _fallback(p)"]),
    (SAME_MODULE_REPORTS, {}, []),
    (SAME_MODULE_RAISES, {}, []),
    (TWO_LEVELS, {}, ["line 14: except ValueError: return _outer(p)"]),
    (IMPORTED_CALL, {}, ["line 7: except ValueError: return fallback(p)"]),
    (IMPORTED_CALL, HELPERS_SILENT, ["line 7: except ValueError: return fallback(p)"]),
    (IMPORTED_CALL, HELPERS_REPORT, []),
    (ALIASED_CALL, HELPERS_REPORT, []),
    (LEVEL_TWO_CALL, LEVEL_TWO_HELPERS, []),
    (LEVEL_TWO_CALL, HELPERS_REPORT, ["line 7: except ValueError: return fallback(p)"]),
])
def test_a_handler_is_loud_when_its_called_function_reports_one_level_deep(source, read, expected):
    assert handlers_in(source, read) == expected


@pytest.mark.parametrize("source", [
    WARNED_HANDLER, LOGGED_HANDLER, RAISED_HANDLER, OPTIONAL_IMPORT, MISSING_MODULE, KEPT_READ,
    KEPT_IN_CONTAINER_READ, KEPT_ON_SELF, KEPT_IN_CONTAINER_UNRETURNED, USES_IN_RETURN,
])
def test_a_handler_that_warns_logs_raises_or_uses_its_exception_is_not_flagged(source):
    assert "except" in source, "fixture must hold a handler"
    assert handlers_in(source) == []


TEXT_RELATIONS = ("immunity_vocabulary", "skill_contracts", "silent_handlers")


def text_scanned(prose=("docs/a.md", "jnwb/a.py"), skill_file=("skills/x/SKILL.md",),
                 python=("jnwb/a.py",), **relations):
    """A graph whose text surfaces are read, holding the text relations the caller names."""
    return {"entities": {"prose": list(prose), "skill_file": list(skill_file),
                         "python": list(python)},
            "relations": {name: relations.get(name, []) for name in TEXT_RELATIONS}}


def test_the_text_rules_are_read_from_their_own_surfaces():
    flagged = [["docs/a.md", "line 2: immune"]]
    assert status(text_scanned(immunity_vocabulary=flagged), "computed:immunity_vocabulary") == (
        "VIOLATED", ["computed:immunity_vocabulary: docs/a.md: line 2: immune"])
    assert status(text_scanned(), "computed:immunity_vocabulary") == ("HELD", [])
    assert status(text_scanned(prose=()), "computed:immunity_vocabulary") == (
        "VIOLATED", ["computed:immunity_vocabulary: the graph reads no prose file"])
    listed = [["skills/x/SKILL.md", "line 3: receipt"]]
    assert status(text_scanned(skill_contracts=listed), "computed:skill_contracts") == (
        "VIOLATED", ["computed:skill_contracts: skills/x/SKILL.md: line 3: receipt"])
    assert status(text_scanned(), "computed:skill_contracts") == ("HELD", [])
    assert status(text_scanned(skill_file=()), "computed:skill_contracts") == (
        "VIOLATED", ["computed:skill_contracts: the graph reads no skill file"])
    swallowed = [["jnwb/a.py", "line 7: except ValueError"]]
    assert status(text_scanned(silent_handlers=swallowed), "computed:silent_handlers") == (
        "VIOLATED", ["computed:silent_handlers: jnwb/a.py: line 7: except ValueError"])
    assert status(text_scanned(), "computed:silent_handlers") == ("HELD", [])
    assert status(text_scanned(python=("scripts/s.py",)), "computed:silent_handlers") == (
        "VIOLATED", ["computed:silent_handlers: the graph reads no jnwb python file"])


def test_the_live_graph_reads_the_text_surfaces_the_new_scans_need(live):
    _, g = live
    prose, skills = g["entities"]["prose"], g["entities"]["skill_file"]
    assert {"README.md", "AGENTS.md"} <= set(prose), "the graph read no named page"
    assert any(p.startswith("docs/") for p in prose), "the graph read no docs page"
    assert any(p.startswith("jnwb/") and p.endswith(".py") for p in prose), "no jnwb file"
    assert any(p.startswith("scripts/") and p.endswith(".py") for p in prose), "no script file"
    assert not any(build_fact_graph._exempt(p) for p in prose), "an exempt file"
    assert skills and all(p.startswith("skills/") and p.endswith("SKILL.md") for p in skills)
    assert set(TEXT_RELATIONS) <= set(g["relations"])


S9_SILENT_F = "def f(p):\n    try:\n        return int(p)\n    except ValueError:\n        return None\n"
S9_SILENT_G = S9_SILENT_F.replace("def f", "def g")
S9_CLASS_METHOD = ("class C:\n    def m(self, p):\n        try:\n            return int(p)\n"
                   "        except ValueError:\n            return None\n")


def scanned_silent(tmp_path, source):
    """The silent_handlers scan of one planted module at jnwb/pkg/a.py."""
    (tmp_path / "jnwb" / "pkg").mkdir(parents=True)
    (tmp_path / "jnwb" / "pkg" / "a.py").write_text(source, encoding="utf-8")
    scans = build_fact_graph._text_scans(tmp_path, [], [], ["jnwb/pkg/a.py"],
                                         {"immunity vocabulary": []})
    return scans["silent_handlers"]


def test_a_silent_handler_is_named_by_its_qualified_function():
    assert build_fact_graph.silent_handler_sites(S9_CLASS_METHOD, "jnwb/pkg/a.py", {}.get) == [
        ("C.m", "line 6: except ValueError: return None")]


def test_a_handler_whose_function_is_listed_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S9_EXCUSED", {("jnwb/pkg/a.py", "f"): "probe: a test"})
    assert scanned_silent(tmp_path, S9_SILENT_F) == []


def test_a_listed_function_does_not_excuse_a_sibling_handler(tmp_path, monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S9_EXCUSED", {("jnwb/pkg/a.py", "f"): "probe: a test"})
    found = scanned_silent(tmp_path, S9_SILENT_F + S9_SILENT_G)
    assert [path for path, _ in found] == ["jnwb/pkg/a.py"]
    assert found[0][1].startswith("line 10: except ValueError")


def test_a_listed_key_that_matches_no_flagged_handler_is_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S9_EXCUSED", {("jnwb/pkg/a.py", "gone"): "probe: a test"})
    found = scanned_silent(tmp_path, S9_SILENT_F)
    assert ["jnwb/pkg/a.py", "S9_EXCUSED lists gone, which no flagged handler matches: stale"] in found
    assert len(found) == 2, "the unlisted handler in f stays flagged beside the stale key"


def test_a_listed_key_in_a_module_with_no_handler_is_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S9_EXCUSED", {("jnwb/pkg/a.py", "f"): "probe: a test"})
    assert scanned_silent(tmp_path, "def f(p):\n    return p\n") == [
        ["jnwb/pkg/a.py", "S9_EXCUSED lists f, which no flagged handler matches: stale"]]


def test_every_excused_handler_has_a_one_line_reason():
    assert build_fact_graph.S9_EXCUSED, "the excuse list must not be empty"
    for key, reason in build_fact_graph.S9_EXCUSED.items():
        assert isinstance(key, tuple) and len(key) == 2, key
        assert reason.strip() and "\n" not in reason, key


def test_the_live_tree_has_no_unexcused_or_stale_silent_handler(live):
    _, g = live
    assert g["relations"]["silent_handlers"] == []


# ------------------------------------------------------------------------ fact S10: schemes


def planted_draws_unnamed(x, rng):
    return rng.permutation(x)


def planted_draws_named(x, rng):
    return {"scheme": "global", "y": rng.permutation(x)}


def planted_sign_flip(x, rng):
    return {"y": rng.choice([-1.0, 1.0], size=len(x))}


def planted_bootstrap(x, rng):
    return {"mean": float(np.mean(rng.choice(x, size=len(x), replace=True)))}


def planted_no_draw(x):
    return {"y": x + 1}


PLANTED_SCHEMES = (planted_draws_unnamed, planted_draws_named, planted_sign_flip,
                   planted_bootstrap, planted_no_draw)


def planted_package(*functions):
    """A stand-in for the package: each planted function is exported under its own name."""
    return types.SimpleNamespace(__all__=[f.__name__ for f in functions],
                                 **{f.__name__: f for f in functions})


def test_the_callable_walk_never_imports_an_exported_submodule():
    """A submodule behind a missing optional extra raises ImportError on access; the walk
    must not touch it (the distribution build has no Plotly for ``jnwb.vis``)."""
    def planted_callable(x):
        return x

    class Package(types.SimpleNamespace):
        def __getattribute__(self, name):
            if name == "vis":
                raise ImportError("planted: the optional extra is not installed")
            return super().__getattribute__(name)

    package = Package(__all__=["planted_callable", "vis"], SUBMODULES=("vis",),
                      planted_callable=planted_callable)
    with pytest.raises(ImportError):
        package.vis
    walked = build_fact_graph._public_callables(package)
    assert [name for name, _, _ in walked] == ["planted_callable"]


def reported(found):
    """The findings keyed by their planted function name."""
    return {name.rpartition(".")[2]: reason for name, reason in found}


def test_a_planted_unnamed_null_is_reported_and_a_named_one_is_not(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S10_EXCUSED", {})
    examined, found = build_fact_graph.scheme_scan(planted_package(*PLANTED_SCHEMES))
    assert set(reported(found)) == {"planted_draws_unnamed", "planted_sign_flip"}


def test_the_scheme_scan_examines_every_planted_callable_and_names_what_it_drew(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S10_EXCUSED", {})
    examined, found = build_fact_graph.scheme_scan(planted_package(*PLANTED_SCHEMES))
    assert examined == len(PLANTED_SCHEMES) == 5, "the scan must examine every planted callable"
    names = reported(found)
    assert names["planted_draws_unnamed"] == "draws permutation and names no scheme key"
    assert names["planted_sign_flip"] == "draws sign flip and names no scheme key"


def test_a_bootstrap_or_a_draw_free_or_named_callable_is_not_reported(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S10_EXCUSED", {})
    examined, found = build_fact_graph.scheme_scan(
        planted_package(planted_bootstrap, planted_no_draw, planted_draws_named))
    assert examined == 3
    assert found == [], "a bootstrap interval is not a null, and the other two draw none unnamed"


def test_a_planted_excuse_skips_its_callable_and_a_stale_one_is_reported(monkeypatch):
    module = planted_draws_unnamed.__module__
    monkeypatch.setattr(build_fact_graph, "S10_EXCUSED", {
        (module, "planted_draws_unnamed"): "planted: excused for the test",
        (module, "planted_no_draw"): "planted: once drew a null",
    })
    _, found = build_fact_graph.scheme_scan(planted_package(*PLANTED_SCHEMES))
    names = reported(found)
    assert "planted_draws_unnamed" not in names, "an excused callable is skipped"
    assert set(names) == {"planted_sign_flip", "planted_no_draw"}
    assert names["planted_no_draw"] == (
        "S10_EXCUSED lists it, but it draws no unnamed null: stale")


def test_a_callable_whose_source_cannot_be_read_is_a_finding_not_a_pass(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S10_EXCUSED", {})
    namespace = {}
    exec("def drawn_without_source(x, rng):\n    return rng.permutation(x)\n", namespace)
    examined, found = build_fact_graph.scheme_scan(
        planted_package(namespace["drawn_without_source"]))
    assert examined == 1
    assert [reason for _, reason in found] == ["source unreadable: not checked"]


def test_the_permutation_schemes_predicate_is_violated_by_a_planted_unnamed_null(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S10_EXCUSED", {})
    examined, found = build_fact_graph.scheme_scan(planted_package(*PLANTED_SCHEMES))
    g = {"entities": {"scheme_examined": examined}, "relations": {"permutation_schemes": found}}
    found_status, reasons = status(g, "computed:permutation_schemes")
    assert found_status == fact_gate.VIOLATED
    assert any("planted_draws_unnamed" in reason for reason in reasons), reasons


def test_the_permutation_schemes_predicate_holds_when_every_planted_null_is_named(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S10_EXCUSED", {})
    examined, found = build_fact_graph.scheme_scan(
        planted_package(planted_draws_named, planted_no_draw, planted_bootstrap))
    g = {"entities": {"scheme_examined": examined}, "relations": {"permutation_schemes": found}}
    assert status(g, "computed:permutation_schemes") == (fact_gate.HELD, [])


def test_a_scheme_scan_that_examines_nothing_is_a_failure():
    g = {"entities": {"scheme_examined": 0}, "relations": {"permutation_schemes": []}}
    found_status, reasons = status(g, "computed:permutation_schemes")
    assert found_status == fact_gate.VIOLATED
    assert reasons == ["computed:permutation_schemes: the graph examined no public callable, "
                       "so no scheme could be checked"]


def test_the_live_scheme_scan_examines_every_public_callable(live):
    _, g = live
    assert g["entities"]["scheme_examined"] == len(
        build_fact_graph._public_callables(build_fact_graph._checkout_jnwb()))


def test_the_live_tree_has_no_unnamed_null(live):
    _, g = live
    assert g["relations"]["permutation_schemes"] == []


def test_an_unnamed_null_planted_in_the_live_graph_fails_s10(live):
    source, g = live
    excused = {f"{module}.{qualname}" for module, qualname in build_fact_graph.S10_EXCUSED}
    modules = {export: path[:-len(".py")].replace("/", ".")
               for path, export in g["relations"]["implements"]}
    planted_name = next(f"{modules[export]}.{export}" for export in sorted(g["entities"]["export"])
                        if f"{modules[export]}.{export}" not in excused)
    assert planted_name.rpartition(".")[2] in g["entities"]["export"], (
        "the planted callable must be present in the graph")
    planted = copy.deepcopy(g)
    planted["relations"]["permutation_schemes"] = [
        [planted_name, "planted: draws permutation and names no scheme key"]]
    clean = {fact: state for fact, state, _ in fact_gate.run(facts_path=source, graph=g)[1]}
    dirty = {fact: state for fact, state, _ in fact_gate.run(facts_path=source, graph=planted)[1]}
    assert clean["S10"] == fact_gate.HELD
    assert dirty["S10"] == fact_gate.VIOLATED


# ------------------------------------------------------------------------ fact S11: rng reports


def planted_consumes_unnamed(x, rng):
    return {"y": resolve_rng(rng, func_name="planted").permutation(x)}


def planted_reports_entropy(x, rng):
    return {"surrogate_seed_entropy": 0,
            "y": resolve_rng(rng, func_name="planted").permutation(x)}


def planted_reports_seed(x, rng):
    return {"seed": 3, "y": recorded_rng(rng, "planted")[0].permutation(x)}


def planted_consumes_nothing(x):
    return {"y": x + 1}


PLANTED_RNG = (planted_consumes_unnamed, planted_reports_entropy, planted_reports_seed,
               planted_consumes_nothing)


def test_a_planted_unnamed_consumption_is_reported_and_a_named_one_is_not(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
    examined, found = build_fact_graph.rng_scan(planted_package(*PLANTED_RNG))
    assert set(reported(found)) == {"planted_consumes_unnamed"}


def test_the_rng_scan_examines_every_planted_callable_and_names_what_it_consumed(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
    examined, found = build_fact_graph.rng_scan(planted_package(*PLANTED_RNG))
    assert examined == len(PLANTED_RNG) == 4, "the scan must examine every planted callable"
    names = reported(found)
    assert names["planted_consumes_unnamed"] == (
        "consumes randomness (resolve_rng) and reports no rng key")


def test_a_consumption_free_or_named_callable_is_not_reported(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
    examined, found = build_fact_graph.rng_scan(
        planted_package(planted_reports_entropy, planted_reports_seed, planted_consumes_nothing))
    assert examined == 3
    assert found == [], "a named consumption and a draw-free callable are not findings"


def test_a_planted_rng_excuse_skips_its_callable_and_a_stale_one_is_reported(monkeypatch):
    module = planted_consumes_unnamed.__module__
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {
        (module, "planted_consumes_unnamed"): "planted: excused for the test",
        (module, "planted_consumes_nothing"): "planted: once consumed randomness",
    })
    _, found = build_fact_graph.rng_scan(planted_package(*PLANTED_RNG))
    names = reported(found)
    assert "planted_consumes_unnamed" not in names, "an excused callable is skipped"
    assert set(names) == {"planted_consumes_nothing"}
    assert names["planted_consumes_nothing"] == (
        "S11_EXCUSED lists it, but it consumes no unnamed randomness: stale")


def test_a_callable_whose_source_cannot_be_read_is_an_rng_finding_not_a_pass(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
    namespace = {}
    exec("def consumed_without_source(x, rng):\n"
         "    return resolve_rng(rng, func_name=\"planted\")\n", namespace)
    examined, found = build_fact_graph.rng_scan(
        planted_package(namespace["consumed_without_source"]))
    assert examined == 1
    assert [reason for _, reason in found] == ["source unreadable: not checked"]


def test_the_rng_reports_predicate_is_violated_by_a_planted_unnamed_consumption(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
    examined, found = build_fact_graph.rng_scan(planted_package(*PLANTED_RNG))
    g = {"entities": {"rng_examined": examined}, "relations": {"rng_reports": found}}
    found_status, reasons = status(g, "computed:rng_reports")
    assert found_status == fact_gate.VIOLATED
    assert any("planted_consumes_unnamed" in reason for reason in reasons), reasons


def test_the_rng_reports_predicate_holds_when_every_planted_consumption_is_named(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "S11_EXCUSED", {})
    examined, found = build_fact_graph.rng_scan(
        planted_package(planted_reports_entropy, planted_reports_seed, planted_consumes_nothing))
    g = {"entities": {"rng_examined": examined}, "relations": {"rng_reports": found}}
    assert status(g, "computed:rng_reports") == (fact_gate.HELD, [])


def test_an_rng_scan_that_examines_nothing_is_a_failure():
    g = {"entities": {"rng_examined": 0}, "relations": {"rng_reports": []}}
    found_status, reasons = status(g, "computed:rng_reports")
    assert found_status == fact_gate.VIOLATED
    assert reasons == ["computed:rng_reports: the graph examined no public callable, "
                       "so no rng report could be checked"]


def test_the_live_rng_scan_examines_every_public_callable(live):
    _, g = live
    assert g["entities"]["rng_examined"] == len(
        build_fact_graph._public_callables(build_fact_graph._checkout_jnwb()))


def test_the_live_tree_has_no_unnamed_randomness(live):
    _, g = live
    assert g["relations"]["rng_reports"] == []


def test_unnamed_randomness_planted_in_the_live_graph_fails_s11(live):
    source, g = live
    excused = {f"{module}.{qualname}" for module, qualname in build_fact_graph.S11_EXCUSED}
    modules = {export: path[:-len(".py")].replace("/", ".")
               for path, export in g["relations"]["implements"]}
    planted_name = next(f"{modules[export]}.{export}" for export in sorted(g["entities"]["export"])
                        if f"{modules[export]}.{export}" not in excused)
    assert planted_name.rpartition(".")[2] in g["entities"]["export"], (
        "the planted callable must be present in the graph")
    planted = copy.deepcopy(g)
    planted["relations"]["rng_reports"] = [
        [planted_name, "planted: consumes randomness (resolve_rng) and reports no rng key"]]
    clean = {fact: state for fact, state, _ in fact_gate.run(facts_path=source, graph=g)[1]}
    dirty = {fact: state for fact, state, _ in fact_gate.run(facts_path=source, graph=planted)[1]}
    assert clean["S11"] == fact_gate.HELD
    assert dirty["S11"] == fact_gate.VIOLATED


# ------------------------------------------------------------------------ fact I2: named units and defaults


def planted_rate_silent(x):
    return x * 1000


def planted_rate_suffixed(x_ms):
    return x_ms * 1000


def planted_rate_declared(x, units="ms"):
    return x * 1000


PLANTED_RATES = (planted_rate_silent, planted_rate_suffixed, planted_rate_declared)


def planted_mode_target(a, mode="mean"):
    return (a, mode)


def planted_mode_silent(a):
    return planted_mode_target(a, mode="median")


def planted_mode_passthrough(a, mode="median"):
    return planted_mode_target(a, mode=mode)


def planted_mode_default(a):
    return planted_mode_target(a, mode="mean")


PLANTED_MODES = (planted_mode_target, planted_mode_silent, planted_mode_passthrough,
                 planted_mode_default)


def planted_lfp_filter(lfp):
    return {"filtered": lfp}


def planted_spikes_consumer(spike_times):
    return planted_lfp_filter(spike_times)


def planted_spikes_declared(spike_times):
    return {"n": len(spike_times)}


def _planted_forward(x):
    return planted_lfp_filter(x)


def planted_spikes_via_helper(spike_times):
    return _planted_forward(spike_times)


def signature_declarations(monkeypatch, declared, extra=()):
    """Point ``DECLARATIONS`` at the planted functions the caller names (name to the set of
    classes it declares), plus each raw key of ``extra`` as a stale entry."""
    from jnwb import _declarations

    def declaration(input_class):
        return _declarations.Declaration(
            input_class=frozenset(input_class),
            estimator="planted estimator",
            estimand="planted estimand",
            unit="planted unit",
            base="seconds",
        )

    module = planted_lfp_filter.__module__
    decls = {f"{globals()[name].__module__}.{name}": declaration(classes)
             for name, classes in declared.items()}
    decls.update({f"{module}.{key}": declaration({"spikes"}) for key in extra})
    monkeypatch.setattr(_declarations, "DECLARATIONS", decls)


def test_a_planted_silent_scaling_is_reported_and_named_ones_are_not(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "I2_UNIT_EXCUSED", {})
    examined, found = build_fact_graph.unit_scan(planted_package(*PLANTED_RATES))
    assert examined == len(PLANTED_RATES) == 3, "the scan must examine every planted callable"
    assert set(reported(found)) == {"planted_rate_silent"}
    [reason] = [reason for _, reason in found]
    assert "scales parameter 'x' by 1000" in reason and "names no unit" in reason


def test_a_planted_unit_excuse_skips_its_callable_and_a_stale_one_is_reported(monkeypatch):
    module = planted_rate_silent.__module__
    monkeypatch.setattr(build_fact_graph, "I2_UNIT_EXCUSED", {
        (module, "planted_rate_silent"): "planted: excused for the test",
        (module, "planted_rate_suffixed"): "planted: once scaled a parameter",
    })
    _, found = build_fact_graph.unit_scan(planted_package(*PLANTED_RATES))
    names = reported(found)
    assert "planted_rate_silent" not in names, "an excused callable is skipped"
    assert set(names) == {"planted_rate_suffixed"}
    assert names["planted_rate_suffixed"] == (
        "I2_UNIT_EXCUSED lists it, but it scales no parameter by a unit factor: stale")


def test_a_callable_whose_source_cannot_be_read_is_a_unit_finding_not_a_pass(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "I2_UNIT_EXCUSED", {})
    namespace = {}
    exec("def scaled_without_source(x):\n    return x * 1000\n", namespace)
    examined, found = build_fact_graph.unit_scan(
        planted_package(namespace["scaled_without_source"]))
    assert examined == 1
    assert [reason for _, reason in found] == ["source unreadable: not checked"]


def test_the_unit_conversions_predicate_is_violated_by_a_planted_silent_scaling(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "I2_UNIT_EXCUSED", {})
    examined, found = build_fact_graph.unit_scan(planted_package(*PLANTED_RATES))
    g = {"entities": {"unit_examined": examined}, "relations": {"unit_conversions": found}}
    found_status, reasons = status(g, "computed:unit_conversions")
    assert found_status == fact_gate.VIOLATED
    assert any("planted_rate_silent" in reason for reason in reasons), reasons


def test_the_unit_conversions_predicate_holds_when_every_planted_scaling_is_named(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "I2_UNIT_EXCUSED", {})
    examined, found = build_fact_graph.unit_scan(
        planted_package(planted_rate_suffixed, planted_rate_declared))
    g = {"entities": {"unit_examined": examined}, "relations": {"unit_conversions": found}}
    assert status(g, "computed:unit_conversions") == (fact_gate.HELD, [])


def test_a_unit_scan_that_examines_nothing_is_a_failure():
    g = {"entities": {"unit_examined": 0}, "relations": {"unit_conversions": []}}
    found_status, reasons = status(g, "computed:unit_conversions")
    assert found_status == fact_gate.VIOLATED
    assert reasons == ["computed:unit_conversions: the graph examined no public callable, "
                       "so no unit conversion could be checked"]


def test_a_planted_silent_default_change_is_reported_and_named_ones_are_not(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "I2_WRAPPER_EXCUSED", {})
    examined, found = build_fact_graph.wrapper_scan(planted_package(*PLANTED_MODES))
    assert examined == len(PLANTED_MODES) == 4, "the scan must examine every planted callable"
    assert set(reported(found)) == {"planted_mode_silent"}
    [reason] = [reason for _, reason in found]
    assert "passes mode='median'" in reason and "whose default is 'mean'" in reason


def test_a_planted_wrapper_excuse_skips_its_callable_and_a_stale_one_is_reported(monkeypatch):
    module = planted_mode_silent.__module__
    monkeypatch.setattr(build_fact_graph, "I2_WRAPPER_EXCUSED", {
        (module, "planted_mode_silent"): "planted: excused for the test",
        (module, "planted_mode_default"): "planted: once changed a default",
    })
    _, found = build_fact_graph.wrapper_scan(planted_package(*PLANTED_MODES))
    names = reported(found)
    assert "planted_mode_silent" not in names, "an excused callable is skipped"
    assert set(names) == {"planted_mode_default"}
    assert names["planted_mode_default"] == (
        "I2_WRAPPER_EXCUSED lists it, but it passes no literal over a default: stale")


def test_a_callable_whose_source_cannot_be_read_is_a_wrapper_finding_not_a_pass(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "I2_WRAPPER_EXCUSED", {})
    namespace = {}
    exec("def wrapped_without_source(a):\n"
         "    return planted_mode_target(a, mode=\"median\")\n", namespace)
    examined, found = build_fact_graph.wrapper_scan(
        planted_package(namespace["wrapped_without_source"]))
    assert examined == 1
    assert [reason for _, reason in found] == ["source unreadable: not checked"]


def test_the_wrapper_defaults_predicate_is_violated_by_a_planted_silent_change(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "I2_WRAPPER_EXCUSED", {})
    examined, found = build_fact_graph.wrapper_scan(planted_package(*PLANTED_MODES))
    g = {"entities": {"wrapper_examined": examined}, "relations": {"wrapper_defaults": found}}
    found_status, reasons = status(g, "computed:wrapper_defaults")
    assert found_status == fact_gate.VIOLATED
    assert any("planted_mode_silent" in reason for reason in reasons), reasons


def test_the_wrapper_defaults_predicate_holds_when_every_planted_default_is_named(monkeypatch):
    monkeypatch.setattr(build_fact_graph, "I2_WRAPPER_EXCUSED", {})
    examined, found = build_fact_graph.wrapper_scan(
        planted_package(planted_mode_target, planted_mode_passthrough, planted_mode_default))
    g = {"entities": {"wrapper_examined": examined}, "relations": {"wrapper_defaults": found}}
    assert status(g, "computed:wrapper_defaults") == (fact_gate.HELD, [])


def test_a_wrapper_scan_that_examines_nothing_is_a_failure():
    g = {"entities": {"wrapper_examined": 0}, "relations": {"wrapper_defaults": []}}
    found_status, reasons = status(g, "computed:wrapper_defaults")
    assert found_status == fact_gate.VIOLATED
    assert reasons == ["computed:wrapper_defaults: the graph examined no public callable, "
                       "so no wrapper default could be checked"]


def test_the_live_tree_lists_its_silent_unit_conversions_and_wrapper_defaults(live):
    _, g = live
    callables = build_fact_graph._public_callables(build_fact_graph._checkout_jnwb())
    assert g["entities"]["unit_examined"] == len(callables)
    assert g["entities"]["wrapper_examined"] == len(callables)
    assert g["entities"]["unit_examined"] > 200
    assert g["entities"]["wrapper_examined"] > 200
    assert g["relations"]["unit_conversions"] == []
    assert g["relations"]["wrapper_defaults"] == []


# ------------------------------------------------------------------------ fact B3: cited choice defaults


def planted_window_default(x, window_ms=(-1000, 2000)):
    return x


def planted_window_taper(x, window="hann"):
    return x


def planted_time_window_none(x, time_window=None):
    return x


def planted_window_s_required(*, window_s):
    return window_s


PLANTED_CHOICES = (planted_window_default, planted_window_taper, planted_time_window_none,
                   planted_window_s_required)


def b3_lexicon():
    """The choice names the live fact stack's constant holds, so the tests hold no copy."""
    text = build_fact_graph.FACT_STACK.read_text(encoding="utf-8")
    return build_fact_graph.read_constants(text)["B3 choice names"]


def b3_row(operation, parameter):
    """One well-formed exceptions row for the callable and parameter named."""
    return {"Operation": operation, "Parameter": parameter, "Default": "planted default",
            "Reason": "planted: cited for the test", "Evidence": "planted: evidence"}


def test_a_planted_defaulted_window_ms_and_a_none_time_window_are_reported():
    examined, found = build_fact_graph.choice_default_scan(
        planted_package(*PLANTED_CHOICES), b3_lexicon(), [])
    assert examined == len(PLANTED_CHOICES) == 4, "the scan must examine every planted callable"
    names = reported(found)
    assert set(names) == {"planted_window_default", "planted_time_window_none"}
    assert "parameter 'window_ms' defaults to (-1000, 2000)" in names["planted_window_default"]
    assert "parameter 'time_window' defaults to None" in names["planted_time_window_none"]


def test_a_taper_window_and_a_required_keyword_only_window_s_are_not_findings():
    examined, found = build_fact_graph.choice_default_scan(
        planted_package(planted_window_taper, planted_window_s_required), b3_lexicon(), [])
    assert examined == 2
    assert found == []


def test_an_exceptions_row_excuses_its_parameter_in_both_operation_forms():
    module = planted_window_default.__module__
    for operation in (f"{module}.planted_window_default", "planted_window_default"):
        _, found = build_fact_graph.choice_default_scan(
            planted_package(planted_window_default), b3_lexicon(),
            [b3_row(operation, "window_ms")])
        assert reported(found) == {}, operation


def test_a_backticked_exceptions_row_as_the_fact_stack_writes_it_excuses_its_parameter():
    text = ("## B3 exceptions\n\n| Operation | Parameter | Default | Reason | Evidence |\n"
            "|---|---|---|---|---|\n"
            "| `planted_window_default` | `window_ms` | `(-1000, 2000)` | planted | planted |\n")
    rows = build_fact_graph.read_b3_exceptions(text)
    assert len(rows) == 1, "the fixture must hold one row"
    _, found = build_fact_graph.choice_default_scan(
        planted_package(planted_window_default), b3_lexicon(), rows)
    assert found == []


def test_a_stale_exceptions_row_is_reported():
    _, found = build_fact_graph.choice_default_scan(
        planted_package(*PLANTED_CHOICES), b3_lexicon(),
        [b3_row("planted_window_taper", "window"), b3_row("planted_gone", "time_window")])
    names = reported(found)
    assert "stale" in names["planted_gone"]
    assert "stale" in names["planted_window_taper"], "a taper window sits outside the lexicon"


def test_a_callable_whose_signature_cannot_be_read_is_a_choice_finding_not_a_pass():
    planted = planted_window_default
    planted.__signature__ = 42  # type: ignore[assignment]
    try:
        examined, found = build_fact_graph.choice_default_scan(
            planted_package(planted), b3_lexicon(), [])
        assert examined == 1
        assert [reason for _, reason in found] == ["signature unreadable: not checked"]
    finally:
        del planted.__signature__


def test_the_choice_defaults_predicate_is_violated_by_a_planted_default():
    examined, found = build_fact_graph.choice_default_scan(
        planted_package(*PLANTED_CHOICES), b3_lexicon(), [])
    g = {"entities": {"choice_examined": examined}, "relations": {"choice_defaults": found}}
    found_status, reasons = status(g, "computed:choice_defaults")
    assert found_status == fact_gate.VIOLATED
    assert any("planted_window_default" in reason for reason in reasons), reasons


def test_the_choice_defaults_predicate_holds_when_every_planted_default_is_excused():
    module = planted_window_default.__module__
    exceptions = [b3_row(f"{module}.planted_window_default", "window_ms"),
                  b3_row("planted_time_window_none", "time_window")]
    examined, found = build_fact_graph.choice_default_scan(
        planted_package(planted_window_default, planted_time_window_none), b3_lexicon(),
        exceptions)
    g = {"entities": {"choice_examined": examined}, "relations": {"choice_defaults": found}}
    assert status(g, "computed:choice_defaults") == (fact_gate.HELD, [])


def test_a_choice_scan_that_examines_nothing_is_a_failure():
    g = {"entities": {"choice_examined": 0}, "relations": {"choice_defaults": []}}
    found_status, reasons = status(g, "computed:choice_defaults")
    assert found_status == fact_gate.VIOLATED
    assert reasons == ["computed:choice_defaults: the graph examined no public callable, "
                       "so no choice default could be checked"]


class _PlantedBase:
    def planted_inherited(self, x, window_ms=(-1000, 2000)):
        return x


class PlantedChild(_PlantedBase):
    pass


def test_an_inherited_defaulted_window_and_a_partial_export_are_choice_findings():
    planted = functools.partial(planted_window_default, window_ms=(0, 1))
    package = types.SimpleNamespace(__name__=__name__.split(".")[0],
                                    __all__=["PlantedChild", "planted_partial"],
                                    PlantedChild=PlantedChild, planted_partial=planted)
    assert _PlantedBase.__module__.split(".")[0] == package.__name__, \
        "the fixture's base must belong to the planted package"
    examined, found = build_fact_graph.choice_default_scan(package, b3_lexicon(), [])
    assert examined == 2
    reasons = {name.rsplit(".", 1)[-1]: reason for name, reason in found}
    assert reasons["planted_inherited"] == "parameter 'window_ms' defaults to (-1000, 2000)"
    assert reasons["planted_partial"] == "a partial, not a function: not checked"


def test_the_live_scan_examines_every_public_callable():
    package = build_fact_graph._checkout_jnwb()
    text = build_fact_graph.FACT_STACK.read_text(encoding="utf-8")
    examined, _ = build_fact_graph.choice_default_scan(
        package, build_fact_graph.read_constants(text)["B3 choice names"],
        build_fact_graph.read_b3_exceptions(text))
    assert examined == (len(build_fact_graph._public_callables(package))
                        + len(build_fact_graph._unwalked_callables(package)))
    assert examined > 0


# ------------------------------------------------------------------------ fact S8: claim classes

CLAIM_TABLE = (
    "| Claim | What it states | What jnwb estimates it with | What it does not license |\n"
    "|---|---|---|---|\n"
    "| Magnitude | how strongly two signals are coupled, without a sign | correlation, "
    "mutual information, `cross_area_coherence`, `wpli` | a direction |\n"
    "| Direction | which signal leads, as a lag asymmetry | `granger`, `phase_slope_index`, "
    "`transfer_entropy`, the sign of `imaginary_coherency` | a delay |\n"
)


def planted_claim_root(tmp_path, table=CLAIM_TABLE):
    """A root whose docs page holds the claim table, so the scan reads its estimators there."""
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "architecture.md").write_text(f"## Claims\n\n{table}\n", encoding="utf-8")
    return tmp_path


PLANTED_LABELS = (
    "import matplotlib.pyplot as plt\n"
    "\n"
    "fig, ax = plt.subplots()\n"
    "ax2 = fig.add_subplot()\n"
    "ax2.set_ylabel(\"Phase Slope (rad/Hz)\")\n"
    "ax.set_ylabel(\"PSI per frequency bin (dimensionless)\")\n"
    "ax.set_title(\"wPLI delay map\")\n"
    "ax.set_title(\"zFLIP delay\")\n"
    "ax.set_title(\"Spectral Granger causality\")\n"
    "ax.set_title(\"Granger: X drives Y\")\n"
)


def reported_lines(found):
    """The line numbers the scan's findings name, keyed to their reasons."""
    return {int(reason.split()[1].rstrip(":")): reason for _, reason in found
            if reason.startswith("line ")}


def test_a_label_naming_an_estimator_beside_a_higher_term_is_reported(tmp_path):
    root = planted_claim_root(tmp_path)
    (root / "fig.py").write_text(PLANTED_LABELS, encoding="utf-8")
    examined, found = build_fact_graph.claim_class_scan(root, ["fig.py"])
    assert examined == {"labels": 6, "units": 0}, "every label is examined; no file is under jnwb/"
    by_line = reported_lines(found)
    assert sorted(by_line) == [5, 7, 10], by_line
    assert "Phase Slope (rad/Hz)" in by_line[5] and "phase_slope_index" in by_line[5] \
        and "rad/Hz" in by_line[5]
    assert "wPLI delay map" in by_line[7] and "wpli" in by_line[7] and "delay" in by_line[7]
    assert "Granger: X drives Y" in by_line[10] and "granger" in by_line[10] \
        and "drives" in by_line[10]


PLANTED_LABEL_FORMS = (
    "import matplotlib.pyplot as plt\n"
    "\n"
    "LABEL = \"Phase Slope (rad/Hz)\"\n"
    "fig, ax = plt.subplots()\n"
    "plt.ylabel(\"Phase Slope (rad/Hz)\")\n"
    "ax.set_ylabel(\"Phase Slope (\" + \"rad/Hz)\")\n"
    "ax.set_ylabel(LABEL)\n"
    "ax.set_title(\"Phase Slope Index rad/Hz\")\n"
    "ax.set_title(\"Granger: X driven by Y\")\n"
    "ax.set_title(\"phase-slope delay\")\n"
    "ax.set_ylabel(\"PSI per session (s)\")\n"
)


def test_label_forms_that_hide_a_higher_term_are_reported(tmp_path):
    root = planted_claim_root(tmp_path)
    (root / "fig.py").write_text(PLANTED_LABEL_FORMS, encoding="utf-8")
    examined, found = build_fact_graph.claim_class_scan(root, ["fig.py"])
    assert examined == {"labels": 7, "units": 0}, "a pyplot call, a sum and a name are labels"
    by_line = reported_lines(found)
    assert sorted(by_line) == [5, 6, 7, 8, 9, 10, 11], by_line
    assert "driven" in by_line[9] and "phase_slope_index" in by_line[10]


PLANTED_LABEL_SHAPES = (
    "from matplotlib.pyplot import xlabel\n"
    "\n"
    "LABEL = \"wpli delay\"\n"
    "TITLE: str = \"Granger: X causing Y\"\n"
    "xlabel(\"Phase Slope (rad/Hz)\")\n"
    "ax.set_ylabel(LABEL)\n"
    "LABEL = \"safe\"\n"
    "ax.set_title(TITLE)\n"
    "ax.set_title(\"wPLI causality map\")\n"
    "ax.text(0.1, 0.2, \"wpli delay\")\n"
    "ax.legend([\"coherence\", \"PSI drivers\"])\n"
    "ax.set_title(\"wpli latency %d\" % 3)\n"
    "ax.set_title(\"{} wpli latency\".format(3))\n"
)


def test_label_shapes_that_hide_a_higher_term_are_reported(tmp_path):
    root = planted_claim_root(tmp_path)
    (root / "fig.py").write_text(PLANTED_LABEL_SHAPES, encoding="utf-8")
    examined, found = build_fact_graph.claim_class_scan(root, ["fig.py"])
    by_line = reported_lines(found)
    assert sorted(by_line) == [5, 6, 8, 9, 10, 11, 12, 13], by_line
    assert examined["labels"] >= 8


PLANTED_LABEL_WRAPPERS = (
    "BASE = \"wpli delay\"\n"
    "ALIAS = BASE\n"
    "CHOSEN = \"PSI lag\" if True else \"PSI latency\"\n"
    "style.panel_title(ax, \"A\", \"wPLI delay map\")\n"
    "ax.set(xlabel=\"Granger drives\", ylabel=\"power\")\n"
    "ax.set_title(ALIAS)\n"
    "ax.set_title(CHOSEN)\n"
    "ax.set_title(\"wPLI causation map\")\n"
)


def test_the_title_wrapper_axes_set_aliases_and_branches_are_read(tmp_path):
    root = planted_claim_root(tmp_path)
    (root / "fig.py").write_text(PLANTED_LABEL_WRAPPERS, encoding="utf-8")
    _, found = build_fact_graph.claim_class_scan(root, ["fig.py"])
    assert sorted(reported_lines(found)) == [4, 5, 6, 7, 8], reported_lines(found)


def test_a_unit_held_in_a_module_constant_is_reported(tmp_path):
    root = planted_claim_root(tmp_path)
    (root / "jnwb").mkdir()
    (root / "jnwb" / "planted.py").write_text(
        "UNIT = \"rad/Hz\"\n"
        "def phase_slope_index(lfp):\n"
        "    return DirectedResult(1.0, unit=UNIT)\n", encoding="utf-8")
    examined, found = build_fact_graph.claim_class_scan(root, ["jnwb/planted.py"])
    assert examined["units"] == 1
    [reason] = [reason for _, reason in found]
    assert "rad/Hz" in reason


def test_a_label_without_an_estimator_or_without_a_higher_term_is_not_reported(tmp_path):
    root = planted_claim_root(tmp_path)
    (root / "fig.py").write_text(PLANTED_LABELS, encoding="utf-8")
    examined, found = build_fact_graph.claim_class_scan(root, ["fig.py"])
    assert examined["labels"] == 6, "the labels must be read for their absence to mean anything"
    reported = " ".join(reason for _, reason in found)
    assert "PSI per frequency bin" not in reported, "dimensionless is no delay unit"
    assert "zFLIP" not in reported, "zflip is no magnitude or direction estimator"
    assert "Spectral Granger causality" not in reported, "the method name is no causal claim"


PLANTED_DIRECTION_MODULE = (
    "class DirectedResult:\n"
    "    def __init__(self, value, unit=\"dimensionless\"):\n"
    "        self.unit = unit\n"
    "\n"
    "def phase_slope_index(lfp):\n"
    "    return DirectedResult(1.0, unit=\"dimensionless\")\n"
    "\n"
    "delayed = DirectedResult(1.0, unit=\"rad/Hz\")\n"
    "counted = DirectedResult(1.0, unit=\"bits\")\n"
)
PLANTED_UNOWNED_MODULE = (
    "class DirectedResult:\n"
    "    pass\n"
    "\n"
    "delayed = DirectedResult(1.0, unit=\"rad/Hz\")\n"
)


def test_a_planted_unit_literal_in_a_module_defining_an_estimator_is_reported(tmp_path):
    root = planted_claim_root(tmp_path)
    (root / "jnwb").mkdir()
    (root / "jnwb" / "planted.py").write_text(PLANTED_DIRECTION_MODULE, encoding="utf-8")
    examined, found = build_fact_graph.claim_class_scan(root, ["jnwb/planted.py"])
    assert examined["units"] == 3, "every unit literal of a *Result call is examined"
    [reason] = [reason for _, reason in found]
    assert "unit 'rad/Hz'" in reason and "phase_slope_index" in reason
    assert "bits" not in reason, "bits is neither a delay unit nor an inference word"


def test_a_unit_literal_outside_a_defining_module_is_not_reported(tmp_path):
    root = planted_claim_root(tmp_path)
    (root / "jnwb").mkdir()
    (root / "jnwb" / "other.py").write_text(PLANTED_UNOWNED_MODULE, encoding="utf-8")
    examined, found = build_fact_graph.claim_class_scan(root, ["jnwb/other.py"])
    assert examined["units"] == 1, "the literal is examined wherever it sits"
    assert found == [], "the module defines no estimand's estimator"


@pytest.mark.parametrize("page", [None, "## Other\n\nno claim table here\n",
                                  CLAIM_TABLE.split("| Direction")[0]],
                         ids=["no page", "no table", "no direction row"])
def test_a_missing_claim_table_or_row_raises(tmp_path, page):
    root = planted_claim_root(tmp_path, page) if page is not None else tmp_path
    with pytest.raises(ValueError, match="claim table|estimand row"):
        build_fact_graph.claim_class_scan(root, [])


def test_a_short_name_whose_estimator_is_in_neither_row_is_stale(tmp_path):
    reduced = CLAIM_TABLE.replace(
        "`granger`, `phase_slope_index`, `transfer_entropy`, the sign of `imaginary_coherency`",
        "`granger`")
    root = planted_claim_root(tmp_path, reduced)
    examined, found = build_fact_graph.claim_class_scan(root, [])
    assert examined == {"labels": 0, "units": 0}
    stale = sorted(reason.split("'")[1] for _, reason in found if reason.endswith(": stale"))
    assert stale == ["icoh", "imaginary coherency", "phase slope", "psi", "te",
                     "transfer entropy"]


def test_the_claim_class_labels_predicate_is_violated_by_a_planted_finding():
    g = {"entities": {"claim_examined": {"labels": 1, "units": 1}},
         "relations": {"claim_class_labels": [["jnwb/a.py", "line 3: planted"]]}}
    found_status, reasons = status(g, "computed:claim_class_labels")
    assert found_status == fact_gate.VIOLATED
    assert reasons == ["computed:claim_class_labels: jnwb/a.py: line 3: planted"]
    g["relations"]["claim_class_labels"] = []
    assert status(g, "computed:claim_class_labels") == (fact_gate.HELD, [])


@pytest.mark.parametrize("examined", [{}, {"labels": 0, "units": 0}],
                         ids=["no counts", "zero counts"])
def test_a_claim_class_scan_that_examines_nothing_is_a_failure(examined):
    g = {"entities": {"claim_examined": examined}, "relations": {"claim_class_labels": []}}
    found_status, reasons = status(g, "computed:claim_class_labels")
    assert found_status == fact_gate.VIOLATED
    assert reasons == ["computed:claim_class_labels: the graph examined no label or unit "
                       "literal, so no claim class could be checked"]


def test_the_live_tree_examines_labels_and_unit_literals_for_claim_classes(live):
    _, g = live
    examined = g["entities"]["claim_examined"]
    assert examined["labels"] > 0, "the live tree holds figure labels to examine"
    assert examined["units"] > 0, "the live tree holds *Result unit literals to examine"
    assert g["relations"]["claim_class_labels"] == [], g["relations"]["claim_class_labels"]


def test_a_planted_signal_callable_with_no_declaration_is_reported(monkeypatch):
    signature_declarations(monkeypatch, {})
    examined, found = build_fact_graph.signature_types_scan(
        planted_package(planted_lfp_filter, planted_spikes_consumer))
    assert examined == 2, "the scan must examine every planted callable"
    assert set(reported(found)) == {"planted_lfp_filter", "planted_spikes_consumer"}
    assert set(reason for _, reason in found) == {
        "takes signal parameters but declares no input class"}


def test_a_planted_declaration_missing_the_class_its_parameters_show_is_reported(monkeypatch):
    signature_declarations(monkeypatch, {"planted_spikes_declared": {"lfp"}})
    examined, found = build_fact_graph.signature_types_scan(
        planted_package(planted_spikes_declared))
    assert examined == 1
    [reason] = [reason for _, reason in found]
    assert "declares input class ['lfp']" in reason
    assert "signal parameters show ['spikes']" in reason


def test_a_declaration_naming_a_class_beyond_its_parameter_names_holds(monkeypatch):
    """An input with a generic parameter name (a TFR beside spike counts) may add a class."""
    signature_declarations(monkeypatch, {})
    _, undeclared = build_fact_graph.signature_types_scan(planted_package(planted_spikes_declared))
    assert set(reported(undeclared)) == {"planted_spikes_declared"}, "fixture must be in the domain"
    signature_declarations(monkeypatch, {"planted_spikes_declared": {"lfp", "spikes"}})
    examined, found = build_fact_graph.signature_types_scan(
        planted_package(planted_spikes_declared))
    assert examined == 1
    assert found == []


def test_a_stale_declarations_key_is_reported(monkeypatch):
    signature_declarations(monkeypatch, {"planted_spikes_declared": {"spikes"}},
                           extra=("planted_gone",))
    _, found = build_fact_graph.signature_types_scan(planted_package(planted_spikes_declared))
    names = reported(found)
    assert set(names) == {"planted_gone"}
    assert names["planted_gone"] == ("DECLARATIONS lists it, but it takes no signal "
                                     "parameter: stale")


def test_a_planted_spikes_caller_reaching_an_lfp_callee_is_violated(monkeypatch):
    signature_declarations(monkeypatch, {"planted_spikes_consumer": {"spikes"},
                                         "planted_lfp_filter": {"lfp"}})
    examined, found = build_fact_graph.signature_types_scan(
        planted_package(planted_spikes_consumer, planted_lfp_filter))
    assert examined == 2
    assert set(reported(found)) == {"planted_spikes_consumer"}
    [reason] = [reason for _, reason in found]
    assert "planted_lfp_filter" in reason and "outside its declared class" in reason
    g = {"entities": {"signature_examined": examined}, "relations": {"signature_types": found}}
    found_status, reasons = status(g, "computed:signature_types")
    assert found_status == fact_gate.VIOLATED
    assert any("planted_spikes_consumer" in reason for reason in reasons), reasons


def test_an_edge_through_a_private_helper_is_violated(monkeypatch):
    signature_declarations(monkeypatch, {"planted_spikes_via_helper": {"spikes"},
                                         "planted_lfp_filter": {"lfp"}})
    examined, found = build_fact_graph.signature_types_scan(
        planted_package(planted_spikes_via_helper, planted_lfp_filter))
    assert examined == 2
    assert set(reported(found)) == {"planted_spikes_via_helper"}
    [reason] = [reason for _, reason in found]
    assert "_planted_forward" in reason and "planted_lfp_filter" in reason


def test_a_signature_types_scan_that_examines_nothing_is_a_failure():
    g = {"entities": {"signature_examined": 0}, "relations": {"signature_types": []}}
    found_status, reasons = status(g, "computed:signature_types")
    assert found_status == fact_gate.VIOLATED
    assert reasons == ["computed:signature_types: the graph examined no public callable, "
                       "so no signature type could be checked"]


def test_the_live_tree_examines_public_callables_for_signature_types(live):
    _, g = live
    callables = build_fact_graph._public_callables(build_fact_graph._checkout_jnwb())
    assert g["entities"]["signature_examined"] == len(callables)
    assert g["entities"]["signature_examined"] > 0
    # Every declaration is in the domain (a stale key is a finding), so an emptied domain or
    # declaration table cannot read as held.
    from jnwb import _declarations
    assert len(_declarations.DECLARATIONS) >= 33
    assert g["relations"]["signature_types"] == []
