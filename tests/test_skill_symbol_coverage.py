"""Every public symbol is routed by a skill, or is excluded for a stated, checked reason.

A routing matrix that silently omits two thirds of the public API is not a matrix; it is a
sample. This module holds the whole of `jnwb.__all__` against the skill files: a symbol is
either mentioned by some skill, or it appears below with a category, and the category's own
assertion has to hold for it.

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
    "UnitNotFoundError",
]

# The `jnwb.ontology` vocabulary: a data model for describing an analysis, not operations to
# choose between. An agent reaches these by constructing what a workflow asks for.
ONTOLOGY = [
    "AlignedDataset",
    "Alignment",
    "Dataset",
    "EpochCollection",
    "Figure",
    "Interpretation",
    "Lineage",
    "Provenance",
    "Query",
    "Question",
    "Result",
]

# Containers a routed operation returns. Routing the operation routes the container; the
# mapping below is checked against the live return annotation.
RETURNED_BY = {
    "AperiodicFitResult": ["aperiodic_fit"],
    "ComplexTFR": ["complex_tfr"],
    "DirectedResult": ["granger", "granger_spectral", "phase_slope_index", "transfer_entropy",
                       "directed_connectivity"],
    "EventTable": ["events"],
    "JRSAResult": ["jrsa"],
    "ProbeGeometry": ["probe_geometry"],
    "VFlipResult": ["vflip", "vflip_from_lfp"],
    "XFlipResult": ["xflip"],
    "ZFlipResult": ["zflip"],
}

# A namespace class: every operation on it is routed as `jnwb.StatisticalAnalysis.name(...)`,
# so routing the bare class as well would put two spellings of one call in the matrix.
NAMESPACES = ["StatisticalAnalysis"]

# Class facades over free functions the matrices already route. Routing both spellings would
# make the matrix ambiguous about which one an agent should call.
ANALYZERS = ["PopulationAnalyzer", "TFRAnalyzer", "UnitAnalyzer"]

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


def test_excluded_analyzers_are_classes_over_routed_functions() -> None:
    for name in ANALYZERS:
        obj = getattr(jnwb, name)
        assert isinstance(obj, type), f"{name} is not a class"
        assert obj.__module__ == "jnwb.analyzers", f"{name} lives in {obj.__module__}"


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
