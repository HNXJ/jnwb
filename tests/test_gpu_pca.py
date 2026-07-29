"""
Unit tests for GPU-accelerated PCA in jnwb.gpu_pca & jnwb.trajectory.
"""

import numpy as np
import pytest
from jnwb.gpu_pca import gpu_pca


def test_gpu_pca_shape():
    rng = np.random.default_rng(42)
    X = rng.normal(size=(100, 50))
    proj, comp, var_exp = gpu_pca(X, n_components=3, device="cpu")
    assert proj.shape == (100, 3)
    assert comp.shape == (3, 50)
    assert 0.0 <= var_exp <= 1.0


def test_gpu_pca_matches_numpy():
    rng = np.random.default_rng(42)
    X = rng.normal(size=(200, 30))

    # CPU SVD via numpy reference
    mean = np.mean(X, axis=0, keepdims=True)
    std = np.std(X, axis=0, keepdims=True)
    std[std == 0.0] = 1.0
    scaled = (X - mean) / std

    _, S_ref, Vt_ref = np.linalg.svd(scaled, full_matrices=False)
    proj_ref = scaled @ Vt_ref[:3, :].T
    total_var = np.sum(S_ref ** 2)
    var_exp_ref = float(np.sum(S_ref[:3] ** 2) / total_var)

    proj_gpu, comp_gpu, var_exp_gpu = gpu_pca(X, n_components=3, device="cpu")

    # Projections match up to sign flip per component
    for c in range(3):
        corr = np.abs(np.corrcoef(proj_ref[:, c], proj_gpu[:, c])[0, 1])
        assert corr > 0.99, f"Component {c} projection correlation too low: {corr}"

    assert pytest.approx(var_exp_ref, abs=1e-4) == var_exp_gpu


def test_gpu_pca_zero_samples():
    X = np.zeros((0, 10))
    proj, comp, var_exp = gpu_pca(X, n_components=3, device="cpu")
    assert proj.shape == (0, 3)
    assert comp.shape == (3, 10)
    assert var_exp == 0.0
