"""An identifier must survive a composition boundary, rather than being rebuilt from position.

Two boundaries are covered.

``vflip_from_lfp`` / ``vflip`` -> ``label_layers``
    ``crossover_contact`` is a PSD **row** index when ``probe_geometry`` is omitted from
    ``vflip`` and a **shaft-rank** index when it is supplied. ``label_layers`` always reads
    it as a shaft rank. The two spaces coincide on a probe whose electrode-table row order
    is depth order, which is why a permutation that reorders the table and the PSD together
    cannot separate them. The fixture here is a two-bank probe, where they differ.

``map_peak_channel_to_area`` / ``classify_layer_from_depth`` -> ``enrich_units_dataframe``
    The join is on ``peak_channel_id``. A join on row position would agree with it whenever
    the units happen to be listed in electrode-table order, so every fixture below is built
    so that the two disagree, and one test asserts that disagreement directly. A fixture on
    which a positional join gives the same answer as an identifier join tests nothing.
"""

from typing import Dict, List

import numpy as np
import pandas as pd
import pytest

import jnwb
from jnwb.testing.synth import synth_laminar_motif

# --------------------------------------------------------------------------------------
# The two-bank probe
# --------------------------------------------------------------------------------------

N_CH = 24
PITCH_UM = 50.0
#: Deliberately asymmetric. A crossover near the centre of the shaft is close to its own
#: reflection, so a fixture built on one cannot separate a reordering from a reversal.
C_CROSSOVER = 6.0

#: Table row r holds shaft contact ``BANKS[r]``: rows 0..11 are the even contacts and rows
#: 12..23 the odd ones. A probe whose channel numbering banks the columns is wired this way.
BANKS = np.concatenate([np.arange(0, N_CH, 2), np.arange(1, N_CH, 2)])


def _contact_key(channel_id: str) -> int:
    return int(channel_id.split("_")[1])


def _sorted_ids(ids) -> List[str]:
    return sorted(ids, key=_contact_key)


@pytest.fixture(scope="module")
def shaft():
    """A linear probe whose electrode table is in depth order."""
    return synth_laminar_motif(
        n_channels=N_CH,
        n_samples=6000,
        fs=1000.0,
        c_crossover=C_CROSSOVER,
        orientation="superficial_to_deep",
        pitch_um=PITCH_UM,
        rng=0,
    )


@pytest.fixture(scope="module")
def two_bank(shaft):
    """The same physical probe, acquired in two-bank order.

    ``channel_id`` names the physical contact, so a label is comparable against the
    depth-ordered arm contact by contact rather than row by row.
    """
    electrodes = pd.DataFrame(
        {
            "x": np.zeros(N_CH),
            "y": np.zeros(N_CH),
            "z": (np.arange(N_CH, dtype=float) * PITCH_UM)[BANKS],
            "channel_id": [f"ch_{i}" for i in BANKS],
        }
    )
    geometry = jnwb.probe_geometry(electrodes, units="um", nominal_pitch=PITCH_UM)
    # The acquisition array follows the table, as it does on disk.
    return geometry, shaft.lfp[BANKS], list(electrodes["channel_id"])


@pytest.fixture(scope="module")
def depth_ordered_truth(shaft) -> Dict[str, str]:
    """Layer per physical contact, from the probe whose table is already in depth order."""
    result = jnwb.vflip_from_lfp(shaft.lfp, shaft.fs, probe_geometry=shaft.probe_geometry)
    assert result.accepted, "the reference arm must locate the motif, or it is not a truth"
    return dict(jnwb.label_layers(result, shaft.probe_geometry))


# --------------------------------------------------------------------------------------
# The fixture must be able to tell the two index spaces apart
# --------------------------------------------------------------------------------------


def test_the_two_bank_table_is_not_in_depth_order(two_bank):
    """Without this the two index spaces coincide and nothing below can discriminate."""
    geometry, _, _ = two_bank
    linear_order = np.asarray(geometry.linear_order)

    assert geometry.is_linear, "the fixture must still be a single linear shaft"
    assert geometry.nominal_pitch == pytest.approx(PITCH_UM)
    assert not np.array_equal(linear_order, np.arange(N_CH)), (
        "the electrode table is in depth order, so PSD-row space and shaft-rank space are "
        "the same space and no assertion in this module can separate them"
    )
    # Every contact appears exactly once: a reordering, not a subset.
    assert sorted(linear_order.tolist()) == list(range(N_CH))


