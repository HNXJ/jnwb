#!/usr/bin/env python3
# scripts/generate_all_tfr_arrays.py
"""
Script to calculate and save the Time-Frequency Representation (TFR) arrays
for all 11 canonical brain areas across all 12 conditions and all sessions.

Saves one file per probe-area combination:
Filename format: <session_id>-<probe_letter>-<area_name>-<condition>.npy
Array shape: (trials, 128, 99, 5000)
- Trials: number of trials for that condition in that session.
- Channels: exactly 128.
- Frequencies: 99 bins, from 3 Hz to 199 Hz (step 2 Hz).
- Time: 5000 ms total, from -1000 ms pre-P1 to +4000 ms post-P1.
"""

import argparse
import os
import sys
import time
import datetime
import numpy as np
from pathlib import Path
import mne
from mne.time_frequency import tfr_array_multitaper

# Set paths
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.analysis.lfp.lfp_preproc import preprocess_lfp
from src.analysis.lfp.lfp_tfr import n_cycles_for_freqs

# Constants
DATA_DIR = Path("D:/workspace/data/arrays")
OUT_DIR = Path("D:/workspace/data/tfr_arrays")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SUBJECT_MAP = {
    "230629": "sub-V198o",
    "230714": "sub-V198o",
    "230719": "sub-V198o",
    "230720": "sub-V198o",
    "230721": "sub-V198o",
    "230630": "sub-C31o",
    "230816": "sub-C31o",
    "230818": "sub-C31o",
    "230823": "sub-C31o",
    "230825": "sub-C31o",
    "230830": "sub-C31o",
    "230831": "sub-C31o",
    "230901": "sub-C31o"
}

SESSION_PROBE_AREAS = {
    "230629": {
        "0": ["V1", "V2"],
        "1": ["V3d", "V3a"]
    },
    "230630": {
        "0": ["PFC"],
        "1": ["V4", "MT"],
        "2": ["V3", "V1"]
    },
    "230714": {
        "0": ["V1", "V2"],
        "1": ["V3d", "V3a"]
    },
    "230719": {
        "0": ["V1", "V2"],
        "1": ["V4"],
        "2": ["V3d", "V3a"]
    },
    "230720": {
        "0": ["V1", "V2"],
        "1": ["V3d", "V3a"]
    },
    "230721": {
        "0": ["V1", "V2"],
        "1": ["V3d", "V3a"]
    },
    "230816": {
        "0": ["PFC"],
        "1": ["V4", "MT"],
        "2": ["V3", "V1"]
    },
    "230818": {
        "0": ["PFC"],
        "1": ["TEO", "FST"],
        "2": ["MT", "MST"]
    },
    "230823": {
        "0": ["FEF"],
        "1": ["MT", "MST"],
        "2": ["V1", "V2", "V3"]
    },
    "230825": {
        "0": ["PFC"],
        "1": ["MT", "MST"],
        "2": ["V4", "TEO"]
    },
    "230830": {
        "0": ["PFC"],
        "1": ["V4", "MT"],
        "2": ["V1", "V3"]
    },
    "230831": {
        "0": ["FEF"],
        "1": ["MT", "MST"],
        "2": ["V4", "TEO"]
    },
    "230901": {
        "0": ["PFC"],
        "1": ["MT", "MST"]
    }
}

PROBE_LETTERS = {
    "0": "A",
    "1": "B",
    "2": "C"
}

CONDITIONS = [
    "AAAB", "AXAB", "AAXB", "AAAX",
    "BBBA", "BXBA", "BBXA", "BBBX",
    "RRRR", "RXRR", "RRXR", "RRRX"
]

FREQS = np.arange(3, 201, 2) # 99 frequency bins
N_CYCLES = n_cycles_for_freqs(FREQS)

