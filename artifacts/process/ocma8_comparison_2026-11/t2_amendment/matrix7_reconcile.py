"""Matrix 7: every logged run against the expectation fixed in matrix7_run.py, read from the run log alone.

Usage: python matrix7_reconcile.py <runs.jsonl> <t2_differential_r3.py>
Independent of the summary matrix7_run.py writes. Checks: one row per (tree, seed), 59 trees x 5 seeds (the
baseline against itself and 58 control trees: 28 correct, 29 wrong, 1 unscored); every run rc 0, no WARN, all
three DIFF lines; at each seed
every tree saw the same input counts, and those equal the counts generate() gives at that seed; then the
expectation per tree with no run excluded. Exit 1 when anything is not met.
"""
import collections
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv):
    m7 = load(HERE / "matrix7_run.py", "matrix7_run")
    gen = load(argv[1], "t2gen")
    kind = {m7.BASE: "base"}
    kind.update({t: "correct" for t in m7.CORRECT})
    kind.update({t: "wrong" for t in m7.WRONG})
    kind.update({t: "none" for t in m7.NONE})
    rows = [json.loads(line) for line in pathlib.Path(argv[0]).read_text(encoding="utf-8").splitlines()]
    by_key = collections.defaultdict(list)
    for row in rows:
        by_key[(row["tree"], row["seed"])].append(row)
    problems = []
    expected_keys = {(t, s) for t in kind for s in m7.SEEDS}
    if set(by_key) != expected_keys:
        problems.append(f"keys: missing {len(expected_keys - set(by_key))}, unexpected {len(set(by_key) - expected_keys)}")
    problems += [f"duplicate run {k}" for k, v in by_key.items() if len(v) != 1]
    run = {k: v[0] for k, v in by_key.items()}
    for key, row in sorted(run.items()):
        if row["rc"] != 0 or row["warn"] != 0 or set(row["found"]) != {"preserved", "corrected", "exploratory"}:
            problems.append(f"run not clean {key}: rc {row['rc']} warn {row['warn']} modes {sorted(row['found'])}")
    print("seed | preserved inputs | corrected inputs | exploratory inputs | trees with these counts | generate() counts")
    for seed in m7.SEEDS:
        counts = collections.Counter(tuple(run[(t, seed)]["found"][m][0] for m in ("preserved", "corrected", "exploratory"))
                                     for t in kind if (t, seed) in run)
        made = collections.Counter(rec["bucket"] if rec["bucket"] == "exploratory" else rec["mode"]
                                   for rec in gen.generate(seed, gen.DEFAULT_ROWS))
        made = (made["preserved"], made["corrected"], made["exploratory"])
        for c, n in counts.items():
            print(f"{seed} | {c[0]} | {c[1]} | {c[2]} | {n} | {made}")
        if len(counts) != 1 or next(iter(counts)) != made:
            problems.append(f"input counts at seed {seed}: runs {dict(counts)}, generate() {made}")
    print("\ntree | kind | scored mismatches (preserved+corrected) per seed | exploratory mismatches per seed | met")
    met_by_kind = collections.Counter()
    n_by_kind = collections.Counter()
    for tree, k in kind.items():
        runs = [run[(tree, s)] for s in m7.SEEDS if (tree, s) in run]
        pres = [r["found"]["preserved"][1] for r in runs]
        scored = [r["found"]["preserved"][1] + r["found"]["corrected"][1] for r in runs]
        expl = [r["found"]["exploratory"][1] for r in runs]
        met = len(runs) == len(m7.SEEDS) and {"base": all(p == 0 for p in pres), "correct": all(s == 0 for s in scored),
                                              "wrong": all(s > 0 for s in scored), "none": True}[k]
        n_by_kind[k] += 1
        met_by_kind[k] += met
        if not met:
            problems.append(f"expectation not met: {tree} ({k}) scored {scored}")
        shown = pres if k == "base" else scored
        print(f"{tree.split('_work/')[-1].split('scratchpad/')[-1]} | {k} | {shown} | {expl} | {met}")
    print(f"\nRUNS {len(rows)} of {len(expected_keys)}")
    for k in ("base", "correct", "wrong", "none"):
        note = " (reported only, not scored)" if k == "none" else " (preserved mode only)" if k == "base" else ""
        print(f"KIND {k}: {met_by_kind[k]} of {n_by_kind[k]} met{note}")
    print("PROBLEMS " + (str(len(problems)) if problems else "0"))
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
