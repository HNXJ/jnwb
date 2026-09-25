"""Structured NWB file discovery for jnwb."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from pynwb import NWBFile

from jnwb.nwb_io import (
    ContainerTypeContradictionWarning,
    NWBInput,
    _with_nwb,
    nwb_read_io,
)

#: Historical spelling of `NWBInput`; this module's entry points are annotated with it.
InspectInput = NWBInput

_MAX_SAMPLES = 5


class NWBInspectError(Exception):
    """Base for every error raised while addressing an NWB file's contents.

    The four classes below were independent, and one of them inherited `IndexError`
    while its three siblings inherited `Exception`, so no single `except` clause caught
    them. They keep their existing bases, so `except IndexError` around
    `ChannelIndexError` still works.
    """


class AmbiguousLayoutError(NWBInspectError):
    """The channel axis of a 2-D continuous series cannot be determined.

    Raised when neither dimension of the data matches the series' electrode count, or
    when both do. Guessing here returns a slice taken across channels at one instant as
    though it were one channel's time course.
    """


class AmbiguousAcquisitionError(NWBInspectError):
    """Several acquisitions are present and ``name`` was not specified."""


class AcquisitionNotFoundError(NWBInspectError):
    """The requested acquisition does not exist."""


class ChannelIndexError(NWBInspectError, IndexError):
    """The requested channel index is out of range for the continuous series."""


class UnitNotFoundError(NWBInspectError):
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


def _series_rate(group: h5py.Group) -> float | None:
    """Sampling rate declared by one series group, in Hz."""
    st = group.get("starting_time")
    if st is not None and "rate" in getattr(st, "attrs", {}):
        return float(st.attrs["rate"])
    rate = group.get("rate")
    if isinstance(rate, h5py.Dataset):
        return float(rate[()])
    return None


def _series_members(group: h5py.Group) -> list[tuple[str | None, str, h5py.Dataset, float | None]]:
    """Every continuous series directly under one container, as
    ``(series_name, data_relpath, data_dataset, rate_hz)``.

    The predecessor walked the whole subtree with ``visititems``, taking the first
    ``data`` leaf and the first ``rate`` leaf **independently**. On an `LFP` container
    holding `lfp_alpha` at 1000 Hz and `lfp_beta` at 500 Hz it reported `lfp_alpha`'s
    shape and path beside `lfp_beta`'s rate -- a sampling rate that belonged to a
    different array. Here ``data`` and ``rate`` always come from the same group, and a
    container holding several series returns several members rather than one blend of
    them.

    ``series_name`` is ``None`` for a series that is itself the container (a direct
    `ElectricalSeries`), and the wrapped name otherwise.
    """
    direct = group.get("data")
    if isinstance(direct, h5py.Dataset):
        return [(None, "data", direct, _series_rate(group))]
    members: list[tuple[str | None, str, h5py.Dataset, float | None]] = []
    for name in sorted(group.keys()):
        child = group[name]
        if not isinstance(child, h5py.Group):
            continue
        for sub_name, rel, ds, rate in _series_members(child):
            members.append((name if sub_name is None else f"{name}/{sub_name}",
                            f"{name}/{rel}", ds, rate))
    return members


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


TIME_BY_CHANNEL = "time_by_channel"
CHANNEL_BY_TIME = "channel_by_time"
AMBIGUOUS_LAYOUT = "ambiguous"


def _series_group(container: h5py.Group, data_relpath: str) -> h5py.Group | None:
    """The group that directly holds one series' `data`, resolved from its relpath.

    `_series_members` reports where each `data` leaf sits but not the group owning it, and the
    owner is what carries that series' own `neurodata_type`: the members of an `LFP` container
    are `ElectricalSeries` and the container is not. Resolving the path here keeps
    `_series_members`' return shape untouched.
    """
    node: Any = container
    for part in data_relpath.split("/")[:-1]:
        node = node.get(part)
        if not isinstance(node, h5py.Group):
            return None
    return node


def _h5_channel_count(group: h5py.Group, data_relpath: str | None) -> int | None:
    """Length of the electrode region sitting beside `data`, or ``None``.

    The series' own region is the arbiter, not the whole electrode table: a series may
    cover a subset of a 384-channel probe.
    """
    if data_relpath is None:
        return None
    node = _series_group(group, data_relpath)
    if node is None:
        return None
    region = node.get("electrodes")
    if region is None:
        return None
    try:
        n = len(region)
    except TypeError:
        return None
    return int(n) or None


def _pynwb_channel_count(series: Any) -> int | None:
    """The same arbiter on the pynwb path: ``len(series.electrodes)``."""
    region = getattr(series, "electrodes", None)
    if region is None:
        return None
    try:
        n = len(region)
    except TypeError:
        return None
    return int(n) or None


#: Series types that carry an electrode region. The NWB schema puts time on the first axis of
#: every TimeSeries; only these types have an electrode count that can contradict it, and a
#: file of theirs that lacks the region falls back to the shape guess. Every other typed series
#: is read time-first, since the shape guess would read five samples of ten values as five
#: channels.
_ELECTRODE_TYPES = frozenset({"ElectricalSeries", "SpikeEventSeries"})


def _resolve_layout(
    shape: Any, n_channels: int | None, neurodata_type: str | None = None
) -> tuple[str, str]:
    """Decide which axis of a 2-D continuous series holds channels.

    This was ``shape[0] >= shape[1]``, which never consulted the electrode count.
    A 64-channel x 1000-sample recording came out ``channel_by_time`` only by accident of
    being wider than tall, and a 50-sample x 100-channel one came out ``channel_by_time``
    while the same ``inspect`` dict carried 100 electrodes.

    Returns ``(layout, basis)``. ``basis`` is internal and says whether the answer came
    from the electrode count or from the shape guess that is all there is without one.
    """
    rows, cols = int(shape[0]), int(shape[1])
    if n_channels:
        n = int(n_channels)
        if cols == n and rows != n:
            return TIME_BY_CHANNEL, "electrode_count"
        if rows == n and cols != n:
            return CHANNEL_BY_TIME, "electrode_count"
        # Both sides match (a square array) or neither does. Guessing here is exactly how
        # a slice across channels gets returned as a channel's time course.
        return AMBIGUOUS_LAYOUT, "electrode_count"
    if neurodata_type is not None and neurodata_type not in _ELECTRODE_TYPES:
        return TIME_BY_CHANNEL, "schema"
    # Nothing to arbitrate with. The shape heuristic is the only answer available.
    return (TIME_BY_CHANNEL if rows >= cols else CHANNEL_BY_TIME), "shape"


CONTINUOUS_KEYS = (
    "name", "path", "neurodata_type", "packaging", "series",
    "data_path", "data_shape", "data_dtype", "layout", "rate_hz", "starting_time",
)


def _starting_time_s(series: Any) -> float | None:
    """A series' ``starting_time`` in seconds, or ``None`` when it has none (timestamps)."""
    start = getattr(series, "starting_time", None)
    if start is None:
        return None
    start = float(start)
    return None if np.isnan(start) else start

