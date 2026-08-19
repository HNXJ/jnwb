import pandas as pd
import numpy as np

from jnwb.addressing import (
    map_peak_channel_to_area,
    classify_layer_from_depth,
    enrich_units_dataframe,
)


def _electrodes_df():
    # Known-answer fixture matching real electrodes_df location strings
    # observed across real sessions (confirmed 2026-07-12: "FEF", "MT, MST",
    # "V1, V2, V3", "V1,V2", "V3d, V3a" - clean comma-separated area names,
    # never coordinate info baked into the same field).
    # channel 0 -> V1 (single-area probe), channel 1 -> PFC, channel 2 has no
    # location, channel 3 does not exist (absent from index).
    return pd.DataFrame(
        {
            "location": ["V1", "PFC", None],
            "group_name": ["probeC", "probeA", "probeB"],
            "z": [500.0, 1500.0, 800.0],
        },
        index=[0, 1, 2],
    )


def test_map_peak_channel_to_area_known_answers():
    elec = _electrodes_df()
    assert map_peak_channel_to_area(0, elec) == "V1"
    assert map_peak_channel_to_area(1, elec) == "PFC"
    assert map_peak_channel_to_area(2, elec) is None  # location is NaN
    assert map_peak_channel_to_area(99, elec) is None  # channel not in index
    assert map_peak_channel_to_area(np.nan, elec) is None
    assert map_peak_channel_to_area(0, None) is None
    assert map_peak_channel_to_area(0, pd.DataFrame()) is None


def test_map_peak_channel_to_area_multi_area_probe_resolves_by_channel_position():
    # Regression test for a real bug found 2026-07-12: a multi-area probe's
    # location string (e.g. real "V1, V2, V3" on one 128-channel probe) was
    # always resolved to the FIRST listed area regardless of the channel's
    # actual position within the probe - e.g. probe C channels near the end
    # of its range were labeled 'V1' when the correct area was 'V3'. Now
    # resolves by channel position within the probe's contiguous electrode
    # index block (matching omission.jnwb_ext.sequence_layout's channel_slice_for_area
    # convention: N areas -> N equal partitions of the probe's channels).
    n = 12  # 12-channel probe for a clean 3-way split (0-3, 4-7, 8-11)
    elec = pd.DataFrame(
        {
            "location": ["V1, V2, V3"] * n,
            "group_name": ["probeC"] * n,
        },
        index=range(100, 100 + n),
    )
    assert map_peak_channel_to_area(100, elec) == "V1"  # first channel
    assert map_peak_channel_to_area(103, elec) == "V1"  # last of first third
    assert map_peak_channel_to_area(104, elec) == "V2"  # first of middle third
    assert map_peak_channel_to_area(107, elec) == "V2"
    assert map_peak_channel_to_area(108, elec) == "V3"  # first of last third
    assert map_peak_channel_to_area(111, elec) == "V3"  # last channel


def test_map_peak_channel_to_area_two_area_probe_resolves_by_channel_position():
    n = 8
    elec = pd.DataFrame(
        {"location": ["MT, MST"] * n, "group_name": ["probeB"] * n},
        index=range(200, 200 + n),
    )
    assert map_peak_channel_to_area(200, elec) == "MT"
    assert map_peak_channel_to_area(203, elec) == "MT"
    assert map_peak_channel_to_area(204, elec) == "MST"
    assert map_peak_channel_to_area(207, elec) == "MST"


def test_classify_layer_from_depth_threshold_boundary():
    elec = _electrodes_df()
    # z=500 < 1000 -> Superficial; z=1500 > 1000 -> Deep
    assert classify_layer_from_depth(0, elec) == "Superficial"
    assert classify_layer_from_depth(1, elec) == "Deep"
    assert classify_layer_from_depth(99, elec) == "Unknown"
    assert classify_layer_from_depth(np.nan, elec) == "Unknown"

    # Exact boundary (z == 1000.0) must resolve to Superficial per the
    # `> 1000.0` (strict) comparison in the implementation.
    boundary_elec = pd.DataFrame({"location": ["V1"], "z": [1000.0]}, index=[0])
    assert classify_layer_from_depth(0, boundary_elec) == "Superficial"


def test_enrich_units_dataframe_maps_area_layer_and_stability():
    elec = _electrodes_df()
    units = pd.DataFrame(
        {
            "cluster_id": [10, 11, 12],
            "peak_channel_id": [0, 1, 2],
            "quality": [1.0, 0.5, 2.0],
            "firing_rate": ["5.5", "3.2", "not_a_number"],
        }
    )

    enriched = enrich_units_dataframe(units, elec)

    # cluster_id renamed to unit_id (SC-002 terminology alignment)
    assert "unit_id" in enriched.columns
    assert list(enriched["unit_id"]) == [10, 11, 12]

    # Real area/layer mapping propagated from electrodes_df.
    # Channel 2 has no location (area=missing) but does have a valid
    # z=800.0, so layer still resolves to 'Superficial' - area and layer
    # are mapped independently. The missing-area value round-trips through
    # a pandas Series.apply(), which represents it as None on some pandas
    # versions and np.nan on others (confirmed: local pandas 3.0.3 keeps
    # None, CI's pandas resolved np.nan) - both mean "no area found", so
    # check via pd.isna() rather than exact identity/equality.
    area_values = list(enriched["area"])
    assert area_values[0] == "V1"
    assert area_values[1] == "PFC"
    assert pd.isna(area_values[2])
    assert list(enriched["layer"]) == ["Superficial", "Deep", "Superficial"]

    # Stability flag: quality >= 1.0
    assert list(enriched["is_stable"]) == [True, False, True]
    assert list(enriched["stable_plus"]) == [True, False, True]

    # firing_rate coerced to numeric, invalid values become NaN not a crash
    assert enriched["firing_rate"].iloc[0] == 5.5
    assert pd.isna(enriched["firing_rate"].iloc[2])


def test_enrich_units_dataframe_without_electrodes_defaults_unknown():
    units = pd.DataFrame({"peak_channel_id": [0, 1]})
    enriched = enrich_units_dataframe(units, None)

    assert enriched["area"].isna().all()
    assert list(enriched["layer"]) == ["Unknown", "Unknown"]
    assert list(enriched["group_name"]) == ["probeA", "probeA"]
    # No quality column provided -> defaults to not-stable, not a crash
    assert list(enriched["is_stable"]) == [False, False]
