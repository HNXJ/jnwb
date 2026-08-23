"""
jnwb.jrsa – Unified Representational Similarity Analysis

Public API: exactly one function.

    >>> import jnwb as oa
    >>> result = oa.jrsa(x1, x2, metric="rsa", stats=True)
    >>> result.summary()
    >>> result.plot()

Author: Claude Code
Version: 1.0.0
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

@dataclass
class JRSAResult:
    """Container returned by jrsa().

    Attributes
    ----------
    value : np.ndarray
        Primary similarity tensor.
    statistic : np.ndarray | None
        Test statistic (r, rho, F, t, Z, GC …).
    effect : np.ndarray | None
        Effect size.
    p : np.ndarray | None
        Raw p-values.
    q : np.ndarray | None
        Corrected p-values (after multiple-comparison correction).
    df : np.ndarray | None
        Degrees of freedom.
    ci : np.ndarray | None
        Confidence intervals, shape (…, 2).
    metric : str
        Metric name.
    axes : tuple
        Compared dimensions.
    aligned_axes : tuple
        Dimensions that were aligned.
    labels : list | None
        Semantic axis labels.
    parameters : dict
        Full parameter snapshot.
    null_distribution : np.ndarray | None
        Permutation null distribution (if return_null=True).
    aligned_x1 : np.ndarray | None
        Internally aligned x1 (if return_input=True).
    aligned_x2 : np.ndarray | None
        Internally aligned x2 (if return_input=True).
    execution : dict
        Runtime metadata (backend, device, runtime, memory, seed).
    """

    value: np.ndarray
    statistic: Optional[np.ndarray] = None
    effect: Optional[np.ndarray] = None
    p: Optional[np.ndarray] = None
    q: Optional[np.ndarray] = None
    df: Optional[np.ndarray] = None
    ci: Optional[np.ndarray] = None
    metric: str = "rsa"
    axes: tuple = ()
    aligned_axes: tuple = ()
    labels: Optional[List[str]] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    null_distribution: Optional[np.ndarray] = None
    aligned_x1: Optional[np.ndarray] = None
    aligned_x2: Optional[np.ndarray] = None
    execution: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # User-facing convenience methods
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Print and return a formatted summary table."""
        lines = _result_summary(self)
        print(lines)
        return lines

    def plot(self, **kwargs):
        """Automatic plot of the result matrix / time-course."""
        return _result_plot(self, **kwargs)

    def save(self, path: str, fmt: str = "npz"):
        """Save result to *path* (npz, json, or csv)."""
        return _result_save(self, path, fmt)

    def __repr__(self) -> str:  # pragma: no cover
        shape = getattr(self.value, "shape", None)
        p_repr = ""
        if self.p is not None and self.p.size > 0:
            try:
                p_repr = f", p={float(np.nanmin(self.p)):.4g}"
            except Exception:
                pass
        return f"JRSAResult(metric='{self.metric}', value.shape={shape}{p_repr})"


# ===========================================================================
# PUBLIC ENTRY POINT
# ===========================================================================

