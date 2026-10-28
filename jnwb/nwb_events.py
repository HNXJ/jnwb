"""Canonical NWB interval-table event and onset extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence, Union

import warnings

import numpy as np
import pandas as pd
from pynwb import NWBFile, TimeSeries

from jnwb.nwb_io import NWBInput, _with_nwb
CodeValue = Union[str, int, float]
CodeSequence = Union[CodeValue, Sequence[CodeValue]]


class NWBEventError(Exception):
    """Base class for event/onset extraction errors."""


class AmbiguousIntervalTableError(NWBEventError):
    """Several interval tables are present and ``table`` was not specified."""


class IntervalTableNotFoundError(NWBEventError):
    """The requested interval table does not exist."""


class ColumnNotFoundError(NWBEventError):
    """A required interval-table column is missing."""


class InvalidOnsetValueError(NWBEventError):
    """A selected row has a missing or non-finite onset timestamp."""


@dataclass(frozen=True)
class EventTable:
    """Structured event rows from one NWB interval table.

    An **event code** is an opaque label stored in a named interval-table column
    (default ``codes``). It identifies which interval row to select; jnwb does
    not assign scientific meaning to code values.

    **Onsets** are read from ``onset_column`` (default ``start_time``) in
    **seconds** relative to the session clock, in original table row order.
    """

    table: str
    path: str
    code_column: str | None
    onset_column: str
    time_unit: str
    codes: tuple[Any, ...]
    onsets: np.ndarray
    stop_times: np.ndarray | None

    @property
    def n_events(self) -> int:
        return len(self.onsets)


def _normalize_table_name(table: str) -> str:
    clean = table.strip()
    if clean.startswith("/intervals/"):
        return clean[len("/intervals/"):]
    if clean.startswith("intervals/"):
        return clean.split("/", 1)[-1]
    return clean


def resolve_interval_table(path_or_nwb: NWBInput, table: str | None = None) -> str:
    """Resolve an interval table name using jnwb addressing rules.

    Takes a path or an open ``NWBFile``, like every other exported NWB function. It used
    to be the only one that required an already-open handle, and to require ``table``
    positionally: a path gave ``AttributeError: 'str' object has no attribute
    'intervals'``, against its exact sibling ``resolve_acquisition(path_or_nwb,
    name=None)``.

    When ``table`` is omitted:

    * use ``trials`` if present;
    * else use the sole interval table when exactly one exists;
    * else raise :class:`AmbiguousIntervalTableError`.
    """
    if not isinstance(path_or_nwb, (NWBFile, str, Path)):
        raise TypeError(
            f"resolve_interval_table: expected a path (str or Path) or an open "
            f"pynwb.NWBFile; got {type(path_or_nwb).__name__}."
        )
    return _with_nwb(path_or_nwb, lambda nwb: _resolve_interval_table(nwb, table))


def _resolve_interval_table(nwb: NWBFile, table: str | None) -> str:
    names = sorted(nwb.intervals.keys()) if nwb.intervals else []
    if not names:
        raise IntervalTableNotFoundError("No interval tables found in NWB file")
    if table is not None:
        name = _normalize_table_name(table)
        if name not in nwb.intervals:
            raise IntervalTableNotFoundError(
                f"Interval table '{name}' not found. Available: {names}"
            )
        return name
    if "trials" in names:
        return "trials"
    if len(names) == 1:
        return names[0]
    raise AmbiguousIntervalTableError(
        "Several interval tables and none named 'trials': "
        f"{names}. Pass table=<name> explicitly."
    )


def _read_interval_dataframe(nwb: NWBFile, table: str) -> pd.DataFrame:
    name = _resolve_interval_table(nwb, table)
    return name, nwb.intervals[name].to_dataframe()


def _refuse_code_type(code: Any) -> None:
    """Refuse a requested code that is bytes or a bool.

    Bytes would be iterated as integers, and a bool compares equal to 0 and 1, so neither can
    name a code. Cell values are read by :func:`_normalize_cell_code`, not checked here.
    """
    if isinstance(code, (bytes, bool, np.bool_)):
        raise TypeError(
            f"event codes must be str, int or float, not {type(code).__name__}: {code!r}"
        )


def _as_code_sequence(codes: CodeSequence | None) -> tuple[CodeValue, ...] | None:
    if codes is None:
        return None
    if isinstance(codes, (str, bytes, bool, np.bool_, int, float, np.integer, np.floating)):
        members = (codes,)
    else:
        members = tuple(codes)
    for code in members:
        _refuse_code_type(code)
    return members  # type: ignore[return-value]


def _is_string_like(value: Any) -> bool:
    return isinstance(value, (str, bytes, np.bytes_))


def _normalize_cell_code(value: Any) -> Any:
    if _is_string_like(value):
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, int):
        return value
    return value


def codes_equal(cell: Any, requested: CodeValue) -> bool:
    """Compare event codes without cross-type coercion (``\"1\"`` ≠ ``1``)."""
    cell_norm = _normalize_cell_code(cell)
    req_norm = _normalize_cell_code(requested)
    if _is_string_like(cell_norm) or isinstance(req_norm, str):
        return isinstance(cell_norm, str) and isinstance(req_norm, str) and cell_norm == req_norm
    if pd.isna(cell_norm) or pd.isna(req_norm):
        return bool(pd.isna(cell_norm) and pd.isna(req_norm))
    return cell_norm == req_norm


def _row_matches_codes(cell: Any, wanted: tuple[CodeValue, ...] | None) -> bool:
    if wanted is None:
        return True
    return any(codes_equal(cell, code) for code in wanted)


_DEFAULT_CODE_COLUMN = "codes"


def _extract_onsets(
    df: pd.DataFrame,
    *,
    codes: CodeSequence | None,
    code_column: str | None,
    onset_column: str,
) -> tuple[np.ndarray, tuple[Any, ...], np.ndarray | None]:
    if onset_column not in df.columns:
        raise ColumnNotFoundError(
            f"Onset column '{onset_column}' not found. Columns: {list(df.columns)}"
        )

    wanted = _as_code_sequence(codes)
    if wanted is not None:
        if code_column is None or code_column not in df.columns:
            raise ColumnNotFoundError(
                f"Code column '{code_column}' not found. Columns: {list(df.columns)}"
            )
        if len(wanted) == 0:
            return (
                np.asarray([], dtype=np.float64),
                tuple(),
                np.asarray([], dtype=np.float64) if "stop_time" in df.columns else None,
            )
    elif code_column is not None and code_column != "codes" and code_column not in df.columns:
        raise ColumnNotFoundError(
            f"Code column '{code_column}' not found. Columns: {list(df.columns)}"
        )

    has_code_col = code_column is not None and code_column in df.columns
    selected_codes: list[Any] = []
    selected_onsets: list[float] = []
    selected_stops: list[float] = []
    has_stop = "stop_time" in df.columns

    for row_idx, row in df.iterrows():
        if wanted is not None:
            if not _row_matches_codes(row[code_column], wanted):
                continue
        onset_raw = row[onset_column]
        if pd.isna(onset_raw):
            raise InvalidOnsetValueError(
                f"Missing onset in column '{onset_column}' at table row {row_idx}"
            )
        onset = float(onset_raw)
        if not np.isfinite(onset):
            raise InvalidOnsetValueError(
                f"Non-finite onset in column '{onset_column}' at table row {row_idx}: {onset_raw}"
            )
        if has_code_col:
            selected_codes.append(_normalize_cell_code(row[code_column]))
        selected_onsets.append(onset)
        if has_stop:
            stop_raw = row["stop_time"]
            selected_stops.append(float(stop_raw) if pd.notna(stop_raw) else np.nan)

    stop_arr = (
        np.asarray(selected_stops, dtype=np.float64)
        if has_stop
        else None
    )
    return (
        np.asarray(selected_onsets, dtype=np.float64),
        tuple(selected_codes),
        stop_arr,
    )


def events(
    path_or_nwb: NWBInput,
    *,
    table: str | None = None,
    code_column: str | None = "codes",
    onset_column: str = "start_time",
) -> EventTable:
    """Read event codes and onset timestamps from one interval table.

    Parameters
    ----------
    path_or_nwb:
        Path to an ``.nwb`` file or an in-memory :class:`pynwb.NWBFile`.
    table:
        Interval table name (e.g. ``test_synth_task``) or path
        (``/intervals/test_synth_task``). When omitted, :func:`resolve_interval_table`
        applies the ``trials`` → sole-table → ambiguity rules.
    code_column:
        Column holding event codes. Defaults to ``codes``, which is a jnwb
        convention rather than an NWB one: a file from another lab usually names
        this column something else, and :func:`inspect` lists the columns that
        exist. A column named explicitly here must exist, or
        :class:`ColumnNotFoundError` is raised naming the columns that do. The
        default name is the one exception -- when ``codes`` is absent, onsets are
        returned without error, ``EventTable.code_column`` is ``None``, and a
        ``UserWarning`` names the available columns.
    onset_column:
        Timestamp column for event alignment. Defaults to ``start_time``.

    Returns
    -------
    EventTable
        All rows from the selected table in original order. Onsets are in seconds.
    """
    def _build(nwb: NWBFile) -> EventTable:
        name, df = _read_interval_dataframe(nwb, table)
        active_code_col = code_column
        if code_column is not None and code_column not in df.columns:
            # A column the caller named explicitly is a stated expectation, so it fails the
            # same way it fails in `event_onsets`. The default name is the one case that is
            # allowed to be absent -- a file from another lab rarely has a column called
            # `codes` -- but it warns rather than returning an empty `codes` tuple in
            # silence, because the column that IS there is what the caller needs next.
            if code_column != _DEFAULT_CODE_COLUMN:
                raise ColumnNotFoundError(
                    f"Code column '{code_column}' not found. Columns: {list(df.columns)}"
                )
            warnings.warn(
                f"No '{_DEFAULT_CODE_COLUMN}' column in interval table '{name}'; "
                f"returning onsets without codes. Columns: {list(df.columns)}. "
                f"Pass code_column= to read one of them as event codes.",
                UserWarning,
                stacklevel=3,
            )
            active_code_col = None
        onsets, codes_out, stops = _extract_onsets(
            df,
            codes=None,
            code_column=active_code_col,
            onset_column=onset_column,
        )
        return EventTable(
            table=name,
            path=f"/intervals/{name}",
            code_column=active_code_col,
            onset_column=onset_column,
            time_unit="seconds",
            codes=codes_out,
            onsets=onsets,
            stop_times=stops,
        )

    return _with_nwb(path_or_nwb, _build)


def event_onsets(
    path_or_nwb: NWBInput,
    *,
    table: str | None = None,
    codes: CodeSequence | None = None,
    code_column: str | None = "codes",
    onset_column: str = "start_time",
) -> np.ndarray:
    """Return onset timestamps (seconds) for rows matching ``codes``.

    Parameters
    ----------
    path_or_nwb:
        NWB path or in-memory file.
    table:
        Interval table selection; see :func:`events`.
    codes:
        One code or a sequence of codes. Matching preserves table order and
        duplicate rows. When omitted (``codes=None``), all rows are returned; the
        default ``codes`` column may then be absent, without a warning, but a
        ``code_column`` you name must exist or ``ColumnNotFoundError`` is raised. When provided but
        nothing matches, returns an empty array (valid empty selection). A bytes or bool code
        raises ``TypeError`` naming its type; str, int and float codes match as before.
    code_column, onset_column:
        See :func:`events`.

    Returns
    -------
    numpy.ndarray
        One-dimensional ``float64`` onset times in seconds, table-row order.
    """
    def _build(nwb: NWBFile) -> np.ndarray:
        name, df = _read_interval_dataframe(nwb, table)
        onsets, _, _ = _extract_onsets(
            df,
            codes=codes,
            code_column=code_column,
            onset_column=onset_column,
        )
        return onsets

    return _with_nwb(path_or_nwb, _build)


def _series_at(nwb: NWBFile, series_path: str) -> TimeSeries:
    """Return the object at ``series_path`` (``<container>/<name>``), which must be a TimeSeries."""
    obj: Any = nwb
    for part in series_path.strip("/").split("/"):
        try:
            obj = obj[part] if isinstance(obj, dict) else getattr(obj, part)
        except (KeyError, AttributeError) as exc:
            raise KeyError(
                f"edges_near_events: no object at '{series_path}' (no '{part}')"
            ) from exc
    if not isinstance(obj, TimeSeries):
        raise TypeError(
            f"edges_near_events: '{series_path}' is a {type(obj).__name__}, not a TimeSeries"
        )
    return obj


def _series_samples(series: TimeSeries) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(times_s, values)`` of a one-dimensional TimeSeries on the session clock.

    A series with a ``rate`` has sample ``i`` at ``starting_time + i / rate``, as
    :func:`jnwb.nwb_inspect.acquisition_channel` reads it; one with ``timestamps`` has those.
    """
    values = np.asarray(series.data[:], dtype=np.float64)
    if values.ndim != 1:
        raise ValueError(
            f"edges_near_events: series '{series.name}' has shape {values.shape}; "
            "one-dimensional data is required"
        )
    if series.rate is not None:
        rate = float(series.rate)
        if not (np.isfinite(rate) and rate > 0):
            raise ValueError(
                f"edges_near_events: series '{series.name}' has rate {rate!r} Hz, "
                "which is not a finite positive rate"
            )
        start = 0.0 if series.starting_time is None else float(series.starting_time)
        times = start + np.arange(values.size) / rate
    else:
        if series.timestamps is None:
            raise ValueError(
                f"edges_near_events: series '{series.name}' has neither a rate nor timestamps"
            )
        times = np.asarray(series.timestamps[:], dtype=np.float64)
    if times.size != values.size or not np.all(np.diff(times) > 0):
        raise ValueError(
            f"edges_near_events: series '{series.name}' needs strictly increasing times, one "
            "per sample"
        )
    return times, values


def _edge_times(
    times: np.ndarray, values: np.ndarray, threshold: float
) -> tuple[np.ndarray, np.ndarray]:
    """Times of the rising and falling edges: the first sample at or past ``threshold``.

    A sample is high when ``value >= threshold``; a NaN sample is low.
    """
    step = np.diff((values >= threshold).astype(np.int8))
    rising = times[np.flatnonzero(step == 1) + 1]
    falling = times[np.flatnonzero(step == -1) + 1]
    return rising, falling


def _nearest_in_window(
    edges: np.ndarray, centers: np.ndarray, before_s: float, after_s: float
) -> np.ndarray:
    """The edge nearest each center within ``[center - before_s, center + after_s]``, else NaN.

    Ties go to the earlier edge. A NaN center gets NaN.
    """
    picked = np.full(centers.shape, np.nan)
    if edges.size == 0:
        return picked
    # edges[j - 1] < center <= edges[j]: the two candidates are the nearest on each side.
    j = np.searchsorted(edges, centers, side="left")
    left = np.full(centers.shape, np.nan)
    right = np.full(centers.shape, np.nan)
    has_left = j > 0
    has_right = j < edges.size
    left[has_left] = edges[j[has_left] - 1]
    right[has_right] = edges[j[has_right]]
    left_ok = centers - left <= before_s
    right_ok = right - centers <= after_s
    prefer_left = left_ok & (~right_ok | (centers - left <= right - centers))
    prefer_right = right_ok & ~prefer_left
    picked[prefer_left] = left[prefer_left]
    picked[prefer_right] = right[prefer_right]
    return picked


def _window_bounds(window_s: tuple[float, float]) -> tuple[float, float]:
    before_s, after_s = (float(v) for v in window_s)
    if not (np.isfinite(before_s) and np.isfinite(after_s)) or before_s < 0.0 or after_s < 0.0:
        raise ValueError(
            "edges_near_events: window_s must be two finite non-negative seconds "
            f"(before_s, after_s); got {window_s!r}"
        )
    return before_s, after_s


def edges_near_events(
    path_or_nwb: NWBInput,
    series_path: str,
    events: Sequence[float] | np.ndarray,
    *,
    threshold: float,
    window_s: tuple[float, float],
) -> pd.DataFrame:
    """Return the rising and falling edge nearest each event of a TimeSeries.

    Parameters
    ----------
    path_or_nwb:
        NWB path or in-memory file.
    series_path:
        Path of a TimeSeries in the file, e.g. ``acquisition/photodiode_1_tracking``. A
        non-TimeSeries object is refused with ``TypeError``.
    events:
        Event times in seconds, on the session clock.
    threshold:
        A sample at or above ``threshold`` is high. A rising edge is the first high sample after
        a low one; a falling edge the first low sample after a high one. Each edge is stamped with
        its sample's time.
    window_s:
        ``(before_s, after_s)``: edges within ``before_s`` before and ``after_s`` after each event
        are candidates. Both must be finite and non-negative.

    Returns
    -------
    pandas.DataFrame
        One row per event, in input order, with columns ``event_s``, ``rising_edge_s``,
        ``rising_lag_s``, ``falling_edge_s`` and ``falling_lag_s``. The edge is the candidate
        nearest the event (ties to the earlier one); a lag is ``edge_s - event_s``, so negative
        means the edge came first. NaN where the window holds no edge of that kind.
    """
    before_s, after_s = _window_bounds(window_s)
    centers = np.asarray(events, dtype=np.float64).ravel()

    def _build(nwb: NWBFile) -> pd.DataFrame:
        times, values = _series_samples(_series_at(nwb, series_path))
        rising, falling = _edge_times(times, values, threshold)
        rising_edge = _nearest_in_window(rising, centers, before_s, after_s)
        falling_edge = _nearest_in_window(falling, centers, before_s, after_s)
        return pd.DataFrame(
            {
                "event_s": centers,
                "rising_edge_s": rising_edge,
                "rising_lag_s": rising_edge - centers,
                "falling_edge_s": falling_edge,
                "falling_lag_s": falling_edge - centers,
            }
        )

    return _with_nwb(path_or_nwb, _build)
