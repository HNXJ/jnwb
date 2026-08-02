r"""
Per-unit trial presence: fraction of correct sequence trials (up to 960/session) in which a
unit fired at least one spike in the full trial window (p1 onset to end, same FULL_TRIAL_WIN
figstyle.py uses: -600 to 4200 ms).

WHY THIS EXISTS
    fig03's "stable" bucket (see fig03_unit_census.py: attach_stability) has been defined by
    grand_stable_firing_rates.csv's stable_trials_keep_fraction, which comes from an upstream
    drift-outlier screen -- not a literal per-trial spike-presence count. This script computes
    the literal quantity directly from NWB spike times and trial onsets: for every unit in
    omission_grand_units.csv, the fraction of that session's correct sequence trials (pooled
    across all 12 GLO_CONDITIONS, not per-condition) in which the unit fired >=1 spike anywhere
    in the full-trial window. unit_layers.csv's `presence_ratio` is a DIFFERENT quantity (a
    Kilosort session-window presence metric, capped at 0.99, not trial-based) and is not reused
    here -- conflating the two would silently redefine "stable" without changing its name.

OUTPUT
    outputs/classification/unit_trial_presence.csv
    columns: session, unit_row, n_correct_trials, n_trials_present, trial_presence_fraction
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, r"D:/workspace/omission")
import jnwb as oa
from jnwb.unit_classification import precompute_condition_onsets

GRAND_TABLE = r"D:/workspace/omission/outputs/classification/omission_grand_units.csv"
NWB_DIR = r"D:/analysis/nwb"
OUT_CSV = r"D:/workspace/omission/outputs/classification/unit_trial_presence.csv"
FULL_TRIAL_WIN = (-600, 4200)  # ms, p1-aligned -- must match figstyle.FULL_TRIAL_WIN


def main():
    df = pd.read_csv(GRAND_TABLE)
    sessions = sorted(df.session.unique())
    rows = []
    t0 = time.time()
    for si, s in enumerate(sessions):
        path = os.path.join(NWB_DIR, s + "_rec.nwb")
        if not os.path.exists(path):
            path = os.path.join(NWB_DIR, s + ".nwb")
        sess = oa.read(path)
        onsets_by_cond = precompute_condition_onsets(sess, correct_only=True)
        all_onsets = np.sort(np.concatenate([v for v in onsets_by_cond.values() if v.size]))
        n_trials = all_onsets.size
        starts = all_onsets + FULL_TRIAL_WIN[0] / 1000.0
        ends = all_onsets + FULL_TRIAL_WIN[1] / 1000.0

        unit_rows = df.loc[df.session == s, "unit_row"].unique()
        for ur in unit_rows:
            st = sess.get_spike_times(int(ur))
            if st is None or len(st) == 0 or n_trials == 0:
                n_present = 0
            else:
                st = np.sort(np.asarray(st, dtype=float))
                lo = np.searchsorted(st, starts, side="left")
                hi = np.searchsorted(st, ends, side="left")
                n_present = int(np.sum(hi > lo))
            frac = n_present / n_trials if n_trials else 0.0
            rows.append({"session": s, "unit_row": int(ur), "n_correct_trials": int(n_trials),
                        "n_trials_present": n_present, "trial_presence_fraction": frac})
        print(f"[{si + 1}/{len(sessions)}] {s}: {n_trials} trials, "
             f"{len(unit_rows)} units ({time.time() - t0:.1f}s elapsed)")

    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False)
    print(f"wrote {OUT_CSV}  {out.shape}")
    print("units with trial_presence_fraction > 0.98:",
         int((out.trial_presence_fraction > 0.98).sum()), "/", len(out),
         f"({100 * (out.trial_presence_fraction > 0.98).mean():.1f}%)")


if __name__ == "__main__":
    main()
