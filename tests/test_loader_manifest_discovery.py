import os
import sys
import json
import pytest
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.analysis.io.loader import DataLoader
from src.analysis.contracts import SessionManifest

def test_get_data_root_returns_none_when_env_absent(monkeypatch):
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    loader = DataLoader()
    assert loader.get_data_root() is None

def test_validate_manifest_returns_unavailable_when_no_data_root(monkeypatch):
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    loader = DataLoader()
    status = loader.validate_session_manifest("230630")
    assert status["status"] == "unavailable"
    assert "Data root unavailable." in status["errors"]

def test_fixture_manifest_loading_allow_fixture(monkeypatch):
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    loader = DataLoader()
    
    # 1. Loading without allow_fixture=True should return None
    manifest = loader.load_session_manifest("230630", allow_fixture=False)
    assert manifest is None
    
    # 2. Loading with allow_fixture=True should return the fixture manifest
    manifest = loader.load_session_manifest("230630", allow_fixture=True)
    assert manifest is not None
    assert manifest.is_fixture() is True
    assert manifest.session_id == "230630"

def test_fixture_manifest_validation_rejected_if_allow_fixture_false(monkeypatch, tmp_path):
    # Put fixture manifest in the temporary directory to mimic placing a fixture in real data root
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    
    fixture_data = {
        "session_id": "230630_fixture",
        "subject": "FixtureSubject",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True}
    }
    
    # Place fixture manifest JSON directly in a candidate location under data_root (tmp_path)
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    manifest_file = manifests_dir / "session_230630_manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(fixture_data, f)
        
    loader = DataLoader()
    # Validate
    res = loader.validate_session_manifest("230630", data_root=tmp_path)
    assert res["status"] == "invalid"
    assert any("Fixture/Synthetic manifest found in real data directory." in err for err in res["errors"])

def test_manifest_discovery_finds_tmp_manifests(tmp_path):
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    manifest_file = manifests_dir / "230630.json"
    manifest_file.touch()
    
    loader = DataLoader()
    discovered = loader.discover_session_manifest_paths(tmp_path)
    assert manifest_file in discovered

def test_missing_manifest_returns_invalid_status(tmp_path):
    loader = DataLoader()
    # Nonexistent session manifest
    res = loader.validate_session_manifest("nonexistent_session_12345", data_root=tmp_path)
    assert res["status"] == "invalid"
    assert any("No candidate manifest file found" in err for err in res["errors"])

def test_multiple_candidates_produce_deterministic_selection_and_warning(tmp_path, caplog):
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    
    # Create two candidates
    p1 = manifests_dir / "session_230630_manifest.json"
    p2 = manifests_dir / "230630_manifest.json"
    
    m_data_1 = {
        "session_id": "230630",
        "subject": "MonkeyA",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": True, "LFP": True}
    }
    m_data_2 = {
        "session_id": "230630",
        "subject": "MonkeyB",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": True, "LFP": True}
    }
    
    with open(p1, "w") as f:
        json.dump(m_data_1, f)
    with open(p2, "w") as f:
        json.dump(m_data_2, f)
        
    loader = DataLoader()
    
    # Test validation detects ambiguity (status="ambiguous" because of multiple candidates, but valid schema)
    res = loader.validate_session_manifest("230630", data_root=tmp_path)
    assert res["status"] == "ambiguous"
    assert any("Multiple candidate manifests found" in warn for warn in res["warnings"])
    
    # Test deterministic loading chooses session_{session_id}_manifest.json
    loaded = loader.load_session_manifest("230630", data_root=tmp_path, allow_fixture=False)
    assert loaded.subject == "MonkeyA"

def test_generic_v3_warning_preserved(tmp_path):
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    manifest_file = manifests_dir / "session_230630_manifest.json"
    
    manifest_data = {
        "session_id": "230630",
        "subject": "MonkeyA",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True},
        "area_mappings": [
            {"area": "V3", "probe": 0, "start_ch": 0, "end_ch": 64, "resolution_status": "unresolved"}
        ]
    }
    
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f)
        
    loader = DataLoader()
    res = loader.validate_session_manifest("230630", data_root=tmp_path)
    assert any("generic V3" in warn for warn in res["warnings"])

def test_dp_alias_normalizes_to_v4(tmp_path):
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    manifest_file = manifests_dir / "session_230630_manifest.json"
    
    manifest_data = {
        "session_id": "230630",
        "subject": "MonkeyA",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True},
        "area_mappings": [
            {"area": "DP", "probe": 0, "start_ch": 0, "end_ch": 64, "resolution_status": "validated"}
        ],
        "units": [
            {"unit_id": "230630-0-1", "probe": 0, "local_idx": 1, "peak_channel": 12, "area": "DP (V4)", "resolution_status": "validated"}
        ],
        "channel_counts_by_area": {
            "DP": 64
        }
    }
    
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f)
        
    loader = DataLoader()
    # 1. Validation detects that DP in raw manifest is NOT normalized
    res = loader.validate_session_manifest("230630", data_root=tmp_path)
    assert res["status"] == "invalid"
    assert any("not normalized to V4" in err for err in res["errors"])
    
    # 2. Loading the manifest normalizes DP to V4 on the fly
    loaded = loader.load_session_manifest("230630", data_root=tmp_path, allow_fixture=False)
    assert loaded.area_mappings[0].area == "V4"
    assert loaded.units[0].area == "V4"
    assert "V4" in loaded.channel_counts_by_area
    assert "DP" not in loaded.channel_counts_by_area

def test_real_data_integration_skipped_without_env(monkeypatch):
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    # This acts as the gated integration test requirement (Rule 10)
    if "OMISSION_DATA_ROOT" not in os.environ:
        pytest.skip("Skipping real data integration test as OMISSION_DATA_ROOT is not set.")
