#!/usr/bin/env python3
"""
Build comprehensive grand table from NWB files.

Extracts ALL units from all NWB files (no filtering).
Includes: unit_id, session_id, cluster_id, area, layer, quality, SNR,
firing_rate, waveform metrics, and spike statistics.

Output: outputs/publication_figures/comprehensive_grand_database_all_units.csv
"""

from __future__ import annotations

import glob
import os
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO

ROOT = Path("D:/workspace/omission")
NWB_DIR = "D:/analysis/nwb"
OUTPUT_DIR = ROOT / "outputs/publication_figures"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def get_nwb_map(nwb_dir: str = NWB_DIR) -> dict[str, str]:
    """Return {session_id: path} for all NWB files."""
    m = {}
    for f in sorted(glob.glob(f"{nwb_dir}/*.nwb")):
        bn = os.path.basename(f)
        sid = bn.split("ses-")[1].split("_")[0] if "ses-" in bn else bn.split("_")[0]
        m[sid] = f
    return m


def extract_all_units(nwb_path: str, session_id: int | str) -> pd.DataFrame:
    """
    Extract all units from a single NWB file.
    Returns DataFrame with all unit metadata.
    """
    rows = []

    try:
        with NWBHDF5IO(nwb_path, "r", load_namespaces=True) as io:
            nwb = io.read()

            # Get units dataframe
            units_df = nwb.units.to_dataframe()

            log.info(f"Session {session_id}: {len(units_df)} units")

            # Get electrode mapping for area/layer info
            try:
                electrodes_df = nwb.electrodes.to_dataframe()
            except:
                electrodes_df = None
                log.warning(f"  Could not read electrodes table")

            # Extract unit by unit
            for idx, row in units_df.iterrows():
                unit_data = {
                    'session_id': int(session_id),
                    'unit_index': int(idx),
                    'unit_id': int(pd.to_numeric(row.get('cluster_id', np.nan), errors='coerce')),
                    'cluster_id': str(row.get('cluster_id', '')),
                }

                # Quality metrics from units table
                for col in ['quality', 'snr', 'firing_rate', 'amplitude', 'amplitude_cutoff',
                           'presence_ratio', 'isolation_distance', 'silhouette_score',
                           'nn_hit_rate', 'nn_miss_rate', 'isi_violations', 'isi_cv',
                           'spread', 'd_prime', 'max_drift', 'cumulative_drift']:
                    if col in row.index:
                        val = row[col]
                        # Handle string values from NWB
                        if isinstance(val, str):
                            val = pd.to_numeric(val, errors='coerce')
                        unit_data[col] = val
                    else:
                        unit_data[col] = np.nan

                # Waveform metrics
                for col in ['waveform_duration', 'waveform_halfwidth', 'PT_ratio',
                           'repolarization_slope', 'recovery_slope', 'velocity_above', 'velocity_below']:
                    if col in row.index:
                        val = row[col]
                        if isinstance(val, str):
                            val = pd.to_numeric(val, errors='coerce')
                        unit_data[col] = val
                    else:
                        unit_data[col] = np.nan

                # Peak channel
                if 'peak_channel_id' in row.index:
                    unit_data['peak_channel_id'] = int(pd.to_numeric(row['peak_channel_id'], errors='coerce'))
                else:
                    unit_data['peak_channel_id'] = np.nan

                # Area and layer from electrodes if available
                if electrodes_df is not None and 'peak_channel_id' in row.index:
                    try:
                        peak_ch = int(pd.to_numeric(row['peak_channel_id'], errors='coerce'))
                        if peak_ch in electrodes_df.index:
                            location = electrodes_df.loc[peak_ch, 'location']
                            unit_data['area_from_electrodes'] = location
                            unit_data['peak_channel_location'] = location
                    except:
                        unit_data['area_from_electrodes'] = np.nan
                        unit_data['peak_channel_location'] = np.nan
                else:
                    unit_data['area_from_electrodes'] = np.nan
                    unit_data['peak_channel_location'] = np.nan

                # Spike times length as proxy for unit activity
                if 'spike_times' in row.index:
                    spike_times = row['spike_times']
                    if spike_times is not None and hasattr(spike_times, '__len__'):
                        unit_data['n_spikes'] = len(spike_times)
                    else:
                        unit_data['n_spikes'] = 0
                else:
                    unit_data['n_spikes'] = 0

                rows.append(unit_data)

    except Exception as e:
        log.error(f"Error processing {nwb_path}: {e}")
        import traceback
        traceback.print_exc()

    return pd.DataFrame(rows)


