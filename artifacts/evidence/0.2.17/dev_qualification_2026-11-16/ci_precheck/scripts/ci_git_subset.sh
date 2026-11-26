#!/usr/bin/env bash
# Print the test files of a jnwb checkout that read git, the push scripts or the README (one line, space separated).
# usage: ci_git_subset.sh <checkout dir>
cd "${1:?checkout}" || exit 2
grep -l -E "verify_lane|jnwb_push|ci_gate|push_guard|rev-parse|rev-list|merge-base|is_git_checkout|\"git\"|'git'|README" tests/*.py | sort | paste -sd' ' -
