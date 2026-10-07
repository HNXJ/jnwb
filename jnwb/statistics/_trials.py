"""Trial-structure helpers over an epochs table."""

from __future__ import annotations

import numpy as np
import pandas as pd


def detect_trial_cycles(epochs_df: pd.DataFrame, gap_factor: float = 10.0) -> np.ndarray:
    """Detect temporal cluster ("cycle") boundaries in a trial table via a gap threshold.

    Sorts ``epochs_df["start_time"]``, flags gaps that exceed ``gap_factor * median(gap)`` as
    cluster boundaries, and returns a 0-indexed integer cluster/cycle id per row, in the
    original row order of ``epochs_df`` (not sorted order).

    Args:
        epochs_df: DataFrame with a ``start_time`` column.
        gap_factor: a gap is a cluster boundary when it exceeds this multiple of the median
            inter-event gap.

    Returns:
        (n_rows,) int array of cycle ids, in ``epochs_df``'s original row order.
    """
    order = np.argsort(epochs_df["start_time"].values)
    t_sorted = epochs_df["start_time"].values[order]
    gaps = np.diff(t_sorted)
    thresh = gap_factor * np.median(gaps) if len(gaps) else np.inf
    breaks = np.where(gaps > thresh)[0]
    cycle_sorted = np.zeros(len(t_sorted), dtype=int)
    for b in breaks:
        cycle_sorted[b + 1:] += 1
    cycle = np.empty(len(order), dtype=int)
    cycle[order] = cycle_sorted
    return cycle


def assign_subblock_quartiles(epochs_df: pd.DataFrame, n_quantiles: int = 4) -> np.ndarray:
    """Assign each row a temporal quantile bucket 0..n_quantiles-1 by its own start_time order.

    Args:
        epochs_df: DataFrame with a ``start_time`` column.
        n_quantiles: number of equal-sized (as equal as possible) temporal buckets.

    Returns:
        (n_rows,) int array of quantile bucket ids, in ``epochs_df``'s original row order.
    """
    order = np.argsort(epochs_df["start_time"].values)
    n = len(order)
    q = np.empty(n, dtype=int)
    edges = np.linspace(0, n, n_quantiles + 1).astype(int)
    for k in range(n_quantiles):
        q[order[edges[k]:edges[k + 1]]] = k
    return q
