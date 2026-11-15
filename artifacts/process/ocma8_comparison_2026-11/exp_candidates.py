"""Pool the evaluators' defects and the extractor's claims into blind candidates (PREREG.md, Measures: Candidates).

Usage: exp_candidates.py <task number> <evaluator 1 output> <evaluator 2 output> <extractor output> <report key csv> <out dir>

Pass `-` for an evaluator that returned no report (it then adds no candidate; the key records it).
Writes `candidates_t<n>.txt`: `CAND | <id> | <p|q> | <file> | "<quoted>" | <sentence>`, p then q, shuffled within
a label, with no source, class or snapshot; and `key_candidates_t<n>.csv` (id, label, source, report id,
snapshots, class), which no judge sees. Refuses (exit 1, nothing written) when an output's COUNT line disagrees
with its parsed lines, a line is malformed, a report of the key has neither a CLAIM nor a NONE line, or a CLAIM
names an unknown report or the other label. One evaluator's defect listed on both snapshots is one candidate.
An arm worktree name in a candidate becomes `TREE`; a role word is left and logged.
"""
import csv
import random
import sys
from pathlib import Path

from exp_scrub import CLASSES, ROLE, TREE


class Refused(Exception):
    pass


def body_lines(path, heads):
    lines = [ln.strip() for ln in Path(path).read_text(encoding="utf-8", errors="replace").splitlines()]
    return [ln for ln in lines if ln.split(" | ", 1)[0].strip() in heads]


def count_line(lines, n, name):
    counts = [ln for ln in lines if ln.startswith("COUNT")]
    if len(counts) != 1 or counts[0].split("|")[-1].strip() != str(n):
        raise Refused(f"{name}: COUNT line {counts} against {n} parsed lines")


def unquote(s, name):
    s = s.strip()
    if len(s) < 2 or s[0] != '"' or s[-1] != '"':
        raise Refused(f"{name}: quoted field not in double quotes: {s!r}")
    return s[1:-1]


def parse_evaluator(path, name):
    """{(label, file, quoted, sentence): {"snaps": set, "class": str}} from DEFECT lines."""
    lines = body_lines(path, {"DEFECT", "COUNT", "GUESS"})
    found = {}
    defects = [ln for ln in lines if ln.startswith("DEFECT")]
    for ln in defects:
        head = ln.split(" | ", 4)
        tail = head[-1].rsplit(" | ", 2) if len(head) == 5 else []
        if len(tail) != 3:
            raise Refused(f"{name}: malformed line: {ln!r}")
        _, label, snap, file, _ = head
        quoted, cls, sentence = unquote(tail[0], name), tail[1].strip(), tail[2].strip()
        if label not in "pq" or len(label) != 1 or snap not in ("pre", "final") or cls not in CLASSES or not sentence:
            raise Refused(f"{name}: bad label, snapshot, class or sentence: {ln!r}")
        item = found.setdefault((label, file.strip(), quoted, sentence), {"snaps": set(), "class": cls})
        item["snaps"].add(snap)
    count_line(lines, len(defects), name)
    if sum(ln.startswith("GUESS") for ln in lines) != 1:
        raise Refused(f"{name}: needs exactly one GUESS line")
    return found


def parse_extractor(path, key):
    lines = body_lines(path, {"CLAIM", "NONE", "COUNT"})
    claims, seen = [], set()
    for ln in lines:
        if ln.startswith("NONE"):
            seen.add(ln.split("|", 1)[1].strip())
        elif ln.startswith("CLAIM"):
            head = ln.split(" | ", 4)
            tail = head[-1].rsplit(" | ", 1) if len(head) == 5 else []
            if len(tail) != 2 or not tail[1].strip():
                raise Refused(f"extractor: malformed line: {ln!r}")
            _, rid, label, file, _ = head
            if key.get(rid.strip()) != label.strip():
                raise Refused(f"extractor: report {rid!r} is unknown or not of attempt {label!r}")
            seen.add(rid.strip())
            claims.append((label.strip(), file.strip(), unquote(tail[0], "extractor"), tail[1].strip(), rid.strip()))
    count_line(lines, len(claims), "extractor")
    if seen != set(key):
        raise Refused(f"extractor: reports without a CLAIM or NONE line, or unknown: {sorted(seen ^ set(key))}")
    return claims


def main(n, ev1, ev2, ext, key_csv, out):
    with open(key_csv, newline="", encoding="utf-8") as fh:
        key = {r["report_id"]: r["label"] for r in csv.DictReader(fh)}
    assert key, "the report key is empty"
    pool = []  # (label, file, quoted, sentence, source, report id, snapshots, class)
    for name, path in (("eval1", ev1), ("eval2", ev2)):
        if path == "-":
            print(f"{name}: no report, no candidate")
            continue
        for (label, file, quoted, sentence), item in parse_evaluator(path, name).items():
            pool.append((label, file, quoted, sentence, name, "", "+".join(sorted(item["snaps"])), item["class"]))
    for label, file, quoted, sentence, rid in parse_extractor(ext, key):
        pool.append((label, file, quoted, sentence, "report", rid, "", ""))
    rng = random.Random(f"candidates-{n}")
    rng.shuffle(pool)
    text, rows, leaks = [], [], []
    for label in "pq":
        mine = [c for c in pool if c[0] == label]
        for k, (_, file, quoted, sentence, source, rid, snaps, cls) in enumerate(mine, 1):
            cid = f"{label}-C{k:02d}"
            line = TREE.sub("TREE", f'CAND | {cid} | {label} | {file} | "{quoted}" | {sentence}')
            leaks += [f"{cid}: {line}"] if ROLE.search(sentence) else []
            text.append(line)
            rows.append((cid, label, source, rid, snaps, cls))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"candidates_t{n}.txt").write_text("\n".join(text) + "\n", encoding="utf-8", newline="\n")
    with open(out / f"key_candidates_t{n}.csv", "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([("candidate_id", "label", "source", "report_id", "snapshots", "class"), *rows])
    (out / f"leaks_candidates_t{n}.txt").write_text("".join(f"{ln}\n" for ln in leaks), encoding="utf-8", newline="\n")
    print(f"candidates: {len(rows)} (p {sum(r[1] == 'p' for r in rows)}, q {sum(r[1] == 'q' for r in rows)}); "
          f"sentences holding a role word: {len(leaks)} (logged)")


if __name__ == "__main__":
    if len(sys.argv) != 7:
        sys.exit(__doc__)
    try:
        main(int(sys.argv[1]), *sys.argv[2:])
    except Refused as e:
        sys.exit(f"REFUSED: {e}")