def test_geometry_at_both_ends_recovers_the_depth_ordered_labels(two_bank, depth_ordered_truth):
    """The control. A failure below is then about the index space, not a dead fixture.

    Were the motif unlocatable, or the support gate to refuse, every label would be ``na``
    and the geometry-omitted comparison would agree for a reason that has nothing to do
    with identifiers.
    """
    geometry, lfp, ids = two_bank
    result = jnwb.vflip_from_lfp(lfp, 1000.0, probe_geometry=geometry)

    assert result.accepted
    assert result.crossover_contact is not None
    labels = jnwb.label_layers(result, geometry)

    assert set(labels) == set(ids)
    assert set(labels.values()) != {"na"}, "an all-na labelling would agree with anything"
    differing = [cid for cid in ids if labels[cid] != depth_ordered_truth[cid]]
    assert differing == [], f"geometry at both ends must reproduce the truth: {differing}"


# --------------------------------------------------------------------------------------
# The boundary itself
# --------------------------------------------------------------------------------------


def test_layer_labels_survive_a_vflip_computed_without_geometry(two_bank, depth_ordered_truth):
    """Either the labels are the depth-ordered ones, or the boundary refuses the result.

    Returning a different layer for a contact, with ``accepted=True`` and no warning, is
    the one outcome this asserts against.
    """
    geometry, lfp, ids = two_bank
    result = jnwb.vflip_from_lfp(lfp, 1000.0)

    try:
        labels = jnwb.label_layers(result, geometry)
    except ValueError:
        # Refusing a result computed in another index space is the other honest answer.
        return

    differing = [cid for cid in ids if labels[cid] != depth_ordered_truth[cid]]
    assert differing == [], (
        f"{len(differing)} of {N_CH} contacts were given a different layer: "
        + str({cid: f"{depth_ordered_truth[cid]}->{labels[cid]}" for cid in differing})
    )


# --------------------------------------------------------------------------------------
# The bad-channel mask crosses the same boundary and is expected to survive it
# --------------------------------------------------------------------------------------

#: Table rows, not shaft ranks. Which of the two a reader means is the whole question.
MASKED_ROWS = [3, 20]


def test_a_bad_channel_mask_names_the_same_contacts_at_both_ends(two_bank):
    """``vflip`` reorders the mask internally; the contacts it excludes must not move."""
    geometry, lfp, ids = two_bank
    mask = np.zeros(N_CH, dtype=bool)
    mask[MASKED_ROWS] = True
    expected = _sorted_ids(ids[r] for r in MASKED_ROWS)

    result = jnwb.vflip_from_lfp(lfp, 1000.0, probe_geometry=geometry, bad_channel_mask=mask)
    assert result.accepted, "the masked fixture must still locate the motif"
    assert result.n_missing == len(MASKED_ROWS)

    passed_again = jnwb.label_layers(result, geometry, bad_channel_mask=mask)
    carried_on_result = jnwb.label_layers(result, geometry)

    assert _sorted_ids(k for k, v in passed_again.items() if v == "na") == expected
    assert _sorted_ids(k for k, v in carried_on_result.items() if v == "na") == expected


def test_the_mask_fixture_discriminates_between_the_two_index_spaces(two_bank):
    """Reading the same mask as shaft ranks must name a different set of contacts.

    Without this the test above passes on a probe where both readings agree, which is the
    state it exists to rule out.
    """
    geometry, _, ids = two_bank
    linear_order = np.asarray(geometry.linear_order)

    as_table_rows = _sorted_ids(ids[r] for r in MASKED_ROWS)
    as_shaft_ranks = _sorted_ids(ids[linear_order[r]] for r in MASKED_ROWS)

    assert as_table_rows != as_shaft_ranks, (
        "the masked rows sit where the two index spaces agree, so the mask assertion "
        f"cannot tell them apart: {as_table_rows}"
    )


# --------------------------------------------------------------------------------------
# peak_channel_id -> area / depth_class
# --------------------------------------------------------------------------------------

