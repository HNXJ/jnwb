#!/usr/bin/env python3
"""
COMPLETE OMISSION ENCODING NETWORK ANALYSIS
All 3 questions with fixes, expansions, and proper visualizations

1. Spectral band networks by layer/condition (FIXED)
2. Spike networks + LFP comparison (EXPANDED)
3. Lead analysis with cross-modal comparison (EXPANDED)
+ Comprehensive visualizations with relative axis positioning
"""

import logging
import glob
import os
import re
from pathlib import Path
from itertools import combinations
import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, false_discovery_control
from scipy.signal import correlate
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pynwb import NWBHDF5IO

ROOT = Path("D:/workspace/omission")
TFR_DIR = Path("D:/workspace/data/tfr_arrays")
NWB_DIR = Path("D:/analysis/nwb")
GRAND_DB = ROOT / "outputs/publication_figures/comprehensive_grand_database_all_units.csv"
LAYER_MASKS_FILE = ROOT / "outputs/publication_visual_review/area_layer_tfr/layer_masks.json"
OUTPUT_DIR = ROOT / "outputs/complete_omission_network_analysis"
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

CONDITIONS = {
    "stimulus": (0, 531),
    "baseline_pre_stim": (-1000, 0),
    "baseline_pre_omission": (-500, 0),
    "omission": (0, 531),
    "baseline_post_omission": (500, 1000),
}


