import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import numpy as np
import pytest

from jnwb.addressing import (
    map_peak_channel_to_area,
    classify_layer_from_depth,
    enrich_units_dataframe,
    parse_probe_areas,
    probe_geometry,
    ProbeGeometry,
    _probe_key_column,
    _resolve_electrode_row,
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
            "depth_unit": ["um", "um", "um"],
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
    # index block (N areas -> N equal partitions of the probe's channels).
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
    boundary_elec = pd.DataFrame({"location": ["V1"], "z": [1000.0], "depth_unit": ["um"]}, index=[0])
    assert classify_layer_from_depth(0, boundary_elec) == "Superficial"
    boundary_deep = pd.DataFrame({"location": ["V1"], "z": [1000.001], "depth_unit": ["um"]}, index=[0])
    assert classify_layer_from_depth(0, boundary_deep) == "Deep"


def test_map_peak_channel_to_area_with_explicit_channel_id_column_and_reset_index():
    # Case where electrodes_df index is 0..N-1 (e.g. after reset_index) but channel identifiers
    # live in a dedicated 'channel_id' column [100, 101, 102].
    elec = pd.DataFrame(
        {
            "channel_id": [100, 101, 102],
            "location": ["V1", "PFC", "FEF"],
            "group_name": ["probeA", "probeA", "probeA"],
            "z": [500.0, 1200.0, 1500.0],
        },
        index=[0, 1, 2],
    )
    # Must look up by channel_id, not row index
    assert map_peak_channel_to_area(100, elec) == "V1"
    assert map_peak_channel_to_area(101, elec) == "PFC"
    assert map_peak_channel_to_area(102, elec) == "FEF"
    # Row index 0 exists, but channel_id 0 does not -> must return None, NOT V1
    assert map_peak_channel_to_area(0, elec) is None


def test_classify_layer_from_depth_with_explicit_channel_id_column_and_reset_index():
    elec = pd.DataFrame(
        {
            "channel_id": [100, 101, 102],
            "z": [500.0, 1200.0, 1500.0],
            "depth_unit": ["um", "um", "um"],
        },
        index=[0, 1, 2],
    )
    assert classify_layer_from_depth(100, elec) == "Superficial"
    assert classify_layer_from_depth(101, elec) == "Deep"
    assert classify_layer_from_depth(0, elec) == "Unknown"


class TestClassifyLayerUnitSafety:
    """Regression suite for unit-safety in classify_layer_from_depth.

    Acceptance invariant:
        unknown or incompatible depth units -/-> plausible layer label.
    """

    def test_reproduced_silent_mm_failure_is_prevented(self):
        # Diagnostic case: z in mm (0.5, 1.5, 2.5 mm).
        # Without units, previously silently returned ['Superficial', 'Superficial', 'Superficial'].
        # Now must return 'Unknown' for all channels because depth unit is unknown.
        df_mm = pd.DataFrame({"z": [0.5, 1.5, 2.5]}, index=[0, 1, 2])
        assert classify_layer_from_depth(0, df_mm) == "Unknown"
        assert classify_layer_from_depth(1, df_mm) == "Unknown"
        assert classify_layer_from_depth(2, df_mm) == "Unknown"

        # With explicit depth_unit='mm', 0.5 mm is Superficial, 1.5 and 2.5 mm are Deep
        assert classify_layer_from_depth(0, df_mm, depth_unit="mm") == "Superficial"
        assert classify_layer_from_depth(1, df_mm, depth_unit="mm") == "Deep"
        assert classify_layer_from_depth(2, df_mm, depth_unit="mm") == "Deep"

    def test_explicit_units_um(self):
        df_um = pd.DataFrame({"z": [500.0, 1500.0]}, index=[0, 1])
        assert classify_layer_from_depth(0, df_um, depth_unit="um") == "Superficial"
        assert classify_layer_from_depth(1, df_um, depth_unit="um") == "Deep"
        # Alternate spellings
        assert classify_layer_from_depth(0, df_um, depth_unit="µm") == "Superficial"
        assert classify_layer_from_depth(1, df_um, depth_unit="microns") == "Deep"

    def test_threshold_boundary_and_custom_thresholds(self):
        df = pd.DataFrame({"z": [1000.0, 1000.001, 800.0, 1200.0]}, index=[0, 1, 2, 3])
        # Exact boundary at 1000.0 um is Superficial
        assert classify_layer_from_depth(0, df, depth_unit="um") == "Superficial"
        assert classify_layer_from_depth(1, df, depth_unit="um") == "Deep"

        # Custom threshold in um
        assert classify_layer_from_depth(2, df, depth_unit="um", threshold=750.0) == "Deep"
        assert classify_layer_from_depth(2, df, depth_unit="um", threshold=850.0) == "Superficial"

        # Custom threshold with explicit threshold_unit='mm'
        assert classify_layer_from_depth(2, df, depth_unit="um", threshold=0.75, threshold_unit="mm") == "Deep"
        assert classify_layer_from_depth(2, df, depth_unit="um", threshold=0.85, threshold_unit="mm") == "Superficial"

    def test_unsupported_depth_unit_argument_is_refused(self):
        df = pd.DataFrame({"z": [500.0, 1500.0]}, index=[0, 1])
        for bad_unit in ["inches", "furlongs", "lightyears", "volts", ""]:
            with pytest.raises(ValueError, match="depth_unit"):
                classify_layer_from_depth(0, df, depth_unit=bad_unit)

    def test_unsupported_unit_declared_in_the_table_still_gives_unknown(self):
        df = pd.DataFrame({"z": [500.0, 1500.0], "depth_unit": ["volts", "volts"]}, index=[0, 1])
        assert classify_layer_from_depth(0, df) == "Unknown"
        assert classify_layer_from_depth(1, df) == "Unknown"

    def test_negative_threshold_is_refused(self):
        df = pd.DataFrame({"z": [500.0, 1500.0]}, index=[0, 1])
        assert classify_layer_from_depth(0, df, depth_unit="um") == "Superficial"
        with pytest.raises(ValueError, match="threshold"):
            classify_layer_from_depth(0, df, depth_unit="um", threshold=-1.0)

    def test_missing_nan_and_infinite_depth(self):
        df = pd.DataFrame({"z": [np.nan, np.inf, -np.inf, None]}, index=[0, 1, 2, 3])
        for ch in range(4):
            assert classify_layer_from_depth(ch, df, depth_unit="um") == "Unknown"

    def test_implausible_coordinates(self):
        # Negative depth (outside cortical column) and excessive depth (> 20 mm)
        df = pd.DataFrame({"z": [-100.0, -0.001, 25000.0, 100000.0]}, index=[0, 1, 2, 3])
        for ch in range(4):
            assert classify_layer_from_depth(ch, df, depth_unit="um") == "Unknown"

    def test_no_unit_guessing(self):
        # High numerical values (e.g. 1500.0) must NOT be guessed as um
        df_high = pd.DataFrame({"z": [1500.0]}, index=[0])
        assert classify_layer_from_depth(0, df_high) == "Unknown"

        # Low numerical values (e.g. 1.5) must NOT be guessed as mm
        df_low = pd.DataFrame({"z": [1.5]}, index=[0])
        assert classify_layer_from_depth(0, df_low) == "Unknown"

    def test_metadata_resolution_via_column_and_attrs(self):
        # Unit declared in column 'depth_unit'
        df_col = pd.DataFrame({"z": [500.0, 1500.0], "depth_unit": ["um", "um"]}, index=[0, 1])
        assert classify_layer_from_depth(0, df_col) == "Superficial"
        assert classify_layer_from_depth(1, df_col) == "Deep"

        # Unit declared in column 'z_unit'
        df_col2 = pd.DataFrame({"z": [0.5, 1.5], "z_unit": ["mm", "mm"]}, index=[0, 1])
        assert classify_layer_from_depth(0, df_col2) == "Superficial"
        assert classify_layer_from_depth(1, df_col2) == "Deep"

        # Unit declared in df.attrs['depth_unit']
        df_attrs = pd.DataFrame({"z": [500.0, 1500.0]}, index=[0, 1])
        df_attrs.attrs["depth_unit"] = "um"
        assert classify_layer_from_depth(0, df_attrs) == "Superficial"
        assert classify_layer_from_depth(1, df_attrs) == "Deep"

        # Unit declared in df.attrs['unit']
        df_attrs2 = pd.DataFrame({"z": [0.5, 1.5]}, index=[0, 1])
        df_attrs2.attrs["unit"] = "mm"
        assert classify_layer_from_depth(0, df_attrs2) == "Superficial"
        assert classify_layer_from_depth(1, df_attrs2) == "Deep"

    def test_constant_label_regression(self):
        # Verify that mm data resolves into diverse labels, not constant 'Superficial'
        df_linear = pd.DataFrame({"z": np.linspace(0.2, 2.0, 10)}, index=range(10))
        labels = [classify_layer_from_depth(ch, df_linear, depth_unit="mm") for ch in range(10)]
        assert "Superficial" in labels
        assert "Deep" in labels
        assert labels != ["Superficial"] * 10


def test_map_peak_channel_to_area_non_contiguous_probe_indices():
    # Multi-area probe with non-contiguous channel indices (e.g. bad channels dropped)
    elec = pd.DataFrame(
        {
            "location": ["V1, V2"] * 4,
            "group_name": ["probeA"] * 4,
        },
        index=[10, 25, 50, 90],  # Non-contiguous, non-unit-step indices
    )
    # First half (channels 10, 25) -> V1
    assert map_peak_channel_to_area(10, elec) == "V1"
    assert map_peak_channel_to_area(25, elec) == "V1"
    # Second half (channels 50, 90) -> V2
    assert map_peak_channel_to_area(50, elec) == "V2"
    assert map_peak_channel_to_area(90, elec) == "V2"


def test_enrich_units_dataframe_maps_area_depth_class_and_stability():
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

    # Real area/depth-class mapping propagated from electrodes_df.
    # Channel 2 has no location (area=missing) but does have a valid
    # z=800.0, so depth_class still resolves to 'Superficial' - area and depth_class
    # are mapped independently. The missing-area value round-trips through
    # a pandas Series.apply(), which represents it as None on some pandas
    # versions and np.nan on others (confirmed: local pandas 3.0.3 keeps
    # None, CI's pandas resolved np.nan) - both mean "no area found", so
    # check via pd.isna() rather than exact identity/equality.
    area_values = list(enriched["area"])
    assert area_values[0] == "V1"
    assert area_values[1] == "PFC"
    assert pd.isna(area_values[2])
    assert list(enriched["depth_class"]) == ["Superficial", "Deep", "Superficial"]

    # Stability flag: quality >= 1.0; legacy stable_plus alias removed
    assert list(enriched["is_stable"]) == [True, False, True]
    assert "stable_plus" not in enriched.columns

    # firing_rate coerced to numeric, invalid values become NaN not a crash
    assert enriched["firing_rate"].iloc[0] == 5.5
    assert pd.isna(enriched["firing_rate"].iloc[2])


def test_enrich_units_dataframe_without_electrodes_defaults_unknown():
    units = pd.DataFrame({"peak_channel_id": [0, 1]})
    enriched = enrich_units_dataframe(units, None)

    assert enriched["area"].isna().all()
    assert list(enriched["depth_class"]) == ["Unknown", "Unknown"]
    assert enriched["group_name"].isna().all()
    # No quality column provided -> no stability label is invented
    assert "is_stable" not in enriched.columns
    assert "stable_plus" not in enriched.columns


@pytest.mark.parametrize("with_electrodes", [True, False], ids=["electrodes", "no_electrodes"])
def test_enrich_writes_no_layer_column_and_returns_a_supplied_one_unchanged(with_electrodes):
    """Neither path writes ``layer`` or warns about it, and a caller's own ``layer`` survives.

    The electrode path is the one that matters for the second half: it computes a depth class,
    so a copy written there would overwrite the caller's values with 'Superficial'/'Deep'.
    """
    import warnings

    elec = _electrodes_df() if with_electrodes else None
    units = pd.DataFrame({"peak_channel_id": [0, 1]})
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        enriched = enrich_units_dataframe(units, elec)
        supplied = enrich_units_dataframe(units.assign(layer=["L2/3", "L5"]), elec)
    about_layer = [
        str(w.message) for w in record
        if issubclass(w.category, (FutureWarning, DeprecationWarning)) or "layer" in str(w.message)
    ]
    assert about_layer == []
    assert "layer" not in enriched.columns
    assert list(supplied["layer"]) == ["L2/3", "L5"]
    expected = ["Superficial", "Deep"] if with_electrodes else ["Unknown", "Unknown"]
    assert list(enriched["depth_class"]) == expected
    assert list(supplied["depth_class"]) == expected


def test_enrich_units_dataframe_categorical_quality():
    units = pd.DataFrame({
        "unit_id": [0, 1, 2, 3],
        "quality": ["good", "mua", "sua", "noise"],
    })
    enriched = enrich_units_dataframe(units, None)
    assert list(enriched["is_stable"]) == [True, False, True, False]


@pytest.mark.parametrize("quality", [
    [2.0, np.nan, 0.0, None],
    ["good", None, "mua", " n/a "],
    ["1", "", "0", "nan"],
])
def test_a_unit_with_no_usable_quality_has_unknown_stability(quality):
    """A missing quality is no evidence of instability: the unit is <NA>, not False."""
    units = pd.DataFrame({"unit_id": [0, 1, 2, 3], "quality": pd.Series(quality, dtype=object)})
    stable = enrich_units_dataframe(units, None)["is_stable"]
    assert stable.dtype == "boolean"
    assert stable.isna().tolist() == [False, True, False, True]
    assert stable.dropna().tolist() == [True, False]


def test_the_stability_cut_off_and_labels_are_arguments():
    numeric = pd.DataFrame({"unit_id": [0, 1], "quality": [1.0, 2.0]})
    assert enrich_units_dataframe(numeric, None)["is_stable"].tolist() == [True, True]
    assert enrich_units_dataframe(
        numeric, None, stable_threshold=2.0)["is_stable"].tolist() == [False, True]
    labels = pd.DataFrame({"unit_id": [0, 1], "quality": ["good", "Accepted "]})
    assert enrich_units_dataframe(labels, None)["is_stable"].tolist() == [True, False]
    assert enrich_units_dataframe(
        labels, None, stable_labels=("accepted",))["is_stable"].tolist() == [False, True]


def test_a_quality_column_with_no_usable_value_adds_no_stability_label():
    """NaN, None, blank strings and the text of a missing value are no quality at all."""
    for quality in (
        [np.nan, np.nan], [None, None], ["", " "], [None, np.nan], ["nan", "None"], ["NaN", "n/a"],
        ["<NA>", "NaT"], [" <na> ", None],
    ):
        units = pd.DataFrame({"unit_id": [0, 1], "quality": pd.Series(quality, dtype=object)})
        enriched = enrich_units_dataframe(units, None)
        assert "is_stable" not in enriched.columns, quality


@pytest.mark.parametrize(
    "text",
    ["#N/A", "#N/A N/A", "#NA", "-nan", "-NaN", "1.#IND", "-1.#IND", "1.#QNAN", "-1.#QNAN"],
)
def test_every_string_pandas_reads_as_missing_adds_no_stability_label(text):
    """Strings `pandas.read_csv` turns into NaN by default are missing here too, not a label
    that is never good."""
    units = pd.DataFrame({"unit_id": [0, 1], "quality": pd.Series([text, None], dtype=object)})
    assert "is_stable" not in enrich_units_dataframe(units, None).columns


def test_the_copied_missing_strings_match_the_installed_pandas():
    """The copy used when pandas moves its private name must not lag the real set."""
    parsers = pytest.importorskip("pandas._libs.parsers")
    if not hasattr(parsers, "STR_NA_VALUES"):
        pytest.skip("this pandas does not expose STR_NA_VALUES")
    from jnwb.addressing import _PANDAS_NA_FALLBACK

    assert set(parsers.STR_NA_VALUES) <= _PANDAS_NA_FALLBACK


def test_enrich_units_dataframe_no_fabricated_probeA():
    # electrodes_df with no probe or group_name column
    elec = pd.DataFrame({"location": ["V1"], "z": [500.0], "depth_unit": ["um"]}, index=[0])
    units = pd.DataFrame({"peak_channel_id": [0]})
    enriched = enrich_units_dataframe(units, elec)
    assert enriched["group_name"].isna().all()

    # electrodes_df with explicit probe column preserves probe identity
    elec_probe = pd.DataFrame(
        {"location": ["V1"], "z": [500.0], "depth_unit": ["um"], "probe": ["shank2"]},
        index=[0],
    )
    enriched_probe = enrich_units_dataframe(units, elec_probe)
    assert list(enriched_probe["group_name"]) == ["shank2"]


def _probe_table(id_col="channel_id", id_values=None):
    per, locs = 8, ["V1", "V2, V3", "MT/MST", "VISpm2/3"]
    d = {"location": [locs[i // per] for i in range(4 * per)],
         "group_name": [f"p{i // per}" for i in range(4 * per)],
         "z": np.tile(np.linspace(0.0, 2000.0, per), 4),
         "depth_unit": "um"}
    if id_col is not None:
        d[id_col] = id_values if id_values is not None else np.arange(4 * per) + 100.0
    return pd.DataFrame(d, index=None if id_col else np.arange(4 * per) * 3 + 1)


_DUPLICATE_ID = np.arange(32) + 100.0
_DUPLICATE_ID[20] = 105.0          # the first match, row 5, must win
_GAP_ID = np.arange(32) + 100.0
_GAP_ID[3] = np.nan                # 103 is then in 'id' only, and must not resolve


@pytest.mark.parametrize("elec, n_resolved", [
    (_probe_table(), 11),
    (_probe_table(id_values=_DUPLICATE_ID), 11),
    (_probe_table(id_values=_GAP_ID).assign(id=np.arange(32) + 100), 10),
    (_probe_table(id_values=(np.arange(32) + 100).astype(np.uint16)), 11),
    # A text column never equals the integer channel ID, so nothing resolves.
    (_probe_table(id_values=[str(v) for v in range(100, 132)]), 0),
    (_probe_table(id_col=None), 7),
], ids=["float", "duplicate", "gap", "uint", "string", "index"])
def test_enrich_agrees_with_the_per_channel_functions(elec, n_resolved):
    """enrich resolves each channel once and caches it; every unit must still read what the
    public per-channel functions return for its own peak channel."""
    ids = [100.0, 105, "106", 103.0, 111.0, 125.0, 131, 4.0, 7, 999.0, np.nan, None, "x",
           105.0, 125, 10, 13.0, 16, 118.0, 122, 28, 43.0]
    got = enrich_units_dataframe(pd.DataFrame({"peak_channel_id": ids}), elec)

    def cells(values):  # a column may hold a missing label as None or NaN
        return [None if v is None or (isinstance(v, float) and np.isnan(v)) else v
                for v in values]

    assert cells(got["area"]) == cells(map_peak_channel_to_area(x, elec) for x in ids)
    assert cells(got["depth_class"]) == [classify_layer_from_depth(x, elec) for x in ids]
    rows = [_resolve_electrode_row(x, elec)[1] for x in ids]
    assert cells(got["group_name"]) == [None if r is None else r["group_name"] for r in rows]
    assert got["area"].notna().sum() == n_resolved


@pytest.mark.parametrize("fast", [True, False], ids=["table", "per_call"])
def test_an_id_missing_from_the_first_identifier_column_resolves_to_nothing(fast):
    """'channel_id' and 'id' number the channels differently here; 103 exists only as an 'id'.
    A lookup that moved on to 'id' would return the row of a different channel."""
    channel_id = np.arange(32) + 100.0
    channel_id[3] = np.nan
    # An object column takes the per-call path; float64 takes the lookup table.
    elec = _probe_table(id_values=channel_id if fast else pd.array(channel_id, dtype=object))
    elec = elec.assign(id=np.arange(32) + 90)
    assert elec["id"].eq(103).any()
    assert _resolve_electrode_row(103, elec) == (None, None)
    assert map_peak_channel_to_area(103, elec) is None
    got = enrich_units_dataframe(pd.DataFrame({"peak_channel_id": [103, 104]}), elec)
    assert got["area"].tolist()[0] is None or pd.isna(got["area"].tolist()[0])
    assert got["area"].tolist()[1] == "V1"


@pytest.mark.parametrize("dtype, stored, asked", [
    (np.float32, 16777216, 16777217),   # 2**24 + 1 rounds to 2**24 in float32
    (np.float16, 2048, 2049),           # 2**11 + 1 rounds to 2**11 in float16
])
def test_enrich_agrees_on_a_narrow_float_identifier_column(dtype, stored, asked):
    """`==` rounds the asked ID to the column's mantissa, so the per-channel functions match
    a neighbouring stored ID; enrich must return the same answer."""
    values = (np.arange(32) + 100).astype(dtype)
    values[0] = stored
    elec = _probe_table(id_values=values)
    ids = [asked, stored, 101]
    got = enrich_units_dataframe(pd.DataFrame({"peak_channel_id": ids}), elec)
    assert list(got["area"]) == [map_peak_channel_to_area(x, elec) for x in ids] == ["V1"] * 3
    assert list(got["depth_class"]) == [classify_layer_from_depth(x, elec) for x in ids]


def test_enrich_applies_the_threshold_it_is_given():
    """z = 1142.9 um is Deep at the default 1000 um and Superficial at 1500 um."""
    elec = _probe_table()
    ids = [100.0, 104.0, 105.0, 107.0]
    default = enrich_units_dataframe(pd.DataFrame({"peak_channel_id": ids}), elec)
    raised = enrich_units_dataframe(pd.DataFrame({"peak_channel_id": ids}), elec,
                                    threshold=1500.0, threshold_unit="um")
    assert list(default["depth_class"]) == ["Superficial", "Deep", "Deep", "Deep"]
    assert list(raised["depth_class"]) == ["Superficial", "Superficial", "Superficial", "Deep"]
    assert list(raised["depth_class"]) == [
        classify_layer_from_depth(x, elec, threshold=1500.0, threshold_unit="um") for x in ids
    ]


# ---------------------------------------------------------------------------------------------
# jnwb must behave identically whether or not a project package is importable.
#
# Until 2026-09-03, addressing.py imported omission's parser when available and fell back to
# generic splitting otherwise. The two disagreed on area NAMES, so merely having omission on
# sys.path changed which cortical area a unit was assigned to. These tests pin the property
# that removed that dependency.
# ---------------------------------------------------------------------------------------------

def _area_map_in_subprocess(block_omission: bool) -> str:
    """Resolve one multi-area channel in a fresh interpreter, optionally with omission hidden."""
    lines = ["import sys"]
    if block_omission:
        # Poisoning sys.modules is the whole block, and it is the only one that works:
        # omission is installed as an editable package, so a finder registered at
        # interpreter startup resolves it no matter what sys.path holds. A sentinel of
        # None makes ``import omission`` raise ModuleNotFoundError regardless of route.
        #
        # This used to additionally strip every sys.path entry whose text contained
        # "omission" or "workspace". That deleted the virtualenv's site-packages whenever
        # the checkout lived under a path containing "workspace" -- as this one does -- so
        # the subprocess died on ``import pandas`` and the test asserted nothing about
        # addressing at all.
        lines += [
            "sys.modules['omission'] = None",
            # Prove the block took effect. Without this the test can silently decay into
            # a no-op that compares jnwb against itself.
            "try:",
            "    import omission",
            "    raise SystemExit('omission is still importable; the block failed')",
            "except ImportError:",
            "    pass",
        ]
    lines += [
        "import pandas as pd, jnwb",
        "elec = pd.DataFrame({'location': ['V3D, DP'] * 8,"
        " 'group_name': ['probeA'] * 8}, index=range(8))",
        "print(jnwb.map_peak_channel_to_area(0, elec),"
        " jnwb.map_peak_channel_to_area(7, elec))",
    ]
    out = subprocess.run([sys.executable, "-c", chr(10).join(lines)],
                         capture_output=True, text=True,
                         cwd=str(Path(__file__).resolve().parent.parent))
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _omission_is_importable() -> bool:
    """Whether the unblocked arm has anything to compare jnwb against."""
    out = subprocess.run([sys.executable, "-c", "import omission"],
                         capture_output=True, text=True,
                         cwd=str(Path(__file__).resolve().parent.parent))
    return out.returncode == 0


def test_area_resolution_is_identical_with_and_without_omission_importable():
    # The blocked arm proves its own block took effect. Nothing proved the *unblocked*
    # arm could import what it is supposed to compare against, so where omission is not
    # installed both arms ran identical code and this passed by comparing jnwb to
    # itself. Skipping says so out loud instead; the comparison is real wherever the
    # dependency exists, which is why this is a skip and not a deletion.
    import pytest  # local, as everywhere else in this file

    if not _omission_is_importable():
        pytest.skip("omission is not importable here, so both arms would run identical code and the comparison would be vacuous")
    with_omission = _area_map_in_subprocess(block_omission=False)
    without_omission = _area_map_in_subprocess(block_omission=True)
    assert with_omission == without_omission, (
        f"jnwb resolved areas differently depending on whether omission was importable: "
        f"{with_omission!r} vs {without_omission!r}"
    )


def test_dp_is_not_silently_folded_into_v4():
    """DP must stay distinct from V4.

    A project-side alias table mapped DP -> V4, which made a 'DP/V4' probe resolve to
    ('V4', 'V4') -- both halves collapsing to one name, so the probe stopped being
    distinguishable by area. Whether DP and V4 are the same area is an anatomical question
    that generic addressing does not get to decide.
    """
    n = 8
    elec = pd.DataFrame(
        {"location": ["DP/V4"] * n, "group_name": ["probeD"] * n},
        index=range(300, 300 + n),
    )
    assert map_peak_channel_to_area(300, elec) == "DP"
    assert map_peak_channel_to_area(307, elec) == "V4"


def test_area_labels_are_preserved_exactly():
    """Labels come back as the file wrote them; only separators and whitespace are consumed.

    This inverts an earlier `test_area_label_casing_is_canonicalized`, which pinned
    `"v3d, V3A"` to `("V3d", "V3a")`. That canonicalization was removed deliberately:
    whether two spellings name the same area is a corpus convention, not something
    generic addressing can decide, so jnwb no longer decides it. The test is kept
    inverted rather than deleted so the record of the choice survives its reversal.
    """
    assert parse_probe_areas("V1, DP") == ("V1", "DP")
    assert parse_probe_areas("DP/V4") == ("DP", "V4")
    assert parse_probe_areas("V3A/V1") == ("V3A", "V1")
    assert parse_probe_areas("v3d,V2") == ("v3d", "V2")
    # whitespace and empty fields are the only things dropped
    assert parse_probe_areas("  V1 , , V2  ") == ("V1", "V2")

    # and the same preservation holds through the positional mapping
    n = 8
    elec = pd.DataFrame(
        {"location": ["v3d, V3A"] * n, "group_name": ["probeE"] * n},
        index=range(400, 400 + n),
    )
    assert map_peak_channel_to_area(400, elec) == "v3d"
    assert map_peak_channel_to_area(407, elec) == "V3A"


def test_channel_118_120_boundary_case_on_a_128_channel_three_area_probe():
    """The 2026-07-12 defect, at its original scale: 128 channels, 'V1, V2, V3'.

    Channels 118-120 sit in the final third and must resolve to V3, not to the first
    listed area. Positional binning must be unaffected by the parser change.
    """
    n = 128
    elec = pd.DataFrame(
        {"location": ["V1, V2, V3"] * n, "group_name": ["probeC"] * n},
        index=range(n),
    )
    for ch in (118, 119, 120):
        assert map_peak_channel_to_area(ch, elec) == "V3", f"channel {ch}"
    assert map_peak_channel_to_area(0, elec) == "V1"
    assert map_peak_channel_to_area(42, elec) == "V1"      # last of first third
    assert map_peak_channel_to_area(43, elec) == "V2"      # first of middle third
    assert map_peak_channel_to_area(127, elec) == "V3"


class TestProbeGeometry:
    def test_linear_probe_uniform_spacing_and_orientation(self):
        # 16 contacts along z-axis, 50 um pitch
        n = 16
        z_coords = np.arange(n) * 50.0
        coords = np.column_stack([np.zeros(n), np.zeros(n), z_coords])
        
        geom = probe_geometry(coords, units="um", pitch_tolerance=0.05)
        assert isinstance(geom, ProbeGeometry)
        assert geom.contact_positions.shape == (n, 3)
        assert geom.is_linear is True
        assert geom.is_uniform is True
        assert np.isclose(geom.nominal_pitch, 50.0)
        assert np.array_equal(geom.linear_order, np.arange(n))
        assert np.allclose(geom.orientation, [0.0, 0.0, 1.0])
        assert geom.units == "um"

    def test_arbitrary_linear_orientation_and_order_recovery(self):
        # 10 contacts along diagonal (1, 1, 0) direction, pitch = 100 um
        n = 10
        pitch = 100.0
        unit_vec = np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0)
        # Shuffle presentation order
        shuffled_indices = np.array([3, 0, 9, 2, 8, 1, 7, 4, 6, 5])
        positions = np.array([i * pitch * unit_vec for i in shuffled_indices])

        geom = probe_geometry(positions, units="um")
        assert geom.is_linear is True
        assert geom.is_uniform is True
        assert np.isclose(geom.nominal_pitch, pitch)
        # Sorted order should place contact 0 first and contact 9 last
        assert shuffled_indices[geom.linear_order[0]] == 0
        assert shuffled_indices[geom.linear_order[-1]] == 9
        # Orientation should align with positive unit_vec
        assert np.allclose(geom.orientation, unit_vec)

    def test_units_conversion_mm_and_m(self):
        # 4 contacts spaced 0.1 mm = 100 um
        coords_mm = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.1], [0.0, 0.0, 0.2], [0.0, 0.0, 0.3]])
        geom_mm = probe_geometry(coords_mm, units="mm")
        assert np.isclose(geom_mm.nominal_pitch, 100.0)
        assert np.isclose(geom_mm.contact_positions[-1, 2], 300.0)

        # In meters: 0.0001 m = 100 um
        coords_m = coords_mm * 1e-3
        geom_m = probe_geometry(coords_m, units="m")
        assert np.isclose(geom_m.nominal_pitch, 100.0)

    def test_irregular_spacing_detected(self):
        # Contacts with gaps: 0, 50, 100, 250, 300 (missing contact at 150, 200)
        z = np.array([0.0, 50.0, 100.0, 250.0, 300.0])
        coords = np.column_stack([np.zeros(len(z)), np.zeros(len(z)), z])
        geom = probe_geometry(coords, units="um", pitch_tolerance=0.1)
        assert geom.is_linear is True
        assert geom.is_uniform is False  # irregular spacing
        assert np.isclose(geom.nominal_pitch, 50.0)  # median distance is 50.0

    def test_tolerance_for_nominal_spacing(self):
        # Contacts with slight jitter within 10% tolerance
        z = np.array([0.0, 52.0, 98.0, 151.0, 203.0])  # pitch ~ 50 um
        coords = np.column_stack([np.zeros(len(z)), np.zeros(len(z)), z])
        geom_strict = probe_geometry(coords, nominal_pitch=50.0, pitch_tolerance=0.02)
        assert geom_strict.is_uniform is False  # 4% deviation exceeds 2%
        geom_loose = probe_geometry(coords, nominal_pitch=50.0, pitch_tolerance=0.10)
        assert geom_loose.is_uniform is True

    def test_non_linear_2d_array(self):
        # 2D planar grid (e.g. 2x2 grid)
        coords_2d = np.array([
            [0.0, 0.0, 0.0],
            [50.0, 0.0, 0.0],
            [0.0, 50.0, 0.0],
            [50.0, 50.0, 0.0],
        ])
        geom = probe_geometry(coords_2d, units="um", strict_linear=False)
        assert geom.is_linear is False
        assert geom.is_uniform is False

        # strict_linear=True must raise ValueError
        import pytest
        with pytest.raises(ValueError, match="non-linear"):
            probe_geometry(coords_2d, units="um", strict_linear=True)

    def test_multi_probe_selection_and_ambiguity(self):
        import pytest
        # DataFrame with two distinct probes
        elec_df = pd.DataFrame({
            "x": [0.0, 0.0, 1000.0, 1000.0],
            "y": [0.0, 0.0, 0.0, 0.0],
            "z": [0.0, 50.0, 0.0, 50.0],
            "group_name": ["probe_A", "probe_A", "probe_B", "probe_B"],
            "channel_id": [0, 1, 10, 11],
        })

        # Omitted probe_name on multi-probe table raises ValueError
        with pytest.raises(ValueError, match="Multiple probes found"):
            probe_geometry(elec_df)

        # Non-existent probe raises ValueError
        with pytest.raises(ValueError, match="Probe 'probe_C' not found"):
            probe_geometry(elec_df, probe_name="probe_C")

        # Explicit probe selection succeeds
        geom_a = probe_geometry(elec_df, probe_name="probe_A")
        assert geom_a.probe_name == "probe_A"
        assert geom_a.contact_positions.shape == (2, 3)
        assert np.array_equal(geom_a.channel_ids, [0, 1])

        geom_b = probe_geometry(elec_df, probe_name="probe_B")
        assert geom_b.probe_name == "probe_B"
        assert geom_b.contact_positions.shape == (2, 3)
        assert np.array_equal(geom_b.channel_ids, [10, 11])

    def test_duplicate_coordinates_raises(self):
        import pytest
        # Two contacts with identical coordinates
        dup_coords = np.array([
            [0.0, 0.0, 100.0],
            [0.0, 0.0, 100.0],
            [0.0, 0.0, 200.0],
        ])
        with pytest.raises(ValueError, match="Duplicate contact coordinates"):
            probe_geometry(dup_coords)

    def test_non_finite_or_nan_coordinates_raises(self):
        import pytest
        nan_coords = np.array([
            [0.0, 0.0, 100.0],
            [0.0, np.nan, 200.0],
        ])
        with pytest.raises(ValueError, match="NaN or non-finite"):
            probe_geometry(nan_coords)

    def test_unsupported_units_raises(self):
        import pytest
        coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 50.0]])
        with pytest.raises(ValueError, match="Unsupported coordinate units"):
            probe_geometry(coords, units="lightyears")

    def test_boundary_single_contact(self):
        coords = np.array([[10.0, 20.0, 30.0]])
        geom = probe_geometry(coords, units="um")
        assert geom.contact_positions.shape == (1, 3)
        assert geom.nominal_pitch is None
        assert geom.orientation is None
        assert geom.is_linear is True
        assert geom.is_uniform is True



