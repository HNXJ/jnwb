#!/usr/bin/env python3
"""Check what quality values exist in NWB."""

from pathlib import Path
from pynwb import NWBHDF5IO
import pandas as pd

NWB_PATH = Path('d:/analysis/nwb/sub-C31o_ses-230823_rec.nwb')

with NWBHDF5IO(str(NWB_PATH), 'r', load_namespaces=True) as io:
    nwb = io.read()
    units_df = nwb.units.to_dataframe()

    print(f"Units shape: {units_df.shape}")
    print(f"\nQuality column unique values:")
    if 'quality' in units_df.columns:
        print(units_df['quality'].unique())
        print(f"\nQuality value counts:")
        print(units_df['quality'].value_counts())
    else:
        print("No quality column")

    print(f"\nAll string columns (quality indicators):")
    for col in units_df.columns:
        if units_df[col].dtype == 'object':
            unique_vals = units_df[col].nunique()
            if unique_vals < 20:
                print(f"{col}: {units_df[col].unique()[:10]}")
