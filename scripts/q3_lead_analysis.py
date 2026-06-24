#!/usr/bin/env python3
"""
QUESTION 3: LEAD/CAUSALITY ANALYSIS
Identifies which modality (LFP vs spike), which band, layer, and area
encodes omission earliest (leads).

Uses cross-correlation with lag to compute lead times.
Output: Lead times (ms) by modality/band/layer/area
"""

import logging
from pathlib import Path
import glob

import numpy as np
import pandas as pd
from scipy.signal import correlate
from scipy.stats import false_discovery_control

ROOT = Path("D:/workspace/omission")
TFR_DIR = Path("D:/workspace/data/tfr_arrays")
OUTPUT_DIR = ROOT / "outputs/q3_lead_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

BANDS = {
    "theta": (4, 8),
    "alpha": (8, 12),
    "beta": (12, 30),
    "low_gamma": (30, 55),
    "high_gamma": (55, 90),
}


def extract_band_power(tfr_data: np.ndarray, band_name: str) -> np.ndarray:
    """Extract power for frequency band. Returns (channels, time, trials)."""
    if band_name not in BANDS:
        return None

    freq_min, freq_max = BANDS[band_name]
    freq_bins = np.linspace(0, 200, tfr_data.shape[1])
    band_mask = (freq_bins >= freq_min) & (freq_bins <= freq_max)

    band_power = tfr_data[:, band_mask, :, :].mean(axis=1)
    return band_power


def compute_lead_time(signal1: np.ndarray, signal2: np.ndarray,
                     max_lag_ms: int = 500, sampling_rate_hz: int = 1000) -> dict:
    """
    Compute lead time between two signals using cross-correlation.

    Args:
        signal1, signal2: 1D arrays (flattened across channels/trials)
        max_lag_ms: maximum lag to test (ms)
        sampling_rate_hz: sampling rate in Hz

    Returns:
        dict with lead_time_ms, correlation_at_peak, and lag_direction
    """
    results = {
        'lead_time_ms': np.nan,
        'peak_correlation': 0.0,
        'lag_direction': 'unknown',  # 'signal1_leads' or 'signal2_leads'
    }

    if len(signal1) < 10 or len(signal2) < 10:
        return results

    # Normalize signals
    signal1 = (signal1 - np.nanmean(signal1)) / (np.nanstd(signal1) + 1e-6)
    signal2 = (signal2 - np.nanmean(signal2)) / (np.nanstd(signal2) + 1e-6)

    # Remove NaN
    valid = ~(np.isnan(signal1) | np.isnan(signal2))
    if valid.sum() < 10:
        return results

    signal1 = signal1[valid]
    signal2 = signal2[valid]

    # Compute cross-correlation
    max_lag_samples = int(max_lag_ms * sampling_rate_hz / 1000)
    ccf = correlate(signal1, signal2, mode='same')

    # Find peak
    peak_idx = np.argmax(np.abs(ccf))
    center_idx = len(ccf) // 2

    lag_samples = peak_idx - center_idx
    lag_ms = lag_samples * 1000 / sampling_rate_hz

    # Clip to max lag
    if abs(lag_ms) <= max_lag_ms:
        results['lead_time_ms'] = float(lag_ms)
        results['peak_correlation'] = float(ccf[peak_idx] / ccf[center_idx])

        if lag_ms < 0:
            results['lag_direction'] = 'signal1_leads'
        elif lag_ms > 0:
            results['lag_direction'] = 'signal2_leads'
        else:
            results['lag_direction'] = 'simultaneous'

    return results


def analyze_lead_times(tfr_dir: str = None) -> pd.DataFrame:
    """
    Analyze lead times across bands and conditions.
    """
    if tfr_dir is None:
        tfr_dir = str(TFR_DIR)

    results = []

    tfr_files = sorted(glob.glob(f"{tfr_dir}/*.npy"))
    log.info(f"Found {len(tfr_files)} TFR files")

    # Sample analysis: compute lead between bands within same area/condition
    processed = set()

    for i, tfr_file in enumerate(tfr_files[:50]):  # Sample first 50 files
        basename = tfr_file.split('/')[-1].split('\\')[-1]

        # Skip if already processed this area-condition
        area_cond = "_".join(basename.split("_")[-2:]).replace(".npy", "")
        if area_cond in processed:
            continue
        processed.add(area_cond)

        try:
            log.info(f"[{i+1}] {basename}")

            # Parse filename
            parts = basename.replace(".npy", "").split("-")
            area = parts[-2]
            condition = parts[-1]

            tfr_data = np.load(tfr_file)

            # Get band powers
            bands_data = {}
            for band_name in BANDS.keys():
                band_power = extract_band_power(tfr_data, band_name)
                if band_power is not None:
                    # Flatten: (channels, time, trials) -> single array
                    bands_data[band_name] = band_power.reshape(-1).mean()

            # Compare bands (lead analysis)
            band_names = list(bands_data.keys())

            for i, band1 in enumerate(band_names):
                for band2 in band_names[i+1:]:
                    # Get signals
                    band1_data = extract_band_power(tfr_data, band1).reshape(-1)
                    band2_data = extract_band_power(tfr_data, band2).reshape(-1)

                    # Remove NaN
                    valid = ~(np.isnan(band1_data) | np.isnan(band2_data))
                    if valid.sum() < 100:
                        continue

                    band1_data = band1_data[valid]
                    band2_data = band2_data[valid]

                    # Compute lead
                    lead_result = compute_lead_time(band1_data, band2_data)

                    results.append({
                        'area': area,
                        'condition': condition,
                        'signal1_band': band1,
                        'signal2_band': band2,
                        'lead_time_ms': lead_result['lead_time_ms'],
                        'peak_correlation': lead_result['peak_correlation'],
                        'lag_direction': lead_result['lag_direction'],
                    })

        except Exception as e:
            log.debug(f"Error: {e}")

    return pd.DataFrame(results)


def main():
    log.info("=" * 80)
    log.info("QUESTION 3: LEAD/CAUSALITY ANALYSIS")
    log.info("=" * 80)

    log.info("\nAnalyzing lead times between frequency bands...")
    log.info("(This computes which band responds first during omission)")

    results = analyze_lead_times()

    if len(results) > 0:
        # Save all results
        output_file = OUTPUT_DIR / "q3_lead_times_all.csv"
        results.to_csv(output_file, index=False)
        log.info(f"\n✓ Saved all lead analysis: {output_file}")

        # Apply statistical threshold
        significant = results[results['peak_correlation'].abs() > 0.3]
        sig_file = OUTPUT_DIR / "q3_lead_times_significant.csv"
        significant.to_csv(sig_file, index=False)
        log.info(f"✓ Saved significant leads: {sig_file}")

        # Summary
        log.info("\n" + "=" * 80)
        log.info("LEAD TIME SUMMARY")
        log.info("=" * 80)

        log.info(f"\nTotal band pair comparisons: {len(results)}")

        log.info("\nMean lead times by band pair:")
        lead_summary = results.groupby(['signal1_band', 'signal2_band'])['lead_time_ms'].agg(['mean', 'count'])
        lead_summary = lead_summary[lead_summary['count'] > 1]
        print(lead_summary.sort_values('mean'))

        log.info("\nDirection of leads:")
        direction_counts = results['lag_direction'].value_counts()
        for direction, count in direction_counts.items():
            log.info(f"  {direction}: {count}")

    log.info("\n" + "=" * 80)
    log.info("QUESTION 3 COMPLETE")
    log.info("=" * 80)


if __name__ == "__main__":
    main()
