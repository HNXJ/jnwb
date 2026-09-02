"""Time-Frequency Representation (TFR) module for jnwb.

Provides the canonical, minimal complex Morlet wavelet transform primitive
(`complex_tfr`), exact discrete wavelet normalization, Cone of Influence (COI)
boundary masking, and direct compatibility with `TFRAccumulator`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union

import numpy as np
from scipy import signal


@dataclass(frozen=True)
class ComplexTFR:
    """Container for complex Time-Frequency Representation outputs.

    Attributes:
        z: Complex wavelet coefficients tensor of shape (..., n_freqs, n_times).
        freqs: 1D array of frequency coordinates in Hz.
        times: 1D array of relative time coordinates in seconds.
        coi_mask: Boolean array matching or broadcastable to `z`, where True indicates
            interior samples outside the declared boundary region (t >= coi_sigma * sigma_t
            and t < T - coi_sigma * sigma_t). Note that wavelet tails decay exponentially
            rather than compactly; coi_mask marks the operational threshold where kernel
            amplitude is within the declared coi_sigma * sigma_t envelope.
        fs: Sampling rate in Hz.
        n_cycles: 1D array of wavelet cycles per frequency bin.
        normalization: Normalization scheme applied ('amplitude' or 'energy').
    """

    z: np.ndarray
    freqs: np.ndarray
    times: np.ndarray
    coi_mask: np.ndarray
    fs: float
    n_cycles: np.ndarray
    normalization: str

    @property
    def power(self) -> np.ndarray:
        """Instantaneous power (|z|^2)."""
        return np.abs(self.z) ** 2

    @property
    def phase(self) -> np.ndarray:
        """Instantaneous phase in radians (-pi, pi]."""
        return np.angle(self.z)

    @property
    def amplitude(self) -> np.ndarray:
        """Instantaneous amplitude magnitude (|z|)."""
        return np.abs(self.z)

    @property
    def shape(self) -> Tuple[int, ...]:
        return self.z.shape

    @property
    def dtype(self) -> np.dtype:
        return self.z.dtype


def morlet_wavelet(
    f0: float,
    fs: float,
    n_cycles: float = 5.0,
    normalization: str = "amplitude",
    cutoff_sigma: float = 4.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate a discrete complex Morlet wavelet kernel.

    Args:
        f0: Center frequency in Hz (must be > 0 and < fs / 2).
        fs: Sampling rate in Hz (must be > 0).
        n_cycles: Number of wavelet cycles (must be > 0).
        normalization: 'amplitude' (L1-scaled such that a unit cosine 1.0 * cos(2*pi*f0*t)
            yields |z| = 1.0 at f0) or 'energy' (L2-normalized such that sum(|w|^2) = 1.0).
        cutoff_sigma: Kernel truncation half-width in units of sigma_t (default 4.0).

    Returns:
        (t, w): Time vector in seconds centered at 0, and complex wavelet kernel w.
    """
    if f0 <= 0:
        raise ValueError(f"f0 must be positive, got {f0}")
    if fs <= 0:
        raise ValueError(f"fs must be positive, got {fs}")
    if f0 >= fs / 2.0:
        raise ValueError(f"f0 ({f0} Hz) must be below Nyquist limit ({fs / 2.0} Hz)")
    if n_cycles <= 0:
        raise ValueError(f"n_cycles must be positive, got {n_cycles}")

    sigma_t = n_cycles / (2.0 * np.pi * f0)
    K = int(np.ceil(cutoff_sigma * sigma_t * fs))
    t = np.arange(-K, K + 1, dtype=np.float64) / fs
    gauss = np.exp(- (t ** 2) / (2.0 * sigma_t ** 2))
    raw = gauss * np.exp(1j * 2.0 * np.pi * f0 * t)

    if normalization == "amplitude":
        norm_factor = 2.0 / np.sum(gauss)
    elif normalization == "energy":
        norm_factor = 1.0 / np.sqrt(np.sum(np.abs(raw) ** 2))
    else:
        raise ValueError(f"Unknown normalization: '{normalization}'. Expected 'amplitude' or 'energy'.")

    return t, raw * norm_factor


