#!/usr/bin/env python3
"""
Minimal Q1 debug: Single session, single condition, single band.
Trace where correlations are computed or skipped.
"""

import logging
import glob
import os
import re
from pathlib import Path
from itertools import combinations

import numpy as np

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

TFR_DIR = Path("D:/workspace/data/tfr_arrays")
BANDS = {"alpha": (8, 12)}
CONDITIONS = {"stimulus": (0, 531)}

# Get TFR files
tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))
log.info(f"Found {len(tfr_files)} TFR files")

# Parse filenames to organize by session/area/condition
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

# Filter to single session (230629) and single condition (AAAB)
file_groups = {}
target_session = 230629
target_condition = 'AAAB'

for tfr_file in tfr_files:
    meta = parse_tfr_filename(tfr_file)
    if not meta:
        continue
    if meta['session'] != target_session or meta['condition'] != target_condition:
        continue

    key = (meta['session'], meta['area'], meta['condition'])
    if key not in file_groups:
        file_groups[key] = {}
    if meta['probe'] not in file_groups[key]:
        file_groups[key][meta['probe']] = []
    file_groups[key][meta['probe']].append(tfr_file)

log.info(f"Files for session {target_session}, condition {target_condition}: {file_groups}")

# Build area data
area_data_by_condition = {}
for (sess, area, cond), probes in file_groups.items():
    if sess != target_session or cond != target_condition:
        continue
    if cond not in area_data_by_condition:
        area_data_by_condition[cond] = {}
    area_data_by_condition[cond][area] = probes

log.info(f"Area data: {list(area_data_by_condition.get(target_condition, {}).keys())}")

# Now try to compute correlations
if target_condition in area_data_by_condition:
    area_data = area_data_by_condition[target_condition]
    areas = sorted(area_data.keys())
    log.info(f"Areas to correlate: {areas}")

    pair_count = 0
    for area1, area2 in combinations(areas, 2):
        pair_count += 1
        log.info(f"\n=== Pair {pair_count}: {area1} vs {area2} ===")

        probe_dict1 = area_data[area1]
        probe_dict2 = area_data[area2]

        log.info(f"  {area1} probe dict: {list(probe_dict1.keys())}")
        log.info(f"  {area2} probe dict: {list(probe_dict2.keys())}")

        if not probe_dict1 or not probe_dict2:
            log.warning(f"  Skipped: empty probe dict")
            continue

        # Get first probe's first file
        probe1_files = list(probe_dict1.values())[0]
        probe2_files = list(probe_dict2.values())[0]

        log.info(f"  {area1} files: {[os.path.basename(f) for f in probe1_files]}")
        log.info(f"  {area2} files: {[os.path.basename(f) for f in probe2_files]}")

        # Load
        try:
            tfr1 = np.load(probe1_files[0])
            tfr2 = np.load(probe2_files[0])
            log.info(f"  Loaded: {tfr1.shape}, {tfr2.shape}")
        except Exception as e:
            log.error(f"  Load error: {e}")
            continue

        # Extract band (alpha)
        band_name = 'alpha'
        f_min, f_max = BANDS[band_name]
        freq_bins = np.linspace(0, 200, tfr1.shape[1])
        band_mask = (freq_bins >= f_min) & (freq_bins <= f_max)

        band1 = tfr1[:, band_mask, :, :].mean(axis=1)
        band2 = tfr2[:, band_mask, :, :].mean(axis=1)
        log.info(f"  Band extracted: {band1.shape}, {band2.shape}")

        # Extract window (stimulus)
        window_name = 'stimulus'
        start_ms, end_ms = CONDITIONS[window_name]
        n_timepoints = band1.shape[1]
        total_duration_ms = 4000
        timepoints_per_ms = n_timepoints / total_duration_ms

        start_idx = max(0, int((start_ms + 2000) * timepoints_per_ms))
        end_idx = min(n_timepoints, int((end_ms + 2000) * timepoints_per_ms))

        data1 = band1[:, start_idx:end_idx, :]
        data2 = band2[:, start_idx:end_idx, :]
        log.info(f"  Window extracted: {data1.shape}, {data2.shape}")

        # Check for filter failures
        if data1 is None or data2 is None:
            log.warning(f"  Skipped: window extraction returned None")
            continue

        if data1.shape[1] < 5:
            log.warning(f"  Skipped: insufficient time points ({data1.shape[1]} < 5)")
            continue

        # Channel averaging
        data1_area = data1.mean(axis=0)
        data2_area = data2.mean(axis=0)
        log.info(f"  After channel avg: {data1_area.shape}, {data2_area.shape}")

        # Flatten and correlate
        data1_flat = data1_area.reshape(-1)
        data2_flat = data2_area.reshape(-1)

        from scipy.stats import spearmanr
        corr, pval = spearmanr(data1_flat, data2_flat)
        log.info(f"  CORRELATION: r={corr:.4f}, p={pval:.6f}")

log.info(f"\n=== SUMMARY ===")
log.info(f"Total pairs to correlate: {pair_count}")
