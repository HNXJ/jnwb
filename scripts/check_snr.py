import pandas as pd
from pynwb import NWBHDF5IO
import glob

gdb = pd.read_csv("outputs/publication_figures/grand_database_6040_units.csv")

# Check if SNR column exists
print("Columns in grand database:")
snr_cols = [c for c in gdb.columns if 'snr' in c.lower()]
print(snr_cols)

# Check NWB for SNR
nwb_files = sorted(glob.glob("D:/analysis/nwb/*.nwb"))
if nwb_files:
    print(f"\nFound {len(nwb_files)} NWB files")

    # Aggregate across all sessions
    all_snr = []

    for nwb_file in nwb_files:
        try:
            with NWBHDF5IO(nwb_file, "r") as io:
                nwb = io.read()
                units_df = nwb.units.to_dataframe()
                snr = pd.to_numeric(units_df['snr'], errors='coerce')
                all_snr.extend(snr.values)
        except Exception as e:
            print(f"Error reading {nwb_file}: {e}")

    all_snr_series = pd.Series(all_snr)
    snr_gte_05 = (all_snr_series >= 0.5).sum()
    snr_total = all_snr_series.notna().sum()

    print(f"\nSNR across all units in NWB:")
    print(f"Units with SNR >= 0.5: {snr_gte_05}")
    print(f"Total units with SNR data: {snr_total}")
    print(f"SNR range: {all_snr_series.min():.2f} to {all_snr_series.max():.2f}")
    print(f"SNR mean: {all_snr_series.mean():.2f}")
else:
    print("No NWB files found")
