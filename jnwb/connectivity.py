"""
jnwb.connectivity -- functional connectivity, mutual information, and Granger causality.

Every estimator is modality-agnostic (LFP traces, binned spike counts, MUAe envelopes,
band-power time courses -- any regularly sampled series). ``CANONICAL_BANDS`` is imported from
``jnwb.spectral``.

Provides methods to compute directional functional connectivity metrics (bivariate Granger Causality),
Shannon Mutual Information between spike trains, and network graph analysis.

MI estimators:
- ``binary_occupancy`` — MI of per-bin spike presence (0/1); discards count/rate structure
- ``spike_count`` — MI of per-bin spike counts (discrete)

Granger returns residual diagnostics; optional ridge VAR; lag selection via AIC/BIC/HQIC.
Residual variance is the maximum-likelihood RSS / N, not RSS / (N - p): the Geweke measure
is a log ratio of ML variances, and the information criteria in ``_info_criterion`` carry
their own explicit parameter counts. This line read ``explicit N - p divisors`` while
``_residual_variance`` took an ``n_params`` argument it never used.

Modality-agnostic directed connectivity (added 2026-08-04)
---------------------------------------------------------
``granger`` / ``phase_slope_index`` / ``transfer_entropy`` all take the same
``(X, Y, ...)`` contract and return the same ``DirectedResult`` shape, so LFP
traces, binned spike counts, MUAe envelopes, band-power time courses and any
other regularly sampled series go through identical code:

    >>> import jnwb
    >>> jnwb.granger(v1_lfp, pfc_lfp, order='auto')          # (n_trials, n_times)
    >>> jnwb.granger_spectral(v1_lfp, pfc_lfp, fs=1000.0)    # Geweke, per band
    >>> jnwb.phase_slope_index(v1_lfp, pfc_lfp, fs=1000.0)   # frequency-resolved
    >>> jnwb.transfer_entropy(rate_a, rate_b, n_surrogates=200)
    >>> jnwb.bin_spikes(spike_times, (-0.5, 1.0), 10.0)      # spikes -> (trials, bins)

Sign convention is uniform: ``x_to_y`` is X -> Y (X leads / X predicts Y).

"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from ._dictlike import DictAccessMixin
from ._backend import (
    CPU,
    CUDA,
    resolve_device,
    warn_device_fallback,
    warn_no_gpu_path,
)
from ._parallel import parallel_map
from ._spread import is_constant, zscore
from ._units import resolve_unit_alias
from ._bins import bin_edges, right_open_counts, whole_bin_count
from ._layout import require_trial_length
from ._rng import Default, REQUIRED, RNGLike, resolve_rng, resolve_seed_alias
from scipy import stats

log = logging.getLogger(__name__)

#: Settled band edges (Hz) -- single source of truth is jnwb.spectral.CANONICAL_BANDS;
#: re-exported here unchanged so this module's existing consumers and internal uses below
#: keep working without modification.
from .spectral import CANONICAL_BANDS


def _fixed_order(order: Any, func_name: str) -> int:
    """A caller-fixed autoregressive order as an int, or ``ValueError``.

    ``int()`` alone accepted ``0`` (a model with no history, returning zero causality),
    truncated ``2.5`` to ``2`` and read ``True`` as ``1``. An integral float such as ``3.0``
    is accepted as the integer it names.
    """
    if isinstance(order, (bool, np.bool_)) or isinstance(order, str):
        raise ValueError(f"{func_name}: order must be 'auto' or an integer >= 1; got {order!r}")
    try:
        as_float = float(order)
    except (TypeError, ValueError):
        raise ValueError(
            f"{func_name}: order must be 'auto' or an integer >= 1; got {order!r}") from None
    if not np.isfinite(as_float) or as_float != int(as_float) or as_float < 1:
        raise ValueError(f"{func_name}: order must be 'auto' or an integer >= 1; got {order!r}")
    return int(as_float)


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
    time_window_s: Optional[Tuple[float, float]] = None,
    bin_size_ms: float = 10.0,
    estimator: str = "binary_occupancy",
    *,
    time_window: Optional[Tuple[float, float]] = None,
) -> float:
    """
    Compute Shannon Mutual Information (MI) between two binned spike trains.

    Args:
        spike_times1: Spike times of unit 1 (seconds)
        spike_times2: Spike times of unit 2 (seconds)
        time_window_s: (start_time, end_time) in seconds. `time_window` is the old
            spelling, kept working; it named no unit while `bin_size_ms` beside it did.
        bin_size_ms: Bin size in ms
        estimator:
            - ``binary_occupancy`` (default): MI of bin occupancy (hist > 0).
              This is **not** MI of full spike trains / rates.
            - ``spike_count``: MI of integer spike counts per bin.

    Returns:
        mi: Mutual Information in bits
    """
    time_window_s = resolve_unit_alias(
        time_window_s, time_window,
        canonical_name="time_window_s", alias_name="time_window",
        func_name="spike_mutual_information",
    )
    if estimator not in ("binary_occupancy", "spike_count"):
        raise ValueError(
            f"Unknown estimator={estimator!r}; use 'binary_occupancy' or 'spike_count'"
        )

    if len(spike_times1) == 0 or len(spike_times2) == 0:
        raise ValueError(
            "spike_mutual_information requires non-empty spike_times1 and spike_times2"
        )

    whole_bin_count(time_window_s, bin_size_ms / 1000.0, "spike_mutual_information",
                    "time_window_s", unit="s")
    hist1 = bin_spikes(spike_times1, window_s=time_window_s, bin_size_ms=bin_size_ms)[0]
    hist2 = bin_spikes(spike_times2, window_s=time_window_s, bin_size_ms=bin_size_ms)[0]

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
    time_window_s: Optional[Tuple[float, float]] = None,
    bin_size_ms: float = 10.0,
    *,
    time_window: Optional[Tuple[float, float]] = None,
) -> float:
    """Explicit alias for binary occupancy MI. `time_window_s` is in seconds."""
    return spike_mutual_information(
        spike_times1,
        spike_times2,
        time_window_s,
        bin_size_ms=bin_size_ms,
        estimator="binary_occupancy",
        time_window=time_window,
    )


def spike_count_mutual_information(
    spike_times1: np.ndarray,
    spike_times2: np.ndarray,
    time_window_s: Optional[Tuple[float, float]] = None,
    bin_size_ms: float = 10.0,
    *,
    time_window: Optional[Tuple[float, float]] = None,
) -> float:
    """Discrete MI on per-bin spike counts. `time_window_s` is in seconds."""
    return spike_mutual_information(
        spike_times1,
        spike_times2,
        time_window_s,
        bin_size_ms=bin_size_ms,
        estimator="spike_count",
        time_window=time_window,
    )


def _residual_variance(residuals: np.ndarray) -> float:
    """Maximum-likelihood residual variance: RSS divided by the sample count N.

    Took an ``n_params`` argument until 0.2.5 and never read it, so both call sites passed a
    parameter count into a divisor that was always ``N``. Removed rather than honoured: the
    ML convention is what the Geweke log ratio wants.
    """
    n = len(residuals)
    return float(np.sum(np.asarray(residuals, dtype=float) ** 2) / max(n, 1))


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
    context: str = "fit_var_bivariate",
    ran_on: Optional[list] = None,
) -> Union[Tuple[float, float], Tuple[float, float, np.ndarray, np.ndarray]]:
    """
    Fit restricted and unrestricted VAR(p) models for bivariate Granger causality.

    Model 1 (restricted):   x(t) = c + sum_{i=1}^p a_i x(t-i) + e_r(t)
    Model 2 (unrestricted): x(t) = c + sum_{i=1}^p a_i x(t-i) + sum_{i=1}^p b_i y(t-i) + e_u(t)

    Returns:
        var_restricted: Residual variance of the restricted model (RSS / N).
        var_unrestricted: Residual variance of the unrestricted model (RSS / N).
        residuals_restr (optional): Residual time series of the restricted model.
        residuals_unrestr (optional): Residual time series of the unrestricted model.

    Args:
        context: The public function the caller invoked, used in device warnings.
            `fit_var_bivariate` is not exported, so naming it sends the reader to code
            they did not call.
        ran_on: When given, receives the device this fit ran on, so a caller that fits
            many times can tell whether one of them fell back.
    """
    resolved = resolve_device(device, context=context, prefer="cupy")
    if resolved == CUDA and ridge > 0:
        # The GPU branch solves by lstsq only; the ridge penalty is applied in the CPU
        # branch below. Requesting both used to skip the GPU with nothing said.
        warn_no_gpu_path(
            context, "the ridge-penalised solver has no GPU path (pass ridge=0 to use "
                     "the GPU)")
    if resolved == CUDA and ridge <= 0:
        try:
            import cupy as cp

            x_gpu = cp.asarray(x)
            y_gpu = cp.asarray(y)
            n = len(x_gpu)
            if n <= order * 2 + 1:
                raise ValueError(
                    f"fit_var_bivariate requires n > 2*order+1; got n={n}, order={order}"
                )

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
                (cp.sum(residuals_restr**2) / max(n_samples, 1)).get()
            )

            beta_unrestr, _, _, _ = cp.linalg.lstsq(XY_reg, target, rcond=None)
            residuals_unrestr = target - XY_reg @ beta_unrestr
            var_unrestricted = float(
                (cp.sum(residuals_unrestr**2) / max(n_samples, 1)).get()
            )

            if return_residuals:
                result = (
                    var_restricted,
                    var_unrestricted,
                    cp.asnumpy(residuals_restr),
                    cp.asnumpy(residuals_unrestr),
                )
            else:
                result = (var_restricted, var_unrestricted)
            if ran_on is not None:
                ran_on.append(CUDA)
            return result
        except Exception as e:
            warn_device_fallback(context, e)
            log.warning(f"CUDA VAR fitting failed: {e}. Falling back to CPU.")

    # CPU implementation
    n = len(x)
    if n <= order * 2 + 1:
        raise ValueError(
            f"fit_var_bivariate requires n > 2*order+1; got n={n}, order={order}"
        )

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
    var_restricted = _residual_variance(residuals_restr)

    beta_unrestr = _ridge_lstsq(XY_reg, target, ridge)
    residuals_unrestr = target - XY_reg @ beta_unrestr
    var_unrestricted = _residual_variance(residuals_unrestr)

    if ran_on is not None:
        ran_on.append(CPU)
    if return_residuals:
        return var_restricted, var_unrestricted, residuals_restr, residuals_unrestr
    return float(var_restricted), float(var_unrestricted)


def _info_criterion(n_samples: int, rss_var: float, n_params: int, criterion: str) -> float:
    """Computes information criterion using ML residual variance sigma2 = RSS / N."""
    if rss_var <= 0 or not np.isfinite(rss_var):
        return float("inf")
    sigma2 = float(rss_var)
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
    context: str = "select_optimal_lag",
    ran_on: Optional[list] = None,
) -> int:
    """
    Select optimal VAR order p using AIC, BIC, or HQIC on the unrestricted model.

    ``ran_on``, when given, receives the device of every fit, as in
    :func:`fit_var_bivariate`.
    """
    n = len(x)
    best_ic = float("inf")
    opt_lag = 1

    actual_max = min(max_lag, (n - 2) // 3)
    if actual_max < 1:
        return 1

    # Once, before the loop. This used to resolve inside `fit_var_bivariate` on every
    # iteration, so one `select_optimal_lag(max_lag=6, device='cuda')` on a machine with
    # no GPU emitted six identical warnings.
    resolved = resolve_device(device, context=context, prefer="cupy")
    if resolved == CUDA and ridge > 0:
        warn_no_gpu_path(
            context, "the ridge-penalised solver has no GPU path (pass ridge=0 to use "
                     "the GPU)")
        resolved = CPU

    for p in range(1, actual_max + 1):
        _, var_unrestricted = fit_var_bivariate(
            x, y, p, device=resolved, ridge=ridge, context=context, ran_on=ran_on)
        n_samples = n - p
        n_params = 2 * p + 1
        ic = _info_criterion(n_samples, var_unrestricted, n_params, criterion)
        if ic < best_ic:
            best_ic = ic
            opt_lag = p

    return opt_lag


def _adf_pvalue(series: np.ndarray) -> float:
    """Dickey-Fuller p-value (no lag augmentation, constant term). H0: unit root.

    The Dickey-Fuller t-statistic is not asymptotically normal under the unit-root null:
    its distribution is shifted well to the left, so the 5% critical value with a constant
    is near -2.86 rather than -1.645. This used to return ``stats.norm.cdf(t_stat)``,
    described as a conservative flag, but the error runs the other way. Measured on pure
    random walks, it certified 48.4% of them stationary at n = 200, 46.5% at n = 500 and
    46.0% at n = 2000, against the 5% a correct test gives, so `stationarity_ok` and
    `ok_for_interpretation` were close to coin flips on exactly the series a user needs
    warned about.

    `statsmodels` is a hard dependency, so this defers to its MacKinnon p-values for the
    same regression (``maxlag=0``, ``regression='c'``) rather than carrying a private and
    wrong approximation.
    """
    y = np.asarray(series, dtype=float).ravel()
    if len(y) < 10:
        return float("nan")
    if not np.all(np.isfinite(y)) or np.ptp(y) == 0:
        return float("nan")
    try:
        import warnings

        from statsmodels.tsa.stattools import adfuller

        with warnings.catch_warnings():
            # statsmodels warns that adfuller's plain-tuple return will become an
            # ADFullerResult in 0.16. Read the p-value in a way that works either way
            # rather than emitting a FutureWarning from every Granger diagnostic.
            warnings.simplefilter("ignore", FutureWarning)
            res = adfuller(y, maxlag=0, regression="c", autolag=None)
        return float(res[1]) if isinstance(res, tuple) else float(res.pvalue)
    except Exception:
        return float("nan")


def _ljung_box_pvalue(residuals: np.ndarray, nlags: int = 10) -> float:
    """Ljung–Box portmanteau test p-value on residual autocorrelations."""
    r = np.asarray(residuals, dtype=float).ravel()
    n = len(r)
    # Constant residuals have no autocorrelation to test; centred, they were rounding residue
    # whose "autocorrelation" was 1 at every lag, and p read 0.0.
    if n < nlags + 2 or is_constant(r):
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
    # Not tested is not passed. `bool(np.isnan(adf_p) or ...)` reported stationarity_ok
    # True whenever the test could not run -- most importantly when `statsmodels`, a
    # declared hard dependency, is absent, since `_adf_pvalue` converts that ImportError
    # into NaN. Two pure random walks then came back ok_for_interpretation=True with an
    # empty warnings list.
    if np.isnan(adf_p):
        warnings.append("stationarity_not_tested")
    elif adf_p > 0.05:
        warnings.append("possible_nonstationarity_adf_p>0.05")
    if np.isnan(lb_p):
        warnings.append("residual_whiteness_not_tested")
    elif lb_p < 0.05:
        warnings.append("residual_autocorrelation_ljung_box_p<0.05")
    return {
        "adf_pvalue": adf_p,
        "ljung_box_pvalue": lb_p,
        "warnings": warnings,
        "stationarity_ok": bool(not np.isnan(adf_p) and adf_p <= 0.05),
        "residual_whiteness_ok": bool(not np.isnan(lb_p) and lb_p >= 0.05),
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

    F_2_to_1 is how much Signal 2's past improves the prediction of Signal 1
    F_1_to_2 is how much Signal 1's past improves the prediction of Signal 2

    Also returns residual diagnostics (lightweight ADF + Ljung–Box). Do not interpret
    GC as biological directionality when diagnostics warn. ``device_used`` names the
    device ('cpu' or 'cuda') that ran every fit.

    References:
        Granger, C. W. J. (1969). Investigating causal relations by econometric models
        and cross-spectral methods. Econometrica. doi:10.2307/1912791 -- Granger
        causality: X Granger-predicts Y when the past of X improves the prediction of Y
        beyond the past of Y, a temporal-lag asymmetry rather than a causal effect.
    """
    warnings.warn(
        "granger_causality is deprecated; use jnwb.granger, which returns DirectedResult.",
        DeprecationWarning,
        stacklevel=2,
    )
    s1 = np.asarray(signal1).flatten()
    s2 = np.asarray(signal2).flatten()

    s1 = zscore(s1.astype(float), axis=0)
    s2 = zscore(s2.astype(float), axis=0)

    # One device decision for the whole call, announced under the name the caller used.
    # With order='auto' this function reaches `fit_var_bivariate` up to 2*max_lag + 2
    # times; each used to resolve for itself and warn as "fit_var_bivariate".
    resolved = resolve_device(device, context="granger_causality", prefer="cupy")
    if resolved == CUDA and ridge > 0:
        warn_no_gpu_path(
            "granger_causality",
            "the ridge-penalised solver has no GPU path (pass ridge=0 to use the GPU)")
        resolved = CPU

    def _fit_all(dev, ran_on):
        if order == "auto":
            o21 = select_optimal_lag(
                s1, s2, device=dev, criterion=criterion, ridge=ridge,
                context="granger_causality", ran_on=ran_on
            )
            o12 = select_optimal_lag(
                s2, s1, device=dev, criterion=criterion, ridge=ridge,
                context="granger_causality", ran_on=ran_on
            )
        else:
            o21 = o12 = _fixed_order(order, "granger_causality")
        fit21 = fit_var_bivariate(
            s1, s2, o21, device=dev, ridge=ridge, return_residuals=True,
            context="granger_causality", ran_on=ran_on
        )
        fit12 = fit_var_bivariate(
            s2, s1, o12, device=dev, ridge=ridge, return_residuals=True,
            context="granger_causality", ran_on=ran_on
        )
        return o21, o12, fit21, fit12

    # Every fit of one call runs on one device. A fit that fell back has already warned;
    # the fits that did run on the GPU are discarded and the whole call recomputed on the
    # CPU, so the order selection and both F statistics come from one estimator and
    # `device_used` names it.
    ran_on = []
    order_2_to_1, order_1_to_2, fit21, fit12 = _fit_all(resolved, ran_on)
    if resolved == CUDA and CPU in ran_on:
        resolved = CPU
        order_2_to_1, order_1_to_2, fit21, fit12 = _fit_all(CPU, None)
    var_r1, var_u1, res_r1, res_u1 = fit21
    var_r2, var_u2, res_r2, res_u2 = fit12
    f_2_to_1 = np.log(var_r1 / var_u1) if var_u1 > 0 else 0.0
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
        "device_used": resolved,
    }


