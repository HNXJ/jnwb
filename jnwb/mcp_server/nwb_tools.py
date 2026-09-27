import h5py
from pathlib import Path
from typing import Dict, Any
from jnwb.nwb_inspect import (
    AMBIGUOUS_LAYOUT,
    _decode,
    _h5_channel_count,
    _ndt,
    _resolve_layout,
    _series_rate,
    inspect,
)
from jnwb.mcp_server.server import mcp

_LAYOUT_BASIS = {
    "electrode_count": "the series' electrode region",
    "schema": "the NWB schema, which puts time on axis 0 of this type",
}


def _scalar_attr(ds: h5py.Dataset, key: str) -> float | None:
    raw = ds.attrs.get(key)
    return None if raw is None else float(raw)


def _series_reference(data: h5py.Dataset, file_path: str) -> Dict[str, Any]:
    """The scaling, timing and layout a caller needs to read `data` as physical values.

    Everything here is read from the file. The layout is reported only when the file decides
    it -- the series' electrode region, or the schema for a type without one -- and is
    ``"unknown"`` otherwise, never guessed from which dimension is longer.
    """
    group = data.parent
    parts = data.name.strip("/").split("/")
    starting = group.get("starting_time")
    timestamps = group.get("timestamps")
    ndt = _ndt(group)
    is_series = parts[-1] == "data" and len(parts) > 2 and (
        ndt is not None or starting is not None or timestamps is not None)
    if not is_series:
        return {
            "series_path": None, "neurodata_type": None, "unit": None, "conversion": None,
            "offset": None, "channel_conversion": None, "rate_hz": None, "starting_time": None,
            "timestamps_path": None, "n_channels": None, "layout": "unknown",
            "layout_basis": None, "reader": None,
            "access_hint": (
                "This dataset is not the data of a TimeSeries, so no conversion, offset or "
                "timing fields apply and the file does not say what its axes are."
            ),
        }

    n_channels = _h5_channel_count(group, "data")
    basis = None
    if data.ndim == 1:
        layout, basis = "time", "schema"
    elif data.ndim == 2:
        layout, basis = _resolve_layout(data.shape, n_channels, ndt)
        if layout == AMBIGUOUS_LAYOUT or basis not in _LAYOUT_BASIS:
            layout, basis = "unknown", None
    else:
        layout = "unknown"

    channel_conversion = group.get("channel_conversion")
    if isinstance(channel_conversion, h5py.Dataset):
        channel_conversion = [float(v) for v in channel_conversion[()].ravel()]
    else:
        channel_conversion = None
    start = None
    if isinstance(starting, h5py.Dataset) and starting.shape == ():
        start = float(starting[()])
    rate = _series_rate(group)
    timestamps_path = timestamps.name if isinstance(timestamps, h5py.Dataset) else None

    reader = None
    if parts[0] in ("acquisition", "processing") and layout != "unknown":
        name = "/".join(parts[1:-1])
        reader = f"jnwb.acquisition_channel({file_path!r}, name={name!r}, channel=k)"

    hint = []
    if reader:
        hint.append(
            f"Read channel k in physical units with {reader}: it applies conversion, "
            "channel_conversion and offset, and warns when starting_time is not 0."
        )
    hint.append(
        "A direct slice of this dataset returns stored values, not physical ones: "
        "physical = conversion * channel_conversion[k] * stored + offset, taking conversion "
        "1.0, channel_conversion 1.0 and offset 0.0 where the file stores none."
    )
    if rate is not None and start is not None:
        hint.append(
            f"Sample i is at starting_time + i / rate_hz = {start!r} + i / {rate!r} s in "
            "session time, the clock the interval tables use."
        )
    elif timestamps_path is not None:
        hint.append(f"Sample i is at {timestamps_path}[i] s in session time.")
    else:
        hint.append("The file records no timing for this dataset.")
    if layout == "time":
        hint.append("The dataset is one-dimensional: axis 0 is time.")
    elif layout == "unknown":
        hint.append(
            "The layout is unknown: nothing in the file says which axis holds channels. "
            "Establish it before slicing by channel."
        )
    else:
        axes = "axis 0 is time and axis 1 is channels" if layout == "time_by_channel" \
            else "axis 0 is channels and axis 1 is time"
        hint.append(f"Layout {layout}: {axes}, decided by {_LAYOUT_BASIS[basis]}.")

    return {
        "series_path": group.name,
        "neurodata_type": ndt,
        "unit": _decode(data.attrs.get("unit")),
        "conversion": _scalar_attr(data, "conversion"),
        "offset": _scalar_attr(data, "offset"),
        "channel_conversion": channel_conversion,
        "rate_hz": rate,
        "starting_time": start,
        "timestamps_path": timestamps_path,
        "n_channels": n_channels,
        "layout": layout,
        "layout_basis": basis,
        "reader": reader,
        "access_hint": " ".join(hint),
    }

