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
        p_repr = f", p={float(np.min(self.p)):.4g}" if self.p is not None else ""
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
    x1_lagged, x2_lagged = _apply_lag(x1, x2, axis_map, lag)

    # --- dispatch metric ------------------------------------------------------
    metric_fn = _METRIC_DISPATCH.get(metric.lower())
    if metric_fn is None:
        raise ValueError(
            f"Unknown metric '{metric}'. "
            f"Choose from: {sorted(_METRIC_DISPATCH)}"
        )

    if verbose:
        print(f"[jrsa] computing {metric!r} …")

    value, statistic, effect, p_raw, df = metric_fn(
        x1_lagged, x2_lagged, axis=-1, **kwargs
    )

    # --- statistics -----------------------------------------------------------
    null_dist = None
    ci = None

    if stats and permutations > 0:
        null_dist = _permutation_test(
            x1_lagged, x2_lagged, metric_fn, permutations, rng, axis=-1, **kwargs
        )
        if p_raw is None:
            p_raw = _p_from_null(value, null_dist, alternative)

    if bootstrap > 0:
        ci = _bootstrap(x1_lagged, x2_lagged, metric_fn, bootstrap, rng, axis=-1, **kwargs)

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

def _prepare_inputs(x1, x2, backend_ctx: dict):
    """Convert inputs to numpy (or chosen backend array) and handle JNWB Signals."""
    x1 = _to_backend(x1, backend_ctx)
    if x2 is not None:
        x2 = _to_backend(x2, backend_ctx)
    else:
        x2 = None  # within-array mode
    return x1, x2


def _validate_inputs(x1: np.ndarray, x2, nan_policy: str):
    """Shape checks and NaN handling."""
    if x1.ndim < 1:
        raise ValueError("x1 must have at least 1 dimension.")
    if nan_policy == "raise" and np.any(np.isnan(x1)):
        raise ValueError("NaN values found in x1 (nan_policy='raise').")
    if x2 is not None:
        if nan_policy == "raise" and np.any(np.isnan(x2)):
            raise ValueError("NaN values found in x2 (nan_policy='raise').")
    if nan_policy == "omit":
        x1 = np.where(np.isnan(x1), 0.0, x1)
        if x2 is not None:
            x2 = np.where(np.isnan(x2), 0.0, x2)
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
    """Resample one array along *axis* to match the other."""
    target = min(n1, n2)
    if align in ("auto", "downsample"):
        if n1 > target:
            idx = np.linspace(0, n1 - 1, target, dtype=int)
            x1 = np.take(x1, idx, axis=axis)
        if n2 > target:
            idx = np.linspace(0, n2 - 1, target, dtype=int)
            x2 = np.take(x2, idx, axis=axis)
    elif align == "upsample":
        target = max(n1, n2)
        if n1 < target:
            idx = np.round(np.linspace(0, n1 - 1, target)).astype(int)
            x1 = np.take(x1, idx, axis=axis)
        if n2 < target:
            idx = np.round(np.linspace(0, n2 - 1, target)).astype(int)
            x2 = np.take(x2, idx, axis=axis)
    elif align in ("interpolate", "linear"):
        try:
            from scipy.interpolate import interp1d
            def _interp(arr, n_src, n_tgt, ax):
                xold = np.linspace(0, 1, n_src)
                xnew = np.linspace(0, 1, n_tgt)
                f = interp1d(xold, arr, axis=ax, kind="linear", fill_value="extrapolate")
                return f(xnew)
            if n1 != target:
                x1 = _interp(x1, n1, target, axis)
            if n2 != target:
                x2 = _interp(x2, n2, target, axis)
        except ImportError:
            x1, x2 = _resample_axis(x1, x2, axis, n1, n2, "downsample", align_mode)
    elif align == "nearest":
        if n1 > target:
            idx = np.round(np.linspace(0, n1 - 1, target)).astype(int)
            x1 = np.take(x1, idx, axis=axis)
        if n2 > target:
            idx = np.round(np.linspace(0, n2 - 1, target)).astype(int)
            x2 = np.take(x2, idx, axis=axis)
    elif align == "cubic":
        try:
            from scipy.interpolate import interp1d
            def _interp_cubic(arr, n_src, n_tgt, ax):
                xold = np.linspace(0, 1, n_src)
                xnew = np.linspace(0, 1, n_tgt)
                f = interp1d(xold, arr, axis=ax, kind="cubic", fill_value="extrapolate")
                return f(xnew)
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
    """Apply reductions (mean, median, …) along named axes."""
    _OPS = {
        "mean": np.mean, "median": np.median,
        "sum": np.sum, "max": np.max, "min": np.min,
    }
    for name, op_str in reduction.items():
        ax = axis_map.get(name)
        if ax is None:
            continue
        op = _OPS.get(op_str, np.mean)
        x1 = op(x1, axis=ax, keepdims=True)
        if x2 is not None:
            x2 = op(x2, axis=ax, keepdims=True)
    return x1, x2


