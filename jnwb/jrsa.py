"""
jnwb.jrsa – Unified Representational Similarity Analysis

Public API: exactly one function.

    >>> import jnwb
    >>> result = oa.jrsa(x1, x2, metric="rsa", stats=True)
    >>> result.summary()
    >>> result.plot()

"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from ._backend import CPU, CUDA, resolve_device
from ._parallel import parallel_map
from ._rng import Default, RNGLike, resolve_seed_alias
from ._spread import is_constant, zscore

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
        Raw p-values, in the tail `alternative` names: the permutation p when a permutation
        null was formed, otherwise the metric's parametric p, or None for a metric that has
        none.
    q : np.ndarray | None
        Corrected p-values (after multiple-comparison correction).
    df : np.ndarray | None
        Degrees of freedom.
    ci : np.ndarray | None
        Percentile bootstrap interval, shape (…, 2), fixed at 95% (the 2.5th and 97.5th
        percentiles of the bootstrap distribution). `alpha` sets the significance
        threshold for the multiple-comparison correction and does not change this
        interval.
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
        Runtime metadata (backend, device, batch_size, runtime, memory, seed). What ran,
        not what was asked for; the request is in `parameters`.
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
            except (TypeError, ValueError):
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
    n_jobs=1,
    batch_size=None,
    rng: RNGLike = Default(None),
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
        First tensor: an ndarray or array-like, a scipy.sparse matrix (densified), a JAX
        array, or a torch tensor or CuPy array on any device (copied to the host). A masked
        array with a masked element raises.
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
        Dimension reductions, e.g. {"trial": "mean"}. The operation is one of
        mean | median | sum | max | min; anything else raises rather than defaulting.
    metric : str
        Similarity metric.  One of: pearson, spearman, kendall, cosine,
        rsa, cka, rv, hsic, distance_correlation, mutual_information,
        procrustes, granger_ssr_ftest, transfer_entropy_histogram_nats, phase_slope.
        The SSR F-test and histogram TE metrics are distinct from connectivity
        ``granger`` and ``transfer_entropy``.
    lag : int | tuple | array-like
        Temporal lag(s).
    window : tuple | int or None
        Analysis window as **sample indices** along the aligned axis: ``(start, stop)``,
        half-open, with negative values counted from the end as in Python slicing, or an
        integer width centred on the axis. This is not a time -- `jrsa` takes no sampling
        rate and cannot convert one. The docstring used to read "e.g. (-500, 500) ms",
        which on a 6-sample axis clamped to the whole axis and returned the unwindowed
        answer with no warning.
    sliding : bool
        Use sliding window.
    normalize : bool
        Normalise each input to [0, 1].
    standardize : bool
        Z-score each input along the last axis; a constant row becomes 0.
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
        holm-sidak | fdr_bh | fdr_by.
        Any other value raises `ValueError`; there is no fallback. This list used to end
        "| cluster | maxT", neither of which was ever implemented -- both raised -- so the
        docstring advertised two methods a caller could not use.
    alpha : float
        Significance threshold for the multiple-comparison correction. It does not set
        the width of `ci`, which is a fixed 95% percentile bootstrap interval.
    alternative : str
        two-sided | greater | less; anything else raises before any computation. It sets
        the tail of `p`. With a permutation null (`stats=True`, `permutations > 0`) the tail
        is counted on the null. Without one, `p` is the metric's parametric p, which is
        two-sided; a one-sided alternative halves it when `value` lies on the requested
        side and gives ``1 - p/2`` otherwise. The `granger_ssr_ftest` parametric p is an
        upper-tail F-test, so that metric raises for a one-sided alternative without a
        permutation null.
    backend : str
        auto | numpy | scipy | jax | torch | cupy. Validated and recorded for API
        compatibility; every input is converted to NumPy whatever this names, so it does
        not change which inputs are accepted, where the arithmetic runs or what it returns.
        'cupy', 'jax' and 'torch' emit a RuntimeWarning saying so.
    device : str
        'cpu', 'cuda' or 'metal', validated by the same `resolve_device` the rest of the
        package uses -- an unknown name raises, and 'cuda' or 'metal' warns that jrsa
        computes on the CPU. `execution['device']` records the resolved device.
    n_jobs : int
        CPU workers. Default 1 (serial), the same default as everywhere else in the
        package; -1 means all cores. Opt in only when the serial work is large enough
        to repay the first parallel call, which costs several seconds because every
        worker imports this package before it can unpickle the callable. Measured one
        call per interpreter on a contended machine, `jrsa(x1, x2)` on a 40x6 input with
        the default 1000 permutations was 10x to 24x slower with `n_jobs=-1` than
        serial across repeated runs; the absolute seconds moved with the contention, the
        ordering did not. It starts to pay at roughly five seconds of serial work -- a
        400x60 input with 10000 permutations ran 10.8 s serial against 5.6 s on all
        cores. `n_jobs` never changes a number.
    batch_size : int or None
        Accepted and recorded in `parameters`; nothing is chunked. jrsa evaluates each
        metric over the whole array in one pass, and the helper that used to chunk had no
        callers -- across batch_size None, 1, 4, 32 and 10000 the value, p-value and
        interval are identical. `execution['batch_size']` records what ran, which is
        always None, on the same rule as `backend` and `device`: `parameters` carries the
        request, `execution` carries what happened.
    random_state : int or None
        Random seed for reproducibility, for both the permutation null and the bootstrap.
        May also be passed as ``seed``, the spelling used by the rest of the package;
        passing both is an error. Leaving it None seeds from OS entropy, so the p-value
        and confidence interval will differ between runs on identical input.
    return_type : str
        result | dict | matrix | value.
    return_null : bool
        Attach null distributions to result.
    return_input : bool
        Attach aligned inputs to result (useful for debugging).
    verbose : bool
        Print progress.
    **kwargs
        Metric-specific keyword arguments (for example ``sigma`` for ``metric='hsic'``,
        ``kernel`` for ``'cka'``, ``rdm_metric`` for ``'rsa'``, ``bins`` for
        ``'mutual_information'``). A keyword the chosen metric does not declare raises
        TypeError rather than being silently ignored.

    Returns
    -------
    JRSAResult
        Rich result object with .summary(), .plot(), .save().

    References
    ----------
    Kriegeskorte, N., et al. (2008). Representational similarity analysis: connecting the
    branches of systems neuroscience. Front. Syst. Neurosci. doi:10.3389/neuro.06.004.2008
    (``metric='rsa'``) -- dissimilarity matrices of correlation distance ("Step 2"),
    compared by Spearman rank correlation ("Step 4").
    Gretton, A., et al. (2005). Measuring statistical dependence with Hilbert-Schmidt
    norms. Lecture Notes in Computer Science. doi:10.1007/11564089_7 (``metric='hsic'``)
    -- the empirical HSIC ``(m - 1)**-2 tr(KHLH)`` of Definition 2, eq. 9, with a Gaussian
    kernel of width ``sigma``.
    Kornblith, S., et al. (2019). Similarity of neural network representations revisited.
    arXiv:1905.00414. doi:10.48550/arXiv.1905.00414 (``metric='cka'``) -- linear CKA,
    ``||Y'X||_F**2 / (||X'X||_F ||Y'Y||_F)`` on column-centered inputs (Table 1).
    Robert, P., & Escoufier, Y. (1976). A unifying tool for linear multivariate statistical
    methods: the RV-coefficient. Appl. Stat. doi:10.2307/2347233 (``metric='rv'``) -- the
    RV coefficient. On column-centered data it equals linear CKA (Kornblith et al. 2019,
    section 3), and the two metrics return the same number.
    Szekely, G. J., Rizzo, M. L., & Bakirov, N. K. (2007). Measuring and testing
    dependence by correlation of distances. Ann. Stat. doi:10.1214/009053607000000505
    (``metric='distance_correlation'``) -- the empirical distance correlation of
    Definitions 4 and 5, eqs. 2.8-2.10. The paper sets it to 0 when an input is constant;
    this returns NaN there.
    """
    t0 = time.perf_counter()

    # --- rng alias ------------------------------------------------------------
    # Because jrsa forwards **kwargs to the metric, and every metric swallows **kwargs,
    # a misspelled seed used to be accepted in silence and leave the parameter at None --
    # an entropy-seeded, irreproducible permutation test that still returned a plausible
    # p. Four repeated calls with seed=0 gave p = 0.2736, 0.3333, 0.2637, 0.2935; with the
    # parameter actually set they give 0.2189 four times. So every accepted spelling is
    # popped explicitly here, and two that disagree raise.
    #
    # `rng` is the canonical package-wide spelling. An earlier repair declared `seed` the
    # package-wide spelling; that was true of 7 functions against 8 spelling it `rng`, and
    # the argument now accepts a Generator as well as an int, which `seed` would misname.
    _given = "rng"
    for _alias in ("random_state", "seed"):
        if _alias in kwargs:
            _was_unset = isinstance(rng, Default)
            rng = resolve_seed_alias(rng, kwargs.pop(_alias), alias_name=_alias,
                                     func_name="jrsa", canonical_name=_given)
            if _was_unset:
                _given = _alias
    random_state = resolve_seed_alias(rng, Default(None), alias_name="seed",
                                      func_name="jrsa")

    # The tail applies to the parametric p as well as the permutation one, so it is checked
    # here rather than only where a permutation null is formed.
    _require_alternative(alternative)
    permutation_p = bool(stats and permutations > 0)
    if (alternative != "two-sided" and not permutation_p
            and str(metric).lower() in _UPPER_TAIL_PARAMETRIC_P):
        raise ValueError(
            f"jrsa: metric {metric!r} reports an upper-tail F-test p, which has no "
            f"{alternative!r} form; use alternative='two-sided', or a permutation null "
            "(stats=True, permutations > 0)."
        )

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
    # `device` used to be recorded verbatim, so `device='bogus_device'` ran and was
    # reported as the device, while all 15 `resolve_device` sites raise for the same
    # string. Routing it here makes jrsa refuse an unknown device like every other
    # function -- and tells us what actually runs, which is the CPU: every metric calls
    # `_ensure_np` on its first line, so an upload to cupy/torch/jax is converted straight
    # back and the computation is NumPy either way. `execution` now says so.
    resolved_device = resolve_device(
        None if str(device).strip().lower() == "auto" else device,
        context="jrsa", prefer="cupy", stacklevel=3,
    )
    if resolved_device == CUDA:
        # The resolver found a GPU, but jrsa will not use it: every metric calls
        # `_ensure_np` first. Saying so is the point -- `execution` used to record
        # `device: 'cuda'` for arithmetic that ran on the CPU.
        warnings.warn(
            "jrsa: device='cuda' was requested, but every jrsa metric computes in NumPy "
            "on the CPU. The result is unchanged and execution['device'] records 'cpu'.",
            RuntimeWarning,
            stacklevel=3,
        )
        resolved_device = CPU
    bk = _get_backend(backend, resolved_device)

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
    _LEGACY_JRSA_METRIC_NAMES = {
        "granger": "granger_ssr_ftest",
        "transfer_entropy": "transfer_entropy_histogram_nats",
    }
    metric_key = metric.lower()
    if metric_key in _LEGACY_JRSA_METRIC_NAMES:
        raise ValueError(
            f"jrsa metric '{metric}' was renamed to "
            f"'{_LEGACY_JRSA_METRIC_NAMES[metric_key]}' to reflect the actual estimand; "
            "connectivity.granger and connectivity.transfer_entropy are distinct "
            "directed estimators."
        )
    metric_fn = _METRIC_DISPATCH.get(metric_key)
    if metric_fn is None:
        raise ValueError(
            f"Unknown metric '{metric}'. "
            f"Choose from: {sorted(_METRIC_DISPATCH)}"
        )

    # Any remaining kwargs are forwarded to the metric, which swallows **kwargs and so
    # cannot reject a typo itself. Validate here instead: a misspelled metric option used
    # to be dropped in silence, and the caller got a default-parameter answer.
    _extra = set(kwargs) - _metric_kwargs(metric_fn)
    if _extra:
        _accepted = sorted(_metric_kwargs(metric_fn))
        raise TypeError(
            f"jrsa() got unexpected keyword argument(s) {sorted(_extra)} for "
            f"metric '{metric}'. That metric accepts: {_accepted or 'no extra options'}."
        )

    # Shuffle the axis the metric actually treats as observations. See
    # _OBSERVATION_AXIS_0_METRICS: for those, axis=-1 is the feature axis and shuffling it
    # is a no-op, which collapsed the null to a point mass and returned p = 1.0 always.
    perm_axis = 0 if metric_key in _OBSERVATION_AXIS_0_METRICS else -1

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
        if not permutation_p:
            p_raw = _one_sided_parametric_p(value, p_raw, alternative)

        if permutation_p:
            null_dist = _permutation_test(
                x1_lagged, x2_lagged, metric_fn, permutations, rng, axis=perm_axis, n_jobs=n_jobs, **kwargs
            )
            # The permutation p wins whenever it was computed. `if p_raw is None` let the
            # metric's own cell-wise parametric p pre-empt it, so `rsa`, `pearson`,
            # `spearman`, `kendall`, `phase_slope` and `granger_ssr_ftest` returned a p that
            # did not move between permutations=10 and permutations=2000 -- it was
            # `rdm_similarity(v1, v2, "spearman")[1]`, which rsa.py:167 states "is not a
            # valid test of RDM relatedness". The valid null was computed and discarded.
            p_parametric = p_raw
            p_raw = _p_from_null(value, null_dist, alternative)

        if bootstrap > 0:
            # `perm_axis`, not -1. The observation axis is axis 0 for the six metrics in
            # `_OBSERVATION_AXIS_0_METRICS`; resampling axis -1 there bootstrapped the
            # *features*, so the interval answered "how much does this depend on which
            # columns I measured" instead of "on which observations I sampled".
            ci = _bootstrap(
                x1_lagged, x2_lagged, metric_fn, bootstrap, rng, axis=perm_axis,
                n_jobs=n_jobs, **kwargs
            )

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
            if not permutation_p:
                p = _one_sided_parametric_p(v, p, alternative)
            val_list.append(v)
            stat_list.append(s)
            eff_list.append(e)
            p_list.append(p)
            df_list.append(d)
            
            nd = None
            c_val = None
            if permutation_p:
                nd = _permutation_test(
                    x1_lagged, x2_lagged, metric_fn, permutations, rng, axis=perm_axis, n_jobs=n_jobs, **kwargs
                )
                # See the single-lag branch: the permutation p wins when it exists.
                p = _p_from_null(v, nd, alternative)
                p_list[-1] = p
                null_dist_list.append(nd)
                
            if bootstrap > 0:
                c_val = _bootstrap(
                    x1_lagged, x2_lagged, metric_fn, bootstrap, rng, axis=perm_axis,
                    n_jobs=n_jobs, **kwargs
                )
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
    exec_meta = _make_exec_meta(bk, resolved_device, t0, random_state)

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
    # Shape before NaN policy. This guard used to live inside the `omit` branch, so the
    # other two policies skipped it and reached the per-metric `[:min(m1, m2)]`
    # truncations: (60, 6) against (40, 6) returned a statistic under nan_policy='raise'
    # and 'propagate' for metrics cka and procrustes, while the default 'omit' refused it.
    # The contract is the same whatever is done about NaN, so the check is too -- and this
    # is what makes those per-metric truncations genuinely unreachable and defensive only.
    if x2 is not None and tuple(x1.shape) != tuple(x2.shape):
        raise ValueError(
            f"x1 and x2 must have the same shape; got {tuple(x1.shape)} and "
            f"{tuple(x2.shape)}. jrsa compares paired observations, so neither the "
            f"observation count nor the feature count is truncated to match."
        )
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
    if align == "dtw":
        try:
            import dtw  # noqa: F401 — optional dependency: dtw-python
        except ImportError as exc:
            raise ImportError(
                "jrsa align='dtw' requires the optional 'dtw-python' package; "
                "install it or choose another align mode (e.g. 'downsample')."
            ) from exc
        raise NotImplementedError(
            "jrsa align='dtw' is reserved for a future DTW alignment path; "
            "use 'downsample', 'linear', or 'interpolate' today."
        )

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


