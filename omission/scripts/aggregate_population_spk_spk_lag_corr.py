r"""
Step 2 of 2 (pool after testing, not before): generalize per-session SPK-SPK lead/lag
correlations across sessions. Same design as aggregate_within_session_lfp_lfp.py, with LAG
playing the role that WINDOW POSITION played there -- lag is a declared axis of the corrected
family, never a "take the max over lags" shortcut (that would inflate the false-positive rate
by construction: 21 lags tested per pair, and >80% of pairs already exceed |Z|>=1.96 at SOME
lag by chance alone before any correction -- see extraction script's smoke-test note).

DESIGN
    Per (scope, node1, node2, lag, condition_group): collapse to per-session Z (one value
    already, since a "node" IS an (area, func_group) pair -- no further within-session
    collapsing needed, unlike the channel-level LFP-LFP script). Session counts as a "hit" at
    |Z| >= Z_THRESH. Pool the hit/no-hit across sessions that had that exact cell (partial
    coverage expected) via exact binomial (Clopper-Pearson). Multiplicity: Holm-Bonferroni and
    BH-FDR together across the ENTIRE family of cells with >= MIN_SESSIONS sessions -- one
    family, not corrected per lag or per condition group separately.

    A separate, explicitly DESCRIPTIVE summary (peak-lag histogram among corrected-significant
    cells only) answers "which lag tends to win," but is never used to select which cells count
    as significant -- that selection is fixed by the per-lag hit-rate test above, decided before
    looking at which lag has the biggest effect.

OUTPUT
    outputs/population_spk_spk_lag_corr/lag_hit_rates.csv
    outputs/population_spk_spk_lag_corr/peak_lag_summary.csv (descriptive only)
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from jnwb import paths as _P
from jnwb.statistics import clopper_pearson

IN_DIR = _P.REPO_ROOT / "outputs/population_spk_spk_lag_corr"
Z_THRESH = 1.96
ALPHA = 0.05
MIN_SESSIONS = 3
CONDITION_GROUPS = ("baseline", "stim", "omission")


def load_session(path, cg):
    d = np.load(path, allow_pickle=True)
    key = f"{cg}_pairs"
    if key not in d.files:
        return None
    pairs = [p.split("|") for p in d[f"{cg}_pairs"]]  # (scope, area1, func1, area2, func2)
    real, nm, ns = d[f"{cg}_real"], d[f"{cg}_null_mean"], d[f"{cg}_null_std"]
    lags_ms = d[f"{cg}_lags_ms"]
    z = np.divide(real - nm, ns, out=np.full_like(real, np.nan), where=ns > 0)
    return pairs, z, lags_ms


def main():
    files = sorted(glob.glob(os.path.join(IN_DIR, "*.npz")))
    print(f"{len(files)} session files found")
    if not files:
        raise SystemExit("no session .npz files -- run extract_population_spk_spk_lag_corr.py")

    rows = []
    for cg in CONDITION_GROUPS:
        session_hits = {}   # (scope, key_nodes, lag_ms) -> list of bool (one per session)
        for f in files:
            loaded = load_session(f, cg)
            if loaded is None:
                continue
            pairs, z, lags_ms = loaded
            for pi, (scope, a1, f1, a2, f2) in enumerate(pairs):
                node1, node2 = (a1, f1), (a2, f2)
                key_nodes = tuple(sorted([node1, node2]))
                for li, lag in enumerate(lags_ms):
                    zval = z[pi, li]
                    if not np.isfinite(zval):
                        continue
                    key = (scope, key_nodes, float(lag))
                    session_hits.setdefault(key, []).append(abs(zval) >= Z_THRESH)

        for (scope, key_nodes, lag), hits in session_hits.items():
            n, k = len(hits), int(sum(hits))
            lo, hi = clopper_pearson(k, n)
            rows.append({
                "condition_group": cg, "scope": scope,
                "node1_area": key_nodes[0][0], "node1_func": key_nodes[0][1],
                "node2_area": key_nodes[1][0], "node2_func": key_nodes[1][1],
                "lag_ms": lag, "n_sessions": n, "n_significant_sessions": k,
                "hit_rate": k / n if n else np.nan, "ci95_lo": lo, "ci95_hi": hi,
            })
    out = pd.DataFrame(rows)

    family = out[out.n_sessions >= MIN_SESSIONS].copy()
    binom_p = [stats.binomtest(int(r.n_significant_sessions), int(r.n_sessions), ALPHA,
                               alternative="greater").pvalue for r in family.itertuples()]
    family["binom_p"] = binom_p
    _, holm_p, _, _ = multipletests(family.binom_p, alpha=ALPHA, method="holm")
    _, bh_p, _, _ = multipletests(family.binom_p, alpha=ALPHA, method="fdr_bh")
    family["holm_p"], family["bh_q"] = holm_p, bh_p
    family["sig_holm"] = holm_p < ALPHA
    family["sig_bh_fdr"] = bh_p < ALPHA

    key_cols = ["condition_group", "scope", "node1_area", "node1_func", "node2_area",
               "node2_func", "lag_ms"]
    out = out.merge(family[key_cols + ["binom_p", "holm_p", "bh_q", "sig_holm", "sig_bh_fdr"]],
                    on=key_cols, how="left").sort_values("bh_q", na_position="last")
    out.to_csv(os.path.join(IN_DIR, "lag_hit_rates.csv"), index=False)

    print(f"family size (n_sessions>={MIN_SESSIONS}): {len(family)} / {len(out)} total cells")
    print(f"Holm-Bonferroni significant: {int(family.sig_holm.sum())}")
    print(f"BH-FDR significant: {int(family.sig_bh_fdr.sum())}")

    surv = out[out.sig_holm.fillna(False).infer_objects(copy=False)]
    print(f"\nHolm survivors ({len(surv)}):")
    if len(surv):
        print(surv[key_cols + ["n_sessions", "hit_rate", "holm_p", "bh_q"]]
              .to_string(index=False))

        # descriptive only -- peak lag AMONG cells already declared significant above, never
        # used to select significance itself.
        summary = []
        for (cg, sc, a1, f1, a2, f2), g in surv.groupby(
                ["condition_group", "scope", "node1_area", "node1_func", "node2_area",
                 "node2_func"]):
            best = g.loc[g.hit_rate.idxmax()]
            summary.append({"condition_group": cg, "scope": sc, "node1": f"{a1}/{f1}",
                            "node2": f"{a2}/{f2}", "peak_lag_ms": best.lag_ms,
                            "hit_rate": best.hit_rate, "holm_p": best.holm_p})
        pd.DataFrame(summary).to_csv(
            os.path.join(IN_DIR, "peak_lag_summary.csv"), index=False)
        print(f"\nwrote peak_lag_summary.csv ({len(summary)} node pairs with >=1 "
             f"Holm-significant lag) -- DESCRIPTIVE, not an independent significance claim")
    else:
        print("(none)")

    print(f"\nWROTE {IN_DIR}/lag_hit_rates.csv ({len(out)} rows)")


if __name__ == "__main__":
    main()
