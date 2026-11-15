"""Blind labels, report scrub and diff scrub for the OCMA-8 comparison (PREREG.md, Measures and Order and blinding).

Usage:
  exp_scrub.py labels <task number>
      prints `A=<p|q> B=<p|q>`, drawn with random.Random(2026111500 + task number).
  exp_scrub.py reports <task number> <arm A report dir> <arm B report dir> <agent ids file> <out dir>
      each report dir holds one file per report, named `<step>_<role>.md`. Writes `reports_t<n>.txt` (the
      EXTRACT slot: every report whole, under an opaque id, label p then q, shuffled within a label) and
      `key_reports_t<n>.csv` (id, label, arm, role, file). Agent ids and role words become `AGENT`, an arm
      worktree name becomes `TREE`. No report is cut.
  exp_scrub.py diff <diff in> <agent ids file> <diff out> <log out>
      copies the diff with each agent id replaced, the token alone, by `AGENT`; logs every added line that holds
      a role word (left as written: role words are common identifiers).

The agent ids file lists the harness's ids of every agent of both cells of the task, one per line.
"""
import csv
import random
import re
import sys
from pathlib import Path

SEED = 2026111500
CLASSES = ("wrong-behaviour", "wrong-pointer", "wrong-value", "meaning-change", "scope", "incomplete", "style")
ROLE = re.compile(r"\b(helpers?|workers?|writers?|keepers?|checkers?|critics?|reviewers?|orchestrators?|formations?|teams?)\b",
                  re.IGNORECASE)
TREE = re.compile(r"\bexp_t\d+_(?:A|B[12]?)\b")


def labels(n):
    """Label of each arm for task n."""
    a = random.Random(SEED + n).choice("pq")
    return {"A": a, "B": "q" if a == "p" else "p"}


def agent_ids(path):
    ids = [ln.strip() for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert ids, "the agent ids file names no agent"
    assert all(re.fullmatch(r"[0-9a-f]{8,}", i) for i in ids), "an agent id is hex, 8 characters or more"
    return re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(ids, key=len, reverse=True))) + r")\b")


def scrub_reports(n, dir_a, dir_b, ids_file, out):
    ids, lab, out = agent_ids(ids_file), labels(n), Path(out)
    rng = random.Random(f"reports-{n}")
    by_label = {}
    for arm, d in (("A", dir_a), ("B", dir_b)):
        files = sorted(Path(d).glob("*.md"))
        assert files, f"arm {arm}: no report in {d}"
        rng.shuffle(files)
        by_label[lab[arm]] = [(arm, f) for f in files]
    text, key = [], []
    for label in "pq":
        for k, (arm, f) in enumerate(by_label[label], 1):
            rid = f"{label}-R{k:02d}"
            body = f.read_text(encoding="utf-8", errors="replace")
            body = ROLE.sub("AGENT", TREE.sub("TREE", ids.sub("AGENT", body)))
            text.append(f"=== report {rid} (attempt {label}) ===\n{body.rstrip()}\n")
            key.append((rid, label, arm, f.stem.split("_", 1)[-1], f.name))
    out.mkdir(parents=True, exist_ok=True)
    (out / f"reports_t{n}.txt").write_text("\n".join(text), encoding="utf-8", newline="\n")
    with open(out / f"key_reports_t{n}.csv", "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([("report_id", "label", "arm", "role", "file"), *key])
    print(f"reports: {len(key)} written whole (p {len(by_label['p'])}, q {len(by_label['q'])})")


def scrub_diff(src, ids_file, dst, log):
    ids = agent_ids(ids_file)
    raw = Path(src).read_bytes()
    text = raw.decode("utf-8", errors="surrogateescape")
    new, n_ids = ids.subn("AGENT", text)
    Path(dst).write_bytes(new.encode("utf-8", errors="surrogateescape"))
    leaks = [ln for ln in new.splitlines() if ln.startswith("+") and not ln.startswith("+++") and ROLE.search(ln)]
    Path(log).write_text(f"agent ids replaced: {n_ids}\nadded lines holding a role word: {len(leaks)}\n"
                         + "".join(f"  {ln}\n" for ln in leaks), encoding="utf-8", newline="\n")
    print(f"diff: {n_ids} agent ids replaced, {len(leaks)} added lines hold a role word (logged)")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["labels"] and len(a) == 2:
        print(" ".join(f"{k}={v}" for k, v in labels(int(a[1])).items()))
    elif a[:1] == ["reports"] and len(a) == 6:
        scrub_reports(int(a[1]), *a[2:])
    elif a[:1] == ["diff"] and len(a) == 5:
        scrub_diff(*a[1:])
    else:
        sys.exit(__doc__)
