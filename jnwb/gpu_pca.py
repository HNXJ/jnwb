"""Module-internal GPU-accelerated PCA via SVD (not in ``jnwb.__all__``).

Tested helper for matrix PCA with explicit CPU fallback. Public population trajectory
analysis uses ``compute_population_trajectory``.
"""

import logging
from typing import Tuple, Dict, Any
import numpy as np

from ._backend import CUDA, resolve_device, warn_device_fallback
from ._precision import resolve_working_dtype
from ._spread import zscore

log = logging.getLogger(__name__)


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
    uses. A component of all zeros has no largest loading and is left alone.

    Args:
        components: ``(n_components, n_features)`` right singular vectors.
        projections: ``(n_samples, n_components)`` coordinates in that basis.

    Returns:
        The same pair, with the sign of each component and its column of the
        projections flipped together, so their product is unchanged.
    """
    if components.size == 0:
        return components, projections
    pivot = np.argmax(np.abs(components), axis=1)
    signs = np.sign(components[np.arange(components.shape[0]), pivot])
    signs[signs == 0.0] = 1.0
    return components * signs[:, None], projections * signs[None, :]


def gpu_pca(
    matrix: np.ndarray,
    n_components: int = 3,
    device: str = "cuda"
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Perform PCA via SVD on a 2D matrix (n_samples, n_features).
    Center and scale features automatically.

    Args:
        matrix: 2D array of shape (n_samples, n_features)
        n_components: Number of principal components to project onto
        device: 'cuda' or 'cpu'

    Returns:
        projections: (n_samples, n_components) projected coordinates
        components: (n_components, n_features) principal component vectors (V_top)
        explained_variance_ratio: Fraction of total variance explained by kept components
    """
    if matrix.ndim != 2:
        raise ValueError(f"gpu_pca expects a 2D matrix, got shape {matrix.shape}")

    # One rule decides the output dtype, and every return path below goes through it.
    # It used to be applied at the arithmetic alone, so the two paths that return without
    # doing any arithmetic -- the empty early return here, and the padding at the end --
    # both handed back float64 for a float32 matrix. The output dtype then depended on
    # whether the input happened to be empty, or on whether `n_components` happened to
    # exceed the rank, rather than on the input dtype.
    working = resolve_working_dtype(matrix.dtype)

    n_samples, n_features = matrix.shape
    if n_samples == 0 or n_features == 0:
        return (
            np.zeros((n_samples, n_components), working),
            np.zeros((n_components, n_features), working),
            0.0
        )

    # Scale and center; a constant column is exactly 0 and takes no component.
    scaled = zscore(matrix, axis=0)

    # The CUDA branch used to cast to float32 while `_svd_numpy` stayed in float64, so
    # `device=` changed the result by ~1e-4 on top of any sign flip. The working dtype is
    # decided once, above, by `resolve_working_dtype`: float32 stays float32, everything
    # else becomes float64 (which also makes float16 work, since `np.linalg.svd` rejects
    # it outright). Centering and scaling can promote, so re-apply the rule to the result.
    if scaled.dtype != working:
        scaled = scaled.astype(working)

    actual_components = min(n_components, n_samples, n_features)

    def _svd_numpy():
        U, S, Vt = np.linalg.svd(scaled, full_matrices=False)
        V_top = Vt[:actual_components, :]
        return scaled @ V_top.T, V_top, S

    # Resolved once, before any arithmetic. Note the default is device="cuda", so on a
    # CPU-only machine this warns -- deliberately: a function named gpu_pca that quietly
    # returns CPU results is exactly the silence this consolidation exists to remove.
    resolved = resolve_device(device, context="gpu_pca", prefer="torch", stacklevel=3)

    if resolved == CUDA:
        try:
            import torch

            tensor = torch.as_tensor(scaled, device="cuda")
            U, S, V = torch.linalg.svd(tensor, full_matrices=False)
            V_top = V[:actual_components, :]
            proj = tensor @ V_top.t()

            proj_np = proj.cpu().numpy()
            S_np = S.cpu().numpy()
            V_np = V_top.cpu().numpy()
        except Exception as e:
            # Wholesale, not partial: discard the GPU attempt entirely and redo it.
            warn_device_fallback("gpu_pca", e, stacklevel=3)
            log.warning(f"PyTorch SVD failed: {e}. Falling back to NumPy SVD.")
            proj_np, V_np, S_np = _svd_numpy()
    else:
        # Previously the cuda branch fell back to torch-on-CPU in float32 while this
        # branch used float64 NumPy, so "cpu" meant two different precisions depending
        # on which device string was passed. One CPU path now, in float64.
        proj_np, V_np, S_np = _svd_numpy()

    V_np, proj_np = pin_component_signs(V_np, proj_np)

    total_var = np.sum(S_np ** 2)
    explained_variance_ratio = (
        float(np.sum(S_np[:actual_components] ** 2) / total_var)
        if total_var > 0.0
        else 0.0
    )

    # If requested n_components > min(n_samples, n_features), pad output. The padding is
    # allocated in the working dtype: a bare np.zeros defaults to float64 and upcasts a
    # float32 result on assignment, so whether the caller got float32 back depended on
    # whether the rank happened to cover n_components.
    if actual_components < n_components:
        pad_proj = np.zeros((n_samples, n_components), working)
        pad_proj[:, :actual_components] = proj_np
        proj_np = pad_proj

        pad_comp = np.zeros((n_components, n_features), working)
        pad_comp[:actual_components, :] = V_np
        V_np = pad_comp

    return proj_np, V_np, explained_variance_ratio
