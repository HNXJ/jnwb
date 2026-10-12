"""
jnwb.spiking -- spike-response metrics: firing rate/latency/z-score relative to behavioral
epochs, significance classification, and spike-LFP phase locking.

``compute_response_metrics``, ``classify_response_significance``, and ``phase_locking_index``
take plain spike-time arrays and caller-supplied epoch windows or LFP phase traces.
"""

import logging
import warnings
from typing import Any, Optional, Tuple, Dict, List, Union
import numpy as np

from ._bins import onset_window, whole_bin_count
from ._spread import is_constant
from ._units import resolve_unit_alias
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
) -> Dict[str, Any]:
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
        - baseline_rates, response_rates: float arrays, one rate (spikes/s) per onset, in
          onset order. Zeros for every onset when there are no spikes, and empty with no
          onsets.
        - baseline_counts, response_counts: integer arrays, one spike count per onset, in
          the same order; the counts `classify_response_significance` tests.
        - baseline_duration_s, response_duration_s: each window's length in seconds.

    Raises:
        ValueError: a window whose start is at or after its stop.

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
    # A reversed window made a negative duration: the count went negative while the rate,
    # a negative count over a negative duration, came out positive.
    for name, (start, stop) in (("baseline_window_s", baseline_window_s),
                                ("response_window_s", response_window_s)):
        if not start < stop:
            raise ValueError(
                f"compute_response_metrics: {name} needs start < stop, got ({start}, {stop})"
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
        'n_trials': len(epoch_onsets),
        'baseline_rates': np.zeros(len(epoch_onsets)),
        'response_rates': np.zeros(len(epoch_onsets)),
        # Counts travel beside the rates because the test needs integers, and a rate times
        # its duration need not round-trip to the count exactly in floating point.
        'baseline_counts': np.zeros(len(epoch_onsets), dtype=np.int64),
        'response_counts': np.zeros(len(epoch_onsets), dtype=np.int64),
    }

    baseline_start, baseline_stop = baseline_window_s
    response_start, response_stop = response_window_s
    baseline_duration = baseline_stop - baseline_start
    response_duration = response_stop - response_start
    metrics['baseline_duration_s'] = float(baseline_duration)
    metrics['response_duration_s'] = float(response_duration)

    if len(epoch_onsets) == 0 or len(spike_times) == 0:
        return metrics

    baseline_spikes = []
    response_spikes = []
    latencies = []

    # Spike minus onset in each right-open window, by binary search on the sorted float64
    # train (`onset_window`, the rule `bin_spikes` and `fano_factor` use).
    st = np.sort(np.asarray(spike_times, dtype=float), axis=None)
    onsets = np.asarray(epoch_onsets, dtype=float).ravel()
    b_lo, b_hi = onset_window(st, onsets, baseline_start, baseline_stop)
    r_lo, r_hi = onset_window(st, onsets, response_start, response_stop)

    for i, onset in enumerate(onsets):
        baseline_spikes.append(b_hi[i] - b_lo[i])
        response_count = r_hi[i] - r_lo[i]
        response_spikes.append(response_count)

        # Compute latency (first spike in response window)
        if response_count > 0:
            latency = (st[r_lo[i]] - onset) - response_start
            latencies.append(latency)

    # Compute rates
    baseline_count_total = np.sum(baseline_spikes)
    response_count_total = np.sum(response_spikes)

    baseline_rate = baseline_count_total / (len(epoch_onsets) * baseline_duration)
    response_rate = response_count_total / (len(epoch_onsets) * response_duration)

    metrics['baseline_rate'] = float(baseline_rate)
    metrics['response_rate'] = float(response_rate)
    metrics['response_count'] = int(response_count_total)
    baseline_rates = np.array(baseline_spikes, dtype=float) / baseline_duration
    response_rates = np.array(response_spikes, dtype=float) / response_duration
    metrics['baseline_rates'] = baseline_rates
    metrics['response_rates'] = response_rates
    metrics['baseline_counts'] = np.array(baseline_spikes, dtype=np.int64)
    metrics['response_counts'] = np.array(response_spikes, dtype=np.int64)

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
    min_spike_count: int = 5,
    *,
    alpha: float = 0.05,
) -> Dict[str, Union[bool, float]]:
    """
    Classify a unit's response against its baseline from `compute_response_metrics` output.

    The p-value is the conditional binomial test of two Poisson counts, Przyborowski and
    Wilenski (1940), Biometrika 31(3/4):313-323, doi:10.2307/2332612. With ``K_r`` response
    and ``K_b`` baseline spikes summed over trials, ``N = K_r + K_b``, and ``d_r``, ``d_b``
    the window durations summed over trials, equal rates give
    ``K_r ~ Binomial(N, d_r / (d_r + d_b))``; the p-value is
    ``scipy.stats.binomtest(K_r, N, d_r / (d_r + d_b)).pvalue``, two-sided, and 1.0 when
    ``N = 0``. Conditioning on the counts makes it exact for any pair of window lengths and
    keeps it valid when the rate varies from trial to trial. It assumes Poisson firing
    within a trial; bursting or refractoriness inside a window breaks that assumption.
    Bursting makes the p-value too small, because the test counts each spike of a burst as
    an independent event. With no effect, 5 Hz firing in bursts of four spikes over 200
    trials and the default windows puts about 30% of units below p = 0.05 when the spikes
    of a burst are 4 ms apart, and about 18% when they are 50 ms apart. The p-value falls
    as trials accumulate at a fixed effect.

    ``response_zscore`` is the effect size: a response is significant when
    ``|response_zscore| >= zscore_threshold`` and ``p < alpha``. Among significant
    responses, ``|z| > 3`` is 'high' and the rest 'medium'.

    Args:
        metrics: Dict from compute_response_metrics(), carrying the per-trial
            `baseline_counts` and `response_counts` and the window lengths
            `baseline_duration_s` and `response_duration_s`.
        zscore_threshold: Effect-size cutoff on ``|response_zscore|``.
        min_spike_count: Minimum spikes needed in response window.
        alpha: Significance level for the p-value, in (0, 1); ``p < alpha`` is strict.

    Returns:
        Dict with:
        - is_significant: bool (both the effect-size cutoff and ``p < alpha`` pass)
        - pvalue: the binomial p-value; 1.0 with no spikes in either window and under
          'low'. Under 'undefined' it is still the binomial p when only `response_zscore`
          is NaN, since the test needs no baseline variance, and NaN otherwise.
        - confidence: 'high', 'medium', 'none', 'low' (fewer than `min_spike_count`
          response spikes), or 'undefined' when `response_zscore` is NaN because the
          baseline had no across-trial variance, when a count is NaN, or when `metrics`
          lacks the per-trial counts or window lengths (a `UserWarning` says so).
          `is_significant` is False under 'undefined' whatever the p, because the
          effect-size cutoff cannot be evaluated.

    Raises:
        ValueError: `alpha` outside (0, 1); count arrays that are not 1-D, differ in
            shape, or hold a negative or non-integer value; a window length that is not
            positive and finite.

    Example:
        >>> sig = classify_response_significance(metrics)
        >>> if sig['is_significant']:
        ...     print(f"Strong response (p={sig['pvalue']:.4f})")
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"classify_response_significance: alpha must be in (0, 1), got {alpha}")
    result = {
        'is_significant': False,
        'pvalue': 1.0,
        'confidence': 'none'
    }

    # Check minimum spike count
    if metrics.get('response_count', 0) < min_spike_count:
        result['confidence'] = 'low'
        return result

    needed = ('baseline_counts', 'response_counts', 'baseline_duration_s', 'response_duration_s')
    missing = [key for key in needed if key not in metrics]
    if missing:
        warnings.warn(
            f"classify_response_significance: metrics has no {missing}, so no test can run; "
            "pass the dict compute_response_metrics returns, which carries the per-trial "
            "counts. Classified 'undefined'.",
            UserWarning,
            stacklevel=2,
        )
        result['confidence'] = 'undefined'
        result['pvalue'] = float('nan')
        return result

    zscore = abs(metrics.get('response_zscore', 0.0))

    response_counts = np.asarray(metrics['response_counts'], dtype=float)
    baseline_counts = np.asarray(metrics['baseline_counts'], dtype=float)
    if response_counts.ndim != 1 or baseline_counts.ndim != 1:
        raise ValueError(
            "classify_response_significance: 'response_counts' and 'baseline_counts' must be "
            f"1-D, one count per trial; got shapes {response_counts.shape} and "
            f"{baseline_counts.shape}"
        )
    if response_counts.shape != baseline_counts.shape:
        raise ValueError(
            "classify_response_significance: 'response_counts' and 'baseline_counts' differ "
            f"in shape ({response_counts.shape} and {baseline_counts.shape})"
        )
    if np.isnan(response_counts).any() or np.isnan(baseline_counts).any():
        result['confidence'] = 'undefined'
        result['pvalue'] = float('nan')
        return result
    for name, counts in (('response_counts', response_counts),
                         ('baseline_counts', baseline_counts)):
        if np.any(counts < 0) or np.any(counts != np.round(counts)):
            raise ValueError(
                f"classify_response_significance: '{name}' must hold non-negative integers"
            )
    d_r = float(metrics['response_duration_s'])
    d_b = float(metrics['baseline_duration_s'])
    if not (np.isfinite(d_r) and np.isfinite(d_b) and d_r > 0 and d_b > 0):
        raise ValueError(
            "classify_response_significance: window lengths must be positive and finite, got "
            f"response {d_r} and baseline {d_b}"
        )

    # Equal trial counts in both arrays, so the summed durations are n * d_r and n * d_b
    # and the expected response share is d_r / (d_r + d_b).
    k_r = int(response_counts.sum())
    n_total = k_r + int(baseline_counts.sum())
    if n_total > 0:
        result['pvalue'] = float(
            stats.binomtest(k_r, n_total, d_r / (d_r + d_b), alternative='two-sided').pvalue
        )

    # NaN means the baseline had no across-trial variance, so the effect-size gate cannot be
    # evaluated; say so rather than treating it as z = 0. The counts test does not need that
    # variance, so its p stands.
    if np.isnan(zscore):
        result['confidence'] = 'undefined'
        return result

    if zscore >= zscore_threshold and result['pvalue'] < alpha:
        result['is_significant'] = True
        result['confidence'] = 'high' if zscore > 3.0 else 'medium'

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

        # P-value approximation for Rayleigh test: the large-n series truncated after its
        # first-order term, rayleigh_pvalue ≈ exp(-z) * (1 + (2*z - z^2) / (4*n)).
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


def _unit_trains(spike_times, name: str) -> List[np.ndarray]:
    """One 1-D float array of spike times (s) per unit; a bare train, as an array or a list
    of numbers, is refused as ambiguous."""
    if isinstance(spike_times, np.ndarray) and spike_times.dtype != object:
        single = True
    else:
        spike_times = list(spike_times)  # read a generator once, for the check and the trains
        single = any(np.ndim(u) == 0 for u in spike_times)
    if single:
        # A list of numbers would otherwise make every spike its own one-spike unit.
        raise ValueError(
            f"{name}: spike_times must be a sequence of per-unit 1-D arrays of spike times in "
            "seconds, got a single train; wrap one unit as [times]."
        )
    trains = [np.asarray(u, dtype=float).ravel() for u in spike_times]
    for i, u in enumerate(trains):
        if not np.all(np.isfinite(u)):
            raise ValueError(f"{name}: unit {i} has a non-finite spike time.")
    return trains


def _unit_counts(trains: List[np.ndarray], window_s, bin_ms: float) -> np.ndarray:
    """``(n_units, n_bins)`` counts in right-open bins, through `bin_spikes`'s whole-bin contract."""
    from .connectivity import bin_spikes
    if not np.isfinite(bin_ms) or bin_ms <= 0:
        raise ValueError(f"bin_ms must be positive and finite, got {bin_ms}.")
    if not trains:
        return np.zeros((0, 0))
    return np.vstack([bin_spikes([u], window_s=window_s, bin_size_ms=bin_ms) for u in trains])