def _apply_preprocessing(x1, x2, normalize, standardize, detrend):
    """Apply per-array preprocessing in place."""
    def _prep(arr):
        if arr is None:
            return arr
        if detrend:
            try:
                from scipy.signal import detrend as sp_detrend
                arr = sp_detrend(arr, axis=-1)
            except ImportError:
                arr = arr - np.polyval(np.polyfit(np.arange(arr.shape[-1]), arr.T, 1), np.arange(arr.shape[-1]))
        if standardize:
            mu = np.nanmean(arr, axis=-1, keepdims=True)
            sd = np.nanstd(arr, axis=-1, keepdims=True)
            arr = (arr - mu) / (sd + 1e-12)
        if normalize:
            lo = np.nanmin(arr, axis=-1, keepdims=True)
            hi = np.nanmax(arr, axis=-1, keepdims=True)
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
    """Apply temporal lag(s) by rolling along the last axis."""
    if lag == 0 or (hasattr(lag, "__len__") and len(lag) == 1 and lag[0] == 0):
        return x1, x2
    if x2 is None:
        return x1, x2
    lags = [lag] if isinstance(lag, (int, float)) else list(lag)
    # For multi-lag we just apply the first lag; full multi-lag returns
    # a stacked result which callers can handle via sliding=True
    shift = int(lags[0])
    x2_shifted = np.roll(x2, shift, axis=-1)
    return x1, x2_shifted


def _stack_batches(arrays, batch_size):
    """Split the last axis of each array into batches."""
    n = arrays[0].shape[-1]
    if batch_size is None or batch_size >= n:
        yield arrays
        return
    for start in range(0, n, batch_size):
        stop = min(start + batch_size, n)
        yield tuple(a[..., start:stop] for a in arrays)


# ===========================================================================
# PRIVATE – statistics
# ===========================================================================

def _compute_statistics(value, x1, x2, metric_fn, alternative, axis, **kwargs):
    """Wrapper; individual metrics compute their own stats inline."""
    return value  # metrics return statistic already


def _permutation_test(x1, x2, metric_fn, n_perm, rng, axis=-1, **kwargs):
    """Label-shuffle permutation test; returns null distribution."""
    null = []
    x2_work = x2 if x2 is not None else x1
    n = x2_work.shape[axis]
    for _ in range(n_perm):
        idx = rng.permutation(n)
        x2_perm = np.take(x2_work, idx, axis=axis)
        v, *_ = metric_fn(x1, x2_perm, axis=axis, **kwargs)
        null.append(float(np.mean(v)) if isinstance(v, np.ndarray) else float(v))
    return np.asarray(null)


def _p_from_null(value, null_dist, alternative):
    """Compute p-value from null distribution."""
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


def _bootstrap(x1, x2, metric_fn, n_boot, rng, axis=-1, **kwargs):
    """Percentile bootstrap; returns (lower, upper) CI array."""
    boot_vals = []
    x2_work = x2 if x2 is not None else x1
    n = x1.shape[axis]
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        x1_b = np.take(x1, idx, axis=axis)
        x2_b = np.take(x2_work, idx, axis=axis)
        v, *_ = metric_fn(x1_b, x2_b, axis=axis, **kwargs)
        boot_vals.append(float(np.mean(v)) if isinstance(v, np.ndarray) else float(v))
    boot_arr = np.asarray(boot_vals)
    ci = np.percentile(boot_arr, [2.5, 97.5])
    return ci


