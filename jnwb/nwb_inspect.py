"""Structured NWB file discovery for jnwb."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import h5py
import numpy as np
from pynwb import NWBFile

from jnwb.nwb_io import nwb_read_io

PathLike = Union[str, Path]
InspectInput = Union[PathLike, NWBFile]

_MAX_SAMPLES = 5


def _decode(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _ndt(obj: h5py.Group | h5py.Dataset) -> str | None:
    raw = obj.attrs.get("neurodata_type")
    if raw is None:
        return None
    return _decode(raw)


def _sample_column(ds: h5py.Dataset, n: int = _MAX_SAMPLES) -> list[Any]:
    if ds.shape[0] == 0:
        return []
    take = min(n, int(ds.shape[0]))
    values = ds[:take]
    out: list[Any] = []
    for item in values:
        if isinstance(item, (bytes, np.bytes_)):
            out.append(item.decode("utf-8", errors="replace"))
        elif isinstance(item, np.generic):
            if np.isnan(item):
                out.append(None)
            else:
                out.append(item.item())
        else:
            out.append(item)
    return out


def _find_series_leaf(group: h5py.Group) -> tuple[str | None, h5py.Dataset | None, float | None]:
    """Return (data_relpath, data_dataset, rate) for an acquisition object."""
    data_path: str | None = None
    data_ds: h5py.Dataset | None = None
    rate: float | None = None

    def visit(name: str, obj: h5py.Dataset | h5py.Group) -> None:
        nonlocal data_path, data_ds, rate
        if isinstance(obj, h5py.Dataset):
            leaf = name.rsplit("/", 1)[-1]
            if leaf == "data" and data_ds is None:
                data_path = name
                data_ds = obj
            if leaf == "rate" and rate is None:
                rate = float(obj[()])
            if leaf == "starting_time" and "rate" in obj.attrs:
                rate = float(obj.attrs["rate"])

    group.visititems(visit)
    if rate is None:
        for _, obj in group.items():
            if isinstance(obj, h5py.Group):
                nested = _find_series_leaf(obj)
                if nested[2] is not None and rate is None:
                    rate = nested[2]
                if nested[1] is not None and data_ds is None:
                    data_path, data_ds, _ = nested
    return data_path, data_ds, rate


def _inspect_intervals_h5py(intervals: h5py.Group) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for name in sorted(intervals.keys()):
        grp = intervals[name]
        if not isinstance(grp, h5py.Group):
            continue
        columns: list[dict[str, Any]] = []
        n_rows = None
        if "start_time" in grp and isinstance(grp["start_time"], h5py.Dataset):
            n_rows = int(grp["start_time"].shape[0])
        for col_name in sorted(grp.keys()):
            ds = grp[col_name]
            if not isinstance(ds, h5py.Dataset):
                continue
            columns.append(
                {
                    "name": col_name,
                    "dtype": str(ds.dtype),
                    "shape": list(ds.shape),
                    "sample_values": _sample_column(ds),
                }
            )
        tables.append(
            {
                "name": name,
                "path": f"/intervals/{name}",
                "n_rows": n_rows,
                "columns": columns,
            }
        )
    return tables


def _inspect_acquisitions_h5py(acquisition: h5py.Group) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in sorted(acquisition.keys()):
        obj = acquisition[name]
        if not isinstance(obj, h5py.Group):
            continue
        ndt = _ndt(obj)
        data_path, data_ds, rate = _find_series_leaf(obj)
        entry: dict[str, Any] = {
            "name": name,
            "path": f"/acquisition/{name}",
            "neurodata_type": ndt,
            "packaging": "lfp_wrapped" if ndt == "LFP" else "direct",
        }
        if data_path is not None:
            entry["data_path"] = f"/acquisition/{name}/{data_path}"
        if data_ds is not None:
            entry["data_shape"] = list(data_ds.shape)
            entry["data_dtype"] = str(data_ds.dtype)
            if len(data_ds.shape) == 2:
                entry["layout"] = "time_by_channel" if data_ds.shape[0] >= data_ds.shape[1] else "channel_by_time"
        if rate is not None:
            entry["rate_hz"] = rate
        out.append(entry)
    return out


def _inspect_electrodes_h5py(electrodes: h5py.Group) -> dict[str, Any]:
    columns = []
    n_rows = None
    if "id" in electrodes:
        n_rows = int(electrodes["id"].shape[0])
    for col_name in sorted(electrodes.keys()):
        ds = electrodes[col_name]
        if isinstance(ds, h5py.Dataset):
            columns.append({"name": col_name, "dtype": str(ds.dtype)})
    return {"n_rows": n_rows, "columns": columns}


def _inspect_units_h5py(units: h5py.Group) -> dict[str, Any]:
    columns = []
    n_rows = None
    if "id" in units:
        n_rows = int(units["id"].shape[0])
    for col_name in sorted(units.keys()):
        ds = units[col_name]
        if isinstance(ds, h5py.Dataset):
            columns.append({"name": col_name, "dtype": str(ds.dtype)})
    return {
        "n_rows": n_rows,
        "columns": columns,
        "has_spike_times": "spike_times" in units,
    }


def _session_from_pynwb(nwb: NWBFile) -> dict[str, Any]:
    return {
        "identifier": str(nwb.identifier) if nwb.identifier else "",
        "session_description": str(nwb.session_description) if nwb.session_description else "",
        "session_start_time": (
            nwb.session_start_time.isoformat() if nwb.session_start_time else ""
        ),
    }


def inspect(path_or_nwb: InspectInput) -> dict[str, Any]:
    """Return structured metadata about an NWB file or in-memory NWB object.

    Discovery only: lists acquisitions, electrodes, units, and **all** interval
    tables with columns and sample values. Does not select a default event table.
    """
    if isinstance(path_or_nwb, NWBFile):
        nwb = path_or_nwb
        session = _session_from_pynwb(nwb)
        interval_tables: list[dict[str, Any]] = []
        if nwb.intervals:
            for name in sorted(nwb.intervals.keys()):
                df = nwb.intervals[name].to_dataframe()
                columns = []
                for col in df.columns:
                    sample = df[col].head(_MAX_SAMPLES).tolist()
                    columns.append(
                        {
                            "name": str(col),
                            "dtype": str(df[col].dtype),
                            "sample_values": sample,
                        }
                    )
                interval_tables.append(
                    {
                        "name": name,
                        "path": f"/intervals/{name}",
                        "n_rows": len(df),
                        "columns": columns,
                    }
                )
        acquisitions: list[dict[str, Any]] = []
        for name, obj in sorted(nwb.acquisition.items()):
            ndt = getattr(obj, "neurodata_type", type(obj).__name__)
            packaging = "lfp_wrapped" if ndt == "LFP" else "direct"
            series = obj
            if ndt == "LFP":
                series = next(iter(obj.electrical_series.values()))
            entry: dict[str, Any] = {
                "name": name,
                "path": f"/acquisition/{name}",
                "neurodata_type": ndt,
                "packaging": packaging,
            }
            if hasattr(series, "data") and series.data is not None:
                shape = series.data.shape
                entry["data_shape"] = list(shape)
                entry["data_dtype"] = str(series.data.dtype)
            rate = getattr(series, "rate", None)
            if rate is not None and not (isinstance(rate, float) and np.isnan(rate)):
                entry["rate_hz"] = float(rate)
            acquisitions.append(entry)
        electrodes = {"n_rows": len(nwb.electrodes) if nwb.electrodes is not None else 0}
        if nwb.electrodes is not None:
            elec_df = nwb.electrodes.to_dataframe()
            electrodes["columns"] = [
                {"name": str(c), "dtype": str(elec_df[c].dtype)} for c in elec_df.columns
            ]
        units = {"n_rows": len(nwb.units) if nwb.units is not None else 0}
        if nwb.units is not None:
            units["has_spike_times"] = "spike_times" in nwb.units.colnames
            units_df = nwb.units.to_dataframe()
            units["columns"] = [
                {"name": str(c), "dtype": str(units_df[c].dtype)} for c in units_df.columns
            ]
        return {
            "session": session,
            "acquisitions": acquisitions,
            "electrodes": electrodes,
            "units": units,
            "interval_tables": interval_tables,
            "time_unit": "seconds",
        }

    path = Path(path_or_nwb)
    if not path.exists():
        raise FileNotFoundError(f"NWB file not found: {path}")

    with nwb_read_io(str(path), load_namespaces=True) as io:
        nwb = io.read()
        session = _session_from_pynwb(nwb)

    with h5py.File(path, "r") as handle:
        acquisitions = (
            _inspect_acquisitions_h5py(handle["acquisition"])
            if "acquisition" in handle
            else []
        )
        electrodes = (
            _inspect_electrodes_h5py(handle["general/extracellular_ephys/electrodes"])
            if handle.get("general/extracellular_ephys/electrodes") is not None
            else {"n_rows": 0, "columns": []}
        )
        units = (
            _inspect_units_h5py(handle["units"])
            if "units" in handle
            else {"n_rows": 0, "columns": [], "has_spike_times": False}
        )
        interval_tables = (
            _inspect_intervals_h5py(handle["intervals"]) if "intervals" in handle else []
        )

    return {
        "session": session,
        "acquisitions": acquisitions,
        "electrodes": electrodes,
        "units": units,
        "interval_tables": interval_tables,
        "time_unit": "seconds",
    }