def fleiss_kappa(counts: np.ndarray) -> float:
    r"""Fleiss' kappa: chance-corrected agreement of many raters on nominal categories (Fleiss 1971).

    ``counts[i, j]`` is how many raters put item ``i`` in category ``j``; every row sums to the
    same number of raters ``m >= 2``. With :math:`p_j` the share of all ratings in category
    ``j``, :math:`P_i = (\sum_j n_{ij}^2 - m) / (m(m-1))`, :math:`\bar P` their mean and
    :math:`P_e = \sum_j p_j^2`, kappa is :math:`(\bar P - P_e) / (1 - P_e)`.

    For binary spike states the items are time bins and the raters are units. From a boolean
    ``active`` array of shape ``(n_units, n_bins)``::

        k = active.sum(axis=0)
        counts = np.column_stack([active.shape[0] - k, k])

    Args:
        counts: ``(n_items, n_categories)`` array of non-negative integer rater counts.

    Returns:
        Kappa as a float: 1 for perfect agreement, 0 at chance, negative below chance.

    Raises:
        ValueError: If `counts` is not 2-D with at least one item and two categories, holds a
            negative, fractional or non-finite count, has rows with different sums or fewer than
            two raters per item, or is constant -- every rating in one category, where
            :math:`P_e = 1` and kappa is 0/0. A constant table is refused, never returned as 0.

    References:
        Fleiss, J. L. (1971). Measuring nominal scale agreement among many raters.
        Psychological Bulletin 76(5), 378-382. doi:10.1037/h0031619
    """
    arr = np.asarray(counts, dtype=float)
    if arr.ndim != 2 or arr.shape[0] < 1 or arr.shape[1] < 2:
        raise ValueError(
            f"fleiss_kappa: counts must be 2-D (n_items, n_categories) with at least one item "
            f"and two categories, got shape {arr.shape}."
        )
    if not np.all(np.isfinite(arr)) or np.any(arr < 0) or np.any(arr != np.round(arr)):
        raise ValueError("fleiss_kappa: counts must be non-negative integers.")
    m = arr.sum(axis=1)
    if np.any(m != m[0]):
        raise ValueError(
            f"fleiss_kappa: every item needs the same number of raters; row sums run from "
            f"{m.min():g} to {m.max():g}."
        )
    m = m[0]
    if m < 2:
        raise ValueError(f"fleiss_kappa: agreement needs at least two raters per item, got {m:g}.")
    p_j = arr.sum(axis=0) / (arr.shape[0] * m)
    p_e = float(np.sum(p_j ** 2))
    if p_e >= 1.0:
        raise ValueError(
            "fleiss_kappa: every rating falls in one category, so chance agreement is 1 and "
            "kappa is 0/0 (undefined)."
        )
    p_i = (np.sum(arr ** 2, axis=1) - m) / (m * (m - 1))
    return float((p_i.mean() - p_e) / (1.0 - p_e))


