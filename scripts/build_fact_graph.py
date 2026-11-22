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

The fact stack must hold exactly the six fact tables, each once, with no
repeated fact ID; a table whose header looks like a fact table but is not exactly one is
refused, because a skipped table would drop its facts without a word.

Usage::

    python scripts/build_fact_graph.py            # write artifacts/fact_graph.json
    python scripts/build_fact_graph.py --out PATH
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
# Under JNWB_EXPECTED_PACKAGE_ROOT the checkout goes last, for `scripts`, behind the named copy.
if os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
    if str(REPO_ROOT) not in sys.path:
        sys.path.append(str(REPO_ROOT))
elif str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from scripts.computational_contract_gate import EXECUTION_PARAMETERS  # noqa: E402
from scripts.gates.boundary import git  # noqa: E402
from scripts.fact_graph._base import (  # noqa: E402
    FACT_GRAPH_PATH,  # noqa: F401
    FACT_STACK,  # noqa: F401
    FACT_TABLES,  # noqa: F401
    FactSourceError,  # noqa: F401
)
from scripts.fact_graph.boundary import boundary_unit_scan  # noqa: E402,F401
from scripts.fact_graph.claims import (  # noqa: E402
    HIGHER_CLASS_TERMS,  # noqa: F401
    LABEL_NAMES,  # noqa: F401
    _GRANGER_METHOD,  # noqa: F401
    _phrase,  # noqa: F401
    claim_class_scan,  # noqa: F401
)
from scripts.fact_graph.effects import (  # noqa: E402
    cache_decisions_scan,  # noqa: F401
    cache_side_effects_scan,  # noqa: F401
    delegation_scan,  # noqa: F401
    documented_guesses_scan,  # noqa: F401
    nwb_side_effects_scan,  # noqa: F401
    reserved_errors_scan,  # noqa: F401
)
from scripts.fact_graph.entities import (  # noqa: E402
    _documents,  # noqa: F401
    _exports,  # noqa: F401
    _module_file,  # noqa: F401
    _pages,  # noqa: F401
    _rel,  # noqa: F401
    _route_targets,  # noqa: F401
    _routes,  # noqa: F401
    _tests,  # noqa: F401
    references,  # noqa: F401
    routing_targets,  # noqa: F401
)
from scripts.fact_graph.facts import (  # noqa: E402
    _all_tables,  # noqa: F401
    load_facts,  # noqa: F401
    read_b3_exceptions,  # noqa: F401
    read_constants,  # noqa: F401
    read_facts,  # noqa: F401
    require_tables,  # noqa: F401
)
from scripts.fact_graph.owned_rules import (  # noqa: E402
    OWNED_RULES,  # noqa: F401
    owned_rule_scans,  # noqa: F401
    owned_rule_sites,  # noqa: F401
)
from scripts.fact_graph.references import (  # noqa: E402
    CORE_HEADER,  # noqa: F401
    METHOD_HEADER,  # noqa: F401
    PAGE_LINK,  # noqa: F401
    PITFALL_HEADER,  # noqa: F401
    REPRODUCTION_HEADER,  # noqa: F401
    normalize_doi,  # noqa: F401
    read_references,  # noqa: F401
    reference_functions,  # noqa: F401
    reference_row_doi,  # noqa: F401
    reference_rows,  # noqa: F401
    reference_table_rows,  # noqa: F401
    routed_citation_exclusions,  # noqa: F401
    uncited_routed_heads,  # noqa: F401
)
from scripts.fact_graph.scheme_rng import (  # noqa: E402
    S10_EXCUSED,  # noqa: F401
    S11_EXCUSED,  # noqa: F401
    _public_callables,  # noqa: F401
    _reach,  # noqa: F401
    _skipped_exports,  # noqa: F401
    scheme_scan,  # noqa: F401
)
from scripts.fact_graph.signatures import (  # noqa: E402
    I4_OPERATIONS,  # noqa: F401
    _passes_rng,  # noqa: F401
    _resolver_call,  # noqa: F401
    _unwalked_callables,  # noqa: F401
    choice_default_scan,  # noqa: F401
    rng_scan,  # noqa: F401
    signal_class_scan,  # noqa: F401
    signature_types_scan,  # noqa: F401
    unit_scan,  # noqa: F401
    wrapper_scan,  # noqa: F401
)
from scripts.fact_graph.source_scans import (  # noqa: E402
    DB_PACKAGE,  # noqa: F401
    JNWB_PACKAGE,  # noqa: F401
    PROSE_EXEMPT,  # noqa: F401
    S9_EXCUSED,  # noqa: F401
    SCANNED_FOR_RNG,  # noqa: F401
    _exempt,  # noqa: F401
    _prose_files,  # noqa: F401
    _skill_files,  # noqa: F401
    _source_scans,  # noqa: F401
    _text_scans,  # noqa: F401
    _tracked_files,  # noqa: F401
    _tracked_python,  # noqa: F401
    db_average_violations,  # noqa: F401
    global_seed_calls,  # noqa: F401
    immunity_scan,  # noqa: F401
    immunity_violations,  # noqa: F401
    python_prose,  # noqa: F401
    rng_violations,  # noqa: F401
    silent_handler_sites,  # noqa: F401
    silent_handler_violations,  # noqa: F401
    skill_contract_violations,  # noqa: F401
)

def _gates() -> Dict[str, str]:
    from scripts import harness_gate

    gates = {}
    for number, run, _ in harness_gate.GATES:
        # A gate adapted by `_one` closes over the check it runs; name that check.
        inner = inspect.getclosurevars(run).nonlocals.get("check", run)
        gates[str(number)] = getattr(inner, "__name__", repr(inner))
    return gates


def _head(root: Path) -> Optional[str]:
    done = git("-C", str(root), "rev-parse", "HEAD")
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
    rng_examined, rng_findings = rng_scan(package)
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
    reference_entries, cites, concerns = read_references(
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
            "reference": reference_entries,
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
            "rng_reports": rng_findings,
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
