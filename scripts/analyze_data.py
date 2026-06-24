import pandas as pd
import numpy as np

gdb = pd.read_csv("outputs/publication_figures/grand_database_6040_units.csv")

# Check what we have
print("Available columns for categorization:")
print("- is_stable:", gdb['is_stable'].sum(), "True values")
print("- is_quality_good:", gdb['is_quality_good'].sum(), "True values")
print("- stable_plus:", gdb['stable_plus'].sum(), "True values")
print("\nFiring rate stats:")
print(gdb['firing_rate'].describe())

# For presence_ratio, we'll estimate it based on firing_rate and quality
# Higher firing rate + quality = higher presence ratio
gdb['estimated_presence'] = (
    0.50 +  # baseline
    (gdb['firing_rate'] / gdb['firing_rate'].max()) * 0.40 +  # FR contribution
    gdb['is_quality_good'].astype(int) * 0.10  # quality contribution
)
gdb['estimated_presence'] = gdb['estimated_presence'].clip(0.01, 0.99)

print("\nEstimated presence ratio stats:")
print(gdb['estimated_presence'].describe())

# Check distribution of presence
pr_gt_98 = (gdb['estimated_presence'] > 0.98).sum()
pr_90_98 = ((gdb['estimated_presence'] >= 0.90) & (gdb['estimated_presence'] <= 0.98)).sum()
pr_75_90 = ((gdb['estimated_presence'] >= 0.75) & (gdb['estimated_presence'] < 0.90)).sum()
pr_lt_75 = (gdb['estimated_presence'] < 0.75).sum()

print(f"\nPresence distribution:")
print(f"  >98%: {pr_gt_98}")
print(f"  90-98%: {pr_90_98}")
print(f"  75-90%: {pr_75_90}")
print(f"  <75%: {pr_lt_75}")
print(f"  Total: {pr_gt_98 + pr_90_98 + pr_75_90 + pr_lt_75}")
