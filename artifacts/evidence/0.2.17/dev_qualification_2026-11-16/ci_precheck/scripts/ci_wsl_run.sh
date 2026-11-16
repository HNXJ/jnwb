#!/usr/bin/env bash
# Run ci_wsl_inner.sh with its output in a log beside this script, and print the verdict lines.
# usage: ci_wsl_run.sh <log name> <inner args...>
here=$(cd "$(dirname "$0")" && pwd)
log="$here/${1:?log name}"; shift
bash "$here/ci_wsl_inner.sh" "$@" > "$log" 2>&1
rc=$?
echo "rc=$rc"
head -1 "$log"
grep -E "^(FAILED|ERROR) |^::error" "$log" | head -40
grep -E "= .*(passed|failed|error).* in [0-9.]+s" "$log" | tail -1
exit "$rc"