#: Alignment algorithms `_resample_axis` implements. `'none'` and `'dtw'` are handled by
#: `_align_dimensions` before it gets here, so they are not members of this set.
ALIGN_MODES = ("auto", "downsample", "upsample", "nearest", "interpolate", "linear", "cubic")


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
    else:
        # The chain used to end here with no `else`, so an unrecognised `align` returned both
        # arrays untouched while `_align_dimensions` still appended the axis to `aligned_axes`
        # and `parameters['align']` echoed the request: a claim that an alignment happened,
        # over data that was never aligned.
        raise ValueError(
            f"jrsa: unrecognized align {align!r}. "
            f"Valid options: {list(ALIGN_MODES)}."
        )
    return x1, x2


#: Reductions `reduction={axis_name: op}` accepts. Written out rather than derived from the
#: dispatch below, so a value the dispatch cannot handle is not silently a valid request.
REDUCTION_OPS = ("mean", "median", "sum", "max", "min")


def _reduce_one(arr, op_str: str, ax: int):
    """Apply one named reduction along *ax*, on CPU or GPU."""
    xp = _get_xp(arr)
    if op_str == "mean":
        return xp.mean(arr, axis=ax, keepdims=True)
    if op_str == "median":
        if xp.__name__ == "cupy":
            try:
                return xp.median(arr, axis=ax, keepdims=True)
            except AttributeError:
                # The 50th percentile with linear interpolation *is* the median: the same
                # number by a different call, so the recorded 'median' stays true.
                return xp.percentile(arr, 50, axis=ax, keepdims=True)
        return np.median(arr, axis=ax, keepdims=True)
    if op_str == "sum":
        return xp.sum(arr, axis=ax, keepdims=True)
    if op_str == "max":
        return xp.max(arr, axis=ax, keepdims=True)
    if op_str == "min":
        return xp.min(arr, axis=ax, keepdims=True)
    # Unreachable: _reduce_dimensions validates first. Kept as a raise rather than a
    # fallthrough so the dispatch cannot regrow a default while the validator is edited.
    raise ValueError(f"jrsa: unhandled reduction {op_str!r}.")


