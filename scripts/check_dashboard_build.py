"""Refuse a dashboard site that is incomplete or was not built from the source commit.

Usage: python scripts/check_dashboard_build.py SITE_DIR EXPECTED_SHA

Exit 0: index.html, app.js and data.json exist and data.json's generated.commit equals EXPECTED_SHA.
Exit 1: a file is missing, generated.commit is unreadable, or the commit differs.
Exit 2: wrong arguments.
"""

import json
import sys
from pathlib import Path

REQUIRED = ("index.html", "app.js", "data.json")


def check(site, expected):
    problems = [f"missing {name} in {site}" for name in REQUIRED if not (site / name).is_file()]
    data_path = site / "data.json"
    if data_path.is_file():
        try:
            commit = json.loads(data_path.read_text(encoding="utf-8"))["generated"]["commit"]
        except (ValueError, KeyError, TypeError) as exc:
            problems.append(f"data.json has no readable generated.commit: {exc}")
        else:
            if commit != expected:
                problems.append(f"data.json generated.commit {commit} != source commit {expected}")
    return problems


def main(argv):
    if len(argv) != 3:
        print("usage: check_dashboard_build.py SITE_DIR EXPECTED_SHA", file=sys.stderr)
        return 2
    problems = check(Path(argv[1]), argv[2])
    for problem in problems:
        print(f"FAIL: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"DASHBOARD BUILD OK: {argv[1]} at {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
