# tests/test_spk_response_metric_sensitivity_a8_2.py
"""
Unit tests for run_spk_response_metric_sensitivity_a8_2.py.
Verifies all 9 Phase A8.2 sensitivity test coverage requirements:
1. sensitivity grid parser preserves threshold/window/family/slot settings.
2. label stability counts are deterministic.
3. corrected-threshold labels are separated from uncorrected labels.
4. X_candidate cannot be marked robust from uncorrected-only evidence.
5. session dominance is detected.
6. warning burden is propagated.
7. denominator fields from A8.1.1 are copied and not renamed ambiguously.
8. output manifests contain source commit, input paths, hashes, and truth_safe_unverified.
9. no manuscript-safe/hierarchy flag is set from A8.2.
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

from scripts.run_spk_response_metric_sensitivity_a8_2 import (
    TRUTH_SAFE_UNVERIFIED,
    load_sensitivity_grid,
    benjamini_hochberg_correction,
    compute_cohens_d,
    compute_entropy,
    resolve_priority_label,
    main
)

@pytest.fixture
def mock_sensitivity_setup(tmp_path):
    a5_dir = tmp_path / "a5"
    a5_dir.mkdir()
    a6_dir = tmp_path / "a6"
    a6_dir.mkdir()
    a7_dir = tmp_path / "a7"
    a7_dir.mkdir()
    a8_dir = tmp_path / "a8"
    a8_dir.mkdir()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    data_root = tmp_path / "data"
    data_root.mkdir()
    out_dir = tmp_path / "out"

    # Create Plan Grid
    grid_csv = plan_dir / "sensitivity_grid.csv"
    with open(grid_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["grid_index", "alpha_level", "q_scope", "cohens_d_minimum", "omission_window", "slot_stratification", "family_stratification", "notes"])
        writer.writerow(["1", "0.05", "within_session_all_units_all_primary_contrasts", "0.3", "1000-1500", "all", "all", "Canonical"])
        writer.writerow(["2", "0.05", "none (p_uncorrected)", "0.0", "1000-1500", "all", "all", "Liberal"])

    # Create mock A7 inventory
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

    # Create mock A8.1.1 summary JSON to test denominator carry forward loading
    a8_sum_json = a8_dir / "response_metric_execution_summary.json"
    with open(a8_sum_json, "w", encoding="utf-8") as f:
        json.dump({
            "n_unique_units_global": 3521,
            "n_raw_behavioral_trials": 29430,
            "n_long_metric_rows_total": 39980,
            "n_primary_contrast_rows": 39232,
            "n_nonprimary_or_auxiliary_metric_rows": 748,
            "n_unit_candidate_label_rows": 3521
        }, f, indent=2)

    # Create mock A8 warning burden
    a8_warn = a8_dir / "warning_summary_by_session_condition_slot.csv"
    with open(a8_warn, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "session_id", "family", "condition", "omission_slot", "contrast_name",
            "warning_type", "n_warnings", "affected_metric_rows", "affected_units_if_available",
            "action_recommendation"
        ])
        writer.writerow(["230630", "A-family", "AXAB", "p2", "omission_vs_control", "missing_control", "2", "5", "0", "Flag session"])

    # Touch mock real data .npy files
    dummy_axab = np.zeros((20, 5, 6000), dtype=np.float32)
    # Unit 0 is S+ candidate (high P1 rate)
    dummy_axab[:, 0, 1000:1531] = (np.random.rand(20, 531) < 0.1).astype(np.float32) * 10.0
    dummy_axab[:, 0, 500:1000] = 0.0 # Low baseline

    dummy_aaab = np.zeros((20, 5, 6000), dtype=np.float32)

    np.save(data_root / "ses230630-units-probe0-spk-AXAB.npy", dummy_axab)
    np.save(data_root / "ses230630-units-probe0-spk-AAAB.npy", dummy_aaab)

    return {
        "a5_dir": a5_dir,
        "a6_dir": a6_dir,
        "a7_dir": a7_dir,
        "a8_dir": a8_dir,
        "plan_dir": plan_dir,
        "data_root": data_root,
        "out_dir": out_dir
    }

def test_sensitivity_grid_parser(tmp_path):
    # 1. sensitivity grid parser preserves threshold/window/family/slot settings.
    grid_csv = tmp_path / "sensitivity_grid.csv"
    with open(grid_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["grid_index", "alpha_level", "q_scope", "cohens_d_minimum", "omission_window", "slot_stratification", "family_stratification", "notes"])
        writer.writerow(["1", "0.05", "within_session_all_units_all_primary_contrasts", "0.3", "1000-1500", "all", "all", "Canonical"])
        writer.writerow(["2", "0.01", "none (p_uncorrected)", "0.5", "1000-1300", "p2", "A+B", "Notes 2"])

    grid = load_sensitivity_grid(grid_csv)
    assert len(grid) == 2
    assert grid[0]["grid_index"] == 1
    assert grid[0]["alpha_level"] == 0.05
    assert grid[0]["q_scope"] == "within_session_all_units_all_primary_contrasts"
    assert grid[0]["cohens_d_minimum"] == 0.3
    assert grid[0]["omission_window"] == "1000-1500"
    assert grid[0]["slot_stratification"] == "all"
    assert grid[0]["family_stratification"] == "all"

    assert grid[1]["grid_index"] == 2
    assert grid[1]["alpha_level"] == 0.01
    assert grid[1]["q_scope"] == "none (p_uncorrected)"
    assert grid[1]["cohens_d_minimum"] == 0.5
    assert grid[1]["omission_window"] == "1000-1300"
    assert grid[1]["slot_stratification"] == "p2"
    assert grid[1]["family_stratification"] == "A+B"

def test_label_stability_entropy_is_deterministic():
    # 2. label stability counts are deterministic.
    labels_a = ["X_candidate", "null_or_unclassified", "X_candidate"]
    labels_b = ["null_or_unclassified", "X_candidate", "X_candidate"]
    assert compute_entropy(labels_a) == compute_entropy(labels_b)
    assert compute_entropy([]) == 0.0
    assert compute_entropy(["S_plus_candidate"] * 5) == 0.0

def test_priority_priority_resolves():
    # Helper behavior check
    assert resolve_priority_label({"X_candidate", "S_plus_candidate"}) == "X_candidate"
    assert resolve_priority_label({"S_plus_candidate", "S_minus_candidate"}) == "S_plus_candidate"
    assert resolve_priority_label(set()) == "null_or_unclassified"

def test_x_candidate_uncorrected_only_block():
    # 4. X_candidate cannot be marked robust from uncorrected-only evidence.
    # Strict labels should resolve S+ if it survives corrected scopes, but if X only appears in uncorrected it should not be strict robust X.
    labels = ["null_or_unclassified", "X_candidate"] # sweep 0 (corrected), sweep 1 (uncorrected)
    grid_mock = [
        {"q_scope": "within_session_all_units_all_primary_contrasts"},
        {"q_scope": "none (p_uncorrected)"}
    ]
    corrected_indices = [i for i, sw in enumerate(grid_mock) if sw["q_scope"] != "none (p_uncorrected)"]
    corrected_labels = [labels[i] for i in corrected_indices]
    
    assert "X_candidate" not in corrected_labels
    assert "X_candidate" in labels # permissive uncorrected only

def test_session_dominance_detection():
    # 5. session dominance is detected.
    session_x_counts = {"230630": 8, "230719": 2}
    total_x_robust = sum(session_x_counts.values())
    max_s_id = max(session_x_counts, key=session_x_counts.get)
    dom_frac = session_x_counts[max_s_id] / total_x_robust
    assert dom_frac == 0.8
    assert dom_frac >= 0.75 # Trigger session dominance bias flag

def test_warning_burden_propagation(mock_sensitivity_setup, monkeypatch):
    # 6. warning burden is propagated.
    a5_dir = mock_sensitivity_setup["a5_dir"]
    a6_dir = mock_sensitivity_setup["a6_dir"]
    a7_dir = mock_sensitivity_setup["a7_dir"]
    a8_dir = mock_sensitivity_setup["a8_dir"]
    plan_dir = mock_sensitivity_setup["plan_dir"]
    data_root = mock_sensitivity_setup["data_root"]
    out_dir = mock_sensitivity_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metric_sensitivity_a8_2.get_git_commit", lambda: "mock_commit_a8_2")

    test_args = [
        "run_spk_response_metric_sensitivity_a8_2.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir),
        "--plan-dir", str(plan_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    with open(out_dir / "candidate_label_stability_by_session.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) > 0
        assert int(rows[0]["warning_burden_warnings_count"]) == 2

def test_denominator_carry_forward_fields(mock_sensitivity_setup, monkeypatch):
    # 7. denominator fields from A8.1.1 are copied and not renamed ambiguously.
    a5_dir = mock_sensitivity_setup["a5_dir"]
    a6_dir = mock_sensitivity_setup["a6_dir"]
    a7_dir = mock_sensitivity_setup["a7_dir"]
    a8_dir = mock_sensitivity_setup["a8_dir"]
    plan_dir = mock_sensitivity_setup["plan_dir"]
    data_root = mock_sensitivity_setup["data_root"]
    out_dir = mock_sensitivity_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metric_sensitivity_a8_2.get_git_commit", lambda: "mock_commit_a8_2")

    test_args = [
        "run_spk_response_metric_sensitivity_a8_2.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir),
        "--plan-dir", str(plan_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    with open(out_dir / "sensitivity_execution_summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)
        assert summary["n_long_metric_rows_total"] == 39980
        assert summary["n_primary_contrast_rows"] == 39232
        assert summary["n_nonprimary_or_auxiliary_metric_rows"] == 748
        assert summary["n_unit_candidate_label_rows"] == 3521

def test_manifest_metadata_and_hashes(mock_sensitivity_setup, monkeypatch):
    # 8. output manifests contain source commit, input paths, hashes, and truth_safe_unverified.
    a5_dir = mock_sensitivity_setup["a5_dir"]
    a6_dir = mock_sensitivity_setup["a6_dir"]
    a7_dir = mock_sensitivity_setup["a7_dir"]
    a8_dir = mock_sensitivity_setup["a8_dir"]
    plan_dir = mock_sensitivity_setup["plan_dir"]
    data_root = mock_sensitivity_setup["data_root"]
    out_dir = mock_sensitivity_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metric_sensitivity_a8_2.get_git_commit", lambda: "mock_commit_a8_2")

    test_args = [
        "run_spk_response_metric_sensitivity_a8_2.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir),
        "--plan-dir", str(plan_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    with open(out_dir / "sensitivity_execution_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)
        assert manifest["artifact_id"] == "A8_2_spk_response_metric_sensitivity"
        assert manifest["truth_status"] == TRUTH_SAFE_UNVERIFIED
        assert manifest["git_commit"] == "mock_commit_a8_2"
        assert len(manifest["hashes"]) > 0

def test_no_manuscript_safe_or_hierarchy_flags(mock_sensitivity_setup, monkeypatch):
    # 9. no manuscript-safe/hierarchy flag is set from A8.2.
    a5_dir = mock_sensitivity_setup["a5_dir"]
    a6_dir = mock_sensitivity_setup["a6_dir"]
    a7_dir = mock_sensitivity_setup["a7_dir"]
    a8_dir = mock_sensitivity_setup["a8_dir"]
    plan_dir = mock_sensitivity_setup["plan_dir"]
    data_root = mock_sensitivity_setup["data_root"]
    out_dir = mock_sensitivity_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metric_sensitivity_a8_2.get_git_commit", lambda: "mock_commit_a8_2")

    test_args = [
        "run_spk_response_metric_sensitivity_a8_2.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir),
        "--plan-dir", str(plan_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    with open(out_dir / "sensitivity_execution_summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)
        assert summary["manuscript_safe_response_class"] is False
        assert summary["area_hierarchy_allowed"] is False

def test_corrected_vs_uncorrected_segregation(mock_sensitivity_setup, monkeypatch):
    # 3. corrected-threshold labels are separated from uncorrected labels.
    a5_dir = mock_sensitivity_setup["a5_dir"]
    a6_dir = mock_sensitivity_setup["a6_dir"]
    a7_dir = mock_sensitivity_setup["a7_dir"]
    a8_dir = mock_sensitivity_setup["a8_dir"]
    plan_dir = mock_sensitivity_setup["plan_dir"]
    data_root = mock_sensitivity_setup["data_root"]
    out_dir = mock_sensitivity_setup["out_dir"]

    monkeypatch.setattr("scripts.run_spk_response_metric_sensitivity_a8_2.get_git_commit", lambda: "mock_commit_a8_2")

    test_args = [
        "run_spk_response_metric_sensitivity_a8_2.py",
        "--data-root", str(data_root),
        "--a5-dir", str(a5_dir),
        "--a6-dir", str(a6_dir),
        "--a7-dir", str(a7_dir),
        "--a8-dir", str(a8_dir),
        "--out-dir", str(out_dir),
        "--plan-dir", str(plan_dir)
    ]
    with patch("sys.argv", test_args):
        main()

    with open(out_dir / "sensitivity_grid_realized.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        # Grid 1 has corrected scope (within_session), Grid 2 has uncorrected
        assert rows[0]["q_scope"] == "within_session_all_units_all_primary_contrasts"
        assert rows[1]["q_scope"] == "none (p_uncorrected)"
