"""Continuous time-series operations and alignment primitives for jnwb."""

from __future__ import annotations

from typing import Literal, Sequence, Union
import numpy as np


BoundaryPolicy = Literal["nan", "error", "drop"]
OnsetUnit = Literal["seconds", "samples"]


def epoch_continuous(
    data: np.ndarray,
    onsets: np.ndarray | Sequence[float],
    *,
    win_s: tuple[float, float],
    fs: float,
    onset_unit: OnsetUnit = "seconds",
    boundary_policy: BoundaryPolicy = "nan",
) -> tuple[np.ndarray, np.ndarray]:
    """Extract fixed-duration epochs from a continuous signal aligned to event onsets.

    Parameters
    ----------
    data:
        1D array of shape ``(n_samples,)`` or 2D array of shape ``(n_samples, n_channels)``.
    onsets:
        1D array or sequence of event onset timestamps.
    win_s:
        Tuple ``(t_pre_s, t_post_s)`` specifying the window relative to each onset
        in seconds. ``t_pre_s`` must be strictly less than ``t_post_s``.
    fs:
        Continuous signal sampling rate in Hz (must be positive).
    onset_unit:
        Unit of ``onsets``. ``"seconds"`` (default) converts onsets to samples using
        ``fs``; ``"samples"`` treats onsets as integer sample indices.
    boundary_policy:
        Policy for epoch windows extending beyond the continuous signal boundaries
        ``[0, n_samples)``:
        - ``"nan"`` (default): pads out-of-bounds segments with ``np.nan``.
        - ``"error"``: raises :class:`ValueError` if any window extends beyond boundaries.
        - ``"drop"``: drops out-of-bounds events from the output array.

    Returns
    -------
    epochs:
        Array of extracted epochs. Shape is ``(n_events, n_window_samples)`` for
        1D input, or ``(n_events, n_window_samples, n_channels)`` for 2D input.
        If ``boundary_policy="drop"``, ``n_events`` may be less than ``len(onsets)``.
    time_axis_s:
        1D array of time offsets relative to onset in seconds, shape ``(n_window_samples,)``.
    """
    arr = np.asarray(data)
    if arr.ndim not in (1, 2):
        raise ValueError(f"Continuous data must be 1D or 2D, got shape {arr.shape}")
    if fs <= 0.0:
        raise ValueError(f"Sampling rate fs must be positive, got {fs}")
    if len(win_s) != 2:
        raise ValueError(f"win_s must be a 2-tuple (t_pre_s, t_post_s), got {win_s}")
    t_pre, t_post = float(win_s[0]), float(win_s[1])
    if t_pre >= t_post:
        raise ValueError(f"win_s[0] must be strictly less than win_s[1], got {win_s}")

    n_pre = int(np.round(t_pre * fs))
    n_post = int(np.round(t_post * fs))
    n_win = n_post - n_pre
    if n_win <= 0:
        raise ValueError(f"Window duration produced non-positive sample count: {n_win}")

    time_axis_s = np.arange(n_pre, n_post, dtype=np.float64) / fs
    n_samples = arr.shape[0]

    onsets_arr = np.asarray(onsets)
    if onsets_arr.size == 0:
        if arr.ndim == 1:
            return np.empty((0, n_win), dtype=arr.dtype), time_axis_s
        return np.empty((0, n_win, arr.shape[1]), dtype=arr.dtype), time_axis_s

    if onset_unit == "seconds":
        center_indices = np.round(onsets_arr.astype(np.float64) * fs).astype(np.int64)
    elif onset_unit == "samples":
        center_indices = np.round(onsets_arr.astype(np.float64)).astype(np.int64)
    else:
        raise ValueError(f"Unknown onset_unit: '{onset_unit}'. Expected 'seconds' or 'samples'")

    if boundary_policy not in ("nan", "error", "drop"):
        raise ValueError(f"Unknown boundary_policy: '{boundary_policy}'. Expected 'nan', 'error', or 'drop'")

    epochs_list: list[np.ndarray] = []
    out_dtype = np.float64 if (boundary_policy == "nan" and np.issubdtype(arr.dtype, np.integer)) else arr.dtype

    for idx, onset_val in zip(center_indices, onsets_arr):
        start = idx + n_pre
        end = idx + n_post

        if 0 <= start and end <= n_samples:
            epochs_list.append(arr[start:end].astype(out_dtype, copy=False))
        else:
            if boundary_policy == "error":
                raise ValueError(
                    f"Epoch window [{start}, {end}) for onset {onset_val} extends outside data [0, {n_samples})"
                )
            elif boundary_policy == "drop":
                continue
            else:  # "nan"
                target_dtype = np.float64 if not np.issubdtype(arr.dtype, np.floating) else arr.dtype
                if arr.ndim == 1:
                    epoch = np.full((n_win,), np.nan, dtype=target_dtype)
                    valid_start = max(0, start)
                    valid_end = min(n_samples, end)
                    if valid_start < valid_end:
                        target_start = valid_start - start
                        target_end = target_start + (valid_end - valid_start)
                        epoch[target_start:target_end] = arr[valid_start:valid_end]
                    epochs_list.append(epoch)
                else:
                    n_ch = arr.shape[1]
                    epoch = np.full((n_win, n_ch), np.nan, dtype=target_dtype)
                    valid_start = max(0, start)
                    valid_end = min(n_samples, end)
                    if valid_start < valid_end:
                        target_start = valid_start - start
                        target_end = target_start + (valid_end - valid_start)
                        epoch[target_start:target_end, :] = arr[valid_start:valid_end, :]
                    epochs_list.append(epoch)

    if not epochs_list:
        if arr.ndim == 1:
            return np.empty((0, n_win), dtype=out_dtype), time_axis_s
        return np.empty((0, n_win, arr.shape[1]), dtype=out_dtype), time_axis_s

    epochs_arr = np.stack(epochs_list, axis=0)
    return epochs_arr, time_axis_s