def main():
    log.info("=" * 80)
    log.info("Comprehensive Grand Database Builder")
    log.info("=" * 80)

    nwb_map = get_nwb_map()
    log.info(f"Found {len(nwb_map)} NWB files\n")

    # Extract from all sessions
    all_rows = []
    total_units = 0

    for session_id in sorted(nwb_map.keys()):
        nwb_path = nwb_map[session_id]
        log.info(f"Processing session {session_id}...")

        sess_df = extract_all_units(nwb_path, session_id)
        all_rows.append(sess_df)
        total_units += len(sess_df)

    # Combine all sessions
    log.info(f"\nCombining {len(all_rows)} sessions...")
    comprehensive_df = pd.concat(all_rows, ignore_index=True)

    log.info(f"\nComprehensive database:")
    log.info(f"  Total units: {len(comprehensive_df)}")
    log.info(f"  Sessions: {comprehensive_df['session_id'].nunique()}")

    # Quality analysis
    log.info(f"\n=== Quality Distribution ===")

    quality_col = 'quality'
    if quality_col in comprehensive_df.columns:
        quality_counts = comprehensive_df[quality_col].value_counts()
        log.info(f"\nQuality values:")
        for val, count in quality_counts.items():
            log.info(f"  {val}: {count} units ({count/len(comprehensive_df)*100:.1f}%)")

        # Check for quality == 1.0 (or True, or '1.0')
        quality_1_count = (
            (comprehensive_df[quality_col] == 1.0) |
            (comprehensive_df[quality_col] == '1.0') |
            (comprehensive_df[quality_col] == True)
        ).sum()
        log.info(f"\n✓ Quality == 1.0 (good): {quality_1_count} units")

    # SNR analysis
    snr_col = 'snr'
    if snr_col in comprehensive_df.columns:
        snr_series = pd.to_numeric(comprehensive_df[snr_col], errors='coerce')
        snr_ge_05 = (snr_series >= 0.5).sum()
        log.info(f"\n✓ SNR >= 0.5: {snr_ge_05} units")

        # Union
        if quality_col in comprehensive_df.columns:
            quality_good = (
                (comprehensive_df[quality_col] == 1.0) |
                (comprehensive_df[quality_col] == '1.0') |
                (comprehensive_df[quality_col] == True)
            )
            snr_good = snr_series >= 0.5
            union = (quality_good | snr_good).sum()
            log.info(f"✓ Quality==1.0 OR SNR>=0.5: {union} units")

    # Firing rate analysis
    if 'firing_rate' in comprehensive_df.columns:
        fr_series = pd.to_numeric(comprehensive_df['firing_rate'], errors='coerce')
        log.info(f"\nFiring rate stats:")
        log.info(f"  Mean: {fr_series.mean():.2f} Hz")
        log.info(f"  Median: {fr_series.median():.2f} Hz")
        log.info(f"  Min: {fr_series.min():.4f} Hz")
        log.info(f"  Max: {fr_series.max():.2f} Hz")

    # Save
    output_path = OUTPUT_DIR / "comprehensive_grand_database_all_units.csv"
    comprehensive_df.to_csv(output_path, index=False)
    log.info(f"\n✓ Saved: {output_path}")

    log.info(f"\nColumns in comprehensive database:")
    for i, col in enumerate(comprehensive_df.columns, 1):
        print(f"  {i:2d}. {col}")

    log.info("\n" + "=" * 80)
    log.info("Done!")
    log.info("=" * 80)


if __name__ == "__main__":
    main()
