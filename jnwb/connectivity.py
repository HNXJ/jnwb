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
    order: int,
    device: str = 'cpu'
) -> Tuple[float, float]:
    """
    Fit restricted and unrestricted bivariate VAR models to compute Granger residuals.

    Args:
        x: Signal 1 (dependent variable)
        y: Signal 2 (causal variable candidate)
        order: Autoregressive order p
        device: 'cpu' or 'cuda' (GPU acceleration)

    Returns:
        var_restricted: Residual variance of X under autoregression of X alone
        var_unrestricted: Residual variance of X under autoregression of X + Y
    """
    if device == 'cuda':
        try:
            import cupy as cp
            x_gpu = cp.asarray(x)
            y_gpu = cp.asarray(y)
            n = len(x_gpu)
            if n <= order * 2 + 1:
                return 1.0, 1.0

            target = x_gpu[order:]
            n_samples = len(target)

            X_reg = cp.zeros((n_samples, order + 1))
            X_reg[:, 0] = 1.0
            for i in range(1, order + 1):
                X_reg[:, i] = x_gpu[order - i: n - i]

            XY_reg = cp.zeros((n_samples, 2 * order + 1))
            XY_reg[:, 0] = 1.0
            for i in range(1, order + 1):
                XY_reg[:, i] = x_gpu[order - i: n - i]
                XY_reg[:, order + i] = y_gpu[order - i: n - i]

            beta_restr, _, _, _ = cp.linalg.lstsq(X_reg, target, rcond=None)
            residuals_restr = target - X_reg @ beta_restr
            var_restricted = cp.var(residuals_restr, ddof=order + 1)

            beta_unrestr, _, _, _ = cp.linalg.lstsq(XY_reg, target, rcond=None)
            residuals_unrestr = target - XY_reg @ beta_unrestr
            var_unrestricted = cp.var(residuals_unrestr, ddof=2 * order + 1)

            return float(var_restricted.get()), float(var_unrestricted.get())
        except Exception as e:
            log.warning(f"CUDA VAR fitting failed: {e}. Falling back to CPU.")

    # CPU implementation
    n = len(x)
    if n <= order * 2 + 1:
        return 1.0, 1.0

    target = x[order:]
    n_samples = len(target)

    X_reg = np.zeros((n_samples, order + 1))
    X_reg[:, 0] = 1.0
    for i in range(1, order + 1):
        X_reg[:, i] = x[order - i: n - i]

    XY_reg = np.zeros((n_samples, 2 * order + 1))
    XY_reg[:, 0] = 1.0
    for i in range(1, order + 1):
        XY_reg[:, i] = x[order - i: n - i]
        XY_reg[:, order + i] = y[order - i: n - i]

    beta_restr, _, _, _ = np.linalg.lstsq(X_reg, target, rcond=None)
    residuals_restr = target - X_reg @ beta_restr
    var_restricted = np.var(residuals_restr, ddof=order + 1)

    beta_unrestr, _, _, _ = np.linalg.lstsq(XY_reg, target, rcond=None)
    residuals_unrestr = target - XY_reg @ beta_unrestr
    var_unrestricted = np.var(residuals_unrestr, ddof=2 * order + 1)

    return float(var_restricted), float(var_unrestricted)


def select_optimal_lag(
    x: np.ndarray,
    y: np.ndarray,
    max_lag: int = 10,
    device: str = 'cpu'
) -> int:
    """
    Select the optimal VAR model order p using Akaike Information Criterion (AIC).

    Args:
        x: Dependent signal
        y: Independent causal signal candidate
        max_lag: Maximum lag order to evaluate
        device: 'cpu' or 'cuda'

    Returns:
        opt_lag: Optimal lag order (between 1 and max_lag)
    """
    n = len(x)
    best_aic = float('inf')
    opt_lag = 1

    actual_max = min(max_lag, (n - 2) // 3)
    if actual_max < 1:
        return 1

    for p in range(1, actual_max + 1):
        _, var_unrestricted = fit_var_bivariate(x, y, p, device=device)
        if var_unrestricted <= 0:
            continue
        
        n_samples = n - p
        aic = n_samples * np.log(var_unrestricted) + 2 * (2 * p + 1)
        if aic < best_aic:
            best_aic = aic
            opt_lag = p

    return opt_lag


def granger_causality(
    signal1: np.ndarray,
    signal2: np.ndarray,
    order: Union[int, str] = 5,
    device: str = 'cpu'
) -> Dict[str, float]:
    """
    Compute bivariate Granger Causality (GC) values between two continuous signals.

    F_2_to_1 is the directional causality from Signal 2 -> Signal 1
    F_1_to_2 is the directional causality from Signal 1 -> Signal 2

    Args:
        signal1: Time series array 1 (e.g., LFP channel 1)
        signal2: Time series array 2 (e.g., LFP channel 2)
        order: VAR model lag order, or 'auto' to select via AIC
        device: 'cpu' or 'cuda' (GPU acceleration via CuPy)

    Returns:
        Dict containing causality values, chosen orders, and residual variances
    """
    s1 = np.asarray(signal1).flatten()
    s2 = np.asarray(signal2).flatten()

    std1 = np.std(s1)
    std2 = np.std(s2)
    s1 = (s1 - np.mean(s1)) / std1 if std1 > 0 else np.zeros_like(s1)
    s2 = (s2 - np.mean(s2)) / std2 if std2 > 0 else np.zeros_like(s2)

    if order == 'auto':
        order_2_to_1 = select_optimal_lag(s1, s2, device=device)
        order_1_to_2 = select_optimal_lag(s2, s1, device=device)
    else:
        order_2_to_1 = int(order)
        order_1_to_2 = int(order)

    var_r1, var_u1 = fit_var_bivariate(s1, s2, order_2_to_1, device=device)
    f_2_to_1 = np.log(var_r1 / var_u1) if var_u1 > 0 else 0.0

    var_r2, var_u2 = fit_var_bivariate(s2, s1, order_1_to_2, device=device)
    f_1_to_2 = np.log(var_r2 / var_u2) if var_u2 > 0 else 0.0

    return {
        'F_2_to_1': float(max(0.0, f_2_to_1)),
        'F_1_to_2': float(max(0.0, f_1_to_2)),
        'order_2_to_1': float(order_2_to_1),
        'order_1_to_2': float(order_1_to_2),
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
