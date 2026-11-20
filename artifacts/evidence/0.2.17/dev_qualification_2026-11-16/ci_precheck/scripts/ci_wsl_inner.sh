#!/usr/bin/env bash
# Run the jnwb suite as an ubuntu CI test leg does, without this machine's home, git identity or Windows PATH.
# usage: ci_wsl_inner.sh <name> <venv> <state:0|1> [pytest args...]   (default args: tests/)
root=$HOME/_temp_jnwb_ci
name=${1:?name}; venv=${2:?venv}; state=${3:?state}; shift 3
# The runner has a system Chrome; here choreographer's download stands in for it.
export BROWSER_PATH="$HOME/.local/share/choreographer/deps/chrome-linux64/chrome"
[ -x "$BROWSER_PATH" ] || { echo "no Chrome at $BROWSER_PATH"; exit 2; }
mkdir -p "$root/home_ci" && : > "$root/empty_gitconfig"
export HOME="$root/home_ci"
export GIT_CONFIG_GLOBAL="$root/empty_gitconfig"
export GITHUB_ACTIONS=true CI=true
export JNWB_FIGURE_FONT_DIR="$root/fonts/liberation-fonts-ttf-2.1.5"
export JNWB_REQUIRE_FIGURE_COMPARISON=0 JNWB_REQUIRE_BROWSER=1
# Drop the Windows directories WSL appends to PATH.
PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/' | paste -sd: -)
export PATH
# shellcheck disable=SC1090,SC1091
source "$root/$venv/bin/activate" || exit 2
cd "$root/src_$name" || exit 2
echo "HEAD $(git rev-parse HEAD); $(python --version); python=$(command -v python); cores=$(nproc)"
if [ "$state" = "1" ]; then python scripts/reconstruct_state.py || { echo "reconstruct_state failed"; exit 1; }; fi
if [ "$#" -eq 0 ]; then set -- tests/; fi
python scripts/ci_pytest.py "$@"
