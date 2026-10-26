#!/usr/bin/env python3
"""Deterministic Operational & Scientific Harness Gate for jnwb generic library.

Mechanically enforces repository controls. The list is the runner's, in its order, and
`tests/test_module_docstrings_match_their_code.py` holds the two to each other: this
said twelve while the runner printed thirteen, and gate 2 had been rewritten from
protected paths to skill-tree uniqueness without the list noticing.

  1. Frozen jnwb boundary: no unauthorized imports from project folders.
  2. Skill tree uniqueness: every SKILL.md lives under skills/, or under artifacts/skills/
     with a name no shipped skill uses.
  3. Machine-local path exclusion: rejects hardcoded drive letters in test suites.
  4. Root allowlist: permits only tracked, authorized root files.
  5. Public symbols documented: every public export is written about by a person.
  6. Dataset leakage: rejects experiment-specific tokens, conditions, and manuscript results.
  7. Version consistency: package and metadata agree.
  8. Python floor consistency: declared support, classifiers, and CI matrix agree.
  9. Documented API matches jnwb.__all__, and the runtime generator agrees.
  10. Docs version matches package: every version the documentation states.
  11. No shadow packages: nothing importable at the repository root that jnwb does not own.
  12. Project identifiers in jnwb/ code strings.
  13. NWB onboarding surface alignment across README, tutorials, skill, and MkDocs.
  14. Internal process vocabulary kept out of public documentation and CHANGELOG.md, the
      CHANGELOG held to its entry template, and item or problem identifiers out of jnwb/,
      docs/ and the files its pages include.
  15. Stack form consistency: declared write sets are comparable, and table rows, the open
      stack's included, keep their header's shape; defect-class counts match their instances,
      and each date a file cites has a dated record.
  16. Line ending consistency: no tracked text file carries both conventions at once.
  17. Stack pointers resolve: Skill, Role and Blocked by name something on this tree.
  18. API member types: each docs/api.md Type cell, and each signature's parameter kinds, are
      true of the runtime object.
  19. Frozen functions: each registered body still hashes to its independently verified value.
  20. State file: a present artifacts/state.md records the live HEAD and carries its generated
      worktree, branch and open-defect rows; an absent one passes.
  21. Computational contract: execution switches select, precision requests are honoured, every
      export has a recorded computational order, and no declared raw-power estimand takes its log
      before its mean.
  22. Fact predicates: no typed fact is VIOLATED on the generated fact graph; the source read
      and the HELD and UNHELD counts are printed.

Returns exit code 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import ast
import itertools
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parents[1]
# Under JNWB_EXPECTED_PACKAGE_ROOT the checkout goes last, so the copy it names wins.
if os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
    if str(REPO_ROOT) not in sys.path:
        sys.path.append(str(REPO_ROOT))
elif str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# The one stack reader, shared with STEP 0a (scripts/stack_parse.py): gates 15 and 17 read the
# same items, at any heading depth, that STEP 0a reads.
from scripts.stack_parse import item_spans, stack_items as _stack_items  # noqa: E402
JNWB_DIR = REPO_ROOT / "jnwb"
OMISSION_DIR = REPO_ROOT / "omission"

from scripts.gates.boundary import (
    AUTHORIZED_JNWB_EXCEPTIONS,
    check_frozen_boundary,
    _is_inside_nested_checkout,
    _GIT_DISCOVERY_ENV,
    GitUnavailable,
    _canonical,
    _run_git,
    _registered_worktrees,
    _git_identity,
    _is_checkout_of,
    _skill_frontmatter_name,
    check_skill_tree_uniqueness,
    check_no_hardcoded_test_paths,
    OWNED_ROOT_PACKAGES,
    INTERNAL_ROOT_PACKAGES,
    SOURCE_ROOT_DIRS,
    EPHEMERAL_ROOT_DIRS,
    TOOL_ROOT_DIRS,
    ALLOWED_ROOT_DIRS,
    ALLOWED_ROOT_FILES,
    check_root_allowlist,
    check_no_shadow_packages,
    check_logarithm_last_in_package,
    check_logarithm_last_rule,
    check_modality_isolation,
    _convention,
    _wholesale_conversions,
    check_line_ending_consistency,
)

from scripts.gates.versions import (
    _test_job_matrix,
    PYTHON_FLOOR,
    PYTHON_SUPPORTED,
    PYTHON_CI_REQUIRED,
    check_version_consistency,
    check_python_floor_consistency,
)

from scripts.gates.docs import (
    GENERATED_REFERENCE,
    check_public_symbols_documented,
    check_documented_api_matches_all,
    check_docs_version_matches_package,
    DATASET_SCAN_ROOT_DOCS,
    DATASET_SCAN_EXEMPT,
    check_dataset_leakage,
    NWB_ONBOARDING_SYMBOLS,
    check_nwb_onboarding_alignment,
)

from scripts.gates.vocabulary import (
    PROJECT_IDENTIFIERS,
    check_no_project_identifiers_in_code,
    INTERNAL_PROCESS_TERMS,
    _internal_term_pattern,
    check_internal_process_vocabulary,
    CHANGELOG_KINDS,
    CHANGELOG_RELEASES_KEPT,
    CHANGELOG_ENTRY_LIMIT,
    CHANGELOG_PROCESS_TERMS,
    CHANGELOG_NAME,
    CHANGELOG_SEED_KINDS,
    CHANGELOG_TEMPLATE_FROM,
    CHANGELOG_CASE_SENSITIVE,
    CHANGELOG_PACKAGE_SCOPED,
    CHANGELOG_PACKAGE_CONTENT,
    _held_to_template,
    _changelog_term_pattern,
    _changelog_entry_violations,
    _bullet_scopes,
    check_changelog_form,
    PROCESS_IDENTIFIER,
    SNIPPET_INLINE,
    SNIPPET_BLOCK,
    _snippet_base_paths,
    _snippet_names,
    _resolve_snippet,
    _included_sources,
    _rel,
    check_no_process_identifiers_in_library,
)

from scripts.gates.stacks_form import (
    TODO_STACK,
    OPEN_STACK,
    _code_span_mask,
    _writes_fields,
    _writes_field_spans,
    _CONTINUES_AS_PATHS,
    _suspected_truncated_writes,
    _BLOCK_ASSERTIONS,
    _ANY_BLOCK_ASSERTION,
    _ITEM_ID,
    _FIELD_LABEL,
    _unwrapped_spans,
    _stop_clause_spans,
    _unwrapped_sentences,
    _excise_blocked_by,
    _blocked_by_none_contradictions,
    _ITEM_COUNT,
    _COUNT_VALUE,
    _CLAUSE_BREAK,
    _summary_regions,
    _miscounted_summaries,
    _NUMERAL_ITEMS,
    _TOTAL_BEFORE,
    _TOTAL_AFTER,
    _inside_quotation,
    _stale_item_totals,
)

from scripts.gates.stacks_closure import (
    _ESCAPED_PIPE,
    GENERATED_FROM,
    _row_delimiters,
    check_stack_form_consistency,
)

from scripts.gates.stacks_pointers import (
    SKILL_PLACEHOLDERS,
    ROLE_PLACEHOLDERS,
    _RESOLVED_FIELDS,
    _field_value,
    _declared_name,
    check_stack_pointers_resolve,
)

from scripts.gates.api_types import (
    API_MD_ROW,
    api_member_kind,
    api_md_parameter_kinds,
    check_api_md_member_types,
)

from scripts.gates.frozen import (
    FROZEN_REGISTER,
    _canonical_ast,
    _strip_docstrings,
    frozen_body_hash,
    check_frozen_validated,
)

from scripts.gates.state import (
    validate_receipt_provenance,
    check_state_file_head,
    check_computational_contract,
    _FACT_REPORT,
    check_fact_predicates,
)

from scripts.learning_gate import (
    awareness_violations,
    citation_violations,
    examined_counts,
    forbidden_sources,
    forbidden_violations,
    ledger_violations,
    mapping_check,
)


def _one(check: Any, header: str) -> Any:
    """Adapt a check returning violations into the (header, violations) shape the runner wants."""

    def run() -> List[Tuple[str, List[str]]]:
        violations = check()
        return [(header, violations)] if violations else []

    return run


def _api_reference_checks() -> List[Tuple[str, List[str]]]:
    """Adapter, not a gate: the API reference is two checks under one PASS line.

    Deliberately does not open with ``Gate N``. That prefix is how
    ``tests/test_harness_adversarial_gates.py`` discovers which function *is* a numbered gate, and
    a helper claiming the number would read as the gate being declared twice.
    """
    from scripts.generate_api_md import check_api_md_is_generated

    found: List[Tuple[str, List[str]]] = []
    set_violations = check_documented_api_matches_all()
    if set_violations:
        found.append(("FAIL: Documented API does not match jnwb.__all__:", set_violations))
    generator_violations = check_api_md_is_generated()
    if generator_violations:
        found.append(
            ("FAIL: docs/api.md is out of sync with the API generator:", generator_violations)
        )
    return found


def _computational_contract_checks() -> List[Tuple[str, List[str]]]:
    """Adapter, not a gate: the computational contract and the log-last estimand rule over
    jnwb/ under one PASS line.

    Deliberately does not open with ``Gate N``, for the reason ``_api_reference_checks`` gives.
    """
    found: List[Tuple[str, List[str]]] = []
    contract = check_computational_contract()
    if contract:
        found.append(("FAIL: The computational contract is broken:", contract))
    estimands = check_logarithm_last_in_package(REPO_ROOT)
    if estimands:
        found.append(
            ("FAIL: A declared raw-power estimand takes its log before its mean:", estimands))
    return found


def _internal_vocabulary_checks() -> List[Tuple[str, List[str]]]:
    """Adapter, not a gate: public documentation, the library source and the CHANGELOG under one
    PASS line."""
    found: List[Tuple[str, List[str]]] = []
    docs_violations = check_internal_process_vocabulary()
    if docs_violations:
        found.append(
            ("FAIL: Internal process vocabulary found in public documentation:", docs_violations)
        )
    library_violations = check_no_process_identifiers_in_library()
    if library_violations:
        found.append(
            ("FAIL: Item or problem identifiers found in jnwb/ or docs/:", library_violations))
    changelog_violations = check_changelog_form()
    if changelog_violations:
        found.append(
            ("FAIL: CHANGELOG.md does not hold the entry template:", changelog_violations))
    return found


def _stack_and_record_checks() -> List[Tuple[str, List[str]]]:
    """Adapter, not a gate: the stack's form and the process records under one PASS line."""
    found: List[Tuple[str, List[str]]] = []
    stack_violations = check_stack_form_consistency()
    if stack_violations:
        found.append(("FAIL: Coordination stack form is not machine-readable:", stack_violations))
    record_violations = (ledger_violations() + citation_violations() + mapping_check()[2]
                         + forbidden_violations(forbidden_sources()))
    if record_violations:
        found.append(("FAIL: A process record disagrees with its own count or its citations:",
                      record_violations))
    return found


