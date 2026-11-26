#!/usr/bin/env bash
# Build a CI-like Windows environment for jnwb: fresh clone at a SHA, fresh venv, the CI install line.
# usage: ci_win_setup.sh <sha> <name>
set -uo pipefail
root=D:/repos/_work/_temp_jnwb_ci
sha=${1:?sha}; name=${2:?name}
mkdir -p "$root" && cd "$root" || exit 2
if [ ! -d "src_$name" ]; then
  git clone -q D:/repos/_work/_temp_jnwb_qual "src_$name" </dev/null || exit 1
  git -C "src_$name" checkout -q --detach "$sha" || exit 1
fi
[ "$(git -C "src_$name" rev-parse HEAD)" = "$sha" ] || { echo "src_$name is not at $sha"; exit 1; }
if [ ! -d fonts/liberation-fonts-ttf-2.1.5 ]; then
  mkdir -p fonts && cd fonts || exit 2
  curl -fsSL --retry 5 --retry-delay 10 --retry-all-errors --connect-timeout 30 -o liberation-fonts.tar.gz \
    https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz || exit 1
  echo "7191c669bf38899f73a2094ed00f7b800553364f90e2637010a69c0e268f25d0  liberation-fonts.tar.gz" | sha256sum -c - || exit 1
  tar xzf liberation-fonts.tar.gz || exit 1
  cd "$root" || exit 2
fi
[ -d venv_win314 ] || C:/Python314/python -m venv venv_win314 || exit 1
py="$root/venv_win314/Scripts/python.exe"
# No pip config file: this machine's global pip config adds an index CI does not have.
export PIP_CONFIG_FILE=nul
"$py" -m pip config list
"$py" -m pip install --upgrade pip -q || exit 1
cd "$root/src_$name" || exit 2
"$py" -m pip install ".[test,docs,vis,wavemap]" -q || { echo "install failed"; exit 1; }
"$py" -m pip install "matplotlib==3.11.2" -q || exit 1
"$py" -m pip freeze > "$root/freeze_win314_$name.txt"
"$py" --version
echo "setup ok: $name at $sha; $(wc -l < "$root/freeze_win314_$name.txt") packages"
