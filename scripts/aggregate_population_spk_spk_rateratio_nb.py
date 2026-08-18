r"""
Step 2 of 2 (pool after testing, not before): generalize per-session NB rate-ratio tests across
sessions. Unlike the correlation-based lead/lag script, each (session, condition_group, pair,
lag) cell here ALREADY carries a real, model-based p-value (the NB regression's own Wald test on
the rate_A coefficient) -- no Z-score-from-a-shuffle-null step is needed first. A session counts
as a "hit" at p < ALPHA; hit rates are pooled across sessions exactly as everywhere else (exact
binomial vs the nominal false-positive rate, Holm-Bonferroni + BH-FDR across the full
(scope, node pair, lag, condition_group) family, cells with >= MIN_SESSIONS sessions only).

OUTPUT
    outputs/population_spk_spk_rateratio_nb/rateratio_hit_rates.csv
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

IN_DIR = _P.REPO_ROOT / "outputs/population_spk_spk_rateratio_nb"
ALPHA = 0.05
MIN_SESSIONS = 3
KEY_COLS = ["condition_group", "scope", "node1_area", "node1_func", "node2_area", "node2_func",
           "lag_ms"]


def main():
    files = sorted(glob.glob(os.path.join(IN_DIR, "*.csv.gz")))
    files = [f for f in files if not os.path.basename(f).startswith("all_session_rows")]
    print(f"{len(files)} session files found")
    if not files:
        raise SystemExit("no session .csv.gz files -- run "
                         "extract_population_spk_spk_rateratio_nb.py first")

    parts = []
    for f in files:
        d = pd.read_csv(f)
        d["session"] = os.path.basename(f).replace(".csv.gz", "")
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    df["hit"] = df.p < ALPHA

    rows = []
    for key, g in df.groupby(KEY_COLS):
        n, k = len(g), int(g.hit.sum())
        lo, hi = clopper_pearson(k, n)
        binom_p = stats.binomtest(k, n, ALPHA, alternative="greater").pvalue if n else np.nan
        median_rr = float(g.rate_ratio.median())
        rows.append({**dict(zip(KEY_COLS, key)), "n_sessions": n, "n_significant_sessions": k,
                    "hit_rate": k / n if n else np.nan, "ci95_lo": lo, "ci95_hi": hi,
                    "binom_p": binom_p, "median_rate_ratio": median_rr})
    out = pd.DataFrame(rows)

    family = out[out.n_sessions >= MIN_SESSIONS].copy()
    if len(family):
        _, holm_p, _, _ = multipletests(family.binom_p, alpha=ALPHA, method="holm")
        _, bh_p, _, _ = multipletests(family.binom_p, alpha=ALPHA, method="fdr_bh")
        family["holm_p"], family["bh_q"] = holm_p, bh_p
        family["sig_holm"] = holm_p < ALPHA
        family["sig_bh_fdr"] = bh_p < ALPHA
    out = out.merge(family[KEY_COLS + ["holm_p", "bh_q", "sig_holm", "sig_bh_fdr"]],
                    on=KEY_COLS, how="left").sort_values("bh_q", na_position="last")

    out.to_csv(os.path.join(IN_DIR, "rateratio_hit_rates.csv"), index=False)
    df.to_csv(os.path.join(IN_DIR, "all_session_rows.csv.gz"), index=False)
    print(f"WROTE {IN_DIR}/rateratio_hit_rates.csv ({len(out)} rows)")
    print(f"family size (n_sessions>={MIN_SESSIONS}): {len(family)} / {len(out)} total cells")
    print(f"Holm-Bonferroni significant: {int(family.sig_holm.sum()) if len(family) else 0}")
    print(f"BH-FDR significant: {int(family.sig_bh_fdr.sum()) if len(family) else 0}")

    surv = out[out.sig_holm.fillna(False).infer_objects(copy=False)]
    print(f"\nHolm survivors ({len(surv)}):")
    if len(surv):
        print(surv[KEY_COLS + ["n_sessions", "hit_rate", "median_rate_ratio", "holm_p", "bh_q"]]
              .to_string(index=False))
    print(f"\nlag_ms distribution among Holm survivors:")
    print(surv.lag_ms.value_counts().sort_index() if len(surv) else "(none)")


if __name__ == "__main__":
    main()