def jrsa(
    x1,
    x2=None,
    # tensor semantics
    adim=-1,
    labels=None,
    align="auto",
    align_mode="fraction",
    reduction=None,
    # analysis
    metric="rsa",
    lag=0,
    window=None,
    sliding=False,
    # preprocessing
    normalize=False,
    standardize=False,
    detrend=False,
    nan_policy="omit",
    # statistics
    stats=True,
    permutations=1000,
    bootstrap=0,
    correction="fdr_bh",
    alpha=0.05,
    alternative="two-sided",
    # execution
    backend="auto",
    device="auto",
    n_jobs=-1,
    batch_size=None,
    random_state=None,
    # output
    return_type="result",
    return_null=False,
    return_input=False,
    verbose=False,
    **kwargs,
) -> JRSAResult:
    """Unified representational similarity / cross-area analysis.

    Parameters
    ----------
    x1 : array-like
        First tensor (ndarray, cupy, torch, jax, or JNWB Signal).
    x2 : array-like or None
        Second tensor.  None → within-x1 analysis.
    adim : int | tuple | str | tuple[str]
        Aligned dimension(s). Default -1.
    labels : list[str] or None
        Semantic axis names, e.g. ["area", "channel", "trial", "time"].
    align : str
        Alignment algorithm: auto | none | downsample | upsample |
        interpolate | nearest | linear | cubic | dtw.
    align_mode : str
        Correspondence rule: fraction | sample | timestamp | index.
    reduction : dict or None
        Dimension reductions, e.g. {"trial": "mean"}.
    metric : str
        Similarity metric.  One of: pearson, spearman, kendall, cosine,
        rsa, cka, rv, hsic, distance_correlation, mutual_information,
        procrustes, granger, transfer_entropy, phase_slope.
    lag : int | tuple | array-like
        Temporal lag(s).
    window : tuple | int or None
        Analysis window, e.g. (-500, 500) ms.
    sliding : bool
        Use sliding window.
    normalize : bool
        Normalise each input to [0, 1].
    standardize : bool
        Z-score each input.
    detrend : bool
        Linear-detrend each input.
    nan_policy : str
        omit | raise | propagate.
    stats : bool
        Compute inferential statistics.
    permutations : int
        Permutation count for null distribution.
    bootstrap : int
        Bootstrap iterations for confidence intervals.
    correction : str
        Multiple-comparison correction: none | bonferroni | holm |
        holm-sidak | fdr_bh | fdr_by | cluster | maxT.
    alpha : float
        Significance threshold.
    alternative : str
        two-sided | greater | less.
    backend : str
        auto | numpy | scipy | jax | torch | cupy.
    device : str
        auto | cpu | cuda | tpu.
    n_jobs : int
        CPU workers (-1 = all cores).
    batch_size : int or None
        Chunk size for large arrays.
    random_state : int or None
        Random seed for reproducibility.
    return_type : str
        result | dict | matrix | value.
    return_null : bool
        Attach null distributions to result.
    return_input : bool
        Attach aligned inputs to result (useful for debugging).
    verbose : bool
        Print progress.
    **kwargs
        Metric-specific keyword arguments.

    Returns
    -------
    JRSAResult
        Rich result object with .summary(), .plot(), .save().
    """
    t0 = time.perf_counter()

    # --- collect parameter snapshot -------------------------------------------
    params = dict(
        adim=adim, labels=labels, align=align, align_mode=align_mode,
        reduction=reduction, metric=metric, lag=lag, window=window,
        sliding=sliding, normalize=normalize, standardize=standardize,
        detrend=detrend, nan_policy=nan_policy, stats=stats,
        permutations=permutations, bootstrap=bootstrap, correction=correction,
        alpha=alpha, alternative=alternative, backend=backend, device=device,
        n_jobs=n_jobs, batch_size=batch_size, random_state=random_state,
        return_type=return_type, return_null=return_null,
        return_input=return_input, verbose=verbose, **kwargs,
    )

    # --- pipeline -------------------------------------------------------------
    rng = np.random.default_rng(random_state)
    bk = _get_backend(backend, device)

    x1, x2 = _prepare_inputs(x1, x2, bk)
    x1, x2 = _validate_inputs(x1, x2, nan_policy)
    x1, x2, axis_map = _standardize_dimensions(x1, x2, adim, labels)
    x1, x2, aligned_axes = _align_dimensions(
        x1, x2, axis_map, align, align_mode, verbose
    )
    if reduction is not None:
        x1, x2 = _reduce_dimensions(x1, x2, axis_map, reduction)
    x1, x2 = _apply_preprocessing(x1, x2, normalize, standardize, detrend)
    x1, x2, windows = _make_windows(x1, x2, axis_map, window, sliding)
    # --- dispatch metric ------------------------------------------------------
    metric_fn = _METRIC_DISPATCH.get(metric.lower())
    if metric_fn is None:
        raise ValueError(
            f"Unknown metric '{metric}'. "
            f"Choose from: {sorted(_METRIC_DISPATCH)}"
        )

    if verbose:
        print(f"[jrsa] computing {metric!r} …")

    # --- temporal lag iteration -----------------------------------------------
    lags = [lag] if isinstance(lag, (int, float)) else list(lag)
    
    if len(lags) <= 1:
        x1_lagged, x2_lagged = _apply_lag(x1, x2, axis_map, lag)
        value, statistic, effect, p_raw, df = metric_fn(
            x1_lagged, x2_lagged, axis=-1, **kwargs
        )
        null_dist = None
        ci = None

        if stats and permutations > 0:
            null_dist = _permutation_test(
                x1_lagged, x2_lagged, metric_fn, permutations, rng, axis=-1, n_jobs=n_jobs, **kwargs
            )
            if p_raw is None:
                p_raw = _p_from_null(value, null_dist, alternative)

        if bootstrap > 0:
            ci = _bootstrap(x1_lagged, x2_lagged, metric_fn, bootstrap, rng, axis=-1, n_jobs=n_jobs, **kwargs)

        q_corrected = None
        if stats and p_raw is not None and correction.lower() != "none":
            q_corrected = _multiple_correction(p_raw, correction, alpha)
    else:
        # Loop over each individual lag and stack the results
        val_list, stat_list, eff_list, p_list, df_list = [], [], [], [], []
        null_dist_list, ci_list = [], []
        
        for l in lags:
            x1_lagged, x2_lagged = _apply_lag(x1, x2, axis_map, l)
            v, s, e, p, d = metric_fn(x1_lagged, x2_lagged, axis=-1, **kwargs)
            val_list.append(v)
            stat_list.append(s)
            eff_list.append(e)
            p_list.append(p)
            df_list.append(d)
            
            nd = None
            c_val = None
            if stats and permutations > 0:
                nd = _permutation_test(
                    x1_lagged, x2_lagged, metric_fn, permutations, rng, axis=-1, n_jobs=n_jobs, **kwargs
                )
                if p is None:
                    p = _p_from_null(v, nd, alternative)
                    p_list[-1] = p
                null_dist_list.append(nd)
                
            if bootstrap > 0:
                c_val = _bootstrap(x1_lagged, x2_lagged, metric_fn, bootstrap, rng, axis=-1, n_jobs=n_jobs, **kwargs)
                ci_list.append(c_val)
        
        xp = _get_xp(x1)
        # Helper to stack along axis=0 if components are arrays/tensors or numeric values
        def _stack_lags(lst):
            if all(item is None for item in lst):
                return None
            # If items are numeric scalars or arrays, stack them
            first = next(item for item in lst if item is not None)
            if isinstance(first, (int, float, np.number)) or (hasattr(first, "ndim") and first.ndim == 0):
                return xp.array([float(item) if item is not None else np.nan for item in lst])
            # Filter None to prevent stack crash, although they should all be same shape
            return xp.stack([item if item is not None else xp.full_like(first, xp.nan) for item in lst], axis=0)
            
        value = _stack_lags(val_list)
        statistic = _stack_lags(stat_list)
        effect = _stack_lags(eff_list)
        p_raw = _stack_lags(p_list)
        df = _stack_lags(df_list)
        null_dist = _stack_lags(null_dist_list) if null_dist_list else None
        ci = _stack_lags(ci_list) if ci_list else None
        
        q_corrected = None
        if stats and p_raw is not None and correction.lower() != "none":
            q_corrected = _multiple_correction(p_raw, correction, alpha)

    # --- build result ---------------------------------------------------------
    exec_meta = _make_exec_meta(bk, device, t0, rng)

    result = _make_result(
        value=value,
        statistic=statistic,
        effect=effect,
        p=p_raw,
        q=q_corrected,
        df=df,
        ci=ci,
        metric=metric,
        axes=tuple(axis_map.values()),
        aligned_axes=aligned_axes,
        labels=labels,
        parameters=params,
        null_distribution=null_dist if return_null else None,
        aligned_x1=x1 if return_input else None,
        aligned_x2=x2 if return_input else None,
        execution=exec_meta,
    )

    # --- return_type conversion -----------------------------------------------
    if return_type == "result":
        return result
    elif return_type == "dict":
        return result.__dict__
    elif return_type == "matrix":
        return result.value
    elif return_type == "value":
        v = result.value
        return float(v) if v.size == 1 else v
    else:
        raise ValueError(f"Unknown return_type '{return_type}'")


# ===========================================================================
# PRIVATE – tensor handling
# ===========================================================================

def _get_xp(arr):
    """Resolve numpy or cupy namespace depending on array type."""
    try:
        import cupy as cp
        if isinstance(arr, cp.ndarray):
            return cp
    except ImportError:
        pass
    return np


def _prepare_inputs(x1, x2, backend_ctx: dict):
    """Convert inputs to numpy (or chosen backend array) and handle JNWB Signals."""
    x1 = _to_backend(x1, backend_ctx)
    if x2 is not None:
        x2 = _to_backend(x2, backend_ctx)
    else:
        x2 = None  # within-array mode
    return x1, x2


def _validate_inputs(x1, x2, nan_policy: str):
    """Shape checks and NaN handling on both CPU and GPU namespaces."""
    xp1 = _get_xp(x1)
    if x1.ndim < 1:
        raise ValueError("x1 must have at least 1 dimension.")
    if nan_policy == "raise" and xp1.any(xp1.isnan(x1)):
        raise ValueError("NaN values found in x1 (nan_policy='raise').")
    if x2 is not None:
        xp2 = _get_xp(x2)
        if nan_policy == "raise" and xp2.any(xp2.isnan(x2)):
            raise ValueError("NaN values found in x2 (nan_policy='raise').")
    if nan_policy == "omit":
        if x2 is not None:
            xp2 = _get_xp(x2)
            # Find joint valid mask (neither is NaN) along the last axis
            # For multi-dimensional inputs, we assume the last axis contains the paired samples.
            # We want to keep samples where both x1 and x2 are not NaN.
            nan_mask = xp1.isnan(x1) | xp2.isnan(x2)
            # Find indices along the last axis where all dimensions are valid (no NaN in any feature/dimension)
            # In general, if there are multiple dimensions, we project the mask down to the last axis.
            if x1.ndim > 1:
                # Collapse over non-last axes to find any NaN position
                reduce_axes = tuple(range(x1.ndim - 1))
                any_nan = nan_mask.any(axis=reduce_axes)
            else:
                any_nan = nan_mask
            
            valid_indices = xp1.where(~any_nan)[0]
            x1 = xp1.take(x1, valid_indices, axis=-1)
            x2 = xp2.take(x2, valid_indices, axis=-1)
        else:
            nan_mask = xp1.isnan(x1)
            if x1.ndim > 1:
                reduce_axes = tuple(range(x1.ndim - 1))
                any_nan = nan_mask.any(axis=reduce_axes)
            else:
                any_nan = nan_mask
            valid_indices = xp1.where(~any_nan)[0]
            x1 = xp1.take(x1, valid_indices, axis=-1)
    # propagate: do nothing, let downstream handle
    return x1, x2


