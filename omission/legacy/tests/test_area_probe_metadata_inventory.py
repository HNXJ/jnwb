# tests/test_area_probe_metadata_inventory.py
"""
Unit and integration tests for Phase A6 Area/Probe/Unit/Channel Metadata Inventory.
Uses tmp_path fixtures to avoid any D:/drive or real data dependencies.
Enforces truth_status: truth_safe_unverified.
"""

import os
import csv
import json
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import patch
import sys

from scripts.build_area_probe_metadata_inventory import (
    normalize_area,
    get_area_group,
    parse_mapping,
    main as build_area_probe_metadata
)

def test_normalize_area():
    assert normalize_area("DP") == "V4"
    assert normalize_area("DP (V4)") == "V4"
    assert normalize_area("V1") == "V1"
    assert normalize_area("V3d") == "V3d"
    assert normalize_area("V3a") == "V3a"
    assert normalize_area("V3") == "V3"

def test_get_area_group():
    assert get_area_group("V1") == "Visual"
    assert get_area_group("V3d") == "Visual"
    assert get_area_group("V3a") == "Visual"
    assert get_area_group("FEF") == "Frontal"
    assert get_area_group("PFC") == "Frontal"
    assert get_area_group("UnknownArea") == "Unknown"

def test_parse_mapping(tmp_path):
    mapping_content = """# Session Area Mapping
| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230630 | 0 | V1, V2 | 128 |
| 230630 | 1 | V3, DP | 128 |
"""
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    mapping = parse_mapping(mapping_file)
    assert "230630" in mapping
    assert 0 in mapping["230630"]
    assert 1 in mapping["230630"]
    
    # Check probe 0
    p0_entries = mapping["230630"][0]
    assert len(p0_entries) == 2
    assert p0_entries[0]["raw_area"] == "V1"
    assert p0_entries[0]["area"] == "V1"
    assert p0_entries[0]["start_ch"] == 0
    assert p0_entries[0]["end_ch"] == 64
    
    # Check probe 1 with DP alias
    p1_entries = mapping["230630"][1]
    assert len(p1_entries) == 2
    assert p1_entries[1]["raw_area"] == "DP"
    assert p1_entries[1]["area"] == "V4" # DP -> V4 alias
    assert p1_entries[1]["start_ch"] == 64
    assert p1_entries[1]["end_ch"] == 128

