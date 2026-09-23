"""Streaming array slice reader for NPZ archives without full-file RAM allocation.

Provides memory-bounded streaming access to arrays stored in .npz files (both compressed
via ZIP_DEFLATED and uncompressed via ZIP_STORED), strictly preserving data types, shapes,
and memory layouts.
"""
from __future__ import annotations

import itertools
import os
import zipfile
from pathlib import Path
from typing import Sequence, Tuple, Union

import numpy as np

__all__ = ["stream_npz_array"]

# Supported zip compression methods for NPZ archives
SUPPORTED_COMPRESSIONS = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})


def _read_skip(f, n_bytes: int, chunk_size: int = 65536) -> None:
    """Discard n_bytes from a sequential stream without accumulating memory in a buffer."""
    mv = memoryview(bytearray(chunk_size))
    while n_bytes > 0:
        take = min(n_bytes, chunk_size)
        n_read = f.readinto(mv[:take])
        if n_read == 0:
            raise EOFError("Unexpected EOF while streaming NPZ archive entry")
        n_bytes -= n_read


def _seek_skip(f, n_bytes: int) -> None:
    """Advance a stored (uncompressed) archive entry by n_bytes without reading them.

    ``ZipExtFile.seek`` clamps a target past the end of the entry instead of failing, so the
    landing position is checked: a header that promises more elements than the entry holds must
    fail here as it does through ``_read_skip``.
    """
    target = f.tell() + n_bytes
    if f.seek(target) != target:
        raise EOFError("Unexpected EOF while streaming NPZ archive entry")


def _stream_slice(
    f,
    shape: Tuple[int, ...],
    fortran_order: bool,
    dtype: np.dtype,
    slice_tuple: Union[slice, int, Tuple[Union[slice, int], ...]],
    seekable: bool = False,
) -> np.ndarray:
    """Stream sliced elements from an open .npy stream in monotonic element order."""
    if isinstance(slice_tuple, (slice, int, np.integer)):
        slice_tuple = (slice_tuple,)

    slices = []
    for s in slice_tuple:
        if isinstance(s, (int, np.integer)):
            slices.append(slice(int(s), int(s) + 1, 1))
        elif isinstance(s, slice):
            slices.append(s)
        else:
            raise TypeError(f"Indices in slice_tuple must be slice or int, got {type(s).__name__}")

    if len(slices) > len(shape):
        raise ValueError(
            f"Too many indices for array: array is {len(shape)}-dimensional, but {len(slices)} were indexed"
        )


    while len(slices) < len(shape):
        slices.append(slice(None))

    indices = [s.indices(dim) for s, dim in zip(slices, shape)]
    out_shape = tuple(len(range(*idx)) for idx in indices)
    order = "F" if fortran_order else "C"

    if any(s == 0 for s in out_shape):
        return np.empty(out_shape, dtype=dtype, order=order)

    ndim = len(shape)
    if fortran_order:
        elem_strides = [1] * ndim
        for i in range(1, ndim):
            elem_strides[i] = elem_strides[i - 1] * shape[i - 1]
    else:
        elem_strides = [1] * ndim
        for i in range(ndim - 2, -1, -1):
            elem_strides[i] = elem_strides[i + 1] * shape[i + 1]

    ranges = [range(*idx) for idx in indices]
    itemsize = dtype.itemsize

    fast_axis = 0 if fortran_order else ndim - 1
    fast_range = ranges[fast_axis]
    fast_stride = elem_strides[fast_axis]
    is_fast_contiguous = (fast_range.step == 1 and fast_stride == 1)

    out = np.empty(out_shape, dtype=dtype, order=order)
    curr_elem = 0
    # A stored entry seeks past what the slice skips, so time follows what is read. A compressed
    # entry has no random access and must be decompressed up to the last selected element.
    skip = _seek_skip if seekable else _read_skip

    def forward_to_elem(target_elem: int) -> None:
        nonlocal curr_elem
        diff_elems = target_elem - curr_elem
        if diff_elems < 0:
            raise ValueError(
                f"Internal streaming error: target element {target_elem} < current element {curr_elem}"
            )
        if diff_elems > 0:
            skip(f, diff_elems * itemsize)
            curr_elem = target_elem


    if is_fast_contiguous and len(fast_range) > 0:
        block_len = len(fast_range)
        block_bytes = block_len * itemsize
        fast_start_elem = fast_range.start * fast_stride

        other_axes = [ax for ax in range(ndim) if ax != fast_axis]
        # To preserve monotonic forward streaming, sort other_axes by descending stride so that
        # the dimension with smallest stride varies in the innermost loop of itertools.product.
        other_axes.sort(key=lambda ax: elem_strides[ax], reverse=True)
        other_ranges = [ranges[ax] for ax in other_axes]
        other_strides = [elem_strides[ax] for ax in other_axes]

        for outer_coords in itertools.product(*other_ranges):
            outer_elem_offset = sum(c * s for c, s in zip(outer_coords, other_strides))
            target_elem = outer_elem_offset + fast_start_elem
            forward_to_elem(target_elem)

            coord_map = dict(zip(other_axes, outer_coords))
            out_slice = []
            for ax in range(ndim):
                if ax == fast_axis:
                    out_slice.append(slice(None))
                else:
                    coord = coord_map[ax]
                    idx_in_out = (coord - ranges[ax].start) // ranges[ax].step
                    out_slice.append(idx_in_out)

            dest_sub = out[tuple(out_slice)]
            if dest_sub.flags.c_contiguous or dest_sub.flags.f_contiguous:
                f.readinto(dest_sub.data)
            else:
                buf = bytearray(block_bytes)
                f.readinto(buf)
                out[tuple(out_slice)] = np.frombuffer(buf, dtype=dtype)
            curr_elem += block_len
    else:
        flat_tasks = []
        for out_idx in np.ndindex(*out_shape):
            elem_offset = sum(ranges[ax][out_idx[ax]] * elem_strides[ax] for ax in range(ndim))
            flat_tasks.append((elem_offset, out_idx))
        flat_tasks.sort(key=lambda t: t[0])

        item_buf = bytearray(itemsize)
        mv_item = memoryview(item_buf)
        for elem_offset, out_idx in flat_tasks:
            forward_to_elem(elem_offset)
            f.readinto(mv_item)
            curr_elem += 1
            out[out_idx] = np.frombuffer(item_buf, dtype=dtype)[0]

    return out


