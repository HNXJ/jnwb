"""Frozen outcome predicates of the OCMA-8 pilot (jnwb 17-103). Usage: pilot_predicates.py <result tree> <baseline sha>

Mechanical part of the evaluation; written before either arm ran. Prints PASS/FAIL per predicate and a summary.
P1 root-allowlist pointer, P2 artifacts folders named, P2b no absent entry, P3 20% growth limit stated,
C1 scope, C4 no new unresolved path pointer (pilot_key.py), SIZE diff lines.
"""
import re
import subprocess
import sys
from pathlib import Path

tree, base = Path(sys.argv[1]), sys.argv[2]
KEY = Path(__file__).with_name("pilot_key.py")


def git(*a):
    return subprocess.run(["git", "-C", str(tree), *a], capture_output=True, text=True, encoding="utf-8").stdout


text = (tree / ".github" / "CONTRIBUTING.md").read_text(encoding="utf-8")
lines = text.splitlines()
res = {}

# P1: every line naming ALLOWED_ROOT_DIRS names scripts/gates/boundary.py, and the symbol is defined there.
hits = [l for l in lines if "ALLOWED_ROOT_DIRS" in l]
defined = "ALLOWED_ROOT_DIRS =" in (tree / "scripts" / "gates" / "boundary.py").read_text(encoding="utf-8")
res["P1"] = (bool(hits) and all("gates/boundary.py" in l for l in hits) and defined, f"{len(hits)} line(s) name the symbol")

# P2 / P2b: the artifacts policy section names every tracked top-level folder of artifacts/ at the baseline.
folders = [p.split("/")[1] for p in git("ls-tree", "-d", "--name-only", base, "artifacts/").split()]
assert len(folders) >= 3, "baseline must list artifacts folders"
m = re.search(r"^### `artifacts/` Policy\n(.*?)(?=^#{1,3} )", text, re.S | re.M)
section = m.group(1) if m else ""
missing = [f for f in folders if f"{f}/" not in section]
res["P2"] = (bool(section) and not missing, f"{len(folders) - len(missing)} of {len(folders)} folders named; missing {missing}")
entries = re.findall(r"^[├└]── (\S+)", section, re.M)
absent = [e for e in entries if e != "scratch/" and not (tree / "artifacts" / e.rstrip("/")).exists()]
res["P2b"] = (bool(entries) and not absent, f"{len(entries)} tree entries; absent {absent}")

# P3: the 20% growth limit is stated near the peak-memory sentence; the 25% margin stays.
idx = [i for i, l in enumerate(lines) if "PEAK_THRESHOLD_MIB" in l]
near = "\n".join(lines[max(0, idx[0] - 8): idx[0] + 12]) if idx else ""
has20 = bool(re.search(r"\b20\s?%", near)) or "PEAK_MEMORY_GROWTH_FRACTION" in near
res["P3"] = (bool(idx) and has20 and "25%" in near, f"20% near: {has20}; 25% kept: {'25%' in near}")

# C1: only .github/CONTRIBUTING.md differs from the baseline (committed or not).
changed = sorted(set(git("diff", "--name-only", base).split()) | set(git("ls-files", "--others", "--exclude-standard").split()))
res["C1"] = (changed == [".github/CONTRIBUTING.md"], f"changed {changed}")

# C4: no path pointer unresolved now that resolved at the baseline.
def unresolved(doc_text):
    tmp = tree / "_temp_pilot_doc.md"
    tmp.write_text(doc_text, encoding="utf-8")
    try:
        out = subprocess.run([sys.executable, str(KEY), str(tree), str(tmp)], capture_output=True, text=True,
                             encoding="utf-8").stdout
    finally:
        tmp.unlink()
    return sorted(re.findall(r"`([^`]+)`", l)[0] for l in out.splitlines() if l.startswith("UNRESOLVED"))

before = unresolved(git("show", f"{base}:.github/CONTRIBUTING.md"))
after = unresolved(text)
new = sorted(set(after) - set(before))
res["C4"] = (not new, f"unresolved before {len(before)}, after {len(after)}; new {new}")

stat = git("diff", "--numstat", base, "--", ".github/CONTRIBUTING.md").split()
for k, (ok, why) in res.items():
    print(f"{'PASS' if ok else 'FAIL'} {k}: {why}")
print(f"SIZE added={stat[0] if stat else 0} removed={stat[1] if stat else 0}")
print(f"SUMMARY primary {sum(res[k][0] for k in ('P1', 'P2', 'P3'))}/3; constraints "
      f"{sum(res[k][0] for k in ('P2b', 'C1', 'C4'))}/3")