def test_area_probe_metadata_integration(tmp_path):
    # Set up directory layout
    data_root = tmp_path / "data"
    data_root.mkdir()
    
    metadata_dir = data_root / "metadata"
    metadata_dir.mkdir()
    
    a5_dir = tmp_path / "a5_reports"
    a5_dir.mkdir()
    
    out_dir = tmp_path / "a6_reports"
    
    # 1. Subjects JSON
    subjects_file = tmp_path / "subjects.json"
    subjects_content = {"230630": "SubA", "230719": "SubB"}
    with open(subjects_file, "w") as f:
        json.dump(subjects_content, f)
        
    # 2. Mapping markdown (with explicit equal segmentation rule declared)
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_content = """# Session-Area Mapping
This mapping table uses equal segmentation partitioning. Labels like V1, V2 imply a 50/50 split of the 128 channels.
For a mixed case boundaries are calculated using np.linspace(0, 128, n_labels + 1).

| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230630 | 0 | V1, V2 | 128 |
| 230630 | 1 | V3, V3d, V3a, DP | 128 |
| 230719 | 0 | PFC | 128 |
"""
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    # 3. A5 shape inventory
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    with open(a5_inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "shape", "signal_class_inferred", "condition_inferred"])
        writer.writerow(["230630", "ses230630-probe0-spk-AAAB.npy", ".npy", "(40, 10, 1000)", "SPK", "AAAB"])
        writer.writerow(["230630", "ses230630-probe1-spk-AAAB.npy", ".npy", "(40, 8, 1000)", "SPK", "AAAB"])
        writer.writerow(["230630", "ses230630-lfp-AAAB.npy", ".npy", "(40, 128, 2000)", "LFP", "AAAB"])
        writer.writerow(["230719", "ses230719-probe0-spk-AAAB.npy", ".npy", "(40, 5, 1000)", "SPK", "AAAB"])
        
    # 4. Units CSV for 230630
    units_records = []
    # Probe 0 units (10 units)
    for u in range(10):
        ch = 30 if u < 5 else 80
        units_records.append({
            "unit_id": u,
            "peak_channel_id": ch,
            "snr": 3.5,
            "presence_ratio": 0.99
        })
    # Probe 1 units (8 units, starting at index 10 in units list)
    # unit 10 -> local ch 10 -> V3
    units_records.append({"unit_id": 10, "peak_channel_id": 128 + 10, "snr": 4.0, "presence_ratio": 0.98})
    # unit 11 -> local ch 40 -> V3d
    units_records.append({"unit_id": 11, "peak_channel_id": 128 + 40, "snr": 4.1, "presence_ratio": 0.98})
    # unit 12 -> local ch 70 -> V3a
    units_records.append({"unit_id": 12, "peak_channel_id": 128 + 70, "snr": 4.2, "presence_ratio": 0.98})
    # unit 13 -> local ch 100 -> DP/V4
    units_records.append({"unit_id": 13, "peak_channel_id": 128 + 100, "snr": 4.3, "presence_ratio": 0.98})
    # unit 14 -> peak ch 10 -> belongs to probe 0 (local ch 10), mismatch since probe is 1!
    units_records.append({"unit_id": 14, "peak_channel_id": 10, "snr": 4.4, "presence_ratio": 0.98})
    # unit 15 -> NaN peak channel
    units_records.append({"unit_id": 15, "peak_channel_id": "", "snr": "", "presence_ratio": ""})
    # unit 16, 17 -> outside mapping / unresolved
    units_records.append({"unit_id": 16, "peak_channel_id": 128 + 150, "snr": 1.0, "presence_ratio": 0.5}) # local ch 150
    units_records.append({"unit_id": 17, "peak_channel_id": 999, "snr": 1.0, "presence_ratio": 0.5}) # local ch > 128
    
    units_file = metadata_dir / "units_ses-230630.csv"
    with open(units_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["unit_id", "peak_channel_id", "snr", "presence_ratio"])
        writer.writeheader()
        for r in units_records:
            writer.writerow(r)
            
    # Run A6 script end-to-end (without heuristic fallback)
    test_args = [
        "build_area_probe_metadata_inventory.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--out-dir", str(out_dir),
        "--mapping-file", str(mapping_file),
        "--subjects-file", str(subjects_file),
        "--provenance-confirmed-sessions", "230630"
    ]
    
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    # Verify reports were generated
    assert (out_dir / "session_metadata_inventory.csv").exists()
    assert (out_dir / "probe_area_inventory.csv").exists()
    assert (out_dir / "channel_area_inventory.csv").exists()
    assert (out_dir / "unit_area_inventory.csv").exists()
    assert (out_dir / "signal_axis_semantics_inventory.csv").exists()
    assert (out_dir / "area_mapping_warnings.csv").exists()
    assert (out_dir / "area_probe_metadata_summary.json").exists()
    assert (out_dir / "area_probe_metadata_summary.md").exists()
    
    # Verify DP alias and V3d/V3a distinction
    probe_inv = pd.read_csv(out_dir / "probe_area_inventory.csv")
    
    # DP -> V4 alias
    dp_rows = probe_inv[probe_inv["raw_area_label"] == "DP"]
    assert len(dp_rows) > 0
    assert (dp_rows["canonical_area_label"] == "V4").all()
    assert (dp_rows["alias_applied"] == "yes").all()
    
    # V3d and V3a distinction
    v3d_rows = probe_inv[probe_inv["raw_area_label"] == "V3d"]
    assert len(v3d_rows) > 0
    assert (v3d_rows["canonical_area_label"] == "V3d").all()
    
    v3a_rows = probe_inv[probe_inv["raw_area_label"] == "V3a"]
    assert len(v3a_rows) > 0
    assert (v3a_rows["canonical_area_label"] == "V3a").all()
    
    # Generic V3 becomes unresolved_generic_v3
    v3_rows = probe_inv[probe_inv["raw_area_label"] == "V3"]
    assert len(v3_rows) > 0
    assert (v3_rows["canonical_area_label"] == "V3").all()
    assert (v3_rows["area_resolution_status"] == "unresolved_generic_v3").all()
    
    # Multi-area probe representation (probe 0 spans V1 and V2)
    p0_rows = probe_inv[(probe_inv["session_id"] == 230630) & (probe_inv["probe_id"] == 0)]
    assert len(p0_rows) == 2
    assert set(p0_rows["canonical_area_label"]) == {"V1", "V2"}
    
    # Missing metadata produces unmapped_no_metadata
    units_inv = pd.read_csv(out_dir / "unit_area_inventory.csv")
    s230719_units = units_inv[units_inv["session_id"] == 230719]
    assert len(s230719_units) == 5
    assert (s230719_units["area_resolution_status"] == "unmapped_no_metadata").all()
    
    # Unit 15 has NaN peak channel
    u15_row = units_inv[units_inv["unit_id"] == "ses-230630_probe1_unit5"]
    assert u15_row.iloc[0]["area_resolution_status"] == "unmapped_no_metadata"
    
    # Unit 14 has mismatch probe (peak_channel_id = 10, placed in probe 1 slice)
    u14_row = units_inv[units_inv["unit_id"] == "ses-230630_probe1_unit4"]
    assert u14_row.iloc[0]["area_resolution_status"] == "invalid_probe"
    
    # SPK unit area assignment uses peak/anchor channel if provided
    # unit 0 is peak ch 30 -> V1 (is_multi_area and explicit_equal was true -> metadata_resolved_equal_segment)
    u0_row = units_inv[units_inv["unit_id"] == "ses-230630_probe0_unit0"]
    assert u0_row.iloc[0]["canonical_area_label"] == "V1"
    assert u0_row.iloc[0]["area_resolution_status"] == "metadata_resolved_equal_segment"
    
    # unit 5 is peak ch 80 -> V2
    u5_row = units_inv[units_inv["unit_id"] == "ses-230630_probe0_unit5"]
    assert u5_row.iloc[0]["canonical_area_label"] == "V2"
    
    # unit 10 (u_idx 0 on probe 1) is peak ch 138 -> V3
    u10_row = units_inv[units_inv["unit_id"] == "ses-230630_probe1_unit0"]
    assert u10_row.iloc[0]["canonical_area_label"] == "V3"
    assert u10_row.iloc[0]["area_resolution_status"] == "unresolved_generic_v3"
    
    # unit 11 (u_idx 1 on probe 1) is peak ch 168 -> V3d
    u11_row = units_inv[units_inv["unit_id"] == "ses-230630_probe1_unit1"]
    assert u11_row.iloc[0]["canonical_area_label"] == "V3d"
    assert u11_row.iloc[0]["area_resolution_status"] == "metadata_resolved_equal_segment"
    
    # unit 12 (u_idx 2 on probe 1) is peak ch 198 -> V3a
    u12_row = units_inv[units_inv["unit_id"] == "ses-230630_probe1_unit2"]
    assert u12_row.iloc[0]["canonical_area_label"] == "V3a"
    
    # unit 13 (u_idx 3 on probe 1) is peak ch 228 -> DP/V4
    u13_row = units_inv[units_inv["unit_id"] == "ses-230630_probe1_unit3"]
    assert u13_row.iloc[0]["canonical_area_label"] == "V4"
    
    # LFP channel mapping uses channel metadata boundaries
    ch_inv = pd.read_csv(out_dir / "channel_area_inventory.csv")
    assert len(ch_inv) == 384 # 3 probes * 128 channels
    # probe 0: channels 0-63 are V1, 64-127 are V2
    p0_ch0 = ch_inv[(ch_inv["probe_id"] == 0) & (ch_inv["channel_index"] == 0)].iloc[0]
    assert p0_ch0["canonical_area_label"] == "V1"
    
    p0_ch80 = ch_inv[(ch_inv["probe_id"] == 0) & (ch_inv["channel_index"] == 80)].iloc[0]
    assert p0_ch80["canonical_area_label"] == "V2"
    
    # probe 1: channels 0-31 are V3, 32-63 are V3d, 64-95 are V3a, 96-127 are V4
    p1_ch10 = ch_inv[(ch_inv["probe_id"] == 1) & (ch_inv["channel_index"] == 10)].iloc[0]
    assert p1_ch10["canonical_area_label"] == "V3"
    assert p1_ch10["area_resolution_status"] == "unresolved_generic_v3"
    
    p1_ch40 = ch_inv[(ch_inv["probe_id"] == 1) & (ch_inv["channel_index"] == 40)].iloc[0]
    assert p1_ch40["canonical_area_label"] == "V3d"
    assert p1_ch40["area_resolution_status"] == "metadata_resolved_equal_segment"
    
    # Verify that summary.json exists and contains truth_safe_unverified
    with open(out_dir / "area_probe_metadata_summary.json", "r") as f:
        summary_json = json.load(f)
    assert summary_json["truth_status"] == "truth_safe_unverified"
    assert summary_json["raw_payload_or_npy_payload_read"] is False

