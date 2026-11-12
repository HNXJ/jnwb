#!/usr/bin/env bash
# Full jnwb suite with artifacts/state.md regenerated at the current HEAD first.
# Usage: jnwb_suite.sh <repo-or-lane-dir> <log-file> [basetemp]
# The optional basetemp goes to pytest as an explicit argument, so it never leaks into
# the harness's subprocess pytest calls (a PYTEST_ADDOPTS env var would). On this machine
# a basetemp outside the repo on the repo's own drive is required: `git clone --local`
# across drives fails with "Improper link".
# pytest runs through the machine suite lock when $JNWB_SUITE_LOCK (default $HOME/.claude/bin/suite_lock.py)
# exists, `python <lock> --label jnwb -- <pytest command>`; otherwise directly. Either way it prints which.
# The three doc-form tests run first; a failure there stops the run before the full suite.
# Prints the HEAD it ran on, the state check, and the summary/FAILED lines.
# On a pass over a clean tracked tree whose HEAD did not move, writes the full sha to
# <git-dir>/jnwb_suite_ok, which jnwb_push.sh requires.
set -o pipefail
dir="$1"; log="$2"; basetemp="$3"
[ -d "$dir" ] && [ -n "$log" ] || { echo "usage: jnwb_suite.sh <dir> <log> [basetemp]"; exit 2; }
cd "$dir" || exit 2
head=$(git rev-parse HEAD) || { echo "git could not resolve HEAD; no suite run"; exit 2; }
stamp="$(git rev-parse --git-dir)/jnwb_suite_ok"
rm -f "$stamp"
# Doc-form first: a doc-form failure shows in seconds, not after the full suite. Its output goes
# to the log, which the full run overwrites on a pass.
docform=(tests/test_changelog_fragments.py tests/test_docs_form_gate.py tests/test_documentation_form.py)
docform_cmd=(python -m pytest "${docform[@]}" -q -p no:cacheprovider -rf)
[ -n "$basetemp" ] && docform_cmd+=(--basetemp "$basetemp")
if ! "${docform_cmd[@]}" > "$log" 2>&1; then
  echo "doc-form tests failed; the full suite did not run"
  grep -E "^FAILED|passed|failed" "$log" | tail -8
  exit 1
fi
echo "doc-form tests passed"
python scripts/reconstruct_state.py >/dev/null || { echo "reconstruct failed"; exit 2; }
python scripts/reconstruct_state.py --check >/dev/null || { echo "state check failed"; exit 2; }
pytest_cmd=(python -m pytest tests/ -q -n 12 -p no:cacheprovider -rf)
[ -n "$basetemp" ] && pytest_cmd+=(--basetemp "$basetemp")
lock="${JNWB_SUITE_LOCK:-$HOME/.claude/bin/suite_lock.py}"
if [ -f "$lock" ]; then
  echo "suite lock: $lock"
  python "$lock" --label jnwb -- "${pytest_cmd[@]}" > "$log" 2>&1
else
  echo "suite lock: none ($lock not found)"
  "${pytest_cmd[@]}" > "$log" 2>&1
fi
rc=$?
echo "head=${head:0:8} suite_rc=$rc"
grep -E "^FAILED|passed|failed" "$log" | tail -8
if [ "$(git rev-parse HEAD)" != "$head" ]; then
  echo "WARNING: HEAD moved during the run"
elif [ $rc -eq 0 ] && [ -z "$(git status --porcelain --untracked-files=no)" ]; then
  echo "$head" > "$stamp"
elif [ $rc -eq 0 ]; then
  echo "NOTE: tracked changes present; no push stamp written"
fi
exit $rc
