"""The whole-bin rule shared by every function that bins spike times into fixed-width bins.

It has no dependency beyond numpy so that eagerly imported modules can call it.
"""
from __future__ import annotations

import numpy as np


def _count_tolerance(start: float, end: float, width: float) -> float:
    """How far from an integer a bin count over ``[start, end)`` can land from rounding alone.

    It grows with the magnitude of the endpoints, because an absolute window hours into a
    recording carries rounding of order 1e-8 bins at 1 ms.
    """
    return 1e-9 + 16 * np.finfo(float).eps * max(abs(start), abs(end)) / width


def bins_within(span, bin_width) -> int:
    """Number of whole ``bin_width`` bins that fit in ``span``.

    A span that is a whole number of bins up to rounding counts as that number, where
    ``int(span / bin_width)`` can truncate it to one fewer.
    """
    span, width = float(span), float(bin_width)
    return int(np.floor(span / width + _count_tolerance(0.0, span, width)))


def bin_edges(start, bin_width, n_bins: int) -> np.ndarray:
    """The ``n_bins + 1`` edges ``start + k * bin_width``."""
    return float(start) + float(bin_width) * np.arange(n_bins + 1)


def right_open_counts(trains, start, end, bin_width, n_bins: int) -> np.ndarray:
    """Spike counts of each train in ``n_bins`` bins from ``start``, every bin right-open.

    A spike at or past ``end`` is excluded, including one on the last edge, which
    :func:`numpy.histogram` alone would count because it closes its last bin on the right.
    Returns a float array ``(n_trains, n_bins)``.
    """
    start, end = float(start), float(end)
    edges = bin_edges(start, bin_width, n_bins)
    rows = [np.histogram(s[(s >= start) & (s < end)], bins=edges)[0] for s in trains]
    return np.asarray(rows, dtype=float).reshape(len(rows), n_bins)


def _first_not_below(st, onsets, w: float, *, inclusive: bool) -> np.ndarray:
    """Per onset, the first index of sorted ``st`` whose ``st - onset`` is not below ``w``.

    "Below" is ``< w``, or ``<= w`` with ``inclusive``. ``st - onset`` rounds monotonically in
    ``st``, so the indices that are below form a prefix. Binary searches on ``onset + w``
    widened by a few ulps bracket the end of that prefix, and a bisection on ``st - onset``
    itself, vectorised over onsets, finds it inside the bracket in ``log2`` of its width.
    """
    pad = 8 * np.finfo(float).eps * (np.abs(onsets) + abs(w))
    lo = np.searchsorted(st, onsets + w - pad, side="left")
    hi = np.searchsorted(st, onsets + w + pad, side="right")
    while np.any(lo < hi):
        open_ = lo < hi
        mid = (lo + hi) // 2
        rel = st[np.where(open_, mid, 0)] - onsets
        below = (rel <= w) if inclusive else (rel < w)
        lo = np.where(open_ & below, mid + 1, lo)
        hi = np.where(open_ & ~below, mid, hi)
    return lo


def onset_window(st, onsets, start_s: float, stop_s: float, *, right_closed: bool = False):
    """``(lo, hi)`` index arrays such that ``st[lo[i]:hi[i]]`` are the spikes selected for onset ``i``.

    A spike at time ``t`` is selected when ``t - onset`` lies in ``[start_s, stop_s)``, or
    ``[start_s, stop_s]`` with ``right_closed``: the onset is subtracted from the spike, as
    `bin_spikes` and :func:`right_open_counts` do on relative times, never added to the
    window edges. The two disagree for a spike within an ulp of an edge: onset 0.03 s with a
    spike at 0.3 s is exactly 0.27 s after the onset, while ``0.03 + 0.27`` rounds above 0.3.

    ``st`` is sorted float64; a NaN sorts last and is never selected. It cannot call
    :func:`right_open_counts`, whose frozen body masks every spike and has no closed right edge.
    """
    onsets = np.asarray(onsets, dtype=float).ravel()
    lo = _first_not_below(st, onsets, float(start_s), inclusive=False)
    hi = _first_not_below(st, onsets, float(stop_s), inclusive=right_closed)
    return lo, np.maximum(hi, lo)


