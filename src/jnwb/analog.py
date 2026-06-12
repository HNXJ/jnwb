"""LFP/MUAe analog TimeSeries epoch extraction for jnwb."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .errors import (
    BLOCKED_ANALOG_EPOCH_OUT_OF_BOUNDS,
    BLOCKED_ANALOG_OBJECT_PATH_MISSING,
    BLOCKED_ANALOG_SAMPLING_RATE_MISSING,
    BLOCKED_ANALOG_TIMEBASE_UNSUPPORTED,
    BLOCKED_EMPTY_EPOCHS,
    JnwbBlockedError,
)
from .schema import EventAddress, SignalAddress


def resolve_timeseries_from_path(nwbfile: Any, object_path: str) -> Any:
    """Resolve a TimeSeries object from an object path string."""
    if not object_path:
        raise JnwbBlockedError(
            "Analog object path missing from signal address",
            code=BLOCKED_ANALOG_OBJECT_PATH_MISSING,
        )

    parts = object_path.split("/")
    if parts[0] == "acquisition" and len(parts) == 2:
        acquisition = getattr(nwbfile, "acquisition", {})
        if parts[1] not in acquisition:
            raise JnwbBlockedError(
                f"Acquisition series not found: {object_path}",
                code=BLOCKED_ANALOG_OBJECT_PATH_MISSING,
            )
        return acquisition[parts[1]]

    if parts[0] == "processing" and len(parts) == 3:
        processing = getattr(nwbfile, "processing", {})
        if parts[1] not in processing:
            raise JnwbBlockedError(
                f"Processing module not found: {object_path}",
                code=BLOCKED_ANALOG_OBJECT_PATH_MISSING,
            )
        module = processing[parts[1]]
        if parts[2] not in module.data_interfaces:
            raise JnwbBlockedError(
                f"Processing series not found: {object_path}",
                code=BLOCKED_ANALOG_OBJECT_PATH_MISSING,
            )
        return module.data_interfaces[parts[2]]

    raise JnwbBlockedError(
        f"Unsupported analog object path: {object_path}",
        code=BLOCKED_ANALOG_OBJECT_PATH_MISSING,
    )


def get_timeseries_channel_count(ts: Any) -> int:
    data = np.asarray(ts.data)
    if data.ndim == 1:
        return 1
    if data.ndim == 2:
        return int(data.shape[1])
    raise JnwbBlockedError(f"Unsupported analog data ndim: {data.ndim}")


def get_sampling_rate_hz(ts: Any) -> float:
    """Resolve sampling rate from rate attribute or regular timestamps."""
    rate = getattr(ts, "rate", None)
    if rate is not None:
        return float(rate)

    timestamps = getattr(ts, "timestamps", None)
    if timestamps is not None:
        ts_arr = np.asarray(timestamps, dtype=np.float64)
        if len(ts_arr) < 2:
            raise JnwbBlockedError(
                "Insufficient timestamps to infer sampling rate",
                code=BLOCKED_ANALOG_SAMPLING_RATE_MISSING,
            )
        dts = np.diff(ts_arr)
        if not np.allclose(dts, dts[0], rtol=1e-3, atol=1e-6):
            raise JnwbBlockedError(
                "Irregular timestamps; only regular analog time bases supported",
                code=BLOCKED_ANALOG_TIMEBASE_UNSUPPORTED,
            )
        return 1.0 / float(dts[0])

    raise JnwbBlockedError(
        "No sampling rate or regular timestamps on analog TimeSeries",
        code=BLOCKED_ANALOG_SAMPLING_RATE_MISSING,
    )


def get_starting_time_s(ts: Any) -> float:
    starting = getattr(ts, "starting_time", None)
    if starting is not None:
        return float(starting)
    timestamps = getattr(ts, "timestamps", None)
    if timestamps is not None and len(timestamps) > 0:
        return float(np.asarray(timestamps)[0])
    return 0.0


def expected_n_samples(window_ms: tuple[int, int], fs: float) -> int:
    """Sample count for half-open window [pre_ms, post_ms) at rate fs."""
    pre_ms, post_ms = window_ms
    duration_ms = post_ms - pre_ms
    if duration_ms <= 0:
        raise JnwbBlockedError(f"Invalid window_ms: {window_ms}")
    return int(np.round(duration_ms / 1000.0 * fs))


def time_axis_ms(window_ms: tuple[int, int], fs: float, n_samples: int | None = None) -> np.ndarray:
    """Milliseconds relative to alignment event; sample k at pre_ms + k*(1000/fs)."""
    if n_samples is None:
        n_samples = expected_n_samples(window_ms, fs)
    return window_ms[0] + np.arange(n_samples, dtype=np.float64) * (1000.0 / fs)


def extract_analog_epoch_chunk(
    ts: Any,
    channel_ids: list[int],
    event_times_s: np.ndarray,
    window_ms: tuple[int, int],
    fs: float | None = None,
    fail_on_oob: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract trial x channel x time analog epochs.

    Window convention: half-open [pre_ms, post_ms) relative to each event anchor.
    """
    if fs is None:
        fs = get_sampling_rate_hz(ts)

    data_all = np.asarray(ts.data)
    if data_all.ndim == 1:
        data_all = data_all[:, np.newaxis]

    n_time = int(data_all.shape[0])
    n_channels = len(channel_ids)
    n_trials = len(event_times_s)
    n_samples = expected_n_samples(window_ms, fs)
    time_ms = time_axis_ms(window_ms, fs, n_samples)
    starting_time = get_starting_time_s(ts)

    pre_ms, post_ms = window_ms
    pre_s = pre_ms / 1000.0
    post_s = post_ms / 1000.0

    out = np.zeros((n_trials, n_channels, n_samples), dtype=np.float32)

    for t_idx, onset_s in enumerate(event_times_s):
        t_start_s = float(onset_s) + pre_s
        t_end_s = float(onset_s) + post_s
        i_start = int(np.round((t_start_s - starting_time) * fs))
        i_end = i_start + n_samples

        if i_start < 0 or i_end > n_time:
            msg = (
                f"Analog epoch out of bounds for trial {t_idx}: "
                f"indices [{i_start}, {i_end}) vs n_time={n_time}"
            )
            if fail_on_oob:
                raise JnwbBlockedError(msg, code=BLOCKED_ANALOG_EPOCH_OUT_OF_BOUNDS)
            continue

        out[t_idx] = data_all[i_start:i_end, channel_ids].T.astype(np.float32)

    if out.size == 0:
        raise JnwbBlockedError("Empty analog epoch chunk", code=BLOCKED_EMPTY_EPOCHS)

    return out, time_ms


