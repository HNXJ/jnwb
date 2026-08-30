"""Regression gate for channel addressing (2026-08-29, bug-channel-id-probe-local-20260829).

THE FAILURE THIS REPRODUCES
    A unit's ``peak_channel_id`` is a ROW INDEX into the session-global NWB electrodes table.
    The old resolve_channel_sets matched it against ``signal_metadata['channel_id']`` and took
    the first hit. That column is session-unique in sub-V182o_ses-260702 (512 of 512) but
    PROBE-LOCAL in sub-C31o_ses-230816_rec (128 unique across 384 rows, 0..127 repeated on each
    of three probes).

    Consequences measured on C31o: 255 of 357 units silently dropped (peak_channel_id 128..378
    never matches a 0..127 column), and 0 wrong-probe hits only by luck of row ordering -- any
    reordering of signal_metadata would have returned another probe's channel with no error.

    The synthetic fixture below reproduces exactly that ID-space geometry, so the bare
    channel_id match cannot silently come back.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from omission.jnwb_ext.spk_lfp_pilot import C2_NEAR_MAX, C2_NEAR_MIN, C3_FAR_MIN, resolve_channel_sets


def _probe_local_metadata(n_probes: int = 3, n_per_probe: int = 128) -> pd.DataFrame:
    """C31o geometry: channel_id restarts at 0 on every probe; local_index likewise."""
    rows = []
    for p in range(n_probes):
        for i in range(n_per_probe):
            rows.append({"session": "synthetic", "probe": f"probe{chr(65 + p)}",
                         "channel_id": i, "local_index": i})
    return pd.DataFrame(rows)


def _session_unique_metadata(n_probes: int = 4, n_per_probe: int = 128) -> pd.DataFrame:
    """V182o geometry: channel_id is globally unique and equals the electrode row."""
    rows = []
    for p in range(n_probes):
        for i in range(n_per_probe):
            rows.append({"session": "synthetic", "probe": f"probe{chr(65 + p)}",
                         "channel_id": p * n_per_probe + i, "local_index": i})
    return pd.DataFrame(rows)


# ------------------------------------------------------- the C31o failure, reproduced
def test_probe_local_channel_id_is_the_hazard_geometry():
    """Guards the premise: if this stops being true the test below proves nothing."""
    sm = _probe_local_metadata()
    assert sm["channel_id"].nunique() == 128 and len(sm) == 384
    assert (sm.groupby("channel_id").size() == 3).all()   # every id on all three probes


@pytest.mark.parametrize("row", [0, 50, 127, 128, 200, 255, 261, 340, 383])
def test_every_electrode_row_resolves_on_its_own_probe(row):
    """The old code dropped rows >= 128 entirely and matched rows < 128 on the FIRST probe.
    Row-position addressing must place every row on the probe that actually owns it."""
    sm = _probe_local_metadata()
    sets = resolve_channel_sets(sm, row, n_electrodes=len(sm))
    assert sets is not None, f"electrode row {row} failed to resolve"
    assert sets.c0_own.tolist() == [row]
    expected_probe = sm.loc[row, "probe"]
    for name, idx in sets.as_dict().items():
        if len(idx):
            assert (sm.loc[idx, "probe"] == expected_probe).all(), (
                f"{name} for row {row} leaked off {expected_probe}")


def test_units_on_later_probes_are_no_longer_silently_dropped():
    """The exact C31o symptom: peak_channel_id 128..383 previously matched nothing."""
    sm = _probe_local_metadata()
    resolved = sum(resolve_channel_sets(sm, r, n_electrodes=len(sm)) is not None
                   for r in range(len(sm)))
    assert resolved == len(sm), f"only {resolved}/{len(sm)} electrode rows resolved"


def test_first_match_on_channel_id_would_have_been_wrong():
    """Demonstrates the defect directly rather than asserting the fix in the abstract."""
    sm = _probe_local_metadata()
    row = 200                                   # probeB owns this electrode
    legacy_hits = sm.index[sm["channel_id"] == row].to_numpy()
    assert len(legacy_hits) == 0, "fixture no longer reproduces the drop-out failure"

    row_b = 50                                  # probeA owns electrode row 50
    legacy_first = int(sm.index[sm["channel_id"] == row_b].to_numpy()[0])
    assert sm.loc[legacy_first, "probe"] == "probeA"
    assert len(sm.index[sm["channel_id"] == row_b]) == 3, (
        "channel_id 50 must be ambiguous across three probes -- that ambiguity is the hazard")
    # Row-position addressing is unambiguous where first-match was merely lucky.
    assert resolve_channel_sets(sm, row_b, n_electrodes=len(sm)).c0_own.tolist() == [row_b]


# ------------------------------------------------------- completeness guard
def test_incomplete_signal_metadata_raises_rather_than_mis_addressing():
    """If the LFP loader ever drops a channel, row position stops being the electrode id."""
    sm = _probe_local_metadata().drop(index=5).reset_index(drop=True)
    with pytest.raises(ValueError, match="Row position no longer indexes"):
        resolve_channel_sets(sm, 200, n_electrodes=384)


def test_count_preserving_reorder_is_caught_by_the_probe_sequence_guard():
    """The hole independent verification found and demonstrated (2026-08-29).

    A row COUNT is necessary but not sufficient. Moving the probeC block to the front preserves
    the count, passes the count guard, and previously resolved electrode row 300 to probeB
    instead of its true probeC with NO error raised. The order guard must catch it.
    """
    sm = _probe_local_metadata()
    probes = sm["probe"].tolist()                       # electrodes-table order
    moved = pd.concat([sm[sm.probe == "probeC"], sm[sm.probe != "probeC"]]).reset_index(drop=True)
    assert len(moved) == len(sm)                        # count guard would pass

    with pytest.raises(ValueError, match="REORDERED"):
        resolve_channel_sets(moved, 300, n_electrodes=len(moved), electrode_probes=probes)

    # and without the order guard it silently returns the WRONG probe -- the defect itself
    silent = resolve_channel_sets(moved, 300, n_electrodes=len(moved))
    assert silent is not None
    assert moved.loc[int(silent.c0_own[0]), "probe"] != sm.loc[300, "probe"]


def test_full_reversal_is_caught():
    sm = _probe_local_metadata()
    probes = sm["probe"].tolist()
    rev = sm.iloc[::-1].reset_index(drop=True)
    with pytest.raises(ValueError, match="REORDERED"):
        resolve_channel_sets(rev, 300, n_electrodes=len(rev), electrode_probes=probes)


def test_probe_sequence_guard_passes_on_correct_order():
    """Complement: the guard must not fire on well-ordered metadata, or it would block everything."""
    sm = _probe_local_metadata()
    probes = sm["probe"].tolist()
    for row in (0, 127, 200, 383):
        s = resolve_channel_sets(sm, row, n_electrodes=len(sm), electrode_probes=probes)
        assert s is not None and s.c0_own.tolist() == [row]


def test_probe_sequence_length_mismatch_is_caught():
    sm = _probe_local_metadata()
    with pytest.raises(ValueError, match="entries but signal_metadata"):
        resolve_channel_sets(sm, 10, electrode_probes=sm["probe"].tolist()[:-1])


def test_out_of_range_row_returns_none_not_an_exception():
    sm = _probe_local_metadata()
    assert resolve_channel_sets(sm, len(sm), n_electrodes=len(sm)) is None
    assert resolve_channel_sets(sm, -1, n_electrodes=len(sm)) is None


# ------------------------------------------------------- V182o must be a no-op
def test_session_unique_geometry_is_unchanged_by_the_fix():
    """Where channel_id == electrode row, row-position addressing and the old channel_id match
    agree exactly -- which is why the pilot's numbers must not move."""
    sm = _session_unique_metadata()
    for row in (0, 1, 127, 128, 300, 511):
        legacy = int(sm.index[sm["channel_id"] == row].to_numpy()[0])
        assert legacy == row
        assert resolve_channel_sets(sm, row, n_electrodes=len(sm)).c0_own.tolist() == [row]


def test_geometry_of_c1_c2_c3_is_preserved():
    """Identity changed; within-probe geometry must not have."""
    sm = _session_unique_metadata()
    own = 128 + 60                                    # probeB, local_index 60
    sets = resolve_channel_sets(sm, own, n_electrodes=len(sm))
    local = sm["local_index"].to_numpy()
    own_local = local[own]

    assert own not in sets.c1_own_excluded.tolist()
    assert len(sets.c1_own_excluded) == 127
    for idx in sets.c2_nearby:
        assert C2_NEAR_MIN <= abs(int(local[idx]) - own_local) <= C2_NEAR_MAX
    for idx in sets.c3_distant:
        assert abs(int(local[idx]) - own_local) >= C3_FAR_MIN
    assert set(sets.c2_nearby.tolist()).isdisjoint(sets.c3_distant.tolist())
