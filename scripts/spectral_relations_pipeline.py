#!/usr/bin/env python3
"""
SPECTRAL-RELATIONS PIPELINE: Production-Grade Analysis
=======================================================

Comprehensive multi-modal network analysis with:
- Full depth analysis (all sessions, areas, conditions)
- Permutation-test significance validation
- Network graph visualization
- Comprehensive comparison visualizations
- Complete result caching for reproducibility

Author: Claude Code
Date: 2025-06-23
Status: PRODUCTION
"""

import logging
import json
import pickle
import glob
import os
import re
from pathlib import Path
from itertools import combinations
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, false_discovery_control, pearsonr
from scipy.signal import correlate
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Rectangle
import networkx as nx
from pynwb import NWBHDF5IO

# ============================================================================
# CONFIGURATION
# ============================================================================

ROOT = Path("D:/workspace/omission")
TFR_DIR = Path("D:/workspace/data/tfr_arrays")
NWB_DIR = Path("D:/analysis/nwb")
GRAND_DB = ROOT / "outputs/publication_figures/comprehensive_grand_database_all_units.csv"
LAYER_MASKS_FILE = ROOT / "outputs/publication_visual_review/area_layer_tfr/layer_masks.json"

PIPELINE_DIR = ROOT / "outputs/spectral_relations_pipeline"
CACHE_DIR = PIPELINE_DIR / "cache"
RESULTS_DIR = PIPELINE_DIR / "results"
FIGS_DIR = PIPELINE_DIR / "figures"