def _standardize_dimensions(x1, x2, adim, labels):
    """Normalise adim to a dict {name: axis_index}."""
    axis_map = {}
    if isinstance(adim, int):
        axis_map["aligned"] = adim % x1.ndim
    elif isinstance(adim, (tuple, list)):
        for i, d in enumerate(adim):
            if isinstance(d, str):
                if labels is None:
                    raise ValueError("labels required when adim contains strings.")
                axis_map[d] = labels.index(d)
            else:
                key = labels[d] if labels and d < len(labels) else f"axis_{d}"
                axis_map[key] = d % x1.ndim
    elif isinstance(adim, str):
        if labels is None:
            raise ValueError("labels required when adim is a string.")
        axis_map[adim] = labels.index(adim)
    else:
        axis_map["aligned"] = -1 % x1.ndim
    return x1, x2, axis_map


def _align_dimensions(x1, x2, axis_map, align, align_mode, verbose):
    """Align x1 and x2 along each axis in axis_map."""
    aligned_axes = ()
    if x2 is None:
        return x1, x2, aligned_axes
    if align == "none":
        return x1, x2, aligned_axes

    aligned_axes_list = []
    for name, ax in axis_map.items():
        n1, n2 = x1.shape[ax], x2.shape[ax]
        if n1 == n2:
            continue
        x1, x2 = _resample_axis(x1, x2, ax, n1, n2, align, align_mode)
        aligned_axes_list.append(ax)
        if verbose:
            print(f"[jrsa] aligned axis {ax} ({name}): {n1} → {n2 if n2 < n1 else n1}")
    return x1, x2, tuple(aligned_axes_list)


def _resample_axis(x1, x2, axis, n1, n2, align, align_mode):
    """Resample one array along *axis* to match the other, respecting GPU/CPU."""
    xp1 = _get_xp(x1)
    xp2 = _get_xp(x2)
    target = min(n1, n2)
    if align in ("auto", "downsample"):
        if n1 > target:
            idx = xp1.linspace(0, n1 - 1, target, dtype=int)
            x1 = xp1.take(x1, idx, axis=axis)
        if n2 > target:
            idx = xp2.linspace(0, n2 - 1, target, dtype=int)
            x2 = xp2.take(x2, idx, axis=axis)
    elif align == "upsample":
        target = max(n1, n2)
        if n1 < target:
            idx = xp1.round(xp1.linspace(0, n1 - 1, target)).astype(int)
            x1 = xp1.take(x1, idx, axis=axis)
        if n2 < target:
            idx = xp2.round(xp2.linspace(0, n2 - 1, target)).astype(int)
            x2 = xp2.take(x2, idx, axis=axis)
    elif align in ("interpolate", "linear"):
        try:
            from scipy.interpolate import interp1d
            def _interp(arr, n_src, n_tgt, ax):
                xp = _get_xp(arr)
                is_gpu = (xp.__name__ == "cupy")
                arr_cpu = arr.get() if is_gpu else arr
                xold = np.linspace(0, 1, n_src)
                xnew = np.linspace(0, 1, n_tgt)
                f = interp1d(xold, arr_cpu, axis=ax, kind="linear", fill_value="extrapolate")
                res = f(xnew)
                return xp.asarray(res) if is_gpu else res
            if n1 != target:
                x1 = _interp(x1, n1, target, axis)
            if n2 != target:
                x2 = _interp(x2, n2, target, axis)
        except ImportError:
            x1, x2 = _resample_axis(x1, x2, axis, n1, n2, "downsample", align_mode)
    elif align == "nearest":
        if n1 > target:
            idx = xp1.round(xp1.linspace(0, n1 - 1, target)).astype(int)
            x1 = xp1.take(x1, idx, axis=axis)
        if n2 > target:
            idx = xp2.round(xp2.linspace(0, n2 - 1, target)).astype(int)
            x2 = xp2.take(x2, idx, axis=axis)
    elif align == "cubic":
        try:
            from scipy.interpolate import interp1d
            def _interp_cubic(arr, n_src, n_tgt, ax):
                xp = _get_xp(arr)
                is_gpu = (xp.__name__ == "cupy")
                arr_cpu = arr.get() if is_gpu else arr
                xold = np.linspace(0, 1, n_src)
                xnew = np.linspace(0, 1, n_tgt)
                f = interp1d(xold, arr_cpu, axis=ax, kind="cubic", fill_value="extrapolate")
                res = f(xnew)
                return xp.asarray(res) if is_gpu else res
            if n1 != target:
                x1 = _interp_cubic(x1, n1, target, axis)
            if n2 != target:
                x2 = _interp_cubic(x2, n2, target, axis)
        except ImportError:
            x1, x2 = _resample_axis(x1, x2, axis, n1, n2, "downsample", align_mode)
    elif align == "dtw":
        # Fallback to downsample; full DTW requires optional dep
        warnings.warn("DTW alignment requires the 'dtw-python' package; falling back to downsample.")
        x1, x2 = _resample_axis(x1, x2, axis, n1, n2, "downsample", align_mode)
    return x1, x2


def _reduce_dimensions(x1, x2, axis_map, reduction: dict):
    """Apply reductions (mean, median, …) along named axes on CPU or GPU."""
    for name, op_str in reduction.items():
        ax = axis_map.get(name)
        if ax is None:
            continue

        xp1 = _get_xp(x1)
        if op_str == "mean":
            x1 = xp1.mean(x1, axis=ax, keepdims=True)
        elif op_str == "median":
            if xp1.__name__ == "cupy":
                try:
                    x1 = xp1.median(x1, axis=ax, keepdims=True)
                except AttributeError:
                    x1 = xp1.percentile(x1, 50, axis=ax, keepdims=True)
            else:
                x1 = np.median(x1, axis=ax, keepdims=True)
        elif op_str == "sum":
            x1 = xp1.sum(x1, axis=ax, keepdims=True)
        elif op_str == "max":
            x1 = xp1.max(x1, axis=ax, keepdims=True)
        elif op_str == "min":
            x1 = xp1.min(x1, axis=ax, keepdims=True)
        else:
            x1 = xp1.mean(x1, axis=ax, keepdims=True)

        if x2 is not None:
            xp2 = _get_xp(x2)
            if op_str == "mean":
                x2 = xp2.mean(x2, axis=ax, keepdims=True)
            elif op_str == "median":
                if xp2.__name__ == "cupy":
                    try:
                        x2 = xp2.median(x2, axis=ax, keepdims=True)
                    except AttributeError:
                        x2 = xp2.percentile(x2, 50, axis=ax, keepdims=True)
                else:
                    x2 = np.median(x2, axis=ax, keepdims=True)
            elif op_str == "sum":
                x2 = xp2.sum(x2, axis=ax, keepdims=True)
            elif op_str == "max":
                x2 = xp2.max(x2, axis=ax, keepdims=True)
            elif op_str == "min":
                x2 = xp2.min(x2, axis=ax, keepdims=True)
            else:
                x2 = xp2.mean(x2, axis=ax, keepdims=True)
    return x1, x2


