r"""
Within-session, trial-matched correlation between POPULATION firing rate and LFP band power --
per area, per functional group, per condition-group, per band. New analysis (2026-08-05),
requested alongside the fig05/06/07 sliding-window connectivity work but distinct from it: this
is population-pooled (all qualifying units in a functional group, averaged), not per-unit/
per-channel, and asks whether population rate co-varies trial-to-trial with band power in the
SAME trial -- not whether two signals are coupled in time within a trial.

Same statistical discipline as everything else built this week (see
feedback_pool_after_testing_not_before memory): test within session first via a trial-mismatch
shuffle null, then pool the resulting per-session significance decisions across sessions with an
exact binomial (Clopper-Pearson) hit rate. Never pool raw per-session correlations and test the
pool directly -- this corpus's large between-session/animal variability has produced 0/N group
results from that approach six separate times already.

FUNCTIONAL GROUPS (5, as of 2026-08-06: S+/S++, S-/S--, O+ (exclusive of O++), O++, Other)
    "Other" (renamed from "Null" same day) means not functionally part of the S+/S-/O+
    families.
    Reuses the exact join/definitions from fig03_unit_census.py (attach_legacy, class5) rather
    than reimplementing: S-family membership (is_Splus/is_Splus_double, is_Sminus/
    is_Sminus_double) comes from the LEGACY_TABLE join and is only defined for units with a
    legacy_screened row (2,921 of 6,650 grand-table units, 15 of 21 sessions) -- units without a
    legacy row are excluded from S+/S- group membership, not folded into Other, exactly as
    fig03's own class5/class8 panels already do. O-family (omission_class) is defined for all
    screened units. **O++ split from O+ 2026-08-06** (originally these were pooled into one "O+"
    bucket): O++ is the strict, R-family-random-control-robust subset of O+, only 15 units
    corpus-wide, and now gets its own group -- "O+" in every output from this date forward means
    O+ EXCLUSIVE of O++, not the O+/O++ union the first version of this script used. Re-running
    this script changes the O+ group's own numbers slightly (fewer, more specific units) as a
    consequence -- flagged, not silently absorbed. Priority when both would apply: O-family
    (O+/O++) outranks S-family, O++ outranks plain O+, same
    as fig03's class8 order, because it is the more specific claim for the units it covers.

CONDITION GROUPS (3, timing from omission.jnwb_ext.sequence_layout.EPOCH_ONSETS_MS)
    baseline : RXRR trials, window (-500, 0) ms re p1 (omission.jnwb_ext.unit_classification.BASELINE_MS)
    stim     : RRRR trials, window (0, 531) ms re p1    -- real p1 response, no omission yet
    omission : RXRR trials, window (1031, 1562) ms re p1 -- the omitted p2 slot

TRIAL CORRESPONDENCE (verified, not assumed)
    Population firing comes from omission.jnwb_ext.connectivity.bin_spikes() using
    precompute_condition_onsets(correct_only=True) trial starts (seconds, from the NWB event
    stream). Band power comes from outputs/condition_band_power_trials/trials.npz, built from
    the TFR .npy arrays under D:/workspace/data/tfr_arrays. These are two independently-built
    per-trial products; trial-index correspondence between them was spot-checked on
    sub-C31o_ses-230816 before building this script (RXRR 51/51, RRRR 100/100 trial counts
    match exactly for both conditions) -- not a full ordering proof, but both are built by
    walking the same "correct trials in NWB event order" filter, and a per-session trial-count
    assertion below aborts that session's key rather than silently using it if counts disagree.

POPULATION RATE
    Mean per-unit firing rate (Hz) across the functional group's qualifying units in that area,
    per trial, in the condition-group's window -- not summed, so group size does not confound
    the comparison across functional groups of very different N.

OUTPUT
    outputs/population_firing_lfp_power_corr/<session>.npz
    outputs/population_firing_lfp_power_corr/index.csv
    outputs/population_firing_lfp_power_corr/receipt.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import omission as oa  # noqa: E402
from omission.jnwb_ext.unit_classification import precompute_condition_onsets  # noqa: E402
from omission.jnwb_ext.connectivity import bin_spikes  # noqa: E402
from jnwb import paths as _P

NWB_DIR = _P.nwb_dir()
UNITS_CSV = _P.REPO_ROOT / "outputs/classification/omission_grand_units.csv"
LEGACY_TABLE = _P.REPO_ROOT / "outputs/classification/grand_s_and_o_units.csv"
BAND_POWER_NPZ = _P.REPO_ROOT / "outputs/condition_band_power_trials/trials.npz"
BAND_POWER_INDEX = _P.REPO_ROOT / "outputs/condition_band_power_trials/index.csv"
OUT_DIR = _P.REPO_ROOT / "outputs/population_firing_lfp_power_corr"

BANDS = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]
MIN_FIRING_RATE_HZ = 0.5
MIN_UNITS_PER_GROUP = 2
# O++ is 15 units corpus-wide; requiring 2 per session per area (as for every other group)
# left only 2 areas with ANY coverage (FEF, V4), each from a single session -- no error bar,
# no cross-session view, and visually an empty row for the other 8 areas. Relaxed to 1 unit
# for O++ ONLY (2026-08-06, explicit exception, not a silent inconsistency): a "population" of
# 1 unit is just that unit's own rate, a real methodological weakening for this group alone,
# but it recovers genuine same-subject cross-session coverage for two areas that a 2-unit floor
# was hiding (V4: sub-C31o sessions 230830 and 230831; MT: sub-V182o sessions 260715 and
# 260717) rather than fabricating anything.
MIN_UNITS_PER_GROUP_OPLUSPLUS = 1
BIN_MS = 10.0
N_SHUFFLE = 200
RNG_SEED = 1234

# (condition_group_name, nwb_condition, window_ms_re_p1)
CONDITION_GROUPS = {
    "baseline": ("RXRR", (-500.0, 0.0)),
    "stim": ("RRRR", (0.0, 531.0)),
    "omission": ("RXRR", (1031.0, 1562.0)),
}


def build_functional_groups(units_df):
    """Returns units_df with a 'func_group' column in {S+, S-, O+, O++, Other} or NaN
    (unresolvable). O++ split out from O+ as its own group (2026-08-06, per request) -- O++ is
    the strict, more-specific nested subset of O+ (robust to the R-family random-control check,
    see CLASSIFICATION.md), only 15 units corpus-wide, and now gets its own row rather than
    being folded into the inclusive O+ bucket. Priority when a unit qualifies for more than one
    bucket: O++ > O+ > S-family, same order as fig03_unit_census.py's class8 (O++ is a strictly
    more specific claim about the same unit than plain O+)."""
    legacy = pd.read_csv(LEGACY_TABLE)
    m = units_df.merge(
        legacy[["session_prefix", "unit_row_idx", "is_Splus", "is_Splus_double",
                "is_Sminus", "is_Sminus_double"]],
        left_on=["session", "unit_row"], right_on=["session_prefix", "unit_row_idx"], how="left")
    legacy_screened = m["is_Splus"].notna()

    o_family = m["omission_class"].isin(["O+", "O++"])
    o_plusplus = m["omission_class"] == "O++"
    s_plus = legacy_screened & ((m["is_Splus"] == True) | (m["is_Splus_double"] == True))  # noqa: E712
    s_minus = legacy_screened & ((m["is_Sminus"] == True) | (m["is_Sminus_double"] == True))  # noqa: E712

    group = np.full(len(m), np.nan, dtype=object)
    group[legacy_screened] = "Other"          # not S+/S-/O+ (renamed from "Null" 2026-08-06)
    group[s_minus.to_numpy()] = "S-"
    group[s_plus.to_numpy()] = "S+"
    group[o_family.to_numpy()] = "O+"          # O-family outranks S-family, same as fig03 class8
    group[o_plusplus.to_numpy()] = "O++"       # O++ outranks plain O+, same as fig03 class8
    m["func_group"] = group
    return m


def band_power_window_mean(bp, times, win_ms):
    i0 = int(np.searchsorted(times, win_ms[0]))
    i1 = int(np.searchsorted(times, win_ms[1]))
    with np.errstate(invalid="ignore"):
        return np.nanmean(bp[:, i0:i1], axis=1)


def shuffle_null_corr(x, y, n_shuffle=N_SHUFFLE, seed=RNG_SEED):
    """Real Pearson r and a trial-mismatch shuffle null distribution of r."""
    rng = np.random.default_rng(seed)
    n = len(x)
    xz = (x - np.nanmean(x)) / (np.nanstd(x) + 1e-12)
    yz = (y - np.nanmean(y)) / (np.nanstd(y) + 1e-12)
    valid = np.isfinite(xz) & np.isfinite(yz)
    if valid.sum() < 5:
        return np.nan, np.full(n_shuffle, np.nan)
    real = float(np.mean(xz[valid] * yz[valid]))
    null = np.empty(n_shuffle, dtype=np.float64)
    idx = np.arange(n)
    for s in range(n_shuffle):
        perm = rng.permutation(idx)
        # reject the identity/fixed-point-heavy permutations that leave true pairing intact
        while np.mean(perm == idx) > 0.2:
            perm = rng.permutation(idx)
        v2 = valid & valid[perm]
        null[s] = np.mean(xz[v2] * yz[perm][v2]) if v2.sum() >= 5 else np.nan
    return real, null


def main(limit_sessions=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    units_df = pd.read_csv(UNITS_CSV)
    units_df = build_functional_groups(units_df)

    bp_index = pd.read_csv(BAND_POWER_INDEX)
    bp = np.load(BAND_POWER_NPZ, allow_pickle=True)
    times = bp["times"]

    sessions = sorted(set(units_df.session.unique()) & set(bp_index.session.unique()))
    if limit_sessions:
        sessions = sessions[:limit_sessions]
    print(f"{len(sessions)} sessions with both unit and band-power data", flush=True)

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
        areas_present = sorted(bp_index.loc[bp_index.session == session, "area"].unique())

        rows_out = []
        for cg_name, (cond, win_ms) in CONDITION_GROUPS.items():
            trial_starts = onsets.get(cond, np.array([]))
            if len(trial_starts) < 5:
                continue
            for area in areas_present:
                key_check = bp_index[(bp_index.session == session) & (bp_index.area == area) &
                                      (bp_index.cond == cond)]
                if key_check.empty:
                    continue
                n_trials_bp = int(key_check["n_trials"].iloc[0])
                if n_trials_bp != len(trial_starts):
                    continue  # trial-count mismatch -- skip rather than silently misalign

                area_units = sess_units[(sess_units.area10 == area) &
                                         (sess_units.firing_rate >= MIN_FIRING_RATE_HZ)]
                for fgroup in ("S+", "S-", "O+", "O++", "Other"):
                    min_units = MIN_UNITS_PER_GROUP_OPLUSPLUS if fgroup == "O++" \
                        else MIN_UNITS_PER_GROUP
                    grp_units = area_units[area_units.func_group == fgroup]
                    if len(grp_units) < min_units:
                        continue

                    rates = []
                    for unit_row in grp_units.unit_row:
                        try:
                            st = sess.get_spike_times(int(unit_row))
                        except Exception:
                            continue
                        if st is None:
                            continue
                        binned = bin_spikes(st, window=(win_ms[0] / 1000.0, win_ms[1] / 1000.0),
                                            bin_size_ms=BIN_MS, trial_starts=trial_starts,
                                            output="rate")
                        rates.append(np.nanmean(binned, axis=1))  # (n_trials,) mean Hz in window
                    if len(rates) < min_units:
                        continue
                    n_tr = min(len(r) for r in rates)
                    pop_rate = np.nanmean(np.stack([r[:n_tr] for r in rates]), axis=0)

                    for band in BANDS:
                        bkey = f"{session}|{area}|{cond}|{band}"
                        if bkey not in bp.files:
                            continue
                        band_trace = bp[bkey][:n_tr]
                        band_scalar = band_power_window_mean(band_trace, times, win_ms)
                        real, null = shuffle_null_corr(pop_rate, band_scalar)
                        rows_out.append({
                            "condition_group": cg_name, "area": area, "func_group": fgroup,
                            "band": band, "n_trials": int(n_tr), "n_units": int(len(rates)),
                            "real_r": real, "null_mean": float(np.nanmean(null)),
                            "null_std": float(np.nanstd(null)),
                        })

        if not rows_out:
            continue
        out_df = pd.DataFrame(rows_out)
        out_df.to_csv(os.path.join(OUT_DIR, f"{session}.csv.gz"), index=False)
        index_rows.append({"session": session, "n_rows": len(out_df)})
        print(f"[{datetime.now():%H:%M:%S}] session {si}/{len(sessions)} ({session}), "
              f"{len(out_df)} rows, {time.time()-t0:.0f}s total", flush=True)

    pd.DataFrame(index_rows).to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Within-session correlation between population firing rate (per area, per "
                   "functional group) and LFP band power, per condition group and band. Pool "
                   "after testing -- this file is step 1/2 of 3, see aggregation script.",
        "functional_groups": "S+ (S+/S++), S- (S-/S--), O+ (O+/O++) outranks S-family, Other (not functionally part of S+/S-/O+); "
                             "S-family requires legacy_screened (see build_functional_groups)",
        "condition_groups": {k: {"nwb_condition": v[0], "window_ms_re_p1": list(v[1])}
                              for k, v in CONDITION_GROUPS.items()},
        "min_firing_rate_hz": MIN_FIRING_RATE_HZ, "min_units_per_group": MIN_UNITS_PER_GROUP,
        "min_units_per_group_oplusplus_exception": MIN_UNITS_PER_GROUP_OPLUSPLUS,
        "n_shuffle": N_SHUFFLE,
        "trial_correspondence": "bin_spikes trial order (from precompute_condition_onsets) "
                                "assumed to match condition_band_power_trials.npz trial order; "
                                "verified by trial-count match on sub-C31o_ses-230816 (RXRR "
                                "51/51, RRRR 100/100) before building this script, and a "
                                "per-(session,area,cond) trial-count assertion skips any key "
                                "where counts disagree rather than silently using it.",
        "n_sessions_processed": len(index_rows),
        "runtime_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {OUT_DIR}/ ({len(index_rows)} sessions), index.csv, receipt.json")


if __name__ == "__main__":
    main(limit_sessions=int(sys.argv[1]) if len(sys.argv) > 1 else None)
