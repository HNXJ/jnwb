"""
Unit and Metadata Extraction for Omission NWB Files

Consolidates logic from archived X-files:
- build_comprehensive_grand_table.py
- build_dataset_census.py
- build_area_probe_metadata_inventory.py
- classify_units_s_s_o.py
- check_quality_*.py (quality assessment)
- check_snr*.py (SNR analysis)

Provides high-level functions for extracting, classifying, and reporting on unit metadata
across multiple NWB sessions.

Author: Migrated from archived scripts
Date: 2026-06-25
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Union
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO

log = logging.getLogger(__name__)


def get_all_units_metadata(
    nwb_paths: Union[str, Path, List[Union[str, Path]]],
    filter_quality: bool = False,
    quality_threshold: float = 1.0
) -> pd.DataFrame:
    """
    Extract all units and metadata from one or more NWB files.

    Args:
        nwb_paths: Single NWB path or list of paths
        filter_quality: If True, filter to units with quality >= quality_threshold
        quality_threshold: Quality cutoff (default 1.0 = 'good')

    Returns:
        DataFrame with all unit metadata across sessions
        Columns: unit_id, session_id, cluster_id, area, layer, quality, snr,
                 firing_rate, waveform_duration, is_stable, stable_plus, ...

    Example:
        >>> units = get_all_units_metadata('/path/to/nwb')
        >>> stable_units = get_all_units_metadata('/path/to/nwbs', filter_quality=True, quality_threshold=1.0)
    """
    if isinstance(nwb_paths, (str, Path)):
        nwb_paths = [nwb_paths]

    all_units = []

    for nwb_path in nwb_paths:
        nwb_path = Path(nwb_path)
        session_id = nwb_path.stem.split("ses-")[1].split("_")[0] if "ses-" in nwb_path.stem else nwb_path.stem

        try:
            with NWBHDF5IO(str(nwb_path), 'r', load_namespaces=True) as io:
                nwb = io.read()

                # Extract units
                if nwb.units is None:
                    log.warning(f"{session_id}: No units found")
                    continue

                raw_units = nwb.units.to_dataframe().copy()
                elec_df = nwb.electrodes.to_dataframe().copy() if nwb.electrodes is not None else None

                from .addressing import enrich_units_dataframe
                units_df = enrich_units_dataframe(raw_units, elec_df)
                units_df['session_id'] = int(session_id)

                log.info(f"{session_id}: {len(units_df)} units extracted")

                if filter_quality:
                    units_df = units_df[units_df['quality'] >= quality_threshold]
                    log.info(f"  Filtered to {len(units_df)} units with quality >= {quality_threshold}")

                all_units.append(units_df)

        except Exception as e:
            log.error(f"{nwb_path.name}: {e}")
            continue

    if not all_units:
        log.warning("No units extracted from any files")
        return pd.DataFrame()

    result = pd.concat(all_units, ignore_index=True)
    log.info(f"Total: {len(result)} units across {len(nwb_paths)} sessions")

    return result


def classify_unit_quality(
    units_df: pd.DataFrame,
    thresholds: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """
    Classify units by quality based on metrics.

    Args:
        units_df: DataFrame with unit metrics (from get_all_units_metadata or NWB directly)
        thresholds: Dict of {'metric': threshold_value}
                   Default: {'quality': 1.0, 'snr': 1.0, 'firing_rate': 0.1}

    Returns:
        DataFrame with added classification columns:
        - quality_class: 'Good', 'Fair', 'Poor'
        - is_valid: bool (passes all thresholds)
        - issue_flags: list of failed criteria

    Example:
        >>> classified = classify_unit_quality(units_df)
        >>> good_units = classified[classified['is_valid']]
    """
    if thresholds is None:
        thresholds = {
            'quality': 1.0,
            'snr': 1.0,
            'firing_rate': 0.1
        }

    units_df = units_df.copy()
    units_df['issue_flags'] = units_df.apply(lambda row: [], axis=1)

    # Quality classification
    for col, thresh in thresholds.items():
        if col in units_df.columns:
            units_df.loc[pd.to_numeric(units_df[col], errors='coerce') < thresh, 'issue_flags'] = \
                units_df['issue_flags'].apply(lambda x: x + [f'{col}<{thresh}'])

    # Overall class
    units_df['quality_class'] = 'Good'
    units_df.loc[units_df['issue_flags'].apply(len) > 0, 'quality_class'] = 'Fair'

    # Check for multiple failures
    critical_flags = ['quality<1.0', 'snr<1.0']
    units_df.loc[units_df['issue_flags'].apply(
        lambda x: any(f in critical_flags for f in x)
    ), 'quality_class'] = 'Poor'

    units_df['is_valid'] = units_df['issue_flags'].apply(len) == 0

    return units_df


def unit_census_report(
    units_df: pd.DataFrame,
    group_by: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Generate a census/summary report of units grouped by session/area/layer.

    Args:
        units_df: DataFrame from get_all_units_metadata
        group_by: Columns to group by (default: ['session_id', 'area', 'layer'])

    Returns:
        Summary DataFrame with counts and statistics

    Example:
        >>> census = unit_census_report(all_units)
        >>> by_area = unit_census_report(all_units, group_by=['area'])
    """
    if group_by is None:
        group_by = ['session_id', 'area', 'layer']

    # Filter to available columns
    group_by = [col for col in group_by if col in units_df.columns]

    if not group_by:
        return units_df.describe()

    # Count column: enrich_units_dataframe (run by get_all_units_metadata) always
    # renames the raw NWB 'cluster_id' column to 'unit_id', so 'cluster_id' is
    # never present on the DataFrame this function actually receives.
    count_col = 'unit_id' if 'unit_id' in units_df.columns else 'cluster_id'

    census = units_df.groupby(group_by, dropna=False).agg({
        count_col: 'count',
        'firing_rate': ['mean', 'median', 'std'],
        'waveform_duration': ['mean', 'median'],
        'snr': ['mean', 'median']
    }).round(2)

    census.columns = ['_'.join(col).strip() for col in census.columns.values]
    census = census.rename(columns={f'{count_col}_count': 'n_units'})

    return census.reset_index()


