"""§3 harness: canonical NWB event/onset API."""

from __future__ import annotations

import inspect
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
    edges_near_events,
    event_onsets,
    events,
    resolve_interval_table,
)
from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    CODE_LABEL_B,
    CODE_NUMERIC_A,
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

    @pytest.mark.parametrize(
        "bad, type_name",
        [
            (b"test-synth-1", "bytes"),
            ([b"test-synth-1"], "bytes"),
            (True, "bool"),
            ([False], "bool"),
            (np.True_, type(np.True_).__name__),
        ],
    )
    def test_bytes_and_bool_codes_are_refused_by_type(self, canonical_path, bad, type_name):
        path, _ = canonical_path
        with pytest.raises(TypeError, match=f"not {type_name}:"):
            event_onsets(path, table=TASK_TABLE, codes=bad)

    def test_str_and_int_codes_still_pass(self, canonical_path):
        path, _ = canonical_path
        assert event_onsets(path, table=TASK_TABLE, codes=1).size == 0
        assert event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A, 1]).size > 0


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

    def test_table_without_codes_column(self, tmp_path):
        path = tmp_path / "no_codes.nwb"
        table = TimeIntervals(name="trials", description="trials without code column")
        table.add_row(start_time=1.5, stop_time=2.5)
        table.add_row(start_time=3.5, stop_time=4.5)
        _write_interval_only_nwb(path, {"trials": table})

        # codes=None extracts all onsets without requiring code column
        onsets = event_onsets(path, codes=None)
        np.testing.assert_allclose(onsets, [1.5, 3.5])

        # events() returns EventTable without code column, and says so out loud
        with pytest.warns(UserWarning, match="No 'codes' column"):
            et = events(path)
        assert et.n_events == 2
        assert et.code_column is None
        assert et.codes == ()
        np.testing.assert_allclose(et.onsets, [1.5, 3.5])

        # Filtering by codes when no code column exists raises ColumnNotFoundError
        with pytest.raises(ColumnNotFoundError):
            event_onsets(path, codes=["some_code"])


class TestAnAbsentCodeColumnIsNotSilent:
    """`events` used to null ANY absent `code_column` before reading the table, so the
    raise in `_extract_onsets` for an explicitly named missing column was unreachable
    through it. Two things followed on a file from another lab, whose trials table had a
    column named `stimulus`: `events(path)` returned `code_column=None, codes=()` with no
    warning, and `events(path, code_column="condition")` -- a name the caller invented --
    returned exactly the same thing instead of failing, while `event_onsets` with the same
    argument raised. The two entry points now agree.
    """

    @staticmethod
    def _foreign(tmp_path):
        path = tmp_path / "foreign.nwb"
        table = TimeIntervals(name="trials", description="a table from another lab")
        table.add_column(name="stimulus", description="stimulus label")
        table.add_row(start_time=1.0, stop_time=2.0, stimulus="grating")
        table.add_row(start_time=3.0, stop_time=4.0, stimulus="blank")
        _write_interval_only_nwb(path, {"trials": table})
        return path

    def test_the_default_column_being_absent_warns_and_names_the_real_columns(self, tmp_path):
        path = self._foreign(tmp_path)
        with pytest.warns(UserWarning) as record:
            et = events(path)
        message = str([w for w in record if issubclass(w.category, UserWarning)][0].message)
        assert "stimulus" in message, message
        assert "code_column" in message, message
        assert et.code_column is None
        np.testing.assert_allclose(et.onsets, [1.0, 3.0])

    def test_event_onsets_says_what_it_does_when_the_default_column_is_absent(self, tmp_path):
        """Only `events` warns about the absent default column; `event_onsets` returns every
        onset quietly, and its docstring must not promise the warning `events` gives."""
        import warnings

        path = self._foreign(tmp_path)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            np.testing.assert_allclose(event_onsets(path, codes=None), [1.0, 3.0])
        codes_doc = event_onsets.__doc__.split("codes:", 1)[1].split("code_column,", 1)[0]
        assert "without a warning" in codes_doc, codes_doc
        assert "warning says so" not in codes_doc, codes_doc

    def test_a_column_the_caller_named_must_exist(self, tmp_path):
        path = self._foreign(tmp_path)
        with pytest.raises(ColumnNotFoundError, match="condition"):
            events(path, code_column="condition")

    def test_events_and_event_onsets_agree_about_the_same_mistake(self, tmp_path):
        path = self._foreign(tmp_path)
        with pytest.raises(ColumnNotFoundError):
            events(path, code_column="condition")
        with pytest.raises(ColumnNotFoundError):
            event_onsets(path, code_column="condition")

    def test_the_real_column_still_reads_normally(self, tmp_path):
        path = self._foreign(tmp_path)
        et = events(path, code_column="stimulus")
        assert et.code_column == "stimulus"
        assert et.codes == ("grating", "blank")
        np.testing.assert_allclose(
            event_onsets(path, codes=["grating"], code_column="stimulus"), [1.0]
        )


