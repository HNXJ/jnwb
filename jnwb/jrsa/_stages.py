"""Input stages: validation, axis naming, alignment, reduction, preprocessing, windows and lag."""

from __future__ import annotations

import numbers
import warnings
import numpy as np
from .._spread import zscore
from ._backends import _get_xp, _to_backend
from ._metrics import _OBSERVATION_AXIS_0_METRICS


def _prepare_inputs(x1, x2, backend_ctx: dict):
    """Convert inputs to numpy (or chosen backend array) and handle JNWB Signals."""
    x1 = _to_backend(x1, backend_ctx)
    if x2 is not None:
        x2 = _to_backend(x2, backend_ctx)
    else:
        x2 = None  # within-array mode
    return x1, x2


def _validate_inputs(x1, x2, nan_policy: str, metric=None):
    """Shape checks and NaN handling on both CPU and GPU namespaces."""
    xp1 = _get_xp(x1)
    size_before = x1.size
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
    # The observation axis: axis 0 for the metrics that read rows as observations, the last
    # axis for the paired metrics. Dropping along the last axis for every metric removed a
    # feature column of cka or rsa instead of the observation that held the NaN.
    obs_axis = 0 if str(metric).lower() in _OBSERVATION_AXIS_0_METRICS else x1.ndim - 1
    if nan_policy == "omit":
        # Keep an observation only when neither input is NaN anywhere in it.
        nan_mask = xp1.isnan(x1)
        if x2 is not None:
            nan_mask = nan_mask | _get_xp(x2).isnan(x2)
        other_axes = tuple(ax for ax in range(x1.ndim) if ax != obs_axis)
        any_nan = nan_mask.any(axis=other_axes) if other_axes else nan_mask
        valid_indices = xp1.where(~any_nan)[0]
        x1 = xp1.take(x1, valid_indices, axis=obs_axis)
        if x2 is not None:
            x2 = _get_xp(x2).take(x2, valid_indices, axis=obs_axis)
    # propagate: do nothing, let downstream handle
    # No values left -- an input with a zero-length axis, or `omit` dropping every sample
    # because some condition is NaN throughout. The metrics disagreed here: hsic,
    # mutual_information and transfer_entropy_histogram_nats returned 0.0 computed from
    # nothing, which reads as "no dependence", six others returned NaN and five raised. Every
    # metric now raises.
    if x1.size == 0 or (x2 is not None and x2.size == 0):
        detail = ""
        if nan_policy == "omit" and size_before > 0:
            empty = [] if x1.ndim < 2 else sorted(
                tuple(int(i) for i in idx)
                for idx in np.argwhere(np.all(np.asarray(nan_mask), axis=obs_axis))
            )
            detail = (
                f" nan_policy='omit' dropped every observation (axis {obs_axis}), because each "
                f"one is NaN somewhere"
                + (f"; position(s) {empty} of the other axes are NaN throughout" if empty else "")
                + "."
            )
        raise ValueError(
            f"jrsa(metric={metric!r}): no samples remain (shape {tuple(x1.shape)}), so the "
            f"metric has nothing to compute from.{detail}"
        )
    return x1, x2


def _is_axis_index(value) -> bool:
    """An integer axis: a Python or NumPy integer, not a bool."""
    return isinstance(value, numbers.Integral) and not isinstance(value, (bool, np.bool_))


def _standardize_dimensions(x1, x2, adim, labels):
    """Normalise adim to a dict {name: axis_index}."""
    axis_map = {}
    # numbers.Integral, not int: np.int64(0) failed isinstance(int) and fell through to -1.
    if _is_axis_index(adim):
        axis_map["aligned"] = int(adim) % x1.ndim
    elif isinstance(adim, (tuple, list)):
        for i, d in enumerate(adim):
            if isinstance(d, str):
                if labels is None:
                    raise ValueError("labels required when adim contains strings.")
                axis_map[d] = labels.index(d)
            elif _is_axis_index(d):
                d = int(d)
                key = labels[d] if labels and d < len(labels) else f"axis_{d}"
                axis_map[key] = d % x1.ndim
            else:
                raise TypeError(
                    f"jrsa: each entry of adim must be an int or a str; got "
                    f"{type(d).__name__} at position {i}."
                )
    elif isinstance(adim, str):
        if labels is None:
            raise ValueError("labels required when adim is a string.")
        axis_map[adim] = labels.index(adim)
    else:
        raise TypeError(
            f"jrsa: adim must be an int, a str, or a tuple or list of them; got "
            f"{type(adim).__name__}. Another type used to be read as adim=-1."
        )
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
        if name not in axis_map:
            # Skipping it returned the unreduced value while `parameters['reduction']`
            # recorded the request.
            raise ValueError(
                f"jrsa: reduction key {name!r} names no axis of `adim`. The axes are "
                f"{list(axis_map)}."
            )
        ax = axis_map[name]
        x1 = _reduce_one(x1, op_str, ax)
        if x2 is not None:
            x2 = _reduce_one(x2, op_str, ax)
    return x1, x2


