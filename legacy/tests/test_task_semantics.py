"""Tests for task semantics and alignment contract validation.

These tests ensure that event code semantics are correctly enforced
and that p1 anchor extraction uses the correct codes (101, not 100).
"""

import numpy as np
import pandas as pd
import pytest

from src.analysis.task_semantics import (
    # Constants
    BLOCKED_CODE100_AS_P1,
    BLOCKED_FIX_CUE_IN_P1_EVENTS,
    BLOCKED_STIMULUS_NUMBER_1_AS_P1,
    BLOCKED_CODE101_MISMATCH_STIM2,
    BLOCKED_INCORRECT_OMISSION_OFFSET,
    # Validation functions
    validate_no_code100_in_p1_events,
    validate_no_fix_cue_appearance,
    validate_all_code101,
    validate_stimulus_number_2_for_code101,
    validate_not_stimulus_number_1,
    validate_omission_offset,
    run_all_validations,
    # Helpers
    get_event_code_semantics,
    is_valid_p1_anchor_code,
    is_fixation_cue_code,
    calculate_aaxb_omission_onset,
    get_aaxb_semantics,
)
from src.analysis.contracts.constants import (
    EVENT_CODE_FIXATION_CUE,
    EVENT_CODE_P1_STIMULUS,
    EVENT_CODE_P2_STIMULUS,
    AAXB_OMISSION_OFFSET_MS,
)


# ============================================================================
# Test Event Code Semantics
# ============================================================================

def test_event_code_100_is_fixation_cue():
    """Code 100 must be identified as fixation cue, NOT p1 anchor."""
    semantics = get_event_code_semantics(EVENT_CODE_FIXATION_CUE)
    assert semantics["is_fixation_cue"] is True
    assert semantics["is_valid_p1_anchor"] is False
    assert "NOT valid" in semantics["description"]


def test_event_code_101_is_valid_p1_anchor():
    """Code 101 must be identified as valid p1 stimulus anchor."""
    semantics = get_event_code_semantics(EVENT_CODE_P1_STIMULUS)
    assert semantics["is_valid_p1_anchor"] is True
    assert semantics["is_fixation_cue"] is False
    assert "VALID" in semantics["description"]


def test_is_valid_p1_anchor_code():
    """is_valid_p1_anchor_code must return True only for code 101."""
    assert is_valid_p1_anchor_code(EVENT_CODE_P1_STIMULUS) is True
    assert is_valid_p1_anchor_code(EVENT_CODE_FIXATION_CUE) is False
    assert is_valid_p1_anchor_code(999) is False


def test_is_fixation_cue_code():
    """is_fixation_cue_code must return True only for code 100."""
    assert is_fixation_cue_code(EVENT_CODE_FIXATION_CUE) is True
    assert is_fixation_cue_code(EVENT_CODE_P1_STIMULUS) is False
    assert is_fixation_cue_code(999) is False


# ============================================================================
# Test Code 100 Rejection
# ============================================================================

def test_validate_no_code100_passes_with_code101_only():
    """Validation passes when all events have code 101."""
    df = pd.DataFrame({
        "codes": [101, 101, 101],
    })
    result = validate_no_code100_in_p1_events(df)
    assert result["passed"] is True
    assert result["n_code100"] == 0
    assert len(result["errors"]) == 0


def test_validate_no_code100_fails_with_code100_present():
    """Validation fails when code 100 (fixation cue) is present."""
    df = pd.DataFrame({
        "codes": [101, 100, 101],  # Code 100 is invalid
    })
    result = validate_no_code100_in_p1_events(df)
    assert result["passed"] is False
    assert result["n_code100"] == 1
    assert len(result["errors"]) == 1
    assert BLOCKED_CODE100_AS_P1 in result["errors"][0]


def test_validate_no_code100_fails_with_only_code100():
    """Validation fails when ALL events have code 100 (complete invalid set)."""
    df = pd.DataFrame({
        "codes": [100, 100, 100],
    })
    result = validate_no_code100_in_p1_events(df)
    assert result["passed"] is False
    assert result["n_code100"] == 3
    assert BLOCKED_CODE100_AS_P1 in result["errors"][0]


# ============================================================================
# Test Fix Cue Appearance Rejection
# ============================================================================

def test_validate_no_fix_cue_passes_without_fix_cue():
    """Validation passes when no 'fix cue appearance' event types."""
    df = pd.DataFrame({
        "event_code_type": ["task_event_2", "task_event_3"],
    })
    result = validate_no_fix_cue_appearance(df)
    assert result["passed"] is True
    assert result["n_fix_cue"] == 0


