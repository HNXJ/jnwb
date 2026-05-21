import os
import sys
import json
import pytest
import subprocess
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.validate_session_manifest_contract import validate_single_manifest_file

def test_validator_skips_when_no_data_root(monkeypatch):
    # Ensure OMISSION_DATA_ROOT is absent
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    
    # Run CLI
    cmd = [sys.executable, "scripts/validate_session_manifest_contract.py"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "SKIPPING" in res.stdout

def test_validator_accepts_valid_fixture(tmp_path):
    # Create a valid fixture manifest json
    manifest_data = {
        "session_id": "230630_fixture",
        "subject": "FixtureSubject",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True},
        "area_mappings": [
            {"area": "V1", "probe": 0, "start_ch": 0, "end_ch": 64, "resolution_status": "validated"}
        ]
    }
    
    m_path = tmp_path / "valid_manifest.json"
    with open(m_path, "w") as f:
        json.dump(manifest_data, f)
        
    res = validate_single_manifest_file(m_path, expect_real=False)
    assert res["valid"] is True
    assert res["is_fixture"] is True
    assert not res["errors"]

def test_validator_rejects_fixture_if_expect_real(tmp_path):
    manifest_data = {
        "session_id": "230630_fixture",
        "subject": "FixtureSubject",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True},
        "area_mappings": []
    }
    
    m_path = tmp_path / "valid_manifest.json"
    with open(m_path, "w") as f:
        json.dump(manifest_data, f)
        
    res = validate_single_manifest_file(m_path, expect_real=True)
    assert res["valid"] is False
    assert any("Fixture/Synthetic manifest found in real data directory" in err for err in res["errors"])

def test_validator_reports_missing_fields(tmp_path):
    # Missing session_id completely in JSON structure
    manifest_data = {
        "subject": "FixtureSubject"
    }
    m_path = tmp_path / "missing_fields.json"
    with open(m_path, "w") as f:
        json.dump(manifest_data, f)
        
    res = validate_single_manifest_file(m_path, expect_real=False)
    assert res["valid"] is False
    assert any("missing required 'session_id' key" in err for err in res["errors"])

def test_validator_preserves_generic_v3_warning(tmp_path):
    manifest_data = {
        "session_id": "230630_fixture",
        "subject": "FixtureSubject",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True},
        "area_mappings": [
            {"area": "V3", "probe": 0, "start_ch": 0, "end_ch": 64, "resolution_status": "unresolved"}
        ]
    }
    m_path = tmp_path / "v3_warning.json"
    with open(m_path, "w") as f:
        json.dump(manifest_data, f)
        
    res = validate_single_manifest_file(m_path, expect_real=False)
    assert any("generic V3" in warn for warn in res["warnings"])

def test_validator_normalizes_dp_to_v4(tmp_path):
    # Check that DP or DP (V4) without normalization is rejected or reported
    manifest_data = {
        "session_id": "230630_fixture",
        "subject": "FixtureSubject",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True},
        "area_mappings": [
            {"area": "DP", "probe": 0, "start_ch": 0, "end_ch": 64, "resolution_status": "validated"}
        ]
    }
    m_path = tmp_path / "dp_normalization.json"
    with open(m_path, "w") as f:
        json.dump(manifest_data, f)
        
    res = validate_single_manifest_file(m_path, expect_real=False)
    assert any("not normalized to V4" in err for err in res["errors"])

def test_validator_does_not_require_private_paths(tmp_path):
    # The validator works using tmp_path and doesn't hardcode "D:/drive" or other user-specific directories
    manifest_data = {
        "session_id": "temp_session",
        "subject": "TempSubject",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True}
    }
    m_path = tmp_path / "temp_manifest.json"
    with open(m_path, "w") as f:
        json.dump(manifest_data, f)
        
    res = validate_single_manifest_file(m_path, expect_real=False)
    assert res["valid"] is True

def test_validator_does_not_create_files_without_out(tmp_path, monkeypatch):
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    manifest_data = {
        "session_id": "temp_session",
        "subject": "TempSubject",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True}
    }
    m_path = tmp_path / "temp_manifest.json"
    with open(m_path, "w") as f:
        json.dump(manifest_data, f)
        
    # Running CLI without --out should not write files
    cmd = [sys.executable, "scripts/validate_session_manifest_contract.py", "--manifest", str(m_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    # No report file created in current directory
    report_file = Path("Session Manifest Contract Validation Report.md")
    assert not report_file.exists()

def test_validator_creates_files_with_out(tmp_path, monkeypatch):
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    manifest_data = {
        "session_id": "temp_session",
        "subject": "TempSubject",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True}
    }
    m_path = tmp_path / "temp_manifest.json"
    with open(m_path, "w") as f:
        json.dump(manifest_data, f)
        
    out_file = tmp_path / "report.md"
    cmd = [sys.executable, "scripts/validate_session_manifest_contract.py", "--manifest", str(m_path), "--out", str(out_file)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert out_file.exists()
    assert "# Session Manifest Contract Validation Report" in out_file.read_text()

def test_cli_returns_nonzero_for_invalid_manifest(tmp_path):
    # Force a validation error
    manifest_data = {
        "session_id": "temp_session",
        "subject": "TempSubject",
        "truth_status": "overriding_truth_should_fail",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True}
    }
    m_path = tmp_path / "bad_manifest.json"
    with open(m_path, "w") as f:
        json.dump(manifest_data, f)
        
    cmd = [sys.executable, "scripts/validate_session_manifest_contract.py", "--manifest", str(m_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0