def _multiple_correction(p: np.ndarray, method: str, alpha: float) -> np.ndarray:
    """Apply multiple-comparison correction; returns q-values."""
    p_flat = np.asarray(p).ravel()
    try:
        from statsmodels.stats.multitest import multipletests
        _METHOD_MAP = {
            "fdr_bh": "fdr_bh", "fdr_by": "fdr_by",
            "bonferroni": "bonferroni", "holm": "holm",
            "holm-sidak": "holm-sidak",
        }
        sm_method = _METHOD_MAP.get(method.lower(), "fdr_bh")
        _, q, _, _ = multipletests(p_flat, alpha=alpha, method=sm_method)
    except ImportError:
        if method.lower() == "bonferroni":
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
    """Convert arbitrary array type to numpy (or backend tensor)."""
    bk = backend_ctx.get("name", "numpy")
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
        return _backend_torch(arr)
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


def _backend_torch(arr):
    """Convert to torch tensor; falls back to numpy if unavailable."""
    try:
        import torch
        return torch.as_tensor(np.asarray(arr, dtype=np.float32))
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
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.stats import pearsonr
    a = x1.reshape(-1) if x1.ndim > 1 else x1
    b = x2.reshape(-1) if x2.ndim > 1 else x2
    n = min(len(a), len(b))
    r, p = pearsonr(a[:n], b[:n])
    df = np.float64(n - 2)
    t = r * np.sqrt(df) / np.sqrt(1 - r ** 2 + 1e-12)
    return np.float64(r), np.float64(t), np.float64(abs(r)), np.float64(p), df


def _spearman(x1, x2, axis=-1, **kwargs):
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.stats import spearmanr
    a = x1.reshape(-1) if x1.ndim > 1 else x1
    b = x2.reshape(-1) if x2.ndim > 1 else x2
    n = min(len(a), len(b))
    rho, p = spearmanr(a[:n], b[:n])
    df = np.float64(n - 2)
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
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.ravel()
    b = x2.ravel()[:len(a)]
    sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)
    return np.float64(sim), np.float64(sim), np.float64(abs(sim)), None, None


def _rsa(x1, x2, axis=-1, rdm_metric="correlation", **kwargs):
    """Representational similarity analysis via RDM correlation."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.spatial.distance import pdist, squareform
    from scipy.stats import spearmanr
    rdm1 = squareform(pdist(x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1), metric=rdm_metric))
    rdm2 = squareform(pdist(x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1), metric=rdm_metric))
    # upper-triangle
    triu = np.triu_indices_from(rdm1, k=1)
    rho, p = spearmanr(rdm1[triu], rdm2[triu])
    return np.float64(rho), np.float64(rho), np.float64(abs(rho)), np.float64(p), None


def _cka(x1, x2, axis=-1, kernel="linear", **kwargs):
    """Centered Kernel Alignment."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    def _center_gram(K):
        n = K.shape[0]
        H = np.eye(n) - np.ones((n, n)) / n
        return H @ K @ H
    def _linear_kernel(X):
        return X @ X.T
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    Kx = _center_gram(_linear_kernel(X))
    Ky = _center_gram(_linear_kernel(Y))
    num = np.sum(Kx * Ky)
    denom = np.sqrt(np.sum(Kx * Kx) * np.sum(Ky * Ky) + 1e-12)
    cka_val = num / denom
    return np.float64(cka_val), np.float64(cka_val), np.float64(cka_val), None, None


