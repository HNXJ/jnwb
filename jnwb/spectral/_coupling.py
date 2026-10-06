"""Coupling between two signals: coherence with a surrogate null, imaginary coherency and wPLI."""

import logging
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
from scipy import signal
from .._backend import CUDA, resolve_device, warn_device_fallback
from .._parallel import parallel_map
from .._rng import DEFAULT_SEED, RNGLike, recorded_rng
from ..permutation import _count_at_least_as_extreme
from .._spread import is_constant as _is_constant
from ._common import _require_band_bins, CANONICAL_BANDS, _resolve_fs
from ._psd import _welch_csd_gpu

log = logging.getLogger(__package__)


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


def _require_1d_pair(x, y, func_name: str) -> None:
    """Both traces are 1-D. `.ravel()` accepted a 2-D array and concatenated its channels
    end to end: `imaginary_coherency(np.stack([x, y]), np.stack([y, x]), fs=1000.)`
    returned a complete result computed across a discontinuity that is not in the data.
    `cross_area_coherence` refuses the same input with the same reasoning.
    """
    for name, trace in ((f"{func_name} x", x), (f"{func_name} y", y)):
        arr = np.asarray(trace)
        if arr.ndim != 1:
            raise ValueError(
                f"{name} must be a 1-D time series, got shape {arr.shape}. This function "
                "compares two traces; to work channel-by-channel, call it per channel "
                "pair. A 2-D array was previously flattened, which joined the channels "
                "end to end and estimated across the joins."
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


def cross_area_coherence(
    lfp_area1: np.ndarray,
    lfp_area2: np.ndarray,
    fs: Optional[float] = None,
    sampling_rate: Optional[float] = None,
    freq_bands: Union[Dict[str, Tuple[float, float]], str, None] = None,
    device: str = 'cpu',
    rng: RNGLike = DEFAULT_SEED,
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
        rng: Randomness for the surrogate shifts: an ``int`` seed, a
             ``numpy.random.Generator``, or ``None`` for fresh OS entropy. Defaults to
             ``DEFAULT_SEED`` (42), the seed this function has always used, so
             ``inspect.signature`` and ``help()`` report the stream a bare call draws.
             INTENTIONAL BREAK (0.2.6): the default was spelled ``None`` and resolved to
             ``SeedSequence(42)`` in the body. A bare call is unchanged --
             ``default_rng(42)`` and ``default_rng(SeedSequence(42))`` are the same
             stream -- but an explicit ``rng=None`` now means what it means everywhere
             else in this package and in NumPy: fresh entropy per call, where it
             previously returned seed 42's surrogates. A ``Generator`` gives up one
             draw, a child seed the surrogates run on and ``surrogate_seed_entropy``
             records. INTENTIONAL BREAK (0.2.10): a ``Generator`` was drawn from in
             place and recorded ``None``, so the result alone could not reproduce its
             p-values; the same ``Generator`` state now gives different shifts.
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
        - surrogate_seed_entropy: The entropy the surrogate generator was built from --
          42 for a bare call, the seed you passed for an int `rng`, the fresh OS
          entropy actually drawn for `rng=None`, and the child seed drawn from a
          `Generator`. Passing it back as `rng` reproduces the surrogates.

        When either trace is constant (every sample equal, all-zero included),
        `coherence_spectrum`, every `band_coherence` and `band_significance` entry and
        `peak_coherence_value` are NaN, and `peak_coherence_freq` is NaN: coherence with a
        channel that does not vary is undefined. The test is exact equality; a trace that
        varies only at rounding level is estimated, and its value is set by that residue.

    Example:
        >>> coh = cross_area_coherence(v1_lfp, pfc_lfp, fs=1000.0, freq_bands='canonical')
        >>> print(f"Alpha coherence: {coh['band_coherence']['alpha']:.3f}")
        >>> print(f"p >= {coh['p_value_floor']:.4f} by construction")

    References:
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
        -- the spectrum as the average of windowed periodograms over overlapping segments.
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
    # The seed is in the signature, not here: `inspect.signature` reports the stream a
    # bare call draws. It is resolved after the device (below), so an invalid device leaves
    # a caller's Generator untouched.

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
        'surrogate_seed_entropy': None,
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

        This used to say the two paths differ -- that scipy detrends each segment and
        uses a periodic Hann window "while `_welch_csd_gpu` uses a symmetric `hanning`
        and no detrend". That has not been true since the CUDA path was rewritten to
        match scipy: it builds the same periodic Hann and detrends by default, and
        measured on an RTX A4000 the two agree to 1.7e-16 relative on `psd_x` and
        3.6e-16 on the cross spectrum.

        The rule stands for the reason that does not depend on that: a null and the
        observed statistic it calibrates must come from the same estimator, because any
        difference between them is read as signal. Passing one estimator through, rather
        than choosing per call, is what makes that structural instead of incidental.
        """
        out = {'band_coherence': {}, 'band_significance': {}}
        frequencies, coherency = estimator(lfp_area1, lfp_area2)
        out['frequencies'] = frequencies
        out['coherence_spectrum'] = coherency

        peak_idx = int(np.argmax(coherency))
        out['peak_coherence_freq'] = float(frequencies[peak_idx])
        out['peak_coherence_value'] = float(coherency[peak_idx])

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
            k = _count_at_least_as_extreme(surrogate_cohs, mean_coh_val, "greater")
            p_val = (k + 1) / (int(n_surrogates) + 1)
            out['band_significance'][band_name] = float(p_val)

        return out

    # Resolve the device ONCE. The GPU path used to be attempted inside the surrogate
    # loop behind a per-iteration `except Exception`, so an intermittent failure (OOM
    # under memory pressure) silently produced a null mixing two estimators, with
    # nothing logged and nothing in the result. A GPU failure now discards the partial
    # work and recomputes everything, observed value included, on the CPU, so the
    # returned values share one estimator, named in `device_used`.
    device_used = resolve_device(device, context='cross_area_coherence', prefer='cupy')
    rng, result['surrogate_seed_entropy'] = recorded_rng(rng, "cross_area_coherence")

    # The shifts are drawn once, after the device resolves (an invalid device leaves a
    # caller's generator untouched) and before any device attempt. Drawn inside
    # `_compute_all`, a CUDA failure part-way through the null left `rng` advanced, so the
    # CPU recompute drew different shifts and p differed from a CPU run under the same seed.
    low_val, high_val = 1, len(lfp_area2) - 1
    shifts = (
        rng.integers(low_val, high_val, size=int(n_surrogates))
        if low_val < high_val
        else np.zeros(int(n_surrogates), dtype=int)
    )
    if _is_constant(lfp_area1) or _is_constant(lfp_area2):
        # Mean removal leaves rounding residue in a constant trace's segments, and the
        # ratio turned it into a coherence (about 0.05 on the CPU, 0.0 on CUDA).
        frequencies = np.fft.rfftfreq(nperseg, 1.0 / fs)
        result.update(
            frequencies=frequencies,
            coherence_spectrum=np.full(len(frequencies), np.nan),
            peak_coherence_freq=float('nan'),
            peak_coherence_value=float('nan'),
        )
        for band_name, (fmin, fmax) in freq_bands.items():
            if np.any((frequencies >= fmin) & (frequencies <= fmax)):
                result['band_coherence'][band_name] = float('nan')
                result['band_significance'][band_name] = float('nan')
        result['device_used'] = device_used
        return result

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
        device: 'cpu' or 'cuda' (CuPy). A GPU failure warns and recomputes on the CPU;
            ``device_used`` records which ran.

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
          - ``device_used``: 'cpu' or 'cuda', the device that computed the spectra.

        When `x` or `y` is constant, all-zero included, ``icoh_mean``, ``icoh_abs_mean``
        and ``coh_mag_mean`` are NaN: coherency with a channel that does not vary is
        undefined.

    Raises:
        ValueError: If `x` and `y` are empty, differ in length, contain NaN or Inf,
            yield fewer than 2 Welch segments, or `freq_range` selects no frequency bin.

    On synthetic data, a common zero-lag-mixed source drives coh_mag_mean up while
    icoh_mean stays near zero; a genuinely lagged shared source drives both up.

    Sign convention: the cross-spectrum is ``S_xy = E[X conj(Y)]``, the conjugate of what
    :func:`scipy.signal.csd` returns, so when `x` leads `y` the imaginary part is positive
    wherever the lag's phase is below pi. :func:`jnwb.phase_slope_index` follows the same
    convention: positive means `x` leads for both.

    References:
        Nolte, G., et al. (2004). Identifying true brain interaction from EEG data using the
        imaginary part of coherency. Clin. Neurophysiol. doi:10.1016/j.clinph.2004.04.029
        -- the imaginary part of coherency, which non-interacting sources mixed at zero lag
        leave at zero.
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
        -- the spectrum as the average of windowed periodograms over overlapping segments.
    """
    fs = _resolve_fs(fs, sampling_rate, "imaginary_coherency")
    _require_1d_pair(x, y, "imaginary_coherency")
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    _require_equal_lengths(x, y, "imaginary_coherency")
    _require_finite_nonempty_pair(x, y, "imaginary_coherency")
    flat = _is_constant(x) or _is_constant(y)
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
    # Both branches return scipy's orientation, E[conj(X) Y]. Its conjugate, E[X conj(Y)],
    # has a positive imaginary part when `x` leads -- the sign `phase_slope_index` reports.
    # Conjugation negates the imaginary part exactly and leaves every magnitude untouched.
    sxy = np.conj(sxy)

    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    _require_band_bins(freqs, mask, freq_range, "imaginary_coherency")

    # Coherency is scale-invariant, so its guard must be too. An absolute floor of 1e-30 on
    # pxx*pyy is a statement about units: the product of two PSDs scales as the fourth power
    # of the signal amplitude, so a recording stored in a smaller unit walks into the clip
    # and the estimate collapses. Measured on a genuinely coherent pair, |icoh_mean| held at
    # 0.5144 down to a scale of 1e-6 and then fell to 0.000142 at 1e-8 and to zero below
    # that -- a fabricated zero produced by the choice of unit alone. A floor relative to
    # the band's own largest product scales with the data and leaves the ratio untouched.
    prod = pxx[mask] * pyy[mask]
    prod_scale = float(np.max(prod)) if prod.size else 0.0
    floor = np.finfo(float).tiny if prod_scale <= 0.0 else prod_scale * 1e-24
    denom = np.sqrt(np.clip(prod, floor, None))
    coherency = sxy[mask] / denom
    im_part = np.imag(coherency)
    coh_mag = np.abs(coherency) ** 2
    if flat:
        im_part = coh_mag = np.full(int(np.sum(mask)), np.nan)

    return {
        "icoh_mean": float(np.mean(im_part)),
        "icoh_abs_mean": float(np.mean(np.abs(im_part))),
        "coh_mag_mean": float(np.mean(coh_mag)),
        "n_freqs": int(np.sum(mask)),
        "device_used": device,
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
        - ``device_used``: `'cpu'` or `'cuda'`, the device that computed the spectra.

        A frequency whose segment cross-spectra are all exactly zero-lag reports 0. The
        estimate does not depend on the amplitude units of `x` and `y`. When `x` or `y` is
        constant, all-zero included, ``wpli``, ``wpli_debiased_sq`` and every entry of
        ``wpli_spectrum`` are NaN: phase lag with a channel that does not vary is undefined.
        Constant means every sample equal. A channel that varies only at rounding level, one
        ulp from constant, is estimated from that residue, and the CPU and CUDA paths can
        return different values for it: device parity is undefined below working precision.

    Raises:
        ValueError: If `x` and `y` are empty, differ in length, contain NaN or Inf,
            yield fewer than 2 Welch segments, or `freq_range` selects no frequency bin.

    References:
        Vinck, M., et al. (2011). An improved index of phase-synchronization for
        electrophysiological data in the presence of volume-conduction, noise and
        sample-size bias. NeuroImage. doi:10.1016/j.neuroimage.2011.01.055 -- the weighted
        phase lag index above and the debiased estimator of squared wPLI. An imaginary part
        no larger than 1e-10 times its cross-spectrum's magnitude counts as zero lag.
    """
    fs = _resolve_fs(fs, sampling_rate, "wpli")
    _require_1d_pair(x, y, "wpli")
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    _require_equal_lengths(x, y, "wpli")
    _require_finite_nonempty_pair(x, y, "wpli")
    flat = _is_constant(x) or _is_constant(y)
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
    if flat:
        # Neither STFT removes the mean, so a constant trace keeps rounding residue in the
        # bins above DC, and wPLI, being scale-free, turned that residue into a value.
        w_f = np.full(len(freqs), np.nan)
        w_deb_sq_f = np.full(len(freqs), np.nan)

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
        "device_used": device,
    }
