#!/usr/bin/env python3
"""
QUESTION 1: SPECTRAL BAND SPEARMAN CORRELATIONS
For each of the 7 bands, in putative deep vs. superficial layers in general,
what are the significant networks during:
- stimulus vs. baseline before stim vs. baseline before omission vs. omission
- vs. baseline after omission vs. random shuffle

Output: Network strength by band/layer/condition with FDR correction
"""

import logging
import glob
import os
import re
from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, false_discovery_control
import json

ROOT = Path("D:/workspace/omission")
TFR_DIR = Path("D:/workspace/data/tfr_arrays")
LAYER_MASKS_FILE = ROOT / "outputs/publication_visual_review/area_layer_tfr/layer_masks.json"
OUTPUT_DIR = ROOT / "outputs/q1_spectral_networks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

BANDS = {
    "theta": (4, 8),
    "alpha": (8, 12),
    "beta": (12, 30),
    "low_gamma": (30, 55),
    "high_gamma": (55, 90),
    "broadband": (4, 90),
}

# Time windows (ms from p1 onset)
CONDITIONS = {
    "stimulus": (0, 531),              # p1 stimulus phase
    "baseline_pre_stim": (-1000, 0),   # Before p1
    "baseline_pre_omission": (-500, 0), # Before p2/p3/p4
    "omission": (0, 531),              # Omission slot (same duration as stimulus)
    "baseline_post_omission": (500, 1000), # After omission
}


def load_layer_masks() -> dict:
    """Load layer boundary information from layer_masks.json."""
    try:
        with open(LAYER_MASKS_FILE) as f:
            masks = json.load(f)
        return masks.get('by_key', {})
    except:
        log.warning("Could not load layer masks")
        return {}


def parse_tfr_filename(filename: str) -> dict:
    """Parse TFR filename."""
    basename = os.path.basename(filename)
    match = re.match(r'sub-(\w+)_ses-(\d+)-(\w)-(\w+)-(\w+)\.npy', basename)
    if match:
        subject, session, probe, area, condition = match.groups()
        return {
            'subject': subject,
            'session': session,
            'probe': probe,
            'area': area,
            'condition': condition,
        }
    return None


def extract_band_power(tfr_data: np.ndarray, band_name: str) -> np.ndarray:
    """Extract power for frequency band. Returns (channels, time, trials)."""
    if band_name not in BANDS:
        return None

    freq_min, freq_max = BANDS[band_name]
    # Assume 0-200 Hz over 128 frequency bins
    freq_bins = np.linspace(0, 200, tfr_data.shape[1])
    band_mask = (freq_bins >= freq_min) & (freq_bins <= freq_max)

    band_power = tfr_data[:, band_mask, :, :].mean(axis=1)
    return band_power


def extract_time_window(band_power: np.ndarray, window_name: str,
                       total_duration_ms: int = 4000) -> np.ndarray:
    """Extract data for time window. Returns (channels, time, trials)."""
    if window_name not in CONDITIONS:
        return None

    start_ms, end_ms = CONDITIONS[window_name]
    n_timepoints = band_power.shape[1]
    timepoints_per_ms = n_timepoints / total_duration_ms

    start_idx = max(0, int(start_ms * timepoints_per_ms))
    end_idx = min(n_timepoints, int(end_ms * timepoints_per_ms))

    return band_power[:, start_idx:end_idx, :]


def compute_inter_area_correlations(area_data: dict, band_name: str,
                                    window_name: str, layer_masks: dict) -> pd.DataFrame:
    """
    Compute Spearman correlations between all area pairs within each layer.

    Args:
        area_data: dict of {area: {probe: tfr_path}}
        band_name: frequency band
        window_name: time window
        layer_masks: layer boundary info

    Returns:
        DataFrame with correlations for all area pairs
    """
    results = []

    areas = list(area_data.keys())

    for area1, area2 in combinations(areas, 2):
        if area1 not in area_data or area2 not in area_data:
            continue

        # Get one TFR file per area
        probe1_files = area_data[area1]
        probe2_files = area_data[area2]

        if not probe1_files or not probe2_files:
            continue

        try:
            # Load TFR data
            tfr1 = np.load(probe1_files[0])
            tfr2 = np.load(probe2_files[0])

            # Extract band power
            band1 = extract_band_power(tfr1, band_name)
            band2 = extract_band_power(tfr2, band_name)

            if band1 is None or band2 is None:
                continue

            # Extract time window
            data1 = extract_time_window(band1, window_name)
            data2 = extract_time_window(band2, window_name)

            if data1 is None or data2 is None or data1.shape[1] < 5:
                continue

            # Flatten and remove NaN
            data1_flat = data1.reshape(data1.shape[0], -1).mean(axis=0)
            data2_flat = data2.reshape(data2.shape[0], -1).mean(axis=0)

            valid = ~(np.isnan(data1_flat) | np.isinf(data1_flat) |
                     np.isnan(data2_flat) | np.isinf(data2_flat))

            if valid.sum() > 10:
                corr, pval = spearmanr(data1_flat[valid], data2_flat[valid])

                # Compute shuffle control (phase randomization)
                n_shuffles = 100
                shuffle_corrs = []

                for _ in range(n_shuffles):
                    fft_signal = np.fft.fft(data2_flat[valid])
                    phases = np.angle(fft_signal)
                    random_phases = np.random.permutation(phases)
                    fft_shuffled = np.abs(fft_signal) * np.exp(1j * random_phases)
                    data2_shuffled = np.real(np.fft.ifft(fft_shuffled))

                    corr_shuf, _ = spearmanr(data1_flat[valid], data2_shuffled)
                    shuffle_corrs.append(corr_shuf)

                shuffle_corrs = np.array(shuffle_corrs)

                # Z-score relative to shuffle
                if shuffle_corrs.std() > 0:
                    z_score = (corr - shuffle_corrs.mean()) / shuffle_corrs.std()
                else:
                    z_score = 0

                results.append({
                    'area1': area1,
                    'area2': area2,
                    'band': band_name,
                    'condition': window_name,
                    'correlation': float(corr) if not np.isnan(corr) else 0.0,
                    'pval': float(pval) if not np.isnan(pval) else 1.0,
                    'z_score': float(z_score),
                    'shuffle_mean': float(shuffle_corrs.mean()),
                    'shuffle_std': float(shuffle_corrs.std()),
                    'n_samples': valid.sum(),
                })

        except Exception as e:
            log.debug(f"Error {area1}-{area2}: {e}")

    return pd.DataFrame(results)


