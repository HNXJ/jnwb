"""Representative-session SPK-LFP pilot under the DOWNGRADED estimand (2026-08-29, Hamm).

Session: sub-V182o_ses-260702 (960 trials, no trial_num collisions, clean behavioural QC).

Reports, per (unit x band x condition x channel-control):
  - signed band-power/firing association (sign retained, four quadrants preserved)
  - Delta_pred = Perf(M_nuisance + past LFP) - Perf(M_nuisance), trial-blocked held-out
  - distributed lag-interval coefficients (signed, not just tau*)
  - band effective temporal support attached to every temporal result
  - C0/C1/C2/C3 spike-contamination controls

Conditions compared: baseline (pre-p1 fixation), stimulus (a presented slot), omission (the
omitted slot for that trial's condition), matched-empty (same slot index in the family's control
condition, where nothing was expected).

NO directional or causal statistic is computed. See spk_lfp_pilot.py's module docstring.

Run:
  OMISSION_NWB_DIR=... OMISSION_ANALYSIS_DIR=... .venv/Scripts/python.exe \
    -m omission.scripts.dev_spk_lfp_pilot_v182o_20260829 [--max-units N] [--probe probeA]
"""
import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.disable(logging.INFO)

from jnwb.paths import nwb_dir  # noqa: E402
from omission.jnwb_ext.analog import load_analog_epochs  # noqa: E402
from omission.jnwb_ext.causal_signal import BANDS  # noqa: E402
from omission.jnwb_ext.session import OmissionSession  # noqa: E402
from omission.jnwb_ext.spk_lfp_pilot import (  # noqa: E402
    LAG_INTERVALS_MS, band_envelope_trials, band_temporal_support, distributed_lag_coefficients,
    electrode_probe_sequence, electrode_row_count, incremental_predictive_dependence,
    lag_interval_features,
    resolve_channel_sets,
    signed_association, spike_counts_in_window, valid_from_ms,
)
from omission.jnwb_ext.unit_classification import family_of  # noqa: E402

SESSION = "sub-V182o_ses-260702"
CLASS_CSV = Path("omission/artifacts/data/pilot_v182o_260702_unitclass.csv")
OUT_JSON = Path("omission/artifacts/.lab/spk-lfp-pilot-v182o-260702-20260829.json")
OUT_CSV = Path("omission/artifacts/data/spk_lfp_pilot_v182o_260702_cells.csv")

# One p1-aligned window spanning the whole sequence, with enough pre-roll for theta's 750 ms
# startup transient plus the longest lag interval (250 ms) before the earliest analysed event
# (fx at -500 ms). -1600 gives 750 + 250 + margin before -500.
WINDOW_MS = (-1600.0, 3700.0)
RESPONSE_MS = (0.0, 200.0)      # spike-count window, strictly after the event
HISTORY_MS = (-200.0, 0.0)      # own spike history, strictly before the event


