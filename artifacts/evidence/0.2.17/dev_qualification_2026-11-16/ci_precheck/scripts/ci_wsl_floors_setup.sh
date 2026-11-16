#!/usr/bin/env bash
# Prepare the CI/CD "dependency floors" leg for jnwb inside WSL: Python 3.12.0, floors resolved by uv.
# usage: ci_wsl_floors_setup.sh <sha> <name>     (creates src_<name> and venv_<name>)
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$HOME/_temp_jnwb_ci
sha=${1:?sha}; name=${2:?name}
floor_python=3.12.0
PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/' | paste -sd: -)
export PATH
cd "$root" || exit 2
[ -d venv_tools ] || { python3 -m venv venv_tools && venv_tools/bin/pip install -q --upgrade pip uv; } || exit 1
uv="$root/venv_tools/bin/uv"
"$uv" python install "$floor_python" || exit 1
base=$("$uv" python find "$floor_python") || exit 1
echo "floor interpreter: $base ($("$base" --version))"
[ "$("$base" --version)" = "Python $floor_python" ] || { echo "not $floor_python"; exit 1; }
[ ! -e "src_$name" ] && [ ! -e "venv_$name" ] || { echo "src_$name or venv_$name exists; choose a new name"; exit 2; }
git clone -q /mnt/d/repos/_work/_temp_jnwb_qual "src_$name" </dev/null || exit 1
git -C "src_$name" checkout -q --detach "$sha" || exit 1
"$base" -m venv "venv_$name" || exit 1
# shellcheck disable=SC1090,SC1091
source "$root/venv_$name/bin/activate" || exit 2
cd "$root/src_$name" || exit 2
python -m pip install -q --upgrade pip uv || exit 1
python "$here/py/floors_in.py" "$root/floors_$name.in" || exit 1
uv pip compile --python-version "$floor_python" --resolution lowest-direct "$root/floors_$name.in" -o "$root/floors_$name.lock" -q || exit 1
python "$here/py/floors_check.py" "$root/floors_$name.lock" "$root/floors_$name.txt" || exit 1
python -m pip install -q ".[test,docs,vis,wavemap]" -c "$root/floors_$name.txt" || { echo "install at the floors failed"; exit 1; }
python -m pip freeze > "$root/freeze_venv_${name}.txt"
echo "setup ok: floors leg $name at $sha; $(wc -l < "$root/freeze_venv_${name}.txt") packages"