#: Data units the NWB core schema pins to a declared type. These are *fixed values* in the
#: standard, not defaults -- ``ElectricalSeries.data.unit`` carries ``value: volts``, which is
#: why a stored unit that differs contradicts the declaration rather than merely overriding it.
#: It is also why the file is the only place the disagreement survives: pynwb substitutes the
#: fixed value on read, so an `ElectricalSeries` whose file stores ``n.a.`` still reports
#: ``volts`` through the object model.
_SCHEMA_FIXED_DATA_UNIT = {"ElectricalSeries": "volts"}


def _series_unit(data_ds: h5py.Dataset) -> str | None:
    """The `unit` recorded beside one series' `data`, or ``None`` when it carries none."""
    raw = data_ds.attrs.get("unit")
    return None if raw is None else _decode(raw)


def _type_contradictions(
    container: h5py.Group,
    members: list[tuple[str | None, str, h5py.Dataset, float | None]],
) -> list[str]:
    """One phrase per series whose own declared type disagrees with what it stores.

    Two shapes are reported and nothing else is:

    * a declared type the schema fixes a data unit for, where the stored unit is a different
      one -- the container says extracellular voltage and holds something that is not;
    * no declared type at all, where nothing in the file says what the series holds.

    A series carrying no `unit` is deliberately not reported. An absent unit contradicts
    nothing, and a warning that also fires on every merely incomplete file carries no more
    information than one that fires on all of them.
    """
    findings: list[str] = []
    for series_name, relpath, data_ds, _rate in members:
        owner = _series_group(container, relpath)
        if owner is None:
            continue
        label = series_name or "data"
        ndt = _ndt(owner)
        unit = _series_unit(data_ds)
        if ndt is None:
            stored = f"unit {unit!r}" if unit is not None else "no unit"
            findings.append(
                f"{label} declares no neurodata_type, so nothing in the file says what signal "
                f"class it holds; it stores {stored} with dtype {data_ds.dtype}"
            )
            continue
        fixed = _SCHEMA_FIXED_DATA_UNIT.get(ndt)
        if fixed is not None and unit is not None and unit != fixed:
            findings.append(
                f"{label} declares neurodata_type {ndt!r}, for which the NWB schema fixes the "
                f"data unit to {fixed!r}, but it stores unit {unit!r} with dtype "
                f"{data_ds.dtype}"
            )
    return findings


