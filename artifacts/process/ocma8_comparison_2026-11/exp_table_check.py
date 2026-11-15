"""Check an adjudicator's defect tables against the candidates (PREREG.md, Measures: Adjudicator).

Usage: exp_table_check.py <candidates file> <adjudicator output>

Prints `TABLE OK ...` and exits 0, or prints every reason after `REFUSED` and exits 1. Refuses when: a ROW line
is malformed; a label, yes/no, class or source is unknown; a row number repeats within a label; a row holds no
candidate, a candidate of the other label or an unknown one; a candidate is in no row or in two; a row real on a
snapshot has source `none` or a row real on neither has another source; a row real only on the final snapshot
has a source other than `arm`.
"""
import collections
import sys
from pathlib import Path

from exp_scrub import CLASSES

SOURCES = ("task-text", "baseline-outside", "baseline-inside", "arm", "none")


def check(cand_path, table_path):
    cands = {}
    for ln in Path(cand_path).read_text(encoding="utf-8").splitlines():
        if ln.startswith("CAND"):
            _, cid, label = [p.strip() for p in ln.split(" | ", 3)[:3]]
            cands[cid] = label
    why = [] if cands else ["the candidates file holds no candidate"]
    lines = [ln.strip() for ln in Path(table_path).read_text(encoding="utf-8", errors="replace").splitlines()]
    rows = [ln for ln in lines if ln.startswith("ROW")]
    used, numbers = collections.Counter(), collections.Counter()
    for ln in rows:
        p = [x.strip() for x in ln.split(" | ", 8)]
        if len(p) != 9 or not p[8]:
            why.append(f"malformed: {ln!r}")
            continue
        _, label, num, pre, fin, cls, source, ids, _ = p
        tag = f"row {label}/{num}"
        if label not in ("p", "q") or pre not in ("yes", "no") or fin not in ("yes", "no"):
            why.append(f"{tag}: label or yes/no value unknown")
            continue
        numbers[(label, num)] += 1
        if cls not in CLASSES:
            why.append(f"{tag}: class {cls!r} unknown")
        if source not in SOURCES:
            why.append(f"{tag}: source {source!r} unknown")
        real = pre == "yes" or fin == "yes"
        if real == (source == "none"):
            why.append(f"{tag}: real on {'a snapshot' if real else 'neither snapshot'} with source {source!r}")
        if pre == "no" and fin == "yes" and source != "arm":
            why.append(f"{tag}: real only on the final snapshot, source must be arm, is {source!r}")
        mine = [c.strip() for c in ids.split(",") if c.strip()]
        if not mine:
            why.append(f"{tag}: holds no candidate")
        for c in mine:
            used[c] += 1
            if cands.get(c) != label:
                why.append(f"{tag}: candidate {c!r} is unknown or of the other attempt")
    why += [f"row number {k[0]}/{k[1]} used {v} times" for k, v in numbers.items() if v > 1]
    why += [f"candidate {c} is in {used[c]} rows" for c in cands if used[c] != 1]
    notes = sum(ln.startswith("NOTE") for ln in lines)  # exploratory, outside the table: counted, never scored
    return why, len(rows), len(cands), notes


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    reasons, n_rows, n_cands, n_notes = check(*sys.argv[1:])
    if reasons:
        print("REFUSED")
        print("\n".join(f"  {r}" for r in reasons))
        sys.exit(1)
    print(f"TABLE OK: {n_rows} rows hold {n_cands} candidates, each once; {n_notes} NOTE lines outside the table")
