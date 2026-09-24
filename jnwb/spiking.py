"""
jnwb.spiking -- spike-response metrics: firing rate/latency/z-score relative to behavioral
epochs, significance classification, and spike-LFP phase locking.

``compute_response_metrics``, ``classify_response_significance``, and ``phase_locking_index``
take plain spike-time arrays and caller-supplied epoch windows or LFP phase traces.
"""

import logging
import warnings
from typing import Optional, Tuple, Dict, List, Union
import numpy as np

from ._spread import is_constant
from ._units import resolve_unit_alias
import pandas as pd
from scipy import stats

log = logging.getLogger(__name__)


def compute_response_metrics(
    spike_times: np.ndarray,
    epoch_onsets: np.ndarray,
    baseline_window_s: Optional[Tuple[float, float]] = None,
    response_window_s: Optional[Tuple[float, float]] = None,
    z_score: bool = True,
    *,
    baseline_window: Optional[Tuple[float, float]] = None,
    response_window: Optional[Tuple[float, float]] = None,
) -> Dict[str, float]:
    """
    Compute firing rate and spike count metrics for stimulus responses.

    The windows are in **seconds**, and now say so. They used to be named
    `baseline_window` and `response_window`, which named no unit at all, while the
    `raster_psth(win_ms=)` a caller reaches in the same workflow is in milliseconds --
    `examples/tutorials/03_spiking.py` calls both in one body. Both take a float 2-tuple,
    so a swap is silent and is off by 1000. The old spellings still work; passing both
    names with different values is an error rather than a silent precedence rule.

    Args:
        spike_times: Array of spike times (seconds, relative to epoch start)
        epoch_onsets: Array of epoch start times (seconds)
        baseline_window_s: (start, stop) seconds relative to epoch onset for baseline
        response_window_s: (start, stop) seconds relative to epoch onset for response
        z_score: If True, return z-scored response relative to baseline
        baseline_window: Deprecated alias for `baseline_window_s`, same unit.
        response_window: Deprecated alias for `response_window_s`, same unit.

    Returns:
        Dict with metrics:
        - baseline_rate: Spikes/sec during baseline
        - response_rate: Spikes/sec during response window
        - response_count: Total spikes in response window
        - response_zscore: Z-score of the response FIRING RATE relative to the baseline
          firing rate across trials. Rates, not counts, so unequal window lengths do not
          manufacture a response. NaN when the baseline has no across-trial variance (the
          same count in every trial, silent or not), where the normal approximation is
          undefined; use a
          Poisson rate-ratio test for those units rather than reading NaN as zero.
        - latency: Time to first spike after response window start (or None)

    Example:
        >>> metrics = compute_response_metrics(spike_times, epoch_onsets)
        >>> print(f"Response z-score: {metrics['response_zscore']:.2f}")
    """
    baseline_window_s = resolve_unit_alias(
        baseline_window_s, baseline_window,
        canonical_name="baseline_window_s", alias_name="baseline_window",
        func_name="compute_response_metrics", default=(-0.250, -0.050),
    )
    response_window_s = resolve_unit_alias(
        response_window_s, response_window,
        canonical_name="response_window_s", alias_name="response_window",
        func_name="compute_response_metrics", default=(0.0, 0.150),
    )

    metrics = {
        'baseline_rate': 0.0,
        'response_rate': 0.0,
        'response_count': 0,
        # NaN: a z-score needs a baseline dispersion, which one trial does not provide and
        # zero spikes do not define. 0.0 reads as "measured, and exactly at baseline", and
        # `classify_response_significance` then returned confidence 'none' with pvalue 1.0
        # where the two-trial case correctly returned 'undefined' and NaN.
        'response_zscore': float('nan'),
        'latency': None,
        'n_trials': len(epoch_onsets)
    }

    if len(epoch_onsets) == 0 or len(spike_times) == 0:
        return metrics

    baseline_start, baseline_stop = baseline_window_s
    response_start, response_stop = response_window_s
    baseline_duration = baseline_stop - baseline_start
    response_duration = response_stop - response_start

    baseline_spikes = []
    response_spikes = []
    latencies = []

    # Pre-sort spike times to ensure searchsorted works correctly
    st = np.sort(spike_times)

    for onset in epoch_onsets:
        # Searchsorted instead of masking: O(log N) instead of O(N)
        # Bounded on right-open intervals [start, stop)
        b_lo = np.searchsorted(st, onset + baseline_start, side='left')
        b_hi = np.searchsorted(st, onset + baseline_stop, side='left')
        baseline_count = b_hi - b_lo

        r_lo = np.searchsorted(st, onset + response_start, side='left')
        r_hi = np.searchsorted(st, onset + response_stop, side='left')
        response_count = r_hi - r_lo

        baseline_spikes.append(baseline_count)
        response_spikes.append(response_count)

        # Compute latency (first spike in response window)
        if response_count > 0:
            latency = st[r_lo] - (onset + response_start)
            latencies.append(latency)

    # Compute rates
    baseline_count_total = np.sum(baseline_spikes)
    response_count_total = np.sum(response_spikes)

    baseline_rate = baseline_count_total / (len(epoch_onsets) * baseline_duration)
    response_rate = response_count_total / (len(epoch_onsets) * response_duration)

    metrics['baseline_rate'] = float(baseline_rate)
    metrics['response_rate'] = float(response_rate)
    metrics['response_count'] = int(response_count_total)

    # Compute z-score on RATES, not raw counts.
    #
    # The two windows need not be the same length, and the defaults are not: baseline is
    # 0.200 s and response 0.150 s. Differencing raw counts therefore charged a
    # homogeneous unit with a response it did not have, and the spurious z grew as the
    # square root of the firing rate because the count difference scales with the rate
    # while the baseline SD scales with its square root. A Poisson unit with no stimulus
    # response at all measured z = -0.47 at 20 Hz, -1.04 at 100 Hz and -1.91 at 500 Hz,
    # and `classify_response_significance` takes abs(z), so a fast non-responsive unit
    # would eventually be certified as responding. Dividing each window by its own
    # duration is exactly a no-op when the windows are equal, which is the case where
    # differencing counts was already correct.
    if z_score and len(baseline_spikes) > 1:
        baseline_rates = np.array(baseline_spikes, dtype=float) / baseline_duration
        response_rates = np.array(response_spikes, dtype=float) / response_duration

        baseline_std = np.std(baseline_rates)
        # Constancy by exact equality: 7 spikes in 0.15 s is 46.67 Hz in every trial, yet the
        # computed std is 7e-15, which made z about 1e15.
        if not is_constant(baseline_rates) and baseline_std > 0:
            response_zscore = (np.mean(response_rates) - np.mean(baseline_rates)) / baseline_std
            metrics['response_zscore'] = float(response_zscore)
        else:
            # A baseline with no across-trial variance leaves the normal approximation
            # undefined; it does not mean the unit failed to respond. Reporting 0.0 here
            # claimed 'no response' for the strongest possible evidence: a unit driven at
            # 133 Hz from a perfectly silent baseline returned z = +0.00, 'none'. NaN says
            # 'not assessable by this statistic' instead of fabricating a null result.
            metrics['response_zscore'] = float('nan')

    # Latency
    if latencies:
        metrics['latency'] = float(np.median(latencies))

    return metrics


