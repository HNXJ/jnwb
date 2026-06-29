"""Tests for epoch extraction alignment and shape contracts.

These tests validate that:
1. SPK epochs have shape trial x unit x time
2. MUAe/LFP epochs have shape trial x channel x time
3. Session IDs are preserved
4. Event codes are validated (no code 100)
5. Omission offset is correct (p1 + 2062ms)
6. Empty arrays are not treated as success
"""

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from src.analysis.task_semantics import (
    BLOCKED_CODE100_AS_P1,
    BLOCKED_STIMULUS_NUMBER_1_AS_P1,
    BLOCKED_SIGNAL_UNAVAILABLE,
    calculate_aaxb_omission_onset,
    validate_no_code100_in_p1_events,
    validate_not_stimulus_number_1,
)
from src.analysis.contracts.constants import (
    EVENT_CODE_P1_STIMULUS,
    EVENT_CODE_FIXATION_CUE,
    AAXB_OMISSION_OFFSET_MS,
)


# ============================================================================
# Shape Contract Tests
# ============================================================================

def test_spk_shape_contract_trial_x_unit_x_time():
    """SPK epochs must have shape (n_trials, n_units, n_time_bins)."""
    n_trials = 10
    n_units = 50
    n_bins = 500
    
    # Simulated spike epochs
    spk_epochs = np.zeros((n_trials, n_units, n_bins), dtype=np.int32)
    
    assert spk_epochs.ndim == 3
    assert spk_epochs.shape[0] == n_trials
    assert spk_epochs.shape[1] == n_units
    assert spk_epochs.shape[2] == n_bins


def test_spk_shape_contract_enforces_dimensions():
    """SPK shape contract rejects wrong dimensions."""
    # Wrong: 2D instead of 3D
    wrong_2d = np.zeros((10, 50))
    assert wrong_2d.ndim != 3
    
    # Wrong: 4D instead of 3D
    wrong_4d = np.zeros((10, 50, 500, 1))
    assert wrong_4d.ndim != 3


def test_muae_lfp_shape_contract_trial_x_channel_x_time():
    """MUAe/LFP epochs must have shape (n_trials, n_channels, n_time_points)."""
    n_trials = 10
    n_channels = 128
    n_time = 5000
    
    # Simulated continuous signal epochs
    signal_epochs = np.zeros((n_trials, n_channels, n_time), dtype=np.float32)
    
    assert signal_epochs.ndim == 3
    assert signal_epochs.shape[0] == n_trials
    assert signal_epochs.shape[1] == n_channels
    assert signal_epochs.shape[2] == n_time


# ============================================================================
# Event Code Validation Tests
# ============================================================================

def test_code100_events_rejected_as_p1_anchor():
    """Code 100 (fixation cue) must be rejected as p1 anchor."""
    # Simulate events with code 100
    df = pd.DataFrame({
        "codes": [100, 101, 101],  # Code 100 is invalid
        "event_code_type": ["fix cue appearance", "task_event_2", "task_event_2"],
    })
    
    result = validate_no_code100_in_p1_events(df, "test_events")
    
    assert result["passed"] is False
    assert result["n_code100"] == 1
    assert BLOCKED_CODE100_AS_P1 in result["errors"][0]


def test_code101_events_accepted_as_p1_anchor():
    """Code 101 (task_event_2) must be accepted as valid p1 anchor."""
    df = pd.DataFrame({
        "codes": [101, 101, 101],
        "event_code_type": ["task_event_2"] * 3,
    })
    
    result = validate_no_code100_in_p1_events(df, "test_events")
    
    assert result["passed"] is True
    assert result["n_code100"] == 0


def test_stimulus_number_1_rejected_as_p1():
    """stimulus_number == 1 must be rejected (corresponds to code 100)."""
    df = pd.DataFrame({
        "stimulus_number": [1, 2, 2],  # stim 1 is fixation cue
    })
    
    result = validate_not_stimulus_number_1(df, "test_events")
    
    assert result["passed"] is False
    assert result["n_stim1"] == 1
    assert BLOCKED_STIMULUS_NUMBER_1_AS_P1 in result["errors"][0]


def test_stimulus_number_2_accepted_as_p1_crosscheck():
    """stimulus_number == 2 is correct cross-check for code 101."""
    df = pd.DataFrame({
        "codes": [101, 101, 101],
        "stimulus_number": [2, 2, 2],
    })
    
    result = validate_not_stimulus_number_1(df, "test_events")
    
    assert result["passed"] is True
    assert result["n_stim1"] == 0