def test_validate_no_fix_cue_fails_with_fix_cue():
    """Validation fails when 'fix cue appearance' event types present."""
    df = pd.DataFrame({
        "event_code_type": ["task_event_2", "fix cue appearance", "task_event_2"],
    })
    result = validate_no_fix_cue_appearance(df)
    assert result["passed"] is False
    assert result["n_fix_cue"] == 1
    assert BLOCKED_FIX_CUE_IN_P1_EVENTS in result["errors"][0]


# ============================================================================
# Test Code 101 Requirement
# ============================================================================

def test_validate_all_code101_passes_with_all_code101():
    """Validation passes when all events have code 101."""
    df = pd.DataFrame({
        "codes": [101, 101, 101],
    })
    result = validate_all_code101(df)
    assert result["passed"] is True
    assert result["n_code101"] == 3


def test_validate_all_code101_fails_with_mixed_codes():
    """Validation fails when events have non-101 codes."""
    df = pd.DataFrame({
        "codes": [101, 102, 101],  # 102 is p2, not p1
    })
    result = validate_all_code101(df)
    assert result["passed"] is False
    assert 102 in result["other_codes"]


# ============================================================================
# Test Stimulus Number Cross-Check
# ============================================================================

def test_validate_stim2_crosscheck_passes_when_all_code101_have_stim2():
    """Validation passes when code 101 events have stimulus_number == 2."""
    df = pd.DataFrame({
        "codes": [101, 101, 101],
        "stimulus_number": [2, 2, 2],
    })
    result = validate_stimulus_number_2_for_code101(df)
    assert result["passed"] is True
    assert result["n_code101_stim2"] == 3


def test_validate_stim2_crosscheck_fails_when_code101_has_wrong_stim():
    """Validation fails when code 101 events don't have stimulus_number == 2."""
    df = pd.DataFrame({
        "codes": [101, 101],
        "stimulus_number": [2, 1],  # Second event has stim 1 (wrong)
    })
    result = validate_stimulus_number_2_for_code101(df)
    assert result["passed"] is False
    assert result["n_code101_not_stim2"] == 1
    assert BLOCKED_CODE101_MISMATCH_STIM2 in result["errors"][0]


# ============================================================================
# Test Stimulus Number 1 Rejection
# ============================================================================

def test_validate_not_stim1_passes_without_stim1():
    """Validation passes when no stimulus_number == 1 rows."""
    df = pd.DataFrame({
        "stimulus_number": [2, 3, 4],
    })
    result = validate_not_stimulus_number_1(df)
    assert result["passed"] is True
    assert result["n_stim1"] == 0


def test_validate_not_stim1_fails_with_stim1():
    """Validation fails when stimulus_number == 1 is present."""
    df = pd.DataFrame({
        "stimulus_number": [2, 1, 3],  # stim 1 is fixation cue
    })
    result = validate_not_stimulus_number_1(df)
    assert result["passed"] is False
    assert result["n_stim1"] == 1
    assert BLOCKED_STIMULUS_NUMBER_1_AS_P1 in result["errors"][0]


# ============================================================================
# Test Omission Offset Validation
# ============================================================================

def test_validate_omission_offset_passes_with_correct_offset():
    """Validation passes when omission onset = p1 + 2062ms."""
    p1_times = np.array([100.0, 200.0, 300.0])  # seconds
    omission_times = p1_times + (AAXB_OMISSION_OFFSET_MS / 1000.0)
    
    result = validate_omission_offset(p1_times, omission_times)
    assert result["passed"] is True
    assert result["offset_mean_ms"] == pytest.approx(AAXB_OMISSION_OFFSET_MS, abs=0.1)


def test_validate_omission_offset_fails_with_wrong_offset():
    """Validation fails when omission offset is wrong."""
    p1_times = np.array([100.0, 200.0])
    omission_times = p1_times + 1.0  # Wrong offset (1s instead of 2.062s)
    
    result = validate_omission_offset(p1_times, omission_times, tolerance_ms=10.0)
    assert result["passed"] is False
    assert BLOCKED_INCORRECT_OMISSION_OFFSET in result["errors"][0]


def test_validate_omission_offset_fails_with_length_mismatch():
    """Validation fails when p1 and omission arrays have different lengths."""
    p1_times = np.array([100.0, 200.0])
    omission_times = np.array([102.062])  # Only one element
    
    result = validate_omission_offset(p1_times, omission_times)
    assert result["passed"] is False
    assert "Length mismatch" in result["errors"][0]


# ============================================================================
# Test Combined Validations
# ============================================================================

