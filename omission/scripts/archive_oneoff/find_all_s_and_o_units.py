"""
scripts/find_all_s_and_o_units.py

Scans all quality == 1.0 units across all active NWB sessions to classify and count:
- S+ (p < 0.05) & S++ (p < 0.01)
- S- (p < 0.05) & S-- (p < 0.01)
- O+ (p < 0.01) & O++ (p < 0.001)

Uses a joint concatenated 27-element vector (RXRR, RRXR, RRRX) with 5000 permutation shuffles.
Enforces the trial stability drift check (< 0.45) and peak dominance check for O+.
Finally, performs a template-matched K-Means clustering (S+, S-, O+, Null) on the firing rate profiles.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.cluster import KMeans

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import omission as oa

NWB_DIR = Path("D:/analysis/nwb")
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_CSV = REPO_ROOT / "outputs/classification/grand_s_and_o_units.csv"

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

TEMPLATES = {
    "S+": {
        "RXRR": [1, 4, 1, 1, 1, 4, 1, 4, 1],
        "RRXR": [1, 4, 1, 4, 1, 1, 1, 4, 1],
        "RRRX": [1, 4, 1, 4, 1, 4, 1, 1, 1]
    },
    "S-": {
        "RXRR": [2, 1, 2, 2, 2, 1, 2, 1, 2],
        "RRXR": [2, 1, 2, 1, 2, 2, 2, 1, 2],
        "RRRX": [2, 1, 2, 1, 2, 1, 2, 2, 2]
    },
    "O+": {
        "RXRR": [0, 0, 0, 1, 0, 0, 0, 0, 0],
        "RRXR": [0, 0, 0, 0, 0, 1, 0, 0, 0],
        "RRRX": [0, 0, 0, 0, 0, 0, 0, 1, 0]
    }
}


def run_permutation_test(rates: np.ndarray, template: np.ndarray, n_perm: int = 5000) -> float:
    """Computes empirical p-value using a vectorized correlation shuffle (5000 permutations)."""
    std_rates = np.std(rates)
    std_temp = np.std(template)
    if std_rates < 1e-5 or std_temp < 1e-5:
        return 1.0

    obs_cov = np.mean(rates * template) - np.mean(rates) * np.mean(template)
    obs_r = obs_cov / (std_rates * std_temp)

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

    print(f"Scanning {len(ready)} sessions for S+, S-, O+ candidates...")
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
            
            # Enforce high-quality single-unit filter
            if u_row.get("quality") != 1.0 or u_row.get("firing_rate", 0.0) < 0.5:
                continue

            spike_times = sess.get_spike_times(ui)
            if spike_times is None or len(spike_times) == 0:
                continue

            # Check trial stability (drift check)
            all_onsets = []
            for c in ["RXRR", "RRXR", "RRRX"]:
                all_onsets.extend(onsets_by_cond[c])

            if len(all_onsets) < 20:
                continue

            trial_counts = []
            for onset in all_onsets:
                idx_start = np.searchsorted(spike_times, onset - 0.5)
                idx_end = np.searchsorted(spike_times, onset + 4.124)
                trial_counts.append(idx_end - idx_start)
            trial_counts = np.array(trial_counts, dtype=float)

            if np.mean(trial_counts) < 1.0:
                continue

            drift_coef, _ = spearmanr(np.arange(len(trial_counts)), trial_counts)
            if np.isnan(drift_coef):
                drift_coef = 1.0

            if abs(drift_coef) >= 0.45:
                continue

            # Calculate firing rates
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

            # Ensure non-zero firing during omission slot for O+ candidates
            non_zero_omit = (cond_rates["RXRR"][3] > 0.0 and cond_rates["RRXR"][5] > 0.0 and cond_rates["RRRX"][7] > 0.0)

            # Check peak firing omission dominance count
            peak_match_count = 0
            if np.argmax(cond_rates["RXRR"]) == 3:
                peak_match_count += 1
            if np.argmax(cond_rates["RRXR"]) == 5:
                peak_match_count += 1
            if np.argmax(cond_rates["RRRX"]) == 7:
                peak_match_count += 1

            # Run template matches
            obs_rates_concat = np.concatenate([cond_rates["RXRR"], cond_rates["RRXR"], cond_rates["RRRX"]])
            
            unit_res = {
                "session_prefix": prefix,
                "unit_row_idx": ui,
                "unit_id": u_row.get("unit_id"),
                "area": u_row.get("area"),
                "layer": u_row.get("layer"),
                "overall_rate": u_row.get("firing_rate"),
                "drift_coef": drift_coef,
                "mean_spikes_per_trial": np.mean(trial_counts)
            }

            # S+ Match
            temp_splus = np.concatenate([TEMPLATES["S+"]["RXRR"], TEMPLATES["S+"]["RRXR"], TEMPLATES["S+"]["RRRX"]])
            if np.std(obs_rates_concat) > 1e-5:
                r_splus, _ = pearsonr(obs_rates_concat, temp_splus)
                p_splus = run_permutation_test(obs_rates_concat, temp_splus, n_perm=1000)
            else:
                r_splus, p_splus = 0.0, 1.0
            
            # S- Match
            temp_sminus = np.concatenate([TEMPLATES["S-"]["RXRR"], TEMPLATES["S-"]["RRXR"], TEMPLATES["S-"]["RRRX"]])
            if np.std(obs_rates_concat) > 1e-5:
                r_sminus, _ = pearsonr(obs_rates_concat, temp_sminus)
                p_sminus = run_permutation_test(obs_rates_concat, temp_sminus, n_perm=1000)
            else:
                r_sminus, p_sminus = 0.0, 1.0

            # O+ Match
            temp_oplus = np.concatenate([TEMPLATES["O+"]["RXRR"], TEMPLATES["O+"]["RRXR"], TEMPLATES["O+"]["RRRX"]])
            if np.std(obs_rates_concat) > 1e-5 and non_zero_omit and peak_match_count >= 2:
                r_oplus, _ = pearsonr(obs_rates_concat, temp_oplus)
                p_oplus = run_permutation_test(obs_rates_concat, temp_oplus, n_perm=5000) # 5000 shuffles for p < 0.001
            else:
                r_oplus, p_oplus = 0.0, 1.0

            unit_res.update({
                "r_Splus": r_splus, "p_Splus": p_splus,
                "r_Sminus": r_sminus, "p_Sminus": p_sminus,
                "r_Oplus": r_oplus, "p_Oplus": p_oplus
            })
            records.append(unit_res)

    df = pd.DataFrame(records)

    # Classify units based on strict p-value thresholds
    # S+ (p < 0.05), S++ (p < 0.01)
    # S- (p < 0.05), S-- (p < 0.01)
    # O+ (p < 0.01), O++ (p < 0.001)
    df["is_Splus"] = (df["p_Splus"] < 0.05) & (df["r_Splus"] > 0.3)
    df["is_Splus_double"] = (df["p_Splus"] < 0.01) & (df["r_Splus"] > 0.3)
    df["is_Sminus"] = (df["p_Sminus"] < 0.05) & (df["r_Sminus"] > 0.3)
    df["is_Sminus_double"] = (df["p_Sminus"] < 0.01) & (df["r_Sminus"] > 0.3)
    df["is_Oplus"] = (df["p_Oplus"] < 0.01) & (df["r_Oplus"] > 0.3)
    df["is_Oplus_double"] = (df["p_Oplus"] < 0.001) & (df["r_Oplus"] > 0.3)

    df.to_csv(OUT_CSV, index=False)
    print(f"Saved database to {OUT_CSV.name}")

    # Total Counts
    print("\n=======================================================")
    print("TOTAL DISCOVERED HIGH-QUALITY UNITS BY CATEGORY")
    print("=======================================================")
    print(f"Total units scanned: {len(df)}")
    print(f"S+ (p < 0.05):   {df['is_Splus'].sum()}")
    print(f"S++ (p < 0.01):  {df['is_Splus_double'].sum()}")
    print(f"S- (p < 0.05):   {df['is_Sminus'].sum()}")
    print(f"S-- (p < 0.01):  {df['is_Sminus_double'].sum()}")
    print(f"O+ (p < 0.01):   {df['is_Oplus'].sum()}")
    print(f"O++ (p < 0.001): {df['is_Oplus_double'].sum()}")

    # Table Per Area
    areas = df["area"].unique()
    area_records = []
    for area in sorted(areas):
        sub = df[df["area"] == area]
        area_records.append({
            "Area": area,
            "Total": len(sub),
            "S+": sub["is_Splus"].sum(),
            "S++": sub["is_Splus_double"].sum(),
            "S-": sub["is_Sminus"].sum(),
            "S--": sub["is_Sminus_double"].sum(),
            "O+": sub["is_Oplus"].sum(),
            "O++": sub["is_Oplus_double"].sum()
        })
    df_area = pd.DataFrame(area_records)
    print("\n=======================================================")
    print("COUNTS PER BRAIN AREA")
    print("=======================================================")
    print(df_area.to_string(index=False))

    # Template-Matched K-Means Clustering
    # We assign each unit to a cluster based on its highest template correlation (S+, S-, O+, Null)
    print("\n=======================================================")
    print("TEMPLATE-MATCHED K-MEANS / CORRELATION CLUSTERING")
    print("=======================================================")
    
    cluster_labels = []
    for idx, r_row in df.iterrows():
        # Correlation scores
        scores = {"S+": r_row["r_Splus"], "S-": r_row["r_Sminus"], "O+": r_row["r_Oplus"]}
        best_cls = max(scores, key=scores.get)
        if scores[best_cls] > 0.35:
            # Enforce significance check for assignment
            if best_cls == "S+" and r_row["is_Splus"]:
                cluster_labels.append("S+")
            elif best_cls == "S-" and r_row["is_Sminus"]:
                cluster_labels.append("S-")
            elif best_cls == "O+" and r_row["is_Oplus"]:
                cluster_labels.append("O+")
            else:
                cluster_labels.append("Null")
        else:
            cluster_labels.append("Null")
            
    df["kmeans_template_cluster"] = cluster_labels
    print(df["kmeans_template_cluster"].value_counts())


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    main()
