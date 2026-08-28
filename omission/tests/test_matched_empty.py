"""Regression tests for omission.jnwb_ext.matched_empty (P3, 2026-08-27).

Covers the real defect found and fixed during this build: passing the long-form (duplicated-
onset) table directly into detect_trial_cycles inflated cycle count past physical trial count.
"""
from __future__ import annotations

import os

import pytest

import omission as oa
from omission.jnwb_ext.matched_empty import build_matched_empty_table
from omission.jnwb_ext.unit_classification import DELAY_WINDOW_MS, SLOT_WINDOW_MS, OM_BASE_GAP_MS, OM_BASE_LEAD_MS

NWB_DIR = os.environ.get("OMISSION_NWB_DIR", "D:/nwb/omission")
SESSION_PATH = os.path.join(NWB_DIR, "sub-C31o_ses-230816_rec.nwb")


@pytest.mark.skipif(not os.path.exists(SESSION_PATH), reason="requires real NWB corpus access")
def test_matched_empty_table_structure_and_cycle_dedup():
    session = oa.read(SESSION_PATH)
    table = build_matched_empty_table(session)
    assert not table.empty

    n_unique_trials = table["p1_onset_s"].nunique()
    n_cycles = table["cycle_id"].nunique()
    # cycles must be far fewer than physical trials -- the exact failure mode of the bug this
    # test guards against (598 "cycles" from ~340 trials before the dedup-before-cycling fix)
    assert n_cycles < n_unique_trials, (
        f"cycle_id ({n_cycles}) should be far fewer than physical trials ({n_unique_trials}); "
        "this exact inversion was the symptom of the pre-fix duplicated-onset bug"
    )

    # every row for the same physical trial must carry the identical cycle_id
    inconsistent = table.groupby("p1_onset_s")["cycle_id"].nunique()
    assert (inconsistent <= 1).all(), "rows sharing a physical trial's onset disagree on cycle_id"

    assert table["cycle_id"].isna().sum() == 0

    counts = table["comparator_type"].value_counts()
    expected_types = {"omission", "local_pre_omission_delay", "post_omission_delay",
                       "trial_delay_mean", "stimulus_present_control"}
    assert set(counts.index) == expected_types
    # the four same-trial comparator types must have identical row counts (one row per
    # omission trial each); stimulus_present_control is drawn from a separate (control) pool
    # and is only guaranteed equal count by construction (resampled to match n_om), not identity
    same_trial_types = ["omission", "local_pre_omission_delay", "post_omission_delay", "trial_delay_mean"]
    assert counts[same_trial_types].nunique() == 1

    is_empty_by_type = table.groupby("comparator_type")["is_empty"].first()
    assert is_empty_by_type["omission"] == False
    assert is_empty_by_type["stimulus_present_control"] == False
    assert is_empty_by_type["local_pre_omission_delay"] == True
    assert is_empty_by_type["post_omission_delay"] == True
    assert is_empty_by_type["trial_delay_mean"] == True


@pytest.mark.skipif(not os.path.exists(SESSION_PATH), reason="requires real NWB corpus access")
def test_matched_empty_windows_disjoint_from_omission_slot_per_trial():
    session = oa.read(SESSION_PATH)
    table = build_matched_empty_table(session)
    same_trial = table[table["trial_role"] == "omission_trial"]

    for (_, cond, slot, idx), group in same_trial.groupby(["p1_onset_s", "condition", "omission_slot", "trial_index"]):
        rows = group.set_index("comparator_type")
        om_lo, om_hi = rows.loc["omission", "window_ms"]
        pre_lo, pre_hi = rows.loc["local_pre_omission_delay", "window_ms"]
        post_lo, post_hi = rows.loc["post_omission_delay", "window_ms"]
        # pre-omission window must end at or before the omission window starts (no overlap)
        assert pre_hi <= om_lo, f"local_pre_omission_delay overlaps omission slot for {cond}/{slot}"
        # post-omission window must start at or after the omission window ends (no overlap)
        assert post_lo >= om_hi, f"post_omission_delay overlaps omission slot for {cond}/{slot}"


def test_preceding_identity_matches_condition_string_directly():
    from omission.jnwb_ext.matched_empty import _preceding_identity
    assert _preceding_identity("AAXB", 3) == "A"   # slot 3 (index 2) preceded by index 1 = "A"
    assert _preceding_identity("BBBX", 4) == "B"   # slot 4 preceded by index 2 = "B"
    assert _preceding_identity("RRXR", 3) == "R"
    assert _preceding_identity("AXAB", 2) == "A"   # slot 2 preceded by index 0 = "A"


@pytest.mark.skipif(not os.path.exists(SESSION_PATH), reason="requires real NWB corpus access")
def test_physical_trial_onsets_unique_before_cycle_dedup():
    """Pins the empirical invariant build_matched_empty_table's cycle assignment relies on:
    physical trial start_time never coincides across trials, within a condition or globally.
    Verified against the real corpus 2026-08-27 (0 duplicates, both scopes) -- this test fails
    loudly if a future session or condition set ever violates it, rather than silently
    collapsing two distinct physical trials into one cycle_id."""
    session = oa.read(SESSION_PATH)
    table = build_matched_empty_table(session)
    om = table[table["trial_role"] == "omission_trial"]
    # every omission physical trial expands to exactly 4 comparator rows -- never more, which
    # would indicate two distinct physical trials merged under one onset key
    n_rows_per_om_trial = om.groupby("p1_onset_s").size()
    assert set(n_rows_per_om_trial.unique()) == {4}
    # a control trial's onset MAY repeat -- the same physical control trial can legitimately be
    # resampled as the matched control for multiple distinct omission events (independent draws
    # per (condition, slot) iteration within one family) -- but every row sharing that onset must
    # still resolve to exactly one cycle_id (covered by test_matched_empty_table_structure_and_cycle_dedup)


def test_slot_to_delay_matches_immediately_following_delay_window():
    # post_omission_delay for slot N must be exactly DELAY_WINDOW_MS["dN"], not shifted
    from omission.jnwb_ext.matched_empty import SLOT_TO_DELAY
    for slot, delay_key in SLOT_TO_DELAY.items():
        assert delay_key == f"d{slot}"
        lo, hi = DELAY_WINDOW_MS[delay_key]
        slot_lo, slot_hi = SLOT_WINDOW_MS[slot]
        assert lo >= slot_hi, f"d{slot} window does not start at/after p{slot} ends"
