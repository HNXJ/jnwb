"""Test primitives: exact intervals, the Mann-Whitney p floor, the sign flip and shuffle p-values."""

from __future__ import annotations

import math
from typing import Sequence, Tuple, Union
import numpy as np
from .._rng import DEFAULT_SEED, RNGLike, resolve_rng
from scipy import stats
from ..permutation import _count_at_least_as_extreme


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
    """Exact (Clopper-Pearson) binomial confidence interval via the Beta-quantile form.

    Computes exact binomial bounds by inverting the binomial cumulative distribution
    function through Beta distribution quantiles.

    Args:
        k: Number of successes (integer, 0 <= k <= n).
        n: Number of trials (positive integer, n >= 1).
        alpha: Significance level in (0, 1), default 0.05 (producing a 95% CI).

    Returns:
        Tuple[float, float]: (lower_bound, upper_bound).

    Raises:
        ValueError: If n <= 0, k < 0, k > n, or alpha is not in (0, 1).

    References:
        Clopper, C. J., & Pearson, E. S. (1934). The use of confidence or fiducial limits
        illustrated in the case of the binomial. Biometrika. doi:10.1093/biomet/26.4.404
        -- the exact binomial interval, computed here from Beta quantiles.
    """
    try:
        k_int = int(k)
        n_int = int(n)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"k and n must be integer-convertible, got k={k!r}, n={n!r}") from exc

    if k != k_int or n != n_int:
        raise ValueError(f"k and n must be exact integers, got k={k!r}, n={n!r}")
    if n_int <= 0:
        raise ValueError(f"n must be >= 1, got n={n_int}")
    if k_int < 0 or k_int > n_int:
        raise ValueError(f"k must satisfy 0 <= k <= n, got k={k_int}, n={n_int}")
    if not (0.0 < float(alpha) < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    lo = 0.0 if k_int == 0 else stats.beta.ppf(alpha / 2.0, k_int, n_int - k_int + 1)
    hi = 1.0 if k_int == n_int else stats.beta.ppf(1.0 - alpha / 2.0, k_int + 1, n_int - k_int)
    return (float(lo), float(hi))


def mann_whitney_p_floor(n1: int, n2: int, alternative: str = "two-sided") -> float:
    """Attainable minimal non-zero p-value floor for a Mann-Whitney U test without ties.

    Under the null hypothesis with sample sizes n1 and n2, the number of distinct rank
    allocations is comb(n1 + n2, n1). The extreme rank configuration has probability
    1 / comb(n1 + n2, n1).

    Args:
        n1: Sample size of group 1 (positive integer >= 1).
        n2: Sample size of group 2 (positive integer >= 1).
        alternative: "two-sided", "greater", or "less".

    Returns:
        float: Minimal attainable p-value under the rank permutation null.

    Raises:
        ValueError: If n1 < 1, n2 < 1, or alternative is unrecognized.
    """
    try:
        n1_int = int(n1)
        n2_int = int(n2)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"n1 and n2 must be integers, got n1={n1!r}, n2={n2!r}") from exc

    if n1 != n1_int or n2 != n2_int:
        raise ValueError(f"n1 and n2 must be exact integers, got n1={n1!r}, n2={n2!r}")
    if n1_int < 1 or n2_int < 1:
        raise ValueError(f"Sample sizes must be >= 1, got n1={n1_int}, n2={n2_int}")

    alt = str(alternative).lower().strip()
    if alt not in ("two-sided", "greater", "less"):
        raise ValueError(
            f"alternative must be 'two-sided', 'greater', or 'less', got {alternative!r}"
        )

    n_comb = math.comb(n1_int + n2_int, n1_int)
    one_sided_floor = 1.0 / float(n_comb)
    if alt in ("greater", "less"):
        return float(one_sided_floor)
    # two-sided: symmetric two-tailed floor is 2 / n_comb, capped at 1.0
    return float(min(1.0, 2.0 * one_sided_floor))