def test_area_probe_metadata_inferred_vs_explicit_equal_segmentation(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    a5_dir = tmp_path / "a5_reports"
    a5_dir.mkdir()
    out_dir = tmp_path / "a6_reports"
    
    # Mapping table WITHOUT explicit equal segmentation declaration
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_content = """# Session-Area Mapping
| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230630 | 0 | V1, V2 | 128 |
"""
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    with open(a5_inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "shape", "signal_class_inferred", "condition_inferred"])
        writer.writerow(["230630", "ses230630-probe0-spk-AAAB.npy", ".npy", "(40, 10, 1000)", "SPK", "AAAB"])
        
    test_args = [
        "build_area_probe_metadata_inventory.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--out-dir", str(out_dir),
        "--mapping-file", str(mapping_file),
        "--allow-heuristic"
    ]
    
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    # Read probe inventory and verify that multi-area segment defaults to heuristic_equal_segment
    probe_inv = pd.read_csv(out_dir / "probe_area_inventory.csv")
    assert (probe_inv["area_resolution_status"] == "heuristic_equal_segment").all()

def test_explicit_channel_boundaries(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    a5_dir = tmp_path / "a5_reports"
    a5_dir.mkdir()
    out_dir = tmp_path / "a6_reports"
    
    # Mapping table with PFC (single area -> explicit channel boundaries 0-128 exist)
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_content = """# Session-Area Mapping
| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230630 | 0 | PFC | 128 |
"""
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    with open(a5_inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "shape", "signal_class_inferred", "condition_inferred"])
        writer.writerow(["230630", "ses230630-probe0-spk-AAAB.npy", ".npy", "(40, 10, 1000)", "SPK", "AAAB"])
        
    test_args = [
        "build_area_probe_metadata_inventory.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--out-dir", str(out_dir),
        "--mapping-file", str(mapping_file)
    ]
    
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    # Single-area probe has explicit boundaries, returns metadata_resolved_channel
    probe_inv = pd.read_csv(out_dir / "probe_area_inventory.csv")
    assert (probe_inv["area_resolution_status"] == "metadata_resolved_channel").all()

