"""Score structural adjudications against the anchor key and against each other.

Usage: python score_adjudication.py <key file> <adjudication.md> [<adjudication.md> ...]

Reads each report's table rows `| kNN | VERDICT | ...`. Prints per adjudicator the agreement with the anchors
(UNRESOLVED counted as not agreeing), every disagreement with its source tree, and for each pair of
adjudicators the raw agreement and Cohen's kappa over the three verdicts.
"""
import json
import pathlib
import re
import sys
from collections import Counter

ROW = re.compile(r"^\s*\|?\s*(k\d\d)\s*\|\s*(PASS|FAIL|UNRESOLVED)\s*\|", re.M)


def kappa(a, b, labels):
    n = len(labels)
    agree = sum(a[k] == b[k] for k in labels) / n
    ca, cb = Counter(a[k] for k in labels), Counter(b[k] for k in labels)
    chance = sum(ca[v] * cb[v] for v in set(ca) | set(cb)) / (n * n)
    return agree, (agree - chance) / (1 - chance) if chance < 1 else float("nan")


def main(argv):
    key = {t["label"]: t for t in json.loads(pathlib.Path(argv[0]).read_text(encoding="utf-8"))["trees"]}
    labels = sorted(key)
    reports = {}
    for path in argv[1:]:
        found = dict(ROW.findall(pathlib.Path(path).read_text(encoding="utf-8")))
        name = pathlib.Path(path).parent.name
        missing = [k for k in labels if k not in found]
        if missing:
            print(f"{name}: no verdict for {missing}")
            return 1
        reports[name] = found
        hits = sum(found[k] == key[k]["anchor"] for k in labels)
        counts = Counter(found.values())
        print(f"{name}: agrees with the anchor on {hits} of {len(labels)}; verdicts {dict(sorted(counts.items()))}")
        for k in labels:
            if found[k] != key[k]["anchor"]:
                print(f"  {k} anchor {key[k]['anchor']} adjudicated {found[k]}: {key[k]['source']} ({key[k]['origin']})")
    names = sorted(reports)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            agree, k = kappa(reports[a], reports[b], labels)
            differ = [x for x in labels if reports[a][x] != reports[b][x]]
            print(f"{a} vs {b}: agreement {agree:.3f}, Cohen's kappa {k:.3f}, n={len(labels)}, differ on {differ or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
