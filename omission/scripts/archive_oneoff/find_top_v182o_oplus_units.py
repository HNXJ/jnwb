"""
scripts/find_top_v182o_oplus_units.py

Finds and lists the most correlated O+ units across ALL units (any quality) in V182o sessions,
sorted by Pearson correlation.
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

import omission as oa

NWB_DIR = Path("D:/analysis/nwb")
V182O_SESSIONS = [
    "sub-V182o_ses-260629",
    "sub-V182o_ses-260702",
    "sub-V182o_ses-260706",
    "sub-V182o_ses-260708"
]

EPOCH_BOUNDS = [
    (-500.0, 0.0), (0.0, 531.0), (531.0, 1031.0),
    (1031.0, 1562.0), (1562.0, 2062.0), (2062.0, 2593.0),
    (2593.0, 3093.0), (3093.0, 3624.0), (3624.0, 4124.0)
]

TEMPLATE_OPLUS = {
    "RXRR": [0, 0, 0, 1, 0, 0, 0, 0, 0],
    "RRXR": [0, 0, 0, 0, 0, 1, 0, 0, 0],
    "RRRX": [0, 0, 0, 0, 0, 0, 0, 1, 0]
}


def main():
    records = []

    print("Scanning V182o sessions...")
    for prefix in V182O_SESSIONS:
        nwb_file = NWB_DIR / (prefix + "_rec.nwb")
        if not nwb_file.exists():
            nwb_file = NWB_DIR / (prefix + ".nwb")
        if not nwb_file.exists():
            continue

        sess = oa.read(str(nwb_file))
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

            cond_rates = {}
            valid = True
            for cond in ["RXRR", "RRXR", "RRRX"]:
                onsets = onsets_by_cond[cond]
                if len(onsets) < 5:
                    valid = False
                    break
                rates = np.zeros(len(EPOCH_BOUNDS))
                for ei, (t0, t1) in enumerate(EPOCH_BOUNDS):
                    dur = (t1 - t0) / 1000.0
                    starts = onsets + t0 / 1000.0
                    ends = onsets + t1 / 1000.0
                    idx_starts = np.searchsorted(spike_times, starts)
                    idx_ends = np.searchsorted(spike_times, ends)
                    counts = idx_ends - idx_starts
                    rates[ei] = np.mean(counts) / dur
                cond_rates[cond] = rates

            if not valid:
                continue

            # Concatenate conditions
            obs_rates_concat = np.concatenate([cond_rates["RXRR"], cond_rates["RRXR"], cond_rates["RRRX"]])
            temp_concat = np.concatenate([TEMPLATE_OPLUS["RXRR"], TEMPLATE_OPLUS["RRXR"], TEMPLATE_OPLUS["RRRX"]])

            if np.std(obs_rates_concat) > 1e-5:
                r, _ = pearsonr(obs_rates_concat, temp_concat)
            else:
                r = 0.0

            records.append({
                "session_prefix": prefix,
                "unit_idx": ui,
                "unit_id": u_row.get("unit_id"),
                "area": u_row.get("area"),
                "layer": u_row.get("layer"),
                "overall_rate": u_row.get("firing_rate"),
                "quality": u_row.get("quality"),
                "r_Oplus": r
            })

    df = pd.DataFrame(records)
    df_sorted = df.sort_values("r_Oplus", ascending=False)
    
    print("\n=========================================================================================")
    print("TOP 30 V182o O+ TEMPLATE MATCHES (ANY QUALITY, ALL UNITS)")
    print("=========================================================================================")
    print(df_sorted.head(30).to_string(index=False))


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    main()
