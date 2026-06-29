# tests/test_manifest_scaffold.py
"""
Phase 2K session manifest validator/scaffold tests.
"""

import os
import sys
import json
import csv
import pytest
import tempfile
import subprocess
from pathlib import Path

from src.analysis.io.loader import DataLoader
from src.analysis.contracts.manifest_scaffold import ManifestScaffoldCandidate, ManifestScaffoldReport
from src.analysis.contracts.constants import TRUTH_SAFE_UNVERIFIED

def test_no_data_root_returns_skipped_report(monkeypatch):
    # 1. No OMISSION_DATA_ROOT returns skipped report.
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    loader = DataLoader()
    report = loader.scaffold_session_manifests(data_root=None)
    assert report.skipped is True
    assert not report.candidates
    assert report.truth_status == TRUTH_SAFE_UNVERIFIED

def test_json_metadata_produces_candidate(tmp_path):
    # 2. tmp_path with metadata JSON produces one candidate.
    # Write a simple metadata JSON file
    m_json = tmp_path / "metadata_ses-230630.json"
    meta_data = {
        "session_id": "230630",
        "subject": "MockSubject",
        "recording_date": "2026-05-21",
        "signal_availability": {"SPK": True, "MUAe": False, "LFP": True}
    }
    m_json.write_text(json.dumps(meta_data))
    
    loader = DataLoader()
    report = loader.scaffold_session_manifests(data_root=str(tmp_path))
    assert report.skipped is False
    assert len(report.candidates) == 1
    
    cand = report.candidates[0]
    assert cand.session_id == "230630"
    assert cand.inferred_subject == "MockSubject"
    assert cand.inferred_recording_date == "2026-05-21"
    assert cand.signal_availability["SPK"] is True
    assert cand.signal_availability["LFP"] is True
    assert cand.detected_fields["subject"] is True

def test_csv_metadata_source_detected(tmp_path):
    # 3. tmp_path with CSV metadata source is detected.
    # 6. DP area token is normalized or warned according to constants.
    # 7. Generic V3 produces unresolved warning.
    m_csv = tmp_path / "units_ses-230630.csv"
    with open(m_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["unit_id", "peak_channel_id", "local_idx", "area"])
        writer.writerow(["230630_unit_0", "12", "0", "DP"])
        writer.writerow(["230630_unit_1", "34", "1", "V3"])
        writer.writerow(["230630_unit_2", "56", "2", "V1"])

    loader = DataLoader()
    report = loader.scaffold_session_manifests(data_root=str(tmp_path))
    assert len(report.candidates) == 1
    cand = report.candidates[0]
    assert cand.session_id == "230630"
    assert cand.detected_fields["unit_counts"] is True
    
    # Verify DP warning
    assert any("DP" in w and "normalize" in w for w in cand.warnings)
    # Verify V3 unresolved warning
    assert any("V3" in w and "UNRESOLVED" in w for w in cand.warnings)

def test_raw_files_ignored_and_not_opened(tmp_path):
    # 4. Raw .nwb, .mat, .h5, .npy, .npz files are ignored/not opened.
    # Create invalid raw files that would crash if read/opened
    for ext in [".nwb", ".mat", ".h5", ".npy", ".npz"]:
        raw_file = tmp_path / f"ses-230630_data{ext}"
        raw_file.write_bytes(b"INVALID RAW DATA TRASH")
        
    loader = DataLoader()
    # If the reader attempted to open/read any raw files, it would raise an exception.
    # It must scan them only by extension to detect signal availability.
    report = loader.scaffold_session_manifests(data_root=str(tmp_path))
    assert not report.errors
    # Signal availability should not be inferred to True from unresolvable names,
    # or if we named it lfp/spk, it would. Let's see:
    cand = report.candidates[0]
    assert cand.session_id == "230630"
    assert cand.signal_availability["SPK"] is False

def test_missing_fields_reported(tmp_path):
    # 5. Candidate with missing required fields reports warnings/errors, not fake values.
    # Write a metadata JSON missing subject and recording_date
    m_json = tmp_path / "metadata_ses-230630.json"
    meta_data = {
        "session_id": "230630"
    }
    m_json.write_text(json.dumps(meta_data))
    
    loader = DataLoader()
    report = loader.scaffold_session_manifests(data_root=str(tmp_path))
    cand = report.candidates[0]
    assert cand.inferred_subject is None
    assert cand.inferred_recording_date is None
    assert any("Missing required field: subject" in w for w in cand.warnings)
    assert any("Missing field: recording_date" in w for w in cand.warnings)

def test_cli_out_writes_only_to_tmp_path(tmp_path, monkeypatch):
    # 8. --out writes only to tmp_path report.
    # 9. Script never writes data/manifests.
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    m_json = tmp_path / "metadata_ses-230630.json"
    m_json.write_text(json.dumps({"session_id": "230630"}))
    
    out_file = tmp_path / "my_report.md"
    
    cmd = [
        sys.executable,
        "scripts/scaffold_session_manifests.py",
        "--data-root", str(tmp_path),
        "--out", str(out_file)
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent)
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert res.returncode == 0
    assert out_file.exists()
    
    # Check that it never created data/manifests directory
    assert not Path("data/manifests").exists()

def test_no_private_paths_and_no_biological_claims(tmp_path):
    # 10. No test uses D:/drive.
    # 11. No biological claims or validation statuses beyond truth_safe_unverified.
    m_json = tmp_path / "metadata_ses-230630.json"
    m_json.write_text(json.dumps({"session_id": "230630", "subject": "MockSubject"}))
    
    loader = DataLoader()
    report = loader.scaffold_session_manifests(data_root=str(tmp_path))
    assert "D:/drive" not in report.data_root
    assert report.truth_status == TRUTH_SAFE_UNVERIFIED
    for cand in report.candidates:
        assert cand.truth_status == TRUTH_SAFE_UNVERIFIED
        assert not any("biological" in w.lower() for w in cand.warnings)

def test_cli_skip_exits_0(monkeypatch):
    # 12. CLI skip exits 0.
    monkeypatch.delenv("OMISSION_DATA_ROOT", raising=False)
    cmd = [sys.executable, "scripts/scaffold_session_manifests.py"]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent)
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    assert res.returncode == 0
    assert "SKIPPING" in res.stdout
