"""
Standalone GPU-accelerated PCA helper for arbitrary matrices in jnwb.trajectory.
Extends existing compute_population_trajectory functionality by providing a direct
gpu_pca(matrix, n_components=3, device='cuda') function with explicit NumPy fallback
and verification testing.
"""

import logging
from typing import Tuple, Dict, Any
import numpy as np

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

    if device == "cuda":
        try:
            import torch
            use_gpu = torch.cuda.is_available()
            target_device = "cuda" if use_gpu else "cpu"
            tensor = torch.tensor(scaled, dtype=torch.float32, device=target_device)
            U, S, V = torch.linalg.svd(tensor, full_matrices=False)
            V_top = V[:actual_components, :]
            proj = tensor @ V_top.t()

            proj_np = proj.cpu().numpy() if use_gpu else proj.numpy()
            S_np = S.cpu().numpy() if use_gpu else S.numpy()
            V_np = V_top.cpu().numpy() if use_gpu else V_top.numpy()
        except Exception as e:
            log.warning(f"PyTorch SVD failed: {e}. Falling back to NumPy SVD.")
            U, S, Vt = np.linalg.svd(scaled, full_matrices=False)
            V_np = Vt[:actual_components, :]
            proj_np = scaled @ V_np.T
            S_np = S
    else:
        U, S, Vt = np.linalg.svd(scaled, full_matrices=False)
        V_np = Vt[:actual_components, :]
        proj_np = scaled @ V_np.T
        S_np = S

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
