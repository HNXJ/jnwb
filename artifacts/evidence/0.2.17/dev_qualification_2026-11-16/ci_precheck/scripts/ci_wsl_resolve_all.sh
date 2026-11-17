#!/usr/bin/env bash
# Resolve the CI install line for every matrix leg and copy the WSL freezes beside this script.
here=$(cd "$(dirname "$0")" && pwd)
root=$HOME/_temp_jnwb_ci
mkdir -p "$here/resolve"
cp "$root"/freeze_*.txt "$here/resolve/" 2>/dev/null
for leg in "3.12 linux" "3.13 linux" "3.14 linux" "3.15 linux" "3.12 windows" "3.13 windows" "3.14 windows"; do
  set -- $leg
  bash "$here/ci_wsl_resolve.sh" fabe "$1" "$2" "$here/resolve/resolve_$2_$1.txt"
done
bash "$here/ci_wsl_resolve.sh" fabe 3.12 linux "$here/resolve/resolve_build_linux_3.12.txt" test,docs
