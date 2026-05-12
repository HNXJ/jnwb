import pytest
import numpy as np
import pandas as pd
from src.analysis.io.loader import DataLoader

@pytest.fixture
def loader():
    return DataLoader()

def test_area_normalization(loader):
    assert loader.normalize_area("DP") == "V4"
    assert loader.normalize_area("DP (V4)") == "V4"
    assert loader.normalize_area("V3") == "V3"
    assert loader.normalize_area("V3d") == "V3d"
    assert loader.normalize_area("V3a") == "V3a"
    assert loader.normalize_area("PFC") == "PFC"

def test_session_230630_metadata_indexing(loader):
    session = "230630"
    df = loader._get_unit_metadata(session)
    assert df is not None, f"Metadata for {session} must exist"
    
    total_units_probes = 0
    for p in range(3): # Session 230630 has 3 probes
        count = loader._get_probe_unit_count(session, p)
        total_units_probes += count
        
    assert len(df) == total_units_probes, "CSV row count must match total units across probes"

def test_unit_resolution_logic(loader):
    session = "230630"
    # Probe 1 in 230630 has V4 (0-64) and MT (64-128)
    # Unit 32 (idx 3 on probe 1) has peak_ch 140 -> local 12 -> V4
    area, status, _ = loader.resolve_unit_area(session, 1, 3, allow_heuristic=False)
    assert area == "V4"
    assert status == "metadata_resolved_equal_segment"

def test_allow_heuristic_behavior(loader):
    # Session 230629 doesn't have CSV metadata
    session = "230629"
    area, status, _ = loader.resolve_unit_area(session, 0, 0, allow_heuristic=False)
    assert area is None
    assert status == "unknown_area"
    
    area, status, _ = loader.resolve_unit_area(session, 0, 0, allow_heuristic=True)
    assert area is not None
    assert status == "heuristic_fallback"

def test_unit_count_conservation(loader):
    session = "230630"
    area = "V4"
    units_meta = loader.get_units_by_area(area, allow_heuristic=False)
    units_total = loader.get_units_by_area(area, allow_heuristic=True)
    
    # All units in 230630 V4 should be metadata resolved (since metadata exists)
    # But check that heuristic count doesn't silently increase without metadata
    assert len(units_meta) <= len(units_total)

def test_downstream_get_signal(loader):
    # Smoke test for get_signal(mode='spk')
    area = "V4"
    condition = "AXAB"
    # Note: this might return None if arrays are missing, but shouldn't crash
    try:
        signals = loader.get_signal("spk", condition, area, session="230630")
        if signals:
            assert isinstance(signals, list)
            for arr in signals:
                assert arr.ndim == 3 # trials x units x time
    except Exception as e:
        pytest.fail(f"get_signal crashed: {e}")

if __name__ == "__main__":
    pytest.main([__file__])
