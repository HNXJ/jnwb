"""
Anatomical addressing and cortical layer mapping for NWB electrode tables.

Maps units/channels to areas and layers from electrode metadata, and standardizes
units DataFrame fields (unit_id, area, layer, quality flags). Probe labels are
split on comma or slash only; this module carries no area vocabulary and does not
normalize spelling or aliases.
"""

import logging
import re
from typing import Optional, Dict
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)


def parse_probe_areas(label: str) -> tuple:
    """Split a multi-area probe label into ordered area names.

    Splits on comma or slash, trims surrounding whitespace, drops empty fields, and
    otherwise returns each label exactly as the NWB file wrote it. This resolves only
    SEPARATION; which channels fall in which area is decided afterwards, by position
    along the probe.

    No vocabulary lives here, deliberately. Neither identity (is `DP` the same area as
    `V4`?) nor spelling (is `v3a` the same area as `V3a`?) is a question generic
    addressing can answer -- both depend on the recording convention of a particular
    corpus, and a library that answered them would silently impose one project's
    convention on every other. A project that knows its own convention normalizes before
    or after calling this; jnwb does not normalize on its behalf.

    Folding labels together here is also lossy in a way that is easy to miss: under a
    project convention treating DP as an alias of V4, a "DP/V4" probe resolved to
    ('V4', 'V4') -- both halves collapsing to one name, so a two-area probe stopped being
    distinguishable by area at all.

        >>> parse_probe_areas("V1, DP")
        ('V1', 'DP')
        >>> parse_probe_areas("DP/V4")
        ('DP', 'V4')
        >>> parse_probe_areas("V3A/V1")
        ('V3A', 'V1')
        >>> parse_probe_areas("v3d,V2")
        ('v3d', 'V2')

    Self-contained by design: jnwb must give identical scientific behaviour whether or not
    any project package is importable, so nothing here may depend on one being installed.
    """
    return tuple(t for t in (p.strip() for p in re.split(r"[,/]", str(label))) if t)


def _resolve_electrode_row(peak_channel_id: float, electrodes_df: pd.DataFrame):
    """Resolve an electrode row from electrodes_df by channel ID.

    Checks explicit identifier columns ('channel_id', 'id', 'electrode_id') first
    to avoid row index / channel ID substitution when DataFrame index is reset or non-default,
    falling back to DataFrame index lookup.

    Returns:
        (row_index, row_series) or (None, None) if not found.
    """
    if pd.isna(peak_channel_id) or electrodes_df is None or len(electrodes_df) == 0:
        return None, None

    try:
        val = int(float(peak_channel_id))
    except (ValueError, TypeError, OverflowError):
        return None, None

    # 1. Check explicit channel identifier columns first
    has_explicit_id_col = False
    for id_col in ['channel_id', 'id', 'electrode_id']:
        if id_col in electrodes_df.columns:
            has_explicit_id_col = True
            matches = electrodes_df.index[electrodes_df[id_col] == val]
            if len(matches) > 0:
                idx = matches[0]
                return idx, electrodes_df.loc[idx]

    # 2. Fall back to DataFrame index ONLY IF no explicit channel ID column was present
    if not has_explicit_id_col and val in electrodes_df.index:
        return val, electrodes_df.loc[val]

    return None, None


def map_peak_channel_to_area(peak_channel_id: float, electrodes_df: pd.DataFrame) -> Optional[str]:
    """
    Map peak channel ID to brain area location.

    Args:
        peak_channel_id: Channel identifier
        electrodes_df: NWB electrodes DataFrame

    Returns:
        Brain area name (e.g. 'V1', 'PFC', 'FEF') or None if unresolved
    """
    idx, row = _resolve_electrode_row(peak_channel_id, electrodes_df)
    if row is None:
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

        loc = row.get(col_to_check)
        if pd.notna(loc):
            loc_str = str(loc).strip()

            # Single-area probe: resolve directly, no channel-position logic needed.
            if ',' not in loc_str and '/' not in loc_str:
                return loc_str

            # Multi-area probe (e.g. "V1, V2, V3" on one 128-channel
            # probe): resolve by the channel's POSITION within the
            # probe, not just the first listed area.
            areas = parse_probe_areas(loc_str)

            if len(areas) <= 1:
                return loc_str.split(',')[0].strip()

            group_col = 'group_name' if 'group_name' in electrodes_df.columns else col_to_check
            probe_key = row.get(group_col)
            probe_rows = electrodes_df[electrodes_df[group_col] == probe_key]
            n_channels_on_probe = len(probe_rows)
            if n_channels_on_probe == 0:
                return loc_str.split(',')[0].strip()

            probe_indices = list(probe_rows.index)
            local_idx = probe_indices.index(idx)

            edges = np.linspace(0, n_channels_on_probe, len(areas) + 1)
            bin_idx = int(np.searchsorted(edges, local_idx, side='right')) - 1
            bin_idx = min(max(bin_idx, 0), len(areas) - 1)
            return areas[bin_idx]
    except (ValueError, KeyError, IndexError, TypeError) as e:
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
    idx, row = _resolve_electrode_row(peak_channel_id, electrodes_df)
    if row is None:
        return 'Unknown'

    try:
        if 'z' in electrodes_df.columns:
            z_val = row.get('z')
            if pd.notna(z_val):
                # Canonical neuroscience threshold: deep vs superficial
                # z values > 1000 microns typically represent deep layers in these linear arrays
                return 'Deep' if float(z_val) > 1000.0 else 'Superficial'
    except (ValueError, TypeError) as e:
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
            def _get_group(x):
                _, r = _resolve_electrode_row(x, electrodes_df)
                return r.get(col_group) if r is not None else None
            df['group_name'] = df['peak_channel_id'].apply(_get_group)
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
    # (object) on some sessions but float64 on others — the same cross-session dtype
    # inconsistency already worked around
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