def _warn_type_contradiction(
    container: h5py.Group,
    path: str,
    members: list[tuple[str | None, str, h5py.Dataset, float | None]],
) -> None:
    """Report, once per container, every series in it whose declared type disagrees.

    Warn, never refuse. The warning is the whole signal; no jnwb
    operation branches on it and the container is read exactly as it would have been.
    """
    findings = _type_contradictions(container, members)
    if not findings:
        return
    warnings.warn(
        f"{path}: declared type disagrees with what the file stores. "
        + "; ".join(findings)
        + ". jnwb reads the container unchanged and nothing downstream branches on this "
        "warning; the typing is the file's to correct.",
        ContainerTypeContradictionWarning,
        stacklevel=2,
    )


def _continuous_entry_h5py(group: h5py.Group, name: str, path: str) -> dict[str, Any]:
    """One `processing_continuous`/`acquisitions` entry, from the file.

    Every key in `CONTINUOUS_KEYS` is always present, `None` where it is not
    known, so `inspect` reports one schema rather than a key set that depends on what
    the file happened to contain.
    """
    ndt = _ndt(group)
    members = _series_members(group)
    # Report a container whose declared type contradicts its contents, and proceed.
    # This sits on the h5py path because it is the only one that can witness the
    # contradiction: pynwb substitutes the schema's fixed `unit` on read, and drops an
    # untyped container from the object model entirely.
    _warn_type_contradiction(group, path, members)
    entry: dict[str, Any] = {
        "name": name,
        "path": path,
        "neurodata_type": ndt,
        "packaging": "lfp_wrapped" if ndt == "LFP" else "direct",
        "series": [m[0] for m in members if m[0] is not None] or None,
        "data_path": None,
        "data_shape": None,
        "data_dtype": None,
        "layout": None,
        "rate_hz": None,
        "starting_time": None,
    }
    # Several series under one container is a question, not an answer: which one is "the"
    # rate, shape and path? The caller names the series it wants.
    if len(members) == 1:
        _, relpath, data_ds, rate = members[0]
        entry["data_path"] = f"{path}/{relpath}"
        entry["data_shape"] = list(data_ds.shape)
        entry["data_dtype"] = str(data_ds.dtype)
        node = _series_group(group, relpath)
        if len(data_ds.shape) == 2:
            entry["layout"] = _resolve_layout(
                data_ds.shape, _h5_channel_count(group, relpath),
                _ndt(node) if node is not None else None)[0]
        entry["rate_hz"] = rate
        st = node.get("starting_time") if node is not None else None
        if isinstance(st, h5py.Dataset) and st.shape == ():
            start = float(st[()])
            entry["starting_time"] = None if np.isnan(start) else start
    return entry


def _inspect_acquisitions_h5py(acquisition: h5py.Group) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in sorted(acquisition.keys()):
        obj = acquisition[name]
        if not isinstance(obj, h5py.Group):
            continue
        out.append(_continuous_entry_h5py(obj, name, f"/acquisition/{name}"))
    return out


def _inspect_processing_continuous_h5py(handle: h5py.File) -> list[dict[str, Any]]:
    if "processing" not in handle:
        return []
    processing = handle["processing"]
    out: list[dict[str, Any]] = []
    for mod_name in sorted(processing.keys()):
        mod = processing[mod_name]
        if not isinstance(mod, h5py.Group):
            continue
        for cname in sorted(mod.keys()):
            obj = mod[cname]
            if not isinstance(obj, h5py.Group):
                continue
            if not _series_members(obj):
                continue
            entry = _continuous_entry_h5py(
                obj, cname, f"/processing/{mod_name}/{cname}")
            entry["module"] = mod_name
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


#: Marks a bare series name that more than one processing container holds.
_SHARED_BARE_NAME = object()