def test_an_atlas_layer_label_is_one_location_and_two_areas_still_split():
    """`VISpm2/3` is layer 2/3 of one area; `V1/V2` is two areas on one probe."""
    assert parse_probe_areas("VISpm2/3") == ("VISpm2/3",)
    assert parse_probe_areas("VISp2/3, VISp4") == ("VISp2/3", "VISp4")
    assert parse_probe_areas("V1/V2") == ("V1", "V2")
    elec = pd.DataFrame({"location": ["VISpm2/3", "VISpm4"]}, index=[1280, 1281])
    assert map_peak_channel_to_area(1280, elec) == "VISpm2/3"
    assert map_peak_channel_to_area(1281, elec) == "VISpm4"
    probe = pd.DataFrame({"location": ["V1/V2"] * 4, "group_name": ["A"] * 4})
    assert [map_peak_channel_to_area(i, probe) for i in range(4)] == ["V1", "V1", "V2", "V2"]


def test_a_sublayer_alternation_is_one_location():
    """`VISp6a/b` is sublayers 6a and 6b of one area, not the areas `VISp6a` and `b`.

    The proxy to avoid: merging every one-letter field. A one-letter field after a label that
    does not end in a digit and a letter still starts a new area, as does a longer field.
    """
    assert parse_probe_areas("VISp6a/b") == ("VISp6a/b",)
    assert parse_probe_areas("VISp6a/b, VISp5") == ("VISp6a/b", "VISp5")
    assert parse_probe_areas("V1/a") == ("V1", "a")
    assert parse_probe_areas("VISa/b") == ("VISa", "b")   # a letter not after a digit
    assert parse_probe_areas("V6A/b") == ("V6A", "b")     # a digit, then an uppercase letter
    assert parse_probe_areas("VISp6a/bc") == ("VISp6a", "bc")   # more than one letter
    assert parse_probe_areas("V6a/V6") == ("V6a", "V6")
    assert parse_probe_areas("V6a/B") == ("V6a", "B")
    elec = pd.DataFrame({"location": ["VISp6a/b"] * 2, "group_name": ["A"] * 2})
    assert [map_peak_channel_to_area(i, elec) for i in range(2)] == ["VISp6a/b"] * 2