def test_unit_csv_row_order_mapping_rejected_without_provenance(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    metadata_dir = data_root / "metadata"
    metadata_dir.mkdir()
    a5_dir = tmp_path / "a5_reports"
    a5_dir.mkdir()
    out_dir = tmp_path / "a6_reports"
    
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_content = """# Session-Area Mapping
| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230630 | 0 | PFC | 128 |
"""
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    # 10 units expected from SPK shape, but CSV only has 5 rows -> provenance mismatch!
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    with open(a5_inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "shape", "signal_class_inferred", "condition_inferred"])
        writer.writerow(["230630", "ses230630-probe0-spk-AAAB.npy", ".npy", "(40, 10, 1000)", "SPK", "AAAB"])
        
    units_file = metadata_dir / "units_ses-230630.csv"
    with open(units_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "peak_channel_id", "snr", "presence_ratio"])
        for idx in range(5):
            writer.writerow([idx, 10, 3.5, 0.99])
            
    test_args = [
        "build_area_probe_metadata_inventory.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--out-dir", str(out_dir),
        "--mapping-file", str(mapping_file)
    ]
    
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    # Read units table and verify that it has unresolved_unit_axis_order and unmapped_no_metadata
    units_inv = pd.read_csv(out_dir / "unit_area_inventory.csv")
    assert (units_inv["unit_axis_join_status"] == "unresolved_unit_axis_order").all()
    assert (units_inv["area_resolution_status"] == "unmapped_no_metadata").all()