def stream_npz_array(
    file_path: Union[str, Path],
    key: str,
    slice_tuple: Union[slice, int, Tuple[Union[slice, int], ...]] = (slice(None),),
) -> np.ndarray:
    """Stream a memory-bounded slice from an uncompressed or compressed NPZ archive.

    Streams chunked array slices directly from the underlying archive without loading
    the full array into RAM. Supports both standard uncompressed archives (ZIP_STORED)
    and compressed archives ZIP_DEFLATED). Preserves exact dtype, shape, and Fortran/C
    memory order.

    Time depends on the compression. A stored archive (``np.savez``) seeks past what the slice
    skips, so time follows the number of elements read. A compressed archive
    (``np.savez_compressed``) is decompressed from the start of the array to its last selected
    element. Seeking means the entry's CRC-32 is checked only when the slice skips nothing;
    read the whole array to verify the file.

    Args:
        file_path: Path to the .npz archive on disk.
        key: Array key within the archive (with or without '.npy' suffix).
        slice_tuple: Slice specification for the array (slice, int, or tuple of slices/ints).

    Returns:
        np.ndarray: Sliced array with preserved dtype and memory order.


    Raises:
        FileNotFoundError: If file_path does not exist on disk.
        KeyError: If key is not present in the NPZ archive.
        ValueError: If archive is corrupt, compression method is unsupported,
                    array format/header is invalid, or layout is unsupported (e.g. object dtype).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"NPZ archive not found: {path}")


    entry_name = key if key.endswith(".npy") else f"{key}.npy"

    try:
        zf = zipfile.ZipFile(path, mode="r")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Corrupt or invalid NPZ archive: {path}") from exc
    except Exception as exc:
        raise ValueError(f"Could not open NPZ archive {path}: {exc}") from exc

    with zf:
        if entry_name not in zf.namelist():
            avail = [n[:-4] if n.endswith(".npy") else n for n in zf.namelist()]
            raise KeyError(f"Key '{key}' not found in archive {path}. Available keys: {avail}")

        info = zf.getinfo(entry_name)
        if info.compress_type not in SUPPORTED_COMPRESSIONS:
            raise ValueError(
                f"Unsupported compression method {info.compress_type} for key '{key}' in {path}. "
                "Supported methods are ZIP_STORED (0) and ZIP_DEFLATED (8)."
            )

        try:
            with zf.open(entry_name, mode="r") as f:
                version = np.lib.format.read_magic(f)
                if version == (1, 0):
                    shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(f)
                elif version == (2, 0):
                    shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(f)
                else:
                    shape, fortran_order, dtype = np.lib.format._read_array_header(f, version)

                if dtype.hasobject:
                    raise ValueError(
                        f"Unsupported array layout: object dtype arrays cannot be streamed from {path}"
                    )

                return _stream_slice(
                    f=f,
                    shape=shape,
                    fortran_order=fortran_order,
                    dtype=dtype,
                    slice_tuple=slice_tuple,
                    seekable=info.compress_type == zipfile.ZIP_STORED and f.seekable(),
                )
        except (KeyError, ValueError):
            raise
        except Exception as exc:
            raise ValueError(f"Failed to stream array '{key}' from corrupt archive {path}: {exc}") from exc
