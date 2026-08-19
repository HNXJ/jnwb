"""
Anatomical Addressing and Cortical Layer Mapping for Omission NWB Analysis.

Provides unified, canonical functions to map units/channels to areas and layers,
and standardizes units DataFrame fields (unit_id, area, layer, quality flags).

Author: Claude Code
Date: 2026-06-28
"""

import logging
from typing import Optional, Dict
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)


def map_peak_channel_to_area(peak_channel_id: float, electrodes_df: pd.DataFrame) -> Optional[str]:
    """
    Map peak channel ID to brain area location.

    Args:
        peak_channel_id: Channel identifier
        electrodes_df: NWB electrodes DataFrame

    Returns:
        Brain area name (e.g. 'V1', 'PFC', 'FEF') or None if unresolved
    """
    if pd.isna(peak_channel_id) or electrodes_df is None or len(electrodes_df) == 0:
        return None

    try:
        # Check location or area columns in electrodes_df
        col_to_check = None
        for col in ['location', 'area', 'group_name']:
            if col in electrodes_df.columns:
                col_to_check = col
                break

        if col_to_check is None:
            return None

        # Resolve index mapping
        idx = int(float(peak_channel_id))
        if idx in electrodes_df.index:
            loc = electrodes_df.loc[idx, col_to_check]
            if pd.notna(loc):
                loc_str = str(loc).strip()

                # Single-area probe: resolve directly, no channel-position logic needed.
                if ',' not in loc_str and '/' not in loc_str:
                    return loc_str

                # Multi-area probe (e.g. "V1, V2, V3" on one 128-channel
                # probe): resolve by the channel's POSITION within the
                # probe, not just the first listed area. Previously this
                # always returned loc.split(',')[0] regardless of position -
                # a real bug confirmed 2026-07-12: e.g. probe C channels
                # 118-120 on a "V1, V2, V3" probe were all labeled 'V1' when
                # the correct area for that channel range is 'V3'.
                # Layering note: multi-area probe splitting needs the omission project's
                # canonical area-name parsing (V3d/V3a convention etc.) -- a lazy, optional
                # dependency on omission/, not a module-load-time one. Single-area probes
                # (the common case) never take this branch.
                from omission.jnwb_ext.sequence_layout import parse_probe_areas
                areas = parse_probe_areas(loc_str)
                if len(areas) <= 1:
                    return loc_str.split(',')[0].strip()

                group_col = 'group_name' if 'group_name' in electrodes_df.columns else col_to_check
                probe_key = electrodes_df.loc[idx, group_col]
                probe_rows = electrodes_df[electrodes_df[group_col] == probe_key]
                probe_start = int(probe_rows.index.min())
                n_channels_on_probe = len(probe_rows)
                local_idx = idx - probe_start

                edges = np.linspace(0, n_channels_on_probe, len(areas) + 1)
                bin_idx = int(np.searchsorted(edges, local_idx, side='right')) - 1
                bin_idx = min(max(bin_idx, 0), len(areas) - 1)
                return areas[bin_idx]
    except Exception as e:
        log.debug(f"Failed to map peak channel {peak_channel_id} to area: {e}")

    return None


def classify_layer_from_depth(peak_channel_id: float, electrodes_df: pd.DataFrame) -> str:
    """
    Classify unit cortical layer using z depth coordinates.

    Args:
        peak_channel_id: Channel identifier
        electrodes_df: NWB electrodes DataFrame

    Returns:
        Cortical layer label ('Deep', 'Superficial', or 'Unknown')
    """
    if pd.isna(peak_channel_id) or electrodes_df is None or len(electrodes_df) == 0:
        return 'Unknown'

    try:
        idx = int(float(peak_channel_id))
        if idx in electrodes_df.index and 'z' in electrodes_df.columns:
            z_val = electrodes_df.loc[idx, 'z']
            if pd.notna(z_val):
                # Canonical neuroscience threshold: deep vs superficial
                # z values > 1000 microns typically represent deep layers in these linear arrays
                return 'Deep' if float(z_val) > 1000.0 else 'Superficial'
    except Exception as e:
        log.debug(f"Failed to classify layer for channel {peak_channel_id}: {e}")

    return 'Unknown'


def enrich_units_dataframe(units_df: pd.DataFrame, electrodes_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """
    Enrich units DataFrame with standardized area, layer, and quality flags.

    Enforces SC-002: Terminology alignment (using unit_id and standard quality flags).

    Args:
        units_df: Raw NWB units DataFrame
        electrodes_df: Raw NWB electrodes DataFrame

    Returns:
        Standardized and enriched DataFrame
    """
    df = units_df.copy()

    # 1. Standardize unit_id column
    if 'cluster_id' in df.columns and 'unit_id' not in df.columns:
        df = df.rename(columns={'cluster_id': 'unit_id'})
    
    # If the index is 'id' or unnamed and representing unit indices, expose unit_id
    if 'unit_id' not in df.columns:
        if df.index.name == 'id' or df.index.name is None:
            df['unit_id'] = df.index
        else:
            df['unit_id'] = np.arange(len(df))

    # 2. Enrich anatomical mapping if electrodes_df is provided
    if electrodes_df is not None and len(electrodes_df) > 0 and 'peak_channel_id' in df.columns:
        df['area'] = df['peak_channel_id'].apply(lambda x: map_peak_channel_to_area(x, electrodes_df))
        df['layer'] = df['peak_channel_id'].apply(lambda x: classify_layer_from_depth(x, electrodes_df))
        
        # Resolve group_name/probe mapping
        col_group = 'group_name' if 'group_name' in electrodes_df.columns else ('probe' if 'probe' in electrodes_df.columns else None)
        if col_group is not None:
            df['group_name'] = df['peak_channel_id'].apply(lambda x: electrodes_df.loc[int(float(x)), col_group] if pd.notna(x) and int(float(x)) in electrodes_df.index else None)
        else:
            df['group_name'] = 'probeA'
    else:
        if 'area' not in df.columns:
            df['area'] = None
        if 'layer' not in df.columns:
            df['layer'] = 'Unknown'
        if 'group_name' not in df.columns:
            df['group_name'] = 'probeA'

    # 3. Handle quality and stable flags
    # Standard quality cutoff: quality >= 1.0 is stable
    if 'quality' in df.columns:
        df['quality'] = pd.to_numeric(df['quality'], errors='coerce')
        df['is_stable'] = df['quality'] >= 1.0
        df['stable_plus'] = df['is_stable']
    else:
        if 'is_stable' not in df.columns:
            df['is_stable'] = False
        if 'stable_plus' not in df.columns:
            df['stable_plus'] = False

    # Force conversion of core types. snr/unit_id are stored as dtype=str
    # (object) on some sessions (e.g. C31o) but float64 on others (e.g.
    # V182o) - the same cross-session inconsistency already worked around
    # for snr in scripts/filter_units.py. unit_id is used as an identity
    # key for equality/isin comparisons throughout the codebase (session.py
    # get_spike_times, factories.py dataset_from_session, etc.) - an
    # object-dtype string column silently fails every such comparison
    # (df['unit_id'] == 156 is always False if the stored value is the
    # string '156.0'), confirmed 2026-07-12. Coerced here at the source.
    for col in ['firing_rate', 'waveform_duration', 'snr', 'unit_id']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Ensure clean RangeIndex (0 to N-1) to guarantee row-position lookup in get_spike_times
    df = df.reset_index(drop=True)

    return df

