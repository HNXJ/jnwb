#!/usr/bin/env bash
# Build a CI-like Linux environment for jnwb inside WSL: fresh clone at a SHA, fresh venv, the CI install line.
# usage: ci_wsl_setup.sh <sha> <name> <venv> <python> [extras]
set -uo pipefail
root=$HOME/_temp_jnwb_ci
sha=${1:?sha}; name=${2:?name}; venv=${3:?venv}; python=${4:?python}; extras=${5:-test,docs,vis,wavemap}
mkdir -p "$root" && cd "$root" || exit 2
if [ ! -d "src_$name" ]; then
  git clone -q /mnt/d/repos/_work/_temp_jnwb_qual "src_$name" </dev/null || exit 1
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
[ -d "$venv" ] || "$python" -m venv "$venv" || exit 1
py="$root/$venv/bin/python"
"$py" -m pip install --upgrade pip -q || exit 1
cd "$root/src_$name" || exit 2
HDF5_PKGCONFIG_NAME=hdf5-serial "$py" -m pip install ".[$extras]" -q || { echo "install failed"; exit 1; }
"$py" -m pip freeze > "$root/freeze_${venv}_$name.txt"
"$py" --version
echo "setup ok: $name at $sha in $venv; $(wc -l < "$root/freeze_${venv}_$name.txt") packages"