def _find_processing_series(nwb: NWBFile) -> tuple[dict[str, Any], list[str]]:
    """Return (lookup_dict, top_level_names) for continuous series in nwb.processing."""
    found: dict[str, Any] = {}
    top_level: list[str] = []
    bare_series: dict[str, list[Any]] = {}
    if not nwb.processing:
        return found, top_level
    for mod_name, mod in nwb.processing.items():
        interfaces = getattr(mod, "data_interfaces", {})
        for cname, obj in interfaces.items():
            ndt = getattr(obj, "neurodata_type", type(obj).__name__)
            if ndt == "LFP" and hasattr(obj, "electrical_series"):
                found[cname] = obj
                found[f"{mod_name}/{cname}"] = obj
                if cname not in top_level:
                    top_level.append(cname)
                for sname, s in obj.electrical_series.items():
                    bare_series.setdefault(sname, []).append(s)
                    if sname not in found:
                        found[sname] = s
                    found[f"{mod_name}/{cname}/{sname}"] = s
            elif hasattr(obj, "data") and (hasattr(obj, "rate") or hasattr(obj, "starting_time")):
                found[cname] = obj
                found[f"{mod_name}/{cname}"] = obj
                if cname not in top_level:
                    top_level.append(cname)
    # A bare series name two containers share is marked rather than resolved to whichever
    # container came first; `resolve_acquisition` refuses it and names the qualified forms.
    for sname, held in bare_series.items():
        if len(held) > 1 and any(found.get(sname) is s for s in held):
            found[sname] = _SHARED_BARE_NAME
    return found, top_level


# Containers that wrap their series, and the attribute that holds them. `LFP` and
# `FilteredEphys` hold ElectricalSeries; the behavior containers hold SpatialSeries or
# TimeSeries the same way, so eye, pupil and position channels unwrap like LFP.
_WRAPPED_SERIES_ATTR = {
    "LFP": "electrical_series",
    "FilteredEphys": "electrical_series",
    "EyeTracking": "spatial_series",
    "Position": "spatial_series",
    "CompassDirection": "spatial_series",
    "PupilTracking": "time_series",
    "BehavioralTimeSeries": "time_series",
}


def _wrapped_series(obj: Any) -> Any:
    """The series mapping a container holds: its `_WRAPPED_SERIES_ATTR` attribute, else
    `electrical_series` (any other type exposing one, as before), else ``None``."""
    ndt = getattr(obj, "neurodata_type", type(obj).__name__)
    if ndt in _WRAPPED_SERIES_ATTR:
        return getattr(obj, _WRAPPED_SERIES_ATTR[ndt], None)
    return getattr(obj, "electrical_series", None)


def _acquisition_nested_series(nwb: NWBFile) -> dict[str, list[Any]]:
    """Series held inside ``/acquisition`` containers (``LFP``, ``FilteredEphys`` and the
    behavior containers in ``_WRAPPED_SERIES_ATTR``).

    Keyed by the bare series name and by ``container/series``. A bare name held by two
    containers maps to both, so the caller can refuse it rather than pick one.
    """
    found: dict[str, list[Any]] = {}
    for cname, obj in (nwb.acquisition or {}).items():
        wrapped = _wrapped_series(obj)
        if not wrapped or not hasattr(wrapped, "items"):
            continue
        for sname, series in wrapped.items():
            found.setdefault(sname, []).append(series)
            found.setdefault(f"{cname}/{sname}", []).append(series)
    return found


def resolve_acquisition(path_or_nwb: InspectInput, name: str | None = None) -> str:
    """Resolve an acquisition or processing continuous series name.

    When ``name`` is omitted:
    - use the sole continuous series when exactly one exists (in acquisitions or processing modules);
    - otherwise raise :class:`AmbiguousAcquisitionError`.
    """
    def _resolve(nwb: NWBFile) -> str:
        acq_names = sorted(nwb.acquisition.keys()) if nwb.acquisition else []
        proc_dict, proc_top = _find_processing_series(nwb)

        all_available = sorted(set(acq_names) | set(proc_top))
        if not all_available:
            raise AcquisitionNotFoundError("No acquisitions or processing continuous series found in NWB file")

        if name is not None:
            in_acquisition = bool(nwb.acquisition) and name in nwb.acquisition
            in_processing = name in proc_dict
            nested = _acquisition_nested_series(nwb)
            if name in nested and not in_acquisition:
                qualified = sorted(k for k in nested if "/" in k and k.rsplit("/", 1)[-1] == name)
                if len(nested[name]) > 1 or in_processing:
                    raise AmbiguousAcquisitionError(
                        f"'{name}' names a series in more than one container: "
                        f"{qualified + (['a processing series'] if in_processing else [])}. "
                        f"Pass the qualified name container/series."
                    )
                return name
            # Both used to be true happily, and acquisition won by the order of
            # these two `if`s. Nothing said so, and the two objects are different data.
            if in_acquisition and in_processing:
                qualified = sorted(
                    k for k in proc_dict if "/" in k and k.rsplit("/", 1)[-1] == name
                )
                raise AmbiguousAcquisitionError(
                    f"'{name}' names both /acquisition/{name} and "
                    f"{qualified or ['a processing series']}. "
                    f"Pass the qualified processing name to mean the latter."
                )
            if in_processing and proc_dict[name] is _SHARED_BARE_NAME:
                qualified = sorted(
                    k for k in proc_dict if "/" in k and k.rsplit("/", 1)[-1] == name
                )
                raise AmbiguousAcquisitionError(
                    f"'{name}' names a series in more than one processing container: "
                    f"{qualified}. Pass the qualified name."
                )
            if in_acquisition or in_processing:
                return name
            nested_names = sorted(k for k in nested if "/" in k)
            raise AcquisitionNotFoundError(
                f"Series '{name}' not found. Available: {all_available}"
                + (f"; series inside containers: {nested_names}" if nested_names else "")
            )

        if len(all_available) == 1:
            return all_available[0]
        raise AmbiguousAcquisitionError(
            f"Several continuous series present: {all_available}. Pass name=<series> explicitly."
        )

    return _with_nwb(path_or_nwb, _resolve)


