#!/usr/bin/env bash
# Make a depth-1 checkout of a jnwb commit in the WSL CI folder, as actions/checkout would.
# usage: ci_wsl_shallow.sh <sha> <name>      (creates src_<name>)
here=$(cd "$(dirname "$0")" && pwd)
bash "$here/ci_shallow_clone.sh" file:///mnt/d/repos/_work/_temp_jnwb_qual "$HOME/_temp_jnwb_ci/src_${2:?name}" "${1:?sha}"
