"""
Functional Connectivity, Mutual Information, and Granger Causality

Provides methods to compute directional functional connectivity metrics (bivariate Granger Causality),
Shannon Mutual Information between spike trains, and network graph analysis.

Author: Claude Code
Date: 2026-06-30
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
import numpy as np

log = logging.getLogger(__name__)


def spike_mutual_information(
    spike_times1: np.ndarray,
    spike_times2: np.ndarray,
    time_window: Tuple[float, float],
    bin_size_ms: float = 10.0
) -> float:
    """
    Compute Shannon Mutual Information (MI) between two binned spike trains.

    Args:
        spike_times1: Spike times of unit 1 (seconds)
        spike_times2: Spike times of unit 2 (seconds)
        time_window: (start_time, end_time) in seconds
        bin_size_ms: Bin size in ms

    Returns:
        mi: Mutual Information in bits
    """
    if len(spike_times1) == 0 or len(spike_times2) == 0:
        return 0.0

    t_start, t_end = time_window
    bin_sec = bin_size_ms / 1000.0
    n_bins = int((t_end - t_start) / bin_sec)

    if n_bins <= 1:
        return 0.0

    bin_edges = np.linspace(t_start, t_end, n_bins + 1)

    # Bin the spike trains (binary occurrence per bin)
    st1 = np.sort(spike_times1)
    st2 = np.sort(spike_times2)

    hist1, _ = np.histogram(st1, bins=bin_edges)
    hist2, _ = np.histogram(st2, bins=bin_edges)

    x = (hist1 > 0).astype(int)
    y = (hist2 > 0).astype(int)

    # Joint distribution
    joint_hist, _, _ = np.histogram2d(x, y, bins=2, range=[[0, 2], [0, 2]])
    p_xy = joint_hist / n_bins

    # Marginals
    p_x = p_xy.sum(axis=1)
    p_y = p_xy.sum(axis=0)

    # Shannon MI calculation
    mi = 0.0
    for i in range(2):
        for j in range(2):
            if p_xy[i, j] > 0:
                mi += p_xy[i, j] * np.log2(p_xy[i, j] / (p_x[i] * p_y[j]))

    return float(mi)


def fit_var_bivariate(
    x: np.ndarray,
    y: np.ndarray,
    order: int
) -> Tuple[float, float]:
    """
    Fit restricted and unrestricted bivariate VAR models to compute Granger residuals.

    Args:
        x: Signal 1 (dependent variable)
        y: Signal 2 (causal variable candidate)
        order: Autoregressive order p

    Returns:
        var_restricted: Residual variance of X under autoregression of X alone
        var_unrestricted: Residual variance of X under autoregression of X + Y
    """
    n = len(x)
    if n <= order * 2 + 1:
        return 1.0, 1.0

    # Build target vector: X[p:]
    target = x[order:]
    n_samples = len(target)

    # Design matrix for restricted model: only past values of X
    # X_lag_i = x[order-i:n-i]
    X_reg = np.zeros((n_samples, order + 1))
    X_reg[:, 0] = 1.0  # intercept
    for i in range(1, order + 1):
        X_reg[:, i] = x[order - i: n - i]

    # Design matrix for unrestricted model: past values of X and Y
    XY_reg = np.zeros((n_samples, 2 * order + 1))
    XY_reg[:, 0] = 1.0  # intercept
    for i in range(1, order + 1):
        XY_reg[:, i] = x[order - i: n - i]
        XY_reg[:, order + i] = y[order - i: n - i]

    # Fit restricted model via least squares
    beta_restr, _, _, _ = np.linalg.lstsq(X_reg, target, rcond=None)
    residuals_restr = target - X_reg @ beta_restr
    var_restricted = np.var(residuals_restr, ddof=order + 1)

    # Fit unrestricted model
    beta_unrestr, _, _, _ = np.linalg.lstsq(XY_reg, target, rcond=None)
    residuals_unrestr = target - XY_reg @ beta_unrestr
    var_unrestricted = np.var(residuals_unrestr, ddof=2 * order + 1)

    return float(var_restricted), float(var_unrestricted)


def granger_causality(
    signal1: np.ndarray,
    signal2: np.ndarray,
    order: int = 5
) -> Dict[str, float]:
    """
    Compute bivariate Granger Causality (GC) values between two continuous signals.

    F_2_to_1 is the directional causality from Signal 2 -> Signal 1
    F_1_to_2 is the directional causality from Signal 1 -> Signal 2

    Args:
        signal1: Time series array 1 (e.g., LFP channel 1)
        signal2: Time series array 2 (e.g., LFP channel 2)
        order: VAR model lag order

    Returns:
        Dict containing causality values and residual variances
    """
    s1 = np.asarray(signal1).flatten()
    s2 = np.asarray(signal2).flatten()

    # Normalise signals
    s1 = (s1 - np.mean(s1)) / np.std(s1)
    s2 = (s2 - np.mean(s2)) / np.std(s2)

    # 2 -> 1
    var_r1, var_u1 = fit_var_bivariate(s1, s2, order)
    f_2_to_1 = np.log(var_r1 / var_u1) if var_u1 > 0 else 0.0

    # 1 -> 2
    var_r2, var_u2 = fit_var_bivariate(s2, s1, order)
    f_1_to_2 = np.log(var_r2 / var_u2) if var_u2 > 0 else 0.0

    return {
        'F_2_to_1': float(max(0.0, f_2_to_1)),
        'F_1_to_2': float(max(0.0, f_1_to_2)),
        'var_restricted_1': var_r1,
        'var_unrestricted_1': var_u1,
        'var_restricted_2': var_r2,
        'var_unrestricted_2': var_u2
    }


def network_topology(
    adjacency_matrix: np.ndarray,
    threshold: float = 0.3
) -> Dict[str, Union[float, int, List[int]]]:
    """
    Compute network graph metrics from a correlation or Granger causality matrix.

    Args:
        adjacency_matrix: Symmetric or asymmetric connectivity matrix
        threshold: Edge detection cutoff threshold

    Returns:
        Dict of network stats (nodes, edges, density, degrees)
    """
    adj = np.abs(adjacency_matrix) > threshold
    np.fill_diagonal(adj, False)

    n_nodes = adj.shape[0]
    n_edges = int(adj.sum())
    # If symmetric, edges count is double. We keep total count.
    possible_edges = n_nodes * (n_nodes - 1) if n_nodes > 1 else 1
    density = n_edges / possible_edges

    in_degrees = adj.sum(axis=0).tolist()
    out_degrees = adj.sum(axis=1).tolist()

    return {
        'n_nodes': n_nodes,
        'n_edges': n_edges,
        'density': float(density),
        'in_degrees': in_degrees,
        'out_degrees': out_degrees,
        'mean_degree': float(np.mean(in_degrees))
    }
