import pandas as pd
from pynwb import NWBHDF5IO
import glob
import os

gdb = pd.read_csv("outputs/publication_figures/grand_database_6040_units.csv")

print("Grand database:")
print(f"Total units: {len(gdb)}")
print(f"Sessions: {sorted(gdb['session_id'].unique())}")

# Check NWB
nwb_files = sorted(glob.glob("D:/analysis/nwb/*.nwb"))
print(f"\nNWB files found: {len(nwb_files)}")

for nwb_file in nwb_files:
    bn = os.path.basename(nwb_file)
    sid = bn.split("ses-")[1].split("_")[0] if "ses-" in bn else bn.split("_")[0]

    with NWBHDF5IO(nwb_file, "r") as io:
        nwb = io.read()
        units_df = nwb.units.to_dataframe()

        gdb_count = len(gdb[gdb['session_id'] == int(sid)])
        nwb_count = len(units_df)

        print(f"\nSession {sid}:")
        print(f"  Grand DB: {gdb_count} units")
        print(f"  NWB: {nwb_count} units")

        if gdb_count != nwb_count:
            print(f"  ⚠️  MISMATCH!")