def _stack_and_record_pass_line() -> str:
    """The stack and record checks' PASS line, naming what they read; nothing read says 0."""
    tables, read, phrases = examined_counts()
    return ("PASS: Stack form consistent (every declared write set names comparable paths and "
            "is not truncated by a stray full stop; no 'Blocked by: none' is contradicted by "
            "its own item's text; every summary count agrees with the items it names; "
            "no summary states an item total the stack does not hold; "
            "every table row in the open stack carries its own table's column count; "
            "every GENERATED_FROM entry resolves against the tree); every defect-class count "
            "matches its instances, and every date a file cites has a dated record; examined: "
            f"{tables} mapping tables ({read} obligation clauses; before, after, never, must, "
            f"only) and {phrases} forbidden phrases.")


def _state_file_checks() -> List[Tuple[str, List[str]]]:
    """Adapter, not a gate: the state file's recorded HEAD and its generated rows, one PASS line."""
    found: List[Tuple[str, List[str]]] = []
    head_violations = check_state_file_head()
    if head_violations:
        found.append(("FAIL: artifacts/state.md does not record the live HEAD:", head_violations))
    row_violations = awareness_violations()
    if row_violations:
        found.append(("FAIL: artifacts/state.md does not carry its generated rows:",
                      row_violations))
    return found


