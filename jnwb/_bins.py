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


def whole_bin_count(window, bin_width, func_name: str, param: str = "win_ms",
                    unit: str = "ms") -> int:
    """Number of ``bin_width`` bins spanning ``window``, refusing a span that is not whole bins.

    ``window`` and ``bin_width`` are in the same ``unit``, which the message names. A partial
    last bin holds less than ``bin_width`` of data but its rate is still divided by the full
    width; a window stretched or shrunk to whole bins divides every bin by a width it does not
    have. The error names the nearest valid windows with the same start.
    """
    start, end = float(window[0]), float(window[1])
    width = float(bin_width)
    n = (end - start) / width
    n_whole = int(round(n))
    if abs(n - n_whole) > _count_tolerance(start, end, width) or n_whole < 1:
        nearest = [(start, start + k * width) for k in (int(np.floor(n)), int(np.ceil(n))) if k >= 1]
        raise ValueError(
            f"{func_name}: {param}=({start:.10g}, {end:.10g}) spans {end - start:.10g} {unit}, "
            f"which is {n:g} bins of {width:g} {unit}, so not every bin would be {width:g} "
            f"{unit} wide and the rates would be wrong. Use "
            + " or ".join(f"{param}=({a:.10g}, {b:.10g})" for a, b in nearest)
            + ", or a bin width that divides the span."
        )
    return n_whole
