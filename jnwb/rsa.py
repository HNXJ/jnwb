"""Representational Dissimilarity Matrix (RDM) and Representational Similarity Analysis (RSA).

Provides core generic primitives for computing RDMs and comparing them across
representations, modalities, models, or time points.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from scipy.spatial.distance import pdist, squareform
from scipy import stats

from ._backend import CUDA, resolve_device

log = logging.getLogger(__name__)


def _condensed_distances(X: np.ndarray, metric: str) -> np.ndarray:
    """Validate a feature matrix and return its `pdist` vector.

    Undefined distances are left as NaN so each caller decides how to report them:
    `rdm` raises, and the `jrsa` RSA metric propagates NaN as its pre-delegation
    `pdist` + `spearmanr` implementation did.
    """
    arr = np.asarray(X, dtype=np.float64)
    if arr.ndim < 2:
        raise ValueError(f"rdm requires at least a 2D array; got shape {arr.shape}.")
    if arr.ndim > 2:
        arr = arr.reshape(arr.shape[0], -1)

    n_conditions = arr.shape[0]
    if n_conditions < 2:
        raise ValueError(f"rdm requires at least 2 conditions/observations; got {n_conditions}.")
    if not np.all(np.isfinite(arr)):
        raise ValueError("rdm input array contains non-finite values (NaN or Inf).")

    with np.errstate(divide="ignore", invalid="ignore"):
        return pdist(arr, metric=metric)


def rdm(
    X: np.ndarray,
    metric: str = "correlation",
    condensed: bool = True,
    device: str = "cpu",
) -> np.ndarray:
    r"""Compute a Representational Dissimilarity Matrix (RDM) from feature vectors.

    Given an :math:`(N, D)` matrix of :math:`N` conditions / stimuli and :math:`D`
    features, computes pairwise dissimilarities :math:`d(x_i, x_j)`:

    - When ``condensed=True`` (default), returns the 1D upper-triangular vector of
      length :math:`N(N - 1) / 2` matching :func:`scipy.spatial.distance.pdist`.
    - When ``condensed=False``, returns the symmetric :math:`N \times N` square matrix
      with zero diagonal.

    Supported Metrics:
        - ``'correlation'``: Pearson correlation distance (:math:`1 - r`)
        - ``'cosine'``: Cosine distance
        - ``'euclidean'``: Euclidean distance (:math:`L_2` norm)
        - ``'cityblock'``: Manhattan distance (:math:`L_1` norm)
        - Any other metric string accepted by :func:`scipy.spatial.distance.pdist`,
          subject to that metric's own requirements (``'mahalanobis'`` needs
          :math:`N > D`).

    Complexity:
        - Time: :math:`O(N^2 \cdot D)`
        - Memory: :math:`O(N^2)` for condensed or full matrix representation.

    Args:
        X: 2D array of shape `(n_conditions, n_features)`. If an array of higher
            dimensionality is passed, it is flattened to 2D across trailing dimensions.
        metric: Distance metric string (default `'correlation'`).
        condensed: If True, returns 1D vector of shape `(N*(N-1)//2,)`. If False,
            returns 2D symmetric square matrix of shape `(N, N)`.
        device: `'cpu'` or `'cuda'`. There is no GPU implementation: `'cuda'` computes
            on CPU and emits a RuntimeWarning saying so.

    Returns:
        1D or 2D array of pairwise dissimilarities with float64 precision.

    Raises:
        ValueError: If `X` has fewer than 2 conditions, contains non-finite values
            (NaN / Inf), `device` is unrecognised, or `metric` is undefined for some
            condition pair. Correlation distance is undefined for a zero-variance
            condition and cosine distance for a zero-norm condition; reporting 0 there
            would declare the condition identical to the others.
    """
    if resolve_device(device, context="rdm", prefer="cupy", stacklevel=3) == CUDA:
        warnings.warn(
            "rdm: device='cuda' was requested, but rdm has no GPU implementation; "
            "computing on CPU.",
            RuntimeWarning,
            stacklevel=2,
        )

    v = _condensed_distances(X, metric)
    undefined = ~np.isfinite(v)
    if np.any(undefined):
        n_conditions = int(np.asarray(X).shape[0])
        rows_i, rows_j = np.triu_indices(n_conditions, k=1)
        pairs = list(zip(rows_i[undefined].tolist(), rows_j[undefined].tolist()))
        raise ValueError(
            f"rdm: the {metric!r} distance is undefined for {len(pairs)} condition pair(s), "
            f"e.g. {pairs[:5]}. Correlation distance is undefined for a zero-variance row "
            "and cosine distance for a zero-norm row. Remove those conditions or choose a "
            "metric defined for them."
        )

    if condensed:
        return v
    return squareform(v)


def _as_condensed_rdm(rdm_in: np.ndarray, name: str) -> np.ndarray:
    """Return a condensed RDM vector, rejecting inputs that are not RDMs."""
    v = np.asarray(rdm_in, dtype=np.float64)
    if v.ndim == 2:
        if v.shape[0] != v.shape[1]:
            raise ValueError(f"{name} must be square if 2D; got shape {v.shape}.")
        if not np.all(np.isfinite(v)):
            raise ValueError("RDM vectors contain non-finite values (NaN or Inf).")
        tol = 1e-8 * max(1.0, float(np.max(np.abs(v)))) if v.size else 1e-8
        asymmetry = float(np.max(np.abs(v - v.T))) if v.size else 0.0
        if asymmetry > tol:
            raise ValueError(
                f"{name} is not symmetric (max |M - M.T| = {asymmetry:.3g}). Only the upper "
                "triangle would be compared, silently discarding the lower one."
            )
        diagonal = float(np.max(np.abs(np.diag(v)))) if v.size else 0.0
        if diagonal > tol:
            raise ValueError(
                f"{name} has a nonzero diagonal (max |diag| = {diagonal:.3g}). A condition's "
                "dissimilarity to itself is 0; a nonzero diagonal usually means a similarity "
                "matrix was passed."
            )
        return squareform(v, checks=False)
    if v.ndim != 1:
        raise ValueError(f"RDMs must be 1D condensed or 2D square; got ndim {v.ndim}.")
    m = v.size
    n = int(round((1.0 + np.sqrt(1.0 + 8.0 * m)) / 2.0))
    if m == 0 or n * (n - 1) // 2 != m:
        raise ValueError(
            f"{name} has length {m}, which is not N(N-1)/2 for any N >= 2 conditions, "
            "so it is not a condensed RDM."
        )
    return v


def rdm_similarity(
    rdm1: np.ndarray,
    rdm2: np.ndarray,
    metric: str = "spearman",
) -> Tuple[float, float]:
    r"""Compute second-order representational similarity between two RDMs.

    Quantifies the agreement between two representational geometries. Accepts either
    condensed 1D dissimilarity vectors or full 2D square matrices. Only the
    off-diagonal upper triangle is compared. RDM cells are not independent
    observations, so the returned p-value is not a valid test of RDM relatedness;
    use a condition-label permutation for inference.

    Supported Comparison Metrics:
        - ``'spearman'`` (default): Spearman rank correlation :math:`\rho` and two-tailed p-value.
        - ``'pearson'``: Linear Pearson correlation :math:`r` and two-tailed p-value.
        - ``'kendall'``: Kendall tau rank correlation :math:`\tau` and two-tailed p-value.
        - ``'cosine'``: Normalized vector cosine similarity :math:`\frac{v_1 \cdot v_2}{\|v_1\| \|v_2\|}` (p-value is NaN).

    Args:
        rdm1, rdm2: 1D condensed vectors of equal length :math:`N(N-1)/2` or 2D
            symmetric zero-diagonal matrices of equal shape :math:`(N, N)`.
        metric: Similarity comparison metric (`'spearman'`, `'pearson'`, `'kendall'`, or `'cosine'`).

    Returns:
        Tuple of `(similarity_coefficient, p_value)`. For `'cosine'`, `p_value` is `nan`.
        The coefficient is `nan` where it is undefined (a constant RDM under a
        correlation metric, or an all-zero RDM under `'cosine'`).

    Raises:
        ValueError: If an RDM is not square, not symmetric, has a nonzero diagonal, has
            a condensed length that is not :math:`N(N-1)/2`, the two lengths differ, or
            entries are non-finite.
    """
    v1 = _as_condensed_rdm(rdm1, "rdm1")
    v2 = _as_condensed_rdm(rdm2, "rdm2")

    if len(v1) != len(v2):
        raise ValueError(f"RDM length mismatch: {len(v1)} vs {len(v2)}.")

    if not (np.all(np.isfinite(v1)) and np.all(np.isfinite(v2))):
        raise ValueError("RDM vectors contain non-finite values (NaN or Inf).")

    metric_lower = metric.lower()
    if metric_lower == "spearman":
        res = stats.spearmanr(v1, v2)
        return float(res.statistic), float(res.pvalue)
    elif metric_lower == "pearson":
        res = stats.pearsonr(v1, v2)
        return float(res.statistic), float(res.pvalue)
    elif metric_lower == "kendall":
        res = stats.kendalltau(v1, v2)
        return float(res.statistic), float(res.pvalue)
    elif metric_lower == "cosine":
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return float("nan"), float("nan")
        cos_sim = float(np.dot(v1, v2) / (norm1 * norm2))
        return cos_sim, float("nan")
    else:
        raise ValueError(f"Unknown similarity metric '{metric}'. Choose 'spearman', 'pearson', 'kendall', or 'cosine'.")