def _python_pass_line() -> str:
    return (
        f"PASS: Python >={PYTHON_FLOOR} floor, classifiers {list(PYTHON_SUPPORTED)}, "
        f"CI covering {list(PYTHON_CI_REQUIRED)} all agree."
    )


def _fact_pass_line() -> str:
    held, unheld = _FACT_REPORT.get("HELD", 0), _FACT_REPORT.get("UNHELD", 0)
    return (f"PASS: No typed fact of {_FACT_REPORT.get('source', 'an unread source')} is "
            f"VIOLATED on the generated fact graph (HELD {held}, UNHELD {unheld}; each UNHELD "
            "fact names the live item that holds it).")


#: Every gate, in the runner's order, as (number, run, pass_line). `pass_line` is a callable
#: because two gates compute their message from constants. The numbers are the ones this module's
#: docstring lists, and `tests/test_module_docstrings_match_their_code.py` holds the two together.
GATES: List[Tuple[int, Any, Any]] = [
    (1, _one(check_frozen_boundary, "FAIL: jnwb/ frozen boundary check failed:"),
     lambda: "PASS: jnwb/ frozen boundary clean (zero unauthorized project imports)."),
    (2, _one(check_skill_tree_uniqueness, "FAIL: Skill tree uniqueness violated:"),
     lambda: "PASS: One skill tree: every SKILL.md is under skills/, or under artifacts/skills/ "
             "without repeating a shipped skill."),
    (3, _one(check_no_hardcoded_test_paths,
             "FAIL: Hardcoded machine-local paths detected in tests:"),
     lambda: "PASS: Tests free of machine-local hardcoded drive paths."),
    (4, _one(check_root_allowlist, "FAIL: Repository root allowlist violated:"),
     lambda: "PASS: Repository root strictly frozen & clean."),
    (5, _one(check_public_symbols_documented, "FAIL: Undocumented public symbols detected:"),
     lambda: "PASS: 100% of public symbols documented in docs/."),
    (6, _one(check_dataset_leakage, "FAIL: Dataset leakage detected in generic modules:"),
     lambda: "PASS: No forbidden study tokens on Gate 6 scan surface "
             "(jnwb/, skills/, docs/**, examples/**, root user-facing docs)."),
    (7, _one(check_version_consistency, "FAIL: Version inconsistency detected:"),
     lambda: "PASS: Package and pyproject.toml versions synchronized."),
    (8, _one(check_python_floor_consistency,
             "FAIL: Python support policy inconsistency detected:"), _python_pass_line),
    (9, _api_reference_checks,
     lambda: "PASS: docs/api.md matches jnwb.__all__ and the runtime API generator."),
    (10, _one(check_docs_version_matches_package,
              "FAIL: Documentation version does not match the package version:"),
     lambda: "PASS: Documentation versions derive from jnwb.__version__."),
    (11, _one(check_no_shadow_packages,
              "FAIL: Import-shadowing package detected at repository root:"),
     lambda: "PASS: No unowned importable package at the repository root."),
    (12, _one(check_no_project_identifiers_in_code,
              "FAIL: Project identifiers found in jnwb/ code:"),
     lambda: "PASS: No project identifiers in jnwb/ code strings or names."),
    (13, _one(check_nwb_onboarding_alignment, "FAIL: NWB onboarding surface misaligned:"),
     lambda: "PASS: NWB onboarding workflow aligned across README, tutorials, skill, and MkDocs."),
    (14, _internal_vocabulary_checks,
     lambda: "PASS: No internal process vocabulary in docs/, skills/, README.md or "
             "artifacts/agents.md "
             f"({len(INTERNAL_PROCESS_TERMS)} "
             "gated terms; 'agent', 'skill' and 'routing' are public capabilities and are not "
             "among them), no item or problem identifier in jnwb/, docs/ or a file a page "
             "includes, and CHANGELOG.md holds the entry template: six kinds, one line of at most "
             f"{CHANGELOG_ENTRY_LIMIT} characters naming its file, a seed kind on [results change], "
             f"{CHANGELOG_RELEASES_KEPT} releases, and no process phrase."),
    (15, _stack_and_record_checks, _stack_and_record_pass_line),
    (16, _one(check_line_ending_consistency,
              "FAIL: Tracked files carry both line-ending conventions:"),
     lambda: "PASS: Line endings consistent (no tracked text file mixes CRLF and bare LF)."),
    (17, _one(check_stack_pointers_resolve,
              "FAIL: A stack field names something that does not exist:"),
     lambda: "PASS: Stack pointers resolve (every 'Skill:' names a skills/*/SKILL.md or a "
             "declared placeholder, every 'Role:' an artifacts/agents/*.md or a human, and "
             "every 'Blocked by:' item id is live)."),
    (18, _one(check_api_md_member_types,
              "FAIL: A docs/api.md Type cell is not true of the runtime object:"),
     lambda: "PASS: docs/api.md Type column and each signature's parameter kinds agree with the "
             "runtime object, on an oracle that does not import the generator."),
    (19, _one(check_frozen_validated,
              "FAIL: A frozen-validated function no longer matches its verified body:"),
     lambda: "PASS: Every frozen-validated function matches its verified body and names a "
             "killing test that exists."),
    (20, _state_file_checks,
     lambda: "PASS: artifacts/state.md is absent or records the live HEAD and carries its "
             "generated worktree, branch and open-defect rows (read only; the generator runs "
             "this harness, so this gate never regenerates the file)."),
    (21, _computational_contract_checks,
     lambda: "PASS: Computational contract holds (every device, backend and n_jobs argument "
             "reaches its deciding mechanism, every precision request is honoured or refused, "
             "and every export has a recorded computational order), and no declared raw-power "
             "estimand takes its log before its mean (the log-last rule over jnwb/)."),
    (22, _one(check_fact_predicates, "FAIL: A typed fact is VIOLATED on the generated fact graph:"),
     _fact_pass_line),
]


