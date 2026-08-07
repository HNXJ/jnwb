r"""
Step 2 of 2 (pool after testing, not before -- feedback_pool_after_testing_not_before memory):
generalize per-session population-firing-vs-band-power correlations across sessions.

Unlike the LFP-LFP/SPK-SPK sliding-window scripts, extract_population_firing_lfp_power_corr.py
already writes ONE scalar (real_r, null_mean, null_std) per session per
(area, func_group, condition_group, band) key -- there is no channel-pair collapsing step here,
population pooling already happened inside the extraction. This script only does the
cross-session step: per key, convert to Z, call a session "significant" at |Z| >= Z_THRESH, pool
hits across the sessions that actually had that key (partial coverage expected) with an exact
binomial (Clopper-Pearson) interval.

MULTIPLICITY
    One family: every (condition_group, area, func_group, band) cell with n_sessions >= 3 (same
    "at least 3 sessions" floor figures 6/7 use before a cell enters their correction family).
    Each cell's hit rate is tested against H0: p = ALPHA (nominal false-positive rate) via an
    exact binomial test, then Holm-Bonferroni (FWER) and Benjamini-Hochberg (FDR) are applied
    across the whole family in one pass -- not per band, per area, or per condition group
    separately, and not conflated with each other (Holm controls FWER, BH controls FDR; they
    are different guarantees, per this project's own statistical doctrine).

OUTPUT
    outputs/population_firing_lfp_power_corr/hit_rates.csv
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

IN_DIR = r"D:/workspace/omission/outputs/population_firing_lfp_power_corr"
Z_THRESH = 1.96
ALPHA = 0.05
MIN_SESSIONS = 3
KEY_COLS = ["condition_group", "area", "func_group", "band"]


def clopper_pearson(k, n, alpha=ALPHA):
    if n == 0:
        return (np.nan, np.nan)
    lo = 0.0 if k == 0 else stats.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return float(lo), float(hi)


def main():
    files = sorted(glob.glob(os.path.join(IN_DIR, "*.csv.gz")))
    files = [f for f in files if not os.path.basename(f).startswith("all_session_rows")]
    print(f"{len(files)} session files found")
    if not files:
        raise SystemExit("no session .csv.gz files -- run "
                          "extract_population_firing_lfp_power_corr.py first")

    parts = []
    for f in files:
        d = pd.read_csv(f)
        d["session"] = os.path.basename(f).replace(".csv.gz", "")
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    df["z"] = (df.real_r - df.null_mean) / df.null_std
    df["hit"] = df.z.abs() >= Z_THRESH

    rows = []
    for key, g in df.groupby(KEY_COLS):
        n = len(g)
        k = int(g.hit.sum())
        lo, hi = clopper_pearson(k, n)
        hit_sign = np.sign(g.loc[g.hit, "z"].mean()) if k else 0
        binom_p = stats.binomtest(k, n, ALPHA, alternative="greater").pvalue if n else np.nan
        rows.append({**dict(zip(KEY_COLS, key)),
                     "n_sessions": n, "n_significant_sessions": k,
                     "hit_rate": k / n if n else np.nan,
                     "ci95_lo": lo, "ci95_hi": hi,
                     "binom_p": binom_p,
                     "mean_z": float(g.z.mean()), "hit_sign": int(hit_sign)})
    out = pd.DataFrame(rows)

    family = out[out.n_sessions >= MIN_SESSIONS].copy()
    if len(family):
        _, holm_p, _, _ = multipletests(family.binom_p, alpha=ALPHA, method="holm")
        _, bh_p, _, _ = multipletests(family.binom_p, alpha=ALPHA, method="fdr_bh")
        family["holm_p"] = holm_p
        family["bh_q"] = bh_p
        family["sig_holm"] = holm_p < ALPHA
        family["sig_bh_fdr"] = bh_p < ALPHA
    out = out.merge(family[KEY_COLS + ["holm_p", "bh_q", "sig_holm", "sig_bh_fdr"]],
                     on=KEY_COLS, how="left")
    out = out.sort_values("bh_q", na_position="last")

    out.to_csv(os.path.join(IN_DIR, "hit_rates.csv"), index=False)
    df.to_csv(os.path.join(IN_DIR, "all_session_rows.csv.gz"), index=False)
    print(f"WROTE {IN_DIR}/hit_rates.csv ({len(out)} rows), all_session_rows.csv.gz "
          f"({len(df)} rows)")
    print(f"family size (n_sessions>={MIN_SESSIONS}): {len(family)} / {len(out)} total cells")
    print(f"Holm-Bonferroni significant: {int(out.sig_holm.sum())}")
    print(f"BH-FDR significant: {int(out.sig_bh_fdr.sum())}")
    surv = out[out.sig_holm.fillna(False)]
    print(surv[KEY_COLS + ["n_sessions", "hit_rate", "mean_z", "holm_p", "bh_q"]]
          .to_string() if len(surv) else "(none survive Holm)")


if __name__ == "__main__":
    main()
