#!/usr/bin/env python3
"""
Diagnostic report for epoch extraction.
Identifies mismatch between expected and actual interval structure.
"""

from pathlib import Path
from pynwb import NWBHDF5IO
import pandas as pd

NWB_PATH = Path('d:/analysis/nwb/sub-C31o_ses-230823_rec.nwb')

print("="*70)
print("EPOCH EXTRACTION DIAGNOSTIC")
print("="*70)

with NWBHDF5IO(str(NWB_PATH), 'r', load_namespaces=True) as io:
    nwb = io.read()

    # 1. Available interval tables
    print("\n1. AVAILABLE INTERVAL TABLES")
    print(f"   Available: {list(nwb.intervals.keys())}")

    # 2. Load the target interval table
    context = 'omission_glo_passive'
    if context not in nwb.intervals:
        print(f"\n   ERROR: {context} not found!")
        exit(1)

    intervals = nwb.intervals[context].to_dataframe()
    print(f"\n   Selected: {context}")
    print(f"   Shape: {intervals.shape[0]} rows x {intervals.shape[1]} columns")

    # 3. Key columns
    print("\n2. KEY COLUMNS")
    key_cols = ['stimulus_number', 'task_condition_number', 'correct', 'trial_num']
    for col in key_cols:
        if col in intervals.columns:
            print(f"   [OK] {col}")
        else:
            print(f"   [XX] {col} (MISSING)")

    # 4. Test condition mapping
    print("\n3. CONDITION MAPPING TEST")

    condition_map = {
        'AAAB': [1, 2], 'AXAB': [3], 'AAXB': [4], 'AAAX': [5],
        'BBBA': [6, 7], 'BXBA': [8], 'BBXA': [9], 'BBBX': [10],
        'RRRR': list(range(11, 27)), 'RXRR': list(range(27, 35)),
        'RRXR': [35, 37, 39, 41], 'RRRX': [36, 38, 40] + list(range(42, 51))
    }

    # Check which conditions exist in data
    print(f"\n   Unique task_condition_number values in NWB:")
    if 'task_condition_number' in intervals.columns:
        unique_conds = sorted(intervals['task_condition_number'].dropna().unique())
        # Convert to numbers for display
        numeric_conds = []
        for c in unique_conds:
            try:
                numeric_conds.append(int(float(c)))
            except:
                numeric_conds.append(c)
        print(f"   {sorted(numeric_conds)}")
    else:
        print(f"   (Column not found)")

    # 4b. Map to condition names
    print(f"\n   Code to condition mapping:")
    code_to_name = {}
    for name, codes in condition_map.items():
        for code in codes:
            code_to_name[code] = name

    cond_counts = {}
    for code, name in code_to_name.items():
        if 'task_condition_number' in intervals.columns:
            # Convert to numeric for comparison
            count = 0
            for idx, row in intervals.iterrows():
                try:
                    if int(float(row['task_condition_number'])) == code:
                        count += 1
                except:
                    pass
            if count > 0:
                cond_counts[name] = cond_counts.get(name, 0) + count
                print(f"   Code {code:3d} -> {name:5s}: {count:5d} rows")

    print(f"\n   Total by condition name:")
    for name, count in sorted(cond_counts.items()):
        print(f"   {name}: {count}")

    # 5. Test phase filtering
    print("\n4. PHASE FILTERING TEST")
    if 'stimulus_number' in intervals.columns:
        # Get unique stimulus_number values
        unique_phases = []
        for val in intervals['stimulus_number'].dropna().unique():
            try:
                unique_phases.append(int(float(val)))
            except:
                unique_phases.append(val)
        print(f"   Unique stimulus_number values: {sorted(set(unique_phases))}")

        for phase in [1, 2, 3, 4, 5]:
            count = 0
            for idx, row in intervals.iterrows():
                try:
                    if int(float(row['stimulus_number'])) == phase:
                        count += 1
                except:
                    pass
            print(f"   Phase {phase}: {count} rows")
    else:
        print(f"   ERROR: stimulus_number column missing")

    # 6. Test correct filtering
    print("\n5. CORRECT TRIALS FILTERING")
    if 'correct' in intervals.columns:
        correct_vals = []
        for val in intervals['correct'].dropna().unique():
            try:
                correct_vals.append(float(val))
            except:
                correct_vals.append(val)
        print(f"   Unique 'correct' values: {sorted(set(correct_vals))}")

        correct_count = 0
        incorrect_count = 0
        for idx, row in intervals.iterrows():
            try:
                if float(row['correct']) == 1.0:
                    correct_count += 1
                else:
                    incorrect_count += 1
            except:
                pass
        print(f"   Correct (1.0): {correct_count}")
        print(f"   Incorrect (0.0): {incorrect_count}")
    else:
        print(f"   ERROR: correct column missing")

    # 7. Simulate get_epochs() call
    print("\n6. SIMULATED get_epochs() CALL")
    print(f"   Request: condition='AAAB', phase=2, correct_only=True")

    result = intervals.copy()
    print(f"   Starting rows: {len(result)}")

    # Apply filters - must convert columns to numeric first
    for col in ['stimulus_number', 'task_condition_number', 'correct']:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors='coerce')

    # Apply correct filter
    if 'correct' in result.columns:
        result = result[result['correct'] == 1.0]
        print(f"   After correct filter: {len(result)}")

    # Apply phase filter
    if 'stimulus_number' in result.columns:
        result = result[result['stimulus_number'] == 2.0]
        print(f"   After phase filter (phase=2): {len(result)}")

    # Apply condition filter
    condition_codes = condition_map.get('AAAB', [])
    if 'task_condition_number' in result.columns:
        result = result[result['task_condition_number'].isin(condition_codes)]
        print(f"   After condition filter (AAAB={condition_codes}): {len(result)}")

    print(f"\n   RESULT: {len(result)} trials returned")
    if len(result) > 0:
        print(f"   [PASS] Epochs are being extracted")
        print(f"   Sample rows:")
        cols_to_show = ['start_time', 'stimulus_number', 'task_condition_number', 'correct']
        print(result[cols_to_show].head(3).to_string())
    else:
        print(f"   [FAIL] No epochs returned")
        print(f"   Diagnosis: Check condition codes and phase numbering above")

print("\n" + "="*70)
print("END DIAGNOSTIC")
print("="*70)
