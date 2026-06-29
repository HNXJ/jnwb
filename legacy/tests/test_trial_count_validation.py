"""Tests for A4 trial-count validation."""

import pytest
import csv
import json
from pathlib import Path

@pytest.fixture(scope="module", autouse=True)
def ensure_validation_files():
    out_dir = Path('reports/analysis_A4_trial_count_validation')
    required = [
        'trial_count_matrix.csv',
        'condition_balance_summary.csv',
        'session_condition_completeness.csv',
        'trial_count_validation_summary.md',
        'trial_count_validation_summary.json'
    ]
    if not all((out_dir / fname).exists() for fname in required):
        import subprocess
        import sys
        a3_dir = Path("reports/analysis_A3_dataset_census")
        if not (a3_dir / "signal_file_inventory.csv").exists():
            subprocess.run([
                sys.executable,
                "scripts/build_dataset_census.py",
                "--data-root", "D:\\workspace\\data"
            ], check=True)
        subprocess.run([
            sys.executable,
            "scripts/build_trial_count_validation.py"
        ], check=True)


def test_all_12_conditions_detected():
    """Test that all 12 conditions are detected."""
    matrix_file = Path('reports/analysis_A4_trial_count_validation/trial_count_matrix.csv')
    assert matrix_file.exists()
    
    conditions = set()
    with open(matrix_file) as f:
        for row in csv.DictReader(f):
            conditions.add(row['condition'])
    
    required = {'AAAB', 'AXAB', 'AAXB', 'AAAX', 'BBBA', 'BXBA', 'BBXA', 'BBBX', 'RRRR', 'RXRR', 'RRXR', 'RRRX'}
    assert required == conditions


def test_family_and_omission_mapping():
    """Test correct family and omission position mappings."""
    matrix_file = Path('reports/analysis_A4_trial_count_validation/trial_count_matrix.csv')
    
    with open(matrix_file) as f:
        rows = {r['condition']: r for r in csv.DictReader(f) if r['session_id'] == '230629'}
    
    assert rows['AAAB']['family'] == 'A-family'
    assert rows['AXAB']['omission_position'] == 'p2'
    assert rows['AAXB']['omission_position'] == 'p3'
    assert rows['AAAX']['omission_position'] == 'p4'
    assert rows['BBBA']['family'] == 'B-family'
    assert rows['RRRR']['family'] == 'R-family'


def test_matched_controls():
    """Test matched control mappings."""
    matrix_file = Path('reports/analysis_A4_trial_count_validation/trial_count_matrix.csv')
    
    with open(matrix_file) as f:
        rows = {r['condition']: r for r in csv.DictReader(f) if r['session_id'] == '230629'}
    
    assert rows['AXAB']['matched_control'] == 'AAAB'
    assert rows['BXBA']['matched_control'] == 'BBBA'
    assert rows['RXRR']['matched_control'] == 'RRRR'


def test_trial_counts_extracted():
    """Test that trial counts are extracted from shapes."""
    matrix_file = Path('reports/analysis_A4_trial_count_validation/trial_count_matrix.csv')
    
    with open(matrix_file) as f:
        rows = {r['condition']: r for r in csv.DictReader(f) if r['session_id'] == '230629'}
    
    assert rows['AAAB']['trial_count'] == '48'
    assert rows['AXAB']['trial_count'] == '6'
    assert rows['RRRR']['trial_count'] == '84'


def test_session_completeness():
    """Test that all sessions are ready for A5."""
    comp_file = Path('reports/analysis_A4_trial_count_validation/session_condition_completeness.csv')
    
    with open(comp_file) as f:
        rows = list(csv.DictReader(f))
    
    assert len(rows) == 13
    for row in rows:
        assert row['readiness_for_A5'] == 'ready_for_A5'


def test_p2_p3_p4_omissions():
    """Test p2/p3/p4 omissions identified."""
    comp_file = Path('reports/analysis_A4_trial_count_validation/session_condition_completeness.csv')
    
    with open(comp_file) as f:
        rows = list(csv.DictReader(f))
    
    for row in rows:
        assert row['has_all_p2_omissions'] == 'yes'
        assert row['has_all_p3_omissions'] == 'yes'
        assert row['has_all_p4_omissions'] == 'yes'


def test_balance_summary():
    """Test balance summary created."""
    balance_file = Path('reports/analysis_A4_trial_count_validation/condition_balance_summary.csv')
    assert balance_file.exists()
    
    with open(balance_file) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 0


def test_truth_status():
    """Test truth_safe_unverified preserved."""
    for csv_file in ['trial_count_matrix.csv', 'condition_balance_summary.csv', 'session_condition_completeness.csv']:
        filepath = Path('reports/analysis_A4_trial_count_validation') / csv_file
        with open(filepath) as f:
            for row in csv.DictReader(f):
                assert row['truth_status'] == 'truth_safe_unverified'


def test_output_files():
    """Test all output files exist."""
    out_dir = Path('reports/analysis_A4_trial_count_validation')
    required = [
        'trial_count_matrix.csv',
        'condition_balance_summary.csv',
        'session_condition_completeness.csv',
        'trial_count_validation_summary.md',
        'trial_count_validation_summary.json'
    ]
    
    for fname in required:
        assert (out_dir / fname).exists()


def test_json_summary():
    """Test summary JSON metadata."""
    json_file = Path('reports/analysis_A4_trial_count_validation/trial_count_validation_summary.json')
    
    with open(json_file) as f:
        data = json.load(f)
    
    assert data['truth_status'] == 'truth_safe_unverified'
    assert data['sessions_analyzed'] == 13
    assert data['sessions_ready_for_a5'] == 13
