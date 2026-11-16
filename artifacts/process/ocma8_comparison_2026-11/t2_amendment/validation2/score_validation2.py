"""Validation 2: score the 24 adjudications against the expected verdicts and the frozen stopping criteria.

Usage: python score_validation2.py <key.jsonl> <slot1 dir> <slot2 dir>

Expected verdicts are EXPECTED below, copied from validation2_controls.md (fixed before adjudication). The
verdict of a slot is the last `VERDICT:` line of <dir>/<label>_slot<k>.md. Tree verdict (protocol section 3):
both PASS -> PASS, both FAIL -> FAIL, otherwise AMBIGUOUS. Prints per-tree rows, the confusion matrices,
agreement, Cohen's kappa, the AMBIGUOUS count and stopping criteria 1 to 3 (4 and 5 are read from the reports).
"""
import collections
import json
import pathlib
import re
import sys

EXPECTED = {**{f"n{i}": "PASS" for i in range(1, 6)}, **{f"m{i}": "FAIL" for i in range(1, 8)}}
VERDICT = re.compile(r"^\s*VERDICT: (PASS|FAIL|UNRESOLVED)\s*$", re.M)


def verdict(path):
    if not path.exists():
        return "MISSING"
    found = VERDICT.findall(path.read_text(encoding="utf-8", errors="replace"))
    return found[-1] if found else "MISSING"


def kappa(pairs):
    n = len(pairs)
    cats = sorted({c for pair in pairs for c in pair})
    po = sum(a == b for a, b in pairs) / n
    pe = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n) for c in cats)
    return None if pe == 1 else (po - pe) / (1 - pe)


def main(argv):
    key_path, dir1, dir2 = (pathlib.Path(a) for a in argv)
    rows = [json.loads(line) for line in key_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    labels = collections.defaultdict(dict)
    for row in rows:
        labels[row["name"]][row["slot"]] = row["label"]
    assert set(labels) == set(EXPECTED), sorted(set(labels) ^ set(EXPECTED))
    print("tree | expected | slot 1 (label) | slot 2 (label) | tree verdict | as expected")
    tree, slots, pairs = {}, {1: [], 2: []}, []
    for name in sorted(EXPECTED):
        v1 = verdict(dir1 / f"{labels[name][1]}_slot1.md")
        v2 = verdict(dir2 / f"{labels[name][2]}_slot2.md")
        tree[name] = v1 if v1 == v2 and v1 in ("PASS", "FAIL") else "AMBIGUOUS"
        slots[1].append((EXPECTED[name], v1))
        slots[2].append((EXPECTED[name], v2))
        pairs.append((v1, v2))
        print(f"{name} | {EXPECTED[name]} | {v1} ({labels[name][1]}) | {v2} ({labels[name][2]}) | {tree[name]} | "
              f"{tree[name] == EXPECTED[name]}")
    print("\nconfusion, tree verdict (rows expected, columns PASS FAIL AMBIGUOUS)")
    for exp in ("PASS", "FAIL"):
        print(exp, [sum(EXPECTED[n] == exp and tree[n] == got for n in EXPECTED) for got in ("PASS", "FAIL", "AMBIGUOUS")])
    for k in (1, 2):
        print(f"confusion, slot {k} (rows expected, columns PASS FAIL UNRESOLVED MISSING)")
        for exp in ("PASS", "FAIL"):
            print(exp, [sum(e == exp and g == got for e, g in slots[k]) for got in ("PASS", "FAIL", "UNRESOLVED", "MISSING")])
    agree = sum(a == b for a, b in pairs)
    k = kappa(pairs)
    print(f"\nslot agreement {agree} of {len(pairs)}; Cohen's kappa {'undefined' if k is None else round(k, 3)}")
    n_amb = sum(v == "AMBIGUOUS" for v in tree.values())
    print(f"AMBIGUOUS trees {n_amb} of {len(tree)}")
    s1 = [n for n in EXPECTED if EXPECTED[n] == "FAIL" and tree[n] == "PASS"]
    s2 = [n for n in EXPECTED if EXPECTED[n] == "PASS" and tree[n] == "FAIL"]
    print(f"STOP 1 (expected FAIL judged PASS): {s1 or 'none'}")
    print(f"STOP 2 (expected PASS judged FAIL): {s2 or 'none'}")
    print(f"STOP 3 (more than 2 of 12 AMBIGUOUS): {n_amb > 2}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
