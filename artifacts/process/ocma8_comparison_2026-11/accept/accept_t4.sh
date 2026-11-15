#!/usr/bin/env bash
# Acceptance for t4 (jynx artifacts/state.md under the artifacts audit): artifacts_check decides by its exit code;
# wc prints the state.md size. Usage: bash accept_t4.sh <tree>
# Prints the last output line of each command, then ACCEPT_RC=0 if every command exited 0, else 1.
if [ $# -ne 1 ]; then
    echo "usage: bash accept_t4.sh <tree>" >&2
    exit 2
fi
cd "$1" || exit 2
export PYTHONDONTWRITEBYTECODE=1
rc_all=0

out=$(python scripts/artifacts_check.py . </dev/null 2>&1)
rc=$?
printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | tail -n 1
[ "$rc" -eq 0 ] || rc_all=1

out=$(wc -c artifacts/state.md 2>&1)
rc=$?
printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | tail -n 1
[ "$rc" -eq 0 ] || rc_all=1

echo "ACCEPT_RC=$rc_all"
exit "$rc_all"
