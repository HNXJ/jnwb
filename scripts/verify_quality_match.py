import pandas as pd
import numpy as np
from pynwb import NWBHDF5IO
import glob

# Load grand database
gdb = pd.read_csv("outputs/publication_figures/grand_database_6040_units.csv")
print(f"Grand database units: {len(gdb)}")
print(f"is_quality_good == True: {(gdb['is_quality_good'] == True).sum()}")
print(f"is_quality_good == False: {(gdb['is_quality_good'] == False).sum()}")

# Get quality from NWB files
nwb_map = {}
nwb_files = sorted(glob.glob("D:/analysis/nwb/*.nwb"))

for nwb_file in nwb_files:
    try:
        with NWBHDF5IO(nwb_file, "r") as io:
            nwb = io.read()
            units_df = nwb.units.to_dataframe()

            quality = pd.to_numeric(units_df['quality'], errors='coerce')

            for idx, row in units_df.iterrows():
                cluster_id = int(row['cluster_id'])
                quality_val = quality.iloc[idx]
                nwb_map[(idx, cluster_id)] = quality_val
    except Exception as e:
        print(f"Error: {e}")

print(f"\nNWB units found: {len(nwb_map)}")

# Compare
mismatches = 0
matches = 0
for _, row in gdb.iterrows():
    unit_id = int(row['unit_id'])
    session_id = row['session_id']
    is_quality_good = row['is_quality_good']

    # Try to find in NWB
    for (idx, cluster_id), nwb_quality in nwb_map.items():
        if cluster_id == unit_id:
            if (is_quality_good == 1) == (nwb_quality == 1.0):
                matches += 1
            else:
                mismatches += 1
            break

print(f"Matches between gdb is_quality_good and NWB quality: {matches}")
print(f"Mismatches: {mismatches}")

# Let me also check if maybe is_quality_good should be combined with SNR
gdb_copy = gdb.copy()
print(f"\nTotal units in grand database: {len(gdb_copy)}")
print(f"is_quality_good == 1: {(gdb_copy['is_quality_good'] == True).sum()}")

# Maybe the user is saying we should define good units as presence_ratio-based?
# Or that we should use SNR criteria from stable_plus definition?
print(f"\nstable_plus == True: {(gdb_copy['stable_plus'] == True).sum()}")
print(f"is_stable == True: {(gdb_copy['is_stable'] == True).sum()}")