def _reduce_dimensions(x1, x2, axis_map, reduction: dict):
    """Apply reductions (mean, median, …) along named axes on CPU or GPU."""
    for name, op_str in reduction.items():
        if op_str not in REDUCTION_OPS:
            # This used to fall through to `mean` while `parameters['reduction']` kept
            # echoing the request, so `reduction={'time': 'medain'}` returned a mean and was
            # recorded as a median. A typo in a reduction is not a preference to be
            # approximated -- the same principle as the correction method above.
            raise ValueError(
                f"jrsa: unrecognized reduction {op_str!r} for axis {name!r}. "
                f"Valid options: {list(REDUCTION_OPS)}."
            )
        ax = axis_map.get(name)
        if ax is None:
            continue
        x1 = _reduce_one(x1, op_str, ax)
        if x2 is not None:
            x2 = _reduce_one(x2, op_str, ax)
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
            # A constant row is exactly 0, decided by exact equality; the 1e-12 offset an
            # earlier version used biased the scale of small-amplitude rows.
            arr = zscore(arr, axis=-1, ignore_nan=True, xp=xp)
        if normalize:
            lo = xp.nanmin(arr, axis=-1, keepdims=True)
            hi = xp.nanmax(arr, axis=-1, keepdims=True)
            arr = (arr - lo) / xp.where(hi > lo, hi - lo, 1.0)
        return arr
    return _prep(x1), _prep(x2)


