"""Bounded signal extraction for analysis recipes.

Extracts signal epochs around events with memory-safe bounded reads.
Never loads full session signals into memory.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Mapping, Literal

import numpy as np
import pandas as pd

from src.analysis.io.nwb_address import get_aligned_unit_signals, _open_nwb
from src.analysis.recipes.specs import WindowSpec


# Typed blocker codes
BLOCKED_SIGNAL_SERIES_MISSING = "BLOCKED_SIGNAL_SERIES_MISSING"
BLOCKED_SIGNAL_RATE_MISSING = "BLOCKED_SIGNAL_RATE_MISSING"
BLOCKED_SIGNAL_WINDOW_OUT_OF_BOUNDS = "BLOCKED_SIGNAL_WINDOW_OUT_OF_BOUNDS"
BLOCKED_UNSUPPORTED_SIGNAL_SHAPE = "BLOCKED_UNSUPPORTED_SIGNAL_SHAPE"


class SignalExtractionWarning(UserWarning):
    """Warning for signal extraction issues."""
    pass


def _warn(code: str, message: str) -> dict[str, str]:
    """Create a warning record."""
    warnings.warn(f"[{code}] {message}", SignalExtractionWarning)
    return {"code": code, "message": message}


def get_spike_epochs(
    nwb_path: str | Path,
    event_vectors: dict[str, np.ndarray],
    window: WindowSpec,
    unit_filter: Mapping[str, Any] | None = None,
    bin_ms: float | None = 1.0,
) -> dict[str, np.ndarray] | dict[str, list]:
    """Extract spike epochs from NWB units table.
    
    Parameters
    ----------
    nwb_path : Path to NWB file
    event_vectors : Condition -> onset times (seconds) from get_event_timing_vectors()
    window : WindowSpec with pre_ms, post_ms, time_base
    unit_filter : Optional filter like {"area": "V1", "presence_ratio_min": 0.95}
    bin_ms : Bin width for spike counting. If None, returns ragged spike times.
    
    Returns
    -------
    If bin_ms is not None:
        dict[str, np.ndarray] with shape (trials, units, time_bins)
        Integer spike counts per bin.
    If bin_ms is None:
        dict[str, list] with ragged structure [trial][unit] -> spike_times_ms
    
    Shape expectations (binned):
    - Input event_vectors: {condition: array(trials,) of onset times}
    - Output: {condition: array(trials, units, time_bins)}
    - Units: spike counts (integer)
    - Time axis: milliseconds relative to event, spaced by bin_ms
    
    Trial structure:
    - Trial axis preserved (no trial averaging)
    - Unit axis preserved (no unit averaging)
    - Time axis: window.pre_ms to window.post_ms in bin_ms steps
    
    Memory safety:
    - Uses NWB lazy spike time reads
    - Never loads full unit spike train into memory
    - Bounded to window around each event
    
    Example
    -------
    >>> events = get_event_timing_vectors(nwb, event="p1")
    >>> window = WindowSpec(pre_ms=-500, post_ms=1000)
    >>> spk = get_spike_epochs(nwb, events, window, bin_ms=10.0)
    >>> spk["AAAB"].shape
    (605, 167, 150)  # trials, units, 10ms bins
    
    Typed blockers:
    - May raise RuntimeError from underlying get_aligned_unit_signals
    """
    nwb_path = Path(nwb_path)
    unit_filter = dict(unit_filter) if unit_filter else {}
    
    # Convert event vectors to the format expected by get_aligned_unit_signals
    # event_vectors is already {condition: array(onset_times_sec)}
    
    # Take first condition for extraction (process iteratively if needed)
    # For now, extract per-condition to handle variable trial counts
    results: dict[str, np.ndarray] = {}
    
    for condition, onset_times_sec in event_vectors.items():
        if len(onset_times_sec) == 0:
            # Empty condition - return empty array with correct shape
            if bin_ms is not None:
                n_bins = int((window.post_ms - window.pre_ms) / bin_ms)
                results[condition] = np.zeros((0, 0, n_bins), dtype=np.int32)
            else:
                results[condition] = []
            continue
        
        # Extract for this condition only
        try:
            aligned = get_aligned_unit_signals(
                nwb_path=nwb_path,
                unit_filter=unit_filter,
                event_vectors={condition: onset_times_sec},
                pre_ms=window.pre_ms,
                post_ms=window.post_ms,
                bin_ms=bin_ms,
            )
            
            # aligned["spikes"][condition] has shape (trials, units, time_bins)
            results[condition] = aligned["spikes"][condition]
            
        except Exception as e:
            warnings.warn(f"Failed to extract spikes for {condition}: {e}")
            if bin_ms is not None:
                n_bins = int((window.post_ms - window.pre_ms) / bin_ms)
                results[condition] = np.zeros((len(onset_times_sec), 0, n_bins), dtype=np.int32)
            else:
                results[condition] = []
    
    return results


def smooth_spike_epochs(
    spk_epochs: dict[str, np.ndarray],
    sigma_ms: float = 20.0,
    fs: float = 1000.0,
) -> dict[str, np.ndarray]:
    """Gaussian-convolve binned spike epochs to create smoothed PSTH.
    
    Parameters
    ----------
    spk_epochs : dict[str, np.ndarray] with shape (trials, units, time)
        Output from get_spike_epochs with bin_ms specified
    sigma_ms : Gaussian kernel standard deviation in milliseconds
    fs : Sampling rate in Hz (default 1000 for 1ms bins)
    
    Returns
    -------
    dict[str, np.ndarray] with same shape (trials, units, time)
        Smoothed firing rate in Hz (continuous)
    
    Shape preservation:
    - Input: (trials, units, time_bins)
    - Output: (trials, units, time_bins)
    - No trial averaging
    - No unit averaging
    
    Units:
    - Input: spike counts per bin (integer)
    - Output: firing rate in Hz (continuous float)
    - Conversion: counts/bin * (1000 ms/s / bin_ms) = Hz
    
    Example
    -------
    >>> spk = get_spike_epochs(nwb, events, window, bin_ms=1.0)
    >>> spk_smooth = smooth_spike_epochs(spk, sigma_ms=20.0)
    >>> spk_smooth["AAAB"].shape == spk["AAAB"].shape
    True
    """
    results: dict[str, np.ndarray] = {}
    
    # Create Gaussian kernel
    # 3-sigma window is usually sufficient
    # Convert sigma from ms to samples
    sigma_samples = sigma_ms * fs / 1000.0
    kernel_size = int(6 * sigma_samples) + 1
    if kernel_size % 2 == 0:
        kernel_size += 1  # Ensure odd length
    
    half_size = kernel_size // 2
    t = np.arange(-half_size, half_size + 1)  # samples
    kernel = np.exp(-t**2 / (2 * sigma_samples**2))
    kernel /= kernel.sum()  # Normalize
    
    for condition, spk_array in spk_epochs.items():
        if spk_array.size == 0:
            results[condition] = spk_array.astype(np.float64)
            continue
        
        n_trials, n_units, n_time = spk_array.shape
        
        # Determine bin size from conversion to Hz
        # If bin_ms=1.0 and fs=1000, then each count is 1 spike/ms = 1000 Hz
        # Conversion factor: counts * (1000 / bin_ms) = Hz
        # For 1ms bins: multiply by 1000 to get Hz
        bin_ms = 1000.0 / fs  # Assuming fs corresponds to 1/bin_ms
        hz_conversion = 1000.0 / bin_ms
        
    # Convolve each trial-unit trace
    smoothed = np.zeros((n_trials, n_units, n_time), dtype=np.float64)
    
    for trial_idx in range(n_trials):
        for unit_idx in range(n_units):
            trace = spk_array[trial_idx, unit_idx, :].astype(np.float64)
            
            # Handle edge case where kernel is larger than trace
            if len(kernel) > len(trace):
                # Fall back to simple smoothing or truncate kernel
                # Use a smaller effective sigma
                small_kernel_size = min(len(trace) - 1 if len(trace) > 1 else 1, 21)
                if small_kernel_size % 2 == 0:
                    small_kernel_size += 1
                small_half = small_kernel_size // 2
                small_t = np.arange(-small_half, small_half + 1)
                # Adjust sigma for smaller kernel
                small_sigma = max(1.0, sigma_samples * small_half / half_size) if half_size > 0 else 1.0
                kernel_small = np.exp(-small_t**2 / (2 * small_sigma**2))
                kernel_small /= kernel_small.sum()
                convolved = np.convolve(trace, kernel_small, mode='same')
            else:
                # Convolve with Gaussian kernel
                convolved = np.convolve(trace, kernel, mode='same')
            
            # Convert to Hz
            smoothed[trial_idx, unit_idx, :] = convolved * hz_conversion
    
    results[condition] = smoothed
    
    return results


def get_lfp_epochs(
    nwb_path: str | Path,
    event_vectors: dict[str, np.ndarray],
    window: WindowSpec,
    channel_map: pd.DataFrame | None = None,
    channel_filter: Mapping[str, Any] | None = None,
    signal_name_hint: str = "lfp",
) -> dict[str, np.ndarray]:
    """Bounded read-only LFP epoch extraction from NWB.
    
    Memory safety: Never loads full session signal into memory.
    Only reads the requested window around each event.
    
    Parameters
    ----------
    nwb_path : Path to NWB file
    event_vectors : Condition -> onset times (seconds)
    window : WindowSpec with pre_ms, post_ms
    channel_map : Optional DataFrame with channel_index, area columns
    channel_filter : Optional filter like {"area": "V1"} or {"channel_indices": [0,1,2]}
    signal_name_hint : Substring to find in acquisition names (default "lfp")
    
    Returns
    -------
    dict[str, np.ndarray] with shape (trials, channels, time)
        LFP signal in microvolts or arbitrary units
    
    Shape expectations:
    - Input event_vectors: {condition: array(trials,) of onset times}
    - Output: {condition: array(trials, channels, time_samples)}
    - Time axis: milliseconds from window.pre_ms to window.post_ms
    
    Memory safety:
    - Opens NWB read-only
    - Finds LFP ElectricalSeries in acquisition
    - Uses bounded indexing: only reads window samples around each event
    - Skips trials that would exceed bounds
    
    Typed blockers:
    - BLOCKED_SIGNAL_SERIES_MISSING: No series matching signal_name_hint
    - BLOCKED_SIGNAL_RATE_MISSING: Series lacks sampling rate
    - BLOCKED_SIGNAL_WINDOW_OUT_OF_BOUNDS: Event too close to session edge
    
    Example
    -------
    >>> events = get_event_timing_vectors(nwb, event="p1")
    >>> window = WindowSpec(pre_ms=-250, post_ms=750)
    >>> lfp = get_lfp_epochs(nwb, events, window, channel_filter={"area": "V1"})
    >>> lfp["AAAB"].shape
    (605, 64, 1000)  # trials, channels, 1ms samples
    """
    nwb_path = Path(nwb_path)
    channel_filter = dict(channel_filter) if channel_filter else {}
    
    nwbfile, io, warns = _open_nwb(nwb_path)
    
    try:
        # Find LFP acquisition
        acquisition = getattr(nwbfile, "acquisition", {})
        lfp_series = None
        lfp_name = None
        
        for name, obj in acquisition.items():
            if signal_name_hint.lower() in name.lower():
                lfp_series = obj
                lfp_name = name
                break
        
        if lfp_series is None:
            raise RuntimeError(
                f"{BLOCKED_SIGNAL_SERIES_MISSING}: "
                f"No acquisition series matching '{signal_name_hint}'"
            )
        
        # Get sampling rate - try explicit rate first, then infer from timestamps
        fs = getattr(lfp_series, "rate", None)
        fs_inferred = False
        
        if fs is None:
            # Try to infer from timestamps
            timestamps = getattr(lfp_series, "timestamps", None)
            if timestamps is not None and len(timestamps) > 1:
                try:
                    # Sample first 1000 timestamps to estimate dt
                    ts_sample = timestamps[:min(1000, len(timestamps))]
                    dts = np.diff(ts_sample)
                    median_dt = np.median(dts)
                    
                    if median_dt > 0 and np.allclose(dts, median_dt, rtol=0.01):
                        # Regular sampling - infer rate
                        fs = 1.0 / median_dt
                        fs_inferred = True
                        warns.append(_warn(
                            "RATE_INFERRED_FROM_TIMESTAMPS",
                            f"Series '{lfp_name}' rate inferred from timestamps: {fs:.2f} Hz (dt={median_dt:.6f}s)"
                        ))
                except Exception:
                    pass
            
            if fs is None:
                raise RuntimeError(
                    f"{BLOCKED_SIGNAL_RATE_MISSING}: "
                    f"Series '{lfp_name}' lacks sampling rate and cannot be inferred from timestamps"
                )
        
        # Determine channel selection
        n_channels_total = lfp_series.data.shape[1] if hasattr(lfp_series.data, 'shape') else 0
        
        if "channel_indices" in channel_filter:
            channel_indices = np.array(channel_filter["channel_indices"])
        elif channel_map is not None and "area" in channel_filter:
            area = channel_filter["area"]
            channel_indices = channel_map[
                channel_map["area"] == area
            ]["channel_index_global"].values
        else:
            # Use all channels
            channel_indices = np.arange(n_channels_total)
        
        n_channels = len(channel_indices)
        
        # Convert window to samples
        pre_samples = int(window.pre_ms / 1000.0 * fs)
        post_samples = int(window.post_ms / 1000.0 * fs)
        n_time_samples = post_samples - pre_samples
        
        # Extract epochs per condition
        results: dict[str, np.ndarray] = {}
        
        for condition, onset_times_sec in event_vectors.items():
            n_trials = len(onset_times_sec)
            
            if n_trials == 0:
                results[condition] = np.zeros((0, n_channels, n_time_samples), dtype=np.float32)
                continue
            
            # Pre-allocate output
            epochs = np.zeros((n_trials, n_channels, n_time_samples), dtype=np.float32)
            
            # Extract each trial
            for trial_idx, onset_sec in enumerate(onset_times_sec):
                onset_sample = int(onset_sec * fs)
                start_sample = onset_sample + pre_samples
                end_sample = onset_sample + post_samples
                
                # Bounds check
                series_length = lfp_series.data.shape[0] if hasattr(lfp_series.data, 'shape') else 0
                if start_sample < 0 or end_sample > series_length:
                    warns.append(_warn(
                        BLOCKED_SIGNAL_WINDOW_OUT_OF_BOUNDS,
                        f"Trial {trial_idx} window [{start_sample}:{end_sample}] "
                        f"exceeds bounds [0:{series_length}]"
                    ))
                    # Fill with NaN for out-of-bounds
                    epochs[trial_idx, :, :] = np.nan
                    continue
                
                # Read bounded window for selected channels
                # Note: This assumes we can index the HDF5 dataset directly
                # For large extractions, consider chunking
                try:
                    data_slice = lfp_series.data[start_sample:end_sample, channel_indices]
                    epochs[trial_idx, :, :] = data_slice.T  # (time, channels) -> (channels, time)
                except Exception as e:
                    warns.append(_warn(
                        BLOCKED_UNSUPPORTED_SIGNAL_SHAPE,
                        f"Failed to read data for trial {trial_idx}: {e}"
                    ))
                    epochs[trial_idx, :, :] = np.nan
            
            results[condition] = epochs
        
        return results
        
    finally:
        if io is not None:
            io.close()


def get_muae_epochs(
    nwb_path: str | Path,
    event_vectors: dict[str, np.ndarray],
    window: WindowSpec,
    channel_map: pd.DataFrame | None = None,
    channel_filter: Mapping[str, Any] | None = None,
    signal_name_hint: str = "muae",
) -> dict[str, np.ndarray]:
    """Bounded MUAe (multi-unit activity envelope) epoch extraction.
    
    Same contract as get_lfp_epochs but for MUAe signal.
    
    Typed blocker:
    - BLOCKED_SIGNAL_SERIES_MISSING if MUAe not present in NWB
    
    Returns
    -------
    dict[str, np.ndarray] with shape (trials, channels, time)
        MUAe envelope in arbitrary units
    
    Note:
    - MUAe may not be present in all NWBs
    - Check acquisition names for "muae", "mua", "envelope"
    """
    try:
        return get_lfp_epochs(
            nwb_path=nwb_path,
            event_vectors=event_vectors,
            window=window,
            channel_map=channel_map,
            channel_filter=channel_filter,
            signal_name_hint=signal_name_hint,
        )
    except RuntimeError as e:
        if BLOCKED_SIGNAL_SERIES_MISSING in str(e):
            raise RuntimeError(
                f"{BLOCKED_SIGNAL_SERIES_MISSING}: "
                f"MUAe signal not found in NWB. "
                f"Tried hint '{signal_name_hint}'. "
                f"Original error: {e}"
            )
        raise
