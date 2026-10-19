"""Effective sample size of autocorrelated samples, by the initial positive sequence rule."""

from __future__ import annotations

import numpy as np

from .._spread import is_constant


def effective_sample_size(x: np.ndarray) -> float:
    """Effective number of independent samples in autocorrelated data.

    Each channel is demeaned, and its autocorrelation rho_k comes from the FFT, normalised by
    lag 0. A channel with no variance is skipped; constancy is decided exactly, as `jnwb`
    decides it elsewhere, since a constant channel's mean is not its value in floating point.
    The lag-k autocorrelation is averaged over the channels, and the lags are summed from k = 1
    while that mean stays positive: the initial positive sequence of Geyer (1992), Statistical
    Science 7(4), 473-483, doi:10.1214/ss/1177011137. The count is n / (1 + 2 sum), clipped to
    [2, n].

    Args:
        x: Samples of shape ``(n_channels, n_samples)``, or ``(n_samples,)`` for one channel.

    Returns:
        The effective sample count, as a float.

    Raises:
        ValueError: If ``x`` is not 1-D or 2-D, holds a non-finite value, has fewer than 2
            samples per channel, or has no channel with variance.
    """
    arr = np.asarray(x, dtype=float)
    if arr.ndim not in (1, 2):
        raise ValueError(
            "effective_sample_size: x must be 1-D (n_samples,) or 2-D (n_channels, n_samples), "
            f"got shape {arr.shape}"
        )
    if not np.all(np.isfinite(arr)):
        bad = int(np.count_nonzero(~np.isfinite(arr)))
        raise ValueError(f"effective_sample_size: x holds {bad} non-finite value(s) (NaN or Inf)")
    data = arr.reshape(1, -1) if arr.ndim == 1 else arr
    n = data.shape[1]
    if n < 2:
        raise ValueError(f"effective_sample_size: x needs at least 2 samples per channel, got {n}")
    constant = is_constant(data, axis=1)
    if np.all(constant):
        raise ValueError(
            "effective_sample_size: x has no channel with variance; every channel is constant, "
            f"shape {arr.shape}"
        )
    centred = data[~constant] - data[~constant].mean(axis=1, keepdims=True)
    size = 1 << (2 * n - 1).bit_length()  # a power of two of at least 2n - 1, so no lag wraps
    spectrum = np.fft.rfft(centred, n=size, axis=1)
    acov = np.fft.irfft(np.abs(spectrum) ** 2, n=size, axis=1)[:, :n]
    mean_rho = (acov / acov[:, :1]).mean(axis=0)
    nonpositive = np.flatnonzero(mean_rho[1:] <= 0)
    kept = int(nonpositive[0]) if nonpositive.size else n - 1
    total = float(mean_rho[1:kept + 1].sum())
    return float(min(max(n / (1.0 + 2.0 * total), 2.0), float(n)))
