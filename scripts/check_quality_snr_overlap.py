import pandas as pd
import numpy as np
from pynwb import NWBHDF5IO
import glob

nwb_files = sorted(glob.glob("D:/analysis/nwb/*.nwb"))

results = []

for nwb_file in nwb_files:
    try:
        with NWBHDF5IO(nwb_file, "r") as io:
            nwb = io.read()
            units_df = nwb.units.to_dataframe()

            snr = pd.to_numeric(units_df['snr'], errors='coerce')
            quality = pd.to_numeric(units_df['quality'], errors='coerce')

            for idx, row in units_df.iterrows():
                snr_val = snr.iloc[idx]
                quality_val = quality.iloc[idx]
                results.append({
                    'snr': snr_val,
                    'quality': quality_val,
                })
    except Exception as e:
        print(f"Error: {e}")

df = pd.DataFrame(results)

# Remove infinite values
df_clean = df.copy()
df_clean = df_clean.replace([np.inf, -np.inf], np.nan)

print("Cross-tabulation: Quality vs SNR >= 0.5")
print("\nQuality=1.0, SNR>=0.5:", ((df_clean['quality'] == 1.0) & (df_clean['snr'] >= 0.5)).sum())
print("Quality=1.0, SNR<0.5:", ((df_clean['quality'] == 1.0) & (df_clean['snr'] < 0.5)).sum())
print("Quality=0.0, SNR>=0.5:", ((df_clean['quality'] == 0.0) & (df_clean['snr'] >= 0.5)).sum())
print("Quality=0.0, SNR<0.5:", ((df_clean['quality'] == 0.0) & (df_clean['snr'] < 0.5)).sum())

print("\nUnion (Quality=1.0 OR SNR>=0.5):", ((df_clean['quality'] == 1.0) | (df_clean['snr'] >= 0.5)).sum())
print("Intersection (Quality=1.0 AND SNR>=0.5):", ((df_clean['quality'] == 1.0) & (df_clean['snr'] >= 0.5)).sum())

print("\nQuality breakdown:")
print(f"Quality == 1.0: {(df_clean['quality'] == 1.0).sum()}")
print(f"Quality == 0.0: {(df_clean['quality'] == 0.0).sum()}")

print("\nSNR >= 0.5 breakdown:")
print(f"SNR >= 0.5: {(df_clean['snr'] >= 0.5).sum()}")
print(f"SNR < 0.5: {(df_clean['snr'] < 0.5).sum()}")
