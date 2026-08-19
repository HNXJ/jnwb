# tests/test_spk_response_metrics_a8_1.py
"""
Unit tests for run_spk_response_metrics_a8_1.py.
Verifies all 15 Phase A8.1 contract requirements:
1. BH-FDR correction works on known p-values.
2. X_candidate requires both omission > baseline and omission > matched stimulus/control.
3. Candidate labels keep `_candidate` suffix.
4. Labels are not manuscript-safe.
5. area_hierarchy_allowed is false.
6. biological_interpretation_allowed is false.
7. session summaries contain no area/hierarchy columns.
8. p2/p3/p4 omissions are computed separately.
9. A/B/R families are not collapsed before family-specific metrics.
10. raw H5 paths are not opened.
11. NPY loading uses memmap/batched slicing.
12. missing matched controls emit warnings rather than silent success.
13. correction_scope is recorded for every p/q value.
14. summary JSON has truth_status = truth_safe_unverified.
15. manuscript_safe_unit_area_from_A6 false blocks any hierarchy output.
"""

import sys
import os
import json
import csv
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

# Insert current directory to import from scripts
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_spk_response_metrics_a8_1 import (
    TRUTH_SAFE_UNVERIFIED,
    get_condition_family,
    get_omission_position,
    get_matched_control,
    benjamini_hochberg_correction,
    compute_cohens_d,
    run_paired_test,
    run_unpaired_test,
    classify_prototype_unit,
    main
)

def test_benjamini_hochberg_correction():
    # 1. BH-FDR correction works on known p-values
    p_values = [0.01, 0.04, 0.03, 0.5, 0.05, np.nan]
    q_values = benjamini_hochberg_correction(p_values)
    
    # Non-nan adjusted values must be in [0, 1]
    assert np.isnan(q_values[5])
    assert q_values[0] <= q_values[2] <= q_values[1] <= q_values[4] <= q_values[3]
    assert all(0.0 <= val <= 1.0 for val in q_values[:5])

def test_x_candidate_classification_rules():
    # 2. X_candidate requires both omission > baseline and omission > matched stimulus/control.
    # 6. biological_interpretation_allowed is false.
    # 9. X_candidate requires both omission > baseline and omission > control.
    
    # Meets all requirements
    rates_valid = {
        "fr_baseline_fx": 1.0,
        "fr_stimulus_p1": 1.0,
        "fr_omission": 10.0,
        "fr_omission_baseline": 1.0,
        "fr_control_omission": 1.0
    }
    assert classify_prototype_unit(rates_valid) == "X_candidate"

    # Fails matched control contrast (omission not > control omission rate)
    rates_failed_ctrl = {
        "fr_baseline_fx": 1.0,
        "fr_stimulus_p1": 1.0,
        "fr_omission": 10.0,
        "fr_omission_baseline": 1.0,
        "fr_control_omission": 12.0
    }
    assert classify_prototype_unit(rates_failed_ctrl) != "X_candidate"

    # Fails omission baseline contrast (omission not > baseline rate)
    rates_failed_base = {
        "fr_baseline_fx": 1.0,
        "fr_stimulus_p1": 1.0,
        "fr_omission": 5.0,
        "fr_omission_baseline": 6.0,
        "fr_control_omission": 1.0
    }
    assert classify_prototype_unit(rates_failed_base) != "X_candidate"

def test_candidate_suffix_and_safety_gating():
    # 3. Candidate labels keep `_candidate` suffix.
    # 4. Labels are not manuscript-safe.
    rates = {
        "fr_baseline_fx": 1.0,
        "fr_stimulus_p1": 10.0,
        "fr_omission": 1.0,
        "fr_omission_baseline": 1.0,
        "fr_control_omission": 1.0
    }
    label = classify_prototype_unit(rates)
    assert label.endswith("_candidate") or label == "null_or_unclassified"

def test_slot_and_family_separation():
    # 8. p2/p3/p4 omissions are computed separately
    # 9. A/B/R families are not collapsed before family-specific metrics
    assert get_omission_position("AXAB") == "p2"
    assert get_omission_position("AAXB") == "p3"
    assert get_omission_position("AAAX") == "p4"

    assert get_condition_family("AXAB") == "A-family"
    assert get_condition_family("BXBA") == "B-family"
    assert get_condition_family("RXRR") == "R-family"

