#!/usr/bin/env bash
# Reproduce the CI/CD "Build & Validate Distribution" job for jnwb inside WSL, step by step.
# usage: ci_wsl_build.sh <sha> <name>
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$HOME/_temp_jnwb_ci
sha=${1:?sha}; name=${2:?name}
export BROWSER_PATH="$HOME/.local/share/choreographer/deps/chrome-linux64/chrome"
[ -x "$BROWSER_PATH" ] || { echo "no Chrome at $BROWSER_PATH"; exit 2; }
ws="$root/ws_build_$name"; clean="$root/clean_env_$name"; outside="$root/outside_$name"
[ ! -e "$ws" ] && [ ! -e "$clean" ] || { echo "$ws or $clean exists; choose a new name"; exit 2; }
bash "$here/ci_shallow_clone.sh" file:///mnt/d/repos/_work/_temp_jnwb_qual "$ws" "$sha" || exit 1
mkdir -p "$root/home_ci" "$outside" && : > "$root/empty_gitconfig"
venv="$root/venv_build_$name"
python3 -m venv "$venv" || exit 1
export HOME="$root/home_ci"
export GIT_CONFIG_GLOBAL="$root/empty_gitconfig"
export GITHUB_ACTIONS=true CI=true GITHUB_WORKSPACE="$ws"
export JNWB_FIGURE_FONT_DIR="$root/fonts/liberation-fonts-ttf-2.1.5"
PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/' | paste -sd: -)
export PATH
# shellcheck disable=SC1090,SC1091
source "$venv/bin/activate" || exit 2
cd "$ws" || exit 2
echo "HEAD $(git rev-parse HEAD); $(python --version)"

step() {
  local title=$1; shift
  echo "=== $title"
  "$@" || { echo "STEP FAILED ($?): $title"; exit 1; }
}

step "upgrade pip" python -m pip install --upgrade pip -q
step "install build tools, docs tools and dependencies" python -m pip install ".[test,docs]" build twine -q
python -m pip freeze > "$root/freeze_build_$name.txt"
step "reconstruct state" python scripts/reconstruct_state.py
step "harness gate" python scripts/harness_gate.py
step "docs build (strict)" python scripts/docs_build.py
step "build sdist and wheel" python -m build
step "twine check" twine check dist/*
step "manifest check" python "$here/py/manifest_check.py"

step "clean venv" python -m venv "$clean"
step "clean venv pip" "$clean/bin/pip" install --upgrade pip -q
step "install the wheel" "$clean/bin/pip" install dist/*.whl -q
step "pip check" "$clean/bin/pip" check
version=$(basename dist/*.whl | cut -d- -f2)
unset PYTHONPATH
cd "$outside" || exit 2
step "smoke installed $version" "$clean/bin/python" "$ws/scripts/smoke_installed.py" --expected-version "$version" --not-under "$ws"

cd "$ws" || exit 2
step "write test requirements" python "$here/py/write_test_requirements.py" "$outside/test-requirements.txt"
step "install test requirements" "$clean/bin/pip" install -r "$outside/test-requirements.txt" -q
"$clean/bin/pip" freeze > "$root/freeze_clean_$name.txt"
purelib=$("$clean/bin/python" "$here/py/purelib.py")
echo "Suite will run against: $purelib/jnwb"
cd "$outside" || exit 2
echo "=== wheel suite"
JNWB_REQUIRE_BROWSER=1 JNWB_EXPECTED_PACKAGE_ROOT="$purelib" "$clean/bin/python" -m pytest \
  --import-mode=importlib -o pythonpath= -n auto --rootdir="$ws" "$ws/tests" -q -rf
suite_rc=$?
echo "wheel suite rc=$suite_rc"
[ "$suite_rc" -eq 0 ] || exit 1

echo "=== tutorials"
export JNWB_EXPECTED_PACKAGE_ROOT="$purelib"
"$clean/bin/python" "$here/py/assert_clean_env.py" || exit 1
status=0
for tutorial in "$ws"/examples/tutorials/[0-9][0-9]_*.py; do
  tname=$(basename "$tutorial")
  if "$clean/bin/python" "$tutorial" > "$outside/tutorial_$tname.log" 2>&1; then
    echo "PASS: $tname"
  else
    echo "FAIL: $tname"
    tail -30 "$outside/tutorial_$tname.log"
    status=1
  fi
done
echo "build job rc=$status"
exit $status
