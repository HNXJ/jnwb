"""Module-internal GPU-accelerated PCA via SVD (not in ``jnwb.__all__``).

Tested helper for matrix PCA with explicit CPU fallback. Public population trajectory
analysis uses ``compute_population_trajectory``.
"""

import logging
from typing import Tuple, Dict, Any
import numpy as np

from ._backend import CUDA, resolve_device, warn_device_fallback

log = logging.getLogger(__name__)


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

    n_samples, n_features = matrix.shape
    if n_samples == 0 or n_features == 0:
        return (
            np.zeros((n_samples, n_components)),
            np.zeros((n_components, n_features)),
            0.0
        )

    # Scale and center
    mean = np.mean(matrix, axis=0, keepdims=True)
    std = np.std(matrix, axis=0, keepdims=True)
    std[std == 0.0] = 1.0
    scaled = (matrix - mean) / std

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

            tensor = torch.tensor(scaled, dtype=torch.float32, device="cuda")
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

    total_var = np.sum(S_np ** 2)
    explained_variance_ratio = (
        float(np.sum(S_np[:actual_components] ** 2) / total_var)
        if total_var > 0.0
        else 0.0
    )

    # If requested n_components > min(n_samples, n_features), pad output
    if actual_components < n_components:
        pad_proj = np.zeros((n_samples, n_components))
        pad_proj[:, :actual_components] = proj_np
        proj_np = pad_proj

        pad_comp = np.zeros((n_components, n_features))
        pad_comp[:actual_components, :] = V_np
        V_np = pad_comp

    return proj_np, V_np, explained_variance_ratio