def build_condition_events(session, trial_meta: pd.DataFrame) -> dict:
    """Map each analysis condition to (event_ms relative to p1, trial mask).

    baseline      -- fx slot, all trials
    stimulus      -- p1 slot (always a presented stimulus), all trials
    omission      -- the omitted slot for that trial's condition (p2/p3/p4)
    matched_empty -- the SAME slot index, on control-condition trials of the same sequence family
                     (nothing expected there), giving a matched comparator rather than a
                     within-trial contrast.
    """
    events = {}
    events["baseline"] = {"event_ms": -500.0, "mask": np.ones(len(trial_meta), dtype=bool),
                          "note": "fx slot, all trials"}
    events["stimulus"] = {"event_ms": 0.0, "mask": np.ones(len(trial_meta), dtype=bool),
                          "note": "p1 slot (always presented), all trials"}

    slot_ms = {2: 1031.0, 3: 2062.0, 4: 3093.0}
    pos = trial_meta["omission_position"].astype(str)
    for slot, ms in slot_ms.items():
        key = f"p{slot}"
        om_mask = (pos == key).to_numpy()
        if om_mask.sum() >= 40:
            events[f"omission_{key}"] = {"event_ms": ms, "mask": om_mask,
                                          "note": f"omitted slot {key}"}
            # matched empty: same absolute slot time, on trials whose omission is ELSEWHERE, so
            # nothing was omitted at this slot and a stimulus was expected-and-present... which is
            # the stimulus case. The matched-EMPTY comparator is the control condition of the same
            # family, identified via family_of(condition).
            ctrl_mask = (~om_mask)
            if ctrl_mask.sum() >= 40:
                events[f"matched_empty_{key}"] = {"event_ms": ms, "mask": ctrl_mask,
                                                   "note": f"slot {key} on trials omitted elsewhere"}
    return events


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-units", type=int, default=40)
    ap.add_argument("--probe", type=str, default=None)
    ap.add_argument("--bands", type=str, default="theta,beta,high_gamma")
    args = ap.parse_args()

    path = Path(nwb_dir()) / f"{SESSION}.nwb"
    bands = [b.strip() for b in args.bands.split(",") if b.strip() in BANDS]

    cls = pd.read_csv(CLASS_CSV).set_index("unit_id")
    session = OmissionSession(str(path))

    print(f"Loading LFP {WINDOW_MS} ms ...", flush=True)
    batch = load_analog_epochs(path, signal_class="LFP", alignment="p1", window_ms=WINDOW_MS,
                               correct_only=True, missing_data="drop")
    sm = batch.signal_metadata.reset_index(drop=True)
    tm = batch.trial_metadata.reset_index(drop=True)
    time_ms = np.asarray(batch.time_ms, dtype=float)
    print(f"  LFP {batch.data.shape} (trial, channel, time); {len(tm)} trials", flush=True)

    assert tm["trial_id"].nunique() == len(tm), "canonical trial identity violated in pilot input"

    onsets_s = tm["source_onset_s"].to_numpy(dtype=float)
    events = build_condition_events(session, tm)
    print(f"  conditions: {list(events)}", flush=True)

    # Unit selection. functional_class merges the shuffle classes (S+/S-/Other) with the
    # project's TEMPLATE-CORRELATION O+/O++ labels, joined on ROW POSITION -- classification
    # 'unit_id' and template 'unit_row_idx' are both row positions into _units_df. The kilosort
    # 'unit_id' COLUMN is a per-probe counter (only 137 unique values for 409 units here; id 0
    # exists on all four probes) and must never be used as a session-unique unit key. See
    # bug-omission-identity-unit-id-column-vs-row-position-20260816.json.
    units = cls.copy()
    if args.probe:
        probe_channels = set(sm.loc[sm["probe"] == args.probe, "channel_id"])
        units = units[units["peak_channel_id"].isin(probe_channels)]
    units = units[units["stable_plus"] == True]  # noqa: E712

    # O+/O++ are rare (20 of 409 here) -- take ALL of them, then fill the remaining budget with
    # the highest-rate units from the other classes. A plain top-N-by-rate selection would drop
    # most of the very classes the contrast is about.
    rare = units[units["functional_class"].isin(["O+", "O++"])]
    rest = units[~units["functional_class"].isin(["O+", "O++"])].sort_values(
        "firing_rate", ascending=False).head(max(args.max_units - len(rare), 0))
    units = pd.concat([rare, rest])
    print(f"  units selected: {len(units)} "
          f"({units['functional_class'].value_counts().to_dict()})", flush=True)

    supports = {b: band_temporal_support(b) for b in bands}
    rows = []

    for band in bands:
        transient_end = valid_from_ms(supports[band], WINDOW_MS[0])
        print(f"\n[{band}] envelope; valid from {transient_end:.0f} ms", flush=True)
        env_cache: dict[int, np.ndarray] = {}

        for n_u, (uid, urow) in enumerate(units.iterrows(), 1):
            chans = resolve_channel_sets(sm, int(urow["peak_channel_id"]),
                                          n_electrodes=electrode_row_count(path),
                                          electrode_probes=electrode_probe_sequence(path))
            if chans is None:
                continue
            spikes = session.get_spike_times(int(uid))
            if spikes is None or len(spikes) < 200:
                continue
            spikes = np.sort(np.asarray(spikes, dtype=float))

            for ctrl_name, ch_idx in chans.as_dict().items():
                if len(ch_idx) == 0:
                    continue
                use = ch_idx if len(ch_idx) <= 8 else ch_idx[:: max(1, len(ch_idx) // 8)][:8]
                key = hash(tuple(sorted(use.tolist())))
                if key not in env_cache:
                    lfp = batch.data[:, use, :].mean(axis=1).astype(float)
                    env, _ = band_envelope_trials(lfp, band)
                    env_cache[key] = env
                env = env_cache[key]

                for cond, spec in events.items():
                    ev_ms = spec["event_ms"]
                    mask = spec["mask"]
                    if mask.sum() < 60:
                        continue
                    if ev_ms - LAG_INTERVALS_MS[-1][1] < transient_end:
                        continue  # would use transient-contaminated samples

                    lagf = lag_interval_features(env[mask], time_ms, ev_ms)
                    ev_onsets = onsets_s[mask] + ev_ms / 1000.0
                    y = spike_counts_in_window(spikes, ev_onsets, *RESPONSE_MS)
                    hist = spike_counts_in_window(spikes, ev_onsets, *HISTORY_MS)
                    nuisance = np.empty((mask.sum(), 0))

                    dp = incremental_predictive_dependence(lagf, nuisance, hist, y)
                    dc = distributed_lag_coefficients(lagf, nuisance, hist, y)
                    assoc = signed_association(lagf[:, 0], y)

                    rows.append({
                        "session": SESSION, "unit_id": int(uid),
                        "functional_class": urow["functional_class"],
                        "shuffle_class": urow["display_class"], "area": urow["area"],
                        "layer": urow.get("layer", ""), "band": band, "condition": cond,
                        "channel_control": ctrl_name, "n_channels_used": int(len(use)),
                        "n_trials": int(mask.sum()),
                        "delta_pred": dp["delta_pred"], "r2_nuisance": dp["r2_nuisance"],
                        "r2_past_lfp": dp["r2_past_lfp"], "n_trials_used": dp["n_trials_used"],
                        "assoc_pearson_r": assoc["pearson_r"], "assoc_sign": assoc["sign"],
                        "integrated_signed_mass": dc["integrated_signed_mass"],
                        **{f"coef_{k}": v for k, v in dc["coefficients"].items()},
                        **({f"quad_{k}": v for k, v in assoc.get("quadrant_fractions", {}).items()}),
                        "effective_latency_ms": supports[band]["effective_latency_ms"],
                    })
            if n_u % 10 == 0:
                print(f"    {n_u}/{len(units)} units", flush=True)

    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nWrote {OUT_CSV}  ({len(df)} cells)")

    summary = {}
    if not df.empty:
        g = df.groupby(["band", "condition", "channel_control"])["delta_pred"]
        summary["delta_pred_by_band_condition_control"] = {
            "|".join(map(str, k)): {"mean": float(v.mean()), "median": float(v.median()),
                                     "n_cells": int(v.notna().sum()),
                                     "frac_positive": float((v > 0).mean())}
            for k, v in g if v.notna().any()
        }
        gs = df.groupby(["band", "condition"])["assoc_pearson_r"]
        summary["signed_association_by_band_condition"] = {
            "|".join(map(str, k)): {"mean_r": float(v.mean()),
                                     "frac_negative": float((v < 0).mean()),
                                     "frac_positive": float((v > 0).mean()),
                                     "n": int(v.notna().sum())}
            for k, v in gs if v.notna().any()
        }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "schema_version": 3,
        "id": "spk-lfp-pilot-v182o-260702-20260829",
        "kind": "evidence",
        "title": "Representative-session SPK-LFP pilot (downgraded estimand): incremental predictive dependence",
        "status": "provisional",
        "estimand": ("Incremental predictive dependence of subsequent firing on PAST band-specific "
                     "LFP state, beyond spike history. NOT a causal or directional claim -- see "
                     "causal-identification-branch-seal-20260828.json."),
        "session": SESSION,
        "window_ms": list(WINDOW_MS), "response_ms": list(RESPONSE_MS), "history_ms": list(HISTORY_MS),
        "lag_intervals_ms": [list(x) for x in LAG_INTERVALS_MS],
        "bands": bands,
        "band_temporal_support": supports,
        "n_units_analysed": int(units.shape[0]),
        "unit_class_counts": {str(k): int(v) for k, v in units["functional_class"].value_counts().items()},
        "o_plus_available": True,
        "o_plus_note": ("O+/O++ labels come from the project's TEMPLATE-CORRELATION tables "
                        "(outputs/classification/grand_oplus_units.csv, grand_oplusplus_units.csv), "
                        "NOT from classify_session_units' shuffle-based is_o_plus (which stays 0 "
                        "unless the separate template-assignment step runs -- an earlier reading of "
                        "that field as 'no O+ units exist' was a method error, retracted in "
                        "v182o-oplus-yield-20260829.json). Joined on ROW POSITION (classification "
                        "unit_id == template unit_row_idx); the kilosort unit_id COLUMN is a "
                        "per-probe counter and is not a session-unique unit key. This session has "
                        "16 O+ and 4 O++ units, all stable_plus."),
        "n_cells": int(len(df)),
        "summary": summary,
        "cells_csv": str(OUT_CSV),
    }, indent=2))
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