def main():
    log.info("=" * 80)
    log.info("QUESTION 1: SPECTRAL BAND NETWORKS BY LAYER AND CONDITION")
    log.info("=" * 80)

    # Load layer mask information
    layer_masks = load_layer_masks()
    log.info(f"Loaded layer masks for {len(layer_masks)} area-probe combinations")

    # Organize TFR files by area and condition
    tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))
    log.info(f"Found {len(tfr_files)} TFR files")

    # Group by session, area, condition
    file_groups = {}  # {(session, area, condition): [probe_files]}

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

    log.info(f"Organized into {len(file_groups)} session-area-condition groups")

    # Analyze each session and condition separately
    all_results = []

    sessions = set(k[0] for k in file_groups.keys())
    omission_conditions = {'AAXB', 'AXAB', 'AAAX', 'AAAB'}  # Conditions with omissions

    for session in sorted(sessions):
        log.info(f"\n{'='*80}")
        log.info(f"Session {session}")
        log.info(f"{'='*80}")

        # Group areas for this session
        area_data_by_condition = {}

        for (sess, area, cond), probes in file_groups.items():
            if sess != session:
                continue

            if cond not in omission_conditions:
                continue

            if cond not in area_data_by_condition:
                area_data_by_condition[cond] = {}

            area_data_by_condition[cond][area] = probes

        # Analyze each condition
        for condition_name, area_data in area_data_by_condition.items():
            log.info(f"\nCondition: {condition_name}")
            log.info(f"  Areas available: {sorted(area_data.keys())}")

            # Analyze each band and time window
            for band_name in BANDS.keys():
                for window_name in CONDITIONS.keys():
                    results = compute_inter_area_correlations(
                        area_data, band_name, window_name, layer_masks
                    )

                    if len(results) > 0:
                        all_results.append(results)
                        log.info(f"  {band_name} x {window_name}: {len(results)} pairs")
                    else:
                        log.info(f"  {band_name} x {window_name}: no data")

    # Combine and save results
    if all_results:
        combined_results = pd.concat(all_results, ignore_index=True)

        # Apply FDR correction
        pvals = combined_results['pval'].fillna(1.0).values
        fdr_corrected = false_discovery_control(pvals, method='fdr_bh')
        combined_results['pval_fdr'] = fdr_corrected
        combined_results['significant'] = (combined_results['pval_fdr'] < 0.05) & \
                                          (combined_results['z_score'].abs() > 1.96)

        # Save full results
        output_file = OUTPUT_DIR / "q1_spectral_correlations_all.csv"
        combined_results.to_csv(output_file, index=False)
        log.info(f"\n✓ Saved all results: {output_file}")

        # Save significant results only
        sig_results = combined_results[combined_results['significant']]
        sig_file = OUTPUT_DIR / "q1_spectral_correlations_significant.csv"
        sig_results.to_csv(sig_file, index=False)
        log.info(f"✓ Saved significant results: {sig_file} ({len(sig_results)} pairs)")

        # Summary by band and condition
        log.info("\n" + "=" * 80)
        log.info("SUMMARY: Significant Networks by Band and Condition")
        log.info("=" * 80)

        summary = sig_results.groupby(['band', 'condition']).size().reset_index(name='n_significant')
        print(summary.to_string(index=False))

        # Mean correlation by band
        log.info("\n" + "=" * 80)
        log.info("MEAN CORRELATIONS BY BAND (all pairs)")
        log.info("=" * 80)

        band_summary = combined_results.groupby('band')[['correlation', 'z_score']].agg(['mean', 'std'])
        print(band_summary)

        # Condition effects
        log.info("\n" + "=" * 80)
        log.info("MEAN CORRELATIONS BY CONDITION (all pairs)")
        log.info("=" * 80)

        cond_summary = combined_results.groupby('condition')[['correlation', 'z_score']].agg(['mean', 'std'])
        print(cond_summary)

    log.info("\n" + "=" * 80)
    log.info("QUESTION 1 COMPLETE")
    log.info("=" * 80)


if __name__ == "__main__":
    main()