#: The electrode table is keyed by its index, with no channel_id column, so the identifier
#: lookup falls through to the index the way an NWB electrodes table does. Every channel
#: carries a distinct area, so landing on the wrong row cannot return the right answer.
_ELECTRODES = {
    10: ("V1", 500.0, "probeA"),
    11: ("V2", 1500.0, "probeB"),
    12: ("V4", 1600.0, "probeC"),
    13: ("MT", 400.0, "probeD"),
}

#: Not the electrode-table row order, and not sorted: a positional join lands elsewhere.
PEAK_CHANNEL_IDS = [13, 10, 12]
UNIT_IDS = [101, 102, 103]
#: The electrode table is permuted independently of the units.
ELECTRODE_ROW_ORDER = [12, 13, 11, 10]


def _electrodes(row_order) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "location": [_ELECTRODES[c][0] for c in row_order],
            "z": [_ELECTRODES[c][1] for c in row_order],
            "depth_unit": ["um"] * len(row_order),
            "group_name": [_ELECTRODES[c][2] for c in row_order],
        },
        index=list(row_order),
    )


def _units(peak_channel_ids, unit_ids) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cluster_id": list(unit_ids),
            "peak_channel_id": list(peak_channel_ids),
            "quality": [1.0] * len(peak_channel_ids),
        }
    )


def test_the_unit_fixture_discriminates_a_positional_join_gives_a_different_answer():
    """A fixture on which a positional join agrees with an identifier join tests nothing.

    The existing coverage uses ``peak_channel_id`` ``[0, 1, 2]`` against an electrode table
    indexed ``[0, 1, 2]`` in that order, so a positional join satisfies its assertions
    identically.
    """
    electrodes = _electrodes(ELECTRODE_ROW_ORDER)
    units = _units(PEAK_CHANNEL_IDS, UNIT_IDS)

    by_identifier = list(jnwb.enrich_units_dataframe(units, electrodes)["area"])
    by_position = [electrodes["location"].iloc[i] for i in range(len(units))]

    assert by_identifier == ["MT", "V1", "V4"]
    assert by_position == ["V4", "MT", "V2"]
    assert by_identifier != by_position, (
        "a positional join returns the same areas on this fixture, so nothing below "
        "distinguishes the two"
    )


def test_area_and_layer_follow_the_channel_identifier_not_the_electrode_row_position():
    units = _units(PEAK_CHANNEL_IDS, UNIT_IDS)

    natural = jnwb.enrich_units_dataframe(units, _electrodes([10, 11, 12, 13]))
    permuted = jnwb.enrich_units_dataframe(units, _electrodes(ELECTRODE_ROW_ORDER))

    for column in ("area", "depth_class", "group_name"):
        assert list(natural[column]) == list(permuted[column]), (
            f"{column} moved when the electrode table was reordered"
        )
    assert list(permuted["area"]) == ["MT", "V1", "V4"]
    assert list(permuted["depth_class"]) == ["Superficial", "Superficial", "Deep"]
    assert list(permuted["group_name"]) == ["probeD", "probeA", "probeC"]


def test_reordering_the_units_does_not_change_any_units_answer():
    """Identity travels with ``unit_id``, not with the row a unit happens to occupy."""
    electrodes = _electrodes(ELECTRODE_ROW_ORDER)
    order = [2, 0, 1]

    first = jnwb.enrich_units_dataframe(_units(PEAK_CHANNEL_IDS, UNIT_IDS), electrodes)
    shuffled = jnwb.enrich_units_dataframe(
        _units([PEAK_CHANNEL_IDS[i] for i in order], [UNIT_IDS[i] for i in order]), electrodes
    )

    for column in ("area", "depth_class"):
        assert dict(zip(first["unit_id"], first[column])) == dict(
            zip(shuffled["unit_id"], shuffled[column])
        ), f"{column} followed the row position rather than unit_id"
    assert list(shuffled["unit_id"]) == [UNIT_IDS[i] for i in order]


def test_a_peak_channel_absent_from_the_electrode_table_yields_no_area():
    """An unresolved channel is not a licence to return the nearest row."""
    electrodes = _electrodes(ELECTRODE_ROW_ORDER)
    enriched = jnwb.enrich_units_dataframe(_units([13, 99, 12], UNIT_IDS), electrodes)

    assert enriched["area"].iloc[0] == "MT"
    assert pd.isna(enriched["area"].iloc[1])
    assert enriched["depth_class"].iloc[1] == "Unknown"
    assert enriched["area"].iloc[2] == "V4"
