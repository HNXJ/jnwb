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

Each row is produced by calling the primitive with `device='cuda'` while counting
`cupy.asarray` and `cupy.asnumpy` calls, and separately recording any `RuntimeWarning`.
**A row claims execution only on a non-zero transfer count.** Several device tests pass on
the fallback branch by design (`test_cuda_matches_cpu_or_warns`), and a skipped test is not
evidence, so neither is relied on here.

Revisions of this receipt through 0.2.4 instead took the *absence* of a `RuntimeWarning` as
proof of execution, on the grounds that `warn_device_fallback` raises one on every fallback.
That inference was unsound, and 05-44 is what makes the warning trustworthy: two call sites
could be denied a GPU they had without warning at all -- `vflip` threw the resolver's answer
away, and `fit_var_bivariate` skipped its GPU branch whenever `ridge > 0`. Silence meant
"nothing announced a fallback", not "the GPU ran". See the two corrections below.

| Primitive | Backend | h2d / d2h | CUDA executed | Max difference vs CPU | Tolerance |
| --- | --- | --- | --- | --- | --- |
| `complex_tfr` | cupy | 26 / 25 | yes | 7.89e-16 | 1e-10 |
| `cross_area_coherence` | cupy | 4 / 0 | yes, `device_used == 'cuda'` | 1.11e-16 | 1e-10 |
| `spectral_tilt` | cupy | 2 / 0 | yes | 5.69e-16 | 1e-10 |
| `relative_power` | cupy | 2 / 1 | yes | 6.66e-16 | 1e-12 |
| `vflip_from_lfp` | -- | **0 / 0** | **no** -- see correction below | n/a | n/a |
| `fit_var_bivariate` (`ridge=0`) | cupy | 4 / 0 | yes | 2.22e-16 | 1e-10 |
| `gpu_pca` | torch | 1 / 0 | yes | 1.91e-12 | 1e-10 |
| `wpli` | cupy | 2 / 0 | yes | 2.05e-15 | 1e-10 |
| `imaginary_coherency` | cupy | 2 / 0 | yes | 1.74e-17 | 1e-10 |

Every row above was re-measured for 0.2.5 by `scratchpad/parity44.py`, which wraps
`cupy.asarray`, `cupy.asnumpy` and `torch.as_tensor` with counters and calls each
primitive once per device. Fixtures: 16384 samples at 1000 Hz with a DC offset of 3.0 for
the pairwise spectral measures at `nperseg=1024`; a 16x5000 array for `complex_tfr` (25
frequencies) and `vflip_from_lfp`; `(8, 25, 200)` against `(8, 25, 1)` for
`relative_power`; 2000 samples at lag 3 for `fit_var_bivariate`; and `(4000, 60)` for
`gpu_pca`. The difference column is the maximum absolute difference over the whole
returned array, or over the float fields of a returned dict.

`gpu_pca` is compared raw, with no sign alignment, which it could not survive before
0.2.5: it cast to float32 inside its CUDA branch while the CPU path stayed in float64, and
neither path pinned an SVD sign, so the raw difference on the projections was 8.005. The
earlier 3.57e-04 figure was measured on component *magnitudes* only, which hides both
defects. 05-43 decides the dtype before the device branch and pins each component's
largest-magnitude loading positive; the residual above is the whole returned array, signs
included. `compute_population_trajectory` measures 9.41e-13 the same way.

`wpli` and `imaginary_coherency` were additionally swept over `nperseg` 255, 256 and 1024
in the 0.2.4 revision, over every returned value; the row above reports the 1024 case from
the 0.2.5 re-measurement. The small changes from the figures recorded in 0.2.4 are fixture
differences, not behaviour changes -- all remain at float64 round-off.

Eight of the eighteen `resolve_device` call sites execute on hardware above. Three route
through the resolver but have no GPU path to execute, and each now says so through
`jnwb._backend.warn_no_gpu_path`: `rdm` and `vflip` have no GPU implementation at all, and
`fit_var_bivariate` has none for `ridge > 0`. The remainder are session-level wrappers that
require NWB fixtures and route through the same resolver verified above; they retain
structural and fallback coverage under clause 1.

The counts in this paragraph are checked by
`tests/test_device_denial_contract.py::TestTheBackendDocstringCountsItsOwnCallSites`
against `jnwb/_backend.py`, which states the same total. "Thirteen" here and "Fifteen" there
were both stale, in opposite directions, for five releases.

## Correction: `vflip_from_lfp` never reached the GPU either

The row above claimed CUDA execution on the same unsound evidence as `wpli`: no
`RuntimeWarning` was emitted. `jnwb/laminar.py` contains no `cupy` or `torch` call anywhere.
`vflip_from_lfp` computes its PSD with `scipy.signal.welch` and forwards `device` to
`vflip`, whose only use of it was `_ = resolve_device(...)` -- the answer was discarded.
Measured on the same A4000, `vflip_from_lfp(lfp(16, 5000), fs=1000, device='cuda')` performs
`h2d=0, d2h=0` transfers. Its "0.00e+00 difference vs CPU" was therefore a comparison of the
CPU path against itself.

Under 05-44 the call emits

    vflip: device='cuda' was requested, but vflip has no GPU implementation; computing on CPU.

so the request is now refused out loud rather than counted as a success. Nothing about what
`vflip` computes changed: regenerating `vflip_calibration_0.2.4_raw.json` from the same 30
seeds reproduces every calibration number bit-identically, differing only in the recorded
source hash and an `environment.jnwb` of 0.2.4 where the previous receipt said 0.2.4rc1.

## Correction: `wpli` never reached the GPU

An earlier revision of this receipt was accepted while `wpli(device='cuda')` had never
executed on a GPU. Its CuPy branch called `cupy.divide(..., where=...)`, which CuPy rejects;
the exception was caught and reported through `log.warning`, not the RuntimeWarning contract,
so a warning-based check saw nothing, and `wpli` was absent from the table above. The branch
also subtracted each segment's mean, which the CPU `stft` path does not, so it would have
disagreed with the CPU had it run. `wpli` and `imaginary_coherency` now resolve the device
through `_backend` and warn on fallback, and the CuPy branch builds the CPU frequency grid.
`tests/test_spectral_nonfabrication.py` checks that a GPU failure warns (on every CI runner)
and, on a CUDA host, that the GPU result matches the CPU.

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
