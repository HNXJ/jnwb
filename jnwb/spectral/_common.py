"""Input checks, sampling-rate resolution and the band table shared by the spectral estimators."""

from typing import Dict, Optional, Tuple
import numpy as np
from .._spread import is_constant as _is_constant


def _require_band_bins(
    freqs: np.ndarray, mask: np.ndarray, freq_range: Tuple[float, float], func_name: str
) -> None:
    """Reject a frequency range that selects no bin of the segment grid."""
    if not np.any(mask):
        step = float(freqs[1] - freqs[0]) if len(freqs) > 1 else float("nan")
        raise ValueError(
            f"{func_name}: freq_range {tuple(freq_range)} contains no bin of the "
            f"frequency grid (0 to {float(freqs[-1]):g} Hz in steps of {step:g} Hz). "
            "Widen freq_range or lengthen nperseg."
        )


def _require_finite_nonempty_trace(x: np.ndarray, func_name: str, name: str = "lfp_trace") -> np.ndarray:
    """Return ``x`` as a float array, rejecting empty or non-finite input.

    Empty input used to return zeros, and a NaN sample gave zeros or NaN powers. A returned
    0 is indistinguishable from a measured absence of power or slope.
    """
    arr = np.asarray(x, dtype=float)
    if arr.size == 0:
        raise ValueError(f"{func_name}: {name} is empty; there is nothing to estimate.")
    if not np.all(np.isfinite(arr)):
        raise ValueError(
            f"{func_name}: {name} must be finite; remove or repair NaN or Inf samples first."
        )
    return arr


def _require_two_samples(arr: np.ndarray, func_name: str, name: str = "lfp_trace") -> np.ndarray:
    """Return ``arr``, rejecting a trace of fewer than 2 samples along its last axis.

    Welch removes the mean of a 1-sample segment and returns a 0.0 PSD, which is
    indistinguishable from a measured absence of power.
    """
    n_times = arr.shape[-1] if arr.ndim else 1
    if n_times < 2:
        raise ValueError(
            f"{func_name}: {name} has {n_times} sample(s) along its last axis; a spectrum "
            "needs at least 2."
        )
    return arr


def _flat_as_zero(x: np.ndarray) -> np.ndarray:
    """A constant trace replaced by the zeros its mean-detrended spectrum is.

    Welch removes each segment's mean, which for a constant 0.3 leaves rounding residue
    rather than 0, so a ``> 0`` power guard read a flat trace as carrying power: its tilt
    was fitted and a flat baseline gave a dB value. Use only ahead of an estimator that
    detrends each segment by its mean, where this changes nothing but the residue.
    """
    return np.zeros_like(x) if _is_constant(x) else x


CANONICAL_BANDS: Dict[str, Tuple[float, float]] = {
    "theta": (4.0, 8.0),
    "alpha": (8.0, 14.0),
    "beta": (14.0, 30.0),
    "low_gamma": (30.0, 50.0),
    "high_gamma": (50.0, 80.0),
}


def _resolve_fs(
    fs: Optional[float] = None,
    sampling_rate: Optional[float] = None,
    func_name: str = "function",
) -> float:
    """Resolve sampling rate from canonical `fs` or legacy alias `sampling_rate`."""
    if fs is not None and sampling_rate is not None:
        if fs != sampling_rate:
            raise ValueError(
                f"Conflicting values provided to {func_name}: fs={fs}, sampling_rate={sampling_rate}. "
                "Specify only one (prefer fs)."
            )
        return _require_positive_fs(fs, func_name)
    if fs is not None:
        return _require_positive_fs(fs, func_name)
    if sampling_rate is not None:
        return _require_positive_fs(sampling_rate, func_name)
    raise ValueError(f"{func_name} requires sampling rate `fs` (in Hz).")


def _require_positive_fs(fs, func_name: str) -> float:
    """A sampling rate is strictly positive and finite, everywhere in this module.

    This check used to be absent, so each caller failed in its own way further down --
    or not at all. `wpli(x, y, fs=0.0)` raised `ZeroDivisionError`; `fs=-1000.0` raised a
    ValueError describing a frequency grid running "0 to -500 Hz in steps of -3.90625
    Hz"; `imaginary_coherency` got a clean message only because it reached scipy's own
    guard, which names scipy's parameter rather than this contract.
    """
    try:
        value = float(fs)
    except (TypeError, ValueError):
        raise ValueError(
            f"{func_name}: fs must be a number in Hz; got {fs!r}."
        ) from None
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(
            f"{func_name}: fs must be finite and strictly positive (Hz); got {fs!r}."
        )
    return value
