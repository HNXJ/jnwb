"""Nested-CV re-run of the V182o SPK-LFP pilot with sensitivity + positive controls
(2026-08-29, Hamm).

Re-run matrix, per cell (cell = unit x band x condition x channel_control):

    fixed        past LFP, alpha = 1                 historical reference
    nested       past LFP, alpha tuned in-fold       PRIMARY ESTIMATOR
    concurrent   post-event LFP                      sensitivity / contemporaneous association
    permuted     past LFP, trials shuffled           NEGATIVE control (defines the null floor)
    inject_<b>   past LFP + known injected effect    POSITIVE sensitivity control, beta sweep

Every arm retains per-fold R^2 for M2 and M3, per-fold delta, and the per-fold selected alpha.

Identity: units are keyed by (session_id, unit_row_idx); the kilosort unit_id column is carried
as raw_unit_id and is LOCAL METADATA, never a join key. Gates in
omission.jnwb_ext.canonical_identity.

Run:
  OMISSION_NWB_DIR=... .venv/Scripts/python.exe \
    -m omission.scripts.dev_spk_lfp_nested_rerun_20260829 [--max-units N] [--bands a,b] \
    [--controls c0_own,c1_own_excluded]
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

logging.disable(logging.INFO)

from jnwb.paths import nwb_dir  # noqa: E402
from omission.jnwb_ext.analog import load_analog_epochs  # noqa: E402
from omission.jnwb_ext.canonical_identity import attach_unit_identity  # noqa: E402
from omission.jnwb_ext.causal_signal import BANDS  # noqa: E402
from omission.jnwb_ext.session import OmissionSession  # noqa: E402
from omission.jnwb_ext.spk_lfp_nested import (  # noqa: E402
    BETA_LEVELS, all_arms, lead_interval_features,
)
from omission.jnwb_ext.spk_lfp_pilot import (  # noqa: E402
    LAG_INTERVALS_MS, band_envelope_trials, band_temporal_support, lag_interval_features,
    electrode_probe_sequence, electrode_row_count, resolve_channel_sets,
    spike_counts_in_window, valid_from_ms,
)
from omission.scripts.dev_spk_lfp_pilot_v182o_20260829 import (  # noqa: E402
    CLASS_CSV as PILOT_CLASS_CSV, HISTORY_MS, RESPONSE_MS, SESSION as PILOT_SESSION,
    WINDOW_MS, build_condition_events,
)

# Slot times used by build_condition_events (p2 1031, p3 2062, p4 3093 ms) are CORPUS
# CONSTANTS from sequence_layout.EPOCH_ONSETS_MS, not session-specific -- verified before
# applying this driver to a second subject.
DEFAULT_OUT_STEM = "spk_lfp_nested_v182o_260702"

ARMS = ["fixed", "nested", "concurrent", "permuted"] + [f"inject_{b:g}" for b in BETA_LEVELS]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-units", type=int, default=40)
    ap.add_argument("--bands", type=str, default="theta,alpha,beta,low_gamma,high_gamma")
    ap.add_argument("--controls", type=str, default="C0_own,C1_own_excluded")
    ap.add_argument("--session", type=str, default=PILOT_SESSION)
    ap.add_argument("--class-csv", type=str, default=None,
                    help="unit-classification table; defaults to the pilot's for the pilot "
                         "session, else unitclass_<session>.csv from dev_build_unitclass")
    ap.add_argument("--out-stem", type=str, default=None)
    args = ap.parse_args()

    SESSION = args.session
    CLASS_CSV = (Path(args.class_csv) if args.class_csv
                 else (PILOT_CLASS_CSV if SESSION == PILOT_SESSION
                       else Path(f"omission/artifacts/data/unitclass_{SESSION}.csv")))
    stem = args.out_stem or (DEFAULT_OUT_STEM if SESSION == PILOT_SESSION
                             else f"spk_lfp_nested_{SESSION}")
    OUT_CSV = Path(f"omission/artifacts/data/{stem}_cells.csv")
    OUT_FOLDS = Path(f"omission/artifacts/data/{stem}_folds.csv")
    OUT_JSON = Path(f"omission/artifacts/.lab/{stem.replace('_', '-')}-20260829.json")
    if not CLASS_CSV.exists():
        raise SystemExit(
            f"classification table missing: {CLASS_CSV}\n"
            f"Build it first:  python -m omission.scripts.dev_build_unitclass_20260829 "
            f"--session {SESSION}")
    print(f"session {SESSION}\n  class table {CLASS_CSV}\n  out {OUT_CSV}", flush=True)

    bands = [b.strip() for b in args.bands.split(",") if b.strip() in BANDS]
    # ChannelSets.as_dict() keys are C0_own / C1_own_excluded / C2_nearby / C3_distant.
    controls = {c.strip().lower() for c in args.controls.split(",") if c.strip()}
    path = Path(nwb_dir()) / f"{SESSION}.nwb"

    cls = pd.read_csv(CLASS_CSV).set_index("unit_id")
    session = OmissionSession(str(path))

    # Canonical unit identity, taken from the UNFILTERED units frame so row positions still
    # correspond to NWB Units rows.
    ident = attach_unit_identity(session._units_df, SESSION)[
        ["session_id", "unit_row_idx", "probe", "raw_unit_id"]
    ].set_index("unit_row_idx")

    print(f"Loading LFP {WINDOW_MS} ms ...", flush=True)
    batch = load_analog_epochs(path, signal_class="LFP", alignment="p1", window_ms=WINDOW_MS,
                               correct_only=True, missing_data="drop")
    sm = batch.signal_metadata.reset_index(drop=True)
    tm = batch.trial_metadata.reset_index(drop=True)
    time_ms = np.asarray(batch.time_ms, dtype=float)
    assert tm["trial_id"].nunique() == len(tm), "canonical trial identity violated in input"

    # Canonical channel identity is (session, electrode row). Assert signal_metadata is COMPLETE
    # so row position still indexes the electrodes table -- see resolve_channel_sets.
    n_electrodes = electrode_row_count(path)
    electrode_probes = electrode_probe_sequence(path)
    print(f"  electrodes {n_electrodes}; signal_metadata rows {len(sm)}", flush=True)
    print(f"  LFP {batch.data.shape}; {len(tm)} trials", flush=True)

    onsets_s = tm["source_onset_s"].to_numpy(dtype=float)
    events = build_condition_events(session, tm)

    units = cls[cls["stable_plus"] == True]  # noqa: E712
    rare = units[units["functional_class"].isin(["O+", "O++"])]
    rest = units[~units["functional_class"].isin(["O+", "O++"])].sort_values(
        "firing_rate", ascending=False).head(max(args.max_units - len(rare), 0))
    units = pd.concat([rare, rest])
    print(f"  units: {len(units)} {units['functional_class'].value_counts().to_dict()}", flush=True)

    supports = {b: band_temporal_support(b) for b in bands}
    rows: list[dict] = []
    fold_rows: list[dict] = []
    t0 = time.time()

    for band in bands:
        transient_end = valid_from_ms(supports[band], WINDOW_MS[0])
        print(f"\n[{band}] valid from {transient_end:.0f} ms", flush=True)
        env_cache: dict[int, np.ndarray] = {}

        for n_u, (uid, urow) in enumerate(units.iterrows(), 1):
            chans = resolve_channel_sets(sm, int(urow["peak_channel_id"]),
                                          n_electrodes=n_electrodes,
                                          electrode_probes=electrode_probes)
            if chans is None:
                continue
            spikes = session.get_spike_times(int(uid))
            if spikes is None or len(spikes) < 200:
                continue
            spikes = np.sort(np.asarray(spikes, dtype=float))
            idrow = ident.loc[int(uid)]

            for ctrl_name, ch_idx in chans.as_dict().items():
                if ctrl_name.lower() not in controls or len(ch_idx) == 0:
                    continue
                use = ch_idx if len(ch_idx) <= 8 else ch_idx[:: max(1, len(ch_idx) // 8)][:8]
                key = hash(tuple(sorted(use.tolist())))
                if key not in env_cache:
                    lfp = batch.data[:, use, :].mean(axis=1).astype(float)
                    env_cache[key], _ = band_envelope_trials(lfp, band)
                env = env_cache[key]

                for cond, spec in events.items():
                    ev_ms, mask = spec["event_ms"], spec["mask"]
                    if mask.sum() < 60:
                        continue
                    if ev_ms - LAG_INTERVALS_MS[-1][1] < transient_end:
                        continue

                    lagf = lag_interval_features(env[mask], time_ms, ev_ms)
                    leadf = lead_interval_features(env[mask], time_ms, ev_ms)
                    ev_onsets = onsets_s[mask] + ev_ms / 1000.0
                    y = spike_counts_in_window(spikes, ev_onsets, *RESPONSE_MS)
                    hist = spike_counts_in_window(spikes, ev_onsets, *HISTORY_MS)

                    arms = all_arms(lagf, leadf, hist, y, seed=0)

                    base = {
                        "session_id": SESSION, "unit_row_idx": int(uid),
                        "probe": idrow["probe"], "raw_unit_id": int(idrow["raw_unit_id"]),
                        "area": urow["area"], "layer": urow.get("layer", ""),
                        "functional_class": urow["functional_class"],
                        "band": band, "condition": cond, "channel_control": ctrl_name,
                        "n_trials": int(mask.sum()),
                        "effective_latency_ms": supports[band]["effective_latency_ms"],
                    }
                    row = dict(base)
                    for arm in ARMS:
                        a = arms[arm]
                        row[f"{arm}__delta"] = a["delta_pooled"]
                        row[f"{arm}__delta_fold_median"] = a["delta_fold_median"]
                        row[f"{arm}__delta_fold_sd"] = a["delta_fold_sd"]
                        row[f"{arm}__frac_folds_positive"] = a["frac_folds_positive"]
                        row[f"{arm}__r2_m2"] = a["r2_m2_pooled"]
                        row[f"{arm}__r2_m3"] = a["r2_m3_pooled"]
                        row[f"{arm}__alpha_m2"] = a["alpha_m2_median"]
                        row[f"{arm}__alpha_m3"] = a["alpha_m3_median"]
                        row[f"{arm}__n_used"] = a["n_trials_used"]
                    rows.append(row)

                    # per-fold detail for the two arms that carry the interpretation
                    for arm in ("nested", "permuted"):
                        a = arms[arm]
                        fold_rows.append({**base, "arm": arm,
                                          "delta_fold_median": a["delta_fold_median"],
                                          "delta_fold_sd": a["delta_fold_sd"],
                                          "delta_fold_min": a["delta_fold_min"],
                                          "delta_fold_max": a["delta_fold_max"],
                                          "frac_folds_positive": a["frac_folds_positive"],
                                          "alpha_m2": a["alpha_m2_median"],
                                          "alpha_m3": a["alpha_m3_median"]})
            if n_u % 10 == 0:
                print(f"    {n_u}/{len(units)} units  ({time.time()-t0:.0f}s, "
                      f"{len(rows)} cells)", flush=True)

    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    pd.DataFrame(fold_rows).to_csv(OUT_FOLDS, index=False)
    print(f"\nWrote {OUT_CSV} ({len(df)} cells) and {OUT_FOLDS}")

    # ---- detection against the PERMUTED null floor, stratified by trial count ---------------
    detection = {}
    if not df.empty:
        df["n_bin"] = np.where(df["n_trials"] > 700, "high_n", "low_n")
        for nb, g in df.groupby("n_bin"):
            floor = float(np.nanquantile(g["permuted__delta"], 0.95))
            detection[nb] = {
                "n_cells": int(len(g)),
                "median_n_trials": float(g["n_trials"].median()),
                "permuted_null_floor_q95": floor,
                "permuted_median": float(np.nanmedian(g["permuted__delta"])),
                "detection_rate_vs_floor": {
                    arm: float(np.nanmean(g[f"{arm}__delta"] > floor)) for arm in ARMS
                },
                "median_delta": {arm: float(np.nanmedian(g[f"{arm}__delta"])) for arm in ARMS},
            }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "schema_version": 3,
        "id": OUT_JSON.stem,
        "kind": "evidence",
        "title": "Nested-CV incremental predictive dependence with sensitivity and injected positive controls",
        "status": "provisional",
        "estimand": ("Incremental predictive dependence of subsequent firing on PAST band-specific "
                     "LFP state, beyond spike history. NOT causal, NOT directional."),
        "session": SESSION,
        "arms": {
            "fixed": "alpha=1, historical reference",
            "nested": "PRIMARY: alpha tuned by RidgeCV LOO-GCV inside each training fold, M2 and M3 independently",
            "concurrent": "post-event LFP; SENSITIVITY control only -- shares instantaneous common drive and possible spike contamination, so it is NOT a positive control for past dependence",
            "permuted": "past LFP with trial correspondence destroyed; NEGATIVE control, defines the null floor",
            "injected": "y + beta*sd(y)*z(L@w) using the cell's OWN real lag features; POSITIVE sensitivity control",
        },
        "injection_geometry_caveat": ("Equal weights across the four lag intervals is the most "
                                      "detectable geometry, so detection rates reported here are an "
                                      "UPPER BOUND on this pipeline's sensitivity."),
        "detection_rule": ("An arm is 'detected' in a cell when its pooled delta exceeds the 95th "
                           "percentile of the PERMUTED arm's delta within the same trial-count "
                           "stratum. Zero is NOT the null: the overfitting penalty puts the null "
                           "floor below zero, and the permuted arm measures where."),
        "beta_levels": list(BETA_LEVELS),
        "window_ms": list(WINDOW_MS), "response_ms": list(RESPONSE_MS),
        "history_ms": list(HISTORY_MS),
        "lag_intervals_ms": [list(x) for x in LAG_INTERVALS_MS],
        "bands": bands, "controls": sorted(controls),
        "n_cells": int(len(df)),
        "runtime_s": round(time.time() - t0, 1),
        "detection_by_trial_count": detection,
    }, indent=2))
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