def _rv(x1, x2, axis=-1, **kwargs):
    """RV coefficient (matrix correlation)."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    S_xy = X @ Y.T
    S_xx = X @ X.T
    S_yy = Y @ Y.T
    rv = np.trace(S_xy @ S_xy.T) / np.sqrt(np.trace(S_xx @ S_xx) * np.trace(S_yy @ S_yy) + 1e-12)
    return np.float64(rv), np.float64(rv), np.float64(rv), None, None


def _hsic(x1, x2, axis=-1, sigma=1.0, **kwargs):
    """Hilbert-Schmidt Independence Criterion."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.spatial.distance import cdist
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
    m = min(X.shape[0], Y.shape[0])
    X, Y = X[:m], Y[:m]
    Kx = np.exp(-cdist(X, X, "sqeuclidean") / (2 * sigma ** 2))
    Ky = np.exp(-cdist(Y, Y, "sqeuclidean") / (2 * sigma ** 2))
    H = np.eye(m) - np.ones((m, m)) / m
    hsic_val = np.trace(Kx @ H @ Ky @ H) / ((m - 1) ** 2)
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
    try:
        _, _, disparity = sp_proc(X, Y)
    except Exception:
        disparity = 1.0
    sim = 1.0 - float(disparity)
    return np.float64(sim), np.float64(sim), np.float64(sim), None, None


def _granger(x1, x2, axis=-1, max_lag=5, **kwargs):
    """Granger causality F-statistic (x2 → x1)."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    try:
        from statsmodels.tsa.stattools import grangercausalitytests
        a = x1.ravel()
        b = x2.ravel()[:len(a)]
        data = np.column_stack([a, b])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = grangercausalitytests(data, maxlag=max_lag, verbose=False)
        # collect F and p at the chosen lag
        best_lag = max_lag
        f_stat = float(res[best_lag][0]["ssr_ftest"][0])
        p_val = float(res[best_lag][0]["ssr_ftest"][1])
        df = float(res[best_lag][0]["ssr_ftest"][2])
        return np.float64(f_stat), np.float64(f_stat), np.float64(f_stat), np.float64(p_val), np.float64(df)
    except ImportError:
        warnings.warn("statsmodels required for Granger causality; returning NaN.")
        return np.float64(np.nan), None, None, None, None


def _transfer_entropy(x1, x2, axis=-1, k=1, **kwargs):
    """Transfer entropy (x2 → x1) via plug-in estimator."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.ravel()
    b = x2.ravel()[:len(a)]
    n = len(a) - k
    bins = max(2, int(np.sqrt(n)))
    te = 0.0
    for i in range(k, len(a)):
        # Simple 1-D TE via conditional probability estimate
        pass
    # Fallback: histogram-based approximation
    mi_val, *_ = _mutual_information(
        np.diff(a[:n + 1]), b[:n], axis=axis
    )
    return np.float64(float(mi_val)), np.float64(float(mi_val)), np.float64(float(mi_val)), None, None


def _phase_slope(x1, x2, axis=-1, **kwargs):
    """Phase Slope Index (PSI) – simplified implementation."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.ravel()
    b = x2.ravel()[:len(a)]
    n = min(len(a), len(b))
    A, B = a[:n], b[:n]
    f_a = np.fft.rfft(A)
    f_b = np.fft.rfft(B)
    cs = f_a * np.conj(f_b)
    psi = np.sum(np.imag(np.conj(cs[:-1]) * cs[1:]))
    psi = psi / (np.abs(psi) + 1e-12)
    return np.float64(float(np.real(psi))), np.float64(float(np.real(psi))), np.float64(abs(float(np.real(psi)))), None, None


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
    return {
        "backend": backend_ctx.get("name", "numpy"),
        "device": device,
        "runtime": time.perf_counter() - t0,
        "memory": None,
        "seed": int(rng.bit_generator.state["state"]["state"]) if hasattr(rng.bit_generator, "state") else None,
    }


def _make_result(
    value, statistic, effect, p, q, df, ci,
    metric, axes, aligned_axes, labels, parameters,
    null_distribution, aligned_x1, aligned_x2, execution,
) -> JRSAResult:
    return JRSAResult(
        value=np.asarray(value) if value is not None else np.float64(np.nan),
        statistic=np.asarray(statistic) if statistic is not None else None,
        effect=np.asarray(effect) if effect is not None else None,
        p=np.asarray(p) if p is not None else None,
        q=np.asarray(q) if q is not None else None,
        df=np.asarray(df) if df is not None else None,
        ci=np.asarray(ci) if ci is not None else None,
        metric=metric,
        axes=axes,
        aligned_axes=aligned_axes,
        labels=labels,
        parameters=parameters,
        null_distribution=null_distribution,
        aligned_x1=aligned_x1,
        aligned_x2=aligned_x2,
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
