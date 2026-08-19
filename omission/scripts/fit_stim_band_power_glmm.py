r"""
Stimulus-window counterpart to fit_omission_band_power_glmm.py -- same area x subject additive
GLMM (Model F) and full pairwise area contrasts, fit on the REAL-STIMULUS response instead of
the omission response, via the SHARED area_subject_glmm.fit_area_subject_and_pairwise()
function (not a reimplementation -- see that module's docstring for why).

INPUT
    outputs/lfp_band_census_stim/channel_band_power.csv.gz (build with
    scripts/compute_stim_channel_band_power_census.py)

    Response: db_stim_baserel -- power during a real stimulus presentation (RRRR/AAAB/BBBA,
    slots 2/3/4) relative to its own -250..-50 ms pre-stimulus baseline, in dB, trial-averaged
    within channel. Same measure/window/baseline convention as db_mid_omirel on the omission
    side, so the two are directly comparable.

MODEL
    F: db ~ C(area, Treatment('V1')) + C(subject), session-level, all sessions with stimulus
    coverage, all 3 subjects -- identical design to the omission side's Model F.

OUTPUT
    outputs/lfp_band_census_stim/glmm_summary.csv
    outputs/lfp_band_census_stim/glmm_results.json
"""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import statsmodels

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from area_subject_glmm import fit_area_subject_and_pairwise  # noqa: E402
from jnwb import paths as _P

CENSUS = _P.REPO_ROOT / "outputs/lfp_band_census_stim/channel_band_power.csv.gz"
OUT_DIR = _P.REPO_ROOT / "outputs/lfp_band_census_stim"
BANDS = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]
RESP = "db_stim_baserel"


def bh(pvals):
    """Benjamini-Hochberg -- identical implementation to figstats.py's (verified correct
    2026-08-05, see artifacts/.lab/v3ad_beta_glmm_two_bugs_fixed_20260805.json); this script
    does not reimplement its own copy, to avoid repeating that exact bug."""
    p = np.asarray(pvals, dtype=float)
    ok = np.isfinite(p)
    out = np.full(p.shape, np.nan)
    if ok.sum() == 0:
        return out
    q = p[ok]
    n = q.size
    order = np.argsort(q)
    adj = np.minimum.accumulate((q[order] * n / np.arange(1, n + 1))[::-1])[::-1]
    res = np.empty(n)
    res[order] = np.clip(adj, 0, 1)
    out[ok] = res
    return out


def main():
    if not os.path.exists(CENSUS):
        raise SystemExit(f"missing {CENSUS} -- run compute_stim_channel_band_power_census.py")
    df = pd.read_csv(CENSUS)
    df["area_infer"] = df["area"].replace({"V3": "V3a/d", "V3d": "V3a/d", "V3a": "V3a/d"})
    ref = "V1" if "V1" in set(df.area_infer) else sorted(df.area_infer.unique())[0]

    rows, notes = fit_area_subject_and_pairwise(
        df, RESP, BANDS, ref, "F_area_subject_controlled_session_level",
        "F_pairwise_area_contrasts")

    out = pd.DataFrame(rows)
    out["_subj"] = ""
    out["p_bh"] = np.nan
    for _, g in out.groupby(["model", "term", "_subj"], dropna=False):
        out.loc[g.index, "p_bh"] = bh(g["p_raw"].values)
    out = out.drop(columns="_subj")
    out.to_csv(os.path.join(OUT_DIR, "glmm_summary.csv"), index=False)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "input": CENSUS, "response": RESP,
        "response_definition": "10*log10(power during a real stimulus / power in its own "
                              "-250..-50 ms pre-stimulus baseline), dB, trial-averaged within "
                              "channel, session-averaged within area before the GLMM sees it",
        "family": "Gaussian, identity link (linear mixed model / OLS fallback)",
        "estimation": "statsmodels MixedLM (REML) or OLS with session-cluster-robust SEs "
                     "(per-band, whichever converges) -- see area_subject_glmm.py",
        "reference_area": ref, "n_rows": int(len(out)),
        "notes_and_skips": notes,
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "statsmodels": statsmodels.__version__,
                "platform": platform.platform()},
    }
    with open(os.path.join(OUT_DIR, "glmm_results.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)

    print(out[out.model == "F_area_subject_controlled_session_level"]
         [["band", "term", "estimate_db", "p_raw", "p_bh"]].to_string(index=False))
    print("\nNOTES:")
    for n in notes:
        print("  -", n)
    print(f"\nWROTE {OUT_DIR}/glmm_summary.csv and glmm_results.json")


if __name__ == "__main__":
    main()
