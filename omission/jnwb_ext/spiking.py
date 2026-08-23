"""
Spiking Metrics and Omission Response Analysis

Consolidates logic from archived X-files:
- _response_metric_common.py
- build_spk_response_metric_contract.py
- classify_units_s_s_o.py (omission response classification)

compute_response_metrics, classify_response_significance, and phase_locking_index were
promoted 2026-08-23 to jnwb.spiking (99%-jnwb-sufficiency normalization) -- they took plain
spike-time arrays with no omission-task coupling. classify_omission_response stays here: its
parameter names and docstring are task-flavored (stimulus vs. omission trials), even though
its statistics (two-sample Mann-Whitney U on binned spike counts) are generic.

Author: Migrated from archived scripts
Date: 2026-06-25
"""

import logging
from typing import Optional, Tuple, Dict, List, Union
import numpy as np
import pandas as pd
from scipy import stats

from jnwb.spiking import compute_response_metrics, classify_response_significance, phase_locking_index

log = logging.getLogger(__name__)


def classify_omission_response(
    unit_spike_times: np.ndarray,
    stimulus_onsets: np.ndarray,
    omission_onsets: np.ndarray,
    response_window: Tuple[float, float] = (0.0, 0.150),
    p_threshold: float = 0.05
) -> Dict[str, Union[bool, float]]:
    """
    Classify unit response to stimulus vs. omission.

    Computes spike counts for stimulus and omission trials, tests for significant
    differences (sig_s = response to stimulus, sig_o = response to omission).

    Args:
        unit_spike_times: Array of spike times for unit (seconds)
        stimulus_onsets: Event onsets for stimulus trials
        omission_onsets: Event onsets for omission trials
        response_window: (start, stop) seconds relative to event onset
        p_threshold: P-value threshold for significance

    Returns:
        Dict with:
        - sig_s: bool (significant stimulus response)
        - sig_o: bool (significant omission response)
        - stimulus_rate: Firing rate during stimulus trials
        - omission_rate: Firing rate during omission trials
        - pvalue_stimulus: P-value for stimulus significance
        - pvalue_omission: P-value for omission significance

    Example:
        >>> classification = classify_omission_response(spikes, stim_onsets, omis_onsets)
        >>> if classification['sig_o']:
        ...     print("Unit responds to omission (ghost signal)")
    """
    result = {
        'sig_s': False,
        'sig_o': False,
        'stimulus_rate': 0.0,
        'omission_rate': 0.0,
        'pvalue_stimulus': 1.0,
        'pvalue_omission': 1.0,
        'n_stimulus_trials': len(stimulus_onsets),
        'n_omission_trials': len(omission_onsets)
    }

    response_start, response_stop = response_window
    response_duration = response_stop - response_start

    st = np.sort(unit_spike_times)

    # Count spikes in stimulus trials using searchsorted
    stimulus_counts = []
    for onset in stimulus_onsets:
        lo = np.searchsorted(st, onset + response_start, side='left')
        hi = np.searchsorted(st, onset + response_stop, side='right')
        stimulus_counts.append(hi - lo)

    # Count spikes in omission trials using searchsorted
    omission_counts = []
    for onset in omission_onsets:
        lo = np.searchsorted(st, onset + response_start, side='left')
        hi = np.searchsorted(st, onset + response_stop, side='right')
        omission_counts.append(hi - lo)

    stimulus_counts = np.array(stimulus_counts)
    omission_counts = np.array(omission_counts)

    # Compute rates
    if len(stimulus_counts) > 0:
        stim_rate = stimulus_counts.sum() / (len(stimulus_counts) * response_duration)
        result['stimulus_rate'] = float(stim_rate)

    if len(omission_counts) > 0:
        omis_rate = omission_counts.sum() / (len(omission_counts) * response_duration)
        result['omission_rate'] = float(omis_rate)

    # Mann-Whitney U test on spike counts (non-parametric)
    if len(stimulus_counts) > 1 and len(omission_counts) > 1:
        stat, pval = stats.mannwhitneyu(stimulus_counts, omission_counts, alternative='two-sided')
        result['pvalue_stimulus'] = pval
        result['pvalue_omission'] = pval

    # Significance tests (using binomial test or direct threshold)
    if np.mean(stimulus_counts) > 0:
        result['sig_s'] = result['pvalue_stimulus'] < p_threshold

    if np.mean(omission_counts) > 0:
        result['sig_o'] = result['pvalue_omission'] < p_threshold

    return result