def _apply_preprocessing(x1, x2, normalize, standardize, detrend):
    """Apply per-array preprocessing in place on CPU or GPU."""
    if normalize and standardize:
        warnings.warn(
            "Both normalize=True and standardize=True are enabled simultaneously. "
            "Standardize (Z-scoring) overrides and negates standard range normalization [0, 1].",
            UserWarning
        )
    def _prep(arr):
        if arr is None:
            return arr
        xp = _get_xp(arr)
        is_gpu = (xp.__name__ == "cupy")
        if detrend:
            if is_gpu:
                arr_cpu = arr.get()
                try:
                    from scipy.signal import detrend as sp_detrend
                    arr_cpu = sp_detrend(arr_cpu, axis=-1)
                except ImportError:
                    arr_cpu = arr_cpu - np.polyval(np.polyfit(np.arange(arr_cpu.shape[-1]), arr_cpu.T, 1), np.arange(arr_cpu.shape[-1]))
                arr = xp.asarray(arr_cpu)
            else:
                try:
                    from scipy.signal import detrend as sp_detrend
                    arr = sp_detrend(arr, axis=-1)
                except ImportError:
                    arr = arr - np.polyval(np.polyfit(np.arange(arr.shape[-1]), arr.T, 1), np.arange(arr.shape[-1]))
        if standardize:
            mu = xp.nanmean(arr, axis=-1, keepdims=True)
            sd = xp.nanstd(arr, axis=-1, keepdims=True)
            arr = (arr - mu) / (sd + 1e-12)
        if normalize:
            lo = xp.nanmin(arr, axis=-1, keepdims=True)
            hi = xp.nanmax(arr, axis=-1, keepdims=True)
            arr = (arr - lo) / (hi - lo + 1e-12)
        return arr
    return _prep(x1), _prep(x2)


def _make_windows(x1, x2, axis_map, window, sliding):
    """Extract window or build sliding windows."""
    if window is None:
        return x1, x2, None
    ax = axis_map.get("aligned", axis_map.get(list(axis_map.keys())[0], -1))
    n = x1.shape[ax]
    if isinstance(window, (int, float)):
        half = int(window) // 2
        center = n // 2
        start, stop = max(0, center - half), min(n, center + half)
    else:
        start, stop = int(window[0]), int(window[1])
        if start < 0:
            start = max(0, n + start)
        if stop < 0:
            stop = max(0, n + stop)
        stop = min(stop, n)
    slices = [slice(None)] * x1.ndim
    slices[ax] = slice(start, stop)
    x1 = x1[tuple(slices)]
    if x2 is not None:
        x2 = x2[tuple(slices)]
    return x1, x2, (start, stop)


def _apply_lag(x1, x2, axis_map, lag):
    """Apply temporal lag(s) by rolling along the last axis on CPU or GPU.
    If multiple lags are passed, returns stacked arrays of shape (n_lags, ...).
    """
    if lag == 0 or (hasattr(lag, "__len__") and len(lag) == 1 and lag[0] == 0):
        return x1, x2
    if x2 is None:
        return x1, x2
    lags = [lag] if isinstance(lag, (int, float)) else list(lag)
    xp = _get_xp(x2)
    
    if len(lags) == 1:
        shift = int(lags[0])
        return x1, xp.roll(x2, shift, axis=-1)
    
    # Stack multiple shifted copies along a new first axis
    # The output will have shape (n_lags, ...)
    x1_stacked = xp.stack([x1 for _ in lags], axis=0)
    x2_stacked = xp.stack([xp.roll(x2, int(l), axis=-1) for l in lags], axis=0)
    return x1_stacked, x2_stacked


# ===========================================================================
# PRIVATE – statistics
# ===========================================================================


def _permutation_test(x1, x2, metric_fn, n_perm, rng, axis=-1, n_jobs=-1, **kwargs):
    """Label-shuffle permutation test; returns null distribution, optimized for GPU if needed."""
    is_cp = False
    try:
        import cupy as cp
        if isinstance(x1, cp.ndarray) or (x2 is not None and isinstance(x2, cp.ndarray)):
            is_cp = True
    except ImportError:
        pass

    if is_cp:
        import cupy as cp
        null = []
        x2_work = x2 if x2 is not None else x1
        n = x2_work.shape[axis]
        for _ in range(n_perm):
            idx = cp.random.permutation(n)
            x2_perm = cp.take(x2_work, idx, axis=axis)
            v, *_ = metric_fn(x1, x2_perm, axis=axis, **kwargs)
            if hasattr(v, "get"):
                v_mean = float(cp.mean(v))
            else:
                v_mean = float(np.mean(v)) if isinstance(v, np.ndarray) else float(v)
            null.append(v_mean)
        return np.asarray(null)

    x2_work = x2 if x2 is not None else x1
    n = x2_work.shape[axis]
    
    # Generate all permutation indices upfront to pass to workers cleanly
    seeds = rng.integers(0, 2**31 - 1, size=n_perm)
    
    def _run_single_perm(seed):
        local_rng = np.random.default_rng(seed)
        idx = local_rng.permutation(n)
        x2_perm = np.take(x2_work, idx, axis=axis)
        v, *_ = metric_fn(x1, x2_perm, axis=axis, **kwargs)
        return float(np.mean(v)) if isinstance(v, np.ndarray) else float(v)

    null = _parallel_map(_run_single_perm, seeds, n_jobs=n_jobs)
    return np.asarray(null)


def _p_from_null(value, null_dist, alternative):
    """Compute p-value from null distribution."""
    if hasattr(value, "get"):
        value = value.get()
    obs = float(np.mean(value)) if isinstance(value, np.ndarray) else float(value)
    n = len(null_dist)
    if alternative == "two-sided":
        p = np.mean(np.abs(null_dist) >= np.abs(obs))
    elif alternative == "greater":
        p = np.mean(null_dist >= obs)
    else:
        p = np.mean(null_dist <= obs)
    p = max(p, 1.0 / (n + 1))
    return np.atleast_1d(np.float64(p))


def _bootstrap(x1, x2, metric_fn, n_boot, rng, axis=-1, n_jobs=-1, **kwargs):
    """Percentile bootstrap; returns (lower, upper) CI array, optimized for GPU if needed."""
    is_cp = False
    try:
        import cupy as cp
        if isinstance(x1, cp.ndarray) or (x2 is not None and isinstance(x2, cp.ndarray)):
            is_cp = True
    except ImportError:
        pass

    if is_cp:
        import cupy as cp
        boot_vals = []
        x2_work = x2 if x2 is not None else x1
        n = x1.shape[axis]
        for _ in range(n_boot):
            idx = cp.random.randint(0, n, size=n)
            x1_b = cp.take(x1, idx, axis=axis)
            x2_b = cp.take(x2_work, idx, axis=axis)
            v, *_ = metric_fn(x1_b, x2_b, axis=axis, **kwargs)
            if hasattr(v, "get"):
                v_mean = float(cp.mean(v))
            else:
                v_mean = float(np.mean(v)) if isinstance(v, np.ndarray) else float(v)
            boot_vals.append(v_mean)
        boot_arr = cp.array(boot_vals)
        ci = cp.percentile(boot_arr, [2.5, 97.5])
        return ci.get()

    x2_work = x2 if x2 is not None else x1
    n = x1.shape[axis]
    seeds = rng.integers(0, 2**31 - 1, size=n_boot)
    
    def _run_single_boot(seed):
        local_rng = np.random.default_rng(seed)
        idx = local_rng.integers(0, n, size=n)
        x1_b = np.take(x1, idx, axis=axis)
        x2_b = np.take(x2_work, idx, axis=axis)
        v, *_ = metric_fn(x1_b, x2_b, axis=axis, **kwargs)
        return float(np.mean(v)) if isinstance(v, np.ndarray) else float(v)

    boot_vals = _parallel_map(_run_single_boot, seeds, n_jobs=n_jobs)
    boot_arr = np.asarray(boot_vals)
    ci = np.percentile(boot_arr, [2.5, 97.5])
    return ci


