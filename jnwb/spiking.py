"""
jnwb.spiking -- generic spike-response metrics: firing rate/latency/z-score relative to
behavioral epochs, significance classification, and spike-LFP phase locking.

PROMOTED 2026-08-23 from omission.jnwb_ext.spiking (99%-jnwb-sufficiency normalization):
compute_response_metrics, classify_response_significance, and phase_locking_index take plain
spike-time arrays and generic (baseline_window, response_window) / (lfp_phase, lfp_timestamps)
parameters, with no omission-task conditions or OmissionSession coupling. classify_omission_
response stays in omission.jnwb_ext.spiking -- its parameter names (stimulus_onsets,
omission_onsets) and docstring are task-flavored, even though its statistical mechanism
(two-sample Mann-Whitney U on binned spike counts) is generic.

Consolidates logic from archived X-files:
- _response_metric_common.py
- build_spk_response_metric_contract.py
- classify_units_s_s_o.py (omission response classification, still in omission.jnwb_ext.spiking)

Author: Migrated from archived scripts
Date: 2026-06-25
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
        b_lo = np.searchsorted(st, onset + baseline_start, side='left')
        b_hi = np.searchsorted(st, onset + baseline_stop, side='right')
        baseline_count = b_hi - b_lo

        r_lo = np.searchsorted(st, onset + response_start, side='left')
        r_hi = np.searchsorted(st, onset + response_stop, side='right')
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
    Compute phase-locking index (PLI) between spikes and LFP phase.

    Measures whether spikes cluster in specific phases of an oscillation
    (e.g., prefer certain phases of theta, alpha, beta).

    Args:
        unit_spike_times: Spike times (seconds)
        lfp_phase: Phase values at each LFP timestamp (radians, -π to π)
        lfp_timestamps: Timestamps for LFP phase samples (seconds)
        n_bins: Number of phase bins for histogram (default: 18 = 20° bins)

    Returns:
        Dict with:
        - pli: Phase-locking index (0-1, higher = more locked)
        - phase_hist: Spike counts per phase bin
        - preferred_phase: Phase with most spikes (radians)
        - rayleigh_z: Rayleigh z-statistic for non-uniformity
        - rayleigh_pvalue: P-value for non-uniform distribution

    Example:
        >>> pli = phase_locking_index(spikes, lfp_phase, lfp_times)
        >>> print(f"Phase locking: {pli['pli']:.3f} (p={pli['rayleigh_pvalue']:.4f})")
    """
    result = {
        'pli': 0.0,
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

    # Phase-locking index (PLI) - deviation from uniform distribution
    uniform_expectation = np.mean(phase_hist)
    max_count = np.max(phase_hist)
    pli = (max_count - uniform_expectation) / (max_count + uniform_expectation) if (max_count + uniform_expectation) > 0 else 0
    result['pli'] = float(pli)

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
