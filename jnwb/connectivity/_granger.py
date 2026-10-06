"""Granger causality: VAR fits, lag selection, residual diagnostics, and the time- and frequency-domain estimators."""

from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from .._backend import CPU, CUDA, resolve_device, warn_device_fallback, warn_no_gpu_path
from .._spread import is_constant, zscore
from .._layout import require_trial_length
from .._rng import Default, RNGLike, resolve_seed_alias
from scipy import stats
from ..spectral import CANONICAL_BANDS
from ._common import DirectedResult, _fixed_order, _surrogate_p, _surrogate_rng, _surrogate_scheme, _surrogate_source
from ._trials import _detrend_trials, _pair_trials, as_trials

log = logging.getLogger(__package__)


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

    Every candidate order is scored on one sample, the ``n - max_order`` targets left after
    trimming ``max_order`` presample values, where ``max_order`` is ``max_lag`` capped at
    ``(n - 2) // 3``. The criteria then differ only through the model, as in
    :func:`granger` (Lütkepohl 2005, section 4.3). Each order used to be scored on its own
    ``n - p`` targets, so a higher order was compared on fewer samples.

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

    # Dropping the first `actual_max - p` samples leaves the targets x[actual_max:] for every p.
    n_samples = n - actual_max
    for p in range(1, actual_max + 1):
        _, var_unrestricted = fit_var_bivariate(
            x[actual_max - p:], y[actual_max - p:], p, device=resolved, ridge=ridge,
            context=context, ran_on=ran_on)
        n_params = 2 * p + 1
        ic = _info_criterion(n_samples, var_unrestricted, n_params, criterion)
        if ic < best_ic:
            best_ic = ic
            opt_lag = p

    return opt_lag


#: What `_adf_pvalue` reads as "the test could not run on this series" and turns into NaN:
#: a singular or non-converging least-squares fit, and the `ValueError` statsmodels raises
#: for a series too short or too flat for the regression, and the `FloatingPointError` the fit
#: raises (underflow or overflow) under a caller's ``np.errstate(all="raise")`` on a tiny, huge
#: or exponential series. Anything else propagates.
#: `LinAlgError` subclasses `ValueError`; it is named so the reader need not know that.
_ADF_NUMERICAL_FAILURES = (np.linalg.LinAlgError, ValueError, FloatingPointError)


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
    wrong approximation. A missing `statsmodels` raises `ImportError`; NaN means only that
    the test could not run on this series (:data:`_ADF_NUMERICAL_FAILURES`).
    """
    from statsmodels.tsa.stattools import adfuller

    y = np.asarray(series, dtype=float).ravel()
    if len(y) < 10:
        return float("nan")
    if not np.all(np.isfinite(y)) or np.ptp(y) == 0:
        return float("nan")
    try:
        with warnings.catch_warnings():
            # statsmodels warns that adfuller's plain-tuple return will become an
            # ADFullerResult in 0.16. Read the p-value in a way that works either way
            # rather than emitting a FutureWarning from every Granger diagnostic.
            warnings.simplefilter("ignore", FutureWarning)
            res = adfuller(y, maxlag=0, regression="c", autolag=None)
    except _ADF_NUMERICAL_FAILURES:
        return float("nan")
    return float(res[1]) if isinstance(res, tuple) else float(res.pvalue)


def _ljung_box_pvalue(residuals: np.ndarray, nlags: int = 10) -> float:
    """Ljung–Box portmanteau test p-value on residual autocorrelations."""
    r = np.asarray(residuals, dtype=float).ravel()
    n = len(r)
    # Constant residuals have no autocorrelation to test; centred, they were rounding residue
    # whose "autocorrelation" was 1 at every lag, and p read 0.0.
    if n < nlags + 2 or is_constant(r):
        return float("nan")
    r = r - np.mean(r)
    denom = _sum_of_products(r, r)
    if denom <= 0:
        return float("nan")
    q = 0.0
    for k in range(1, nlags + 1):
        rk = _sum_of_products(r[k:], r[:-k]) / denom
        q += (rk**2) / (n - k)
    q *= n * (n + 2)
    return float(stats.chi2.sf(q, df=nlags))


def _series_diagnostics(series: np.ndarray, residuals: np.ndarray, order: int) -> Dict:
    adf_p = _adf_pvalue(series)
    lb_p = _ljung_box_pvalue(residuals, nlags=min(10, max(order * 2, 2)))
    warnings = []
    # Not tested is not passed. `bool(np.isnan(adf_p) or ...)` reported stationarity_ok
    # True whenever the test could not run: two pure random walks came back
    # ok_for_interpretation=True with an empty warnings list. A missing `statsmodels` now
    # raises in `_adf_pvalue`, so NaN here is a series the test could not run on.
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
    return _sum_of_products(resid, resid), resid


def _sum_of_products(a: np.ndarray, b: np.ndarray) -> float:
    """``sum(a * b)`` in an order fixed by the length alone.

    ``np.dot`` on two vectors calls the BLAS dot product, which above about ten thousand
    elements splits the sum across threads; its rounding then depends on the BLAS thread
    count, and a worker process runs a different count from the parent. NumPy's pairwise
    ``sum`` does not thread.
    """
    return float(np.sum(np.multiply(a, b)))


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
        rng: surrogate randomness: an ``int`` seed (default 0), a ``Generator``, from
            which one child seed is drawn and used, or ``None`` for fresh OS entropy; a
            float is refused. Passing ``params['surrogate_seed_entropy']`` back as ``rng``
            reproduces the p-values (``seed`` is the old spelling and still works)

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
        # GC is log(var_r / var_f): its rounding is that of the ratio, not of GC's own size.
        p_xy = _surrogate_p(null_xy, fit_xy["gc"], "greater", scale=1.0)
        p_yx = _surrogate_p(null_yx, fit_yx["gc"], "greater", scale=1.0)
        null_net = null_xy - null_yx
        p_net = _surrogate_p(null_net, obs_net, "two-sided",
                             scale=max(1.0, abs(fit_xy["gc"])) + max(1.0, abs(fit_yx["gc"])))
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
        # Each frequency's GC is a log ratio, rounded at the scale of the ratio (see granger).
        p_xy = _surrogate_p(null_xy, total_xy, "greater", scale=1.0)
        p_yx = _surrogate_p(null_yx, total_yx, "greater", scale=1.0)
        for name, vals in per_band.items():
            f_lo, f_hi = vals["band_hz"]
            mask = (freqs >= f_lo) & (freqs <= f_hi)
            if mask.sum() >= 2:
                obs_xy = vals["value"]
                nb_xy = np.asarray(null_xy_by_band[name], dtype=float)
                vals["p_surrogate"] = _surrogate_p(nb_xy, obs_xy, "greater", scale=1.0)

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