def main():
    parser = argparse.ArgumentParser(description="TFR Generation Pipeline")
    parser.add_argument("--smoke", action="store_true", help="Run in smoke test mode (one session, probe, and condition)")
    parser.add_argument("--session", type=str, default=None, help="Filter by session ID (e.g., 230630)")
    parser.add_argument("--condition", type=str, default=None, help="Filter by condition (e.g., AXAB)")
    args = parser.parse_args()

    print(f"=== TFR GENERATION PIPELINE ===")
    print(f"Started at: {datetime.datetime.now().isoformat()}")
    print(f"Output directory: {OUT_DIR}")
    print(f"Frequency range: 3 Hz to 199 Hz (step 2 Hz, {len(FREQS)} bins)")
    print(f"Time window: -1000 ms to +4000 ms relative to P1 (5000 ms total, decimated to 500 bins with decim=10)")
    if args.smoke:
        print("SMOKE TEST MODE ENABLED")
    print(f"===============================\n")

    total_files_saved = 0
    start_time = time.time()

    for session, probes in SESSION_PROBE_AREAS.items():
        if args.smoke and session != "230630":
            continue
        if args.session and session != args.session:
            continue

        subject = SUBJECT_MAP[session]
        nwb_id = f"{subject}_ses-{session}"
        print(f"\n>>> Processing Session: {nwb_id}")

        for probe, areas in probes.items():
            if args.smoke and probe != "0":
                continue

            probe_letter = PROBE_LETTERS[probe]
            print(f"  Probe {probe} ({probe_letter}) -> Areas: {areas}")

            for condition in CONDITIONS:
                if args.smoke and condition != "AXAB":
                    continue
                if args.condition and condition != args.condition:
                    continue

                # Load LFP file
                filename = f"ses{session}-probe{probe}-lfp-{condition}.npy"
                file_path = DATA_DIR / filename

                if not file_path.exists():
                    # Try alternate name format if any
                    filename_alt = f"ses{session}-probe{probe_letter}-lfp-{condition}.npy"
                    file_path_alt = DATA_DIR / filename_alt
                    if file_path_alt.exists():
                        file_path = file_path_alt
                    else:
                        continue

                print(f"    Condition {condition}: loading {file_path.name}...")
                try:
                    # Load and preprocess
                    lfp = np.load(file_path, mmap_mode='r')
                    n_trials, n_ch, n_times = lfp.shape

                    # Ensure exact 128 channels
                    if n_ch != 128:
                        print(f"      Warning: Channel count is {n_ch}, padding/slicing to 128.")
                        if n_ch < 128:
                            lfp_full = np.pad(lfp, ((0, 0), (0, 128 - n_ch), (0, 0)), mode='constant')
                        else:
                            lfp_full = lfp[:, :128, :]
                    else:
                        lfp_full = lfp

                    # Slice time window: first 5000 ms (sample 0 to 5000)
                    # Raw LFP files are 6000 ms long, starting at -1000 ms pre-P1.
                    # So index 0:5000 is exactly -1000 ms to +4000 ms relative to P1.
                    lfp_sliced = lfp_full[:, :, :5000]

                    # Preprocess (1Hz highpass + CAR)
                    lfp_clean = preprocess_lfp(lfp_sliced, fs=1000.0)

                    # Compute multitaper TFR with decim=10 for 10x compression (500 time bins)
                    # Shape of lfp_clean is (trials, 128, 5000)
                    # Output shape of tfr_array_multitaper is (trials, 128, 99, 500)
                    t0 = time.time()
                    power = tfr_array_multitaper(
                        lfp_clean,
                        sfreq=1000.0,
                        freqs=FREQS,
                        n_cycles=N_CYCLES,
                        output='power',
                        use_fft=True,
                        verbose=False,
                        decim=10,
                        n_jobs=-1
                    )
                    t1 = time.time()
                    print(f"      TFR computed in {t1 - t0:.2f} seconds. Shape: {power.shape}")

                    # Convert to float32 to save 50% storage space
                    power_f32 = power.astype(np.float32)

                    # Save one file per area mapped to this probe
                    first_out_path = None
                    for area in areas:
                        out_filename = f"{nwb_id}-{probe_letter}-{area}-{condition}.npy"
                        out_path = OUT_DIR / out_filename
                        if first_out_path is None:
                            np.save(out_path, power_f32)
                            first_out_path = out_path
                            print(f"      Saved: {out_filename}")
                        else:
                            # Use hard link to save disk space and prevent duplication
                            if out_path.exists():
                                out_path.unlink()
                            os.link(first_out_path, out_path)
                            print(f"      Linked: {out_filename} -> {first_out_path.name}")
                        total_files_saved += 1

                except Exception as e:
                    print(f"      Error processing {filename}: {e}")

    elapsed = time.time() - start_time
    print(f"\n==========================================")
    print(f"TFR Generation Pipeline Completed!")
    print(f"Total files saved: {total_files_saved}")
    print(f"Total elapsed time: {elapsed / 60:.2f} minutes")
    print(f"==========================================")

if __name__ == "__main__":
    main()
