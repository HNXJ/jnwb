import numpy as np
from pathlib import Path
import re

# Check TFR data structure
tfr_file = Path("D:/workspace/data/tfr_arrays/sub-C31o_ses-230630-A-PFC-AAAB.npy")
data = np.load(tfr_file)

print(f"TFR data shape: {data.shape}")
print(f"Likely: (channels/bands, frequency_or_time_bins)")

# Count and parse files
tfr_dir = Path("D:/workspace/data/tfr_arrays")
all_files = sorted(list(tfr_dir.glob("*.npy")))
print(f"\nTotal TFR files: {len(all_files)}")

# Parse filenames
sessions = set()
probes = set()
areas = set()
conditions = set()

for f in all_files[:100]:
    match = re.match(r'sub-(\w+)_ses-(\d+)-(\w)-(\w+)-(\w+)\.npy', f.name)
    if match:
        subject, session, probe, area, condition = match.groups()
        sessions.add(session)
        probes.add(probe)
        areas.add(area)
        conditions.add(condition)

print(f"\nUnique sessions: {sorted(sessions)}")
print(f"Probes: {sorted(probes)}")
print(f"Areas: {sorted(areas)}")
print(f"Conditions (samples): {sorted(list(conditions))[:5]}")
print(f"Total conditions: {len(conditions)}")

print("\n=== ANALYSIS PLAN ===")
print("""
1. SPECTRAL BAND CORRELATION ANALYSIS
   - Load TFR data for each band (theta, alpha, beta, gamma, etc.)
   - Define time windows:
     * Stimulus: p1 onset (0-531 ms)
     * Baseline before stim: [-1000, 0] ms
     * Baseline before omission: [-500, 0] ms before p2/p3/p4 (omission slots)
     * Omission phase: omission slot duration
     * Baseline after omission: [+500, +1000] ms after omission slot
   - For each window, compute Spearman correlation between areas within layer
     * Superficial layer correlations
     * Deep layer correlations
   - Control: shuffled phase correlation
   - Statistics: FDR correction across bands and conditions

2. SPIKING NETWORK ANALYSIS
   - Load spike data from NWB and/or grand database
   - Compute cross-correlation between units
   - Group by area and layer
   - Compare with spectral results

3. LEAD/CAUSALITY ANALYSIS
   - Cross-correlation with lag (-500 to +500 ms)
   - Identify which modality leads (LFP vs spike)
   - Identify which band, layer, area shows earliest response
   - Statistical significance with permutation test

4. OUTPUT
   - Network graphs (correlation strength)
   - Lead time matrices
   - Statistical summary tables
""")
