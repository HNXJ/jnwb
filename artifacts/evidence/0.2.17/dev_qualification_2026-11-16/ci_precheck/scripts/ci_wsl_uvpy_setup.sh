#!/usr/bin/env bash
# Install interpreters through uv and build one CI-like venv per interpreter on an existing WSL checkout.
# usage: ci_wsl_uvpy_setup.sh <sha> <src name> <python version>...     (venv name: venv_<version without dots>)
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$HOME/_temp_jnwb_ci
sha=${1:?sha}; name=${2:?src name}; shift 2
PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/' | paste -sd: -)
export PATH
uv="$root/venv_tools/bin/uv"
for pyver in "$@"; do
  "$uv" python install "$pyver" || { echo "uv has no $pyver"; exit 1; }
  base=$("$uv" python find "$pyver") || exit 1
  echo "interpreter: $base ($("$base" --version))"
  bash "$here/ci_wsl_setup.sh" "$sha" "$name" "venv_${pyver//./}" "$base" 2>&1 | grep -E "setup ok|failed|is not at|error:" | head -5
done
