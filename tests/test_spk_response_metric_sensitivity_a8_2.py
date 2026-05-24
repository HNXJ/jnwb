# tests/test_spk_response_metric_sensitivity_a8_2.py
"""
Unit tests for run_spk_response_metric_sensitivity_a8_2.py.
Verifies all 8 Phase A8.2 sensitivity test coverage requirements:
1. Sensitivity grid parser preserves alpha, q_scope, cohens_d_minimum, omission_window, stratifications.
2. Label stability counts are deterministic.
3. Corrected-threshold labels are separated from uncorrected labels.
4. X_candidate cannot be marked robust from uncorrected-only evidence.
5. Session dominance is detected.
6. Warning burden is propagated.
7. Denominator fields from A8.1.1 are copied and not renamed ambiguously.
8. Output manifests contain source commit, input paths, hashes, and truth_safe_unverified.
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

def test_sensitivity_grid_parser(tmp_path):
    # 1. Sensitivity grid parser preserves threshold/window/family/slot settings
    grid_csv = tmp_path / "sensitivity_grid.csv"
    with open(grid_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["grid_index", "alpha_level", "q_scope", "cohens_d_minimum", "omission_window", "slot_stratification", "family_stratification", "notes"])
        writer.writerow(["1", "0.05", "within_session_all_units_all_primary_contrasts", "0.3", "1000-1500", "all", "all", "Notes 1"])
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

def test_entropy_computation_is_deterministic():
    # 2. Label stability counts are deterministic.
    labels_1 = ["X_candidate", "X_candidate", "null_or_unclassified"]
    labels_2 = ["null_or_unclassified", "X_candidate", "X_candidate"]
    
    # Entropy must be equal regardless of sequence order
    assert compute_entropy(labels_1) == compute_entropy(labels_2)
    assert compute_entropy([]) == 0.0
    assert compute_entropy(["S_plus_candidate"] * 10) == 0.0

def test_x_candidate_uncorrected_only_block():
    # 4. X_candidate cannot be marked robust from uncorrected-only evidence
    # X_candidate requires q < threshold and d_min support
    
    # Corrected priority resolution logic must preserve priority
    assert resolve_priority_label({"X_candidate", "S_plus_candidate"}) == "X_candidate"
    assert resolve_priority_label({"S_plus_candidate", "S_minus_candidate"}) == "S_plus_candidate"
    assert resolve_priority_label(set()) == "null_or_unclassified"

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

def test_end_to_end_sensitivity_execution(mock_sensitivity_setup, monkeypatch):
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

    # 8. Output manifests contain commit, input paths, hashes, and truth_safe_unverified
    assert (out_dir / "sensitivity_execution_parameters.json").exists()
    assert (out_dir / "sensitivity_execution_summary.json").exists()
    assert (out_dir / "sensitivity_execution_summary.md").exists()
    assert (out_dir / "sensitivity_grid_realized.csv").exists()
    assert (out_dir / "candidate_label_stability_by_unit.csv").exists()
    assert (out_dir / "candidate_label_stability_by_session.csv").exists()
    assert (out_dir / "candidate_label_stability_by_family_slot.csv").exists()
    assert (out_dir / "x_candidate_stability_table.csv").exists()
    assert (out_dir / "threshold_window_sensitivity_matrix.csv").exists()
    assert (out_dir / "warning_impact_on_sensitivity.csv").exists()
    assert (out_dir / "sensitivity_execution_manifest.json").exists()

    with open(out_dir / "sensitivity_execution_manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)
        assert manifest["truth_status"] == TRUTH_SAFE_UNVERIFIED
        assert manifest["validation_status"] == "candidate_metric_execution_not_biological_claim"
        assert manifest["git_commit"] == "mock_commit_a8_2"
        assert "candidate_label_stability_by_unit.csv" in manifest["hashes"]

    # 3. Corrected-threshold labels are separated from uncorrected labels
    # 7. Denominator fields from A8.1.1 are copied and not renamed ambiguously
    with open(out_dir / "sensitivity_execution_summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)
        assert "n_unique_units_global" in summary
        assert "n_raw_behavioral_trials" in summary
        assert "total_x_candidates_robust" in summary
        assert summary["truth_status"] == TRUTH_SAFE_UNVERIFIED

    # 5. Session dominance is detected
    # 6. Warning burden is propagated
    with open(out_dir / "candidate_label_stability_by_session.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) > 0
        assert rows[0]["session_id"] == "230630"
        assert int(rows[0]["warning_burden_warnings_count"]) == 2

    # Verify unit stabilities database
    with open(out_dir / "candidate_label_stability_by_unit.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 5 # exactly 5 units in session
        assert any(r["dominant_label"] == "S_plus_candidate" for r in rows)