def network_topology(
    adjacency_matrix: np.ndarray,
    threshold: float = 0.3,
) -> Dict[str, Union[float, int, List[int]]]:
    """
    Compute network graph metrics from a correlation or Granger causality matrix.

    The diagonal is ignored.

    Raises:
        ValueError: If ``adjacency_matrix`` is not square 2-D, an off-diagonal entry is NaN or
            Inf, or ``threshold`` is not finite. A NaN entry counted as "no edge", and a
            non-square matrix returned in- and out-degree lists of different lengths.
    """
    adjacency_matrix = np.asarray(adjacency_matrix, dtype=float)
    if adjacency_matrix.ndim != 2 or adjacency_matrix.shape[0] != adjacency_matrix.shape[1]:
        raise ValueError(
            f"network_topology: adjacency_matrix must be square 2-D, got shape {adjacency_matrix.shape}"
        )
    off_diagonal = ~np.eye(adjacency_matrix.shape[0], dtype=bool)
    if not np.all(np.isfinite(adjacency_matrix[off_diagonal])):
        raise ValueError("network_topology: adjacency_matrix has NaN or Inf off the diagonal")
    if not np.isfinite(threshold):
        raise ValueError(f"network_topology: threshold must be finite, got {threshold}")
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
class DirectedResult(DictAccessMixin):
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
            # Both channels. `log.warning` is invisible to `warnings.simplefilter`,
            # `pytest.warns` and `-W error`, so a caller who had asked to be told about
            # silent data loss was not told: the truncation reached the estimator with an
            # empty warning list. The log line stays for operators; the warning is what
            # the caller can actually act on.
            log.warning(
                "%s: ragged trials %s -> truncated to %d samples", name,
                sorted(lengths), n_min,
            )
            warnings.warn(
                f"{name}: ragged trial lengths {sorted(lengths)} truncated to {n_min} "
                f"samples, discarding {sum(lengths) - n_min * len(arrs)} sample(s). Pass "
                "allow_ragged=False to make this an error.",
                RuntimeWarning,
                stacklevel=3,
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
        return zscore(a, axis=1)
    if mode == "linear":
        n = a.shape[1]
        t = np.linspace(-1.0, 1.0, n)
        design = np.column_stack([np.ones(n), t])
        beta = np.linalg.lstsq(design, a.T, rcond=None)[0]
        return a - (design @ beta).T
    raise ValueError(f"Unknown detrend={mode!r}; use None|'demean'|'zscore'|'linear'")


def _count_nonfinite_spikes(spike_times, trial_starts) -> int:
    """Number of non-finite entries in `spike_times`, whatever nesting it arrived in."""
    if trial_starts is None and isinstance(spike_times, (list, tuple)) and (
        len(spike_times) == 0 or np.ndim(spike_times[0]) >= 1
    ):
        trains = [np.asarray(s, dtype=float).ravel() for s in spike_times]
    else:
        trains = [np.asarray(spike_times, dtype=float).ravel()]
    return int(sum(int(np.sum(~np.isfinite(s))) for s in trains))


def bin_spikes(
    spike_times,
    window_s: Optional[Tuple[float, float]] = None,
    bin_size_ms: float = 10.0,
    trial_starts: Optional[Sequence[float]] = None,
    output: str = "count",
    return_centers: bool = False,
    *,
    window: Optional[Tuple[float, float]] = None,
):
    r"""Bridge spike data into the ``(n_trials, n_bins)`` contract used by every estimator.

    Temporal Axis Contract
    ----------------------
    - **Bins**: $K = (t_1 - t_0) / \Delta$ intervals, where
      $t_0, t_1 = \text{window}$ (seconds) and $\Delta = \text{bin\_size\_ms} / 1000$ (seconds).
      $K$ must be a whole number, so every bin is $\Delta$ wide.
      Each bin $k \in \{0, \dots, K-1\}$ covers the right-open interval:
      $$[t_k, t_{k+1}) = [t_0 + k\Delta,\; t_0 + (k+1)\Delta)$$
    - **Boundary Exclusion**: Spikes strictly prior to $t_0$ ($t < t_0$) or at/beyond
      the terminal boundary ($t \ge t_1$) are excluded. This enforces uniform right-open
      semantics $[t_k, t_{k+1})$ across all bins, avoiding the default NumPy histogram
      right-closed boundary artifact on the last bin.
    - **Coordinates / Bin Centers**: When ``return_centers=True``, returns the bin centers
      $c_k = t_0 + (k + 0.5)\Delta$ (seconds, aligned to the trial or window time origin).

    Args:
        spike_times: 1-D array of absolute spike times (seconds) if ``trial_starts``
            is provided; or a list/tuple of per-trial 1-D arrays relative to window.
        window: ``(start, end)`` in seconds. Relative to trial start if
            ``trial_starts`` is given, else absolute.
        bin_size_ms: Bin width in milliseconds ($\Delta \times 1000$).
        trial_starts: Optional trial-aligned event times (seconds) to epoch a single
            continuous spike train into trials.
        output: ``'count'`` (integer spike count per bin) or ``'rate'`` (spikes / sec = Hz).
        return_centers: If True, also return 1-D array of bin center coordinates.

    Returns:
        ``(n_trials, n_bins)`` float array, or ``(array, centers)`` if ``return_centers=True``.

    Raises:
        ValueError: If the span of ``window_s`` is not a whole multiple of ``bin_size_ms``;
            the message names the nearest valid windows.
    """
    # `window` named no unit while its neighbour `bin_size_ms` did, in the same call.
    # Both are times, one in seconds and one in milliseconds, and only one said so.
    window_s = resolve_unit_alias(
        window_s, window, canonical_name="window_s", alias_name="window",
        func_name="bin_spikes",
    )
    if output not in ("count", "rate"):
        raise ValueError(f"output must be 'count' or 'rate'; got {output!r}")
    t0, t1 = float(window_s[0]), float(window_s[1])
    if not t1 > t0:
        raise ValueError(f"window_s must satisfy end > start; got {window_s}")
    bin_sec = float(bin_size_ms) / 1000.0
    n_bins = whole_bin_count((t0, t1), bin_sec, "bin_spikes", "window_s", unit="s")
    if n_bins < 2:
        raise ValueError(
            f"window_s {window_s} at bin_size_ms={bin_size_ms} yields {n_bins} bins; need >= 2"
        )
    edges = bin_edges(t0, bin_sec, n_bins)

    n_nonfinite = _count_nonfinite_spikes(spike_times, trial_starts)
    if n_nonfinite:
        # These were dropped by the `(s >= t0) & (s < t1)` comparison, which is False for
        # NaN, so a train of NaN spike times produced a confident all-zero rate with no
        # indication that anything had been discarded.
        warnings.warn(
            f"bin_spikes: {n_nonfinite} non-finite spike time(s) dropped. They cannot be "
            "assigned to a bin; the returned counts are over the finite spikes only.",
            RuntimeWarning,
            stacklevel=2,
        )

    if trial_starts is not None:
        st = np.asarray(spike_times, dtype=float).ravel()
        trains = (st - float(start) for start in np.asarray(trial_starts, dtype=float).ravel())
    elif isinstance(spike_times, (list, tuple)) and (
        len(spike_times) == 0 or np.ndim(spike_times[0]) >= 1
    ):
        trains = [np.asarray(s, dtype=float).ravel() for s in spike_times]
    else:
        trains = [np.asarray(spike_times, dtype=float).ravel()]

    counts = right_open_counts(trains, t0, t1, bin_sec, n_bins)
    if counts.size == 0:
        raise ValueError("bin_spikes produced no trials")
    out = counts / bin_sec if output == "rate" else counts
    if return_centers:
        return out, edges[:-1] + bin_sec / 2.0
    return out


def _surrogate_rng(
    rng: RNGLike, func_name: str
) -> Tuple[np.random.Generator, Optional[int]]:
    """The surrogate generator, and the entropy that rebuilds it.

    An ``int`` seed draws the stream ``default_rng(seed)`` always drew, and its entropy is
    the seed. ``None`` draws fresh OS entropy and returns it, so ``rng=<entropy>``
    reproduces the p-values. A ``Generator`` is used in place, advancing the caller's
    stream; its position is not recoverable, so the entropy is ``None``. A float or bool
    raises ``TypeError`` through ``resolve_rng`` rather than being truncated.

    INTENTIONAL BREAK (0.2.6.1): ``None`` meant seed 0 and was recorded as ``seed=None``,
    a ``Generator`` raised ``TypeError`` and ``2.7`` ran as seed 2.
    """
    if isinstance(rng, np.random.Generator):
        return rng, None
    resolve_rng(rng, func_name=func_name)
    sequence = np.random.SeedSequence(None if rng is None else int(rng))
    return np.random.default_rng(sequence), int(sequence.entropy)


#: Fewest trials for which the surrogates re-pair trials instead of shifting them.
#: INTENTIONAL BREAK (0.2.6.1): this was 3. With n trials there are only about n!/e
#: derangements -- 2 at three trials -- so the null holds a handful of distinct values. On
#: independent white noise (100 pairs, 39 surrogates), P(p <= 0.05) was 0.25-0.33 at three
#: trials across granger, granger_spectral, phase_slope_index and transfer_entropy, and
#: 0.14-0.21 at four; the circular shift gave 0.02-0.10 at three, four and six trials,
#: and its one value above 0.075 (phase_slope_index at four) was 0.052 over 400 pairs.
_MIN_TRIALS_FOR_TRIAL_PERMUTATION = 7


def _surrogate_scheme(n_trials: int) -> str:
    """The surrogate scheme :func:`_surrogate_source` uses for ``n_trials``."""
    if n_trials >= _MIN_TRIALS_FOR_TRIAL_PERMUTATION:
        return "trial_permutation"
    return "circular_shift"


def _surrogate_source(a: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    Destroy cross-signal timing while preserving each trial's own autocorrelation.

    Trial permutation when there are at least ``_MIN_TRIALS_FOR_TRIAL_PERMUTATION`` (7)
    trials (pairs the source with the wrong trial), otherwise a circular shift of each
    trial by at least 10% of the record and at most 90% of it.
    """
    n_trials, n_times = a.shape
    if _surrogate_scheme(n_trials) == "trial_permutation":
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


def _granger_order_criteria(
    src: np.ndarray,
    tgt: np.ndarray,
    z_list: List[np.ndarray],
    max_order: int,
    ridge: float,
    criterion: str,
) -> np.ndarray:
    """Information criterion of the unrestricted model for each order 1..``max_order``.

    Every order is scored on one sample: the rows left after trimming ``max_order``
    presample values from each trial, so the criteria differ only through the model. The
    residual variance is the maximum-likelihood ``RSS / N``. Element ``p - 1`` holds order
    ``p``; an order with no more rows than parameters scores ``inf``.
    """
    sources = [tgt, src] + list(z_list)
    design, yy = _stack_var_design(tgt, sources, max_order)
    n_obs = design.shape[0]
    scores = np.full(max_order, np.inf)
    for p in range(1, max_order + 1):
        cols = [0] + [1 + s * max_order + j for s in range(len(sources)) for j in range(p)]
        if n_obs <= len(cols):
            break
        rss, _ = _ols_rss(design[:, cols], yy, ridge)
        scores[p - 1] = _info_criterion(n_obs, rss / n_obs, len(cols), criterion)
    return scores


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
    rng: RNGLike = Default(0),
    time_axis: int = -1,
    *,
    seed: Any = Default(0),
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
        order: VAR lag order, or ``'auto'`` to select by ``criterion``. Every candidate
            order is scored on one sample, trimmed by the largest candidate, with the
            maximum-likelihood residual variance ``RSS / N``
        max_lag: upper bound for automatic order selection
        criterion: ``'bic'`` (default, conservative) | ``'aic'`` | ``'hqic'``
        Z: optional conditioning signal(s) — same shape as X, or a list of such
            arrays. Present in *both* the restricted and unrestricted models, so
            the reported influence is X -> Y not routed through Z.
        ridge: L2 penalty on non-intercept coefficients (0 = plain OLS)
        detrend: per-trial preprocessing, default ``'zscore'``
        n_surrogates: if > 0, also run a surrogate test alongside the analytic
            F-test. Set this when residuals are not white. With 7 or more trials the
            surrogates pair the source with the wrong trial; with fewer, each source
            trial is circularly shifted by 10-90% of its length, because a few trials
            admit too few re-pairings for a null. ``params['surrogate_scheme']`` records
            which ran.
        rng: surrogate randomness: an ``int`` seed (default 0), a ``Generator`` used
            in place, or ``None`` for fresh OS entropy; a float is refused. Passing
            ``params['surrogate_seed_entropy']`` back as ``rng`` reproduces the
            p-values (``seed`` is the old spelling and still works)

    Returns:
        DirectedResult with ``unit='log variance ratio'``. ``p_*`` are analytic
        F-test p-values unless ``n_surrogates > 0``, in which case they are the
        surrogate p-values and the F-test values are kept in ``diagnostics``.
        Under the null the estimate approaches zero (non-negative under plain OLS since
        unrestricted RSS <= restricted RSS); read magnitude together with the p-value.

    Note:
        This is time-domain GC. Band-resolved directionality is *not* obtained by
        band-passing the input — filtering distorts the very lag structure GC
        reads. Use :func:`granger_spectral` (Geweke decomposition of this same
        VAR) or :func:`phase_slope_index` instead.

    References:
        Granger, C. W. J. (1969). Investigating causal relations by econometric models
        and cross-spectral methods. Econometrica. doi:10.2307/1912791 -- Granger
        causality: X Granger-predicts Y when the past of X improves the prediction of Y
        beyond the past of Y, a temporal-lag asymmetry rather than a causal effect.
        Geweke, J. (1982). Measurement of linear dependence and feedback between multiple
        time series. J. Am. Stat. Assoc. doi:10.1080/01621459.1982.10477803 -- the measure
        of linear feedback, the log ratio of restricted to unrestricted residual variance,
        which is ``x_to_y``.
        Geweke, J. F. (1984). Measures of conditional linear dependence and feedback
        between time series. J. Am. Stat. Assoc. doi:10.1080/01621459.1984.10477110
        -- the conditional measure, with the past of `Z` in both models.
        Lütkepohl, H. (2005). New Introduction to Multiple Time Series Analysis. Springer.
        doi:10.1007/978-3-540-27752-1 -- order selection, section 4.3: AIC, HQ and SC
        (``'bic'``) from the maximum-likelihood residual covariance, every candidate order
        fitted to the same sample.
    """
    seed = resolve_seed_alias(rng, seed, alias_name='seed', func_name='granger')
    surrogate_rng, seed_entropy = _surrogate_rng(seed, "granger")
    if criterion not in ("aic", "bic", "hqic"):
        raise ValueError(f"criterion must be aic|bic|hqic; got {criterion!r}")

    x, y = _pair_trials(X, Y, time_axis=time_axis)
    # Checked on the resolved trial shape, before detrending: a transposed array read as many
    # very short trials pools into plenty of design rows, so nothing further down is short of
    # data and nothing raised. The missing quantity is within-trial extent.
    require_trial_length(
        x,
        max_lag if isinstance(order, str) else _fixed_order(order, "granger"),
        "granger",
        history_name="max_lag" if isinstance(order, str) else "order",
        time_axis=time_axis,
    )
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
        if n_obs <= d_u.shape[1]:
            raise ValueError(
                f"order={p} leaves {n_obs} observations for {d_u.shape[1]} parameters; "
                "lower the order or supply more trials/samples"
            )
        rss_r, res_r = _ols_rss(d_r, yy, ridge)
        rss_u, res_u = _ols_rss(d_u, yy, ridge)
        df_u = n_obs - d_u.shape[1]
        df_extra = d_u.shape[1] - d_r.shape[1]
        # Maximum-likelihood residual variance, RSS / N, as in `_residual_variance`
        sig2_r = rss_r / max(n_obs, 1)
        sig2_u = rss_u / max(n_obs, 1)
        # A zero unrestricted residual variance means the VAR could not be fitted, not
        # that the directed influence is zero. Returning 0.0 made `granger(ones, ones)`
        # report x_to_y = y_to_x = 0.0 with an empty warnings list and
        # ok_for_interpretation = True, while `granger_spectral` raises and
        # `transfer_entropy` warns `degenerate_discretization` on the identical input.
        degenerate = not (sig2_u > 0) or not np.isfinite(sig2_u)
        gc_val = float(np.log(sig2_r / sig2_u)) if not degenerate else float("nan")
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
            "degenerate": bool(degenerate),
        }

    def _select_order(src: np.ndarray, tgt: np.ndarray) -> int:
        n_free = n_trials * n_times
        cap = max(1, min(int(max_lag), (n_times - 2) // 3, n_free // (8 * (2 + len(z_list)))))
        scores = _granger_order_criteria(src, tgt, z_list, cap, ridge, criterion)
        return int(np.argmin(scores)) + 1

    if order == "auto":
        order_xy = _select_order(x, y)
        order_yx = _select_order(y, x)
    else:
        order_xy = order_yx = _fixed_order(order, "granger")

    fit_xy = _one_direction(x, y, order_xy)  # X -> Y
    fit_yx = _one_direction(y, x, order_yx)  # Y -> X

    p_xy: Optional[float] = fit_xy["p_f"]
    p_yx: Optional[float] = fit_yx["p_f"]
    p_net: Optional[float] = None
    surrogate_info: Dict[str, Any] = {"n_surrogates": int(n_surrogates)}

    if n_surrogates > 0:
        obs_net = fit_xy["gc"] - fit_yx["gc"]
        null_xy = np.empty(n_surrogates)
        null_yx = np.empty(n_surrogates)
        for i in range(int(n_surrogates)):
            x_s = _surrogate_source(x, surrogate_rng)
            null_xy[i] = _one_direction(x_s, y, order_xy)["gc"]
            y_s = _surrogate_source(y, surrogate_rng)
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
    if fit_xy.get("degenerate") or fit_yx.get("degenerate"):
        warnings_all.append("degenerate_residual_variance_var_not_identifiable")
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
            "seed": None if isinstance(seed, np.random.Generator) else seed,
            "surrogate_seed_entropy": seed_entropy if n_surrogates > 0 else None,
            "surrogate_scheme": _surrogate_scheme(n_trials) if n_surrogates > 0 else None,
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
    rng: RNGLike = Default(0),
    time_axis: int = -1,
    *,
    seed: Any = Default(0),
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
        n_surrogates: surrogate test (there is no analytic null here); the scheme is
            as in :func:`granger` and is recorded in ``params['surrogate_scheme']``
        rng: surrogate randomness, as in :func:`granger`; passing
            ``params['surrogate_seed_entropy']`` back as ``rng`` reproduces the p-values

    Returns:
        DirectedResult with ``unit='log variance ratio'``,
        ``spectrum = {freqs, gc_x_to_y, gc_y_to_x}``, and
        ``per_band[name] = {value, value_reverse, peak_hz, peak_hz_reverse, ...}``.
        ``x_to_y``/``y_to_x`` are the frequency averages over the full spectrum.
        ``diagnostics['spectral_radius'] >= 1`` means the VAR is non-stationary
        and the decomposition must not be interpreted.

    References:
        Geweke, J. (1982). Measurement of linear dependence and feedback between multiple
        time series. J. Am. Stat. Assoc. doi:10.1080/01621459.1982.10477803 -- the
        frequency decomposition of the measure of linear feedback, from the transfer
        function of the fitted VAR.
    """
    seed = resolve_seed_alias(rng, seed, alias_name='seed', func_name='granger_spectral')
    surrogate_rng, seed_entropy = _surrogate_rng(seed, "granger_spectral")
    if fs is None or not np.isfinite(fs) or fs <= 0:
        raise ValueError(f"granger_spectral requires a positive fs; got {fs!r}")

    x, y = _pair_trials(X, Y, time_axis=time_axis)
    require_trial_length(
        x,
        max_lag if isinstance(order, str) else _fixed_order(order, "granger_spectral"),
        "granger_spectral",
        history_name="max_lag" if isinstance(order, str) else "order",
        time_axis=time_axis,
    )
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
        p = _fixed_order(order, "granger_spectral")

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
        null_xy = np.empty(int(n_surrogates))
        null_yx = np.empty(int(n_surrogates))
        null_xy_by_band: Dict[str, List[float]] = {name: [] for name in per_band}
        null_yx_by_band: Dict[str, List[float]] = {name: [] for name in per_band}
        for i in range(int(n_surrogates)):
            xs = _surrogate_source(x, surrogate_rng)
            a_s, sig_s, _ = _fit_var_matrix([xs, y], p, ridge=ridge)
            tmp = _spectral_gc_from_var(a_s, sig_s, freqs, fs)
            null_xy[i] = _mean_over(tmp[1], all_mask)
            ys = _surrogate_source(y, surrogate_rng)
            a_s2, sig_s2, _ = _fit_var_matrix([x, ys], p, ridge=ridge)
            tmp2 = _spectral_gc_from_var(a_s2, sig_s2, freqs, fs)
            null_yx[i] = _mean_over(tmp2[0], all_mask)
            for name, vals in per_band.items():
                f_lo, f_hi = vals["band_hz"]
                mask = (freqs >= f_lo) & (freqs <= f_hi)
                if mask.sum() >= 2:
                    null_xy_by_band[name].append(_mean_over(tmp[1], mask))
                    null_yx_by_band[name].append(_mean_over(tmp2[0], mask))
        p_xy = float((1 + np.sum(null_xy >= total_xy)) / (n_surrogates + 1))
        p_yx = float((1 + np.sum(null_yx >= total_yx)) / (n_surrogates + 1))
        for name, vals in per_band.items():
            f_lo, f_hi = vals["band_hz"]
            mask = (freqs >= f_lo) & (freqs <= f_hi)
            if mask.sum() >= 2:
                obs_xy = vals["value"]
                nb_xy = np.asarray(null_xy_by_band[name], dtype=float)
                vals["p_surrogate"] = float(
                    (1 + np.sum(nb_xy >= obs_xy)) / (len(nb_xy) + 1)
                )

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
            "seed": None if isinstance(seed, np.random.Generator) else seed,
            "surrogate_seed_entropy": seed_entropy if n_surrogates > 0 else None,
            "surrogate_scheme": _surrogate_scheme(n_trials) if n_surrogates > 0 else None,
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


def _psi_leave_one_out(fx: np.ndarray, fy: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """PSI over ``idx`` with each segment left out in turn: one replicate per segment.

    Replicate ``i`` is ``_psi_from_spectra`` on every segment but ``i``. Its spectra are means
    over the remaining segments, and each such sum is a prefix sum plus a suffix sum, so all
    ``S`` replicates cost T(S * B) over the ``B`` bins in ``idx`` instead of T(S^2 * F) for
    recomputing each from its segments. The two sums are added rather than one segment being
    subtracted from the total: a subtraction cancels when one segment holds most of a bin's power.
    """
    ax = fx[:, idx]
    ay = fy[:, idx]
    n_seg = ax.shape[0]

    def left_out_mean(v: np.ndarray) -> np.ndarray:
        before = np.zeros_like(v)
        np.cumsum(v[:-1], axis=0, out=before[1:])
        after = np.zeros_like(v)
        after[:-1] = np.cumsum(v[:0:-1], axis=0)[::-1]
        return (before + after) / (n_seg - 1)

    sxy = left_out_mean(ax * np.conj(ay))
    sxx = left_out_mean(np.abs(ax) ** 2)
    syy = left_out_mean(np.abs(ay) ** 2)
    denom = np.sqrt(sxx * syy)
    coh = np.divide(sxy, denom, out=np.zeros_like(sxy), where=denom > 0)
    return np.sum(np.imag(np.conj(coh[:, :-1]) * coh[:, 1:]), axis=1)


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
    rng: RNGLike = Default(0),
    time_axis: int = -1,
    *,
    seed: Any = Default(0),
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
            (``df``..``fs/2``); ``'canonical'`` for :data:`CANONICAL_BANDS`; a ``(fmin, fmax)``
            tuple; or a ``{name: (fmin, fmax)}`` dict
        nperseg: Welch segment length in samples (default: n_times // 4, clipped
            to [16, n_times]). Frequency resolution is ``fs / nperseg``.
        noverlap: segment overlap (default nperseg // 2)
        window: ``'hann'`` | ``'hamming'`` | ``'boxcar'``
        detrend: per-trial preprocessing, default ``'demean'``
        jackknife: estimate the standard deviation of PSI by leave-one-segment-out
            and report ``z = psi / sd``, the normalization Nolte et al. use for
            significance. ``|z| > 2`` is the conventional threshold.
        n_surrogates: optional surrogate test in addition to (or, with
            jackknife=False, instead of) the jackknife z; the scheme is as in
            :func:`granger` and is recorded in ``params['surrogate_scheme']``
        rng: surrogate randomness, as in :func:`granger`; passing
            ``params['surrogate_seed_entropy']`` back as ``rng`` reproduces the p-values

    Returns:
        DirectedResult with ``unit='psi'``, ``per_band[name] = {value, z, sd,
        n_freq_bins, band_hz}``, and ``spectrum = {freqs, psi_per_freq, coherence}``.
        ``x_to_y`` is the summed PSI over the whole requested range with
        ``y_to_x = -x_to_y``; ``net == x_to_y``. When no band holds the two frequency bins a
        slope needs, ``x_to_y``, ``y_to_x`` and ``net`` are NaN and
        ``diagnostics['ok_for_interpretation']`` is False.

    References:
        Nolte, G., et al. (2008). Robustly estimating the flow direction of information in
        complex physical systems. Phys. Rev. Lett. doi:10.1103/PhysRevLett.100.234101
        -- PSI, eq. 3, summed over the coherency of eq. 4 with the cross-spectrum
        ``S_xy = <X Y*>`` of eq. 2; ``z`` is the normalization of eq. 6. The paper's
        jackknife leaves out one epoch, a block of several segments, at a time; this one
        leaves out one Welch segment, and adjacent segments overlap by ``noverlap``.
    """
    seed = resolve_seed_alias(rng, seed, alias_name='seed', func_name='phase_slope_index')
    surrogate_rng, seed_entropy = _surrogate_rng(seed, "phase_slope_index")
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

    # The headline `net` is a raw sum over whatever band table the caller passed, so two
    # bands covering the same bins contribute that band twice: {'a': (14, 30), 'b':
    # (14, 30)} returned exactly 2x the estimate of {'beta': (14, 30)} on the same data.
    _band_bins: Dict[str, np.ndarray] = {
        _n: np.flatnonzero((freqs >= _lo) & (freqs <= _hi))
        for _n, (_lo, _hi) in band_map.items()
    }
    _overlaps = sorted(
        {
            tuple(sorted((_a, _b)))
            for _a in _band_bins
            for _b in _band_bins
            if _a != _b and np.intersect1d(_band_bins[_a], _band_bins[_b]).size
        }
    )
    if _overlaps:
        _pairs = ", ".join(f"{_a}/{_b}" for _a, _b in _overlaps)
        warnings_all.append(f"overlapping_bands_counted_more_than_once:{_pairs}")
        warnings.warn(
            "phase_slope_index: bands overlap on the frequency grid "
            f"({_pairs}); `net` sums the bands, so the shared bins are counted once per "
            "band. Use disjoint bands, or read `per_band` instead of `net`.",
            RuntimeWarning,
            stacklevel=2,
        )

    per_band: Dict[str, Dict[str, Any]] = {}
    jk_per_band: Dict[str, np.ndarray] = {}
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
            jk = _psi_leave_one_out(fx, fy, idx)
            sd =float(np.sqrt((n_seg - 1) / n_seg * np.sum((jk - jk.mean()) ** 2)))
            jk_per_band[name] = jk
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
        null = {name: np.empty(int(n_surrogates)) for name in per_band}
        for i in range(int(n_surrogates)):
            y_s = _surrogate_source(y, surrogate_rng)
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

    band_values = np.array([v["value"] for v in per_band.values()], dtype=float)
    # np.nansum of an all-NaN array is 0.0, which reads as "no lead" when no band had a slope.
    total = float(np.nansum(band_values)) if np.isfinite(band_values).any() else float("nan")

    # One top-level p-value across the evaluated bands
    p_top = None
    if len(per_band) == 1:
        single = next(iter(per_band.values()))
        p_top = single.get("p_surrogate")
        if p_top is None and np.isfinite(single.get("z", np.nan)):
            # Student t, not a standard normal: the delete-one jackknife z is built from
            # `n_seg` leave-one-out replicates and carries about `n_seg - 1` degrees of
            # freedom. The Gaussian tail reported p = 0.0 from 10 segments, and
            # overstated moderate evidence by an order of magnitude (z = 3.29 gave
            # 0.001 against 0.0094 under t(9)).
            p_top = float(2 * stats.t.sf(abs(single["z"]), df=max(n_seg - 1, 1)))
    else:
        if n_surrogates > 0 and null:
            valid_band_nulls = [null[k] for k in null if np.all(np.isfinite(null[k]))]
            if valid_band_nulls and np.isfinite(total):
                null_tot = np.sum(valid_band_nulls, axis=0)
                p_top = float((1 + np.sum(np.abs(null_tot) >= abs(total))) / (len(null_tot) + 1))
        elif jackknife and n_seg >= 3 and jk_per_band:
            jk_tot = np.sum(list(jk_per_band.values()), axis=0)
            sd_tot = float(np.sqrt((n_seg - 1) / n_seg * np.sum((jk_tot - jk_tot.mean()) ** 2)))
            if sd_tot > 0 and np.isfinite(sd_tot) and np.isfinite(total):
                z_tot = float(total / sd_tot)
                p_top = float(2 * stats.t.sf(abs(z_tot), df=max(n_seg - 1, 1)))

    return DirectedResult(
        method="psi",
        x_to_y=total,
        y_to_x=-total,
        net=total,
        unit="psi",
        p_x_to_y=p_top,
        p_y_to_x=p_top,
        p_net=p_top,
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
            "seed": None if isinstance(seed, np.random.Generator) else seed,
            "surrogate_seed_entropy": seed_entropy if n_surrogates > 0 else None,
            "surrogate_scheme": _surrogate_scheme(n_trials) if n_surrogates > 0 else None,
        },
        diagnostics={
            "n_segments": int(n_seg),
            "mean_coherence": float(np.mean(np.abs(coh_full))),
            "p_source": "surrogate" if n_surrogates > 0 else ("jackknife_z" if jackknife else None),
            # PSI is antisymmetric: one test, direction carried by the sign.
            "p_covers_both_directions": True,
            "p_is_omnibus": bool(len(per_band) > 1),
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


def _codes(cols: List[np.ndarray]) -> np.ndarray:
    """Row-wise integer codes for a list of equal-length integer vectors.

    Codes number the distinct rows in lexicographic order, first column most significant,
    which is the order ``np.unique(axis=0)`` gives. Each column is shifted to start at zero
    and the row becomes one mixed-radix integer, first column the most significant digit,
    so a 1-D ``np.unique`` of the keys yields the same codes without sorting rows. When
    the product of the radices would not fit in int64, the row-wise ``np.unique`` runs
    instead.
    """
    if len(cols) == 1:
        return np.asarray(np.unique(cols[0], return_inverse=True)[1]).ravel()
    arrays = [np.asarray(c).ravel() for c in cols]
    if all(np.issubdtype(a.dtype, np.integer) for a in arrays) and arrays[0].size > 0:
        radices = [int(a.max()) - int(a.min()) + 1 for a in arrays]
        span = 1
        for r in radices:
            span *= r
        if span < 2**62:
            key = np.zeros(arrays[0].size, dtype=np.int64)
            for a, r in zip(arrays, radices):
                key = key * r + (a - a.min()).astype(np.int64)
            return np.asarray(np.unique(key, return_inverse=True)[1]).ravel()
    stacked = np.column_stack(arrays)
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
    rng: RNGLike = Default(0),
    detrend: Optional[str] = None,
    time_axis: int = -1,
    *,
    seed: Any = Default(0),
) -> DirectedResult:
    """
    Transfer entropy — model-free, nonlinear directed information flow, in bits.

    ``TE(X -> Y) = I(Y_t ; X_past | Y_past)``: how much X's past reduces
    uncertainty about Y's present *beyond* what Y's own past already explains.

    TE is positively biased at finite sample size, so a raw TE > 0 means nothing
    on its own. This implementation therefore runs a surrogate test by default
    and reports both the raw value and ``bias_corrected`` (raw minus surrogate
    mean, the "effective transfer entropy"). With ``n_surrogates=0`` there is no
    null to subtract and the ``bias_corrected_*`` keys are absent.

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
            ``'symbolic'`` raises ``ValueError``. Its surrogate null is not calibrated
            under zero-lag mixing: two noisy copies of one white source, with no
            directed coupling, test significant in both directions. Use
            ``'quantile'`` until a calibrated null exists.
        bins: number of states for quantile/uniform
        symbolic_order: kept so that later positional arguments keep their places;
            it configures only the refused ``'symbolic'`` estimator and is unused
        bias_correction: ``'mm'`` (Miller-Madow) applied to each entropy term, or None
        n_surrogates: surrogate draws for the p-value and bias correction.
            Set to 0 only if you are calibrating the null some other way.
        rng: surrogate randomness: an ``int`` seed (default 0), a ``Generator`` used
            in place, or ``None`` for fresh OS entropy; a float is refused. Passing
            ``params['surrogate_seed_entropy']`` back as ``rng`` reproduces the
            p-values (``seed`` is the old spelling and still works)
        detrend: usually ``None``; TE is invariant to monotone rescaling under
            the quantile estimator, so z-scoring buys nothing

    Returns:
        DirectedResult with ``unit='bits'``. ``diagnostics['samples_per_joint_state']``
        below ~10 means the estimate is undersampled and a warning fires — reduce
        ``bins``, ``k``, or ``l`` rather than reporting it.

    References:
        Schreiber, T. (2000). Measuring information transfer. Phys. Rev. Lett.
        doi:10.1103/PhysRevLett.85.461 -- transfer entropy, eq. 4, with target history
        `k` and source history `l`; ``delay=1`` is the paper's alignment.
        Marschinski, R., & Kantz, H. (2002). Eur. Phys. J. B.
        doi:10.1140/epjb/e2002-00379-2 -- effective transfer entropy, the raw value minus
        the surrogate mean, reported as ``bias_corrected_*``. The surrogates here permute
        trials (7 or more) or circularly shift the source (fewer), which keeps its
        autocorrelation; ``params['surrogate_scheme']`` records which.
    """
    seed = resolve_seed_alias(rng, seed, alias_name='seed', func_name='transfer_entropy')
    surrogate_rng, seed_entropy = _surrogate_rng(seed, "transfer_entropy")
    if estimator == "symbolic":
        # INTENTIONAL BREAK (0.2.6.1). Ordinal patterns of order m span m samples, so a
        # target pattern and a source pattern one step earlier share samples. Zero-lag
        # mixing therefore reads as information flow, while the surrogates -- which shift
        # or re-pair the source -- destroy that overlap, and the null sits below it. On two
        # noisy copies of one white source (20 replicates, 49 surrogates) it rejected at
        # 0.05 in both directions 19 times; the quantile estimator rejected 1 and 3 times.
        raise ValueError(
            "transfer_entropy: estimator='symbolic' is refused. Its surrogate null is not "
            "calibrated under zero-lag mixing, so a common source with no directed "
            "coupling tests significant in both directions. Use estimator='quantile'."
        )
    if estimator not in ("quantile", "uniform", "discrete"):
        raise ValueError(f"estimator must be quantile|uniform|discrete; got {estimator!r}")
    if min(k, l) < 1 or delay < 1:
        raise ValueError(f"k, l, delay must all be >= 1; got k={k}, l={l}, delay={delay}")

    x, y = _pair_trials(X, Y, time_axis=time_axis)
    # The embedding consumes max(k, delay * l) leading samples per trial.
    _history = max(int(k), int(delay) * int(l))
    require_trial_length(
        x, _history, "transfer_entropy", history_name="k/l/delay", time_axis=time_axis
    )
    x = _detrend_trials(x, detrend)
    y = _detrend_trials(y, detrend)
    n_trials, n_times = x.shape

    xq = _discretize(x, bins, estimator)
    yq = _discretize(y, bins, estimator)

    te_xy, n_used, n_joint_xy = _te_one_direction(xq, yq, k, l, delay, bias_correction)
    te_yx, _, n_joint_yx = _te_one_direction(yq, xq, k, l, delay, bias_correction)

    p_xy = p_yx = p_net = None
    eff_xy, eff_yx = te_xy, te_yx
    surrogate_info: Dict[str, Any] = {"n_surrogates": int(n_surrogates)}

    if n_surrogates > 0:
        null_xy = np.empty(int(n_surrogates))
        null_yx = np.empty(int(n_surrogates))
        for i in range(int(n_surrogates)):
            null_xy[i] = _te_one_direction(
                _surrogate_source(xq, surrogate_rng).astype(np.int64),
                yq, k, l, delay, bias_correction,
            )[0]
            null_yx[i] = _te_one_direction(
                _surrogate_source(yq, surrogate_rng).astype(np.int64),
                xq, k, l, delay, bias_correction,
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
    n_states_x = int(np.unique(xq).size)
    n_states_y = int(np.unique(yq).size)
    warnings_all: List[str] = []
    if samples_per_state < 10:
        warnings_all.append(
            f"undersampled_te_{samples_per_state:.1f}_samples_per_joint_state"
        )
    # The opposite failure to undersampling, and it was invisible: a discretization that
    # collapses reports FEWER joint states, so samples_per_joint_state goes UP and the
    # undersampling check stays quiet. Quantile edges on a sparse series are the common
    # case -- spike counts averaging 0.05 or 0.1 per bin are almost all zero, so every
    # quantile edge lands on 0 and the whole series maps to one symbol. TE is then
    # identically 0 by construction. Measured with X driving Y at lag 1: TE = 0.0000 bits,
    # p = 1.0, ok_for_interpretation = True and no warning at all.
    if min(n_states_x, n_states_y) < 2:
        warnings_all.append(
            f"degenerate_discretization_{min(n_states_x, n_states_y)}_state_te_is_identically_zero"
        )
    elif estimator in ("quantile", "uniform") and min(n_states_x, n_states_y) < bins:
        warnings_all.append(
            f"discretization_collapsed_to_{min(n_states_x, n_states_y)}_of_{bins}_requested_bins"
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
            "bias_correction": bias_correction,
            "n_surrogates": int(n_surrogates),
            "detrend": detrend,
            "seed": None if isinstance(seed, np.random.Generator) else seed,
            "surrogate_seed_entropy": seed_entropy if n_surrogates > 0 else None,
            "surrogate_scheme": _surrogate_scheme(n_trials) if n_surrogates > 0 else None,
        },
        diagnostics={
            "n_embedding_samples": int(n_used),
            "n_realized_states_x": n_states_x,
            "n_realized_states_y": n_states_y,
            "n_joint_states_x_to_y": int(n_joint_xy),
            "n_joint_states_y_to_x": int(n_joint_yx),
            "samples_per_joint_state": float(samples_per_state),
            # Only present when surrogates ran. Without them there is no null
            # mean to subtract, and eff_* still holds the raw estimate -- a
            # value under this name would claim a correction that never
            # happened. Granger reports the pair the same way.
            **(
                {"bias_corrected_x_to_y": eff_xy, "bias_corrected_y_to_x": eff_yx}
                if n_surrogates > 0
                else {}
            ),
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
    n_jobs: int = 1,
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
        n_jobs: CPU workers for the pairs. Default 1 (serial); -1 uses every core.
            Each estimator seeds its surrogates from its own ``rng`` argument, so
            the result is identical for any n_jobs. A ``Generator`` passed as ``rng``
            is drawn once per pair before any worker starts.
        **kwargs: forwarded to the estimator

    Returns:
        dict with ``matrix`` (``M[i, j]`` = influence of node i on node j;
        diagonal NaN), ``p_matrix``, ``q_matrix`` (NaN when ``fdr=False`` or no
        p-values), ``labels``, ``results`` (the full DirectedResult per ordered
        pair), ``method``, and ``warnings``.

    References:
        Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate. J. R.
        Stat. Soc. B. doi:10.1111/j.2517-6161.1995.tb02031.x -- the step-up procedure
        behind ``q_matrix`` (``fdr_method='bh'``).
        Benjamini, Y., & Yekutieli, D. (2001). The control of the false discovery rate in
        multiple testing under dependency. Ann. Stat. doi:10.1214/aos/1013699998
        -- ``fdr_method='by'``, valid under arbitrary dependence.
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

    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    # A Generator shared across workers would be copied into each one and replayed, so the
    # surrogates would depend on n_jobs. Draw one int seed per pair up front instead; each
    # pair then records its seed as `surrogate_seed_entropy`.
    pair_kwargs = [kwargs] * len(pairs)
    if "rng" in kwargs and "seed" in kwargs:
        # Both spellings of one argument: refuse a contradiction here, before the per-pair
        # seeds below would replace both with one value and hide it.
        resolve_seed_alias(kwargs["rng"], kwargs["seed"], alias_name="seed",
                           func_name="directed_network")
    gen_keys = [k for k in ("rng", "seed") if isinstance(kwargs.get(k), np.random.Generator)]
    if gen_keys:
        pair_seeds = kwargs[gen_keys[0]].integers(0, 2**63 - 1, size=len(pairs))
        pair_kwargs = [{**kwargs, **{k: int(s) for k in gen_keys}} for s in pair_seeds]
    pair_results = parallel_map(
        lambda job: directed_connectivity(
            series[job[0][0]], series[job[0][1]], method=method, **job[1]
        ),
        list(zip(pairs, pair_kwargs)),
        n_jobs=n_jobs,
    )
    for (i, j), res in zip(pairs, pair_results):
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
    # The family is the set of off-diagonal p-values that actually reached
    # false_discovery_control, not every off-diagonal cell: an estimator that
    # returns no p-value (TE without surrogates) or a pair that failed leaves
    # NaN, and those cells are never corrected.
    fdr_family_size = 0
    if fdr:
        off = ~np.eye(n, dtype=bool)
        finite = off & np.isfinite(p_matrix)
        fdr_family_size = int(finite.sum())
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
        "fdr_family_size": fdr_family_size,
        "results": results,
        "params": kwargs,
        "warnings": warnings_all,
    }
