"""
Spectral Analysis: Band-Limited Oscillations and Cross-Area Coherence

New orthogonal jnwb module for spectral/oscillatory analysis.
Consolidates advanced spectral functions from archived Y-files:
- harmonic/ folder
- coherence/ folder
- spectral_relations_pipeline (selected methods)

Provides functions for analyzing frequency-band specific activity,
cross-area synchronization, and spectral hierarchy.

Author: New jnwb module
Date: 2026-06-25
"""

import logging
from typing import Dict, Optional, Tuple, Union
import numpy as np
from scipy import signal, stats
import pandas as pd

log = logging.getLogger(__name__)


def harmonic_analysis(
    lfp_trace: np.ndarray,
    sampling_rate: float,
    freq_range: Tuple[float, float] = (1.0, 90.0),
    harmonic_orders: int = 3,
    device: str = 'cpu'
) -> Dict:
    """
    Decompose LFP trace into fundamental and harmonic components.

    Identifies dominant frequency and its harmonics, useful for understanding
    multi-scale oscillatory structure (e.g., theta and theta harmonics).

    Args:
        lfp_trace: Time series data (1D array, voltage)
        sampling_rate: Sampling frequency (Hz)
        freq_range: (min, max) frequency bounds for analysis (Hz)
        harmonic_orders: Number of harmonic multiples to track
        device: 'cpu' or 'cuda' (GPU acceleration via CuPy)

    Returns:
        Dict with:
        - fundamental_freq: Dominant frequency (Hz)
        - harmonics: {order: (freq, power)} for orders 1-N
        - spectral_profile: Full power spectrum
        - frequencies: Frequency bins for spectrum
        - harmonic_ratio: Power ratio (fundamental / sum of harmonics)

    Example:
        >>> analysis = harmonic_analysis(lfp_data, sampling_rate=1000.0)
        >>> print(f"Theta fundamental: {analysis['fundamental_freq']:.1f} Hz")
    """
    result = {
        'fundamental_freq': 0.0,
        'harmonics': {},
        'spectral_profile': np.array([]),
        'frequencies': np.array([]),
        'harmonic_ratio': 0.0,
    }

    if len(lfp_trace) == 0:
        return result

    # Compute power spectrum
    if device == 'cuda':
        try:
            frequencies, pxx, _, _ = _welch_csd_gpu(lfp_trace, lfp_trace, sampling_rate, min(len(lfp_trace), 4096))
        except Exception as e:
            log.warning(f"GPU welch failed: {e}. Falling back to CPU.")
            frequencies, pxx = signal.welch(
                lfp_trace,
                fs=sampling_rate,
                window='hann',
                nperseg=min(len(lfp_trace), 4096),
                noverlap=None
            )
    else:
        frequencies, pxx = signal.welch(
            lfp_trace,
            fs=sampling_rate,
            window='hann',
            nperseg=min(len(lfp_trace), 4096),
            noverlap=None
        )

    result['frequencies'] = frequencies
    result['spectral_profile'] = pxx

    # Filter to frequency range
    mask = (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    freqs_range = frequencies[mask]
    pxx_range = pxx[mask]

    if len(pxx_range) == 0:
        return result

    # Find fundamental (peak in range)
    peak_idx = np.argmax(pxx_range)
    fundamental_freq = freqs_range[peak_idx]
    result['fundamental_freq'] = float(fundamental_freq)

    # Find harmonics
    tolerance = fundamental_freq * 0.1  # ±10% tolerance
    fundamental_power = pxx_range[peak_idx]

    for order in range(1, harmonic_orders + 1):
        harmonic_freq = fundamental_freq * order
        if harmonic_freq <= freq_range[1]:
            # Find peak near harmonic frequency
            harmonic_mask = np.abs(freqs_range - harmonic_freq) < tolerance
            if np.any(harmonic_mask):
                harmonic_idx = np.argmax(pxx_range[harmonic_mask])
                harmonic_freqs = freqs_range[harmonic_mask]
                harmonic_power = pxx_range[harmonic_mask][harmonic_idx]

                result['harmonics'][order] = {
                    'freq': float(harmonic_freqs[harmonic_idx]),
                    'power': float(harmonic_power),
                    'relative_power': float(harmonic_power / fundamental_power) if fundamental_power > 0 else 0.0
                }

    # Harmonic ratio (fundamental vs. harmonics)
    if len(result['harmonics']) > 0:
        total_harmonic_power = sum(h['power'] for h in result['harmonics'].values() if 'power' in h)
        if total_harmonic_power > 0:
            result['harmonic_ratio'] = float(fundamental_power / (fundamental_power + total_harmonic_power))

    return result


def cross_area_coherence(
    lfp_area1: np.ndarray,
    lfp_area2: np.ndarray,
    sampling_rate: float,
    freq_bands: Optional[Dict[str, Tuple[float, float]]] = None,
    device: str = 'cpu'
) -> Dict:
    """
    Compute frequency-resolved coherence between two LFP signals.

    Coherence quantifies phase synchronization between areas across frequencies.
    High coherence = strong coupling; low coherence = weak coupling.

    Args:
        lfp_area1: Time series from area 1
        lfp_area2: Time series from area 2
        sampling_rate: Sampling frequency (Hz)
        freq_bands: Dict of {'band_name': (freq_min, freq_max)}
                   Default: Standard frequency bands (delta, theta, alpha, beta, gamma)
        device: 'cpu' or 'cuda' (GPU acceleration via CuPy)

    Returns:
        Dict with:
        - coherence_spectrum: Coherence at each frequency
        - frequencies: Frequency bins
        - band_coherence: {band_name: mean_coherence, ...}
        - band_significance: {band_name: p_value, ...}
        - peak_coherence_freq: Frequency with highest coherence (Hz)

    Example:
        >>> coh = cross_area_coherence(v1_lfp, pfc_lfp, sampling_rate=1000.0)
        >>> print(f"Alpha coherence: {coh['band_coherence']['alpha']:.3f}")
    """
    if freq_bands is None:
        freq_bands = {
            'delta': (1, 4),
            'theta': (4, 8),
            'alpha': (8, 12),
            'beta': (12, 30),
            'low_gamma': (30, 55),
            'high_gamma': (55, 90),
        }

    result = {
        'coherence_spectrum': np.array([]),
        'frequencies': np.array([]),
        'band_coherence': {},
        'band_significance': {},
        'peak_coherence_freq': 0.0,
        'peak_coherence_value': 0.0,
    }

    if len(lfp_area1) != len(lfp_area2):
        log.warning("LFP traces have different lengths")
        return result

    # Compute coherence
    if device == 'cuda':
        try:
            frequencies, psd_x, psd_y, csd_xy = _welch_csd_gpu(
                lfp_area1, lfp_area2, sampling_rate, min(len(lfp_area1), 4096)
            )
            # Avoid division by zero
            denom = psd_x * psd_y
            coherency = np.zeros_like(csd_xy, dtype=float)
            mask = denom > 0
            coherency[mask] = np.abs(csd_xy[mask]) ** 2 / denom[mask]
        except Exception as e:
            log.warning(f"GPU coherence failed: {e}. Falling back to CPU.")
            frequencies, coherency = signal.coherence(
                lfp_area1,
                lfp_area2,
                fs=sampling_rate,
                nperseg=min(len(lfp_area1), 4096),
                noverlap=None
            )
    else:
        frequencies, coherency = signal.coherence(
            lfp_area1,
            lfp_area2,
            fs=sampling_rate,
            nperseg=min(len(lfp_area1), 4096),
            noverlap=None
        )

    result['frequencies'] = frequencies
    result['coherence_spectrum'] = coherency

    # Peak coherence
    peak_idx = np.argmax(coherency)
    result['peak_coherence_freq'] = float(frequencies[peak_idx])
    result['peak_coherence_value'] = float(coherency[peak_idx])

    # Band-specific coherence
    for band_name, (fmin, fmax) in freq_bands.items():
        mask = (frequencies >= fmin) & (frequencies <= fmax)
        if np.any(mask):
            band_coh = coherency[mask]
            result['band_coherence'][band_name] = float(np.mean(band_coh))

            # Significance test: compare to surrogate (phase-randomized/shuffled) coherence
            surrogate_cohs = []
            rng = np.random.default_rng(42)
            n_surr = 50
            if len(lfp_area1) > 50000:
                n_surr = 10
            
            mean_coh_val = np.mean(band_coh)
            
            # Fast surrogate: circularly shift lfp_area2 and recompute coherence
            for _ in range(n_surr):
                low_val = 1
                high_val = len(lfp_area2) - 1
                shift = rng.integers(low_val, high_val) if low_val < high_val else 0
                lfp_y_shuffled = np.roll(lfp_area2, shift)
                if device == 'cuda':
                    try:
                        _, psd_x_shuf, psd_y_shuf, csd_xy_shuf = _welch_csd_gpu(
                            lfp_area1, lfp_y_shuffled, sampling_rate, min(len(lfp_area1), 4096)
                        )
                        denom_shuf = psd_x_shuf * psd_y_shuf
                        coh_shuf = np.zeros_like(csd_xy_shuf, dtype=float)
                        shuf_mask = denom_shuf > 0
                        coh_shuf[shuf_mask] = np.abs(csd_xy_shuf[shuf_mask]) ** 2 / denom_shuf[shuf_mask]
                    except Exception:
                        _, coh_shuf = signal.coherence(lfp_area1, lfp_y_shuffled, fs=sampling_rate, nperseg=min(len(lfp_area1), 4096), noverlap=None)
                else:
                    _, coh_shuf = signal.coherence(lfp_area1, lfp_y_shuffled, fs=sampling_rate, nperseg=min(len(lfp_area1), 4096), noverlap=None)
                
                band_coh_shuf = coh_shuf[mask] if len(coh_shuf) > 0 else np.array([0.0])
                surrogate_cohs.append(np.mean(band_coh_shuf))
                
            p_val = np.sum(np.array(surrogate_cohs) >= mean_coh_val) / n_surr
            result['band_significance'][band_name] = float(p_val)

    return result


def spectral_tilt(
    lfp_trace: np.ndarray,
    sampling_rate: float,
    freq_range: Tuple[float, float] = (1.0, 100.0),
    device: str = 'cpu'
) -> Dict:
    """
    Analyze 1/f spectral tilt (aperiodic component).

    The aperiodic (1/f) slope reflects broadband neural activity and is useful
    for understanding general network state (higher slope = more high-frequency content).

    Args:
        lfp_trace: Time series data
        sampling_rate: Sampling frequency (Hz)
        freq_range: Frequency range for fitting
        device: 'cpu' or 'cuda' (GPU acceleration via CuPy)

    Returns:
        Dict with:
        - exponent: 1/f exponent (slope, negative value)
        - offset: Power at 1 Hz (intercept)
        - fit_quality: R-squared of fit

    Example:
        >>> tilt = spectral_tilt(lfp_data, sampling_rate=1000.0)
        >>> print(f"Spectral exponent: {tilt['exponent']:.2f}")
    """
    result = {
        'exponent': 0.0,
        'offset': 0.0,
        'fit_quality': 0.0,
    }

    if len(lfp_trace) == 0:
        return result

    # Compute power spectrum
    if device == 'cuda':
        try:
            frequencies, pxx, _, _ = _welch_csd_gpu(lfp_trace, lfp_trace, sampling_rate, min(len(lfp_trace), 4096))
        except Exception as e:
            log.warning(f"GPU welch failed: {e}. Falling back to CPU.")
            frequencies, pxx = signal.welch(
                lfp_trace,
                fs=sampling_rate,
                nperseg=min(len(lfp_trace), 4096)
            )
    else:
        frequencies, pxx = signal.welch(
            lfp_trace,
            fs=sampling_rate,
            nperseg=min(len(lfp_trace), 4096)
        )

    # Filter to range and remove DC
    mask = (frequencies > 0.5) & (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    freqs = frequencies[mask]
    pxx_db = 10 * np.log10(pxx[mask])

    if len(freqs) < 2:
        return result

    # Fit 1/f slope on log-log scale
    # Power = Offset * f^exponent
    # log(Power) = log(Offset) + exponent * log(freq)
    log_freqs = np.log10(freqs)
    log_power = np.log10(pxx[mask])

    # Linear regression
    coeffs = np.polyfit(log_freqs, log_power, 1)
    exponent = coeffs[0]
    offset_log = coeffs[1]

    result['exponent'] = float(exponent)
    result['offset'] = float(10 ** offset_log)

    # Fit quality (R-squared)
    fitted = np.polyval(coeffs, log_freqs)
    ss_res = np.sum((log_power - fitted) ** 2)
    ss_tot = np.sum((log_power - np.mean(log_power)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    result['fit_quality'] = float(r_squared)

    return result


def band_power(
    lfp_trace: np.ndarray,
    sampling_rate: float,
    freq_range: Tuple[float, float],
    normalize: bool = True,
    baseline: Optional[np.ndarray] = None,
    device: str = 'cpu'
) -> float:
    """
    Compute power in a frequency band.

    Args:
        lfp_trace: Time series data
        sampling_rate: Sampling frequency (Hz)
        freq_range: (min_freq, max_freq) in Hz
        normalize: If True, return as dB relative to baseline
        baseline: Baseline time series for normalization (optional)
        device: 'cpu' or 'cuda' (GPU acceleration via CuPy)

    Returns:
        Power in band (units depend on normalize flag)

    Example:
        >>> theta_power = band_power(lfp_data, 1000.0, (4, 8))
        >>> baseline_power = band_power(baseline_lfp, 1000.0, (4, 8), normalize=False)
        >>> normalized_power = band_power(lfp_data, 1000.0, (4, 8), baseline=baseline_lfp)
    """
    if len(lfp_trace) == 0:
        return 0.0

    # Compute power spectrum
    if device == 'cuda':
        try:
            frequencies, pxx, _, _ = _welch_csd_gpu(lfp_trace, lfp_trace, sampling_rate, min(len(lfp_trace), 4096))
        except Exception as e:
            log.warning(f"GPU welch failed: {e}. Falling back to CPU.")
            frequencies, pxx = signal.welch(
                lfp_trace,
                fs=sampling_rate,
                nperseg=min(len(lfp_trace), 4096)
            )
    else:
        frequencies, pxx = signal.welch(
            lfp_trace,
            fs=sampling_rate,
            nperseg=min(len(lfp_trace), 4096)
        )

    # Extract band
    mask = (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    band_power_val = np.mean(pxx[mask]) if np.any(mask) else 0.0

    # Normalize to baseline if provided
    if normalize and baseline is not None and len(baseline) > 0:
        if device == 'cuda':
            try:
                _, baseline_pxx, _, _ = _welch_csd_gpu(baseline, baseline, sampling_rate, min(len(baseline), 4096))
            except Exception as e:
                log.warning(f"GPU baseline welch failed: {e}. Falling back to CPU.")
                _, baseline_pxx = signal.welch(
                    baseline,
                    fs=sampling_rate,
                    nperseg=min(len(baseline), 4096)
                )
        else:
            _, baseline_pxx = signal.welch(
                baseline,
                fs=sampling_rate,
                nperseg=min(len(baseline), 4096)
            )
        baseline_power_val = np.mean(baseline_pxx[mask]) if np.any(mask) else 1.0

        if baseline_power_val > 0:
            band_power_val = 10 * np.log10(band_power_val / baseline_power_val)

    return float(band_power_val)


def _welch_csd_gpu(x: np.ndarray, y: np.ndarray, fs: float, nperseg: int, noverlap: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Helper to compute PSD and CSD on GPU using CuPy."""
    import cupy as cp
    if noverlap is None:
        noverlap = nperseg // 2
    step = nperseg - noverlap

    x_g = cp.asarray(x)
    y_g = cp.asarray(y)
    n = len(x_g)

    window = cp.hanning(nperseg)
    U = cp.sum(window ** 2) / fs

    segments_x = []
    segments_y = []
    start = 0
    while start + nperseg <= n:
        segments_x.append(x_g[start:start+nperseg] * window)
        segments_y.append(y_g[start:start+nperseg] * window)
        start += step

    if not segments_x:
        segments_x.append(x_g[:nperseg] * window[:len(x_g)])
        segments_y.append(y_g[:nperseg] * window[:len(y_g)])

    X = cp.fft.rfft(cp.stack(segments_x), axis=-1)
    Y = cp.fft.rfft(cp.stack(segments_y), axis=-1)

    scale = 1.0 / (fs * cp.sum(window ** 2))

    psd_x = cp.mean(cp.abs(X) ** 2, axis=0) * scale
    psd_y = cp.mean(cp.abs(Y) ** 2, axis=0) * scale
    csd_xy = cp.mean(X * cp.conj(Y), axis=0) * scale

    # One-sided scaling
    psd_x[1:-1] *= 2.0
    psd_y[1:-1] *= 2.0
    csd_xy[1:-1] *= 2.0

    freqs = cp.fft.rfftfreq(nperseg, d=1.0/fs)
    return freqs.get(), psd_x.get(), psd_y.get(), csd_xy.get()