def _refuse_an_adim_the_resampling_ignores(metric, adim, axis_map, ndim_in, dropped_axis_0,
                                           perm_axis, *, permutation_p, bootstrap, lag):
    """Raise when a non-default `adim` would be ignored by the null, bootstrap or `lag`.

    Those act on a fixed axis of the input: the last for the paired metrics, axis 0 for the
    row metrics, or axis 1 when a reduction removed axis 0. With ``adim=0`` on a 2-D input,
    pearson returned the value and p of ``adim=-1`` exactly, and a lag shifted the last
    axis. A non-default `adim` is accepted with any of the three only when it names that
    axis; following `adim` is not implemented. An `adim` naming only the last axis, as the
    default ``adim=-1`` does, is exempt: for the row metrics it names the features while
    the resampling acts on the observations, as the docstring states.
    """
    used = [name for name, on in (("the permutation null", permutation_p),
                                  ("bootstrap", bootstrap > 0),
                                  ("lag", bool(np.any(np.asarray(lag) != 0)))) if on]
    if not used or set(axis_map.values()) == {ndim_in - 1}:
        return
    acted = ndim_in - 1 if perm_axis == -1 else (1 if dropped_axis_0 else 0)
    if acted in axis_map.values():
        return
    kind = ("the last axis, for a paired metric" if perm_axis == -1 else
            "the observations of a row metric")
    raise ValueError(
        f"jrsa(metric={metric!r}, adim={adim!r}): {', '.join(used)} act(s) on axis {acted} of "
        f"the input ({kind}) whatever `adim` names, and `adim` does not name it, so the "
        "result would not follow `adim`. Name that axis in `adim`, use the default adim=-1 "
        "with the aligned axis last, or drop the resampling (stats=False or "
        "permutations=0, bootstrap=0, lag=0)."
    )


def _window_axis_name(axis_map):
    """The `axis_map` entry `window` applies to: ``'aligned'``, else the first `adim` axis."""
    return "aligned" if "aligned" in axis_map else list(axis_map)[0]


def _drop_reduced_observation_axis(x1, x2, axis_map, reduction, window, metric):
    """Remove axis 0 of a row metric's input when `reduction` reduced it.

    The row metrics read axis 0 as observations. A reduction keeps the reduced axis at
    length 1, which left one observation and a NaN (cka) or an error (rsa): averaging trials
    of a (trials, conditions, units) input gave NaN where cka on ``x.mean(0)`` gave 0.69. The
    axis is removed instead, so the next axis becomes the observations, and `lag` and the
    permutation null act on it. Returns the axis numbering `window` reads after the removal;
    `axis_map` itself, which the result records, keeps the numbering of the input.
    """
    reduced = {axis_map[name] for name in reduction if name in axis_map}
    if 0 not in reduced:
        return x1, x2, axis_map
    if x1.ndim < 2:
        raise ValueError(
            f"jrsa(metric={metric!r}): the reduction removes axis 0 of a 1-D input, which "
            "leaves no observation axis."
        )
    if window is not None:
        target = _window_axis_name(axis_map)
        if axis_map[target] == 0:
            raise ValueError(
                f"jrsa(metric={metric!r}): `window` applies to axis {target!r}, which the "
                "reduction removed. Window the input before reducing it, or name the axis to "
                "window first in `adim`."
            )
    xp = _get_xp(x1)
    x1 = xp.squeeze(x1, axis=0)
    if x2 is not None:
        x2 = _get_xp(x2).squeeze(x2, axis=0)
    return x1, x2, {name: ax - 1 for name, ax in axis_map.items() if ax != 0}


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
    """Extract the analysis window. `jrsa` refuses `sliding=True` before this runs.

    `window` is in sample indices along the aligned axis. The clamping below used to be
    silent in both directions: `(-500, 500)` on a 6-sample axis became `(0, 6)` -- the
    whole axis, so a caller who believed they had windowed got the unwindowed answer --
    and `(10, 30)` became an empty slice that produced a NaN statistic rather than an
    error. Both now say what happened.
    """
    if window is None:
        return x1, x2, None
    ax = axis_map[_window_axis_name(axis_map)]
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


def _apply_lag(x1, x2, axis_map, lag, axis=-1):
    """Pair x1[t] with x2[t - lag] along ``axis``, keeping only the overlap, on CPU or GPU.

    ``axis`` is the observation axis: -1 for the paired metrics, 0 for
    `_OBSERVATION_AXIS_0_METRICS`, whose last axis holds features they are invariant to.
    A lag of l drops |l| samples: x1 keeps ``[l:]`` and x2 ``[:n - l]`` for l > 0, x1
    ``[:n - |l|]`` and x2 ``[|l|:]`` for l < 0. The lag used to be circular (``roll``),
    which paired the end of each series with its start. One lag per call; `jrsa` loops.
    """
    if x2 is None:
        return x1, x2
    lags = [lag] if np.ndim(lag) == 0 else list(np.asarray(lag).ravel())
    if len(lags) != 1:
        raise ValueError(f"_apply_lag takes one lag per call; got {len(lags)}.")
    shift = int(lags[0])
    if shift == 0:
        return x1, x2
    xp = _get_xp(x2)
    n = x2.shape[axis]
    if abs(shift) >= n:
        raise ValueError(
            f"jrsa: lag={shift} leaves no overlap on an axis of {n} samples; |lag| must be "
            f"below {n}."
        )
    k = abs(shift)
    head, tail = xp.arange(0, n - k), xp.arange(k, n)
    if shift > 0:
        return xp.take(x1, tail, axis=axis), xp.take(x2, head, axis=axis)
    return xp.take(x1, head, axis=axis), xp.take(x2, tail, axis=axis)


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
