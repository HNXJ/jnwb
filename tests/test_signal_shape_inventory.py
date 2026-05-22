# tests/test_signal_shape_inventory.py
"""
Target unit and integration tests for Phase A5 Signal Shape and Availability Census.
Uses tmp_path fixtures to avoid any D:/drive or real data dependencies.
"""

import os
import csv
import json
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Import functions from our script
from scripts.build_signal_shape_inventory import (
    infer_signal_class,
    get_expected_dims,
    locate_file_recursively,
    inspect_npy_shape,
    parse_shape_str,
    TRUTH_SAFE_UNVERIFIED
)

def test_infer_signal_class():
    # 1. Detect SPK/SUA/LFP/MUAe signal class from filename tokens
    assert infer_signal_class("session_230630_spk_AAAB.npy") == "SPK"
    assert infer_signal_class("session_230630_spike_AAAB.npy") == "SPK"
    assert infer_signal_class("session_230630_sua_AAAB.npy") == "SPK"
    assert infer_signal_class("session_230630_unit_probe0_AAAB.npy") == "SPK"
    
    assert infer_signal_class("session_230630_lfp_AAAB.npy") == "LFP"
    assert infer_signal_class("session_230630_LFP_AXAB.npy") == "LFP"
    
    assert infer_signal_class("session_230630_muae_AAAB.npy") == "MUAe"
    assert infer_signal_class("session_230630_mua_AXAB.npy") == "MUAe"
    
    assert infer_signal_class("session_230630_behavior.npy") == "behavior"
    assert infer_signal_class("session_230630_eye.npy") == "behavior"
    
    assert infer_signal_class("session_230630_manifest.json") == "metadata"

def test_expected_dimensions():
    # 2. SPK .npy rank-3 shape maps to trial, unit, time
    assert get_expected_dims("SPK") == "trial, unit, time"
    
    # 3. LFP .npy rank-3 shape maps to trial, channel, time
    assert get_expected_dims("LFP") == "trial, channel, time"
    
    # 4. MUAe .npy rank-3 shape maps to trial, channel, time
    assert get_expected_dims("MUAe") == "trial, channel, time"
    
    assert get_expected_dims("behavior") == "None"
    assert get_expected_dims("metadata") == "None"

def test_inspect_npy_shape_rank3(tmp_path):
    # Test valid rank-3 npy file
    arr = np.zeros((10, 5, 100), dtype=np.float32)
    file_path = tmp_path / "test_rank3.npy"
    np.save(file_path, arr)
    
    shape_str, ndim, dtype_str, err = inspect_npy_shape(file_path)
    assert err is None
    assert shape_str == "(10, 5, 100)"
    assert ndim == 3
    assert dtype_str == "float32"

def test_inspect_npy_shape_rank2_unexpected(tmp_path):
    # 5. Rank-2 .npy produces unexpected_rank warning (will be handled by main/inventory logic)
    arr = np.zeros((10, 5), dtype=np.int32)
    file_path = tmp_path / "test_rank2.npy"
    np.save(file_path, arr)
    
    shape_str, ndim, dtype_str, err = inspect_npy_shape(file_path)
    assert err is None
    assert shape_str == "(10, 5)"
    assert ndim == 2
    assert dtype_str == "int32"

def test_parse_shape_str():
    assert parse_shape_str("(10, 5, 100)") == 3
    assert parse_shape_str("(48, 128)") == 2
    assert parse_shape_str("blocked_no_payload_read") is None
    assert parse_shape_str("") is None

def test_locate_file_recursively(tmp_path):
    sub = tmp_path / "sub" / "dir"
    sub.mkdir(parents=True)
    f_path = sub / "find_me.npy"
    f_path.touch()
    
    found = locate_file_recursively(tmp_path, "find_me.npy")
    assert found == f_path
    
    not_found = locate_file_recursively(tmp_path, "absent.npy")
    assert not_found is None