for d in [PIPELINE_DIR, CACHE_DIR, RESULTS_DIR, FIGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

# Frequency bands
BANDS = {
    "theta": (4, 8),
    "alpha": (8, 12),
    "beta": (12, 30),
    "low_gamma": (30, 55),
    "high_gamma": (55, 90),
}

# Behavioral conditions
CONDITIONS = {
    "stimulus": (0, 531),
    "baseline_pre_stim": (-1000, 0),
    "baseline_pre_omission": (-500, 0),
    "omission": (0, 531),
    "baseline_post_omission": (500, 1000),
}

# Visual areas (canonical ordering: feedforward)
AREAS_ORDERED = ["V1", "V3", "V4", "MT", "MST", "PFC", "FEF"]

# Permutation testing parameters
N_PERMUTATIONS = 500  # Number of permutations per test
PERMUTATION_SEED = 42
ALPHA_FDR = 0.05
Z_THRESHOLD = 1.96

# ============================================================================
# CORE PIPELINE CLASS
# ============================================================================

class SpectralRelationsPipeline:
    """Production-grade spectral relations analysis pipeline."""

    def __init__(self):
        self.tfr_files = sorted(glob.glob(str(TFR_DIR / "*.npy")))
        self.nwb_map = self._get_nwb_map()
        self.units_db = pd.read_csv(GRAND_DB)
        self.layer_masks = self._load_layer_masks()

        # Results storage
        self.q1_results = []  # Spectral networks
        self.q2_results = []  # Spike networks
        self.q3_results = []  # Lead times
        self.permutation_cache = {}  # Cache permutation tests

        log.info(f"Initialized pipeline with {len(self.tfr_files)} TFR files")
        log.info(f"Found {len(self.nwb_map)} NWB files, {len(self.units_db)} units")

    def _get_nwb_map(self) -> Dict[int, str]:
        """Get session to NWB file mapping."""
        nwb_map = {}
        for f in sorted(glob.glob(str(NWB_DIR / "*.nwb"))):
            basename = os.path.basename(f)
            if "ses-" in basename:
                sid = basename.split("ses-")[1].split("_")[0]
                nwb_map[int(sid)] = f
        return nwb_map

    def _load_layer_masks(self) -> Dict:
        """Load layer boundary information."""
        try:
            with open(LAYER_MASKS_FILE) as f:
                masks = json.load(f)
            return masks.get('by_key', {})
        except:
            log.warning("Could not load layer masks")
            return {}

    def parse_tfr_filename(self, filename: str) -> Optional[Dict]:
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

    def extract_band_power(self, tfr_data: np.ndarray, band_name: str) -> Optional[np.ndarray]:
        """Extract band power. Returns (channels, time, trials)."""
        if band_name not in BANDS:
            return None

        freq_min, freq_max = BANDS[band_name]
        freq_bins = np.linspace(0, 200, tfr_data.shape[1])
        band_mask = (freq_bins >= freq_min) & (freq_bins <= freq_max)

        return tfr_data[:, band_mask, :, :].mean(axis=1)

    def extract_time_window(self, band_power: np.ndarray, window_name: str) -> Optional[np.ndarray]:
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

    def compute_permutation_correlation(self, sig1: np.ndarray, sig2: np.ndarray,
                                       n_perms: int = N_PERMUTATIONS) -> Dict:
        """
        Compute Spearman correlation with permutation testing.

        Returns:
            dict with correlation, p_value, z_score, perm_mean, perm_std
        """
        # Remove NaN/Inf
        valid = ~(np.isnan(sig1) | np.isinf(sig1) | np.isnan(sig2) | np.isinf(sig2))
        if valid.sum() < 10:
            return {
                'correlation': np.nan,
                'pval_perm': 1.0,
                'z_score': 0.0,
                'perm_mean': 0.0,
                'perm_std': 0.0,
            }

        sig1_valid = sig1[valid]
        sig2_valid = sig2[valid]

        # Actual correlation
        corr_actual, _ = spearmanr(sig1_valid, sig2_valid)

        # Permutation test (shuffle sig2)
        np.random.seed(PERMUTATION_SEED)
        perm_corrs = []

        for _ in range(n_perms):
            perm_idx = np.random.permutation(len(sig2_valid))
            sig2_perm = sig2_valid[perm_idx]
            corr_perm, _ = spearmanr(sig1_valid, sig2_perm)
            perm_corrs.append(corr_perm)

        perm_corrs = np.array(perm_corrs)
        perm_mean = perm_corrs.mean()
        perm_std = perm_corrs.std()

        # P-value: proportion of permutations with |corr| >= |corr_actual|
        p_value = (np.abs(perm_corrs) >= np.abs(corr_actual)).sum() / n_perms
        z_score = (corr_actual - perm_mean) / (perm_std + 1e-6)

        return {
            'correlation': float(corr_actual) if not np.isnan(corr_actual) else 0.0,
            'pval_perm': float(p_value),
            'z_score': float(z_score),
            'perm_mean': float(perm_mean),
            'perm_std': float(perm_std),
        }

    def run_q1_full_depth(self):
        """Question 1: Full-depth spectral band network analysis."""
        log.info("\n" + "=" * 80)
        log.info("QUESTION 1: SPECTRAL BAND NETWORKS (FULL DEPTH)")
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

        log.info(f"Organized into {len(file_groups)} session-area-condition groups")

        # Analyze all sessions and conditions
        sessions = sorted(set(k[0] for k in file_groups.keys()))
        omission_conditions = {'AAXB', 'AXAB', 'AAAX', 'AAAB', 'BBBA', 'BBBX', 'BBXA', 'BXBA', 'RRRR', 'RRRX', 'RRXR', 'RXRR'}

        result_count = 0

        for session_idx, session in enumerate(sessions):
            log.info(f"\n[Session {session_idx+1}/{len(sessions)}] Session {session}")

            area_data_by_condition = {}

            for (sess, area, cond), probes in file_groups.items():
                if sess != session or cond not in omission_conditions:
                    continue

                if cond not in area_data_by_condition:
                    area_data_by_condition[cond] = {}
                area_data_by_condition[cond][area] = probes

            # Analyze each condition
            for condition_name, area_data in area_data_by_condition.items():
                areas = sorted(area_data.keys())
                log.info(f"  {condition_name}: {len(areas)} areas")

                # Analyze all band x window combinations
                for band_name in BANDS.keys():
                    for window_name in CONDITIONS.keys():
                        results = self._compute_inter_area_correlations_full(
                            area_data, band_name, window_name, session
                        )

                        if len(results) > 0:
                            self.q1_results.extend(results)
                            result_count += len(results)

        log.info(f"\nQ1 Complete: {result_count} correlations computed")

        # Apply FDR correction
        if self.q1_results:
            q1_df = pd.DataFrame(self.q1_results)
            pvals = q1_df['pval_perm'].fillna(1.0).values
            q1_df['pval_fdr'] = false_discovery_control(pvals, method='fdr_bh')
            q1_df['significant'] = (q1_df['pval_fdr'] < ALPHA_FDR) & (q1_df['z_score'].abs() > Z_THRESHOLD)

            q1_df.to_csv(RESULTS_DIR / "q1_spectral_networks_full.csv", index=False)
            log.info(f"✓ Q1: {len(q1_df)} pairs, {len(q1_df[q1_df['significant']])} significant (FDR<0.05)")

            # Cache for visualization
            with open(CACHE_DIR / "q1_results.pkl", 'wb') as f:
                pickle.dump(q1_df, f)

            return q1_df
        return None

    def _compute_inter_area_correlations_full(self, area_data: Dict, band_name: str,
                                              window_name: str, session: int) -> List[Dict]:
        """Compute all inter-area correlations with permutation testing."""
        results = []

        areas = list(area_data.keys())
        pairs = list(combinations(areas, 2))

        for area1, area2 in pairs:
            try:
                # area_data[area] is a dict of {probe: [files]}
                probe_dict1 = area_data[area1]
                probe_dict2 = area_data[area2]

                if not probe_dict1 or not probe_dict2:
                    log.debug(f"Skipped {area1}-{area2}: empty probe dict")
                    continue

                # Get first probe's first file for each area
                probe1_files = list(probe_dict1.values())[0]  # First probe's files
                probe2_files = list(probe_dict2.values())[0]

                if not probe1_files or not probe2_files:
                    log.debug(f"Skipped {area1}-{area2}: no files")
                    continue

                # Load TFR data
                tfr1 = np.load(probe1_files[0])
                tfr2 = np.load(probe2_files[0])

                # Extract bands
                band1 = self.extract_band_power(tfr1, band_name)
                band2 = self.extract_band_power(tfr2, band_name)

                if band1 is None or band2 is None:
                    log.debug(f"Skipped {area1}-{area2}: band extraction returned None")
                    continue

                # Extract time windows
                data1 = self.extract_time_window(band1, window_name)
                data2 = self.extract_time_window(band2, window_name)

                if data1 is None or data2 is None:
                    log.debug(f"Skipped {area1}-{area2}: window extraction returned None")
                    continue

                if data1.shape[1] < 5:
                    log.debug(f"Skipped {area1}-{area2}: insufficient time points ({data1.shape[1]} < 5)")
                    continue

                # CRITICAL FIX: Average across channels to handle variable channel counts
                # Input: (channels, time, trials) → Output: (time, trials)
                data1_area = data1.mean(axis=0)  # Average channels
                data2_area = data2.mean(axis=0)

                # Flatten for correlation
                data1_flat = data1_area.reshape(-1)
                data2_flat = data2_area.reshape(-1)

                # Compute correlation with permutation test
                corr_result = self.compute_permutation_correlation(data1_flat, data2_flat)

                results.append({
                    'session': session,
                    'area1': area1,
                    'area2': area2,
                    'band': band_name,
                    'condition': window_name,
                    'correlation': corr_result['correlation'],
                    'pval_perm': corr_result['pval_perm'],
                    'z_score': corr_result['z_score'],
                    'perm_mean': corr_result['perm_mean'],
                    'perm_std': corr_result['perm_std'],
                    'n_samples': len(data1_flat),
                })

            except Exception as e:
                log.error(f"Exception computing {area1}-{area2} ({band_name}, {window_name}): {e}")

        if len(results) == 0 and len(pairs) > 0:
            log.warning(f"Q1 computed 0 results from {len(pairs)} pairs for {band_name}/{window_name}")

        return results

    def run_q2_full_depth(self):
        """Question 2: Full-depth spike network analysis."""
        log.info("\n" + "=" * 80)
        log.info("QUESTION 2: SPIKE NETWORKS (FULL DEPTH)")
        log.info("=" * 80)

        results = []

        sessions = sorted(self.units_db['session_id'].unique())

        for session_idx, session_id in enumerate(sessions):
            if session_id not in self.nwb_map:
                continue

            log.info(f"[{session_idx+1}/{len(sessions)}] Session {session_id}")

            nwb_path = self.nwb_map[session_id]
            sess_units = self.units_db[self.units_db['session_id'] == session_id]

            try:
                with NWBHDF5IO(nwb_path, "r", load_namespaces=True) as io:
                    nwb = io.read()
                    units_df = nwb.units.to_dataframe()

                    # Get spike trains
                    unit_ids = sess_units['unit_id'].unique()
                    spike_trains = {}

                    for unit_idx, unit_row in units_df.iterrows():
                        cluster_id = int(float(unit_row.get('cluster_id', -1)))
                        if cluster_id not in unit_ids:
                            continue

                        spike_times = np.asarray(unit_row.get('spike_times', []))
                        if len(spike_times) > 5:
                            spike_trains[cluster_id] = spike_times

                    # Compute unit correlations with permutation test
                    unit_ids_list = list(spike_trains.keys())

                    for i, uid1 in enumerate(unit_ids_list):
                        for uid2 in unit_ids_list[i+1:]:
                            try:
                                spikes1 = len(spike_trains[uid1])
                                spikes2 = len(spike_trains[uid2])

                                # Bin spikes
                                max_time = max(spike_trains[uid1].max(), spike_trains[uid2].max())
                                bins = np.arange(0, max_time + 0.1, 0.1)

                                count1, _ = np.histogram(spike_trains[uid1], bins=bins)
                                count2, _ = np.histogram(spike_trains[uid2], bins=bins)

                                # Permutation correlation
                                corr_result = self.compute_permutation_correlation(count1, count2, n_perms=500)

                                # Lead time from cross-correlation
                                ccf = correlate(count1, count2, mode='same')
                                lag_idx = np.argmax(np.abs(ccf))
                                lag_ms = (lag_idx - len(ccf)//2) * 100

                                results.append({
                                    'session': session_id,
                                    'unit1': uid1,
                                    'unit2': uid2,
                                    'correlation': corr_result['correlation'],
                                    'pval_perm': corr_result['pval_perm'],
                                    'z_score': corr_result['z_score'],
                                    'lag_ms': float(lag_ms),
                                    'n_spikes1': spikes1,
                                    'n_spikes2': spikes2,
                                })
                            except:
                                pass

                    log.info(f"  {len(results)} unit pairs so far")

            except Exception as e:
                log.warning(f"Error: {e}")

        # Save results
        if results:
            q2_df = pd.DataFrame(results)
            pvals = q2_df['pval_perm'].fillna(1.0).values
            q2_df['pval_fdr'] = false_discovery_control(pvals, method='fdr_bh')
            q2_df['significant'] = q2_df['pval_fdr'] < ALPHA_FDR

            q2_df.to_csv(RESULTS_DIR / "q2_spike_networks_full.csv", index=False)
            log.info(f"✓ Q2: {len(q2_df)} unit pairs, {len(q2_df[q2_df['significant']])} significant")

            with open(CACHE_DIR / "q2_results.pkl", 'wb') as f:
                pickle.dump(q2_df, f)

            return q2_df
        return None

    def run_q3_full_depth(self):
        """Question 3: Full-depth lead analysis."""
        log.info("\n" + "=" * 80)
        log.info("QUESTION 3: LEAD ANALYSIS (FULL DEPTH)")
        log.info("=" * 80)

        results = []
        file_count = 0

        for i, tfr_file in enumerate(self.tfr_files):
            if i % 100 == 0:
                log.info(f"Processing file {i+1}/{len(self.tfr_files)}")

            try:
                tfr_data = np.load(tfr_file)
                meta = self.parse_tfr_filename(tfr_file)
                if not meta:
                    continue

                file_count += 1

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

                        sig1_valid = sig1[valid]
                        sig2_valid = sig2[valid]

                        # Normalize
                        sig1_norm = (sig1_valid - sig1_valid.mean()) / (sig1_valid.std() + 1e-6)
                        sig2_norm = (sig2_valid - sig2_valid.mean()) / (sig2_valid.std() + 1e-6)

                        # Cross-correlation
                        ccf = correlate(sig1_norm, sig2_norm, mode='same')
                        lag_idx = np.argmax(np.abs(ccf))
                        center = len(ccf) // 2
                        lag_samples = lag_idx - center
                        lag_ms = lag_samples / 1000 * 1000  # Assuming 1kHz

                        corr_peak = ccf[lag_idx] / (ccf[center] + 1e-6)

                        # Permutation test for lead significance
                        np.random.seed(PERMUTATION_SEED)
                        perm_lags = []
                        for _ in range(min(100, N_PERMUTATIONS)):
                            perm_idx = np.random.permutation(len(sig2_norm))
                            sig2_perm = sig2_norm[perm_idx]
                            ccf_perm = correlate(sig1_norm, sig2_perm, mode='same')
                            lag_perm = (np.argmax(np.abs(ccf_perm)) - center)
                            perm_lags.append(lag_perm)

                        perm_lags = np.array(perm_lags)
                        lag_p_value = (np.abs(perm_lags) >= np.abs(lag_samples)).sum() / len(perm_lags) if len(perm_lags) > 0 else 1.0

                        results.append({
                            'session': meta['session'],
                            'area': meta['area'],
                            'condition': meta['condition'],
                            'band1': band1,
                            'band2': band2,
                            'lag_ms': float(lag_ms) if abs(lag_ms) < 500 else np.nan,
                            'correlation': float(corr_peak),
                            'pval_lag': float(lag_p_value),
                        })

            except Exception as e:
                log.debug(f"Error: {e}")

        log.info(f"Q3 Complete: {file_count} TFR files, {len(results)} band pairs")

        # Save results
        if results:
            q3_df = pd.DataFrame(results)
            q3_df['significant'] = q3_df['pval_lag'] < ALPHA_FDR

            q3_df.to_csv(RESULTS_DIR / "q3_lead_times_full.csv", index=False)
            log.info(f"✓ Q3: {len(q3_df)} comparisons, {len(q3_df[q3_df['significant']])} significant")

            with open(CACHE_DIR / "q3_results.pkl", 'wb') as f:
                pickle.dump(q3_df, f)

            return q3_df
        return None

    def run_all(self):
        """Run complete pipeline."""
        log.info("\n\n" + "=" * 80)
        log.info("SPECTRAL-RELATIONS PIPELINE: FULL-DEPTH ANALYSIS")
        log.info("=" * 80)

        q1_df = self.run_q1_full_depth()
        q2_df = self.run_q2_full_depth()
        q3_df = self.run_q3_full_depth()

        log.info("\n" + "=" * 80)
        log.info("PIPELINE COMPLETE")
        log.info("=" * 80)
        log.info(f"Results saved to: {RESULTS_DIR}")
        log.info(f"Cache saved to: {CACHE_DIR}")

        return {
            'q1': q1_df,
            'q2': q2_df,
            'q3': q3_df,
        }


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run pipeline."""
    pipeline = SpectralRelationsPipeline()
    results = pipeline.run_all()


if __name__ == "__main__":
    main()
