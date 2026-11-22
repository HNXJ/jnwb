#!/usr/bin/env bash
# Push the current branch of a jnwb checkout to origin only when
#   - jnwb_suite.sh passed at exactly this HEAD (its stamp), unless every commit since
#     origin/<branch> touches only artifacts/ (plan/stack edits; the stack checks below are the gate),
#   - the tracked tree is clean, and
#   - no Actions run on the branch is in flight, and
#   - CI ran at origin's tip of the branch, read from the remote at push time: at least one run is
#     listed at that SHA and every run there completed and succeeded; a run at an earlier SHA does
#     not count (scripts/ci_gate.py --tip). Override: JNWB_PUSH_OVER_RED=1 pushes over one case only,
#     a completed run at the tip that did not succeed (ci_gate exit 3), for the push that carries the
#     fix. Every other refusal, a tip with no run or a pending run among them, stays a refusal.
# An artifacts-only push first runs the stack checks: scripts/harness_gate.py (gate 15 among them)
# and tests/test_stack_item_length.py.
# Usage: jnwb_push.sh <dir> [branch=dev] [--item <id>]
#   --item <id>: also refuse a push whose diff against origin/<branch> leaves the Writes of that
#   todo item (read from origin/<branch>), beyond the always-writable stacks and changelog paths.
#   The check is verify_lane.py --push-item; an artifacts-only push whose Writes name a bare
#   directory is refused there.
# Usage: jnwb_push.sh <dir> --tag vX.Y.Z
#   Tags origin/main's tip, and only when the newest completed run on main is at that tip and
#   succeeded (no override). A tag that already exists on origin is never moved.
set -o pipefail
here=$(cd "$(dirname "$0")" && pwd)
dir="$1"; branch="${2:-dev}"
bin="$HOME/.claude/bin"  # the CI in-flight helper jarness installs

if [ "$branch" = "--tag" ]; then
  tag="${3:-}"
  [[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "refusing: tag must be vX.Y.Z, got '$tag'"; exit 2; }
  cd "$dir" || exit 2
  git fetch origin main </dev/null || { echo "refusing: fetch of origin/main failed"; exit 1; }
  tip=$(git rev-parse origin/main) || { echo "refusing: origin/main is unreadable"; exit 1; }
  remote_tag=$(git ls-remote --tags origin "refs/tags/$tag" </dev/null) \
    || { echo "refusing: ls-remote of origin failed"; exit 1; }
  [ -z "$remote_tag" ] || { echo "refusing: tag $tag already exists on origin; a tag is never moved"; exit 1; }
  inflight=$(python "$bin/ci_inflight.py" hnxj/jnwb main) || { echo "refusing: CI count unreadable"; exit 1; }
  [ "$inflight" = "0" ] || { echo "refusing: $inflight run(s) in flight on main"; exit 1; }
  gate_out=$(python "$here/ci_gate.py" hnxj/jnwb main --require-name "CI/CD"); gate_rc=$?
  case "$gate_rc" in
    0) ;;
    2) echo "refusing: CI conclusion unreadable: $gate_out"; exit 1 ;;
    *) echo "refusing: CI gate on main: $gate_out"; exit 1 ;;
  esac
  case "$gate_out" in
    "pass ${tip:0:8}"*) ;;
    *) echo "refusing: the newest completed main run is not at origin/main tip ${tip:0:8}: $gate_out"; exit 1 ;;
  esac
  # origin/main may have moved while CI was read; the tag goes only to the tip the CI check named.
  now_out=$(git ls-remote origin refs/heads/main </dev/null) || { echo "refusing: ls-remote of origin/main failed"; exit 1; }
  now=${now_out%%$'\t'*}
  [ "$now" = "$tip" ] || { echo "refusing: origin/main moved from ${tip:0:8} to ${now:0:8} since the CI read"; exit 1; }
  git push origin "$tip:refs/tags/$tag" </dev/null || exit 1
  echo "pushed $tag at ${tip:0:8}"
  exit 0
fi

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
changed=$(git diff --name-only "origin/$branch..HEAD") || { echo "refusing: git diff origin/$branch..HEAD failed"; exit 1; }
outside=$(git diff --name-only "origin/$branch..HEAD" | grep -v '^artifacts/' || true)
if [ -n "$outside" ]; then
  [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$head" ] || {
    echo "no passing jnwb_suite.sh run at ${head:0:8}; files outside artifacts/ changed:"
    echo "$outside" | head -5
    exit 1
  }
elif [ -n "$changed" ]; then
  # Artifacts-only: the stack checks are the gate, and they run before anything is pushed.
  log=$(mktemp)
  if ! python scripts/harness_gate.py </dev/null >"$log" 2>&1; then
    echo "refusing: stack gate (scripts/harness_gate.py) failed on an artifacts-only push:"
    tail -n 20 "$log"; rm -f "$log"; exit 1
  fi
  if ! python -m pytest tests/test_stack_item_length.py -q -p no:cacheprovider >"$log" 2>&1; then
    echo "refusing: tests/test_stack_item_length.py failed on an artifacts-only push:"
    tail -n 20 "$log"; rm -f "$log"; exit 1
  fi
  rm -f "$log"
fi
inflight=$(python "$bin/ci_inflight.py" hnxj/jnwb "$branch") || { echo "CI count unreadable"; exit 1; }
[ "$inflight" = "0" ] || { echo "$inflight run(s) in flight on $branch"; exit 1; }
# CI must have run at the commit this push builds on, origin's tip of the branch as the remote holds
# it now; the newest run of the branch may sit at an earlier SHA and says nothing about the tip.
tip_out=$(git ls-remote origin "refs/heads/$branch" </dev/null) \
  || { echo "refusing: ls-remote of origin/$branch failed"; exit 1; }
# ls-remote matches a pattern by its trailing path, so a ref such as refs/heads/a/refs/heads/dev is
# listed too, and sorts first; one line is the only answer that names the branch.
case "$tip_out" in
  *$'\n'*) echo "refusing: origin lists more than one ref matching refs/heads/$branch"; exit 1 ;;
esac
tip=${tip_out%%$'\t'*}
if [ -z "$tip" ]; then
  gate_out="refuse: origin has no $branch, so no CI run can be at its tip"; gate_rc=1
else
  gate_out=$(python "$here/ci_gate.py" hnxj/jnwb "$branch" --tip "$tip"); gate_rc=$?
fi
case "$gate_rc" in
  0) ;;
  2) echo "CI conclusion unreadable: $gate_out"; exit 1 ;;
  3) if [ "${JNWB_PUSH_OVER_RED:-}" = "1" ]; then
       echo "CI gate on $branch: $gate_out; pushing anyway (JNWB_PUSH_OVER_RED=1)"
     else
       echo "CI gate on $branch: $gate_out; refusing. Read its failure; to push the fix, set JNWB_PUSH_OVER_RED=1"
       exit 1
     fi ;;
  *) echo "CI gate on $branch: $gate_out; refusing"; exit 1 ;;
esac
git push origin "$branch" </dev/null