def exact_sign_flip(
    diffs: Union[Sequence[float], np.ndarray],
    alternative: str = "two-sided",
    n_mc: int = 10000,
    rng: RNGLike = DEFAULT_SEED,
) -> Tuple[float, float, float]:
    """Exact paired sign-flip permutation test for paired sample differences.

    Evaluates the mean paired difference against the null distribution generated
    by assigning independent random signs (+1 or -1) to each difference:

    - For N <= 20: exact direct combinatorial enumeration across all 2^N sign flips.
      No RNG is used or required.
    - For N > 20: Monte Carlo sign-flip sampling with caller-controlled `rng`.

    A null mean within rounding of the observed one counts as a tie. That width is
    proportional to the differences, so rescaling them (a change of units) leaves p unchanged.

    Args:
        diffs: 1D array-like of paired differences (e.g. condition A - condition B).
        alternative: "two-sided" (|mean_null| >= |mean_obs|),
                     "greater" (mean_null >= mean_obs), or
                     "less" (mean_null <= mean_obs).
        n_mc: Number of Monte Carlo sign-flip resamples when N > 20 (default 10,000).
        rng: Generator or integer seed for Monte Carlo when N > 20.

    Returns:
        Tuple[float, float, float]: (observed_mean, p_value, p_floor) where:
            - observed_mean: mean of the input differences.
            - p_value: exact or Monte Carlo p-value under the sign-flip null.
            - p_floor: minimal attainable non-zero p-value under extreme configuration.

    Raises:
        ValueError: If diffs is empty, contains non-finite values, or alternative is invalid.
    """
    arr = np.asarray(diffs, dtype=float).ravel()
    if arr.size == 0:
        raise ValueError("diffs cannot be empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError("diffs must contain only finite numerical values (no NaN or Inf)")

    alt = str(alternative).lower().strip()
    if alt not in ("two-sided", "greater", "less"):
        raise ValueError(
            f"alternative must be 'two-sided', 'greater', or 'less', got {alternative!r}"
        )

    n = arr.size
    obs_mean = float(np.mean(arr))

    # Attainable non-zero p-value floor
    if n <= 60:
        total_flips = 1 << n
        one_sided_floor = 1.0 / float(total_flips)
        p_floor = min(1.0, 2.0 * one_sided_floor) if alt == "two-sided" else one_sided_floor
    else:
        p_floor = 0.0

    tol = _tie_tolerance(arr)

    if n <= 20:
        # Exact direct enumeration of all 2^N combinations
        n_total = 1 << n
        chunk_size = min(n_total, 65536)
        count = 0

        for start in range(0, n_total, chunk_size):
            end = min(start + chunk_size, n_total)
            indices = np.arange(start, end, dtype=np.uint32)[:, None]
            bits = (indices >> np.arange(n, dtype=np.uint32)) & 1
            signs = np.where(bits, 1.0, -1.0)
            null_means = (signs @ arr) / float(n)
            count += _count_at_least_as_extreme(null_means, obs_mean, alt, atol=tol)

        p_value = float(count / n_total)
    else:
        # Monte Carlo sign-flip permutations
        if n_mc <= 0:
            raise ValueError(f"n_mc must be positive, got {n_mc}")
        gen = resolve_rng(rng, func_name="exact_sign_flip")

        # Draw random +/- 1 signs: shape (n_mc, n)
        signs = gen.choice([-1.0, 1.0], size=(n_mc, n), replace=True)
        null_means = (signs @ arr) / float(n)

        # Exact finite Monte Carlo p-value with (1 + k) / (B + 1)
        k = _count_at_least_as_extreme(null_means, obs_mean, alt, atol=tol)

        p_value = float((1.0 + k) / (float(n_mc) + 1.0))
        p_floor = float(1.0 / (float(n_mc) + 1.0))

    return (obs_mean, p_value, float(p_floor))


def _require_shuffle_inputs(a: np.ndarray, b: np.ndarray, n_shuffles: int, func_name: str) -> None:
    """Reject inputs for which a shuffle p-value would be fabricated.

    A NaN made the observed statistic NaN and every null comparison False, so the p-value was
    its minimum, 1/(n_shuffles+1): "significant" for any n_shuffles >= 20.
    """
    if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))):
        raise ValueError(f"{func_name}: a and b must be finite; drop or repair NaN or Inf values first")
    if isinstance(n_shuffles, bool) or not isinstance(n_shuffles, (int, np.integer)) or n_shuffles < 1:
        raise ValueError(f"{func_name}: n_shuffles must be a positive integer, got {n_shuffles!r}")


def _tie_tolerance(values: np.ndarray) -> float:
    """Width within which two evaluations of one permutation statistic are the same number.

    The statistic is a mean, or a difference of means over disjoint subsets, of ``values``
    (or of ``values`` with signs flipped). A draw that reproduces the observed split sums the
    same terms in another order and can land an ulp below the observed statistic, so a bare
    ``>=`` fails to count it and the p-value comes out too small: 3 v 3 separated groups,
    exact p 0.1, gave p < 0.05 in 16 of 200 seeds. Summing in any order moves a subset mean
    by less than ``eps * sum(|v|)`` over that subset, and the difference of two means by
    less than twice that, so two evaluations differ by less than ``4 * eps * sum(|v|)``;
    the tolerance doubles that bound. It scales with the data, so a change of units leaves
    every comparison unchanged.

    A difference of means ignores a common offset and ``sum(|v|)`` does not, so the unpaired
    callers centre the pooled values on their mean before computing the statistic, the null
    and this width. Uncentred, n = 1000 per group at an offset of 1e10 times the spread
    counted every split as a tie and returned p 1.0 where the exact rank was 0.487.
    """
    return 8.0 * float(np.finfo(float).eps) * float(np.sum(np.abs(values)))


