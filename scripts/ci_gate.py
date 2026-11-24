"""Decide from the CI runs of a branch whether jnwb_push.sh may push.

Usage: python scripts/ci_gate.py <owner/repo> [branch=dev] [--tip SHA] [--require-name NAME]
With --tip (the branch push; SHA is origin's tip of the branch, 40 hex digits), reads the runs of the
branch at that SHA from the Actions API, whatever their status: at least one must be listed, every
one must be completed and every one must have concluded success. A run at any other SHA does not
count, so green CI at an earlier commit never passes a later tip.
Without --tip (the tag push, which compares the printed SHA with origin/main's tip itself), reads the
completed runs of the branch (newest first, 20 per page). Only the newest SHA counts: every completed
run at that SHA must have concluded success.
With --require-name, at least one run at the deciding SHA must be a successful run named NAME (the
tag push needs the CI/CD run, not any run).
Exit codes: 0 pass (prints "pass <sha8> ..."); 3 refuse on a completed run that did not conclude
success, the line ending "; run ids: <id> ..." (the only refusal JNWB_PUSH_OVER_RED may override); 1 refuse for any other reason (a run not
completed, no run listed or at the tip, a missing required name); 2 unreadable (network, HTTP
status, bad JSON, a response without workflow_runs, such as a rate-limit body, a --tip that is not
a full SHA, or, with --tip, a total_count that is missing or exceeds the runs of the one page read).
JNWB_CI_API overrides the API base; the tests point it at a local server.
"""
import json
import os
import re
import sys
import urllib.request

USAGE = "usage: ci_gate.py <owner/repo> [branch] [--tip SHA] [--require-name NAME]"


def fetch(repo, branch, tip=None):
    base = os.environ.get("JNWB_CI_API", "https://api.github.com")
    query = f"head_sha={tip}&per_page=100" if tip else "status=completed&per_page=20"
    url = f"{base}/repos/{repo}/actions/runs?branch={branch}&{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def decide(runs, require_name=None, tip=None):
    """(exit code, line) for the runs of a branch, newest first.

    A run counts only at the deciding SHA: ``tip`` when given, else the newest SHA listed. With
    ``tip``, no run at it refuses, and so does a run there that is not completed. Any conclusion
    other than success refuses, a failed or cancelled run among them; no run listed refuses. With
    ``require_name``, a successful run of that name must also be among the runs at the deciding SHA.
    """
    if tip is None:
        if not runs:
            return 1, "refuse: no completed run is listed on the branch"
        sha = runs[0]["head_sha"]
    else:
        sha = tip
    at_sha = [run for run in runs if run["head_sha"] == sha]
    if not at_sha:
        newest = f"the newest listed run is at {runs[0]['head_sha'][:8]}" if runs else "no run is listed"
        return 1, f"refuse: no run at the branch tip {sha[:8]}; {newest}"
    if tip is not None:
        pending = [f"{run.get('name')}: {run.get('status')}" for run in at_sha
                   if run.get("status") != "completed"]
        if pending:
            return 1, f"refuse: {sha[:8]} has run(s) not completed: " + "; ".join(pending)
    red = [run for run in at_sha if run.get("conclusion") != "success"]
    if red:
        bad = "; ".join(f"{run.get('name')}: {run.get('conclusion')}" for run in red)
        ids = " ".join(str(run.get("id")) for run in red)
        return 3, f"refuse: {sha[:8]} has completed run(s) not successful: {bad}; run ids: {ids}"
    if require_name and not any(run.get("name") == require_name for run in at_sha):
        return 1, f"refuse: no successful '{require_name}' run at {sha[:8]}"
    return 0, f"pass {sha[:8]}: {len(at_sha)} completed run(s) succeeded"


def _option(args, name):
    """Remove ``name VALUE`` from ``args``; (value or None, whether the value was missing)."""
    if name not in args:
        return None, False
    at = args.index(name)
    if at + 1 >= len(args):
        return None, True
    value = args[at + 1]
    del args[at:at + 2]
    return value, False


def main(argv):
    args = list(argv)
    require_name, no_name = _option(args, "--require-name")
    tip, no_tip = _option(args, "--tip")
    if no_name or no_tip or not args:
        print(USAGE)
        return 2
    if tip is not None and not re.fullmatch(r"[0-9a-f]{40}", tip):
        print(f"unreadable: --tip must be a full 40-hex SHA, got '{tip}'")
        return 2
    repo = args[0]
    branch = args[1] if len(args) > 1 else "dev"
    try:
        data = fetch(repo, branch, tip)
    except Exception as exc:  # network, HTTP status, timeout or bad JSON
        print(f"unreadable: {exc}")
        return 2
    runs = data.get("workflow_runs") if isinstance(data, dict) else None
    if runs is None:
        print("unreadable: no workflow_runs in the response")
        return 2
    total = data.get("total_count")
    if tip is not None and (type(total) is not int or total > len(runs)):
        print(f"unreadable: total_count is {total!r} with {len(runs)} run(s) read at the tip; "
              "a run not read could have failed")
        return 2
    try:
        code, line = decide(runs, require_name, tip)
    except (KeyError, TypeError) as exc:
        print(f"unreadable: malformed run ({exc})")
        return 2
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
