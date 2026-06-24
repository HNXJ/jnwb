#!/usr/bin/env python3
"""Check intervals table."""

from pathlib import Path
from pynwb import NWBHDF5IO
import pandas as pd

NWB_PATH = Path('d:/analysis/nwb/sub-C31o_ses-230823_rec.nwb')

with NWBHDF5IO(str(NWB_PATH), 'r', load_namespaces=True) as io:
    nwb = io.read()
    intervals = nwb.intervals['omission_glo_passive'].to_dataframe()

    print(f"Intervals shape: {intervals.shape}")
    print(f"\nFirst 5 rows:")
    print(intervals.head())

    print(f"\nKey columns:")
    for col in ['stimulus_number', 'task_condition_number', 'correct', 'trial_num']:
        if col in intervals.columns:
            print(f"\n{col}:")
            print(f"  Unique values: {sorted(intervals[col].unique()[:10])}")
            print(f"  Range: {intervals[col].min()} to {intervals[col].max()}")
        else:
            print(f"{col}: NOT FOUND")
