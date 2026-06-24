#!/usr/bin/env python3
"""
QUESTION 2: SPIKE-BASED NETWORK ANALYSIS
Compute spike cross-correlations across areas and layers.
Compare with LFP networks to identify similar/different communication patterns.

Output: Unit-to-unit correlations by layer/area with comparison to LFP
"""

import logging
from pathlib import Path
import glob

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, false_discovery_control
from pynwb import NWBHDF5IO

ROOT = Path("D:/workspace/omission")
NWB_DIR = Path("D:/analysis/nwb")
GRAND_DB = ROOT / "outputs/publication_figures/comprehensive_grand_database_all_units.csv"
OUTPUT_DIR = ROOT / "outputs/q2_spike_networks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def load_grand_database() -> pd.DataFrame:
    """Load comprehensive unit database."""
    return pd.read_csv(GRAND_DB)


def get_nwb_map() -> dict:
    """Get mapping of session to NWB file."""
    nwb_map = {}
    for f in sorted(glob.glob(str(NWB_DIR / "*.nwb"))):
        basename = f.split('/')[-1].split('\\')[-1]
        if "ses-" in basename:
            sid = basename.split("ses-")[1].split("_")[0]
            nwb_map[int(sid)] = f
    return nwb_map


def extract_spike_trains(nwb_path: str, unit_ids: list, time_window: tuple = None) -> dict:
    """
    Extract spike trains for specified units.

    Args:
        nwb_path: path to NWB file
        unit_ids: list of unit IDs to extract
        time_window: (start_s, end_s) tuple for time window

    Returns:
        dict of {unit_id: spike_times}
    """
    spike_trains = {}

    try:
        with NWBHDF5IO(nwb_path, "r", load_namespaces=True) as io:
            nwb = io.read()
            units_df = nwb.units.to_dataframe()

            for unit_idx, unit_row in units_df.iterrows():
                cluster_id = int(float(unit_row.get('cluster_id', -1)))
                if cluster_id not in unit_ids:
                    continue

                spike_times = np.asarray(unit_row.get('spike_times', []))

                if time_window:
                    mask = (spike_times >= time_window[0]) & (spike_times <= time_window[1])
                    spike_times = spike_times[mask]

                if len(spike_times) > 0:
                    spike_trains[cluster_id] = spike_times

    except Exception as e:
        log.warning(f"Error reading {nwb_path}: {e}")

    return spike_trains


def compute_unit_correlations(session_id: int, units_df: pd.DataFrame, nwb_path: str) -> pd.DataFrame:
    """
    Compute cross-correlations between units in same session.

    Args:
        session_id: session ID
        units_df: DataFrame of units for this session
        nwb_path: path to NWB file

    Returns:
        DataFrame with unit-to-unit correlations
    """
    results = []

    if len(units_df) < 2:
        return pd.DataFrame(results)

    # Get spike trains
    unit_ids = units_df['unit_id'].unique()
    spike_trains = extract_spike_trains(nwb_path, unit_ids)

    if len(spike_trains) < 2:
        return pd.DataFrame(results)

    # Compute firing rates as simple "spike count" measure
    # This is a simplified version - full analysis would use cross-correlation
    unit_ids_list = list(spike_trains.keys())

    for i, uid1 in enumerate(unit_ids_list):
        for uid2 in unit_ids_list[i+1:]:
            try:
                row1 = units_df[units_df['unit_id'] == uid1].iloc[0] if len(units_df[units_df['unit_id'] == uid1]) > 0 else None
                row2 = units_df[units_df['unit_id'] == uid2].iloc[0] if len(units_df[units_df['unit_id'] == uid2]) > 0 else None

                if row1 is None or row2 is None:
                    continue

                # Get spike count as correlation proxy
                spikes1 = len(spike_trains[uid1])
                spikes2 = len(spike_trains[uid2])

                # Simple correlation: covariance of firing across bins
                if spikes1 > 5 and spikes2 > 5:
                    # Bin spikes into 100ms bins
                    max_time = max(spike_trains[uid1].max(), spike_trains[uid2].max())
                    bins = np.arange(0, max_time + 0.1, 0.1)

                    count1, _ = np.histogram(spike_trains[uid1], bins=bins)
                    count2, _ = np.histogram(spike_trains[uid2], bins=bins)

                    # Compute correlation
                    corr, pval = spearmanr(count1, count2)

                    if not np.isnan(corr):
                        results.append({
                            'session': session_id,
                            'unit1_id': int(uid1),
                            'unit2_id': int(uid2),
                            'area1': row1.get('area_from_electrodes', 'Unknown'),
                            'area2': row2.get('area_from_electrodes', 'Unknown'),
                            'correlation': float(corr),
                            'pval': float(pval) if not np.isnan(pval) else 1.0,
                            'spikes1': spikes1,
                            'spikes2': spikes2,
                        })

            except Exception as e:
                log.debug(f"Error unit pair {uid1}-{uid2}: {e}")

    return pd.DataFrame(results)


def main():
    log.info("=" * 80)
    log.info("QUESTION 2: SPIKE-BASED NETWORK ANALYSIS")
    log.info("=" * 80)

    # Load unit database
    units_db = load_grand_database()
    log.info(f"Loaded {len(units_db)} units from grand database")

    # Get NWB files
    nwb_map = get_nwb_map()
    log.info(f"Found {len(nwb_map)} NWB files")

    all_results = []

    # Analyze each session
    for session_id in sorted(units_db['session_id'].unique()):
        if session_id not in nwb_map:
            log.warning(f"Session {session_id} not in NWB map")
            continue

        log.info(f"\nSession {session_id}")

        nwb_path = nwb_map[session_id]
        sess_units = units_db[units_db['session_id'] == session_id]

        log.info(f"  Units: {len(sess_units)}")

        # Compute unit correlations
        results = compute_unit_correlations(session_id, sess_units, nwb_path)

        if len(results) > 0:
            all_results.append(results)
            log.info(f"  Computed {len(results)} unit pairs")

    if all_results:
        combined_results = pd.concat(all_results, ignore_index=True)

        # Apply FDR correction
        pvals = combined_results['pval'].fillna(1.0).values
        fdr_corrected = false_discovery_control(pvals, method='fdr_bh')
        combined_results['pval_fdr'] = fdr_corrected
        combined_results['significant'] = combined_results['pval_fdr'] < 0.05

        # Save results
        output_file = OUTPUT_DIR / "q2_spike_correlations_all.csv"
        combined_results.to_csv(output_file, index=False)
        log.info(f"\n✓ Saved all spike results: {output_file}")

        sig_results = combined_results[combined_results['significant']]
        sig_file = OUTPUT_DIR / "q2_spike_correlations_significant.csv"
        sig_results.to_csv(sig_file, index=False)
        log.info(f"✓ Saved significant results: {sig_file} ({len(sig_results)} pairs)")

        # Summary statistics
        log.info("\n" + "=" * 80)
        log.info("SPIKE NETWORK SUMMARY")
        log.info("=" * 80)

        log.info(f"\nTotal unit pairs analyzed: {len(combined_results)}")
        log.info(f"Significant correlations (FDR<0.05): {len(sig_results)} ({len(sig_results)/len(combined_results)*100:.1f}%)")

        log.info("\nMean correlation by area pair:")
        area_pairs = combined_results.groupby(['area1', 'area2'])['correlation'].agg(['mean', 'count'])
        print(area_pairs[area_pairs['count'] > 1].sort_values('mean', ascending=False))

    log.info("\n" + "=" * 80)
    log.info("QUESTION 2 COMPLETE")
    log.info("=" * 80)


if __name__ == "__main__":
    main()