class TestEnrichingWithoutAPeakChannelWarns:
    """A units table without `peak_channel_id` cannot be joined to the electrodes it is given.

    It used to fill every row with None and 'Unknown' in silence. The proxy to avoid: a warning
    on every call, so a table with the column, and a call with no or an empty electrodes table,
    stay quiet.
    """

    ELECTRODES = pd.DataFrame({"location": ["V1", "V1"], "z": [100.0, 2000.0]})

    def test_the_fill_warns_and_names_the_columns(self):
        units = pd.DataFrame({"quality": [1, 0]})
        with pytest.warns(UserWarning, match=r"no 'peak_channel_id' column.*"
                                             r"\['area', 'depth_class', 'group_name'\]"):
            out = enrich_units_dataframe(units, self.ELECTRODES, depth_unit="um")
        assert out["area"].isna().all() and (out["depth_class"] == "Unknown").all()

    @pytest.mark.parametrize("case", ["with peak channel", "no electrodes", "empty electrodes",
                                      "nothing to fill"])
    def test_a_resolvable_or_electrode_free_call_does_not_warn(self, case):
        import warnings

        units = pd.DataFrame({"quality": [1, 0], "peak_channel_id": [0, 1]})
        electrodes = self.ELECTRODES
        if case == "no electrodes":
            units, electrodes = units.drop(columns="peak_channel_id"), None
        if case == "empty electrodes":
            units, electrodes = units.drop(columns="peak_channel_id"), self.ELECTRODES.iloc[0:0]
        if case == "nothing to fill":
            units = units.drop(columns="peak_channel_id").assign(
                area="V1", depth_class="Deep", group_name="A")
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            out = enrich_units_dataframe(units, electrodes, depth_unit="um")
        if case == "with peak channel":
            assert out["depth_class"].tolist() == ["Superficial", "Deep"]