def _make_windows(x1, x2, axis_map, window, sliding):
    """Extract window or build sliding windows.

    `window` is in sample indices along the aligned axis. The clamping below used to be
    silent in both directions: `(-500, 500)` on a 6-sample axis became `(0, 6)` -- the
    whole axis, so a caller who believed they had windowed got the unwindowed answer --
    and `(10, 30)` became an empty slice that produced a NaN statistic rather than an
    error. Both now say what happened.
    """
    if window is None:
        return x1, x2, None
    ax = axis_map.get("aligned", axis_map.get(list(axis_map.keys())[0], -1))
    n = x1.shape[ax]
    if isinstance(window, (int, float)):
        half = int(window) // 2
        center = n // 2
        start, stop = max(0, center - half), min(n, center + half)
    else:
        requested = (int(window[0]), int(window[1]))
        start, stop = requested
        if start < 0:
            start = max(0, n + start)
        if stop < 0:
            stop = max(0, n + stop)
        stop = min(stop, n)
        if start >= stop:
            raise ValueError(
                f"jrsa: window={window!r} selects no samples of the {n}-sample aligned "
                f"axis (resolved to [{start}, {stop})). `window` is in sample indices, "
                "not milliseconds."
            )
        if (start, stop) == (0, n) and requested != (0, n):
            warnings.warn(
                f"jrsa: window={window!r} covers the whole {n}-sample aligned axis after "
                "clamping, so no windowing was applied. `window` is in sample indices, "
                "not milliseconds.",
                RuntimeWarning,
                stacklevel=3,
            )
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


def _metric_kwargs(metric_fn):
    """The keyword options a metric actually declares, excluding its **kwargs catch-all."""
    import inspect

    return {
        name
        for name, param in inspect.signature(metric_fn).parameters.items()
        if param.kind is param.KEYWORD_ONLY
        or (param.kind is param.POSITIONAL_OR_KEYWORD and param.default is not param.empty)
    } - {"axis"}


def _permutation_test(x1, x2, metric_fn, n_perm, rng, axis=-1, n_jobs=1, **kwargs):
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
        seeds = rng.integers(0, 2**31 - 1, size=n_perm)
        for seed in seeds:
            local_rng = np.random.default_rng(int(seed))
            idx = cp.asarray(local_rng.permutation(n))
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

    null = parallel_map(_run_single_perm, seeds, n_jobs=n_jobs)
    return np.asarray(null)


#: Tail specifications `alternative=` accepts, written out rather than derived from the
#: dispatch in `_p_from_null`.
ALTERNATIVES = ("two-sided", "greater", "less")

#: Metrics whose parametric p is an upper-tail test of a non-negative statistic rather than
#: a two-sided test of a signed one, so a one-sided p cannot be formed from it by halving.
_UPPER_TAIL_PARAMETRIC_P = frozenset({"granger_ssr_ftest"})


def _require_alternative(alternative):
    if alternative not in ALTERNATIVES:
        # This chain used to end in a bare `else` computing the *less* tail, so an
        # unrecognised alternative -- including the case variant 'GREATER' -- returned the
        # left-tail p-value while `parameters['alternative']` echoed the request. A one-sided
        # test asked for in the wrong case came back as p = 1.0 where the right answer was
        # 0.005. Same principle as the correction method and the reduction: a request the
        # dispatch does not recognise is not a request to be approximated.
        raise ValueError(
            f"jrsa: unrecognized alternative {alternative!r}. "
            f"Valid options: {list(ALTERNATIVES)} (lowercase)."
        )


def _one_sided_parametric_p(value, p, alternative):
    """One-sided p from a metric's two-sided parametric p: ``p / 2`` when ``value`` lies on
    the requested side, ``1 - p / 2`` otherwise, and NaN where ``value`` is not finite."""
    if p is None or alternative == "two-sided":
        return p
    if hasattr(value, "get"):
        value = value.get()
    v = np.asarray(value, dtype=np.float64)
    p2 = np.asarray(p, dtype=np.float64)
    on_side = v > 0 if alternative == "greater" else v < 0
    out = np.where(np.isfinite(v), np.where(on_side, p2 / 2.0, 1.0 - p2 / 2.0), np.nan)
    return np.float64(out) if out.ndim == 0 else out


