"""The whole-bin rule shared by every function that bins spike times into fixed-width bins.

It has no dependency beyond numpy so that eagerly imported modules can call it.
"""
from __future__ import annotations

import numpy as np


def whole_bin_count(window, bin_width, func_name: str, param: str = "win_ms",
                    unit: str = "ms") -> int:
    """Number of ``bin_width`` bins spanning ``window``, refusing a span that is not whole bins.

    ``window`` and ``bin_width`` are in the same ``unit``, which the message names. A partial
    last bin holds less than ``bin_width`` of data but its rate is still divided by the full
    width; a window stretched or shrunk to whole bins divides every bin by a width it does not
    have. The error names the nearest valid windows with the same start.

    The tolerance on the bin count grows with the magnitude of the window's endpoints, because
    an absolute window hours into a recording carries rounding of order 1e-8 bins at 1 ms.
    """
    start, end = float(window[0]), float(window[1])
    width = float(bin_width)
    n = (end - start) / width
    n_whole = int(round(n))
    tol = 1e-9 + 16 * np.finfo(float).eps * max(abs(start), abs(end)) / width
    if abs(n - n_whole) > tol or n_whole < 1:
        nearest = [(start, start + k * width) for k in (int(np.floor(n)), int(np.ceil(n))) if k >= 1]
        raise ValueError(
            f"{func_name}: {param}=({start:.10g}, {end:.10g}) spans {end - start:.10g} {unit}, "
            f"which is {n:g} bins of {width:g} {unit}, so not every bin would be {width:g} "
            f"{unit} wide and the rates would be wrong. Use "
            + " or ".join(f"{param}=({a:.10g}, {b:.10g})" for a, b in nearest)
            + ", or a bin width that divides the span."
        )
    return n_whole
