# -*- coding: utf-8 -*-
"""NWB TimeSeries sampling rate resolver - read-only, no NWB mutation.

This module provides utilities to resolve sampling rates from NWB TimeSeries
objects when the explicit `rate` attribute is missing, using timestamps or
trusted fallback metadata.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np


def resolve_nwb_timeseries_rate(
    ts: Any,
    *,
    series_path: str = "",
    trusted_fallback_hz: float | None = None,
    timestamp_sample_size: int = 1000,
    jitter_tolerance: float = 0.01,
) -> tuple[float | None, dict[str, Any]]:
    """Resolve sampling rate for an NWB TimeSeries-like object without mutating the NWB.

    Resolution order (first successful):
    1. ts.rate if present and finite
    2. ts.timestamps median dt if timestamps are present and length >= 2
    3. ts.starting_time_rate if represented differently by PyNWB
    4. trusted_fallback_hz only if caller provides it

    Parameters
    ----------
    ts : Any
        NWB TimeSeries-like object (e.g., ElectricalSeries, TimeSeries)
    series_path : str
        Path identifier for error messages (e.g., "acquisition/probe_0_lfp")
    trusted_fallback_hz : float | None
        Explicit fallback rate from trusted manifest/source metadata.
        Only used if rate cannot be resolved from ts directly.
    timestamp_sample_size : int
        Number of timestamps to sample for dt calculation (default 1000)
    jitter_tolerance : float
        Relative tolerance for timestamp regularity check (default 0.01 = 1%)

    Returns
    -------
    rate_hz : float | None
        Resolved sampling rate in Hz, or None if unresolvable
    metadata : dict
        Resolution metadata including:
        - source: "rate" | "timestamps" | "starting_time" | "trusted_fallback" | "unresolved"
        - series_path: str
        - rate_hz: float | None
        - n_timestamps_used: int | None
        - median_dt_s: float | None
        - jitter_max: float | None  # max relative deviation from median dt
        - warnings: list[str]

    Raises
    ------
    No exceptions raised. Returns (None, metadata) on failure.

    Examples
    --------
    >>> from pynwb import NWBHDF5IO
    >>> with NWBHDF5IO('file.nwb', 'r') as io:
    ...     nwb = io.read()
    ...     lfp = nwb.acquisition['probe_0_lfp']
    ...     rate, meta = resolve_nwb_timeseries_rate(
    ...         lfp, series_path='acquisition/probe_0_lfp'
    ...     )
    ...     print(f"Rate: {rate} Hz from {meta['source']}")
    """
    metadata: dict[str, Any] = {
        "series_path": series_path,
        "rate_hz": None,
        "source": "unresolved",
        "n_timestamps_used": None,
        "median_dt_s": None,
        "jitter_max": None,
        "warnings": [],
    }

    # 1. Check explicit rate attribute
    rate_attr = getattr(ts, "rate", None)
    if rate_attr is not None:
        try:
            rate_val = float(rate_attr)
            if np.isfinite(rate_val) and rate_val > 0:
                metadata["rate_hz"] = rate_val
                metadata["source"] = "rate"
                return rate_val, metadata
            else:
                metadata["warnings"].append(
                    f"Explicit rate exists but is non-finite or non-positive: {rate_val}"
                )
        except (TypeError, ValueError) as e:
            metadata["warnings"].append(f"Could not parse rate attribute: {e}")

    # 2. Check timestamps for regular sampling
    timestamps = getattr(ts, "timestamps", None)
    if timestamps is not None:
        try:
            # Get timestamp data - handle h5py datasets
            if hasattr(timestamps, "shape"):
                n_timestamps = timestamps.shape[0]
            elif hasattr(timestamps, "__len__"):
                n_timestamps = len(timestamps)
            else:
                n_timestamps = 0

            if n_timestamps >= 2:
                # Sample timestamps for efficiency
                sample_size = min(timestamp_sample_size, n_timestamps)
                ts_sample = np.asarray(timestamps[:sample_size])

                # Compute dt values
                dts = np.diff(ts_sample)
                median_dt = float(np.median(dts))

                if median_dt > 0:
                    # Check jitter (regularity)
                    jitter = np.abs(dts - median_dt) / median_dt
                    jitter_max = float(np.max(jitter))

                    metadata["n_timestamps_used"] = sample_size
                    metadata["median_dt_s"] = median_dt
                    metadata["jitter_max"] = jitter_max

                    if jitter_max <= jitter_tolerance:
                        # Regular sampling - compute rate
                        rate_hz = 1.0 / median_dt
                        metadata["rate_hz"] = rate_hz
                        metadata["source"] = "timestamps"
                        return rate_hz, metadata
                    else:
                        metadata["warnings"].append(
                            f"Timestamps irregular: jitter={jitter_max:.4f} > tolerance={jitter_tolerance}"
                        )
                else:
                    metadata["warnings"].append(
                        f"Median dt is non-positive: {median_dt}"
                    )
            else:
                metadata["warnings"].append(
                    f"Insufficient timestamps for rate calculation: {n_timestamps}"
                )
        except Exception as e:
            metadata["warnings"].append(f"Error processing timestamps: {e}")

    # 3. Check starting_time and rate representation
    starting_time = getattr(ts, "starting_time", None)
    if starting_time is not None:
        # Some NWB objects store rate differently
        # This is a placeholder for future implementation
        metadata["warnings"].append(
            "starting_time exists but no additional rate info found"
        )

    # 4. Use trusted fallback if provided
    if trusted_fallback_hz is not None:
        try:
            fallback_val = float(trusted_fallback_hz)
            if np.isfinite(fallback_val) and fallback_val > 0:
                metadata["rate_hz"] = fallback_val
                metadata["source"] = "trusted_fallback"
                metadata["warnings"].append(
                    f"Using trusted fallback rate: {fallback_val} Hz"
                )
                return fallback_val, metadata
            else:
                metadata["warnings"].append(
                    f"Trusted fallback is non-finite or non-positive: {fallback_val}"
                )
        except (TypeError, ValueError) as e:
            metadata["warnings"].append(f"Invalid trusted fallback: {e}")

    # Unresolvable
    metadata["warnings"].append(
        "Could not resolve rate from: explicit rate, timestamps, or trusted fallback"
    )
    return None, metadata


def resolve_nwb_lfp_rate(
    nwbfile: Any,
    probe_name: str,
    *,
    trusted_fallback_hz: float | None = None,
) -> tuple[float | None, dict[str, Any]]:
    """Convenience wrapper to resolve LFP rate from NWB acquisition.

    Parameters
    ----------
    nwbfile : Any
        NWBFile object
    probe_name : str
        LFP series name (e.g., "probe_0_lfp")
    trusted_fallback_hz : float | None
        Optional trusted fallback rate

    Returns
    -------
    rate_hz, metadata
        Same as resolve_nwb_timeseries_rate
    """
    acquisition = getattr(nwbfile, "acquisition", {})
    if probe_name not in acquisition:
        return None, {
            "series_path": f"acquisition/{probe_name}",
            "rate_hz": None,
            "source": "unresolved",
            "warnings": [f"LFP series '{probe_name}' not found in acquisition"],
        }

    lfp_series = acquisition[probe_name]
    series_path = f"acquisition/{probe_name}"

    return resolve_nwb_timeseries_rate(
        lfp_series,
        series_path=series_path,
        trusted_fallback_hz=trusted_fallback_hz,
    )


# Typed blocker constants for downstream use
BLOCKED_LFP_RATE_UNRESOLVED = "BLOCKED_LFP_RATE_UNRESOLVED"
BLOCKED_LFP_SERIES_MISSING = "BLOCKED_LFP_SERIES_MISSING"