def _electrical_series_from_acquisition(acq: Any, name: str | None = None):
    """Unwrap a wrapping container (`LFP`, `FilteredEphys`, or a behavior container such
    as `EyeTracking`) to the series it holds; any other object is returned as is.

    This was ``next(iter(...))``, so a container holding two series silently
    returned whichever came first, while `inspect` reported a third answer built from
    both. A container that holds more than one series is a question for the caller.
    """
    ndt = getattr(acq, "neurodata_type", type(acq).__name__)
    attr = _WRAPPED_SERIES_ATTR.get(ndt)
    if attr is None:
        return acq
    wrapped = getattr(acq, attr, None) or {}
    label = name or getattr(acq, "name", ndt)
    kind = "electrical series" if attr == "electrical_series" else "series"
    if not wrapped:
        raise AcquisitionNotFoundError(
            f"Container '{label}' holds no {kind}"
        )
    if len(wrapped) > 1:
        raise AmbiguousAcquisitionError(
            f"Container '{label}' wraps {len(wrapped)} {kind}: "
            f"{sorted(wrapped)}. Pass name=<series> explicitly."
        )
    return next(iter(wrapped.values()))


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


def _warn_if_declared_unit_contradicts_storage(series: Any, acq_name: str) -> None:
    """Warn when the type this series declares fixes a data unit the file does not store.

    `inspect` warns where the contradiction is *declared*; this is where the harm *lands*.
    An int16 spike container declared `ElectricalSeries` is exactly the case where applying
    the volts conversion is wrong, and this function returned the converted array and warned
    nothing.

    The object model cannot witness the disagreement: pynwb substitutes the schema's fixed
    value on read, so `series.unit` reads ``'volts'`` for a file that stores ``'n.a.'`` --
    measured. What *is* reachable is the unit recorded beside `data`, because a lazily read
    series leaves `series.data` as a live `h5py.Dataset` carrying its own attrs. No second
    open is needed, which is cheaper than this defect was first recorded as costing.

    For an in-memory file never written to disk there is no stored unit and nothing to
    contradict, so `data` has no attrs and this returns silently.
    """
    ndt = getattr(series, "neurodata_type", type(series).__name__)
    fixed = _SCHEMA_FIXED_DATA_UNIT.get(ndt)
    if fixed is None:
        return
    data = getattr(series, "data", None)
    attrs = getattr(data, "attrs", None)
    if attrs is None:
        return
    try:
        stored = attrs.get("unit")
    except Exception:
        return
    if stored is None:
        return
    stored = _decode(stored)
    if stored == fixed:
        return
    conversion = getattr(series, "conversion", None)
    dtype = getattr(data, "dtype", None)
    warnings.warn(
        f"acquisition_channel: series '{acq_name}' declares neurodata_type {ndt!r}, for which "
        f"the NWB schema fixes the data unit to {fixed!r}, but the file stores unit "
        f"{stored!r} (dtype {dtype}). The returned array has had conversion="
        f"{conversion!r} applied and is being presented as {fixed}, which is wrong if the "
        f"series does not hold extracellular voltage. `series.unit` cannot show you this: "
        f"pynwb substitutes the schema's fixed value on read.",
        RuntimeWarning,
        stacklevel=3,
    )


