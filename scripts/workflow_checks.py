#!/usr/bin/env python3
"""Checks the release workflow hands to its jobs. Each is a plain function a test can drive.

``qualifying-run`` reads an Actions run listing on stdin and prints the id of the run that lets a
release tag skip the test legs. ``same-wheel`` refuses a wheel fetched from an index whose sha256
is not the build artifact's. It uses only the standard library, so a job can run it before any
install.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

WORKFLOW_PATH = ".github/workflows/workflow.yml"


def qualifying_run_id(listing: Any, sha: str, *, branch: str = "main") -> str:
    """The id of the first run of this workflow that passed on ``branch`` at ``sha``, or ``""``.

    A listing without ``workflow_runs``, such as a rate-limit body, names no run, so the caller
    runs the tests.
    """
    runs = listing.get("workflow_runs") if isinstance(listing, dict) else None
    for run in runs or []:
        if (run.get("head_sha") == sha and run.get("head_branch") == branch
                and run.get("path") == WORKFLOW_PATH and run.get("conclusion") == "success"):
            return str(run["id"])
    return ""


def missing_matrix_legs(matrix: dict, classifiers: Iterable[str]) -> set:
    """The (os, Python version) legs the test matrix does not run, out of every 3.x interpreter the
    classifiers declare on every system the matrix lists. An ``exclude`` entry removes a leg."""
    declared = set()
    for classifier in classifiers:
        match = re.fullmatch(r"Programming Language :: Python :: (3\.\d+)", classifier)
        if match:
            declared.add(match.group(1))
    excluded = {(entry["os"], entry["python-version"]) for entry in matrix.get("exclude", [])}
    run = {(os, version) for os in matrix["os"] for version in matrix["python-version"]}
    expected = {(os, version) for os in matrix["os"] for version in declared}
    return expected - (run - excluded)


def wheel_problem(built: Path, fetched: Path) -> str:
    """``""`` when the fetched wheel is byte-for-byte the build artifact, else a message that
    names both sha256 digests."""
    built_digest = hashlib.sha256(built.read_bytes()).hexdigest()
    fetched_digest = hashlib.sha256(fetched.read_bytes()).hexdigest()
    if built_digest == fetched_digest:
        return ""
    return f"{fetched.name} sha256 {fetched_digest} is not the build artifact's {built_digest}"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    qualifying = commands.add_parser(
        "qualifying-run", help="print the id of the passed main run a listing on stdin names")
    qualifying.add_argument("--sha", required=True, help="the commit the tag points at")
    same = commands.add_parser(
        "same-wheel", help="refuse a fetched wheel whose sha256 differs from the build artifact's")
    same.add_argument("built", type=Path)
    same.add_argument("fetched", type=Path)
    args = parser.parse_args(argv)
    if args.command == "qualifying-run":
        print(qualifying_run_id(json.load(sys.stdin), args.sha))
    elif args.command == "same-wheel":
        problem = wheel_problem(args.built, args.fetched)
        if problem:
            print(f"FAIL: {problem}", file=sys.stderr)
            return 1
        print(f"{args.fetched.name}: sha256 matches the build artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
