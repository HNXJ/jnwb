"""Network topology, the directed-estimator dispatcher and N-node directed networks."""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from .._parallel import parallel_map
from .._rng import resolve_seed_alias
from scipy import stats
from ._common import DirectedResult
from ._granger import granger, granger_spectral
from ._psi import phase_slope_index
from ._transfer_entropy import transfer_entropy


def network_topology(
    adjacency_matrix: np.ndarray,
    threshold: float = 0.3,
) -> Dict[str, Union[float, int, List[int]]]:
    """
    Compute network graph metrics from a correlation or Granger causality matrix.

    The diagonal is ignored. An edge is an entry whose absolute value exceeds ``threshold``.

    Raises:
        TypeError: If ``adjacency_matrix`` is complex. Casting to float would keep the real
            part and drop the imaginary one; pass ``np.abs(matrix)`` for the magnitude, or
            the part you mean.
        ValueError: If ``adjacency_matrix`` is not square 2-D, an off-diagonal entry is NaN or
            Inf, or ``threshold`` is not finite. A NaN entry counted as "no edge", and a
            non-square matrix returned in- and out-degree lists of different lengths.
    """
    if np.iscomplexobj(adjacency_matrix):
        raise TypeError(
            "network_topology: adjacency_matrix is complex, and a float cast would drop its "
            "imaginary part. Pass np.abs(adjacency_matrix) to threshold the magnitude, or "
            "the real or imaginary part explicitly."
        )
    adjacency_matrix = np.asarray(adjacency_matrix, dtype=float)
    if adjacency_matrix.ndim != 2 or adjacency_matrix.shape[0] != adjacency_matrix.shape[1]:
        raise ValueError(
            f"network_topology: adjacency_matrix must be square 2-D, got shape {adjacency_matrix.shape}"
        )
    off_diagonal = ~np.eye(adjacency_matrix.shape[0], dtype=bool)
    if not np.all(np.isfinite(adjacency_matrix[off_diagonal])):
        raise ValueError("network_topology: adjacency_matrix has NaN or Inf off the diagonal")
    if not np.isfinite(threshold):
        raise ValueError(f"network_topology: threshold must be finite, got {threshold}")
    adj = np.abs(adjacency_matrix) > threshold
    np.fill_diagonal(adj, False)

    n_nodes = adj.shape[0]
    n_edges = int(adj.sum())
    possible_edges = n_nodes * (n_nodes - 1) if n_nodes > 1 else 1
    density = n_edges / possible_edges

    in_degrees = adj.sum(axis=0).tolist()
    out_degrees = adj.sum(axis=1).tolist()

    return {
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "density": float(density),
        "in_degrees": in_degrees,
        "out_degrees": out_degrees,
        "mean_degree": float(np.mean(in_degrees)),
    }


# ---------------------------------------------------------------------------
# Dispatcher and N-node networks
# ---------------------------------------------------------------------------

DIRECTED_METHODS = {
    "granger": granger,
    "gc": granger,
    "granger_spectral": granger_spectral,
    "sgc": granger_spectral,
    "psi": phase_slope_index,
    "phase_slope_index": phase_slope_index,
    "te": transfer_entropy,
    "transfer_entropy": transfer_entropy,
}


def directed_connectivity(X, Y, method: str = "granger", **kwargs) -> DirectedResult:
    """
    One entry point for all three directed estimators.

    Args:
        X, Y: any signal accepted by :func:`as_trials`
        method: ``'granger'``/``'gc'`` | ``'psi'``/``'phase_slope_index'`` |
            ``'te'``/``'transfer_entropy'``
        **kwargs: forwarded verbatim to the chosen estimator

    Example:
        >>> for m in ('granger', 'psi', 'te'):
        ...     r = directed_connectivity(v1, pfc, method=m, **({'fs': 1000.} if m == 'psi' else {}))
    """
    key = str(method).lower()
    if key not in DIRECTED_METHODS:
        raise ValueError(
            f"Unknown method={method!r}; choose from {sorted(set(DIRECTED_METHODS))}"
        )
    return DIRECTED_METHODS[key](X, Y, **kwargs)


