import numpy as np
import pytest
import jnwb as oa


def _cupy_available() -> bool:
    try:
        import cupy  # noqa: F401
    except ImportError:
        return False
    return True


requires_cupy = pytest.mark.skipif(
    not _cupy_available(),
    reason="cupy not installed / no CUDA GPU available on this machine",
)


@requires_cupy
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

    # Run with CuPy (GPU) requested. 05-26: jrsa does not execute on the GPU -- every
    # metric calls `_ensure_np` on its first line, so the upload was converted straight
    # back and the arithmetic ran on the CPU. This used to assert
    # `execution["device"] == "cuda"`, which is what made the false provenance look
    # verified. The request is still honoured as a request, and recorded in `parameters`.
    with pytest.warns(RuntimeWarning, match="computes in NumPy"):
        res_gpu = oa.jrsa(x, y, metric="pearson", device="cuda", stats=True, permutations=100)
    assert res_gpu.value is not None
    assert res_gpu.execution["device"] == "cpu"
    assert res_gpu.execution["backend"] == "numpy"
    assert res_gpu.parameters["device"] == "cuda"
    assert res_gpu.parameters["backend"] == "auto"

    # The values agree exactly, not merely to rtol: it is the same code path.
    # `AGENTS.md` invariant 6 -- the device never changes a number.
    np.testing.assert_array_equal(np.asarray(res_cpu.value), np.asarray(res_gpu.value))
    
    # Test spearman correlation consistency
    res_spearman_cpu = oa.jrsa(x, y, metric="spearman", device="cpu")
    res_spearman_gpu = oa.jrsa(x, y, metric="spearman", device="cuda")
    np.testing.assert_allclose(res_spearman_cpu.value, res_spearman_gpu.value, rtol=1e-5)

    # Test cosine similarity consistency
    res_cosine_cpu = oa.jrsa(x, y, metric="cosine", device="cpu")
    res_cosine_gpu = oa.jrsa(x, y, metric="cosine", device="cuda")
    np.testing.assert_allclose(res_cosine_cpu.value, res_cosine_gpu.value, rtol=1e-5)

    # Test permutation test and bootstrapping consistency
    res_stats_cpu = oa.jrsa(x, y, metric="pearson", device="cpu", stats=True, permutations=200, bootstrap=200, random_state=42)
    res_stats_gpu = oa.jrsa(x, y, metric="pearson", device="cuda", stats=True, permutations=200, bootstrap=200, random_state=42)
    
    # We verify that permutation p-values and confidence intervals are closely aligned
    # (they are computed using identical seeded random_state)
    np.testing.assert_allclose(res_stats_cpu.p, res_stats_gpu.p, rtol=1e-2, atol=1e-2)
    np.testing.assert_allclose(res_stats_cpu.ci, res_stats_gpu.ci, rtol=1e-2, atol=1e-2)