@mcp.tool()
def inspect_nwb(file_path: str) -> Dict[str, Any]:
    """
    Inspect the structure and metadata of an NWB file using jnwb.
    
    Args:
        file_path: Absolute or relative path to the .nwb file.
        
    Returns:
        Structured JSON metadata or error dictionary.
    """
    path = Path(file_path)
    if not path.exists():
        return {
            "error": f"File not found: {file_path}",
            "error_type": "FileNotFound"
        }
        
    try:
        return inspect(path)
    except Exception as e:
        return {
            "error": f"Failed to parse NWB file: {str(e)}",
            "error_type": "ParseError"
        }

@mcp.tool()
def prepare_signal_reference(file_path: str, dataset_path: str) -> Dict[str, Any]:
    """
    Prepare a lazy reference to a large electrophysiology or signal dataset WITHOUT loading data into memory.
    
    Args:
        file_path: Path to the .nwb file.
        dataset_path: HDF5 path to the target dataset (e.g., '/acquisition/ElectricalSeries/data').
        
    Returns:
        Dataset metadata, or an error dictionary. For the data of a TimeSeries it also carries
        what turns stored values into physical ones and samples into session times:
        ``conversion``, ``offset`` and ``channel_conversion`` (``None`` where the file stores
        none), ``unit``, ``rate_hz``, ``starting_time`` or ``timestamps_path``, and ``layout``,
        which is ``"unknown"`` unless the file decides which axis holds channels. ``reader``
        names the jnwb call that applies the scaling for one channel; a raw slice of the
        dataset does not apply it. ``access_hint`` says all of this in one paragraph.
    """
    path = Path(file_path)
    if not path.exists():
        return {
            "error": f"File not found: {file_path}",
            "error_type": "FileNotFound"
        }

    try:
        with h5py.File(str(path), 'r') as f:
            if dataset_path not in f:
                return {
                    "error": f"Dataset path '{dataset_path}' not found in NWB file",
                    "error_type": "PathNotFound"
                }
                
            obj = f[dataset_path]
            if not isinstance(obj, h5py.Dataset):
                return {
                    "error": f"Path '{dataset_path}' is a {type(obj).__name__}, not a dataset",
                    "error_type": "ParseError"
                }
                
            dtype_str = str(obj.dtype)
            shape_list = list(obj.shape)
            chunk_shape = list(obj.chunks) if obj.chunks else None
            compression = str(obj.compression) if obj.compression else None
            
            # Calculate estimated size in MB
            itemsize = obj.dtype.itemsize
            total_elements = 1
            for dim in shape_list:
                total_elements *= dim
            estimated_size_mb = float(total_elements * itemsize) / (1024.0 * 1024.0)
            
            return {
                "dataset_path": dataset_path,
                "dtype": dtype_str,
                "shape": shape_list,
                "chunk_shape": chunk_shape,
                "compression": compression,
                "estimated_size_mb": estimated_size_mb,
                **_series_reference(obj, file_path),
            }
    except Exception as e:
        return {
            "error": f"Failed to prepare signal reference: {str(e)}",
            "error_type": "Unknown"
        }
