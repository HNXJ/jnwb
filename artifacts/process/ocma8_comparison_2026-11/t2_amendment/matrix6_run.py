"""Generator revision 2 with the wide-table family: every control tree at five seeds, three runs at a time.

Usage: python t2_matrix6.py <out file>
Runs t2_differential_r2.py <tree> <base> --seed S for each tree and seed; writes one line per run and a
per-tree summary; checks each tree's expectation (behaviour-correct: 0 and 0 at every seed; wrong: more than 0
at every seed). Records `git status --porcelain` hashes of base and the corrected reference before and after.
"""
import concurrent.futures
import hashlib
import re
import subprocess
import sys
import time

D = "D:/repos/_work/exp_t2diff/t2_differential_r2.py"
W = "D:/repos/_work"
V = "D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev_t2c/trees"
BASE = f"{W}/exp_prereq/t2/base"
SEEDS = (2026111600, 1, 2, 3, 4)
CORRECT = ([f"{W}/exp_t2beh/pos2"] + [f"{W}/exp_t2ctl/{t}" for t in ("v1", "v2", "v3", "a1", "u1", "u2", "u3")]
           + [f"{V}/{t}" for t in ("v_cls", "v_gen", "v_partial", "v_map", "v_split2", "v_scan", "v_wrap",
                                   "u_disp", "u_hidden_call", "u_const2", "u_allhidden")])
WRONG = ([f"{W}/exp_prereq/t2/pos"] + [f"{W}/exp_t2cov/m{i}" for i in (10, 11, 12, 13)]
         + [f"{W}/exp_t2ctl/{t}" for t in ("s_tab", "s_hdr", "s_led", "s_ledsingle", "t1")]
         + [f"{W}/exp_t2ctl/M{i}" for i in range(1, 10)]
         + [f"{V}/{t}" for t in ("w_maxsplit", "w_ws", "w_bq")])
UNOBSERVED = [f"{V}/w_hdr2"]  # no public-entry difference found in 42 targeted probes; reported, no expectation
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
    found = {mode: (int(n), int(m)) for mode, n, m in LINE.findall(proc.stdout)}
    warn = sum(line.startswith("WARN ") for line in proc.stdout.splitlines())
    return tree, seed, proc.returncode, found, warn, round(time.time() - t0)


def main(argv):
    before = {t: porcelain(t) for t in (BASE, CORRECT[0])}
    trees = [BASE] + CORRECT + WRONG + UNOBSERVED
    jobs = [(t, s) for t in trees for s in SEEDS]
    results = {}
    with concurrent.futures.ThreadPoolExecutor(3) as pool, open(argv[0], "w", encoding="utf-8", newline="\n") as out:
        out.write("tree | seed | preserved mism/inputs | corrected mism/inputs | exploratory mism/inputs | WARN | s | rc\n")
        for tree, seed, rc, found, warn, secs in pool.map(one, jobs):
            results[(tree, seed)] = (rc, found, warn)
            cells = " | ".join(f"{found.get(m, ('?', '?'))[1]}/{found.get(m, ('?', '?'))[0]}"
                               for m in ("preserved", "corrected", "exploratory"))
            out.write(f"{tree} | {seed} | {cells} | {warn} | {secs} | {rc}\n")
            out.flush()
        bad = 0
        for tree in trees:
            runs = [results[(tree, s)] for s in SEEDS]
            ok_run = all(rc == 0 and set(f) == {"preserved", "corrected", "exploratory"} and w == 0 for rc, f, w in runs)
            scored = [f["preserved"][1] + f["corrected"][1] if "corrected" in f else -1 for _, f, _ in runs]
            kind = ("base" if tree == BASE else "correct" if tree in CORRECT else "wrong" if tree in WRONG
                    else "unobserved")
            met = {"base": all(f.get("preserved", (0, 1))[1] == 0 for _, f, _ in runs),
                   "correct": all(s == 0 for s in scored), "wrong": all(s > 0 for s in scored),
                   "unobserved": True}[kind] and ok_run
            bad += not met
            out.write(f"SUMMARY {tree} | {kind} | scored mismatches min {min(scored)} max {max(scored)} | "
                      f"runs ok {ok_run} | expectation met {met}\n")
        after = {t: porcelain(t) for t in before}
        out.write(f"PORCELAIN {before} -> {after}\n")
        out.write(f"TOTAL trees={len(trees)} runs={len(jobs)} expectations not met={bad}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
