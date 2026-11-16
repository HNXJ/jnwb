#!/usr/bin/env bash
# Acceptance for experiment task t2 (jnwb item 17-95, the cells() half). Usage: bash accept_t2.sh <tree>
# Runs in <tree>, one after another: the harness gate; pytest on the test files that import or name
# one of the four scripts holding a baseline splitter definition (build_dashboard, build_fact_graph,
# learning_gate, release_gate), a list resolved once at ac995dde by an AST survey of tests/ and frozen
# here (30 files), run on six xdist workers; pytest on t2_preserved_test.py beside this script (the
# table-row behaviour every reader keeps). Prints each command's last output line, then ACCEPT_RC=0
# when all passed. Amended 2026-11-15 (t2_amendment/AMENDMENT.md): `-n 6` and the third command.
set -u

here=$(cd "$(dirname "$0")" && pwd)
tree="${1:-}"
if [ -z "$tree" ] || ! cd "$tree"; then
    echo "usage: bash accept_t2.sh <tree>  (cannot enter: ${tree:-<none>})"
    echo "ACCEPT_RC=1"
    exit 1
fi

rc_all=0
tag=$(basename "$(pwd)")  # one pytest basetemp per tree: two trees may run this at once

out=$(PYTHONDONTWRITEBYTECODE=1 python scripts/harness_gate.py 2>&1 </dev/null)
rc=$?
echo "harness_gate rc=$rc last: $(printf '%s\n' "$out" | tail -n 1)"
[ "$rc" -eq 0 ] || rc_all=1

out=$(PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -n 6 --basetemp="D:/pytest_temp/exp_t2_accept_$tag" \
    tests/test_build_dashboard.py \
    tests/test_changelog_fragments.py \
    tests/test_ci_conclusion_gate.py \
    tests/test_claim_vocabulary_prose.py \
    tests/test_dashboard_page.py \
    tests/test_dashboard_workflow.py \
    tests/test_dependency_floors_are_installable.py \
    tests/test_distribution_manifest_inspection.py \
    tests/test_docs_user_navigation.py \
    tests/test_fact_gate.py \
    tests/test_fact_graph_boundary_units.py \
    tests/test_harness_adversarial_gates.py \
    tests/test_import_profile_receipt.py \
    tests/test_learning_gate.py \
    tests/test_module_docstrings_match_their_code.py \
    tests/test_mutation_harness_validity.py \
    tests/test_reference_claims_ledger.py \
    tests/test_references_resolve.py \
    tests/test_release_body_gate.py \
    tests/test_release_body_script.py \
    tests/test_release_contains_main.py \
    tests/test_release_figure_registry.py \
    tests/test_release_gate_receipt_history.py \
    tests/test_release_recovery_gates.py \
    tests/test_release_requires_an_empty_open_stack.py \
    tests/test_release_version_is_unpublished.py \
    tests/test_rng_parameters_by_use.py \
    tests/test_signal_class.py \
    tests/test_stack_metadata_contradictions.py \
    tests/test_workflow_release_policy.py 2>&1 </dev/null)
rc=$?
echo "pytest rc=$rc last: $(printf '%s\n' "$out" | tail -n 1)"
[ "$rc" -eq 0 ] || rc_all=1

out=$(PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider --basetemp="D:/pytest_temp/exp_t2_accept_${tag}_rows" \
    "$here/t2_preserved_test.py" 2>&1 </dev/null)
rc=$?
echo "table rows rc=$rc last: $(printf '%s\n' "$out" | tail -n 1)"
[ "$rc" -eq 0 ] || rc_all=1

echo "ACCEPT_RC=$rc_all"
exit "$rc_all"
