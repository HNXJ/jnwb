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

from src.analysis.io.loader import DataLoader
from src.analysis.contracts.data_source_index import DataSourceIndex, DataSourceRecord

def test_no_omission_data_root_returns_unavailable(monkeypatch):
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    loader = DataLoader()
    
    # 1. Discover data sources returns status "unavailable" or "Data root unavailable." error
    index = loader.discover_data_sources()
    assert "Data root unavailable." in index.errors
    
    # 2. Get signal source status returns status "unavailable"
    status = loader.get_signal_source_status("230630", "LFP")
    assert status["status"] == "unavailable"

def test_manifest_discovery_in_tmp_path(tmp_path):
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    manifest_file = manifests_dir / "230630_manifest.json"
    manifest_file.touch()
    
    loader = DataLoader()
    index = loader.discover_data_sources(tmp_path)
    
    assert len(index.records) == 1
    rec = index.records[0]
    assert rec.role == "manifest"
    assert rec.source_status == "discovered_manifest"
    assert rec.readable_for_phase2 is True
    assert rec.session_id == "230630"

def test_metadata_discovery_in_tmp_path(tmp_path):
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    metadata_file = metadata_dir / "230630_units.csv"
    metadata_file.touch()
    
    loader = DataLoader()
    index = loader.discover_data_sources(tmp_path)
    
    assert len(index.records) == 1
    rec = index.records[0]
    assert rec.role == "metadata"
    assert rec.source_status == "discovered_metadata"
    assert rec.readable_for_phase2 is True
    assert rec.session_id == "230630"

def test_nwb_discovery_blocked_in_tmp_path(tmp_path):
    nwb_dir = tmp_path / "nwb"
    nwb_dir.mkdir()
    nwb_file = nwb_dir / "session_230630.nwb"
    nwb_file.touch()
    
    loader = DataLoader()
    index = loader.discover_data_sources(tmp_path)
    
    assert len(index.records) == 1
    rec = index.records[0]
    assert rec.role == "raw_neural_array"
    assert rec.source_status == "discovered_raw_blocked"
    assert rec.readable_for_phase2 is False
    assert "Blocked" in rec.reason_not_read
    assert rec.session_id == "230630"

def test_arrays_discovery_blocked_in_tmp_path(tmp_path):
    arrays_dir = tmp_path / "arrays"
    arrays_dir.mkdir()
    npy_file = arrays_dir / "foo_230719.npy"
    npy_file.touch()
    
    loader = DataLoader()
    index = loader.discover_data_sources(tmp_path)
    
    assert len(index.records) == 1
    rec = index.records[0]
    assert rec.role == "raw_neural_array"
    assert rec.source_status == "discovered_raw_blocked"
    assert rec.readable_for_phase2 is False
    assert "Blocked" in rec.reason_not_read
    assert rec.session_id == "230719"

def test_signal_class_classification_by_tokens(tmp_path):
    arrays_dir = tmp_path / "arrays"
    arrays_dir.mkdir()
    
    spk_file = arrays_dir / "session_230630_spk.npy"
    mua_file = arrays_dir / "session_230630_mua.npy"
    lfp_file = arrays_dir / "session_230630_lfp.npy"
    
    spk_file.touch()
    mua_file.touch()
    lfp_file.touch()
    
    loader = DataLoader()
    index = loader.discover_data_sources(tmp_path)
    
    records_dict = {r.signal_class: r for r in index.records}
    assert "SPK" in records_dict
    assert "MUAe" in records_dict
    assert "LFP" in records_dict
    
    # Also verify get_signal_source_status returns discovered_candidate
    status = loader.get_signal_source_status("230630", "LFP", data_root=tmp_path)
    assert status["status"] == "discovered_candidate"
    assert status["session_id"] == "230630"
    assert status["signal_class"] == "LFP"
    assert status["path"] == str(lfp_file)

def test_cli_skips_cleanly_without_data_root(monkeypatch):
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    cmd = [sys.executable, "scripts/validate_data_source_index.py"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "SKIPPING" in res.stdout

def test_cli_writes_report_to_tmp_path(tmp_path):
    # Setup tmp_path with a dummy manifest JSON
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    m_file = manifests_dir / "session_230630_manifest.json"
    
    manifest_data = {
        "session_id": "230630",
        "subject": "MonkeyA",
        "truth_status": "truth_safe_unverified",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True}
    }
    with open(m_file, "w") as f:
        json.dump(manifest_data, f)
        
    out_file = tmp_path / "report.md"
    cmd = [
        sys.executable, 
        "scripts/validate_data_source_index.py", 
        "--data-root", str(tmp_path), 
        "--out", str(out_file)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    assert res.returncode == 0
    assert out_file.exists()
    report_text = out_file.read_text()
    assert "# Data Source Index Contract Validation Report" in report_text
    assert "session_230630_manifest.json" in report_text
