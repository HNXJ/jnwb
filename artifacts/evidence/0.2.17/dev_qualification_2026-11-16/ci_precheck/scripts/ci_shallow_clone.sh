#!/usr/bin/env bash
# Check out one commit the way actions/checkout does: depth 1, local branch dev tracking origin/dev.
# usage: ci_shallow_clone.sh <source repo url> <dest dir> <sha> [branch=dev]
set -uo pipefail
src=${1:?source}; dest=${2:?dest}; sha=${3:?sha}; branch=${4:-dev}
[ ! -e "$dest" ] || { echo "$dest exists"; exit 2; }
git init -q "$dest" || exit 1
cd "$dest" || exit 2
git remote add origin "$src" || exit 1
git -c uploadpack.allowAnySHA1InWant=true -c protocol.file.allow=always fetch -q --no-tags --depth=1 origin \
  "+$sha:refs/remotes/origin/$branch" </dev/null || { echo "shallow fetch failed"; exit 1; }
git checkout -q --force -B "$branch" "refs/remotes/origin/$branch" || exit 1
echo "HEAD $(git rev-parse HEAD); commits reachable: $(git rev-list --count HEAD); shallow: $(git rev-parse --is-shallow-repository)"
[ "$(git rev-parse HEAD)" = "$sha" ] || { echo "not at $sha"; exit 1; }
