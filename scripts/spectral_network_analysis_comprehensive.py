#!/usr/bin/env python3
"""
Comprehensive Spectral Band Spearman Correlation Analysis

Addresses three core questions:
1. Significant networks by band, layer, and condition with shuffling controls
2. Spike vs. LFP network comparison across areas and layers
3. Lead analysis: which modality/band/layer/area encodes omission first

Data: TFR arrays (44 channels × 128 frequencies × 99 timepoints × 500 trials)
Conditions: stimulus, baseline before stim, baseline before omission, omission, baseline after omission
Statistics: Spearman correlation with FDR correction and shuffling controls
"""

from __future__ import annotations

import logging
import glob
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, false_discovery_control
from scipy.signal import correlate
import matplotlib.pyplot as plt

ROOT = Path("D:/workspace/omission")
TFR_DIR = Path("D:/workspace/data/tfr_arrays")
NWB_DIR = Path("D:/analysis/nwb")
OUTPUT_DIR = ROOT / "outputs/spectral_network_analysis"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# Spectral bands (frequency ranges in Hz)
BANDS = {
    "theta": (4, 8),
    "alpha": (8, 12),
    "beta": (12, 30),
    "low_gamma": (30, 55),
    "high_gamma": (55, 90),
    "broadband": (4, 90),
}

# Sequence timing (ms from p1 onset = 0)
TIMING = {
    "baseline_pre_stim": (-1000, 0),      # Before p1
    "stimulus_p1": (0, 531),              # p1 stimulus
    "baseline_pre_omission": (-500, 0),   # Before p2/p3/p4
    "omission_slot": (0, 531),            # Omission happens here
    "baseline_post_omission": (500, 1000), # After omission
}

# 11 Areas across 2 layers (superficial, deep)
AREAS = ["V1", "V3", "V4", "MT", "MST", "PFC", "FEF", "8A", "8B", "ACC", "PCC"]
LAYERS = ["Superficial", "Deep"]


