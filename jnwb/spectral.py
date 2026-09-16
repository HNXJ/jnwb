"""
jnwb.spectral -- spectral/oscillatory analysis: band-limited power, cross-area coherence,
1/f tilt, imaginary coherency, and re-referencing for LFP time series.

All functions take plain time-series arrays and generic keyword parameters. ``CANONICAL_BANDS``
is the default band-edge table (theta/alpha/beta/gamma); override via ``freq_bands=`` on any
caller that accepts it.
"""

import logging
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import optimize, signal, stats
import pandas as pd

from ._backend import CUDA, resolve_device, warn_device_fallback
from ._parallel import parallel_map

log = logging.getLogger(__name__)

#: Default band edges (Hz) -- standard neuroscience convention; overridable per call.
def _require_equal_lengths(x: np.ndarray, y: np.ndarray, func_name: str) -> None:
    """Reject unpaired traces instead of truncating to the shorter one.

    INTENTIONAL BREAK (0.2.4). These estimators took ``n = min(len(x), len(y))`` and
    silently discarded the tail of the longer trace. Truncation is a scientific decision
    -- it changes which samples are compared and, for a mismatch, means the two traces
    no longer describe the same interval -- so it belongs to the caller.
    """
    if len(x) != len(y):
        raise ValueError(
            f"{func_name}: x and y must have the same length, got {len(x)} and {len(y)}. "
            "These are paired time series; truncating to the shorter one silently "
            "changes which samples are compared, so it is the caller's decision."
        )


def _require_finite_nonempty_pair(x: np.ndarray, y: np.ndarray, func_name: str) -> None:
    """Reject paired traces from which no cross-spectrum can be estimated.

    An empty pair used to return 0.0, and a NaN sample made every wPLI term NaN, which the
    zero-denominator guard then reported as 0.0. Both read as "no coupling".
    """
    if len(x) == 0:
        raise ValueError(f"{func_name}: x and y are empty; there is nothing to estimate.")
    if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
        raise ValueError(
            f"{func_name}: x and y must be finite. A NaN or Inf sample propagates into "
            "every segment that contains it; remove or repair those samples first."
        )


#: Bins at or below this frequency are excluded from the 1/f fit: the DC and near-DC bins
#: of a Welch spectrum are dominated by the detrending residual, not by the aperiodic slope.
#: It is a property of the estimator, so `spectral_tilt` reports the band it actually fitted.
_TILT_DC_FLOOR_HZ = 0.5

#: Minimum usable bins for a 1/f fit. Below this the "exponent" is an interpolation
#: through a handful of points rather than an estimate.
_MIN_TILT_BINS = 6


def _require_band_bins(
    freqs: np.ndarray, mask: np.ndarray, freq_range: Tuple[float, float], func_name: str
) -> None:
    """Reject a frequency range that selects no bin of the segment grid."""
    if not np.any(mask):
        step = float(freqs[1] - freqs[0]) if len(freqs) > 1 else float("nan")
        raise ValueError(
            f"{func_name}: freq_range {tuple(freq_range)} contains no bin of the "
            f"frequency grid (0 to {float(freqs[-1]):g} Hz in steps of {step:g} Hz). "
            "Widen freq_range or lengthen nperseg."
        )


def _require_finite_nonempty_trace(x: np.ndarray, func_name: str, name: str = "lfp_trace") -> np.ndarray:
    """Return ``x`` as a float array, rejecting empty or non-finite input.

    Empty input used to return zeros, and a NaN sample gave zeros or NaN powers. A returned
    0 is indistinguishable from a measured absence of power or slope.
    """
    arr = np.asarray(x, dtype=float)
    if arr.size == 0:
        raise ValueError(f"{func_name}: {name} is empty; there is nothing to estimate.")
    if not np.all(np.isfinite(arr)):
        raise ValueError(
            f"{func_name}: {name} must be finite; remove or repair NaN or Inf samples first."
        )
    return arr


#: Imaginary cross-spectral terms below this fraction of their cross-spectral magnitude are
#: treated as exactly zero-lag (a phase within 1e-10 rad of 0 or pi). The cutoff is
#: relative so wPLI does not depend on the units of the input: the absolute 1e-12 it
#: replaces zeroed every term of volt-scaled LFP and reported wPLI = 0 for coupled signals.
ZERO_LAG_RTOL = 1e-10


def _wpli_from_cross_spectra(Sxy, xp=np):
    """Per-frequency wPLI and debiased squared wPLI from segment cross-spectra.

    ``Sxy`` has shape ``(n_freqs, n_segments)``; ``xp`` is ``numpy`` or ``cupy``. A
    frequency with no non-zero-lag term (every imaginary part zero) reports 0 for both,
    the zero-lag convention; the debiased estimate also reports 0 when fewer than two
    terms are non-zero, where it is undefined.
    """
    imag = xp.imag(Sxy)
    imag = xp.where(xp.abs(imag) <= ZERO_LAG_RTOL * xp.abs(Sxy), 0.0, imag)
    sum_imag = xp.sum(imag, axis=1)
    sum_abs = xp.sum(xp.abs(imag), axis=1)
    sum_sq = xp.sum(imag ** 2, axis=1)

    has_lag = sum_abs > 0
    wpli_f = xp.where(has_lag, xp.abs(sum_imag) / xp.where(has_lag, sum_abs, 1.0), 0.0)

    num_deb = sum_imag ** 2 - sum_sq
    den_deb = sum_abs ** 2 - sum_sq
    has_pairs = den_deb > ZERO_LAG_RTOL * sum_abs ** 2
    deb_f = xp.where(has_pairs, num_deb / xp.where(has_pairs, den_deb, 1.0), 0.0)
    return wpli_f, deb_f


