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
    return_indices: bool = False,
) -> tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, np.ndarray]:
    r"""Extract fixed-duration epochs from a continuous signal aligned to event onsets.

    Time-to-Sample Mapping
    ----------------------
    Sample indices are computed from continuous timestamps using IEEE 754
    round-half-to-even (banker's rounding):

    .. math::
        n_{\mathrm{pre}} = \operatorname{round}(t_{\mathrm{pre}} \cdot f_s) \\
        n_{\mathrm{post}} = \operatorname{round}(t_{\mathrm{post}} \cdot f_s) \\
        n_{\mathrm{center}} = \operatorname{round}(t_{\mathrm{onset}} \cdot f_s)

    The extraction window for each event spans the half-open sample interval:

    .. math::
        [n_{\mathrm{center}} + n_{\mathrm{pre}}, \, n_{\mathrm{center}} + n_{\mathrm{post}})

    containing :math:`n_{\mathrm{win}} = n_{\mathrm{post}} - n_{\mathrm{pre}}` samples.
    The returned ``time_axis_s`` is defined as:

    .. math::
        t_k = \frac{n_{\mathrm{pre}} + k}{f_s}, \quad k \in \{0, 1, \dots, n_{\mathrm{win}} - 1\}

    Parameters
    ----------
    data:
        1D array of shape ``(n_samples,)`` or 2D array of shape ``(n_samples, n_channels)``.
    onsets:
        1D array or sequence of event onset timestamps.
    win_s:
        Tuple ``(t_pre_s, t_post_s)`` specifying the window relative to each onset
        in seconds. ``t_pre_s`` must be strictly less than ``t_post_s``. Negative
        windows (e.g. ``(-0.5, -0.1)``) and asymmetric windows are fully supported.
    fs:
        Continuous signal sampling rate in Hz (must be positive).
    onset_unit:
        Unit of ``onsets``. ``"seconds"`` (default) converts onsets to samples using
        ``fs``; ``"samples"`` treats onsets as integer sample indices.
    boundary_policy:
        Policy for epoch windows extending beyond continuous signal boundaries
        ``[0, n_samples)``:
        - ``"nan"`` (default): pads out-of-bounds segments with ``np.nan``.
        - ``"error"``: raises :class:`ValueError` if any window extends beyond boundaries.
        - ``"drop"``: drops out-of-bounds events from the output array.
    return_indices:
        If ``True``, also returns an integer array of the 0-based indices of the
        events retained from ``onsets``. When ``boundary_policy="drop"``, this
        preserves exact identity correspondence to input events and metadata.

    Returns
    -------
    epochs:
        Array of extracted epochs. Shape is ``(n_events, n_window_samples)`` for
        1D input, or ``(n_events, n_window_samples, n_channels)`` for 2D input.
        If ``boundary_policy="drop"``, ``n_events`` may be less than ``len(onsets)``.
    time_axis_s:
        1D array of time offsets relative to onset in seconds, shape ``(n_window_samples,)``.
    retained_indices:
        1D array of int64 indices of retained events in ``onsets``, shape ``(n_events,)``.
        Only returned if ``return_indices=True``.
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
        empty_ret = np.empty((0,), dtype=np.int64)
        if arr.ndim == 1:
            empty_epochs = np.empty((0, n_win), dtype=arr.dtype)
        else:
            empty_epochs = np.empty((0, n_win, arr.shape[1]), dtype=arr.dtype)
        return (empty_epochs, time_axis_s, empty_ret) if return_indices else (empty_epochs, time_axis_s)

    if onset_unit == "seconds":
        center_indices = np.round(onsets_arr.astype(np.float64) * fs).astype(np.int64)
    elif onset_unit == "samples":
        center_indices = np.round(onsets_arr.astype(np.float64)).astype(np.int64)
    else:
        raise ValueError(f"Unknown onset_unit: '{onset_unit}'. Expected 'seconds' or 'samples'")

    if boundary_policy not in ("nan", "error", "drop"):
        raise ValueError(f"Unknown boundary_policy: '{boundary_policy}'. Expected 'nan', 'error', or 'drop'")

    epochs_list: list[np.ndarray] = []
    retained_list: list[int] = []
    out_dtype = np.float64 if (boundary_policy == "nan" and np.issubdtype(arr.dtype, np.integer)) else arr.dtype

    for event_idx, (idx, onset_val) in enumerate(zip(center_indices, onsets_arr)):
        start = idx + n_pre
        end = idx + n_post

        if 0 <= start and end <= n_samples:
            epochs_list.append(arr[start:end].astype(out_dtype, copy=False))
            retained_list.append(event_idx)
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
                    retained_list.append(event_idx)
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
                    retained_list.append(event_idx)

    retained_arr = np.array(retained_list, dtype=np.int64)
    if not epochs_list:
        if arr.ndim == 1:
            empty_epochs = np.empty((0, n_win), dtype=out_dtype)
        else:
            empty_epochs = np.empty((0, n_win, arr.shape[1]), dtype=out_dtype)
        return (empty_epochs, time_axis_s, retained_arr) if return_indices else (empty_epochs, time_axis_s)

    epochs_arr = np.stack(epochs_list, axis=0)
    return (epochs_arr, time_axis_s, retained_arr) if return_indices else (epochs_arr, time_axis_s)
