# tests/test_trial_count_validation.py
"""
Target unit tests for Phase A4 session x condition trial-count validation.
Uses tmp_path fixtures to avoid any D:/drive or real data dependencies.
"""

import os
import csv
import json
import pytest
from pathlib import Path
from unittest.mock import patch
import sys

# Import helpers from our script
from scripts.build_trial_count_validation import (
    get_condition_family,
    get_omission_position,
    get_matched_control,
    find_trial_count_sources,
    extract_trial_counts
)

def test_condition_helpers():
    # 1. Family mappings
    assert get_condition_family("AAAB") == "A-family"
    assert get_condition_family("AXAB") == "A-family"
    assert get_condition_family("BXBA") == "B-family"
    assert get_condition_family("RRRX") == "R-family"
    assert get_condition_family("UNKNOWN") == "Unknown"
    
    # 2. Omission mappings
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
    
    # 3. Matched control mappings
    assert get_matched_control("AXAB") == "AAAB"
    assert get_matched_control("BXBA") == "BBBA"
    assert get_matched_control("RXRR") == "RRRR"
    assert get_matched_control("AAAB") == "AAAB"

def test_extract_trial_counts_json(tmp_path):
    # Setup mock session manifest JSON file
    manifest_data = {
        "session_id": "230630",
        "conditions": [
            {"code": "AXAB", "trial_count": 40},
            {"code": "AAAB", "trial_count": 45}
        ]
    }
    json_path = tmp_path / "session_230630_manifest.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)
        
    counts = extract_trial_counts(json_path, "json", "230630")
    assert counts["AXAB"] == 40
    assert counts["AAAB"] == 45
    
    # Cross session pollution guard test
    counts_wrong_session = extract_trial_counts(json_path, "json", "230719")
    assert not counts_wrong_session

def test_extract_trial_counts_json_flat(tmp_path):
    # Setup mock flat trial counts json structure
    manifest_data = {
        "session_id": "230630",
        "trial_counts": {
            "AAAB": 50,
            "AXAB": 48
        }
    }
    json_path = tmp_path / "trial_counts_230630.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)
        
    counts = extract_trial_counts(json_path, "json", "230630")
    assert counts["AAAB"] == 50
    assert counts["AXAB"] == 48

def test_extract_trial_counts_csv(tmp_path):
    # Setup mock CSV metadata file
    csv_path = tmp_path / "trial_counts_230630.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "condition", "trial_count"])
        writer.writerow(["230630", "AXAB", "40"])
        writer.writerow(["230630", "AAAB", "42"])
        writer.writerow(["230719", "AXAB", "50"]) # different session
        
    counts = extract_trial_counts(csv_path, "csv", "230630")
    assert counts["AXAB"] == 40
    assert counts["AAAB"] == 42
    assert "230719" not in counts

