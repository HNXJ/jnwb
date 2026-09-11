"""§3 harness: canonical NWB event/onset API."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import pynwb
from dateutil.tz import tzutc
from pynwb import NWBHDF5IO
from pynwb.epoch import TimeIntervals

import jnwb
from jnwb.nwb_events import (
    AmbiguousIntervalTableError,
    ColumnNotFoundError,
    EventTable,
    IntervalTableNotFoundError,
    InvalidOnsetValueError,
    codes_equal,
    event_onsets,
    events,
    resolve_interval_table,
)
from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    CODE_LABEL_B,
    CODE_NUMERIC_A,
    CODE_NUMERIC_B,
    FLASH_TABLE,
    RF_TABLE,
    TASK_TABLE,
    canonical_co_resident_options,
    numeric_codes_options,
    task_only_options,
    write_synth_nwb,
)


def _write_interval_only_nwb(path: Path, tables: dict[str, TimeIntervals]) -> None:
    nwb = pynwb.NWBFile(
        session_description="interval test",
        identifier="INTERVAL_TEST",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    for table in tables.values():
        nwb.add_time_intervals(table)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)


def _task_table_with_extra_row() -> TimeIntervals:
    table = TimeIntervals(name=TASK_TABLE, description="task")
    table.add_column(name="codes", description="codes")
    table.add_column(name="task_condition_number", description="cond")
    table.add_column(name="stimulus_number", description="stim")
    table.add_column(name="trial_num", description="trial")
    table.add_column(name="correct", description="correct")
    table.add_column(name="marker_flag", description="marker")
    onsets = 1.0 + 0.5 * np.arange(10)
    for i, onset in enumerate(onsets):
        code = CODE_LABEL_A if i % 2 == 0 else CODE_LABEL_B
        table.add_row(
            start_time=float(onset),
            stop_time=float(onset),
            codes=code,
            task_condition_number=float((i % 2) + 1),
            stimulus_number=float((i % 3) + 1),
            trial_num=float(i + 1),
            correct=1.0,
            marker_flag=float(i % 2),
        )
    # duplicate code row with distinct onset
    table.add_row(
        start_time=float(onsets[0] + 0.01),
        stop_time=float(onsets[0] + 0.01),
        codes=CODE_LABEL_A,
        task_condition_number=1.0,
        stimulus_number=1.0,
        trial_num=99.0,
        correct=1.0,
        marker_flag=0.0,
    )
    return table


@pytest.fixture
def canonical_path(tmp_path):
    path = tmp_path / "canonical.nwb"
    receipt = write_synth_nwb(path, canonical_co_resident_options())
    return path, receipt


class TestPublicExports:
    def test_symbols_exported(self):
        for name in (
            "events",
            "event_onsets",
            "EventTable",
            "resolve_interval_table",
            "AmbiguousIntervalTableError",
        ):
            assert hasattr(jnwb, name)


class TestCodesEqual:
    def test_no_string_numeric_coercion(self):
        assert not codes_equal("1", 1)
        assert not codes_equal(1.0, "1.0")
        assert codes_equal("test-synth-1", "test-synth-1")
        assert codes_equal(1.0, 1.0)


class TestCanonicalFixture:
    def test_task_onsets_exact(self, canonical_path):
        path, receipt = canonical_path
        onsets = event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
        expected = receipt.task_onsets_s[::2]
        np.testing.assert_allclose(onsets, expected)

    def test_rf_and_flash_tables(self, canonical_path):
        path, receipt = canonical_path
        rf = event_onsets(path, table=RF_TABLE, codes=[CODE_LABEL_A])
        flash = event_onsets(path, table=FLASH_TABLE, codes=[CODE_LABEL_B])
        np.testing.assert_allclose(rf, receipt.rf_onsets_s[::2])
        np.testing.assert_allclose(flash, receipt.flash_onsets_s[1::2])

    def test_events_structured_return(self, canonical_path):
        path, _ = canonical_path
        et = events(path, table=TASK_TABLE)
        assert isinstance(et, EventTable)
        assert et.path == f"/intervals/{TASK_TABLE}"
        assert et.code_column == "codes"
        assert et.onset_column == "start_time"
        assert et.time_unit == "seconds"
        assert et.n_events == 10

    def test_numeric_codes(self, tmp_path):
        path = tmp_path / "numeric.nwb"
        receipt = write_synth_nwb(path, numeric_codes_options())
        onsets = event_onsets(path, table=TASK_TABLE, codes=[CODE_NUMERIC_A])
        np.testing.assert_allclose(onsets, receipt.task_onsets_s[::2])

    def test_task_only_fallback(self, tmp_path):
        path = tmp_path / "task_only.nwb"
        receipt = write_synth_nwb(path, task_only_options())
        onsets = event_onsets(path, codes=[CODE_LABEL_A])
        np.testing.assert_allclose(onsets, receipt.task_onsets_s[::2])

    def test_duplicate_codes_preserved(self, tmp_path):
        path = tmp_path / "dup.nwb"
        _write_interval_only_nwb(path, {TASK_TABLE: _task_table_with_extra_row()})
        onsets = event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
        assert onsets.shape == (6,)
        assert onsets[0] == 1.0
        assert 1.01 in onsets

    def test_absent_requested_code_empty(self, canonical_path):
        path, _ = canonical_path
        onsets = event_onsets(path, table=TASK_TABLE, codes=["missing-code"])
        assert onsets.size == 0

    def test_empty_codes_sequence_empty(self, canonical_path):
        path, _ = canonical_path
        onsets = event_onsets(path, table=TASK_TABLE, codes=[])
        assert onsets.size == 0

    def test_ambiguous_omitted_table(self, canonical_path):
        path, _ = canonical_path
        with pytest.raises(AmbiguousIntervalTableError):
            event_onsets(path, codes=[CODE_LABEL_A])

    def test_missing_table(self, canonical_path):
        path, _ = canonical_path
        with pytest.raises(IntervalTableNotFoundError):
            event_onsets(path, table="absent_table")

    def test_missing_codes_column(self, canonical_path):
        path, _ = canonical_path
        with pytest.raises(ColumnNotFoundError):
            event_onsets(path, table=TASK_TABLE, code_column="absent_col")

    def test_alternate_code_column(self, tmp_path):
        path = tmp_path / "alt_col.nwb"
        table = TimeIntervals(name="custom_events", description="custom")
        table.add_column(name="event_label", description="label")
        table.add_row(start_time=1.0, stop_time=1.0, event_label="test-synth-1")
        _write_interval_only_nwb(path, {"custom_events": table})
        onsets = event_onsets(
            path,
            table="custom_events",
            codes=["test-synth-1"],
            code_column="event_label",
        )
        np.testing.assert_allclose(onsets, [1.0])

    def test_table_path_form(self, canonical_path):
        path, receipt = canonical_path
        onsets = event_onsets(
            path,
            table=f"/intervals/{TASK_TABLE}",
            codes=[CODE_LABEL_B],
        )
        np.testing.assert_allclose(onsets, receipt.task_onsets_s[1::2])

    def test_string_code_no_match_numeric_request(self, canonical_path):
        path, _ = canonical_path
        onsets = event_onsets(path, table=TASK_TABLE, codes=[1.0])
        assert onsets.size == 0


class TestEdgeConstructs:
    def test_missing_onset_column(self, tmp_path):
        path = tmp_path / "no_onset.nwb"
        table = TimeIntervals(name="bad", description="bad")
        table.add_column(name="codes", description="codes")
        table.add_row(start_time=1.0, stop_time=1.0, codes=CODE_LABEL_A)
        _write_interval_only_nwb(path, {"bad": table})
        with pytest.raises(ColumnNotFoundError):
            event_onsets(path, table="bad", onset_column="missing_start")

    def test_nan_onset_raises(self, tmp_path):
        path = tmp_path / "nan_onset.nwb"
        table = TimeIntervals(name=TASK_TABLE, description="task")
        table.add_column(name="codes", description="codes")
        table.add_row(start_time=np.nan, stop_time=np.nan, codes=CODE_LABEL_A)
        _write_interval_only_nwb(path, {TASK_TABLE: table})
        with pytest.raises(InvalidOnsetValueError):
            event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])

    def test_trials_table_preferred(self, tmp_path):
        path = tmp_path / "trials.nwb"
        trials = TimeIntervals(name="trials", description="trials")
        trials.add_column(name="codes", description="codes")
        trials.add_row(start_time=5.0, stop_time=5.0, codes="test-synth-1")
        other = TimeIntervals(name="other", description="other")
        other.add_column(name="codes", description="codes")
        other.add_row(start_time=9.0, stop_time=9.0, codes="test-synth-2")
        _write_interval_only_nwb(path, {"trials": trials, "other": other})
        with NWBHDF5IO(str(path), "r") as io:
            assert resolve_interval_table(io.read(), None) == "trials"
        onsets = event_onsets(path, codes=["test-synth-1"])
        np.testing.assert_allclose(onsets, [5.0])