def _p_from_null(value, null_dist, alternative):
    """Compute p-value from null distribution.

    Returns NaN when the observed statistic or the whole null is non-finite. Comparisons
    against NaN are all False, so the exceedance count was 0 and the p-value came out at
    its own floor, ``1/(n+1)`` -- the *most* significant value the test can emit. A
    constant input against a Gaussian one reported ``value: nan, p: 0.000999``.

    Returns a 0-d array, matching `value`, `statistic` and `effect`. This used to return
    `np.atleast_1d(...)`, a shape-``(1,)`` array, for a result whose every other field was
    0-d: one scalar p-value wrapped in a length-1 axis. Under
    NumPy>=2 -- the floor `pyproject.toml` declares -- `float()` on that array raises
    `TypeError`, so the documented quickstart line
    ``float(jrsa_res.p)`` did not run. This function reduces `value` to a single
    scalar `obs` before it counts anything, so it has no vector-valued case to preserve;
    a vector-valued `p` still arises where it is real, from `_stack_lags` over multiple
    lags, which now yields shape ``(n_lags,)`` and so matches `value` there too instead
    of the former ``(n_lags, 1)``.
    """
    _require_alternative(alternative)
    if hasattr(value, "get"):
        value = value.get()
    obs = float(np.mean(value)) if isinstance(value, np.ndarray) else float(value)
    null_dist = np.asarray(null_dist)
    n = len(null_dist)
    if not np.isfinite(obs) or n == 0 or not np.any(np.isfinite(null_dist)):
        return np.asarray(np.nan, dtype=np.float64)
    if alternative == "two-sided":
        k = int(np.sum(np.abs(null_dist) >= np.abs(obs)))
    elif alternative == "greater":
        k = int(np.sum(null_dist >= obs))
    else:
        k = int(np.sum(null_dist <= obs))
    p = (1 + k) / (n + 1)
    return np.asarray(p, dtype=np.float64)


def _bootstrap(x1, x2, metric_fn, n_boot, rng, axis=-1, n_jobs=1, **kwargs):
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
        seeds = rng.integers(0, 2**31 - 1, size=n_boot)
        for seed in seeds:
            local_rng = np.random.default_rng(int(seed))
            idx = cp.asarray(local_rng.integers(0, n, size=n))
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

    boot_vals = parallel_map(_run_single_boot, seeds, n_jobs=n_jobs)
    boot_arr = np.asarray(boot_vals)
    ci = np.percentile(boot_arr, [2.5, 97.5])
    return ci


# Every accepted value of `correction`, and the `statsmodels` method it runs. `None` means
# no correction. 'none' is a key here rather than a special case outside the map so that the
# accepted set has one home: while it was absent, `.get('none', 'fdr_bh')` returned
# Benjamini-Hochberg q-values under the label 'none'.
_CORRECTION_METHOD_MAP = {
    "none": None,
    "fdr_bh": "fdr_bh", "fdr_by": "fdr_by",
    "bonferroni": "bonferroni", "holm": "holm",
    "holm-sidak": "holm-sidak",
}


def _multiple_correction(p: np.ndarray, method: str, alpha: float) -> np.ndarray:
    """Apply multiple-comparison correction; returns q-values.

    ``method='none'`` applies no correction: the q-values are the p-values, as float64.
    """
    p_flat = np.asarray(p).ravel()
    m_lower = method.lower()
    if m_lower not in _CORRECTION_METHOD_MAP:
        # This used to warn and fall back to 'fdr_bh' while `parameters['correction']`
        # kept echoing the request, so a run corrected one way was recorded as corrected
        # another. A typo in a correction method is not a preference to be approximated.
        raise ValueError(
            f"Unrecognized correction method {method!r}. "
            f"Valid options: {sorted(_CORRECTION_METHOD_MAP.keys())}."
        )
    sm_method = _CORRECTION_METHOD_MAP[m_lower]
    if sm_method is None:
        # Returns before the `statsmodels` import: asking for no correction must not
        # require the library that does correction.
        return np.array(p, dtype=np.float64)
    try:
        from statsmodels.stats.multitest import multipletests
        _, q, _, _ = multipletests(p_flat, alpha=alpha, method=sm_method)
    except ImportError as exc:
        # `statsmodels` is a hard dependency, so this runs only where a declared
        # dependency is missing. It used to route every method but 'bonferroni' to
        # Benjamini-Hochberg while `parameters['correction']` kept echoing the request:
        # a 'holm' run was recorded as 'holm' and was in fact 'fdr_bh'. Same principle as
        # the unrecognised-method branch above -- an estimator that cannot run is not a
        # licence to return a differently-computed number under the requested label.
        #
        # 'bonferroni' keeps its fallback because it is not a substitution: p*m clipped
        # at 1 is Bonferroni, and it reproduces `multipletests(method='bonferroni')`
        # exactly, so the recorded label stays true.
        if m_lower == "bonferroni":
            # `float(...)`, not `len(...)`: an integer p-array times a Python int keeps the
            # array's integer dtype, and the product then overflows a narrow one. The
            # float multiplier reproduces `multipletests(method='bonferroni')` for every
            # input dtype, and is bit-identical to the int multiplier for float input.
            q = np.minimum(p_flat * float(len(p_flat)), 1.0)
        else:
            raise ImportError(
                f"jrsa correction={method!r} requires 'statsmodels', which is a declared "
                f"dependency of jnwb and could not be imported. Install it "
                f"(pip install 'statsmodels>=0.14.0'), or pass correction='bonferroni', "
                f"which jnwb computes without it."
            ) from exc
    return q.reshape(np.asarray(p).shape)


# ===========================================================================
# PRIVATE – execution / backend
# ===========================================================================

_VALID_BACKENDS = ("auto", "numpy", "scipy", "cupy", "jax", "torch")
#: The backends that name an accelerator library jrsa does not compute with.
_ACCELERATOR_BACKENDS = ("cupy", "jax", "torch")