def _require_identifiable_segmentation(
    n_samples: int, nperseg: int, noverlap: int, func_name: str, quantity: str
) -> int:
    """Reject a segmentation that cannot identify a cross-spectral ratio.

    Shared by every estimator that divides a cross-spectrum by the auto-spectra
    (`cross_area_coherence`, `imaginary_coherency`, `wpli`). With a single segment the
    numerator and denominator are built from the same one spectral realization, so the
    ratio collapses to its maximum by algebra: coherence is 1.0 at every frequency and
    wPLI is +/-1, for ANY two signals including independent noise. Plain PSD estimators
    are NOT affected -- a one-segment periodogram is noisy but unbiased -- so this guard
    deliberately does not apply to them.
    """
    n_segments = welch_segment_count(n_samples, nperseg, noverlap)
    if n_segments < MIN_IDENTIFIABLE_SEGMENTS:
        raise ValueError(
            f"{func_name}: {quantity} is not identifiable from {n_segments} Welch "
            f"segment(s) ({n_samples} samples, nperseg={nperseg}, noverlap={noverlap}). "
            "A single segment makes the cross-spectrum an exact function of the "
            "auto-spectra, so the ratio saturates regardless of real coupling. Supply a "
            "smaller nperseg, a smaller noverlap, or a longer recording."
        )
    return n_segments


#: Fewest Welch segments from which magnitude-squared coherence is identifiable.
#: With K = 1 the single cross-spectral estimate satisfies |X Y*|^2 = |X|^2 |Y|^2
#: exactly, so the ratio is 1.0 at every frequency for any pair of signals. This is an
#: algebraic identity, not an estimation error, and no amount of surrogate testing
#: recovers from it: the surrogates saturate at 1.0 too. K = 2 is the mathematical
#: boundary. It is NOT a statement about how many segments good science needs -- the
#: null coherence still has expectation ~1/K, so K = 2 carries a null mean near 0.5.
MIN_IDENTIFIABLE_SEGMENTS = 2

#: Floor on the default segment length, so tiny inputs do not derive nperseg = 0.
MIN_COHERENCE_NPERSEG = 8


def welch_segment_count(n_samples: int, nperseg: int, noverlap: int) -> int:
    """Number of Welch segments scipy will average, given the segmentation.

    Mirrors the segment loop in :func:`scipy.signal.welch`: segments start every
    ``nperseg - noverlap`` samples and only whole segments are used.
    """
    if nperseg <= 0 or noverlap >= nperseg or n_samples < nperseg:
        return 0
    return 1 + (int(n_samples) - int(nperseg)) // (int(nperseg) - int(noverlap))


CANONICAL_BANDS: Dict[str, Tuple[float, float]] = {
    "theta": (4.0, 8.0),
    "alpha": (8.0, 14.0),
    "beta": (14.0, 30.0),
    "low_gamma": (30.0, 50.0),
    "high_gamma": (50.0, 80.0),
}


def _require_channel_permutation(
    channel_order: np.ndarray, n_channels: int, func_name: str
) -> np.ndarray:
    """Return ``channel_order`` as an index array, rejecting anything but a permutation.

    A short, long, or duplicated order silently dropped channels in ``bipolar_reference``
    and left rows of ``laplacian_reference``'s output unwritten, so the function returned
    whatever ``np.empty_like`` had been handed: two identical calls did not agree, and the
    uninitialised values (order 1e-297) are not distinguishable from a measured amplitude.
    """
    order = np.asarray(channel_order)
    if order.ndim != 1:
        raise ValueError(
            f"{func_name}: channel_order must be 1-D, got shape {order.shape}."
        )
    if not np.issubdtype(order.dtype, np.integer):
        raise ValueError(
            f"{func_name}: channel_order must be an integer index array, got dtype {order.dtype}."
        )
    if order.shape[0] != n_channels:
        raise ValueError(
            f"{func_name}: channel_order has {order.shape[0]} entries for {n_channels} "
            "channels; it must name every channel exactly once."
        )
    if not np.array_equal(np.sort(order), np.arange(n_channels)):
        raise ValueError(
            f"{func_name}: channel_order must be a permutation of range({n_channels}); "
            f"got {np.array2string(order, threshold=16)}. Repeated or out-of-range "
            "indices drop channels and leave the output partly uninitialised."
        )
    return order


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
    through — average power, divide by baseline, then take the logarithm exactly once.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(ratio)


#: Accepted aggregation estimands for :func:`aggregate_to_db`. These are genuinely different
#: estimands, not implementation details, which is why the caller must name one:
#: ``sum_c P_c / sum_c P0_c == sum_c w_c (P_c / P0_c)`` with ``w_c = P0_c / sum_j P0_j`` --
#: i.e. "ratio_of_means" is a baseline-power-weighted average of the very same per-unit ratios
#: that "mean_of_ratios" weights equally. A quiet default would silently pick one for the caller.
DB_AGGREGATIONS = ("mean_of_ratios", "ratio_of_means")

#: Accepted estimand models for :func:`relative_power`.
#: - "mean_of_ratios": Arithmetic mean of per-unit ratios E[P / P0] (equal weighting per unit/channel).
#: - "ratio_of_means": Ratio of aggregated means E[P] / E[P0] (baseline-power-weighted average).
#: - "log_ratio": 10 * log10(P / P0) in decibels (no spatial/trial aggregation, preserving exact ratio-to-dB).
RELATIVE_POWER_MODELS = ("mean_of_ratios", "ratio_of_means", "log_ratio")


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
    which is the failure the "take the logarithm last" rule exists to prevent.
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
            b_bc = np.broadcast_to(b, p.shape)
            if nan_policy == "omit":
                valid = np.isfinite(p) & np.isfinite(b_bc)
                num = np.sum(np.where(valid, p, 0.0), axis=aggregate_over)
                den = np.sum(np.where(valid, b_bc, 0.0), axis=aggregate_over)
                count = np.sum(valid, axis=aggregate_over)
                aggregated = np.where(count > 0, num / den, np.nan)
            else:
                num = total(p, axis=aggregate_over)
                den = total(b_bc, axis=aggregate_over)
                aggregated = num / den
        return to_db(aggregated)


