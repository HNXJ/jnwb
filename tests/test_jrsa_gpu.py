import numpy as np
import pytest
import jnwb as oa


def _cuda_device_is_usable() -> bool:
    """Importable is not usable.

    This used to be `import cupy` in a try block. CuPy installs without a GPU, and on such a
    machine the test below ran and failed: `jrsa` refuses the device in `resolve_device` and
    warns that none was found, never reaching the "computes in NumPy" message the test waits
    for. CI never saw it because CI does not install CuPy at all.
    """
    try:
        from jnwb._backend import gpu_available
    except ImportError:  # pragma: no cover - jnwb is a hard dependency of this file
        return False
    return bool(gpu_available(prefer="cupy"))


requires_cupy = pytest.mark.skipif(
    not _cuda_device_is_usable(),
    reason="no usable CUDA device via CuPy on this machine",
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

    # Run with CuPy (GPU) requested. jrsa does not execute on the GPU -- every
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
    # The device never changes a number.
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
    # null='iid': x and y are i.i.d. draws, and a paired-metric bootstrap requires it named.
    res_stats_cpu = oa.jrsa(x, y, metric="pearson", device="cpu", stats=True, permutations=200, bootstrap=200, random_state=42, null="iid")
    res_stats_gpu = oa.jrsa(x, y, metric="pearson", device="cuda", stats=True, permutations=200, bootstrap=200, random_state=42, null="iid")
    
    # We verify that permutation p-values and confidence intervals are closely aligned
    # (they are computed using identical seeded random_state)
    np.testing.assert_allclose(res_stats_cpu.p, res_stats_gpu.p, rtol=1e-2, atol=1e-2)
    np.testing.assert_allclose(res_stats_cpu.ci, res_stats_gpu.ci, rtol=1e-2, atol=1e-2)


def _paired_inputs():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(12, 30))
    b = a @ rng.normal(size=(30, 30)) * 0.2 + rng.normal(size=(12, 30))
    return a, b


def _value(x1, x2, metric):
    return float(np.asarray(oa.jrsa(x1, x2, metric=metric, stats=False).value).ravel()[0])


def _torch_cuda_is_usable() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


@pytest.mark.parametrize("metric", ["cka", "rsa"])
class TestInputConversion:
    """Every accepted input type gives the dense-array value, and a mask is never dropped.

    Conversion used to take `.data` from any object carrying one: a sparse matrix became
    its stored non-zeros (CKA 0.011 against 0.801, RSA NaN), a CuPy array became a device
    pointer and raised, and a masked array lost its mask.
    """

    def test_scipy_sparse_matches_dense(self, metric):
        sparse = pytest.importorskip("scipy.sparse")
        a, b = _paired_inputs()
        assert _value(sparse.csr_matrix(a), sparse.csr_matrix(b), metric) == pytest.approx(
            _value(a, b, metric), rel=1e-12)

    def test_masked_element_raises(self, metric):
        a, b = _paired_inputs()
        masked = np.ma.masked_array(a, mask=np.zeros_like(a, dtype=bool))
        masked.mask[0, :5] = True
        with pytest.raises(TypeError, match="mask"):
            oa.jrsa(masked, b, metric=metric, stats=False)

    def test_unmasked_masked_array_matches_dense(self, metric):
        a, b = _paired_inputs()
        assert _value(np.ma.masked_array(a), b, metric) == pytest.approx(
            _value(a, b, metric), rel=1e-12)

    @requires_cupy
    def test_cupy_matches_dense(self, metric):
        import cupy as cp
        a, b = _paired_inputs()
        assert _value(cp.asarray(a), cp.asarray(b), metric) == pytest.approx(
            _value(a, b, metric), rel=1e-12)

    @pytest.mark.skipif(not _torch_cuda_is_usable(), reason="no CUDA device via torch")
    def test_torch_cuda_matches_dense(self, metric):
        import torch
        a, b = _paired_inputs()
        assert _value(torch.tensor(a).cuda(), torch.tensor(b).cuda(), metric) == pytest.approx(
            _value(a, b, metric), rel=1e-12)

