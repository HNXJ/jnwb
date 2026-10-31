"""Showcase 2, across mice: sign-flip on A_P4 - A_P3 per area, BH over tested areas.

Usage: python scripts/aggregate_s2.py [responsive|all]
Reads results/s2/sessions/*.json (or s2_allunits_exploratory) and writes summary.csv,
per_session.csv and receipt.json next to them.
"""
import json
import sys

import numpy as np
import pandas as pd

from glo_common import AREAS, RESULTS, SEED, receipt
import jnwb

MIN_MICE = 6
POP = sys.argv[1] if len(sys.argv) > 1 else "responsive"
BASE = RESULTS / ("s2" if POP == "responsive" else "s2_allunits_exploratory")


def main():
    rows, inputs, excluded = [], {}, {}
    for f in sorted((BASE / "sessions").glob("*.json")):
        r = json.load(open(f))
        meta = json.load(open(RESULTS / "sessions" / r["session"] / "session.json"))
        if not (meta["validation"]["pass"] and meta["clock_pass"]):
            excluded[r["session"]] = "failed condition validation"
            continue
        inputs[r["session"]] = {k: r[k] for k in ("asset_id", "dandi_sha256", "counts_npz_sha256", "script_commit", "jnwb_commit")}
        for a, v in r["areas"].items():
            row = {"session": r["session"], "mouse": r["mouse"], "area": a, "n_units": v["n_units"],
                   "n_main2": r["n_trials"]["main2"], "n_seq": r["n_trials"]["seq"],
                   "n_blocks_main2": r["n_blocks"]["main2"], "n_blocks_seq": r["n_blocks"]["seq"]}
            if "P4" in v:
                row.update(A4=v["P4"]["accuracy"], A3=v["P3"]["accuracy"], base=v["P4"]["majority_baseline_accuracy"],
                           auc4=v["P4"]["auc"], auc3=v["P3"]["auc"], status4=v["P4"]["status"], status3=v["P3"]["status"],
                           est=v["estimand_A4_minus_A3"], p_P4=v["null"]["p_P4"], p_P3=v["null"]["p_P3"],
                           p_diff=v["null"]["p_diff"], null4=v["null"]["null_P4_mean"], null3=v["null"]["null_P3_mean"],
                           drift_acc=v["expl_drift_main1_vs_main2_P4"]["accuracy"],
                           drift_base=v["expl_drift_main1_vs_main2_P4"]["majority_baseline_accuracy"],
                           gain_removed_acc=v["expl_gain_removed_P4"]["accuracy"],
                           unit_shuffled_acc=v["expl_unit_shuffled_P4"]["accuracy"],
                           tr_p4=json.dumps([round(x, 4) for x in v["expl_time_resolved"]["p4"]]),
                           tr_p3=json.dumps([round(x, 4) for x in v["expl_time_resolved"]["p3"]]))
            rows.append(row)
    ps = pd.DataFrame(rows)
    ps.to_csv(BASE / "per_session.csv", index=False)
    rng = np.random.default_rng(SEED)
    summ = []
    for a in AREAS:
        s = ps[(ps.area == a) & ps.get("est", pd.Series(np.nan, index=ps.index)).notna()] if "est" in ps else ps.iloc[0:0]
        row = {"area": a, "n_mice": len(s)}
        if len(s):
            row.update(mean_A4=s.A4.mean(), mean_A3=s.A3.mean(), mean_base=s.base.mean(), mean_drift_acc=s.drift_acc.mean(),
                       mean_gain_removed=s.gain_removed_acc.mean(), mean_unit_shuffled=s.unit_shuffled_acc.mean(),
                       n_sessions_p_diff_05=int((s.p_diff < 0.05).sum()))
        if len(s) >= MIN_MICE:
            x = s.est.to_numpy()
            mean, p, floor = jnwb.exact_sign_flip(x, alternative="two-sided")
            idx = rng.integers(0, len(x), size=(10000, len(x)))
            lo, hi = np.percentile(x[idx].mean(axis=1), [2.5, 97.5])
            row.update(mean_est=mean, ci_lo=lo, ci_hi=hi, p=p, p_floor=floor)
        elif len(s):
            row.update(mean_est=s.est.mean(), note=f"not testable: {len(s)} mice < {MIN_MICE}")
        summ.append(row)
    summ = pd.DataFrame(summ)
    summ["q"] = np.nan
    if "p" in summ and summ.p.notna().any():
        ok = summ.p.notna()
        summ.loc[ok, "q"] = jnwb.fdr_correct(summ.loc[ok, "p"].to_numpy())
    summ.to_csv(BASE / "summary.csv", index=False)
    json.dump(receipt({"inputs": inputs, "excluded_sessions": excluded, "population": POP, "min_mice": MIN_MICE}),
              open(BASE / "receipt.json", "w"), indent=1, default=str)
    pd.set_option("display.width", 220)
    print(summ.to_string())


if __name__ == "__main__":
    main()