_CORRECTION_METHOD_MAP = {
    "fdr_bh": "fdr_bh", "fdr_by": "fdr_by",
    "bonferroni": "bonferroni", "holm": "holm",
    "holm-sidak": "holm-sidak",
}


def _multiple_correction(p: np.ndarray, method: str, alpha: float) -> np.ndarray:
    """Apply multiple-comparison correction; returns q-values."""
    p_flat = np.asarray(p).ravel()
    m_lower = method.lower()
    if m_lower not in _CORRECTION_METHOD_MAP and m_lower != "none":
        warnings.warn(
            f"Unrecognized correction method '{method}'. Falling back to 'fdr_bh'. "
            f"Valid options: {sorted(_CORRECTION_METHOD_MAP.keys())}",
            UserWarning,
            stacklevel=2,
        )
    try:
        from statsmodels.stats.multitest import multipletests
        sm_method = _CORRECTION_METHOD_MAP.get(m_lower, "fdr_bh")
        _, q, _, _ = multipletests(p_flat, alpha=alpha, method=sm_method)
    except ImportError:
        if m_lower == "bonferroni":
            q = np.minimum(p_flat * len(p_flat), 1.0)
        else:
            # Fallback BH
            n = len(p_flat)
            order = np.argsort(p_flat)
            q = np.empty(n)
            q[order] = p_flat[order] * n / (np.arange(1, n + 1))
            q = np.minimum.accumulate(q[::-1])[::-1]
            q = np.minimum(q, 1.0)
    return q.reshape(np.asarray(p).shape)


def _confidence_interval(values, alpha=0.05):
    """Analytical CI from normal approximation."""
    from scipy import stats as sp_stats
    n = len(values)
    se = sp_stats.sem(values)
    ci = sp_stats.t.interval(1 - alpha, df=n - 1, loc=np.mean(values), scale=se)
    return np.asarray(ci)


# ===========================================================================
# PRIVATE – execution / backend
# ===========================================================================

def _get_backend(backend: str, device: str) -> dict:
    """Resolve backend and device; return context dict."""
    if backend == "auto":
        backend = _autodetect_backend(device)
    return {"name": backend, "device": device}


def _autodetect_backend(device: str) -> str:
    """Pick the best available backend."""
    if device in ("cuda",):
        try:
            import cupy  # noqa: F401
            return "cupy"
        except ImportError:
            try:
                import torch
                if torch.cuda.is_available():
                    return "torch"
            except ImportError:
                pass
    if device in ("tpu",):
        try:
            import jax  # noqa: F401
            return "jax"
        except ImportError:
            pass
    return "numpy"


def _to_backend(arr, backend_ctx: dict) -> np.ndarray:
    """Convert arbitrary array type to numpy (or backend tensor), placing on correct device."""
    bk = backend_ctx.get("name", "numpy")
    dev = backend_ctx.get("device", "cpu")
    # Extract data from JNWB Signal objects
    if hasattr(arr, "data"):
        arr = arr.data
    if hasattr(arr, "numpy"):
        # torch or jax
        try:
            arr = arr.numpy()
        except Exception:
            arr = np.asarray(arr)
    if hasattr(arr, "get"):
        # cupy
        arr = arr.get()
    if bk == "numpy":
        return np.asarray(arr, dtype=np.float64)
    elif bk == "cupy":
        return _backend_cupy(arr)
    elif bk == "jax":
        return _backend_jax(arr)
    elif bk == "torch":
        return _backend_torch(arr, dev)
    return np.asarray(arr, dtype=np.float64)


def _parallel_map(fn, items, n_jobs=-1):
    """Map fn over items, optionally in parallel with joblib."""
    try:
        from joblib import Parallel, delayed
        return Parallel(n_jobs=n_jobs)(delayed(fn)(it) for it in items)
    except ImportError:
        return [fn(it) for it in items]


def _chunk_tensor(arr, batch_size, axis=-1):
    """Yield slices of arr along axis."""
    n = arr.shape[axis]
    for start in range(0, n, batch_size):
        stop = min(start + batch_size, n)
        slc = [slice(None)] * arr.ndim
        slc[axis] = slice(start, stop)
        yield arr[tuple(slc)]


# --- backend wrappers -------------------------------------------------------

def _backend_numpy(arr):
    """Ensure numpy float64 array."""
    return np.asarray(arr, dtype=np.float64)


def _backend_cupy(arr):
    """Convert to cupy array; falls back to numpy if unavailable."""
    try:
        import cupy as cp
        return cp.asarray(arr)
    except ImportError:
        warnings.warn("CuPy not available; falling back to NumPy.")
        return np.asarray(arr, dtype=np.float64)


def _backend_jax(arr):
    """Convert to jax array; falls back to numpy if unavailable."""
    try:
        import jax.numpy as jnp
        return jnp.asarray(arr)
    except ImportError:
        warnings.warn("JAX not available; falling back to NumPy.")
        return np.asarray(arr, dtype=np.float64)


def _backend_torch(arr, device="cpu"):
    """Convert to torch tensor placing on correct device; falls back to numpy if unavailable."""
    try:
        import torch
        t = torch.as_tensor(np.asarray(arr, dtype=np.float32))
        if device == "cuda" and torch.cuda.is_available():
            t = t.cuda()
        return t
    except ImportError:
        warnings.warn("PyTorch not available; falling back to NumPy.")
        return np.asarray(arr, dtype=np.float64)


# ===========================================================================
# PRIVATE – metric implementations
# ===========================================================================
# Every metric has the same signature:
#   _metric(x1, x2, axis=-1, **kwargs) -> (value, statistic, effect, p, df)
# When x2 is None, within-x1 analysis is performed.

def _ensure_np(*arrays):
    """Return list of plain numpy arrays (handles torch/jax/cupy)."""
    out = []
    for a in arrays:
        if a is None:
            out.append(None)
            continue
        if hasattr(a, "numpy"):
            try:
                a = a.numpy()
            except Exception:
                a = np.asarray(a)
        if hasattr(a, "get"):
            a = a.get()
        out.append(np.asarray(a, dtype=np.float64))
    return out


