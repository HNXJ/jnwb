"""
Functional Connectivity, Mutual Information, and Granger Causality

Provides methods to compute directional functional connectivity metrics (bivariate Granger Causality),
Shannon Mutual Information between spike trains, and network graph analysis.

MI estimators:
- ``binary_occupancy`` — MI of per-bin spike presence (0/1); discards count/rate structure
- ``spike_count`` — MI of per-bin spike counts (discrete)

Granger returns residual diagnostics; optional ridge VAR; lag selection via AIC/BIC/HQIC.
Residual variance uses explicit N - p divisors.

Modality-agnostic directed connectivity (added 2026-08-04)
---------------------------------------------------------
``granger`` / ``phase_slope_index`` / ``transfer_entropy`` all take the same
``(X, Y, ...)`` contract and return the same ``DirectedResult`` shape, so LFP
traces, binned spike counts, MUAe envelopes, band-power time courses and any
other regularly sampled series go through identical code:

    >>> import jnwb as oa
    >>> oa.granger(v1_lfp, pfc_lfp, order='auto')          # (n_trials, n_times)
    >>> oa.granger_spectral(v1_lfp, pfc_lfp, fs=1000.0)    # Geweke, per band
    >>> oa.phase_slope_index(v1_lfp, pfc_lfp, fs=1000.0)   # frequency-resolved
    >>> oa.transfer_entropy(rate_a, rate_b, n_surrogates=200)
    >>> oa.bin_spikes(spike_times, (-0.5, 1.0), 10.0)      # spikes -> (trials, bins)

Sign convention is uniform: ``x_to_y`` is X -> Y (X leads / X predicts Y).

Author: Claude Code
Date: 2026-06-30
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy import stats

log = logging.getLogger(__name__)

#: Settled Omission band edges (Hz). See CLAUDE.md "Band definitions".
#: PROMOTED 2026-08-23: single source of truth moved to jnwb.spectral.CANONICAL_BANDS
#: (99%-jnwb-sufficiency normalization) -- re-exported here unchanged so this module's
#: existing consumers and internal uses below keep working without modification.
from jnwb.spectral import CANONICAL_BANDS


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


# ===========================================================================
# Generalized directed connectivity — shared input contract
# ===========================================================================
#
# Every public estimator below accepts X and Y in the same forms:
#
#   1-D array            (n_times,)              -> one trial
#   2-D array            (n_trials, n_times)     -> trials x time (``time_axis=-1``)
#   list/tuple of 1-D    ragged allowed          -> truncated to the shortest, logged
#
# and returns a ``DirectedResult``. Nothing in this layer knows or cares whether
# the samples are LFP microvolts, spike counts, MUAe, or dB band power.


@dataclass
class DirectedResult:
    """
    Uniform return type for every directed connectivity estimator.

    Attributes:
        method: ``'granger'`` | ``'psi'`` | ``'transfer_entropy'``
        x_to_y: directed influence X -> Y (units in ``unit``)
        y_to_x: directed influence Y -> X
        net: net directionality. For GC/TE this is ``x_to_y - y_to_x``;
            for PSI (antisymmetric by construction) it is the PSI value itself,
            positive when X leads Y.
        unit: physical/units label for the estimates
        p_x_to_y / p_y_to_x / p_net: p-values where the estimator defines them,
            else ``None``. ``None`` means *not computed*, never "not significant".
        per_band: ``{band_name: {...}}`` for frequency-resolved methods, else ``{}``
        n_trials / n_times / fs: shape and sampling receipts
        params: every parameter that affects the number, for provenance
        diagnostics: assumption checks; ``warnings`` non-empty => do not
            interpret the number as biological directionality
    """

    method: str
    x_to_y: float
    y_to_x: float
    net: float
    unit: str
    p_x_to_y: Optional[float] = None
    p_y_to_x: Optional[float] = None
    p_net: Optional[float] = None
    per_band: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    spectrum: Optional[Dict[str, np.ndarray]] = None
    n_trials: int = 0
    n_times: int = 0
    fs: Optional[float] = None
    params: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    # dict-style access, so callers written against the older dict-returning
    # functions in this module keep working
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "method": self.method,
            "x_to_y": self.x_to_y,
            "y_to_x": self.y_to_x,
            "net": self.net,
            "unit": self.unit,
            "p_x_to_y": self.p_x_to_y,
            "p_y_to_x": self.p_y_to_x,
            "p_net": self.p_net,
            "per_band": self.per_band,
            "n_trials": self.n_trials,
            "n_times": self.n_times,
            "fs": self.fs,
            "params": self.params,
            "diagnostics": self.diagnostics,
        }
        if self.spectrum is not None:
            out["spectrum"] = self.spectrum
        return out

    @property
    def ok(self) -> bool:
        """True when no diagnostic warning fired."""
        return not self.diagnostics.get("warnings")

    def summary(self) -> str:
        lines = [
            f"{self.method}  ({self.n_trials} trials x {self.n_times} samples"
            + (f", fs={self.fs} Hz)" if self.fs else ")"),
            f"  X -> Y : {self.x_to_y:+.6g} {self.unit}"
            + (f"   p={self.p_x_to_y:.4g}" if self.p_x_to_y is not None else ""),
            f"  Y -> X : {self.y_to_x:+.6g} {self.unit}"
            + (f"   p={self.p_y_to_x:.4g}" if self.p_y_to_x is not None else ""),
            f"  net    : {self.net:+.6g} {self.unit}"
            + (f"   p={self.p_net:.4g}" if self.p_net is not None else ""),
        ]
        for band, vals in self.per_band.items():
            lines.append(
                f"  [{band}] {vals.get('value', float('nan')):+.6g}"
                + (
                    f"  z={vals['z']:+.3f}"
                    if vals.get("z") is not None and np.isfinite(vals.get("z", np.nan))
                    else ""
                )
            )
        for w in self.diagnostics.get("warnings", []):
            lines.append(f"  ! {w}")
        return "\n".join(lines)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"DirectedResult(method={self.method!r}, x_to_y={self.x_to_y:.6g}, "
            f"y_to_x={self.y_to_x:.6g}, net={self.net:.6g})"
        )


def as_trials(
    X,
    time_axis: int = -1,
    name: str = "X",
    allow_ragged: bool = True,
) -> np.ndarray:
    """
    Normalize any supported signal container to a ``(n_trials, n_times)`` float array.

    Args:
        X: 1-D array, 2-D array, or list/tuple of 1-D arrays (one per trial)
        time_axis: which axis of a 2-D input is time (default last)
        name: label used in error messages
        allow_ragged: if False, unequal trial lengths raise instead of truncating

    Raises:
        ValueError: on 3-D+ input, empty input, or non-finite samples. NaNs are
            never silently dropped — a series containing them is a hard error.
    """
    if isinstance(X, (list, tuple)):
        arrs = [np.asarray(a, dtype=float).ravel() for a in X]
        if not arrs:
            raise ValueError(f"{name}: empty trial list")
        lengths = {a.size for a in arrs}
        if len(lengths) > 1:
            if not allow_ragged:
                raise ValueError(f"{name}: ragged trial lengths {sorted(lengths)}")
            n_min = min(lengths)
            log.warning(
                "%s: ragged trials %s -> truncated to %d samples", name,
                sorted(lengths), n_min,
            )
            arrs = [a[:n_min] for a in arrs]
        arr = np.stack(arrs, axis=0)
    else:
        arr = np.asarray(X, dtype=float)
        if arr.ndim == 1:
            arr = arr[None, :]
        elif arr.ndim == 2:
            if time_axis in (0,):
                arr = arr.T
            elif time_axis not in (-1, 1):
                raise ValueError(f"{name}: time_axis must be 0, 1 or -1; got {time_axis}")
        else:
            raise ValueError(
                f"{name}: expected 1-D or 2-D (n_trials, n_times); got shape {arr.shape}. "
                "Reduce channels first (select or average) — this layer will not "
                "guess which axis is a channel."
            )

    if arr.size == 0:
        raise ValueError(f"{name}: empty signal")
    if not np.all(np.isfinite(arr)):
        n_bad = int(np.sum(~np.isfinite(arr)))
        raise ValueError(
            f"{name}: {n_bad} non-finite sample(s) of {arr.size}. Interpolate or drop "
            "the affected trials explicitly; connectivity will not impute them."
        )
    return arr


def _pair_trials(X, Y, time_axis: int = -1) -> Tuple[np.ndarray, np.ndarray]:
    """Normalize an X/Y pair and assert matching shape."""
    x = as_trials(X, time_axis=time_axis, name="X")
    y = as_trials(Y, time_axis=time_axis, name="Y")
    if x.shape != y.shape:
        raise ValueError(
            f"X and Y must have identical (n_trials, n_times); got {x.shape} vs {y.shape}"
        )
    return x, y


def _detrend_trials(a: np.ndarray, mode: Optional[str]) -> np.ndarray:
    """Per-trial detrending. ``None`` leaves the data untouched."""
    if mode in (None, "none", False):
        return a
    if mode == "demean":
        return a - a.mean(axis=1, keepdims=True)
    if mode == "zscore":
        mu = a.mean(axis=1, keepdims=True)
        sd = a.std(axis=1, keepdims=True)
        sd = np.where(sd > 0, sd, 1.0)
        return (a - mu) / sd
    if mode == "linear":
        n = a.shape[1]
        t = np.linspace(-1.0, 1.0, n)
        design = np.column_stack([np.ones(n), t])
        beta = np.linalg.lstsq(design, a.T, rcond=None)[0]
        return a - (design @ beta).T
    raise ValueError(f"Unknown detrend={mode!r}; use None|'demean'|'zscore'|'linear'")


def bin_spikes(
    spike_times,
    window: Tuple[float, float],
    bin_size_ms: float = 10.0,
    trial_starts: Optional[Sequence[float]] = None,
    output: str = "count",
    return_centers: bool = False,
):
    """
    Bridge spike data into the ``(n_trials, n_bins)`` contract used by every
    estimator in this module.

    Args:
        spike_times: either a 1-D array of absolute spike times (seconds), or a
            list of per-trial 1-D arrays already expressed relative to ``window``
        window: (start, end) in seconds. Relative to each trial start when
            ``trial_starts`` is given, else absolute.
        bin_size_ms: bin width in ms
        trial_starts: trial-aligned event times (seconds). Required to epoch a
            single absolute spike train into trials.
        output: ``'count'`` (spikes per bin) or ``'rate'`` (Hz)
        return_centers: also return bin centers (seconds, relative to window start
            convention of ``window``)

    Returns:
        ``(n_trials, n_bins)`` array, or ``(array, centers)`` if ``return_centers``.
    """
    if output not in ("count", "rate"):
        raise ValueError(f"output must be 'count' or 'rate'; got {output!r}")
    t0, t1 = float(window[0]), float(window[1])
    if not t1 > t0:
        raise ValueError(f"window must satisfy end > start; got {window}")
    bin_sec = float(bin_size_ms) / 1000.0
    n_bins = int(round((t1 - t0) / bin_sec))
    if n_bins < 2:
        raise ValueError(
            f"window {window} at bin_size_ms={bin_size_ms} yields {n_bins} bins; need >= 2"
        )
    edges = t0 + bin_sec * np.arange(n_bins + 1)

    if trial_starts is not None:
        st = np.asarray(spike_times, dtype=float).ravel()
        rows = []
        for start in np.asarray(trial_starts, dtype=float).ravel():
            rel = st - float(start)
            rel = rel[(rel >= t0) & (rel < t1)]
            rows.append(np.histogram(rel, bins=edges)[0])
    else:
        if isinstance(spike_times, (list, tuple)) and (
            len(spike_times) == 0 or np.ndim(spike_times[0]) >= 1
        ):
            trains = [np.asarray(s, dtype=float).ravel() for s in spike_times]
        else:
            trains = [np.asarray(spike_times, dtype=float).ravel()]
        rows = [np.histogram(s, bins=edges)[0] for s in trains]

    counts = np.asarray(rows, dtype=float)
    if counts.size == 0:
        raise ValueError("bin_spikes produced no trials")
    out = counts / bin_sec if output == "rate" else counts
    if return_centers:
        return out, edges[:-1] + bin_sec / 2.0
    return out


def _rng(seed: Optional[int]) -> np.random.Generator:
    """Deterministic by default — an unseeded connectivity p-value is not reproducible."""
    return np.random.default_rng(0 if seed is None else int(seed))


def _surrogate_source(a: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    Destroy cross-signal timing while preserving each trial's own autocorrelation.

    Trial permutation when >= 3 trials (pairs the source with the wrong trial),
    otherwise a circular shift of at least 10% of the record.
    """
    n_trials, n_times = a.shape
    if n_trials >= 3:
        perm = rng.permutation(n_trials)
        # guarantee a real derangement so no trial keeps its own partner
        for i in range(n_trials):
            if perm[i] == i:
                j = (i + 1) % n_trials
                perm[i], perm[j] = perm[j], perm[i]
        return a[perm]
    lo = max(1, n_times // 10)
    out = np.empty_like(a)
    for i in range(n_trials):
        out[i] = np.roll(a[i], int(rng.integers(lo, max(lo + 1, n_times - lo))))
    return out


# ---------------------------------------------------------------------------
# 1. Granger causality (linear, predictive)
# ---------------------------------------------------------------------------


def _stack_var_design(
    target: np.ndarray,
    sources: List[np.ndarray],
    order: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Build a lag design matrix stacked over trials, never crossing trial boundaries.

    Args:
        target: (n_trials, n_times) series being predicted
        sources: list of (n_trials, n_times) predictor series (target itself included
            by the caller when its own history should be in the model)
        order: number of lags

    Returns:
        (design, y) with design = [intercept | lag1..lagP of each source]
    """
    n_trials, n_times = target.shape
    n_rows = n_trials * (n_times - order)
    n_cols = 1 + order * len(sources)
    design = np.empty((n_rows, n_cols), dtype=float)
    y = np.empty(n_rows, dtype=float)
    design[:, 0] = 1.0
    row = 0
    for tr in range(n_trials):
        n_here = n_times - order
        sl = slice(row, row + n_here)
        y[sl] = target[tr, order:]
        col = 1
        for src in sources:
            for lag in range(1, order + 1):
                design[sl, col] = src[tr, order - lag : n_times - lag]
                col += 1
        row += n_here
    return design, y


def _ols_rss(design: np.ndarray, y: np.ndarray, ridge: float) -> Tuple[float, np.ndarray]:
    beta = _ridge_lstsq(design, y, ridge)
    resid = y - design @ beta
    return float(np.dot(resid, resid)), resid


def granger(
    X,
    Y,
    order: Union[int, str] = "auto",
    max_lag: int = 20,
    criterion: str = "bic",
    Z=None,
    ridge: float = 0.0,
    detrend: Optional[str] = "zscore",
    n_surrogates: int = 0,
    seed: Optional[int] = 0,
    time_axis: int = -1,
) -> DirectedResult:
    """
    Bivariate or conditional Granger causality between two arbitrary signals.

    Works on anything sampled on a common regular grid: LFP, binned spike counts
    (see :func:`bin_spikes`), MUAe, band-power time courses. Trials are pooled by
    stacking lag-design rows, so no regression window ever spans a trial boundary.

    ``x_to_y`` is the log variance ratio for predicting Y: how much Y's residual
    variance shrinks when X's past is added to Y's own past (and Z's past, if given).

    Args:
        X, Y: (n_times,), (n_trials, n_times), or list of 1-D trials
        order: VAR lag order, or ``'auto'`` to select by ``criterion``
        max_lag: upper bound for automatic order selection
        criterion: ``'bic'`` (default, conservative) | ``'aic'`` | ``'hqic'``
        Z: optional conditioning signal(s) — same shape as X, or a list of such
            arrays. Present in *both* the restricted and unrestricted models, so
            the reported influence is X -> Y not routed through Z.
        ridge: L2 penalty on non-intercept coefficients (0 = plain OLS)
        detrend: per-trial preprocessing, default ``'zscore'``
        n_surrogates: if > 0, also run a trial-shuffled surrogate test alongside
            the analytic F-test. Set this when residuals are not white.
        seed: RNG seed for surrogates (default 0 — deterministic)

    Returns:
        DirectedResult with ``unit='log variance ratio'``. ``p_*`` are analytic
        F-test p-values unless ``n_surrogates > 0``, in which case they are the
        surrogate p-values and the F-test values are kept in ``diagnostics``.
        Under the null the estimate fluctuates slightly **below** zero because the
        restricted and unrestricted variances carry different N-p divisors; read
        magnitude together with the p-value, never the sign alone.

    Note:
        This is time-domain GC. Band-resolved directionality is *not* obtained by
        band-passing the input — filtering distorts the very lag structure GC
        reads. Use :func:`granger_spectral` (Geweke decomposition of this same
        VAR) or :func:`phase_slope_index` instead.
    """
    if criterion not in ("aic", "bic", "hqic"):
        raise ValueError(f"criterion must be aic|bic|hqic; got {criterion!r}")

    x, y = _pair_trials(X, Y, time_axis=time_axis)
    x = _detrend_trials(x, detrend)
    y = _detrend_trials(y, detrend)

    z_list: List[np.ndarray] = []
    if Z is not None:
        # A list/tuple here means "several conditioning signals", not "trials of one
        # signal" — pass multi-trial Z as a 2-D (n_trials, n_times) array.
        z_items = list(Z) if isinstance(Z, (list, tuple)) else [Z]
        for i, z in enumerate(z_items):
            zi = as_trials(z, time_axis=time_axis, name=f"Z[{i}]")
            if zi.shape != x.shape:
                raise ValueError(
                    f"Z[{i}] shape {zi.shape} does not match X/Y {x.shape}"
                )
            z_list.append(_detrend_trials(zi, detrend))

    n_trials, n_times = x.shape

    def _one_direction(src: np.ndarray, tgt: np.ndarray, p: int) -> Dict[str, Any]:
        restricted_sources = [tgt] + z_list
        unrestricted_sources = restricted_sources + [src]
        d_r, yy = _stack_var_design(tgt, restricted_sources, p)
        d_u, _ = _stack_var_design(tgt, unrestricted_sources, p)
        n_obs = d_u.shape[0]
        if n_obs <= d_u.shape[1] + 1:
            raise ValueError(
                f"order={p} leaves {n_obs} observations for {d_u.shape[1]} parameters; "
                "lower the order or supply more trials/samples"
            )
        rss_r, res_r = _ols_rss(d_r, yy, ridge)
        rss_u, res_u = _ols_rss(d_u, yy, ridge)
        df_u = n_obs - d_u.shape[1]
        df_extra = d_u.shape[1] - d_r.shape[1]
        sig2_r = rss_r / max(n_obs - d_r.shape[1], 1)
        sig2_u = rss_u / max(df_u, 1)
        gc_val = float(np.log(sig2_r / sig2_u)) if sig2_u > 0 else 0.0
        if rss_u > 0 and df_extra > 0 and df_u > 0:
            f_stat = ((rss_r - rss_u) / df_extra) / (rss_u / df_u)
            p_val = float(stats.f.sf(max(f_stat, 0.0), df_extra, df_u))
        else:
            f_stat, p_val = float("nan"), float("nan")
        return {
            "gc": gc_val,
            "f_stat": float(f_stat),
            "p_f": p_val,
            "df_num": int(df_extra),
            "df_den": int(df_u),
            "n_obs": int(n_obs),
            "resid_u": res_u,
            "sig2_restricted": float(sig2_r),
            "sig2_unrestricted": float(sig2_u),
        }

    def _select_order(src: np.ndarray, tgt: np.ndarray) -> int:
        n_free = n_trials * n_times
        cap = max(1, min(int(max_lag), (n_times - 2) // 3, n_free // (8 * (2 + len(z_list)))))
        best_ic, best_p = float("inf"), 1
        n_src = 2 + len(z_list)
        for p in range(1, cap + 1):
            d_u, yy = _stack_var_design(tgt, [tgt, src] + z_list, p)
            if d_u.shape[0] <= d_u.shape[1] + 1:
                break
            rss_u, _ = _ols_rss(d_u, yy, ridge)
            n_obs = d_u.shape[0]
            n_par = 1 + p * n_src
            sigma2 = rss_u / n_obs
            if sigma2 <= 0:
                continue
            ll = n_obs * np.log(sigma2)
            if criterion == "aic":
                ic = ll + 2 * n_par
            elif criterion == "bic":
                ic = ll + n_par * np.log(n_obs)
            else:
                ic = ll + 2 * n_par * np.log(np.log(max(n_obs, 3)))
            if ic < best_ic:
                best_ic, best_p = ic, p
        return best_p

    if order == "auto":
        order_xy = _select_order(x, y)
        order_yx = _select_order(y, x)
    else:
        order_xy = order_yx = int(order)
        if order_xy < 1:
            raise ValueError(f"order must be >= 1; got {order}")

    fit_xy = _one_direction(x, y, order_xy)  # X -> Y
    fit_yx = _one_direction(y, x, order_yx)  # Y -> X

    p_xy: Optional[float] = fit_xy["p_f"]
    p_yx: Optional[float] = fit_yx["p_f"]
    p_net: Optional[float] = None
    surrogate_info: Dict[str, Any] = {"n_surrogates": int(n_surrogates)}

    if n_surrogates > 0:
        rng = _rng(seed)
        obs_net = fit_xy["gc"] - fit_yx["gc"]
        null_xy = np.empty(n_surrogates)
        null_yx = np.empty(n_surrogates)
        for i in range(int(n_surrogates)):
            x_s = _surrogate_source(x, rng)
            null_xy[i] = _one_direction(x_s, y, order_xy)["gc"]
            y_s = _surrogate_source(y, rng)
            null_yx[i] = _one_direction(y_s, x, order_yx)["gc"]
        p_xy = float((1 + np.sum(null_xy >= fit_xy["gc"])) / (n_surrogates + 1))
        p_yx = float((1 + np.sum(null_yx >= fit_yx["gc"])) / (n_surrogates + 1))
        null_net = null_xy - null_yx
        p_net = float(
            (1 + np.sum(np.abs(null_net) >= abs(obs_net))) / (n_surrogates + 1)
        )
        surrogate_info.update(
            {
                "null_mean_x_to_y": float(null_xy.mean()),
                "null_mean_y_to_x": float(null_yx.mean()),
                "bias_corrected_x_to_y": float(fit_xy["gc"] - null_xy.mean()),
                "bias_corrected_y_to_x": float(fit_yx["gc"] - null_yx.mean()),
                "f_test_p_x_to_y": fit_xy["p_f"],
                "f_test_p_y_to_x": fit_yx["p_f"],
            }
        )

    # Ljung-Box on the first trial's residual block only: the stacked residual
    # vector concatenates trials, and lagged products across a trial boundary
    # would be spurious autocorrelation.
    block = n_times - order_xy
    diag_xy = _series_diagnostics(y[0], fit_xy["resid_u"][:block], order_xy)
    block = n_times - order_yx
    diag_yx = _series_diagnostics(x[0], fit_yx["resid_u"][:block], order_yx)
    warnings_all = list(dict.fromkeys(diag_xy["warnings"] + diag_yx["warnings"]))
    if order == "auto" and max(order_xy, order_yx) >= max(1, min(max_lag, (n_times - 2) // 3)):
        warnings_all.append("selected_order_hit_max_lag_ceiling")

    return DirectedResult(
        method="granger",
        x_to_y=fit_xy["gc"],
        y_to_x=fit_yx["gc"],
        net=fit_xy["gc"] - fit_yx["gc"],
        unit="log variance ratio",
        p_x_to_y=p_xy,
        p_y_to_x=p_yx,
        p_net=p_net,
        n_trials=n_trials,
        n_times=n_times,
        params={
            "order_x_to_y": order_xy,
            "order_y_to_x": order_yx,
            "order_arg": order,
            "criterion": criterion if order == "auto" else None,
            "max_lag": int(max_lag),
            "ridge": float(ridge),
            "detrend": detrend,
            "n_conditioning": len(z_list),
            "seed": seed,
        },
        diagnostics={
            "direction_x_to_y": {k: v for k, v in diag_xy.items()},
            "direction_y_to_x": {k: v for k, v in diag_yx.items()},
            "f_x_to_y": fit_xy["f_stat"],
            "f_y_to_x": fit_yx["f_stat"],
            "df_x_to_y": (fit_xy["df_num"], fit_xy["df_den"]),
            "df_y_to_x": (fit_yx["df_num"], fit_yx["df_den"]),
            "n_observations": fit_xy["n_obs"],
            "surrogates": surrogate_info,
            "warnings": warnings_all,
            "ok_for_interpretation": len(warnings_all) == 0,
        },
    )


# ---------------------------------------------------------------------------
# 1b. Spectral (Geweke) Granger causality
# ---------------------------------------------------------------------------


def _fit_var_matrix(
    series: List[np.ndarray], order: int, ridge: float = 0.0
) -> Tuple[np.ndarray, np.ndarray, int]:
    """
    Fit a full n-variate VAR(p) stacked over trials.

    Model: ``x_t = c + sum_k A_k x_{t-k} + e_t``, ``cov(e) = Sigma``.

    Args:
        series: list of (n_trials, n_times) arrays, one per variable
        order: lag order p
        ridge: L2 penalty on non-intercept coefficients

    Returns:
        (A, Sigma, n_obs) with ``A`` shaped (order, n_vars, n_vars) where
        ``A[k, i, j]`` multiplies variable j at lag k+1 in variable i's equation.
    """
    n_vars = len(series)
    n_trials, n_times = series[0].shape
    design, _ = _stack_var_design(series[0], series, order)
    targets = np.column_stack(
        [np.concatenate([s[tr, order:] for tr in range(n_trials)]) for s in series]
    )
    n_obs, n_par = design.shape
    if n_obs <= n_par + n_vars:
        raise ValueError(
            f"order={order} leaves {n_obs} observations for {n_par} parameters "
            f"per equation; lower the order or supply more data"
        )
    beta = _ridge_lstsq(design, targets, ridge)  # (n_par, n_vars)
    resid = targets - design @ beta
    sigma = (resid.T @ resid) / max(n_obs - n_par, 1)

    # design columns are [intercept | var0 lag1..p | var1 lag1..p | ...]
    a = np.empty((order, n_vars, n_vars))
    for j in range(n_vars):
        for k in range(order):
            a[k, :, j] = beta[1 + j * order + k, :]
    return a, np.atleast_2d(sigma), int(n_obs)


def _var_spectral_radius(a: np.ndarray) -> float:
    """Spectral radius of the VAR companion matrix; >= 1 means a non-stationary fit."""
    order, n_vars, _ = a.shape
    comp = np.zeros((order * n_vars, order * n_vars))
    comp[:n_vars, :] = np.hstack([a[k] for k in range(order)])
    if order > 1:
        comp[n_vars:, : n_vars * (order - 1)] = np.eye(n_vars * (order - 1))
    return float(np.max(np.abs(np.linalg.eigvals(comp))))


def granger_spectral(
    X,
    Y,
    fs: float,
    order: Union[int, str] = "auto",
    max_lag: int = 20,
    criterion: str = "bic",
    n_freqs: int = 256,
    bands: Union[str, Dict[str, Tuple[float, float]], Tuple[float, float], None] = None,
    ridge: float = 0.0,
    detrend: Optional[str] = "zscore",
    n_surrogates: int = 0,
    seed: Optional[int] = 0,
    time_axis: int = -1,
) -> DirectedResult:
    """
    Frequency-resolved Granger causality (Geweke, 1982) — directionality per band.

    This is the *parametric* route: a single bivariate VAR is fitted once (the
    same fit :func:`granger` uses), then decomposed in the frequency domain via
    the transfer function ``H(f) = A(f)^-1`` and noise covariance ``Sigma``.
    Wilson spectral factorization is required only for the *non*-parametric
    variant that starts from an observed cross-spectrum; it is not needed here
    and is not implemented.

    ``f_{X->Y}(f) = ln( S_yy(f) / (|H~_yy(f)|^2 * Sigma_yy) )``, with ``H~`` the
    instantaneous-causality-normalized transfer function. The estimate is >= 0 at
    every frequency by construction.

    Geweke's decomposition means the frequency average returns the time-domain
    value, so ``x_to_y`` here is directly comparable to ``granger(X, Y).x_to_y``
    — a large disagreement is a symptom (usually VAR misspecification), not noise.

    Args:
        X, Y: any signal accepted by :func:`as_trials`
        fs: sampling rate in Hz
        order: VAR order, or ``'auto'`` (selected exactly as in :func:`granger`)
        n_freqs: frequency grid points on [0, Nyquist]
        bands: ``None`` (whole spectrum), ``'canonical'``, ``(fmin, fmax)``, or a
            ``{name: (fmin, fmax)}`` dict. Each band reports its mean and its
            peak frequency in both directions.
        n_surrogates: trial-shuffled surrogate test (there is no analytic null here)

    Returns:
        DirectedResult with ``unit='log variance ratio'``,
        ``spectrum = {freqs, gc_x_to_y, gc_y_to_x}``, and
        ``per_band[name] = {value, value_reverse, peak_hz, peak_hz_reverse, ...}``.
        ``x_to_y``/``y_to_x`` are the frequency averages over the full spectrum.
        ``diagnostics['spectral_radius'] >= 1`` means the VAR is non-stationary
        and the decomposition must not be interpreted.
    """
    if fs is None or not np.isfinite(fs) or fs <= 0:
        raise ValueError(f"granger_spectral requires a positive fs; got {fs!r}")

    x, y = _pair_trials(X, Y, time_axis=time_axis)
    x = _detrend_trials(x, detrend)
    y = _detrend_trials(y, detrend)
    n_trials, n_times = x.shape

    if order == "auto":
        probe = granger(
            x, y, order="auto", max_lag=max_lag, criterion=criterion,
            ridge=ridge, detrend=None, n_surrogates=0,
        )
        p = int(max(probe.params["order_x_to_y"], probe.params["order_y_to_x"]))
    else:
        p = int(order)
        if p < 1:
            raise ValueError(f"order must be >= 1; got {order}")

    a, sigma, n_obs = _fit_var_matrix([x, y], p, ridge=ridge)
    radius = _var_spectral_radius(a)

    freqs = np.linspace(0.0, fs / 2.0, int(n_freqs))
    s11, s22 = float(sigma[0, 0]), float(sigma[1, 1])
    s12 = float(sigma[0, 1])
    if s11 <= 0 or s22 <= 0:
        raise ValueError("degenerate VAR residual covariance; check for constant input")

    gc_y_to_x = np.zeros(len(freqs))  # influence on variable 0 (X)
    gc_x_to_y = np.zeros(len(freqs))  # influence on variable 1 (Y)
    for fi, f in enumerate(freqs):
        af = np.eye(2, dtype=complex)
        for k in range(p):
            af -= a[k] * np.exp(-2j * np.pi * f * (k + 1) / fs)
        h = np.linalg.inv(af)
        s = h @ sigma @ h.conj().T

        # Y -> X : partial out X's noise contribution to Y's innovation
        h11_t = h[0, 0] + (s12 / s11) * h[0, 1]
        denom_x = (abs(h11_t) ** 2) * s11
        gc_y_to_x[fi] = np.log(s[0, 0].real / denom_x) if denom_x > 0 else 0.0

        # X -> Y
        h22_t = h[1, 1] + (s12 / s22) * h[1, 0]
        denom_y = (abs(h22_t) ** 2) * s22
        gc_x_to_y[fi] = np.log(s[1, 1].real / denom_y) if denom_y > 0 else 0.0

    warnings_all: List[str] = []
    min_val = float(min(gc_x_to_y.min(), gc_y_to_x.min()))
    if min_val < -1e-8:
        warnings_all.append(f"negative_spectral_gc_{min_val:.2e}_numerically_unstable")
    # Geweke GC is non-negative analytically; clip float noise only.
    gc_x_to_y = np.clip(gc_x_to_y, 0.0, None)
    gc_y_to_x = np.clip(gc_y_to_x, 0.0, None)
    if radius >= 1.0:
        warnings_all.append(f"var_non_stationary_spectral_radius_{radius:.3f}")

    def _mean_over(values: np.ndarray, mask: np.ndarray) -> float:
        """Trapezoidal frequency average == Geweke's integral over [0, Nyquist]."""
        f_sel, v_sel = freqs[mask], values[mask]
        if f_sel.size < 2:
            return float("nan")
        span = f_sel[-1] - f_sel[0]
        if span <= 0:
            return float(v_sel.mean())
        return float(np.sum((v_sel[:-1] + v_sel[1:]) / 2.0 * np.diff(f_sel)) / span)

    if bands is None:
        band_map = {"full": (float(freqs[0]), float(freqs[-1]))}
    elif isinstance(bands, str):
        if bands != "canonical":
            raise ValueError(f"bands string must be 'canonical'; got {bands!r}")
        band_map = dict(CANONICAL_BANDS)
    elif isinstance(bands, dict):
        band_map = {k: (float(v[0]), float(v[1])) for k, v in bands.items()}
    else:
        band_map = {"band": (float(bands[0]), float(bands[1]))}

    per_band: Dict[str, Dict[str, Any]] = {}
    for name, (f_lo, f_hi) in band_map.items():
        mask = (freqs >= f_lo) & (freqs <= f_hi)
        if mask.sum() < 2:
            warnings_all.append(f"band_{name}_has_{int(mask.sum())}_grid_points")
            per_band[name] = {
                "value": float("nan"), "value_reverse": float("nan"),
                "peak_hz": float("nan"), "peak_hz_reverse": float("nan"),
                "band_hz": (f_lo, f_hi), "n_freq_bins": int(mask.sum()),
                "p_surrogate": None,
            }
            continue
        sel = np.flatnonzero(mask)
        per_band[name] = {
            "value": _mean_over(gc_x_to_y, mask),
            "value_reverse": _mean_over(gc_y_to_x, mask),
            "peak_hz": float(freqs[sel[np.argmax(gc_x_to_y[sel])]]),
            "peak_hz_reverse": float(freqs[sel[np.argmax(gc_y_to_x[sel])]]),
            "band_hz": (f_lo, f_hi),
            "n_freq_bins": int(mask.sum()),
            "p_surrogate": None,
        }

    all_mask = np.ones(len(freqs), dtype=bool)
    total_xy = _mean_over(gc_x_to_y, all_mask)
    total_yx = _mean_over(gc_y_to_x, all_mask)

    p_xy = p_yx = None
    if n_surrogates > 0:
        rng = _rng(seed)
        null_xy = np.empty(int(n_surrogates))
        null_yx = np.empty(int(n_surrogates))
        for i in range(int(n_surrogates)):
            xs = _surrogate_source(x, rng)
            a_s, sig_s, _ = _fit_var_matrix([xs, y], p, ridge=ridge)
            tmp = _spectral_gc_from_var(a_s, sig_s, freqs, fs)
            null_xy[i] = _mean_over(tmp[1], all_mask)
            ys = _surrogate_source(y, rng)
            a_s2, sig_s2, _ = _fit_var_matrix([x, ys], p, ridge=ridge)
            tmp2 = _spectral_gc_from_var(a_s2, sig_s2, freqs, fs)
            null_yx[i] = _mean_over(tmp2[0], all_mask)
        p_xy = float((1 + np.sum(null_xy >= total_xy)) / (n_surrogates + 1))
        p_yx = float((1 + np.sum(null_yx >= total_yx)) / (n_surrogates + 1))
        for name, vals in per_band.items():
            f_lo, f_hi = vals["band_hz"]
            mask = (freqs >= f_lo) & (freqs <= f_hi)
            if mask.sum() >= 2:
                vals["p_surrogate"] = p_xy

    return DirectedResult(
        method="granger_spectral",
        x_to_y=total_xy,
        y_to_x=total_yx,
        net=total_xy - total_yx,
        unit="log variance ratio",
        p_x_to_y=p_xy,
        p_y_to_x=p_yx,
        p_net=None,
        per_band=per_band,
        spectrum={
            "freqs": freqs,
            "gc_x_to_y": gc_x_to_y,
            "gc_y_to_x": gc_y_to_x,
        },
        n_trials=n_trials,
        n_times=n_times,
        fs=float(fs),
        params={
            "order": p,
            "order_arg": order,
            "criterion": criterion if order == "auto" else None,
            "n_freqs": int(n_freqs),
            "bands": {k: list(v) for k, v in band_map.items()},
            "ridge": float(ridge),
            "detrend": detrend,
            "n_surrogates": int(n_surrogates),
            "seed": seed,
        },
        diagnostics={
            "spectral_radius": radius,
            "stationary": bool(radius < 1.0),
            "noise_covariance": sigma.tolist(),
            "n_observations": int(n_obs),
            "min_raw_spectral_gc": min_val,
            "warnings": warnings_all,
            "ok_for_interpretation": len(warnings_all) == 0,
        },
    )


def _spectral_gc_from_var(
    a: np.ndarray, sigma: np.ndarray, freqs: np.ndarray, fs: float
) -> Tuple[np.ndarray, np.ndarray]:
    """(gc_y_to_x, gc_x_to_y) over ``freqs`` from VAR coefficients — surrogate helper."""
    p = a.shape[0]
    s11, s22, s12 = float(sigma[0, 0]), float(sigma[1, 1]), float(sigma[0, 1])
    out_yx = np.zeros(len(freqs))
    out_xy = np.zeros(len(freqs))
    for fi, f in enumerate(freqs):
        af = np.eye(2, dtype=complex)
        for k in range(p):
            af -= a[k] * np.exp(-2j * np.pi * f * (k + 1) / fs)
        h = np.linalg.inv(af)
        s = h @ sigma @ h.conj().T
        d_x = (abs(h[0, 0] + (s12 / s11) * h[0, 1]) ** 2) * s11
        d_y = (abs(h[1, 1] + (s12 / s22) * h[1, 0]) ** 2) * s22
        out_yx[fi] = max(np.log(s[0, 0].real / d_x), 0.0) if d_x > 0 else 0.0
        out_xy[fi] = max(np.log(s[1, 1].real / d_y), 0.0) if d_y > 0 else 0.0
    return out_yx, out_xy


# ---------------------------------------------------------------------------
# 2. Phase slope index (frequency-domain, volume-conduction robust)
# ---------------------------------------------------------------------------


def _welch_segments(a: np.ndarray, nperseg: int, noverlap: int) -> np.ndarray:
    """Slice (n_trials, n_times) into (n_segments, nperseg), never crossing trials."""
    step = max(1, nperseg - noverlap)
    segs = []
    n_times = a.shape[1]
    for tr in range(a.shape[0]):
        for start in range(0, n_times - nperseg + 1, step):
            segs.append(a[tr, start : start + nperseg])
    if not segs:
        raise ValueError(
            f"no segments: nperseg={nperseg} exceeds n_times={n_times}"
        )
    return np.asarray(segs, dtype=float)


def _psi_from_spectra(
    fx: np.ndarray, fy: np.ndarray, idx: np.ndarray, weights: Optional[np.ndarray] = None
) -> float:
    """PSI over the frequency indices ``idx`` from per-segment FFTs."""
    sxy = np.mean(fx * np.conj(fy), axis=0)
    sxx = np.mean(np.abs(fx) ** 2, axis=0)
    syy = np.mean(np.abs(fy) ** 2, axis=0)
    denom = np.sqrt(sxx * syy)
    coh = np.divide(sxy, denom, out=np.zeros_like(sxy), where=denom > 0)
    c = coh[idx]
    return float(np.sum(np.imag(np.conj(c[:-1]) * c[1:])))


def phase_slope_index(
    X,
    Y,
    fs: float,
    bands: Union[str, Dict[str, Tuple[float, float]], Tuple[float, float], None] = None,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    window: str = "hann",
    detrend: Optional[str] = "demean",
    jackknife: bool = True,
    n_surrogates: int = 0,
    seed: Optional[int] = 0,
    time_axis: int = -1,
) -> DirectedResult:
    """
    Phase Slope Index (Nolte et al., 2008) — which signal leads in phase.

    PSI is antisymmetric: ``psi(X, Y) == -psi(Y, X)`` exactly. Positive means
    **X leads Y**. Because it uses the *slope* of the coherency phase rather than
    its value, a zero-lag common source (volume conduction, shared reference)
    contributes ~0 rather than a spurious direction.

    There is therefore **one** test here, not two. ``p_x_to_y`` and ``p_y_to_x``
    are deliberately the same number — the direction lives in the *sign*, and the
    p-value asks only whether the lead is distinguishable from zero. Reading them
    as independent per-direction tests (as GC and TE's are) will report a
    significant lead in both directions at once, which is not what happened.
    ``diagnostics['p_covers_both_directions']`` flags this.

    Coherency is estimated by averaging cross- and auto-spectra over Welch
    segments pooled across trials — a single-segment coherency has magnitude 1 by
    construction and its PSI is meaningless, so segmenting is not optional.

    PSI needs power spread across a *band*. A near-pure tone returns ~0 however
    large its delay, because at a single frequency a delay and a phase offset are
    indistinguishable and the neighbouring bins hold only window leakage carrying
    that same phase. Measured here: band-limited noise (14-30 Hz) delayed 10 ms
    gives z = 64, while a 20 Hz sinusoid with the identical delay gives z = 3.
    Low ``|z|`` on a narrowband signal is therefore not evidence of no lead.

    Args:
        X, Y: (n_times,), (n_trials, n_times), or list of 1-D trials
        fs: sampling rate in Hz (required — PSI is a frequency-domain measure)
        bands: ``None`` for one estimate over the whole spectrum except DC
            (``df``..``fs/2``); ``'canonical'`` for the
            settled Omission band set (:data:`CANONICAL_BANDS`); a ``(fmin, fmax)``
            tuple; or a ``{name: (fmin, fmax)}`` dict
        nperseg: Welch segment length in samples (default: n_times // 4, clipped
            to [16, n_times]). Frequency resolution is ``fs / nperseg``.
        noverlap: segment overlap (default nperseg // 2)
        window: ``'hann'`` | ``'hamming'`` | ``'boxcar'``
        detrend: per-trial preprocessing, default ``'demean'``
        jackknife: estimate the standard deviation of PSI by leave-one-segment-out
            and report ``z = psi / sd``, the normalization Nolte et al. use for
            significance. ``|z| > 2`` is the conventional threshold.
        n_surrogates: optional trial-shuffled surrogate test in addition to (or,
            with jackknife=False, instead of) the jackknife z

    Returns:
        DirectedResult with ``unit='psi'``, ``per_band[name] = {value, z, sd,
        n_freq_bins, band_hz}``, and ``spectrum = {freqs, psi_per_freq, coherence}``.
        ``x_to_y`` is the summed PSI over the whole requested range with
        ``y_to_x = -x_to_y``; ``net == x_to_y``.
    """
    if fs is None or not np.isfinite(fs) or fs <= 0:
        raise ValueError(f"phase_slope_index requires a positive fs; got {fs!r}")

    x, y = _pair_trials(X, Y, time_axis=time_axis)
    x = _detrend_trials(x, detrend)
    y = _detrend_trials(y, detrend)
    n_trials, n_times = x.shape

    if nperseg is None:
        nperseg = int(np.clip(n_times // 4, 16, n_times))
    nperseg = int(min(nperseg, n_times))
    if nperseg < 8:
        raise ValueError(f"nperseg={nperseg} too small for a usable spectrum")
    if noverlap is None:
        noverlap = nperseg // 2
    noverlap = int(min(noverlap, nperseg - 1))

    win_fn = {"hann": np.hanning, "hamming": np.hamming, "boxcar": np.ones}
    if window not in win_fn:
        raise ValueError(f"window must be one of {sorted(win_fn)}; got {window!r}")
    taper = win_fn[window](nperseg)

    seg_x = _welch_segments(x, nperseg, noverlap)
    seg_y = _welch_segments(y, nperseg, noverlap)
    seg_x = (seg_x - seg_x.mean(axis=1, keepdims=True)) * taper
    seg_y = (seg_y - seg_y.mean(axis=1, keepdims=True)) * taper
    fx = np.fft.rfft(seg_x, axis=1)
    fy = np.fft.rfft(seg_y, axis=1)
    freqs = np.fft.rfftfreq(nperseg, d=1.0 / fs)
    n_seg = fx.shape[0]
    df = fs / nperseg

    # resolve band specification
    if bands is None:
        # everything except DC. A hard-coded lower edge in Hz would silently
        # empty the band for slowly sampled series (band-power time courses,
        # normalized-frequency use with fs=2).
        band_map = {"full": (df, fs / 2.0)}
    elif isinstance(bands, str):
        if bands != "canonical":
            raise ValueError(f"bands string must be 'canonical'; got {bands!r}")
        band_map = dict(CANONICAL_BANDS)
    elif isinstance(bands, dict):
        band_map = {k: (float(v[0]), float(v[1])) for k, v in bands.items()}
    else:
        band_map = {"band": (float(bands[0]), float(bands[1]))}

    warnings_all: List[str] = []
    if n_seg < 8:
        warnings_all.append(f"only_{n_seg}_welch_segments_coherency_poorly_estimated")

    # full-spectrum PSI per frequency (for the returned spectrum)
    sxy = np.mean(fx * np.conj(fy), axis=0)
    sxx = np.mean(np.abs(fx) ** 2, axis=0)
    syy = np.mean(np.abs(fy) ** 2, axis=0)
    denom = np.sqrt(sxx * syy)
    coh_full = np.divide(sxy, denom, out=np.zeros_like(sxy), where=denom > 0)
    psi_per_freq = np.imag(np.conj(coh_full[:-1]) * coh_full[1:])

    per_band: Dict[str, Dict[str, Any]] = {}
    for name, (f_lo, f_hi) in band_map.items():
        idx = np.flatnonzero((freqs >= f_lo) & (freqs <= f_hi))
        if idx.size < 2:
            warnings_all.append(
                f"band_{name}_has_{idx.size}_bins_at_df={df:.3g}Hz_psi_undefined"
            )
            per_band[name] = {
                "value": float("nan"),
                "z": float("nan"),
                "sd": float("nan"),
                "n_freq_bins": int(idx.size),
                "band_hz": (f_lo, f_hi),
                "p_surrogate": None,
            }
            continue

        value = _psi_from_spectra(fx, fy, idx)

        sd = float("nan")
        if jackknife and n_seg >= 3:
            jk = np.empty(n_seg)
            keep = np.ones(n_seg, dtype=bool)
            for i in range(n_seg):
                keep[i] = False
                jk[i] = _psi_from_spectra(fx[keep], fy[keep], idx)
                keep[i] = True
            sd = float(np.sqrt((n_seg - 1) / n_seg * np.sum((jk - jk.mean()) ** 2)))
        elif jackknife:
            warnings_all.append("jackknife_needs_at_least_3_segments")

        per_band[name] = {
            "value": value,
            "z": float(value / sd) if sd and np.isfinite(sd) and sd > 0 else float("nan"),
            "sd": sd,
            "n_freq_bins": int(idx.size),
            "band_hz": (f_lo, f_hi),
            "p_surrogate": None,
        }

    if n_surrogates > 0:
        rng = _rng(seed)
        null = {name: np.empty(int(n_surrogates)) for name in per_band}
        for i in range(int(n_surrogates)):
            y_s = _surrogate_source(y, rng)
            seg_ys = _welch_segments(y_s, nperseg, noverlap)
            seg_ys = (seg_ys - seg_ys.mean(axis=1, keepdims=True)) * taper
            fys = np.fft.rfft(seg_ys, axis=1)
            for name, vals in per_band.items():
                f_lo, f_hi = vals["band_hz"]
                idx = np.flatnonzero((freqs >= f_lo) & (freqs <= f_hi))
                null[name][i] = (
                    _psi_from_spectra(fx, fys, idx) if idx.size >= 2 else np.nan
                )
        for name, vals in per_band.items():
            obs = vals["value"]
            nl = null[name]
            nl = nl[np.isfinite(nl)]
            vals["p_surrogate"] = (
                float((1 + np.sum(np.abs(nl) >= abs(obs))) / (nl.size + 1))
                if nl.size and np.isfinite(obs)
                else None
            )

    total = float(np.nansum([v["value"] for v in per_band.values()]))
    primary = next(iter(per_band.values()))
    p_primary = primary.get("p_surrogate")
    if p_primary is None and np.isfinite(primary.get("z", np.nan)):
        # two-sided normal approximation on the jackknife z (Nolte et al.)
        p_primary = float(2 * stats.norm.sf(abs(primary["z"])))

    return DirectedResult(
        method="psi",
        x_to_y=total,
        y_to_x=-total,
        net=total,
        unit="psi",
        p_x_to_y=p_primary,
        p_y_to_x=p_primary,
        p_net=p_primary,
        per_band=per_band,
        spectrum={
            "freqs": freqs,
            "psi_freqs": (freqs[:-1] + freqs[1:]) / 2.0,
            "psi_per_freq": psi_per_freq,
            "coherence": np.abs(coh_full),
        },
        n_trials=n_trials,
        n_times=n_times,
        fs=float(fs),
        params={
            "nperseg": int(nperseg),
            "noverlap": int(noverlap),
            "window": window,
            "freq_resolution_hz": float(df),
            "n_segments": int(n_seg),
            "bands": {k: list(v) for k, v in band_map.items()},
            "jackknife": bool(jackknife),
            "n_surrogates": int(n_surrogates),
            "detrend": detrend,
            "seed": seed,
        },
        diagnostics={
            "n_segments": int(n_seg),
            "mean_coherence": float(np.mean(np.abs(coh_full))),
            "p_source": "surrogate" if n_surrogates > 0 else ("jackknife_z" if jackknife else None),
            # PSI is antisymmetric: one test, direction carried by the sign.
            "p_covers_both_directions": True,
            "warnings": warnings_all,
            "ok_for_interpretation": len(warnings_all) == 0,
        },
    )


# ---------------------------------------------------------------------------
# 3. Transfer entropy (model-free, nonlinear)
# ---------------------------------------------------------------------------


def _discretize(a: np.ndarray, bins: int, strategy: str) -> np.ndarray:
    """
    Map a (n_trials, n_times) float array to integer states in [0, bins).

    Edges are computed once over all trials so every trial shares a state space.
    """
    flat = a.ravel()
    if strategy == "uniform":
        lo, hi = float(flat.min()), float(flat.max())
        if hi <= lo:
            return np.zeros_like(a, dtype=np.int64)
        edges = np.linspace(lo, hi, bins + 1)[1:-1]
    elif strategy == "quantile":
        qs = np.linspace(0.0, 1.0, bins + 1)[1:-1]
        edges = np.unique(np.quantile(flat, qs))
        if edges.size == 0:
            return np.zeros_like(a, dtype=np.int64)
    elif strategy == "discrete":
        vals = np.unique(flat)
        if vals.size > 64:
            raise ValueError(
                f"estimator='discrete' saw {vals.size} distinct values; that is a "
                "continuous signal — use 'quantile' or 'uniform' instead."
            )
        return np.searchsorted(vals, a).astype(np.int64)
    else:  # pragma: no cover - guarded by caller
        raise ValueError(f"unknown discretization {strategy!r}")
    return np.searchsorted(edges, a, side="right").astype(np.int64)


def _ordinal_symbols(a: np.ndarray, m: int) -> np.ndarray:
    """Bandt-Pompe ordinal patterns of order m -> (n_trials, n_times - m + 1) codes."""
    n_trials, n_times = a.shape
    if n_times <= m:
        raise ValueError(f"symbolic order m={m} needs n_times > m; got {n_times}")
    windows = np.stack([a[:, i : n_times - m + 1 + i] for i in range(m)], axis=-1)
    ranks = np.argsort(np.argsort(windows, axis=-1), axis=-1)
    powers = m ** np.arange(m)
    return (ranks * powers).sum(axis=-1).astype(np.int64)


def _codes(cols: List[np.ndarray]) -> np.ndarray:
    """Row-wise integer codes for a list of equal-length integer vectors."""
    if len(cols) == 1:
        return np.asarray(np.unique(cols[0], return_inverse=True)[1]).ravel()
    stacked = np.column_stack(cols)
    # ravel(): NumPy 2.0 briefly returned a column vector for axis-wise inverse
    return np.asarray(np.unique(stacked, axis=0, return_inverse=True)[1]).ravel()


def _entropy_bits(codes: np.ndarray, bias_correction: Optional[str]) -> float:
    """Plug-in Shannon entropy in bits, optionally Miller-Madow corrected."""
    n = codes.size
    if n == 0:
        return 0.0
    counts = np.bincount(codes)
    counts = counts[counts > 0]
    p = counts / n
    h = float(-np.sum(p * np.log2(p)))
    if bias_correction == "mm":
        h += (counts.size - 1) / (2.0 * n * np.log(2.0))
    return h


def _te_one_direction(
    src_q: np.ndarray,
    tgt_q: np.ndarray,
    k: int,
    l: int,
    delay: int,
    bias_correction: Optional[str],
) -> Tuple[float, int, int]:
    """
    TE(source -> target) in bits from pre-discretized integer series.

    TE = H(Y_t, Y_hist) + H(Y_hist, X_hist) - H(Y_hist) - H(Y_t, Y_hist, X_hist)
    """
    n_trials, n_times = tgt_q.shape
    start = max(k, delay + l - 1)
    if n_times - start < 2:
        raise ValueError(
            f"history k={k}, l={l}, delay={delay} leaves < 2 samples per trial "
            f"(n_times={n_times})"
        )
    fut, y_hist, x_hist = [], [], []
    for tr in range(n_trials):
        t = np.arange(start, n_times)
        fut.append(tgt_q[tr, t])
        y_hist.append(np.column_stack([tgt_q[tr, t - j] for j in range(1, k + 1)]))
        x_hist.append(
            np.column_stack([src_q[tr, t - delay - j] for j in range(0, l)])
        )
    a = np.concatenate(fut)
    b = np.vstack(y_hist)
    c = np.vstack(x_hist)

    code_b = _codes([b[:, j] for j in range(b.shape[1])])
    code_c = _codes([c[:, j] for j in range(c.shape[1])])
    h_ab = _entropy_bits(_codes([a, code_b]), bias_correction)
    h_bc = _entropy_bits(_codes([code_b, code_c]), bias_correction)
    h_b = _entropy_bits(code_b, bias_correction)
    h_abc = _entropy_bits(_codes([a, code_b, code_c]), bias_correction)
    te = h_ab + h_bc - h_b - h_abc
    n_joint = int(np.unique(_codes([a, code_b, code_c])).size)
    return float(te), a.size, n_joint


def transfer_entropy(
    X,
    Y,
    k: int = 1,
    l: int = 1,
    delay: int = 1,
    estimator: str = "quantile",
    bins: int = 4,
    symbolic_order: int = 3,
    bias_correction: Optional[str] = "mm",
    n_surrogates: int = 200,
    seed: Optional[int] = 0,
    detrend: Optional[str] = None,
    time_axis: int = -1,
) -> DirectedResult:
    """
    Transfer entropy — model-free, nonlinear directed information flow, in bits.

    ``TE(X -> Y) = I(Y_t ; X_past | Y_past)``: how much X's past reduces
    uncertainty about Y's present *beyond* what Y's own past already explains.

    TE is positively biased at finite sample size, so a raw TE > 0 means nothing
    on its own. This implementation therefore runs a surrogate test by default
    and reports both the raw value and ``bias_corrected`` (raw minus surrogate
    mean, the "effective transfer entropy").

    Args:
        X, Y: (n_times,), (n_trials, n_times), or list of 1-D trials
        k: target history length (samples)
        l: source history length (samples)
        delay: source lag in samples; ``delay=1`` is the immediate past
        estimator:
            ``'quantile'`` — equal-population bins (default; robust to skew/outliers)
            ``'uniform'``  — equal-width bins
            ``'discrete'`` — the signal is already integer-valued (spike counts);
                             states are taken as-is, no binning
            ``'symbolic'`` — Bandt-Pompe ordinal patterns of ``symbolic_order``;
                             amplitude-invariant, good for drifting LFP
        bins: number of states for quantile/uniform
        symbolic_order: pattern order m for ``'symbolic'`` (m! states)
        bias_correction: ``'mm'`` (Miller-Madow) applied to each entropy term, or None
        n_surrogates: surrogate draws for the p-value and bias correction.
            Set to 0 only if you are calibrating the null some other way.
        seed: RNG seed (default 0 — deterministic)
        detrend: usually ``None``; TE is invariant to monotone rescaling under
            quantile/symbolic estimators, so z-scoring buys nothing

    Returns:
        DirectedResult with ``unit='bits'``. ``diagnostics['samples_per_joint_state']``
        below ~10 means the estimate is undersampled and a warning fires — reduce
        ``bins``, ``k``, or ``l`` rather than reporting it.
    """
    if estimator not in ("quantile", "uniform", "discrete", "symbolic"):
        raise ValueError(
            f"estimator must be quantile|uniform|discrete|symbolic; got {estimator!r}"
        )
    if min(k, l) < 1 or delay < 1:
        raise ValueError(f"k, l, delay must all be >= 1; got k={k}, l={l}, delay={delay}")

    x, y = _pair_trials(X, Y, time_axis=time_axis)
    x = _detrend_trials(x, detrend)
    y = _detrend_trials(y, detrend)
    n_trials, n_times = x.shape

    if estimator == "symbolic":
        xq = _ordinal_symbols(x, symbolic_order)
        yq = _ordinal_symbols(y, symbolic_order)
    else:
        xq = _discretize(x, bins, estimator)
        yq = _discretize(y, bins, estimator)

    te_xy, n_used, n_joint_xy = _te_one_direction(xq, yq, k, l, delay, bias_correction)
    te_yx, _, n_joint_yx = _te_one_direction(yq, xq, k, l, delay, bias_correction)

    p_xy = p_yx = p_net = None
    eff_xy, eff_yx = te_xy, te_yx
    surrogate_info: Dict[str, Any] = {"n_surrogates": int(n_surrogates)}

    if n_surrogates > 0:
        rng = _rng(seed)
        null_xy = np.empty(int(n_surrogates))
        null_yx = np.empty(int(n_surrogates))
        for i in range(int(n_surrogates)):
            null_xy[i] = _te_one_direction(
                _surrogate_source(xq, rng).astype(np.int64), yq, k, l, delay, bias_correction
            )[0]
            null_yx[i] = _te_one_direction(
                _surrogate_source(yq, rng).astype(np.int64), xq, k, l, delay, bias_correction
            )[0]
        p_xy = float((1 + np.sum(null_xy >= te_xy)) / (n_surrogates + 1))
        p_yx = float((1 + np.sum(null_yx >= te_yx)) / (n_surrogates + 1))
        obs_net = te_xy - te_yx
        null_net = null_xy - null_yx
        p_net = float((1 + np.sum(np.abs(null_net) >= abs(obs_net))) / (n_surrogates + 1))
        eff_xy = te_xy - float(null_xy.mean())
        eff_yx = te_yx - float(null_yx.mean())
        surrogate_info.update(
            {
                "null_mean_x_to_y": float(null_xy.mean()),
                "null_mean_y_to_x": float(null_yx.mean()),
                "null_sd_x_to_y": float(null_xy.std(ddof=1)) if n_surrogates > 1 else 0.0,
                "null_sd_y_to_x": float(null_yx.std(ddof=1)) if n_surrogates > 1 else 0.0,
                "bias_corrected_x_to_y": eff_xy,
                "bias_corrected_y_to_x": eff_yx,
            }
        )

    samples_per_state = n_used / max(max(n_joint_xy, n_joint_yx), 1)
    warnings_all: List[str] = []
    if samples_per_state < 10:
        warnings_all.append(
            f"undersampled_te_{samples_per_state:.1f}_samples_per_joint_state"
        )
    if n_surrogates == 0:
        warnings_all.append("no_surrogates_raw_te_is_positively_biased")

    return DirectedResult(
        method="transfer_entropy",
        x_to_y=te_xy,
        y_to_x=te_yx,
        net=te_xy - te_yx,
        unit="bits",
        p_x_to_y=p_xy,
        p_y_to_x=p_yx,
        p_net=p_net,
        n_trials=n_trials,
        n_times=n_times,
        params={
            "k": int(k),
            "l": int(l),
            "delay": int(delay),
            "estimator": estimator,
            "bins": int(bins) if estimator in ("quantile", "uniform") else None,
            "symbolic_order": int(symbolic_order) if estimator == "symbolic" else None,
            "bias_correction": bias_correction,
            "n_surrogates": int(n_surrogates),
            "detrend": detrend,
            "seed": seed,
        },
        diagnostics={
            "n_embedding_samples": int(n_used),
            "n_joint_states_x_to_y": int(n_joint_xy),
            "n_joint_states_y_to_x": int(n_joint_yx),
            "samples_per_joint_state": float(samples_per_state),
            "bias_corrected_x_to_y": eff_xy,
            "bias_corrected_y_to_x": eff_yx,
            "surrogates": surrogate_info,
            "warnings": warnings_all,
            "ok_for_interpretation": len(warnings_all) == 0,
        },
    )


# ---------------------------------------------------------------------------
# Dispatcher and N-node networks
# ---------------------------------------------------------------------------

DIRECTED_METHODS = {
    "granger": granger,
    "gc": granger,
    "granger_spectral": granger_spectral,
    "sgc": granger_spectral,
    "psi": phase_slope_index,
    "phase_slope_index": phase_slope_index,
    "te": transfer_entropy,
    "transfer_entropy": transfer_entropy,
}


def directed_connectivity(X, Y, method: str = "granger", **kwargs) -> DirectedResult:
    """
    One entry point for all three directed estimators.

    Args:
        X, Y: any signal accepted by :func:`as_trials`
        method: ``'granger'``/``'gc'`` | ``'psi'``/``'phase_slope_index'`` |
            ``'te'``/``'transfer_entropy'``
        **kwargs: forwarded verbatim to the chosen estimator

    Example:
        >>> for m in ('granger', 'psi', 'te'):
        ...     r = directed_connectivity(v1, pfc, method=m, **({'fs': 1000.} if m == 'psi' else {}))
    """
    key = str(method).lower()
    if key not in DIRECTED_METHODS:
        raise ValueError(
            f"Unknown method={method!r}; choose from {sorted(set(DIRECTED_METHODS))}"
        )
    return DIRECTED_METHODS[key](X, Y, **kwargs)


def directed_network(
    signals,
    method: str = "granger",
    labels: Optional[Sequence[str]] = None,
    fdr: bool = True,
    fdr_method: str = "bh",
    **kwargs,
) -> Dict[str, Any]:
    """
    All-pairs directed connectivity over N nodes.

    Args:
        signals: ``{label: signal}`` dict, a list of signals, or a 3-D array
            ``(n_nodes, n_trials, n_times)`` / 2-D ``(n_nodes, n_times)``
        method: as in :func:`directed_connectivity`
        labels: node names (required only when ``signals`` is not a dict)
        fdr: Benjamini-Hochberg across the family of all N*(N-1) ordered pairs.
            The family is the whole matrix — correcting one cell in isolation
            would imply an undisclosed set.
        **kwargs: forwarded to the estimator

    Returns:
        dict with ``matrix`` (``M[i, j]`` = influence of node i on node j;
        diagonal NaN), ``p_matrix``, ``q_matrix`` (NaN when ``fdr=False`` or no
        p-values), ``labels``, ``results`` (the full DirectedResult per ordered
        pair), ``method``, and ``warnings``.
    """
    if isinstance(signals, dict):
        labels = list(signals.keys())
        series = [signals[k] for k in labels]
    else:
        arr = signals
        if isinstance(arr, np.ndarray) and arr.ndim in (2, 3):
            series = [arr[i] for i in range(arr.shape[0])]
        else:
            series = list(arr)
        if labels is None:
            labels = [f"node{i}" for i in range(len(series))]
        labels = list(labels)
    n = len(series)
    if n < 2:
        raise ValueError(f"directed_network needs >= 2 nodes; got {n}")
    if len(labels) != n:
        raise ValueError(f"{len(labels)} labels for {n} signals")

    matrix = np.full((n, n), np.nan)
    p_matrix = np.full((n, n), np.nan)
    results: Dict[Tuple[str, str], DirectedResult] = {}
    warnings_all: List[str] = []

    for i in range(n):
        for j in range(i + 1, n):
            res = directed_connectivity(series[i], series[j], method=method, **kwargs)
            matrix[i, j] = res.x_to_y
            matrix[j, i] = res.y_to_x
            if res.p_x_to_y is not None:
                p_matrix[i, j] = res.p_x_to_y
            if res.p_y_to_x is not None:
                p_matrix[j, i] = res.p_y_to_x
            results[(labels[i], labels[j])] = res
            for w in res.diagnostics.get("warnings", []):
                tag = f"{labels[i]}<->{labels[j]}: {w}"
                if tag not in warnings_all:
                    warnings_all.append(tag)

    q_matrix = np.full((n, n), np.nan)
    if fdr:
        off = ~np.eye(n, dtype=bool)
        finite = off & np.isfinite(p_matrix)
        if finite.any():
            q_matrix[finite] = stats.false_discovery_control(
                p_matrix[finite], method=fdr_method
            )

    return {
        "matrix": matrix,
        "p_matrix": p_matrix,
        "q_matrix": q_matrix,
        "labels": labels,
        "method": method,
        "n_nodes": n,
        "fdr_family_size": int(n * (n - 1)) if fdr else 0,
        "results": results,
        "params": kwargs,
        "warnings": warnings_all,
    }