def compute_psd(lfp_data: np.ndarray, fs: float, axis: int = 0):
    """Welch power spectral density of a plain LFP array.

    Thin ``scipy.signal.welch`` wrapper on caller-supplied traces.

    Args:
        lfp_data: array with time along ``axis``; (n_times,) or (n_times, n_channels)
            under the default.
        fs: sampling rate in Hz (must be positive and finite).
        axis: axis along which time is sampled (default 0, matching the documented
            ``(n_times, n_channels)`` layout). Pass ``axis=-1`` for channel-major data.

    Returns:
        (freqs, psd) tuple.

    Raises:
        ValueError: If ``lfp_data`` is empty or non-finite, ``fs`` is not positive and
            finite, or ``axis`` is out of range for ``lfp_data``.

    Notes:
        ``nperseg`` is derived from the length along ``axis``. It used to be derived from
        ``len(lfp_data)``, the length along axis 0 whatever ``axis`` meant, so a
        channel-major ``(8, 4000)`` array was segmented into 8 samples and returned a
        5-bin spectrum while ``compute_multitaper_psd(..., axis=-1)`` returned 2001 bins
        over the same data.

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
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
    freqs, psd = signal.welch(arr, fs=fs, nperseg=min(n_times, int(fs)), axis=axis)
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
        - harmonic_ratio: P(fundamental) / (P(fundamental) + sum of P(orders 2..N)); 1.0
          when no higher order falls inside ``freq_range``

        ``fundamental_freq`` and ``harmonic_ratio`` are NaN, and ``harmonics`` is empty, when
        no bin in ``freq_range`` has positive power (a constant trace).

    Raises:
        ValueError: If ``lfp_trace`` is empty or non-finite, ``freq_range`` contains no bin
            of the Welch grid, or ``device`` is not a recognised device name.

    Example:
        >>> analysis = harmonic_analysis(lfp_data, fs=1000.0)
        >>> print(f"Theta fundamental: {analysis['fundamental_freq']:.1f} Hz")

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
    """
    fs = _resolve_fs(fs, sampling_rate, "harmonic_analysis")
    lfp_trace = _require_finite_nonempty_trace(lfp_trace, "harmonic_analysis")
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
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
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

    Raises:
        ValueError: if the segmentation yields fewer than
            ``MIN_IDENTIFIABLE_SEGMENTS`` (2) Welch segments. With one segment the
            cross-spectrum is the exact geometric mean of the auto-spectra, so
            coherence is 1.0 everywhere by algebra and the estimator is
            non-identifiable. Surrogate testing does not rescue this: the surrogates
            saturate at 1.0 as well.

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
        nperseg: Welch segment length in samples. Default ``min(max(N // 8, 8), 4096)``,
                 which yields 15 segments for any N up to 32768 and more beyond it.
                 INTENTIONAL BREAK (0.2.4): the previous default ``min(N, 4096)`` put
                 every input up to ~8192 samples into a single segment, where
                 magnitude-squared coherence is identically 1.0 for ANY two signals --
                 independent Gaussian traces reported perfect coherence. The default was
                 re-chosen by comparing candidate segment lengths on independent and
                 known-coupled synthetic signals across N from 1024 to 60000; ``N // 8``
                 separated coupled from null better than ``N // 4`` at every length
                 tested, and a fixed length cannot serve short and long traces at once.
                 Frequency resolution is ``fs / nperseg``, so a band narrower than that
                 resolves to no bins and is omitted from the band outputs.
        noverlap: Samples of overlap between segments. Default ``nperseg // 2``. Must
                  satisfy ``0 <= noverlap < nperseg``.

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
        - nperseg, noverlap: the segmentation actually used
        - n_segments_used: Welch segments averaged, K. The null expectation of
          coherence is approximately 1/K (measured 1.00-1.06 x 1/K at 50% overlap,
          the excess growing with K because overlapping segments are correlated), so
          K is required to interpret any coherence value this function returns.
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
        'nperseg': None,
        'noverlap': None,
        'n_segments_used': 0,
        'n_surrogates_used': int(n_surrogates),
        'p_value_floor': 1.0 / (int(n_surrogates) + 1),
        'surrogate_seed_entropy': seed_entropy,
    }

    lfp_area1 = np.asarray(lfp_area1)
    lfp_area2 = np.asarray(lfp_area2)
    for name, trace in (("lfp_area1", lfp_area1), ("lfp_area2", lfp_area2)):
        if trace.ndim != 1:
            raise ValueError(
                f"{name} must be a 1-D time series, got shape {trace.shape}. This function "
                "compares two traces; to work channel-by-channel, call it per channel pair. "
                "A 2-D array was previously accepted and then indexed as if it were 1-D, "
                "which set nperseg to the channel count and took argmax over the flattened "
                "array."
            )
    # Non-finite input made every band coherence NaN and every surrogate comparison
    # False, so `band_significance` came out at its floor, 1/(n_surrogates+1), for every
    # band at once -- maximal significance from a statistic that does not exist. `wpli`
    # and `imaginary_coherency` already refuse the same input.
    _require_finite_nonempty_pair(lfp_area1, lfp_area2, "cross_area_coherence")
    if len(lfp_area1) != len(lfp_area2):
        # INTENTIONAL BREAK (0.2.4). This logged a warning and returned a dict of zeros,
        # which is indistinguishable from a measured coherence of zero: peak_coherence_
        # value was 0.0, no key marked the result as absent, and the log line is invisible
        # unless the caller configured logging. Coherence is defined only for paired
        # samples, so unequal lengths are malformed input, not a zero-coupling result.
        raise ValueError(
            f"lfp_area1 and lfp_area2 must have the same length, got "
            f"{len(lfp_area1)} and {len(lfp_area2)}. Coherence is defined only between "
            "paired samples; truncating or padding to a common length is the caller's "
            "decision, not this function's."
        )

    n_samples = int(len(lfp_area1))
    if nperseg is None:
        nperseg = min(max(n_samples // 8, MIN_COHERENCE_NPERSEG), 4096)
    nperseg = int(nperseg)
    if nperseg < 2:
        raise ValueError(f"nperseg must be >= 2, got {nperseg}")
    if noverlap is None:
        noverlap = nperseg // 2
    noverlap = int(noverlap)
    if not (0 <= noverlap < nperseg):
        raise ValueError(
            f"noverlap must satisfy 0 <= noverlap < nperseg, got noverlap={noverlap} "
            f"with nperseg={nperseg}"
        )

    n_segments = welch_segment_count(n_samples, nperseg, noverlap)
    if n_segments < MIN_IDENTIFIABLE_SEGMENTS:
        step = nperseg - noverlap
        raise ValueError(
            f"coherence is not identifiable from {n_segments} Welch segment(s): "
            f"{n_samples} samples with nperseg={nperseg}, noverlap={noverlap}. "
            "With a single segment the cross-spectrum is the exact geometric mean of "
            "the auto-spectra, so magnitude-squared coherence is identically 1.0 at "
            "every frequency for ANY two signals, coupled or independent. Supply a "
            f"smaller nperseg (<= {max(2, (n_samples + step) // 2)} keeps at least "
            f"{MIN_IDENTIFIABLE_SEGMENTS} segments here), a smaller noverlap, or a "
            "longer recording."
        )
    result['nperseg'] = nperseg
    result['noverlap'] = noverlap
    result['n_segments_used'] = n_segments

    def _coherence_cpu(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        return signal.coherence(x, y, fs=fs, nperseg=nperseg, noverlap=noverlap)

    def _coherence_gpu(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        frequencies, psd_x, psd_y, csd_xy = _welch_csd_gpu(x, y, fs, nperseg, noverlap)
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

        All three are NaN when fewer than two bins in ``freq_range`` have positive power (a
        constant or all-zero trace); ``fit_quality`` is NaN when every fitted bin has the same
        power.

    Raises:
        ValueError: If ``lfp_trace`` is empty or contains NaN or Inf, or ``device`` is not a
            recognised device name.

    Example:
        >>> tilt = spectral_tilt(lfp_data, fs=1000.0, freq_range=(1.0, 100.0))
        >>> print(f"Spectral exponent: {tilt['exponent']:.2f}")

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
    """
    fs = _resolve_fs(fs, sampling_rate, "spectral_tilt")
    lfp_trace = _require_finite_nonempty_trace(lfp_trace, "spectral_tilt")
    # NaN marks a slope the spectrum cannot support. These fields reported 0.0, which reads as
    # a measured flat spectrum.
    result = {
        'exponent': float('nan'),
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
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else float('nan')
    result['fit_quality'] = float(r_squared)

    return result


@dataclass
class AperiodicFitResult:
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

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

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
        - Valid inputs with non-converging or ill-conditioned fits return
          `accepted=False` rather than raising unhandled exceptions or fabricating parameters.

    Args:
        freqs: 1D array of strictly increasing, finite frequency coordinates in Hz, shape `(n_freqs,)`.
        psd: Power spectral density array in (U_in)^2/Hz, shape `(n_freqs,)` or `(..., n_freqs)`.
            Must be strictly non-negative and finite.
        freq_range: Tuple `(f_min, f_max)` in Hz defining the fitting range (inclusive).
            Must satisfy `0 < f_min < f_max`.
        mode: Model type, either `'fixed'` (k = 0) or `'knee'` (k > 0). Default is `'fixed'`.

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

    def _fit_single_1d(p_1d: np.ndarray) -> AperiodicFitResult:
        fit_psd = p_1d[mask]
        log_power = np.log10(fit_psd)
        ss_tot = float(np.sum((log_power - np.mean(log_power)) ** 2))

        if mode == "fixed":
            try:
                coeffs = np.polyfit(log_freqs, log_power, 1)
                chi = float(-coeffs[0])
                b = float(coeffs[1])
                fitted = b - chi * log_freqs
                ss_res = float(np.sum((log_power - fitted) ** 2))
                r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
                return AperiodicFitResult(
                    offset=b,
                    exponent=chi,
                    knee=None,
                    r_squared=r2,
                    freq_range=range_tuple,
                    mode="fixed",
                    accepted=True,
                )
            except Exception:
                return AperiodicFitResult(
                    offset=None,
                    exponent=None,
                    knee=None,
                    r_squared=None,
                    freq_range=range_tuple,
                    mode="fixed",
                    accepted=False,
                )
        else:
            # Knee mode: L(f) = b - log10(k + f^chi)
            def _knee_model(f, b_param, chi_param, k_param):
                return b_param - np.log10(k_param + f ** chi_param)

            try:
                # Linear initialization
                coeffs_init = np.polyfit(log_freqs, log_power, 1)
                chi_init = max(0.01, float(-coeffs_init[0]))
                b_init = float(coeffs_init[1])
                p0 = [b_init, chi_init, 1.0]
                bounds = ((-np.inf, 0.0, 0.0), (np.inf, np.inf, np.inf))
                popt, _ = optimize.curve_fit(
                    _knee_model,
                    fit_freqs,
                    log_power,
                    p0=p0,
                    bounds=bounds,
                    maxfev=5000,
                )
                b_opt = float(popt[0])
                chi_opt = float(popt[1])
                k_opt = float(popt[2])
                fitted = _knee_model(fit_freqs, b_opt, chi_opt, k_opt)
                ss_res = float(np.sum((log_power - fitted) ** 2))
                r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
                return AperiodicFitResult(
                    offset=b_opt,
                    exponent=chi_opt,
                    knee=k_opt,
                    r_squared=r2,
                    freq_range=range_tuple,
                    mode="knee",
                    accepted=True,
                )
            except Exception:
                return AperiodicFitResult(
                    offset=None,
                    exponent=None,
                    knee=None,
                    r_squared=None,
                    freq_range=range_tuple,
                    mode="knee",
                    accepted=False,
                )

    if psd_arr.ndim == 1:
        return _fit_single_1d(psd_arr)

    # Multidimensional batch handling across leading dimensions
    leading_shape = psd_arr.shape[:-1]
    flat_psd = psd_arr.reshape(-1, len(freqs_arr))
    results_flat = [_fit_single_1d(row) for row in flat_psd]
    results_arr = np.array(results_flat, dtype=object).reshape(leading_shape)
    return results_arr.tolist()


def relative_power(
    power: np.ndarray,
    baseline: np.ndarray,
    *,
    model: str = "mean_of_ratios",
    axis: Optional[Union[int, Tuple[int, ...]]] = None,
    device: str = "cpu",
) -> np.ndarray:
    """
    Compute relative power of a signal against baseline under an explicit mathematical estimand.

    Mathematical Estimands:
        - ``"mean_of_ratios"``:
          Computes :math:`\\frac{1}{N} \\sum_{c=1}^{N} \\frac{P_c}{B_c}` across the specified ``axis``.
          Treats every unit/channel with equal weight. Returns linear dimensionless ratio.
        - ``"ratio_of_means"``:
          Computes :math:`\\frac{\\sum_c P_c}{\\sum_c B_c}` across the specified ``axis``.
          Equivalent to a baseline-power-weighted average of per-unit ratios:
          :math:`\\sum_c w_c (P_c / B_c)` where :math:`w_c = B_c / \\sum_j B_j`.
          Returns linear dimensionless ratio.
        - ``"log_ratio"``:
          Computes :math:`10 \\log_{10}(P / B)` elementwise in decibels (dB).
          Preserves the log-last principle without spatial or trial aggregation.

    Important Scientific Invariants:
        - The three models represent mathematically distinct estimands. They coincide only when
          baseline power is strictly identical across the aggregation axis. Under unequal baselines,
          they diverge. The requested model is returned exactly as specified; the library never
          silently converts among them.
        - Preserves linear scale when ``"mean_of_ratios"`` or ``"ratio_of_means"`` is requested.
          Conversion to decibels occurs only when ``model="log_ratio"`` is explicitly chosen,
          preventing premature logarithmic transforms before aggregation (Jensen's inequality).
        - Negative or non-finite inputs, zero baseline values, and mismatched non-broadcastable
          shapes fail loudly by raising :class:`ValueError`.

    Args:
        power: Power array in :math:`(U_{\\text{in}})^2` or :math:`(U_{\\text{in}})^2/\\text{Hz}`.
            Must be finite and strictly non-negative. Any shape.
        baseline: Baseline power array in the same physical units as ``power``, broadcastable against ``power``.
            Must be finite, strictly non-negative, and contain non-zero values where division occurs.
        model: Estimand model, strictly one of ``"mean_of_ratios"``, ``"ratio_of_means"``, or ``"log_ratio"``.
            Default is ``"mean_of_ratios"``.
        axis: Axis or tuple of axes to reduce along when using ``"mean_of_ratios"`` or ``"ratio_of_means"``.
            If ``None`` and ``model="mean_of_ratios"``, computes elementwise ratio :math:`P / B` without reduction.
            If ``None`` and ``model="ratio_of_means"``, reduces across all elements (:math:`\\sum P / \\sum B`).
            For ``model="log_ratio"``, ``axis`` must be ``None`` (elementwise dB transform).
        device: Hardware device to use: ``"cpu"`` or ``"cuda"``. Resolved via :func:`resolve_device`.
            If ``"cuda"`` is requested but unavailable, falls back to CPU with a diagnostic warning.

    Returns:
        :class:`numpy.ndarray` of relative power values matching broadcast/reduced shape.
        Linear scale (dimensionless) for ``"mean_of_ratios"`` and ``"ratio_of_means"``;
        decibels (:math:`\\text{dB}`) for ``"log_ratio"``.

    Raises:
        ValueError: If ``model`` is unrecognized; if any input is empty; if ``power`` or ``baseline``
            contains negative or non-finite (NaN/Inf) values; if ``baseline`` contains zeros causing
            division by zero; if shapes cannot broadcast; or if ``axis`` is provided with ``model="log_ratio"``.

    Examples:
        >>> import numpy as np
        >>> p = np.array([2.0, 8.0])
        >>> b = np.array([1.0, 2.0])
        >>> # Mean of ratios: (2/1 + 8/2) / 2 = (2 + 4) / 2 = 3.0
        >>> float(relative_power(p, b, model="mean_of_ratios", axis=0))
        3.0
        >>> # Ratio of means: (2 + 8) / (1 + 2) = 10 / 3 = 3.333...
        >>> float(relative_power(p, b, model="ratio_of_means", axis=0))
        3.3333333333333335
        >>> # Log ratio: [10*log10(2), 10*log10(4)] = [3.010..., 6.020...]
        >>> relative_power(p, b, model="log_ratio")
        array([3.01029996, 6.02059991])
    """
    if model not in RELATIVE_POWER_MODELS:
        raise ValueError(f"model must be one of {list(RELATIVE_POWER_MODELS)}; got {model!r}")

    if model == "log_ratio" and axis is not None:
        raise ValueError(
            f"model='log_ratio' computes elementwise decibels without aggregation; "
            f"got axis={axis!r}. For aggregated decibels, use jnwb.aggregate_to_db."
        )

    # Resolve device with observable fallback
    resolved_dev = resolve_device(device, context="relative_power", prefer="cupy", stacklevel=3)

    p_arr = np.asarray(power, dtype=np.float64)
    b_arr = np.asarray(baseline, dtype=np.float64)

    if p_arr.size == 0 or b_arr.size == 0:
        raise ValueError("power and baseline inputs must not be empty.")

    if not (np.all(np.isfinite(p_arr)) and np.all(np.isfinite(b_arr))):
        raise ValueError("power and baseline inputs must contain finite values (no NaN or Inf).")

    if np.any(p_arr < 0):
        raise ValueError("power contains negative values. Power must be non-negative ratio-scale.")

    if np.any(b_arr < 0):
        raise ValueError("baseline contains negative values. Baseline must be non-negative ratio-scale.")

    # Broadcast check
    try:
        b_broadcast = np.broadcast_to(b_arr, p_arr.shape)
    except ValueError as e:
        raise ValueError(
            f"baseline shape {b_arr.shape} cannot broadcast to power shape {p_arr.shape}."
        ) from e

    if np.any(b_broadcast == 0):
        raise ValueError("baseline contains zero values resulting in division by zero.")

    # Execute computation
    if resolved_dev == CUDA:
        try:
            import cupy as cp

            p_gpu = cp.asarray(p_arr)
            b_gpu = cp.asarray(b_arr)
            b_gpu_broadcast = cp.broadcast_to(b_gpu, p_gpu.shape)

            if model == "mean_of_ratios":
                if axis is None:
                    res_gpu = p_gpu / b_gpu_broadcast
                else:
                    res_gpu = cp.mean(p_gpu / b_gpu_broadcast, axis=axis)
            elif model == "ratio_of_means":
                num = cp.sum(p_gpu, axis=axis)
                den = cp.sum(b_gpu_broadcast, axis=axis)
                res_gpu = num / den
            else:  # log_ratio
                res_gpu = 10.0 * cp.log10(p_gpu / b_gpu_broadcast)

            return cp.asnumpy(res_gpu)
        except Exception as exc:
            warn_device_fallback("relative_power", exc, stacklevel=3)
            # Wholesale CPU fallback below

    # CPU path
    if model == "mean_of_ratios":
        if axis is None:
            return p_arr / b_broadcast
        return np.mean(p_arr / b_broadcast, axis=axis)
    elif model == "ratio_of_means":
        num = np.sum(p_arr, axis=axis)
        den = np.sum(b_broadcast, axis=axis)
        return num / den
    else:  # log_ratio
        with np.errstate(divide="ignore", invalid="ignore"):
            return 10.0 * np.log10(p_arr / b_broadcast)


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

    Raises:
        ValueError: If ``lfp_trace`` (or, with ``normalize=True``, ``baseline``) is empty or
            non-finite, ``freq_range`` contains no Welch bin, the baseline has no power in
            ``freq_range``, or ``device`` is not a recognised device name.

    Example:
        >>> theta_power = band_power(lfp_data, fs=1000.0, freq_range=(4, 8), normalize=False)
        >>> baseline_power = band_power(baseline_lfp, fs=1000.0, freq_range=(4, 8), normalize=False)
        >>> normalized_power = band_power(lfp_data, fs=1000.0, freq_range=(4, 8), baseline=baseline_lfp)

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
    """
    fs = _resolve_fs(fs, sampling_rate, "band_power")
    lfp_trace = _require_finite_nonempty_trace(lfp_trace, "band_power")
    if normalize:
        if baseline is None or np.size(baseline) == 0:
            raise ValueError(
                "band_power(normalize=True) requires a non-empty baseline trace for dB normalization"
            )
        baseline = _require_finite_nonempty_trace(baseline, "band_power", name="baseline")
    device = resolve_device(device, context="band_power", prefer="cupy", stacklevel=3)

    def _welch(trace):
        nperseg = min(len(trace), 4096)
        if device == CUDA:
            try:
                freqs, pxx, _, _ = _welch_csd_gpu(trace, trace, fs, nperseg)
                return freqs, pxx
            except Exception as e:
                warn_device_fallback("band_power", e, stacklevel=4)
        return signal.welch(trace, fs=fs, nperseg=nperseg)

    frequencies, pxx = _welch(lfp_trace)

    # Extract band
    mask = (frequencies >= freq_range[0]) & (frequencies <= freq_range[1])
    if not np.any(mask):
        raise ValueError(
            f"band_power found no Welch bins in freq_range={freq_range}; "
            f"grid spans [{frequencies[0]:.4g}, {frequencies[-1]:.4g}] Hz"
        )
    band_power_val = float(np.mean(pxx[mask]))

    if normalize:
        # The baseline has its own Welch grid when its length differs from the trace's; the
        # trace's mask applied to it raised IndexError.
        baseline_freqs, baseline_pxx = _welch(baseline)
        baseline_mask = (baseline_freqs >= freq_range[0]) & (baseline_freqs <= freq_range[1])
        if not np.any(baseline_mask):
            raise ValueError(
                f"band_power found no Welch bins of the baseline in freq_range={freq_range}; "
                f"baseline grid spans [{baseline_freqs[0]:.4g}, {baseline_freqs[-1]:.4g}] Hz"
            )
        baseline_power_val = float(np.mean(baseline_pxx[baseline_mask]))
        if not baseline_power_val > 0:
            # This returned the linear power, not a dB value, with no indication.
            raise ValueError(
                "band_power: the baseline has no power in freq_range, so the dB ratio is undefined"
            )
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
    frequency), so it is the preferred estimator when zero-lag volume conduction must be
    suppressed.
    Callers are responsible for re-referencing (see ``bipolar_reference`` /
    ``laplacian_reference``) before calling this; imaginary coherency controls
    for zero-lag mixing but does not substitute for reducing it upstream.

    Args:
        x, y: 1D time series of equal length, same sampling rate, already
            re-referenced (bipolar or Laplacian) to reduce shared-reference mixing.
        fs: Sampling frequency in Hz (canonical).
        sampling_rate: Supported alias for `fs` in Hz.
        freq_range: (min_freq, max_freq) in Hz to average coherency over.
        nperseg: Welch/CSD segment length; defaults to ``min(max(N // 8, 8), 1024)``,
            which keeps at least 2 segments so the ratio is identifiable.
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

    Raises:
        ValueError: If `x` and `y` are empty, differ in length, contain NaN or Inf,
            yield fewer than 2 Welch segments, or `freq_range` selects no frequency bin.

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
    _require_equal_lengths(x, y, "imaginary_coherency")
    _require_finite_nonempty_pair(x, y, "imaginary_coherency")
    n = len(x)

    if nperseg is None:
        nperseg = min(max(n // 8, MIN_COHERENCE_NPERSEG), 1024)
    if noverlap is None:
        noverlap = nperseg // 2
    _require_identifiable_segmentation(n, nperseg, noverlap, "imaginary_coherency", "coh_mag_mean")

    device = resolve_device(device, context="imaginary_coherency", prefer="cupy", stacklevel=3)
    if device == 'cuda':
        try:
            freqs, pxx, pyy, sxy = _welch_csd_gpu(x, y, fs, nperseg, noverlap)
        except Exception as e:
            warn_device_fallback("imaginary_coherency", e)
            device = 'cpu'
    if device != 'cuda':
        freqs, pxx = signal.welch(x, fs=fs, nperseg=nperseg, noverlap=noverlap)
        _, pyy = signal.welch(y, fs=fs, nperseg=nperseg, noverlap=noverlap)
        _, sxy = signal.csd(x, y, fs=fs, nperseg=nperseg, noverlap=noverlap)

    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    _require_band_bins(freqs, mask, freq_range, "imaginary_coherency")

    # Coherency is scale-invariant, so its guard must be too. An absolute floor of 1e-30 on
    # pxx*pyy is a statement about units: the product of two PSDs scales as the fourth power
    # of the signal amplitude, so a recording stored in a smaller unit walks into the clip
    # and the estimate collapses. Measured on a genuinely coherent pair, icoh_mean held at
    # -0.5144 down to a scale of 1e-6 and then fell to -0.000142 at 1e-8 and to zero below
    # that -- a fabricated zero produced by the choice of unit alone. A floor relative to
    # the band's own largest product scales with the data and leaves the ratio untouched.
    prod = pxx[mask] * pyy[mask]
    prod_scale = float(np.max(prod)) if prod.size else 0.0
    floor = np.finfo(float).tiny if prod_scale <= 0.0 else prod_scale * 1e-24
    denom = np.sqrt(np.clip(prod, floor, None))
    coherency = sxy[mask] / denom
    im_part = np.imag(coherency)
    coh_mag = np.abs(coherency) ** 2

    return {
        "icoh_mean": float(np.mean(im_part)),
        "icoh_abs_mean": float(np.mean(np.abs(im_part))),
        "coh_mag_mean": float(np.mean(coh_mag)),
        "n_freqs": int(np.sum(mask)),
    }


def wpli(
    x: np.ndarray,
    y: np.ndarray,
    fs: Optional[float] = None,
    sampling_rate: Optional[float] = None,
    freq_range: Tuple[float, float] = (1.0, 90.0),
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    device: str = "cpu",
) -> Dict[str, Any]:
    r"""Weighted Phase Lag Index (wPLI) between two continuous signals.

    wPLI (Vinck et al., 2011) evaluates the consistency of non-zero-phase-lag coupling
    between two signals by weighting phase leads and lags by the magnitude of the
    imaginary cross-spectrum across segments:

    .. math::
        \text{wPLI}(f) = \frac{|\sum_k \text{Im}(S_{xy, k}(f))|}{\sum_k |\text{Im}(S_{xy, k}(f))|}

    By weighting solely by the imaginary component of the cross-spectral density,
    wPLI reduces sensitivity specifically to zero-phase-lag coupling (such as
    instantaneous volume conduction or shared-reference contamination). It does not
    confer immunity to volume conduction, non-zero-lag common inputs, source mixing,
    or reference-induced phase structure.

    wPLI magnitude is strictly unsigned (:math:`\ge 0`) and measures coupling
    consistency, not directional propagation. To infer lead/lag directionality or
    delay, see :func:`jnwb.phase_slope_index` or :func:`jnwb.zflip`.

    Args:
        x, y: 1D time series of equal length.
        fs: Sampling frequency in Hz (canonical).
        sampling_rate: Supported alias for `fs` in Hz.
        freq_range: `(min_freq, max_freq)` in Hz to average wPLI over.
        nperseg: Welch segment length; defaults to ``min(max(N // 8, 8), 256)``, which
            keeps at least 2 segments so the ratio is identifiable.
        noverlap: Welch segment overlap; defaults to `nperseg // 2`.
        device: `'cpu'` or `'cuda'` (CuPy). A CUDA failure recomputes on CPU and emits a
            RuntimeWarning.

    Returns:
        Dict with:
        - ``wpli``: Float average of standard wPLI across `freq_range`.
        - ``wpli_debiased_sq``: Float average of debiased squared wPLI across `freq_range`.
        - ``freqs``: 1D array of frequency bins.
        - ``wpli_spectrum``: 1D array of standard wPLI across all frequencies.
        - ``n_segments``: Number of Welch segments evaluated.
        - ``n_freqs``: Number of frequency bins within `freq_range`.

        A frequency whose segment cross-spectra are all exactly zero-lag reports 0. The
        estimate does not depend on the amplitude units of `x` and `y`.

    Raises:
        ValueError: If `x` and `y` are empty, differ in length, contain NaN or Inf,
            yield fewer than 2 Welch segments, or `freq_range` selects no frequency bin.

    References:
        Vinck, M., et al. (2011). An improved index of phase-synchronization for
        electrophysiological data in the presence of volume-conduction, noise and
        sample-size bias. NeuroImage. doi:10.1016/j.neuroimage.2011.01.055
    """
    fs = _resolve_fs(fs, sampling_rate, "wpli")
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    _require_equal_lengths(x, y, "wpli")
    _require_finite_nonempty_pair(x, y, "wpli")
    n = len(x)

    if nperseg is None:
        nperseg = min(max(n // 8, MIN_COHERENCE_NPERSEG), 256)
    if noverlap is None:
        noverlap = nperseg // 2
    _require_identifiable_segmentation(n, nperseg, noverlap, "wpli", "wpli")

    device = resolve_device(device, context="wpli", prefer="cupy", stacklevel=3)
    if device == "cuda":
        try:
            import cupy as cp
            from scipy import fft as sp_fft

            x_g = cp.asarray(x, dtype=cp.float64)
            y_g = cp.asarray(y, dtype=cp.float64)
            n_segments = welch_segment_count(n, nperseg, noverlap)
            starts = cp.arange(n_segments) * (nperseg - noverlap)
            index = starts[:, None] + cp.arange(nperseg)[None, :]
            # Periodic Hann and no detrending, as scipy.signal.stft on the CPU path.
            window = 0.5 - 0.5 * cp.cos(2.0 * cp.pi * cp.arange(nperseg) / nperseg)
            X_fft = cp.fft.rfft(x_g[index] * window, axis=-1)  # (n_seg, n_freqs)
            Y_fft = cp.fft.rfft(y_g[index] * window, axis=-1)
            w_f, w_deb_sq_f = _wpli_from_cross_spectra((cp.conj(X_fft) * Y_fft).T, xp=cp)
            # The CPU grid, so both devices select the same bins at a band edge.
            freqs = sp_fft.rfftfreq(nperseg, 1.0 / fs)
            w_f = w_f.get()
            w_deb_sq_f = w_deb_sq_f.get()
        except Exception as e:
            warn_device_fallback("wpli", e)
            device = "cpu"

    if device != "cuda":
        # CPU STFT
        freqs, _, Zx = signal.stft(
            x, fs=fs, nperseg=nperseg, noverlap=noverlap, boundary=None, padded=False
        )
        _, _, Zy = signal.stft(
            y, fs=fs, nperseg=nperseg, noverlap=noverlap, boundary=None, padded=False
        )
        w_f, w_deb_sq_f = _wpli_from_cross_spectra(np.conj(Zx) * Zy)  # (n_freqs, n_segments)
        n_segments = Zx.shape[1]

    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    _require_band_bins(freqs, mask, freq_range, "wpli")
    wpli_val = float(np.mean(w_f[mask]))
    wpli_deb_sq_val = float(np.mean(w_deb_sq_f[mask]))

    return {
        "wpli": wpli_val,
        "wpli_debiased_sq": wpli_deb_sq_val,
        "freqs": freqs,
        "wpli_spectrum": w_f,
        "n_segments": n_segments,
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
    order = (
        np.arange(channel_data.shape[0])
        if channel_order is None
        else _require_channel_permutation(
            channel_order, channel_data.shape[0], "bipolar_reference"
        )
    )
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

    Raises:
        ValueError: If ``channel_data`` is not 2-D, has fewer than 2 channels, or
            ``channel_order`` is not a permutation of ``range(n_channels)``.
    """
    channel_data = np.asarray(channel_data, dtype=float)
    if channel_data.ndim != 2:
        raise ValueError(f"channel_data must be 2D (n_channels, n_samples), got shape {channel_data.shape}")
    order = (
        np.arange(channel_data.shape[0])
        if channel_order is None
        else _require_channel_permutation(
            channel_order, channel_data.shape[0], "laplacian_reference"
        )
    )
    ordered = channel_data[order]
    n_ch = ordered.shape[0]
    if n_ch < 2:
        # A single contact has no neighbour; this returned the channel minus itself (zeros).
        raise ValueError(f"laplacian_reference needs at least 2 channels, got {n_ch}")
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
    """
    import cupy as cp
    if noverlap is None:
        noverlap = nperseg // 2
    step = nperseg - noverlap

    x_g = cp.asarray(x, dtype=cp.float64)
    y_g = cp.asarray(y, dtype=cp.float64)
    n = len(x_g)

    if n < nperseg:
        x_g = cp.pad(x_g, (0, nperseg - n))
        y_g = cp.pad(y_g, (0, nperseg - n))
        n = nperseg

    # Periodic Hann window matching scipy.signal.get_window('hann', nperseg)
    window = 0.5 - 0.5 * cp.cos(2.0 * cp.pi * cp.arange(nperseg) / nperseg)

    segments_x = []
    segments_y = []
    start = 0
    while start + nperseg <= n:
        seg_x = x_g[start:start+nperseg]
        seg_y = y_g[start:start+nperseg]
        if detrend == "constant":
            seg_x = seg_x - cp.mean(seg_x)
            seg_y = seg_y - cp.mean(seg_y)
        segments_x.append(seg_x * window)
        segments_y.append(seg_y * window)
        start += step

    X = cp.fft.rfft(cp.stack(segments_x), axis=-1)
    Y = cp.fft.rfft(cp.stack(segments_y), axis=-1)

    scale = 1.0 / (fs * cp.sum(window ** 2))

    psd_x = cp.mean(cp.abs(X) ** 2, axis=0) * scale
    psd_y = cp.mean(cp.abs(Y) ** 2, axis=0) * scale
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