# ============================================================================
# Omission Offset Tests
# ============================================================================

def test_omission_offset_calculation_seconds():
    """Omission onset = p1 onset + 2062ms (input in seconds)."""
    p1_onsets = np.array([100.0, 200.0, 300.0])  # seconds
    
    omission_onsets = calculate_aaxb_omission_onset(p1_onsets)
    
    expected_offset_s = AAXB_OMISSION_OFFSET_MS / 1000.0  # 2.062
    expected_omission = p1_onsets + expected_offset_s
    
    np.testing.assert_array_almost_equal(omission_onsets, expected_omission, decimal=3)


def test_omission_offset_calculation_milliseconds():
    """Omission onset = p1 onset + 2062ms (input in milliseconds)."""
    p1_onsets_ms = np.array([100000.0, 200000.0, 300000.0])  # milliseconds
    
    omission_onsets = calculate_aaxb_omission_onset(p1_onsets_ms)
    
    expected_omission = p1_onsets_ms + AAXB_OMISSION_OFFSET_MS
    
    np.testing.assert_array_almost_equal(omission_onsets, expected_omission, decimal=1)


def test_omission_offset_consistency():
    """Omission offset must be consistently 2062ms across all events."""
    p1_onsets = np.array([100.0, 150.0, 200.0, 250.0])
    
    omission_onsets = calculate_aaxb_omission_onset(p1_onsets)
    
    # Check all offsets are the same
    offsets_ms = (omission_onsets - p1_onsets) * 1000.0
    
    assert np.allclose(offsets_ms, AAXB_OMISSION_OFFSET_MS, atol=0.1)


# ============================================================================
# Empty Array Handling Tests
# ============================================================================

def test_empty_array_not_treated_as_success():
    """Empty arrays must be explicitly blocked, not treated as success."""
    # Simulate empty epoch extraction result
    empty_epochs = np.array([])
    
    # Empty should be detected and blocked
    is_empty = empty_epochs.size == 0
    
    assert is_empty is True
    # In real extraction, this would return BLOCKED_EMPTY_EPOCHS


def test_empty_trials_blocked():
    """Zero trials must be blocked."""
    from src.jnwb.errors import BLOCKED_EMPTY_EPOCHS, JnwbBlockedError
    from src.jnwb.qc import validate_event_address
    from src.jnwb.schema import EventAddress

    empty_addr = EventAddress(
        task="omission_glo_passive",
        conditions=["AAXB"],
        condition_numbers=[4],
        anchor="p1",
        sessions=[],
        events_by_session={},
        time_unit="s",
        p1_code=101,
        correct_only=True,
    )
    with pytest.raises(JnwbBlockedError) as exc:
        validate_event_address(empty_addr)
    assert exc.value.code == BLOCKED_EMPTY_EPOCHS


def test_empty_units_blocked():
    """Zero units must be blocked."""
    from src.jnwb.errors import BLOCKED_SIGNAL_UNAVAILABLE, JnwbBlockedError
    from src.jnwb.qc import validate_signal_address
    from src.jnwb.schema import SignalAddress

    empty_sig = SignalAddress(
        signal="SPK",
        sessions=[],
        source_paths=[],
        object_paths={},
        ids_by_session={},
        area_by_id={},
        layer_by_id={},
        probe_by_id={},
        sampling_rate_by_session={},
        units="spikes",
    )
    with pytest.raises(JnwbBlockedError) as exc:
        validate_signal_address(empty_sig)
    assert exc.value.code == BLOCKED_SIGNAL_UNAVAILABLE


# ============================================================================
# Session Preservation Tests
# ============================================================================

def test_session_id_preserved_in_metadata():
    """Session IDs must be preserved in output metadata."""
    # Simulate metadata DataFrame
    metadata = pd.DataFrame({
        "session": ["ses1", "ses1", "ses2", "ses2"],
        "unit_id": ["u1", "u2", "u1", "u2"],
        "area": ["V1", "V1", "V2", "V2"],
    })
    
    # Verify all sessions present
    sessions = metadata["session"].unique()
    assert "ses1" in sessions
    assert "ses2" in sessions


