import pandas as pd
import numpy as np

comp = pd.read_csv("outputs/publication_figures/comprehensive_grand_database_all_units.csv")

quality_1 = comp['quality'] == 1.0
pr = pd.to_numeric(comp['presence_ratio'], errors='coerce')
snr = pd.to_numeric(comp['snr'], errors='coerce')
fr = pd.to_numeric(comp['firing_rate'], errors='coerce')
amp_cutoff = pd.to_numeric(comp['amplitude_cutoff'], errors='coerce')

print("=== Searching for combinations that yield ~4,099 ===\n")

# Try various combinations
candidates = [
    ("Quality==1.0", quality_1),
    ("PR>=0.90", pr >= 0.90),
    ("PR>=0.85", pr >= 0.85),
    ("SNR>0.5", snr > 0.5),
    ("Quality==1.0 OR SNR>0.5", quality_1 | (snr > 0.5)),
    ("Quality==1.0 OR PR>=0.90", quality_1 | (pr >= 0.90)),
    ("Quality==1.0 OR PR>=0.85", quality_1 | (pr >= 0.85)),
    ("(Quality==1.0 OR PR>=0.90) AND FR>0.5", (quality_1 | (pr >= 0.90)) & (fr > 0.5)),
    ("Quality==1.0 AND FR>0.5", quality_1 & (fr > 0.5)),
    ("(PR>=0.90 OR Quality==1.0) AND amplitude_cutoff<inf",
     (pr >= 0.90 | quality_1) & (amp_cutoff < np.inf)),
]

results = []
for label, mask in candidates:
    count = mask.sum()
    results.append((label, count))
    pct = count / len(comp) * 100
    marker = " ✓" if 4000 <= count <= 4200 else ""
    print(f"{count:4d} ({pct:5.1f}%) {label}{marker}")

print("\n=== Closest matches to 4,099 ===")
results.sort(key=lambda x: abs(x[1] - 4099))
for label, count in results[:5]:
    print(f"{count:4d} (diff: {abs(count-4099):3d}) {label}")

# Check quality==1.0 AND presence_ratio >= threshold for different thresholds
print("\n=== Quality==1.0 AND PR>threshold ===")
for pr_thresh in np.arange(0.5, 1.0, 0.05):
    count = (quality_1 & (pr > pr_thresh)).sum()
    marker = " ✓" if 4000 <= count <= 4200 else ""
    print(f"  PR>{pr_thresh:.2f}: {count:4d}{marker}")
