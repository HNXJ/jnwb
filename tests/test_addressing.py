import subprocess
import sys
from pathlib import Path

import pandas as pd
import numpy as np

from jnwb.addressing import (
    map_peak_channel_to_area,
    classify_layer_from_depth,
    enrich_units_dataframe,
    parse_probe_areas,
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
        lines += [
            "sys.path = [p for p in sys.path"
            " if 'omission' not in p.lower() and 'workspace' not in p.lower()]",
            "sys.modules['omission'] = None",
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


def test_area_resolution_is_identical_with_and_without_omission_importable():
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
