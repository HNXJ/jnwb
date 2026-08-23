r"""
Within-session, trial-matched LEAD/LAG correlation between population firing rate of two
(area, functional_group) nodes -- replaces directed Granger causality as fig06's SPK-SPK
method (2026-08-06 direction: "keep Granger for LFP, use sliding correlation for SPK-SPK").
Granger stays fig05's LFP-LFP method; this is SPK-SPK, node-for-node with
extract_population_firing_lfp_power_corr.py's (area, func_group) definition, not per-unit.

QUESTION
    Is there a lead/lag relationship -- not just a same-time relationship -- between the
    population firing of two (area, functional_type) nodes, within session, across baseline,
    stim and omission windows? "Lead/lag" here means: does node A's activity at time t predict
    node B's activity at time t + lag better than at lag 0, for some nonzero lag?

DESIGN
    Reuses smoke_test_sliding_trial_correlation.lagged_corr_same_trial(), which holds node A's
    window fixed and slides node B's window across a range of lags, trial by trial (same trial
    K throughout -- never correlating trial K of A against trial J of B for the REAL estimate).
    Null: the same trial-mismatch shuffle already validated for every other sliding-window
    analysis this project has built (A's trial K against B's trial J != K, at every lag) --
    breaks the true within-trial lead/lag relationship while preserving each node's own
    trial-to-trial structure. Real vs null gives Z(lag) per pair; the pair's peak |Z| lag and
    its sign is the lead/lag call (lag > 0: A leads B; lag < 0: B leads A).

    LAG RANGE: +-100 ms, 10 ms steps (21 lags) -- deliberately narrower than the LFP-LFP script's
    +-200 ms sliding-WINDOW-position range, because this is a lag axis over a much shorter
    per-condition window (stim/omission ~530 ms), not a window slid across a multi-second trial.
    Each node's rate trace is extracted with 100 ms of extra margin on both sides
    (jnwb.connectivity.bin_spikes with a widened window) specifically so a shifted node-B
    window never runs past what was actually extracted.

NODES: (area10, functional_group) -- SAME DEFINITION AS THE LFP-POWER SCRIPT
    Reuses extract_population_firing_lfp_power_corr.build_functional_groups() and
    CONDITION_GROUPS verbatim (import, not reimplementation) -- S+ (S+/S++), S- (S-/S--), O+
    (O+/O++), Other (not functionally part of S+/S-/O+); baseline/stim/omission windows identical to that script's. A node needs
    >=MIN_UNITS_PER_GROUP qualifying units (firing_rate >= MIN_FIRING_RATE_HZ) to be included.

SCOPE (this pass)
    within_area  : pairs of DIFFERENT functional groups in the SAME area (same-group same-area
                   would be a trivial autocorrelation, excluded)
    between_area : any functional-group pair across DIFFERENT areas

OUTPUT
    outputs/population_spk_spk_lag_corr/<session>.npz
    outputs/population_spk_spk_lag_corr/index.csv
    outputs/population_spk_spk_lag_corr/receipt.json
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
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
sys.path.insert(0, SCRIPTS)
import omission as oa  # noqa: E402
from omission.jnwb_ext.unit_classification import precompute_condition_onsets  # noqa: E402
from jnwb.connectivity import bin_spikes  # noqa: E402
from extract_population_firing_lfp_power_corr import (  # noqa: E402
    build_functional_groups, CONDITION_GROUPS, UNITS_CSV, MIN_FIRING_RATE_HZ, MIN_UNITS_PER_GROUP,
)
from smoke_test_sliding_trial_correlation import lagged_corr_same_trial, N_SHUFFLE  # noqa: E402
from jnwb import paths as _P

NWB_DIR = _P.nwb_dir()
OUT_DIR = _P.REPO_ROOT / "outputs/population_spk_spk_lag_corr"

BIN_MS = 10.0
MAX_LAG_MS = 100.0
LAG_STEP_MS = 10.0
PAD_MS = MAX_LAG_MS


def main(limit_sessions=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    units_df = pd.read_csv(UNITS_CSV)
    units_df = build_functional_groups(units_df)
    sessions = sorted(units_df.session.unique())
    if limit_sessions:
        sessions = sessions[:limit_sessions]

    pad_bins = int(round(PAD_MS / BIN_MS))
    lag_step_bins = int(round(LAG_STEP_MS / BIN_MS))

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
        sess_units = units_df[units_df.session == session]

        cg_rows = []
        for cg_name, (cond, win_ms) in CONDITION_GROUPS.items():
            trial_starts = onsets.get(cond, np.array([]))
            if len(trial_starts) < 5:
                continue
            win_len_core = int(round((win_ms[1] - win_ms[0]) / BIN_MS))
            padded_win_s = ((win_ms[0] - PAD_MS) / 1000.0, (win_ms[1] + PAD_MS) / 1000.0)

            rates = {}
            for area, garea in sess_units[sess_units.firing_rate >= MIN_FIRING_RATE_HZ] \
                    .groupby("area10"):
                for fgroup, gfg in garea.groupby("func_group"):
                    if fgroup not in ("S+", "S-", "O+", "Other") or len(gfg) < MIN_UNITS_PER_GROUP:
                        continue
                    unit_rates = []
                    for unit_row in gfg.unit_row:
                        try:
                            st = sess.get_spike_times(int(unit_row))
                        except Exception:
                            continue
                        if st is None or len(st) == 0:
                            continue
                        binned = bin_spikes(st, window=padded_win_s, bin_size_ms=BIN_MS,
                                            trial_starts=trial_starts, output="rate")
                        unit_rates.append(binned)
                    if len(unit_rates) < MIN_UNITS_PER_GROUP:
                        continue
                    n_tr = min(r.shape[0] for r in unit_rates)
                    n_bins = min(r.shape[1] for r in unit_rates)
                    pop_rate = np.nanmean(
                        np.stack([r[:n_tr, :n_bins] for r in unit_rates]), axis=0)
                    rates[(area, fgroup)] = pop_rate

            nodes = list(rates)
            pairs = []
            for a1, a2 in combinations(nodes, 2):
                if a1[0] == a2[0] and a1[1] == a2[1]:
                    continue
                scope = "within_area" if a1[0] == a2[0] else "between_area"
                pairs.append((scope, a1, a2))
            if not pairs:
                continue

            n_lags = 2 * pad_bins // lag_step_bins + 1
            results = np.full((len(pairs), n_lags), np.nan, dtype=np.float32)
            null_mean = np.full((len(pairs), n_lags), np.nan, dtype=np.float32)
            null_std = np.full((len(pairs), n_lags), np.nan, dtype=np.float32)
            n_trials_used = np.zeros(len(pairs), dtype=np.int32)

            for pi, (scope, n1, n2) in enumerate(pairs):
                x, y = rates[n1], rates[n2]
                n_tr = min(x.shape[0], y.shape[0])
                exp_len = win_len_core + 2 * pad_bins
                if x.shape[1] < exp_len or y.shape[1] < exp_len:
                    continue
                real, null, lags = lagged_corr_same_trial(
                    x[:n_tr, :exp_len], y[:n_tr, :exp_len], win_len_core, pad_bins,
                    lag_step_bins=lag_step_bins, n_shuffle=N_SHUFFLE)
                results[pi] = np.nanmean(real, axis=0)
                null_mean[pi] = null.mean(axis=0)
                null_std[pi] = null.std(axis=0)
                n_trials_used[pi] = n_tr

            cg_rows.append({
                "cg": cg_name,
                "pairs": np.array([f"{sc}|{n1[0]}|{n1[1]}|{n2[0]}|{n2[1]}"
                                   for sc, n1, n2 in pairs]),
                "real": results, "null_mean": null_mean, "null_std": null_std,
                "n_trials": n_trials_used, "lags_ms": (lags * BIN_MS).astype(np.float32),
            })

        if not cg_rows:
            continue
        save_kwargs = {}
        for r in cg_rows:
            save_kwargs[f"{r['cg']}_pairs"] = r["pairs"]
            save_kwargs[f"{r['cg']}_real"] = r["real"]
            save_kwargs[f"{r['cg']}_null_mean"] = r["null_mean"]
            save_kwargs[f"{r['cg']}_null_std"] = r["null_std"]
            save_kwargs[f"{r['cg']}_n_trials"] = r["n_trials"]
            save_kwargs[f"{r['cg']}_lags_ms"] = r["lags_ms"]
        np.savez_compressed(os.path.join(OUT_DIR, f"{session}.npz"), **save_kwargs)
        n_pairs_total = sum(len(r["pairs"]) for r in cg_rows)
        index_rows.append({"session": session, "n_condition_groups": len(cg_rows),
                           "n_pairs_total": n_pairs_total})
        print(f"[{datetime.now():%H:%M:%S}] session {si}/{len(sessions)} ({session}), "
             f"{n_pairs_total} pairs x {len(cg_rows)} condition groups, "
             f"{time.time()-t0:.0f}s total", flush=True)

    pd.DataFrame(index_rows).to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Within-session, trial-matched lead/lag correlation between population "
                  "firing rate of (area, functional_group) node pairs -- replaces directed "
                  "Granger as fig06's SPK-SPK method; Granger unchanged for fig05 LFP-LFP.",
        "nodes": "(area10, func_group in S+/S-/O+/Other), reused verbatim from "
                "extract_population_firing_lfp_power_corr.build_functional_groups",
        "condition_groups": {k: {"nwb_condition": v[0], "window_ms_re_p1": list(v[1])}
                             for k, v in CONDITION_GROUPS.items()},
        "lag_range_ms": [-MAX_LAG_MS, MAX_LAG_MS], "lag_step_ms": LAG_STEP_MS,
        "pad_ms_each_side": PAD_MS, "bin_ms": BIN_MS, "n_shuffle": N_SHUFFLE,
        "min_firing_rate_hz": MIN_FIRING_RATE_HZ, "min_units_per_group": MIN_UNITS_PER_GROUP,
        "lag_sign_convention": "lag > 0: first-listed node leads second-listed node "
                               "(second node's LATER activity resembles first node's now)",
        "n_sessions_processed": len(index_rows),
        "runtime_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {OUT_DIR}/ ({len(index_rows)} sessions), index.csv, receipt.json")


if __name__ == "__main__":
    main(limit_sessions=int(sys.argv[1]) if len(sys.argv) > 1 else None)