def classify_response_significance(
    metrics: Dict[str, float],
    zscore_threshold: float = 1.96,
    min_spike_count: int = 5
) -> Dict[str, Union[bool, float]]:
    """
    Classify unit response as significant based on metrics.

    Args:
        metrics: Dict from compute_response_metrics()
        zscore_threshold: Z-score cutoff for significance (default: 1.96 = p<0.05)
        min_spike_count: Minimum spikes needed in response window

    Returns:
        Dict with:
        - is_significant: bool (response passes threshold)
        - pvalue: Approximate p-value from z-score
        - confidence: Confidence level ('high', 'medium', 'low', 'none', or 'undefined'
          when response_zscore is NaN because the baseline had no across-trial variance)

    Example:
        >>> sig = classify_response_significance(metrics)
        >>> if sig['is_significant']:
        ...     print(f"Strong response (p={sig['pvalue']:.4f})")
    """
    result = {
        'is_significant': False,
        'pvalue': 1.0,
        'confidence': 'none'
    }

    # Check minimum spike count
    if metrics.get('response_count', 0) < min_spike_count:
        result['confidence'] = 'low'
        return result

    # Convert z-score to p-value. NaN means the baseline had no across-trial variance, so
    # this statistic cannot assess the unit; say so rather than treating it as z = 0.
    zscore = abs(metrics.get('response_zscore', 0.0))
    if np.isnan(zscore):
        result['confidence'] = 'undefined'
        result['pvalue'] = float('nan')
        return result
    if zscore > 0:
        pvalue = 2 * (1 - stats.norm.cdf(zscore))
        result['pvalue'] = pvalue

        if zscore >= zscore_threshold:
            result['is_significant'] = True
            if zscore > 3.0:
                result['confidence'] = 'high'
            else:
                result['confidence'] = 'medium'

    return result


