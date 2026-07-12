import pandas as pd
import numpy as np

from jnwb.addressing import (
    map_peak_channel_to_area,
    classify_layer_from_depth,
    enrich_units_dataframe,
)


def _electrodes_df():
    # Known-answer fixture: channel 0 -> V1 superficial, channel 1 -> PFC deep,
    # channel 2 has no location, channel 3 does not exist (absent from index).
    return pd.DataFrame(
        {
            "location": ["V1, AP -3.2, ML 12.1", "PFC", None],
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
    # Channel 2 has no location (area=None) but does have a valid z=800.0,
    # so layer still resolves to 'Superficial' - area and layer are mapped
    # independently.
    assert list(enriched["area"]) == ["V1", "PFC", None]
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

    assert list(enriched["area"]) == [None, None]
    assert list(enriched["layer"]) == ["Unknown", "Unknown"]
    assert list(enriched["group_name"]) == ["probeA", "probeA"]
    # No quality column provided -> defaults to not-stable, not a crash
    assert list(enriched["is_stable"]) == [False, False]