def _pearson(x1, x2, axis=-1, **kwargs):
    # Check if inputs are CuPy arrays
    try:
        import cupy as cp
        if isinstance(x1, cp.ndarray) or (x2 is not None and isinstance(x2, cp.ndarray)):
            a = x1.ravel() if x1.ndim > 1 else x1
            y2 = x2 if x2 is not None else x1
            b = y2.ravel()[:len(a)] if y2.ndim > 1 else y2[:len(a)]
            n = len(a)
            # CuPy correlation calculation
            a_mean = cp.mean(a)
            b_mean = cp.mean(b)
            a_std = cp.std(a)
            b_std = cp.std(b)
            if a_std < 1e-12 or b_std < 1e-12:
                r = cp.array(0.0)
            else:
                r = cp.mean((a - a_mean) * (b - b_mean)) / (a_std * b_std + 1e-12)
            df = n - 2
            t = r * cp.sqrt(df) / cp.sqrt(1 - r ** 2 + 1e-12)
            
            # Parametric p-value calculated on CPU/GPU boundary
            t_cpu = float(t.get()) if hasattr(t, "get") else float(t)
            from scipy.stats import t as sp_t
            p_val = 2 * sp_t.sf(abs(t_cpu), df)
            return r, t, cp.abs(r), np.float64(p_val), float(df)
    except ImportError:
        pass

    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.reshape(-1) if x1.ndim > 1 else x1
    b = x2.reshape(-1) if x2.ndim > 1 else x2
    n = min(len(a), len(b))
    from jnwb.statistics import StatisticalAnalysis
    res = StatisticalAnalysis.exploratory_correlate(a[:n], b[:n])
    if "error" in res:
        raise ValueError(f"_pearson: cannot compute correlation ({res['error']}, n={n})")
    p_info = res["parametric"]
    r, p = p_info["statistic"], p_info["pval"]
    df = np.float64(p_info["df"])
    t = r * np.sqrt(df) / np.sqrt(1 - r ** 2 + 1e-12)
    return np.float64(r), np.float64(t), np.float64(abs(r)), np.float64(p), df


def _spearman(x1, x2, axis=-1, **kwargs):
    # For spearman rank, we rank-transform on CuPy then run Pearson
    try:
        import cupy as cp
        if isinstance(x1, cp.ndarray) or (x2 is not None and isinstance(x2, cp.ndarray)):
            a = x1.ravel() if x1.ndim > 1 else x1
            y2 = x2 if x2 is not None else x1
            b = y2.ravel()[:len(a)] if y2.ndim > 1 else y2[:len(a)]
            # Rank transform
            a_rank = cp.argsort(cp.argsort(a)).astype(cp.float64)
            b_rank = cp.argsort(cp.argsort(b)).astype(cp.float64)
            n = len(a)
            a_mean = cp.mean(a_rank)
            b_mean = cp.mean(b_rank)
            a_std = cp.std(a_rank)
            b_std = cp.std(b_rank)
            if a_std < 1e-12 or b_std < 1e-12:
                rho = cp.array(0.0)
            else:
                rho = cp.mean((a_rank - a_mean) * (b_rank - b_mean)) / (a_std * b_std + 1e-12)
            df = n - 2
            t = rho * cp.sqrt(df) / cp.sqrt(1 - rho ** 2 + 1e-12)
            
            # Parametric p-value calculated on CPU/GPU boundary
            t_cpu = float(t.get()) if hasattr(t, "get") else float(t)
            from scipy.stats import t as sp_t
            p_val = 2 * sp_t.sf(abs(t_cpu), df)
            return rho, t, cp.abs(rho), np.float64(p_val), float(df)
    except ImportError:
        pass

    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.reshape(-1) if x1.ndim > 1 else x1
    b = x2.reshape(-1) if x2.ndim > 1 else x2
    n = min(len(a), len(b))
    from jnwb.statistics import StatisticalAnalysis
    res = StatisticalAnalysis.exploratory_correlate(a[:n], b[:n])
    if "error" in res:
        raise ValueError(f"_spearman: cannot compute correlation ({res['error']}, n={n})")
    np_info = res["non_parametric"]
    rho, p = np_info["statistic"], np_info["pval"]
    df = np.float64(np_info["df"])
    t = rho * np.sqrt(df) / np.sqrt(1 - rho ** 2 + 1e-12)
    return np.float64(rho), np.float64(t), np.float64(abs(rho)), np.float64(p), df


def _kendall(x1, x2, axis=-1, **kwargs):
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.stats import kendalltau
    a = x1.reshape(-1) if x1.ndim > 1 else x1
    b = x2.reshape(-1) if x2.ndim > 1 else x2
    n = min(len(a), len(b))
    tau, p = kendalltau(a[:n], b[:n])
    return np.float64(tau), np.float64(tau), np.float64(abs(tau)), np.float64(p), None


def _cosine(x1, x2, axis=-1, **kwargs):
    try:
        import cupy as cp
        if isinstance(x1, cp.ndarray) or (x2 is not None and isinstance(x2, cp.ndarray)):
            a = x1.ravel()
            y2 = x2 if x2 is not None else x1
            b = y2.ravel()[:len(a)]
            sim = cp.dot(a, b) / (cp.linalg.norm(a) * cp.linalg.norm(b) + 1e-12)
            return sim, sim, cp.abs(sim), None, None
    except ImportError:
        pass

    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.ravel()
    b = x2.ravel()[:len(a)]
    sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)
    return np.float64(sim), np.float64(sim), np.float64(abs(sim)), None, None


def _rsa(x1, x2, axis=-1, rdm_metric="correlation", **kwargs):
    """Representational similarity analysis via condensed RDM correlation (avoiding squareform)."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.spatial.distance import pdist
    from scipy.stats import spearmanr
    # We directly compute pdist which returns the condensed upper-triangular vector representation
    # This avoids constructing the full square matrix via squareform and slicing.
    v1 = pdist(x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1), metric=rdm_metric)
    v2 = pdist(x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1), metric=rdm_metric)
    rho, p = spearmanr(v1, v2)
    return np.float64(rho), np.float64(rho), np.float64(abs(rho)), np.float64(p), None


def _cka(x1, x2, axis=-1, kernel="linear", **kwargs):
    """Centered Kernel Alignment optimized for linear complexity O(md^2) when d << m."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    d1, d2 = X.shape[1], Y.shape[1]
    
    # Standard centering: H @ K @ H.
    # For linear kernel: Kx = X @ X.T.
    # Center matrix: X_c = (I - 1/m * 11^T) @ X = X - mean(X, axis=0).
    # Then centered Gram matrix is X_c @ X_c.T.
    # Its trace/dot product is equivalent to trace((X_c @ X_c.T) @ (Y_c @ Y_c.T))
    # which can be computed as ||X_c.T @ Y_c||_F^2, which is O(m * d1 * d2) instead of O(m^3).
    X_c = X - np.mean(X, axis=0, keepdims=True)
    Y_c = Y - np.mean(Y, axis=0, keepdims=True)
    
    # Calculate trace of Kx_c @ Ky_c which is ||X_c.T @ Y_c||_F^2
    cross = X_c.T @ Y_c
    num = np.sum(cross ** 2)
    
    # Denominators are ||X_c.T @ X_c||_F^2 and ||Y_c.T @ Y_c||_F^2
    denom_x = np.sum((X_c.T @ X_c) ** 2)
    denom_y = np.sum((Y_c.T @ Y_c) ** 2)
    
    cka_val = num / np.sqrt(denom_x * denom_y + 1e-12)
    return np.float64(cka_val), np.float64(cka_val), np.float64(cka_val), None, None


