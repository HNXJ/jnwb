"""Generator revision 3: every control tree at five seeds, ten runs at a time, resumable.

Usage: python matrix7_run.py <out file>
Runs t2_differential_r3.py <tree> <base> --seed S for each tree and seed. Each finished run is appended to
<out file>.runs.jsonl; a rerun skips the runs already there. When all runs exist it writes <out file>: one line
per run and a per-tree summary against the expectation fixed here before the run (behaviour-correct: 0 scored
mismatches at every seed; wrong: more than 0 at every seed; none: reported only). `git status --porcelain`
hashes of base and the corrected reference are taken before and after.
"""
import concurrent.futures
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time

D = "D:/repos/_work/exp_t2diff/t2_differential_r3.py"
W = "D:/repos/_work"
SCR = "D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad"
V3 = f"{SCR}/rev_t2c/trees"   # review 3's trees
V4 = f"{SCR}/rev4/trees"      # review 4's trees
N = f"{W}/exp_t2val2"         # validation 2's trees
BASE = f"{W}/exp_prereq/t2/base"
SEEDS = (2026111600, 1, 2, 3, 4)
CORRECT = ([f"{W}/exp_t2beh/pos2"] + [f"{W}/exp_t2ctl/{t}" for t in ("v1", "v2", "v3", "a1", "u1", "u2", "u3")]
           + [f"{V3}/{t}" for t in ("v_cls", "v_gen", "v_partial", "v_map", "v_split2", "v_scan", "v_wrap",
                                    "u_disp", "u_hidden_call", "u_const2", "u_allhidden")]
           # validation 2 trees whose corrected test gave 6 passed
           + [f"{N}/{t}" for t in ("n1", "n2", "n3", "n4", "n5", "m1", "m2", "m3", "m5")])
WRONG = ([f"{W}/exp_prereq/t2/pos"] + [f"{W}/exp_t2cov/m{i}" for i in (10, 11, 12, 13)]
         + [f"{W}/exp_t2ctl/{t}" for t in ("s_tab", "s_hdr", "s_led", "s_ledsingle", "t1")]
         + [f"{W}/exp_t2ctl/M{i}" for i in range(1, 10)]
         + [f"{V3}/{t}" for t in ("w_maxsplit", "w_bq", "w_hdr2")]
         + [f"{V4}/{t}" for t in ("w_bsall", "w_collapse", "w_cap2", "w_merge1")]
         # validation 2 trees that leave escapes unhonoured at some site (corrected test failed)
         + [f"{N}/{t}" for t in ("m4", "m6", "m7")])
NONE = [f"{V3}/w_ws"]  # strip(" \t") for strip(): only the whitespace-padding family saw it, now exploratory (F8)
LINE = re.compile(r"^DIFF (preserved|corrected|exploratory) (?:readers=\d+ )?inputs=(\d+) mismatches=(\d+)", re.M)


def porcelain(tree):
    out = subprocess.run(["git", "-C", tree, "status", "--porcelain"], capture_output=True,
                         stdin=subprocess.DEVNULL).stdout
    return hashlib.sha256(out).hexdigest()[:12]


def one(job):
    tree, seed = job
    t0 = time.time()
    proc = subprocess.run([sys.executable, D, tree, BASE, "--seed", str(seed)], capture_output=True,
                          stdin=subprocess.DEVNULL, text=True, encoding="utf-8")
    found = {mode: [int(n), int(m)] for mode, n, m in LINE.findall(proc.stdout)}
    warn = sum(line.startswith("WARN ") for line in proc.stdout.splitlines())
    return {"tree": tree, "seed": seed, "rc": proc.returncode, "found": found, "warn": warn,
            "s": round(time.time() - t0)}


def main(argv):
    out_path = pathlib.Path(argv[0])
    runs_path = pathlib.Path(argv[0] + ".runs.jsonl")
    trees = [BASE] + CORRECT + WRONG + NONE
    assert len(set(trees)) == len(trees)
    done = {}
    if runs_path.exists():
        for line in runs_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[(row["tree"], row["seed"])] = row
    jobs = [(t, s) for t in trees for s in SEEDS if (t, s) not in done]
    before = {t: porcelain(t) for t in (BASE, CORRECT[0])}
    with concurrent.futures.ThreadPoolExecutor(10) as pool, open(runs_path, "a", encoding="utf-8", newline="\n") as log:
        for row in pool.map(one, jobs):
            done[(row["tree"], row["seed"])] = row
            log.write(json.dumps(row) + "\n")
            log.flush()
    after = {t: porcelain(t) for t in before}
    bad = 0
    with open(out_path, "w", encoding="utf-8", newline="\n") as out:
        out.write("tree | seed | preserved mism/inputs | corrected mism/inputs | exploratory mism/inputs | WARN | s | rc\n")
        for tree in trees:
            for seed in SEEDS:
                row = done[(tree, seed)]
                cells = " | ".join(f"{row['found'].get(m, ['?', '?'])[1]}/{row['found'].get(m, ['?', '?'])[0]}"
                                   for m in ("preserved", "corrected", "exploratory"))
                out.write(f"{tree} | {seed} | {cells} | {row['warn']} | {row['s']} | {row['rc']}\n")
        for tree in trees:
            runs = [done[(tree, s)] for s in SEEDS]
            ok_run = all(r["rc"] == 0 and set(r["found"]) == {"preserved", "corrected", "exploratory"}
                         and r["warn"] == 0 for r in runs)
            scored = [r["found"]["preserved"][1] + r["found"]["corrected"][1] if "corrected" in r["found"] else -1
                      for r in runs]
            kind = ("base" if tree == BASE else "correct" if tree in CORRECT else "wrong" if tree in WRONG else "none")
            met = {"base": all(r["found"].get("preserved", [0, 1])[1] == 0 for r in runs),
                   "correct": all(s == 0 for s in scored), "wrong": all(s > 0 for s in scored),
                   "none": True}[kind] and ok_run
            bad += not met
            out.write(f"SUMMARY {tree} | {kind} | scored mismatches min {min(scored)} max {max(scored)} | "
                      f"runs ok {ok_run} | expectation met {met}\n")
        out.write(f"PORCELAIN {before} -> {after} (the 'before' of a resumed run is taken at the resume)\n")
        out.write(f"TOTAL trees={len(trees)} runs={len(trees) * len(SEEDS)} expectations not met={bad}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
