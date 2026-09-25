"""Zero spread, decided exactly.

``np.std`` and ``np.var`` are no test of constancy. The mean of a constant 0.3 is not 0.3 in
floating point, so its std is about 5.6e-17 rather than 0 and a ``> 0`` or ``== 0`` guard reads
the constant as varying. Dividing its centred values (the same residue) by that std gives
+-1, so a constant feature standardised to a column of ones. A slice is constant here when its
largest value equals its smallest.
"""
from __future__ import annotations

import warnings
from typing import Any, Optional, Union

import numpy as np


def is_constant(a: Any, axis: Optional[int] = None, *, keepdims: bool = False,
                ignore_nan: bool = False, xp: Any = np) -> Union[bool, Any]:
    """True where every value of the slice equals every other, compared exactly.

    ``axis=None`` answers for the whole array and returns a bool; an empty array is constant.
    With ``ignore_nan`` NaN entries are skipped, and an all-NaN slice is not constant. A NaN
    otherwise makes its slice non-constant. ``xp`` is the array namespace (NumPy or CuPy).
    """
    if not hasattr(a, "shape"):
        a = xp.asarray(a)
    if axis is None and a.size == 0:
        return True
    if ignore_nan:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN slice
            hi = xp.nanmax(a, axis=axis, keepdims=keepdims)
            lo = xp.nanmin(a, axis=axis, keepdims=keepdims)
    else:
        hi = a.max(axis=axis, keepdims=keepdims)
        lo = a.min(axis=axis, keepdims=keepdims)
    same = hi == lo
    return bool(same) if axis is None else same


def zscore(a: Any, axis: int, *, ignore_nan: bool = False, xp: Any = np) -> Any:
    """``(a - mean) / std`` along ``axis`` (population std), with each constant slice exactly 0.

    NaN stays NaN. A slice that varies but whose std underflows to 0 is centred and left
    unscaled.
    """
    mean_fn, std_fn = (xp.nanmean, xp.nanstd) if ignore_nan else (xp.mean, xp.std)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)       # all-NaN slice
        mean = mean_fn(a, axis=axis, keepdims=True)
        sd = std_fn(a, axis=axis, keepdims=True)
    constant = is_constant(a, axis=axis, keepdims=True, ignore_nan=ignore_nan, xp=xp)
    z = (a - mean) / xp.where(sd > 0, sd, 1.0)
    return xp.where(constant, a * 0, z)
