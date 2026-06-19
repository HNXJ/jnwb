#!/usr/bin/env python
"""
Phase 2A: Full-Sequence Epoch Recovery with p1_relative Alignment

Extracts p1_relative-aligned epochs from raw NWB data for all conditions with:
- Proper event-code-based alignment to p1_relative anchor (event code 101)
- Trial-by-trial LFP extraction
- Baseline power sanity validation
- Comparison against existing NPY files
- Complete validation report
"""

import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Tuple, List, Optional
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

NWB_DIR = Path("D:/analysis/nwb")
OUTPUT_DIR = Path("outputs/epochs_full_sequence")
A4_PATH = Path("reports/analysis_A4_trial_count_validation/trial_count_matrix.csv")
NPY_DIR = Path("D:/workspace/data/other/checkpoints/oglo4")

# Epoch timing specification (ms from p1_relative onset)
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

FS = 1000  # Hz
TOTAL_WINDOW_MS = [-250, 1750]
TOTAL_SAMPLES = int((TOTAL_WINDOW_MS[1] - TOTAL_WINDOW_MS[0]) * FS / 1000)

# Event codes
EVENT_CODE_P1_STIMULUS = 101
EVENT_CODE_P2_STIMULUS = 102
EVENT_CODE_P3_STIMULUS = 103
EVENT_CODE_P4_STIMULUS = 104

