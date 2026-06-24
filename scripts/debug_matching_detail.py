import pandas as pd
from pynwb import NWBHDF5IO
import glob
import os

gdb = pd.read_csv("outputs/publication_figures/grand_database_6040_units.csv")

nwb_files = sorted(glob.glob("D:/analysis/nwb/*.nwb"))

# Check one session in detail
test_session = 230630
print(f"Testing session {test_session}...\n")

gdb_sess = gdb[gdb['session_id'] == test_session]
print(f"Grand DB units: {len(gdb_sess)}")
print(f"Grand DB unit_ids: {sorted(gdb_sess['unit_id'].unique())[:20]}")

for nwb_file in nwb_files:
    bn = os.path.basename(nwb_file)
    sid = bn.split("ses-")[1].split("_")[0] if "ses-" in bn else bn.split("_")[0]

    if int(sid) != test_session:
        continue

    with NWBHDF5IO(nwb_file, "r") as io:
        nwb = io.read()
        units_df = nwb.units.to_dataframe()

        print(f"\nNWB units: {len(units_df)}")

        # Check cluster_id format
        cluster_ids = pd.to_numeric(units_df['cluster_id'], errors='coerce')
        print(f"NWB cluster_ids: {sorted(cluster_ids.unique())[:20]}")

        # Try matching
        matched = 0
        for _, gdb_row in gdb_sess.iterrows():
            gdb_unit_id = int(gdb_row['unit_id'])
            # Check if this unit_id exists in NWB cluster_ids
            if (cluster_ids == gdb_unit_id).any():
                matched += 1

        print(f"\nMatched units: {matched} / {len(gdb_sess)}")

        # Check for units in NWB not in grand DB
        nwb_only = 0
        for cluster_id in cluster_ids.unique():
            if pd.isna(cluster_id):
                continue
            if not (gdb_sess['unit_id'] == int(cluster_id)).any():
                nwb_only += 1

        print(f"Units in NWB not in grand DB: {nwb_only}")