def _rv(x1, x2, axis=-1, **kwargs):
    """RV coefficient optimized via trace identity to run at O(md^2) when d << m."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    
    # Standard formula uses full gram matrices: S_xx = X @ X.T (m x m)
    # trace(S_xy @ S_xy.T) = trace(X @ Y.T @ Y @ X.T) = trace(X.T @ X @ Y.T @ Y)
    # = Frobenius norm of (X.T @ Y) squared. This drops calculation from O(m^3) to O(m * d1 * d2 + d1^3).
    C_xy = X.T @ Y
    num = np.sum(C_xy ** 2)
    
    C_xx = X.T @ X
    C_yy = Y.T @ Y
    denom_x = np.sum(C_xx ** 2)
    denom_y = np.sum(C_yy ** 2)
    
    rv = num / np.sqrt(denom_x * denom_y + 1e-12)
    return np.float64(rv), np.float64(rv), np.float64(rv), None, None


def _hsic(x1, x2, axis=-1, sigma=1.0, **kwargs):
    """Hilbert-Schmidt Independence Criterion with efficient centering.
    Avoids explicit dense centering matrix allocation.
    Assumes symmetric kernels (like the default Gaussian RBF) such that K^T = K
    and trace(Kx @ Ky) = sum(Kx * Ky).
    """
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.spatial.distance import cdist
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2 is not None else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    
    Kx = np.exp(-cdist(X, X, "sqeuclidean") / (2 * sigma ** 2))
    Ky = np.exp(-cdist(Y, Y, "sqeuclidean") / (2 * sigma ** 2))
    
    # Assert kernel symmetry to avoid silent failure on non-symmetric custom kernels
    if not (np.allclose(Kx, Kx.T) and np.allclose(Ky, Ky.T)):
         raise ValueError("HSIC optimization requires symmetric kernel matrices.")
    
    # Tr(Kx @ H @ Ky @ H) where H = I - 1/m * J.
    # Tr(Kx @ H @ Ky @ H) = Tr(Kx @ Ky) - 2/m * sum(Kx @ Ky) + 1/m^2 * sum(Kx) * sum(Ky) (fully centered trace).
    # Since kernels are symmetric, Tr(Kx @ Ky) = sum(Kx * Ky).
    tr_kx_ky = np.sum(Kx * Ky)
    row_sum_kx = np.sum(Kx, axis=1)
    col_sum_ky = np.sum(Ky, axis=0)
    term2 = (2.0 / m) * np.dot(row_sum_kx, col_sum_ky)
    term3 = (1.0 / (m ** 2)) * np.sum(Kx) * np.sum(Ky)
    
    hsic_val = (tr_kx_ky - term2 + term3) / ((m - 1) ** 2)
    return np.float64(hsic_val), np.float64(hsic_val), np.float64(hsic_val), None, None


def _distance_correlation(x1, x2, axis=-1, **kwargs):
    """Distance correlation (Székely & Rizzo)."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.spatial.distance import cdist
    X = x1.reshape(x1.shape[0], -1) if x1.ndim > 1 else x1[:, None]
    Y = x2.reshape(x2.shape[0], -1) if x2.ndim > 1 else x2[:, None]
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]

    def _dcov(A, B):
        A = A - A.mean(axis=0) - A.mean(axis=1, keepdims=True) + A.mean()
        B = B - B.mean(axis=0) - B.mean(axis=1, keepdims=True) + B.mean()
        return np.sqrt(abs(np.mean(A * B)))

    dA = cdist(X, X)
    dB = cdist(Y, Y)
    dcov_xy = _dcov(dA, dB)
    dcov_xx = _dcov(dA, dA)
    dcov_yy = _dcov(dB, dB)
    dc = dcov_xy / np.sqrt(dcov_xx * dcov_yy + 1e-12)
    return np.float64(dc), np.float64(dc), np.float64(dc), None, None


def _mutual_information(x1, x2, axis=-1, bins=32, **kwargs):
    """Mutual information via histogram estimator."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.ravel()
    b = x2.ravel()[:len(a)]
    c_xy, xe, ye = np.histogram2d(a, b, bins=bins)
    c_xy = c_xy / c_xy.sum()
    c_x = c_xy.sum(axis=1)
    c_y = c_xy.sum(axis=0)
    outer = np.outer(c_x, c_y)
    mask = c_xy > 0
    mi = np.sum(c_xy[mask] * np.log(c_xy[mask] / (outer[mask] + 1e-12)))
    return np.float64(mi), np.float64(mi), np.float64(mi), None, None


def _procrustes(x1, x2, axis=-1, **kwargs):
    """Procrustes dissimilarity (1 - similarity)."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.spatial import procrustes as sp_proc
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    n = min(X.shape[1], Y.shape[1])
    X, Y = X[:, :n], Y[:, :n]
    _, _, disparity = sp_proc(X, Y)
    sim = 1.0 - float(disparity)
    return np.float64(sim), np.float64(sim), np.float64(sim), None, None


def _granger(x1, x2, axis=-1, max_lag=5, **kwargs):
    """Granger causality F-statistic (x2 → x1) with best lag selection by AIC."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    try:
        from statsmodels.tsa.stattools import grangercausalitytests
        a = x1.ravel()
        b = x2.ravel()[:len(a)]
        data = np.column_stack([a, b])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = grangercausalitytests(data, maxlag=max_lag, verbose=False)
        
        # Select best lag from 1 to max_lag based on minimum AIC
        # statsmodels grangercausalitytests returns a dict.
        # For each lag, res[lag][1] contains the results of the OLS regressions.
        # Under res[lag][1], there are multiple regression results (e.g. 'lrtest', 'params_ftest', 'ssr_chi2test', 'ssr_ftest').
        # The unrestricted OLS model results are in res[lag][1][1] (unrestricted model object).
        # We can fetch the AIC from res[lag][1][1].aic
        best_lag = 1
        min_aic = float('inf')
        for lag in range(1, max_lag + 1):
            try:
                # res[lag][1] is a list of [res_restricted, res_unrestricted, joint_test_results] or similar.
                # In statsmodels: res[lag][1] contains (results_d, results_m, lr_result) where results_m is the unrestricted OLS model result.
                unrestricted_model = res[lag][1][1]
                aic = unrestricted_model.aic
                if aic < min_aic:
                    min_aic = aic
                    best_lag = lag
            except Exception:
                # Fallback to last lag if AIC extraction structure changes
                best_lag = lag
        
        f_stat = float(res[best_lag][0]["ssr_ftest"][0])
        p_val = float(res[best_lag][0]["ssr_ftest"][1])
        df = float(res[best_lag][0]["ssr_ftest"][2])
        return np.float64(f_stat), np.float64(f_stat), np.float64(f_stat), np.float64(p_val), np.float64(df)
    except ImportError:
        warnings.warn("statsmodels required for Granger causality; returning NaN.")
        return np.float64(np.nan), None, None, None, None


def _entropy(probs):
    """Calculate Shannon entropy in nats from probability array."""
    probs = probs[probs > 0]
    return -np.sum(probs * np.log(probs))


def _transfer_entropy(x1, x2, axis=-1, k=1, bins=10, **kwargs):
    """Transfer entropy (x2 → x1) via plug-in histogram estimator."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.ravel()
    b = x2.ravel()[:len(a)]
    
    # We estimate TE(Y -> X) = H(X_t, X_{t-1}) + H(X_{t-1}, Y_{t-1}) - H(X_{t-1}) - H(X_t, X_{t-1}, Y_{t-1})
    # with Y = b, X = a.
    xt = a[1:]
    xt1 = a[:-1]
    yt1 = b[:-1]
    
    # Digitise and joint histogram of 3 variables
    sample = np.column_stack([xt, xt1, yt1])
    hist_3d, _ = np.histogramdd(sample, bins=bins)
    p_3d = hist_3d / hist_3d.sum()
    
    # Marginals
    p_xt_xt1 = p_3d.sum(axis=2)
    p_xt1_yt1 = p_3d.sum(axis=0)
    p_xt1 = p_3d.sum(axis=(0, 2))
    
    # Entropies
    h_3d = _entropy(p_3d)
    h_xt_xt1 = _entropy(p_xt_xt1)
    h_xt1_yt1 = _entropy(p_xt1_yt1)
    h_xt1 = _entropy(p_xt1)
    
    te = h_xt_xt1 + h_xt1_yt1 - h_xt1 - h_3d
    te = max(0.0, te)  # non-negative constraint
    
    return np.float64(te), np.float64(te), np.float64(te), None, None