def _get_backend(backend: str, device: str) -> dict:
    """Validate the requested backend and report the one that executes.

    Every metric converts its inputs with `_ensure_np` before it computes anything, so
    the executing backend is NumPy whatever was requested. This used to report the
    *request*: `jrsa(device='cuda', backend='cupy')` recorded
    `{'backend': 'cupy', 'device': 'cuda'}` for arithmetic that ran on the CPU, and
    `_autodetect_backend` picked a name from what happened to be importable, which
    likewise changed the record and nothing else. `parameters['backend']` still carries
    what the caller asked for; `execution['backend']` now carries what ran.

    Naming an accelerator library is a request that is not delivered, so it is announced
    the way a denied ``device='cuda'`` is.
    """
    requested = str(backend).strip().lower()
    if requested not in _VALID_BACKENDS:
        raise ValueError(
            f"jrsa: unrecognised backend {backend!r}; expected one of "
            f"{sorted(_VALID_BACKENDS)}."
        )
    if requested in _ACCELERATOR_BACKENDS:
        warnings.warn(
            f"jrsa: backend={requested!r} was requested, but every jrsa metric computes in "
            f"NumPy on the CPU; execution['backend'] records 'numpy'.",
            RuntimeWarning,
            stacklevel=3,
        )
    return {"name": "numpy", "requested": requested, "device": device}


def _to_backend(arr, backend_ctx: dict) -> np.ndarray:
    """Convert one input to a float64 NumPy array on the host, or raise.

    Dispatch is by type, never by attribute: an ndarray's `.data` is a raw buffer, a CuPy
    array's is a device pointer and a sparse matrix's is its stored non-zeros, so taking
    `.data` from anything that has one returned a wrong array or raised. Accepted: NumPy
    arrays and array-likes, scipy.sparse (densified), torch tensors on any device
    (detached, copied to host), CuPy arrays (copied to host), JAX arrays, and a container
    without `__array__` whose `.data` is one of these (a pynwb TimeSeries). A masked array
    with a masked element raises, because no metric honours a mask.

    jrsa is a NumPy estimator; `backend` and `device` are validated and recorded, and
    change no number.
    """
    if isinstance(arr, np.ma.MaskedArray):
        if np.ma.getmaskarray(arr).any():
            raise TypeError(
                "jrsa: a masked array with masked elements was passed, and no jrsa metric "
                "honours a mask; converting it would compute on the masked values. Drop "
                "or impute them first."
            )
        arr = np.ma.getdata(arr)
    if isinstance(arr, np.ndarray):
        return np.asarray(arr, dtype=np.float64)
    library = type(arr).__module__.split(".")[0]
    if library == "scipy":
        import scipy.sparse
        if scipy.sparse.issparse(arr):
            return np.asarray(arr.toarray(), dtype=np.float64)
    if library == "torch":
        return arr.detach().cpu().double().numpy()
    if library == "cupy":
        return np.asarray(arr.get(), dtype=np.float64)
    if hasattr(arr, "__array__") or isinstance(arr, (list, tuple)) or np.isscalar(arr):
        return np.asarray(arr, dtype=np.float64)
    if hasattr(arr, "data"):
        return _to_backend(arr.data, backend_ctx)
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
            except (RuntimeError, TypeError, ValueError):
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
            b = y2.ravel() if y2.ndim > 1 else y2
            if len(a) != len(b):
                raise ValueError(
                    f"_pearson: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
                )
            n = len(a)
            # CuPy correlation calculation
            a_mean = cp.mean(a)
            b_mean = cp.mean(b)
            a_std = cp.std(a)
            b_std = cp.std(b)
            # NaN for a constant vector, as on the CPU path, decided by exact equality: cp.std
            # of 100 values of 2.7 is 4.4e-16. The absolute cutoff and offset an earlier
            # version used reported 0.0 there and shrank r at small amplitude.
            if is_constant(a, xp=cp) or is_constant(b, xp=cp):
                r = cp.array(cp.nan)
            else:
                r = cp.mean((a - a_mean) * (b - b_mean)) / (a_std * b_std)
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
    if len(a) != len(b):
        raise ValueError(
            f"_pearson: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
        )
    n = len(a)
    from jnwb.statistics import StatisticalAnalysis
    res = StatisticalAnalysis.exploratory_correlate(a, b)
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
            b = y2.ravel() if y2.ndim > 1 else y2
            if len(a) != len(b):
                raise ValueError(
                    f"_spearman: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
                )
            # Average ranks for ties, as scipy.stats.spearmanr does on the CPU path. The double
            # argsort this replaces broke ties by position, so tied data gave a different rho on
            # the GPU and a constant vector got distinct ranks instead of an undefined result.
            from scipy.stats import rankdata
            a_rank = cp.asarray(rankdata(cp.asnumpy(a)))
            b_rank = cp.asarray(rankdata(cp.asnumpy(b)))
            n = len(a)
            a_mean = cp.mean(a_rank)
            b_mean = cp.mean(b_rank)
            a_std = cp.std(a_rank)
            b_std = cp.std(b_rank)
            if float(a_std) == 0.0 or float(b_std) == 0.0:
                rho = cp.array(cp.nan)
            else:
                rho = cp.mean((a_rank - a_mean) * (b_rank - b_mean)) / (a_std * b_std)
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
    if len(a) != len(b):
        raise ValueError(
            f"_spearman: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
        )
    n = len(a)
    from jnwb.statistics import StatisticalAnalysis
    res = StatisticalAnalysis.exploratory_correlate(a, b)
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
    if len(a) != len(b):
        raise ValueError(
            f"_kendall: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
        )
    tau, p = kendalltau(a, b)
    return np.float64(tau), np.float64(tau), np.float64(abs(tau)), np.float64(p), None


