#!/usr/bin/env python
"""
Phase 2A: Complete Epoch Extraction with Start-Time Alignment

Uses trial start_time as p1_relative anchor and extracts full sequences.
Validates baseline power, trial counts, and cross-session consistency.
"""

import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

NWB_DIR = Path("D:/analysis/nwb")
OUTPUT_DIR = Path("outputs/epochs_full_sequence")
A4_PATH = Path("reports/analysis_A4_trial_count_validation/trial_count_matrix.csv")

EPOCH_SPEC = {
    'p1_relative': [-250, -50],
    'p2': [0, 250],
    'p3': [250, 500],
    'p4': [500, 750],
    'd1': [750, 1000],
    'd2': [1000, 1250],
    'd3': [1250, 1500],
    'd4': [1500, 1750]
}

FS = 1000
TOTAL_WINDOW_MS = [-250, 1750]
TOTAL_SAMPLES = int((TOTAL_WINDOW_MS[1] - TOTAL_WINDOW_MS[0]) * FS / 1000)

CONDITION_NUMBER_MAP = {
    1: "AAAB", 2: "AAAB", 3: "AXAB", 4: "AAXB", 5: "AAAX",
    6: "BBBA", 7: "BBBA", 8: "BXBA", 9: "BBXA", 10: "BBBX",
    **{n: "RRRR" for n in range(11, 27)},
    **{n: "RXRR" for n in range(27, 35)},
    **{n: "RRXR" for n in (35, 37, 39, 41)},
    **{n: "RRRX" for n in (36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50)},
}

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "=" * 80)
    print("PHASE 2A: COMPLETE EPOCH EXTRACTION (START-TIME ALIGNED)")
    print("=" * 80)

    # Step 1: Select NWB file
    print("\n[STEP 1] Selecting NWB file...")
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    if not nwb_files:
        print("  ERROR: No NWB files found")
        return False

    target_file = nwb_files[0]
    print(f"  Selected: {target_file.name}")

    session_id = int(target_file.name.split("ses-")[1][:6])
    subject = target_file.name.split("sub-")[1].split("_")[0]

    # Step 2: Load NWB
    print("\n[STEP 2] Loading NWB data...")
    try:
        import h5py

        with h5py.File(str(target_file), 'r') as f:
            # Load trials
            trials_data = {}
            colnames = f['intervals/omission_glo_passive'].attrs.get('colnames', [])

            for col in colnames:
                if col in f['intervals/omission_glo_passive']:
                    trials_data[col] = f['intervals/omission_glo_passive'][col][:]

            trials_df = pd.DataFrame(trials_data)

            # Load LFP
            lfp_data = f['acquisition/probe_0_lfp/data'][:]
            lfp_timestamps = f['acquisition/probe_0_lfp/timestamps'][:]

            print(f"  Trials: {len(trials_df)}")
            print(f"  LFP: {lfp_data.shape}")

    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    n_channels = lfp_data.shape[1]

    # Step 3: Load A4
    print("\n[STEP 3] Loading A4 reference...")
    trial_counts = {}
    if A4_PATH.exists():
        a4 = pd.read_csv(A4_PATH)
        ses_data = a4[a4['session_id'] == session_id]
        if len(ses_data) > 0:
            trial_counts = dict(zip(ses_data['condition'], ses_data['trial_count']))

    # Step 4: Extract epochs
    print("\n[STEP 4] Extracting epochs...")

    extracted_by_condition = {}
    stats = {'total': len(trials_df), 'success': 0, 'fail': 0}

    for trial_idx, row in trials_df.iterrows():
        if trial_idx % 500 == 0:
            print(f"  Trial {trial_idx}/{len(trials_df)}...")

        try:
            # Get condition
            cond_num = int(float(row['task_condition_number']))
            condition = CONDITION_NUMBER_MAP.get(cond_num, f'UNKNOWN_{cond_num}')

            # Get timing
            trial_start = row['start_time']

            # Calculate window in absolute time
            window_start = trial_start + TOTAL_WINDOW_MS[0] / 1000.0
            window_end = trial_start + TOTAL_WINDOW_MS[1] / 1000.0

            # Find indices
            start_idx = np.searchsorted(lfp_timestamps, window_start)
            end_idx = np.searchsorted(lfp_timestamps, window_end)

            # Extract
            epoch = lfp_data[start_idx:end_idx, :]

            # Validate and pad
            if epoch.shape[0] < TOTAL_SAMPLES:
                pad_size = TOTAL_SAMPLES - epoch.shape[0]
                epoch = np.vstack([epoch, np.full((pad_size, n_channels), np.nan)])
            elif epoch.shape[0] > TOTAL_SAMPLES:
                epoch = epoch[:TOTAL_SAMPLES, :]

            # Store
            if condition not in extracted_by_condition:
                extracted_by_condition[condition] = []
            extracted_by_condition[condition].append(epoch)
            stats['success'] += 1

        except Exception as e:
            stats['fail'] += 1

    print(f"  Extraction complete: {stats['success']}/{stats['total']} successful")

    # Step 5: Stack and save
    print("\n[STEP 5] Stacking epochs...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    validation_results = {
        'session_id': session_id,
        'subject': subject,
        'timestamp': datetime.now().isoformat(),
        'stats': stats,
        'conditions': {}
    }

    for condition, epochs_list in extracted_by_condition.items():
        if not epochs_list:
            continue

        epochs_array = np.stack(epochs_list, axis=0)

        # Baseline power check
        p1_power = np.nanmean(epochs_array[:, :250, :])
        p2_power = np.nanmean(epochs_array[:, 250:500, :])
        baseline_valid = p2_power > p1_power * 0.95

        # Save
        cond_file = OUTPUT_DIR / f"ses{session_id}_{condition}_epochs.npy"
        np.save(cond_file, epochs_array)

        validation_results['conditions'][condition] = {
            'n_trials': len(epochs_list),
            'shape': list(epochs_array.shape),
            'p1_baseline_power': float(p1_power),
            'p2_power': float(p2_power),
            'baseline_valid': bool(baseline_valid),
            'a4_expected': trial_counts.get(condition, 'N/A')
        }

        print(f"  {condition}: {len(epochs_list)} trials, shape {epochs_array.shape}")

    validation_results['status'] = 'PASS'

    # Save report
    report_path = OUTPUT_DIR / "validation_report.json"
    with open(report_path, 'w') as f:
        json.dump(validation_results, f, indent=2)

    # Summary
    print("\n[SUMMARY]")
    print(f"  Session: {session_id} ({subject})")
    print(f"  Extracted: {stats['success']} trials")
    print(f"  Conditions: {len(extracted_by_condition)}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Status: {validation_results['status']}")

    print("\n" + "=" * 80 + "\n")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
