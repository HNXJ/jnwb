"""Mutual information between spike trains."""

from __future__ import annotations

from typing import Optional, Tuple
import numpy as np
from .._units import resolve_unit_alias
from .._bins import whole_bin_count
from ._trials import bin_spikes


def _discrete_mi_from_labels(x: np.ndarray, y: np.ndarray) -> float:
    """Shannon MI (bits) between two discrete integer sequences of equal length."""
    x = np.asarray(x).ravel()
    y = np.asarray(y).ravel()
    n = len(x)
    if n == 0:
        return 0.0
    # Map labels to compact indices
    _, x_inv = np.unique(x, return_inverse=True)
    _, y_inv = np.unique(y, return_inverse=True)
    n_x = int(x_inv.max()) + 1
    n_y = int(y_inv.max()) + 1
    joint = np.zeros((n_x, n_y), dtype=float)
    np.add.at(joint, (x_inv, y_inv), 1.0)
    p_xy = joint / n
    p_x = p_xy.sum(axis=1)
    p_y = p_xy.sum(axis=0)
    mi = 0.0
    for i in range(n_x):
        for j in range(n_y):
            if p_xy[i, j] > 0 and p_x[i] > 0 and p_y[j] > 0:
                mi += p_xy[i, j] * np.log2(p_xy[i, j] / (p_x[i] * p_y[j]))
    return float(mi)


def spike_mutual_information(
    spike_times1: np.ndarray,
    spike_times2: np.ndarray,
    time_window_s: Optional[Tuple[float, float]] = None,
    bin_size_ms: float = 10.0,
    estimator: str = "binary_occupancy",
    *,
    time_window: Optional[Tuple[float, float]] = None,
) -> float:
    """
    Compute Shannon Mutual Information (MI) between two binned spike trains.

    Args:
        spike_times1: Spike times of unit 1 (seconds)
        spike_times2: Spike times of unit 2 (seconds)
        time_window_s: (start_time, end_time) in seconds. `time_window` is the old
            spelling, kept working; it named no unit while `bin_size_ms` beside it did.
        bin_size_ms: Bin size in ms
        estimator:
            - ``binary_occupancy`` (default): MI of bin occupancy (hist > 0).
              This is **not** MI of full spike trains / rates.
            - ``spike_count``: MI of integer spike counts per bin.

    Returns:
        mi: Mutual Information in bits
    """
    time_window_s = resolve_unit_alias(
        time_window_s, time_window,
        canonical_name="time_window_s", alias_name="time_window",
        func_name="spike_mutual_information",
    )
    if estimator not in ("binary_occupancy", "spike_count"):
        raise ValueError(
            f"Unknown estimator={estimator!r}; use 'binary_occupancy' or 'spike_count'"
        )

    if len(spike_times1) == 0 or len(spike_times2) == 0:
        raise ValueError(
            "spike_mutual_information requires non-empty spike_times1 and spike_times2"
        )

    whole_bin_count(time_window_s, bin_size_ms / 1000.0, "spike_mutual_information",
                    "time_window_s", unit="s")
    hist1 = bin_spikes(spike_times1, window_s=time_window_s, bin_size_ms=bin_size_ms)[0]
    hist2 = bin_spikes(spike_times2, window_s=time_window_s, bin_size_ms=bin_size_ms)[0]

    if estimator == "binary_occupancy":
        x = (hist1 > 0).astype(int)
        y = (hist2 > 0).astype(int)
    else:
        x = hist1.astype(int)
        y = hist2.astype(int)

    return _discrete_mi_from_labels(x, y)


def binary_occupancy_mutual_information(
    spike_times1: np.ndarray,
    spike_times2: np.ndarray,
    time_window_s: Optional[Tuple[float, float]] = None,
    bin_size_ms: float = 10.0,
    *,
    time_window: Optional[Tuple[float, float]] = None,
) -> float:
    """Explicit alias for binary occupancy MI. `time_window_s` is in seconds."""
    return spike_mutual_information(
        spike_times1,
        spike_times2,
        time_window_s,
        bin_size_ms=bin_size_ms,
        estimator="binary_occupancy",
        time_window=time_window,
    )


def spike_count_mutual_information(
    spike_times1: np.ndarray,
    spike_times2: np.ndarray,
    time_window_s: Optional[Tuple[float, float]] = None,
    bin_size_ms: float = 10.0,
    *,
    time_window: Optional[Tuple[float, float]] = None,
) -> float:
    """Discrete MI on per-bin spike counts. `time_window_s` is in seconds."""
    return spike_mutual_information(
        spike_times1,
        spike_times2,
        time_window_s,
        bin_size_ms=bin_size_ms,
        estimator="spike_count",
        time_window=time_window,
    )