def test_a_text_unit_id_is_kept_and_a_numeric_text_id_is_coerced():
    # The coercion exists for numeric-looking text ids: '156.0' compares unequal to 156. It
    # applies only when every id is numeric, so a text id such as 'u1' is kept as it is.
    text = enrich_units_dataframe(pd.DataFrame({"unit_id": ["u1", "u2"]}), None)
    assert list(text["unit_id"]) == ["u1", "u2"]
    numeric = enrich_units_dataframe(pd.DataFrame({"unit_id": ["156.0", "157"]}), None)
    assert list(numeric["unit_id"]) == [156.0, 157.0]
    assert numeric["unit_id"].dtype == float


@pytest.mark.parametrize("missing", [None, np.nan, pd.NA])
def test_a_multi_area_contact_with_a_missing_probe_key_is_refused(missing):
    # Two areas on one probe: a contact's position along its probe picks its area, and a
    # contact with no probe key has no probe to take a position on.
    elec = pd.DataFrame({"location": ["V1, V2"] * 4, "group_name": ["A", "A", "A", missing]})
    assert elec["group_name"].isna().sum() == 1, "the fixture must leave one contact unkeyed"
    with pytest.raises(ValueError, match=r"'group_name'.*\['A'\]"):
        map_peak_channel_to_area(3, elec)


