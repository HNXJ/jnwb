"""Regression tests for omission.jnwb_ext.omission_identity's unit-identity contract.

2026-08-15: build_noise_controlled_spike_matrix, build_noise_controlled_spike_matrix_with_
subblocks, decode_identity_cycle_deconfound, and decode_time_from_features all used
units_df["unit_id"].tolist() -- the per-probe-local kilosort column -- as the argument to
session.get_spike_times(), instead of the row-position identity that get_spike_times's own
primary lookup actually uses (see jnwb/session.py:get_spike_times, jnwb/trajectory.py's
documented sub-C31o_ses-230816_rec collision, jnwb/unit_classification.py,
jnwb/structured_identity_m2a.py). A unit_id column value that happens to equal another row's
position silently fetched that OTHER unit's real spike train. Fixed to use units_df.index.

This module previously had no dedicated test file at all (a gap already flagged in
context/handoff/2026-08-15-prgs-prepare/JNWB_ARCHITECTURE.md).
"""

import numpy as np
import pandas as pd

from omission.jnwb_ext.omission_identity import (
    build_noise_controlled_spike_matrix,
    build_noise_controlled_spike_matrix_with_subblocks,
    decode_identity_cycle_deconfound,
    decode_time_from_features,
)


class _StubSession:
    """Minimal duck-typed session exercising only get_units()/get_spike_times() -- no real
    NWB access. The 'unit_id' column is deliberately non-identity to row position and even
    collides with another row's own row-index value, reproducing the exact shape of a real
    gapped-kilosort-id session (see jnwb/trajectory.py's documented collision)."""

    def __init__(self, n_rows: int = 3):
        # Row 1's unit_id column value (2.0) collides with row 2's own row position -- this is
        # the precise failure mode: a caller using the column instead of the index would
        # silently fetch row 2's spike train while asking for "unit_id 2.0" at row 1.
        self._units = pd.DataFrame({"unit_id": [10.0, 2.0, 7.0][:n_rows]})
        # Ground truth is keyed by ROW POSITION -- the canonical identity.
        self._spikes_by_row = {
            0: np.array([0.05, 0.06]),
            1: np.array([0.05, 0.06, 0.07, 0.08]),
            2: np.array([0.05]),
        }

    def get_units(self, area=None, quality=None, firing_rate_range=None):
        return self._units.copy()

    def get_epochs(self, phase=None, condition=None, correct_only=True):
        raise NotImplementedError("not needed by these tests")

    def get_spike_times(self, unit_id):
        # Mirrors OmissionSession.get_spike_times's real primary lookup: row position.
        key = int(unit_id)
        return self._spikes_by_row.get(key)


def test_build_noise_controlled_spike_matrix_uses_row_position_identity():
    session = _StubSession()
    epochs_a = pd.DataFrame({"start_time": [0.0, 10.0]})
    epochs_b = pd.DataFrame({"start_time": [20.0, 30.0]})
    X, labels, unit_ids = build_noise_controlled_spike_matrix(
        session, area="V1", epochs_cond_a=epochs_a, epochs_cond_b=epochs_b,
        time_window_ms=(0.0, 200.0),
    )
    assert unit_ids == [0, 1, 2], (
        "unit identity must be the units_df row position, not the 'unit_id' column "
        "(row 1's unit_id column value 2.0 collides with row 2's own row position)"
    )
    assert X.shape == (len(labels), 3)


def test_build_noise_controlled_spike_matrix_with_subblocks_uses_row_position_identity():
    session = _StubSession()
    epochs_a = pd.DataFrame({"start_time": [0.0, 10.0, 20.0, 30.0]})
    epochs_b = pd.DataFrame({"start_time": [40.0, 50.0, 60.0, 70.0]})
    X, labels, unit_ids, quartiles = build_noise_controlled_spike_matrix_with_subblocks(
        session, area="V1", epochs_cond_a=epochs_a, epochs_cond_b=epochs_b,
        time_window_ms=(0.0, 200.0),
    )
    assert unit_ids == [0, 1, 2]


def test_decode_time_from_features_uses_row_position_identity(monkeypatch):
    session = _StubSession()
    epochs = pd.DataFrame({"start_time": [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]})

    captured = {}
    orig_get_spike_times = session.get_spike_times

    def spy(unit_id):
        captured.setdefault("unit_ids", []).append(unit_id)
        return orig_get_spike_times(unit_id)

    monkeypatch.setattr(session, "get_spike_times", spy)
    decode_time_from_features(session, area="V1", epochs=epochs, time_window_ms=(0.0, 200.0))
    assert captured["unit_ids"] == [0, 1, 2], (
        "decode_time_from_features must query spikes by row position, not the 'unit_id' column"
    )


def test_decode_identity_cycle_deconfound_uses_row_position_identity(monkeypatch):
    session = _StubSession()

    def epochs_for(condition):
        # Two widely-separated cycles so detect_trial_cycles finds >=2 cycles, and >=6 trials
        # per condition (the function's own minimum).
        near_zero = [0.0, 1.0, 2.0]
        near_far = [10_000.0, 10_001.0, 10_002.0]
        return pd.DataFrame({"start_time": near_zero + near_far})

    monkeypatch.setattr(session, "get_epochs", lambda phase=None, condition=None, correct_only=True: epochs_for(condition))

    captured = {}
    orig_get_spike_times = session.get_spike_times

    def spy(unit_id):
        captured.setdefault("unit_ids", []).append(unit_id)
        return orig_get_spike_times(unit_id)

    monkeypatch.setattr(session, "get_spike_times", spy)
    result = decode_identity_cycle_deconfound(session, area="V1", slot_key="p2")
    assert result["status"] in ("success", "insufficient_cycles")
    assert set(captured["unit_ids"]) == {0, 1, 2}, (
        "decode_identity_cycle_deconfound must query spikes by row position, not the "
        "'unit_id' column"
    )
