"""
jnwb.spectral -- generic spectral/oscillatory analysis: band-limited power, cross-area
coherence, 1/f tilt, imaginary coherency, and re-referencing, for any LFP time series.

PROMOTED 2026-08-23 from omission.jnwb_ext.spectral (99%-jnwb-sufficiency normalization): all
functions take plain time-series arrays and generic keyword parameters, with no omission-task
conditions/classes anywhere. CANONICAL_BANDS below is the single-source-of-truth band-edge
default (moved here from omission.jnwb_ext.connectivity, which now re-exports it rather than
defining a second copy -- see that module's own docstring note "no second, pre-correction
copy"); the band edges (theta/alpha/beta/gamma) are the standard neuroscience convention this
corpus settled on, not omission-specific values, and remain fully overridable via the
freq_bands= parameter.

Originally: new orthogonal jnwb module for spectral/oscillatory analysis, consolidating
advanced spectral functions from archived Y-files:
- harmonic/ folder
- coherence/ folder
- spectral_relations_pipeline (selected methods)

Provides functions for analyzing frequency-band specific activity,
cross-area synchronization, and spectral hierarchy.

Author: New jnwb module
Date: 2026-06-25
"""

import logging
import warnings
from typing import Dict, Optional, Tuple, Union
import numpy as np
from scipy import signal, stats
import pandas as pd

from ._backend import CUDA, resolve_device, warn_device_fallback
from ._parallel import parallel_map

log = logging.getLogger(__name__)

#: Settled band edges (Hz) -- standard neuroscience convention, not omission-specific.
#: Single source of truth: omission.jnwb_ext.connectivity.CANONICAL_BANDS re-exports this
#: constant rather than defining a second copy (see that module's docstring).
CANONICAL_BANDS: Dict[str, Tuple[float, float]] = {
    "theta": (4.0, 8.0),
    "alpha": (8.0, 14.0),
    "beta": (14.0, 30.0),
    "low_gamma": (30.0, 50.0),
    "high_gamma": (50.0, 80.0),
}


def _resolve_fs(
    fs: Optional[float] = None,
    sampling_rate: Optional[float] = None,
    func_name: str = "function",
) -> float:
    """Resolve sampling rate from canonical `fs` or legacy alias `sampling_rate`."""
    if fs is not None and sampling_rate is not None:
        if fs != sampling_rate:
            raise ValueError(
                f"Conflicting values provided to {func_name}: fs={fs}, sampling_rate={sampling_rate}. "
                "Specify only one (prefer fs)."
            )
        return float(fs)
    if fs is not None:
        return float(fs)
    if sampling_rate is not None:
        return float(sampling_rate)
    raise ValueError(f"{func_name} requires sampling rate `fs` (in Hz).")


