"""Representational Dissimilarity Matrix (RDM) and Representational Similarity Analysis (RSA).

Provides core generic primitives for computing RDMs and comparing them across
representations, modalities, models, or time points.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from scipy.spatial.distance import pdist, squareform
from scipy import stats

from ._backend import resolve_device

log = logging.getLogger(__name__)


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
        - ``'cityblock'`` / ``'manhattan'``: Manhattan distance (:math:`L_1` norm)
        - Any metric string supported by :func:`scipy.spatial.distance.pdist`.

    Complexity:
        - Time: :math:`O(N^2 \cdot D)`
        - Memory: :math:`O(N^2)` for condensed or full matrix representation.

    Args:
        X: 2D array of shape `(n_conditions, n_features)`. If an array of higher
            dimensionality is passed, it is flattened to 2D across trailing dimensions.
        metric: Distance metric string (default `'correlation'`).
        condensed: If True, returns 1D vector of shape `(N*(N-1)//2,)`. If False,
            returns 2D symmetric square matrix of shape `(N, N)`.
        device: `'cpu'` or `'cuda'` (falls back gracefully to CPU if CUDA unavailable).

    Returns:
        1D or 2D array of pairwise dissimilarities with float64 precision.

    Raises:
        ValueError: If `X` has fewer than 2 conditions or contains non-finite values (NaN / Inf).
    """
    arr = np.asarray(X, dtype=np.float64)
    if arr.ndim < 2:
        raise ValueError(f"rdm requires at least a 2D array; got shape {arr.shape}.")
    if arr.ndim > 2:
        arr = arr.reshape(arr.shape[0], -1)

    n_conditions, n_features = arr.shape
    if n_conditions < 2:
        raise ValueError(f"rdm requires at least 2 conditions/observations; got {n_conditions}.")
    if not np.all(np.isfinite(arr)):
        raise ValueError("rdm input array contains non-finite values (NaN or Inf).")

    v = pdist(arr, metric=metric)

    # In case of constant features resulting in NaN distances under correlation
    if np.any(np.isnan(v)):
        v = np.nan_to_num(v, nan=0.0)

    if condensed:
        return v
    return squareform(v)


def rdm_similarity(
    rdm1: np.ndarray,
    rdm2: np.ndarray,
    metric: str = "spearman",
) -> Tuple[float, float]:
    r"""Compute second-order representational similarity between two RDMs.

    Quantifies the agreement between two representational geometries. Accepts either
    condensed 1D dissimilarity vectors or full 2D square matrices.

    Supported Comparison Metrics:
        - ``'spearman'`` (default): Spearman rank correlation :math:`ho` and two-tailed p-value.
        - ``'pearson'``: Linear Pearson correlation :math:`r` and two-tailed p-value.
        - ``'kendall'``: Kendall tau rank correlation :math:`	au` and two-tailed p-value.
        - ``'cosine'``: Normalized vector cosine similarity :math:`rac{v_1 \cdot v_2}{\|v_1\| \|v_2\|}` (p-value is NaN).

    Args:
        rdm1, rdm2: 1D condensed vectors of equal length :math:`N(N-1)/2` or 2D
            symmetric matrices of equal shape :math:`(N, N)`.
        metric: Similarity comparison metric (`'spearman'`, `'pearson'`, `'kendall'`, or `'cosine'`).

    Returns:
        Tuple of `(similarity_coefficient, p_value)`. For `'cosine'`, `p_value` is `nan`.

    Raises:
        ValueError: If RDMs have incompatible shapes, invalid dimensions, or non-finite entries.
    """
    v1 = np.asarray(rdm1, dtype=np.float64)
    v2 = np.asarray(rdm2, dtype=np.float64)

    # Convert 2D square matrices to condensed vectors
    if v1.ndim == 2:
        if v1.shape[0] != v1.shape[1]:
            raise ValueError(f"rdm1 must be square if 2D; got shape {v1.shape}.")
        v1 = squareform(v1, checks=False)
    if v2.ndim == 2:
        if v2.shape[0] != v2.shape[1]:
            raise ValueError(f"rdm2 must be square if 2D; got shape {v2.shape}.")
        v2 = squareform(v2, checks=False)

    if v1.ndim != 1 or v2.ndim != 1:
        raise ValueError(f"RDMs must be 1D condensed or 2D square; got ndim {v1.ndim} and {v2.ndim}.")
    if len(v1) != len(v2):
        raise ValueError(f"RDM length mismatch: {len(v1)} vs {len(v2)}.")
    if len(v1) == 0:
        return 0.0, float("nan")

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
            return 0.0, float("nan")
        cos_sim = float(np.dot(v1, v2) / (norm1 * norm2))
        return cos_sim, float("nan")
    else:
        raise ValueError(f"Unknown similarity metric '{metric}'. Choose 'spearman', 'pearson', 'kendall', or 'cosine'.")
