"""Showcase 2, per session: decode context (main 2 vs sequenced control) from xxxx responses.

Usage: python scripts/decode_s2.py SESSION_ID [N_PERM] [responsive|all]
("responsive" is the preregistered population; "all" is a post-hoc exploratory variant.)
Writes results/s2/sessions/<ses>.json. PREREGISTRATION.md fixes the estimand: accuracy at P4
minus accuracy at P3, features = counts of each included unit in four 50-ms bins 50-250 ms
after the onset, grouped nested CV with groups = stimulus block. N_PERM (default 1000)
block-level label permutations give the within-session null for P4 and P3.
"""
import os

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "1"

import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import warnings  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from glo_common import AREAS, RESULTS, SEED, receipt, sha256  # noqa: E402
import jnwb  # noqa: E402

MIN_UNITS = 20
N_SPLITS = 5


def feats(counts, lo_bin, n50):
    """(units, trials, 75) 10-ms counts -> (trials, units * n50) 50-ms counts from lo_bin."""
    c = counts[:, :, lo_bin:lo_bin + 5 * n50].astype(float)
    u, t, _ = c.shape
    c = c.reshape(u, t, n50, 5).sum(axis=3)
    return c.transpose(1, 0, 2).reshape(t, u * n50)


def decode(X, y, g, rng=SEED):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = jnwb.nested_cv_linear_svm(X, y, n_splits=N_SPLITS, rng=rng, groups=g)
    return {k: (float(r[k]) if k in ("accuracy", "f1", "auc", "majority_baseline_accuracy") else r[k])
            for k in ("accuracy", "f1", "auc", "majority_baseline_accuracy", "status", "cv_scheme", "seed")}


def block_perm(y, g, i):
    """Exchange context labels between whole blocks: one label per block, permuted globally."""
    blocks = np.unique(g)
    lab = np.array([y[g == b][0] for b in blocks])
    perm = jnwb.permute_labels(lab, scheme="global", rng=SEED + i)
    return perm[np.searchsorted(blocks, g)]


def main():
    ses = sys.argv[1]
    n_perm = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    population = sys.argv[3] if len(sys.argv) > 3 else "responsive"
    assert population in ("responsive", "all")
    t0 = time.time()
    d = RESULTS / "sessions" / ses
    meta = json.load(open(d / "session.json"))
    cond = pd.read_csv(d / "conditions.csv", keep_default_na=False)
    kept = cond[cond.excluded == ""].reset_index(drop=True)
    z = np.load(d / "counts.npz")
    assert np.array_equal(kept["seq"].to_numpy(), z["seq"])
    area = z["area"]
    pop = z["responsive"] if population == "responsive" else np.ones(len(area), bool)
    ctx, pat, blk = kept.context.to_numpy(), kept.pattern.to_numpy(), kept.block.to_numpy()
    sel = ((ctx == "main2") | (ctx == "seq")) & (pat == "xxxx")
    y = np.where(ctx[sel] == "main2", 1, 0)
    g = blk[sel]
    dsel = ((ctx == "main1") | (ctx == "main2")) & (pat == "xxxx")
    yd, gd = np.where(ctx[dsel] == "main2", 1, 0), blk[dsel]
    out = {"session": ses, "mouse": meta["subject_id"], "n_trials": {"main2": int(y.sum()), "seq": int((y == 0).sum())},
           "n_blocks": {"main2": int(len(np.unique(g[y == 1]))), "seq": int(len(np.unique(g[y == 0])))}, "areas": {}}
    perm_labels = [block_perm(y, g, i) for i in range(n_perm)]
    out["n_distinct_permutations"] = int(len({p.tobytes() for p in perm_labels}))
    for a in AREAS:
        m = (area == a) & pop
        rec = {"n_units": int(m.sum())}
        if m.sum() < MIN_UNITS:
            rec["status"] = "fewer_than_20_units"
            out["areas"][a] = rec
            continue
        X4 = feats(z["p4"][m][:, sel], 30, 4)
        X3 = feats(z["p3"][m][:, sel], 30, 4)
        rec["P4"] = decode(X4, y, g)
        rec["P3"] = decode(X3, y, g)
        rec["estimand_A4_minus_A3"] = rec["P4"]["accuracy"] - rec["P3"]["accuracy"]
        null4 = np.array([decode(X4, yp, g)["accuracy"] for yp in perm_labels])
        null3 = np.array([decode(X3, yp, g)["accuracy"] for yp in perm_labels])
        nd = null4 - null3
        rec["null"] = {"n": n_perm, "p_P4": float((1 + np.sum(null4 >= rec["P4"]["accuracy"] - 1e-12)) / (1 + n_perm)),
                       "p_P3": float((1 + np.sum(null3 >= rec["P3"]["accuracy"] - 1e-12)) / (1 + n_perm)),
                       "p_diff": float((1 + np.sum(nd >= rec["estimand_A4_minus_A3"] - 1e-12)) / (1 + n_perm)),
                       "null_P4_mean": float(null4.mean()), "null_P3_mean": float(null3.mean())}
        # Exploratory controls (no null).
        Xd = feats(z["p4"][m][:, dsel], 30, 4)
        rec["expl_drift_main1_vs_main2_P4"] = decode(Xd, yd, gd)
        rec["expl_gain_removed_P4"] = decode(X4 - X4.mean(axis=1, keepdims=True), y, g)
        rng = np.random.default_rng(SEED)
        u4 = z["p4"][m][:, sel].astype(float)
        shuf = np.empty_like(u4)
        for t in range(u4.shape[1]):
            shuf[:, t] = u4[rng.permutation(u4.shape[0]), t]
        rec["expl_unit_shuffled_P4"] = decode(feats(shuf, 30, 4), y, g)
        rec["expl_time_resolved"] = {e: [decode(feats(z[e][m][:, sel], 25 + 5 * k, 1), y, g)["accuracy"] for k in range(10)]
                                     for e in ("p3", "p4")}
        # Exploratory geometry: correlation RDM of condition-mean population vectors.
        r3 = z["p3"][m][:, :, 30:50].sum(axis=2) / 0.2
        r4 = z["p4"][m][:, :, 30:50].sum(axis=2) / 0.2
        s_idx = np.flatnonzero(sel)
        conds = {"main2_P3": r3[:, s_idx[y == 1]].mean(1), "main2_P4": r4[:, s_idx[y == 1]].mean(1),
                 "seq_P3": r3[:, s_idx[y == 0]].mean(1), "seq_P4": r4[:, s_idx[y == 0]].mean(1)}
        R = jnwb.rdm(np.array(list(conds.values())), metric="correlation", condensed=False)
        rec["expl_rdm"] = {"conditions": list(conds), "matrix": R.round(6).tolist()}
        out["areas"][a] = rec
        print(ses, a, m.sum(), "A4", round(rec["P4"]["accuracy"], 3), "A3", round(rec["P3"]["accuracy"], 3),
              "base", round(rec["P4"]["majority_baseline_accuracy"], 3), "p_diff", rec["null"]["p_diff"], flush=True)
    out["seconds"] = round(time.time() - t0, 1)
    out = receipt({**out, "asset_id": meta["asset_id"], "dandi_sha256": meta["dandi_sha256"],
                   "counts_npz_sha256": sha256(d / "counts.npz"), "n_perm": n_perm, "population": population})
    od = RESULTS / ("s2" if population == "responsive" else "s2_allunits_exploratory") / "sessions"
    od.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(od / f"{ses}.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