def test_a_multi_area_label_grouped_only_by_location_is_refused():
    # A location names no probe: two probes can carry one label, so it cannot key them.
    elec = pd.DataFrame({"location": ["V1, V2"] * 4}, index=[0, 1, 2, 3])
    assert "group_name" not in elec.columns and "probe" not in elec.columns, \
        "the fixture must have no probe column"
    with pytest.raises(ValueError, match="no probe is named"):
        map_peak_channel_to_area(1, elec)


def test_a_multi_area_probe_is_resolved_by_position_along_its_own_probe():
    # Two probes share one multi-area label; each contact's position is along its own probe.
    elec = pd.DataFrame(
        {"location": ["V1, V2"] * 8, "probe": ["P1"] * 4 + ["P2"] * 4}, index=range(8)
    )
    assert elec["location"].nunique() == 1, "the fixture must give both probes one label"
    assert elec["probe"].value_counts().to_dict() == {"P1": 4, "P2": 4}
    areas = [map_peak_channel_to_area(ch, elec) for ch in range(8)]
    assert areas == ["V1", "V1", "V2", "V2", "V1", "V1", "V2", "V2"]


@pytest.mark.parametrize("columns, expected", [
    (["group_name", "group", "probe", "device"], "group_name"),
    (["group", "probe", "device", "location"], "group"),
    (["probe", "device", "location"], "probe"),
    (["device", "location"], "device"),
    (["location"], None),
])
def test_the_probe_key_is_the_first_of_group_name_group_probe_device_and_never_location(columns, expected):
    elec = pd.DataFrame({column: ["x"] for column in columns})
    assert _probe_key_column(elec) == expected


