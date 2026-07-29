"""
Canonical stability + S+/S-/O+/X candidate audit for sub-V182o_ses-260629.

Reconciles two prior gaps flagged in review:

1. "is_stable" in the live jnwb.addressing proxy (quality>=1.0, stable_plus
   aliased identically) is NOT the same test as this project's canonical
   3-criterion stability pipeline (outputs/archive/scripts/tag_stable_units.py):
     C1: >=5 spikes in EVERY correct trial, window [-1000,+4000]ms around p1
     C2: mean firing_rate >= 1.0 Hz
     C3: presence_ratio >= 0.98 OR snr > 0.75
   A unit is canonically Stable iff C1 AND C2 AND C3.

2. The earlier O+ candidate audit (examples/06_find_omission_positive_units_v182o.py)
   used an ad hoc Mann-Whitney + 4Hz-diff test, not the project's actual
   candidate-labeling pipeline (outputs/archive/scripts/run_spk_response_metrics_a8_1.py
   + _response_metric_common.py):
     - fx (pre-p1 baseline):      [-500, 0]   ms
     - p1 (stimulus response):    [0, 531]    ms
     - omission window (p2/p3/p4): [onset, onset+531] ms
     - local pre-omission baseline: [onset-250, onset-50] ms
     - control-omission window:    same [onset, onset+531] ms, matched control condition
     - p1_vs_baseline:   paired Wilcoxon(p1_trials, fx_trials) + Cohen's d      -> S+/S-
     - om_vs_baseline:   paired Wilcoxon(om_trials, om_base_trials) + d        -> O+/O- candidate
     - om_vs_control:    unpaired Mann-Whitney(om_trials, ctrl_om_trials) + d  -> X candidate (add-on)
     - BH-FDR correction applied across all units within the session
     - Thresholds: rate > 2.0 Hz, q < 0.05, |d| > 0.3
     - Priority: X_candidate > O_plus_candidate > O_minus_candidate >
                 S_plus_candidate > S_minus_candidate > null_or_unclassified

Both tests are run independently here and cross-tabulated against the 4 units
previously flagged (243, 150, 102, 261) so we know exactly which historical
definition each one does or doesn't satisfy.
"""

import logging
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from jnwb import read

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

NWB_PATH = "D:/analysis/nwb/sub-V182o_ses-260629.nwb"

P1_ONSET_MS = 0
SLOT_ONSETS = {"p2": 1031, "p3": 2062, "p4": 3093}

FAMILIES = {
    "A": {"ctrl": "AAAB", "slots": {"p2": "AXAB", "p3": "AAXB", "p4": "AAAX"}},
    "B": {"ctrl": "BBBA", "slots": {"p2": "BXBA", "p3": "BBXA", "p4": "BBBX"}},
    "R": {"ctrl": "RRRR", "slots": {"p2": "RXRR", "p3": "RRXR", "p4": "RRRX"}},
}

RATE_FLOOR_HZ = 2.0
Q_THRESHOLD = 0.05
EFFECT_THRESHOLD = 0.3
MIN_TRIALS = 5

# --- canonical stability pipeline (tag_stable_units.py) ---
MIN_SPIKES_PER_TRIAL = 5
MIN_FIRING_RATE = 1.0
MIN_PRESENCE_RATIO = 0.98
MIN_SNR = 0.75
STABILITY_WINDOW_MS = (-1000, 4000)


def compute_cohens_d(x, y):
    mx, my = np.mean(x), np.mean(y)
    vx, vy = np.var(x, ddof=1) if len(x) > 1 else 0.0, np.var(y, ddof=1) if len(y) > 1 else 0.0
    pooled_std = np.sqrt((vx + vy) / 2.0) + 1e-8
    return (mx - my) / pooled_std


def run_paired_test(x, y):
    diff = x - y
    if np.all(diff == 0):
        return 1.0, 0.0
    try:
        _, p = stats.wilcoxon(x, y)
        return float(p), float(compute_cohens_d(x, y))
    except Exception:
        return 1.0, float(compute_cohens_d(x, y))