def complex_tfr(
    data: np.ndarray,
    fs: float,
    freqs: np.ndarray,
    n_cycles: Union[float, np.ndarray] = 5.0,
    time_axis: int = -1,
    normalization: str = "amplitude",
    dtype: np.dtype = np.complex128,
    coi_sigma: float = 2.0,
) -> ComplexTFR:
    """Compute complex Time-Frequency Representation via Morlet wavelet convolution.

    Args:
        data: Real-valued input signal array of arbitrary dimensionality (..., T).
        fs: Sampling rate in Hz (must be > 0).
        freqs: 1D array of frequency coordinates in Hz (strictly positive and increasing).
        n_cycles: Number of wavelet cycles. Can be a scalar float or a 1D array matching `len(freqs)`.
        time_axis: Axis along which time is sampled (default -1).
        normalization: 'amplitude' (default, unit cosine -> peak |z| = 1.0) or 'energy' (L2 unit energy).
        dtype: Output complex dtype (np.complex128 or np.complex64).
        coi_sigma: Multiplier on sigma_t defining the Cone of Influence (default 2.0).

    Returns:
        ComplexTFR containing complex coefficients tensor `z`, `freqs`, `times`, and `coi_mask`.
    """
    arr = np.asarray(data)
    if not np.issubdtype(arr.dtype, np.number):
        raise TypeError(f"data must be numeric, got dtype {arr.dtype}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("data contains NaN or Inf values")
    if fs <= 0:
        raise ValueError(f"fs must be positive, got {fs}")

    freqs_arr = np.asarray(freqs, dtype=np.float64)
    if freqs_arr.ndim != 1 or len(freqs_arr) == 0:
        raise ValueError(f"freqs must be a non-empty 1D array, got shape {freqs_arr.shape}")
    if np.any(freqs_arr <= 0):
        raise ValueError("All frequencies in freqs must be strictly positive")
    if len(freqs_arr) > 1 and np.any(np.diff(freqs_arr) <= 0):
        raise ValueError("freqs must be strictly monotonically increasing")
    if np.any(freqs_arr >= fs / 2.0):
        raise ValueError(f"All freqs must be strictly below Nyquist ({fs / 2.0} Hz)")

    n_freqs = len(freqs_arr)
    if np.isscalar(n_cycles):
        if n_cycles <= 0:
            raise ValueError(f"n_cycles must be positive, got {n_cycles}")
        cycles_arr = np.full(n_freqs, float(n_cycles), dtype=np.float64)
    else:
        cycles_arr = np.asarray(n_cycles, dtype=np.float64)
        if cycles_arr.shape != freqs_arr.shape:
            raise ValueError(f"n_cycles shape {cycles_arr.shape} must match freqs shape {freqs_arr.shape}")
        if np.any(cycles_arr <= 0):
            raise ValueError("All elements in n_cycles must be strictly positive")

    # Normalize time axis
    time_dim = arr.ndim + time_axis if time_axis < 0 else time_axis
    if time_dim < 0 or time_dim >= arr.ndim:
        raise IndexError(f"time_axis {time_axis} out of bounds for array with ndim {arr.ndim}")

    n_times = arr.shape[time_dim]
    times = np.arange(n_times, dtype=np.float64) / fs

    # Pre-allocate output tensor: insert frequency axis immediately before time axis
    prefix_shape = arr.shape[:time_dim]
    suffix_shape = arr.shape[time_dim + 1:]
    out_shape = prefix_shape + (n_freqs, n_times) + suffix_shape

    z_out = np.zeros(out_shape, dtype=dtype)
    coi_mask = np.ones((n_freqs, n_times), dtype=bool)

    # Convolve for each frequency
    for fi in range(n_freqs):
        f0 = freqs_arr[fi]
        nc = cycles_arr[fi]
        _, w = morlet_wavelet(f0, fs, n_cycles=nc, normalization=normalization)

        # Reshape kernel to match input array dimensionality for fftconvolve
        w_shape = [1] * arr.ndim
        w_shape[time_dim] = -1
        w_shaped = w.reshape(w_shape)

        # Convolution along time_axis
        conv_res = signal.fftconvolve(arr, w_shaped, mode="same", axes=time_dim)

        # Assign into frequency slice
        # Use slice indexing: slice for all leading dimensions, fi for freq dimension
        sl = [slice(None)] * len(out_shape)
        sl[time_dim] = fi
        z_out[tuple(sl)] = conv_res.astype(dtype)

        # COI mask computation for this frequency
        sigma_t = nc / (2.0 * np.pi * f0)
        k_coi = int(np.ceil(coi_sigma * sigma_t * fs))
        if k_coi > 0:
            coi_mask[fi, :min(k_coi, n_times)] = False
            coi_mask[fi, max(0, n_times - k_coi):] = False

    # Broadcast coi_mask to match z_out leading/trailing dimensions if any
    coi_broadcast = np.broadcast_to(
        coi_mask.reshape((1,) * len(prefix_shape) + (n_freqs, n_times) + (1,) * len(suffix_shape)),
        out_shape
    ).copy()

    return ComplexTFR(
        z=z_out,
        freqs=freqs_arr,
        times=times,
        coi_mask=coi_broadcast,
        fs=float(fs),
        n_cycles=cycles_arr,
        normalization=normalization,
    )