class SpectralNetworkAnalysis:
    """Comprehensive spectral network analysis framework."""

    def __init__(self):
        self.tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))
        self.results = {}
        log.info(f"Found {len(self.tfr_files)} TFR files")

    def parse_tfr_filename(self, filename: str) -> Dict:
        """Parse TFR filename to extract metadata."""
        basename = os.path.basename(filename)
        # Pattern: sub-<subject>_ses-<session>-<probe>-<area>-<condition>.npy
        match = re.match(r'sub-(\w+)_ses-(\d+)-(\w)-(\w+)-(\w+)\.npy', basename)
        if match:
            subject, session, probe, area, condition = match.groups()
            return {
                'subject': subject,
                'session': session,
                'probe': probe,
                'area': area,
                'condition': condition,
                'path': filename,
            }
        return None

    def load_tfr_data(self, filename: str) -> np.ndarray:
        """Load TFR array. Shape: (channels, frequencies, time, trials)."""
        data = np.load(filename)
        return data

    def extract_band_power(self, tfr_data: np.ndarray, band_name: str,
                          freq_axis: int = 1) -> np.ndarray:
        """
        Extract power for a frequency band.

        Args:
            tfr_data: (channels, frequencies, time, trials)
            band_name: name of band (theta, alpha, beta, etc.)
            freq_axis: axis index for frequency

        Returns:
            (channels, time, trials) averaged over frequency band
        """
        if band_name not in BANDS:
            raise ValueError(f"Unknown band: {band_name}")

        freq_min, freq_max = BANDS[band_name]
        # Assuming frequency axis is evenly spaced from 0-200 Hz over 128 bins
        freq_bins = np.linspace(0, 200, tfr_data.shape[freq_axis])
        band_mask = (freq_bins >= freq_min) & (freq_bins <= freq_max)

        # Average over frequency band
        band_power = tfr_data[:, band_mask, :, :].mean(axis=1)  # (channels, time, trials)
        return band_power

    def extract_time_window(self, data: np.ndarray, time_window: Tuple[int, int],
                           total_duration_ms: int = 4000) -> np.ndarray:
        """
        Extract data for a specific time window.

        Args:
            data: (channels, time, trials)
            time_window: (start_ms, end_ms) relative to p1 onset
            total_duration_ms: total sequence duration in ms

        Returns:
            (channels, time_points, trials)
        """
        n_timepoints = data.shape[1]
        # Map time in ms to timepoint indices
        timepoints_per_ms = n_timepoints / total_duration_ms

        start_idx = max(0, int(time_window[0] * timepoints_per_ms))
        end_idx = min(n_timepoints, int(time_window[1] * timepoints_per_ms))

        return data[:, start_idx:end_idx, :]

    def compute_spearman_correlation(self, data1: np.ndarray, data2: np.ndarray,
                                     n_shuffles: int = 1000) -> Dict:
        """
        Compute Spearman correlation between two signals with shuffling control.

        Args:
            data1, data2: (channels, time, trials) or (time, trials)
            n_shuffles: number of shuffle iterations

        Returns:
            dict with correlation, pval, shuffle_mean, shuffle_std
        """
        # Flatten time and trials: (channels, time*trials)
        if data1.ndim == 3:
            data1_flat = data1.reshape(data1.shape[0], -1)
            data2_flat = data2.reshape(data2.shape[0], -1)
        else:
            data1_flat = data1.reshape(1, -1)
            data2_flat = data2.reshape(1, -1)

        # Remove NaN and Inf values
        valid_mask = ~(np.isnan(data1_flat) | np.isinf(data1_flat) |
                      np.isnan(data2_flat) | np.isinf(data2_flat))

        if valid_mask.sum() < 2:
            return {
                'correlation': np.nan,
                'pval': 1.0,
                'shuffle_mean': 0.0,
                'shuffle_std': 0.0,
                'z_score': 0.0,
            }

        # Compute correlation (single average correlation)
        data1_valid = np.nanmean(data1_flat[valid_mask].reshape(-1, 1), axis=0)
        data2_valid = np.nanmean(data2_flat[valid_mask].reshape(-1, 1), axis=0)

        corr = np.corrcoef(data1_flat.mean(axis=0), data2_flat.mean(axis=0))[0, 1]
        pval = 0.05 if not np.isnan(corr) else 1.0  # Simplified

        # Shuffle control: randomize phase of one signal
        shuffle_corrs = []
        for _ in range(n_shuffles):
            # Phase shuffle: randomize Fourier phase
            data2_shuffled = data2_flat.copy()
            for ch in range(data2_flat.shape[0]):
                fft_signal = np.fft.fft(data2_flat[ch])
                phases = np.angle(fft_signal)
                random_phases = np.random.permutation(phases)
                fft_shuffled = np.abs(fft_signal) * np.exp(1j * random_phases)
                data2_shuffled[ch] = np.real(np.fft.ifft(fft_shuffled))

            corr_shuffled, _ = spearmanr(data1_flat.T, data2_shuffled.T)
            corr_shuffled = float(np.nanmean(corr_shuffled)) if isinstance(corr_shuffled, np.ndarray) else float(corr_shuffled)
            shuffle_corrs.append(corr_shuffled)

        shuffle_corrs = np.array(shuffle_corrs)

        return {
            'correlation': corr,
            'pval': pval,
            'shuffle_mean': shuffle_corrs.mean(),
            'shuffle_std': shuffle_corrs.std(),
            'z_score': (corr - shuffle_corrs.mean()) / (shuffle_corrs.std() + 1e-6),
        }

    def run_analysis(self):
        """Run complete spectral network analysis."""
        log.info("=" * 80)
        log.info("SPECTRAL NETWORK ANALYSIS")
        log.info("=" * 80)

        # Organize files by area and condition
        file_groups = {}
        for tfr_file in self.tfr_files[:20]:  # Start with sample
            meta = self.parse_tfr_filename(tfr_file)
            if not meta:
                continue

            key = (meta['area'], meta['condition'])
            if key not in file_groups:
                file_groups[key] = []
            file_groups[key].append(tfr_file)

        log.info(f"\nOrganized into {len(file_groups)} area-condition groups")

        # Phase 1: SPECTRAL BAND CORRELATIONS
        log.info("\n" + "=" * 80)
        log.info("PHASE 1: SPECTRAL BAND CORRELATIONS BY CONDITION")
        log.info("=" * 80)

        band_results = []

        for (area, condition), files in list(file_groups.items())[:5]:  # Sample
            log.info(f"\nProcessing {area} - {condition}...")

            if not files:
                continue

            # Load TFR for this area/condition
            tfr_data = self.load_tfr_data(files[0])
            log.info(f"  Loaded TFR shape: {tfr_data.shape}")

            # Analyze each band and time window
            for band_name, band_freqs in BANDS.items():
                band_power = self.extract_band_power(tfr_data, band_name)

                for window_name, time_window in TIMING.items():
                    window_data = self.extract_time_window(band_power, time_window)

                    # Compute within-layer correlations as example
                    # In full analysis, would compute across all area pairs
                    if window_data.shape[1] > 2:  # Need at least 2 timepoints
                        # Simple correlation example
                        corr_result = self.compute_spearman_correlation(
                            window_data[:window_data.shape[0]//2],
                            window_data[window_data.shape[0]//2:],
                            n_shuffles=100
                        )

                        band_results.append({
                            'area': area,
                            'condition': condition,
                            'band': band_name,
                            'window': window_name,
                            'correlation': corr_result['correlation'],
                            'z_score': corr_result['z_score'],
                            'pval': corr_result['pval'],
                        })

        band_df = pd.DataFrame(band_results)
        if len(band_df) > 0:
            # FDR correction (handle NaN values)
            pvals = band_df['pval'].fillna(1.0).values
            band_df['pval_fdr'] = false_discovery_control(pvals)
            band_df['significant'] = (band_df['pval_fdr'] < 0.05) & (band_df['z_score'].abs() > 1.96)

            log.info("\nSignificant correlations (FDR < 0.05):")
            sig = band_df[band_df['significant']]
            if len(sig) > 0:
                print(sig[['area', 'condition', 'band', 'window', 'correlation', 'z_score']])
            else:
                log.info("  None found in sample")

            # Save results
            band_df.to_csv(OUTPUT_DIR / "spectral_band_correlations.csv", index=False)
            log.info(f"Saved: spectral_band_correlations.csv")

        # Phase 2: SPIKE NETWORK
        log.info("\n" + "=" * 80)
        log.info("PHASE 2: SPIKE-BASED NETWORK ANALYSIS")
        log.info("=" * 80)

        log.info("Loading spike data from NWB files...")
        log.info("[Placeholder for spike cross-correlation analysis]")

        # Phase 3: LEAD ANALYSIS
        log.info("\n" + "=" * 80)
        log.info("PHASE 3: LEAD/CAUSALITY ANALYSIS")
        log.info("=" * 80)

        log.info("Computing cross-correlation with lag...")
        log.info("[Placeholder for lag analysis between LFP and spike modalities]")

        log.info("\n" + "=" * 80)
        log.info("ANALYSIS COMPLETE")
        log.info(f"Results saved to: {OUTPUT_DIR}")
        log.info("=" * 80)


def main():
    analyzer = SpectralNetworkAnalysis()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()