def directed_network(
    signals,
    method: str = "granger",
    labels: Optional[Sequence[str]] = None,
    fdr: bool = True,
    fdr_method: str = "bh",
    n_jobs: int = 1,
    **kwargs,
) -> Dict[str, Any]:
    """
    All-pairs directed connectivity over N nodes.

    Args:
        signals: ``{label: signal}`` dict, a list of signals, or a 3-D array
            ``(n_nodes, n_trials, n_times)`` / 2-D ``(n_nodes, n_times)``
        method: as in :func:`directed_connectivity`
        labels: node names (required only when ``signals`` is not a dict)
        fdr: Benjamini-Hochberg across the family of all N*(N-1) ordered pairs.
            The family is the whole matrix — correcting one cell in isolation
            would imply an undisclosed set.
        n_jobs: CPU workers for the pairs. Default 1 (serial); -1 uses every core.
            Each estimator seeds its surrogates from its own ``rng`` argument, so
            the result is identical for any n_jobs. A ``Generator`` passed as ``rng``
            is drawn once per pair before any worker starts.
        **kwargs: forwarded to the estimator

    Returns:
        dict with ``matrix`` (``M[i, j]`` = influence of node i on node j;
        diagonal NaN), ``p_matrix``, ``q_matrix`` (NaN when ``fdr=False`` or no
        p-values), ``labels``, ``results`` (the full DirectedResult per ordered
        pair), ``method``, and ``warnings``.

    References:
        Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate. J. R.
        Stat. Soc. B. doi:10.1111/j.2517-6161.1995.tb02031.x -- the step-up procedure
        behind ``q_matrix`` (``fdr_method='bh'``).
        Benjamini, Y., & Yekutieli, D. (2001). The control of the false discovery rate in
        multiple testing under dependency. Ann. Stat. doi:10.1214/aos/1013699998
        -- ``fdr_method='by'``, valid under arbitrary dependence.
    """
    if isinstance(signals, dict):
        labels = list(signals.keys())
        series = [signals[k] for k in labels]
    else:
        arr = signals
        if isinstance(arr, np.ndarray) and arr.ndim in (2, 3):
            series = [arr[i] for i in range(arr.shape[0])]
        else:
            series = list(arr)
        if labels is None:
            labels = [f"node{i}" for i in range(len(series))]
        labels = list(labels)
    n = len(series)
    if n < 2:
        raise ValueError(f"directed_network needs >= 2 nodes; got {n}")
    if len(labels) != n:
        raise ValueError(f"{len(labels)} labels for {n} signals")

    matrix = np.full((n, n), np.nan)
    p_matrix = np.full((n, n), np.nan)
    results: Dict[Tuple[str, str], DirectedResult] = {}
    warnings_all: List[str] = []

    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    # A Generator shared across workers would be copied into each one and replayed, so the
    # surrogates would depend on n_jobs. Draw one int seed per pair up front instead; each
    # pair then records its seed as `surrogate_seed_entropy`.
    pair_kwargs = [kwargs] * len(pairs)
    if "rng" in kwargs and "seed" in kwargs:
        # Both spellings of one argument: refuse a contradiction here, before the per-pair
        # seeds below would replace both with one value and hide it.
        resolve_seed_alias(kwargs["rng"], kwargs["seed"], alias_name="seed",
                           func_name="directed_network")
    gen_keys = [k for k in ("rng", "seed") if isinstance(kwargs.get(k), np.random.Generator)]
    if gen_keys:
        pair_seeds = kwargs[gen_keys[0]].integers(0, 2**63 - 1, size=len(pairs))
        pair_kwargs = [{**kwargs, **{k: int(s) for k in gen_keys}} for s in pair_seeds]
    pair_results = parallel_map(
        lambda job: directed_connectivity(
            series[job[0][0]], series[job[0][1]], method=method, **job[1]
        ),
        list(zip(pairs, pair_kwargs)),
        n_jobs=n_jobs,
    )
    for (i, j), res in zip(pairs, pair_results):
        matrix[i, j] = res.x_to_y
        matrix[j, i] = res.y_to_x
        if res.p_x_to_y is not None:
            p_matrix[i, j] = res.p_x_to_y
        if res.p_y_to_x is not None:
            p_matrix[j, i] = res.p_y_to_x
        results[(labels[i], labels[j])] = res
        for w in res.diagnostics.get("warnings", []):
            tag = f"{labels[i]}<->{labels[j]}: {w}"
            if tag not in warnings_all:
                warnings_all.append(tag)

    q_matrix = np.full((n, n), np.nan)
    # The family is the set of off-diagonal p-values that actually reached
    # false_discovery_control, not every off-diagonal cell: an estimator that
    # returns no p-value (TE without surrogates) or a pair that failed leaves
    # NaN, and those cells are never corrected.
    fdr_family_size = 0
    if fdr:
        off = ~np.eye(n, dtype=bool)
        finite = off & np.isfinite(p_matrix)
        fdr_family_size = int(finite.sum())
        if finite.any():
            q_matrix[finite] = stats.false_discovery_control(
                p_matrix[finite], method=fdr_method
            )

    return {
        "matrix": matrix,
        "p_matrix": p_matrix,
        "q_matrix": q_matrix,
        "labels": labels,
        "method": method,
        "n_nodes": n,
        "fdr_family_size": fdr_family_size,
        "results": results,
        "params": kwargs,
        "warnings": warnings_all,
    }
