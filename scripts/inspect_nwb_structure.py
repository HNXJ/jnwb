#!/usr/bin/env python3
"""
Inspect NWB structure to understand what data is available.
"""

from pathlib import Path
from pynwb import NWBHDF5IO
import pandas as pd

NWB_PATH = Path('d:/analysis/nwb/sub-C31o_ses-230823_rec.nwb')

print(f"Inspecting: {NWB_PATH}")

with NWBHDF5IO(str(NWB_PATH), 'r', load_namespaces=True) as io:
    nwb = io.read()

    # Check units
    print("\n=== UNITS TABLE ===")
    if nwb.units is not None:
        units_df = nwb.units.to_dataframe()
        print(f"Shape: {units_df.shape}")
        print(f"Columns: {units_df.columns.tolist()}")
        print(f"\nFirst 3 rows:")
        print(units_df.head(3))
        print(f"\nData types:")
        print(units_df.dtypes)
    else:
        print("No units table")

    # Check electrodes
    print("\n=== ELECTRODES TABLE ===")
    if nwb.electrodes is not None:
        elec_df = nwb.electrodes.to_dataframe()
        print(f"Shape: {elec_df.shape}")
        print(f"Columns: {elec_df.columns.tolist()}")
        print(f"\nFirst 3 rows:")
        print(elec_df.head(3))

        # Check location column for area info
        if 'location' in elec_df.columns:
            print(f"\nUnique locations: {elec_df['location'].unique()[:10]}")
    else:
        print("No electrodes table")

    # Check intervals
    print("\n=== INTERVALS ===")
    print(f"Available intervals: {list(nwb.intervals.keys())}")

    if 'omission_glo_passive' in nwb.intervals:
        intervals_df = nwb.intervals['omission_glo_passive'].to_dataframe()
        print(f"Interval shape: {intervals_df.shape}")
        print(f"Interval columns: {intervals_df.columns.tolist()}")
        print(f"\nFirst 3 rows:")
        print(intervals_df.head(3))

print("\n[OK] Structure inspection complete")
