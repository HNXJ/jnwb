"""Showcase 2 version 2, across mice (PREREGISTRATION_S2_v2.md).

Usage: python scripts/aggregate_s2v2.py
Family A: sign-flip on A - majority baseline at P4 and P3, BH over tested area x onset cells.
Family B: sign-flip on A_P4 - A_P3, BH over tested areas. AUC reported, not tested.
Writes results/s2v2/per_session.csv, family_A.csv, family_B.csv, auc.csv, receipt.json.
"""
import json

import numpy as np
import pandas as pd

from glo_common import AREAS, RESULTS, SEED, receipt
import jnwb

MIN_MICE = 6
BASE = RESULTS / "s2v2"
EXCLUDED = {"1186358749": "DECISIONS.md ruling 5"}


def boot_ci(x, rng):
    idx = rng.integers(0, len(x), size=(10000, len(x)))
    return np.percentile(x[idx].mean(axis=1), [2.5, 97.5])


def test(values, rng):
    mean, p, floor = jnwb.exact_sign_flip(values, alternative="two-sided")
    lo, hi = boot_ci(values, rng)
    return {"mean": mean, "ci_lo": lo, "ci_hi": hi, "p": p, "p_floor": floor}


def bh(df):
    df["q"] = np.nan
    ok = df.p.notna()
    if ok.any():
        df.loc[ok, "q"] = jnwb.fdr_correct(df.loc[ok, "p"].to_numpy())
    return df


def main():
    rows, inputs = [], {}
    for f in sorted((BASE / "sessions").glob("*.json")):
        r = json.load(open(f))
        if r["session"] in EXCLUDED:
            continue
        meta = json.load(open(RESULTS / "sessions" / r["session"] / "session.json"))
        assert meta["validation"]["pass"] and meta["clock_pass"], r["session"]
        inputs[r["session"]] = {k: r[k] for k in ("asset_id", "dandi_sha256", "counts_npz_sha256", "script_commit", "jnwb_commit")}
        for a, v in r["areas"].items():
            row = {"session": r["session"], "mouse": r["mouse"], "area": a, "n_units": v["n_units"]}
            if "P4" in v and v["P4"]["status"] == "success" and v["P3"]["status"] == "success":
                for k in ("P4", "P3"):
                    row.update({f"A_{k}": v[k]["accuracy"], f"base_{k}": v[k]["majority_baseline_accuracy"],
                                f"auc_{k}": v[k]["auc"], f"unadj_A_{k}": v["expl_unadjusted_" + k]["accuracy"],
                                f"unadj_auc_{k}": v["expl_unadjusted_" + k]["auc"]})
                row.update(drift_adj=v["expl_drift_adjusted_P4"]["accuracy"], drift_unadj=v["expl_drift_unadjusted_P4"]["accuracy"],
                           drift_base=v["expl_drift_adjusted_P4"]["majority_baseline_accuracy"])
            rows.append(row)
    ps = pd.DataFrame(rows)
    ps.to_csv(BASE / "per_session.csv", index=False)
    rng = np.random.default_rng(SEED)
    fa, fb, au = [], [], []
    for a in AREAS:
        s = ps[(ps.area == a) & ps.A_P4.notna()]
        n = len(s)
        for k in ("P4", "P3"):
            row = {"area": a, "onset": k, "n_mice": n, "mean_A": s[f"A_{k}"].mean(), "mean_base": s[f"base_{k}"].mean()}
            if n >= MIN_MICE:
                row.update(test((s[f"A_{k}"] - s[f"base_{k}"]).to_numpy(), rng))
            fa.append(row)
        row = {"area": a, "n_mice": n}
        if n >= MIN_MICE:
            row.update(test((s.A_P4 - s.A_P3).to_numpy(), rng))
        fb.append(row)
        row = {"area": a, "n_mice": n, "auc_P4": s.auc_P4.mean(), "auc_P3": s.auc_P3.mean(),
               "unadj_auc_P4": s.unadj_auc_P4.mean(), "unadj_A_P4": s.unadj_A_P4.mean(), "unadj_A_P3": s.unadj_A_P3.mean(),
               "drift_adj": s.drift_adj.mean(), "drift_unadj": s.drift_unadj.mean(), "drift_base": s.drift_base.mean()}
        if n:
            for k in ("P4", "P3"):
                row[f"auc_{k}_ci_lo"], row[f"auc_{k}_ci_hi"] = boot_ci(s[f"auc_{k}"].to_numpy(), rng)
            d = (s.auc_P4 - s.auc_P3).to_numpy()
            row["auc_diff"] = d.mean()
            row["auc_diff_ci_lo"], row["auc_diff_ci_hi"] = boot_ci(d, rng)
        au.append(row)
    fa, fb, au = bh(pd.DataFrame(fa)), bh(pd.DataFrame(fb)), pd.DataFrame(au)
    fa.to_csv(BASE / "family_A.csv", index=False)
    fb.to_csv(BASE / "family_B.csv", index=False)
    au.to_csv(BASE / "auc.csv", index=False)
    json.dump(receipt({"inputs": inputs, "excluded_sessions": EXCLUDED, "min_mice": MIN_MICE,
                       "preregistration": "PREREGISTRATION_S2_v2.md"}), open(BASE / "receipt.json", "w"), indent=1, default=str)
    pd.set_option("display.width", 250)
    for t in (fa, fb, au):
        print(t.round(4).to_string())


if __name__ == "__main__":
    main()
