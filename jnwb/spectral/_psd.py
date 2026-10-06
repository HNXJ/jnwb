"""Power spectra: Welch and multitaper PSD, harmonic analysis, 1/f tilt and the aperiodic fit."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import optimize, signal
from .._dictlike import DictAccessMixin
from .._spread import is_constant as _is_constant
from .._backend import CPU, CUDA, resolve_device, warn_device_fallback
from ._common import (
    _require_band_bins,
    _require_finite_nonempty_trace,
    _require_two_samples,
    _flat_as_zero,
    _resolve_fs,
)

log = logging.getLogger(__package__)


#: Bins at or below this frequency are excluded from the 1/f fit: the DC and near-DC bins
#: of a Welch spectrum are dominated by the detrending residual, not by the aperiodic slope.
#: It is a property of the estimator, so `spectral_tilt` reports the band it actually fitted.
_TILT_DC_FLOOR_HZ = 0.5

#: Minimum usable bins for a 1/f fit. Below this the "exponent" is an interpolation
#: through a handful of points rather than an estimate.
_MIN_TILT_BINS = 6

#: Percentile of the clipped residual at or below which `aperiodic_fit(robust=True)`
#: keeps a bin for its second fit: FOOOF 1.1.0's `_ap_percentile_thresh`, in percent.
_ROBUST_AP_PERCENTILE = 0.025


def compute_psd(lfp_data: np.ndarray, fs: float, axis: int = 0, *, nperseg: Optional[int] = None):
    """Welch power spectral density of a plain LFP array.

    Thin ``scipy.signal.welch`` wrapper on caller-supplied traces.

    Args:
        lfp_data: array with time along ``axis``; (n_times,) or (n_times, n_channels)
            under the default.
        fs: sampling rate in Hz (must be positive and finite).
        axis: axis along which time is sampled (default 0, matching the documented
            ``(n_times, n_channels)`` layout). Pass ``axis=-1`` for channel-major data.
        nperseg: Welch segment length in samples, from 2 to the length along ``axis``.
            ``None`` keeps ``min(n_times, int(fs))``, one second or the whole trace, and
            at least 2 samples. The
            frequency resolution is ``fs / nperseg``.

    Returns:
        (freqs, psd) tuple. A trace constant along ``axis`` has an exactly zero PSD.

    Raises:
        ValueError: If ``lfp_data`` is empty or non-finite, ``fs`` is not positive and
            finite, ``axis`` is out of range for ``lfp_data``, or ``nperseg`` is not an
            integer from 2 to the length along ``axis``.

    Notes:
        The default ``nperseg`` is derived from the length along ``axis``. It used to be derived from
        ``len(lfp_data)``, the length along axis 0 whatever ``axis`` meant, so a
        channel-major ``(8, 4000)`` array was segmented into 8 samples and returned a
        5-bin spectrum while ``compute_multitaper_psd(..., axis=-1)`` returned 2001 bins
        over the same data.

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
        -- the spectrum as the average of windowed periodograms over overlapping segments.
    """
    arr = _require_finite_nonempty_trace(lfp_data, "compute_psd", name="lfp_data")
    if not (np.isfinite(fs) and fs > 0):
        raise ValueError(f"compute_psd: fs must be positive and finite, got {fs}.")
    if not -arr.ndim <= axis < arr.ndim:
        raise ValueError(
            f"compute_psd: axis {axis} is out of range for data of shape {arr.shape}."
        )
    n_times = arr.shape[axis]
    if n_times < 2:
        raise ValueError(
            f"compute_psd: axis {axis} has {n_times} sample(s); a spectrum needs at least "
            "2. A 1-sample trace used to return a 0.0 PSD, which is indistinguishable "
            "from a measured absence of power."
        )
    if nperseg is None:
        nperseg = min(n_times, max(2, int(fs)))
    if isinstance(nperseg, (bool, np.bool_)) or not isinstance(nperseg, (int, np.integer)):
        raise ValueError(f"compute_psd: nperseg must be an integer, got {nperseg!r}.")
    if not 2 <= nperseg <= n_times:
        raise ValueError(
            f"compute_psd: nperseg must be from 2 to the {n_times} samples along axis {axis}, "
            f"got {nperseg}. scipy would shorten a longer segment to the trace without saying so."
        )
    # Welch removes each segment's mean, which for a constant trace leaves rounding residue
    # (about 1e-33) rather than 0; a trace constant along `axis` is replaced by the zeros its
    # detrended spectrum is, as `_flat_as_zero` does for a whole trace.
    arr = np.where(_is_constant(arr, axis=axis, keepdims=True), 0.0, arr)
    freqs, psd = signal.welch(arr, fs=fs, nperseg=int(nperseg), axis=axis)
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
        device: 'cpu' or 'cuda' (GPU acceleration via CuPy). 'cuda' is the slower
            route below roughly 22500 samples. At that size the Welch helper's fixed
            cost -- one host-to-device transfer, the window, the FFT plan and the
            copies back -- is most of the call, and there is too little arithmetic left
            to amortise it. Paired on an RTX A4000, R = T_cuda / T_cpu is about 1.15 at
            16384 samples, crosses 1.0 near 22500, and reaches 0.07 at 4.2 M. The
            crossover is documented rather than applied automatically: the CPU and CUDA
            Welch paths do not agree bit for bit, so routing on input length would make
            the answer depend on how long the trace is, which invariant 6 forbids. See
            `artifacts/benchmarks/gpu_launch_overhead_0.2.5.md`.

    Returns:
        Dict with:
        - fundamental_freq: Dominant frequency (Hz)
        - harmonics: {order: (freq, power)} for orders 1-N
        - spectral_profile: Full power spectrum
        - frequencies: Frequency bins for spectrum
        - harmonic_ratio: P(fundamental) / (P(fundamental) + sum of P(orders 2..N)); 1.0
          when no higher order falls inside ``freq_range``
        - device_used: 'cpu' or 'cuda', the device that computed the spectrum

        ``fundamental_freq`` and ``harmonic_ratio`` are NaN, and ``harmonics`` is empty, when
        no bin in ``freq_range`` has positive power (a constant trace).

    Raises:
        ValueError: If ``lfp_trace`` is empty, non-finite or a single sample, ``freq_range``
            contains no bin of the Welch grid, or ``device`` is not a recognised device name.

    Example:
        >>> analysis = harmonic_analysis(lfp_data, fs=1000.0)
        >>> print(f"Theta fundamental: {analysis['fundamental_freq']:.1f} Hz")

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
        -- the spectrum as the average of windowed periodograms over overlapping segments.
    """
    fs = _resolve_fs(fs, sampling_rate, "harmonic_analysis")
    lfp_trace = _flat_as_zero(_require_two_samples(
        _require_finite_nonempty_trace(lfp_trace, "harmonic_analysis"), "harmonic_analysis"))
    result = {
        'fundamental_freq': float('nan'),
        'harmonics': {},
        'spectral_profile': np.array([]),
        'frequencies': np.array([]),
        'harmonic_ratio': float('nan'),
    }

    # Compute power spectrum
    device = resolve_device(device, context="harmonic_analysis", prefer="cupy", stacklevel=3)
    if device == CUDA:
        try:
            frequencies, pxx, _, _ = _welch_csd_gpu(lfp_trace, lfp_trace, fs, min(len(lfp_trace), 4096))
        except Exception as e:
            warn_device_fallback("harmonic_analysis", e, stacklevel=3)
            device = CPU
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

    result['device_used'] = device
    result['frequencies'] = frequencies
    result['spectral_profile'] = pxx

    # Filter to frequency range
    mask = (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    freqs_range = frequencies[mask]
    pxx_range = pxx[mask]

    _require_band_bins(frequencies, mask, freq_range, "harmonic_analysis")
    if not np.any(pxx_range > 0):
        # No power in range, so no dominant frequency. This reported the first bin as the
        # fundamental with zero power.
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
                    'relative_power': float(harmonic_power / fundamental_power) if fundamental_power > 0 else float('nan')
                }

    # Harmonic ratio (fundamental vs. higher harmonics). Order 1 is the fundamental itself;
    # summing it into the harmonics counted the fundamental twice and capped the ratio at 0.5.
    higher_harmonic_power = sum(
        h['power'] for order, h in result['harmonics'].items() if order >= 2
    )
    result['harmonic_ratio'] = float(fundamental_power / (fundamental_power + higher_harmonic_power))

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

    Fits log10(Power) = log10(Offset) + slope * log10(freq) over the specified
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
        device: 'cpu' or 'cuda' (GPU acceleration via CuPy). 'cuda' is the slower
            route below roughly 22500 samples. At that size the Welch helper's fixed
            cost -- one host-to-device transfer, the window, the FFT plan and the
            copies back -- is most of the call, and there is too little arithmetic left
            to amortise it. Paired on an RTX A4000, R = T_cuda / T_cpu is about 1.15 at
            16384 samples, crosses 1.0 near 22500, and reaches 0.07 at 4.2 M. The
            crossover is documented rather than applied automatically: the CPU and CUDA
            Welch paths do not agree bit for bit, so routing on input length would make
            the answer depend on how long the trace is, which invariant 6 forbids. See
            `artifacts/benchmarks/gpu_launch_overhead_0.2.5.md`.

    Returns:
        Dict with:
        - slope: log-log slope, negative for a 1/f decay. :func:`aperiodic_fit` reports
          the exponent, which is ``-slope``.
        - offset: power at 1 Hz (10^intercept)
        - fit_quality: R-squared of the linear fit
        - device_used: 'cpu' or 'cuda', the device that computed the spectrum

        All three are NaN when fewer than two bins in ``freq_range`` have positive power (a
        constant or all-zero trace); ``fit_quality`` is NaN when every fitted bin has the same
        power. There is no ``exponent`` key: an exponent is the positive decay rate
        :func:`aperiodic_fit` reports.

    Raises:
        ValueError: If ``lfp_trace`` is empty or contains NaN or Inf, or ``device`` is not a
            recognised device name.

    Example:
        >>> tilt = spectral_tilt(lfp_data, fs=1000.0, freq_range=(1.0, 100.0))
        >>> print(f"Log-log slope: {tilt['slope']:.2f}")

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
        -- the spectrum as the average of windowed periodograms over overlapping segments.
    """
    fs = _resolve_fs(fs, sampling_rate, "spectral_tilt")
    lfp_trace = _flat_as_zero(_require_finite_nonempty_trace(lfp_trace, "spectral_tilt"))
    # NaN marks a slope the spectrum cannot support. These fields reported 0.0, which reads as
    # a measured flat spectrum.
    # INTENTIONAL BREAK (0.2.10): the `exponent` key, deprecated in 0.2.7 for `slope`, is gone.
    result = {
        'slope': float('nan'),
        'offset': float('nan'),
        'fit_quality': float('nan'),
        # The band actually fitted, which is not the band requested: bins at or below
        # _TILT_DC_FLOOR_HZ are excluded, so freq_range=(0.1, 100) and (0.5, 100) returned
        # a bit-identical exponent with nothing to say they had been silently merged.
        'fitted_band_hz': (float('nan'), float('nan')),
        'n_bins_fitted': 0,
    }

    # Compute power spectrum
    resolved = resolve_device(device, context="spectral_tilt", prefer="cupy", stacklevel=3)
    if resolved == CUDA:
        try:
            frequencies, pxx, _, _ = _welch_csd_gpu(lfp_trace, lfp_trace, fs, min(len(lfp_trace), 4096))
        except Exception as e:
            warn_device_fallback("spectral_tilt", e, stacklevel=3)
            log.warning(f"GPU welch failed: {e}. Falling back to CPU.")
            resolved = CPU
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
    result['device_used'] = resolved

    # Filter to range and remove DC. The 0.5 Hz floor is part of the estimand, not a
    # detail: `freq_range=(0.1, 100)` and `(0.5, 100)` returned a bit-identical exponent
    # because everything below 0.5 Hz was dropped without a word. The band actually
    # fitted is now reported, so a silently narrowed request is visible.
    mask = (frequencies > _TILT_DC_FLOOR_HZ) & (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    _require_band_bins(frequencies, mask, freq_range, "spectral_tilt")
    freqs = frequencies[mask]

    # Two separate conditions, which must not be conflated:
    #
    #   (a) the requested band is too narrow to fit on this grid -- a malformed request,
    #       which raises. freq_range=(400, 401) selected 5 bins and returned exponent
    #       -995.2 with offset inf and a fit_quality of 0.687, behind only a RuntimeWarning.
    #
    #   (b) the band has bins but none carries positive power -- a constant or zero trace,
    #       where the tilt is genuinely undefined and NaN is the answer, not an error.
    if freqs.size < _MIN_TILT_BINS:
        raise ValueError(
            f"spectral_tilt: freq_range {tuple(freq_range)} selects {int(freqs.size)} "
            f"bin(s) of the Welch grid above {_TILT_DC_FLOOR_HZ} Hz; a 1/f fit needs at "
            f"least {_MIN_TILT_BINS}. Widen freq_range or lengthen nperseg."
        )

    valid = pxx[mask] > 0
    if np.sum(valid) < 2:
        return result

    freqs = freqs[valid]
    result['fitted_band_hz'] = (float(freqs[0]), float(freqs[-1]))
    result['n_bins_fitted'] = int(freqs.size)
    # Fit 1/f slope on log-log scale
    # Power = Offset * f^slope
    # log(Power) = log(Offset) + slope * log(freq)
    log_freqs = np.log10(freqs)
    log_power = np.log10(pxx[mask][valid])

    # Linear regression
    coeffs = np.polyfit(log_freqs, log_power, 1)
    slope = coeffs[0]
    offset_log = coeffs[1]

    result['slope'] = float(slope)
    result['offset'] = float(10 ** offset_log)

    # Fit quality (R-squared)
    fitted = np.polyval(coeffs, log_freqs)
    ss_res = np.sum((log_power - fitted) ** 2)
    ss_tot = np.sum((log_power - np.mean(log_power)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else float('nan')
    result['fit_quality'] = float(r_squared)

    return result


@dataclass
class AperiodicFitResult(DictAccessMixin):
    """
    Container for 1/f aperiodic spectral parameter estimates.

    Attributes:
        offset: Broadband offset parameter `b` (log10 power intercept), or None if fit rejected.
        exponent: Aperiodic spectral slope / exponent `chi` (positive for 1/f decay), or None if fit rejected.
        knee: Knee parameter `k` (>0.0 for knee mode, None for fixed mode or rejected fit).
        r_squared: Coefficient of determination (R^2) of the fit in log10 space, or None if fit rejected.
        freq_range: Evaluated frequency range `(f_min, f_max)` in Hz.
        mode: Fitting model (`'fixed'` or `'knee'`).
        accepted: Whether the optimization successfully converged to a valid fit.
    """

    offset: Optional[float]
    exponent: Optional[float]
    knee: Optional[float]
    r_squared: Optional[float]
    freq_range: Tuple[float, float]
    mode: str
    accepted: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offset": self.offset,
            "exponent": self.exponent,
            "knee": self.knee,
            "r_squared": self.r_squared,
            "freq_range": self.freq_range,
            "mode": self.mode,
            "accepted": self.accepted,
        }


def aperiodic_fit(
    freqs: np.ndarray,
    psd: np.ndarray,
    freq_range: Tuple[float, float],
    mode: str = "fixed",
    *,
    robust: bool = False,
) -> Union[AperiodicFitResult, List[Any]]:
    """
    Fit aperiodic 1/f spectral parameters directly to an existing power spectrum.

    Fits the standard log-log aperiodic formulation:
        L(f) = b - log10(k + f^chi)

    In `'fixed'` mode, the knee parameter is constrained to `k = 0`, reducing to
    `L(f) = b - chi * log10(f)`. In `'knee'` mode, `k > 0` is optimized to capture
    a low-frequency plateau.

    Important Scientific Distinctions:
        - This function operates strictly on pre-computed `(freqs, psd)` arrays;
          it does not recompute Welch periodograms or require time-series data.
        - By neuroscience convention (Donoghue et al. 2020), `exponent` (chi) is
          reported as a positive number representing 1/f decay (decay rate chi).
          In contrast, unconstrained linear slope in :func:`spectral_tilt` is negative.
          The mathematical equivalence is `exponent_aperiodic == -slope_spectral_tilt`
          and `offset_aperiodic == log10(offset_spectral_tilt)`.
        - A fit whose optimizer fails returns `accepted=False` rather than raising or
          fabricating parameters. An ill-conditioned fit that converges is still
          `accepted=True`; read `r_squared` before trusting it.

    Args:
        freqs: 1D array of strictly increasing, finite frequency coordinates in Hz, shape `(n_freqs,)`.
        psd: Power spectral density array in (U_in)^2/Hz, shape `(n_freqs,)` or `(..., n_freqs)`.
            Must be strictly non-negative and finite.
        freq_range: Tuple `(f_min, f_max)` in Hz defining the fitting range (inclusive).
            Must satisfy `0 < f_min < f_max`.
        mode: Model type, either `'fixed'` (k = 0) or `'knee'` (k > 0). Default is `'fixed'`.
        robust: False (default) fits every bin in `freq_range`. True is the robust
            aperiodic fit of the reference implementation, `FOOOF._robust_ap_fit` (fooof
            1.1.0; Donoghue et al. 2020): fit once, then refit only the bins whose residual
            above the first fit, clipped at 0, is at or below its 0.025th percentile, so
            bins a peak lifts above the first fit are left out. It detects and subtracts no
            peak: it is the initial aperiodic fit of that algorithm, not the final one,
            which is refitted after Gaussian peaks are subtracted. `r_squared` is then over
            the kept bins, and the fit is rejected when fewer than 4 are kept.

    Returns:
        :class:`AperiodicFitResult` dataclass for 1D input, or nested list/array of results
        for multidimensional PSD input matching leading batch dimensions `(...)`.

    Raises:
        ValueError: If frequencies are non-monotonic, non-positive, or non-finite;
            if PSD contains negative, NaN, or infinite values; if `freq_range` is invalid;
            if `mode` is unrecognized; or if fewer than 4 frequency bins fall in `freq_range`.

    References:
        Donoghue, T., et al. (2020). Parameterizing neural power spectra into periodic and
        aperiodic components. Nature Neuroscience. doi:10.1038/s41593-020-00744-x
        -- the aperiodic component of Methods eq. 3; `'fixed'` is its k = 0 case. The
        paper's algorithm fits the aperiodic component after detecting and removing
        periodic peaks. By default this function fits it to every bin in `freq_range` and
        removes nothing, so an oscillatory peak inside the range steepens or flattens the
        fitted exponent; choose a range without peaks, or pass `robust=True`, which
        lessens the bias without removing the peak.
        FOOOF (fooof-tools.github.io/fooof), `FOOOF._robust_ap_fit` -- the reference for
        `robust=True`, including its 0.025 percentile threshold (`_ap_percentile_thresh`).
    """
    if mode not in ("fixed", "knee"):
        raise ValueError(f"Invalid mode '{mode}'. Must be 'fixed' or 'knee'.")

    freqs_arr = np.asarray(freqs, dtype=np.float64)
    if freqs_arr.ndim != 1:
        raise ValueError(f"freqs must be a 1D array, got ndim={freqs_arr.ndim}.")
    if len(freqs_arr) == 0:
        raise ValueError("freqs array is empty.")
    if not np.all(np.isfinite(freqs_arr)):
        raise ValueError("freqs array contains NaN or infinite values.")
    if np.any(freqs_arr <= 0):
        raise ValueError("freqs array must contain strictly positive frequencies (> 0).")
    if not np.all(np.diff(freqs_arr) > 0):
        raise ValueError("freqs array must be strictly increasing.")

    if len(freq_range) != 2:
        raise ValueError(f"freq_range must be a 2-tuple (f_min, f_max), got {freq_range}.")
    f_min, f_max = float(freq_range[0]), float(freq_range[1])
    if not (np.isfinite(f_min) and np.isfinite(f_max)):
        raise ValueError(f"freq_range must contain finite bounds, got ({f_min}, {f_max}).")
    if f_min <= 0:
        raise ValueError(f"freq_range minimum must be strictly positive (> 0), got {f_min}.")
    if f_min >= f_max:
        raise ValueError(f"freq_range f_min ({f_min}) must be strictly less than f_max ({f_max}).")

    psd_arr = np.asarray(psd, dtype=np.float64)
    if psd_arr.ndim == 0:
        raise ValueError("psd must have at least 1 dimension.")
    if psd_arr.shape[-1] != len(freqs_arr):
        raise ValueError(
            f"Trailing dimension of psd ({psd_arr.shape[-1]}) does not match freqs length ({len(freqs_arr)})."
        )
    if not np.all(np.isfinite(psd_arr)):
        raise ValueError("psd array contains NaN or infinite values.")
    if np.any(psd_arr <= 0):
        raise ValueError("psd array contains non-positive values (<= 0). Non-positive power is undefined in log space.")

    # Frequency mask
    mask = (freqs_arr >= f_min) & (freqs_arr <= f_max)
    n_points = int(np.sum(mask))
    if n_points < 4:
        raise ValueError(
            f"Insufficient frequency bins in freq_range ({f_min}, {f_max}): "
            f"found {n_points} bins, but at least 4 are required for aperiodic fitting."
        )

    fit_freqs = freqs_arr[mask]
    log_freqs = np.log10(fit_freqs)
    range_tuple = (f_min, f_max)

    # Knee mode: L(f) = b - log10(k + f^chi)
    def _knee_model(f, b_param, chi_param, k_param):
        return b_param - np.log10(k_param + f ** chi_param)

    def _fit(f_sel, log_f_sel, log_power, p0=None):
        """``(offset, exponent, knee, r_squared, fitted)`` of `mode` on the given bins.

        Raises when the optimiser fails. ``p0`` seeds the knee fit; ``None`` is the linear
        initialisation.
        """
        ss_tot = float(np.sum((log_power - np.mean(log_power)) ** 2))
        if mode == "fixed":
            coeffs = np.polyfit(log_f_sel, log_power, 1)
            chi = float(-coeffs[0])
            b = float(coeffs[1])
            k = None
            fitted = b - chi * log_f_sel
        else:
            if p0 is None:
                # Linear initialization
                coeffs_init = np.polyfit(log_f_sel, log_power, 1)
                chi_init = max(0.01, float(-coeffs_init[0]))
                b_init = float(coeffs_init[1])
                p0 = [b_init, chi_init, 1.0]
            bounds = ((-np.inf, 0.0, 0.0), (np.inf, np.inf, np.inf))
            popt, _ = optimize.curve_fit(
                _knee_model,
                f_sel,
                log_power,
                p0=p0,
                bounds=bounds,
                maxfev=5000,
            )
            b = float(popt[0])
            chi = float(popt[1])
            k = float(popt[2])
            fitted = _knee_model(f_sel, b, chi, k)
        ss_res = float(np.sum((log_power - fitted) ** 2))
        r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
        return b, chi, k, r2, fitted

    def _fit_single_1d(p_1d: np.ndarray) -> AperiodicFitResult:
        log_power = np.log10(p_1d[mask])
        try:
            b, chi, k, r2, fitted = _fit(fit_freqs, log_freqs, log_power)
            if robust:
                # FOOOF 1.1.0 `_robust_ap_fit`: residual above the first fit, clipped at 0,
                # and the bins at or below its `_ap_percentile_thresh` (0.025) percentile.
                flat = np.maximum(log_power - fitted, 0.0)
                keep = flat <= np.percentile(flat, _ROBUST_AP_PERCENTILE)
                if int(np.sum(keep)) < 4:
                    raise ValueError("fewer than 4 bins remain for the robust refit")
                seed = None if mode == "fixed" else [b, chi, k]
                b, chi, k, r2, _ = _fit(
                    fit_freqs[keep], log_freqs[keep], log_power[keep], p0=seed
                )
        except Exception:
            return AperiodicFitResult(
                offset=None,
                exponent=None,
                knee=None,
                r_squared=None,
                freq_range=range_tuple,
                mode=mode,
                accepted=False,
            )
        return AperiodicFitResult(
            offset=b,
            exponent=chi,
            knee=k,
            r_squared=r2,
            freq_range=range_tuple,
            mode=mode,
            accepted=True,
        )

    if psd_arr.ndim == 1:
        return _fit_single_1d(psd_arr)

    # Multidimensional batch handling across leading dimensions
    leading_shape = psd_arr.shape[:-1]
    flat_psd = psd_arr.reshape(-1, len(freqs_arr))
    results_flat = [_fit_single_1d(row) for row in flat_psd]
    results_arr = np.array(results_flat, dtype=object).reshape(leading_shape)
    return results_arr.tolist()


def _welch_csd_gpu(
    x: np.ndarray,
    y: np.ndarray,
    fs: float,
    nperseg: int,
    noverlap: Optional[int] = None,
    detrend: Union[str, bool] = "constant",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Helper to compute PSD and CSD on GPU using CuPy matching scipy.signal.welch and csd parity.

    Implements:
    - Periodic Hann window matching scipy.signal.get_window('hann', nperseg).
    - Segment-level detrending (default: 'constant' detrending, subtracting segment mean).
    - Conjugate orientation matching scipy.signal.csd: conj(X) * Y.
    - Exact one-sided scaling for even and odd nperseg (doubling positive frequencies).
    - Zero-padding for inputs shorter than nperseg.
    - A self-spectrum short circuit when ``y is x``, which returns the same four arrays
      it would otherwise compute, bit for bit.
    """
    import cupy as cp
    if noverlap is None:
        noverlap = nperseg // 2
    step = nperseg - noverlap

    # `harmonic_analysis` and `spectral_tilt` call this as
    # `_welch_csd_gpu(trace, trace, ...)` and keep only `pxx`, so half of everything
    # below was a second copy of the first half. Reusing the first half is exact, not
    # an approximation: `y is x` means the two branches transfer the same bytes, gather
    # the same indices and run the same `rfft`, so `Y` is bit-identical to `X` and
    # `conj(X) * Y` is bit-identical to `conj(X) * X`. Measured at 16384 samples, it
    # takes 1.66 ms down to 1.06 ms at every nperseg tested, which is 36% of the call.
    same_signal = y is x

    x_g = cp.asarray(x, dtype=cp.float64)
    y_g = x_g if same_signal else cp.asarray(y, dtype=cp.float64)
    n = len(x_g)

    if n < nperseg:
        x_g = cp.pad(x_g, (0, nperseg - n))
        y_g = x_g if same_signal else cp.pad(y_g, (0, nperseg - n))
        n = nperseg

    # Periodic Hann window matching scipy.signal.get_window('hann', nperseg)
    window = 0.5 - 0.5 * cp.cos(2.0 * cp.pi * cp.arange(nperseg) / nperseg)

    # This was a Python `while` loop appending one device array per segment, so
    # a 16384-sample trace at nperseg=256 ran 127 iterations and about 762 kernel
    # launches before `cp.stack`. Launch overhead, not arithmetic, was the cost: the
    # whole call took 26.8 ms against 16.6 ms for the equivalent scipy calls, and even
    # at nperseg=4096 -- 7 segments, which is what `spectral_tilt` and
    # `harmonic_analysis` ask for -- 2.6 ms of a 3.2 ms call was the loop, against a
    # fixed floor of 0.62 ms for the transfers, window and FFT together.
    #
    # One strided index builds every segment at once. Verified against the loop at
    # nperseg 64, 128, 255, 256, 512, 1024 and 2048: `max|difference| == 0.0` on all
    # four outputs, because the per-segment mean and the row-wise mean of the same
    # array reduce in the same order there. At 4096 and 8192 `cupy` picks a different
    # row-mean reduction, the detrend constant moves in its last bits, and the outputs
    # shift by up to 1.43e-13 relative -- smaller than this path's pre-existing
    # disagreement with scipy on the same input (2.6e-15 at 256 rising to 4.1e-13 at
    # 2048), so the CPU/CUDA gap is not widened. The estimator is unchanged: same
    # window, same detrend, same scaling.
    n_segments = (n - nperseg) // step + 1
    offsets = step * cp.arange(n_segments)
    idx = cp.arange(nperseg)[None, :] + offsets[:, None]
    seg_x = x_g[idx]
    seg_y = seg_x if same_signal else y_g[idx]
    if detrend == "constant":
        seg_x = seg_x - seg_x.mean(axis=1, keepdims=True)
        seg_y = seg_x if same_signal else seg_y - seg_y.mean(axis=1, keepdims=True)

    X = cp.fft.rfft(seg_x * window, axis=-1)
    Y = X if same_signal else cp.fft.rfft(seg_y * window, axis=-1)

    scale = 1.0 / (fs * cp.sum(window ** 2))

    psd_x = cp.mean(cp.abs(X) ** 2, axis=0) * scale
    # `.copy()` matters: the one-sided scaling below is in place, so aliasing psd_y to
    # psd_x would double the positive frequencies twice.
    psd_y = psd_x.copy() if same_signal else cp.mean(cp.abs(Y) ** 2, axis=0) * scale
    csd_xy = cp.mean(cp.conj(X) * Y, axis=0) * scale

    # One-sided scaling
    if nperseg % 2:
        psd_x[1:] *= 2.0
        psd_y[1:] *= 2.0
        csd_xy[1:] *= 2.0
    else:
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

    Multitaper spectral estimation (Thomson, 1982) averages eigenspectra modulated by
    orthogonal Slepian tapers, optimal for minimizing spectral leakage in finite-length
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
                A finite trace constant along `axis` has an exactly zero PSD.

    Raises:
        ValueError: If `fs <= 0`, `nw <= 0`, `k_tapers` is out of bounds, or `data` contains NaNs.

    References:
        Thomson, D. J. (1982). Spectrum estimation and harmonic analysis. Proc. IEEE.
        doi:10.1109/PROC.1982.12433 -- the multitaper estimate from DPSS tapers. The K
        eigenspectra are averaged with equal weight; no adaptive weighting is applied.
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

    # Detrend data by subtracting mean along time axis. A trace constant along `axis` is
    # exactly 0 after it; the subtraction alone leaves rounding residue (about 1e-32). An
    # infinite constant is not finite after it, and keeps its NaN.
    arr_mean = np.mean(arr, axis=axis, keepdims=True)
    flat = _is_constant(arr, axis=axis, keepdims=True) & np.isfinite(arr_mean)
    detrended = np.where(flat, 0.0, arr - arr_mean)

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
        # One-sided scaling. DC is never doubled, and the Nyquist bin is never doubled --
        # but an rfft grid only HAS a Nyquist bin when n_fft is even. For odd n_fft the last
        # bin is an ordinary positive frequency and must be doubled like the rest. Excluding
        # it unconditionally left the top bin of every odd-length epoch a factor of two too
        # small: a tone at 499.5 Hz in a 1001-sample record reported 0.0999 there against
        # 0.1993 for the same tone one bin lower. Broadband Parseval hardly notices one bin
        # in 501, which is why this survived a total-power check.
        if n_fft % 2 == 0:
            if n_freqs > 2:
                psd_k[:, 1:-1] *= 2.0
        elif n_freqs > 1:
            psd_k[:, 1:] *= 2.0
        psd_accum += psd_k

    psd_mean = psd_accum / k_tapers
    psd_out = psd_mean.reshape(orig_shape + (n_freqs,))
    # Move frequency axis back to original axis position
    psd_out = np.moveaxis(psd_out, -1, axis)
    return freqs, psd_out