def spike_count_correlation(
    spike_times,
    window_s: Tuple[float, float],
    *,
    bin_ms: float,
) -> Dict[str, Any]:
    """Mean pairwise Pearson correlation of binned spike counts (Cohen and Kohn 2011).

    Each unit's spikes are counted in right-open bins of `bin_ms` over `window_s` (the
    `bin_spikes` contract), and the Pearson r of every pair of units' count series is averaged.
    The bin width sets the timescale the correlation measures, so it has no default.

    The samples are time bins within one window, not repeated trials, so a rate change shared
    by two units (signal correlation) raises r as much as shared trial-to-trial variability.
    This is not the trial-based noise correlation :math:`r_{sc}` of Cohen and Kohn (2011);
    for that, correlate per-trial counts, or subtract the trial-averaged rate from each bin first.

    A unit whose counts do not vary has no defined r with any partner. It is excluded and
    reported, never scored as r = 0, which would pull the mean toward zero.

    Args:
        spike_times: Sequence of per-unit 1-D arrays of spike times in seconds.
        window_s: ``(start, end)`` in seconds; the span must be at least 3 whole bins.
        bin_ms: Bin width in milliseconds; required.

    Returns:
        Dict with ``mean_r`` (NaN with fewer than two usable units), ``r`` (the
        ``(n_units, n_units)`` correlation matrix, NaN in excluded units' rows and columns and
        on the diagonal), ``n_pairs``, ``n_units``, ``n_bins``, ``excluded_units`` (indices of
        zero-variance units) and ``n_excluded``.

    Raises:
        ValueError: If `spike_times` is a bare array, a spike time is non-finite, `bin_ms` is not
            positive and finite, or the window is not whole bins or is fewer than 3 bins.

    References:
        Cohen, M. R., and Kohn, A. (2011). Measuring and interpreting neuronal correlations.
        Nature Neuroscience 14(7), 811-819. doi:10.1038/nn.2842
    """
    trains = _unit_trains(spike_times, "spike_count_correlation")
    counts = _unit_counts(trains, window_s, bin_ms)
    n_window_bins = whole_bin_count(window_s, float(bin_ms) / 1000.0, "spike_count_correlation",
                                    "window_s", unit="s")
    if n_window_bins < 3:
        # INTENTIONAL BREAK (0.2.10): 2 bins returned a mean of correlations that are all +1
        # or -1, since a Pearson r of two points is +-1 whatever the units do.
        raise ValueError(
            f"spike_count_correlation: window_s {tuple(window_s)} at bin_ms={bin_ms:g} gives "
            f"{n_window_bins} bins; a Pearson r needs at least 3, because with 2 every r is "
            "+1 or -1."
        )
    n_units = len(trains)
    n_bins = counts.shape[1] if n_units else 0
    excluded = [i for i in range(n_units) if np.all(counts[i] == counts[i, 0])] if n_bins else list(range(n_units))
    keep = [i for i in range(n_units) if i not in excluded]
    r = np.full((n_units, n_units), np.nan)
    if len(keep) >= 2:
        sub = np.corrcoef(counts[keep])
        r[np.ix_(keep, keep)] = sub
    np.fill_diagonal(r, np.nan)
    iu = np.triu_indices(len(keep), k=1)
    pair_r = r[np.ix_(keep, keep)][iu] if len(keep) >= 2 else np.array([])
    return {
        "mean_r": float(pair_r.mean()) if pair_r.size else float("nan"),
        "r": r,
        "n_pairs": int(pair_r.size),
        "n_units": n_units,
        "n_bins": int(n_bins),
        "excluded_units": np.asarray(excluded, dtype=int),
        "n_excluded": len(excluded),
    }


