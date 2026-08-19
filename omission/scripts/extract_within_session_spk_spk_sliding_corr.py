r"""
Within-session, trial-matched sliding-window SPK-SPK correlation -- same design and engine as
extract_within_session_lfp_lfp_sliding_corr.py (see that script's docstring for the full
rationale: test within session first via a trial-mismatch shuffle null, pool across sessions
only afterward). Here both "channels" are single units' spike rate traces instead of LFP band
power.

"GOOD" UNIT SELECTION
    Per area per session, rank units by firing_rate * (1 - q1_p) from the existing
    omission_grand_units.csv classification (real evoked-response magnitude AND reliability,
    not just raw rate -- a high-rate unit with no reliable omission-locked modulation is not
    preferable to a moderate-rate unit with a real, significant one for this purpose). Top
    N_GOOD_UNITS per area. Units with firing_rate too low to support a meaningful spike-count
    correlation (MIN_FIRING_RATE_HZ) are excluded before ranking.

SPIKE RATE TRACE
    omission.jnwb_ext.connectivity.bin_spikes(), 10 ms bins (matching the LFP script's native resolution),
    output='rate' -- same p1-aligned window and trial-onset convention
    (precompute_condition_onsets, correct_only=True) as every other condition-based extraction
    in this repo.

OUTPUT
    outputs/within_session_spk_spk_sliding_corr/<session>.npz
    outputs/within_session_spk_spk_sliding_corr/index.csv
    outputs/within_session_spk_spk_sliding_corr/receipt.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from itertools import combinations, product

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import omission as oa  # noqa: E402
from omission.jnwb_ext.unit_classification import precompute_condition_onsets  # noqa: E402
from omission.jnwb_ext.connectivity import bin_spikes  # noqa: E402
from smoke_test_sliding_trial_correlation import (  # noqa: E402
    sliding_corr_same_trial, WIN_HALF_MS, STEP_MS,
)
from jnwb import paths as _P

NWB_DIR = _P.nwb_dir()
UNITS_CSV = _P.REPO_ROOT / "outputs/classification/omission_grand_units.csv"
OUT_DIR = _P.REPO_ROOT / "outputs/within_session_spk_spk_sliding_corr"

N_GOOD_UNITS = 6
MIN_FIRING_RATE_HZ = 1.0
COND = "RXRR"
WIN_S = (0.0, 3.0)          # matches the LFP script's (0, 3000) ms window, re: p1 onset
BIN_MS = 10.0


def good_units_per_area(units_df, session):
    sub = units_df[(units_df.session == session) & (units_df.firing_rate >= MIN_FIRING_RATE_HZ)].copy()
    sub["score"] = sub["firing_rate"] * (1.0 - sub["q1_p"].clip(0, 1))
    out = {}
    for area, g in sub.groupby("area10"):
        top = g.sort_values("score", ascending=False).head(N_GOOD_UNITS)
        out[area] = list(zip(top["unit_row"].astype(int), top["score"]))
    return out


def main(limit_sessions=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    units_df = pd.read_csv(UNITS_CSV)
    sessions = sorted(units_df.session.unique())
    if limit_sessions:
        sessions = sessions[:limit_sessions]

    win_half_bins = int(round(WIN_HALF_MS / BIN_MS))
    step_bins = int(round(STEP_MS / BIN_MS))

    index_rows = []
    t0 = time.time()
    for si, session in enumerate(sessions, 1):
        candidates = [os.path.join(NWB_DIR, f"{session}_rec.nwb"),
                     os.path.join(NWB_DIR, f"{session}.nwb")]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if path is None:
            continue
        try:
            sess = oa.read(path)
        except Exception:
            continue
        onsets = precompute_condition_onsets(sess, correct_only=True)
        trial_starts = onsets.get(COND, np.array([]))
        if len(trial_starts) < 3:
            continue

        good = good_units_per_area(units_df, session)
        areas_present = list(good)
        if len(areas_present) < 1:
            continue

        rates = {}
        for a in areas_present:
            for unit_row, _score in good[a]:
                try:
                    st = sess.get_spike_times(unit_row)
                except Exception:
                    continue
                if st is None or len(st) == 0:
                    continue
                binned = bin_spikes(st, window=WIN_S, bin_size_ms=BIN_MS,
                                    trial_starts=trial_starts, output="rate")
                rates[(a, unit_row)] = binned

        pairs = []
        for a in areas_present:
            units_here = [u for u, _ in good[a] if (a, u) in rates]
            for u1, u2 in combinations(units_here, 2):
                pairs.append(("within_area", a, u1, a, u2))
        for a1, a2 in combinations(areas_present, 2):
            u1s = [u for u, _ in good[a1] if (a1, u) in rates]
            u2s = [u for u, _ in good[a2] if (a2, u) in rates]
            for u1, u2 in product(u1s, u2s):
                pairs.append(("between_area", a1, u1, a2, u2))

        if not pairs:
            continue
        n_t = rates[list(rates)[0]].shape[1]
        n_windows = len(np.arange(win_half_bins, n_t - win_half_bins, step_bins))
        results = np.full((len(pairs), n_windows), np.nan, dtype=np.float32)
        null_mean = np.full((len(pairs), n_windows), np.nan, dtype=np.float32)
        null_std = np.full((len(pairs), n_windows), np.nan, dtype=np.float32)
        n_trials_used = np.zeros(len(pairs), dtype=np.int32)

        for pi, (scope, a1, u1, a2, u2) in enumerate(pairs):
            x, y = rates[(a1, u1)], rates[(a2, u2)]
            n_tr = min(x.shape[0], y.shape[0])
            real, null, centers = sliding_corr_same_trial(x[:n_tr], y[:n_tr],
                                                           win_half_bins, step_bins)
            nw = min(real.shape[1], n_windows)
            results[pi, :nw] = np.nanmean(real[:, :nw], axis=0)
            null_mean[pi, :nw] = null[:, :nw].mean(axis=0)
            null_std[pi, :nw] = null[:, :nw].std(axis=0)
            n_trials_used[pi] = n_tr

        np.savez_compressed(
            os.path.join(OUT_DIR, f"{session}.npz"),
            real=results, null_mean=null_mean, null_std=null_std,
            n_trials=n_trials_used, centers_ms=centers.astype(np.float32) * BIN_MS,
            pairs=np.array([f"{s}|{a1}|{u1}|{a2}|{u2}" for s, a1, u1, a2, u2 in pairs]))
        index_rows.append({"session": session, "n_pairs": len(pairs),
                           "areas": areas_present, "n_windows": n_windows})
        print(f"[{datetime.now():%H:%M:%S}] session {si}/{len(sessions)} ({session}), "
             f"{len(pairs)} pairs, {time.time()-t0:.0f}s total", flush=True)

    pd.DataFrame(index_rows).to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Within-session, trial-matched sliding-window SPK-SPK correlation, same "
                  "design/engine as the LFP-LFP script, unit spike rate instead of band power.",
        "n_good_units_per_area": N_GOOD_UNITS, "min_firing_rate_hz": MIN_FIRING_RATE_HZ,
        "condition": COND, "window_s_re_p1": list(WIN_S), "bin_ms": BIN_MS,
        "sliding_half_width_ms": WIN_HALF_MS, "sliding_step_ms": STEP_MS,
        "n_sessions_processed": len(index_rows),
        "runtime_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {OUT_DIR}/ ({len(index_rows)} sessions), index.csv, receipt.json")


if __name__ == "__main__":
    main(limit_sessions=int(sys.argv[1]) if len(sys.argv) > 1 else None)
