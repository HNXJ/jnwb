"""Inference: the null schemes, permutation and bootstrap, p-values and multiple-comparison correction."""

from __future__ import annotations

import numpy as np
from .._parallel import parallel_map
from ..permutation import _count_at_least_as_extreme


#: Accepted values of `null=`. None resolves per metric inside `jrsa`.
NULL_SCHEMES = ("circular_shift", "block", "iid")


def _require_null(null, block_len):
    if null is not None and null not in NULL_SCHEMES:
        raise ValueError(
            f"jrsa: unrecognized null {null!r}. Valid options: None or {list(NULL_SCHEMES)} "
            "(lowercase)."
        )
    if null == "block":
        if (block_len is None or isinstance(block_len, bool)
                or not isinstance(block_len, (int, np.integer)) or block_len < 1):
            raise ValueError(
                f"jrsa: null='block' needs block_len, a positive integer number of samples "
                f"that spans the autocorrelation of the data; got block_len={block_len!r}."
            )
    elif block_len is not None:
        raise ValueError(
            f"jrsa: block_len={block_len!r} applies only to null='block'; got null={null!r}."
        )


def _null_index(local_rng, n, scheme, block_len):
    """Index array that resamples an axis of length ``n`` under ``scheme``.

    ``'iid'`` is ``local_rng.permutation(n)``, the draw every metric used before `null=`
    existed, so a given seed reproduces the p-values of 0.2.6.
    """
    if scheme == "iid":
        return local_rng.permutation(n)
    if scheme == "circular_shift":
        # Shift 0 is drawn too. `_p_from_null`'s (1 + k) / (n_perm + 1) is valid for draws
        # that are uniform over the whole group of n rotations; leaving the identity out
        # reports 1 / (n_perm + 1) for an observed value above every rotation, where the
        # right answer is 1/n -- 0.0005 against 0.17 on a 6-sample axis.
        k = int(local_rng.integers(0, n))
        return np.roll(np.arange(n), k)
    starts = np.arange(0, n, block_len)
    order = local_rng.permutation(len(starts))
    return np.concatenate([np.arange(starts[i], min(starts[i] + block_len, n)) for i in order])


def _check_null_axis(n, scheme, block_len):
    if scheme == "block" and n < 2 * block_len:
        raise ValueError(
            f"jrsa: null='block' needs at least two blocks on the permuted axis; "
            f"block_len={block_len} with {n} samples gives fewer."
        )


def _permutation_test(x1, x2, metric_fn, n_perm, rng, axis=-1, n_jobs=1,
                      scheme="iid", block_len=None, **kwargs):
    """Permutation null of x2 against x1 along ``axis`` under ``scheme`` (see `_null_index`);
    returns the null distribution."""
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
        _check_null_axis(n, scheme, block_len)
        seeds = rng.integers(0, 2**31 - 1, size=n_perm)
        for seed in seeds:
            local_rng = np.random.default_rng(int(seed))
            idx = cp.asarray(_null_index(local_rng, n, scheme, block_len))
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
    _check_null_axis(n, scheme, block_len)

    # Generate all permutation indices upfront to pass to workers cleanly
    seeds = rng.integers(0, 2**31 - 1, size=n_perm)

    def _run_single_perm(seed):
        local_rng = np.random.default_rng(seed)
        idx = _null_index(local_rng, n, scheme, block_len)
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
    k = _count_at_least_as_extreme(null_dist, obs, alternative)
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
                f"(pip install 'statsmodels>=0.14.5'), or pass correction='bonferroni', "
                f"which jnwb computes without it."
            ) from exc
    return q.reshape(np.asarray(p).shape)
