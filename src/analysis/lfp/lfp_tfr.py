# -*- coding: utf-8 -*-
"""
lfp_tfr.py - Canonical Multitaper TFR Engine
Implements trial-preserved high-fidelity spectral analysis.
"""
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np
import mne
from mne.time_frequency import tfr_array_multitaper
from src.analysis.lfp.lfp_constants import FS_LFP, BANDS

def default_band_time_support_ms(band_name: str) -> float:
    """Default effective time support per band (ms).

    Goal: low-frequency (Theta) estimates require longer support than
    alpha/beta/gamma to avoid unstable power estimates.
    """
    # Project-specific bands currently available: Theta/Alpha/l-beta/h-beta/Gamma_L/Gamma_H.
    # Theta is treated as the "low-frequency" stable branch.
    if band_name == "Theta":
        return 1200.0  # ~3-9 cycles for 3-7 Hz (enough for stability)
    if band_name in ("Alpha", "Beta", "l-beta", "h-beta"):
        return 200.0
    if band_name in ("Gamma", "Gamma_L", "Gamma_H"):
        return 150.0
    # Fallback (short support)
    return 200.0


def n_cycles_for_freqs(
    freqs: np.ndarray,
    *,
    band_time_support_ms: dict[str, float] | None = None,
    bands: dict[str, Tuple[int, int]] | None = None,
) -> np.ndarray:
    """Compute frequency-dependent multitaper `n_cycles` values.

    MNE's multitaper TFR uses `n_cycles` to control effective time support.
    We implement a band-dependent policy by assigning each frequency f a
    desired effective window length and setting:

        n_cycles(f) = (window_seconds) * f

    Args:
        freqs: Frequencies in Hz (array of shape (n_freqs,))
        band_time_support_ms: Optional mapping band -> effective time support (ms)
        bands: Optional mapping band -> (fmin, fmax)

    Returns:
        Array of shape (n_freqs,) with float `n_cycles` per frequency.
    """
    if bands is None:
        bands = BANDS
    if band_time_support_ms is None:
        band_time_support_ms = {}

    freqs = np.asarray(freqs, dtype=float)
    n_cycles = np.empty_like(freqs, dtype=float)

    # Default support if a frequency doesn't land in any defined band.
    default_support_ms = 200.0

    for i, f in enumerate(freqs):
        assigned = False
        for band_name, (fmin, fmax) in bands.items():
            if (f >= fmin) and (f <= fmax):
                support_ms = band_time_support_ms.get(band_name)  # may be None
                if support_ms is None:
                    support_ms = default_band_time_support_ms(band_name)
                window_s = support_ms / 1000.0
                n_cycles[i] = window_s * f
                assigned = True
                break
        if not assigned:
            window_s = default_support_ms / 1000.0
            n_cycles[i] = window_s * f

    # Safety clamp: too-small n_cycles can undercut low-frequency stability.
    n_cycles = np.clip(n_cycles, 2.0, 20.0)
    return n_cycles

def compute_multitaper_tfr(
    data: np.ndarray, 
    fs: float = FS_LFP, 
    freqs: np.ndarray = np.arange(4, 81, 2), 
    n_cycles: float | np.ndarray = 7,
    *,
    use_band_dependent_n_cycles: bool = False,
    band_time_support_ms: dict[str, float] | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes TFR using multitaper. Returns linear power.
    data shape: (trials, channels, time)
    Returns: freqs, times_ms, power (trials, channels, freqs, times)
    """
    if data.ndim == 2:
        data = data[None, :, :]
    data = data.astype(np.float64)
    
    n_trials, n_ch, n_times = data.shape
    # To save memory, we process one channel at a time if many channels exist
    # and use a small trial batch size.
    
    # Pre-allocate if possible, but TFR is huge. 
    # Let's just use the batching logic but keep it tight.
    batch_size = 8 # Reduced batch size
    power_list = []
    
    if use_band_dependent_n_cycles:
        n_cycles = n_cycles_for_freqs(freqs, band_time_support_ms=band_time_support_ms)

    for i in range(0, n_trials, batch_size):
        batch = data[i:i+batch_size]
        # tfr_array_multitaper returns (n_trials, n_channels, n_freqs, n_times)
        batch_power = tfr_array_multitaper(batch, sfreq=fs, freqs=freqs, n_cycles=n_cycles, 
                                     output='power', use_fft=True, verbose=False, n_jobs=1)
        power_list.append(batch_power.astype(np.float32)) # Use float32 to save 50% memory
        
    power = np.concatenate(power_list, axis=0)
    times_ms = np.linspace(0, n_times/fs*1000, n_times)
    return freqs, times_ms, power

def compute_band_power_efficiently(data, fs=FS_LFP, freqs=None, bands=None):
    """
    Computes band power without ever storing the full 4D TFR.
    
    Parameters
    ----------
    data : np.ndarray
        Input data (trials, channels, time)
    fs : float
        Sampling frequency in Hz
    freqs : np.ndarray | None
        Frequencies to compute. If None, uses np.arange(4, 81, 2)
    bands : dict | None
        Band definitions {name: (fmin, fmax)}. If None, uses default BANDS.
    
    Returns
    -------
    freqs, times_ms, band_results
    """
    if freqs is None:
        freqs = np.arange(4, 81, 2)
    
    if bands is None:
        bands = BANDS
    
    n_trials, n_ch, n_times = data.shape
    band_results = {band: np.zeros((n_trials, n_ch, n_times), dtype=np.float32) for band in bands}
    
    batch_size = 4

    # Optional: use band-dependent effective time support by converting to
    # a frequency-dependent `n_cycles` array.
    n_cycles = 7
    # If callers pass custom bands, keep policy consistent with available band names.
    use_band_dependent = True
    if use_band_dependent:
        n_cycles = n_cycles_for_freqs(freqs, band_time_support_ms=None, bands=bands)
    for i in range(0, n_trials, batch_size):
        batch = data[i:i+batch_size]
        batch_power = tfr_array_multitaper(batch, sfreq=fs, freqs=freqs, n_cycles=n_cycles, 
                                     output='power', use_fft=True, verbose=False, n_jobs=1)
        
        for band, (fmin, fmax) in bands.items():
            mask = (freqs >= fmin) & (freqs <= fmax)
            if not np.any(mask):
                # No frequencies match this band - leave as zeros but warn
                continue
            # Average over frequencies and store in float32
            band_results[band][i:i+batch_size] = np.mean(batch_power[:, :, mask, :], axis=2).astype(np.float32)
            
    times_ms = np.linspace(0, n_times/fs*1000, n_times)
    return freqs, times_ms, band_results

# Alias for compatibility with legacy and user scripts
compute_tfr = compute_multitaper_tfr

def get_band_power(freqs: np.ndarray, power: np.ndarray, band_limits: Tuple[int, int]) -> np.ndarray:
    mask = (freqs >= band_limits[0]) & (freqs <= band_limits[1])
    return np.nanmean(power[..., mask, :], axis=-2)

def collapse_band_power(freqs: np.ndarray, power: np.ndarray) -> Dict[str, np.ndarray]:
    out: Dict[str, np.ndarray] = {}
    for band, lims in BANDS.items():
        out[band] = get_band_power(freqs, power, lims)
    return out
