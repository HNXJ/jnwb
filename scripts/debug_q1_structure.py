#!/usr/bin/env python3
"""Debug Q1 data structure to understand why 0 correlations computed."""

import glob
import os
import re
from pathlib import Path
from itertools import combinations

TFR_DIR = Path("D:/workspace/data/tfr_arrays")
tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))

print(f"Total TFR files: {len(tfr_files)}\n")

def parse_tfr_filename(filename):
    basename = os.path.basename(filename)
    match = re.match(r'sub-(\w+)_ses-(\d+)-(\w)-(\w+)-(\w+)\.npy', basename)
    if match:
        subject, session, probe, area, condition = match.groups()
        return {
            'subject': subject,
            'session': int(session),
            'probe': probe,
            'area': area,
            'condition': condition,
        }
    return None

# Replicate the grouping logic
file_groups = {}
for tfr_file in tfr_files:
    meta = parse_tfr_filename(tfr_file)
    if not meta:
        continue

    key = (meta['session'], meta['area'], meta['condition'])
    if key not in file_groups:
        file_groups[key] = {}
    if meta['probe'] not in file_groups[key]:
        file_groups[key][meta['probe']] = []
    file_groups[key][meta['probe']].append(tfr_file)

print(f"File groups created: {len(file_groups)}\n")

# Show sample structure
session = 230629
omission_conditions = {'AAXB', 'AXAB', 'AAAX', 'AAAB', 'BBBA', 'BBBX', 'BBXA', 'BXBA', 'RRRR', 'RRRX', 'RRXR', 'RXRR'}

area_data_by_condition = {}

for (sess, area, cond), probes in file_groups.items():
    if sess != session or cond not in omission_conditions:
        continue

    if cond not in area_data_by_condition:
        area_data_by_condition[cond] = {}
    area_data_by_condition[cond][area] = probes

print(f"Session {session}:")
print(f"  Conditions found: {list(area_data_by_condition.keys())}\n")

# Show sample condition
if 'AAAB' in area_data_by_condition:
    print(f"  AAAB condition areas:")
    for area, probe_dict in area_data_by_condition['AAAB'].items():
        print(f"    {area}: {type(probe_dict).__name__} with keys {list(probe_dict.keys())}")
        for probe, files in probe_dict.items():
            print(f"      probe {probe}: {len(files)} file(s)")

# Check if we can iterate pairs
areas = list(area_data_by_condition['AAAB'].keys())
print(f"\n  Areas to correlate: {areas}")
pair_count = len(list(combinations(areas, 2)))
print(f"  Pairs to compute: {pair_count}")

if pair_count > 0:
    # Test the extraction
    area1, area2 = list(combinations(areas, 2))[0]
    probe_dict1 = area_data_by_condition['AAAB'][area1]
    probe_dict2 = area_data_by_condition['AAAB'][area2]

    print(f"\n  Testing extraction for {area1} vs {area2}:")
    print(f"    probe_dict1 type: {type(probe_dict1).__name__}, keys: {list(probe_dict1.keys())}")

    probe1_files = list(probe_dict1.values())[0]
    print(f"    probe1_files: {len(probe1_files)} files")
    print(f"      first: {os.path.basename(probe1_files[0])}")

    # Check loading
    import numpy as np
    try:
        tfr1 = np.load(probe1_files[0])
        print(f"    Loaded successfully: shape {tfr1.shape}")
    except Exception as e:
        print(f"    ERROR loading: {e}")
else:
    print("\nWARNING: No pairs found to correlate!")
