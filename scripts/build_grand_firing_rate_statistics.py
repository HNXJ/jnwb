"""
scripts/build_grand_firing_rate_statistics.py

Computes grand firing rate statistics and stable trial mean rate comparisons
across all active NWB sessions. Discovers unstable trials (rate drops > 50%)
and calculates the grand mean of stable trials to preserve maximum data.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa

NWB_DIR = Path("D:/analysis/nwb")
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"
OUT_CSV = REPO_ROOT / "outputs/classification/grand_stable_firing_rates.csv"
REPORT_MD = REPO_ROOT / "outputs/classification/grand_firing_rate_report.md"


def analyze_unit_stable_rate(spike_times: np.ndarray, onsets: np.ndarray, trial_dur: float = 4.624) -> tuple[float, float, float]:
    """Calculates overall mean rate, stable trials mean rate, and fraction of kept stable trials."""
    if len(onsets) == 0 or len(spike_times) == 0:
        return 0.0, 0.0, 0.0

    trial_rates = []
    for onset in onsets:
        t0, t1 = onset - 0.5, onset + 4.124
        c = np.sum((spike_times >= t0) & (spike_times < t1))
        trial_rates.append(c / trial_dur)

    trial_rates = np.array(trial_rates)
    overall_mean = float(np.mean(trial_rates))

    # Determine stable trials: trials where rate does not drop by > 50% of the median rate
    median_rate = np.median(trial_rates)
    if median_rate < 0.1:
        # For very low rate units, use absolute threshold
        stable_mask = trial_rates >= 0.0
    else:
        stable_mask = trial_rates >= (0.5 * median_rate)

    stable_rates = trial_rates[stable_mask]
    stable_mean = float(np.mean(stable_rates)) if len(stable_rates) > 0 else 0.0
    keep_fraction = float(len(stable_rates) / len(trial_rates))

    return overall_mean, stable_mean, keep_fraction


def main():
    readiness = pd.read_csv(READINESS_CSV)
    ready = readiness[readiness["nwb_ok"] == True].copy()

    records = []

    print(f"Analyzing stable trial firing rates for {len(ready)} sessions...")
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

        # Use all correct RRRR trials as baseline
        epochs = sess.get_epochs(phase=2, condition="RRRR", correct_only=True)
        onsets = epochs["start_time"].values
        if len(onsets) == 0:
            continue

        units = sess.get_units()
        for ui in range(len(units)):
            u_row = units.iloc[ui]
            spike_times = sess.get_spike_times(ui)
            if spike_times is None:
                continue

            overall_m, stable_m, keep_f = analyze_unit_stable_rate(spike_times, onsets)
            records.append({
                "session_prefix": prefix,
                "unit_idx": ui,
                "unit_id": u_row.get("unit_id"),
                "area": u_row.get("area"),
                "layer": u_row.get("layer"),
                "quality": u_row.get("quality"),
                "raw_overall_rate": u_row.get("firing_rate"),
                "stable_trial_mean": stable_m,
                "stable_trials_keep_fraction": keep_f
            })

    df = pd.DataFrame(records)
    df.to_csv(OUT_CSV, index=False)
    print(f"Saved database to {OUT_CSV.name}")

    # Build Markdown Report
    total_units = len(df)
    mean_raw = df["raw_overall_rate"].mean()
    mean_stable = df["stable_trial_mean"].mean()

    # Percentiles
    p_raw = df["raw_overall_rate"].quantile([0.1, 0.25, 0.5, 0.75, 0.9, 0.95])
    p_stable = df["stable_trial_mean"].quantile([0.1, 0.25, 0.5, 0.75, 0.9, 0.95])

    session_counts = df["session_prefix"].value_counts()

    md_content = f"""# Grand Firing Rate and Stable Trial Statistics Report

- **Total Sessions Analyzed**: {len(session_counts)}
- **Total Units Evaluated**: {total_units}
- **Raw Firing Rate Mean**: {mean_raw:.3f} Hz
- **Grand Stable-Trial Firing Rate Mean**: {mean_stable:.3f} Hz
- **Average Fraction of Trials Kept per Unit**: {df["stable_trials_keep_fraction"].mean() * 100:.1f}%

## 1. Firing Rate Percentiles Comparison

| Percentile | Raw Firing Rate (Hz) | Stable-Trial Firing Rate (Hz) |
|---|---|---|
| **10%** | {p_raw[0.10]:.3f} | {p_stable[0.10]:.3f} |
| **25%** | {p_raw[0.25]:.3f} | {p_stable[0.25]:.3f} |
| **50% (Median)** | {p_raw[0.50]:.3f} | {p_stable[0.50]:.3f} |
| **75%** | {p_raw[0.75]:.3f} | {p_stable[0.75]:.3f} |
| **90%** | {p_raw[0.90]:.3f} | {p_stable[0.90]:.3f} |
| **95%** | {p_raw[0.95]:.3f} | {p_stable[0.95]:.3f} |

## 2. Unit Counts and Stable Firing Rate by Session

| Session Prefix | Unit Count | Raw Rate Mean (Hz) | Stable Rate Mean (Hz) | Kept Trial Fraction |
|---|---|---|---|---|
"""
    for sess_id in sorted(session_counts.index):
        sub_df = df[df["session_prefix"] == sess_id]
        md_content += (f"| `{sess_id}` | {len(sub_df)} | {sub_df['raw_overall_rate'].mean():.2f} | "
                       f"{sub_df['stable_trial_mean'].mean():.2f} | {sub_df['stable_trials_keep_fraction'].mean() * 100:.1f}% |\n")

    md_content += """
## 3. Stable Firing Rate by Area

| Area | Unit Count | Raw Rate Mean (Hz) | Stable Rate Mean (Hz) | Kept Trial Fraction |
|---|---|---|---|---|
"""
    area_counts = df["area"].value_counts()
    for area in sorted(area_counts.index):
        sub_df = df[df["area"] == area]
        md_content += (f"| **{area}** | {len(sub_df)} | {sub_df['raw_overall_rate'].mean():.2f} | "
                       f"{sub_df['stable_trial_mean'].mean():.2f} | {sub_df['stable_trials_keep_fraction'].mean() * 100:.1f}% |\n")

    REPORT_MD.write_text(md_content, encoding="utf-8")
    print(f"Saved markdown report to {REPORT_MD.name}")


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    main()
