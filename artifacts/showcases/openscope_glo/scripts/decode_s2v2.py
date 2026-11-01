"""Showcase 2 version 2, per session (PREREGISTRATION_S2_v2.md).

Usage: python scripts/decode_s2v2.py SESSION_ID
All quality units; features residualised on [1, stimulus_block] by OLS over the decoded trials
(no label used); accuracy, AUC and majority baseline at P4 and P3. Writes
results/s2v2/sessions/<ses>.json.
"""
import os

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[v] = "1"

import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from decode_s2 import decode, feats  # noqa: E402
from glo_common import AREAS, RESULTS, receipt, sha256  # noqa: E402

MIN_UNITS = 20


def residualise(X, pos):
    """Residuals of each column of X from an OLS fit on [1, pos]."""
    D = np.column_stack([np.ones(len(pos)), pos.astype(float)])
    beta = np.linalg.lstsq(D, X, rcond=None)[0]
    return X - D @ beta


def main():
    ses = sys.argv[1]
    t0 = time.time()
    d = RESULTS / "sessions" / ses
    meta = json.load(open(d / "session.json"))
    cond = pd.read_csv(d / "conditions.csv", keep_default_na=False)
    kept = cond[cond.excluded == ""].reset_index(drop=True)
    z = np.load(d / "counts.npz")
    assert np.array_equal(kept["seq"].to_numpy(), z["seq"])
    area = z["area"]
    ctx, pat, blk = kept.context.to_numpy(), kept.pattern.to_numpy(), kept.block.to_numpy()
    sel = ((ctx == "main2") | (ctx == "seq")) & (pat == "xxxx")
    y, g = np.where(ctx[sel] == "main2", 1, 0), blk[sel]
    dsel = ((ctx == "main1") | (ctx == "main2")) & (pat == "xxxx")
    yd, gd = np.where(ctx[dsel] == "main2", 1, 0), blk[dsel]
    out = {"session": ses, "mouse": meta["subject_id"], "n_trials": {"main2": int(y.sum()), "seq": int((y == 0).sum())},
           "n_blocks": {"main2": int(len(np.unique(g[y == 1]))), "seq": int(len(np.unique(g[y == 0])))},
           "block_range": {"seq": [int(g[y == 0].min()), int(g[y == 0].max())], "main2": [int(g[y == 1].min()), int(g[y == 1].max())]},
           "areas": {}}
    for a in AREAS:
        m = area == a
        rec = {"n_units": int(m.sum())}
        if m.sum() < MIN_UNITS:
            rec["status"] = "fewer_than_20_units"
            out["areas"][a] = rec
            continue
        for e, key in (("p4", "P4"), ("p3", "P3")):
            X = feats(z[e][m][:, sel], 30, 4)
            rec[key] = decode(residualise(X, g), y, g)
            rec["expl_unadjusted_" + key] = decode(X, y, g)
        Xd = feats(z["p4"][m][:, dsel], 30, 4)
        rec["expl_drift_adjusted_P4"] = decode(residualise(Xd, gd), yd, gd)
        rec["expl_drift_unadjusted_P4"] = decode(Xd, yd, gd)
        out["areas"][a] = rec
        print(ses, a, int(m.sum()), "A4", round(rec["P4"]["accuracy"], 3), "A3", round(rec["P3"]["accuracy"], 3),
              "base", round(rec["P4"]["majority_baseline_accuracy"], 3), "auc4", round(rec["P4"]["auc"], 3), flush=True)
    out["seconds"] = round(time.time() - t0, 1)
    out = receipt({**out, "asset_id": meta["asset_id"], "dandi_sha256": meta["dandi_sha256"],
                   "counts_npz_sha256": sha256(d / "counts.npz"), "population": "all_quality_units",
                   "preregistration": "PREREGISTRATION_S2_v2.md"})
    od = RESULTS / "s2v2" / "sessions"
    od.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(od / f"{ses}.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
