#!/usr/bin/env python3
"""Debug Q1 correlation computation."""

import numpy as np
from pathlib import Path
from itertools import combinations
from scipy.stats import spearmanr

# Test parameters
band_name = 'alpha'
window_name = 'stimulus'
BANDS = {
    "theta": (4, 8),
    "alpha": (8, 12),
    "beta": (12, 30),
    "low_gamma": (30, 55),
    "high_gamma": (55, 90),
}
CONDITIONS = {
    "stimulus": (0, 531),
    "baseline_pre_stim": (-1000, 0),
    "baseline_pre_omission": (-500, 0),
    "omission": (0, 531),
    "baseline_post_omission": (500, 1000),
}

# Load sample TFR data
tfr1 = np.load("D:/workspace/data/tfr_arrays/sub-V198o_ses-230629-A-V1-AAAB.npy")
tfr2 = np.load("D:/workspace/data/tfr_arrays/sub-V198o_ses-230629-B-V3a-AAAB.npy")

print(f"TFR1 shape: {tfr1.shape}")
print(f"TFR2 shape: {tfr2.shape}\n")

# Extract band
def extract_band_power(tfr_data, band_name):
    """Extract band power. Returns (channels, time, trials)."""
    if band_name not in BANDS:
        return None

    freq_min, freq_max = BANDS[band_name]
    freq_bins = np.linspace(0, 200, tfr_data.shape[1])
    band_mask = (freq_bins >= freq_min) & (freq_bins <= freq_max)

    return tfr_data[:, band_mask, :, :].mean(axis=1)

band1 = extract_band_power(tfr1, band_name)
band2 = extract_band_power(tfr2, band_name)

print(f"Band1 (alpha) shape: {band1.shape}")
print(f"Band2 (alpha) shape: {band2.shape}\n")

# Extract time window
def extract_time_window(band_power, window_name):
    """Extract time window. Returns (channels, time, trials)."""
    if window_name not in CONDITIONS:
        return None

    start_ms, end_ms = CONDITIONS[window_name]
    n_timepoints = band_power.shape[1]
    total_duration_ms = 4000
    timepoints_per_ms = n_timepoints / total_duration_ms

    # Add 2000ms offset for baseline window
    start_idx = max(0, int((start_ms + 2000) * timepoints_per_ms))
    end_idx = min(n_timepoints, int((end_ms + 2000) * timepoints_per_ms))

    if start_idx >= end_idx or start_idx >= n_timepoints:
        return None

    return band_power[:, start_idx:end_idx, :]

data1 = extract_time_window(band1, window_name)
data2 = extract_time_window(band2, window_name)

print(f"Data1 (windowed) shape: {data1.shape if data1 is not None else 'None'}")
print(f"Data2 (windowed) shape: {data2.shape if data2 is not None else 'None'}\n")

if data1 is not None and data2 is not None:
    # Channel averaging (CRITICAL FIX)
    print("Applying channel averaging...")
    data1_area = data1.mean(axis=0)  # (channels, time, trials) -> (time, trials)
    data2_area = data2.mean(axis=0)

    print(f"Data1_area shape: {data1_area.shape}")
    print(f"Data2_area shape: {data2_area.shape}\n")

    # Flatten
    data1_flat = data1_area.reshape(-1)
    data2_flat = data2_area.reshape(-1)

    print(f"Flattened shapes: {data1_flat.shape}, {data2_flat.shape}")
    print(f"Flatten sanity check: {len(data1_flat)} samples\n")

    # Check for NaN/Inf
    print(f"Data1 NaN count: {np.isnan(data1_flat).sum()}")
    print(f"Data1 Inf count: {np.isinf(data1_flat).sum()}")
    print(f"Data2 NaN count: {np.isnan(data2_flat).sum()}")
    print(f"Data2 Inf count: {np.isinf(data2_flat).sum()}\n")

    # Test correlation
    valid = ~(np.isnan(data1_flat) | np.isinf(data1_flat) | np.isnan(data2_flat) | np.isinf(data2_flat))
    print(f"Valid samples: {valid.sum()} / {len(valid)}")

    if valid.sum() >= 10:
        sig1_valid = data1_flat[valid]
        sig2_valid = data2_flat[valid]

        corr, pval = spearmanr(sig1_valid, sig2_valid)
        print(f"\nSpearman correlation: r={corr:.4f}, p={pval:.6f}")

        if np.isnan(corr):
            print("WARNING: Correlation is NaN!")
        if np.isnan(pval):
            print("WARNING: P-value is NaN!")
    else:
        print("ERROR: Too few valid samples for correlation!")
