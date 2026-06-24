#!/usr/bin/env python3
"""Check what columns are in units DataFrame after our enrichment."""

from pathlib import Path
from pynwb import NWBHDF5IO
import pandas as pd

NWB_PATH = Path('d:/analysis/nwb/sub-C31o_ses-230823_rec.nwb')

with NWBHDF5IO(str(NWB_PATH), 'r', load_namespaces=True) as io:
    nwb = io.read()
    units_df = nwb.units.to_dataframe().copy()

    print("Columns in units table:")
    print(units_df.columns.tolist())

    print("\nFirst 3 rows of key columns:")
    key_cols = ['cluster_id', 'peak_channel_id', 'quality', 'area', 'layer']
    existing_cols = [c for c in key_cols if c in units_df.columns]
    print(units_df[existing_cols].head(3))

    print(f"\nArea values:")
    if 'area' in units_df.columns:
        print(units_df['area'].value_counts())
        print(f"\nNull areas: {units_df['area'].isna().sum()}")
    else:
        print("No area column")
