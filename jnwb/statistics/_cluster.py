"""The cluster-based permutation test."""

from __future__ import annotations

import warnings
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
from .._parallel import parallel_map, spawn_seeds
from .._rng import RNGLike, resolve_rng
from .._spread import is_constant as _is_constant
from ..permutation import _count_at_least_as_extreme, permute_labels


def cluster_permutation_test(
    X: np.ndarray,
    Y: np.ndarray,
    *,
    paired: bool = False,
    groups: Optional[Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]] = None,
    scheme: Optional[str] = None,
    threshold: float = 2.0,
    n_permutations: int = 1000,
    tail: str = "both",
    rng: RNGLike = 0,
    n_jobs: int = 1,
) -> Dict[str, Union[np.ndarray, List[Dict[str, Union[float, np.ndarray]]]]]:
    """Non-parametric cluster-based permutation test for multidimensional signals (Maris & Oostenveld, 2007).

    Identifies spatiotemporal or spectrotemporal clusters exceeding a cluster-forming threshold,
    evaluating their significance against a null distribution of the maximum cluster-level statistic
    formed under paired (sign-flip), independent (label-shuffle), or grouped (within-group restricted)
    exchangeability schemes.

    Multiple comparisons across time, frequency, and channels are controlled via the maximum-cluster
    statistic (family-wise error rate control).

    Finite Monte Carlo p-values are computed with exact pseudo-count correction:
        p = (1 + k) / (B + 1)
    where k is the number of permutation draws at least as extreme as the observed cluster,
    with tol = 100 * eps * |observed_stat| so that a draw reproducing the observed split with
    its sum taken in another order counts:
        - For tail='greater': k = sum(max_null_stats >= observed_stat - tol)
        - For tail='less':    k = sum(max_null_stats <= observed_stat + tol)
        - For tail='both':    k = sum(max_null_stats >= abs(observed_stat) - tol)

    Args:
        X: Sample array for condition 1, shape (n_samples_X, ...).
        Y: Sample array for condition 2, shape (n_samples_X, ...) if paired=True,
            or (n_samples_Y, ...) if paired=False. Trailing dimensions must match X.
        paired: If True, tests paired differences (X - Y) via random sign-flipping.
            If False, tests independent samples (Welch unequal-variance t-test) via condition label shuffling.
        groups: Group identifiers for exchangeability restriction (e.g. session_id or subject_id).
            - When paired=True: Array of shape (n_samples_X,).
            - When paired=False: Either a tuple (groups_X, groups_Y) matching X and Y samples,
              or a single array of shape (n_samples_X + n_samples_Y,).
            Required when scheme='within_group'. When paired=True, each pair is already
            the sampling unit; sign-flips are independent across pairs and ``groups`` does
            not further restrict the null.
        scheme: Explicit exchangeability scheme for independent testing:
            - 'global': Unrestricted condition label shuffle across all samples.
            - 'within_group': Condition labels are shuffled strictly within each group/session,
              preserving group composition and guarding against session-level confounding.
            Defaults to 'within_group' if groups is provided, otherwise 'global'.
        threshold: Cluster-forming threshold (positive float) applied to point-wise t-statistics (|t| > threshold).
        n_permutations: Number of permutation draws (default: 1000). Must be >= 1.
        tail: One of 'both' (positive and negative clusters), 'greater' (positive clusters only),
            or 'less' (negative clusters only). Default is 'both'.
        rng: An explicit numpy.random.Generator instance (e.g. np.random.default_rng(seed)).
        n_jobs: CPU workers for the permutation loop. Default 1 (serial); -1 uses every
            core. Results are identical for any n_jobs, because each permutation is
            seeded from `rng` before the loop starts.

    Returns:
        Dict with:
        - 'stat_map': Observed point-wise t-statistic map, shape X.shape[1:].
        - 'clusters': List of dicts, each describing an identified cluster:
            - 'statistic': Float, sum of point-wise t-statistics in the cluster.
            - 'p_value': Float, exact finite Monte Carlo p-value in (0, 1].
            - 'mask': Boolean ndarray with shape X.shape[1:], indicating cluster members.
        - 'max_null_stats': 1D ndarray of length `n_permutations`, containing the extremal cluster
            statistic under each null permutation draw (maximum for 'greater', minimum for 'less',
            or maximum absolute value for 'both').

    Raises:
        ValueError: If inputs have mismatched shapes, threshold <= 0, n_permutations < 1,
            invalid tail specification, or invalid group configuration.
        TypeError: If rng is provided but not an instance of numpy.random.Generator.

    References:
        Maris, E., & Oostenveld, R. (2007). Nonparametric statistical testing of EEG- and
        MEG-data. J. Neurosci. Methods. doi:10.1016/j.jneumeth.2007.03.024 -- the
        cluster-based permutation test: the sum of t within each suprathreshold cluster,
        tested against the permutation distribution of the largest cluster statistic.
        Phipson, B., & Smyth, G. K. (2010). Permutation p-values should never be zero.
        Stat. Appl. Genet. Mol. Biol. doi:10.2202/1544-6115.1585 -- the p-value
        ``(1 + k) / (B + 1)`` over B random permutations.
    """
    from scipy import ndimage

    if threshold <= 0:
        raise ValueError(f"Cluster threshold must be strictly positive; got {threshold}.")
    if n_permutations < 1:
        raise ValueError(f"n_permutations must be >= 1; got {n_permutations}.")
    if tail not in ("both", "greater", "less"):
        raise ValueError(f"tail must be 'both', 'greater', or 'less'; got {tail!r}.")
    rng = resolve_rng(rng, func_name="cluster_permutation_test")

    X_arr = np.asarray(X, dtype=float)
    Y_arr = np.asarray(Y, dtype=float)

    # isfinite, not isnan. An Inf sample used to pass this guard and then drive the
    # variance at its point to NaN, where `out=np.zeros_like(m)` left the pre-filled 0.0 --
    # so an infinite observation guaranteed its point joined no cluster. Inf and NaN are
    # both non-estimable, and are rejected identically.
    if not (np.isfinite(X_arr).all() and np.isfinite(Y_arr).all()):
        raise ValueError(
            "Cannot perform cluster permutation test on data containing NaN or infinite "
            "values."
        )

    if scheme is None:
        scheme = "within_group" if groups is not None else "global"
    elif scheme not in ("global", "within_group"):
        raise ValueError(f"scheme must be 'global' or 'within_group'; got {scheme!r}.")

    if paired:
        if X_arr.shape != Y_arr.shape:
            raise ValueError(f"Paired cluster permutation requires identical shapes; got {X_arr.shape} vs {Y_arr.shape}.")
        n_obs = X_arr.shape[0]
        if n_obs < 2:
            raise ValueError(f"Paired cluster permutation requires at least 2 samples; got {n_obs}.")
        diff = X_arr - Y_arr
        if groups is not None:
            groups_arr = np.asarray(groups)
            if groups_arr.shape[0] != n_obs:
                raise ValueError(f"Paired groups length {groups_arr.shape[0]} != sample count {n_obs}.")
    else:
        if X_arr.shape[1:] != Y_arr.shape[1:]:
            raise ValueError(
                f"Independent cluster permutation requires matching trailing dimensions; "
                f"got {X_arr.shape[1:]} vs {Y_arr.shape[1:]}."
            )
        n1 = X_arr.shape[0]
        n2 = Y_arr.shape[0]
        if n1 < 2 or n2 < 2:
            raise ValueError(f"Independent cluster permutation requires at least 2 samples per group; got {n1}, {n2}.")
        pooled = np.concatenate([X_arr, Y_arr], axis=0)
        n_total = n1 + n2
        orig_labels = np.array([0] * n1 + [1] * n2)

        if groups is not None:
            if isinstance(groups, tuple):
                if len(groups) != 2:
                    raise ValueError("Tuple groups must have length 2 (groups_X, groups_Y).")
                gX, gY = np.asarray(groups[0]), np.asarray(groups[1])
                if gX.shape[0] != n1 or gY.shape[0] != n2:
                    raise ValueError(f"Tuple groups lengths ({gX.shape[0]}, {gY.shape[0]}) do not match ({n1}, {n2}).")
                pooled_groups = np.concatenate([gX, gY], axis=0)
            else:
                pooled_groups = np.asarray(groups)
                if pooled_groups.shape[0] != n_total:
                    raise ValueError(f"groups length {pooled_groups.shape[0]} != total samples {n_total}.")
        else:
            if scheme == "within_group":
                raise ValueError("scheme='within_group' requires groups to be specified.")
            pooled_groups = None

    def _finite_t(m: np.ndarray, se: np.ndarray, constant: np.ndarray,
                  exact_m: np.ndarray) -> np.ndarray:
        """t = m / se, with the zero-standard-error points answered rather than zero-filled.

        Zero standard error makes the statistic 0/0. A difference that is exactly zero in
        every observation is an *observed* zero and stays 0.0. A constant non-zero
        difference is perfectly consistent and its t is unbounded; 0.0 was the most wrong
        available answer there, reporting the strongest possible effect as no effect, so
        that point is now NaN and is reported as non-estimable instead.

        ``constant`` marks the points whose data have no spread, tested exactly, and
        ``exact_m`` is their difference: the computed ``se`` and ``m`` of constant data are
        rounding residue (about 1e-17 for 0.3), which made the t there 1e16 or any value.
        """
        degenerate = constant | ~(se > 0)
        t = np.divide(m, se, out=np.zeros_like(m), where=~degenerate)
        if np.any(degenerate):
            m_d = np.where(constant, exact_m, m)
            t = np.where(degenerate, np.where(m_d == 0, 0.0, np.nan), t)
        return t

    def _calc_t_paired(d: np.ndarray) -> np.ndarray:
        n = d.shape[0]
        m = np.mean(d, axis=0)
        v = np.var(d, axis=0, ddof=1)
        se = np.sqrt(v / n)
        return _finite_t(m, se, _is_constant(d, axis=0), d[0])

    def _calc_t_unpaired(x1: np.ndarray, x2: np.ndarray) -> np.ndarray:
        n_a, n_b = x1.shape[0], x2.shape[0]
        m1, m2 = np.mean(x1, axis=0), np.mean(x2, axis=0)
        v1, v2 = np.var(x1, axis=0, ddof=1), np.var(x2, axis=0, ddof=1)
        se = np.sqrt(v1 / n_a + v2 / n_b)
        constant = _is_constant(x1, axis=0) & _is_constant(x2, axis=0)
        return _finite_t(m1 - m2, se, constant, x1[0] - x2[0])

    def _labelled_maps(t_map: np.ndarray) -> List[Tuple[np.ndarray, int]]:
        maps = []
        if tail in ("both", "greater"):
            maps.append(ndimage.label(t_map > threshold))
        if tail in ("both", "less"):
            maps.append(ndimage.label(t_map < -threshold))
        return maps

    def _cluster_sums(t_map: np.ndarray, labeled: np.ndarray, n_labels: int) -> List[float]:
        """The sum of ``t_map`` over each label ``1..n_labels``, in label order.

        One stable sort of the S labelled points and one sum per contiguous run: O(M + S
        log S) for a map of M points, where a full-map mask per cluster was O(K M). The
        stable sort keeps each cluster's points in C order, so each run is the array
        ``t_map[labeled == i]`` itself and its sum is bitwise the same.
        """
        flat = labeled.ravel()
        points = np.flatnonzero(flat)
        points = points[np.argsort(flat[points], kind="stable")]
        values = t_map.ravel()[points]
        bounds = np.concatenate(([0], np.cumsum(np.bincount(flat[points], minlength=n_labels + 1)[1:])))
        return [float(np.sum(values[bounds[i]:bounds[i + 1]])) for i in range(n_labels)]

    def _extract_clusters(t_map: np.ndarray) -> List[Tuple[float, np.ndarray]]:
        found = []
        for labeled, n_labels in _labelled_maps(t_map):
            sums = _cluster_sums(t_map, labeled, n_labels)
            found.extend((s, labeled == i) for i, s in enumerate(sums, start=1))
        return found

    def _extremal_cluster_stat(t_map: np.ndarray) -> float:
        sums = [s for labeled, n_labels in _labelled_maps(t_map)
                for s in _cluster_sums(t_map, labeled, n_labels)]
        if len(sums) == 0:
            return 0.0
        if tail == "greater":
            return max(sums)
        if tail == "less":
            return min(sums)
        return max(abs(s) for s in sums)

    # 1. Observed statistic map and clusters
    obs_t = _calc_t_paired(diff) if paired else _calc_t_unpaired(X_arr, Y_arr)
    n_degenerate = int(np.isnan(obs_t).sum())
    if n_degenerate:
        warnings.warn(
            f"cluster_permutation_test: {n_degenerate} point(s) have a constant non-zero "
            "difference across observations, so the t statistic there is undefined (zero "
            "standard error). They are reported as NaN and take part in no cluster.",
            RuntimeWarning,
            stacklevel=2,
        )
    obs_clusters = _extract_clusters(obs_t)

    # 2. Permutation null distribution of extremal cluster statistic
    flip_shape = (n_obs, *([1] * (diff.ndim - 1))) if paired else ()

    # One seed per permutation, drawn before any worker starts, so permutation b uses
    # the same randomness whether this runs serially or across twelve cores. Advancing
    # the shared generator inside the loop would tie the result to scheduling order.
    permutation_seeds = spawn_seeds(rng, n_permutations)

    def _one_permutation(seed: np.random.SeedSequence) -> float:
        perm_rng = np.random.default_rng(seed)
        if paired:
            flips = perm_rng.choice([-1.0, 1.0], size=flip_shape)
            p_t = _calc_t_paired(diff * flips)
        else:
            # Delegate permutation strictly to canonical permute_labels
            p_labels = permute_labels(
                orig_labels,
                groups=pooled_groups,
                scheme=scheme,
                rng=perm_rng,
            )
            idx0 = np.flatnonzero(p_labels == 0)
            idx1 = np.flatnonzero(p_labels == 1)
            p_t = _calc_t_unpaired(pooled[idx0], pooled[idx1])

        # A null draw needs only the extremal sum, never a cluster mask.
        return _extremal_cluster_stat(p_t)

    max_null_stats = np.asarray(
        parallel_map(_one_permutation, permutation_seeds, n_jobs=n_jobs), dtype=float
    )

    # 3. Exact finite Monte Carlo p-values with (1 + k) / (B + 1)
    cluster_results: List[Dict[str, Union[float, np.ndarray]]] = []
    for stat, mask in obs_clusters:
        # 'both' compares |stat| with a null that is already a maximum of |sums|.
        if tail == "less":
            k = _count_at_least_as_extreme(max_null_stats, stat, "less")
        else:
            k = _count_at_least_as_extreme(max_null_stats, abs(stat), "greater")
        p_val = (1.0 + k) / (n_permutations + 1.0)
        cluster_results.append({
            'statistic': stat,
            'p_value': float(p_val),
            'mask': mask,
        })

    # Sort clusters by statistical prominence (largest absolute sum first)
    cluster_results.sort(key=lambda c: abs(c['statistic']), reverse=True)

    return {
        'stat_map': obs_t,
        'clusters': cluster_results,
        'max_null_stats': max_null_stats,
    }