def phase_locking_index(
    unit_spike_times: np.ndarray,
    lfp_phase: np.ndarray,
    lfp_timestamps: np.ndarray,
    n_bins: int = 18
) -> Dict[str, Union[float, np.ndarray]]:
    """
    Compute circular phase distribution and Rayleigh non-uniformity test of spikes relative to LFP phase.

    Measures whether spikes cluster in specific phases of an oscillation (e.g. theta, alpha, beta).

    Warning:
        The heuristic histogram contrast returned in `peak_to_mean_contrast` (and its compatibility
        alias `pli`) exhibits severe sample-count bias (~1/sqrt(N) under noise). For inferential
        comparisons across units or conditions with differing spike counts, use
        `pairwise_phase_consistency` (PPC), which is an asymptotically unbiased estimator.

    Args:
        unit_spike_times: Spike times (seconds).
        lfp_phase: Phase values at each LFP timestamp (radians, -π to π).
        lfp_timestamps: Timestamps for LFP phase samples (seconds).
        n_bins: Number of phase bins for histogram (default: 18 = 20° bins).

    Returns:
        Dict with:
        - peak_to_mean_contrast: Heuristic histogram contrast (max - mean) / (max + mean) in [0, 1].
        - pli: Backwards-compatibility alias for `peak_to_mean_contrast` (subject to sample-count bias).
        - phase_hist: Spike counts per phase bin.
        - preferred_phase: Phase bin center with most spikes (radians).
        - rayleigh_z: Rayleigh z-statistic for circular non-uniformity.
        - rayleigh_pvalue: P-value for Rayleigh non-uniformity test.
        - n_spikes: Total number of spike times evaluated.

        With no spike inside the LFP window, ``n_spikes`` is 0, ``phase_hist`` is all zeros, and
        ``peak_to_mean_contrast``, ``pli``, ``preferred_phase``, ``rayleigh_z`` and
        ``rayleigh_pvalue`` are NaN.

    Example:
        >>> res = phase_locking_index(spikes, lfp_phase, lfp_times)
        >>> print(f"Preferred phase: {res['preferred_phase']:.3f} (Rayleigh p={res['rayleigh_pvalue']:.4f})")
        >>> # For unbiased across-unit comparison, use PPC:
        >>> ppc = pairwise_phase_consistency(spike_phases)
    """
    # No spike, no phase: every value field stays NaN until a spike phase is computed.
    result = {
        'peak_to_mean_contrast': float('nan'),
        'pli': float('nan'),  # Legacy alias for peak_to_mean_contrast
        'phase_hist': np.zeros(n_bins),
        'preferred_phase': float('nan'),
        'rayleigh_z': float('nan'),
        'rayleigh_pvalue': float('nan'),
        'n_spikes': len(unit_spike_times)
    }

    if len(unit_spike_times) == 0:
        return result

    # Interpolate the LFP phase at spike times through its unit vector.
    #
    # np.interp's `period` is the period of the x coordinates, not of fp, so
    # `period=2*np.pi` wrapped the spike times and the LFP timestamps modulo 6.2832
    # SECONDS. Any recording longer than that was folded onto itself and each spike took
    # the phase of an unrelated moment. A unit locked to phase 0 with 2 ms jitter over
    # 60 s, whose true resultant length is 0.995, reported pli 0.305; the same unit
    # reported 0.804 over its first 6 s, because the defect scales with duration.
    #
    # Interpolating cos and sin separately handles the +-pi wrap that `period` was
    # presumably meant to address, and leaves the time axis alone.
    # np.interp clamps, so every spike outside [t0, t1] received the identical endpoint
    # phase and the resultant length grew with the number of excluded spikes. Ten spikes
    # 500 s past the end of a 10 s recording reported rayleigh_z 10.0 -- exactly n, the
    # maximal resultant -- with p = 0.0; mixing five of them with five in-range spikes
    # gave p = 0.0234 where the five real spikes alone give p = 0.8335.
    unit_spike_times = np.asarray(unit_spike_times, dtype=float)
    lfp_timestamps = np.asarray(lfp_timestamps, dtype=float)
    t_lo, t_hi = float(lfp_timestamps[0]), float(lfp_timestamps[-1])
    in_range = (unit_spike_times >= t_lo) & (unit_spike_times <= t_hi)
    n_excluded = int((~in_range).sum())
    result['n_spikes_outside_lfp_window'] = n_excluded
    if n_excluded:
        warnings.warn(
            f"phase_locking_index: {n_excluded} of {unit_spike_times.size} spike(s) fall "
            f"outside the LFP window [{t_lo:g}, {t_hi:g}] s and are excluded. They used to "
            "be assigned the nearest endpoint phase, which inflates the resultant length.",
            RuntimeWarning,
            stacklevel=2,
        )
    unit_spike_times = unit_spike_times[in_range]
    result['n_spikes'] = int(unit_spike_times.size)
    if unit_spike_times.size == 0:
        return result

    cos_phase = np.interp(unit_spike_times, lfp_timestamps, np.cos(lfp_phase))
    sin_phase = np.interp(unit_spike_times, lfp_timestamps, np.sin(lfp_phase))
    spike_phases = np.arctan2(sin_phase, cos_phase)

    # Phase histogram
    phase_hist, bin_edges = np.histogram(spike_phases, bins=n_bins, range=(-np.pi, np.pi))
    result['phase_hist'] = phase_hist

    # Preferred phase
    preferred_bin = np.argmax(phase_hist)
    preferred_phase = bin_edges[preferred_bin] + (bin_edges[1] - bin_edges[0]) / 2
    result['preferred_phase'] = float(preferred_phase)

    # Heuristic peak-to-mean histogram contrast: (max - mean) / (max + mean)
    # WARNING: This quantity exhibits severe positive sample-size bias (~1/sqrt(N) under noise).
    # For population comparisons across units with differing spike counts, use pairwise_phase_consistency.
    uniform_expectation = np.mean(phase_hist)
    max_count = np.max(phase_hist)
    contrast = (max_count - uniform_expectation) / (max_count + uniform_expectation) if (max_count + uniform_expectation) > 0 else 0.0
    result['peak_to_mean_contrast'] = float(contrast)
    result['pli'] = float(contrast)  # Retained for backwards compatibility

    # Rayleigh test for non-uniformity
    if len(spike_phases) > 0:
        sin_sum = np.sum(np.sin(spike_phases))
        cos_sum = np.sum(np.cos(spike_phases))
        r = np.sqrt(sin_sum**2 + cos_sum**2) / len(spike_phases)
        z = len(spike_phases) * r**2

        result['rayleigh_z'] = float(z)
        # z == 0 is a measured zero resultant, whose p-value is exactly 1.
        result['rayleigh_pvalue'] = 1.0

        # P-value approximation for Rayleigh test
        # For large n, rayleigh_pvalue ≈ exp(-z) * (1 + (2*z - z^2) / (4*n) - (24*z - 132*z^2 + 76*z^3 - 9*z^4) / (288*n^2))
        if z > 0:
            pval = np.exp(-z) * (1 + (2*z - z**2) / (4*len(spike_phases)))
            # The series expansion goes negative for large z, and a negative p-value
            # passes every `p < alpha` test and corrupts any FDR machinery downstream.
            # `+ 0.0` normalizes the IEEE -0.0 that underflow produces here.
            result['rayleigh_pvalue'] = float(min(max(pval, 0.0), 1.0)) + 0.0

    return result