def _phase_slope(x1, x2, axis=-1, fs=None, nperseg=None, noverlap=None,
                 bands=None, jackknife=True, **kwargs):
    """
    Phase Slope Index (PSI), delegated to :func:`jnwb.connectivity.phase_slope_index`.

    Superseded implementation (pre-2026-08-04) took a single ``rfft`` of the whole
    ravelled record. A one-segment coherency has magnitude identically 1 at every
    frequency, so its phase-slope sum is unweighted by coherence and is not PSI in
    the sense of Nolte et al. (2008). Coherency must be averaged over segments.

    Args:
        fs: sampling rate in Hz. When omitted, ``fs=2.0`` is used so frequencies
            read as normalized units (Nyquist = 1.0) — ``bands`` given in Hz then
            mean nothing, so pass a real ``fs`` if you want a named band.
        nperseg / noverlap / bands / jackknife: forwarded verbatim.

    Returns:
        (psi, jackknife_z, |psi|, p, None) — ``psi`` keeps its physical scale;
        ``statistic`` is now the jackknife z rather than a copy of ``psi``, and
        ``p`` is the two-sided normal-approximation p-value on that z (previously
        both were ``None``).
    """
    # PSI delegates to jnwb.connectivity's segmented estimator (promoted 2026-08-23 from
    # omission.jnwb_ext.connectivity, 99%-jnwb-sufficiency normalization -- this is now an
    # intra-package import, not a cross-project one).
    from .connectivity import phase_slope_index as _psi_impl

    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.ravel()
    b = x2.ravel()[: len(a)]
    n = min(len(a), len(b))
    if fs is None:
        fs = 2.0  # normalized frequency: Nyquist == 1.0
        if bands is None:
            warnings.warn(
                "phase_slope called without fs and without bands: the result is a "
                "PSI summed over the entire spectrum, where a narrowband lead is "
                "diluted by broadband noise and the sign can flip with nperseg. "
                "Pass fs= and bands= (or a normalized band, Nyquist=1.0) to get a "
                "frequency-specific direction.",
                RuntimeWarning,
                stacklevel=2,
            )
    res = _psi_impl(
        a[:n], b[:n], fs=fs, bands=bands, nperseg=nperseg,
        noverlap=noverlap, jackknife=jackknife,
    )
    band = next(iter(res.per_band.values()))
    z = band.get("z", np.nan)
    p = res.p_x_to_y
    return (
        np.float64(res.x_to_y),
        np.float64(z),
        np.float64(abs(res.x_to_y)),
        None if p is None else np.float64(p),
        None,
    )


_METRIC_DISPATCH = {
    "pearson": _pearson,
    "spearman": _spearman,
    "kendall": _kendall,
    "cosine": _cosine,
    "rsa": _rsa,
    "cka": _cka,
    "rv": _rv,
    "hsic": _hsic,
    "distance_correlation": _distance_correlation,
    "mutual_information": _mutual_information,
    "procrustes": _procrustes,
    "granger": _granger,
    "transfer_entropy": _transfer_entropy,
    "phase_slope": _phase_slope,
}


# ===========================================================================
# PRIVATE – result helpers
# ===========================================================================

def _make_exec_meta(backend_ctx, device, t0, rng):
    seed_val = None
    if rng is not None:
        try:
            if hasattr(rng, "bit_generator") and hasattr(rng.bit_generator, "state"):
                state = rng.bit_generator.state
                if isinstance(state, dict) and "state" in state:
                    sub_state = state["state"]
                    if isinstance(sub_state, dict) and "state" in sub_state:
                        seed_val = int(sub_state["state"])
                    elif isinstance(sub_state, int):
                        seed_val = sub_state
        except Exception:
            pass
    return {
        "backend": backend_ctx.get("name", "numpy"),
        "device": device,
        "runtime": time.perf_counter() - t0,
        "memory": None,
        "seed": seed_val,
    }


def _make_result(
    value, statistic, effect, p, q, df, ci,
    metric, axes, aligned_axes, labels, parameters,
    null_distribution, aligned_x1, aligned_x2, execution,
) -> JRSAResult:
    def _to_numpy(a):
        if a is None:
            return None
        if hasattr(a, "get"):
            a = a.get()
        return np.asarray(a)

    return JRSAResult(
        value=_to_numpy(value) if value is not None else np.float64(np.nan),
        statistic=_to_numpy(statistic),
        effect=_to_numpy(effect),
        p=_to_numpy(p),
        q=_to_numpy(q),
        df=_to_numpy(df),
        ci=_to_numpy(ci),
        metric=metric,
        axes=axes,
        aligned_axes=aligned_axes,
        labels=labels,
        parameters=parameters,
        null_distribution=_to_numpy(null_distribution),
        aligned_x1=_to_numpy(aligned_x1),
        aligned_x2=_to_numpy(aligned_x2),
        execution=execution,
    )


def _result_summary(result: JRSAResult) -> str:
    lines = [
        "JRSAResult Summary",
        "=" * 40,
        f"  metric     : {result.metric}",
        f"  value      : {result.value}",
        f"  statistic  : {result.statistic}",
        f"  effect     : {result.effect}",
        f"  p (raw)    : {result.p}",
        f"  q (corr.)  : {result.q}",
        f"  df         : {result.df}",
        f"  CI         : {result.ci}",
        f"  backend    : {result.execution.get('backend')}",
        f"  runtime    : {result.execution.get('runtime', 0):.4f}s",
    ]
    return "\n".join(lines)


def _result_plot(result: JRSAResult, **kwargs):
    """Auto-plot: matrix heatmap if 2-D, else line."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        warnings.warn("matplotlib not available for plotting.")
        return None
    val = np.asarray(result.value)
    fig, ax = plt.subplots(figsize=kwargs.get("figsize", (6, 5)))
    if val.ndim == 2:
        im = ax.imshow(val, aspect="auto", cmap=kwargs.get("cmap", "RdBu_r"))
        plt.colorbar(im, ax=ax)
    else:
        ax.plot(val)
    ax.set_title(f"jrsa – {result.metric}")
    plt.tight_layout()
    return fig


def _result_save(result: JRSAResult, path: str, fmt: str):
    """Save result fields to npz / json / csv."""
    if fmt == "npz":
        payload = {k: v for k, v in result.__dict__.items()
                   if isinstance(v, (np.ndarray, type(None)))}
        np.savez_compressed(path, **{k: v for k, v in payload.items() if v is not None})
    elif fmt == "json":
        import json
        def _serial(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return str(obj)
        with open(path, "w") as fh:
            json.dump(result.__dict__, fh, default=_serial, indent=2)
    elif fmt == "csv":
        import csv
        rows = [(k, v) for k, v in result.__dict__.items() if not isinstance(v, np.ndarray)]
        with open(path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["field", "value"])
            writer.writerows(rows)
    else:
        raise ValueError(f"Unknown format '{fmt}'. Choose from: npz, json, csv.")
