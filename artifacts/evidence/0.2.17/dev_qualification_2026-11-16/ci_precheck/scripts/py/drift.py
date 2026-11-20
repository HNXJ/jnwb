"""Compare the packages a CI job log installed with a pip freeze or uv lock taken today.

usage: drift.py <job log> <freeze or lock file>
Reads every "Successfully installed ..." line of the log (a later line overrides an earlier one) and
every "name==version" line of the other file. Prints each package whose version differs or that only
one side holds, then the counts. Exit 0 when the sets agree, 1 otherwise.
"""
import re
import sys


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def from_log(path):
    got = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        at = line.find("Successfully installed ")
        if at < 0:
            continue
        for item in line[at + len("Successfully installed "):].split():
            name, _, version = item.rpartition("-")
            if name:
                got[norm(name)] = version
    return got


def from_freeze(path):
    got = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"([A-Za-z0-9_.\-]+)==(\S+)", line.strip())
        if m:
            got[norm(m.group(1))] = m.group(2)
    return got


def main(argv):
    then, now = from_log(argv[1]), from_freeze(argv[2])
    if not then or not now:
        print(f"unreadable: {len(then)} package(s) in the log, {len(now)} in the freeze")
        return 2
    skip = {"pip", "jnwb", "uv", "setuptools", "wheel"}
    changed = sorted(n for n in then.keys() & now.keys() if then[n] != now[n] and n not in skip)
    only_then = sorted(then.keys() - now.keys() - skip)
    only_now = sorted(now.keys() - then.keys() - skip)
    for n in changed:
        print(f"changed  {n}: {then[n]} -> {now[n]}")
    for n in only_then:
        print(f"log only {n}=={then[n]}")
    for n in only_now:
        print(f"now only {n}=={now[n]}")
    print(f"log {len(then)} package(s), now {len(now)}; changed {len(changed)}, "
          f"log only {len(only_then)}, now only {len(only_now)}")
    return 0 if not (changed or only_then or only_now) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