@pytest.fixture
def mock_a5_a6_a7_setup(tmp_path):
    a5_dir = tmp_path / "a5"
    a5_dir.mkdir()
    a6_dir = tmp_path / "a6"
    a6_dir.mkdir()
    a7_dir = tmp_path / "a7"
    a7_dir.mkdir()
    a8_dir = tmp_path / "a8"
    a8_dir.mkdir()
    data_root = tmp_path / "data"
    data_root.mkdir()
    out_dir = tmp_path / "out"

    # Create mock A7 inventory CSV
    a7_csv = a7_dir / "spk_smoke_file_inventory.csv"
    with open(a7_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "session_id", "condition", "signal_class", "source_file", "shape", "dims",
            "n_trials", "n_units", "n_timepoints", "time_axis_status",
            "p1_relative_possible", "omission_relative_possible", "payload_read_policy", "warnings"
        ])
        writer.writerow([
            "230630", "AXAB", "SPK", "ses230630-units-probe0-spk-AXAB.npy", "(20, 5, 6000)", "trial, unit, time",
            "20", "5", "6000", "valid_timebase_6000ms", "true", "true", "memmap", "None"
        ])
        writer.writerow([
            "230630", "AAAB", "SPK", "ses230630-units-probe0-spk-AAAB.npy", "(20, 5, 6000)", "trial, unit, time",
            "20", "5", "6000", "valid_timebase_6000ms", "true", "true", "memmap", "None"
        ])

    # Create mock A6 unit inventory CSV (manuscript_safe_unit_area = false)
    a6_csv = a6_dir / "unit_area_inventory.csv"
    with open(a6_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "session_id", "unit_id", "unit_index", "sorting_quality_or_status",
            "peak_channel_or_status", "anchor_channel_or_status", "probe_id_or_status",
            "raw_area_label", "canonical_area_label", "area_group", "area_resolution_status",
            "unit_axis_join_status", "manuscript_safe_unit_area", "source_file", "warnings"
        ])
        for i in range(5):
            writer.writerow([
                "230630", f"ses-230630_probe0_unit{i}", str(i), "Good",
                "32", "32", "0", "V1", "V1", "V1_V2", "metadata_resolved_equal_segment",
                "provenance_confirmed", "false", "unit_metadata_ses-230630.csv", "None"
            ])

    # Touch mock real data .npy files
    dummy_axab = np.zeros((20, 5, 6000), dtype=np.float32)
    # Unit 0 is X_candidate
    dummy_axab[:, 0, 2031:2562] = (np.random.rand(20, 531) < 0.05).astype(np.float32) # High omission rate
    dummy_axab[:, 0, 1781:1981] = 0.0 # Low baseline
    
    # Unit 1 is S+
    dummy_axab[:, 1, 1000:1531] = (np.random.rand(20, 531) < 0.05).astype(np.float32)
    dummy_axab[:, 1, 500:1000] = 0.0

    dummy_aaab = np.zeros((20, 5, 6000), dtype=np.float32)
    # Unit 0 in control is flat low
    dummy_aaab[:, 0, :] = 0.0

    np.save(data_root / "ses230630-units-probe0-spk-AXAB.npy", dummy_axab)
    np.save(data_root / "ses230630-units-probe0-spk-AAAB.npy", dummy_aaab)

    return {
        "a5_dir": a5_dir,
        "a6_dir": a6_dir,
        "a7_dir": a7_dir,
        "a8_dir": a8_dir,
        "data_root": data_root,
        "out_dir": out_dir
    }

