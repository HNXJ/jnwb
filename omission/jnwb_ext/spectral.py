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


def to_db(ratio):
    """``10*log10(ratio)``, the single point every power-ratio-to-dB conversion should pass
    through -- the project's "log last" rule (CLAUDE.md tripwire #3: average power, divide by
    baseline, log exactly once). Promoted 2026-08-14 from four identical one-liners in
    context/figures/ scripts; this enforces the convention in one place instead of by
    convention alone at 10+ inline ``10*np.log10(...)`` call sites across jnwb and scripts.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(ratio)


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
                   Default: omission.jnwb_ext.connectivity.CANONICAL_BANDS — the settled
                   Omission set (theta 4-8, alpha 8-14, beta 14-30,
                   low_gamma 30-50, high_gamma 50-80).
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
        # INTENTIONAL BREAK (2026-08-04). The former default was the
        # pre-correction set (delta 1-4, alpha 8-12, beta 12-30, low_gamma 30-55,
        # high_gamma 55-90), which contradicts the settled band definitions in
        # CLAUDE.md that every fitted coefficient in outputs/lfp_band_census_v2/
        # uses. Band *names* are unchanged, so callers keyed by name keep working;
        # the *numbers* move: alpha widens (8-12 -> 8-14), beta narrows
        # (12-30 -> 14-30), low_gamma narrows (30-55 -> 30-50), high_gamma shifts
        # (55-90 -> 50-80), and delta is dropped because no project doctrine
        # defines its edges. Pass freq_bands= explicitly to reproduce old output.
        from .connectivity import CANONICAL_BANDS
        freq_bands = dict(CANONICAL_BANDS)

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
                
            p_val = (np.sum(np.array(surrogate_cohs) >= mean_coh_val) + 1) / (n_surr + 1)
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


def imaginary_coherency(
    x: np.ndarray,
    y: np.ndarray,
    sampling_rate: float,
    freq_range: Tuple[float, float],
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    device: str = 'cpu',
) -> Dict[str, float]:
    """
    Imaginary part of coherency (Nolte et al. 2004) between two continuous signals.

    Volume conduction and shared-reference artifacts mix into both channels at
    zero lag, which drives the REAL part of coherency without any true circuit
    interaction. The imaginary part is insensitive to zero-lag mixing by
    construction (a purely zero-lag-mixed pair has Im(Cxy) = 0 at every
    frequency), so it is the estimator this project's fig06/fig07 volume-
    conduction control requires -- see context/figures/lfp_lfp_connectivity_supplement/README.md (renamed twice 2026-08-04/05: originally fig06_band_power_coupling, then fig05_lfp_lfp_coupling, now this -- this analysis is its supp_lfp_lfp_coherency.py supplement; fig05 itself is now the area x band GLMM in fig05_v1_area_hierarchy_glmm/).
    Callers are responsible for re-referencing (see ``bipolar_reference`` /
    ``laplacian_reference``) before calling this; imaginary coherency controls
    for zero-lag mixing but does not substitute for reducing it upstream.

    Args:
        x, y: 1D time series of equal length, same sampling rate, already
            re-referenced (bipolar or Laplacian) to reduce shared-reference mixing.
        sampling_rate: Hz.
        freq_range: (min_freq, max_freq) in Hz to average coherency over.
        nperseg: Welch/CSD segment length; defaults to min(len(x), 1024).
        noverlap: defaults to nperseg // 2.
        device: 'cpu' or 'cuda' (CuPy), mirroring ``band_power``'s dispatch pattern.

    Returns:
        dict with:
          - ``icoh_mean``: signed mean of Im(Cxy(f)) across the band (can partially
            cancel across frequencies -- the standard Nolte et al. quantity).
          - ``icoh_abs_mean``: mean of |Im(Cxy(f))| across the band (never cancels;
            use when only coupling strength, not sign, is of interest).
          - ``coh_mag_mean``: mean magnitude-squared coherence across the band, for
            comparison -- large gap between this and icoh indicates the raw
            coherence is dominated by zero-lag (volume-conduction-like) mixing.
          - ``n_freqs``: number of frequency bins averaged.

    Validated against synthetic cases in scripts/validate_imaginary_coherency.py:
    a common zero-lag-mixed source drives coh_mag_mean up while icoh_mean stays
    near zero; a genuinely lagged shared source drives both up.
    """
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    n = min(len(x), len(y))
    if n == 0:
        return {"icoh_mean": 0.0, "icoh_abs_mean": 0.0, "coh_mag_mean": 0.0, "n_freqs": 0}
    x, y = x[:n], y[:n]

    if nperseg is None:
        nperseg = min(n, 1024)
    if noverlap is None:
        noverlap = nperseg // 2

    if device == 'cuda':
        try:
            freqs, pxx, pyy, sxy = _welch_csd_gpu(x, y, sampling_rate, nperseg, noverlap)
        except Exception as e:
            log.warning(f"GPU coherency failed: {e}. Falling back to CPU.")
            device = 'cpu'
    if device != 'cuda':
        freqs, pxx = signal.welch(x, fs=sampling_rate, nperseg=nperseg, noverlap=noverlap)
        _, pyy = signal.welch(y, fs=sampling_rate, nperseg=nperseg, noverlap=noverlap)
        _, sxy = signal.csd(x, y, fs=sampling_rate, nperseg=nperseg, noverlap=noverlap)

    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    if not np.any(mask):
        return {"icoh_mean": 0.0, "icoh_abs_mean": 0.0, "coh_mag_mean": 0.0, "n_freqs": 0}

    denom = np.sqrt(np.clip(pxx[mask] * pyy[mask], 1e-30, None))
    coherency = sxy[mask] / denom
    im_part = np.imag(coherency)
    coh_mag = np.abs(coherency) ** 2

    return {
        "icoh_mean": float(np.mean(im_part)),
        "icoh_abs_mean": float(np.mean(np.abs(im_part))),
        "coh_mag_mean": float(np.mean(coh_mag)),
        "n_freqs": int(np.sum(mask)),
    }


def bipolar_reference(channel_data: np.ndarray, channel_order: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Bipolar (adjacent-channel difference) re-reference along a probe's depth order.

    Each output channel i is ``data[order[i+1]] - data[order[i]]``, so a common
    signal present identically on adjacent contacts (shared reference, distant
    volume-conducted source) cancels; a genuine local generator does not.
    Output has one fewer channel than the input.

    Args:
        channel_data: (n_channels, n_samples) array, one row per electrode contact.
        channel_order: optional (n_channels,) index array giving depth order
            (shallow to deep or vice versa); defaults to row order as given.

    Returns:
        (n_channels - 1, n_samples) bipolar-referenced array.
    """
    channel_data = np.asarray(channel_data, dtype=float)
    if channel_data.ndim != 2:
        raise ValueError(f"channel_data must be 2D (n_channels, n_samples), got shape {channel_data.shape}")
    order = np.arange(channel_data.shape[0]) if channel_order is None else np.asarray(channel_order)
    ordered = channel_data[order]
    return ordered[1:] - ordered[:-1]


