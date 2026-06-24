#!/usr/bin/env python3
"""
Simplified Spectral Network Analysis
Answers three core questions about omission encoding networks
"""

import logging
import glob
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path("D:/workspace/omission")
TFR_DIR = Path("D:/workspace/data/tfr_arrays")
OUTPUT_DIR = ROOT / "outputs/spectral_network_analysis"
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
    """Extract power for frequency band. Shape: (channels, time, trials)."""
    if band_name not in BANDS:
        return None

    freq_min, freq_max = BANDS[band_name]
    # Assume 0-200 Hz over 128 frequency bins
    freq_bins = np.linspace(0, 200, tfr_data.shape[1])
    band_mask = (freq_bins >= freq_min) & (freq_bins <= freq_max)

    # Average over frequency: (channels, freq_bins, time, trials) -> (channels, time, trials)
    band_power = tfr_data[:, band_mask, :, :].mean(axis=1)
    return band_power


def main():
    log.info("=" * 70)
    log.info("SPECTRAL NETWORK ANALYSIS FOR OMISSION ENCODING")
    log.info("=" * 70)

    # Organize TFR files
    tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))
    log.info(f"Found {len(tfr_files)} TFR files")

    # Group by area and condition
    file_groups = {}
    for tfr_file in tfr_files:
        meta = parse_tfr_filename(tfr_file)
        if not meta:
            continue
        key = (meta['area'], meta['condition'])
        if key not in file_groups:
            file_groups[key] = []
        file_groups[key].append(tfr_file)

    log.info(f"Organized into {len(file_groups)} area-condition groups")

    # Analyze sample
    results = []

    log.info("\n" + "=" * 70)
    log.info("ANALYZING FIRST 10 AREA-CONDITION COMBINATIONS")
    log.info("=" * 70)

    for i, ((area, condition), files) in enumerate(list(file_groups.items())[:10]):
        log.info(f"\n[{i+1}] {area} - {condition} ({len(files)} files)")

        if not files:
            continue

        try:
            # Load first TFR file
            tfr_data = np.load(files[0])
            log.info(f"  TFR shape: {tfr_data.shape}")

            # Analyze each band
            for band_name in BANDS.keys():
                band_power = extract_band_power(tfr_data, band_name)

                if band_power is None or band_power.shape[1] < 10:
                    continue

                # Compute mean correlation across timepoints and trials
                # Split channels into two groups and correlate
                n_ch = band_power.shape[0]
                if n_ch > 2:
                    group1 = band_power[:n_ch//2].reshape(n_ch//2, -1).mean(axis=0)
                    group2 = band_power[n_ch//2:].reshape(n_ch - n_ch//2, -1).mean(axis=0)

                    # Remove NaN/Inf
                    valid = ~(np.isnan(group1) | np.isinf(group1) |
                             np.isnan(group2) | np.isinf(group2))

                    if valid.sum() > 10:
                        corr, pval = spearmanr(group1[valid], group2[valid])

                        results.append({
                            'area': area,
                            'condition': condition,
                            'band': band_name,
                            'correlation': float(corr) if not np.isnan(corr) else 0.0,
                            'pval': float(pval) if not np.isnan(pval) else 1.0,
                            'n_samples': valid.sum(),
                        })

                        log.info(f"    {band_name}: r={corr:.3f}, p={pval:.4f}")

        except Exception as e:
            log.warning(f"  Error: {e}")

    # Save results
    if results:
        results_df = pd.DataFrame(results)
        output_file = OUTPUT_DIR / "spectral_correlations_sample.csv"
        results_df.to_csv(output_file, index=False)
        log.info(f"\n✓ Saved: {output_file}")

        # Summary statistics
        log.info("\n" + "=" * 70)
        log.info("SUMMARY STATISTICS")
        log.info("=" * 70)
        print(results_df.groupby('band')[['correlation', 'pval']].agg(['mean', 'std']))

    log.info("\n" + "=" * 70)
    log.info("NEXT STEPS:")
    log.info("=" * 70)
    print("""
1. Expand analysis across ALL area pairs and conditions
2. Add spike cross-correlation analysis from NWB files
3. Compute lead times using cross-correlation with lag
4. Apply FDR correction across all comparisons
5. Generate network graphs showing connection strengths
6. Test statistical significance with permutation tests
    """)


if __name__ == "__main__":
    main()
