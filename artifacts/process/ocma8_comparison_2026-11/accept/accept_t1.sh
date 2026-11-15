#!/usr/bin/env bash
# Acceptance for task t1 (jarness T-82). Usage: bash accept_t1.sh <tree>
# Runs the acceptance commands in <tree> one after another, prints each one's rc and last output line,
# then ACCEPT_RC=0 when all passed, else 1.
tree="$1"
if [ -z "$tree" ] || [ ! -d "$tree" ]; then
  echo "usage: bash accept_t1.sh <tree>" >&2
  exit 2
fi
cd "$tree" || exit 2
export PYTHONDONTWRITEBYTECODE=1  # no __pycache__ written into the tree under test
rc_all=0
tag=$(basename "$(pwd)")  # one pytest basetemp per tree: two trees may run this at once

step() {
  local out rc last
  out=$("$@" 2>&1 </dev/null)
  rc=$?
  last=$(printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | tail -n 1)
  echo "rc=$rc | $* | ${last:-(no output)}"
  [ "$rc" -eq 0 ] || rc_all=1
}

step python harness/lint.py
step python harness/audit.py --selftest
step python -m pytest harness/hooks -q -p no:cacheprovider --basetemp="D:/pytest_temp/exp_t1_accept_$tag"

# test files under harness/ whose name contains "selfcheck", resolved in the tree at run time
sc_files=$(find harness \( -name 'test_*.py' -o -name '*_test.py' \) -name '*selfcheck*' | sort)
if [ -z "$sc_files" ]; then
  echo "rc=1 | selfcheck test files: none under harness/"
  rc_all=1
else
  echo "selfcheck test files: $(echo $sc_files)"
  # shellcheck disable=SC2086
  step python -m pytest $sc_files -q -p no:cacheprovider --basetemp="D:/pytest_temp/exp_t1_accept_selfcheck_$tag"
fi

echo "ACCEPT_RC=$rc_all"
exit $rc_all
