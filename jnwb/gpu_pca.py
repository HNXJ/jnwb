"""Module-internal SVD helpers (not in ``jnwb.__all__``).

``pin_component_signs`` fixes the sign of each principal component, and ``_svd_numpy`` is the
NumPy SVD fallback of ``compute_population_trajectory``.
"""

from typing import Tuple
import numpy as np


def pin_component_signs(
    components: np.ndarray, projections: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Force each component's largest-magnitude loading positive.

    An SVD determines each component only up to a sign: ``V`` and ``-V`` describe the
    same subspace and explain the same variance, and LAPACK and cuSOLVER routinely
    choose differently for the same matrix, component by component. Callers saw that as
    components whose sign disagreed between devices, with ``max|cpu - cuda| / |cpu| == 2``
    -- the exact signature of a flipped component, and indistinguishable from a real
    disagreement until you align the signs by hand. The device must never change a number,
    so the convention is pinned in the library rather than left to whichever routine ran.

    Any rule fixed by the data works; this is the one `sklearn.utils.extmath.svd_flip`
    uses, with ties broken by index. A component of all zeros has no largest loading and
    is left alone.

    Ties: loadings whose magnitudes agree to within ``sqrt(eps)`` of the component's dtype,
    relative to the largest, are treated as tied, and the lowest-index one is the pivot.
    Plain ``argmax`` let rounding choose among tied loadings, and ties are routine: two
    z-scored features always give components ``[1, 1]/sqrt(2)`` and ``[1, -1]/sqrt(2)``,
    where LAPACK and cuSOLVER round the two magnitudes differently and so pinned opposite
    signs in 32 of 200 matrices.

    Args:
        components: ``(n_components, n_features)`` right singular vectors.
        projections: ``(n_samples, n_components)`` coordinates in that basis.

    Returns:
        The same pair, with the sign of each component and its column of the
        projections flipped together, so their product is unchanged.
    """
    if components.size == 0:
        return components, projections
    magnitude = np.abs(components)
    dtype = components.dtype if np.issubdtype(components.dtype, np.floating) else np.float64
    tol = np.sqrt(np.finfo(dtype).eps)
    tied = magnitude >= magnitude.max(axis=1, keepdims=True) * (1.0 - tol)
    pivot = np.argmax(tied, axis=1)
    signs = np.sign(components[np.arange(components.shape[0]), pivot])
    signs[signs == 0.0] = 1.0
    return components * signs[:, None], projections * signs[None, :]


def _svd_numpy(matrix: np.ndarray, n_components: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The NumPy SVD fallback of `compute_population_trajectory`.

    Returns the projections onto the top ``n_components`` right singular vectors, those
    vectors, and every singular value.
    """
    _, S, Vt = np.linalg.svd(matrix, full_matrices=False)
    V_top = Vt[:n_components, :]
    return matrix @ V_top.T, V_top, S
