"""Decide from the completed CI runs of a branch whether jnwb_push.sh may push.

Usage: python scripts/ci_gate.py <owner/repo> [branch=dev]
Reads the completed runs of the branch from the Actions API (newest first, 20 per page). Only the
newest SHA counts: every completed run at that SHA must have concluded success.
Exit codes: 0 pass (prints "pass <sha8> ..."); 1 refuse (prints "refuse: ..." naming each run that
did not succeed, or that no run is listed); 2 unreadable (network, HTTP status, bad JSON, or a
response without workflow_runs, such as a rate-limit body).
JNWB_CI_API overrides the API base; the tests point it at a local server.
"""
import json
import os
import sys
import urllib.request


def fetch(repo, branch):
    base = os.environ.get("JNWB_CI_API", "https://api.github.com")
    url = f"{base}/repos/{repo}/actions/runs?branch={branch}&status=completed&per_page=20"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def decide(runs):
    """(exit code, line) for the completed runs of a branch, newest first.

    A run counts only at the newest SHA. Any conclusion other than success refuses there, a failed
    or cancelled run among them; no run listed refuses.
    """
    if not runs:
        return 1, "refuse: no completed run is listed on the branch"
    sha = runs[0]["head_sha"]
    at_sha = [run for run in runs if run["head_sha"] == sha]
    bad = [f"{run.get('name')}: {run.get('conclusion')}" for run in at_sha
           if run.get("conclusion") != "success"]
    if bad:
        return 1, f"refuse: {sha[:8]} has completed run(s) not successful: " + "; ".join(bad)
    return 0, f"pass {sha[:8]}: {len(at_sha)} completed run(s) succeeded"


def main(argv):
    repo = argv[0]
    branch = argv[1] if len(argv) > 1 else "dev"
    try:
        data = fetch(repo, branch)
    except Exception as exc:  # network, HTTP status, timeout or bad JSON
        print(f"unreadable: {exc}")
        return 2
    runs = data.get("workflow_runs") if isinstance(data, dict) else None
    if runs is None:
        print("unreadable: no workflow_runs in the response")
        return 2
    try:
        code, line = decide(runs)
    except (KeyError, TypeError) as exc:
        print(f"unreadable: malformed run ({exc})")
        return 2
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
