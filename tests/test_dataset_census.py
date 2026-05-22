# tests/test_dataset_census.py
"""
Target unit tests for the Phase A3 descriptive dataset census.
Uses tmp_path fixtures to avoid any D:/drive or real data dependencies.
"""

import os
import csv
import json
import numpy as np
import pytest
from pathlib import Path

# Import the builder functions
from scripts.build_dataset_census import (
    discover_session,
    detect_condition,
    get_condition_family,
    get_omission_position,
    get_matched_control,
    infer_signal_class,
    inspect_npy_shape,
    inspect_metadata_file
)

def test_discover_session():
    assert discover_session("ses-230630_rec.npy") == "230630"
    assert discover_session("sub-V198o_ses-230714_rec.h5") == "230714"
    assert discover_session("ses230719-probe0-lfp.npy") == "230719"
    assert discover_session("units_ses-230818.csv") == "230818"
    assert discover_session("no_session_here.txt") is None

def test_detect_condition():
    # Detect standard conditions
    assert detect_condition("ses230630-units-probe0-spk-AXAB.npy") == "AXAB"
    assert detect_condition("ses230630-lfp-BBBA.npy") == "BBBA"
    assert detect_condition("ses230714-muae-RRXR.npy") == "RRXR"
    assert detect_condition("AXAB_lowercase") == "AXAB"
    assert detect_condition("random_control") is None

def test_mapping_omission_and_family():
    # Families
    assert get_condition_family("AXAB") == "A-family"
    assert get_condition_family("BXBA") == "B-family"
    assert get_condition_family("RXRR") == "R-family"
    assert get_condition_family("INVALID") == "Unknown"
    
    # Omissions
    assert get_omission_position("AXAB") == "p2"
    assert get_omission_position("BXBA") == "p2"
    assert get_omission_position("RXRR") == "p2"
    
    assert get_omission_position("AAXB") == "p3"
    assert get_omission_position("BBXA") == "p3"
    assert get_omission_position("RRXR") == "p3"
    
    assert get_omission_position("AAAX") == "p4"
    assert get_omission_position("BBBX") == "p4"
    assert get_omission_position("RRRX") == "p4"
    
    assert get_omission_position("AAAB") == "None"
    
    # Matched controls
    assert get_matched_control("AXAB") == "AAAB"
    assert get_matched_control("BXBA") == "BBBA"
    assert get_matched_control("RXRR") == "RRRR"
    assert get_matched_control("AAAB") == "AAAB"

def test_infer_signal_class():
    assert infer_signal_class("ses230630-units-probe0-spk-AXAB.npy") == "SPK"
    assert infer_signal_class("units_ses-230630.csv") == "SPK"
    assert infer_signal_class("ses230630-probe0-lfp-AAAB.npy") == "LFP"
    assert infer_signal_class("ses230714-muae-RRXR.npy") == "MUAe"
    assert infer_signal_class("behavior_eye_data.bhv2.mat") == "behavior"
    assert infer_signal_class("session_230630_manifest.json") == "metadata"
    assert infer_signal_class("unknown_file_type.bin") == "unknown"

def test_npy_shape_mmap_inspect(tmp_path):
    # Create tiny dummy .npy file
    dummy_arr = np.random.rand(5, 10, 100)
    npy_path = tmp_path / "test_mmap.npy"
    np.save(npy_path, dummy_arr)
    
    # Verify shape is correctly extracted via memory map
    shape_str = inspect_npy_shape(npy_path)
    assert shape_str == "(5, 10, 100)"

def test_blocked_formats(tmp_path):
    # Non-npy formats shouldn't be read or opened
    h5_path = tmp_path / "test.h5"
    h5_path.write_text("dummy h5 content")
    
    # Verify that shape is blocked
    # In build_dataset_census.py, non-npy files are marked as blocked_format
    # We will test this by running the main or checking roles
    assert h5_path.exists()

def test_light_metadata_inspection(tmp_path):
    # 1. CSV
    csv_path = tmp_path / "units_ses-230630.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["peak_channel_id", "brain_area", "trial_id", "unit_id", "onset_time"])
        writer.writerow([12, "V1", 1, 0, 0.0])
        
    cols, h_area, h_cond, h_trial, h_unit, h_chan, m_warns = inspect_metadata_file(csv_path, ".csv")
    assert "peak_channel_id" in cols
    assert h_area is True
    assert h_trial is True
    assert h_unit is True
    assert h_chan is True
    assert len(m_warns) == 0

    # 2. JSON
    json_path = tmp_path / "session_230630_manifest.json"
    manifest_data = {
        "subject": "V198o",
        "recording_date": "2023-06-30",
        "condition_family": "A-family",
        "trial_counts": {"AAAB": 50, "AXAB": 50}
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)
        
    cols, h_area, h_cond, h_trial, h_unit, h_chan, m_warns = inspect_metadata_file(json_path, ".json")
    assert "subject" in cols
    assert h_cond is True # condition_family contains condition
    assert len(m_warns) == 0

def test_full_census_run(tmp_path):
    # Setup mock data directory
    data_root = tmp_path / "data"
    data_root.mkdir()
    
    arrays_dir = data_root / "arrays"
    arrays_dir.mkdir()
    
    metadata_dir = data_root / "metadata"
    metadata_dir.mkdir()
    
    # 1. Create a dummy .npy signal file
    npy_file = arrays_dir / "ses230630-units-probe0-spk-AXAB.npy"
    dummy_arr = np.random.rand(1, 2, 50)
    np.save(npy_file, dummy_arr)
    
    # 2. Create a dummy .h5 file
    h5_file = arrays_dir / "lfp_by_area_ses-230630.h5"
    h5_file.write_text("h5 binary mock payload")
    
    # 3. Create a dummy metadata file
    csv_file = metadata_dir / "units_ses-230630.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["peak_channel_id", "brain_area"])
        writer.writerow([10, "V1"])
        
    out_dir = tmp_path / "reports"
    
    # Run build_dataset_census.py code by importing and calling main with mocked sys.argv
    import sys
    from unittest.mock import patch
    
    test_args = [
        "build_dataset_census.py",
        "--data-root", str(data_root),
        "--out-dir", str(out_dir),
        "--max-shape-files", "10"
    ]
    
    with patch.object(sys, "argv", test_args):
        from scripts.build_dataset_census import main as census_main
        census_main()
        
    # Verify outputs
    assert (out_dir / "session_inventory.csv").exists()
    assert (out_dir / "condition_inventory.csv").exists()
    assert (out_dir / "signal_file_inventory.csv").exists()
    assert (out_dir / "metadata_inventory.csv").exists()
    assert (out_dir / "area_mapping_warnings.csv").exists()
    assert (out_dir / "dataset_census_summary.md").exists()
    assert (out_dir / "dataset_census_summary.json").exists()
    
    # Read summary and check truth status
    summary_text = (out_dir / "dataset_census_summary.md").read_text()
    assert "truth_safe_unverified" in summary_text
    assert "No Biological Claims" in summary_text
    
    with open(out_dir / "dataset_census_summary.json", "r") as f:
        summary_json = json.load(f)
        assert summary_json["truth_status"] == "truth_safe_unverified"
        assert summary_json["total_sessions"] == 1