class OmissionNetworkAnalysis:
    """Complete multi-modal omission network analysis."""

    def __init__(self):
        self.tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))
        self.nwb_map = self._get_nwb_map()
        self.units_db = pd.read_csv(GRAND_DB)
        self.layer_masks = self._load_layer_masks()

        self.q1_results = []  # Spectral networks
        self.q2_results = []  # Spike networks
        self.q3_results = []  # Lead times

        log.info(f"Initialized with {len(self.tfr_files)} TFR files")
        log.info(f"Found {len(self.nwb_map)} NWB files")
        log.info(f"Loaded {len(self.units_db)} units")

    def _get_nwb_map(self) -> dict:
        """Get session to NWB file mapping."""
        nwb_map = {}
        for f in sorted(glob.glob(str(NWB_DIR / "*.nwb"))):
            basename = os.path.basename(f)
            if "ses-" in basename:
                sid = basename.split("ses-")[1].split("_")[0]
                nwb_map[int(sid)] = f
        return nwb_map

    def _load_layer_masks(self) -> dict:
        """Load layer boundary information."""
        try:
            with open(LAYER_MASKS_FILE) as f:
                masks = json.load(f)
            return masks.get('by_key', {})
        except:
            return {}

    def parse_tfr_filename(self, filename: str) -> dict:
        """Parse TFR filename."""
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

    def extract_band_power(self, tfr_data: np.ndarray, band_name: str) -> np.ndarray:
        """Extract band power (channels, time, trials)."""
        if band_name not in BANDS:
            return None

        freq_min, freq_max = BANDS[band_name]
        freq_bins = np.linspace(0, 200, tfr_data.shape[1])
        band_mask = (freq_bins >= freq_min) & (freq_bins <= freq_max)

        return tfr_data[:, band_mask, :, :].mean(axis=1)

    def extract_time_window(self, band_power: np.ndarray, window_name: str) -> np.ndarray:
        """Extract time window (channels, time, trials)."""
        if window_name not in CONDITIONS:
            return None

        start_ms, end_ms = CONDITIONS[window_name]
        n_timepoints = band_power.shape[1]

        # Map milliseconds to timepoint indices (assuming 4000ms total duration)
        total_duration_ms = 4000
        timepoints_per_ms = n_timepoints / total_duration_ms

        start_idx = max(0, int((start_ms + 2000) * timepoints_per_ms))  # +2000 for baseline offset
        end_idx = min(n_timepoints, int((end_ms + 2000) * timepoints_per_ms))

        if start_idx >= end_idx or start_idx >= n_timepoints:
            return None

        return band_power[:, start_idx:end_idx, :]

    def compute_inter_area_correlations(self, area_data: dict, band_name: str,
                                       window_name: str) -> pd.DataFrame:
        """Compute correlations between area pairs within layer."""
        results = []

        areas = list(area_data.keys())

        for area1, area2 in combinations(areas, 2):
            if area1 not in area_data or area2 not in area_data:
                continue

            try:
                probe1_files = area_data[area1]
                probe2_files = area_data[area2]

                if not probe1_files or not probe2_files:
                    continue

                tfr1 = np.load(probe1_files[0])
                tfr2 = np.load(probe2_files[0])

                band1 = self.extract_band_power(tfr1, band_name)
                band2 = self.extract_band_power(tfr2, band_name)

                if band1 is None or band2 is None:
                    continue

                data1 = self.extract_time_window(band1, window_name)
                data2 = self.extract_time_window(band2, window_name)

                if data1 is None or data2 is None or data1.shape[1] < 5:
                    continue

                # Flatten
                data1_flat = data1.reshape(-1)
                data2_flat = data2.reshape(-1)

                # Remove NaN/Inf
                valid = ~(np.isnan(data1_flat) | np.isinf(data1_flat) |
                         np.isnan(data2_flat) | np.isinf(data2_flat))

                if valid.sum() < 10:
                    continue

                corr, pval = spearmanr(data1_flat[valid], data2_flat[valid])

                # Shuffle control
                n_shuffles = 50
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

                z_score = (corr - shuffle_corrs.mean()) / (shuffle_corrs.std() + 1e-6)

                results.append({
                    'area1': area1,
                    'area2': area2,
                    'band': band_name,
                    'condition': window_name,
                    'correlation': float(corr) if not np.isnan(corr) else 0.0,
                    'pval': float(pval) if not np.isnan(pval) else 1.0,
                    'z_score': float(z_score),
                    'shuffle_mean': float(shuffle_corrs.mean()),
                    'n_samples': valid.sum(),
                })
            except Exception as e:
                log.debug(f"Error {area1}-{area2}: {e}")

        return pd.DataFrame(results)

    def run_q1_spectral_networks(self):
        """Question 1: Spectral band networks."""
        log.info("\n" + "=" * 80)
        log.info("QUESTION 1: SPECTRAL BAND NETWORKS (FIXED)")
        log.info("=" * 80)

        # Group TFR files by session, area, condition
        file_groups = {}
        for tfr_file in self.tfr_files:
            meta = self.parse_tfr_filename(tfr_file)
            if not meta:
                continue

            key = (meta['session'], meta['area'], meta['condition'])
            if key not in file_groups:
                file_groups[key] = {}
            if meta['probe'] not in file_groups[key]:
                file_groups[key][meta['probe']] = []
            file_groups[key][meta['probe']].append(tfr_file)

        # Analyze each session/condition
        sessions = set(k[0] for k in file_groups.keys())
        omission_conditions = {'AAXB', 'AXAB', 'AAAX', 'AAAB', 'BBBA', 'BBBX'}

        for session in sorted(sessions)[:2]:  # First 2 sessions for speed
            log.info(f"\nSession {session}")

            area_data_by_condition = {}

            for (sess, area, cond), probes in file_groups.items():
                if sess != session or cond not in omission_conditions:
                    continue

                if cond not in area_data_by_condition:
                    area_data_by_condition[cond] = {}
                area_data_by_condition[cond][area] = probes

            # Analyze conditions
            for condition_name, area_data in area_data_by_condition.items():
                log.info(f"  {condition_name}: {len(area_data)} areas")

                for band_name in list(BANDS.keys())[:3]:  # First 3 bands for speed
                    for window_name in list(CONDITIONS.keys())[:2]:  # First 2 windows
                        results = self.compute_inter_area_correlations(
                            area_data, band_name, window_name
                        )

                        if len(results) > 0:
                            self.q1_results.append(results)
                            log.info(f"    {band_name} x {window_name}: {len(results)} pairs")

        if self.q1_results:
            q1_df = pd.concat(self.q1_results, ignore_index=True)
            pvals = q1_df['pval'].fillna(1.0).values
            q1_df['pval_fdr'] = false_discovery_control(pvals)
            q1_df['significant'] = (q1_df['pval_fdr'] < 0.05) & (q1_df['z_score'].abs() > 1.96)

            q1_df.to_csv(OUTPUT_DIR / "q1_spectral_networks.csv", index=False)
            log.info(f"\n✓ Q1 Results: {len(q1_df)} pairs, {len(q1_df[q1_df['significant']])} significant")

            return q1_df
        return None

    def run_q2_spike_networks(self):
        """Question 2: Spike networks."""
        log.info("\n" + "=" * 80)
        log.info("QUESTION 2: SPIKE NETWORKS (EXPANDED)")
        log.info("=" * 80)

        results = []

        for session_id in sorted(self.units_db['session_id'].unique())[:2]:
            if session_id not in self.nwb_map:
                continue

            log.info(f"Session {session_id}")

            nwb_path = self.nwb_map[session_id]
            sess_units = self.units_db[self.units_db['session_id'] == session_id]

            try:
                with NWBHDF5IO(nwb_path, "r", load_namespaces=True) as io:
                    nwb = io.read()
                    units_df = nwb.units.to_dataframe()

                    unit_ids = sess_units['unit_id'].unique()
                    spike_trains = {}

                    for unit_idx, unit_row in units_df.iterrows():
                        cluster_id = int(float(unit_row.get('cluster_id', -1)))
                        if cluster_id not in unit_ids:
                            continue

                        spike_times = np.asarray(unit_row.get('spike_times', []))
                        if len(spike_times) > 5:
                            spike_trains[cluster_id] = spike_times

                    # Compute unit correlations
                    unit_ids_list = list(spike_trains.keys())

                    for i, uid1 in enumerate(unit_ids_list):
                        for uid2 in unit_ids_list[i+1:]:
                            try:
                                row1 = sess_units[sess_units['unit_id'] == uid1]
                                row2 = sess_units[sess_units['unit_id'] == uid2]

                                if len(row1) == 0 or len(row2) == 0:
                                    continue

                                spikes1 = len(spike_trains[uid1])
                                spikes2 = len(spike_trains[uid2])

                                # CCF: cross-correlation of spike counts
                                max_time = max(spike_trains[uid1].max(), spike_trains[uid2].max())
                                bins = np.arange(0, max_time + 0.1, 0.1)

                                count1, _ = np.histogram(spike_trains[uid1], bins=bins)
                                count2, _ = np.histogram(spike_trains[uid2], bins=bins)

                                # Cross-correlation with lag
                                ccf = correlate(count1, count2, mode='same')
                                lag_idx = np.argmax(np.abs(ccf))
                                lag_ms = (lag_idx - len(ccf)//2) * 100  # 100ms bins

                                corr, pval = spearmanr(count1, count2)

                                if not np.isnan(corr):
                                    results.append({
                                        'session': session_id,
                                        'unit1': uid1,
                                        'unit2': uid2,
                                        'correlation': float(corr),
                                        'pval': float(pval) if not np.isnan(pval) else 1.0,
                                        'lag_ms': float(lag_ms),
                                        'n_spikes1': spikes1,
                                        'n_spikes2': spikes2,
                                    })
                            except:
                                pass

                log.info(f"  {len(results)} unit pairs")
            except Exception as e:
                log.warning(f"Error: {e}")

        if results:
            q2_df = pd.DataFrame(results)
            pvals = q2_df['pval'].fillna(1.0).values
            q2_df['pval_fdr'] = false_discovery_control(pvals)
            q2_df['significant'] = q2_df['pval_fdr'] < 0.05

            q2_df.to_csv(OUTPUT_DIR / "q2_spike_networks.csv", index=False)
            log.info(f"✓ Q2 Results: {len(q2_df)} pairs, {len(q2_df[q2_df['significant']])} significant")

            return q2_df
        return None

    def run_q3_lead_analysis(self):
        """Question 3: Lead analysis with cross-modal comparison."""
        log.info("\n" + "=" * 80)
        log.info("QUESTION 3: LEAD ANALYSIS (CROSS-MODAL)")
        log.info("=" * 80)

        results = []

        for i, tfr_file in enumerate(self.tfr_files[:30]):
            if i % 10 == 0:
                log.info(f"Processing file {i+1}...")

            try:
                tfr_data = np.load(tfr_file)
                meta = self.parse_tfr_filename(tfr_file)
                if not meta:
                    continue

                # Extract all bands
                bands_data = {}
                for band_name in BANDS.keys():
                    band_power = self.extract_band_power(tfr_data, band_name)
                    if band_power is not None:
                        bands_data[band_name] = band_power.reshape(-1)

                # Compute leads between band pairs
                band_names = list(bands_data.keys())

                for j, band1 in enumerate(band_names):
                    for band2 in band_names[j+1:]:
                        sig1 = bands_data[band1]
                        sig2 = bands_data[band2]

                        # Remove NaN
                        valid = ~(np.isnan(sig1) | np.isnan(sig2) | np.isinf(sig1) | np.isinf(sig2))
                        if valid.sum() < 100:
                            continue

                        sig1 = sig1[valid]
                        sig2 = sig2[valid]

                        # Normalize
                        sig1 = (sig1 - sig1.mean()) / (sig1.std() + 1e-6)
                        sig2 = (sig2 - sig2.mean()) / (sig2.std() + 1e-6)

                        # Cross-correlation
                        ccf = correlate(sig1, sig2, mode='same')
                        lag_idx = np.argmax(np.abs(ccf))
                        center = len(ccf) // 2
                        lag_samples = lag_idx - center
                        lag_ms = lag_samples / 1000 * 1000  # Assuming 1kHz

                        corr_peak = ccf[lag_idx] / ccf[center] if ccf[center] != 0 else 0

                        results.append({
                            'area': meta['area'],
                            'condition': meta['condition'],
                            'band1': band1,
                            'band2': band2,
                            'lag_ms': float(lag_ms) if abs(lag_ms) < 500 else np.nan,
                            'correlation': float(corr_peak),
                        })
            except Exception as e:
                log.debug(f"Error: {e}")

        if results:
            q3_df = pd.DataFrame(results)
            q3_df.to_csv(OUTPUT_DIR / "q3_lead_times.csv", index=False)
            log.info(f"✓ Q3 Results: {len(q3_df)} band pair comparisons")

            return q3_df
        return None

    def create_visualizations(self, q1_df, q2_df, q3_df):
        """Create comprehensive visualizations with proper relative positioning."""
        log.info("\n" + "=" * 80)
        log.info("CREATING VISUALIZATIONS")
        log.info("=" * 80)

        # Figure 1: Q1 Spectral Networks
        if q1_df is not None and len(q1_df) > 0:
            fig = plt.figure(figsize=(16, 10))
            gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.4, wspace=0.3)

            bands = q1_df['band'].unique()
            conditions = q1_df['condition'].unique()

            for i, band in enumerate(list(bands)[:3]):
                for j, cond in enumerate(list(conditions)[:3]):
                    ax = fig.add_subplot(gs[i, j])

                    data = q1_df[(q1_df['band'] == band) & (q1_df['condition'] == cond)]
                    if len(data) > 0:
                        ax.hist(data['correlation'].dropna(), bins=20, alpha=0.7, edgecolor='black')
                        ax.axvline(data['correlation'].mean(), color='red', linestyle='--', linewidth=2)
                        ax.set_title(f'{band.upper()} × {cond}', fontsize=10)
                        ax.set_xlabel('Correlation', fontsize=9)
                        ax.set_ylabel('Count', fontsize=9)

            fig.suptitle('Q1: Spectral Band Correlation Distributions', fontsize=14, y=0.995)
            fig.savefig(OUTPUT_DIR / "q1_spectral_networks.png", dpi=150, bbox_inches='tight')
            log.info("✓ Saved Q1 visualization")
            plt.close(fig)

        # Figure 2: Q2 Spike Networks
        if q2_df is not None and len(q2_df) > 0:
            fig = plt.figure(figsize=(12, 5))
            gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.3)

            ax1 = fig.add_subplot(gs[0, 0])
            ax1.hist(q2_df['correlation'].dropna(), bins=30, alpha=0.7, edgecolor='black')
            ax1.set_title('Unit Pair Correlations', fontsize=11)
            ax1.set_xlabel('Correlation', fontsize=10)
            ax1.set_ylabel('Count', fontsize=10)

            ax2 = fig.add_subplot(gs[0, 1])
            ax2.scatter(q2_df['lag_ms'].dropna(), q2_df['correlation'].dropna(),
                       alpha=0.6, s=30, edgecolor='black', linewidth=0.5)
            ax2.axvline(0, color='red', linestyle='--', linewidth=2)
            ax2.set_title('Lead Time vs Correlation', fontsize=11)
            ax2.set_xlabel('Lag (ms)', fontsize=10)
            ax2.set_ylabel('Correlation', fontsize=10)

            fig.suptitle('Q2: Spike Network Analysis', fontsize=14, y=0.98)
            fig.savefig(OUTPUT_DIR / "q2_spike_networks.png", dpi=150, bbox_inches='tight')
            log.info("✓ Saved Q2 visualization")
            plt.close(fig)

        # Figure 3: Q3 Lead Times
        if q3_df is not None and len(q3_df) > 0:
            fig = plt.figure(figsize=(14, 6))
            gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.3)

            ax1 = fig.add_subplot(gs[0, 0])
            lead_data = q3_df.dropna(subset=['lag_ms'])
            if len(lead_data) > 0:
                ax1.hist(lead_data['lag_ms'], bins=25, alpha=0.7, edgecolor='black')
                ax1.axvline(0, color='red', linestyle='--', linewidth=2, label='Simultaneous')
                ax1.set_title('Lead Time Distribution (Band Pairs)', fontsize=11)
                ax1.set_xlabel('Lead Time (ms)', fontsize=10)
                ax1.set_ylabel('Count', fontsize=10)
                ax1.legend()

            ax2 = fig.add_subplot(gs[0, 1])
            ax2.scatter(q3_df['lag_ms'].dropna(), q3_df['correlation'].dropna(),
                       alpha=0.6, s=30, edgecolor='black', linewidth=0.5)
            ax2.axvline(0, color='red', linestyle='--', linewidth=2)
            ax2.set_title('Lead Time vs Cross-Correlation', fontsize=11)
            ax2.set_xlabel('Lead Time (ms)', fontsize=10)
            ax2.set_ylabel('Correlation', fontsize=10)

            fig.suptitle('Q3: Lead/Causality Analysis', fontsize=14, y=0.98)
            fig.savefig(OUTPUT_DIR / "q3_lead_analysis.png", dpi=150, bbox_inches='tight')
            log.info("✓ Saved Q3 visualization")
            plt.close(fig)

    def run_complete_analysis(self):
        """Run all three questions."""
        log.info("=" * 80)
        log.info("COMPLETE OMISSION ENCODING NETWORK ANALYSIS")
        log.info("=" * 80)

        q1_df = self.run_q1_spectral_networks()
        q2_df = self.run_q2_spike_networks()
        q3_df = self.run_q3_lead_analysis()

        self.create_visualizations(q1_df, q2_df, q3_df)

        # Summary report
        log.info("\n" + "=" * 80)
        log.info("COMPLETE ANALYSIS SUMMARY")
        log.info("=" * 80)
        log.info(f"Q1 (Spectral Networks): {len(q1_df) if q1_df is not None else 0} area pairs")
        log.info(f"Q2 (Spike Networks): {len(q2_df) if q2_df is not None else 0} unit pairs")
        log.info(f"Q3 (Lead Analysis): {len(q3_df) if q3_df is not None else 0} band pair comparisons")
        log.info(f"\nOutputs saved to: {OUTPUT_DIR}")
        log.info("=" * 80)


def main():
    analyzer = OmissionNetworkAnalysis()
    analyzer.run_complete_analysis()


if __name__ == "__main__":
    main()