def _count_fano(counts) -> np.ndarray:
    """Fano factor of each row of a count array ``(n_rows, n_counts)``: the unbiased
    (ddof=1) variance over the mean, NaN where the mean is 0. The one Fano rule of the
    library; `fano_factor` and `UnitAnalyzer.quality_metrics` call it."""
    counts = np.asarray(counts, dtype=float)
    mean = counts.mean(axis=1)
    out = np.full(counts.shape[0], np.nan)
    ok = mean > 0
    out[ok] = counts[ok].var(axis=1, ddof=1) / mean[ok]
    return out


def fano_factor(
    spike_times,
    onsets_s,
    window_s: Tuple[float, float],
    *,
    summary: str,
) -> Dict[str, Any]:
    """Fano factor per unit across trials, summarised over units (Churchland et al. 2010).

    For each unit, the spikes whose time minus the onset lies in ``[window_s[0], window_s[1])``
    are counted on every trial, as in `bin_spikes`, and the count's across-trial variance
    (ddof=1, the unbiased estimate, so a Poisson unit has expectation 1) is divided by its mean. `summary` chooses
    the mean or the median over units and has no default.

    A unit with a zero mean count has no defined Fano factor. It is excluded and reported, never
    returned as 0 or 1.

    Args:
        spike_times: Sequence of per-unit 1-D arrays of spike times in seconds.
        onsets_s: 1-D array of trial onsets in seconds; at least two trials.
        window_s: ``(start, end)`` in seconds relative to each onset, start before end.
        summary: ``'mean'`` or ``'median'`` over the usable units; required.

    Returns:
        Dict with ``fano`` (the summary; NaN when no unit is usable), ``per_unit`` (NaN for
        excluded units), ``counts`` (``(n_units, n_trials)``), ``n_units``, ``n_trials``,
        ``excluded_units`` and ``n_excluded``.

    Raises:
        ValueError: If `spike_times` is a bare array, a time is non-finite, there are fewer than
            two onsets, the window's start is not before its end, or `summary` is not
            ``'mean'`` or ``'median'``.

    References:
        Churchland, M. M., et al. (2010). Stimulus onset quenches neural variability: a
        widespread cortical phenomenon. Nature Neuroscience 13(3), 369-378.
        doi:10.1038/nn.2501
    """
    if summary not in ("mean", "median"):
        raise ValueError(f"fano_factor: summary must be 'mean' or 'median', got {summary!r}.")
    trains = _unit_trains(spike_times, "fano_factor")
    onsets = np.asarray(onsets_s, dtype=float).ravel()
    if onsets.size < 2 or not np.all(np.isfinite(onsets)):
        raise ValueError(
            f"fano_factor: needs at least two trial onsets, all finite, for a variance; got "
            f"{onsets.size}, {int(np.sum(~np.isfinite(onsets)))} non-finite."
        )
    w0, w1 = (float(v) for v in window_s)
    if not (np.isfinite(w0) and np.isfinite(w1) and w0 < w1):
        raise ValueError(f"fano_factor: window_s start must be before its end, got {window_s}.")
    counts = np.zeros((len(trains), onsets.size))
    for i, u in enumerate(trains):
        lo, hi = onset_window(np.sort(u), onsets, w0, w1)
        counts[i] = hi - lo
    mean = counts.mean(axis=1) if trains else np.zeros(0)
    excluded = np.flatnonzero(mean == 0)
    per_unit = _count_fano(counts)
    usable = per_unit[mean > 0]
    agg = np.mean if summary == "mean" else np.median
    return {
        "fano": float(agg(usable)) if usable.size else float("nan"),
        "per_unit": per_unit,
        "counts": counts,
        "n_units": len(trains),
        "n_trials": int(onsets.size),
        "excluded_units": excluded,
        "n_excluded": int(excluded.size),
    }