def test_a_multi_area_probe_named_only_by_device_resolves_by_position():
    elec = pd.DataFrame({"location": ["V1, V2"] * 8, "device": ["D1"] * 4 + ["D2"] * 4},
                        index=range(8))
    assert elec["location"].nunique() == 1, "the fixture must give both probes one label"
    areas = [map_peak_channel_to_area(ch, elec) for ch in range(8)]
    assert areas == ["V1", "V1", "V2", "V2", "V1", "V1", "V2", "V2"]


@pytest.mark.parametrize("column", ["group", "device"])
def test_probe_geometry_still_names_its_probe_by_group_or_device(column):
    elec = pd.DataFrame({
        "x": [0.0] * 4 + [1000.0] * 4,
        "y": [0.0] * 8,
        "z": [0.0, 50.0, 100.0, 150.0] * 2,
        column: ["A"] * 4 + ["B"] * 4,
        "channel_id": range(8),
    })
    geom = probe_geometry(elec, probe_name="A")
    assert geom.probe_name == "A"
    assert geom.contact_positions.shape == (4, 3)


def test_enrich_names_the_probe_of_a_group_column_by_its_name():
    elec = pd.DataFrame(
        {"location": ["V1"], "group": [SimpleNamespace(name="probeA")], "z": [500.0],
         "depth_unit": ["um"]},
        index=[0],
    )
    enriched = enrich_units_dataframe(pd.DataFrame({"peak_channel_id": [0]}), elec)
    assert enriched["group_name"].tolist() == ["probeA"]


def test_a_fractional_channel_id_is_refused_not_truncated_to_a_channel():
    elec = pd.DataFrame({"location": ["V1", "PFC", "V4"]}, index=[0, 1, 2])
    # The precondition: truncating 2.7 would reach channel 2, which carries an area.
    assert map_peak_channel_to_area(2.0, elec) == "V4"
    with pytest.raises(ValueError, match="2.7"):
        map_peak_channel_to_area(2.7, elec)
    with pytest.raises(ValueError, match="2.7"):
        classify_layer_from_depth(2.7, elec)
    with pytest.raises(ValueError, match="2.7"):
        enrich_units_dataframe(pd.DataFrame({"peak_channel_id": [0.0, 2.7]}), elec)


