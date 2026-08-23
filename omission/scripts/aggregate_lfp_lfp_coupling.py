r"""
RENAMED 2026-08-23 (normalization Batch 3, lfp_lfp_coupling family review): this file was
aggregate_lfp_lfp_coupling_corrected.py. As with aggregate_spike_lfp_coupling.py's rename in
the same batch, there was never a separate uncorrected file in this repo -- the "_corrected"
suffix is dropped as noise, not as a scientific-variant merge. The other lfp_lfp_coupling
family members (aggregate_lfp_lfp_te_stats.py, aggregate_within_session_lfp_lfp.py,
compute_lfp_lfp_te_network.py, extract_within_session_lfp_lfp_sliding_corr.py) were reviewed
in the same pass and confirmed DISTINCT_ESTIMAND -- imaginary coherency, transfer entropy, and
sliding-window correlation are three different connectivity methods, not successive versions
of one estimand -- so none of them were touched.

Corrected-pooling aggregation for scripts/extract_lfp_coupling_matrices.py's imaginary-coherency
product (outputs/lfp_coupling_matrices/coupling.npz), rerun 2026-08-13 with raw-LFP movement-
artifact repair (omission.jnwb_ext.artifact_repair.repair_lfp_trials) inserted before coupling computation.

WHY A NEW SCRIPT, NOT A FOURTH clopper_pearson
    scripts/aggregate_within_session_lfp_lfp.py already implements the validated design (session
    is the unit of inference; per-session z-score vs a within-session trial-shuffle null; only
    THEN pool across sessions as a proportion tested against the nominal false-positive rate with
    an exact Clopper-Pearson interval -- see omission-signal skill #10, and the corpus-wide
    incident record where raw session point-estimate pooling manufactured 0/45-0/240 false
    negatives six times in one week). But that script's `session_area_pair_z` / file loader is
    written against a DIFFERENT product's shape (outputs/within_session_lfp_lfp_sliding_corr/
    *.npz, one file per session, sliding-window axis). extract_lfp_coupling_matrices.py's
    coupling.npz is one file for the whole corpus, keyed "session|context|band|areaA|layerA|
    areaB|layerB" -> [obs, null_mu, null_sd, n_shuffle, n_trials], no window axis. Rather than
    reinvent Clopper-Pearson a fourth time (three implementations already exist: figstats.py::
    proportion_vs_reference, fit_omission_band_power_glmm.py::clopper_pearson,
    aggregate_within_session_lfp_lfp.py::clopper_pearson), this script IMPORTS the latter and
    adapts only the loading/grouping step to coupling.npz's shape.

DESIGN (mirrors aggregate_within_session_lfp_lfp.py exactly, adapted for one-window-per-context)
    1. Per (session, context, band, areaA, areaB): pool layer-cells within that area pair (mean
       effect across whichever layer combinations exist for that session -- same step
       supp_lfp_lfp_coherency.py::session_area_pair_effect already used, reused here) into one
       z = (obs - null_mu) / null_sd.
    2. A session counts as "significant" for that (context, band, areaA, areaB) if |z| >=
       Z_THRESH (1.96, two-sided -- same threshold and sidedness as
       aggregate_within_session_lfp_lfp.py, for direct comparability).
    3. Pool across sessions: among sessions that had this cell recorded at all (partial coverage
       expected), count how many were significant; exact Clopper-Pearson interval against ALPHA.

Output: outputs/lfp_coupling_matrices/area_pair_hit_rates_repaired.csv
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))

from aggregate_within_session_lfp_lfp import clopper_pearson, Z_THRESH, ALPHA  # noqa: E402
from figstyle import AREA_POOL  # noqa: E402

COUPLING_NPZ = REPO / "outputs" / "lfp_coupling_matrices" / "coupling.npz"
OUT_CSV = REPO / "outputs" / "lfp_coupling_matrices" / "area_pair_hit_rates_repaired.csv"


def load():
    d = np.load(COUPLING_NPZ, allow_pickle=True)
    keys, vals = d["keys"], d["values"]
    rows = []
    for k, v in zip(keys, vals):
        session, ctx, band, areaA, layerA, areaB, layerB = k.split("|")
        rows.append({
            "session": session, "context": ctx, "band": band,
            "areaA": AREA_POOL.get(areaA, areaA), "layerA": layerA,
            "areaB": AREA_POOL.get(areaB, areaB), "layerB": layerB,
            "obs": v[0], "null_mu": v[1], "null_sd": v[2],
            "n_shuffle": v[3], "n_trials": v[4],
        })
    return pd.DataFrame(rows)


def session_area_pair_z(df, context, band):
    """One z per (session, areaA<=areaB), pooling layer-cells within that area pair by
    averaging observed and null separately first (same convention as
    supp_lfp_lfp_coherency.py::session_area_pair_effect, extended to carry null_sd through)."""
    sub = df[(df.context == context) & (df.band == band)].copy()
    lo = np.minimum(sub.areaA, sub.areaB)
    hi = np.maximum(sub.areaA, sub.areaB)
    sub["areaA"], sub["areaB"] = lo, hi
    g = sub.groupby(["session", "areaA", "areaB"], as_index=False)[
        ["obs", "null_mu", "null_sd"]].mean()
    g["z"] = np.divide(g.obs - g.null_mu, g.null_sd,
                       out=np.full(len(g), np.nan), where=g.null_sd.values > 0)
    return g


def main():
    if not COUPLING_NPZ.exists():
        raise SystemExit(f"missing {COUPLING_NPZ} -- run extract_lfp_coupling_matrices.py first")
    df = load()
    contexts = sorted(df.context.unique())
    bands = sorted(df.band.unique())
    print(f"{df.session.nunique()} sessions, contexts={contexts}, bands={bands}")

    rows = []
    for context in contexts:
        for band in bands:
            g = session_area_pair_z(df, context, band)
            for (areaA, areaB), gg in g.groupby(["areaA", "areaB"]):
                zvals = gg.z.dropna().values
                n = len(zvals)
                if n == 0:
                    continue
                k = int(np.sum(np.abs(zvals) >= Z_THRESH))
                lo, hi = clopper_pearson(k, n, alpha=ALPHA)
                rows.append({
                    "context": context, "band": band, "areaA": areaA, "areaB": areaB,
                    "n_sessions": n, "n_significant_sessions": k,
                    "hit_rate": k / n if n else np.nan,
                    "ci95_lo": lo, "ci95_hi": hi,
                    "above_chance": (lo > ALPHA) if np.isfinite(lo) else False,
                    "z_thresh": Z_THRESH, "alpha": ALPHA,
                })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    n_above = int(out.above_chance.sum()) if len(out) else 0
    print(f"WROTE {OUT_CSV} ({len(out)} area-pair x band x context cells, "
         f"{n_above} with hit-rate CI lower bound above alpha={ALPHA})")
    if len(out):
        top = out.sort_values("hit_rate", ascending=False).head(20)
        print(top[["context", "band", "areaA", "areaB", "n_sessions",
                   "n_significant_sessions", "hit_rate", "ci95_lo", "above_chance"]]
             .to_string())


if __name__ == "__main__":
    main()