class TestTablePathNamesTheTable:
    """`/intervals/<t>/codes` used to resolve to the table `codes`, so the error named the
    wrong table. The path names one table; a further segment is refused under the name the
    caller gave."""

    def test_extra_segment_is_refused_under_the_callers_name(self, canonical_path):
        path, _ = canonical_path
        with pytest.raises(IntervalTableNotFoundError) as info:
            resolve_interval_table(path, f"/intervals/{TASK_TABLE}/codes")
        message = str(info.value)
        assert f"'{TASK_TABLE}/codes'" in message, message
        assert "'codes'" not in message, message

    def test_table_path_still_resolves_to_its_table(self, canonical_path):
        path, _ = canonical_path
        assert resolve_interval_table(path, f"/intervals/{TASK_TABLE}") == TASK_TABLE


EDGE_RATE_HZ = 1000.0
#: Planted flips of the square wave, in seconds: high on [1.0, 1.2), [2.0, 2.3) and [3.5, end).
PLANTED_RISING_S = (1.0, 2.0, 3.5)
PLANTED_FALLING_S = (1.2, 2.3)


def _square_wave() -> np.ndarray:
    t = np.arange(4000) / EDGE_RATE_HZ
    high = (t >= 1.0) & (t < 1.2) | (t >= 2.0) & (t < 2.3) | (t >= 3.5)
    values = high.astype(np.float64)
    assert np.count_nonzero(np.diff(values)) == 5, "fixture must plant five flips"
    return values


def _write_square_wave(path: Path, *, rate: bool) -> None:
    nwb = pynwb.NWBFile(
        session_description="edge test",
        identifier="EDGE_TEST",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    times = np.arange(4000) / EDGE_RATE_HZ
    timing = {"rate": EDGE_RATE_HZ} if rate else {"timestamps": times}
    series = pynwb.TimeSeries(name="photodiode", data=_square_wave(), unit="a.u.", **timing)
    nwb.add_acquisition(series)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)


