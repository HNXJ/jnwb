import pytest
import json
from pathlib import Path
from src.scripts.build_session_manifest import build_manifest

def test_fixture_manifest_builds():
    session_id = "230630"
    out_dir = "artifacts/test_manifests"
    manifest_path = build_manifest(session_id, out_dir, fixture_mode=True)
    
    assert manifest_path.exists()
    
    with open(manifest_path, "r") as f:
        data = json.load(f)
    
    assert data["session_id"] == session_id
    assert "area_mappings" in data
    assert len(data["area_mappings"]) > 0
    
    # Check for canonical area PFC in 230630
    areas = [m["area"] for m in data["area_mappings"]]
    assert "PFC" in areas
    
    # Check conditions
    codes = [c["code"] for c in data["conditions"]]
    assert "AXAB" in codes
    assert "AAAB" in codes
    
    # Timing
    assert data["omission_onsets_ms"]["2"] == 1031.0

def test_v3_unresolved_warning():
    # Session 230630 has V3 on Probe 2
    session_id = "230630"
    out_dir = "artifacts/test_manifests"
    manifest_path = build_manifest(session_id, out_dir, fixture_mode=True)
    
    with open(manifest_path, "r") as f:
        data = json.load(f)
        
    v3_entry = [m for m in data["area_mappings"] if m["area"] == "V3"]
    assert len(v3_entry) > 0
    assert v3_entry[0]["resolution_status"] == "unresolved"
    
    warnings = " ".join(data["warnings"])
    assert "UNRESOLVED generic V3" in warnings

def test_dp_mapping_in_manifest():
    # Session 230719 has DP
    session_id = "230719"
    out_dir = "artifacts/test_manifests"
    manifest_path = build_manifest(session_id, out_dir, fixture_mode=True)
    
    with open(manifest_path, "r") as f:
        data = json.load(f)
        
    areas = [m["area"] for m in data["area_mappings"]]
    assert "V4" in areas
    assert "DP" not in areas # Should be normalized to V4

if __name__ == "__main__":
    pytest.main([__file__])
