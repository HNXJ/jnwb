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
                # Clean up area (split by comma and strip coordinates)
                return str(loc).split(',')[0].strip()
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

    # Force conversion of core types
    for col in ['firing_rate', 'waveform_duration']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df