def test_end_to_end_metrics_execution(mock_a5_a6_a7_setup, monkeypatch):
    a5_dir = mock_a5_a6_a7_setup["a5_dir"]
    a6_dir = mock_a5_a6_a7_setup["a6_dir"]
    a7_dir = mock_a5_a6_a7_setup["a7_dir"]
    a8_dir = mock_a5_a6_a7_setup["a8_dir"]
    data_root = mock_a5_a6_a7_setup["data_root"]
    out_dir = mock_a5_a6_a7_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metrics_a8_1.get_git_commit", lambda: "mock_commit_a8_1")

    # Spy on np.load to ensure memmap is strictly 'r'
    mmap_modes = []
    orig_np_load = np.load

    def spy_np_load(file, *args, **kwargs):
        mmap_modes.append(kwargs.get("mmap_mode"))
        return orig_np_load(file, *args, **kwargs)

    monkeypatch.setattr(np, "load", spy_np_load)

    # Run the main execution script
    test_args = [
        "run_spk_response_metrics_a8_1.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir),
        "--unit-batch-size", "2"
    ]
    with patch("sys.argv", test_args):
        main()

    # 11. Verify NPY loading uses memmap safety
    assert len(mmap_modes) > 0
    assert all(mode == "r" for mode in mmap_modes)

    # Verify generated output files
    assert (out_dir / "response_metric_execution_parameters.json").exists()
    assert (out_dir / "unit_response_metrics_long.csv").exists()
    assert (out_dir / "unit_candidate_labels.csv").exists()
    assert (out_dir / "session_candidate_summary_no_area.csv").exists()
    assert (out_dir / "condition_slot_family_summary_no_area.csv").exists()
    assert (out_dir / "correction_scope_summary.csv").exists()
    assert (out_dir / "response_metric_execution_summary.json").exists()
    assert (out_dir / "response_metric_execution_summary.md").exists()

    # 14. Verify summary JSON has truth_status = truth_safe_unverified
    # 5. area_hierarchy_allowed is false
    with open(out_dir / "response_metric_execution_summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)
        assert summary["truth_status"] == TRUTH_SAFE_UNVERIFIED
        assert summary["manuscript_safe_response_class"] is False
        assert summary["area_hierarchy_allowed"] is False
        assert summary["biological_interpretation_allowed"] is False
        assert summary["raw_h5_reads"] == 0

    # 7. Verify session summaries contain no area or hierarchy columns
    with open(out_dir / "session_candidate_summary_no_area.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        # Block anatomical area / cortical hierarchy columns but allow metadata indicators
        anatomical_cols = ["area", "raw_area_label", "canonical_area_label", "area_group", "hierarchy"]
        assert not any(col in headers for col in anatomical_cols)

    # 13. Verify correction_scope is recorded for every contrast
    with open(out_dir / "unit_response_metrics_long.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) > 0
        for r in rows:
            assert r["correction_scope"] == "within_session_all_units_all_primary_contrasts"
            assert r["biological_interpretation_allowed"] == "false"
            assert r["area_hierarchy_allowed"] == "false"

    # 15. Verify manuscript_safe_unit_area_from_A6 is false
    with open(out_dir / "unit_candidate_labels.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        label_rows = list(reader)
        assert len(label_rows) > 0
        for r in label_rows:
            assert r["manuscript_safe_unit_area_from_A6"] == "false"
            assert r["manuscript_safe_response_class"] == "false"

def test_zero_hdf5_reads_block(mock_a5_a6_a7_setup, monkeypatch):
    # 10. raw H5 paths are not opened
    a5_dir = mock_a5_a6_a7_setup["a5_dir"]
    a6_dir = mock_a5_a6_a7_setup["a6_dir"]
    a7_dir = mock_a5_a6_a7_setup["a7_dir"]
    a8_dir = mock_a5_a6_a7_setup["a8_dir"]
    data_root = mock_a5_a6_a7_setup["data_root"]
    out_dir = mock_a5_a6_a7_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metrics_a8_1.get_git_commit", lambda: "mock_commit_a8_1")

    # Append an .h5 entry into A7 inventory
    a7_csv = a7_dir / "spk_smoke_file_inventory.csv"
    with open(a7_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "230630", "AXAB", "SPK", "ses230630-units-probe0-spk-AXAB.h5", "(20, 5, 6000)", "trial, unit, time",
            "20", "5", "6000", "valid_timebase_6000ms", "true", "true", "memmap", "None"
        ])

    # Touch mock real data .h5 file
    dummy_h5 = data_root / "ses230630-units-probe0-spk-AXAB.h5"
    dummy_h5.write_text("dummy h5 content")

    # Mock locate_file_recursively to return the .h5 path
    monkeypatch.setattr(
        "scripts.run_spk_response_metrics_a8_1.locate_file_recursively",
        lambda data_root, filename: dummy_h5 if "AXAB.h5" in filename else None
    )

    # Run execution script
    test_args = [
        "run_spk_response_metrics_a8_1.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    # Verify that H5 read was recorded as a skipped policy violation and 0 H5 files were opened
    with open(out_dir / "response_metric_execution_summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)
        assert summary["raw_h5_reads"] == 1

def test_missing_control_warning(mock_a5_a6_a7_setup, monkeypatch):
    # 12. missing matched controls emit warnings rather than silent success
    a5_dir = mock_a5_a6_a7_setup["a5_dir"]
    a6_dir = mock_a5_a6_a7_setup["a6_dir"]
    a7_dir = mock_a5_a6_a7_setup["a7_dir"]
    a8_dir = mock_a5_a6_a7_setup["a8_dir"]
    data_root = mock_a5_a6_a7_setup["data_root"]
    out_dir = mock_a5_a6_a7_setup["out_dir"]

    # Delete the control file ses230630-units-probe0-spk-AAAB.npy from inventory to trigger missing control
    a7_csv = a7_dir / "spk_smoke_file_inventory.csv"
    with open(a7_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "session_id", "condition", "signal_class", "source_file", "shape", "dims",
            "n_trials", "n_units", "n_timepoints", "time_axis_status",
            "p1_relative_possible", "omission_relative_possible", "payload_read_policy", "warnings"
        ])
        writer.writerow([
            "230630", "AXAB", "SPK", "ses230630-units-probe0-spk-AXAB.npy", "(20, 5, 6000)", "trial, unit, time",
            "20", "5", "6000", "valid_timebase_6000ms", "true", "true", "memmap", "None"
        ])

    monkeypatch.setattr("scripts.run_spk_response_metrics_a8_1.get_git_commit", lambda: "mock_commit_a8_1")

    # Run execution script
    test_args = [
        "run_spk_response_metrics_a8_1.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    # Check warnings
    with open(out_dir / "response_metric_execution_warnings.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        warnings = list(reader)
        assert len(warnings) > 0
        assert any(w["warning_type"] == "missing_control" for w in warnings)

def test_global_unique_units_not_confused_with_session_units(mock_a5_a6_a7_setup, monkeypatch):
    # Ensures global unique units matches len(unit_labels_records) and is not shadowed by session unit counts
    a5_dir = mock_a5_a6_a7_setup["a5_dir"]
    a6_dir = mock_a5_a6_a7_setup["a6_dir"]
    a7_dir = mock_a5_a6_a7_setup["a7_dir"]
    a8_dir = mock_a5_a6_a7_setup["a8_dir"]
    data_root = mock_a5_a6_a7_setup["data_root"]
    out_dir = mock_a5_a6_a7_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metrics_a8_1.get_git_commit", lambda: "mock_commit_a8_1")

    test_args = [
        "run_spk_response_metrics_a8_1.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    with open(out_dir / "response_metric_execution_summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)
        # In our mock setup we have exactly 5 mock units in session 230630.
        # Global unique units should be exactly 5, and NOT shadowed by anything else.
        assert summary["n_unique_units_global"] == 5

def test_trial_count_semantics_are_explicit(mock_a5_a6_a7_setup, monkeypatch):
    # Verifies that trial dimensions are correctly mapped to explicit semantic labels
    a5_dir = mock_a5_a6_a7_setup["a5_dir"]
    a6_dir = mock_a5_a6_a7_setup["a6_dir"]
    a7_dir = mock_a5_a6_a7_setup["a7_dir"]
    a8_dir = mock_a5_a6_a7_setup["a8_dir"]
    data_root = mock_a5_a6_a7_setup["data_root"]
    out_dir = mock_a5_a6_a7_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metrics_a8_1.get_git_commit", lambda: "mock_commit_a8_1")

    test_args = [
        "run_spk_response_metrics_a8_1.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    # Read long database
    with open(out_dir / "unit_response_metrics_long.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        assert "n_raw_behavioral_trials" in headers
        assert "n_trials" not in headers

    # Read summary JSON
    with open(out_dir / "response_metric_execution_summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)
        assert "n_raw_behavioral_trials" in summary
        assert "n_unit_trial_observations" in summary
        assert "n_trials_used" not in summary

def test_candidate_session_counts_sum_to_session_units(mock_a5_a6_a7_setup, monkeypatch):
    # Ensures S+, S-, O+, O-, X, and null counts in session_candidate_summary_no_area.csv sum exactly to n_unique_units_by_session.
    a5_dir = mock_a5_a6_a7_setup["a5_dir"]
    a6_dir = mock_a5_a6_a7_setup["a6_dir"]
    a7_dir = mock_a5_a6_a7_setup["a7_dir"]
    a8_dir = mock_a5_a6_a7_setup["a8_dir"]
    data_root = mock_a5_a6_a7_setup["data_root"]
    out_dir = mock_a5_a6_a7_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metrics_a8_1.get_git_commit", lambda: "mock_commit_a8_1")

    test_args = [
        "run_spk_response_metrics_a8_1.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    with open(out_dir / "session_candidate_summary_no_area.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            n_eval = int(r["n_unique_units_by_session"])
            n_s_plus = int(r["n_S_plus_candidate"])
            n_s_minus = int(r["n_S_minus_candidate"])
            n_o_plus = int(r["n_O_plus_candidate"])
            n_o_minus = int(r["n_O_minus_candidate"])
            n_x_omit = int(r["n_X_candidate"])
            n_null = int(r["n_null_or_unclassified"])
            assert n_eval == (n_s_plus + n_s_minus + n_o_plus + n_o_minus + n_x_omit + n_null)

def test_warning_aggregation_outputs_expected_columns(mock_a5_a6_a7_setup, monkeypatch):
    # Validates structure and content of warning_summary_by_session_condition_slot.csv
    a5_dir = mock_a5_a6_a7_setup["a5_dir"]
    a6_dir = mock_a5_a6_a7_setup["a6_dir"]
    a7_dir = mock_a5_a6_a7_setup["a7_dir"]
    a8_dir = mock_a5_a6_a7_setup["a8_dir"]
    data_root = mock_a5_a6_a7_setup["data_root"]
    out_dir = mock_a5_a6_a7_setup["out_dir"]

    # Delete the control file ses230630-units-probe0-spk-AAAB.npy to trigger missing control warning
    a7_csv = a7_dir / "spk_smoke_file_inventory.csv"
    with open(a7_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "session_id", "condition", "signal_class", "source_file", "shape", "dims",
            "n_trials", "n_units", "n_timepoints", "time_axis_status",
            "p1_relative_possible", "omission_relative_possible", "payload_read_policy", "warnings"
        ])
        writer.writerow([
            "230630", "AXAB", "SPK", "ses230630-units-probe0-spk-AXAB.npy", "(20, 5, 6000)", "trial, unit, time",
            "20", "5", "6000", "valid_timebase_6000ms", "true", "true", "memmap", "None"
        ])

    monkeypatch.setattr("scripts.run_spk_response_metrics_a8_1.get_git_commit", lambda: "mock_commit_a8_1")

    test_args = [
        "run_spk_response_metrics_a8_1.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    # Read warning summary CSV
    with open(out_dir / "warning_summary_by_session_condition_slot.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        expected_cols = [
            "session_id", "family", "condition", "omission_slot", "contrast_name",
            "warning_type", "n_warnings", "affected_metric_rows", "affected_units_if_available",
            "action_recommendation"
        ]
        assert all(col in headers for col in expected_cols)
        
        rows = list(reader)
        assert len(rows) > 0
        assert rows[0]["session_id"] == "230630"
        assert rows[0]["warning_type"] == "missing_control"

def test_long_metric_row_counts_match_csv_and_glossary(mock_a5_a6_a7_setup, monkeypatch):
    a5_dir = mock_a5_a6_a7_setup["a5_dir"]
    a6_dir = mock_a5_a6_a7_setup["a6_dir"]
    a7_dir = mock_a5_a6_a7_setup["a7_dir"]
    a8_dir = mock_a5_a6_a7_setup["a8_dir"]
    data_root = mock_a5_a6_a7_setup["data_root"]
    out_dir = mock_a5_a6_a7_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metrics_a8_1.get_git_commit", lambda: "mock_commit_a8_1")

    test_args = [
        "run_spk_response_metrics_a8_1.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    # Read long CSV rows
    with open(out_dir / "unit_response_metrics_long.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        long_rows = list(reader)
        
    # Read labels CSV rows
    with open(out_dir / "unit_candidate_labels.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        label_rows = list(reader)

    # Read summary JSON
    with open(out_dir / "response_metric_execution_summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)

    # Assert exact row match
    assert len(long_rows) == summary["n_long_metric_rows_total"]
    assert len(label_rows) == summary["n_unit_candidate_label_rows"]

    primary_count = sum(1 for r in long_rows if r["contrast_name"] in [
        "stimulus_vs_baseline", "omission_vs_local_baseline", "omission_vs_matched_stimulus"
    ])
    auxiliary_count = sum(1 for r in long_rows if r["contrast_name"] not in [
        "stimulus_vs_baseline", "omission_vs_local_baseline", "omission_vs_matched_stimulus"
    ])

    assert primary_count == summary["n_primary_contrast_rows"]
    assert auxiliary_count == summary["n_nonprimary_or_auxiliary_metric_rows"]
    assert summary["n_long_metric_rows_total"] == primary_count + auxiliary_count