def test_unresolved_unit_axis_order_blocks_metadata_resolved(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    metadata_dir = data_root / "metadata"
    metadata_dir.mkdir()
    a5_dir = tmp_path / "a5_reports"
    a5_dir.mkdir()
    out_dir = tmp_path / "a6_reports"
    
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_content = """# Session-Area Mapping
| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230630 | 0 | PFC | 128 |
"""
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    # 10 units expected, CSV has 5 rows -> blocks metadata-resolved unit-area mapping
    # But since --allow-heuristic is active, it falls back to heuristic_equal_segment
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    with open(a5_inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "shape", "signal_class_inferred", "condition_inferred"])
        writer.writerow(["230630", "ses230630-probe0-spk-AAAB.npy", ".npy", "(40, 10, 1000)", "SPK", "AAAB"])
        
    units_file = metadata_dir / "units_ses-230630.csv"
    with open(units_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "peak_channel_id", "snr", "presence_ratio"])
        for idx in range(5):
            writer.writerow([idx, 10, 3.5, 0.99])
            
    test_args = [
        "build_area_probe_metadata_inventory.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--out-dir", str(out_dir),
        "--mapping-file", str(mapping_file),
        "--allow-heuristic"
    ]
    
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    units_inv = pd.read_csv(out_dir / "unit_area_inventory.csv")
    assert (units_inv["unit_axis_join_status"] == "unresolved_unit_axis_order").all()
    assert (units_inv["area_resolution_status"] == "heuristic_equal_segment").all()

def test_no_absolute_paths_in_defaults():
    import inspect
    from scripts import build_area_probe_metadata_inventory
    
    # Inspect build_area_probe_metadata_inventory source code
    source = inspect.getsource(build_area_probe_metadata_inventory)
    
    # Check that no hardcoded absolute drive letters are defined as string constants (outside comments/recepits)
    # The default args in parse_args should be relative
    for line in source.splitlines():
        if "default=" in line or "parser.add_argument" in line:
            assert "D:\\" not in line
            assert "C:\\" not in line
            assert "/Users/" not in line

def test_summary_json_contains_truth_safe_unverified(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    a5_dir = tmp_path / "a5_reports"
    a5_dir.mkdir()
    out_dir = tmp_path / "a6_reports"
    
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_content = """# Session-Area Mapping
| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230630 | 0 | PFC | 128 |
"""
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    with open(a5_inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "shape", "signal_class_inferred", "condition_inferred"])
        writer.writerow(["230630", "ses230630-probe0-spk-AAAB.npy", ".npy", "(40, 10, 1000)", "SPK", "AAAB"])
        
    test_args = [
        "build_area_probe_metadata_inventory.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--out-dir", str(out_dir),
        "--mapping-file", str(mapping_file)
    ]
    
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    with open(out_dir / "area_probe_metadata_summary.json", "r") as f:
        summary_json = json.load(f)
        
    assert summary_json["truth_status"] == "truth_safe_unverified"

