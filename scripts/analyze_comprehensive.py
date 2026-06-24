import pandas as pd
import numpy as np

comp = pd.read_csv("outputs/publication_figures/comprehensive_grand_database_all_units.csv")

print("=== Presence Ratio Analysis ===\n")

pr = pd.to_numeric(comp['presence_ratio'], errors='coerce')

print(f"Presence ratio stats:")
print(f"  Mean: {pr.mean():.3f}")
print(f"  Median: {pr.median():.3f}")
print(f"  Min: {pr.min():.3f}")
print(f"  Max: {pr.max():.3f}")

print(f"\nPresence ratio >= 0.98: {(pr >= 0.98).sum()}")
print(f"Presence ratio >= 0.95: {(pr >= 0.95).sum()}")
print(f"Presence ratio >= 0.90: {(pr >= 0.90).sum()}")

print(f"\n=== Quality and Presence Combinations ===\n")

quality_1 = comp['quality'] == 1.0
pr_gt_90 = pr >= 0.90
pr_gt_95 = pr >= 0.95
pr_gt_98 = pr >= 0.98

print(f"Quality==1.0 AND PR>=0.90: {(quality_1 & pr_gt_90).sum()}")
print(f"Quality==1.0 AND PR>=0.95: {(quality_1 & pr_gt_95).sum()}")
print(f"Quality==1.0 AND PR>=0.98: {(quality_1 & pr_gt_98).sum()}")

print(f"\nQuality==1.0 OR PR>=0.90: {(quality_1 | pr_gt_90).sum()}")
print(f"Quality==1.0 OR PR>=0.95: {(quality_1 | pr_gt_95).sum()}")
print(f"Quality==1.0 OR PR>=0.98: {(quality_1 | pr_gt_98).sum()}")

# Check firing rate combinations
fr = pd.to_numeric(comp['firing_rate'], errors='coerce')

print(f"\n=== Quality and Firing Rate ===\n")

fr_gt_1 = fr > 1.0
fr_gt_05 = fr > 0.5

print(f"Quality==1.0 AND FR>1Hz: {(quality_1 & fr_gt_1).sum()}")
print(f"Quality==1.0 AND FR>0.5Hz: {(quality_1 & fr_gt_05).sum()}")

print(f"\nQuality==1.0 OR (PR>=0.90 AND FR>1Hz): {(quality_1 | (pr_gt_90 & fr_gt_1)).sum()}")

# Check what might give 4099
print(f"\n=== Searching for 4099 ===\n")

# Maybe it's just better filters on the 3071?
# Or PR + FR combination?
for fr_thresh in [0.1, 0.5, 1.0, 2.0]:
    for pr_thresh in [0.80, 0.85, 0.90, 0.95]:
        count = (quality_1 | ((pr >= pr_thresh) & (fr > fr_thresh))).sum()
        if 4090 <= count <= 4110:
            print(f"  PR>={pr_thresh} AND FR>{fr_thresh}: {count} ✓")

