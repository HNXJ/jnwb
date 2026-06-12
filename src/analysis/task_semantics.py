"""Task semantics and validation for omission analysis.

Provides canonical constants, validation helpers, and semantic checking
for event codes, conditions, and alignment anchors.

Critical validation rules:
- CODE 100 (fix cue) is NOT a valid p1 anchor
- CODE 101 (task_event_2) is the CORRECT p1 stimulus onset anchor
- stimulus_number == 1 corresponds to code 100 (fixation cue)
- stimulus_number == 2 corresponds to code 101 (p1 stimulus)
- AAXB condition = condition number 4
- AAXB omission is at p3 (2062ms from p1 onset)
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .contracts.constants import (
    AAXB_CONDITION_NUMBER,
    AAXB_OMISSION_OFFSET_MS,
    AAXB_OMISSION_SLOT,
    EVENT_CODE_FIXATION_CUE,
    EVENT_CODE_P1_STIMULUS,
    EVENT_CODE_TO_STIMULUS_POS,
)


# ============================================================================
# Typed Blockers / Error Codes
# ============================================================================

BLOCKED_CODE100_AS_P1 = "BLOCKED_CODE100_AS_P1_ANCHOR"
BLOCKED_FIX_CUE_IN_P1_EVENTS = "BLOCKED_FIX_CUE_APPEARANCE_IN_P1_EVENTS"
BLOCKED_STIMULUS_NUMBER_1_AS_P1 = "BLOCKED_STIMULUS_NUMBER_1_TREATED_AS_P1"
BLOCKED_CODE101_MISMATCH_STIM2 = "BLOCKED_CODE101_DOES_NOT_HAVE_STIMULUS_NUMBER_2"
BLOCKED_INCORRECT_OMISSION_OFFSET = "BLOCKED_INCORRECT_OMISSION_OFFSET_CALCULATION"
BLOCKED_CONDITION_4_NOT_AAXB = "BLOCKED_CONDITION_4_NOT_VERIFIED_AS_AAXB"
BLOCKED_INFLATED_STIMULUS_ROWS = "BLOCKED_INFLATED_STIMULUS_ROWS_USED_AS_TRIAL_ANCHORS"
BLOCKED_SIGNAL_UNAVAILABLE = "BLOCKED_SIGNAL_UNAVAILABLE"
BLOCKED_EMPTY_EPOCHS = "BLOCKED_EMPTY_EPOCHS"


# ============================================================================
# Validation Functions
# ============================================================================

def validate_no_code100_in_p1_events(df: pd.DataFrame, context: str = "") -> dict[str, Any]:
    """Validate that no code 100 (fixation cue) events are present in p1 anchor set.
    
    Args:
        df: DataFrame with 'codes' column
        context: Description of the data being validated
        
    Returns:
        Validation result dict with 'passed', 'errors', 'n_code100', 'n_total'
    """
    result = {
        "passed": True,
        "errors": [],
        "n_code100": 0,
        "n_total": len(df),
        "context": context,
    }
    
    if "codes" not in df.columns:
        result["passed"] = False
        result["errors"].append("Missing 'codes' column")
        return result
    
    # Check for code 100
    code100_mask = df["codes"] == EVENT_CODE_FIXATION_CUE
    n_code100 = code100_mask.sum()
    result["n_code100"] = int(n_code100)
    
    if n_code100 > 0:
        result["passed"] = False
        result["errors"].append(
            f"{BLOCKED_CODE100_AS_P1}: Found {n_code100} code 100 (fixation cue) events. "
            f"Code 100 is NOT a valid p1 anchor. Use code {EVENT_CODE_P1_STIMULUS} (p1 stimulus)."
        )
    
    return result


def validate_no_fix_cue_appearance(df: pd.DataFrame, context: str = "") -> dict[str, Any]:
    """Validate that no "fix cue appearance" event types are present.
    
    Args:
        df: DataFrame with 'event_code_type' column
        context: Description of the data being validated
        
    Returns:
        Validation result dict
    """
    result = {
        "passed": True,
        "errors": [],
        "n_fix_cue": 0,
        "n_total": len(df),
        "context": context,
    }
    
    if "event_code_type" not in df.columns:
        # Column not present - can't validate, assume pass
        return result
    
    # Check for fix cue appearance
    fix_cue_mask = df["event_code_type"].str.contains("fix cue", case=False, na=False)
    n_fix_cue = fix_cue_mask.sum()
    result["n_fix_cue"] = int(n_fix_cue)
    
    if n_fix_cue > 0:
        result["passed"] = False
        result["errors"].append(
            f"{BLOCKED_FIX_CUE_IN_P1_EVENTS}: Found {n_fix_cue} 'fix cue appearance' events. "
            f"These are fixation cues, not p1 stimulus onsets."
        )
    
    return result


def validate_all_code101(df: pd.DataFrame, context: str = "") -> dict[str, Any]:
    """Validate that all events have code 101 (p1 stimulus onset).
    
    Args:
        df: DataFrame with 'codes' column
        context: Description of the data being validated
        
    Returns:
        Validation result dict
    """
    result = {
        "passed": True,
        "errors": [],
        "n_code101": 0,
        "n_other_codes": 0,
        "other_codes": [],
        "n_total": len(df),
        "context": context,
    }
    
    if "codes" not in df.columns:
        result["passed"] = False
        result["errors"].append("Missing 'codes' column")
        return result
    
    code101_mask = df["codes"] == EVENT_CODE_P1_STIMULUS
    n_code101 = code101_mask.sum()
    result["n_code101"] = int(n_code101)
    
    other_codes = df[~code101_mask]["codes"].unique().tolist()
    result["other_codes"] = other_codes
    result["n_other_codes"] = len(other_codes)
    
    if n_code101 != len(df):
        result["passed"] = False
        result["errors"].append(
            f"Expected all events to have code {EVENT_CODE_P1_STIMULUS}, "
            f"but found {len(df) - n_code101} events with other codes: {other_codes}"
        )
    
    return result


def validate_stimulus_number_2_for_code101(df: pd.DataFrame, context: str = "") -> dict[str, Any]:
    """Validate that code 101 events have stimulus_number == 2 (cross-check).
    
    Args:
        df: DataFrame with 'codes' and 'stimulus_number' columns
        context: Description of the data being validated
        
    Returns:
        Validation result dict
    """
    result = {
        "passed": True,
        "errors": [],
        "n_code101_stim2": 0,
        "n_code101_not_stim2": 0,
        "n_total": len(df),
        "context": context,
    }
    
    if "codes" not in df.columns or "stimulus_number" not in df.columns:
        # Can't validate without both columns
        return result
    
    # Filter to code 101 rows
    code101_mask = df["codes"] == EVENT_CODE_P1_STIMULUS
    code101_df = df[code101_mask]
    
    if len(code101_df) == 0:
        return result
    
    # Check stimulus_number
    stim2_mask = code101_df["stimulus_number"] == 2
    n_stim2 = stim2_mask.sum()
    result["n_code101_stim2"] = int(n_stim2)
    result["n_code101_not_stim2"] = int(len(code101_df) - n_stim2)
    
    if not stim2_mask.all():
        result["passed"] = False
        bad_stim_nums = code101_df[~stim2_mask]["stimulus_number"].unique().tolist()
        result["errors"].append(
            f"{BLOCKED_CODE101_MISMATCH_STIM2}: Code 101 events should have stimulus_number == 2, "
            f"but found stimulus_number values: {bad_stim_nums}"
        )
    
    return result


def validate_not_stimulus_number_1(df: pd.DataFrame, context: str = "") -> dict[str, Any]:
    """Validate that stimulus_number == 1 is NOT treated as p1.
    
    Args:
        df: DataFrame with 'stimulus_number' column
        context: Description of the data being validated
        
    Returns:
        Validation result dict
    """
    result = {
        "passed": True,
        "errors": [],
        "n_stim1": 0,
        "n_total": len(df),
        "context": context,
    }
    
    if "stimulus_number" not in df.columns:
        return result
    
    stim1_mask = df["stimulus_number"] == 1
    n_stim1 = stim1_mask.sum()
    result["n_stim1"] = int(n_stim1)
    
    if n_stim1 > 0:
        result["passed"] = False
        result["errors"].append(
            f"{BLOCKED_STIMULUS_NUMBER_1_AS_P1}: Found {n_stim1} rows with stimulus_number == 1. "
            f"stimulus_number == 1 corresponds to fixation cue (code 100), NOT p1 stimulus. "
            f"Use code 101 or stimulus_number == 2 for p1 onset."
        )
    
    return result


def validate_omission_offset(
    p1_onset_times: np.ndarray,
    omission_onset_times: np.ndarray,
    expected_offset_ms: float = AAXB_OMISSION_OFFSET_MS,
    tolerance_ms: float = 1.0,
) -> dict[str, Any]:
    """Validate that omission onset = p1 onset + expected offset.
    
    Args:
        p1_onset_times: Array of p1 onset times (seconds)
        omission_onset_times: Array of omission onset times (seconds)
        expected_offset_ms: Expected offset in milliseconds
        tolerance_ms: Tolerance for validation
        
    Returns:
        Validation result dict
    """
    result = {
        "passed": True,
        "errors": [],
        "expected_offset_ms": expected_offset_ms,
        "tolerance_ms": tolerance_ms,
        "actual_offsets_ms": [],
        "offset_mean_ms": None,
        "offset_std_ms": None,
        "offset_min_ms": None,
        "offset_max_ms": None,
    }
    
    if len(p1_onset_times) != len(omission_onset_times):
        result["passed"] = False
        result["errors"].append(
            f"Length mismatch: {len(p1_onset_times)} p1 times vs {len(omission_onset_times)} omission times"
        )
        return result
    
    if len(p1_onset_times) == 0:
        result["passed"] = False
        result["errors"].append("Empty input arrays")
        return result
    
    # Calculate actual offsets
    actual_offsets_s = omission_onset_times - p1_onset_times
    actual_offsets_ms = actual_offsets_s * 1000.0
    
    result["actual_offsets_ms"] = actual_offsets_ms.tolist()
    result["offset_mean_ms"] = float(actual_offsets_ms.mean())
    result["offset_std_ms"] = float(actual_offsets_ms.std())
    result["offset_min_ms"] = float(actual_offsets_ms.min())
    result["offset_max_ms"] = float(actual_offsets_ms.max())
    
    # Check if all offsets are within tolerance
    expected_offset_s = expected_offset_ms / 1000.0
    tolerance_s = tolerance_ms / 1000.0
    
    within_tolerance = np.abs(actual_offsets_s - expected_offset_s) <= tolerance_s
    n_within = within_tolerance.sum()
    n_total = len(within_tolerance)
    
    if n_within != n_total:
        result["passed"] = False
        result["errors"].append(
            f"{BLOCKED_INCORRECT_OMISSION_OFFSET}: {n_total - n_within}/{n_total} offsets "
            f"outside tolerance {tolerance_ms}ms. Expected {expected_offset_ms}ms, "
            f"got range {result['offset_min_ms']:.1f} - {result['offset_max_ms']:.1f}ms"
        )
    
    return result


def run_all_validations(df: pd.DataFrame, context: str = "") -> dict[str, Any]:
    """Run all validation checks on a DataFrame of event anchors.
    
    Args:
        df: DataFrame with event data
        context: Description of the data being validated
        
    Returns:
        Combined validation results
    """
    results = {
        "context": context,
        "all_passed": True,
        "validations": {},
        "errors": [],
    }
    
    # Run each validation
    validations = [
        ("no_code100", validate_no_code100_in_p1_events),
        ("no_fix_cue", validate_no_fix_cue_appearance),
        ("all_code101", validate_all_code101),
        ("stim2_crosscheck", validate_stimulus_number_2_for_code101),
        ("not_stim1", validate_not_stimulus_number_1),
    ]
    
    for name, validator in validations:
        result = validator(df, context)
        results["validations"][name] = result
        if not result["passed"]:
            results["all_passed"] = False
            results["errors"].extend(result["errors"])
    
    return results


# ============================================================================
# Event Code Helpers
# ============================================================================

def get_event_code_semantics(code: int) -> dict[str, Any]:
    """Get semantic information about an event code.
    
    Args:
        code: Event code number
        
    Returns:
        Dict with 'is_valid_p1_anchor', 'position', 'description'
    """
    position = EVENT_CODE_TO_STIMULUS_POS.get(code, "unknown")
    
    return {
        "code": code,
        "position": position,
        "is_valid_p1_anchor": code == EVENT_CODE_P1_STIMULUS,
        "is_fixation_cue": code == EVENT_CODE_FIXATION_CUE,
        "description": {
            EVENT_CODE_FIXATION_CUE: "fixation cue onset - NOT valid p1 anchor",
            EVENT_CODE_P1_STIMULUS: "p1 stimulus onset - VALID anchor",
        }.get(code, f"unknown code {code}"),
    }


def is_valid_p1_anchor_code(code: int) -> bool:
    """Check if an event code is a valid p1 stimulus anchor.
    
    Args:
        code: Event code number
        
    Returns:
        True if code is valid p1 anchor (code 101)
    """
    return code == EVENT_CODE_P1_STIMULUS


def is_fixation_cue_code(code: int) -> bool:
    """Check if an event code is a fixation cue (invalid as p1 anchor).
    
    Args:
        code: Event code number
        
    Returns:
        True if code is fixation cue (code 100)
    """
    return code == EVENT_CODE_FIXATION_CUE


# ============================================================================
# AAXB Omission Helpers
# ============================================================================

def calculate_aaxb_omission_onset(p1_onset_times: np.ndarray) -> np.ndarray:
    """Calculate AAXB omission onset times from p1 onset times.
    
    Args:
        p1_onset_times: Array of p1 onset times (seconds or ms)
        
    Returns:
        Array of omission onset times (same units as input)
    """
    # Determine if input is in seconds or milliseconds
    # p1 times in seconds are typically 100-10000 range
    # p1 times in ms would be much larger
    if np.mean(p1_onset_times) > 10000:  # Likely milliseconds
        return p1_onset_times + AAXB_OMISSION_OFFSET_MS
    else:  # Likely seconds
        return p1_onset_times + (AAXB_OMISSION_OFFSET_MS / 1000.0)


def get_aaxb_semantics() -> dict[str, Any]:
    """Get complete AAXB semantics information.
    
    Returns:
        Dict with AAXB condition information
    """
    return {
        "condition_label": "AAXB",
        "condition_numbers": [AAXB_CONDITION_NUMBER],
        "sequence": "A-A-X-B",
        "omission_slot": AAXB_OMISSION_SLOT,
        "omission_position": 3,  # p3
        "omission_offset_ms": AAXB_OMISSION_OFFSET_MS,
        "omission_offset_s": AAXB_OMISSION_OFFSET_MS / 1000.0,
        "p1_anchor_code": EVENT_CODE_P1_STIMULUS,
        "p1_anchor_event_type": "task_event_2",
        "correct_p1_stimulus_number": 2,
        "incorrect_p1_stimulus_number": 1,  # Fixation cue
    }
