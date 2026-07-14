"""
scripts/classify_s_s_statistically.py

Loads the spiking rate database ({session_prefix}_spiking_rate.h5) and units metadata,
performs Mann-Whitney U-tests and independent t-tests comparing firing rates during
stimulus presentation halves (p1_1, p1_2) vs. delay period halves (d1_1, d1_2) across trials.

Classifies units as:
- Statistically significant S+ (significant increase in stimulus vs. delay, p < 0.05)
- Statistically significant S- (significant decrease in stimulus vs. delay, p < 0.05)
- Null (no significant difference)

Outputs a classification summary report and saves the updated unit metadata table.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DB_DIR = Path("D:/workspace/data/connectivity_databases")
OUT_DIR = REPO_ROOT / "outputs/classification"


def process_statistical_classification(session_prefix: str, cond: str = "RRRR") -> None:
    spiking_h5 = DB_DIR / f"{session_prefix}_spiking_rate.h5"
    meta_csv = DB_DIR / f"{session_prefix}_units_metadata.csv"

    if not spiking_h5.exists() or not meta_csv.exists():
        print(f"  [ERROR] Database files for {session_prefix} do not exist under {DB_DIR}")
        return

    # Load metadata
    df_meta = pd.read_csv(meta_csv)
    n_units = len(df_meta)

    # Load spiking rates for the chosen condition (default: RRRR)
    with h5py.File(spiking_h5, "r") as sf:
        if cond not in sf:
            print(f"  [ERROR] Condition {cond} not found in spiking database.")
            return
        rates = sf[cond][:]  # (n_units, n_events, n_trials)

    # Event indices
    # We compare:
    #   p1_1 (index 2) + p1_2 (index 3) vs d1_1 (index 4) + d1_2 (index 5)
    # Firing rates are spikes per second.
    p1_rates = (rates[:, 2, :] + rates[:, 3, :]) / 2.0  # (n_units, n_trials)
    d1_rates = (rates[:, 4, :] + rates[:, 5, :]) / 2.0  # (n_units, n_trials)

    u_pvals = []
    t_pvals = []
    mean_diffs = []
    stat_labels = []

    for ui in range(n_units):
        p1_trial_rates = p1_rates[ui, :]
        d1_trial_rates = d1_rates[ui, :]

        # Mann-Whitney U test
        u_stat, u_pval = stats.mannwhitneyu(p1_trial_rates, d1_trial_rates, alternative="two-sided")
        # Independent T-test
        t_stat, t_pval = stats.ttest_ind(p1_trial_rates, d1_trial_rates, equal_var=False)

        mean_diff = np.mean(p1_trial_rates) - np.mean(d1_trial_rates)

        u_pvals.append(u_pval)
        t_pvals.append(t_pval)
        mean_diffs.append(mean_diff)

        # Classification based on U-test (robust to mean-matching outlier issues)
        if u_pval < 0.05:
            if mean_diff > 0:
                stat_labels.append("S+")
            else:
                stat_labels.append("S-")
        else:
            stat_labels.append("Null")

    # Add columns to metadata
    df_meta["mwu_p_val"] = u_pvals
    df_meta["ttest_p_val"] = t_pvals
    df_meta["p1_minus_d1_mean_diff"] = mean_diffs
    df_meta["stat_s_label"] = stat_labels

    out_csv = OUT_DIR / f"{session_prefix}_statistical_s_classification.csv"
    df_meta.to_csv(out_csv, index=False)
    print(f"\nStatistical S+/S- classification completed for {session_prefix}:")
    print(f"  Total units: {n_units}")
    print(f"  MWU S+ (Stimulus > Delay, p < 0.05): {sum(df_meta['stat_s_label'] == 'S+')}")
    print(f"  MWU S- (Stimulus < Delay, p < 0.05): {sum(df_meta['stat_s_label'] == 'S-')}")
    print(f"  MWU Null (No sig diff):              {sum(df_meta['stat_s_label'] == 'Null')}")
    print(f"  Saved updated table to {out_csv.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Statistical S+/S- unit classification.")
    parser.add_argument("--session", default="sub-C31o_ses-230823", help="Session prefix.")
    parser.add_argument("--condition", default="RRRR", help="Condition group to evaluate.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    process_statistical_classification(args.session, args.condition)


if __name__ == "__main__":
    main()
