#!/usr/bin/env bash
# Push the current branch of a jnwb checkout to origin only when
#   - jnwb_suite.sh passed at exactly this HEAD (its stamp), unless every commit since
#     origin/<branch> touches only artifacts/ (plan/stack edits; their stack tests are the gate),
#   - the tracked tree is clean, and
#   - no Actions run on the branch is in flight, and
#   - every completed run at the newest SHA on the branch succeeded, and at least one is listed
#     (scripts/ci_gate.py; override: JNWB_PUSH_OVER_RED=1, for the push that carries the fix).
# Usage: jnwb_push.sh <dir> [branch=dev] [--item <id>]
#   --item <id>: also refuse a push whose diff against origin/<branch> leaves the Writes of that
#   todo item (read from origin/<branch>), beyond the always-writable stacks and changelog paths.
#   The check is verify_lane.py --push-item.
set -o pipefail
here=$(cd "$(dirname "$0")" && pwd)
dir="$1"; branch="${2:-dev}"
[ "$branch" != "--item" ] || { echo "usage: jnwb_push.sh <dir> [branch] [--item <id>]"; exit 2; }
cd "$dir" || exit 2
[ "$(git rev-parse --abbrev-ref HEAD)" = "$branch" ] || { echo "not on $branch"; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "tracked changes present"; exit 1; }
item=""
if [ "${3:-}" = "--item" ]; then
  item="${4:-}"
  [ -n "$item" ] || { echo "usage: jnwb_push.sh <dir> [branch] [--item <id>]"; exit 2; }
  # The item's Writes are read from the target, so fetch it first.
  git fetch origin "$branch" </dev/null || { echo "fetch of origin/$branch failed"; exit 1; }
  python scripts/verify_lane.py --push-item "$item" --target "origin/$branch" || exit 1
fi
head=$(git rev-parse HEAD)
stamp="$(git rev-parse --git-dir)/jnwb_suite_ok"
outside=$(git diff --name-only "origin/$branch..HEAD" | grep -v '^artifacts/' || true)
if [ -n "$outside" ]; then
  [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$head" ] || {
    echo "no passing jnwb_suite.sh run at ${head:0:8}; files outside artifacts/ changed:"
    echo "$outside" | head -5
    exit 1
  }
fi
bin="$HOME/.claude/bin"  # the CI in-flight helper jarness installs
inflight=$(python "$bin/ci_inflight.py" hnxj/jnwb "$branch") || { echo "CI count unreadable"; exit 1; }
[ "$inflight" = "0" ] || { echo "$inflight run(s) in flight on $branch"; exit 1; }
gate_out=$(python "$here/ci_gate.py" hnxj/jnwb "$branch"); gate_rc=$?
case "$gate_rc" in
  0) ;;
  2) echo "CI conclusion unreadable: $gate_out"; exit 1 ;;
  *) if [ "${JNWB_PUSH_OVER_RED:-}" = "1" ]; then
       echo "CI gate on $branch: $gate_out; pushing anyway (JNWB_PUSH_OVER_RED=1)"
     else
       echo "CI gate on $branch: $gate_out; refusing. Read its failure; to push the fix, set JNWB_PUSH_OVER_RED=1"
       exit 1
     fi ;;
esac
git push origin "$branch" </dev/null