def acquisition_channel(
    path_or_nwb: InspectInput,
    name: str | None = None,
    channel: int = 0,
) -> tuple[np.ndarray, float]:
    r"""Return one continuous acquisition channel and its sampling rate in Hz.

    Resolves direct :class:`~pynwb.ecephys.ElectricalSeries` objects and
    ``LFP`` containers with nested electrical series from both
    ``/acquisition`` and processing modules (e.g. ``processing/ecephys/LFP``).
    In ``/acquisition``, behavior containers (``EyeTracking``, ``PupilTracking``,
    ``BehavioralTimeSeries``, ``Position``, ``CompassDirection``) and ``FilteredEphys``
    unwrap to the series they hold the same way.

    Parameters
    ----------
    path_or_nwb:
        Path to an NWB file or an in-memory :class:`~pynwb.NWBFile`.
    name:
        Name of the continuous series or container. When omitted, resolves the
        sole available series if unique.
    channel:
        Zero-based channel index, in the series' own channel axis. That axis is read
        from the series' electrode region, so ``channel=k`` is the same channel whether
        the array is stored time-by-channel or channel-by-time.
        Raises :class:`ChannelIndexError` if channel is out of range, and
        :class:`AmbiguousLayoutError` when the electrode count matches neither dimension
        of a 2-D array or matches both. For 1D series, channel must be 0.

    Returns
    -------
    data:
        1D ``float64`` array of physically scaled samples according to the NWB
        specification (:math:`x_{\mathrm{physical}} = \mathrm{conversion} \cdot c_k \cdot x_{\mathrm{stored}} + \mathrm{offset}`,
        where :math:`c_k` is the series' ``channel_conversion`` entry for the channel, 1 when absent).
        A ``channel_conversion`` whose length is not the channel count raises ``ValueError``.
        Units match the series ``unit`` attribute (typically ``"volts"`` for
        :class:`~pynwb.ecephys.ElectricalSeries`).
    rate_hz:
        Sampling rate in Hz.

    Warns
    -----
    UserWarning
        When the series' ``starting_time`` is not 0. Sample 0 is at ``starting_time`` in
        session time, so subtract it from session-time event onsets before
        :func:`epoch_continuous`. :func:`inspect` reports it per series as ``starting_time``.
    """

    def _read(nwb: NWBFile) -> tuple[np.ndarray, float]:
        acq_name = resolve_acquisition(nwb, name)
        nested = _acquisition_nested_series(nwb)
        if nwb.acquisition and acq_name in nwb.acquisition:
            container = nwb.acquisition[acq_name]
        elif acq_name in nested:
            container = nested[acq_name][0]
        else:
            proc_dict, _ = _find_processing_series(nwb)
            container = proc_dict[acq_name]
        series = _electrical_series_from_acquisition(container, acq_name)
        if not hasattr(series, "data") or series.data is None:
            raise AcquisitionNotFoundError(
                f"Series '{acq_name}' has no readable data array"
            )

        # Warned before the array is read and scaled, so the caller sees the contradiction
        # even if reading the slice then fails for an unrelated reason.
        _warn_if_declared_unit_contradicts_storage(series, acq_name)

        shape = series.data.shape
        if len(shape) == 1:
            if channel != 0:
                raise ChannelIndexError(
                    f"Channel index {channel} out of range for 1D series '{acq_name}' with shape {shape}"
                )
            data = np.asarray(series.data[:], dtype=np.float64)
        elif len(shape) == 2:
            # This sliced axis 1 unconditionally and bounds-checked shape[1],
            # never consulting the layout its own sibling `inspect` reports. On a
            # channel-major (64, 1000) series with 64 electrodes, channel=0 returned
            # data[:, 0] -- 64 samples taken across channels at one instant -- as a
            # 1000 Hz channel trace, channel=999 returned another such slice, and
            # channel=1000 raised "out of range ... with 1000 channels" for a file
            # that has 64 of them.
            n_channels = _pynwb_channel_count(series)
            layout, basis = _resolve_layout(
                shape, n_channels, getattr(series, "neurodata_type", None))
            if layout == AMBIGUOUS_LAYOUT:
                raise AmbiguousLayoutError(
                    f"Cannot tell which axis of series '{acq_name}' holds channels: "
                    f"shape {tuple(shape)} against {n_channels} electrodes, so neither "
                    f"dimension matches or both do. Guessing would return a slice "
                    f"across channels as a channel's time course."
                )
            n = shape[1] if layout == TIME_BY_CHANNEL else shape[0]
            if channel < 0 or channel >= n:
                raise ChannelIndexError(
                    f"Channel index {channel} out of range for series '{acq_name}' "
                    f"with {n} channels (layout {layout}, decided by {basis})"
                )
            if layout == TIME_BY_CHANNEL:
                data = np.asarray(series.data[:, channel], dtype=np.float64)
            else:
                data = np.asarray(series.data[channel, :], dtype=np.float64)
        else:
            raise ValueError(
                f"Unsupported series data shape {shape} for '{acq_name}' (expected 1D or 2D)"
            )

        conversion = getattr(series, "conversion", None)
        offset = getattr(series, "offset", None)
        if conversion is not None and not (isinstance(conversion, float) and np.isnan(conversion)):
            c_val = float(conversion)
            if c_val != 1.0:
                data = data * c_val
        # `channel_conversion` is the per-channel factor of an ElectricalSeries, applied after
        # `conversion` and before `offset`; indexed on the channel axis, like `channel`.
        channel_conversion = getattr(series, "channel_conversion", None)
        if channel_conversion is not None:
            factors = np.asarray(channel_conversion[:], dtype=np.float64).ravel()
            n_expected = 1 if len(shape) == 1 else n
            if factors.size != n_expected:
                raise ValueError(
                    f"Series '{acq_name}' stores {factors.size} channel_conversion factors "
                    f"for {n_expected} channels; the physical value of channel {channel} "
                    f"cannot be computed"
                )
            if factors[channel] != 1.0:
                data = data * factors[channel]
        if offset is not None and not (isinstance(offset, float) and np.isnan(offset)):
            o_val = float(offset)
            if o_val != 0.0:
                data = data + o_val

        rate = getattr(series, "rate", None)
        if rate is None or (isinstance(rate, float) and np.isnan(rate)):
            raise AcquisitionNotFoundError(
                f"Series '{acq_name}' has no constant sampling rate"
            )
        start = _starting_time_s(series)
        if start is not None and start != 0.0:
            warnings.warn(
                f"acquisition_channel: series '{acq_name}' has starting_time={start!r} s, so "
                f"sample 0 of the returned array is at {start!r} s in session time. Event "
                f"times from the file's interval tables are session times: subtract "
                f"{start!r} s from them before epoch_continuous, or every epoch is misaligned "
                f"by {start!r} s.",
                UserWarning,
                stacklevel=3,
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


def _continuous_entry_pynwb(obj: Any, name: str, path: str) -> dict[str, Any]:
    """The `CONTINUOUS_KEYS` entry for one container, from the object model.

    Same keys, same meanings and the same refusal as `_continuous_entry_h5py`, so the
    two call forms of `inspect` do not describe the same file with two vocabularies.
    """
    ndt = getattr(obj, "neurodata_type", type(obj).__name__)
    entry: dict[str, Any] = {
        "name": name,
        "path": path,
        "neurodata_type": ndt,
        "packaging": "lfp_wrapped" if ndt == "LFP" else "direct",
        "series": None,
        "data_path": None,
        "data_shape": None,
        "data_dtype": None,
        "layout": None,
        "rate_hz": None,
        "starting_time": None,
    }
    # Every wrapping container unwraps, as the file walk does, not only `LFP`.
    held = _wrapped_series(obj)
    if held is not None and hasattr(held, "items"):
        wrapped = dict(held)
        entry["series"] = sorted(wrapped) or None
        if len(wrapped) != 1:
            return entry
        series_name = next(iter(sorted(wrapped)))
        series = wrapped[series_name]
        relpath = f"{series_name}/data"
    else:
        series = obj
        relpath = "data"

    data = getattr(series, "data", None)
    if data is None:
        return entry
    shape = getattr(data, "shape", None)
    if shape is None:
        shape = np.shape(data)
    dtype = getattr(data, "dtype", None)
    if dtype is None:
        dtype = np.asarray(data).dtype
    entry["data_path"] = f"{path}/{relpath}"
    entry["data_shape"] = list(shape)
    entry["data_dtype"] = str(dtype)
    if len(shape) == 2:
        entry["layout"] = _resolve_layout(
            shape, _pynwb_channel_count(series), getattr(series, "neurodata_type", None))[0]
    rate = getattr(series, "rate", None)
    if rate is not None and not (isinstance(rate, float) and np.isnan(rate)):
        entry["rate_hz"] = float(rate)
    entry["starting_time"] = _starting_time_s(series)
    return entry


def _table_columns_pynwb(table: Any, with_shape: bool, with_samples: bool) -> list[dict[str, Any]]:
    """Columns of a `DynamicTable`, including its `id` column, sorted by name.

    `id` is a column of every `DynamicTable`; `to_dataframe()` makes it the index, which
    is why the object form used to report one fewer column than the file form.
    """
    df = table.to_dataframe()
    series = {"id": df.index.to_series()}
    for col in df.columns:
        series[str(col)] = df[col]
    out: list[dict[str, Any]] = []
    for col_name in sorted(series):
        values = series[col_name]
        entry: dict[str, Any] = {"name": col_name, "dtype": str(values.dtype)}
        if with_shape:
            entry["shape"] = [len(values)]
        if with_samples:
            entry["sample_values"] = values.head(_MAX_SAMPLES).tolist()
        out.append(entry)
    return out


def _inspect_object(nwb: NWBFile) -> dict[str, Any]:
    """`inspect` for an NWB object with no file behind it.

    Produces the schema `_inspect_file` produces. The values it cannot know are the ones
    that exist only on disk -- a dtype chosen at write time, for instance -- and those
    come from the in-memory arrays instead.
    """
    # `nwb.intervals` is empty until the file is written and read back: in memory
    # `add_trial` populates `nwb.trials` and nothing else, so the object form used to
    # report no interval tables at all for a file that plainly has one.
    tables: dict[str, Any] = dict(nwb.intervals or {})
    for attr in ("trials", "epochs", "invalid_times"):
        table = getattr(nwb, attr, None)
        if table is not None and attr not in tables:
            tables[attr] = table

    interval_tables: list[dict[str, Any]] = []
    for name in sorted(tables):
        table = tables[name]
        interval_tables.append({
            "name": name,
            "path": f"/intervals/{name}",
            "n_rows": len(table),
            "columns": _table_columns_pynwb(table, with_shape=True, with_samples=True),
        })

    acquisitions = [
        _continuous_entry_pynwb(obj, name, f"/acquisition/{name}")
        for name, obj in sorted((nwb.acquisition or {}).items())
    ]

    processing_continuous: list[dict[str, Any]] = []
    for mod_name, mod in sorted((nwb.processing or {}).items()):
        for cname, obj in sorted(getattr(mod, "data_interfaces", {}).items()):
            entry = _continuous_entry_pynwb(
                obj, cname, f"/processing/{mod_name}/{cname}")
            if entry["data_path"] is None and entry["series"] is None:
                continue          # not a continuous series at all
            entry["module"] = mod_name
            processing_continuous.append(entry)

    if nwb.electrodes is not None:
        electrodes = {
            "n_rows": len(nwb.electrodes),
            "columns": _table_columns_pynwb(
                nwb.electrodes, with_shape=False, with_samples=False),
        }
    else:
        electrodes = {"n_rows": 0, "columns": []}

    if nwb.units is not None:
        units = {
            "n_rows": len(nwb.units),
            "columns": _table_columns_pynwb(
                nwb.units, with_shape=False, with_samples=False),
            "has_spike_times": "spike_times" in nwb.units.colnames,
        }
    else:
        units = {"n_rows": 0, "columns": [], "has_spike_times": False}

    return {
        "session": _session_from_pynwb(nwb),
        "acquisitions": acquisitions,
        "processing_continuous": processing_continuous,
        "electrodes": electrodes,
        "units": units,
        "interval_tables": interval_tables,
        "time_unit": "seconds",
    }


def _inspect_file(path: Path, nwb: NWBFile | None = None) -> dict[str, Any]:
    """`inspect` for a file on disk. `nwb`, when given, is an already-read handle on the
    same file, used for the session block so the file is not opened with pynwb twice."""
    if nwb is None:
        with nwb_read_io(str(path), load_namespaces=True) as io:
            session = _session_from_pynwb(io.read())
    else:
        session = _session_from_pynwb(nwb)

    with h5py.File(path, "r") as handle:
        acquisitions = (
            _inspect_acquisitions_h5py(handle["acquisition"])
            if "acquisition" in handle
            else []
        )
        processing_continuous = (
            _inspect_processing_continuous_h5py(handle)
            if "processing" in handle
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
        "processing_continuous": processing_continuous,
        "electrodes": electrodes,
        "units": units,
        "interval_tables": interval_tables,
        "time_unit": "seconds",
    }


def inspect(path_or_nwb: InspectInput) -> dict[str, Any]:
    """Return structured metadata about an NWB file or in-memory NWB object.

    Discovery only: lists acquisitions, electrodes, units, and **all** interval
    tables with columns and sample values. Does not select a default event table.

    Both call forms answer with one schema. They used to be two independent
    walks, so ``inspect(path)`` and ``inspect(nwb)`` reported different keys, different
    column lists and different dtypes for the same file. An `NWBFile` that was read from
    a file is now described by that file, which is what makes passing an open handle --
    the documented way to avoid reopening -- give the same answer as passing the path.
    An `NWBFile` with no file behind it is described from its arrays, in the same schema.
    """
    if isinstance(path_or_nwb, NWBFile):
        source = getattr(path_or_nwb, "container_source", None)
        if source:
            source_path = Path(str(source))
            if source_path.exists():
                return _inspect_file(source_path, nwb=path_or_nwb)
        return _inspect_object(path_or_nwb)

    path = Path(path_or_nwb)
    if not path.exists():
        raise FileNotFoundError(f"NWB file not found: {path}")
    return _inspect_file(path)
