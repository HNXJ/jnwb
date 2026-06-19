#!/usr/bin/env python
"""
Extract trial manifest from all 13 NWB sessions.
Filter: CORRECT TRIALS ONLY (correct=1.0)
Output: CSV with (session_id | trial_num | block | condition_code | condition_label | p1_onset_time)
"""

import h5py
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Configuration
NWB_DIR = Path("D:/analysis/nwb")
OUTPUT_DIR = Path("outputs/trial_manifests")

# Condition mapping
CONDITION_MAP = {
    1: "AAAB", 2: "AAAB", 3: "AXAB", 4: "AAXB", 5: "AAAX",
    6: "BBBA", 7: "BBBA", 8: "BXBA", 9: "BBXA", 10: "BBBX",
    **{n: "RRRR" for n in range(11, 27)},
    **{n: "RXRR" for n in range(27, 35)},
    **{n: "RRXR" for n in (35, 37, 39, 41)},
    **{n: "RRRX" for n in (36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50)},
}

def extract_session(nwb_path):
    """Extract correct trials from one NWB session."""

    session_id = int(nwb_path.name.split("ses-")[1][:6])

    with h5py.File(str(nwb_path), 'r') as f:
        # Load trials
        trials_data = {}
        colnames = f['intervals/omission_glo_passive'].attrs.get('colnames', [])

        for col in colnames:
            col_str = col.decode() if isinstance(col, bytes) else str(col)
            data = f['intervals/omission_glo_passive'][col][:]

            # Convert bytes to proper types
            if data.dtype == object:
                try:
                    # Try numeric conversion
                    data = pd.to_numeric([d.decode() if isinstance(d, bytes) else d for d in data])
                except:
                    # Keep as strings
                    data = [d.decode() if isinstance(d, bytes) else d for d in data]

            trials_data[col_str] = data

        trials_df = pd.DataFrame(trials_data)

    # Filter: correct trials only
    correct_mask = trials_df['correct'].astype(float) == 1.0
    trials_correct = trials_df[correct_mask].copy()

    if len(trials_correct) == 0:
        return None

    # Extract required fields
    result = pd.DataFrame({
        'session_id': session_id,
        'trial_num': trials_correct['trial_num'].astype(int),
        'block': trials_correct['task_block_number'].astype(int),
        'condition_code': trials_correct['task_condition_number'].astype(int),
        'p1_onset_time': trials_correct['start_time'].astype(float),
    })

    # Map condition code to label
    result['condition_label'] = result['condition_code'].map(CONDITION_MAP)

    return result

def main():
    print("\n" + "=" * 80)
    print("EXTRACTING TRIAL MANIFEST (CORRECT TRIALS ONLY)")
    print("=" * 80)

    # Find all NWB files
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    print(f"\nFound {len(nwb_files)} NWB files")

    # Extract all sessions
    all_trials = []
    session_stats = []

    for i, nwb_file in enumerate(nwb_files, 1):
        print(f"\n[{i}/{len(nwb_files)}] Processing {nwb_file.name}...")

        try:
            session_df = extract_session(nwb_file)

            if session_df is None:
                print(f"  WARNING: No trials found")
                continue

            session_id = session_df['session_id'].iloc[0]
            n_trials = len(session_df)

            print(f"  Session {session_id}: {n_trials} correct trials")

            # Summary stats
            cond_counts = session_df['condition_label'].value_counts()
            print(f"  Conditions: {len(cond_counts)}")

            session_stats.append({
                'session_id': session_id,
                'n_correct_trials': n_trials,
                'n_conditions': len(cond_counts),
                'blocks': sorted(session_df['block'].unique())
            })

            all_trials.append(session_df)

        except Exception as e:
            print(f"  ERROR: {e}")

    # Concatenate all sessions
    print(f"\n" + "=" * 80)
    print("CONSOLIDATING...")
    print("=" * 80)

    manifest_df = pd.concat(all_trials, ignore_index=True)

    print(f"\nTotal correct trials across all sessions: {len(manifest_df)}")
    print(f"Sessions processed: {manifest_df['session_id'].nunique()}")
    print(f"Conditions: {manifest_df['condition_label'].nunique()}")
    print(f"Blocks: {manifest_df['block'].nunique()}")

    # Summary by condition
    print(f"\nTrials by condition (all sessions):")
    cond_summary = manifest_df.groupby('condition_label').size().sort_values(ascending=False)
    for cond, count in cond_summary.items():
        print(f"  {cond}: {count} trials")

    # Summary by session
    print(f"\nTrials by session:")
    for _, row in pd.DataFrame(session_stats).iterrows():
        print(f"  Session {int(row['session_id'])}: {row['n_correct_trials']} trials")

    # Save manifest
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest_path = OUTPUT_DIR / "trial_manifest_correct_only.csv"
    manifest_df.to_csv(manifest_path, index=False)
    print(f"\nSaved: {manifest_path}")

    # Save session summary
    summary_path = OUTPUT_DIR / "session_summary.csv"
    pd.DataFrame(session_stats).to_csv(summary_path, index=False)
    print(f"Saved: {summary_path}")

    # Show first few rows
    print(f"\n" + "=" * 80)
    print("MANIFEST PREVIEW (first 10 rows)")
    print("=" * 80)
    print(manifest_df.head(10).to_string())

    print("\n" + "=" * 80)
    print("COMPLETE")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
