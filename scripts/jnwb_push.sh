#!/usr/bin/env bash
# Push the current branch of a jnwb checkout to origin only when
#   - jnwb_suite.sh passed at exactly this HEAD (its stamp), unless every commit since
#     origin/<branch> touches only artifacts/ (plan/stack edits; their stack tests are the gate),
#   - the tracked tree is clean, and
#   - no Actions run on the branch is in flight, and
#   - the newest completed run on the branch succeeded (override: JNWB_PUSH_OVER_RED=1,
#     for the push that carries the fix).
# Usage: jnwb_push.sh <dir> [branch=dev]
set -o pipefail
dir="$1"; branch="${2:-dev}"
cd "$dir" || exit 2
[ "$(git rev-parse --abbrev-ref HEAD)" = "$branch" ] || { echo "not on $branch"; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "tracked changes present"; exit 1; }
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
bin="$HOME/.claude/bin"  # the CI helpers jarness installs
inflight=$(python "$bin/ci_inflight.py" hnxj/jnwb "$branch") || { echo "CI count unreadable"; exit 1; }
[ "$inflight" = "0" ] || { echo "$inflight run(s) in flight on $branch"; exit 1; }
last=$(python "$bin/ci_last_conclusion.py" hnxj/jnwb "$branch") || { echo "CI conclusion unreadable"; exit 1; }
case "$last" in
  success*|none*) ;;
  *) if [ "${JNWB_PUSH_OVER_RED:-}" = "1" ]; then
       echo "last CI run on $branch: $last; pushing anyway (JNWB_PUSH_OVER_RED=1)"
     else
       echo "last CI run on $branch: $last; refusing. Read its failure; to push the fix, set JNWB_PUSH_OVER_RED=1"
       exit 1
     fi ;;
esac
git push origin "$branch" </dev/null
