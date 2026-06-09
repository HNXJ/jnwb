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

def compute_multitaper_tfr(
    data: np.ndarray, 
    fs: float = FS_LFP, 
    freqs: np.ndarray = np.arange(4, 81, 2), 
    n_cycles: float | np.ndarray = 7
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
    for i in range(0, n_trials, batch_size):
        batch = data[i:i+batch_size]
        batch_power = tfr_array_multitaper(batch, sfreq=fs, freqs=freqs, n_cycles=7, 
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