def test_full_validation_run(tmp_path):
    # Setup mock workspace structure
    data_root = tmp_path / "data"
    data_root.mkdir()
    
    a3_dir = tmp_path / "a3_reports"
    a3_dir.mkdir()
    
    out_dir = tmp_path / "a4_reports"
    
    # 1. Create a dummy session_inventory.csv in A3
    session_inventory = a3_dir / "session_inventory.csv"
    with open(session_inventory, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "warnings"])
        writer.writerow(["999999", "Probe 2 uses generic V3."])
        writer.writerow(["888888", "None"])
        
    # 2. Create a dummy condition_inventory.csv in A3
    condition_inventory = a3_dir / "condition_inventory.csv"
    with open(condition_inventory, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "condition", "signal_classes_detected", "source_basenames"])
        # session 999999 has all conditions present via files (12 conditions)
        for cond in ["AAAB", "AXAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", "RRRR", "RXRR", "RRXR", "RRRX"]:
            writer.writerow(["999999", cond, "LFP,SPK", f"ses999999-{cond}.npy"])
        # session 888888 is missing AXAB (only 11 conditions present)
        for cond in ["AAAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", "RRRR", "RXRR", "RRXR", "RRRX"]:
            writer.writerow(["888888", cond, "LFP,SPK", f"ses888888-{cond}.npy"])
            
    # 3. Create explicit manifest JSON for 999999 with observed counts
    # This manifest is placed under data_root/manifests directory
    manifests_folder = data_root / "manifests"
    manifests_folder.mkdir()
    manifest_999999 = manifests_folder / "999999.json"
    manifest_data = {
        "session_id": "999999",
        "conditions": [
            {"code": cond, "trial_count": 40 if cond != "AAAB" else 42}
            for cond in ["AAAB", "AXAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", "RRRR", "RXRR", "RRXR", "RRRX"]
        ]
    }
    with open(manifest_999999, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)
        
    # 4. Create an ambiguous trial counts CSV for 999999 as well, to trigger ambiguous counts if both scanned
    # But wait, we want to check if ambiguous is successfully triggered when multiple sources exist with inconsistent counts.
    # Let's put a conflicting source in a different location in data_root
    conflicting_csv = data_root / "session_999999_trial_counts.csv"
    with open(conflicting_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "condition", "trial_count"])
        # conflict on AXAB: 50 instead of 40
        writer.writerow(["999999", "AXAB", "50"])
        # match on others to not pollute too much
        for cond in ["AAAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", "RRRR", "RXRR", "RRXR", "RRRX"]:
            writer.writerow(["999999", cond, "40" if cond != "AAAB" else "42"])
            
    # Run the main validation function
    test_args = [
        "build_trial_count_validation.py",
        "--data-root", str(data_root),
        "--a3-dir", str(a3_dir),
        "--out-dir", str(out_dir)
    ]
    
    with patch.object(sys, "argv", test_args):
        from scripts.build_trial_count_validation import main as validation_main
        validation_main()
        
    # Assert output files exist
    assert (out_dir / "trial_count_matrix.csv").exists()
    assert (out_dir / "condition_balance_summary.csv").exists()
    assert (out_dir / "session_condition_completeness.csv").exists()
    assert (out_dir / "trial_count_warnings.csv").exists()
    assert (out_dir / "trial_count_validation_summary.md").exists()
    assert (out_dir / "trial_count_validation_summary.json").exists()
    
    # Check that truth_safe_unverified is preserved in output files
    with open(out_dir / "trial_count_validation_summary.json", "r") as f:
        summary_json = json.load(f)
        assert summary_json["truth_status"] == "truth_safe_unverified"
        assert summary_json["total_sessions"] == 2
        
    summary_md = (out_dir / "trial_count_validation_summary.md").read_text()
    assert "truth_safe_unverified" in summary_md
    assert "No Biological Claims" in summary_md
    
    # Read the matrix to verify conditions status
    matrix_rows = []
    with open(out_dir / "trial_count_matrix.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            matrix_rows.append(row)
            
    # Verify ambiguous trial count for AXAB in 999999 (because CSV has 50 and JSON has 40)
    axab_rows_999999 = [r for r in matrix_rows if r["session_id"] == "999999" and r["condition"] == "AXAB"]
    assert len(axab_rows_999999) == 1
    assert axab_rows_999999[0]["trial_count_status"] == "ambiguous"
    assert axab_rows_999999[0]["trial_count"] == "" # empty
    
    # Verify observed count for AAXB in 999999 (it matched in CSV and JSON, or only exists in JSON manifest)
    # Actually it's 40 in both, so it should be observed and equal to 40
    aaxb_rows_999999 = [r for r in matrix_rows if r["session_id"] == "999999" and r["condition"] == "AAXB"]
    assert len(aaxb_rows_999999) == 1
    assert aaxb_rows_999999[0]["trial_count_status"] == "observed"
    assert aaxb_rows_999999[0]["trial_count"] == "40"
    
    # Verify inferred_from_file_inventory for session 888888 (no explicit manifest JSON/CSV exists for 888888)
    # The condition inventories exist, so AXAB is missing, and others are inferred_from_file_inventory
    matrix_rows_888888 = [r for r in matrix_rows if r["session_id"] == "888888"]
    axab_row_888888 = [r for r in matrix_rows_888888 if r["condition"] == "AXAB"]
    assert len(axab_row_888888) == 1
    assert axab_row_888888[0]["trial_count_status"] == "missing"
    assert axab_row_888888[0]["trial_count"] == ""
    
    aaxb_row_888888 = [r for r in matrix_rows_888888 if r["condition"] == "AAXB"]
    assert len(aaxb_row_888888) == 1
    assert aaxb_row_888888[0]["trial_count_status"] == "inferred_from_file_inventory"
    assert aaxb_row_888888[0]["trial_count"] == ""
    
    # Check session completeness csv
    completeness_rows = []
    with open(out_dir / "session_condition_completeness.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            completeness_rows.append(row)
            
    c_999999 = [r for r in completeness_rows if r["session_id"] == "999999"][0]
    assert c_999999["n_conditions_detected"] == "12"
    assert c_999999["readiness_for_A5"] == "yes"
    assert c_999999["has_all_p2_omissions"] == "yes"
    assert c_999999["has_all_p3_omissions"] == "yes"
    assert c_999999["has_all_p4_omissions"] == "yes"
    
    c_888888 = [r for r in completeness_rows if r["session_id"] == "888888"][0]
    assert c_888888["n_conditions_detected"] == "11"
    assert c_888888["readiness_for_A5"] == "no"
    assert c_888888["has_all_p2_omissions"] == "no" # missing AXAB
    assert c_888888["has_all_p3_omissions"] == "yes"
    assert c_888888["has_all_p4_omissions"] == "yes"
