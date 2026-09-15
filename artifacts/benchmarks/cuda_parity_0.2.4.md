# CUDA execution and CPU parity receipt (0.2.4-15)

Purpose: `docs/install.md` and the `gpu` extra (`cupy-cuda12x`) publicly claim CUDA 12.x
acceleration, so the release needs a receipt of CUDA **executing**, not of CUDA tests passing.
Several device tests pass on the CPU-fallback branch by design (`test_cuda_matches_cpu_or_warns`),
and a skipped test is not evidence either. Each row below was produced by calling the primitive
with `device='cuda'` inside `warnings.catch_warnings(record=True)` and requiring that **no**
`RuntimeWarning` was emitted -- `jnwb._backend.warn_device_fallback` raises one on every fallback,
so its absence is what distinguishes execution from fallback.

## Environment

| Field | Value |
| --- | --- |
| Device | NVIDIA RTX A4000 |
| CUDA runtime | 12090 (12.9) |
| CuPy | 14.0.1 |
| PyTorch | 2.12.0+cu126 |
| `cupy_available()` / `torch_cuda_available()` | True / True |
| `resolve_device('cuda', prefer='cupy'\|'torch'\|None)` | `cuda` in all three |

## Results

| Primitive | Backend | CUDA executed (no fallback warning) | Max difference vs CPU |
| --- | --- | --- | --- |
| `complex_tfr` | cupy | yes | 9.258e-16 (rel) |
| `gpu_pca` | torch | yes | 1.461e-05 (rel, float32 input) |
| `cross_area_coherence` | cupy | yes, `device_used == 'cuda'` | 1.332e-15 (abs, coherence spectrum) |
| `spectral_tilt` | cupy | yes | 2.012e-16 (abs, `exponent`) |

`gpu_pca` compares component magnitudes: PCA component sign is arbitrary, so a raw comparison
would report a spurious mismatch. Its 1e-05 residual is float32 precision, not a discrepancy.

## Scope and what this does NOT establish

- One GPU, one driver, one CUDA version, on Windows. This is not a matrix.
- No CI runner has CUDA, so nothing here is reproduced by remote CI. Regression protection for
  the GPU path remains the structural tests, which pass on CPU-only machines by design.
- Four device-routed primitives were exercised. `resolve_device` has more call sites
  (`analyzers`, `connectivity.fit_var_bivariate`, `trajectory`, `laminar.vflip`, `rsa`); those
  were not measured here.
