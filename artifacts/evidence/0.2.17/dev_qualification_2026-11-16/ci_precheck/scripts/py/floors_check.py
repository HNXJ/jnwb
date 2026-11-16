"""Check the resolved lock argv[1] against the declared floors and write the pins to argv[2] (floors job)."""
import re
import sys

sys.path.insert(0, ".")
from scripts.release_gate import declared_dependency_floors  # noqa: E402

core = {n.lower(): f for extra, n, f in declared_dependency_floors() if not extra}
pins = {}
for line in open(sys.argv[1]):
    m = re.match(r"([A-Za-z0-9_.\-]+)==(\S+)", line)
    if m and m.group(1).lower() in core:
        pins[m.group(1).lower()] = m.group(2)
missing = sorted(set(core) - set(pins))
if missing:
    sys.exit(f"no resolved version for {missing}")
higher = []
with open(sys.argv[2], "w") as out:
    for name in sorted(pins):
        out.write(f"{name}=={pins[name]}\n")
        print(f"{name}: declared >={core[name]}, installed {pins[name]}")
        if pins[name] != core[name]:
            higher.append(name)
if higher:
    sys.exit(f"declared floors that do not hold: {higher}")