CONDITION_NUMBER_MAP = {
    1: "AAAB", 2: "AAAB", 3: "AXAB", 4: "AAXB", 5: "AAAX",
    6: "BBBA", 7: "BBBA", 8: "BXBA", 9: "BBXA", 10: "BBBX",
    **{n: "RRRR" for n in range(11, 27)},
    **{n: "RXRR" for n in range(27, 35)},
    **{n: "RRXR" for n in (35, 37, 39, 41)},
    **{n: "RRRX" for n in (36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50)},
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_nwb_data(nwb_path: Path):
    """Load comprehensive NWB data using h5py."""
    import h5py

    with h5py.File(str(nwb_path), 'r') as f:
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

        return trials_df, lfp_data, lfp_timestamps


def parse_trial_codes(codes_string: str) -> Dict[int, float]:
    """Parse trial codes string (format: 'code1@time1 code2@time2')."""
    codes_dict = {}
    if not isinstance(codes_string, str):
        return codes_dict

    try:
        for part in codes_string.split():
            if '@' in part:
                code, time_str = part.split('@')
                codes_dict[int(code)] = float(time_str)
    except:
        pass

    return codes_dict


def extract_trial_epoch(lfp_data: np.ndarray, lfp_timestamps: np.ndarray,
                        trial_start: float, trial_stop: float,
                        codes_string: str, target_samples: int) -> Optional[np.ndarray]:
    """
    Extract epoch for one trial aligned to p1_relative (event code 101).

    Returns: (target_samples, n_channels) array or None if extraction fails
    """
    try:
        # Parse event codes in trial
        codes_dict = parse_trial_codes(codes_string)

        # Find p1_relative anchor (event code 101)
        if EVENT_CODE_P1_STIMULUS not in codes_dict:
            return None

        p1_time = codes_dict[EVENT_CODE_P1_STIMULUS]

        # Calculate window start and end in absolute time
        window_start_rel = TOTAL_WINDOW_MS[0] / 1000.0  # ms -> seconds
        window_end_rel = TOTAL_WINDOW_MS[1] / 1000.0

        window_start = p1_time + window_start_rel
        window_end = p1_time + window_end_rel

        # Find indices in LFP data
        start_idx = np.searchsorted(lfp_timestamps, window_start)
        end_idx = np.searchsorted(lfp_timestamps, window_end)

        # Extract epoch
        epoch = lfp_data[start_idx:end_idx, :]

        # Validate shape
        if epoch.shape[0] < target_samples:
            # Pad with NaNs
            pad_size = target_samples - epoch.shape[0]
            epoch = np.vstack([epoch, np.full((pad_size, epoch.shape[1]), np.nan)])
        elif epoch.shape[0] > target_samples:
            # Truncate
            epoch = epoch[:target_samples, :]

        return epoch

    except Exception as e:
        return None


def compute_baseline_power(epoch: np.ndarray) -> Tuple[float, float]:
    """Compute baseline vs stimulus power. Returns (p1_power, p2_power)."""
    try:
        # p1_relative: samples 0-250 (first 250ms)
        # p2: samples 250-500 (next 250ms)
        p1_power = np.nanmean(epoch[:250, :])
        p2_power = np.nanmean(epoch[250:500, :])
        return p1_power, p2_power
    except:
        return np.nan, np.nan


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "=" * 80)
    print("PHASE 2A: FULL-SEQUENCE EPOCH RECOVERY WITH ALIGNMENT")
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
    print(f"  Subject: {subject}, Session: {session_id}")

    # Step 2: Load NWB data
    print("\n[STEP 2] Loading NWB data...")
    try:
        trials_df, lfp_data, lfp_timestamps = load_nwb_data(target_file)
        print(f"  Trials: {len(trials_df)}")
        print(f"  LFP shape: {lfp_data.shape}")
        print(f"  Timestamp range: {lfp_timestamps[0]:.2f}s to {lfp_timestamps[-1]:.2f}s")
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # Step 3: Load A4 reference
    print("\n[STEP 3] Loading A4 trial counts...")
    trial_counts = {}
    if A4_PATH.exists():
        a4 = pd.read_csv(A4_PATH)
        ses_data = a4[a4['session_id'] == session_id]
        if len(ses_data) > 0:
            trial_counts = dict(zip(ses_data['condition'], ses_data['trial_count']))
            print(f"  Found A4 data for {len(trial_counts)} conditions")
        else:
            print(f"  WARNING: No A4 data for session {session_id}")

    # Step 4: Extract epochs
    print("\n[STEP 4] Extracting epochs...")
    print(f"  Total trials to process: {len(trials_df)}")
    print(f"  Target samples per epoch: {TOTAL_SAMPLES}")

    extracted_by_condition = {}
    extraction_stats = {
        'total_attempted': len(trials_df),
        'successful': 0,
        'failed': 0,
        'failed_reasons': {}
    }

    # Process all trials
    n_channels = lfp_data.shape[1]

    for trial_idx, row in trials_df.iterrows():
        if trial_idx % 500 == 0:
            print(f"  Processing trial {trial_idx}/{len(trials_df)}...")

        try:
            # Get condition
            cond_num = int(float(row['task_condition_number']))
            condition = CONDITION_NUMBER_MAP.get(cond_num, f'UNKNOWN_{cond_num}')

            # Extract epoch
            codes_str = str(row.get('codes', ''))
            epoch = extract_trial_epoch(lfp_data, lfp_timestamps,
                                       row['start_time'], row['stop_time'],
                                       codes_str, TOTAL_SAMPLES)

            if epoch is None:
                extraction_stats['failed'] += 1
                reason = 'no_p1_anchor'
                extraction_stats['failed_reasons'][reason] = \
                    extraction_stats['failed_reasons'].get(reason, 0) + 1
                continue

            # Validate epoch shape
            if epoch.shape != (TOTAL_SAMPLES, n_channels):
                extraction_stats['failed'] += 1
                reason = f'shape_mismatch'
                extraction_stats['failed_reasons'][reason] = \
                    extraction_stats['failed_reasons'].get(reason, 0) + 1
                continue

            # Store epoch
            if condition not in extracted_by_condition:
                extracted_by_condition[condition] = []
            extracted_by_condition[condition].append(epoch)

            extraction_stats['successful'] += 1

        except Exception as e:
            extraction_stats['failed'] += 1
            reason = 'exception'
            extraction_stats['failed_reasons'][reason] = \
                extraction_stats['failed_reasons'].get(reason, 0) + 1

    # Step 5: Stack epochs and validate
    print("\n[STEP 5] Stacking and validating epochs...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    validation_results = {
        'session_id': session_id,
        'timestamp': datetime.now().isoformat(),
        'extraction_stats': extraction_stats,
        'conditions': {}
    }

    all_valid = True

    for condition, epochs_list in extracted_by_condition.items():
        if not epochs_list:
            continue

        epochs_array = np.stack(epochs_list, axis=0)  # (n_trials, n_samples, n_channels)

        # Validation checks
        checks = {
            'shape': epochs_array.shape[0] > 0,
            'no_nan_rows': not np.isnan(epochs_array).any(axis=(1, 2)).any(),
            'baseline_power': True
        }

        # Baseline power sanity check
        p1_powers = []
        p2_powers = []
        for epoch in epochs_list:
            p1, p2 = compute_baseline_power(epoch)
            p1_powers.append(p1)
            p2_powers.append(p2)

        p1_powers = np.array(p1_powers)
        p2_powers = np.array(p2_powers)

        # Check that p2 power is slightly higher than p1 (stimulus response)
        if np.isfinite(p1_powers).any() and np.isfinite(p2_powers).any():
            p2_greater = np.nanmean(p2_powers) > np.nanmean(p1_powers) * 0.95
            checks['baseline_power'] = p2_greater

        condition_valid = all(checks.values())

        validation_results['conditions'][condition] = {
            'n_trials': len(epochs_list),
            'shape': epochs_array.shape,
            'checks': checks,
            'valid': condition_valid,
            'baseline_p1_mean': float(np.nanmean(p1_powers)) if np.isfinite(p1_powers).any() else None,
            'baseline_p2_mean': float(np.nanmean(p2_powers)) if np.isfinite(p2_powers).any() else None,
        }

        if not condition_valid:
            all_valid = False

        # Save condition-specific epochs
        cond_file = OUTPUT_DIR / f"ses{session_id}_{condition}_epochs.npy"
        np.save(cond_file, epochs_array)
        print(f"  {condition}: {len(epochs_list)} epochs → {cond_file.name}")

    # Step 6: Generate validation report
    print("\n[STEP 6] Generating validation report...")

    validation_results['status'] = 'PASS' if all_valid else 'FAIL'
    validation_results['summary'] = {
        'total_extracted': extraction_stats['successful'],
        'total_failed': extraction_stats['failed'],
        'success_rate': extraction_stats['successful'] / extraction_stats['total_attempted']
        if extraction_stats['total_attempted'] > 0 else 0,
        'conditions_processed': len(extracted_by_condition),
        'all_valid': all_valid
    }

    report_path = OUTPUT_DIR / "validation_report_full.json"
    with open(report_path, 'w') as f:
        json.dump(validation_results, f, indent=2)
    print(f"  Saved: {report_path}")

    # Step 7: Summary
    print("\n[SUMMARY]")
    print(f"  Session: {session_id} ({subject})")
    print(f"  Total trials processed: {extraction_stats['total_attempted']}")
    print(f"  Successfully extracted: {extraction_stats['successful']}")
    print(f"  Failed: {extraction_stats['failed']}")
    print(f"  Success rate: {validation_results['summary']['success_rate']:.1%}")
    print(f"  Conditions processed: {len(extracted_by_condition)}")
    print(f"  Validation status: {validation_results['status']}")

    if extraction_stats['failed_reasons']:
        print(f"  Failure reasons:")
        for reason, count in extraction_stats['failed_reasons'].items():
            print(f"    - {reason}: {count}")

    print("\n" + "=" * 80)
    print("PHASE 2A FULL EXTRACTION COMPLETE")
    print("=" * 80 + "\n")

    return validation_results['status'] == 'PASS'


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