class TestEdgesNearEvents:
    """edges_near_events: lags of the rising and falling edges to planted flips."""

    def test_lags_match_planted_flips(self, tmp_path):
        path = tmp_path / "square.nwb"
        _write_square_wave(path, rate=True)
        df = edges_near_events(
            path, "acquisition/photodiode", [0.9, 2.1], threshold=0.5, window_s=(0.2, 0.5)
        )
        one_sample = 1.0 / EDGE_RATE_HZ
        assert len(df) == 2
        # Event 0.9: rising 1.0 (+0.1), falling 1.2 (+0.3).
        # Event 2.1: rising 2.0 (-0.1), falling 2.3 (+0.2).
        np.testing.assert_allclose(df["event_s"], [0.9, 2.1])
        np.testing.assert_allclose(df["rising_edge_s"], [1.0, 2.0], atol=one_sample)
        np.testing.assert_allclose(df["falling_edge_s"], [1.2, 2.3], atol=one_sample)
        np.testing.assert_allclose(df["rising_lag_s"], [0.1, -0.1], atol=one_sample)
        np.testing.assert_allclose(df["falling_lag_s"], [0.3, 0.2], atol=one_sample)

    def test_nearest_edge_wins_over_an_earlier_one(self, tmp_path):
        path = tmp_path / "square.nwb"
        _write_square_wave(path, rate=True)
        # Window [0.8, 2.0] holds rising 1.0 (-0.4) and 2.0 (+0.6); the nearer one is 1.0.
        df = edges_near_events(
            path, "acquisition/photodiode", [1.4], threshold=0.5, window_s=(0.6, 0.6)
        )
        one_sample = 1.0 / EDGE_RATE_HZ
        np.testing.assert_allclose(df["rising_edge_s"], [1.0], atol=one_sample)
        np.testing.assert_allclose(df["rising_lag_s"], [-0.4], atol=one_sample)
        np.testing.assert_allclose(df["falling_lag_s"], [-0.2], atol=one_sample)

    def test_window_with_no_edge_gives_nan(self, tmp_path):
        path = tmp_path / "square.nwb"
        _write_square_wave(path, rate=True)
        df = edges_near_events(
            path, "acquisition/photodiode", [3.0], threshold=0.5, window_s=(0.1, 0.1)
        )
        for column in ("rising_edge_s", "rising_lag_s", "falling_edge_s", "falling_lag_s"):
            assert np.isnan(df[column].iloc[0]), column

    def test_timestamps_series_reads_like_a_rate_series(self, tmp_path):
        rate_path = tmp_path / "rate.nwb"
        stamp_path = tmp_path / "stamps.nwb"
        _write_square_wave(rate_path, rate=True)
        _write_square_wave(stamp_path, rate=False)
        kwargs = dict(threshold=0.5, window_s=(0.2, 0.5))
        events_s = [0.9, 2.1]
        by_rate = edges_near_events(rate_path, "acquisition/photodiode", events_s, **kwargs)
        by_stamp = edges_near_events(stamp_path, "acquisition/photodiode", events_s, **kwargs)
        np.testing.assert_allclose(by_stamp.to_numpy(), by_rate.to_numpy())

    def test_open_file_and_path_agree(self, tmp_path):
        path = tmp_path / "square.nwb"
        _write_square_wave(path, rate=True)
        from_path = edges_near_events(
            path, "acquisition/photodiode", [0.9], threshold=0.5, window_s=(0.2, 0.5)
        )
        with NWBHDF5IO(str(path), "r") as io:
            from_open = edges_near_events(
                io.read(), "acquisition/photodiode", [0.9], threshold=0.5, window_s=(0.2, 0.5)
            )
        np.testing.assert_allclose(from_open.to_numpy(), from_path.to_numpy())

    def test_a_non_timeseries_path_is_refused(self, tmp_path):
        path = tmp_path / "intervals.nwb"
        table = TimeIntervals(name="trials", description="trials")
        table.add_row(start_time=1.0, stop_time=2.0)
        _write_interval_only_nwb(path, {"trials": table})
        with pytest.raises(TypeError, match="not a TimeSeries"):
            edges_near_events(
                path, "intervals/trials", [1.0], threshold=0.5, window_s=(0.1, 0.1)
            )

    @pytest.mark.parametrize("window", [(-0.1, 0.2), (0.2, -0.1)])
    def test_a_negative_window_bound_is_refused(self, tmp_path, window):
        path = tmp_path / "square.nwb"
        _write_square_wave(path, rate=True)
        with pytest.raises(ValueError, match="window"):
            edges_near_events(path, "acquisition/photodiode", [1.0], threshold=0.5, window_s=window)

    def test_threshold_series_and_window_have_no_default(self, tmp_path):
        params = inspect.signature(edges_near_events).parameters
        for name in ("series_path", "threshold", "window_s"):
            assert params[name].default is inspect.Parameter.empty, name
        path = tmp_path / "square.nwb"
        _write_square_wave(path, rate=True)
        with pytest.raises(TypeError):
            edges_near_events(path, "acquisition/photodiode", [1.0], window_s=(0.1, 0.1))

