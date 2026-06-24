import pandas as pd
import numpy as np

comp = pd.read_csv("outputs/publication_figures/comprehensive_grand_database_all_units.csv")

print("=== Unit Quality Thresholds ===\n")

# Basic counts
quality_1 = (comp['quality'] == 1.0).sum()
print(f"Quality == 1.0: {quality_1}")

pr = pd.to_numeric(comp['presence_ratio'], errors='coerce')
pr_90 = (pr >= 0.90).sum()
pr_85 = (pr >= 0.85).sum()
pr_80 = (pr >= 0.80).sum()

print(f"Presence ratio >= 0.90: {pr_90}")
print(f"Presence ratio >= 0.85: {pr_85}")
print(f"Presence ratio >= 0.80: {pr_80}")

snr = pd.to_numeric(comp['snr'], errors='coerce')
snr_05 = (snr > 0.5).sum()
print(f"SNR > 0.5: {snr_05}")

# Combinations
print(f"\n=== Combinations ===\n")

mask_q1 = comp['quality'] == 1.0
mask_pr90 = pr >= 0.90
mask_snr05 = snr > 0.5

count1 = (mask_q1 | mask_pr90).sum()
print(f"Quality==1.0 OR PR>=0.90: {count1}")

count2 = (mask_q1 | mask_snr05).sum()
print(f"Quality==1.0 OR SNR>0.5: {count2}")

count3 = (mask_q1 & mask_pr90).sum()
print(f"Quality==1.0 AND PR>=0.90: {count3}")

# Check individual sessions
print(f"\n=== By Session ===\n")
for sess in sorted(comp['session_id'].unique()):
    sess_mask = comp['session_id'] == sess
    sess_q1 = (comp[sess_mask]['quality'] == 1.0).sum()
    print(f"Session {sess}: {sess_q1} units with quality==1.0")

# Total
print(f"\nTotal across all sessions: {quality_1}")
