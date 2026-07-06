"""
Find omission-positive (O+) neurons in the new V182o recording.

Replicates the exact "strict trial-by-trial omission selectivity audit"
from outputs/archive/scripts/generate_all_rasters_expanded.py, using only
jNWB session primitives (get_epochs, get_spike_times) instead of raw pynwb.

Definition of O+ (per original script docstring):
  Stable units showing a significant increase in firing rate during an
  omission slot relative to the matched fully-present control trials:
    - diff (omission_rate - control_rate) >= 4.0 Hz
    - one-sided Mann-Whitney U p < 0.01 (omission > control)
  Evaluated across all 9 (family x slot) combinations per unit; a unit
  passes if its BEST combination clears both thresholds.

Onsets are always taken at p1 (stimulus_number == 2); the omission/control
windows for slots 2/3/4 are offsets relative to that p1 onset, matching the
task sequence design (p1 at [0,500], p2 at [1031,1531], p3 at [2062,2562],
p4 at [3093,3593] ms).
"""

import logging
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from jnwb import read

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

NWB_PATH = "D:/analysis/nwb/sub-V182o_ses-260629.nwb"

# family -> {slot: {cond, window_ms, ctrl_cond}}
FAMILIES = {
    "A": {
        2: {"cond": "AXAB", "ctrl": "AAAB", "window": (1031, 1531)},
        3: {"cond": "AAXB", "ctrl": "AAAB", "window": (2062, 2562)},
        4: {"cond": "AAAX", "ctrl": "AAAB", "window": (3093, 3593)},
    },
    "B": {
        2: {"cond": "BXBA", "ctrl": "BBBA", "window": (1031, 1531)},
        3: {"cond": "BBXA", "ctrl": "BBBA", "window": (2062, 2562)},
        4: {"cond": "BBBX", "ctrl": "BBBA", "window": (3093, 3593)},
    },
    "R": {
        2: {"cond": "RXRR", "ctrl": "RRRR", "window": (1031, 1531)},
        3: {"cond": "RRXR", "ctrl": "RRRR", "window": (2062, 2562)},
        4: {"cond": "RRRX", "ctrl": "RRRR", "window": (3093, 3593)},
    },
}

DIFF_THRESHOLD_HZ = 4.0
P_THRESHOLD = 0.01
MIN_TRIALS = 5


def window_rates(spike_times: np.ndarray, onsets: np.ndarray, window_ms) -> np.ndarray:
    """Firing rate (Hz) in a fixed window relative to each p1 onset."""
    w_start_s = window_ms[0] / 1000.0
    w_end_s = window_ms[1] / 1000.0
    dur_s = w_end_s - w_start_s
    rates = np.empty(len(onsets))
    for i, onset in enumerate(onsets):
        t0, t1 = onset + w_start_s, onset + w_end_s
        n_spikes = np.sum((spike_times >= t0) & (spike_times <= t1))
        rates[i] = n_spikes / dur_s
    return rates


def precompute_onsets(session) -> dict:
    """Compute p1-onset arrays once per (family, slot) combo, reused across all units."""
    onsets = {}
    for fam_name, slots in FAMILIES.items():
        for slot, cfg in slots.items():
            om_epochs = session.get_epochs(phase=2, condition=cfg["cond"], correct_only=True)
            ctrl_epochs = session.get_epochs(phase=2, condition=cfg["ctrl"], correct_only=True)
            onsets[(fam_name, slot)] = {
                "om": om_epochs['start_time'].values,
                "ctrl": ctrl_epochs['start_time'].values,
            }
    return onsets


def audit_unit(session, unit_id, onsets_cache: dict) -> dict:
    """Run the 9 family x slot comparisons for one unit; return the best result."""
    spike_times = session.get_spike_times(unit_id)
    if spike_times is None or len(spike_times) == 0:
        return None

    results = []
    for fam_name, slots in FAMILIES.items():
        for slot, cfg in slots.items():
            om_onsets = onsets_cache[(fam_name, slot)]["om"]
            ctrl_onsets = onsets_cache[(fam_name, slot)]["ctrl"]

            if len(om_onsets) < MIN_TRIALS or len(ctrl_onsets) < MIN_TRIALS:
                continue

            om_rates = window_rates(spike_times, om_onsets, cfg["window"])
            ctrl_rates = window_rates(spike_times, ctrl_onsets, cfg["window"])

            om_mean, ctrl_mean = np.mean(om_rates), np.mean(ctrl_rates)
            diff = om_mean - ctrl_mean

            try:
                _, p_val = mannwhitneyu(om_rates, ctrl_rates, alternative='greater')
            except ValueError:
                p_val = 1.0

            results.append({
                "family": fam_name, "slot": slot,
                "condition": cfg["cond"], "control": cfg["ctrl"],
                "om_mean_hz": om_mean, "ctrl_mean_hz": ctrl_mean,
                "diff": diff, "p_val": p_val,
                "n_om_trials": len(om_onsets), "n_ctrl_trials": len(ctrl_onsets),
            })

    if not results:
        return None
    return max(results, key=lambda r: r["diff"])


def find_omission_positive_units():
    session = read(NWB_PATH)
    log.info(f"Loaded {Path(NWB_PATH).name}: {session._metadata.get('n_units')} total units")

    units = session._units_df
    stable = units[units['is_stable'] == True].copy()
    log.info(f"Auditing {len(stable)} stable units for omission selectivity "
             f"(diff >= {DIFF_THRESHOLD_HZ} Hz, Mann-Whitney p < {P_THRESHOLD})")

    onsets_cache = precompute_onsets(session)
    for (fam, slot), d in onsets_cache.items():
        log.info(f"  {fam}/slot{slot}: n_om={len(d['om'])}, n_ctrl={len(d['ctrl'])}")

    records = []
    for unit_id, row in stable.iterrows():
        best = audit_unit(session, unit_id, onsets_cache)
        if best is None:
            continue
        if best["diff"] >= DIFF_THRESHOLD_HZ and best["p_val"] < P_THRESHOLD:
            records.append({
                "unit_id": int(unit_id),
                "area": row.get("area", "Unknown"),
                "layer": row.get("layer", "Unknown"),
                "firing_rate": row.get("firing_rate", np.nan),
                "best_family": best["family"],
                "best_slot": best["slot"],
                "best_condition": best["condition"],
                "max_diff_hz": best["diff"],
                "p_val": best["p_val"],
                "om_mean_hz": best["om_mean_hz"],
                "ctrl_mean_hz": best["ctrl_mean_hz"],
                "n_om_trials": best["n_om_trials"],
                "n_ctrl_trials": best["n_ctrl_trials"],
            })

    result_df = pd.DataFrame(records).sort_values("max_diff_hz", ascending=False)
    return result_df


if __name__ == "__main__":
    df = find_omission_positive_units()

    print("=" * 90)
    print(f"OMISSION-POSITIVE (O+) UNIT AUDIT — sub-V182o_ses-260629")
    print("=" * 90)
    print(f"Found {len(df)} O+ units (strict criteria: diff >= {DIFF_THRESHOLD_HZ} Hz, p < {P_THRESHOLD})\n")

    if len(df) > 0:
        print(df.to_string(index=False))
        print()
        print("By area:")
        print(df['area'].value_counts().to_string())

        out_path = Path("D:/workspace/omission/outputs/publication_figures/o_plus_units_V182o_ses260629.csv")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"\nSaved: {out_path}")
    else:
        print("No units passed strict O+ criteria.")
