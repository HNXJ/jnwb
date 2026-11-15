#!/usr/bin/env bash
# OCMA-8 pilot (jnwb 17-103) acceptance: run in a jnwb worktree. Usage: pilot_accept.sh <worktree> <basetemp-name>
# Prints one line per check with rc and seconds, then ACCEPT_RC (0 only when every check exits 0).
W=${1:?worktree}; B=${2:?basetemp name}
cd "$W" || exit 9
bad=0
t0=$(date +%s)
python -m pytest -q -p no:cacheprovider --basetemp="D:/pytest_temp/$B" \
  tests/test_docs_user_navigation.py tests/test_generation_closure_is_declared.py \
  tests/test_harness_adversarial_gates.py tests/test_module_docstrings_match_their_code.py \
  tests/test_readme_smoke.py tests/test_release_recovery_gates.py \
  tests/test_rng_convention_matches_the_signatures.py tests/test_skills_are_findable_from_an_installed_copy.py \
  tests/test_skills_validation.py tests/test_standing_rules_name_no_cycle.py \
  tests/test_workflow_release_policy.py > "$W/../_temp_accept_$B.pytest.txt" 2>&1
rc=$?; [ $rc -ne 0 ] && bad=1
echo "pytest-contributing-readers rc=$rc s=$(( $(date +%s) - t0 )) :: $(tail -1 "$W/../_temp_accept_$B.pytest.txt")"
t0=$(date +%s)
python scripts/harness_gate.py > "$W/../_temp_accept_$B.gate.txt" 2>&1
rc=$?; [ $rc -ne 0 ] && bad=1
echo "harness_gate rc=$rc s=$(( $(date +%s) - t0 )) :: $(tail -1 "$W/../_temp_accept_$B.gate.txt")"
echo "ACCEPT_RC=$bad"
