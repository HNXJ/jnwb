"""Decide from the completed CI runs of a branch whether jnwb_push.sh may push.

Usage: python scripts/ci_gate.py <owner/repo> [branch=dev] [--require-name NAME]
Reads the completed runs of the branch from the Actions API (newest first, 20 per page). Only the
newest SHA counts: every completed run at that SHA must have concluded success. With
--require-name, at least one run at that SHA must be a successful run named NAME (the tag push
needs the CI/CD run, not any run).
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


def decide(runs, require_name=None):
    """(exit code, line) for the completed runs of a branch, newest first.

    A run counts only at the newest SHA. Any conclusion other than success refuses there, a failed
    or cancelled run among them; no run listed refuses. With ``require_name``, a successful run of
    that name must also be among the runs at the newest SHA.
    """
    if not runs:
        return 1, "refuse: no completed run is listed on the branch"
    sha = runs[0]["head_sha"]
    at_sha = [run for run in runs if run["head_sha"] == sha]
    bad = [f"{run.get('name')}: {run.get('conclusion')}" for run in at_sha
           if run.get("conclusion") != "success"]
    if bad:
        return 1, f"refuse: {sha[:8]} has completed run(s) not successful: " + "; ".join(bad)
    if require_name and not any(run.get("name") == require_name for run in at_sha):
        return 1, f"refuse: no successful '{require_name}' run at {sha[:8]}"
    return 0, f"pass {sha[:8]}: {len(at_sha)} completed run(s) succeeded"


def main(argv):
    args = list(argv)
    require_name = None
    if "--require-name" in args:
        at = args.index("--require-name")
        if at + 1 >= len(args):
            print("usage: ci_gate.py <owner/repo> [branch] [--require-name NAME]")
            return 2
        require_name = args[at + 1]
        del args[at:at + 2]
    repo = args[0]
    branch = args[1] if len(args) > 1 else "dev"
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
        code, line = decide(runs, require_name)
    except (KeyError, TypeError) as exc:
        print(f"unreadable: malformed run ({exc})")
        return 2
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
