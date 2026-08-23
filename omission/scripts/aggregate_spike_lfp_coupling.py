r"""
RENAMED 2026-08-23 (normalization Batch 3, spike_lfp_coupling family canonicalization): this
file was aggregate_spike_lfp_coupling_v2_corrected.py. The "_v2_corrected" suffix is dropped
because there was never a separate uncorrected implementation as a tracked file -- "the
original (never group-corrected) PPC pipeline" referred to below is a historical design flaw in
the pre-2026-08-15 fig07 approach, not a file in this repo. scripts/extract_spike_lfp_coupling_v2.py
mentioned below is now scripts/extract_spike_lfp_coupling.py (renamed same pass).

Corrected-pooling aggregation for scripts/extract_spike_lfp_coupling.py's PPC product
(outputs/spike_lfp_coupling/coupling_v2.npz) -- the corrected-design PPC rebuild Hamm asked for
(2026-08-15 AskUserQuestion: "Rebuild corrected PPC first", rejecting both the omission-signal
skill's retirement of PPC and reuse of the already-null sliding-correlation replacement).

WHY THIS DESIGN, NOT A FIFTH clopper_pearson
    Same corrected-pooling design as scripts/aggregate_lfp_lfp_coupling.py (renamed 2026-08-23
    from aggregate_lfp_lfp_coupling_corrected.py; itself
    adapting scripts/aggregate_within_session_lfp_lfp.py's validated pattern to a different
    product shape) -- session is the unit of inference, per-session z vs the within-session
    trial-shuffle null already computed by the extraction script, THEN pool across sessions as a
    proportion with an exact Clopper-Pearson interval (omission-signal skill #10: pooling raw
    session point-estimates manufactured 0/45-0/240 false negatives six times on this corpus
    including, per that skill's own text, PPC itself -- "each had a validated within-session
    shuffle null and each found large single-session effects (z > 20-88)"). Imports
    jnwb.statistics.clopper_pearson (the promoted canonical implementation) rather than
    reimplementing.

NEW HERE, vs THE ORIGINAL (never group-corrected) PPC pipeline
    Splits cells by FUNCTIONAL CLASS (S+, S++, S-, S--, O+, O++, O-, O--) using
    outputs/classification/unit_master_features.csv, not just area x layer x band x context --
    that class split is the actual novel question this supplemental analysis asks ("phase
    locking during omission, by neuron type"), not present in the original fig07 pipeline.

Output: outputs/spike_lfp_coupling/class_hit_rates_v2.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))

from jnwb.statistics import clopper_pearson  # noqa: E402
from figstyle import AREA_POOL  # noqa: E402

COUPLING_NPZ = REPO / "outputs/spike_lfp_coupling/coupling_v2.npz"
UNIT_FEATURES = REPO / "outputs/classification/unit_master_features.csv"
OUT_CSV = REPO / "outputs/spike_lfp_coupling/class_hit_rates_v2.csv"

Z_THRESH = 1.96
ALPHA = 0.05
CLASSES = ["is_Splus", "is_Splus_double", "is_Sminus", "is_Sminus_double",
          "is_Oplus", "is_Oplus_double", "is_Ominus", "is_Ominus_double"]
MIN_SESSIONS = 3


def load():
    d = np.load(COUPLING_NPZ, allow_pickle=True)
    keys, vals = d["keys"], d["values"]
    rows = []
    for k, v in zip(keys, vals):
        session, ctx, band, area, layer, unit_row = k.split("|")
        rows.append({
            "session": session, "context": ctx, "band": band,
            "area": AREA_POOL.get(area, area), "layer": layer, "unit_row": int(unit_row),
            "obs": v[0], "null_mu": v[1], "null_sd": v[2], "n_shuffle": v[3], "n_spikes": v[4],
        })
    return pd.DataFrame(rows)


def attach_class(df):
    feat = pd.read_csv(UNIT_FEATURES)
    feat = feat.rename(columns={"session": "unit_session", "unit_row": "unit_row",
                                "area10": "unit_area"})
    m = df.merge(feat[["unit_session", "unit_row", "unit_area"] + CLASSES],
                left_on=["session", "unit_row"], right_on=["unit_session", "unit_row"],
                how="left")
    return m


def main():
    if not COUPLING_NPZ.exists():
        raise SystemExit(f"missing {COUPLING_NPZ} -- run extract_spike_lfp_coupling_v2.py first")
    df = load()
    df = attach_class(df)
    df["z"] = np.divide(df.obs - df.null_mu, df.null_sd,
                        out=np.full(len(df), np.nan), where=df.null_sd.values > 0)

    rows = []
    contexts = sorted(df.context.unique())
    bands = sorted(df.band.unique())
    for cls in CLASSES:
        sub_cls = df[df[cls] == True]  # noqa: E712
        for context in contexts:
            for band in bands:
                for area, g in sub_cls[(sub_cls.context == context) &
                                       (sub_cls.band == band)].groupby("area"):
                    # session = unit of inference: one z per session (mean across its own
                    # class units / layers within that area x band x context cell first).
                    g_sess = g.groupby("session").z.mean().dropna()
                    n = len(g_sess)
                    if n < MIN_SESSIONS:
                        continue
                    k = int(np.sum(np.abs(g_sess.to_numpy()) >= Z_THRESH))
                    lo, hi = clopper_pearson(k, n, alpha=ALPHA)
                    rows.append({
                        "class": cls, "context": context, "band": band, "area": area,
                        "n_sessions": n, "n_significant_sessions": k,
                        "hit_rate": k / n, "ci95_lo": lo, "ci95_hi": hi,
                        "above_chance": bool(lo > ALPHA) if np.isfinite(lo) else False,
                        "z_thresh": Z_THRESH, "alpha": ALPHA,
                    })

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    n_above = int(out.above_chance.sum()) if len(out) else 0
    print(f"WROTE {OUT_CSV} ({len(out)} class x context x band x area cells, "
         f"{n_above} with hit-rate CI lower bound above alpha={ALPHA})")
    if len(out) and n_above:
        print(out[out.above_chance].sort_values("hit_rate", ascending=False)
             [["class", "context", "band", "area", "n_sessions", "n_significant_sessions",
               "hit_rate", "ci95_lo"]].to_string(index=False))
    elif len(out):
        print("No class x context x band x area cell's hit-rate CI lower bound exceeds alpha "
             "-- a clean null under the corrected design, reported as such (CLAUDE.md tripwire "
             "#10), not re-designed until something comes back significant.")


if __name__ == "__main__":
    main()
