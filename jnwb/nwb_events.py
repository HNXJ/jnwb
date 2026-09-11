"""Canonical NWB interval-table event and onset extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence, Union

import numpy as np
import pandas as pd
from pynwb import NWBFile

from jnwb.nwb_io import nwb_read_io

PathLike = Union[str, Path]
NWBInput = Union[PathLike, NWBFile]
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
    code_column: str
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
        return clean.split("/", 3)[-1]
    if clean.startswith("intervals/"):
        return clean.split("/", 1)[-1]
    return clean


def resolve_interval_table(nwb: NWBFile, table: str | None) -> str:
    """Resolve an interval table name using jnwb addressing rules.

    When ``table`` is omitted:

    * use ``trials`` if present;
    * else use the sole interval table when exactly one exists;
    * else raise :class:`AmbiguousIntervalTableError`.
    """
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


def _with_nwb(path_or_nwb: NWBInput, fn):
    if isinstance(path_or_nwb, NWBFile):
        return fn(path_or_nwb)
    path = Path(path_or_nwb)
    if not path.exists():
        raise FileNotFoundError(f"NWB file not found: {path}")
    with nwb_read_io(str(path), load_namespaces=True) as io:
        return fn(io.read())


def _read_interval_dataframe(nwb: NWBFile, table: str) -> pd.DataFrame:
    name = resolve_interval_table(nwb, table)
    return name, nwb.intervals[name].to_dataframe()


def _as_code_sequence(codes: CodeSequence | None) -> tuple[CodeValue, ...] | None:
    if codes is None:
        return None
    if isinstance(codes, (str, int, float, np.integer, np.floating)):
        return (codes,)  # type: ignore[return-value]
    return tuple(codes)


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


def _extract_onsets(
    df: pd.DataFrame,
    *,
    codes: CodeSequence | None,
    code_column: str,
    onset_column: str,
) -> tuple[np.ndarray, tuple[Any, ...], np.ndarray | None]:
    if code_column not in df.columns:
        raise ColumnNotFoundError(
            f"Code column '{code_column}' not found. Columns: {list(df.columns)}"
        )
    if onset_column not in df.columns:
        raise ColumnNotFoundError(
            f"Onset column '{onset_column}' not found. Columns: {list(df.columns)}"
        )

    wanted = _as_code_sequence(codes)
    if wanted is not None and len(wanted) == 0:
        return (
            np.asarray([], dtype=np.float64),
            tuple(),
            np.asarray([], dtype=np.float64) if "stop_time" in df.columns else None,
        )

    selected_codes: list[Any] = []
    selected_onsets: list[float] = []
    selected_stops: list[float] = []
    has_stop = "stop_time" in df.columns

    for row_idx, row in df.iterrows():
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
    code_column: str = "codes",
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
        Column holding event codes. Defaults to ``codes`` because that is the
        primary supported corpus pattern; pass another name explicitly when needed.
    onset_column:
        Timestamp column for event alignment. Defaults to ``start_time``.

    Returns
    -------
    EventTable
        All rows from the selected table in original order. Onsets are in seconds.
    """
    def _build(nwb: NWBFile) -> EventTable:
        name, df = _read_interval_dataframe(nwb, table)
        onsets, codes_out, stops = _extract_onsets(
            df,
            codes=None,
            code_column=code_column,
            onset_column=onset_column,
        )
        return EventTable(
            table=name,
            path=f"/intervals/{name}",
            code_column=code_column,
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
    code_column: str = "codes",
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
        duplicate rows. When omitted, all rows are returned. When provided but
        nothing matches, returns an empty array (valid empty selection).
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