def network_burst_index(
    spike_times,
    window_s: Tuple[float, float],
    *,
    bin_ms: float,
    threshold_hz: float,
    min_duration_ms: float,
) -> Dict[str, Any]:
    """Fraction of spikes inside network bursts found from the population rate (Wagenaar et al. 2006).

    All units' spikes are pooled and counted in right-open bins of `bin_ms` over `window_s`;
    the population rate of a bin is its count over the bin width (Hz, summed over units). A
    network burst is a maximal run of consecutive bins at or above `threshold_hz` lasting at
    least `min_duration_ms`. The index is the number of spikes in burst bins over all spikes in
    the window. Bin width, threshold and minimum duration each set what counts as a burst, so
    none has a default.

    Args:
        spike_times: Sequence of per-unit 1-D arrays of spike times in seconds.
        window_s: ``(start, end)`` in seconds; the span must be whole bins.
        bin_ms: Bin width in milliseconds; required.
        threshold_hz: Population-rate threshold in Hz, summed over units; required, positive.
        min_duration_ms: Shortest run that counts as a burst, in milliseconds; required,
            non-negative.

    Returns:
        Dict with ``burst_index`` (NaN when the window holds no spike), ``n_bursts``,
        ``bursts_s`` (``(n_bursts, 2)`` start and end times in seconds, right-open),
        ``n_spikes`` and ``n_spikes_in_bursts``.

    Raises:
        ValueError: If `spike_times` is a bare array, a time is non-finite, `bin_ms` or
            `threshold_hz` is not positive and finite, `min_duration_ms` is negative or
            non-finite, or the window is not whole bins.

    References:
        Wagenaar, D. A., Pine, J., and Potter, S. M. (2006). An extremely rich repertoire of
        bursting patterns during the development of cortical cultures. BMC Neuroscience 7, 11.
        doi:10.1186/1471-2202-7-11
    """
    if not np.isfinite(threshold_hz) or threshold_hz <= 0:
        raise ValueError(f"network_burst_index: threshold_hz must be positive and finite, got {threshold_hz}.")
    if not np.isfinite(min_duration_ms) or min_duration_ms < 0:
        raise ValueError(
            f"network_burst_index: min_duration_ms must be non-negative and finite, got {min_duration_ms}."
        )
    trains = _unit_trains(spike_times, "network_burst_index")
    pooled = np.concatenate(trains) if trains else np.zeros(0)
    counts = _unit_counts([pooled], window_s, bin_ms)[0]
    # Compared in counts and bins, with a relative tolerance: 7 spikes in a 70 ms bin is
    # 99.99999999999999 Hz in floating point, and "at or above 100 Hz" must include it.
    tol = 1.0 - 1e-9
    above = np.concatenate([[False], counts >= threshold_hz * bin_ms / 1000.0 * tol, [False]])
    edges = np.flatnonzero(np.diff(above.astype(int)))
    starts, stops = edges[0::2], edges[1::2]
    keep = (stops - starts) >= min_duration_ms / bin_ms * tol
    starts, stops = starts[keep], stops[keep]
    in_burst = int(sum(counts[a:b].sum() for a, b in zip(starts, stops)))
    total = int(counts.sum())
    t0 = float(window_s[0])
    step = bin_ms / 1000.0
    return {
        "burst_index": in_burst / total if total else float("nan"),
        "n_bursts": int(starts.size),
        "bursts_s": np.column_stack([t0 + starts * step, t0 + stops * step]).reshape(-1, 2),
        "n_spikes": total,
        "n_spikes_in_bursts": in_burst,
    }