def run_unpaired_test(x, y):
    if len(x) == 0 or len(y) == 0:
        return 1.0, 0.0
    if len(x) == len(y) and np.all(x == y):
        return 1.0, 0.0
    try:
        _, p = stats.mannwhitneyu(x, y, alternative="two-sided")
        return float(p), float(compute_cohens_d(x, y))
    except Exception:
        return 1.0, float(compute_cohens_d(x, y))


def rate_in_window(spike_times, onset_s, window_ms):
    t0 = onset_s + window_ms[0] / 1000.0
    t1 = onset_s + window_ms[1] / 1000.0
    n = np.sum((spike_times >= t0) & (spike_times <= t1))
    return n / ((window_ms[1] - window_ms[0]) / 1000.0)


def per_trial_rates(spike_times, onsets, window_ms):
    return np.array([rate_in_window(spike_times, o, window_ms) for o in onsets])


# ============================================================================
# 1. CANONICAL 3-CRITERION STABILITY TEST
# ============================================================================

def canonical_stability_test(session, unit_id, all_onsets_p1) -> dict:
    spike_times = session.get_spike_times(unit_id)
    if spike_times is None or len(spike_times) == 0:
        return {"is_stable_canonical": False, "min_trial_spikes": 0, "n_trials_checked": 0}

    counts = per_trial_rates(spike_times, all_onsets_p1, STABILITY_WINDOW_MS) * \
             ((STABILITY_WINDOW_MS[1] - STABILITY_WINDOW_MS[0]) / 1000.0)
    min_spikes = int(counts.min()) if len(counts) > 0 else 0
    c1 = min_spikes >= MIN_SPIKES_PER_TRIAL

    row = session._units_df.loc[unit_id]
    c2 = float(row.get("firing_rate", 0.0)) >= MIN_FIRING_RATE
    c3 = (float(row.get("presence_ratio", 0.0)) >= MIN_PRESENCE_RATIO) or \
         (float(row.get("snr", 0.0)) > MIN_SNR)

    return {
        "is_stable_canonical": bool(c1 and c2 and c3),
        "c1_min_spikes_per_trial": c1,
        "c2_firing_rate": c2,
        "c3_presence_or_snr": c3,
        "min_trial_spikes": min_spikes,
        "n_trials_checked": len(counts),
    }


# ============================================================================
# 2. CANONICAL S+/S-/O+/X CANDIDATE PIPELINE
# ============================================================================

def compute_unit_metrics(session, unit_id, onsets_cache) -> list:
    spike_times = session.get_spike_times(unit_id)
    if spike_times is None or len(spike_times) == 0:
        return []

    records = []
    for fam_name, fam_cfg in FAMILIES.items():
        ctrl_cond = fam_cfg["ctrl"]
        ctrl_onsets = onsets_cache[(fam_name, "ctrl")]
        if len(ctrl_onsets) < MIN_TRIALS:
            continue

        fx_trials = per_trial_rates(spike_times, ctrl_onsets, (-500, 0))
        p1_trials = per_trial_rates(spike_times, ctrl_onsets, (0, 531))
        p_p1, d_p1 = run_paired_test(p1_trials, fx_trials)

        rec = {
            "family": fam_name, "omission_slot": "None",
            "fr_baseline_fx": float(np.mean(fx_trials)), "fr_stimulus_p1": float(np.mean(p1_trials)),
            "p_stimulus_p1_vs_baseline": p_p1, "d_stimulus_p1_vs_baseline": d_p1,
            "fr_omission": 0.0, "fr_omission_baseline": 0.0, "fr_control_omission": 0.0,
            "p_omission_vs_baseline": 1.0, "d_omission_vs_baseline": 0.0,
            "p_omission_vs_control": 1.0, "d_omission_vs_control": 0.0,
        }
        records.append(rec)

        for slot, om_cond in fam_cfg["slots"].items():
            om_onsets = onsets_cache[(fam_name, slot)]
            if len(om_onsets) < MIN_TRIALS:
                continue

            onset_ms = SLOT_ONSETS[slot]
            om_window = (onset_ms, onset_ms + 531)
            base_window = (onset_ms - 250, onset_ms - 50)

            fx_trials_s = per_trial_rates(spike_times, om_onsets, (-500, 0))
            p1_trials_s = per_trial_rates(spike_times, om_onsets, (0, 531))
            p_p1_s, d_p1_s = run_paired_test(p1_trials_s, fx_trials_s)

            om_trials = per_trial_rates(spike_times, om_onsets, om_window)
            om_base_trials = per_trial_rates(spike_times, om_onsets, base_window)
            p_om_base, d_om_base = run_paired_test(om_trials, om_base_trials)

            ctrl_om_trials = per_trial_rates(spike_times, ctrl_onsets, om_window)
            p_om_ctrl, d_om_ctrl = run_unpaired_test(om_trials, ctrl_om_trials)

            records.append({
                "family": fam_name, "omission_slot": slot,
                "fr_baseline_fx": float(np.mean(fx_trials_s)), "fr_stimulus_p1": float(np.mean(p1_trials_s)),
                "p_stimulus_p1_vs_baseline": p_p1_s, "d_stimulus_p1_vs_baseline": d_p1_s,
                "fr_omission": float(np.mean(om_trials)), "fr_omission_baseline": float(np.mean(om_base_trials)),
                "fr_control_omission": float(np.mean(ctrl_om_trials)),
                "p_omission_vs_baseline": p_om_base, "d_omission_vs_baseline": d_om_base,
                "p_omission_vs_control": p_om_ctrl, "d_omission_vs_control": d_om_ctrl,
            })

    return records


