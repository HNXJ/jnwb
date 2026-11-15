#!/usr/bin/env bash
# Acceptance for t3 (todo item 17-97, test_rng_* group): the rng tests pass, and the tests/ collection count is printed.
# Usage: bash accept_t3.sh <tree>
# Prints the last output line of each command, then ACCEPT_RC=0 if every command exited 0, else 1.
if [ $# -ne 1 ]; then
    echo "usage: bash accept_t3.sh <tree>" >&2
    exit 2
fi
cd "$1" || exit 2
export PYTHONDONTWRITEBYTECODE=1
rc_all=0
tag=$(basename "$(pwd)")  # one pytest basetemp per tree: two trees may run this at once

out=$(python -m pytest tests -q -p no:cacheprovider --basetemp="D:/pytest_temp/exp_t3_accept_$tag" -k rng </dev/null 2>&1)
rc=$?
printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | tail -n 1
[ "$rc" -eq 0 ] || rc_all=1

out=$(python -m pytest tests --collect-only -q -p no:cacheprovider --basetemp="D:/pytest_temp/exp_t3_accept_collect_$tag"</dev/null 2>&1)
rc=$?
printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | tail -n 1
[ "$rc" -eq 0 ] || rc_all=1

echo "ACCEPT_RC=$rc_all"
exit "$rc_all"
