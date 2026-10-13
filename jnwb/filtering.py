'''Digital Filtering primitives for continuous neural and physiological time series.

Provides Second-Order Sections (SOS) bandpass and notch filtering with explicit
distinction between zero-phase forward-backward filtering (acausal, zero phase distortion,
doubled effective filter order) and causal forward-only filtering (preserves filter delay).
'''
from __future__ import annotations

import numpy as np
from scipy import signal


def bandpass_filter(
    data: np.ndarray,
    fs: float,
    low_cut: float,
    high_cut: float,
    order: int = 4,
    zero_phase: bool = True,
    axis: int = -1,
) -> np.ndarray:
    '''Apply a Butterworth bandpass filter using Second-Order Sections (SOS).

    References:
        Virtanen, P., et al. (2020). SciPy 1.0: fundamental algorithms for
        scientific computing in Python. Nat. Methods. doi:10.1038/s41592-019-0686-2
        -- the scipy.signal routines this runs through: Butterworth SOS design
        (butter) with zero-phase forward-backward (sosfiltfilt) or causal forward
        (sosfilt) application. The paper describes the library, not this filter.
    '''
    if fs <= 0:
        raise ValueError(f"Sampling frequency fs must be strictly positive; got {fs}.")
    nyquist = fs / 2.0
    if low_cut <= 0:
        raise ValueError(f"low_cut must be strictly positive; got {low_cut}.")
    if high_cut >= nyquist:
        raise ValueError(f"high_cut ({high_cut} Hz) must be less than Nyquist frequency ({nyquist} Hz).")
    if low_cut >= high_cut:
        raise ValueError(f"low_cut ({low_cut}) must be strictly less than high_cut ({high_cut}).")
    if order < 1:
        raise ValueError(f"Filter order must be at least 1; got {order}.")

    arr = np.asarray(data, dtype=float)
    if not np.isfinite(arr).all():
        raise ValueError("Cannot filter data containing non-finite values (NaN or Inf). Repair or omit missing values prior to filtering.")

    sos = signal.butter(order, [low_cut, high_cut], btype="bandpass", fs=fs, output="sos")
    if zero_phase:
        try:
            return signal.sosfiltfilt(sos, arr, axis=axis)
        except ValueError as err:
            raise ValueError(
                f"Signal length along axis {axis} ({arr.shape[axis]}) is too short for zero-phase "
                f"bandpass filtering with order {order}: {err}"
            ) from err
    return signal.sosfilt(sos, arr, axis=axis)


def notch_filter(
    data: np.ndarray,
    fs: float,
    freq: float = 60.0,
    q: float = 30.0,
    zero_phase: bool = True,
    axis: int = -1,
) -> np.ndarray:
    '''Apply an IIR notch filter using Second-Order Sections (SOS) conversion.

    References:
        Virtanen, P., et al. (2020). SciPy 1.0: fundamental algorithms for
        scientific computing in Python. Nat. Methods. doi:10.1038/s41592-019-0686-2
        -- the scipy.signal routines this runs through: notch design (iirnotch),
        transfer-function to SOS conversion (tf2sos), and zero-phase (sosfiltfilt)
        or causal (sosfilt) application. The paper describes the library, not this filter.
    '''
    if fs <= 0:
        raise ValueError(f"Sampling frequency fs must be strictly positive; got {fs}.")
    nyquist = fs / 2.0
    if freq <= 0:
        raise ValueError(f"Notch center frequency must be strictly positive; got {freq}.")
    if freq >= nyquist:
        raise ValueError(f"Notch frequency ({freq} Hz) must be less than Nyquist frequency ({nyquist} Hz).")
    if q <= 0:
        raise ValueError(f"Quality factor q must be strictly positive; got {q}.")

    arr = np.asarray(data, dtype=float)
    if not np.isfinite(arr).all():
        raise ValueError("Cannot filter data containing non-finite values (NaN or Inf). Repair or omit missing values prior to filtering.")

    b, a = signal.iirnotch(freq, q, fs=fs)
    sos = signal.tf2sos(b, a)
    if zero_phase:
        try:
            return signal.sosfiltfilt(sos, arr, axis=axis)
        except ValueError as err:
            raise ValueError(
                f"Signal length along axis {axis} ({arr.shape[axis]}) is too short for zero-phase "
                f"notch filtering: {err}"
            ) from err
    return signal.sosfilt(sos, arr, axis=axis)
