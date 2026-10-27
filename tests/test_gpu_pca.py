"""
Unit tests for the SVD helpers in jnwb.gpu_pca that jnwb.trajectory uses.
"""

import sys

import numpy as np
import pytest


def test_the_trajectory_falls_back_to_numpy_when_torch_is_unavailable(monkeypatch):
    """The CUDA branch's except path, exercised without a GPU.

    `resolve_device` is pinned to CUDA so the branch is entered on any machine, and
    `import torch` is made to fail inside it -- setting a module to None in `sys.modules`
    is what makes its import raise. The NumPy answer is taken first, on the CPU, so the
    comparison does not depend on the patched resolver.

    What this establishes: the fallback's control flow, that a failed GPU attempt is
    discarded wholesale, warns, and returns the NumPy answer. What it does not establish:
    that CUDA execution works, or that GPU and CPU agree numerically on real hardware.
    Neither is reachable without a GPU in the runner, and this test must not be read as
    covering them.
    """
    import jnwb.trajectory as traj

    X = np.random.default_rng(42).normal(size=(12, 6, 20))
    monkeypatch.setattr(traj, "build_time_resolved_matrix",
                        lambda *a, **k: (X, list(range(6)), np.arange(20.0)))
    cpu = traj.compute_population_trajectory(None, "A", None, n_components=3, device="cpu")

    monkeypatch.setattr(traj, "resolve_device", lambda *a, **k: traj.CUDA)
    monkeypatch.setitem(sys.modules, "torch", None)
    with pytest.warns(Warning):
        fallback = traj.compute_population_trajectory(
            None, "A", None, n_components=3, device="cuda")

    np.testing.assert_allclose(fallback["trajectory"], cpu["trajectory"], atol=1e-12)
    assert fallback["device_used"] == "cpu"


def test_the_trajectory_and_the_svd_helper_share_one_fallback():
    """The NumPy SVD fallback is one private helper, in `jnwb.gpu_pca`, that the trajectory calls."""
    import jnwb.gpu_pca as gpu_module
    import jnwb.trajectory as trajectory_module

    assert trajectory_module._svd_numpy is gpu_module._svd_numpy


def test_the_svd_fallback_helper_is_the_explicit_svd_bit_for_bit():
    from jnwb.gpu_pca import _svd_numpy

    scaled = np.random.default_rng(7).standard_normal((40, 6))
    proj, V_top, S = _svd_numpy(scaled, 3)
    _, S_ref, Vt = np.linalg.svd(scaled, full_matrices=False)
    np.testing.assert_array_equal(V_top, Vt[:3, :])
    np.testing.assert_array_equal(proj, scaled @ Vt[:3, :].T)
    np.testing.assert_array_equal(S, S_ref)


def test_gpu_pca_is_removed_from_its_module_and_the_package_surface():
    import jnwb
    import jnwb.gpu_pca as gpu_module

    assert not hasattr(gpu_module, "gpu_pca"), "gpu_pca was removed in 0.2.14"
    assert "gpu_pca" not in jnwb.__all__