def analog_signal_metadata_rows(
    signal_addr: SignalAddress,
    skey: str,
    object_path: str,
    fs: float,
    units: str | None,
    polarity: str = "unknown",
) -> pd.DataFrame:
    channel_ids = signal_addr.ids_by_session[skey]
    return pd.DataFrame(
        [
            {
                "session_id": skey,
                "signal_id": ch,
                "channel_id": ch,
                "global_channel_index": idx,
                "signal_class": signal_addr.signal,
                "area": signal_addr.area_by_id[skey].get(ch),
                "layer": signal_addr.layer_by_id[skey].get(ch),
                "probe": signal_addr.probe_by_id[skey].get(ch),
                "object_path": object_path,
                "sampling_rate_hz": fs,
                "units": units,
                "polarity": polarity,
            }
            for idx, ch in enumerate(channel_ids)
        ]
    )


def trial_metadata_rows(events: list[dict], skey: str, trial_offset: int = 0) -> list[dict]:
    return [
        {
            "trial_global": trial_offset + t_idx,
            "trial_in_session": t_idx,
            "trial_id": ev.get("trial_id", trial_offset + t_idx),
            "session_id": skey,
            "condition": ev["condition"],
            "condition_number": ev["condition_number"],
            "onset_s": ev["onset_s"],
            "anchor": ev["anchor"],
            "anchor_time_s": ev["onset_s"],
            "alignment_event": ev["anchor"],
            "time_base": "p1_relative",
            "omission_offset_ms": ev.get("omission_offset_ms"),
        }
        for t_idx, ev in enumerate(events)
    ]
