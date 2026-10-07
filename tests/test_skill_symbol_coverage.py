"""Every public symbol is routed by a skill, or is excluded for a stated, checked reason.

A routing matrix that silently omits two thirds of the public API is not a matrix; it is a
sample. This module holds the whole of `jnwb.__all__` against the skill files: a symbol is
either mentioned by some skill, or it appears below with a category, and the category's own
assertion has to hold for it.

The same holds for modules, docs pages, example scripts and notebooks: each is named by a
skill or the nav, or is listed below with a reason a test checks against the tree.

The exclusions are not a mute list. An entry that names a symbol the package no longer
exports, or one a skill has since started routing, fails here -- a registry that can go stale
without erroring is the defect this file exists to prevent.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

import jnwb

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

WORD = re.compile(r"\b([A-Za-z_]\w*)\b")
# A routing row, not a passing mention: a bullet that calls the symbol. Prose naming a
# function teaches nothing about how to call it, so it does not count as routed.
CALL = re.compile(r"`jnwb\.(?:\w+\.)*(\w+)\(")

# Reached by handling what a routed operation raises, never by choosing it from a matrix.
ERRORS = [
    "AcquisitionNotFoundError",
    "AmbiguousAcquisitionError",
    "AmbiguousIntervalTableError",
    "AmbiguousLayoutError",
    "ChannelIndexError",
    "ColumnNotFoundError",
    "IntervalTableNotFoundError",
    "InvalidOnsetValueError",
    "MissingRequiredNWBFieldError",
    "NWBEventError",
    "NWBInspectError",
    "RaggedIndexRepairRefused",
    "SqueezedAttributeWarning",
    "UnitNotFoundError",
]

# The `jnwb.ontology` vocabulary: a data model for describing an analysis, not operations to
# choose between. No skill routes the module; a reader meets these types in
# `docs/02_paths_addressing_metadata.md`, and `test_excluded_ontology_types_come_from_the_ontology_module`
# holds each to the module.
ONTOLOGY = [
    "AlignedDataset",
    "Alignment",
    "Dataset",
    "Figure",
    "Interpretation",
    "Query",
    "Question",
]

# Containers a routed operation returns. Routing the operation routes the container; the
# mapping below is checked against the live return annotation.
RETURNED_BY = {
    "AperiodicFitResult": ["aperiodic_fit"],
    "ComplexTFR": ["complex_tfr"],
    "DirectedResult": ["granger", "granger_spectral", "phase_slope_index", "transfer_entropy",
                       "directed_connectivity"],
    "JRSAResult": ["jrsa"],
    "NWBValidationReport": ["validate_nwb"],
    "Preflight": ["preflight"],
    "RaggedIndexReport": ["check_ragged_indices"],
    "RaggedIndexRepair": ["repair_ragged_index"],
    "ProbeGeometry": ["probe_geometry"],
    "VFlipResult": ["vflip", "vflip_from_lfp"],
    "XFlipResult": ["xflip"],
    "ZFlipResult": ["zflip"],
}

# A namespace class: every operation on it is routed as `jnwb.StatisticalAnalysis.name(...)`,
# so routing the bare class as well would put two spellings of one call in the matrix.
NAMESPACES = ["StatisticalAnalysis"]

# The analyzer classes. Their methods compute on their own, so they are not facades over
# routed functions; routing rows for them were declined (2026-09-29, D8 (e)). The methods
# left without a row are listed per class below and held to the live class by
# `test_excluded_analyzer_methods_are_the_unrouted_ones`.
ANALYZERS = ["PopulationAnalyzer", "TFRAnalyzer", "UnitAnalyzer"]
ANALYZER_METHODS_WITHOUT_A_ROW = {
    "PopulationAnalyzer": ["compare_criteria", "distribution_by_area", "network_connectivity",
                           "pie_chart_data", "population_trajectory"],
    "TFRAnalyzer": ["average_across_channels", "by_layer", "compare_conditions",
                    "correlate_areas", "extract_band", "trial_average"],
    "UnitAnalyzer": ["autocorrelogram", "psth", "quality_metrics", "raster"],
}
RULINGS = ROOT / "artifacts" / "rulings" / "2026-09-29.md"

# Modules no skill routes, each with the reason its exclusion is checked against the tree.
# A module is routed when a skill names it or an ancestor package, or routes an export
# defined in it; a module that becomes routed fails `test_no_module_exclusion_is_stale`.
MODULE_EXCLUSIONS = {
    "jnwb.analyzers": "analyzers",
    "jnwb.bilinear": "unexported",
    "jnwb.gpu_pca": "unexported",
    "jnwb.nam": "unexported",
    "jnwb.mcp_server": "unexported",
    "jnwb.testing": "unexported",
}

# Pages and scripts reached by neither the nav nor a skill. A path that becomes routed
# fails `test_no_path_exclusion_is_stale`.
PATH_EXCLUSIONS = {
    "docs/01_architecture_and_philosophy.md": "redirect",
    "docs/documentation_form.md": "contract",
}

# Enumerations and tables that a routed operation validates its arguments against, plus the
# pointer an installed copy carries in place of the skills themselves -- SKILLS_URL is how a
# harness finds the routing rows, so it cannot be routed by one.
CONSTANTS = [
    "CANONICAL_BANDS", "DB_AGGREGATIONS", "DETECTION_TAILS", "RELATIVE_POWER_MODELS",
    "SKILLS_URL",
]

# The submodule alias; its contents are routed individually.
MODULES = ["io"]

# Undocumented internal guards. A symbol with no docstring cannot be routed honestly -- the
# row would have to invent the contract. These are candidates for de-export, not for routing.
INTERNAL = ["assert_mergeable"]

EXCLUDED = {
    **{n: "error" for n in ERRORS},
    **{n: "ontology" for n in ONTOLOGY},
    **{n: "returned" for n in RETURNED_BY},
    **{n: "analyzer" for n in ANALYZERS},
    **{n: "constant" for n in CONSTANTS},
    **{n: "namespace" for n in NAMESPACES},
    **{n: "module" for n in MODULES},
    **{n: "internal" for n in INTERNAL},
}


def _pages() -> dict[str, str]:
    pages = {p.parent.name: p.read_text(encoding="utf-8") for p in sorted(SKILLS.rglob("SKILL.md"))}
    assert len(pages) >= 7, f"only {len(pages)} skill pages found under {SKILLS}"
    return pages


@pytest.fixture(scope="module")
def mentioned() -> set[str]:
    words: set[str] = set()
    for text in _pages().values():
        words.update(WORD.findall(text))
    return words


@pytest.fixture(scope="module")
def routed() -> dict[str, set[str]]:
    """symbol -> the skills whose routing rows call it."""
    out: dict[str, set[str]] = {}
    for skill, text in _pages().items():
        for line in text.splitlines():
            if not line.lstrip().startswith("- "):
                continue
            for name in CALL.findall(line):
                out.setdefault(name, set()).add(skill)
    return out


def test_every_public_symbol_is_routed_or_excluded(
    mentioned: set[str], routed: dict[str, set[str]]
) -> None:
    public = sorted(jnwb.__all__)
    assert len(public) >= 150, f"only {len(public)} public symbols; the export list shrank"
    orphans = []
    for name in public:
        if name in EXCLUDED:
            continue
        # A callable has to be reachable as a call. A constant or a type only has to be
        # named, because there is no signature to teach.
        reachable = name in routed if callable(getattr(jnwb, name)) else name in mentioned
        if not reachable:
            orphans.append(name)
    assert not orphans, (
        f"{len(orphans)} public symbols are routed by no skill and carry no exclusion: "
        f"{orphans}"
    )


def test_most_of_the_public_api_is_actually_routed(routed: dict[str, set[str]]) -> None:
    public = sorted(jnwb.__all__)
    covered = [s for s in public if s in routed]
    # Guards the other direction: the test above could also be satisfied by excluding
    # everything. Every symbol an agent has to *choose* is reachable as a call.
    assert len(covered) >= 110, f"only {len(covered)} of {len(public)} symbols carry a row"


def test_the_router_sends_laminar_work_to_the_skill_that_routes_it() -> None:
    """The root router is the only entry point, so a subsystem it never names is unreachable.

    Which skill owns the layer estimators is read off the routing rows, not asserted here --
    moving `label_layers` to another skill has to move the router line with it.
    """
    owners: set[str] = set()
    for skill, text in _pages().items():
        for line in text.splitlines():
            if line.lstrip().startswith("- ") and "label_layers" in CALL.findall(line):
                owners.add(skill)
    assert len(owners) == 1, f"`label_layers` is routed by {owners or 'no skill'}"
    owner = owners.pop()
    router = (SKILLS / "jnwb" / "SKILL.md").read_text(encoding="utf-8")
    hits = [ln for ln in router.splitlines() if "aminar" in ln and owner in ln]
    assert hits, f"the root router names no laminar delegation to `{owner}`"


def test_no_exclusion_is_stale(routed: dict[str, set[str]]) -> None:
    public = set(jnwb.__all__)
    gone = sorted(n for n in EXCLUDED if n not in public)
    assert not gone, f"excluded symbols that are no longer exported: {gone}"
    # Prose may name an excluded type freely -- the row for `vflip` has to say what it
    # returns. What must not happen is an excluded symbol acquiring a routing row of its own.
    now_routed = sorted(n for n in EXCLUDED if n in routed)
    assert not now_routed, (
        f"excluded as out of routing scope, but a skill now routes them: {now_routed}. "
        f"Remove the exclusion rather than leaving two answers in the tree."
    )


def test_excluded_errors_are_exceptions() -> None:
    for name in ERRORS:
        obj = getattr(jnwb, name)
        assert isinstance(obj, type) and issubclass(obj, Exception), f"{name} is not an error"


def test_excluded_ontology_types_come_from_the_ontology_module() -> None:
    for name in ONTOLOGY:
        obj = getattr(jnwb, name)
        assert isinstance(obj, type), f"{name} is not a type"
        assert obj.__module__ == "jnwb.ontology", f"{name} lives in {obj.__module__}"


def test_excluded_containers_are_returned_by_a_routed_operation(
    routed: dict[str, set[str]]
) -> None:
    for name, producers in RETURNED_BY.items():
        for producer in producers:
            assert producer in jnwb.__all__, f"{producer} is not public"
            annotation = str(inspect.signature(getattr(jnwb, producer)).return_annotation)
            assert name in annotation, (
                f"{producer} is credited with returning {name}, but returns {annotation}"
            )
        carried = [p for p in producers if p in routed]
        assert carried, (
            f"{name} is excluded because {producers} return it, but no skill routes any of "
            f"them, so nothing reaches it"
        )


def test_excluded_namespaces_have_their_methods_routed(routed: dict[str, set[str]]) -> None:
    for name in NAMESPACES:
        cls = getattr(jnwb, name)
        assert isinstance(cls, type), f"{name} is not a class"
        methods = [m for m in dir(cls) if not m.startswith("_") and m in routed]
        assert methods, f"no method of {name} carries a routing row"


METHOD_CALL = re.compile(r"`jnwb\.(\w+)\.(\w+)\(")


def test_excluded_analyzers_are_classes_in_the_analyzers_module() -> None:
    for name in ANALYZERS:
        obj = getattr(jnwb, name)
        assert isinstance(obj, type), f"{name} is not a class"
        assert obj.__module__ == "jnwb.analyzers", f"{name} lives in {obj.__module__}"


def test_excluded_analyzer_methods_are_the_unrouted_ones() -> None:
    """The reason is that no row routes a method, so the list is the live class minus the rows."""
    assert sorted(ANALYZER_METHODS_WITHOUT_A_ROW) == sorted(ANALYZERS)
    with_row = set()
    for text in _pages().values():
        for line in text.splitlines():
            if line.lstrip().startswith("- "):
                with_row.update(METHOD_CALL.findall(line))
    for cls_name, listed in ANALYZER_METHODS_WITHOUT_A_ROW.items():
        cls = getattr(jnwb, cls_name)
        live = sorted(m for m, v in vars(cls).items()
                      if not m.startswith("_") and callable(getattr(cls, m)))
        routed_now = sorted(m for m in live if (cls_name, m) in with_row)
        assert not routed_now, f"{cls_name} methods now have a row; unlist them: {routed_now}"
        assert sorted(listed) == live, (
            f"{cls_name} public methods are {live}; the exclusion lists {sorted(listed)}. "
            f"A new method needs a row or a ruling, not a silent exclusion."
        )
    ruling = RULINGS.read_text(encoding="utf-8")
    row = next((ln for ln in ruling.splitlines() if ln.startswith("| D8")), "")
    assert "no new routing rows for the analyzer classes" in row, (
        f"{RULINGS.name} no longer holds the D8 ruling that the analyzer exclusion cites"
    )


def _public_modules() -> list[str]:
    names = []
    for path in sorted((ROOT / "jnwb").rglob("*.py")):
        parts = list(path.relative_to(ROOT).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if len(parts) < 2 or any(p.startswith("_") for p in parts[1:]):
            continue
        names.append(".".join(parts))
    return names


def _export_modules() -> dict[str, str]:
    """export -> the module that defines it, read off the live object."""
    out = {}
    for name in jnwb.__all__:
        module = getattr(getattr(jnwb, name), "__module__", None)
        if isinstance(module, str):
            out[name] = module
    return out


def _within(module: str, package: str) -> bool:
    return module == package or module.startswith(package + ".")


def _module_is_routed(module: str, text: str, routed: dict[str, set[str]]) -> bool:
    rel = module.removeprefix("jnwb.")
    path = rel.replace(".", "/")
    ancestors = [".".join(rel.split(".")[: i + 1]) for i in range(len(rel.split(".")))]
    if any(re.search(rf"\bjnwb\.{re.escape(a)}\b", text) for a in ancestors):
        return True
    if re.search(rf"\bjnwb/{re.escape(path)}(?:\.py|/)", text):
        return True
    return any(_within(m, module) for n, m in _export_modules().items() if n in routed)


def test_every_module_is_routed_or_excluded(routed: dict[str, set[str]]) -> None:
    text = "\n".join(_pages().values())
    modules = _public_modules()
    assert len(modules) >= 40, f"only {len(modules)} public modules found; the walk broke"
    orphans = [
        m for m in modules
        if not _module_is_routed(m, text, routed)
        and not any(_within(m, e) for e in MODULE_EXCLUSIONS)
    ]
    assert not orphans, f"modules no skill names or routes, with no exclusion: {orphans}"


def test_no_module_exclusion_is_stale(routed: dict[str, set[str]]) -> None:
    text = "\n".join(_pages().values())
    modules = set(_public_modules())
    for module in MODULE_EXCLUSIONS:
        assert module in modules, f"{module} is excluded but no longer exists"
        assert not _module_is_routed(module, text, routed), (
            f"{module} is routed now; remove its exclusion"
        )


def test_module_exclusion_reasons_hold() -> None:
    defined_in = {}
    for name, module in _export_modules().items():
        defined_in.setdefault(module, []).append(name)
    for module, reason in MODULE_EXCLUSIONS.items():
        exports = sorted(n for m, ns in defined_in.items() if _within(m, module) for n in ns)
        if reason == "unexported":
            assert not exports, f"{module} is excluded as unexported but defines {exports}"
        elif reason == "analyzers":
            assert exports and set(exports) <= set(ANALYZERS), f"{module} defines {exports}"
        else:
            raise AssertionError(f"{module}: unknown reason {reason!r}")


def _mkdocs_block(key: str) -> list[str]:
    """The lines under a top-level key of mkdocs.yml, up to the next top-level key."""
    lines = (ROOT / "mkdocs.yml").read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(key + ":"))
    block = []
    for ln in lines[start + 1:]:
        if ln and not ln[0].isspace() and not ln.startswith("#"):
            break
        block.append(ln)
    return block


def _nav_pages() -> set[str]:
    return {m for ln in _mkdocs_block("nav") for m in re.findall(r"([\w/.-]+\.md)\b", ln)}


def _skill_paths() -> set[str]:
    text = "\n".join(_pages().values())
    return set(re.findall(r"(?:docs|examples)/[\w./-]*[\w/]", text))


def _doc_pages() -> list[str]:
    return [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "docs").rglob("*.md"))]


def _example_files() -> list[str]:
    return [p.relative_to(ROOT).as_posix()
            for pattern in ("*.py", "*.ipynb") for p in sorted((ROOT / "examples").rglob(pattern))]


def _path_is_routed(path: str, nav: set[str], refs: set[str]) -> bool:
    if path.startswith("docs/") and path.removeprefix("docs/") in nav:
        return True
    return any(path == r or (r.endswith("/") and path.startswith(r)) for r in refs)


def test_every_page_script_and_notebook_is_routed_or_excluded() -> None:
    nav, refs = _nav_pages(), _skill_paths()
    pages, examples = _doc_pages(), _example_files()
    assert len(nav) >= 25 and len(pages) >= 25 and len(examples) >= 12, (
        f"{len(nav)} nav pages, {len(pages)} pages, {len(examples)} examples: a parser broke"
    )
    orphans = [p for p in pages + examples
               if not _path_is_routed(p, nav, refs) and p not in PATH_EXCLUSIONS]
    assert not orphans, f"in no nav and no skill, with no exclusion: {orphans}"


def test_no_path_exclusion_is_stale() -> None:
    nav, refs = _nav_pages(), _skill_paths()
    for path in PATH_EXCLUSIONS:
        assert (ROOT / path).is_file(), f"{path} is excluded but does not exist"
        assert not _path_is_routed(path, nav, refs), f"{path} is routed now; remove its exclusion"


def test_path_exclusion_reasons_hold() -> None:
    for path, reason in PATH_EXCLUSIONS.items():
        name = Path(path).name
        text = (ROOT / path).read_text(encoding="utf-8")
        if reason == "redirect":
            target = re.search(r'http-equiv="refresh"[^>]*url=\.\./([\w-]+)/', text)
            assert target, f"{path} is excluded as a redirect and holds no refresh"
            assert (ROOT / "docs" / f"{target.group(1)}.md").is_file(), (
                f"{path} redirects to {target.group(1)}, which is not a page"
            )
            assert f"{target.group(1)}.md" in _nav_pages(), f"redirect target is not in the nav"
            assert name in "\n".join(_mkdocs_block("not_in_nav")), (
                f"{name} is not declared in mkdocs `not_in_nav`"
            )
        elif reason == "contract":
            assert name in "\n".join(_mkdocs_block("exclude_docs")), (
                f"{name} is excluded as a contributor contract but not from the built site"
            )
        else:
            raise AssertionError(f"{path}: unknown reason {reason!r}")


def test_excluded_constants_are_not_callable() -> None:
    for name in CONSTANTS:
        obj = getattr(jnwb, name)
        assert not callable(obj), f"{name} is callable; it is an operation, so route it"
        # `str` is here for SKILLS_URL. It is deliberately narrow: an excluded constant has
        # to be data, so a function that slipped into this list fails on the line above and a
        # class fails here.
        assert isinstance(obj, (dict, tuple, list, frozenset, str)), f"{name} is a {type(obj)}"


def test_excluded_modules_are_modules() -> None:
    for name in MODULES:
        assert inspect.ismodule(getattr(jnwb, name)), f"{name} is not a module"


def test_excluded_internals_carry_no_documented_contract() -> None:
    for name in INTERNAL:
        obj = getattr(jnwb, name)
        assert not inspect.getdoc(obj), (
            f"{name} is documented now, so it can be routed honestly -- write the row and "
            f"drop the exclusion"
        )