def pairwise_phase_consistency(
    phases: np.ndarray,
    axis: int = -1,
) -> Union[float, np.ndarray]:
    """Compute the Pairwise Phase Consistency (PPC) across angular samples (Vinck et al., 2010).

    PPC is an unbiased estimator of rhythmic phase synchronization. Unlike the mean resultant
    length or histogram-based phase-locking indices, PPC has an expected value that is
    statistically independent of the number of spikes or observations (N).

    Contract:
        - Accepts phases directly in radians [-pi, pi) or [0, 2*pi). Phase extraction from
          continuous signals is kept strictly separate.
        - Evaluates along `axis` (default: -1).
        - For N < 2 observations along the evaluated axis, PPC is non-identifiable and returns
          NaN (never 0.0).
        - Uses the exact O(N) resultant formulation:
          PPC = (|sum e^(i*theta)|^2 - N) / (N * (N - 1))
          which is mathematically identical to the O(N^2) double sum over all unique pairs.
        - Identical phases yield 1.0.
        - Rotation-invariant: PPC(theta + phi) == PPC(theta).
        - Under a circular uniform distribution null, E[PPC] == 0.

    Args:
        phases: Array containing phase angles in radians.
        axis: Axis along which to compute PPC (default: -1).

    Returns:
        PPC value (float for 1D input, or ndarray with `axis` reduced). Returns NaN where N < 2.

    References:
        Vinck, M., et al. (2010). The pairwise phase consistency: a bias-free measure of
        rhythmic neuronal synchronization. NeuroImage. doi:10.1016/j.neuroimage.2010.01.073
        -- the PPC, the mean cosine of the phase difference over all pairs of observations,
        computed through the resultant formula above.
    """
    arr = np.asarray(phases, dtype=float)
    n = arr.shape[axis] if arr.ndim > 0 else 0
    if n < 2:
        if arr.ndim <= 1:
            return float("nan")
        out_shape = list(arr.shape)
        out_shape.pop(axis)
        return np.full(out_shape, np.nan, dtype=float)

    cos_sum = np.sum(np.cos(arr), axis=axis)
    sin_sum = np.sum(np.sin(arr), axis=axis)
    result = (cos_sum**2 + sin_sum**2 - n) / (n * (n - 1))
    if np.ndim(result) == 0:
        return float(result)
    return result


