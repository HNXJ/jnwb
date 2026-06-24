#!/usr/bin/env python3
"""
Minimal spectral pipeline test - fast validation without full computation
"""

import logging
import glob
from pathlib import Path
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Paths
TFR_DIR = Path("D:/workspace/data/tfr_arrays")
RESULTS_DIR = Path("D:/workspace/omission/outputs/spectral_relations_pipeline/results")

def test_tfr_discovery():
    """Test 1: Can we find TFR files?"""
    tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))
    log.info(f"TEST 1: TFR Discovery")
    log.info(f"  Found {len(tfr_files)} TFR files")
    return len(tfr_files) > 0

def test_tfr_loading():
    """Test 2: Can we load a TFR file?"""
    tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))
    if not tfr_files:
        return False

    try:
        data = np.load(tfr_files[0])
        log.info(f"TEST 2: TFR Loading")
        log.info(f"  Loaded: {tfr_files[0].split('/')[-1]}")
        log.info(f"  Shape: {data.shape}")
        return True
    except Exception as e:
        log.error(f"  ERROR: {e}")
        return False

def test_band_extraction():
    """Test 3: Can we extract frequency bands?"""
    tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))
    if not tfr_files:
        return False

    try:
        data = np.load(tfr_files[0])

        # Extract alpha band (8-12 Hz)
        # Assume linear 0-200 Hz over 128 frequency bins
        freq_min, freq_max = 8, 12
        freq_bins = np.linspace(0, 200, data.shape[1])
        band_mask = (freq_bins >= freq_min) & (freq_bins <= freq_max)

        alpha = data[:, band_mask, :, :].mean(axis=1)

        log.info(f"TEST 3: Band Extraction")
        log.info(f"  Alpha band shape (after mean): {alpha.shape}")
        log.info(f"  Mean power: {alpha.mean():.4f}")
        return True
    except Exception as e:
        log.error(f"  ERROR: {e}")
        return False

def test_basic_correlation():
    """Test 4: Can we compute correlations?"""
    tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))
    if len(tfr_files) < 2:
        return False

    try:
        data1 = np.load(tfr_files[0])
        data2 = np.load(tfr_files[1])

        # Extract alpha from both
        freq_bins = np.linspace(0, 200, data1.shape[1])
        band_mask = (freq_bins >= 8) & (freq_bins <= 12)

        alpha1 = data1[:, band_mask, :, :].mean(axis=1)  # (channels, time, trials)
        alpha2 = data2[:, band_mask, :, :].mean(axis=1)

        # CRITICAL FIX: Average across channels to handle variable channel counts
        alpha1_area = alpha1.mean(axis=0).flatten()  # (time, trials) → flat
        alpha2_area = alpha2.mean(axis=0).flatten()

        # Correlation
        corr = np.corrcoef(alpha1_area, alpha2_area)[0, 1]

        log.info(f"TEST 4: Correlation")
        log.info(f"  File 1 shape before channel-avg: {alpha1.shape}")
        log.info(f"  File 2 shape before channel-avg: {alpha2.shape}")
        log.info(f"  After channel-avg and flatten: {alpha1_area.shape[0]} samples")
        log.info(f"  Correlation: {corr:.4f}")
        return not np.isnan(corr)
    except Exception as e:
        log.error(f"  ERROR: {e}")
        return False

def test_unit_loading():
    """Test 5: Can we load units database?"""
    try:
        units_file = Path("D:/workspace/omission/outputs/publication_figures/comprehensive_grand_database_all_units.csv")
        if units_file.exists():
            units = pd.read_csv(units_file)
            log.info(f"TEST 5: Units Database")
            log.info(f"  Loaded {len(units)} units")
            return len(units) > 0
        else:
            log.warning(f"TEST 5: Units file not found")
            return False
    except Exception as e:
        log.error(f"  ERROR: {e}")
        return False

def main():
    log.info("=" * 80)
    log.info("MINIMAL SPECTRAL PIPELINE TEST")
    log.info("=" * 80)

    tests = [
        ("TFR Discovery", test_tfr_discovery),
        ("TFR Loading", test_tfr_loading),
        ("Band Extraction", test_band_extraction),
        ("Basic Correlation", test_basic_correlation),
        ("Unit Loading", test_unit_loading),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results[test_name] = "PASS" if passed else "FAIL"
        except Exception as e:
            results[test_name] = f"ERROR: {e}"
            log.error(f"  Exception: {e}")

    log.info("\n" + "=" * 80)
    log.info("TEST SUMMARY")
    log.info("=" * 80)
    for test_name, result in results.items():
        status = "✓" if result == "PASS" else "✗"
        log.info(f"  {status} {test_name}: {result}")

    all_passed = all(r == "PASS" for r in results.values())
    log.info("\n" + ("=" * 80))
    if all_passed:
        log.info("✓ ALL TESTS PASSED - Pipeline ready to run")
    else:
        log.info("✗ SOME TESTS FAILED - Check errors above")
    log.info("=" * 80)

if __name__ == "__main__":
    main()