def laplacian_reference(channel_data: np.ndarray, channel_order: Optional[np.ndarray] = None) -> np.ndarray:
    """
    1D nearest-neighbor Laplacian re-reference along a probe's depth order.

    Each interior output channel i is ``data[order[i]] - mean(data[order[i-1]], data[order[i+1]])``.
    Like ``bipolar_reference``, this cancels signal shared identically across
    neighboring contacts (shared reference / distant volume conduction) while
    preserving a source local to one contact. Edge channels (first/last in
    ``channel_order``) use their single available neighbor instead of a two-
    neighbor mean.

    Args:
        channel_data: (n_channels, n_samples) array, one row per electrode contact.
        channel_order: optional (n_channels,) index array giving depth order;
            defaults to row order as given.

    Returns:
        (n_channels, n_samples) Laplacian-referenced array, same channel count
        as input (unlike ``bipolar_reference``, which drops one channel).
    """
    channel_data = np.asarray(channel_data, dtype=float)
    if channel_data.ndim != 2:
        raise ValueError(f"channel_data must be 2D (n_channels, n_samples), got shape {channel_data.shape}")
    order = np.arange(channel_data.shape[0]) if channel_order is None else np.asarray(channel_order)
    ordered = channel_data[order]
    n_ch = ordered.shape[0]
    out = np.empty_like(ordered)
    for i in range(n_ch):
        if i == 0:
            neighbor_mean = ordered[1] if n_ch > 1 else ordered[0]
        elif i == n_ch - 1:
            neighbor_mean = ordered[i - 1]
        else:
            neighbor_mean = 0.5 * (ordered[i - 1] + ordered[i + 1])
        out[i] = ordered[i] - neighbor_mean
    # Result is in `order` order; un-permute back to original channel positions.
    result = np.empty_like(out)
    result[order] = out
    return result


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
