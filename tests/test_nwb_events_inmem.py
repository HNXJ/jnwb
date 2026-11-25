"""Interval-table resolution on an unwritten in-memory NWBFile matches the written file (17-165).

pynwb keeps `trials`, `epochs` and `invalid_times` on their own NWBFile attributes until a write;
`nwb.intervals` holds them only after a write and read back. Resolution must not depend on that.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pynwb
import pytest
from dateutil.tz import tzutc
from pynwb import NWBHDF5IO
from pynwb.epoch import TimeIntervals

from jnwb.nwb_events import (
    IntervalTableNotFoundError,
    event_onsets,
    events,
    resolve_interval_table,
)

TRIAL_ONSETS = (1.0, 2.0, 3.0)
CUSTOM_ONSETS = (10.0, 11.0)
EPOCH_ONSETS = (20.0, 30.0)


def _new_nwb() -> pynwb.NWBFile:
    return pynwb.NWBFile(
        session_description="in-memory interval test",
        identifier="INMEM_INTERVALS",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )


def _add_trials(nwb: pynwb.NWBFile) -> None:
    for onset in TRIAL_ONSETS:
        nwb.add_trial(start_time=onset, stop_time=onset + 0.5)


def _add_custom(nwb: pynwb.NWBFile) -> None:
    custom = TimeIntervals(name="custom", description="custom intervals")
    for onset in CUSTOM_ONSETS:
        custom.add_interval(start_time=onset, stop_time=onset + 0.5)
    nwb.add_time_intervals(custom)


def _add_epochs(nwb: pynwb.NWBFile) -> None:
    for onset in EPOCH_ONSETS:
        nwb.add_epoch(start_time=onset, stop_time=onset + 1.0)


def _add_invalid_times(nwb: pynwb.NWBFile) -> None:
    for onset in CUSTOM_ONSETS:
        nwb.add_invalid_time_interval(start_time=onset, stop_time=onset + 0.25)


CASES = [
    pytest.param(_add_trials, None, "trials", id="trials-only"),
    pytest.param(
        lambda nwb: (_add_trials(nwb), _add_custom(nwb)), None, "trials", id="trials-and-custom"
    ),
    pytest.param(_add_epochs, "epochs", "epochs", id="epochs"),
    pytest.param(_add_invalid_times, None, "invalid_times", id="invalid-times-only"),
]


def _write(nwb: pynwb.NWBFile, path: Path) -> Path:
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


@pytest.mark.parametrize(("build", "table", "expected"), CASES)
def test_in_memory_resolution_matches_written_file(build, table, expected, tmp_path):
    mem_nwb = _new_nwb()
    build(mem_nwb)
    disk_path = _write(_build_fresh(build), tmp_path / "written.nwb")

    disk = events(disk_path, table=table, code_column=None)
    assert disk.table == expected  # positive control: the written file is unchanged
    assert disk.n_events > 0, "fixture must build rows"

    assert resolve_interval_table(mem_nwb, table) == expected
    mem = events(mem_nwb, table=table, code_column=None)
    assert mem.table == expected
    np.testing.assert_array_equal(mem.onsets, disk.onsets)
    np.testing.assert_array_equal(
        event_onsets(mem_nwb, table=table, code_column=None), disk.onsets
    )


def _build_fresh(build) -> pynwb.NWBFile:
    nwb = _new_nwb()
    build(nwb)
    return nwb


def test_in_memory_trials_are_not_hidden_behind_another_table():
    nwb = _new_nwb()
    _add_trials(nwb)
    _add_custom(nwb)
    assert resolve_interval_table(nwb) == "trials"


def test_empty_in_memory_file_still_raises_not_found():
    nwb = _new_nwb()
    with pytest.raises(IntervalTableNotFoundError, match="No interval tables"):
        resolve_interval_table(nwb)
    with pytest.raises(IntervalTableNotFoundError):
        resolve_interval_table(nwb, "epochs")


def test_in_memory_trials_only_has_no_epochs_table():
    nwb = _new_nwb()
    _add_trials(nwb)
    with pytest.raises(IntervalTableNotFoundError, match="'epochs' not found"):
        resolve_interval_table(nwb, "epochs")
