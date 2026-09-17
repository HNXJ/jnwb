"""
Unit tests for GPU-accelerated PCA in jnwb.gpu_pca & jnwb.trajectory.
"""

import sys

import numpy as np
import pytest
from jnwb.gpu_pca import gpu_pca


def _eigh_reference(X, k):
    """Principal components via eigendecomposition of the scatter matrix.

    A different route to the same quantity than the implementation's SVD: the
    eigenvectors of Z'Z are the right singular vectors of Z, and its eigenvalues are the
    squared singular values. `np.linalg.eigh` and `np.linalg.svd` are different LAPACK
    drivers, so a bug in the one the implementation calls cannot cancel here.

    The standardisation is recomputed rather than taken from the library, so a change
    there is caught too.
    """
    mean = np.mean(X, axis=0, keepdims=True)
    std = np.std(X, axis=0, keepdims=True)
    std[std == 0.0] = 1.0
    Z = (X - mean) / std

    evals, evecs = np.linalg.eigh(Z.T @ Z)
    order = np.argsort(evals)[::-1]
    evals = evals[order]
    V = evecs[:, order].T[:k, :].copy()

    # The library's documented convention: largest-magnitude loading positive.
    for c in range(V.shape[0]):
        j = np.argmax(np.abs(V[c]))
        if V[c, j] < 0:
            V[c] = -V[c]

    return Z @ V.T, V, float(np.sum(evals[:k]) / np.sum(evals))


def test_gpu_pca_shape():
    rng = np.random.default_rng(42)
    X = rng.normal(size=(100, 50))
    proj, comp, var_exp = gpu_pca(X, n_components=3, device="cpu")
    assert proj.shape == (100, 3)
    assert comp.shape == (3, 50)
    assert 0.0 <= var_exp <= 1.0


def test_gpu_pca_matches_an_independent_eigendecomposition():
    """Replaces a comparison against a copy of the implementation.

    The previous version computed its "numpy reference" as
    `np.linalg.svd(scaled, full_matrices=False)` then `scaled @ Vt[:3].T` -- line for
    line `_svd_numpy()`, the branch it was checking -- and compared with `abs(corr)`,
    which is invariant to sign and so could not see `pin_component_signs` either.
    """
    rng = np.random.default_rng(42)
    X = rng.normal(size=(200, 30))

    proj_ref, comp_ref, var_ref = _eigh_reference(X, 3)
    proj, comp, var_exp = gpu_pca(X, n_components=3, device="cpu")

    # Non-vacuity: three of thirty components must explain a proper fraction. At 0 or 1
    # the comparisons below would hold for degenerate outputs too.
    assert 0.05 < var_ref < 0.95, var_ref

    np.testing.assert_allclose(comp, comp_ref, atol=1e-8)
    np.testing.assert_allclose(proj, proj_ref, atol=1e-8)
    assert var_exp == pytest.approx(var_ref, abs=1e-12)


def test_gpu_pca_pins_each_component_sign():
    """The `abs(corr)` comparison this replaces was blind to this by construction."""
    rng = np.random.default_rng(1)
    X = rng.normal(size=(120, 8))
    _, comp, _ = gpu_pca(X, n_components=3, device="cpu")
    for c in range(comp.shape[0]):
        largest = comp[c, np.argmax(np.abs(comp[c]))]
        assert largest > 0, f"component {c} has its largest loading negative: {largest}"


def test_gpu_pca_falls_back_to_numpy_when_torch_is_unavailable(monkeypatch):
    """The CUDA branch's except path, exercised without a GPU.

    `resolve_device` is pinned to CUDA so the branch is entered on any machine, and
    `import torch` is made to fail inside it -- setting a module to None in `sys.modules`
    is what makes its import raise.

    What this establishes: the fallback's control flow, that a failed GPU attempt is
    discarded wholesale, warns, and returns the NumPy answer. What it does not establish:
    that CUDA execution works, or that GPU and CPU agree numerically on real hardware.
    Neither is reachable without a GPU in the runner, and this test must not be read as
    covering them.
    """
    import jnwb.gpu_pca as mod

    monkeypatch.setattr(mod, "resolve_device", lambda *a, **k: mod.CUDA)
    monkeypatch.setitem(sys.modules, "torch", None)

    rng = np.random.default_rng(42)
    X = rng.normal(size=(60, 10))

    with pytest.warns(Warning):
        proj, comp, var_exp = gpu_pca(X, n_components=3, device="cuda")

    proj_ref, comp_ref, var_ref = _eigh_reference(X, 3)
    np.testing.assert_allclose(comp, comp_ref, atol=1e-8)
    np.testing.assert_allclose(proj, proj_ref, atol=1e-8)
    assert var_exp == pytest.approx(var_ref, abs=1e-12)


def test_gpu_pca_zero_samples():
    X = np.zeros((0, 10))
    proj, comp, var_exp = gpu_pca(X, n_components=3, device="cpu")
    assert proj.shape == (0, 3)
    assert comp.shape == (3, 10)
    assert var_exp == 0.0