def test_integration_shape_inventory(tmp_path):
    # Setup directories
    data_root = tmp_path / "data"
    data_root.mkdir()
    
    a3_dir = tmp_path / "a3_reports"
    a3_dir.mkdir()
    
    a4_dir = tmp_path / "a4_reports"
    a4_dir.mkdir()
    
    out_dir = tmp_path / "a5_reports"
    
    # 6. .h5/.nwb/.mat/.npz are blocked and not opened (we create files to represent them, but main logic blocks them based on extension)
    (data_root / "ses230630_raw.h5").touch()
    (data_root / "ses230630_raw.mat").touch()
    
    # Create valid rank-3 SPK and LFP .npy files
    spk_arr = np.zeros((40, 10, 1000), dtype=np.float32)
    lfp_arr = np.zeros((40, 32, 2000), dtype=np.float32)
    
    spk_file = data_root / "ses230630_spk_AAAB.npy"
    lfp_file = data_root / "ses230630_lfp_AAAB.npy"
    np.save(spk_file, spk_arr)
    np.save(lfp_file, lfp_arr)
    
    # 5. Rank-2 npy (unexpected rank)
    rank2_arr = np.zeros((50, 100), dtype=np.float32)
    rank2_file = data_root / "ses230630_spk_AXAB.npy"
    np.save(rank2_file, rank2_arr)
    
    # Write mock signal_file_inventory.csv for A3
    signal_file_inventory = a3_dir / "signal_file_inventory.csv"
    with open(signal_file_inventory, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "size_bytes", "signal_class_inferred", "condition_inferred", "shape_if_safe"])
        # Standard valid ones
        writer.writerow(["230630", "ses230630_spk_AAAB.npy", ".npy", "1000", "SPK", "AAAB", ""])
        writer.writerow(["230630", "ses230630_lfp_AAAB.npy", ".npy", "2000", "LFP", "AAAB", ""])
        # Unexpected rank
        writer.writerow(["230630", "ses230630_spk_AXAB.npy", ".npy", "500", "SPK", "AXAB", ""])
        # Blocked formats
        writer.writerow(["230630", "ses230630_raw.h5", ".h5", "999999", "metadata", "None", "blocked_format"])
        writer.writerow(["230630", "ses230630_raw.mat", ".mat", "555555", "metadata", "None", "blocked_format"])
        # 7. Semantic mismatch file (LFP containing SPK token)
        writer.writerow(["230630", "ses230630_spk_in_lfp.npy", ".npy", "1234", "LFP", "AAXB", ""])
        
    # Create the semantic mismatch file
    np.save(data_root / "ses230630_spk_in_lfp.npy", np.zeros((10, 10, 10), dtype=np.float32))
    
    # Run the main script
    from scripts.build_signal_shape_inventory import main as build_inventory
    
    test_args = [
        "build_signal_shape_inventory.py",
        "--data-root", str(data_root),
        "--a3-dir", str(a3_dir),
        "--a4-dir", str(a4_dir),
        "--out-dir", str(out_dir)
    ]
    
    with patch.object(sys, "argv", test_args):
        build_inventory()
        
    # Check outputs exist
    assert (out_dir / "session_signal_availability.csv").exists()
    assert (out_dir / "signal_shape_inventory.csv").exists()
    assert (out_dir / "session_condition_signal_matrix.csv").exists()
    assert (out_dir / "signal_shape_warnings.csv").exists()
    assert (out_dir / "signal_shape_summary.md").exists()
    assert (out_dir / "signal_shape_summary.json").exists()
    
    # Read signal_shape_inventory.csv and verify fields
    shape_inv = []
    with open(out_dir / "signal_shape_inventory.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            shape_inv.append(row)
            
    # Verify we have correct number of rows (6 files)
    assert len(shape_inv) == 6
    
    # Verify SPK AAAB (rank-3)
    spk_row = next(r for r in shape_inv if r["basename"] == "ses230630_spk_AAAB.npy")
    assert spk_row["shape_status"] == "expected_rank3"
    assert spk_row["ndim"] == "3"
    assert spk_row["expected_dims"] == "trial, unit, time"
    # 10. payload_read must be false for all outputs
    assert spk_row["payload_read"] == "False"
    # 11. truth_safe_unverified preserved
    assert spk_row["truth_status"] == TRUTH_SAFE_UNVERIFIED
    
    # Verify LFP AAAB (rank-3)
    lfp_row = next(r for r in shape_inv if r["basename"] == "ses230630_lfp_AAAB.npy")
    assert lfp_row["shape_status"] == "expected_rank3"
    assert lfp_row["ndim"] == "3"
    assert lfp_row["expected_dims"] == "trial, channel, time"
    assert lfp_row["payload_read"] == "False"
    
    # Verify Rank-2 unexpected_rank
    rank2_row = next(r for r in shape_inv if r["basename"] == "ses230630_spk_AXAB.npy")
    assert rank2_row["shape_status"] == "unexpected_rank"
    assert rank2_row["ndim"] == "2"
    assert "unexpected shape" in rank2_row["warnings"]
    
    # Verify blocked formats (.h5 and .mat)
    h5_row = next(r for r in shape_inv if r["basename"] == "ses230630_raw.h5")
    assert h5_row["shape_status"] == "blocked"
    assert h5_row["shape"] == "blocked_no_payload_read"
    assert h5_row["payload_read"] == "False"
    
    # 7. Semantic mismatch is flagged
    mismatch_row = next(r for r in shape_inv if r["basename"] == "ses230630_spk_in_lfp.npy")
    assert mismatch_row["semantic_status"] == "semantic_mismatch"
    assert "contains SPK token" in mismatch_row["warnings"]
    
    # Verify signal_shape_warnings.csv contains unexpected_rank and semantic_mismatch warnings
    warns = []
    with open(out_dir / "signal_shape_warnings.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            warns.append(row)
            
    assert len(warns) >= 2
    assert any(w["warning_type"] == "unexpected_rank" for w in warns)
    assert any(w["warning_type"] == "semantic_mismatch" for w in warns)
    
    # 8. session_signal_availability summarizes counts correctly
    avail = []
    with open(out_dir / "session_signal_availability.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            avail.append(row)
            
    # Should have 3 rows (SPK, MUAe, LFP for session 230630)
    assert len(avail) == 3
    
    # Verify SPK availability summary
    spk_avail = next(r for r in avail if r["signal_class"] == "SPK")
    assert int(spk_avail["n_files"]) == 2
    assert int(spk_avail["n_conditions_with_signal"]) == 2
    assert spk_avail["availability_status"] == "partial"
    assert spk_avail["readiness_for_A6"] == "no" # because not all 12 conditions are complete
    
    # 9. session_condition_signal_matrix preserves condition and signal-class separation
    matrix = []
    with open(out_dir / "session_condition_signal_matrix.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            matrix.append(row)
            
    # Should have 12 rows (one for each condition in session 230630)
    assert len(matrix) == 12
    
    # Verify AAAB has_spk=yes, has_lfp=yes, AXAB has_spk=yes, has_lfp=no, others have no
    aaab_mat = next(r for r in matrix if r["condition"] == "AAAB")
    assert aaab_mat["has_spk"] == "yes"
    assert aaab_mat["has_lfp"] == "yes"
    assert aaab_mat["has_muae"] == "no"
    assert aaab_mat["spk_shape_status"] == "expected_rank3"
    assert aaab_mat["lfp_shape_status"] == "expected_rank3"
    
    axab_mat = next(r for r in matrix if r["condition"] == "AXAB")
    assert axab_mat["has_spk"] == "yes"
    assert axab_mat["has_lfp"] == "no"
    assert axab_mat["spk_shape_status"] == "unexpected_rank"
    assert axab_mat["lfp_shape_status"] == "missing"
    
    # Load signal_shape_summary.json and check truth status
    with open(out_dir / "signal_shape_summary.json", "r", encoding="utf-8") as f:
        summary_json = json.load(f)
    assert summary_json["truth_status"] == TRUTH_SAFE_UNVERIFIED
    
    # Read signal_shape_summary.md and check for TRUTH_SAFE_UNVERIFIED and "No Biological Claims"
    with open(out_dir / "signal_shape_summary.md", "r", encoding="utf-8") as f:
        md_text = f.read()
    assert TRUTH_SAFE_UNVERIFIED in md_text
    assert "No Biological Claims" in md_text
    # 12. No D:/drive hardcoded paths
    assert "D:/drive" not in md_text
    assert "d:/drive" not in md_text