def test_area_probe_metadata_integration_with_heuristic(tmp_path):
    # Test heuristic path with --allow-heuristic
    data_root = tmp_path / "data"
    data_root.mkdir()
    
    a5_dir = tmp_path / "a5_reports"
    a5_dir.mkdir()
    
    out_dir = tmp_path / "a6_reports"
    
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_content = """# Session-Area Mapping
| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230719 | 0 | V1, V2 | 128 |
"""
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    with open(a5_inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "shape", "signal_class_inferred", "condition_inferred"])
        writer.writerow(["230719", "ses230719-probe0-spk-AAAB.npy", ".npy", "(40, 10, 1000)", "SPK", "AAAB"])
        
    test_args = [
        "build_area_probe_metadata_inventory.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--out-dir", str(out_dir),
        "--mapping-file", str(mapping_file),
        "--allow-heuristic"
    ]
    
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    # Read units table
    units_inv = pd.read_csv(out_dir / "unit_area_inventory.csv")
    assert len(units_inv) == 10
    
    # 10 units on probe 0, V1/V2 mapped.
    # Because start_ch = 0, end_ch = 64 for V1, start_ch = 64, end_ch = 128 for V2
    # u_start for V1 = int(10 * 0/128) = 0, u_end for V1 = int(10 * 64/128) = 5
    # So u_idx 0-4 are V1, 5-9 are V2
    u0 = units_inv[units_inv["unit_index"] == 0].iloc[0]
    assert u0["canonical_area_label"] == "V1"
    assert u0["area_resolution_status"] == "heuristic_equal_segment"
    
    u5 = units_inv[units_inv["unit_index"] == 5].iloc[0]
    assert u5["canonical_area_label"] == "V2"
    assert u5["area_resolution_status"] == "heuristic_equal_segment"

def test_a6_1_provenance_and_safety(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    metadata_dir = data_root / "metadata"
    metadata_dir.mkdir()
    a5_dir = tmp_path / "a5_reports"
    a5_dir.mkdir()
    out_dir = tmp_path / "a6_reports"
    
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_content = """# Session-Area Mapping
| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230630 | 0 | PFC | 128 |
"""
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    # 10 units expected from SPK shape
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    with open(a5_inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "shape", "signal_class_inferred", "condition_inferred"])
        writer.writerow(["230630", "ses230630-probe0-spk-AAAB.npy", ".npy", "(40, 10, 1000)", "SPK", "AAAB"])
        
    # Write a units CSV with matching count of 10 rows
    units_file = metadata_dir / "units_ses-230630.csv"
    with open(units_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["unit_id", "peak_channel_id", "snr", "presence_ratio"])
        for idx in range(10):
            writer.writerow([idx, 10, 3.5, 0.99])
            
    # Run 1: WITHOUT explicit provenance confirmation
    test_args = [
        "build_area_probe_metadata_inventory.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--out-dir", str(out_dir),
        "--mapping-file", str(mapping_file)
    ]
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    units_inv = pd.read_csv(out_dir / "unit_area_inventory.csv")
    assert (units_inv["unit_axis_join_status"] == "row_order_count_matched_unvalidated").all()
    assert (units_inv["manuscript_safe_unit_area"] == False).all()
    assert (units_inv["area_resolution_status"] == "provisional_unit_area_from_count_matched_row_order").all()
    
    # Run 2: WITH command-line provenance confirmation
    test_args_prov = test_args + ["--provenance-confirmed-sessions", "230630"]
    with patch.object(sys, "argv", test_args_prov):
        build_area_probe_metadata()
        
    units_inv_prov = pd.read_csv(out_dir / "unit_area_inventory.csv")
    assert (units_inv_prov["unit_axis_join_status"] == "row_order_provenance_confirmed").all()
    assert (units_inv_prov["manuscript_safe_unit_area"] == True).all()
    assert (units_inv_prov["area_resolution_status"] == "metadata_resolved_channel").all()
    
    # Run 3: WITH provenance JSON file in metadata
    prov_json_file = metadata_dir / "units_ses-230630_provenance.json"
    prov_json_file.write_text('{"provenance_confirmed": true}', encoding="utf-8")
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    units_inv_file = pd.read_csv(out_dir / "unit_area_inventory.csv")
    assert (units_inv_file["unit_axis_join_status"] == "row_order_provenance_confirmed").all()
    assert (units_inv_file["manuscript_safe_unit_area"] == True).all()
    prov_json_file.unlink() # cleanup

