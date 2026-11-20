"""Compare per-test outcomes of two `pytest -v -n auto` logs.

usage: outcome_diff.py <log a> <log b>
Reads lines "[gwN] [ NN%] OUTCOME test id" and prints each test whose outcome differs or that only
one log holds, then the outcome counts of each log.
"""
import collections
import re
import sys

LINE = re.compile(r"\[gw\d+\] \[\s*\d+%\] (PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR) (\S+)")


def outcomes(path):
    got = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        m = LINE.search(line)
        if m:
            got[m.group(2)] = m.group(1)
    return got


def main(argv):
    a, b = outcomes(argv[1]), outcomes(argv[2])
    if not a or not b:
        print(f"unreadable: {len(a)} outcome(s) in a, {len(b)} in b")
        return 2
    by_file = collections.Counter()
    shown = 0
    for test in sorted(a.keys() | b.keys()):
        left, right = a.get(test, "absent"), b.get(test, "absent")
        if left != right:
            by_file[(test.split("::")[0], left, right)] += 1
            if shown < 40 and "absent" not in (left, right):
                print(f"{left} -> {right}  {test}")
                shown += 1
    for (name, left, right), count in sorted(by_file.items()):
        print(f"{count:4d}  {left} -> {right}  {name}")
    print("a:", dict(collections.Counter(a.values())))
    print("b:", dict(collections.Counter(b.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