def get_snr_analysis(
    units_df: pd.DataFrame,
    snr_threshold: float = 1.0,
    detail: bool = False
) -> Dict:
    """
    Analyze SNR distribution and quality.

    Args:
        units_df: DataFrame with SNR values
        snr_threshold: Cutoff for 'good' SNR
        detail: If True, return per-session breakdown

    Returns:
        Dict with SNR statistics and pass rates

    Example:
        >>> snr_stats = get_snr_analysis(units_df)
        >>> print(f"Units with SNR>1.0: {snr_stats['pass_rate']:.1%}")
    """
    if 'snr' not in units_df.columns:
        log.warning("No SNR column found")
        return {}

    snr_vals = pd.to_numeric(units_df['snr'], errors='coerce').dropna()

    result = {
        'n_units_with_snr': len(snr_vals),
        'snr_mean': snr_vals.mean(),
        'snr_median': snr_vals.median(),
        'snr_std': snr_vals.std(),
        'snr_min': snr_vals.min(),
        'snr_max': snr_vals.max(),
        'pass_count': (snr_vals >= snr_threshold).sum(),
        'pass_rate': (snr_vals >= snr_threshold).mean()
    }

    if detail and 'session_id' in units_df.columns:
        result['by_session'] = {}
        for session in units_df['session_id'].unique():
            sess_snr = pd.to_numeric(
                units_df[units_df['session_id'] == session]['snr'],
                errors='coerce'
            ).dropna()
            result['by_session'][session] = {
                'n': len(sess_snr),
                'mean': sess_snr.mean(),
                'pass_rate': (sess_snr >= snr_threshold).mean()
            }

    return result


def electrode_inventory(
    nwb_paths: Union[str, Path, List[Union[str, Path]]]
) -> pd.DataFrame:
    """
    Build inventory of electrodes, mapping to units and areas.

    Args:
        nwb_paths: Single or list of NWB file paths

    Returns:
        DataFrame with electrode metadata and unit assignments

    Example:
        >>> inv = electrode_inventory('/path/to/nwbs')
        >>> fef_channels = inv[inv['area'] == 'FEF']
    """
    if isinstance(nwb_paths, (str, Path)):
        nwb_paths = [nwb_paths]

    all_elecs = []

    for nwb_path in nwb_paths:
        nwb_path = Path(nwb_path)
        session_id = nwb_path.stem.split("ses-")[1].split("_")[0] if "ses-" in nwb_path.stem else nwb_path.stem

        try:
            with NWBHDF5IO(str(nwb_path), 'r', load_namespaces=True) as io:
                nwb = io.read()

                if nwb.electrodes is None:
                    continue

                elec_df = nwb.electrodes.to_dataframe().copy()
                elec_df['session_id'] = int(session_id)
                elec_df['elec_id'] = elec_df.index

                # Add unit assignment info
                if nwb.units is not None:
                    units_df = nwb.units.to_dataframe()
                    if 'peak_channel_id' in units_df.columns:
                        # Count units per channel
                        unit_counts = units_df['peak_channel_id'].value_counts()
                        elec_df['n_units_on_channel'] = elec_df.index.map(
                            lambda x: unit_counts.get(float(x), 0)
                        )
                    else:
                        elec_df['n_units_on_channel'] = 0
                else:
                    elec_df['n_units_on_channel'] = 0

                all_elecs.append(elec_df)

        except Exception as e:
            log.error(f"{nwb_path.name}: {e}")
            continue

    if not all_elecs:
        log.warning("No electrode data extracted")
        return pd.DataFrame()

    return pd.concat(all_elecs, ignore_index=False)
