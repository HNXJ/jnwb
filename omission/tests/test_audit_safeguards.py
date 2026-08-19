"""
Unit tests for Dual-Area Probe Channel Mapping Unification and
Spike Lookup Index Fallback Safety.
"""

import numpy as np
import pandas as pd
import pytest

from jnwb.addressing import map_peak_channel_to_area, enrich_units_dataframe
from omission.jnwb_ext.sequence_layout import channel_slice_for_area, parse_probe_areas



def test_dual_area_probe_slice_unification():
    """
    Asserts that map_peak_channel_to_area and channel_slice_for_area agree on 128-ch dual probes.
    Channels 1-64 (0-63 0-indexed) -> Area 1 (e.g. V1)
    Channels 65-128 (64-127 0-indexed) -> Area 2 (e.g. V4)
    """
    # Build fake 128-ch electrodes DataFrame
    channels = np.arange(128)
    # 64 channels V1, 64 channels V4
    location_str = "V1, V4"
    electrodes_df = pd.DataFrame({
        'location': [location_str] * 128
    }, index=channels)

    # Test slice constants from sequence_layout
    v1_slice = channel_slice_for_area(parse_probe_areas("V1, V4"), "V1")
    v4_slice = channel_slice_for_area(parse_probe_areas("V1, V4"), "V4")


    assert v1_slice == slice(0, 64)
    assert v4_slice == slice(64, 128)

    # Test individual channel mapping via addressing
    for ch in range(0, 64):
        mapped = map_peak_channel_to_area(ch, electrodes_df)
        assert mapped == "V1", f"Channel {ch} should map to V1, got {mapped}"

    for ch in range(64, 128):
        mapped = map_peak_channel_to_area(ch, electrodes_df)
        assert mapped == "V4", f"Channel {ch} should map to V4, got {mapped}"


def test_unit_row_position_index_reset_safety():
    """
    Asserts that enrich_units_dataframe enforces a contiguous RangeIndex (0 to N-1),
    preventing non-contiguous index gaps from causing row-position vs kilosort unit_id collisions.
    """
    # Create fake raw units DataFrame with gaps (simulating dropna or filtered clusters)
    raw_units = pd.DataFrame({
        'cluster_id': [0, 4, 7, 12],  # Kilosort IDs with gaps
        'firing_rate': [2.5, 5.0, 1.2, 8.4],
        'peak_channel_id': [10, 20, 70, 80]
    }, index=[0, 4, 7, 12])  # Non-contiguous index

    # Enrich units
    enriched = enrich_units_dataframe(raw_units, electrodes_df=None)

    # Index must be reset to RangeIndex 0..3
    assert list(enriched.index) == [0, 1, 2, 3]
    # 'unit_id' column must preserve original kilosort IDs
    assert list(enriched['unit_id']) == [0, 4, 7, 12]