def _zero_spread_t(a: float, b: float) -> Tuple[float, float]:
    """(t, p) of a t-test whose data have no spread, `a` and `b` being the constant values
    compared: no test when they are equal, and an unbounded t with p 0.0 otherwise, which is
    what scipy returns when the spread computes to exactly zero. A constant at inf or -inf has
    no test either; the check is on the values, so a finite difference too large to represent
    keeps its sign."""
    if a == b or not (math.isfinite(a) and math.isfinite(b)):
        return float("nan"), float("nan")
    return math.copysign(math.inf, a - b), 0.0


def shuffle_pvalue_paired(
    a: np.ndarray,
    b: np.ndarray,
    n_shuffles: int,
    rng: RNGLike,
    alternative: str = "two-sided",
) -> Tuple[float, float]:
    """Shuffle-controlled p-value for ``mean(a - b)`` via paired sign-flips.

    Null: randomly flip the sign of each paired difference (equivalent to swapping a/b labels
    within trial). Returns (observed_diff, p_value), or ``(nan, nan)`` for fewer than two
    pairs, where no null distribution exists.

    Raises:
        ValueError: If ``a`` and ``b`` differ in length (they were truncated to the shorter,
            pairing unrelated trials), contain NaN or Inf, or ``n_shuffles`` < 1.
    """
    rng = resolve_rng(rng, func_name="shuffle_pvalue_paired")
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) != len(b):
        raise ValueError(
            f"shuffle_pvalue_paired: a and b must be paired (equal length); got {len(a)} and {len(b)}"
        )
    _require_shuffle_inputs(a, b, n_shuffles, "shuffle_pvalue_paired")
    n = len(a)
    if n < 2:
        return float("nan"), float("nan")
    alt = _require_alternative(alternative, "shuffle_pvalue_paired")
    diff = a - b
    obs = float(np.mean(diff))
    flips = rng.choice(np.array([-1.0, 1.0]), size=(n_shuffles, n))
    null = flips @ diff / n
    k = _count_at_least_as_extreme(null, obs, alt, atol=_tie_tolerance(diff))
    return obs, float((1.0 + k) / (n_shuffles + 1.0))


def _require_alternative(alternative: str, func_name: str) -> str:
    """Normalize and validate a tail specification.

    The `if greater / elif less / else` chains this replaces had a two-sided fallthrough,
    so `alternative='GREATER'` and `alternative='nonsense'` both silently returned the
    two-sided p -- 0.163 where the one-sided value was 0.093. `exact_sign_flip` already
    case-folds and validates the identical parameter.
    """
    alt = str(alternative).strip().lower()
    if alt not in ("two-sided", "greater", "less"):
        raise ValueError(
            f"{func_name}: alternative must be one of 'two-sided', 'greater', 'less'; "
            f"got {alternative!r}. An unrecognised value used to select 'two-sided' "
            "silently."
        )
    return alt


def shuffle_pvalue_unpaired(
    a: np.ndarray,
    b: np.ndarray,
    n_shuffles: int,
    rng: RNGLike,
    alternative: str = "two-sided",
) -> Tuple[float, float]:
    """Shuffle-controlled p-value for ``mean(a) - mean(b)`` via label-shuffling.

    ``alternative`` defaults to ``'two-sided'``, as in :func:`shuffle_pvalue_paired`. It
    used to default to ``'greater'`` while its paired sibling defaulted to two-sided: on
    one dataset the two "defaults" were p = 0.041 and p = 0.163.

    Returns (observed_diff, p_value), or ``(nan, nan)`` when either group has fewer than two
    values.

    Raises:
        ValueError: If ``a`` or ``b`` contains NaN or Inf, or ``n_shuffles`` < 1.
    """
    rng = resolve_rng(rng, func_name="shuffle_pvalue_unpaired")
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    _require_shuffle_inputs(a, b, n_shuffles, "shuffle_pvalue_unpaired")
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    alt = _require_alternative(alternative, "shuffle_pvalue_unpaired")
    pooled = np.concatenate([a, b])
    pooled = pooled - np.mean(pooled)  # see _tie_tolerance
    n_a = len(a)
    obs = float(np.mean(pooled[:n_a]) - np.mean(pooled[n_a:]))
    null = np.empty(n_shuffles)
    for i in range(n_shuffles):
        rng.shuffle(pooled)
        null[i] = float(np.mean(pooled[:n_a]) - np.mean(pooled[n_a:]))
    k = _count_at_least_as_extreme(null, obs, alt, atol=_tie_tolerance(pooled))
    return obs, float((1.0 + k) / (n_shuffles + 1.0))
