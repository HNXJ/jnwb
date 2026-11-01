#!/usr/bin/env bash
# Full jnwb suite with artifacts/state.md regenerated at the current HEAD first.
# Usage: jnwb_suite.sh <repo-or-lane-dir> <log-file> [basetemp]
# The optional basetemp goes to pytest as an explicit argument, so it never leaks into
# the harness's subprocess pytest calls (a PYTEST_ADDOPTS env var would). On this machine
# a basetemp outside the repo on the repo's own drive is required: `git clone --local`
# across drives fails with "Improper link" (jnwb#27-era machine note, 2026-10-02).
# Prints the HEAD it ran on, the state check, and the summary/FAILED lines.
# On a pass over a clean tracked tree whose HEAD did not move, writes the full sha to
# <git-dir>/jnwb_suite_ok, which jnwb_push.sh requires.
set -o pipefail
dir="$1"; log="$2"; basetemp="$3"
[ -d "$dir" ] && [ -n "$log" ] || { echo "usage: jnwb_suite.sh <dir> <log> [basetemp]"; exit 2; }
cd "$dir" || exit 2
head=$(git rev-parse HEAD)
stamp="$(git rev-parse --git-dir)/jnwb_suite_ok"
rm -f "$stamp"
python scripts/reconstruct_state.py >/dev/null || { echo "reconstruct failed"; exit 2; }
python scripts/reconstruct_state.py --check >/dev/null || { echo "state check failed"; exit 2; }
if [ -n "$basetemp" ]; then
  python -m pytest tests/ -q -n 12 -p no:cacheprovider -rf --basetemp "$basetemp" > "$log" 2>&1
else
  python -m pytest tests/ -q -n 12 -p no:cacheprovider -rf > "$log" 2>&1
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