def _cosine(x1, x2, axis=-1, **kwargs):
    try:
        import cupy as cp
        if isinstance(x1, cp.ndarray) or (x2 is not None and isinstance(x2, cp.ndarray)):
            a = x1.ravel()
            y2 = x2 if x2 is not None else x1
            b = y2.ravel()
            if len(a) != len(b):
                raise ValueError(
                    f"_cosine: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
                )
            na, nb = float(cp.linalg.norm(a)), float(cp.linalg.norm(b))
            sim = cp.dot(a / na, b / nb) if na > 0 and nb > 0 else cp.array(cp.nan)
            return sim, sim, cp.abs(sim), None, None
    except ImportError:
        pass

    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    a = x1.ravel()
    b = x2.ravel()
    if len(a) != len(b):
        raise ValueError(
            f"_cosine: vector length mismatch (len(x1)={len(a)}, len(x2)={len(b)})"
        )
    # Undefined (NaN) for a zero vector. The 1e-12 offset this replaces reported 0.0 there
    # and biased small-amplitude inputs.
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    sim = np.dot(a / na, b / nb) if na > 0 and nb > 0 else np.nan
    return np.float64(sim), np.float64(sim), np.float64(abs(sim)), None, None


def _rsa(x1, x2, axis=-1, rdm_metric="correlation", **kwargs):
    """Representational similarity analysis via condensed RDM correlation (delegating to jnwb.rsa).

    A distance undefined for some condition pair (correlation distance of a zero-variance
    row) makes the similarity NaN, which is what the pre-delegation `pdist` + `spearmanr`
    implementation returned.
    """
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from .rsa import _condensed_distances, rdm_similarity
    v1 = _condensed_distances(x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1), rdm_metric)
    v2 = _condensed_distances(x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1), rdm_metric)
    if not (np.all(np.isfinite(v1)) and np.all(np.isfinite(v2))):
        nan = np.float64(np.nan)
        return nan, nan, nan, nan, None
    rho, p = rdm_similarity(v1, v2, metric="spearman")
    return np.float64(rho), np.float64(rho), np.float64(abs(rho)), np.float64(p), None


def _cka(x1, x2, axis=-1, kernel="linear", **kwargs):
    """Centered Kernel Alignment optimized for linear complexity O(md^2) when d << m."""
    # The linear-kernel identity below is what makes this O(m*d1*d2) rather than O(m^3);
    # it is not a Gram matrix that a kernel could be substituted into. `kernel='rbf'` and
    # `kernel='nonsense_kernel'` were both accepted and both returned the linear answer.
    if kernel != "linear":
        raise NotImplementedError(
            f"jrsa(metric='cka') implements the linear kernel only; got kernel={kernel!r}. "
            "The linear form is computed in closed form, not from an explicit Gram matrix, "
            "so another kernel cannot be substituted. Use metric='hsic' for a kernel CKA."
        )
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
    # CKA is invariant to scaling either input, so normalise first. The ratio used to carry a
    # 1e-12 offset under a quantity that scales as amplitude^8, which drove CKA toward 0 for
    # small-amplitude inputs (0.72 -> 0.08 at 1e-3 scale) and reported 0.0 for a constant one.
    nx, ny = np.linalg.norm(X_c), np.linalg.norm(Y_c)
    if nx == 0 or ny == 0:
        nan = np.float64(np.nan)
        return nan, nan, nan, None, None
    X_c = X_c / nx
    Y_c = Y_c / ny
    cross = X_c.T @ Y_c
    num = np.sum(cross ** 2)
    
    # Denominators are ||X_c.T @ X_c||_F^2 and ||Y_c.T @ Y_c||_F^2
    denom_x = np.sum((X_c.T @ X_c) ** 2)
    denom_y = np.sum((Y_c.T @ Y_c) ** 2)
    
    cka_val = num / np.sqrt(denom_x * denom_y)
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
    # The RV coefficient is defined on column-centred matrices, exactly as _cka centres
    # above. Without centring the Gram matrices are dominated by the common mean, so any
    # two representations sharing an offset look identical: two independent Gaussian
    # samples shifted by +50 returned RV = 1.0000, and independent zero-mean samples
    # returned 0.16 where the centred value is the small-sample floor.
    X = X - X.mean(axis=0, keepdims=True)
    Y = Y - Y.mean(axis=0, keepdims=True)

    # RV is invariant to scaling either input; normalise first (see _cka).
    nx, ny = np.linalg.norm(X), np.linalg.norm(Y)
    if nx == 0 or ny == 0:
        nan = np.float64(np.nan)
        return nan, nan, nan, None, None
    X = X / nx
    Y = Y / ny
    C_xy = X.T @ Y
    num = np.sum(C_xy ** 2)
    
    C_xx = X.T @ X
    C_yy = Y.T @ Y
    denom_x = np.sum(C_xx ** 2)
    denom_y = np.sum(C_yy ** 2)
    
    rv = num / np.sqrt(denom_x * denom_y)
    return np.float64(rv), np.float64(rv), np.float64(rv), None, None


def _hsic(x1, x2, axis=-1, sigma=1.0, **kwargs):
    """Hilbert-Schmidt Independence Criterion with efficient centering.
    Avoids explicit dense centering matrix allocation.
    Assumes symmetric kernels (like the default Gaussian RBF) such that K^T = K
    and trace(Kx @ Ky) = sum(Kx * Ky).
    """
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    from scipy.spatial.distance import cdist
    # Both sides need the same (n_samples, n_features) shape: cdist rejects anything else, and
    # flattening only x1 made every non-2-D call fail on x2 instead.
    X = x1 if x1.ndim == 2 else x1.reshape(x1.shape[0], -1)
    Y = x2 if x2.ndim == 2 else x2.reshape(x2.shape[0], -1)
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
    # Undefined (NaN) when every row of an input is identical. The 1e-12 offset this replaces
    # reported 0.0 there and biased small-amplitude inputs.
    dc = dcov_xy / np.sqrt(dcov_xx * dcov_yy) if dcov_xx > 0 and dcov_yy > 0 else np.nan
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