def to_db(ratio):
    """``10*log10(ratio)``, the single point every power-ratio-to-dB conversion should pass
    through -- the project's "log last" rule (CLAUDE.md tripwire #3: average power, divide by
    baseline, log exactly once). Promoted 2026-08-14 from four identical one-liners in
    context/figures/ scripts; this enforces the convention in one place instead of by
    convention alone at 10+ inline ``10*np.log10(...)`` call sites across jnwb and scripts.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(ratio)


#: Accepted aggregation estimands for :func:`aggregate_to_db`. These are genuinely different
#: estimands, not implementation details, which is why the caller must name one:
#: ``sum_c P_c / sum_c P0_c == sum_c w_c (P_c / P0_c)`` with ``w_c = P0_c / sum_j P0_j`` --
#: i.e. "ratio_of_means" is a baseline-power-weighted average of the very same per-unit ratios
#: that "mean_of_ratios" weights equally. A quiet default would silently pick one for the caller.
DB_AGGREGATIONS = ("mean_of_ratios", "ratio_of_means")


def aggregate_to_db(
    power,
    baseline,
    *,
    how: str,
    aggregate_over=None,
    nan_policy: str = "propagate",
):
    """Form a power ratio, aggregate on the RATIO scale, and take ``10*log10`` exactly once.

    This is the enforcing form of :func:`to_db`. ``to_db`` is a bare conversion: it cannot stop
    a caller who already holds decibels from averaging them. Averaging decibels is a Jensen
    error -- ``mean(log x) != log(mean x)`` -- and it biases every unit by its own noisiness,
    which is the failure CLAUDE.md tripwire 2 ("take the logarithm last") exists to prevent.
    Stating the rule did not prevent it; this function makes the correct order the only order
    reachable through the API.

    Args:
        power: signal-interval power, ratio-scale and non-negative. Any shape.
        baseline: baseline power for the same units, broadcastable against ``power``.
        how: which estimand to form, named explicitly -- no default. ``"mean_of_ratios"``
            weights every unit equally; ``"ratio_of_means"`` weights each unit by its own
            baseline power (see :data:`DB_AGGREGATIONS`). Geometric mean is deliberately not
            offered: ``10*log10(geomean(r)) == mean(10*log10(r))`` identically, so it is
            mean-of-decibels -- the defect itself -- under a respectable name.
        aggregate_over: axis or tuple of axes to aggregate the ratios over. ``None`` performs
            no aggregation and simply converts the elementwise ratio, still logging once.
        nan_policy: ``"propagate"`` (default) or ``"omit"`` to aggregate over non-NaN entries
            only. Artifact repair legitimately leaves NaNs behind, so omitting is a real
            choice -- but it is never the silent one.

    Returns:
        Decibel array, reduced along ``aggregate_over``.

    Raises:
        ValueError: if ``how`` or ``nan_policy`` is not recognised, or if any input is
            negative. The negativity check is the dB-input tripwire: a ratio-scale power is
            non-negative by definition, whereas decibel arrays routinely carry negative
            values, so passing decibels in here fails loudly instead of computing a plausible
            wrong number. It is a guard, not a proof -- an all-positive dB array cannot be
            distinguished from power by inspection, so the contract remains: pass power.

    Example:
        >>> import numpy as np
        >>> p = np.array([[2.0, 4.0], [8.0, 4.0]])   # (units, trials)
        >>> b = np.array([[1.0, 1.0], [2.0, 2.0]])
        >>> float(aggregate_to_db(p, b, how="mean_of_ratios", aggregate_over=None)[0, 0])
        3.0102999566398116
    """
    if how not in DB_AGGREGATIONS:
        if str(how).lower() in ("geometric", "geomean", "geometric_mean"):
            raise ValueError(
                "how='geometric' is deliberately unsupported: 10*log10(geomean(r)) is "
                "identically mean(10*log10(r)), i.e. averaging decibels -- the exact defect "
                f"this function exists to prevent. Choose one of {list(DB_AGGREGATIONS)}."
            )
        raise ValueError(f"how must be one of {list(DB_AGGREGATIONS)}; got {how!r}")
    if nan_policy not in ("propagate", "omit"):
        raise ValueError(f"nan_policy must be 'propagate' or 'omit'; got {nan_policy!r}")

    p = np.asarray(power, dtype=float)
    b = np.asarray(baseline, dtype=float)
    for name, arr in (("power", p), ("baseline", b)):
        if arr.size and np.any(arr < 0):
            raise ValueError(
                f"{name} contains negative values, so it is not ratio-scale power. If these "
                "are already decibels, do not aggregate them: pass the underlying power and "
                "baseline and let this function take the logarithm last."
            )

    mean = np.nanmean if nan_policy == "omit" else np.mean
    total = np.nansum if nan_policy == "omit" else np.sum

    with np.errstate(divide="ignore", invalid="ignore"):
        if aggregate_over is None:
            aggregated = p / b
        elif how == "mean_of_ratios":
            aggregated = mean(p / b, axis=aggregate_over)
        else:
            num = total(p, axis=aggregate_over)
            den = total(np.broadcast_to(b, p.shape), axis=aggregate_over)
            aggregated = num / den
        return to_db(aggregated)


def compute_psd(lfp_data: np.ndarray, fs: float):
    """Welch power spectral density of a plain LFP array.

    PROMOTED 2026-08-23 from omission.jnwb_ext.report (99%-jnwb-sufficiency normalization): a
    thin, generic ``scipy.signal.welch`` wrapper with no session, condition, or report-specific
    coupling.

    Args:
        lfp_data: (n_times,) or (n_times, n_channels) array.
        fs: sampling rate in Hz.

    Returns:
        (freqs, psd) tuple.

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
    """
    freqs, psd = signal.welch(lfp_data, fs=fs, nperseg=min(len(lfp_data), int(fs)), axis=0)
    return freqs, psd


def harmonic_analysis(
    lfp_trace: np.ndarray,
    fs: Optional[float] = None,
    sampling_rate: Optional[float] = None,
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
        fs: Sampling frequency in Hz (canonical).
        sampling_rate: Supported alias for `fs` in Hz.
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
        >>> analysis = harmonic_analysis(lfp_data, fs=1000.0)
        >>> print(f"Theta fundamental: {analysis['fundamental_freq']:.1f} Hz")

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
    """
    fs = _resolve_fs(fs, sampling_rate, "harmonic_analysis")
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
            frequencies, pxx, _, _ = _welch_csd_gpu(lfp_trace, lfp_trace, fs, min(len(lfp_trace), 4096))
        except Exception as e:
            log.warning(f"GPU welch failed: {e}. Falling back to CPU.")
            frequencies, pxx = signal.welch(
                lfp_trace,
                fs=fs,
                window='hann',
                nperseg=min(len(lfp_trace), 4096),
                noverlap=None
            )
    else:
        frequencies, pxx = signal.welch(
            lfp_trace,
            fs=fs,
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
    fs: Optional[float] = None,
    sampling_rate: Optional[float] = None,
    freq_bands: Union[Dict[str, Tuple[float, float]], str, None] = None,
    device: str = 'cpu',
    rng: Optional[np.random.Generator] = None,
    n_surrogates: int = 50,
    n_jobs: int = 1,
) -> Dict:
    """
    Compute frequency-resolved coherence between two LFP signals.

    Coherence quantifies phase synchronization between areas across frequencies.
    High coherence = strong coupling; low coherence = weak coupling.

    The per-band significance test compares the observed band-mean coherence against a
    null built by **circularly shifting** ``lfp_area2`` by a random offset. The shift
    preserves each signal's autocorrelation and amplitude spectrum and destroys only the
    *relative* alignment of the two series, which is the quantity under test. Earlier
    docs called this phase randomization; that is a different null hypothesis.

    Args:
        lfp_area1: Time series from area 1
        lfp_area2: Time series from area 2
        fs: Sampling frequency in Hz (canonical).
        sampling_rate: Supported alias for `fs` in Hz.
        freq_bands: Required. A {'band_name': (freq_min, freq_max)} dict, or
                   'canonical' for CANONICAL_BANDS (theta 4-8, alpha 8-14, beta 14-30,
                   low_gamma 30-50, high_gamma 50-80). The bands decide every
                   band_coherence and p-value, so the caller names them.
        device: 'cpu' or 'cuda' (GPU acceleration via CuPy). Resolved **once**, before
                any coherence is computed; see `device_used` in the returned dict.
        rng: Generator for the surrogate shifts. Defaults to
             ``np.random.default_rng(42)``, matching the convention in
             `jnwb.statistics`. Previously hardcoded and unreachable, so every caller
             got the same 50 surrogates and no seed could be recorded.
        n_surrogates: Number of circular-shift surrogates per band (default 50).
                      Sets the resolution of the test: with the (count + 1) / (n + 1)
                      estimator the smallest attainable p-value is
                      ``1 / (n_surrogates + 1)``, so 1/51 = 0.0196 at the default. To
                      reject at a smaller alpha, raise this; the cost is linear.
        n_jobs: CPU workers for the surrogate spectra. Default 1 (serial); -1 uses every
                core. Results are identical for any n_jobs. Worth raising only when the
                surrogates take more than about a second in total, since the process
                pool costs a few seconds to start.

    Returns:
        Dict with:
        - coherence_spectrum: Coherence at each frequency
        - frequencies: Frequency bins
        - band_coherence: {band_name: mean_coherence, ...}
        - band_significance: {band_name: p_value, ...}. Every band is tested against
          the SAME set of surrogate signals, so these p-values are dependent by
          construction. Use a max-statistic or cluster correction across bands; a
          correction assuming independence is invalid here.
        - peak_coherence_freq: Frequency with highest coherence (Hz)
        - peak_coherence_value: Coherence at that frequency
        - device_used: 'cpu' or 'cuda' -- the estimator that produced *every* value
          here, observed and surrogate alike
        - n_surrogates_used: Surrogates actually drawn per band
        - p_value_floor: Smallest p-value this call could return,
          1 / (n_surrogates_used + 1). A p-value at the floor means "not resolvable
          with this many surrogates".
        - surrogate_seed_entropy: Entropy of the default generator, or None when the
          caller supplied `rng` (record your own seed in that case).

    Example:
        >>> coh = cross_area_coherence(v1_lfp, pfc_lfp, fs=1000.0, freq_bands='canonical')
        >>> print(f"Alpha coherence: {coh['band_coherence']['alpha']:.3f}")
        >>> print(f"p >= {coh['p_value_floor']:.4f} by construction")

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
    """
    fs = _resolve_fs(fs, sampling_rate, "cross_area_coherence")
    # INTENTIONAL BREAK (0.1.4). None used to mean CANONICAL_BANDS, so the band
    # taxonomy -- which decides every band_coherence and p-value -- was chosen for the
    # caller. The caller now names it, as phase_slope_index already requires.
    if freq_bands is None:
        raise ValueError(
            "cross_area_coherence needs freq_bands: a {name: (fmin, fmax)} dict, or "
            "'canonical' for CANONICAL_BANDS"
        )
    if isinstance(freq_bands, str):
        if freq_bands != "canonical":
            raise ValueError(f"freq_bands string must be 'canonical'; got {freq_bands!r}")
        freq_bands = dict(CANONICAL_BANDS)

    if n_surrogates < 1:
        raise ValueError(f"n_surrogates must be >= 1, got {n_surrogates}")

    # INTENTIONAL BREAK (0.1.3). This function used to drop the surrogate count from 50
    # to 10 whenever len(lfp) > 50000, making the p-value floor a function of input
    # length: 1/51 = 0.0196 for short signals, 1/11 = 0.0909 for long ones. At 1 kHz
    # that threshold is 50 s of data, so a caller testing at alpha = 0.05 could not
    # reject on a long recording, and the return value said nothing. The count is now
    # uniform and the floor it implies is reported. Pass n_surrogates=10 for the old
    # cost.
    seed_entropy = None
    if rng is None:
        seed_sequence = np.random.SeedSequence(42)
        seed_entropy = int(seed_sequence.entropy)
        rng = np.random.default_rng(seed_sequence)

    result = {
        'coherence_spectrum': np.array([]),
        'frequencies': np.array([]),
        'band_coherence': {},
        'band_significance': {},
        'peak_coherence_freq': 0.0,
        'peak_coherence_value': 0.0,
        'device_used': 'cpu',
        'n_surrogates_used': int(n_surrogates),
        'p_value_floor': 1.0 / (int(n_surrogates) + 1),
        'surrogate_seed_entropy': seed_entropy,
    }

    if len(lfp_area1) != len(lfp_area2):
        log.warning("LFP traces have different lengths")
        return result

    nperseg = min(len(lfp_area1), 4096)

    def _coherence_cpu(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        return signal.coherence(x, y, fs=fs, nperseg=nperseg, noverlap=None)

    def _coherence_gpu(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        frequencies, psd_x, psd_y, csd_xy = _welch_csd_gpu(x, y, fs, nperseg)
        denom = psd_x * psd_y
        coherency = np.zeros_like(csd_xy, dtype=float)
        nonzero = denom > 0
        coherency[nonzero] = np.abs(csd_xy[nonzero]) ** 2 / denom[nonzero]
        return frequencies, coherency

    def _compute_all(estimator) -> Dict:
        """Observed statistic and the entire null, from ONE estimator.

        The CPU and GPU paths differ: scipy detrends each segment and uses a periodic
        Hann window, while `_welch_csd_gpu` uses a symmetric `hanning` and no detrend.
        Both bias coherence, the quantity under test, so a null assembled from a
        mixture belongs to neither estimator.
        """
        out = {'band_coherence': {}, 'band_significance': {}}
        frequencies, coherency = estimator(lfp_area1, lfp_area2)
        out['frequencies'] = frequencies
        out['coherence_spectrum'] = coherency

        peak_idx = int(np.argmax(coherency))
        out['peak_coherence_freq'] = float(frequencies[peak_idx])
        out['peak_coherence_value'] = float(coherency[peak_idx])

        low_val, high_val = 1, len(lfp_area2) - 1
        shifts = (
            rng.integers(low_val, high_val, size=int(n_surrogates))
            if low_val < high_val
            else np.zeros(int(n_surrogates), dtype=int)
        )

        # One surrogate spectrum per shift, computed once and reused across bands.
        #
        # This preserves the null's cross-band dependence structure. The old code built
        # the generator inside the band loop, so every band drew the identical shift
        # sequence and the surrogate *signals* were already shared; it just recomputed
        # each spectrum from scratch per band, spending n_surrogates x n_bands estimator
        # calls on n_surrogates distinct spectra.
        #
        # Sharing surrogates across bands is what makes a max-statistic or cluster
        # correction valid. The per-band p-values are therefore dependent, which the
        # docstring states, since a Bonferroni over them would be invalid.
        surrogate_spectra = parallel_map(
            lambda shift: estimator(lfp_area1, np.roll(lfp_area2, int(shift)))[1],
            list(shifts),
            n_jobs=1 if device_requested_cuda else n_jobs,
        )

        for band_name, (fmin, fmax) in freq_bands.items():
            mask = (frequencies >= fmin) & (frequencies <= fmax)
            if not np.any(mask):
                continue
            mean_coh_val = float(np.mean(coherency[mask]))
            out['band_coherence'][band_name] = mean_coh_val

            surrogate_cohs = np.array([
                float(np.mean(spectrum[mask])) if len(spectrum) > 0 else 0.0
                for spectrum in surrogate_spectra
            ])
            p_val = (np.sum(surrogate_cohs >= mean_coh_val) + 1) / (int(n_surrogates) + 1)
            out['band_significance'][band_name] = float(p_val)

        return out

    # Resolve the device ONCE. The GPU path used to be attempted inside the surrogate
    # loop behind a per-iteration `except Exception`, so an intermittent failure (OOM
    # under memory pressure) silently produced a null mixing two estimators, with
    # nothing logged and nothing in the result. A GPU failure now discards the partial
    # work and recomputes everything, observed value included, on the CPU, so the
    # returned values share one estimator, named in `device_used`.
    device_used = resolve_device(device, context='cross_area_coherence', prefer='cupy')
    # CPU workers are pointless once the estimator is on the GPU: each process would
    # build its own CUDA context, competing for the same device.
    device_requested_cuda = device_used == CUDA
    if device_used == CUDA:
        try:
            computed = _compute_all(_coherence_gpu)
        except Exception as exc:
            warn_device_fallback('cross_area_coherence', exc)
            log.warning("GPU coherence failed: %s. Falling back to CPU wholesale.", exc)
            device_used = 'cpu'
            computed = _compute_all(_coherence_cpu)
    else:
        computed = _compute_all(_coherence_cpu)

    result.update(computed)
    result['device_used'] = device_used
    return result


def spectral_tilt(
    lfp_trace: np.ndarray,
    fs: Optional[float] = None,
    sampling_rate: Optional[float] = None,
    freq_range: Tuple[float, float] = (1.0, 100.0),
    device: str = 'cpu'
) -> Dict:
    """
    Fit 1/f spectral tilt via linear regression of log10 power versus log10 frequency.

    Fits log10(Power) = log10(Offset) + exponent * log10(freq) over the specified
    frequency range.

    Important Scientific Distinction:
        This routine performs an unconstrained linear fit across the chosen band; it does
        NOT model or isolate narrow-band oscillatory peaks (e.g. alpha or gamma rhythms).
        Prominent rhythms falling within `freq_range` will tilt the regression line. Select
        the fitting bounds carefully to minimize contamination by narrowband oscillations.

    Args:
        lfp_trace: Time series data
        fs: Sampling frequency in Hz (canonical).
        sampling_rate: Supported alias for `fs` in Hz.
        freq_range: Frequency range (f_min, f_max) in Hz for regression fitting
        device: 'cpu' or 'cuda' (GPU acceleration via CuPy)

    Returns:
        Dict with:
        - exponent: log-log slope (typically negative)
        - offset: power at 1 Hz (10^intercept)
        - fit_quality: R-squared of the linear fit

    Example:
        >>> tilt = spectral_tilt(lfp_data, fs=1000.0, freq_range=(1.0, 100.0))
        >>> print(f"Spectral exponent: {tilt['exponent']:.2f}")

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
    """
    fs = _resolve_fs(fs, sampling_rate, "spectral_tilt")
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
            frequencies, pxx, _, _ = _welch_csd_gpu(lfp_trace, lfp_trace, fs, min(len(lfp_trace), 4096))
        except Exception as e:
            log.warning(f"GPU welch failed: {e}. Falling back to CPU.")
            frequencies, pxx = signal.welch(
                lfp_trace,
                fs=fs,
                nperseg=min(len(lfp_trace), 4096)
            )
    else:
        frequencies, pxx = signal.welch(
            lfp_trace,
            fs=fs,
            nperseg=min(len(lfp_trace), 4096)
        )

    # Filter to range and remove DC
    mask = (frequencies > 0.5) & (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    freqs = frequencies[mask]

    if len(freqs) < 2 or np.all(pxx[mask] <= 0):
        return result

    valid = pxx[mask] > 0
    if np.sum(valid) < 2:
        return result

    freqs = freqs[valid]
    # Fit 1/f slope on log-log scale
    # Power = Offset * f^exponent
    # log(Power) = log(Offset) + exponent * log(freq)
    log_freqs = np.log10(freqs)
    log_power = np.log10(pxx[mask][valid])

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
    fs: Optional[float] = None,
    sampling_rate: Optional[float] = None,
    freq_range: Tuple[float, float] = (1.0, 90.0),
    normalize: bool = True,
    baseline: Optional[np.ndarray] = None,
    device: str = 'cpu'
) -> float:
    """
    Compute power in a frequency band.

    Args:
        lfp_trace: Time series data
        fs: Sampling frequency in Hz (canonical).
        sampling_rate: Supported alias for `fs` in Hz.
        freq_range: (min_freq, max_freq) in Hz
        normalize: If True, return as dB relative to baseline
        baseline: Baseline time series for normalization (optional)
        device: 'cpu' or 'cuda' (GPU acceleration via CuPy)

    Returns:
        Power in band (units depend on normalize flag)

    Example:
        >>> theta_power = band_power(lfp_data, fs=1000.0, freq_range=(4, 8))
        >>> baseline_power = band_power(baseline_lfp, fs=1000.0, freq_range=(4, 8), normalize=False)
        >>> normalized_power = band_power(lfp_data, fs=1000.0, freq_range=(4, 8), baseline=baseline_lfp)

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
    """
    fs = _resolve_fs(fs, sampling_rate, "band_power")
    if len(lfp_trace) == 0:
        return 0.0

    # Compute power spectrum
    if device == 'cuda':
        try:
            frequencies, pxx, _, _ = _welch_csd_gpu(lfp_trace, lfp_trace, fs, min(len(lfp_trace), 4096))
        except Exception as e:
            log.warning(f"GPU welch failed: {e}. Falling back to CPU.")
            frequencies, pxx = signal.welch(
                lfp_trace,
                fs=fs,
                nperseg=min(len(lfp_trace), 4096)
            )
    else:
        frequencies, pxx = signal.welch(
            lfp_trace,
            fs=fs,
            nperseg=min(len(lfp_trace), 4096)
        )

    # Extract band
    mask = (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    band_power_val = np.mean(pxx[mask]) if np.any(mask) else 0.0

    # Normalize to baseline if provided
    if normalize and baseline is not None and len(baseline) > 0:
        if device == 'cuda':
            try:
                _, baseline_pxx, _, _ = _welch_csd_gpu(baseline, baseline, fs, min(len(baseline), 4096))
            except Exception as e:
                log.warning(f"GPU baseline welch failed: {e}. Falling back to CPU.")
                _, baseline_pxx = signal.welch(
                    baseline,
                    fs=fs,
                    nperseg=min(len(baseline), 4096)
                )
        else:
            _, baseline_pxx = signal.welch(
                baseline,
                fs=fs,
                nperseg=min(len(baseline), 4096)
            )
        baseline_power_val = np.mean(baseline_pxx[mask]) if np.any(mask) else 1.0

        if baseline_power_val > 0:
            band_power_val = 10 * np.log10(band_power_val / baseline_power_val)

    return float(band_power_val)


def imaginary_coherency(
    x: np.ndarray,
    y: np.ndarray,
    fs: Optional[float] = None,
    sampling_rate: Optional[float] = None,
    freq_range: Tuple[float, float] = (1.0, 90.0),
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
        fs: Sampling frequency in Hz (canonical).
        sampling_rate: Supported alias for `fs` in Hz.
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

    References:
        Nolte, G., et al. (2004). Identifying true brain interaction from EEG data using the
        imaginary part of coherency. Clin. Neurophysiol. doi:10.1016/j.clinph.2004.04.029
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
    """
    fs = _resolve_fs(fs, sampling_rate, "imaginary_coherency")
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
            freqs, pxx, pyy, sxy = _welch_csd_gpu(x, y, fs, nperseg, noverlap)
        except Exception as e:
            log.warning(f"GPU coherency failed: {e}. Falling back to CPU.")
            device = 'cpu'
    if device != 'cuda':
        freqs, pxx = signal.welch(x, fs=fs, nperseg=nperseg, noverlap=noverlap)
        _, pyy = signal.welch(y, fs=fs, nperseg=nperseg, noverlap=noverlap)
        _, sxy = signal.csd(x, y, fs=fs, nperseg=nperseg, noverlap=noverlap)

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


def compute_multitaper_psd(
    data: np.ndarray,
    fs: float,
    nw: float = 3.0,
    k_tapers: Optional[int] = None,
    axis: int = -1,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute power spectral density via the Discrete Prolate Spheroidal Sequences (DPSS) multitaper method.

    Multitaper spectral estimation (Thomson, 1982; Mitra & Pesaran, 1999) averages eigenspectra
    modulated by orthogonal Slepian tapers, optimal for minimizing spectral leakage in finite-length
    physiological epochs.

    Contract & Normalization:
        Each eigenspectrum is normalized by the discrete taper energy:
            P_k(f) = |X_k(f)|^2 / (fs * sum_n v_k[n]^2)
        For real signals, non-DC and non-Nyquist components are doubled (one-sided scaling),
        preserving total physical variance under Parseval's theorem:
            sum_f P(f) * df ≈ Var(x).

    Args:
        data: Continuous time series array of arbitrary shape.
        fs: Sampling frequency in Hz. Must be strictly positive.
        nw: Time-halfbandwidth product (default: 3.0). Must be strictly positive.
        k_tapers: Number of DPSS tapers to average (default: max(1, int(2 * nw - 1))).
            Must be in range [1, N] where N is length of `data` along `axis`.
        axis: Time axis along which to compute the spectrum (default: -1).

    Returns:
        (freqs, psd) tuple:
            freqs: 1D array of frequency bin centers in Hz (from 0 to fs / 2).
            psd: Power spectral density array with `axis` corresponding to frequencies.

    Raises:
        ValueError: If `fs <= 0`, `nw <= 0`, `k_tapers` is out of bounds, or `data` contains NaNs.
    """
    if fs <= 0:
        raise ValueError(f"Sampling frequency fs must be strictly positive; got {fs}.")
    if nw <= 0:
        raise ValueError(f"Time-halfbandwidth product nw must be strictly positive; got {nw}.")

    arr = np.asarray(data, dtype=float)
    if np.isnan(arr).any():
        raise ValueError("Cannot compute multitaper PSD on data containing NaN values.")

    n_samples = arr.shape[axis]
    if n_samples < 4:
        raise ValueError(f"Signal length along axis ({n_samples}) too short for multitaper spectral estimation.")

    if k_tapers is None:
        k_tapers = max(1, int(2 * nw - 1))
    if not (1 <= k_tapers <= n_samples):
        raise ValueError(f"k_tapers ({k_tapers}) must be between 1 and signal length ({n_samples}).")

    from scipy.signal.windows import dpss

    tapers = dpss(n_samples, NW=nw, Kmax=k_tapers, sym=False)  # shape: (K, N)

    # Detrend data by subtracting mean along time axis
    arr_mean = np.mean(arr, axis=axis, keepdims=True)
    detrended = arr - arr_mean

    # Bring evaluated axis to last position
    detrended = np.moveaxis(detrended, axis, -1)
    orig_shape = detrended.shape[:-1]
    flat = detrended.reshape(-1, n_samples)  # shape: (M, N)

    n_fft = n_samples
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / fs)
    n_freqs = len(freqs)

    psd_accum = np.zeros((flat.shape[0], n_freqs), dtype=float)
    for k in range(k_tapers):
        taper_k = tapers[k]
        taper_energy = np.sum(taper_k ** 2)
        # Apply taper
        tapered = flat * taper_k  # (M, N)
        fft_k = np.fft.rfft(tapered, n=n_fft, axis=-1)
        psd_k = (np.abs(fft_k) ** 2) / (fs * taper_energy)
        # One-sided scaling
        if n_freqs > 2:
            psd_k[:, 1:-1] *= 2.0
        psd_accum += psd_k

    psd_mean = psd_accum / k_tapers
    psd_out = psd_mean.reshape(orig_shape + (n_freqs,))
    # Move frequency axis back to original axis position
    psd_out = np.moveaxis(psd_out, -1, axis)
    return freqs, psd_out


def voltage_curvature_1d(
    lfp_matrix: np.ndarray,
    pitch_um: float,
    axis: int = 0,
) -> np.ndarray:
    """Compute the discrete second spatial derivative of extracellular potential along a laminar probe.

    Estimates spatial voltage curvature (Nicholson & Freeman, 1975):
        Curvature(z_i) = (V[i+1] - 2*V[i] + V[i-1]) / (pitch_um * 1e-6)^2

    Important Scientific Distinction:
        Voltage curvature is the purely electrical second derivative (in V/m^2 when potential is in Volts).
        It does NOT assume a tissue conductivity tensor and is NOT physical Current Source Density (CSD).
        To compute physical CSD in A/m^3, call ``current_source_density_1d(..., conductivity_s_per_m=...)``.

    Args:
        lfp_matrix: 2D array of continuous local field potentials in Volts (V),
            with shape (n_channels, n_times) when axis=0. Minimum 3 channels required.
        pitch_um: Inter-contact spacing (electrode pitch) in micrometers (um). Must be strictly positive.
        axis: Spatial/channel axis along which to take the second derivative (default: 0).

    Returns:
        Curvature array in V/m^2 with 2 fewer channels along `axis` than `lfp_matrix`
        (interior channels 1 to N-2).

    Raises:
        ValueError: If `pitch_um <= 0` or number of channels along `axis` is less than 3.
    """
    if pitch_um <= 0:
        raise ValueError(f"Electrode pitch must be strictly positive; got {pitch_um} um.")
    arr = np.asarray(lfp_matrix, dtype=float)
    n_ch = arr.shape[axis]
    if n_ch < 3:
        raise ValueError(f"Voltage curvature requires at least 3 channels along spatial axis; got {n_ch}.")

    pitch_m = pitch_um * 1e-6
    delta_z2 = pitch_m ** 2

    # Second spatial difference: (V[i+1] - 2*V[i] + V[i-1]) / delta_z2
    sl_prev = [slice(None)] * arr.ndim
    sl_curr = [slice(None)] * arr.ndim
    sl_next = [slice(None)] * arr.ndim

    sl_prev[axis] = slice(0, n_ch - 2)
    sl_curr[axis] = slice(1, n_ch - 1)
    sl_next[axis] = slice(2, n_ch)

    d2v = (arr[tuple(sl_next)] - 2.0 * arr[tuple(sl_curr)] + arr[tuple(sl_prev)]) / delta_z2
    return d2v


def current_source_density_1d(
    lfp_matrix: np.ndarray,
    pitch_um: float,
    conductivity_s_per_m: float,
    axis: int = 0,
) -> np.ndarray:
    """Compute physical 1D Current Source Density (CSD) along a laminar electrode array.

    Physical CSD models transmembrane current sources and sinks per unit volume via Poisson's equation
    in an assumed isotropic, homogeneous extracellular medium:
        CSD(z_i) = -sigma * d^2V / dz^2
                 ≈ -conductivity_s_per_m * (V[i+1] - 2*V[i] + V[i-1]) / (pitch_um * 1e-6)^2

    Sign Convention:
        - Negative values indicate a CURRENT SINK (inward transmembrane current, e.g. excitatory synaptic input).
        - Positive values indicate a CURRENT SOURCE (outward passive/return current).

    Dimensional Invariant:
        Potential V must be in Volts (V).
        Pitch must be in micrometers (um, converted to m).
        Conductivity must be explicitly supplied in Siemens per meter (S/m).
        Output is returned in SI physical units: Amperes per cubic meter (A/m^3).
        (Note: 1 A/m^3 = 10^-3 uA/mm^3 = 1 nA/mm^3).

    Args:
        lfp_matrix: 2D array of continuous local field potentials in Volts (V),
            with shape (n_channels, n_times) when axis=0. Minimum 3 channels required.
        pitch_um: Inter-contact spacing in micrometers (um). Must be strictly positive.
        conductivity_s_per_m: Extracellular tissue conductivity in S/m (e.g. 0.3 to 0.4 S/m in mammalian cortex).
            Required argument; never defaulted. Must be strictly positive.
        axis: Spatial/channel axis along probe depth (default: 0).

    Returns:
        Array of physical Current Source Density in A/m^3, with 2 fewer channels along `axis`.

    Raises:
        ValueError: If `pitch_um <= 0`, `conductivity_s_per_m <= 0`, or channel count < 3.
    """
    if conductivity_s_per_m <= 0:
        raise ValueError(
            f"Tissue conductivity must be strictly positive; got {conductivity_s_per_m} S/m. "
            "CSD is physically undefined without positive conductivity."
        )
    curvature = voltage_curvature_1d(lfp_matrix, pitch_um=pitch_um, axis=axis)
    return -conductivity_s_per_m * curvature

