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

## Acceptance criterion (0.2.4-15, as scoped for this RC)

1. every publicly CUDA-routed primitive has structural / fallback tests;
2. representative high-risk CUDA paths execute on one real supported CUDA system;
3. CPU/GPU numerical parity is demonstrated within declared tolerances;
4. CI verifies CPU / fallback behaviour.

Multiple GPU machines are explicitly NOT required for this release.

## Clause 1 -- structural and fallback tests

`tests/test_backend.py` (19 tests, 0 skipped) asserts that every routed module imports the
shared resolver and that none probes CuPy with a bare import, so a new call site cannot
acquire its own private device logic. Fallback is observable by contract:
`test_denied_gpu_warning_names_the_caller`, `test_warns_and_names_the_exception`,
`test_says_partial_work_was_discarded`, `test_gpu_failure_falls_back_wholesale_and_warns`,
`test_gpu_pca_warns_when_its_default_device_is_unavailable`.

## Clause 2 and 3 -- real-hardware execution and parity

Each row was produced by calling the primitive with `device='cuda'` inside
`warnings.catch_warnings(record=True)` and requiring that **no** `RuntimeWarning` was
emitted. `jnwb._backend.warn_device_fallback` raises one on every fallback, so its absence
is what distinguishes execution from fallback. Several device tests pass on the fallback
branch by design (`test_cuda_matches_cpu_or_warns`), and a skipped test is not evidence, so
neither is relied on here.

| Primitive | Backend | CUDA executed | Max difference vs CPU | Tolerance |
| --- | --- | --- | --- | --- |
| `complex_tfr` | cupy | yes | 5.83e-16 | 1e-10 |
| `cross_area_coherence` | cupy | yes, `device_used == 'cuda'` | 3.33e-16 | 1e-10 |
| `spectral_tilt` | cupy | yes | 4.58e-16 | 1e-10 |
| `relative_power` | cupy | yes | 0.00e+00 | 1e-12 |
| `vflip_from_lfp` | cupy | yes | 0.00e+00 | 1e-10 |
| `fit_var_bivariate` | cupy | yes | 0.00e+00 | 1e-10 |
| `gpu_pca` | torch | yes | 3.57e-04 | 1e-3 (float32 in) |

`gpu_pca` compares component magnitudes: PCA component sign is arbitrary, so a raw
comparison would report a spurious mismatch. Its 1e-04 residual is float32 precision.

Seven of the ten `resolve_device` call sites are covered. The three not exercised on
hardware -- `compute_population_trajectory`, `population_trajectory`, `UnitAnalyzer.acg` --
are session-level wrappers that require NWB fixtures and route through the same resolver
verified above; they retain structural and fallback coverage under clause 1.

## Clause 4 -- CI

CI runners have no CUDA, so every `device='cuda'` call there takes the fallback branch.
The full suite including `tests/test_backend.py` passes on Python 3.12 and 3.14 across
ubuntu-latest and windows-latest, which is the CPU/fallback verification this clause asks
for. Nothing in this file is reproduced by CI, by construction.

## Environment

| Field | Value |
| --- | --- |
| Device | NVIDIA RTX A4000 |
| CUDA runtime | 12090 (12.9) |
| CuPy | 14.0.1 |
| PyTorch | 2.12.0+cu126 |
| `resolve_device('cuda', prefer='cupy'\|'torch'\|None)` | `cuda` in all three |

## Scope

One GPU, one driver, one CUDA version, on Windows. This is hardware evidence sufficient for
the RC under the criterion above, not a package-wide multi-GPU qualification.
