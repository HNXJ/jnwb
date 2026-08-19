import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from src.analysis.io.loader import DataLoader

@pytest.fixture
def mock_mapping_file(tmp_path):
    mapping_content = """| Session | Probe | Area | Total Ch |
|:---|:---|:---|:---|
| 230630 | 0 | V1, V2 | 128 |
| 230630 | 1 | V3, V4 | 128 |
| 230901 | 0 | PFC | 128 |
"""
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_file.write_text(mapping_content)
    return mapping_file

@pytest.fixture
def mock_metadata_dir(tmp_path):
    meta_dir = tmp_path / "metadata"
    meta_dir.mkdir()
    
    # Session 230630 metadata: 2 probes, 10 units each
    units = []
    for p in range(2):
        for u in range(10):
            # Probe 0: units 0-9 (V1: 0-4 (ch 32), V2: 5-9 (ch 96))
            # Probe 1: units 10-19 (V3: 10-14 (ch 32), V4: 15-19 (ch 96))
            if p == 0:
                ch = 32 if u < 5 else 96
            else:
                ch = 32 if u < 5 else 96
            
            # Unit 7 on Probe 0 has NaN peak_ch to test unresolved_metadata
            if p == 0 and u == 7:
                ch = np.nan
            # Unit 8 on Probe 0 has peak_ch on WRONG probe (e.g. 1*128 + 32 = 160)
            if p == 0 and u == 8:
                ch = 160

            units.append({
                "unit_id": u + p*10,
                "peak_channel_id": ch if pd.isna(ch) else int(ch) + p*128
            })
    
    df = pd.DataFrame(units)
    df.to_csv(meta_dir / "units_ses-230630.csv", index=False)
    return meta_dir

@pytest.fixture
def loader(mock_mapping_file, mock_metadata_dir, tmp_path):
    # Setup data_dir structure
    data_dir = tmp_path / "arrays"
    data_dir.mkdir()
    
    # Create dummy .npy files for unit counts
    for p in range(2):
        dummy_arr = np.zeros((1, 10, 1)) # 10 units
        np.save(data_dir / f"ses230630-units-probe{p}-spk-AXAB.npy", dummy_arr)
        
    l = DataLoader(data_dir=str(data_dir), mapping_file=str(mock_mapping_file))
    # Override metadata dir to use the mock one
    l.data_dir = data_dir
    return l

def test_resolve_unit_area_metadata_resolved(loader):
    # Valid V1 resolution
    area, status, warn = loader.resolve_unit_area("230630", 0, 0)
    assert area == "V1"
    assert status == "metadata_resolved_equal_segment"

def test_resolve_unit_area_unresolved_metadata_nan(loader):
    # Unit 7 has NaN peak_channel_id
    area, status, warn = loader.resolve_unit_area("230630", 0, 7)
    assert area is None
    assert status == "unresolved_metadata"
    assert "NaN" in warn

def test_resolve_unit_area_unresolved_metadata_probe_mismatch(loader):
    # Unit 8 has peak_channel_id on probe 1 but is in probe 0 data
    area, status, warn = loader.resolve_unit_area("230630", 0, 8)
    assert area is None
    assert status == "unresolved_metadata"
    assert "mismatch" in warn

def test_resolve_unit_area_blacklisted(loader):
    area, status, warn = loader.resolve_unit_area("230901", 0, 0)
    assert area is None
    assert status == "blacklisted"

def test_resolve_unit_area_unresolved_no_probe_mapping(loader):
    # Session 230630 has no mapping for probe 3
    area, status, warn = loader.resolve_unit_area("230630", 3, 0)
    assert area is None
    assert status == "unresolved_no_probe_mapping"

def test_resolve_unit_area_unknown_area(mock_mapping_file, tmp_path):
    # Build a loader where probe 0 has a gap: only V1 (0-64), no coverage for ch 64-128.
    # Then supply metadata placing a unit at ch 96 (local) -> falls outside V1 -> unknown_area.
    mapping_content = """| Session | Probe | Area | Total Ch |
|:---|:---|:---|:---|
| 230777 | 0 | V1 | 64 |
"""
    gap_mapping = tmp_path / "gap-mapping.md"
    gap_mapping.write_text(mapping_content)

    meta_dir = tmp_path / "metadata_gap"
    meta_dir.mkdir()
    import pandas as pd
    df = pd.DataFrame([{"unit_id": 0, "peak_channel_id": 96}])  # ch 96 -> outside V1 (0-64)
    df.to_csv(meta_dir / "units_ses-230777.csv", index=False)

    from src.analysis.io.loader import DataLoader
    data_dir = tmp_path / "arrays_gap"
    data_dir.mkdir()
    import numpy as np
    np.save(data_dir / "ses230777-units-probe0-spk-AXAB.npy", np.zeros((1, 1, 1)))

    l = DataLoader(data_dir=str(data_dir), mapping_file=str(gap_mapping))
    area, status, warn = l.resolve_unit_area("230777", 0, 0)
    assert area is None
    assert status == "unknown_area"

def test_resolve_unit_area_heuristic_fallback(tmp_path):
    # Session has a probe mapping but NO metadata CSV -> heuristic path.
    # With allow_heuristic=True, unit_idx placed within the first area's linear partition.
    mapping_content = """| Session | Probe | Area | Total Ch |
|:---|:---|:---|:---|
| 230888 | 0 | V1, V2 | 128 |
"""
    heuristic_mapping = tmp_path / "heuristic-mapping.md"
    heuristic_mapping.write_text(mapping_content)

    data_dir = tmp_path / "arrays_heuristic"
    data_dir.mkdir()
    import numpy as np
    # 10 units on probe 0; no metadata CSV -> forces heuristic path.
    np.save(data_dir / "ses230888-units-probe0-spk-AXAB.npy", np.zeros((1, 10, 1)))

    from src.analysis.io.loader import DataLoader
    l = DataLoader(data_dir=str(data_dir), mapping_file=str(heuristic_mapping))
    # unit_idx=2, 10 total units: V1 covers 0-64 -> linear partition 0-4 = V1
    area, status, warn = l.resolve_unit_area("230888", 0, 2, allow_heuristic=True)
    assert status == "heuristic_fallback"
    assert area == "V1"

def test_normalize_area(loader):
    assert loader.normalize_area("DP") == "V4"
    assert loader.normalize_area("DP (V4)") == "V4"
    assert loader.normalize_area("V1") == "V1"