def _grangercausalitytests_compat(data, maxlag):
    """Call statsmodels grangercausalitytests across versions with/without ``verbose``."""
    import inspect

    from statsmodels.tsa.stattools import grangercausalitytests

    kwargs = {"maxlag": maxlag}
    if "verbose" in inspect.signature(grangercausalitytests).parameters:
        kwargs["verbose"] = False
    return grangercausalitytests(data, **kwargs)


def _granger(x1, x2, axis=-1, max_lag=5, **kwargs):
    """Granger causality F-statistic (x2 → x1) with best lag selection by AIC."""
    x1, x2 = _ensure_np(x1, x2 if x2 is not None else x1)
    try:
        a = x1.ravel()
        b = x2.ravel()[:len(a)]
        data = np.column_stack([a, b])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = _grangercausalitytests_compat(data, maxlag=max_lag)
        
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
            except (IndexError, KeyError, AttributeError, TypeError) as exc:
                warnings.warn(
                    f"Granger AIC extraction failed at lag {lag}: {exc}; skipping lag",
                    stacklevel=2,
                )
        
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
    # PSI delegates to jnwb.connectivity's segmented estimator.
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


#: Metrics that consume whole representations rather than paired observations along the
#: last axis. Each reshapes its inputs to (n_observations, n_features) and ignores `axis`
#: entirely, so observations lie on axis 0.
#:
#: This matters for the permutation null. `_permutation_test` shuffled axis=-1 for every
#: metric, which for these is the FEATURE axis -- and all of them are invariant to a
#: permutation of features, because a column permutation is an orthogonal transform and
#: these are all orthogonally invariant. Every permuted value therefore equalled the
#: observed one and the null was a point mass, so p came back as exactly 1.0 regardless of
#: the data. Measured on independent 60 x 12 Gaussian representations, `cka`, `rv`, `hsic`,
#: `distance_correlation` and `procrustes` all reported p = 1.0000.
_OBSERVATION_AXIS_0_METRICS = frozenset({
    "cka", "rv", "hsic", "distance_correlation", "procrustes", "rsa",
})

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
    "granger_ssr_ftest": _granger,
    "transfer_entropy_histogram_nats": _transfer_entropy,
    "phase_slope": _phase_slope,
}


# ===========================================================================
# PRIVATE – result helpers
# ===========================================================================

def _make_exec_meta(backend_ctx, device, t0, random_state):
    """`seed` is the `random_state` that was used, so it can be fed back.

    It used to be `rng.bit_generator.state['state']['state']` -- the 128-bit internal
    counter, e.g. 69277902251545625047243999639177715869 for `random_state=7`. That is a
    faithful record of the generator's position and a useless one for reproduction:
    passing it back as `random_state` seeds a different stream. `None` is recorded as
    None, which is the honest answer for a run seeded from OS entropy and, per the
    `random_state` docstring, one that will not reproduce.
    """
    seed_val = random_state
    return {
        "backend": backend_ctx.get("name", "numpy"),
        "device": device,
        # None means one pass over the whole array, which is always: jrsa does not chunk,
        # whatever `parameters['batch_size']` asked for.
        "batch_size": None,
        "runtime": time.perf_counter() - t0,
        "memory": None,
        "seed": seed_val,
    }


class _ScalarPValue(np.ndarray):
    """0-d float array that still answers ``[0]``, with a `FutureWarning`, until 0.2.7.

    `p` and `q` of a single-lag result used to be shape ``(1,)`` and are now 0-d like
    `value`. A 0-d array raises `IndexError` on ``[0]``, which would break code written
    against the old shape without notice. This view returns the scalar ``self[()]`` for
    ``[0]`` and changes nothing else: every other index is the base ndarray's, and ufuncs
    and NumPy functions receive a plain ndarray, so ``p * 2``, ``p < 0.05`` and
    ``np.isnan(p)`` return exactly what they return for a plain 0-d array (a NumPy scalar).
    It pickles as a plain ndarray, so a stored result does not depend on this class, which
    0.2.7 removes.
    """

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        if "out" in kwargs:
            kwargs["out"] = _plain_arrays(kwargs["out"])
        return getattr(ufunc, method)(*_plain_arrays(inputs), **kwargs)

    def __array_function__(self, func, types, args, kwargs):
        return super().__array_function__(
            func, (np.ndarray,), _plain_arrays(args), _plain_arrays(kwargs)
        )

    def __getitem__(self, key):
        if (
            self.ndim == 0
            and isinstance(key, (int, np.integer))
            and not isinstance(key, (bool, np.bool_))
            and key == 0
        ):
            field_name = getattr(self, "_field_name", "p")
            warnings.warn(
                f"JRSAResult.{field_name} is 0-d; indexing it with [0] is deprecated and "
                f"raises IndexError in 0.2.7. Use float(result.{field_name}) or "
                f"result.{field_name}[()].",
                FutureWarning,
                stacklevel=2,
            )
            return super().__getitem__(())
        return super().__getitem__(key)

    def __repr__(self):
        return repr(self.view(np.ndarray))

    def __reduce_ex__(self, protocol):
        return np.asarray(self).__reduce_ex__(protocol)


def _plain_arrays(obj):
    """Replace every `_ScalarPValue` in a (nested) tuple, list or dict with a plain view."""
    if isinstance(obj, _ScalarPValue):
        return obj.view(np.ndarray)
    if isinstance(obj, tuple):
        return tuple(_plain_arrays(o) for o in obj)
    if isinstance(obj, list):
        return [_plain_arrays(o) for o in obj]
    if isinstance(obj, dict):
        return {k: _plain_arrays(v) for k, v in obj.items()}
    return obj


def _scalar_p_value(a, field_name):
    """Wrap a 0-d p-value array in `_ScalarPValue`; anything else is returned unchanged."""
    if a is None or np.ndim(a) != 0:
        return a
    out = np.asarray(a).view(_ScalarPValue)
    out._field_name = field_name
    return out


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
        p=_scalar_p_value(_to_numpy(p), "p"),
        q=_scalar_p_value(_to_numpy(q), "q"),
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
