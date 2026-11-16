#!/usr/bin/env bash
# Run the git-reading subset of the suite in a WSL checkout through ci_wsl_run.sh, on four workers.
# usage: ci_wsl_subset_run.sh <log name> <name> <venv>
here=$(cd "$(dirname "$0")" && pwd)
log=${1:?log name}; name=${2:?name}; venv=${3:?venv}
files=$(bash "$here/ci_git_subset.sh" "$HOME/_temp_jnwb_ci/src_$name") || exit 2
echo "subset: $(echo "$files" | wc -w) file(s)"
# shellcheck disable=SC2086
bash "$here/ci_wsl_run.sh" "$log" "$name" "$venv" 0 $files -n 4
