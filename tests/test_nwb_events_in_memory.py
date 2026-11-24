"""Interval tables of an in-memory NWBFile resolve as they do once written and read back.

In memory, `add_trial`, `add_epoch` and `add_invalid_time_interval` fill `nwb.trials`,
`nwb.epochs` and `nwb.invalid_times`; `nwb.intervals` holds only tables added with
`add_time_intervals`. Each test compares the object form with the same file on disk.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
from dateutil.tz import tzutc
from pynwb import NWBHDF5IO, NWBFile
from pynwb.epoch import TimeIntervals

from jnwb.nwb_events import event_onsets, events, resolve_interval_table

TRIAL_STARTS = (1.0, 2.5, 4.0)
TRIAL_CODES = ("a", "b", "a")
CUSTOM_STARTS = (10.0, 20.0)
EPOCH_STARTS = (0.25, 7.0)


def _build(*, trials: bool, custom: bool, epochs: bool) -> NWBFile:
    nwb = NWBFile(
        session_description="in-memory intervals",
        identifier="IN_MEMORY_INTERVALS",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    if trials:
        nwb.add_trial_column(name="codes", description="codes")
        for start, code in zip(TRIAL_STARTS, TRIAL_CODES):
            nwb.add_trial(start_time=start, stop_time=start + 0.5, codes=code)
    if custom:
        table = TimeIntervals(name="custom", description="custom")
        table.add_column(name="codes", description="codes")
        for start in CUSTOM_STARTS:
            table.add_interval(start_time=start, stop_time=start + 1.0, codes="z")
        nwb.add_time_intervals(table)
    if epochs:
        for start in EPOCH_STARTS:
            nwb.add_epoch(start_time=start, stop_time=start + 0.1)
    return nwb


def _on_disk(tmp_path, **kwargs):
    path = tmp_path / "written.nwb"
    with NWBHDF5IO(str(path), "w") as io:
        io.write(_build(**kwargs))
    return path


def test_trials_only_resolves_trials_in_memory(tmp_path):
    nwb = _build(trials=True, custom=False, epochs=False)
    assert nwb.trials is not None and not nwb.intervals, "fixture must hold trials outside nwb.intervals"
    path = _on_disk(tmp_path, trials=True, custom=False, epochs=False)
    assert resolve_interval_table(path) == "trials"
    assert resolve_interval_table(nwb) == "trials"
    np.testing.assert_array_equal(event_onsets(nwb), event_onsets(path))
    np.testing.assert_array_equal(event_onsets(nwb), np.asarray(TRIAL_STARTS))


def test_trials_beat_a_custom_table_in_memory(tmp_path):
    nwb = _build(trials=True, custom=True, epochs=False)
    assert list(nwb.intervals) == ["custom"], "fixture must hold trials outside nwb.intervals"
    path = _on_disk(tmp_path, trials=True, custom=True, epochs=False)
    assert resolve_interval_table(path) == "trials"
    assert resolve_interval_table(nwb) == "trials"
    in_memory, written = events(nwb), events(path)
    assert in_memory.table == written.table == "trials"
    assert in_memory.codes == written.codes == TRIAL_CODES
    np.testing.assert_array_equal(in_memory.onsets, written.onsets)
    np.testing.assert_array_equal(event_onsets(nwb, codes="a"), event_onsets(path, codes="a"))


def test_named_epochs_resolve_in_memory(tmp_path):
    nwb = _build(trials=False, custom=True, epochs=True)
    assert nwb.epochs is not None and "epochs" not in nwb.intervals, "fixture must hold epochs outside nwb.intervals"
    path = _on_disk(tmp_path, trials=False, custom=True, epochs=True)
    assert resolve_interval_table(path, "epochs") == "epochs"
    assert resolve_interval_table(nwb, "epochs") == "epochs"
    np.testing.assert_array_equal(
        event_onsets(nwb, table="epochs", code_column=None),
        event_onsets(path, table="epochs", code_column=None),
    )
    np.testing.assert_array_equal(
        event_onsets(nwb, table="epochs", code_column=None), np.asarray(EPOCH_STARTS)
    )


def _bare() -> NWBFile:
    return NWBFile(
        session_description="in-memory intervals",
        identifier="IN_MEMORY_INTERVALS",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )


def _write(tmp_path, nwb: NWBFile):
    path = tmp_path / "written.nwb"
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


def _invalid_times_only() -> NWBFile:
    nwb = _bare()
    for start in EPOCH_STARTS:
        nwb.add_invalid_time_interval(start_time=start, stop_time=start + 0.1)
    return nwb


def _trials_beside_an_intervals_entry_named_trials() -> NWBFile:
    nwb = _bare()
    nwb.add_trial(start_time=1.0, stop_time=1.5)
    table = TimeIntervals(name="trials", description="added with add_time_intervals")
    table.add_interval(start_time=50.0, stop_time=51.0)
    nwb.add_time_intervals(table)
    return nwb


def test_invalid_times_only_resolves_in_memory(tmp_path):
    nwb = _invalid_times_only()
    assert nwb.invalid_times is not None and not nwb.intervals, "fixture must hold invalid_times outside nwb.intervals"
    path = _write(tmp_path, _invalid_times_only())
    assert resolve_interval_table(path) == "invalid_times"
    assert resolve_interval_table(nwb) == "invalid_times"
    np.testing.assert_array_equal(event_onsets(nwb, code_column=None), event_onsets(path, code_column=None))
    np.testing.assert_array_equal(event_onsets(nwb, code_column=None), np.asarray(EPOCH_STARTS))


def test_an_intervals_entry_named_trials_wins_as_on_disk(tmp_path):
    nwb = _trials_beside_an_intervals_entry_named_trials()
    assert nwb.trials is not nwb.intervals["trials"], "fixture must hold two distinct tables named trials"
    path = _write(tmp_path, _trials_beside_an_intervals_entry_named_trials())
    assert resolve_interval_table(path) == resolve_interval_table(nwb) == "trials"
    np.testing.assert_array_equal(event_onsets(path, code_column=None), [50.0])
    np.testing.assert_array_equal(event_onsets(nwb, code_column=None), event_onsets(path, code_column=None))