def test_undeclared_depth_reads_z_from_pia_unchanged():
    # Pinned on BASE. With no declared shallow end, z is read as depth from pia for every probe:
    # probe B's contacts sit 1100 um and up in z, and are Deep because of that, not because of
    # their own probe's shallow end.
    elec = pd.DataFrame(
        {"z": [100.0, 1200.0, 1100.0, 1300.0], "depth_unit": ["um"] * 4,
         "group_name": ["probeA", "probeA", "probeB", "probeB"]},
        index=[0, 1, 2, 3],
    )
    expected = ["Superficial", "Deep", "Deep", "Deep"]
    assert [classify_layer_from_depth(ch, elec) for ch in range(4)] == expected
    enriched = enrich_units_dataframe(pd.DataFrame({"peak_channel_id": [0, 1, 2, 3]}), elec)
    assert enriched["depth_class"].tolist() == expected


def test_shallow_end_max_reads_depth_from_the_declared_shallow_contact():
    # A probe whose z grows toward pia: its shallowest contact is the largest z.
    elec = pd.DataFrame(
        {"z": [600.0, 1000.0, 1400.0, 1800.0], "depth_unit": ["um"] * 4}, index=[0, 1, 2, 3]
    )
    # Precondition: the undeclared reading inverts the two ends (z read from pia).
    assert classify_layer_from_depth(0, elec) == "Superficial"
    assert classify_layer_from_depth(3, elec) == "Deep"
    kw = {"depth_axis": "z", "shallow_end": "max"}
    # Depth from the contact at z = 1800: 1200, 800, 400, 0 um.
    assert [classify_layer_from_depth(ch, elec, **kw) for ch in range(4)] == [
        "Deep", "Superficial", "Superficial", "Superficial"]
    enriched = enrich_units_dataframe(pd.DataFrame({"peak_channel_id": [0, 1, 2, 3]}), elec, **kw)
    assert enriched["depth_class"].tolist() == [
        "Deep", "Superficial", "Superficial", "Superficial"]


def test_shallow_end_min_agrees_with_undeclared_when_z_is_depth_from_pia():
    elec = pd.DataFrame({"z": [0.0, 400.0, 900.0, 1000.0, 1200.0], "depth_unit": ["um"] * 5},
                        index=range(5))
    # Precondition: the shallowest contact is at z = 0, so z already is depth from it.
    assert elec["z"].min() == 0.0
    undeclared = [classify_layer_from_depth(ch, elec) for ch in range(5)]
    declared = [classify_layer_from_depth(ch, elec, depth_axis="z", shallow_end="min")
                for ch in range(5)]
    assert undeclared == ["Superficial", "Superficial", "Superficial", "Superficial", "Deep"]
    assert declared == undeclared


def test_depth_is_anchored_per_probe():
    elec = pd.DataFrame(
        {"z": [500.0, 1700.0, 2000.0, 2800.0], "depth_unit": ["um"] * 4,
         "group_name": ["probeA", "probeA", "probeB", "probeB"]},
        index=range(4),
    )
    # Precondition: read from pia, both of probe B's contacts are Deep.
    assert classify_layer_from_depth(2, elec) == "Deep"
    assert classify_layer_from_depth(3, elec) == "Deep"
    kw = {"depth_axis": "z", "shallow_end": "min"}
    # Each probe's own shallowest contact is depth 0: probe A 0 and 1200 um, probe B 0 and 800 um.
    assert [classify_layer_from_depth(ch, elec, **kw) for ch in range(4)] == [
        "Superficial", "Deep", "Superficial", "Superficial"]


def test_a_contact_with_no_probe_key_warns_and_reads_unknown():
    elec = pd.DataFrame(
        {"z": [0.0, 500.0], "depth_unit": ["um"] * 2, "group_name": ["probeA", None]},
        index=[0, 1],
    )
    with pytest.warns(UserWarning, match="has no probe key") as caught:
        assert classify_layer_from_depth(1, elec, depth_axis="z", shallow_end="min") == "Unknown"
    assert len(caught) == 1
    # One warning per public call, however many units sit on the channel.
    with pytest.warns(UserWarning, match="has no probe key") as caught:
        enriched = enrich_units_dataframe(
            pd.DataFrame({"peak_channel_id": [0, 1, 1]}), elec, depth_axis="z", shallow_end="min")
    assert enriched["depth_class"].tolist() == ["Superficial", "Unknown", "Unknown"]
    assert len(caught) == 1


def test_a_declaration_is_refused_unless_complete_and_valid():
    elec = pd.DataFrame({"z": [0.0, 500.0], "depth_unit": ["um"] * 2}, index=[0, 1])
    with pytest.raises(ValueError, match="declared together") as one_alone:
        classify_layer_from_depth(0, elec, depth_axis="z")
    assert "depth_axis" in str(one_alone.value) and "shallow_end" in str(one_alone.value)
    with pytest.raises(ValueError, match="declared together"):
        classify_layer_from_depth(0, elec, shallow_end="min")
    with pytest.raises(ValueError, match="depth_axis must be one of"):
        classify_layer_from_depth(0, elec, depth_axis="w", shallow_end="min")
    with pytest.raises(ValueError, match="is not a column"):
        classify_layer_from_depth(0, elec, depth_axis="x", shallow_end="min")
    with pytest.raises(ValueError, match="shallow_end must be one of"):
        classify_layer_from_depth(0, elec, depth_axis="z", shallow_end="top")
    with pytest.raises(ValueError, match="declared together"):
        enrich_units_dataframe(pd.DataFrame({"peak_channel_id": [0]}), elec, depth_axis="z")


# Two 8-contact probes: positions 0 to 7 sit in V1, 8 to 15 in V2, electrodes in position order.
# Unit ``pos`` sits on the contact at position ``pos``, so its planted area is PLANTED_AREA[pos].
N_CONTACTS = 16
PLANTED_AREA = ["V1"] * 8 + ["V2"] * 8
# A permutation of the positions with no fixed point: a lookup by position or id reads another row.
SHIFTED_HARDWARE = [(pos + 8) % N_CONTACTS for pos in range(N_CONTACTS)]


def _write_probe_pair(path, *, hardware, units):
    """Write an NWB file holding the two probes above. ``hardware`` gives one hardware channel per
    position, or None for no hardware_channel column. ``units`` holds (region, peak_channel_id)
    per unit: the region is the list of electrode ids the unit names, or None for no region."""
    from datetime import datetime

    from dateutil.tz import tzlocal
    from pynwb import NWBFile, NWBHDF5IO

    nwb = NWBFile(session_description="addressing fixture", identifier="addressing",
                  session_start_time=datetime.now(tzlocal()))
    if hardware is not None:
        nwb.add_electrode_column("hardware_channel", "hardware channel of the contact")
    nwb.add_electrode_column("group_name", "probe name")
    device = nwb.create_device(name="device")
    groups = {area: nwb.create_electrode_group(name=f"probe_{area}", description=area,
                                               location=area, device=device)
              for area in ("V1", "V2")}
    for pos in range(N_CONTACTS):
        group = groups[PLANTED_AREA[pos]]
        extra = {} if hardware is None else {"hardware_channel": hardware[pos]}
        nwb.add_electrode(location=group.location, group=group, group_name=group.name,
                          x=0.0, y=0.0, z=float(pos % 8) * 10.0, **extra)
    nwb.add_unit_column("peak_channel_id", "peak channel")
    for region, peak in units:
        extra = {} if region is None else {"electrodes": region}
        nwb.add_unit(spike_times=[0.1], peak_channel_id=peak, **extra)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)


