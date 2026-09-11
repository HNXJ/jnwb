from pathlib import Path
from typing import Optional, Dict, Any
from jnwb.mcp_server.server import mcp
from jnwb.nwb_events import (
    AmbiguousIntervalTableError,
    ColumnNotFoundError,
    IntervalTableNotFoundError,
    InvalidOnsetValueError,
    events,
    resolve_interval_table,
)
from jnwb.nwb_io import nwb_read_io


def _table_from_event_group_path(event_group_path: str | None) -> str | None:
    if not event_group_path:
        return None
    clean = event_group_path.lstrip("/")
    parts = clean.split("/")
    if len(parts) >= 2 and parts[0] == "intervals":
        return parts[1]
    return clean


def _mcp_code_column(columns) -> str | None:
    for col in ("codes", "code", "event_code", "event_codes", "value", "type"):
        if col in columns:
            return col
    for col in columns:
        if "code" in str(col).lower():
            return col
    return None


def _events_to_mcp_payload(et) -> Dict[str, Any]:
    rows = []
    stops = et.stop_times
    if stops is None:
        stops = [None] * len(et.onsets)
    for code, start, stop in zip(et.codes, et.onsets, stops):
        if isinstance(code, float) and float(code).is_integer():
            code_out: Any = int(code)
        else:
            code_out = code
        rows.append(
            {
                "code": code_out,
                "start_time": float(start),
                "stop_time": float(stop) if stop is not None and stop == stop else None,
            }
        )
    return {
        "event_group_path": et.path,
        "events": rows,
        "total_events": et.n_events,
        "time_unit": et.time_unit,
    }


@mcp.tool()
def get_event_codes_and_timings(file_path: str, event_group_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract all event/trial codes and their corresponding sample timestamps from an NWB file using jnwb.

    Args:
        file_path: Path to the .nwb file.
        event_group_path: HDF5 path to the events/trials group, e.g. '/intervals/trials'.
            When omitted: '/intervals/trials', else the file's only interval table, else an
            AmbiguousPath error listing the tables.

    Returns:
        Structured JSON metadata and list of events or error dictionary.
    """
    path = Path(file_path)
    if not path.exists():
        return {
            "error": f"File not found: {file_path}",
            "error_type": "FileNotFound"
        }

    table_arg = _table_from_event_group_path(event_group_path)
    try:
        with nwb_read_io(str(path), load_namespaces=True) as io:
            nwb = io.read()
            if not nwb.intervals:
                return {
                    "error": "No event or interval groups found in NWB file",
                    "error_type": "PathNotFound",
                }
            table = resolve_interval_table(nwb, table_arg)
            df = nwb.intervals[table].to_dataframe()
            code_col = _mcp_code_column(df.columns)
            if code_col is None:
                return {
                    "error": f"Could not find a code column in /intervals/{table}",
                    "error_type": "ParseError",
                }
            et = events(nwb, table=table, code_column=code_col)
        return _events_to_mcp_payload(et)
    except IntervalTableNotFoundError as exc:
        return {"error": str(exc), "error_type": "PathNotFound"}
    except AmbiguousIntervalTableError as exc:
        return {"error": str(exc), "error_type": "AmbiguousPath"}
    except (ColumnNotFoundError, InvalidOnsetValueError) as exc:
        return {"error": str(exc), "error_type": "ParseError"}
    except Exception as e:
        return {
            "error": f"Failed to extract events: {str(e)}",
            "error_type": "Unknown"
        }
