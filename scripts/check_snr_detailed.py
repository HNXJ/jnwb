import pandas as pd
import numpy as np
from pynwb import NWBHDF5IO
import glob

nwb_files = sorted(glob.glob("D:/analysis/nwb/*.nwb"))

all_snr = []
all_quality = []

for nwb_file in nwb_files:
    try:
        with NWBHDF5IO(nwb_file, "r") as io:
            nwb = io.read()
            units_df = nwb.units.to_dataframe()

            # Get SNR values
            snr = pd.to_numeric(units_df['snr'], errors='coerce')
            quality = units_df['quality']

            all_snr.extend(snr.values)
            all_quality.extend(quality.values)
    except Exception as e:
        print(f"Error reading {nwb_file}: {e}")

all_snr_series = pd.Series(all_snr)
all_quality_series = pd.Series(all_quality)

print("SNR Statistics:")
print(f"Total units: {len(all_snr)}")
print(f"SNR non-NaN: {all_snr_series.notna().sum()}")
print(f"SNR with inf: {np.isinf(all_snr_series).sum()}")
print(f"SNR == 0: {(all_snr_series == 0).sum()}")

# Remove infinities and NaNs for stats
snr_clean = all_snr_series.replace([np.inf, -np.inf], np.nan)
snr_valid = snr_clean.dropna()

print(f"\nSNR (excluding inf/NaN):")
print(f"Count: {len(snr_valid)}")
print(f"Min: {snr_valid.min():.4f}")
print(f"Max: {snr_valid.max():.4f}")
print(f"Mean: {snr_valid.mean():.4f}")
print(f"Median: {snr_valid.median():.4f}")

print(f"\nSNR >= 0.5 (excluding inf/NaN): {(snr_valid >= 0.5).sum()}")
print(f"SNR >= 0.75 (excluding inf/NaN): {(snr_valid >= 0.75).sum()}")
print(f"SNR > 0.75 (excluding inf/NaN): {(snr_valid > 0.75).sum()}")

print(f"\nQuality distribution:")
print(all_quality_series.value_counts())

# Cross-tabulation
print(f"\nQuality vs SNR >= 0.5:")
quality_snr_gt05 = (snr_valid >= 0.5).sum()
quality_snr_lt05 = (snr_valid < 0.5).sum()
print(f"SNR >= 0.5: {quality_snr_gt05}")
print(f"SNR < 0.5: {quality_snr_lt05}")