def precompute_onsets(session) -> dict:
    onsets = {}
    for fam_name, fam_cfg in FAMILIES.items():
        onsets[(fam_name, "ctrl")] = session.get_epochs(
            phase=2, condition=fam_cfg["ctrl"], correct_only=True)['start_time'].values
        for slot, om_cond in fam_cfg["slots"].items():
            onsets[(fam_name, slot)] = session.get_epochs(
                phase=2, condition=om_cond, correct_only=True)['start_time'].values
    return onsets


def classify_records(df: pd.DataFrame) -> pd.DataFrame:
    """Apply BH-FDR correction (session-wide) then resolve candidate labels."""
    df = df.copy()

    for pcol, qcol in [
        ("p_stimulus_p1_vs_baseline", "q_stimulus_p1_session"),
        ("p_omission_vs_baseline", "q_omission_vs_baseline_session"),
        ("p_omission_vs_control", "q_omission_vs_control_session"),
    ]:
        pvals = df[pcol].values
        _, qvals, _, _ = multipletests(pvals, method="fdr_bh")
        df[qcol] = qvals

    def resolve(row):
        labels = []
        if row["fr_stimulus_p1"] > RATE_FLOOR_HZ and row["q_stimulus_p1_session"] < Q_THRESHOLD and \
           row["d_stimulus_p1_vs_baseline"] > EFFECT_THRESHOLD:
            labels.append("S_plus_candidate")
        if row["fr_baseline_fx"] > RATE_FLOOR_HZ and row["q_stimulus_p1_session"] < Q_THRESHOLD and \
           row["d_stimulus_p1_vs_baseline"] < -EFFECT_THRESHOLD:
            labels.append("S_minus_candidate")

        if row["omission_slot"] != "None":
            q_ob, q_oc = row["q_omission_vs_baseline_session"], row["q_omission_vs_control_session"]
            d_ob, d_oc = row["d_omission_vs_baseline"], row["d_omission_vs_control"]

            if row["fr_omission"] > RATE_FLOOR_HZ and q_ob < Q_THRESHOLD and d_ob > EFFECT_THRESHOLD:
                labels.append("O_plus_candidate")
            if row["fr_omission_baseline"] > RATE_FLOOR_HZ and q_ob < Q_THRESHOLD and d_ob < -EFFECT_THRESHOLD:
                labels.append("O_minus_candidate")
            if (row["fr_omission"] > RATE_FLOOR_HZ and q_ob < Q_THRESHOLD and d_ob > EFFECT_THRESHOLD and
                    q_oc < Q_THRESHOLD and d_oc > EFFECT_THRESHOLD):
                labels.append("X_candidate")

        return "; ".join(labels) if labels else "null_or_unclassified"

    df["candidate_labels"] = df.apply(resolve, axis=1)
    return df


