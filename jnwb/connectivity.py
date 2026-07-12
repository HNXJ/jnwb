"""
Functional Connectivity, Mutual Information, and Granger Causality

Provides methods to compute directional functional connectivity metrics (bivariate Granger Causality),
Shannon Mutual Information between spike trains, and network graph analysis.

MI estimators:
- ``binary_occupancy`` — MI of per-bin spike presence (0/1); discards count/rate structure
- ``spike_count`` — MI of per-bin spike counts (discrete)

Granger returns residual diagnostics; optional ridge VAR; lag selection via AIC/BIC/HQIC.
Residual variance uses explicit N - p divisors.

Author: Claude Code
Date: 2026-06-30
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats

log = logging.getLogger(__name__)


def _discrete_mi_from_labels(x: np.ndarray, y: np.ndarray) -> float:
    """Shannon MI (bits) between two discrete integer sequences of equal length."""
    x = np.asarray(x).ravel()
    y = np.asarray(y).ravel()
    n = len(x)
    if n == 0:
        return 0.0
    # Map labels to compact indices
    _, x_inv = np.unique(x, return_inverse=True)
    _, y_inv = np.unique(y, return_inverse=True)
    n_x = int(x_inv.max()) + 1
    n_y = int(y_inv.max()) + 1
    joint = np.zeros((n_x, n_y), dtype=float)
    np.add.at(joint, (x_inv, y_inv), 1.0)
    p_xy = joint / n
    p_x = p_xy.sum(axis=1)
    p_y = p_xy.sum(axis=0)
    mi = 0.0
    for i in range(n_x):
        for j in range(n_y):
            if p_xy[i, j] > 0 and p_x[i] > 0 and p_y[j] > 0:
                mi += p_xy[i, j] * np.log2(p_xy[i, j] / (p_x[i] * p_y[j]))
    return float(mi)


def spike_mutual_information(
    spike_times1: np.ndarray,
    spike_times2: np.ndarray,
    time_window: Tuple[float, float],
    bin_size_ms: float = 10.0,
    estimator: str = "binary_occupancy",
) -> float:
    """
    Compute Shannon Mutual Information (MI) between two binned spike trains.

    Args:
        spike_times1: Spike times of unit 1 (seconds)
        spike_times2: Spike times of unit 2 (seconds)
        time_window: (start_time, end_time) in seconds
        bin_size_ms: Bin size in ms
        estimator:
            - ``binary_occupancy`` (default): MI of bin occupancy (hist > 0).
              This is **not** MI of full spike trains / rates.
            - ``spike_count``: MI of integer spike counts per bin.

    Returns:
        mi: Mutual Information in bits
    """
    if estimator not in ("binary_occupancy", "spike_count"):
        raise ValueError(
            f"Unknown estimator={estimator!r}; use 'binary_occupancy' or 'spike_count'"
        )

    if len(spike_times1) == 0 or len(spike_times2) == 0:
        return 0.0

    t_start, t_end = time_window
    bin_sec = bin_size_ms / 1000.0
    n_bins = int((t_end - t_start) / bin_sec)

    if n_bins <= 1:
        return 0.0

    bin_edges = np.linspace(t_start, t_end, n_bins + 1)
    hist1, _ = np.histogram(np.sort(spike_times1), bins=bin_edges)
    hist2, _ = np.histogram(np.sort(spike_times2), bins=bin_edges)

    if estimator == "binary_occupancy":
        x = (hist1 > 0).astype(int)
        y = (hist2 > 0).astype(int)
    else:
        x = hist1.astype(int)
        y = hist2.astype(int)

    return _discrete_mi_from_labels(x, y)


def binary_occupancy_mutual_information(
    spike_times1: np.ndarray,
    spike_times2: np.ndarray,
    time_window: Tuple[float, float],
    bin_size_ms: float = 10.0,
) -> float:
    """Explicit alias for binary occupancy MI."""
    return spike_mutual_information(
        spike_times1,
        spike_times2,
        time_window,
        bin_size_ms=bin_size_ms,
        estimator="binary_occupancy",
    )


def spike_count_mutual_information(
    spike_times1: np.ndarray,
    spike_times2: np.ndarray,
    time_window: Tuple[float, float],
    bin_size_ms: float = 10.0,
) -> float:
    """Discrete MI on per-bin spike counts."""
    return spike_mutual_information(
        spike_times1,
        spike_times2,
        time_window,
        bin_size_ms=bin_size_ms,
        estimator="spike_count",
    )


def _residual_variance(residuals: np.ndarray, n_params: int) -> float:
    """RSS / (N - p) residual variance."""
    n = len(residuals)
    dof = max(n - int(n_params), 1)
    return float(np.sum(np.asarray(residuals, dtype=float) ** 2) / dof)


def _ridge_lstsq(A: np.ndarray, b: np.ndarray, ridge: float) -> np.ndarray:
    """Least squares with optional ridge on non-intercept columns."""
    if ridge <= 0:
        beta, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
        return beta
    n_col = A.shape[1]
    ata = A.T @ A
    # Do not ridge the intercept (column 0)
    pen = np.eye(n_col) * ridge
    pen[0, 0] = 0.0
    return np.linalg.solve(ata + pen, A.T @ b)


def fit_var_bivariate(
    x: np.ndarray,
    y: np.ndarray,
    order: int,
    device: str = "cpu",
    ridge: float = 0.0,
    return_residuals: bool = False,
) -> Union[Tuple[float, float], Tuple[float, float, np.ndarray, np.ndarray]]:
    """
    Fit restricted and unrestricted bivariate VAR models to compute Granger residuals.

    Residual variances use RSS / (N - p) with p = number of regressors.
    Optional ``ridge`` shrinks non-intercept coefficients (CPU path).
    """
    if device == "cuda" and ridge <= 0:
        try:
            import cupy as cp

            x_gpu = cp.asarray(x)
            y_gpu = cp.asarray(y)
            n = len(x_gpu)
            if n <= order * 2 + 1:
                if return_residuals:
                    return 1.0, 1.0, np.array([]), np.array([])
                return 1.0, 1.0

            target = x_gpu[order:]
            n_samples = len(target)

            X_reg = cp.zeros((n_samples, order + 1))
            X_reg[:, 0] = 1.0
            for i in range(1, order + 1):
                X_reg[:, i] = x_gpu[order - i : n - i]

            XY_reg = cp.zeros((n_samples, 2 * order + 1))
            XY_reg[:, 0] = 1.0
            for i in range(1, order + 1):
                XY_reg[:, i] = x_gpu[order - i : n - i]
                XY_reg[:, order + i] = y_gpu[order - i : n - i]

            beta_restr, _, _, _ = cp.linalg.lstsq(X_reg, target, rcond=None)
            residuals_restr = target - X_reg @ beta_restr
            var_restricted = float(
                (cp.sum(residuals_restr**2) / max(n_samples - (order + 1), 1)).get()
            )

            beta_unrestr, _, _, _ = cp.linalg.lstsq(XY_reg, target, rcond=None)
            residuals_unrestr = target - XY_reg @ beta_unrestr
            var_unrestricted = float(
                (cp.sum(residuals_unrestr**2) / max(n_samples - (2 * order + 1), 1)).get()
            )

            if return_residuals:
                return (
                    var_restricted,
                    var_unrestricted,
                    cp.asnumpy(residuals_restr),
                    cp.asnumpy(residuals_unrestr),
                )
            return var_restricted, var_unrestricted
        except Exception as e:
            log.warning(f"CUDA VAR fitting failed: {e}. Falling back to CPU.")

    # CPU implementation
    n = len(x)
    if n <= order * 2 + 1:
        if return_residuals:
            return 1.0, 1.0, np.array([]), np.array([])
        return 1.0, 1.0

    target = x[order:]
    n_samples = len(target)

    X_reg = np.zeros((n_samples, order + 1))
    X_reg[:, 0] = 1.0
    for i in range(1, order + 1):
        X_reg[:, i] = x[order - i : n - i]

    XY_reg = np.zeros((n_samples, 2 * order + 1))
    XY_reg[:, 0] = 1.0
    for i in range(1, order + 1):
        XY_reg[:, i] = x[order - i : n - i]
        XY_reg[:, order + i] = y[order - i : n - i]

    beta_restr = _ridge_lstsq(X_reg, target, ridge)
    residuals_restr = target - X_reg @ beta_restr
    var_restricted = _residual_variance(residuals_restr, order + 1)

    beta_unrestr = _ridge_lstsq(XY_reg, target, ridge)
    residuals_unrestr = target - XY_reg @ beta_unrestr
    var_unrestricted = _residual_variance(residuals_unrestr, 2 * order + 1)

    if return_residuals:
        return var_restricted, var_unrestricted, residuals_restr, residuals_unrestr
    return float(var_restricted), float(var_unrestricted)


def _info_criterion(n_samples: int, rss_var: float, n_params: int, criterion: str) -> float:
    """rss_var is already RSS/(N-p); convert to RSS for IC."""
    if rss_var <= 0:
        return float("inf")
    rss = rss_var * max(n_samples - n_params, 1)
    sigma2 = rss / n_samples
    if sigma2 <= 0:
        return float("inf")
    ll_term = n_samples * np.log(sigma2)
    if criterion == "aic":
        return float(ll_term + 2 * n_params)
    if criterion == "bic":
        return float(ll_term + n_params * np.log(n_samples))
    if criterion == "hqic":
        return float(ll_term + 2 * n_params * np.log(np.log(max(n_samples, 3))))
    raise ValueError(f"Unknown criterion={criterion!r}")


def select_optimal_lag(
    x: np.ndarray,
    y: np.ndarray,
    max_lag: int = 10,
    device: str = "cpu",
    criterion: str = "aic",
    ridge: float = 0.0,
) -> int:
    """
    Select optimal VAR order p using AIC, BIC, or HQIC on the unrestricted model.
    """
    n = len(x)
    best_ic = float("inf")
    opt_lag = 1

    actual_max = min(max_lag, (n - 2) // 3)
    if actual_max < 1:
        return 1

    for p in range(1, actual_max + 1):
        _, var_unrestricted = fit_var_bivariate(x, y, p, device=device, ridge=ridge)
        n_samples = n - p
        n_params = 2 * p + 1
        ic = _info_criterion(n_samples, var_unrestricted, n_params, criterion)
        if ic < best_ic:
            best_ic = ic
            opt_lag = p

    return opt_lag


def _adf_pvalue(series: np.ndarray) -> float:
    """
    Lightweight Dickey–Fuller (no lag augmentation) p-value via OLS t-stat.
    H0: unit root. Uses asymptotic normal approximation for the t-stat
    (conservative diagnostic flag, not a full ADF table).
    """
    y = np.asarray(series, dtype=float).ravel()
    if len(y) < 10:
        return float("nan")
    dy = np.diff(y)
    y_lag = y[:-1]
    # dy = a + b * y_lag
    X = np.column_stack([np.ones(len(y_lag)), y_lag])
    beta, _, _, _ = np.linalg.lstsq(X, dy, rcond=None)
    resid = dy - X @ beta
    dof = max(len(dy) - 2, 1)
    s2 = float(np.sum(resid**2) / dof)
    xtx_inv = np.linalg.pinv(X.T @ X)
    se_b = np.sqrt(max(s2 * xtx_inv[1, 1], 0.0))
    if se_b == 0:
        return float("nan")
    t_stat = float(beta[1] / se_b)
    # One-sided: more negative => more evidence against unit root
    return float(stats.norm.cdf(t_stat))


def _ljung_box_pvalue(residuals: np.ndarray, nlags: int = 10) -> float:
    """Ljung–Box portmanteau test p-value on residual autocorrelations."""
    r = np.asarray(residuals, dtype=float).ravel()
    n = len(r)
    if n < nlags + 2:
        return float("nan")
    r = r - np.mean(r)
    denom = np.dot(r, r)
    if denom <= 0:
        return float("nan")
    q = 0.0
    for k in range(1, nlags + 1):
        rk = np.dot(r[k:], r[:-k]) / denom
        q += (rk**2) / (n - k)
    q *= n * (n + 2)
    return float(stats.chi2.sf(q, df=nlags))


def _series_diagnostics(series: np.ndarray, residuals: np.ndarray, order: int) -> Dict:
    adf_p = _adf_pvalue(series)
    lb_p = _ljung_box_pvalue(residuals, nlags=min(10, max(order * 2, 2)))
    warnings = []
    if not np.isnan(adf_p) and adf_p > 0.05:
        warnings.append("possible_nonstationarity_adf_p>0.05")
    if not np.isnan(lb_p) and lb_p < 0.05:
        warnings.append("residual_autocorrelation_ljung_box_p<0.05")
    return {
        "adf_pvalue": adf_p,
        "ljung_box_pvalue": lb_p,
        "warnings": warnings,
        "stationarity_ok": bool(np.isnan(adf_p) or adf_p <= 0.05),
        "residual_whiteness_ok": bool(np.isnan(lb_p) or lb_p >= 0.05),
    }


def granger_causality(
    signal1: np.ndarray,
    signal2: np.ndarray,
    order: Union[int, str] = 5,
    device: str = "cpu",
    ridge: float = 0.0,
    criterion: str = "aic",
) -> Dict[str, Union[float, dict, list]]:
    """
    Compute bivariate Granger Causality (GC) values between two continuous signals.

    F_2_to_1 is the directional causality from Signal 2 -> Signal 1
    F_1_to_2 is the directional causality from Signal 1 -> Signal 2

    Also returns residual diagnostics (lightweight ADF + Ljung–Box). Do not interpret
    GC as biological directionality when diagnostics warn.
    """
    s1 = np.asarray(signal1).flatten()
    s2 = np.asarray(signal2).flatten()

    std1 = np.std(s1)
    std2 = np.std(s2)
    s1 = (s1 - np.mean(s1)) / std1 if std1 > 0 else np.zeros_like(s1)
    s2 = (s2 - np.mean(s2)) / std2 if std2 > 0 else np.zeros_like(s2)

    if order == "auto":
        order_2_to_1 = select_optimal_lag(
            s1, s2, device=device, criterion=criterion, ridge=ridge
        )
        order_1_to_2 = select_optimal_lag(
            s2, s1, device=device, criterion=criterion, ridge=ridge
        )
    else:
        order_2_to_1 = int(order)
        order_1_to_2 = int(order)

    var_r1, var_u1, res_r1, res_u1 = fit_var_bivariate(
        s1, s2, order_2_to_1, device=device, ridge=ridge, return_residuals=True
    )
    f_2_to_1 = np.log(var_r1 / var_u1) if var_u1 > 0 else 0.0

    var_r2, var_u2, res_r2, res_u2 = fit_var_bivariate(
        s2, s1, order_1_to_2, device=device, ridge=ridge, return_residuals=True
    )
    f_1_to_2 = np.log(var_r2 / var_u2) if var_u2 > 0 else 0.0

    diag_2_to_1 = _series_diagnostics(s1, res_u1, order_2_to_1)
    diag_1_to_2 = _series_diagnostics(s2, res_u2, order_1_to_2)
    all_warnings = list(
        dict.fromkeys(diag_2_to_1["warnings"] + diag_1_to_2["warnings"])
    )

    return {
        "F_2_to_1": float(f_2_to_1),
        "F_1_to_2": float(f_1_to_2),
        "order_2_to_1": float(order_2_to_1),
        "order_1_to_2": float(order_1_to_2),
        "var_restricted_1": float(var_r1),
        "var_unrestricted_1": float(var_u1),
        "var_restricted_2": float(var_r2),
        "var_unrestricted_2": float(var_u2),
        "ridge": float(ridge),
        "lag_criterion": criterion if order == "auto" else None,
        "diagnostics": {
            "direction_2_to_1": diag_2_to_1,
            "direction_1_to_2": diag_1_to_2,
            "warnings": all_warnings,
            "ok_for_interpretation": len(all_warnings) == 0,
        },
    }


def network_topology(
    adjacency_matrix: np.ndarray,
    threshold: float = 0.3,
) -> Dict[str, Union[float, int, List[int]]]:
    """
    Compute network graph metrics from a correlation or Granger causality matrix.
    """
    adj = np.abs(adjacency_matrix) > threshold
    np.fill_diagonal(adj, False)

    n_nodes = adj.shape[0]
    n_edges = int(adj.sum())
    possible_edges = n_nodes * (n_nodes - 1) if n_nodes > 1 else 1
    density = n_edges / possible_edges

    in_degrees = adj.sum(axis=0).tolist()
    out_degrees = adj.sum(axis=1).tolist()

    return {
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "density": float(density),
        "in_degrees": in_degrees,
        "out_degrees": out_degrees,
        "mean_degree": float(np.mean(in_degrees)),
    }
