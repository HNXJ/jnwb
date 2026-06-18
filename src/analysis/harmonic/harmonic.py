"""
harmonic.py
===========
Core primitives for LFP-to-LFP and Spiking-to-LFP Harmonic Analysis.
"""

import numpy as np
import scipy.signal as signal
from scipy.signal import hilbert, butter, filtfilt
import pandas as pd
from src.analysis.lfp.stats import compute_modulation_index

def detect_high_snr_channels(metadata_csv: str, snr_threshold: float = 1.5) -> pd.DataFrame:
    """
    Read grand_unit_metadata.csv and return a DataFrame of channels
    where the maximum recorded stable unit SNR is >= snr_threshold.
    """
    df = pd.read_csv(metadata_csv)
    # Filter stable only
    stable = df[df["is_stable"]].copy()
    if len(stable) == 0:
        return pd.DataFrame(columns=["session_id", "peak_channel_global", "max_snr", "area", "layer"])
        
    # Group by session and peak_channel_global
    grouped = stable.groupby(["session_id", "peak_channel_global"]).agg({
        "snr": "max",
        "area": "first",
        "layer": "first"
    }).reset_index()
    
    # Filter by SNR threshold
    high_snr = grouped[grouped["snr"] >= snr_threshold].copy()
    high_snr = high_snr.rename(columns={"snr": "max_snr"})
    return high_snr

def get_bandpass_phase(data: np.ndarray, fs: float, lowcut: float, highcut: float) -> np.ndarray:
    """Extract instantaneous phase using Butterworth bandpass + Hilbert transform."""
    nyq = 0.5 * fs
    b, a = butter(4, [lowcut/nyq, highcut/nyq], btype='band')
    filtered = filtfilt(b, a, data, axis=-1)
    phase = np.angle(hilbert(filtered, axis=-1))
    return phase

def get_bandpass_amplitude(data: np.ndarray, fs: float, lowcut: float, highcut: float) -> np.ndarray:
    """Extract instantaneous amplitude envelope using Butterworth bandpass + Hilbert transform."""
    nyq = 0.5 * fs
    b, a = butter(4, [lowcut/nyq, highcut/nyq], btype='band')
    filtered = filtfilt(b, a, data, axis=-1)
    amplitude = np.abs(hilbert(filtered, axis=-1))
    return amplitude

def compute_nm_phase_coupling(phase_low: np.ndarray, phase_high: np.ndarray, n: int = 1, m: int = 2) -> float:
    """
    Computes n:m phase synchronization value (PLV_n,m).
    PLV_n,m = | < e^{i(n * phi_low - m * phi_high)} > |
    """
    # Compute phase difference
    phase_diff = n * phase_low - m * phase_high
    # Compute average vector length
    plv = np.abs(np.mean(np.exp(1j * phase_diff)))
    return float(plv)

def compute_spk_lfp_plv(spike_times: np.ndarray, lfp_phase: np.ndarray, lfp_timestamps: np.ndarray) -> float:
    """
    Computes Spike-LFP Phase Locking Value for a single unit.
    For each spike time, interpolates the LFP phase at that time, and computes PLV.
    """
    if len(spike_times) == 0 or len(lfp_phase) == 0:
        return 0.0
        
    # Unroll phase to interpolate correctly
    unrolled_phase = np.unwrap(lfp_phase)
    
    # Interpolate LFP phase at spike times
    spike_phases = np.interp(spike_times, lfp_timestamps, unrolled_phase)
    
    # Convert back to [-pi, pi]
    spike_phases_wrapped = (spike_phases + np.pi) % (2 * np.pi) - np.pi
    
    # Compute PLV
    plv = np.abs(np.mean(np.exp(1j * spike_phases_wrapped)))
    return float(plv)
