"""
Complex TFR Preprocessing & Complex Functional Metrics Helper.
Provides methods to save/load real and imaginary Morlet wavelet coefficients,
and compute Phase-Locking Value (PLV) and Imaginary Coherence across complex TFR signals.
"""

import logging
from typing import Tuple, Dict, Optional
import numpy as np

log = logging.getLogger(__name__)


def tfr_complex_load(
    re_path: str,
    im_path: str
) -> np.ndarray:
    """
    Load real and imaginary coefficient arrays and reconstruct complex TFR array.

    Returns:
        Complex array of shape matching input files (dtype=np.complex128)
    """
    re = np.load(re_path)
    im = np.load(im_path)
    if re.shape != im.shape:
        raise ValueError(f"Shape mismatch between real {re.shape} and imag {im.shape}")
    return re.astype(np.float64) + 1j * im.astype(np.float64)


def plv_from_complex(z1: np.ndarray, z2: np.ndarray, axis: int = -1) -> float:
    """
    Compute Phase-Locking Value (PLV) between two complex TFR coefficient arrays.

    PLV = | mean( exp(i * (phase1 - phase2)) ) |

    Args:
        z1, z2: Complex arrays of matching shape
        axis: Axis over which to average phases (e.g., time or trials)

    Returns:
        Scalar PLV in range [0, 1]
    """
    z1 = np.asarray(z1)
    z2 = np.asarray(z2)
    if z1.shape != z2.shape:
        raise ValueError(f"Shape mismatch: {z1.shape} vs {z2.shape}")

    # Phase difference unit vectors
    phi1 = np.angle(z1)
    phi2 = np.angle(z2)
    phase_diff = phi1 - phi2

    # Mean vector length
    complex_mean = np.mean(np.exp(1j * phase_diff), axis=axis)
    plv = np.abs(complex_mean)
    return float(np.mean(plv))


def imaginary_coherence(z1: np.ndarray, z2: np.ndarray, axis: int = -1) -> np.ndarray:
    """
    Compute Imaginary Coherence (icoh) between two complex signal arrays.

    icoh = Im( S12 ) / sqrt( S11 * S22 )

    Imcoherence eliminates zero-lag volume conduction artifacts.

    Args:
        z1, z2: Complex arrays of matching shape
        axis: Axis over which to compute expectations (e.g. trials/time)

    Returns:
        Imaginary coherence array
    """
    z1 = np.asarray(z1)
    z2 = np.asarray(z2)
    if z1.shape != z2.shape:
        raise ValueError(f"Shape mismatch: {z1.shape} vs {z2.shape}")

    s12 = np.mean(z1 * np.conj(z2), axis=axis)
    s11 = np.real(np.mean(z1 * np.conj(z1), axis=axis))
    s22 = np.real(np.mean(z2 * np.conj(z2), axis=axis))

    denom = np.sqrt(s11 * s22)
    denom[denom == 0.0] = 1.0

    return np.imag(s12) / denom
