"""
jnwb.spiking -- spike-response metrics: firing rate/latency/z-score relative to behavioral
epochs, significance classification, and spike-LFP phase locking.

``compute_response_metrics``, ``classify_response_significance``, and ``phase_locking_index``
take plain spike-time arrays and caller-supplied epoch windows or LFP phase traces.
"""

import logging
from typing import Optional, Tuple, Dict, List, Union
import numpy as np
import pandas as pd
from scipy import stats

log = logging.getLogger(__name__)


def compute_response_metrics(
    spike_times: np.ndarray,
    epoch_onsets: np.ndarray,
    baseline_window: Tuple[float, float] = (-0.250, -0.050),
    response_window: Tuple[float, float] = (0.0, 0.150),
    z_score: bool = True
) -> Dict[str, float]:
    """
    Compute firing rate and spike count metrics for stimulus responses.

    Args:
        spike_times: Array of spike times (seconds, relative to epoch start)
        epoch_onsets: Array of epoch start times (seconds)
        baseline_window: (start, stop) seconds relative to epoch onset for baseline
        response_window: (start, stop) seconds relative to epoch onset for response
        z_score: If True, return z-scored response relative to baseline

    Returns:
        Dict with metrics:
        - baseline_rate: Spikes/sec during baseline
        - response_rate: Spikes/sec during response window
        - response_count: Total spikes in response window
        - response_zscore: Z-score of response relative to baseline
        - latency: Time to first spike after response window start (or None)

    Example:
        >>> metrics = compute_response_metrics(spike_times, epoch_onsets)
        >>> print(f"Response z-score: {metrics['response_zscore']:.2f}")
    """
    metrics = {
        'baseline_rate': 0.0,
        'response_rate': 0.0,
        'response_count': 0,
        'response_zscore': 0.0,
        'latency': None,
        'n_trials': len(epoch_onsets)
    }

    if len(epoch_onsets) == 0 or len(spike_times) == 0:
        return metrics

    baseline_start, baseline_stop = baseline_window
    response_start, response_stop = response_window
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

    # Compute z-score
    if z_score and len(baseline_spikes) > 1:
        baseline_spikes_arr = np.array(baseline_spikes)
        response_spikes_arr = np.array(response_spikes)

        baseline_std = np.std(baseline_spikes_arr)
        if baseline_std > 0:
            baseline_mean = np.mean(baseline_spikes_arr)
            response_mean = np.mean(response_spikes_arr)
            response_zscore = (response_mean - baseline_mean) / baseline_std
            metrics['response_zscore'] = float(response_zscore)

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
        - confidence: Confidence level ('high', 'medium', 'low', or 'none')

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

    # Convert z-score to p-value
    zscore = abs(metrics.get('response_zscore', 0.0))
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

    Example:
        >>> res = phase_locking_index(spikes, lfp_phase, lfp_times)
        >>> print(f"Preferred phase: {res['preferred_phase']:.3f} (Rayleigh p={res['rayleigh_pvalue']:.4f})")
        >>> # For unbiased across-unit comparison, use PPC:
        >>> ppc = pairwise_phase_consistency(spike_phases)
    """
    result = {
        'peak_to_mean_contrast': 0.0,
        'pli': 0.0,  # Legacy alias for peak_to_mean_contrast
        'phase_hist': np.zeros(n_bins),
        'preferred_phase': 0.0,
        'rayleigh_z': 0.0,
        'rayleigh_pvalue': 1.0,
        'n_spikes': len(unit_spike_times)
    }

    if len(unit_spike_times) == 0:
        return result

    # Interpolate LFP phase at spike times
    spike_phases = np.interp(unit_spike_times, lfp_timestamps, lfp_phase, period=2*np.pi)

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

        # P-value approximation for Rayleigh test
        # For large n, rayleigh_pvalue ≈ exp(-z) * (1 + (2*z - z^2) / (4*n) - (24*z - 132*z^2 + 76*z^3 - 9*z^4) / (288*n^2))
        if z > 0:
            pval = np.exp(-z) * (1 + (2*z - z**2) / (4*len(spike_phases)))
            result['rayleigh_pvalue'] = float(min(pval, 1.0))

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
    return gaussian_filter1d(arr, sigma=sigma_bins, axis=axis, mode="reflect")

