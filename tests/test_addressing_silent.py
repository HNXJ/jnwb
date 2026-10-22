"""Unreadable addressing inputs are reported, not replaced by a silent None or 'Unknown' (fact S9).

A channel id that is not a number, and a depth unit that will not convert to text, resolve to
area None or depth 'Unknown' as before; each public call now also warns once, naming what it
could not read. A missing value (NaN, None) is absent, not unreadable, and warns nothing.
"""

import warnings

import numpy as np
import pandas as pd

from jnwb.addressing import classify_layer_from_depth, enrich_units_dataframe, map_peak_channel_to_area


class Unreadable:
    """A value whose text form raises, as a caller-supplied object may."""

    def __str__(self):
        raise ValueError("no text form")


def _elec():
    return pd.DataFrame({
        "channel_id": [0, 1],
        "location": ["V1", "PFC"],
        "depth_unit": ["um", "um"],
        "z": [100.0, 2000.0],
    })


def _caught(call):
    """The UserWarning messages a call emits, and its return value."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        value = call()
    return value, [str(w.message) for w in caught if issubclass(w.category, UserWarning)]


def test_an_unparsed_channel_id_warns_and_resolves_to_no_area():
    area, messages = _caught(lambda: map_peak_channel_to_area("probe-x", _elec()))
    assert area is None
    assert len(messages) == 1 and "'probe-x'" in messages[0]


def test_a_classification_warns_and_is_unknown_for_an_unparsed_channel_id():
    depth, messages = _caught(lambda: classify_layer_from_depth("ch?", _elec()))
    assert depth == "Unknown"
    assert len(messages) == 1 and "'ch?'" in messages[0]


def test_an_enrich_call_warns_once_naming_every_unparsed_id():
    units = pd.DataFrame({"peak_channel_id": ["x0", "y1", "x0", 1.0]})
    _, messages = _caught(lambda: enrich_units_dataframe(units, _elec()))
    named = [m for m in messages if "peak_channel_id" in m]
    assert len(named) == 1
    assert "'x0'" in named[0] and "'y1'" in named[0]


def test_a_missing_channel_id_is_absent_and_warns_nothing():
    area, messages = _caught(lambda: map_peak_channel_to_area(np.nan, _elec()))
    assert area is None
    assert messages == []


def test_an_unreadable_explicit_depth_unit_warns_once_per_call_not_per_channel():
    units = pd.DataFrame({"peak_channel_id": [0, 1, 0, 1]})
    _, messages = _caught(lambda: enrich_units_dataframe(units, _elec(), depth_unit=Unreadable()))
    named = [m for m in messages if "depth unit" in m]
    assert len(named) == 1
    assert "no text form" in named[0]


def test_an_unreadable_row_depth_unit_warns_and_is_unknown():
    elec = _elec()
    elec["depth_unit"] = [Unreadable(), "um"]
    depth, messages = _caught(lambda: classify_layer_from_depth(0, elec))
    assert depth == "Unknown"
    assert any("no text form" in m for m in messages)


def test_an_unreadable_attribute_depth_unit_warns_and_is_unknown():
    elec = _elec().drop(columns=["depth_unit"])
    elec.attrs["depth_unit"] = Unreadable()
    depth, messages = _caught(lambda: classify_layer_from_depth(0, elec))
    assert depth == "Unknown"
    assert any("no text form" in m for m in messages)


def test_a_readable_depth_unit_warns_nothing():
    depth, messages = _caught(lambda: classify_layer_from_depth(1, _elec(), depth_unit="um"))
    assert depth == "Deep"
    assert messages == []
