#!/usr/bin/env bash
# Download Chrome through choreographer into a WSL venv and report where a browser is found.
# usage: ci_wsl_chrome.sh <venv>
root=$HOME/_temp_jnwb_ci
venv=${1:?venv}
PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/' | paste -sd: -)
export PATH
# shellcheck disable=SC1090,SC1091
source "$root/$venv/bin/activate" || exit 2
choreo_get_chrome 2>&1 | tail -3
find "$root/$venv" -maxdepth 9 -type f -name chrome 2>/dev/null | head -3
choreo_diagnose 2>&1 | grep -i -E "browser|chrome|error|found" | head -10
