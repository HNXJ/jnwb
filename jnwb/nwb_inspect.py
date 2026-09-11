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


class AmbiguousAcquisitionError(Exception):
    """Several acquisitions are present and ``name`` was not specified."""


class AcquisitionNotFoundError(Exception):
    """The requested acquisition does not exist."""


class UnitNotFoundError(Exception):
    """The requested units-table row does not exist."""


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


def _with_nwb(path_or_nwb: InspectInput, fn):
    if isinstance(path_or_nwb, NWBFile):
        return fn(path_or_nwb)
    path = Path(path_or_nwb)
    if not path.exists():
        raise FileNotFoundError(f"NWB file not found: {path}")
    with nwb_read_io(str(path), load_namespaces=True) as io:
        return fn(io.read())


def resolve_acquisition(nwb: NWBFile, name: str | None) -> str:
    """Resolve an acquisition name.

    When ``name`` is omitted, use the sole acquisition when exactly one exists;
    otherwise raise :class:`AmbiguousAcquisitionError`.
    """
    names = sorted(nwb.acquisition.keys()) if nwb.acquisition else []
    if not names:
        raise AcquisitionNotFoundError("No acquisitions found in NWB file")
    if name is not None:
        if name not in nwb.acquisition:
            raise AcquisitionNotFoundError(
                f"Acquisition '{name}' not found. Available: {names}"
            )
        return name
    if len(names) == 1:
        return names[0]
    raise AmbiguousAcquisitionError(
        f"Several acquisitions present: {names}. Pass name=<acquisition> explicitly."
    )


def _electrical_series_from_acquisition(acq: Any):
    ndt = getattr(acq, "neurodata_type", type(acq).__name__)
    if ndt == "LFP":
        return next(iter(acq.electrical_series.values()))
    return acq


def unit_spike_times(path_or_nwb: InspectInput, unit_index: int = 0) -> np.ndarray:
    """Return spike times (seconds) for one units-table row.

    Parameters
    ----------
    path_or_nwb:
        NWB path or in-memory :class:`pynwb.NWBFile`.
    unit_index:
        Row index in the units table (0-based).
    """

    def _read(nwb: NWBFile) -> np.ndarray:
        if nwb.units is None:
            raise UnitNotFoundError("NWB file has no units table")
        if unit_index < 0 or unit_index >= len(nwb.units):
            raise UnitNotFoundError(
                f"Unit index {unit_index} out of range for {len(nwb.units)} units"
            )
        if "spike_times" not in nwb.units.colnames:
            raise UnitNotFoundError("Units table has no spike_times column")
        return np.asarray(nwb.units["spike_times"][unit_index], dtype=np.float64)

    return _with_nwb(path_or_nwb, _read)


def acquisition_channel(
    path_or_nwb: InspectInput,
    name: str | None = None,
    channel: int = 0,
) -> tuple[np.ndarray, float]:
    """Return one continuous acquisition channel and its sampling rate in Hz.

    Resolves direct :class:`~pynwb.ecephys.ElectricalSeries` objects and
    ``LFP`` containers with nested electrical series (see :func:`inspect`).
    """

    def _read(nwb: NWBFile) -> tuple[np.ndarray, float]:
        acq_name = resolve_acquisition(nwb, name)
        series = _electrical_series_from_acquisition(nwb.acquisition[acq_name])
        if not hasattr(series, "data") or series.data is None:
            raise AcquisitionNotFoundError(
                f"Acquisition '{acq_name}' has no readable data array"
            )
        data = np.asarray(series.data[:, channel], dtype=np.float64)
        rate = getattr(series, "rate", None)
        if rate is None or (isinstance(rate, float) and np.isnan(rate)):
            raise AcquisitionNotFoundError(
                f"Acquisition '{acq_name}' has no constant sampling rate"
            )
        return data, float(rate)

    return _with_nwb(path_or_nwb, _read)


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
