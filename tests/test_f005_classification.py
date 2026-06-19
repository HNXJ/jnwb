#!/usr/bin/env python3
"""Tests for f005 unit classification (S+, S-, O/X).

These tests validate:
1. Code100 anchors are rejected
2. Code101 anchors are accepted
3. S+ synthetic units are classified correctly
4. S- synthetic units are classified correctly
5. O/X synthetic units are classified correctly
6. Overlapping S+ and O/X labels are stored but display as O/X
7. Output manifest contains class definitions and thresholds
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from scripts.classify_units_s_s_o import (
    ClassificationConfig,
    classify_s_plus,
    classify_s_minus,
    classify_ox,
    assign_display_class,
    validate_anchor_provenance,
    validate_data_quality,
    validate_time_coverage,
    extract_window_rate,
    BLOCKED_ANCHOR_CODE100,
    BLOCKED_ANCHOR_NOT_CODE101,
    BLOCKED_TIME_AXIS_NOT_P1_RELATIVE,
)


# ============================================================================
# Anchor Validation Tests
# ============================================================================

def test_reject_code100_anchor():
    """Epochs with code100 anchor must be rejected."""
    epochs_dict = {
        "anchor_code": 100,
        "anchor_type": "fixation_cue",
        "time_base": "fixation_relative",
    }
    
    result = validate_anchor_provenance(epochs_dict)
    
    assert result["valid"] is False
    assert result["blocker"] == BLOCKED_ANCHOR_CODE100


def test_reject_unverified_anchor():
    """Epochs without explicit code101 provenance must be rejected."""
    epochs_dict = {
        "time_base": "unknown",
    }
    
    result = validate_anchor_provenance(epochs_dict)
    
    assert result["valid"] is False
    assert result["blocker"] in (BLOCKED_ANCHOR_NOT_CODE101, BLOCKED_TIME_AXIS_NOT_P1_RELATIVE)


def test_accept_code101_anchor():
    """Epochs with explicit code101 anchor are accepted."""
    epochs_dict = {
        "anchor_code": 101,
        "anchor_type": "p1_stimulus",
        "time_base": "p1_relative",
    }
    
    result = validate_anchor_provenance(epochs_dict)
    
    assert result["valid"] is True
    assert result["error"] is None


def test_reject_non_p1_relative_time_base():
    """Time base must be p1-relative, not omission-relative or other."""
    epochs_dict = {
        "anchor_code": 101,
        "time_base": "omission_relative",
    }
    
    result = validate_anchor_provenance(epochs_dict)
    
    assert result["valid"] is False
    assert result["blocker"] == BLOCKED_TIME_AXIS_NOT_P1_RELATIVE


# ============================================================================
# Data Quality Tests
# ============================================================================

def test_reject_nonfinite_data():
    """Non-finite values in spike data must be rejected."""
    # Create data with NaN
    spk_epochs = np.zeros((10, 5, 100))
    spk_epochs[0, 0, 0] = np.nan
    
    result = validate_data_quality(spk_epochs)
    
    assert result["valid"] is False
    assert "finite" in result["error"].lower()


def test_reject_wrong_dimensions():
    """Spike epochs must be 3D (trial x unit x time)."""
    # 2D data
    spk_epochs = np.zeros((10, 100))
    
    result = validate_data_quality(spk_epochs)
    
    assert result["valid"] is False
    assert "3D" in result["error"]


def test_accept_valid_3d_data():
    """Valid 3D data passes validation."""
    spk_epochs = np.zeros((10, 5, 100))
    
    result = validate_data_quality(spk_epochs)
    
    assert result["valid"] is True


# ============================================================================
# S+ Classification Tests
# ============================================================================

def test_synthetic_s_plus_unit_classified():
    """Synthetic S+ unit (p1 > baseline) is classified correctly."""
    np.random.seed(42)
    config = ClassificationConfig(p_threshold=0.05, effect_increase=1.20)
    
    n_trials = 20
    n_units = 1
    
    # Baseline: low rate
    baseline_rates = np.random.poisson(5, size=(n_trials, n_units)).astype(float)
    
    # P1: higher rate (>20% increase, statistically significant)
    p1_rates = np.random.poisson(8, size=(n_trials, n_units)).astype(float)
    
    is_s_plus, p_values_raw, p_values_fdr, rank_biserials, pct_changes = classify_s_plus(
        baseline_rates, p1_rates, config
    )
    
    # Should classify as S+
    assert bool(is_s_plus[0])
    assert p_values_fdr[0] < config.p_threshold  # Check FDR-corrected
    assert pct_changes[0] > 0
    assert np.isfinite(rank_biserials[0])  # Rank-biserial computed


def test_synthetic_non_s_plus_unit_rejected():
    """Unit without significant increase is not classified as S+."""
    np.random.seed(42)
    config = ClassificationConfig()
    
    n_trials = 20
    n_units = 1
    
    # No significant difference
    baseline_rates = np.random.poisson(5, size=(n_trials, n_units)).astype(float)
    p1_rates = np.random.poisson(5, size=(n_trials, n_units)).astype(float)
    
    is_s_plus, p_values_raw, p_values_fdr, rank_biserials, pct_changes = classify_s_plus(
        baseline_rates, p1_rates, config
    )
    
    # Should not classify as S+
    assert not bool(is_s_plus[0])


# ============================================================================
# S- Classification Tests
# ============================================================================

def test_synthetic_s_minus_unit_classified():
    """Synthetic S- unit (p1 < baseline) is classified correctly."""
    config = ClassificationConfig(p_threshold=0.05, effect_decrease=0.80)
    
    n_trials = 20
    n_units = 1
    
    # Baseline: higher rate
    baseline_rates = np.random.poisson(8, size=(n_trials, n_units)).astype(float)
    
    # P1: lower rate (<80% of baseline, statistically significant)
    p1_rates = np.random.poisson(4, size=(n_trials, n_units)).astype(float)
    
    is_s_minus, p_values_raw, p_values_fdr, rank_biserials, pct_changes = classify_s_minus(
        baseline_rates, p1_rates, config
    )
    
    # Should classify as S-
    assert bool(is_s_minus[0])
    assert p_values_fdr[0] < config.p_threshold  # Check FDR-corrected
    assert pct_changes[0] < 0


def test_synthetic_non_s_minus_unit_rejected():
    """Unit without significant decrease is not classified as S-."""
    config = ClassificationConfig()
    
    n_trials = 20
    n_units = 1
    
    # No significant difference
    baseline_rates = np.random.poisson(5, size=(n_trials, n_units)).astype(float)
    p1_rates = np.random.poisson(5, size=(n_trials, n_units)).astype(float)
    
    is_s_minus, p_values_raw, p_values_fdr, rank_biserials, pct_changes = classify_s_minus(
        baseline_rates, p1_rates, config
    )
    
    # Should not classify as S-
    assert not bool(is_s_minus[0])


# ============================================================================
# O/X Classification Tests
# ============================================================================

def test_synthetic_ox_unit_classified():
    """Synthetic O/X unit (omission > p1 AND omission > p2 AND omission > baseline) is classified."""
    config = ClassificationConfig(p_threshold=0.05)
    
    n_trials = 20
    n_units = 1
    
    # Low baseline and stimulus rates
    baseline_rates = np.random.poisson(3, size=(n_trials, n_units)).astype(float)
    p1_rates = np.random.poisson(4, size=(n_trials, n_units)).astype(float)
    p2_rates = np.random.poisson(4, size=(n_trials, n_units)).astype(float)
    
    # High omission rate
    omission_rates = np.random.poisson(10, size=(n_trials, n_units)).astype(float)
    
    is_ox, p_values_raw, p_values_fdr, rank_biserials, pct_changes = classify_ox(
        baseline_rates, p1_rates, p2_rates, omission_rates, config
    )
    
    # Should classify as O/X
    assert bool(is_ox[0])
    assert p_values_fdr[0] < config.p_threshold  # Check FDR-corrected


def test_ox_requires_exceeding_p1_and_p2():
    """O/X requires omission > p1 AND omission > p2."""
    config = ClassificationConfig()
    
    n_trials = 20
    n_units = 1
    
    baseline_rates = np.random.poisson(3, size=(n_trials, n_units)).astype(float)
    p1_rates = np.random.poisson(10, size=(n_trials, n_units)).astype(float)  # High p1
    p2_rates = np.random.poisson(10, size=(n_trials, n_units)).astype(float)  # High p2
    omission_rates = np.random.poisson(8, size=(n_trials, n_units)).astype(float)  # Less than p1/p2
    
    is_ox, p_values_raw, p_values_fdr, rank_biserials, pct_changes = classify_ox(
        baseline_rates, p1_rates, p2_rates, omission_rates, config
    )
    
    # Should not classify as O/X (omission < p1 and omission < p2)
    assert not bool(is_ox[0])


def test_ox_requires_exceeding_baseline():
    """O/X requires omission > baseline."""
    config = ClassificationConfig()
    
    n_trials = 20
    n_units = 1
    
    baseline_rates = np.random.poisson(15, size=(n_trials, n_units)).astype(float)  # High baseline
    p1_rates = np.random.poisson(4, size=(n_trials, n_units)).astype(float)
    p2_rates = np.random.poisson(4, size=(n_trials, n_units)).astype(float)
    omission_rates = np.random.poisson(10, size=(n_trials, n_units)).astype(float)  # Less than baseline
    
    is_ox, p_values_raw, p_values_fdr, rank_biserials, pct_changes = classify_ox(
        baseline_rates, p1_rates, p2_rates, omission_rates, config
    )
    
    # Should not classify as O/X (omission < baseline)
    assert not bool(is_ox[0])


# ============================================================================
# Display Class Priority Tests
# ============================================================================

def test_ox_takes_precedence_over_s_plus():
    """Overlapping O/X and S+ unit displays as O/X."""
    n_units = 3
    
    is_s_plus = np.array([True, True, False])
    is_s_minus = np.array([False, False, False])
    is_ox = np.array([True, False, False])  # First unit is both S+ and O/X
    
    display_classes = assign_display_class(is_s_plus, is_s_minus, is_ox)
    
    # First unit should display as O/X (precedence)
    assert display_classes[0] == "O/X"
    # Second unit is S+ only
    assert display_classes[1] == "S+"
    # Third unit is unclassified
    assert display_classes[2] == "unclassified"


def test_ox_takes_precedence_over_s_minus():
    """Overlapping O/X and S- unit displays as O/X."""
    n_units = 3
    
    is_s_plus = np.array([False, False, False])
    is_s_minus = np.array([True, True, False])
    is_ox = np.array([True, False, False])  # First unit is both S- and O/X
    
    display_classes = assign_display_class(is_s_plus, is_s_minus, is_ox)
    
    # First unit should display as O/X (precedence)
    assert display_classes[0] == "O/X"
    # Second unit is S- only
    assert display_classes[1] == "S-"


def test_s_plus_takes_precedence_over_s_minus():
    """Overlapping S+ and S- unit displays as S+ (after O/X)."""
    n_units = 3
    
    is_s_plus = np.array([True, True, False])
    is_s_minus = np.array([True, False, True])
    is_ox = np.array([False, False, False])
    
    display_classes = assign_display_class(is_s_plus, is_s_minus, is_ox)
    
    # First unit is both, displays as S+
    assert display_classes[0] == "S+"
    # Second unit is S+ only
    assert display_classes[1] == "S+"
    # Third unit is S- only
    assert display_classes[2] == "S-"


# ============================================================================
# Time Coverage Tests
# ============================================================================

def test_time_coverage_valid():
    """Valid time coverage passes validation."""
    time_axis_ms = np.arange(-1000, 4000, 10)
    
    required_windows = [
        ("baseline", (-500, 0)),
        ("p1", (0, 531)),
    ]
    
    result = validate_time_coverage(time_axis_ms, required_windows)
    
    assert result["valid"] is True


def test_time_coverage_invalid_window():
    """Missing required window fails validation."""
    time_axis_ms = np.arange(0, 4000, 10)  # Starts at 0, missing negative times
    
    required_windows = [
        ("baseline", (-500, 0)),
    ]
    
    result = validate_time_coverage(time_axis_ms, required_windows)
    
    assert result["valid"] is False
    assert "baseline" in result["error"]


# ============================================================================
# Extract Window Rate Tests
# ============================================================================

def test_extract_window_rate_basic():
    """Basic window rate extraction."""
    # 10 trials, 5 units, 100 time bins (10ms each, so 1000ms total)
    spk_epochs = np.zeros((10, 5, 100))
    spk_epochs[:, :, 50:60] = 1  # 100-200ms window: 1 spike per bin
    
    time_axis_ms = np.arange(-500, 500, 10)  # -500 to 490ms
    window_ms = (0, 100)  # 0-100ms = 10 bins, each with 1 spike
    bin_ms = 10
    
    rates = extract_window_rate(spk_epochs, time_axis_ms, window_ms, bin_ms)
    
    # Shape should be (n_trials, n_units)
    assert rates.shape == (10, 5)
    
    # Rate should be 1 spike / (0.01s * 10 bins) = 10 Hz? No, wait
    # Actually each bin has 1 spike, 10 bins, so 10 spikes total
    # Duration is 100ms = 0.1s
    # So rate = 10 spikes / 0.1s = 100 Hz... let me recalculate
    
    # Actually the function sums spikes and divides by duration
    # So if we put spikes in 50:60, that's indices 50-59 (10 bins)
    # But window 0-100ms would be indices 50-60... let me fix the test
    
    # Actually time_axis_ms = -500 to 490, step 10
    # So index 50 = 0ms (since -500 + 50*10 = 0)
    # Index 60 = 100ms
    
    # So window 0-100ms captures indices 50:60 (10 bins)
    # With 1 spike per bin, that's 10 spikes over 0.1s = 100 Hz
    
    expected_rate = 100.0  # Hz
    assert np.allclose(rates, expected_rate)


def test_extract_window_rate_empty():
    """Empty window raises error."""
    spk_epochs = np.zeros((10, 5, 100))
    time_axis_ms = np.arange(-500, 500, 10)
    
    # Window outside time axis
    window_ms = (1000, 1100)
    bin_ms = 10
    
    with pytest.raises(ValueError):
        extract_window_rate(spk_epochs, time_axis_ms, window_ms, bin_ms)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
