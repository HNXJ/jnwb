#!/usr/bin/env bash
# Resolve jnwb's CI install line today for one interpreter and platform, without installing anything.
# usage: ci_wsl_resolve.sh <src name> <python version> <linux|windows> <out file> [extras, comma separated]
set -uo pipefail
root=$HOME/_temp_jnwb_ci
name=${1:?src name}; pyver=${2:?python version}; platform=${3:?platform}; out=${4:?out file}
extras=${5:-test,docs,vis,wavemap}
args=()
IFS=',' read -ra list <<< "$extras"
for extra in "${list[@]}"; do args+=(--extra "$extra"); done
"$root/venv_tools/bin/uv" pip compile "$root/src_$name/pyproject.toml" "${args[@]}" \
  --python-version "$pyver" --python-platform "$platform" --no-header -q -o "$out" || { echo "resolve failed"; exit 1; }
echo "$pyver $platform: $(grep -c '==' "$out") pins"