def test_a6_1_unit_id_join_preference(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    metadata_dir = data_root / "metadata"
    metadata_dir.mkdir()
    manifests_dir = data_root / "manifests"
    manifests_dir.mkdir()
    a5_dir = tmp_path / "a5_reports"
    a5_dir.mkdir()
    out_dir = tmp_path / "a6_reports"
    
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_content = """# Session-Area Mapping
| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230630 | 0 | PFC | 128 |
"""
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    # 2 units expected from SPK shape
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    with open(a5_inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "shape", "signal_class_inferred", "condition_inferred"])
        writer.writerow(["230630", "ses230630-probe0-spk-AAAB.npy", ".npy", "(40, 2, 1000)", "SPK", "AAAB"])
        
    # Write session manifest JSON with units mapping
    manifest_file = manifests_dir / "session_230630_manifest.json"
    manifest_data = {
        "units": [
            {"probe": 0, "local_index": 0, "unit_id": "unit_A"},
            {"probe": 0, "local_index": 1, "unit_id": "unit_B"}
        ]
    }
    with open(manifest_file, "w") as f:
        json.dump(manifest_data, f)
        
    # Write units CSV with unit_id column matching manifest unit_ids
    units_file = metadata_dir / "units_ses-230630.csv"
    with open(units_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["unit_id", "peak_channel_id", "snr", "presence_ratio"])
        writer.writeheader()
        writer.writerow({"unit_id": "unit_A", "peak_channel_id": 10, "snr": 3.5, "presence_ratio": 0.99})
        writer.writerow({"unit_id": "unit_B", "peak_channel_id": 20, "snr": 3.5, "presence_ratio": 0.99})
        
    test_args = [
        "build_area_probe_metadata_inventory.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--out-dir", str(out_dir),
        "--mapping-file", str(mapping_file)
    ]
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    units_inv = pd.read_csv(out_dir / "unit_area_inventory.csv")
    assert (units_inv["unit_axis_join_status"] == "unit_id_join").all()
    assert (units_inv["manuscript_safe_unit_area"] == True).all()
    assert (units_inv["area_resolution_status"] == "metadata_resolved_channel").all()

def test_a6_1_summary_json_denominators(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    metadata_dir = data_root / "metadata"
    metadata_dir.mkdir()
    a5_dir = tmp_path / "a5_reports"
    a5_dir.mkdir()
    out_dir = tmp_path / "a6_reports"
    
    mapping_file = tmp_path / "session-area-mapping.md"
    mapping_content = """# Session-Area Mapping
| Session | Probe | Area | Total Ch |
| :--- | :--- | :--- | :--- |
| 230630 | 0 | PFC | 128 |
"""
    mapping_file.write_text(mapping_content, encoding="utf-8")
    
    a5_inventory_path = a5_dir / "signal_shape_inventory.csv"
    with open(a5_inventory_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["session_id", "basename", "extension", "shape", "signal_class_inferred", "condition_inferred"])
        writer.writerow(["230630", "ses230630-probe0-spk-AAAB.npy", ".npy", "(40, 5, 1000)", "SPK", "AAAB"])
        
    units_file = metadata_dir / "units_ses-230630.csv"
    with open(units_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["unit_id", "peak_channel_id", "snr", "presence_ratio"])
        for idx in range(5):
            writer.writerow([idx, 10, 3.5, 0.99])
            
    test_args = [
        "build_area_probe_metadata_inventory.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--out-dir", str(out_dir),
        "--mapping-file", str(mapping_file)
    ]
    with patch.object(sys, "argv", test_args):
        build_area_probe_metadata()
        
    with open(out_dir / "area_probe_metadata_summary.json", "r") as f:
        summary_json = json.load(f)
        
    assert summary_json["truth_status"] == "truth_safe_unverified"
    
    # Check that split denominator counts are present and populated
    assert "probe_area_resolution_status_counts" in summary_json
    assert "lfp_channel_area_resolution_status_counts" in summary_json
    assert "spk_unit_area_resolution_status_counts" in summary_json
    assert "unit_axis_join_status_counts" in summary_json
    assert "unit_area_manuscript_safe_counts" in summary_json
    
    assert summary_json["probe_area_resolution_status_counts"]["metadata_resolved_channel"] == 1
    assert summary_json["spk_unit_area_resolution_status_counts"]["provisional_unit_area_from_count_matched_row_order"] == 5
    assert summary_json["unit_axis_join_status_counts"]["row_order_count_matched_unvalidated"] == 5
    assert summary_json["unit_area_manuscript_safe_counts"]["false"] == 5