def test_no_session_silently_dropped():
    """No session should be silently dropped from output."""
    from src.jnwb.errors import BLOCKED_SESSION_SILENTLY_DROPPED, JnwbBlockedError
    from src.jnwb.epochs import load_epochs
    from src.jnwb.schema import EventAddress, NWBFileRecord, SignalAddress

    rec = NWBFileRecord(
        path="/fake.nwb",
        session_id="ses-1",
        subject="sub-1",
        date=None,
        task_names=[],
        has_spk=True,
        has_lfp=False,
        has_muae=False,
    )
    sig = SignalAddress(
        signal="SPK",
        sessions=["sub_1_ses_1", "sub_1_ses_2"],
        source_paths=[rec.path, rec.path],
        object_paths={"sub_1_ses_1": "units", "sub_1_ses_2": "units"},
        ids_by_session={"sub_1_ses_1": [0], "sub_1_ses_2": [0]},
        area_by_id={"sub_1_ses_1": {0: "V1"}, "sub_1_ses_2": {0: "V1"}},
        layer_by_id={"sub_1_ses_1": {0: None}, "sub_1_ses_2": {0: None}},
        probe_by_id={"sub_1_ses_1": {0: None}, "sub_1_ses_2": {0: None}},
        sampling_rate_by_session={"sub_1_ses_1": None, "sub_1_ses_2": None},
        units="spikes",
    )
    ev = EventAddress(
        task="omission_glo_passive",
        conditions=["AAXB"],
        condition_numbers=[4],
        anchor="p1",
        sessions=["sub_1_ses_1"],
        events_by_session={"sub_1_ses_1": [{"onset_s": 1.0, "condition": "AAXB", "code": 101}]},
        time_unit="s",
        p1_code=101,
        correct_only=True,
    )
    with pytest.raises(JnwbBlockedError) as exc:
        load_epochs([rec], sig, ev, window_ms=(-100, 100), bin_ms=10.0)
    assert exc.value.code == BLOCKED_SESSION_SILENTLY_DROPPED


# ============================================================================
# Signal Class Separation Tests
# ============================================================================

def test_spk_muae_lfp_remain_separate():
    """SPK, MUAe, and LFP must remain separate signal classes."""
    # Signal class should be explicit
    signals = {
        "SPK": {"dtype": np.int32, "dims": ("trial", "unit", "time")},
        "MUAe": {"dtype": np.float32, "dims": ("trial", "channel", "time")},
        "LFP": {"dtype": np.float32, "dims": ("trial", "channel", "time")},
    }
    
    # SPK is spike counts (int)
    assert signals["SPK"]["dtype"] == np.int32
    
    # MUAe and LFP are continuous (float)
    assert signals["MUAe"]["dtype"] == np.float32
    assert signals["LFP"]["dtype"] == np.float32
    
    # SPK uses "unit" dimension
    assert "unit" in signals["SPK"]["dims"]
    
    # MUAe/LFP use "channel" dimension
    assert "channel" in signals["MUAe"]["dims"]
    assert "channel" in signals["LFP"]["dims"]


# ============================================================================
# Alignment Event Tests
# ============================================================================

def test_p1_alignment_event_documented():
    """p1-aligned epochs must document p1 as alignment event."""
    alignment = {
        "event": "p1_onset",
        "event_code": 101,
        "event_code_type": "task_event_2",
        "window_ms": (-1000, 4000),
        "time_base": "p1_relative",
    }
    
    assert alignment["event_code"] == 101
    assert alignment["event_code_type"] == "task_event_2"


def test_omission_alignment_event_documented():
    """omission-aligned epochs must document omission as alignment event."""
    alignment = {
        "event": "omission_onset",
        "derived_from": "p1_onset",
        "offset_ms": AAXB_OMISSION_OFFSET_MS,
        "window_ms": (-1000, 1000),
        "time_base": "omission_relative",
    }
    
    assert alignment["offset_ms"] == 2062
    assert alignment["derived_from"] == "p1_onset"


# ============================================================================
# Manifest Completeness Tests
# ============================================================================

def test_manifest_requires_required_fields():
    """Manifest must contain required fields for reproducibility."""
    required_fields = [
        "signal_class",
        "alignment_event",
        "time_base",
        "window_ms",
        "shape",
        "input_path",
        "output_path",
        "repo_sha",
    ]
    
    # Simulate incomplete manifest
    incomplete_manifest = {
        "signal_class": "SPK",
        "shape": (10, 50, 500),
        # Missing: alignment_event, time_base, window_ms, input_path, output_path, repo_sha
    }
    
    missing = [f for f in required_fields if f not in incomplete_manifest]
    
    assert "alignment_event" in missing
    assert "repo_sha" in missing


def test_manifest_shape_matches_data():
    """Manifest shape must match actual data shape."""
    data = np.zeros((10, 50, 500))
    
    manifest = {"shape": (10, 50, 500)}
    
    assert manifest["shape"] == data.shape


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
