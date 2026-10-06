"""
jnwb.jrsa – Unified Representational Similarity Analysis

Public API: exactly one function.

    >>> import jnwb
    >>> result = jnwb.jrsa(x1, x2, metric="rsa", stats=True, null="iid")
    >>> result.summary()
    >>> result.plot()

"""

from __future__ import annotations

import numbers
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from .._backend import CPU, CUDA, resolve_device
from .._parallel import parallel_map
from .._rng import Default, RNGLike, resolve_rng, resolve_seed_alias
from .._spread import is_constant, zscore
from ..permutation import _count_at_least_as_extreme

from ._result import (
    JRSAResult,
    _make_exec_meta,
    _make_result,
    _result_summary,
    _result_plot,
    _result_save,
)
from ._backends import (
    _get_xp,
    _VALID_BACKENDS,
    _ACCELERATOR_BACKENDS,
    _get_backend,
    _to_backend,
    _ensure_np,
)
from ._metrics import (
    _pearson,
    _spearman,
    _kendall,
    _cosine,
    _rsa,
    _cka,
    _rv,
    _hsic,
    _distance_correlation,
    _mutual_information,
    _procrustes,
    _grangercausalitytests_compat,
    _granger,
    _require_one_series,
    _require_paired_shape,
    _entropy,
    _transfer_entropy,
    _phase_slope,
    _OBSERVATION_AXIS_0_METRICS,
    _METRIC_DISPATCH,
)
from ._stages import (
    _prepare_inputs,
    _validate_inputs,
    _is_axis_index,
    _standardize_dimensions,
    _align_dimensions,
    ALIGN_MODES,
    _resample_axis,
    REDUCTION_OPS,
    _reduce_one,
    _reduce_dimensions,
    _refuse_an_adim_the_resampling_ignores,
    _window_axis_name,
    _drop_reduced_observation_axis,
    _apply_preprocessing,
    _make_windows,
    _apply_lag,
    _metric_kwargs,
)
from ._inference import (
    NULL_SCHEMES,
    _require_null,
    _null_index,
    _check_null_axis,
    _permutation_test,
    ALTERNATIVES,
    _UPPER_TAIL_PARAMETRIC_P,
    _require_alternative,
    _one_sided_parametric_p,
    _p_from_null,
    _bootstrap,
    _CORRECTION_METHOD_MAP,
    _multiple_correction,
)


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
    null=None,
    block_len=None,
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
        Aligned dimension(s). Default -1. It steers alignment, `reduction` (axes named
        here) and `window`. Nothing downstream follows it: the paired metrics pair samples
        and resample the last axis, the observation-axis metrics resample axis 0 (see
        `null`), and `lag` shifts the axis the metric treats as observations, comparing the
        overlap only. So an `adim` other than the default that does not name that axis
        raises ValueError when a permutation null, `bootstrap` or a nonzero `lag` is used:
        ``adim=0`` with pearson on a 2-D input would return the result of ``adim=-1``.
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
        Each key names an axis of `adim`: a label, ``"axis_<d>"`` for an unlabelled int
        `d` of a tuple (``adim=(-3, -2)`` gives ``"axis_-3"`` and ``"axis_-2"``), or
        ``"aligned"`` for a single int. Any other key raises.
        A reduced axis stays at length 1, except axis 0 for rsa, cka, rv, hsic,
        distance_correlation and procrustes: that axis is removed, so averaging the trials
        of a (trials, conditions, units) input compares conditions, as ``x.mean(0)`` would.
        `lag`, the null and `window` then number the axes of the reduced input, and a
        `window` on the removed axis raises. `result.axes` keeps the input's numbering.
        ``nan_policy='omit'`` acts on the input's axis 0 (the trials) before the reduction:
        a NaN drops its whole trial, so the result differs from ``nanmean`` over trials, and
        a condition that is NaN in every trial leaves no trial and raises. `bootstrap`, like
        the null, resamples the reduced input's axis 0 (the conditions).
    metric : str
        Similarity metric.  One of: pearson, spearman, kendall, cosine,
        rsa, cka, rv, hsic, distance_correlation, mutual_information,
        procrustes, granger_ssr_ftest, transfer_entropy_histogram_nats, phase_slope.
        The SSR F-test and histogram TE metrics are distinct from connectivity
        ``granger`` and ``transfer_entropy``.
        Direction of the directed metrics: ``granger_ssr_ftest`` and
        ``transfer_entropy_histogram_nats`` measure x2 -> x1 (how much x2's past predicts
        x1), the reverse of ``jnwb.granger(X, Y).x_to_y``; ``phase_slope`` is positive
        when x1 leads x2, as ``jnwb.phase_slope_index(x, y).x_to_y`` is when x leads y.
    lag : int | tuple | array-like
        Temporal lag(s) in samples. A lag of l pairs x1[t] with x2[t - l] along the axis the
        metric treats as observations, whatever `adim` names: the last axis for the paired
        metrics, axis 0 for rsa, cka, rv, hsic, distance_correlation and procrustes (the axes
        of `null`). Only the overlap is compared, so each lag drops |l| samples, and the
        null and bootstrap act on that shortened series; `execution['n_overlap']` records
        the samples used (a list for several lags). |l| must be below the axis length. The
        lag used to be circular, which paired each series' end with its start.
    window : tuple | int or None
        Analysis window as **sample indices** along the aligned axis: ``(start, stop)``,
        half-open, with negative values counted from the end as in Python slicing, or an
        integer width centred on the axis. This is not a time -- `jrsa` takes no sampling
        rate and cannot convert one. The docstring used to read "e.g. (-500, 500) ms",
        which on a 6-sample axis clamped to the whole axis and returned the unwindowed
        answer with no warning. For rsa, cka, rv, hsic, distance_correlation and procrustes
        at the default ``adim=-1`` the aligned axis is the last, the features, while `lag`
        and the null act on axis 0, the observations: ``jrsa(x, y, metric='cka',
        window=(0, 20))`` on (200, 40) input keeps 20 of the 40 features and all 200
        observations. To window the observations, pass ``adim=0``.
    sliding : bool
        Only ``False`` is supported. ``True`` raises NotImplementedError: it used to be
        accepted and ignored. For a sliding-window analysis, call ``jrsa`` once per
        window, e.g. ``[jrsa(x1, x2, window=(s, s + w)) for s in range(0, n - w + 1, step)]``.
    normalize : bool
        Normalise each input to [0, 1].
    standardize : bool
        Z-score each input along the last axis; a constant row becomes 0.
    detrend : bool
        Linear-detrend each input.
    nan_policy : str
        omit | raise | propagate. ``'omit'`` drops every observation that is NaN anywhere:
        a sample of the last axis for the paired metrics, a row of axis 0 for rsa, cka, rv,
        hsic, distance_correlation and procrustes (the axes of `null`). An input with no
        observations left raises ValueError for every metric.
    stats : bool
        Compute inferential statistics.
    permutations : int
        Permutation count for null distribution.
    bootstrap : int
        Bootstrap iterations for confidence intervals. The bootstrap resamples single
        samples of the permuted axis (see `null`). For the paired metrics, ``bootstrap > 0``
        raises unless ``null='iid'`` is named, declaring the samples exchangeable: on
        autocorrelated data single-sample resampling undercovers, and on independent AR(1)
        pairs with coefficient 0.9 the 95% interval of pearson covered 0 for 0.475 of pairs.
        No block bootstrap is implemented.
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
        upper-tail F-test of a non-negative F, which has no side to halve on, so that metric
        raises for a one-sided alternative without a permutation null.
    null : {None, 'circular_shift', 'block', 'iid'}
        How each permutation resamples x2 along the permuted axis; anything else raises.
        The permuted axis is the last axis for the paired metrics -- pearson, spearman,
        kendall, cosine, mutual_information, granger_ssr_ftest,
        transfer_entropy_histogram_nats and phase_slope -- and axis 0, the observations, for
        rsa, cka, rv, hsic, distance_correlation and procrustes. The last axis is the
        aligned axis only at the default ``adim=-1``: for the paired metrics the null and
        `lag` act on axis -1 whatever `adim` names, so put time last. Another `adim` that
        does not name the permuted axis raises ValueError (see `adim`).

        - ``'circular_shift'`` rotates x2 by a shift drawn uniformly from 0 to n - 1, the
          same shift for every row. Each series keeps its autocorrelation, so the null
          holds for autocorrelated time series. There are only n distinct shifts, so p
          cannot fall much below ``1/n``.
        - ``'block'`` cuts the axis into consecutive blocks of `block_len` samples (the last
          may be shorter) and permutes their order. `block_len` should span several
          autocorrelation times: on independent AR(1) series with coefficient 0.9 (200
          samples), ``block_len=20`` rejected at p <= 0.05 for 0.30 of pairs with cka and
          ``block_len=50`` for 0.062.
        - ``'iid'`` permutes single samples, which is exchangeable only when the samples
          are independent. On a time axis it must be named: on two independent AR(1)
          series with coefficient 0.9 it rejects at p <= 0.05 about half the time.
        - ``None`` (default) is ``'circular_shift'`` for the paired metrics. The
          observation-axis metrics have no default: forming a null for them without naming
          `null` raises ValueError, because whether their rows are exchangeable depends on
          what the rows are. Name ``'iid'`` for exchangeable conditions or observations and
          ``'circular_shift'`` when axis 0 is time, where the i.i.d. row permutation is
          invalid -- cka and rv rejected every one of 40 independent AR(1) pairs at
          p <= 0.05. ``'block'`` is not calibrated for these metrics (see above).

        ``execution['null']`` records the scheme that ran, or None when no permutation null
        was formed. Before 0.2.6.1 every metric used ``'iid'``.
    block_len : int or None
        Block length in samples for ``null='block'``, where it is required: the block has
        to span the autocorrelation of the data, which jrsa does not estimate. At least two
        blocks must fit on the permuted axis. Passing it with any other `null` raises.
        ``execution['null_block_len']`` records it.
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
    random_state : int, numpy.random.Generator or None
        Random seed for reproducibility, for both the permutation null and the bootstrap.
        Any other type raises ``TypeError``.
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
        Metric-specific keyword arguments: ``rdm_metric`` for ``'rsa'``, ``kernel`` for
        ``'cka'`` (``'linear'`` only), ``sigma`` for ``'hsic'``, ``bins`` for
        ``'mutual_information'`` and ``'transfer_entropy_histogram_nats'``, ``max_lag`` for
        ``'granger_ssr_ftest'``, and ``fs``, ``nperseg``, ``noverlap``, ``bands`` and
        ``jackknife`` for ``'phase_slope'``. A keyword the chosen metric does not declare
        raises TypeError rather than being silently ignored. The histogram TE conditions on
        one past sample of each series and takes no history length. ``granger_ssr_ftest``,
        ``phase_slope`` and ``transfer_entropy_histogram_nats`` take one series per input:
        a multi-row input raises ValueError.

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

    if sliding:
        raise NotImplementedError(
            "jrsa(sliding=True) is not implemented; it used to be accepted and ignored. "
            "Loop over windows instead, one call per window: "
            "[jrsa(x1, x2, window=(s, s + w), ...) for s in range(0, n - w + 1, step)], "
            "where `window` is in sample indices along the aligned axis."
        )

    # The tail applies to the parametric p as well as the permutation one, so it is checked
    # here rather than only where a permutation null is formed.
    _require_alternative(alternative)
    _require_null(null, block_len)
    permutation_p = bool(stats and permutations > 0)
    if (alternative != "two-sided" and not permutation_p
            and str(metric).lower() in _UPPER_TAIL_PARAMETRIC_P):
        raise ValueError(
            f"jrsa: alternative={alternative!r} needs a one-sided p, and metric {metric!r} "
            "reports an upper-tail F-test p. F is non-negative and has no side, so the "
            "one-sided p cannot be formed by halving, as it is for a signed statistic. Use "
            "alternative='two-sided', or a permutation null (stats=True, permutations > 0)."
        )

    # --- collect parameter snapshot -------------------------------------------
    params = dict(
        adim=adim, labels=labels, align=align, align_mode=align_mode,
        reduction=reduction, metric=metric, lag=lag, window=window,
        sliding=sliding, normalize=normalize, standardize=standardize,
        detrend=detrend, nan_policy=nan_policy, stats=stats,
        permutations=permutations, bootstrap=bootstrap, correction=correction,
        alpha=alpha, alternative=alternative, null=null, block_len=block_len,
        backend=backend, device=device,
        n_jobs=n_jobs, batch_size=batch_size, random_state=random_state,
        return_type=return_type, return_null=return_null,
        return_input=return_input, verbose=verbose, **kwargs,
    )

    # --- pipeline -------------------------------------------------------------
    rng = resolve_rng(random_state, func_name="jrsa")
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
    x1, x2 = _validate_inputs(x1, x2, nan_policy, metric)
    x1, x2, axis_map = _standardize_dimensions(x1, x2, adim, labels)
    ndim_in = x1.ndim
    x1, x2, aligned_axes = _align_dimensions(
        x1, x2, axis_map, align, align_mode, verbose
    )
    window_axes = axis_map
    if reduction is not None:
        x1, x2 = _reduce_dimensions(x1, x2, axis_map, reduction)
        if str(metric).lower() in _OBSERVATION_AXIS_0_METRICS:
            x1, x2, window_axes = _drop_reduced_observation_axis(
                x1, x2, axis_map, reduction, window, metric
            )
    x1, x2 = _apply_preprocessing(x1, x2, normalize, standardize, detrend)
    x1, x2, windows = _make_windows(x1, x2, window_axes, window, sliding)
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
    _refuse_an_adim_the_resampling_ignores(
        metric, adim, axis_map, ndim_in, x1.ndim < ndim_in, perm_axis,
        permutation_p=permutation_p, bootstrap=bootstrap, lag=lag,
    )
    # Paired metrics compare samples along the aligned axis, usually time, where single
    # samples are not exchangeable: an i.i.d. shuffle there rejected about half of
    # independent AR(1) pairs at phi = 0.9.
    if perm_axis == 0 and null is None and permutation_p:
        raise ValueError(
            f"jrsa(metric={metric!r}) needs a named null=: its permutation null resamples the "
            "rows of axis 0, and whether they are exchangeable depends on what they are. Name "
            "null='iid' when the rows are exchangeable conditions or observations, and "
            "null='circular_shift' when axis 0 is time: on independent AR(1) series the i.i.d. "
            "row permutation rejected every pair for cka and rv. null='block' is not "
            "calibrated for this metric: with block_len=20 it rejected cka at p <= 0.05 for "
            "0.30 of independent AR(1) pairs (coefficient 0.9, 200 samples). Without a "
            "permutation null (stats=False or permutations=0) no scheme is needed."
        )
    null_scheme = null if null is not None else "circular_shift"
    if bootstrap > 0 and perm_axis == -1 and null != "iid":
        raise ValueError(
            f"jrsa(metric={metric!r}): bootstrap resamples single samples of the last axis, "
            "which undercovers on autocorrelated data: on independent AR(1) pairs with "
            "coefficient 0.9 the 95% interval of pearson covered 0 for 0.475 of pairs. Name "
            "null='iid' to declare the samples exchangeable, or set bootstrap=0."
        )

    if verbose:
        print(f"[jrsa] computing {metric!r} …")

    # --- temporal lag iteration -----------------------------------------------
    # np.ndim, not isinstance(int): a NumPy integer or 0-d array is one lag.
    lags = [lag] if np.ndim(lag) == 0 else list(np.asarray(lag).ravel())

    if len(lags) <= 1:
        x1_lagged, x2_lagged = _apply_lag(x1, x2, axis_map, lag, axis=perm_axis)
        value, statistic, effect, p_raw, df = metric_fn(
            x1_lagged, x2_lagged, axis=-1, **kwargs
        )
        null_dist = None
        ci = None
        if not permutation_p:
            p_raw = _one_sided_parametric_p(value, p_raw, alternative)

        if permutation_p:
            null_dist = _permutation_test(
                x1_lagged, x2_lagged, metric_fn, permutations, rng, axis=perm_axis, n_jobs=n_jobs,
                scheme=null_scheme, block_len=block_len, **kwargs
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
            x1_lagged, x2_lagged = _apply_lag(x1, x2, axis_map, l, axis=perm_axis)
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
                    x1_lagged, x2_lagged, metric_fn, permutations, rng, axis=perm_axis,
                    n_jobs=n_jobs, scheme=null_scheme, block_len=block_len, **kwargs
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
    exec_meta["null"] = null_scheme if permutation_p else None
    exec_meta["null_block_len"] = block_len if permutation_p and null_scheme == "block" else None
    _n_axis = x1.shape[perm_axis]
    _overlap = [_n_axis - abs(int(l)) if x2 is not None else _n_axis for l in lags]
    exec_meta["n_overlap"] = _overlap[0] if len(lags) <= 1 else _overlap

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


# Public classes keep the module path they had before the split, so pickles and reprs
# that name it still resolve.
for _cls in (JRSAResult,):
    _cls.__module__ = __name__
del _cls
