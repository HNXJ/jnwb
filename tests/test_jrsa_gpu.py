import numpy as np
import pytest
import jnwb as oa

def test_jrsa_cupy_gpu_execution():
    """Verify that jrsa executes on CUDA using CuPy and returns consistent values."""
    # Generate mock 1D input signals
    rng = np.random.default_rng(42)
    x = rng.normal(0, 1, 100)
    y = x * 0.5 + rng.normal(0, 0.2, 100)

    # Run with default NumPy (CPU) device
    res_cpu = oa.jrsa(x, y, metric="pearson", device="cpu", stats=True, permutations=100)
    assert res_cpu.value is not None
    assert res_cpu.execution["device"] == "cpu"

    # Run with CuPy (GPU) device
    res_gpu = oa.jrsa(x, y, metric="pearson", device="cuda", stats=True, permutations=100)
    assert res_gpu.value is not None
    assert res_gpu.execution["device"] == "cuda"
    assert res_gpu.execution["backend"] == "cupy"

    # Check value consistency between CPU and GPU
    np.testing.assert_allclose(res_cpu.value, res_gpu.value, rtol=1e-5)
    
    # Test spearman correlation consistency
    res_spearman_cpu = oa.jrsa(x, y, metric="spearman", device="cpu")
    res_spearman_gpu = oa.jrsa(x, y, metric="spearman", device="cuda")
    np.testing.assert_allclose(res_spearman_cpu.value, res_spearman_gpu.value, rtol=1e-5)