def test_run_all_validations_passes_with_valid_data():
    """All validations pass with correct code 101 data."""
    df = pd.DataFrame({
        "codes": [101, 101],
        "stimulus_number": [2, 2],
        "event_code_type": ["task_event_2", "task_event_2"],
    })
    result = run_all_validations(df)
    assert result["all_passed"] is True
    assert len(result["errors"]) == 0


def test_run_all_validations_fails_with_code100_data():
    """All validations fail with code 100 (fixation cue) data."""
    df = pd.DataFrame({
        "codes": [100, 100],
        "stimulus_number": [1, 1],
        "event_code_type": ["fix cue appearance", "fix cue appearance"],
    })
    result = run_all_validations(df)
    assert result["all_passed"] is False
    assert len(result["errors"]) > 0
    # Should have multiple errors
    assert any(BLOCKED_CODE100_AS_P1 in e for e in result["errors"])


# ============================================================================
# Test AAXB Helpers
# ============================================================================

def test_calculate_aaxb_omission_onset_seconds():
    """Omission onset calculation works with seconds input."""
    p1_times = np.array([100.0, 200.0, 300.0])
    omission_times = calculate_aaxb_omission_onset(p1_times)
    
    expected_offset_s = AAXB_OMISSION_OFFSET_MS / 1000.0
    np.testing.assert_array_almost_equal(
        omission_times - p1_times,
        np.array([expected_offset_s, expected_offset_s, expected_offset_s]),
        decimal=3
    )


def test_calculate_aaxb_omission_onset_milliseconds():
    """Omission onset calculation works with milliseconds input."""
    p1_times_ms = np.array([100000.0, 200000.0, 300000.0])
    omission_times_ms = calculate_aaxb_omission_onset(p1_times_ms)
    
    np.testing.assert_array_almost_equal(
        omission_times_ms - p1_times_ms,
        np.array([AAXB_OMISSION_OFFSET_MS, AAXB_OMISSION_OFFSET_MS, AAXB_OMISSION_OFFSET_MS]),
        decimal=1
    )


def test_get_aaxb_semantics():
    """AAXB semantics include correct omission information."""
    semantics = get_aaxb_semantics()
    assert semantics["condition_label"] == "AAXB"
    assert semantics["omission_slot"] == "p3"
    assert semantics["omission_offset_ms"] == AAXB_OMISSION_OFFSET_MS
    assert semantics["p1_anchor_code"] == EVENT_CODE_P1_STIMULUS
    assert semantics["correct_p1_stimulus_number"] == 2
    assert semantics["incorrect_p1_stimulus_number"] == 1


# ============================================================================
# Regression Tests for Negative Control
# ============================================================================

def test_stimulus_number_1_is_rejected_as_p1():
    """REGRESSION: stimulus_number == 1 must NOT be treated as p1 anchor.
    
    This is a critical regression test. Previously, stimulus_number == 1
    was incorrectly used as p1 anchor, but it corresponds to code 100
    (fixation cue), not code 101 (p1 stimulus).
    """
    df = pd.DataFrame({
        "codes": [100, 100, 100],
        "stimulus_number": [1, 1, 1],
        "event_code_type": ["fix cue appearance"] * 3,
    })
    
    # This should fail ALL validations
    result = run_all_validations(df)
    assert result["all_passed"] is False
    
    # Specifically check the stim1 rejection
    stim1_result = validate_not_stimulus_number_1(df)
    assert stim1_result["passed"] is False
    assert stim1_result["n_stim1"] == 3


def test_inflated_1981_stimulus_rows_rejected():
    """REGRESSION: Inflated stimulus-row vectors must be rejected.
    
    Previously, 1981 stimulus presentation rows (not trial anchors)
    were incorrectly used. This test ensures validation catches such
    inflated event sets by checking for proper p1 anchor semantics.
    """
    # Simulate inflated data with many stimulus rows per trial
    # This would have multiple codes per "trial" without proper filtering
    n_trials = 135
    n_rows_per_trial = 4  # p1, p2, p3, p4
    
    codes = []
    for _ in range(n_trials):
        # Wrong: includes all stimulus presentations
        codes.extend([101, 102, 103, 104])  # p1, p2, p3, p4
    
    df = pd.DataFrame({"codes": codes})
    
    # This should fail because not all codes are 101 (p1)
    result = validate_all_code101(df)
    assert result["passed"] is False
    assert 102 in result["other_codes"]  # p2 code present
    assert 103 in result["other_codes"]  # p3 code present
    assert 104 in result["other_codes"]  # p4 code present


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