def onset_locked_counts(spike_times, onsets, start_s, stop_s, edges, scale: float,
                        *, right_closed: bool) -> np.ndarray:
    """Spike counts of each onset's window in ``edges``, counting every selected spike.

    A spike is selected for an onset by :func:`onset_window`: its time minus the onset lies in
    ``[start_s, stop_s)``, or ``[start_s, stop_s]`` with ``right_closed``, in seconds. That
    relative time, times ``scale`` (1000 for millisecond edges), is binned in ``edges``, whose
    outer edges are ``start_s * scale`` and ``stop_s * scale``. The scaling can round a
    selected spike just outside them -- onset 2.0 s with a spike at 1.9 s gives
    -100.00000000000009 ms against a first edge of -100 -- and :func:`numpy.histogram` would
    drop it, so relative times are clipped to the outer edges. Values already inside are
    unchanged.

    The train is sorted once, in float64, and each window is a binary search. A NaN sorts
    last and is never selected. Returns a float array ``(n_onsets, len(edges) - 1)``.
    """
    st = np.sort(np.asarray(spike_times, dtype=float), axis=None)
    onsets = np.asarray(onsets, dtype=float).ravel()
    lo, hi = onset_window(st, onsets, start_s, stop_s, right_closed=right_closed)
    counts = np.zeros((onsets.size, len(edges) - 1))
    for i, t0 in enumerate(onsets):
        rel = np.clip((st[lo[i]:hi[i]] - t0) * scale, edges[0], edges[-1])
        counts[i], _ = np.histogram(rel, bins=edges)
    return counts


def whole_bin_count(window, bin_width, func_name: str, param: str = "win_ms",
                    unit: str = "ms", width_param: str = "bin_width") -> int:
    """Number of ``bin_width`` bins spanning ``window``, refusing a span that is not whole bins.

    ``window`` and ``bin_width`` are in the same ``unit``, which the message names. A partial
    last bin holds less than ``bin_width`` of data, so its count is short and a rate divided by
    the full width reads low; a window stretched or shrunk to whole bins has no bin of the
    stated width. The error names the nearest valid windows with the same start, and refuses
    a window whose end is not after its start, naming which. A width that is not finite and
    positive is refused under the caller's name for it, ``width_param``.
    """
    start, end = float(window[0]), float(window[1])
    width = float(bin_width)
    if not (np.isfinite(width) and width > 0):
        raise ValueError(f"{func_name}: {width_param}={width:g} must be finite and positive.")
    if not (np.isfinite(start) and np.isfinite(end) and end > start):
        what = ("must have finite ends" if not (np.isfinite(start) and np.isfinite(end))
                else "is reversed: its end precedes its start" if end < start
                else "is empty: its end equals its start")
        raise ValueError(f"{func_name}: {param}=({start:.10g}, {end:.10g}) {what}. "
                         "Give (start, end) with finite ends and end > start.")
    n = (end - start) / width
    n_whole = int(round(n))
    if abs(n - n_whole) > _count_tolerance(start, end, width) or n_whole < 1:
        nearest = [(start, start + k * width) for k in (int(np.floor(n)), int(np.ceil(n))) if k >= 1]
        p = _distinguishing_digits([start, end] + [b for _, b in nearest])
        raise ValueError(
            f"{func_name}: {param}=({start:.{p}g}, {end:.{p}g}) spans {end - start:.10g} {unit}, "
            f"which is {n:g} bins of {width:g} {unit}, so the last bin would be partial. Use "
            + " or ".join(f"{param}=({a:.{p}g}, {b:.{p}g})" for a, b in nearest)
            + ", or a bin width that divides the span."
        )
    return n_whole


def _distinguishing_digits(values) -> int:
    """The fewest significant digits, ten or more, that print distinct ``values`` apart.

    Windows far from zero differ past the tenth digit: at 3e12 ms a refused window and the
    two suggested in its place all print as ``(3e+12, 3e+12)`` with ten.
    """
    for p in range(10, 17):
        if len({f"{v:.{p}g}" for v in values}) == len(set(values)):
            return p
    return 17
