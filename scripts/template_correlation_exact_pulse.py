"""
scripts/template_correlation_exact_pulse.py

Scans all units in sub-C31o_ses-230823 and correlates their 9-epoch firing rate vectors
against the user-defined ideal templates:
1. S+: RRRR=[1,4,1,4,1,4,1,4,1], RXRR=[1,4,1,1,1,4,1,4,1], RRXR=[1,4,1,4,1,1,1,4,1], RRRX=[1,4,1,4,1,4,1,1,1]
2. S-: RRRR=[2,1,2,1,2,1,2,1,2], RXRR=[2,1,2,2,2,1,2,1,2], RRXR=[2,1,2,1,2,2,2,1,2], RRRX=[2,1,2,1,2,1,2,2,2]
3. O+: RRRR=[1,1,1,1,1,1,1,1,1], RXRR=[1,1,1,4,1,1,1,1,1], RRXR=[1,1,1,1,1,4,1,1,1], RRRX=[1,1,1,1,1,1,1,4,1]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa

NWB_PATH = "D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb"
CONDITIONS = ["RRRR", "RXRR", "RRXR", "RRRX"]

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

# Exact templates from user specification
TEMPLATES = {
    "S+": {
        "RRRR": [1, 4, 1, 4, 1, 4, 1, 4, 1],
        "RXRR": [1, 4, 1, 1, 1, 4, 1, 4, 1],
        "RRXR": [1, 4, 1, 4, 1, 1, 1, 4, 1],
        "RRRX": [1, 4, 1, 4, 1, 4, 1, 1, 1]
    },
    "S-": {
        "RRRR": [2, 1, 2, 1, 2, 1, 2, 1, 2],
        "RXRR": [2, 1, 2, 2, 2, 1, 2, 1, 2],
        "RRXR": [2, 1, 2, 1, 2, 2, 2, 1, 2],
        "RRRX": [2, 1, 2, 1, 2, 1, 2, 2, 2]
    },
    "O+": {
        "RRRR": [1, 1, 1, 1, 1, 1, 1, 1, 1],
        "RXRR": [1, 1, 1, 4, 1, 1, 1, 1, 1],
        "RRXR": [1, 1, 1, 1, 1, 4, 1, 1, 1],
        "RRRX": [1, 1, 1, 1, 1, 1, 1, 4, 1]
    }
}


def main():
    sess = oa.read(NWB_PATH)
    units_df = sess.get_units()
    n_units = len(units_df)

    # Extract trials for the 4 conditions
    onsets_by_cond = {}
    for cond in CONDITIONS:
        epochs = sess.get_epochs(phase=2, condition=cond, correct_only=True)
        onsets_by_cond[cond] = epochs["start_time"].values

    # Precalculate per-epoch firing rates for all units
    # Shape: (n_units, n_conditions, 9)
    rates = np.zeros((n_units, len(CONDITIONS), len(EPOCH_BOUNDS)))

    for ui in range(n_units):
        spike_times = sess.get_spike_times(ui)
        if spike_times is None or len(spike_times) == 0:
            continue
        for ci, cond in enumerate(CONDITIONS):
            onsets = onsets_by_cond[cond]
            if len(onsets) == 0:
                continue
            for ei, (t0, t1) in enumerate(EPOCH_BOUNDS):
                dur = (t1 - t0) / 1000.0
                counts = [
                    np.sum((spike_times >= onset + t0 / 1000.0) & (spike_times < onset + t1 / 1000.0))
                    for onset in onsets
                ]
                rates[ui, ci, ei] = np.mean(counts) / dur

    # Correlate with templates
    records = []
    for ui in range(n_units):
        row = units_df.iloc[ui]
        u_records = {"unit_idx": ui, "unit_id": row.get("unit_id"), "area": row.get("area"), "mean_rate": row.get("firing_rate")}

        for key, cond_templates in TEMPLATES.items():
            corrs = []
            for ci, cond in enumerate(CONDITIONS):
                vec = rates[ui, ci, :]
                temp = np.array(cond_templates[cond])
                # Pearson correlation
                if np.std(vec) > 1e-5 and np.std(temp) > 1e-5:
                    r, _ = pearsonr(vec, temp)
                    corrs.append(r)
                else:
                    corrs.append(0.0)
            u_records[f"r_{key}"] = np.mean(corrs)

        records.append(u_records)

    df_res = pd.DataFrame(records)

    # Output Top matches
    for key in ["S+", "S-", "O+"]:
        print(f"\n=======================================================")
        print(f"Top 10 Exact Pulse matches for: {key}")
        print(f"=======================================================")
        top = df_res.sort_values(f"r_{key}", ascending=False).head(10)
        print(top[["unit_idx", "unit_id", "area", "mean_rate", f"r_{key}"]].to_string(index=False))


if __name__ == "__main__":
    main()
