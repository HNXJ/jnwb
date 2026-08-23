r"""
Within-session, trial-matched sliding-window LFP-LFP correlation -- fig05's new relationship
analysis (2026-08-05), replacing the pool-before-test connectivity methods (coherency/Granger/
TE, all null 0/240-0/150) with a design that tests significance WITHIN each session first, per
explicit user direction. See feedback_pool_after_testing_not_before memory / this project's
own repeated failure this week for why.

DESIGN
    Per session, per pair of "good" channels (see below), per band, per sliding window position:
    correlate channel_N[trial K, window] against channel_M[trial K, window] -- same trial, same
    window, across the SET of trials within that session (n_trials correlation values per
    window). Null: channel_N[trial K] against channel_M[trial J != K] (trial-mismatch shuffle,
    N_SHUFFLE=200), same logic as jnwb.connectivity._surrogate_source. Window +-200ms, 10ms
    step (scripts/smoke_test_sliding_trial_correlation.py validated this design and its
    vectorized implementation -- reused here directly, not reimplemented).

SCOPE ORDER (this script: step 1 and 2 of 3)
    1. Within session, within area/probe: pairs among a session's own "good" channels in the
       SAME area (local/microcircuit coupling).
    2. Within session, between area/probe: pairs of "good" channels across DIFFERENT areas
       (long-range coupling).
    Step 3 (cross-session generalization, accepting partial area-pair coverage) is a separate
    aggregation script run AFTER this one, once every session's own significance decision
    exists -- see feedback_pool_after_testing_not_before: pool after testing, not before.

"GOOD" CHANNEL SELECTION
    Per area per session, rank channels by a band-averaged SNR-like score from the EXISTING
    channel_band_power_v2 census (no new computation): mean over the 5 bands of
    |db_mid_omirel| / (db_mid_omirel_sd / sqrt(n_trials)). Top N_GOOD_CHANNELS per area.

CONDITION
    RXRR only for this first pass (matches fig04/05's existing p2-omission scope). The R/A/B-
    family slot realignment from PLAN_sliding_window_connectivity.md is a stated follow-up, not
    done in this first build -- flagged, not silently skipped.

OUTPUT
    outputs/within_session_lfp_lfp_sliding_corr/<session>.npz  per session, checkpointed
        immediately after that session finishes -- z: (n_pairs, n_bands, n_windows) array,
        pairs: list of (scope, areaA, chA, areaB, chB) tuples, centers_ms, band names
    outputs/within_session_lfp_lfp_sliding_corr/index.csv
    outputs/within_session_lfp_lfp_sliding_corr/receipt.json
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from itertools import combinations, product

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smoke_test_sliding_trial_correlation import (  # noqa: E402
    band_power_trace, sliding_corr_same_trial, WIN_HALF_MS, STEP_MS, BIN_MS, N_SHUFFLE,
)
from jnwb import paths as _P
from jnwb.spectral import CANONICAL_BANDS as BANDS

TFR_DIR = _P.tfr_dir()
CENSUS = _P.REPO_ROOT / "outputs/lfp_band_census_v2/channel_band_power.csv.gz"
AREA_VEC = _P.REPO_ROOT / "outputs/channel_area_vector/channel_area_vector.csv"
OUT_DIR = _P.REPO_ROOT / "outputs/within_session_lfp_lfp_sliding_corr"

N_GOOD_CHANNELS = 6
COND = "RXRR"
AREA_POOL = {"V3": "V3a/d", "V3a": "V3a/d", "V3d": "V3a/d"}
WIN_MS = (0, 3000)           # analysis window re: p1 onset for this first pass (fx-p1-d1-p2)

FNAME_RE = re.compile(r"^sub-(?P<subject>.+?)_ses-(?P<session>.+?)-(?P<probe>[A-Z])-"
                      r"(?P<area>.+)-(?P<cond>[A-Z]+)$")


def good_channels_per_area(census_df, session_prefix):
    sub = census_df[census_df.session_prefix == session_prefix].copy()
    sub["t_like"] = sub["db_mid_omirel"].abs() / (
        sub["db_mid_omirel_sd"] / np.sqrt(sub["n_trials"].clip(lower=1)))
    out = {}
    for area, g in sub.groupby("area"):
        score = g.groupby("channel")["t_like"].mean().sort_values(ascending=False)
        out[area] = score.index[:N_GOOD_CHANNELS].to_numpy()
    return out


def main(limit_sessions=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    census = pd.read_csv(CENSUS)
    sessions = sorted(census.session_prefix.unique())
    if limit_sessions:
        sessions = sessions[:limit_sessions]

    i0 = int(round((WIN_MS[0] - (-1000.0)) / BIN_MS))
    i1 = int(round((WIN_MS[1] - (-1000.0)) / BIN_MS))
    win_half_bins = int(round(WIN_HALF_MS / BIN_MS))
    step_bins = int(round(STEP_MS / BIN_MS))

    index_rows = []
    t0 = time.time()
    for si, session in enumerate(sessions, 1):
        good = good_channels_per_area(census, session)
        if len(good) < 1:
            continue

        # locate this session's RXRR files, one per (probe, area)
        files = {}
        sess_tag = session.split("sub-")[1] if "sub-" in session else session
        for f in glob.glob(os.path.join(TFR_DIR, f"*{sess_tag}*-{COND}.npy")):
            m = FNAME_RE.match(os.path.basename(f)[:-4])
            if not m:
                continue
            area10 = AREA_POOL.get(m["area"], m["area"])
            files[area10] = f  # last one wins if duplicate area token in one session

        areas_present = [a for a in good if a in files]
        if len(areas_present) < 1:
            continue

        loaded = {}
        for a in areas_present:
            try:
                loaded[a] = np.load(files[a], mmap_mode="r")
            except Exception:
                continue

        pairs = []
        # ---- scope 1: within area ----
        for a in areas_present:
            chans = good[a]
            for c1, c2 in combinations(chans, 2):
                pairs.append(("within_area", a, int(c1), a, int(c2)))
        # ---- scope 2: between area ----
        for a1, a2 in combinations(areas_present, 2):
            for c1, c2 in product(good[a1], good[a2]):
                pairs.append(("between_area", a1, int(c1), a2, int(c2)))

        n_windows = len(np.arange(win_half_bins, (i1 - i0) - win_half_bins, step_bins))
        band_names = list(BANDS)
        results = np.full((len(pairs), len(band_names), n_windows), np.nan, dtype=np.float32)
        null_mean = np.full((len(pairs), len(band_names), n_windows), np.nan, dtype=np.float32)
        null_std = np.full((len(pairs), len(band_names), n_windows), np.nan, dtype=np.float32)
        n_trials_used = np.zeros(len(pairs), dtype=np.int32)

        for pi, (scope, a1, c1, a2, c2) in enumerate(pairs):
            arr1, arr2 = loaded.get(a1), loaded.get(a2)
            if arr1 is None or arr2 is None:
                continue
            n1 = min(arr1.shape[3], i1) - i0
            n2 = min(arr2.shape[3], i1) - i0
            n = min(n1, n2)
            if n < 2 * win_half_bins + step_bins:
                continue
            n_tr = min(arr1.shape[0], arr2.shape[0])
            for bi, (lo, hi) in enumerate(BANDS.values()):
                x = band_power_trace(arr1[:n_tr], [c1], (lo, hi), i0, i0 + n)[:, 0, :]
                y = band_power_trace(arr2[:n_tr], [c2], (lo, hi), i0, i0 + n)[:, 0, :]
                real, null, centers = sliding_corr_same_trial(x, y, win_half_bins, step_bins)
                nw = min(real.shape[1], n_windows)
                results[pi, bi, :nw] = np.nanmean(real[:, :nw], axis=0)
                null_mean[pi, bi, :nw] = null[:, :nw].mean(axis=0)
                null_std[pi, bi, :nw] = null[:, :nw].std(axis=0)
            n_trials_used[pi] = n_tr

        np.savez_compressed(
            os.path.join(OUT_DIR, f"{session}.npz"),
            real=results, null_mean=null_mean, null_std=null_std,
            n_trials=n_trials_used, centers_ms=centers.astype(np.float32) * BIN_MS + WIN_MS[0],
            bands=np.array(band_names),
            pairs=np.array([f"{s}|{a1}|{c1}|{a2}|{c2}" for s, a1, c1, a2, c2 in pairs]))
        index_rows.append({"session": session, "n_pairs": len(pairs),
                           "areas": list(areas_present), "n_windows": n_windows})
        print(f"[{datetime.now():%H:%M:%S}] session {si}/{len(sessions)} ({session}), "
             f"{len(pairs)} pairs, {time.time()-t0:.0f}s total", flush=True)

    pd.DataFrame(index_rows).to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Within-session, trial-matched sliding-window LFP-LFP correlation, "
                  "within-area and between-area 'good' channel pairs. Step 1-2 of 3 (see "
                  "module docstring); cross-session generalization is a separate script.",
        "n_good_channels_per_area": N_GOOD_CHANNELS, "condition": COND,
        "window_ms_re_p1": list(WIN_MS), "sliding_half_width_ms": WIN_HALF_MS,
        "sliding_step_ms": STEP_MS, "n_shuffle": N_SHUFFLE, "bands_hz": BANDS,
        "n_sessions_processed": len(index_rows),
        "not_yet_done": "R/A/B-family slot realignment "
                        "(PLAN_sliding_window_connectivity.md) -- RXRR-only for this pass",
        "runtime_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {OUT_DIR}/ ({len(index_rows)} sessions), index.csv, receipt.json")


if __name__ == "__main__":
    main(limit_sessions=int(sys.argv[1]) if len(sys.argv) > 1 else None)