def gaussian_smooth_rate(
    rate: np.ndarray,
    bin_ms: float,
    sigma_ms: float = 20.0,
    axis: int = -1,
) -> np.ndarray:
    """Apply symmetrical, acausal Gaussian smoothing to a binned firing rate trace.

    Unlike causal exponential smoothing (`causal_exp_smooth`), symmetrical Gaussian smoothing
    does not introduce the systematic one-sided forward delay characteristic of causal filters.
    It is suited for instantaneous firing rate visualization, PSTH curve presentation, and
    population trajectory (PCA) state-space construction. Note: as an acausal filter, it smooths
    bidirectionally across temporal boundaries.

    Args:
        rate: Array of firing rates (or spike counts) of arbitrary dimension.
        bin_ms: Width of each time bin in milliseconds. Must be strictly positive.
        sigma_ms: Standard deviation of Gaussian smoothing kernel in milliseconds (default: 20.0).
            If sigma_ms <= 0, returns a copy of `rate` un-smoothed.
        axis: Axis along which to smooth (default: -1, the time axis).

    Non-finite input:
        A Gaussian kernel is a weighted sum, so one non-finite bin contaminates every bin the
        kernel reaches. This is the one consumer of six that accepts an epoch truncated by the
        end of the recording, and it used to neither refuse nor report the support it lost.
        Measured at ``bin_ms=10, sigma_ms=20``: an interior NaN bin widens 1 into 17, and the
        NaN a boundary policy actually produces sits at an *epoch edge*, where the kernel
        reaches one side only and the same call widens 1 into 9. Contamination is nine times
        the defect at the boundary and seventeen times it in the interior.

        The array is still returned -- refusing would break every caller who is knowingly
        smoothing a padded epoch -- but a ``RuntimeWarning`` now names how many bins went in
        non-finite and how many came out that way, so the loss is reported rather than
        silent. Mask or interpolate before calling if the spread is unacceptable.

    Returns:
        Smoothed array of the same shape and float dtype as `rate`.

    Raises:
        ValueError: If `bin_ms <= 0`.
    """
    if bin_ms <= 0:
        raise ValueError(f"bin_ms must be strictly positive; got {bin_ms}.")
    arr = np.asarray(rate, dtype=float)
    if sigma_ms <= 0:
        return arr.copy()

    from scipy.ndimage import gaussian_filter1d
    sigma_bins = sigma_ms / bin_ms
    out = gaussian_filter1d(arr, sigma=sigma_bins, axis=axis, mode="reflect")

    # Measured on the output rather than predicted from sigma: the kernel's reach is truncated
    # at an array edge, so a boundary NaN spreads less far than an interior one and a computed
    # radius would overstate the loss at exactly the position where the loss actually occurs.
    # No `nan_policy` argument is offered here on purpose -- whether an additive public API
    # change requires a CHANGELOG entry and a deprecation path is not yet decided, and
    # warning needs no new parameter.
    n_bad_in = int(np.count_nonzero(~np.isfinite(arr)))
    if n_bad_in:
        n_bad_out = int(np.count_nonzero(~np.isfinite(out)))
        warnings.warn(
            f"gaussian_smooth_rate: {n_bad_in} non-finite bin(s) of {arr.size} spread to "
            f"{n_bad_out} after smoothing at sigma_ms={sigma_ms} / bin_ms={bin_ms} "
            f"({sigma_bins:g} bins). A Gaussian kernel is a weighted sum, so every bin the "
            "kernel reaches is contaminated. Mask or interpolate the non-finite bins before "
            "smoothing if that spread is not intended.",
            RuntimeWarning,
            stacklevel=2,
        )
    return out

