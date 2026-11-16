#!/usr/bin/env bash
# Run the git-reading subset of the suite in a Windows checkout through ci_win_inner.sh, on four workers.
# usage: ci_win_subset_run.sh <log name> <name> [extra test files...]
here=$(cd "$(dirname "$0")" && pwd)
log="$here/${1:?log name}"; name=${2:?name}; shift 2
files=$(bash "$here/ci_git_subset.sh" "D:/repos/_work/_temp_jnwb_ci/src_$name") || exit 2
echo "subset: $(echo "$files" | wc -w) file(s)"
# shellcheck disable=SC2086
bash "$here/ci_win_inner.sh" "$name" $files "$@" -n 4 > "$log" 2>&1
rc=$?
echo "rc=$rc"
head -1 "$log"
grep -a -E "^(FAILED|ERROR) |^::error" "$log" | head -40 | cut -c1-300
grep -a -E "= .*(passed|failed|error).* in [0-9.]+s" "$log" | tail -1
exit "$rc"
