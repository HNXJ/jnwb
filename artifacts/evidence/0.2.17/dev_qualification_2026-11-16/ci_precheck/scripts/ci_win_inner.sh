#!/usr/bin/env bash
# Run the jnwb suite as the Windows 3.14 CI leg does, without this machine's home, git identity or data paths.
# usage: ci_win_inner.sh <name> [pytest args...]   (default args: tests/)
root=D:/repos/_work/_temp_jnwb_ci
name=${1:?name}; shift
unset JNWB_NWB_DIR JNWB_META_DIR JNWB_ANALYSIS_DIR JNWB_TFR_DIR PYTHONIOENCODING GIT_EDITOR
mkdir -p "$root/home_win" && : > "$root/empty_gitconfig"
export HOME="$root/home_win"
export USERPROFILE='D:\repos\_work\_temp_jnwb_ci\home_win'
export GIT_CONFIG_GLOBAL="$root/empty_gitconfig"
export GITHUB_ACTIONS=true CI=true
export JNWB_FIGURE_FONT_DIR="$root/fonts/liberation-fonts-ttf-2.1.5"
export JNWB_REQUIRE_FIGURE_COMPARISON=1 JNWB_REQUIRE_BROWSER=1
# shellcheck disable=SC1091
source "$root/venv_win314/Scripts/activate" || exit 2
cd "$root/src_$name" || exit 2
echo "HEAD $(git rev-parse HEAD); $(python --version); python=$(command -v python)"
if [ "$#" -eq 0 ]; then set -- tests/; fi
python scripts/ci_pytest.py "$@" --basetemp "D:/pytest_temp/jnwb_ci_win_$name"
