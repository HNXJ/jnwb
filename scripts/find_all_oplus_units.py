"""
scripts/find_all_oplus_units.py

Scans all units across all active NWB sessions to discover every stable, statistically
significant O+ (Pulse) and O*+ (Ramper) unit based on template correlation and permutation tests.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa

NWB_DIR = Path("D:/analysis/nwb")
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_CSV = REPO_ROOT / "outputs/classification/grand_oplus_units.csv"

# 9 Epochs bounds
EPOCH_BOUNDS = [
    (-500.0, 0.0),      # fx
    (0.0, 531.0),       # p1
    (531.0, 1031.0),    # d1
    (1031.0, 1562.0),   # p2
    (1562.0, 2062.0),   # d2
    (2062.0, 2593.0),   # p3
    (2593.0, 3093.0),   # d3
    (3093.0, 3624.0),   # p4
    (3624.0, 4124.0),   # d4
]

# User defined templates for rxrr, rrxr, rrrx conditions
TEMPLATES = {
    "O+": {
        "RXRR": [0, 0, 0, 1, 0, 0, 0, 0, 0],
        "RRXR": [0, 0, 0, 0, 0, 1, 0, 0, 0],
        "RRRX": [0, 0, 0, 0, 0, 0, 0, 1, 0]
    },
    "O*+": {
        "RXRR": [0, 0, 0, 1, 1, 0, 0, 0, 0],
        "RRXR": [0, 0, 0, 0, 0, 1, 1, 0, 0],
        "RRRX": [0, 0, 0, 0, 0, 0, 0, 1, 1]
    }
}


def run_permutation_test(rates: np.ndarray, template: np.ndarray, n_perm: int = 1000) -> float:
    """Computes empirical p-value using a vectorized correlation shuffle."""
    std_rates = np.std(rates)
    std_temp = np.std(template)
    if std_rates < 1e-5 or std_temp < 1e-5:
        return 1.0

    obs_cov = np.mean(rates * template) - np.mean(rates) * np.mean(template)
    obs_r = obs_cov / (std_rates * std_temp)

    # Pre-generate all random permutations of template
    shuffled_all = np.array([np.random.permutation(template) for _ in range(n_perm)])
    covs = np.mean(rates * shuffled_all, axis=1) - np.mean(rates) * np.mean(shuffled_all, axis=1)
    stds = np.std(shuffled_all, axis=1)
    stds[stds < 1e-5] = 1.0
    rs = covs / (std_rates * stds)

    return float(np.mean(rs >= obs_r))



def main():
    readiness = pd.read_csv(READINESS_CSV)
    ready = readiness[readiness["nwb_ok"] == True].copy()

    records = []

    print(f"Scanning {len(ready)} sessions for O+ and O*+ candidates...")
    for idx, row in ready.iterrows():
        prefix = row["session_prefix"]
        nwb_file = NWB_DIR / (prefix + "_rec.nwb")
        if not nwb_file.exists():
            nwb_file = NWB_DIR / (prefix + ".nwb")
        if not nwb_file.exists():
            continue

        try:
            sess = oa.read(str(nwb_file))
        except Exception as e:
            print(f"  Failed to load {prefix}: {e}")
            continue

        onsets_by_cond = {}
        for cond in ["RXRR", "RRXR", "RRRX"]:
            epochs = sess.get_epochs(phase=2, condition=cond, correct_only=True)
            onsets_by_cond[cond] = epochs["start_time"].values

        units = sess.get_units()
        for ui in range(len(units)):
            u_row = units.iloc[ui]
            spike_times = sess.get_spike_times(ui)
            if spike_times is None or len(spike_times) == 0:
                continue

            # Check trial stability (drift check)
            from scipy.stats import spearmanr
            all_onsets = []
            for c in ["RXRR", "RRXR", "RRRX"]:
                all_onsets.extend(onsets_by_cond[c])

            if len(all_onsets) < 20:
                continue

            # Compute Spearman correlation of total spike count vs trial index across correct trials
            trial_counts = []
            for onset in all_onsets:
                # searchsorted spike count in trial window
                idx_start = np.searchsorted(spike_times, onset - 0.5)
                idx_end = np.searchsorted(spike_times, onset + 4.124)
                trial_counts.append(idx_end - idx_start)
            trial_counts = np.array(trial_counts, dtype=float)
            
            # Check stability (spiking at least 1 per trial on average)
            if np.mean(trial_counts) < 1.0:
                continue

            drift_coef, _ = spearmanr(np.arange(len(trial_counts)), trial_counts)
            if np.isnan(drift_coef):
                drift_coef = 1.0
            
            # stability constraint: reject high-drift units (abs drift >= 0.45)
            if abs(drift_coef) >= 0.45:
                continue

            # Calculate firing rates for the 3 conditions (vectorized using searchsorted)
            cond_rates = {}
            valid = True
            for cond in ["RXRR", "RRXR", "RRRX"]:
                onsets = onsets_by_cond[cond]
                if len(onsets) < 5:
                    valid = False
                    break
                rates = np.zeros(len(EPOCH_BOUNDS))
                for ei, (t0_val, t1_val) in enumerate(EPOCH_BOUNDS):
                    dur = (t1_val - t0_val) / 1000.0
                    starts = onsets + t0_val / 1000.0
                    ends = onsets + t1_val / 1000.0
                    idx_starts = np.searchsorted(spike_times, starts)
                    idx_ends = np.searchsorted(spike_times, ends)
                    counts = idx_ends - idx_starts
                    rates[ei] = np.mean(counts) / dur
                cond_rates[cond] = rates

            if not valid:
                continue

            # Ensure non-zero firing during omission slot:
            # RXRR omission slot: p2 (index 3)
            # RRXR omission slot: p3 (index 5)
            # RRRX omission slot: p4 (index 7)
            if cond_rates["RXRR"][3] <= 0.0 or cond_rates["RRXR"][5] <= 0.0 or cond_rates["RRRX"][7] <= 0.0:
                continue

            # Check peak firing omission dominance constraint:
            # For O+ candidates, the maximum firing rate among the 9 epochs must be the omission slot
            # in at least 2 of the 3 conditions (more than 50% of the times).
            peak_match_count = 0
            if np.argmax(cond_rates["RXRR"]) == 3:
                peak_match_count += 1
            if np.argmax(cond_rates["RRXR"]) == 5:
                peak_match_count += 1
            if np.argmax(cond_rates["RRRX"]) == 7:
                peak_match_count += 1

            # Evaluate correlation for both patterns using concatenated 27-element vectors
            for key in ["O+", "O*+"]:
                # If checking O+ (Pulse), enforce peak firing dominance rule
                if key == "O+" and peak_match_count < 2:
                    continue

                # Concatenate the 3 conditions together
                obs_rates_concat = np.concatenate([cond_rates["RXRR"], cond_rates["RRXR"], cond_rates["RRRX"]])
                temp_concat = np.concatenate([TEMPLATES[key]["RXRR"], TEMPLATES[key]["RRXR"], TEMPLATES[key]["RRRX"]])

                if np.std(obs_rates_concat) > 1e-5:
                    r, _ = pearsonr(obs_rates_concat, temp_concat)
                else:
                    r = 0.0

                # Only run permutation test if Pearson correlation is high
                if r > 0.40:
                    p_val = run_permutation_test(obs_rates_concat, temp_concat, n_perm=1000)
                    if p_val < 0.05:
                        records.append({
                            "session_prefix": prefix,
                            "unit_row_idx": ui,
                            "unit_id": u_row.get("unit_id"),
                            "area": u_row.get("area"),
                            "layer": u_row.get("layer"),
                            "overall_rate": u_row.get("firing_rate"),
                            "pattern_type": key,
                            "mean_correlation": r,
                            "permutation_pval": p_val,
                            "quality": u_row.get("quality"),
                            "drift_coef": drift_coef,
                            "mean_spikes_per_trial": np.mean(trial_counts)
                        })

    df = pd.DataFrame(records)
    # Filter for stable units (overall rate > 0.5 Hz)
    df = df[df["overall_rate"] >= 0.5]
    df.to_csv(OUT_CSV, index=False)
    print(f"Saved results to {OUT_CSV.name}")

    print("\n=========================================================================")
    print("ALL DISCOVERED STABLE SIGNIFICANT OMISSION (O+ / O*+) UNITS")
    print("=========================================================================")
    print(df.to_string(index=False))


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    main()
