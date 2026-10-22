"""A check that could not run, or a value that could not be read, says so (fact S9).

Each handler here used to return None or an empty reason with no word, so a layout was guessed,
an undefined type went unreported, or a stored unit went unchecked without the reader knowing.
"""

import os
from datetime import datetime, timezone
from types import SimpleNamespace

import h5py
import numpy as np
import pytest
from pynwb import NWBHDF5IO, NWBFile, TimeSeries

from jnwb import nwb_inspect
from jnwb.nwb_inspect import (
    _h5_channel_count,
    _pynwb_channel_count,
    _registered_types,
    _unknown_type,
    _warn_if_declared_unit_contradicts_storage,
    _why_unread,
)


def _nwb_with_series(tmp_path):
    path = tmp_path / "odd.nwb"
    nwb = NWBFile(session_description="s", identifier="i",
                  session_start_time=datetime(2020, 1, 1, tzinfo=timezone.utc))
    nwb.add_acquisition(TimeSeries(name="odd", data=np.zeros(100), unit="V", rate=1000.0))
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


def test_an_electrode_region_with_no_length_warns_that_the_layout_is_guessed(tmp_path):
    with h5py.File(tmp_path / "region.h5", "w") as handle:
        group = handle.create_group("acq")
        group.create_dataset("data", data=np.zeros((5, 3)))
        group.create_dataset("electrodes", data=1.0)
        with pytest.warns(UserWarning, match="electrode region"):
            assert _h5_channel_count(handle["acq"], "data") is None


def test_a_readable_electrode_region_is_counted_and_warns_nothing(tmp_path, recwarn):
    with h5py.File(tmp_path / "region.h5", "w") as handle:
        group = handle.create_group("acq")
        group.create_dataset("data", data=np.zeros((5, 3)))
        group.create_dataset("electrodes", data=np.arange(3))
        assert _h5_channel_count(handle["acq"], "data") == 3
    assert not [w for w in recwarn if "electrode region" in str(w.message)]


def test_a_pynwb_electrode_region_with_no_length_warns_that_the_layout_is_guessed():
    series = SimpleNamespace(electrodes=object())
    with pytest.warns(UserWarning, match="electrode region"):
        assert _pynwb_channel_count(series) is None


def test_an_undefined_type_check_that_cannot_run_says_why(tmp_path, monkeypatch):
    path = _nwb_with_series(tmp_path)
    _registered_types.cache_clear()

    def refuse(*args, **kwargs):
        raise RuntimeError("namespace file is corrupt")

    monkeypatch.setattr(nwb_inspect, "NWBHDF5IO", SimpleNamespace(load_namespaces=refuse))
    with h5py.File(path, "r") as handle:
        with pytest.warns(UserWarning, match="namespace file is corrupt"):
            assert _unknown_type(handle["acquisition/odd"], "TimeSeries") is None
    _registered_types.cache_clear()


def test_an_undefined_type_check_whose_file_cannot_be_stat_ed_says_why(tmp_path, monkeypatch):
    path = _nwb_with_series(tmp_path)

    def gone(*args, **kwargs):
        raise OSError("file vanished")

    with h5py.File(path, "r") as handle:
        monkeypatch.setattr(os, "stat", gone)
        with pytest.warns(UserWarning, match="file vanished"):
            assert _unknown_type(handle["acquisition/odd"], "TimeSeries") is None


def test_why_unread_carries_the_exception_class_and_text(tmp_path, monkeypatch):
    path = tmp_path / "source.nwb"
    path.write_bytes(b"not read")

    def boom(*args, **kwargs):
        raise OSError("disk went away")

    monkeypatch.setattr(nwb_inspect.h5py, "File", boom)
    reason = _why_unread(SimpleNamespace(container_source=str(path)), "odd")
    assert "OSError" in reason and "disk went away" in reason


def _unit_series(attrs):
    data = SimpleNamespace(attrs=attrs, dtype="int16")
    return SimpleNamespace(neurodata_type="ElectricalSeries", data=data,
                           conversion=1.0, channel_conversion=None)


class _UnreadableAttrs:
    def get(self, key, default=None):
        raise OSError("stored unit cannot be read")


def test_an_unreadable_stored_unit_warns_that_the_volts_check_did_not_run():
    with pytest.warns(RuntimeWarning, match="could not be read"):
        _warn_if_declared_unit_contradicts_storage(_unit_series(_UnreadableAttrs()), "odd", 0)


def test_a_stored_unit_that_agrees_warns_nothing(recwarn):
    _warn_if_declared_unit_contradicts_storage(_unit_series({"unit": "volts"}), "odd", 0)
    assert not [w for w in recwarn if issubclass(w.category, RuntimeWarning)]
