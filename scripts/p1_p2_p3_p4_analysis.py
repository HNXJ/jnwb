#!/usr/bin/env python
"""
Verify that correct P1, P2, P3, P4 counts are equal per condition group.
Each trial should have all 4 phases (unless omitted, which would disqualify it).
"""

import sys
sys.path.insert(0, 'D:/workspace/omission/scripts')

from jnwb_helper_functions import get_binary_events_for_code
from pathlib import Path
import pandas as pd
import numpy as np
from pynwb import NWBHDF5IO

NWB_DIR = Path("D:/analysis/nwb")

# Condition grouping (12 groups)
CONDITION_GROUPS = {
    'AAAB': [1, 2],
    'AXAB': [3],
    'AAXB': [4],
    'AAAX': [5],
    'BBBA': [6, 7],
    'BXBA': [8],
    'BBXA': [9],
    'BBBX': [10],
    'RRRR': list(range(11, 27)),
    'RXRR': list(range(27, 35)),
    'RRXR': [35, 37, 39, 41],
    'RRRX': [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
}

print("=" * 100)
print("CORRECT EVENTS: P1 vs P2 vs P3 vs P4 (by Condition Group)")
print("=" * 100)

nwb_files = sorted(NWB_DIR.glob("*.nwb"))

# Aggregate across all sessions
group_totals = {group: {'P1': 0, 'P2': 0, 'P3': 0, 'P4': 0} for group in CONDITION_GROUPS.keys()}

for i, nwb_file in enumerate(nwb_files, 1):
    session_id = int(nwb_file.name.split("ses-")[1][:6])

    print(f"\n[{i}/{len(nwb_files)}] Session {session_id}...", end=" ", flush=True)

    try:
        with NWBHDF5IO(str(nwb_file), 'r', load_namespaces=True) as io:
            nwb = io.read()

            # Binary filters
            correct_b = get_binary_events_for_code(nwb, 1.0, 'omission_glo_passive', 'correct')
            p1_b = get_binary_events_for_code(nwb, 2.0, 'omission_glo_passive', 'stimulus_number')
            p2_b = get_binary_events_for_code(nwb, 3.0, 'omission_glo_passive', 'stimulus_number')
            p3_b = get_binary_events_for_code(nwb, 4.0, 'omission_glo_passive', 'stimulus_number')
            p4_b = get_binary_events_for_code(nwb, 5.0, 'omission_glo_passive', 'stimulus_number')

            # Count per group
            for group_name, cond_codes in CONDITION_GROUPS.items():
                # Create binary for this group
                group_b = np.zeros(len(correct_b), dtype=bool)
                for code in cond_codes:
                    cond_b = get_binary_events_for_code(nwb, float(code), 'omission_glo_passive', 'task_condition_number')
                    group_b |= cond_b

                # Count each phase
                p1_count = np.sum(correct_b & p1_b & group_b)
                p2_count = np.sum(correct_b & p2_b & group_b)
                p3_count = np.sum(correct_b & p3_b & group_b)
                p4_count = np.sum(correct_b & p4_b & group_b)

                group_totals[group_name]['P1'] += p1_count
                group_totals[group_name]['P2'] += p2_count
                group_totals[group_name]['P3'] += p3_count
                group_totals[group_name]['P4'] += p4_count

            print("OK")

    except Exception as e:
        print(f"ERROR: {e}")

# Print results
print("\n" + "=" * 100)
print("GRAND TOTALS: P1 vs P2 vs P3 vs P4 by Condition Group")
print("=" * 100)

results = []
for group_name in ['AAAB', 'AXAB', 'AAXB', 'AAAX', 'BBBA', 'BXBA', 'BBXA', 'BBBX', 'RRRR', 'RXRR', 'RRXR', 'RRRX']:
    counts = group_totals[group_name]
    results.append({
        'Group': group_name,
        'P1': counts['P1'],
        'P2': counts['P2'],
        'P3': counts['P3'],
        'P4': counts['P4'],
        'Match': 'YES' if len(set(counts.values())) == 1 else 'NO'
    })

results_df = pd.DataFrame(results)
print("\n" + results_df.to_string(index=False))

print("\n" + "=" * 100)
print("VERIFICATION")
print("=" * 100)

all_match = all(r['Match'] == 'YES' for r in results)
if all_match:
    print("\nOK: ALL GROUPS MATCH - P1 = P2 = P3 = P4 counts")
    total_p1 = results_df['P1'].sum()
    print(f"Total correct trials per phase: {total_p1}")
else:
    print("\nWARNING: MISMATCH DETECTED:")
    for r in results:
        if r['Match'] == 'NO':
            print(f"  {r['Group']}: P1={r['P1']}, P2={r['P2']}, P3={r['P3']}, P4={r['P4']}")

print("\n" + "=" * 100 + "\n")