def run_full_preflight() -> bool:
    """Run every gate and report each one's state independently.

    This returned at the first failure until 2026-09-19, and the cost of that was measured rather
    than argued: agent worktrees inside the repository tripped gate 2, the runner stopped, and
    gates 3 through 13 did not run -- including gate 4, which held a second, genuine instance of
    the same defect and only became visible once gate 2 was fixed. One PASS line was printed where
    thirteen were expected, and three separate packets reported the resulting red suite as
    unrelated to their work without anyone establishing that the remaining gates had executed at
    all. A first failure makes every later gate *unknown*, and the workflow was treating them as
    observed.

    So every gate now runs, whatever the ones before it did, and the contract is:

        harness PASS  <=>  every gate executed and every gate passed

    A gate that raises is reported ERROR and does not stop the rest. A gate that genuinely cannot
    be reached is reported NOT RUN by name, because a gate that vanishes from the output looks
    exactly like a gate with nothing to say.
    """
    # A violation quoting a character the console cannot encode (a Windows cp1252 console and
    # a stack line containing `Θ`) raised inside `print`, so the gate's findings collapsed into
    # one ERROR line and the gate was listed as failed twice. The evidence is the output.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")
    print("=== Running Harness Pre-Flight Verification Gates ===")

    executed: List[int] = []
    failed: List[int] = []

    # The report is a function and the loop is wrapped, because `not_run` used to be unreachable:
    # both the success and the `except` path appended to `executed`, so the only way to skip a
    # gate was an escaping BaseException -- which also skipped the reporting that would have said
    # so. A NOT RUN line nothing can produce is not a safeguard, it is a comment. 06-64 deleted
    # the whole block and the suite stayed green.
    try:
        for number, run, pass_line in GATES:
            try:
                found = run()
                if found:
                    failed.append(number)
                    for header, violations in found:
                        print(header)
                        for violation in violations:
                            print(f"  - {violation}")
                else:
                    # Inside the try: a pass_line() that raises used to abort the runner with no
                    # verdict at all, which is the same failure this gate table exists to prevent.
                    print(pass_line())
            except Exception as exc:  # a gate that breaks must not hide the gates after it
                if number not in failed:
                    failed.append(number)
                print(f"ERROR: gate {number} raised {type(exc).__name__}: {exc}")
            # Appended last, so a gate abandoned part-way is genuinely not executed.
            executed.append(number)
    except BaseException:
        # SystemExit, KeyboardInterrupt, or anything else that is not an ordinary error. Say which
        # gates never ran before letting it go; an interrupted run must not read as a clean one.
        _print_preflight_verdict(executed, failed)
        raise

    return _print_preflight_verdict(executed, failed)


def _print_preflight_verdict(executed: List[int], failed: List[int]) -> bool:
    """Name every gate's state, then the verdict. Unknown is never reported as passing."""
    not_run = [number for number, _, _ in GATES if number not in executed]
    for number in not_run:
        print(f"NOT RUN: gate {number} did not execute; its state is unknown, not passing.")

    if failed or not_run:
        print(
            f"OVERALL: FAIL. {len(executed)} of {len(GATES)} gates executed; "
            f"failed: {failed or 'none'}; not run: {not_run or 'none'}."
        )
        return False

    print(f"ALL HARNESS GATES PASSED. {len(executed)} of {len(GATES)} gates executed.")
    return True


if __name__ == "__main__":
    success = run_full_preflight()
    sys.exit(0 if success else 1)