def _read_units_and_electrodes(path):
    from pynwb import NWBHDF5IO

    with NWBHDF5IO(str(path), "r") as io:
        nwb = io.read()
        return nwb.units.to_dataframe(), nwb.electrodes.to_dataframe()


def _areas(out):
    """The area column with each missing area as None: pandas 3 stores a missing string as NaN."""
    return [area if isinstance(area, str) else None for area in out["area"]]


def test_enrich_reads_the_area_of_the_electrode_a_unit_region_names(tmp_path):
    units = [([pos], SHIFTED_HARDWARE[pos]) for pos in range(N_CONTACTS)]
    path = tmp_path / "region.nwb"
    _write_probe_pair(path, hardware=SHIFTED_HARDWARE, units=units)
    units_df, electrodes_df = _read_units_and_electrodes(path)
    # Fixture check: no unit's peak channel is the row it sits on.
    assert all(peak != region[0] for region, peak in units)
    out = enrich_units_dataframe(units_df, electrodes_df)
    assert _areas(out) == PLANTED_AREA


def test_hardware_channel_gives_the_area_when_the_units_have_no_region(tmp_path):
    units = [(None, SHIFTED_HARDWARE[pos]) for pos in range(N_CONTACTS)]
    path = tmp_path / "hardware.nwb"
    _write_probe_pair(path, hardware=SHIFTED_HARDWARE, units=units)
    units_df, electrodes_df = _read_units_and_electrodes(path)
    assert "electrodes" not in units_df.columns
    out = enrich_units_dataframe(units_df, electrodes_df)
    assert _areas(out) == PLANTED_AREA
    peaks = list(units_df["peak_channel_id"])
    assert [map_peak_channel_to_area(peak, electrodes_df) for peak in peaks] == PLANTED_AREA


def test_a_region_of_several_electrodes_takes_the_one_whose_hardware_channel_is_the_peak(tmp_path):
    units = [([2, 10], 10), ([2, 10], 2), ([2, 10], 5), ([2, 3], 2)]
    path = tmp_path / "several.nwb"
    _write_probe_pair(path, hardware=SHIFTED_HARDWARE, units=units)
    units_df, electrodes_df = _read_units_and_electrodes(path)
    # Fixture check: electrode 2 (V1) carries channel 10 and electrode 10 (V2) carries channel 2;
    # neither electrode of region [2, 3] carries channel 2.
    assert electrodes_df.loc[[2, 10], "hardware_channel"].tolist() == [10, 2]
    out = enrich_units_dataframe(units_df, electrodes_df)
    # Peak 2 is the id of electrode 2 but no hardware channel of region [2, 3]: no area, not the id.
    assert _areas(out) == ["V1", "V2", None, None]


def test_without_hardware_channel_a_region_of_several_electrodes_matches_the_id(tmp_path):
    units = [([2, 10], 10), ([2, 10], 2), ([2, 10], 5)]
    path = tmp_path / "several_ids.nwb"
    _write_probe_pair(path, hardware=None, units=units)
    units_df, electrodes_df = _read_units_and_electrodes(path)
    assert "hardware_channel" not in electrodes_df.columns
    out = enrich_units_dataframe(units_df, electrodes_df)
    assert _areas(out) == ["V2", "V1", None]


def test_an_empty_region_gives_no_area_and_never_falls_back_to_the_id(tmp_path):
    # Peak 3 is the id of electrode 3 (V1) and the hardware channel of electrode 11 (V2).
    units = [([], 3), ([2], 10)]
    path = tmp_path / "empty.nwb"
    _write_probe_pair(path, hardware=SHIFTED_HARDWARE, units=units)
    units_df, electrodes_df = _read_units_and_electrodes(path)
    out = enrich_units_dataframe(units_df, electrodes_df)
    # The second unit's region names electrode 2 alone, so its row is that electrode whatever
    # its peak channel is.
    assert _areas(out) == [None, "V1"]


def test_a_probe_whose_hardware_channel_is_minus_one_resolves_to_no_area(tmp_path):
    hardware = list(range(8)) + [-1] * 8  # probe V1 wired at channels 0 to 7, probe V2 not wired
    units = [(None, 2), (None, 10)]
    path = tmp_path / "minus_one.nwb"
    _write_probe_pair(path, hardware=hardware, units=units)
    units_df, electrodes_df = _read_units_and_electrodes(path)
    out = enrich_units_dataframe(units_df, electrodes_df)
    # Peak 10 is the id of electrode 10 (V2); the unwired probe must not fall back to it.
    assert _areas(out) == ["V1", None]


def test_a_file_with_neither_column_keeps_the_identifier_lookup(tmp_path):
    units = [(None, pos) for pos in range(N_CONTACTS)]
    path = tmp_path / "neither.nwb"
    _write_probe_pair(path, hardware=None, units=units)
    units_df, electrodes_df = _read_units_and_electrodes(path)
    assert "electrodes" not in units_df.columns
    assert "hardware_channel" not in electrodes_df.columns
    out = enrich_units_dataframe(units_df, electrodes_df)
    assert _areas(out) == PLANTED_AREA
    peaks = list(units_df["peak_channel_id"])
    assert [map_peak_channel_to_area(peak, electrodes_df) for peak in peaks] == PLANTED_AREA


def test_enrich_without_a_region_warns_on_a_probe_collision_like_the_per_channel_function():
    """A peak channel that is the hardware channel of electrodes on more than one probe names
    no row; enrich surfaces that reason the same way it surfaces its other unread reasons,
    one UserWarning naming the caller, as map_peak_channel_to_area does for the same input."""
    elec = pd.DataFrame({
        "hardware_channel": [7, 7, 8, 8],
        "group_name": ["p1", "p2", "p1", "p2"],
        "location": ["V1", "V2", "V1", "V2"],
        "z": [100.0, 100.0, 200.0, 200.0],
        "depth_unit": ["um"] * 4,
    })
    assert (elec["hardware_channel"] == 7).sum() == 2
    with pytest.warns(UserWarning,
                       match=r"could not be read.*hardware channel of electrodes on 2 probes"):
        out = enrich_units_dataframe(pd.DataFrame({"peak_channel_id": [7.0]}), elec)
    assert out["area"].isna().all()
    with pytest.warns(UserWarning, match="hardware channel of electrodes on 2 probes"):
        assert map_peak_channel_to_area(7.0, elec) is None


def test_enrich_without_a_region_stays_quiet_when_the_channel_is_absent():
    """A peak channel the table does not hold names nothing and warns about nothing."""
    import warnings

    elec = pd.DataFrame({
        "hardware_channel": [7, 7, 8, 8],
        "group_name": ["p1", "p2", "p1", "p2"],
        "location": ["V1", "V2", "V1", "V2"],
    })
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        out = enrich_units_dataframe(pd.DataFrame({"peak_channel_id": [99.0]}), elec)
    assert out["area"].isna().all()