def resolve_primary_label(labels_str: str) -> str:
    labels = labels_str.split("; ")
    for priority in ["X_candidate", "O_plus_candidate", "O_minus_candidate",
                     "S_plus_candidate", "S_minus_candidate"]:
        if priority in labels:
            return priority
    return "null_or_unclassified"


def main():
    session = read(NWB_PATH)
    units = session._units_df
    log.info(f"Loaded {Path(NWB_PATH).name}: {len(units)} total units")

    # --- canonical stability (all units, for the C1 whole-session onset set) ---
    all_p1_epochs = session.get_epochs(phase=2, correct_only=True)
    all_p1_onsets = all_p1_epochs['start_time'].values
    log.info(f"Canonical stability C1 uses {len(all_p1_onsets)} correct p1 onsets (all conditions)")

    stability_records = []
    for unit_id in units.index:
        res = canonical_stability_test(session, unit_id, all_p1_onsets)
        res["unit_id"] = int(unit_id)
        stability_records.append(res)
    stability_df = pd.DataFrame(stability_records).set_index("unit_id")

    n_canon_stable = stability_df["is_stable_canonical"].sum()
    n_live_stable = units["is_stable"].sum()
    log.info(f"Canonical stable: {n_canon_stable}/{len(units)}  |  Live jnwb is_stable proxy: {n_live_stable}/{len(units)}")

    # --- canonical S+/S-/O+/X candidate pipeline (all units w/ spikes) ---
    onsets_cache = precompute_onsets(session)
    for k, v in onsets_cache.items():
        log.info(f"  onsets {k}: n={len(v)}")

    all_records = []
    for unit_id in units.index:
        recs = compute_unit_metrics(session, unit_id, onsets_cache)
        for r in recs:
            r["unit_id"] = int(unit_id)
        all_records.extend(recs)

    metrics_df = pd.DataFrame(all_records)
    metrics_df = classify_records(metrics_df)

    # Resolve one primary label per unit (priority across all its family/slot rows)
    unit_primary = {}
    for unit_id, group in metrics_df.groupby("unit_id"):
        all_labels = "; ".join(group["candidate_labels"].tolist())
        unit_primary[unit_id] = resolve_primary_label(all_labels)

    primary_df = pd.Series(unit_primary, name="primary_candidate_label").to_frame()
    primary_df.index.name = "unit_id"

    # --- merge everything ---
    result = units[["area", "layer", "firing_rate", "snr", "presence_ratio", "is_stable", "stable_plus"]].copy()
    result.index.name = "unit_id"
    result = result.join(stability_df[["is_stable_canonical", "min_trial_spikes", "n_trials_checked"]])
    result = result.join(primary_df)
    result["primary_candidate_label"] = result["primary_candidate_label"].fillna("null_or_unclassified")

    out_path = Path("D:/workspace/omission/outputs/publication_figures/canonical_audit_V182o_ses260629.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_path)

    print("=" * 100)
    print("CANONICAL STABILITY + S+/S-/O+/X CANDIDATE AUDIT — sub-V182o_ses-260629")
    print("=" * 100)
    print(f"\nCanonical is_stable (3-criterion): {n_canon_stable}/{len(units)}")
    print(f"Live jnwb is_stable proxy (quality>=1.0): {n_live_stable}/{len(units)}")
    print(f"\nCandidate label counts (all {len(units)} units, no stability filter):")
    print(result["primary_candidate_label"].value_counts().to_string())

    print("\n" + "=" * 100)
    print("CROSS-TABULATION: previously flagged units (243, 150, 102, 261)")
    print("=" * 100)
    flagged = [243, 150, 102, 261]
    cols = ["area", "layer", "is_stable", "stable_plus", "is_stable_canonical",
            "min_trial_spikes", "primary_candidate_label"]
    print(result.loc[flagged, cols].to_string())

    prime_candidates = result[(result["primary_candidate_label"] == "X_candidate") &
                               (result["is_stable_canonical"] == True)]
    print(f"\n'Prime' equivalent (X_candidate AND canonical stable): {len(prime_candidates)} units")
    if len(prime_candidates) > 0:
        print(prime_candidates[["area", "layer", "primary_candidate_label"]].to_string())

    print(f"\nSaved: {out_path}")
    return result


if __name__ == "__main__":
    main()
