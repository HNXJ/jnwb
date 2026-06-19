#!/usr/bin/env python
"""
jNWB Helper Functions - Event-centric NWB data extraction
Based on jNWB.ipynb patterns for binary event filtering and signal extraction
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional

def get_binary_events_for_code(nwb, target_code, target_interval_name: str, code_column: str) -> np.ndarray:
    """
    Create a binary array marking all rows matching a specific code value.

    Args:
        nwb: NWBFile object
        target_code: Value to match in code_column
        target_interval_name: Name of interval table (e.g., 'omission_glo_passive')
        code_column: Column name to search (e.g., 'correct', 'codes', 'stimulus_number', 'task_condition_number')

    Returns:
        np.ndarray: Boolean array, True where code matches target_code
    """
    # Get interval table as dataframe
    interval_df = nwb.intervals[target_interval_name].to_dataframe()

    # Get column data
    column_data = interval_df[code_column].values

    # Convert to numeric if needed
    if column_data.dtype == object:
        try:
            column_data = pd.to_numeric([float(str(x)) for x in column_data])
        except:
            column_data = column_data

    # Create binary array
    binary_array = np.array(column_data == target_code, dtype=bool)

    return binary_array


def get_onset_time_bin(nwb, binary_array: np.ndarray, target_interval_name: str) -> np.ndarray:
    """
    Extract onset times (start_time) for all True indices in binary array.

    Args:
        nwb: NWBFile object
        binary_array: Boolean array indicating which rows to extract
        target_interval_name: Name of interval table

    Returns:
        np.ndarray: Onset times (in seconds) for matched events
    """
    interval_df = nwb.intervals[target_interval_name].to_dataframe()
    onset_times = interval_df['start_time'].values[binary_array]

    return onset_times


def get_signal_array(nwb, onset_times: np.ndarray, time_pre: float, time_post: float,
                     signal_type: str = 'lfp') -> np.ndarray:
    """
    Extract aligned signal windows around onset times.

    Args:
        nwb: NWBFile object
        onset_times: Array of event times to align to
        time_pre: Time before onset (seconds)
        time_post: Time after onset (seconds)
        signal_type: 'lfp', 'muae', or 'spikes'

    Returns:
        np.ndarray: (n_events, n_timepoints, n_channels) for LFP/MUAe
    """
    # Get sampling rate and data based on signal type
    if signal_type == 'lfp':
        signal_container = nwb.acquisition.get('probe_0_lfp')
        if signal_container is None:
            # Try alternative names
            for key in nwb.acquisition:
                if 'lfp' in key.lower():
                    signal_container = nwb.acquisition[key]
                    break
    elif signal_type == 'muae':
        signal_container = nwb.acquisition.get('probe_0_muae')
    else:
        raise ValueError(f"Unknown signal_type: {signal_type}")

    if signal_container is None:
        raise ValueError(f"Could not find {signal_type} signal in acquisition")

    fs = int(signal_container.rate)
    timestamps = signal_container.timestamps[:]
    data = signal_container.data[:]

    # Calculate sample indices
    samples_pre = int(time_pre * fs)
    samples_post = int(time_post * fs)
    total_samples = samples_pre + samples_post

    # Extract epochs
    epochs = []
    for onset_time in onset_times:
        # Find closest timestamp
        idx = np.searchsorted(timestamps, onset_time)
        start_idx = max(0, idx - samples_pre)
        end_idx = min(len(data), idx + samples_post)

        # Extract window
        epoch = data[start_idx:end_idx, :]

        # Pad if necessary
        if epoch.shape[0] < total_samples:
            pad_top = idx - samples_pre - start_idx
            pad_bottom = total_samples - epoch.shape[0] - pad_top
            epoch = np.pad(epoch, ((pad_top, pad_bottom), (0, 0)), mode='constant', value=np.nan)

        epochs.append(epoch)

    return np.array(epochs)


def extract_correct_p1_by_condition(nwb_file_path: str) -> pd.DataFrame:
    """
    Extract correct P1 trials grouped by condition using binary event filtering.

    Returns:
        DataFrame with columns: condition_code, condition_label, p1_count
    """
    from pynwb import NWBHDF5IO

    # Condition mapping
    CONDITION_MAP = {
        1: "AAAB", 2: "AAAB", 3: "AXAB", 4: "AAXB", 5: "AAAX",
        6: "BBBA", 7: "BBBA", 8: "BXBA", 9: "BBXA", 10: "BBBX",
        **{n: "RRRR" for n in range(11, 27)},
        **{n: "RXRR" for n in range(27, 35)},
        **{n: "RRXR" for n in (35, 37, 39, 41)},
        **{n: "RRRX" for n in (36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50)},
    }

    with NWBHDF5IO(str(nwb_file_path), 'r', load_namespaces=True) as io:
        nwb = io.read()

        # Binary event filters
        correct_b = get_binary_events_for_code(nwb, 1.0, 'omission_glo_passive', 'correct')
        p1_b = get_binary_events_for_code(nwb, 2, 'omission_glo_passive', 'stimulus_number')

        results = []

        # For each condition code (1-50)
        for cond_code in range(1, 51):
            cond_b = get_binary_events_for_code(nwb, float(cond_code), 'omission_glo_passive', 'task_condition_number')

            # Combine: correct AND p1 AND this condition
            matched = correct_b & p1_b & cond_b
            count = np.sum(matched)

            if count > 0:
                cond_label = CONDITION_MAP.get(cond_code, f'UNKNOWN_{cond_code}')
                results.append({
                    'condition_code': cond_code,
                    'condition_label': cond_label,
                    'p1_correct_count': count
                })

        return pd.DataFrame(results)
