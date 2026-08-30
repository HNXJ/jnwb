"""Permanent gates for canonical trial / unit / channel identity (2026-08-29, Hamm).

Two independently observed failure classes -- trial_num (per-block counter) and unit_id
(per-probe kilosort counter) both used as global identities -- justify deterministic prevention
rather than another agent instruction. These tests are the prevention.

The real-data tests are skipped when no NWB corpus is configured, but when a corpus IS present
they assert the identity SEMANTICS themselves, so a corpus change that breaks the assumption
fails here rather than silently mislabelling units downstream.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from omission.jnwb_ext.canonical_identity import (
    UNIT_IDENTITY_COLUMNS,
    assert_unique,
    assert_unique_channels,
    assert_unique_units,
    attach_unit_identity,
    forbid_identity_join,
    safe_merge,
)

SESSION = "sub-V182o_ses-260702"


# --------------------------------------------------------------------------- forbidden keys
@pytest.mark.parametrize("key", ["trial_num", "unit_id", "trial_index"])
def test_bare_local_counter_is_rejected(key):
    with pytest.raises(ValueError, match="LOCAL COUNTER"):
        forbid_identity_join([key])


@pytest.mark.parametrize("qualifier", ["probe", "group_name", "electrode_group"])
def test_probe_qualified_unit_id_is_allowed(qualifier):
    forbid_identity_join([qualifier, "unit_id"])  # (probe, unit_id) is globally unique


def test_probe_qualifier_does_not_rescue_trial_num():
    """trial_num is per-BLOCK, not per-probe -- a probe column does not make it unique."""
    with pytest.raises(ValueError, match="LOCAL COUNTER"):
        forbid_identity_join(["probe", "trial_num"])


def test_canonical_keys_pass():
    forbid_identity_join(["session_id", "unit_row_idx"])
    forbid_identity_join(["trial_id"])


# --------------------------------------------------------------------------- uniqueness gates
def test_assert_unique_reports_collisions_not_just_failure():
    frame = pd.DataFrame({"session_id": ["s"] * 3, "unit_row_idx": [0, 1, 1]})
    with pytest.raises(ValueError, match="1 collisions"):
        assert_unique_units(frame)


def test_assert_unique_missing_column_is_keyerror():
    with pytest.raises(KeyError, match="unit_row_idx"):
        assert_unique_units(pd.DataFrame({"session_id": ["s"]}))


def test_channel_identity_requires_a_probe_column():
    frame = pd.DataFrame({"session": ["s"] * 2, "local_index": [0, 0]})
    with pytest.raises(KeyError, match="not globally meaningful"):
        assert_unique_channels(frame)


def test_probe_local_channel_index_alone_would_collide_but_probe_separates_it():
    frame = pd.DataFrame({
        "session": ["s"] * 4,
        "probe": ["probeA", "probeA", "probeB", "probeB"],
        "local_index": [0, 1, 0, 1],
    })
    assert_unique_channels(frame)                      # (session, probe, local_index) is fine
    with pytest.raises(ValueError):                    # local_index alone is not
        assert_unique(frame, ["session", "local_index"], what="channel table")


# --------------------------------------------------------------------------- attach + merge
def test_attach_unit_identity_demotes_raw_unit_id_and_is_row_position():
    """The exact defect: unit_id repeats across probes; unit_row_idx must not."""
    units = pd.DataFrame({
        "unit_id": [0, 1, 0, 1],
        "group_name": ["probeA", "probeA", "probeB", "probeB"],
        "area": ["FEF", "FEF", "MT", "MT"],
    })
    out = attach_unit_identity(units, SESSION)
    assert list(out["unit_row_idx"]) == [0, 1, 2, 3]
    assert list(out["raw_unit_id"]) == [0, 1, 0, 1]
    assert out["raw_unit_id"].nunique() == 2 and out["unit_row_idx"].nunique() == 4
    for col in UNIT_IDENTITY_COLUMNS:
        assert col in out.columns


def test_safe_merge_rejects_the_join_that_mislabelled_six_units():
    """Reproduces the shape of the real bug: joining templates on the probe-local unit_id."""
    classification = pd.DataFrame({"unit_id": [0, 1, 0, 1], "area": ["FEF", "FEF", "MT", "MT"]})
    templates = pd.DataFrame({"unit_id": [0, 1], "is_o_plus": [True, False]})
    with pytest.raises(ValueError, match="LOCAL COUNTER"):
        safe_merge(classification, templates, on="unit_id", context="template join")


def test_safe_merge_on_row_position_is_one_to_one():
    left = pd.DataFrame({"session_id": [SESSION] * 3, "unit_row_idx": [0, 1, 2],
                         "area": ["FEF", "MT", "TEO"]})
    right = pd.DataFrame({"session_id": [SESSION] * 3, "unit_row_idx": [0, 1, 2],
                          "is_o_plus": [True, False, True]})
    merged = safe_merge(left, right, on=["session_id", "unit_row_idx"], context="template join")
    assert len(merged) == 3
    assert list(merged["area"]) == ["FEF", "MT", "TEO"]


def test_safe_merge_detects_fan_out():
    left = pd.DataFrame({"session_id": [SESSION], "unit_row_idx": [0]})
    right = pd.DataFrame({"session_id": [SESSION] * 2, "unit_row_idx": [0, 0]})
    with pytest.raises(ValueError, match="not unique"):
        safe_merge(left, right, on=["session_id", "unit_row_idx"])


# --------------------------------------------------------------------------- real-data gates
def _nwb_path() -> Path | None:
    root = os.environ.get("OMISSION_NWB_DIR")
    if not root:
        return None
    p = Path(root) / f"{SESSION}.nwb"
    return p if p.exists() else None


requires_corpus = pytest.mark.skipif(_nwb_path() is None,
                                     reason="OMISSION_NWB_DIR not configured or session absent")


@requires_corpus
def test_real_units_table_raw_unit_id_is_probe_local_not_session_unique():
    """Guards the ASSUMPTION, not just the code: if this ever becomes session-unique the
    surrounding doctrine needs revisiting rather than silently still holding."""
    from omission.jnwb_ext.session import OmissionSession

    units = OmissionSession(str(_nwb_path()))._units_df
    assert units["unit_id"].nunique() < len(units), (
        "raw unit_id is now session-unique; the probe-local assumption in "
        "canonical_identity.py must be re-derived rather than assumed"
    )
    out = attach_unit_identity(units, SESSION)
    assert_unique_units(out)
    assert out["unit_row_idx"].nunique() == len(units)


@requires_corpus
def test_real_lfp_channel_identity_is_unique_under_the_canonical_key():
    from omission.jnwb_ext.analog import load_lfp_epochs

    sm = load_lfp_epochs(_nwb_path(), alignment="p1", window_ms=(-500.0, 500.0),
                         missing_data="drop").signal_metadata
    assert_unique_channels(sm)
    # local_index alone is probe-local and WOULD collide -- that is why probe is in the key.
    assert sm["local_index"].nunique() < len(sm)


@requires_corpus
def test_real_trial_table_canonical_key_is_unique_where_trial_num_is_not():
    from omission.jnwb_ext.analog import load_lfp_epochs

    tm = load_lfp_epochs(_nwb_path(), alignment="p1", window_ms=(-500.0, 500.0),
                         missing_data="drop").trial_metadata
    assert tm["trial_id"].nunique() == len(tm)


@requires_corpus
def test_pilot_unit_class_table_uses_row_position_semantics():
    """The pilot's classification CSV must be keyed by row position, and must still agree with
    the units table row-for-row -- this is what makes its O+/O++ labels trustworthy."""
    from omission.jnwb_ext.session import OmissionSession

    csv = Path("omission/artifacts/data/pilot_v182o_260702_unitclass.csv")
    if not csv.exists():
        pytest.skip("pilot classification table not built")
    cls = pd.read_csv(csv).sort_values("unit_id")
    units = OmissionSession(str(_nwb_path()))._units_df
    assert np.array_equal(cls["unit_id"].to_numpy(), np.arange(len(units))), (
        "pilot unit_id is not a contiguous row position into the units table"
    )
    assert np.array_equal(cls["peak_channel_id"].to_numpy(), units["peak_channel_id"].to_numpy())
    assert np.array_equal(cls["area"].astype(str).to_numpy(), units["area"].astype(str).to_numpy())
