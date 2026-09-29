# Execution API: numerical identity across CPU, parallel CPU and CUDA

The minimal base of 07-22: before any execution control becomes public (fact D11), identity is
measured for every public operation such a control would cover. Measured 2026-09-29 on the
development machine, `jnwb/` as at `57094a1a`.

## Ruled 2026-09-29

| Question | Ruling |
|---|---|
| The execution surface | (a): per-call `device=` and `n_jobs=` arguments stay, plus one shared field shape in which every result records the device and worker count that ran; no global or scoped state |
| E-1, E-2 (`directed_network` differs with worker count and BLAS thread count) | carried by the integrator as a separate required item |
| E-4 (the comparison helper scored `jrsa`'s call records) | repaired in `tests/test_execution_switch.py`: `_arrays` drops a result dataclass's `execution` and `parameters` fields, as its `to_dict` branch already did. Before, two identical `jrsa` calls scored a gap of 0.51 on `execution.runtime`; after, 0.0 |

The measurement and the options below are kept as they were put.

## What was measured, and against which tolerance

**Scope.** Every export of `jnwb.__all__` (and every public method of an exported class) whose
signature takes `device`, `backend`, `n_jobs`, `precision`, `dtype`, `use_gpu` or `gpu`, found by
`find_switches.py`: 21 callables.

| Switch | Callables | Measured here |
|---|---|---|
| `device` (request) | 16: `band_power`, `relative_power`, `spectral_tilt`, `harmonic_analysis`, `imaginary_coherency`, `wpli`, `cross_area_coherence`, `complex_tfr`, `granger_causality`, `UnitAnalyzer.autocorrelogram`, `PopulationAnalyzer.population_trajectory`, `compute_population_trajectory`, `rdm`, `vflip`, `vflip_from_lfp`, `jrsa` | cuda against cpu |
| `n_jobs` | 4: `cluster_permutation_test`, `cross_area_coherence`, `directed_network`, `jrsa` | 2, 4, 8 and -1 (24 cores) against 1 |
| `backend` (request) | 1: `jrsa` | auto, scipy, cupy, jax, torch against numpy |
| `device`, `backend` (record only) | `ComplexTFR.__init__`, `Provenance.__init__` | nothing: they record what ran and select nothing |
| `dtype` (precision) | `complex_tfr`, `TFRAccumulator.__init__` | nothing: a precision request changes the number by design; each function's policy is `jnwb._precision.PRECISION_POLICY`, held by `tests/test_precision_switch.py` |

**Stated tolerances.** No function states a tolerance of its own in its docstring (read with
`stated_tolerances.py`; the paragraphs it prints name devices, not tolerances).
The tolerances are stated once for the package:

| Comparison | Tolerance | Where stated |
|---|---|---|
| CUDA against CPU, float64 | `max|cuda - cpu| <= 1e-9 * max|cpu|` per output array | `tests/test_execution_switch.py` module docstring (`CUDA_RTOL`); `jnwb/_backend.py` points to it |
| parallel CPU against serial | bit equality | `tests/test_execution_switch.py` docstring; `docs/10_operation_specifications.md` §1 ("identical at every `n_jobs`"); the `directed_network` docstring ("the result is identical for any n_jobs") |
| Metal against CPU, 32-bit | `1e-5 * max|cpu|` | `tests/test_execution_switch.py`; not measured: no Metal hardware, JAX is CPU-only here |

**Gap.** For each numeric leaf of a result, `max|got - ref| / max|ref|` over finite entries; the
operation's gap is its worst leaf, the definition `tests/test_execution_switch.py` uses. A
difference in leaf set, shape or finite mask raises instead of being scored. Fields that record
the call (`execution`, `parameters` of a result dataclass) are not results and are excluded:
the first run scored jrsa's wall time and its echo of `n_jobs` as gaps of 9 to 132, which
`diagnose.py` traced to exactly those two leaves and nothing else.

**Sizes.** "small" is the input of `tests/test_execution_switch.py`; "large" is 8 times longer
along time (and 8 times more permutations or rows where the call has them).

**Machine.** NVIDIA RTX A4000, CuPy 14.0.1, PyTorch 2.12.0+cu126 (CUDA reachable through both),
NumPy 2.4.6, Python 3.14.3, Windows 11, 24 cores, OpenBLAS at 24 threads. `jnwb` imported from
the lane worktree, asserted by path in the script.

**Command.**

```text
python artifacts/evidence/0.2.8/api_proposals/measure_identity.py --json <out.json>
python artifacts/evidence/0.2.8/api_proposals/render_identity.py <out.json>
```

The scripts ran from the lane scratchpad and are copied here unchanged. The raw JSON is not
committed (`.gitignore` excludes `*.json`); the tables below are rendered from it by
`render_identity.py`, not typed. The scripts hold the lane worktree's absolute path in `WT`;
point it at another checkout to re-run.

## Result

| | Operations | Within the stated tolerance |
|---|---|---|
| `device`, cuda against cpu | 16 | 16 of 16 at both sizes; worst gap 1.3e-11 (`spectral_tilt`, small); the six CPU-only operations warn and are bit-identical |
| `n_jobs`, parallel against serial | 4 | 3 of 4. **`directed_network` differs at the large size**: worst gap 1.8e-9, not bit-identical at 2, 4, 8 or -1 workers |
| `backend` | 1 | `jrsa`: bit-identical for all five; cupy, jax and torch warn that NumPy ran |
| `device` and `n_jobs` together | 1 | `cross_area_coherence`, cuda with 8 workers against cpu serial: 1.7e-15 |

## Per operation

### `band_power`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | small | 0 | yes | not recorded | within |
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | large | 0 | yes | not recorded | within |

### `relative_power`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | small | 0 | yes | cpu | within |
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | large | 0 | yes | cpu | within |

### `spectral_tilt`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda vs cpu | rel. 1e-9 | small | 1.3e-11 | no | cuda | within |
| `device` | cuda vs cpu | rel. 1e-9 | large | 1.3e-13 | no | cuda | within |

### `harmonic_analysis`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda vs cpu | rel. 1e-9 | small | 4.1e-16 | no | cuda | within |
| `device` | cuda vs cpu | rel. 1e-9 | large | 2.4e-15 | no | cuda | within |

### `imaginary_coherency`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda vs cpu | rel. 1e-9 | small | 1.2e-16 | no | cuda | within |
| `device` | cuda vs cpu | rel. 1e-9 | large | 0 | yes | cuda | within |

### `wpli`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda vs cpu | rel. 1e-9 | small | 8.0e-16 | no | cuda | within |
| `device` | cuda vs cpu | rel. 1e-9 | large | 8.9e-16 | no | cuda | within |

### `cross_area_coherence`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda vs cpu | rel. 1e-9 | small | 8.4e-16 | no | cuda | within |
| `device` | cuda vs cpu | rel. 1e-9 | large | 1.7e-15 | no | cuda | within |
| `n_jobs` | 2, 4, 8, -1 vs 1 | bit equality | small | worst 0 | yes | n/a | within |
| `n_jobs` | 2, 4, 8, -1 vs 1 | bit equality | large | worst 0 | yes | n/a | within |
| `device` + `n_jobs` | cuda, 8 vs cpu, 1 | rel. 1e-9 | small | 8.4e-16 | no | cuda | within |
| `device` + `n_jobs` | cuda, 8 vs cpu, 1 | rel. 1e-9 | large | 1.7e-15 | no | cuda | within |

### `complex_tfr`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda vs cpu | rel. 1e-9 | small | 1.1e-15 | no | cuda | within |
| `device` | cuda vs cpu | rel. 1e-9 | large | 1.4e-15 | no | cuda | within |

### `granger_causality`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda vs cpu | rel. 1e-9 | small | 3.8e-13 | no | cuda | within |
| `device` | cuda vs cpu | rel. 1e-9 | large | 1.0e-12 | no | cuda | within |

### `UnitAnalyzer.autocorrelogram`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda vs cpu | rel. 1e-9 | small | 0 | yes | cuda | within |
| `device` | cuda vs cpu | rel. 1e-9 | large | 0 | yes | cuda | within |

### `PopulationAnalyzer.population_trajectory`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda vs cpu | rel. 1e-9 | small | 6.3e-15 | no | cuda | within |
| `device` | cuda vs cpu | rel. 1e-9 | large | 6.0e-14 | no | cuda | within |

### `compute_population_trajectory`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda vs cpu | rel. 1e-9 | small | 1.5e-13 | no | cuda | within |
| `device` | cuda vs cpu | rel. 1e-9 | large | 1.2e-13 | no | cuda | within |

### `rdm`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | small | 0 | yes | cpu | within |
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | large | 0 | yes | cpu | within |

### `vflip`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | small | 0 | yes | not recorded | within |
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | large | 0 | yes | not recorded | within |

### `vflip_from_lfp`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | small | 0 | yes | not recorded | within |
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | large | 0 | yes | not recorded | within |

### `jrsa`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | small | 0 | yes | cpu | within |
| `device` | cuda (warns, runs CPU) vs cpu | rel. 1e-9 | large | 0 | yes | cpu | within |
| `n_jobs` | 2, 4, 8, -1 vs 1 | bit equality | small | worst 0 | yes | n/a | within |
| `n_jobs` | 2, 4, 8, -1 vs 1 | bit equality | large | worst 0 | yes | n/a | within |
| `backend` | auto vs numpy | bit equality | small | 0 | yes | numpy | within |
| `backend` | scipy vs numpy | bit equality | small | 0 | yes | numpy | within |
| `backend` | cupy vs numpy | bit equality | small | 0 | yes | numpy | within; warns |
| `backend` | jax vs numpy | bit equality | small | 0 | yes | numpy | within; warns |
| `backend` | torch vs numpy | bit equality | small | 0 | yes | numpy | within; warns |
| `backend` | auto vs numpy | bit equality | large | 0 | yes | numpy | within |
| `backend` | scipy vs numpy | bit equality | large | 0 | yes | numpy | within |
| `backend` | cupy vs numpy | bit equality | large | 0 | yes | numpy | within; warns |
| `backend` | jax vs numpy | bit equality | large | 0 | yes | numpy | within; warns |
| `backend` | torch vs numpy | bit equality | large | 0 | yes | numpy | within; warns |

### `cluster_permutation_test`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `n_jobs` | 2, 4, 8, -1 vs 1 | bit equality | small | worst 0 | yes | n/a | within |
| `n_jobs` | 2, 4, 8, -1 vs 1 | bit equality | large | worst 0 | yes | n/a | within |

### `directed_network`

| Switch | Compared | Stated tolerance | Size | Measured gap | Bit-identical | Device recorded | Verdict |
|---|---|---|---|---|---|---|---|
| `n_jobs` | 2, 4, 8, -1 vs 1 | bit equality | small | worst 0 | yes | n/a | within |
| `n_jobs` | 2, 4, 8, -1 vs 1 | bit equality | large | worst 1.8e-09 | no | n/a | EXCEEDS |

### Timing (seconds, one call, this machine)

| Operation | Size | cpu | cuda |
|---|---|---|---|
| `band_power` | small | 0.0027 | 0.0016 |
| `band_power` | large | 0.0044 | 0.0041 |
| `relative_power` | small | 0.0002 | 0.0001 |
| `relative_power` | large | 0.0002 | 0.0001 |
| `spectral_tilt` | small | 0.0025 | 1.0721 |
| `spectral_tilt` | large | 0.0054 | 0.0229 |
| `harmonic_analysis` | small | 0.002 | 0.004 |
| `harmonic_analysis` | large | 0.0046 | 0.0033 |
| `imaginary_coherency` | small | 0.0075 | 0.0465 |
| `imaginary_coherency` | large | 0.029 | 0.0234 |
| `wpli` | small | 0.0011 | 0.0832 |
| `wpli` | large | 0.0039 | 0.0075 |
| `cross_area_coherence` | small | 0.0636 | 0.0405 |
| `cross_area_coherence` | large | 0.1011 | 0.0503 |
| `complex_tfr` | small | 0.009 | 0.6254 |
| `complex_tfr` | large | 0.0414 | 0.0529 |
| `granger_causality` | small | 0.1966 | 0.643 |
| `granger_causality` | large | 0.0235 | 0.0842 |
| `UnitAnalyzer.autocorrelogram` | small | 0.9553 | 0.2825 |
| `UnitAnalyzer.autocorrelogram` | large | 0.0099 | 0.0052 |
| `PopulationAnalyzer.population_trajectory` | small | 0.0006 | 0.0063 |
| `PopulationAnalyzer.population_trajectory` | large | 0.0016 | 0.0163 |
| `compute_population_trajectory` | small | 0.0151 | 0.1178 |
| `compute_population_trajectory` | large | 0.0188 | 0.0397 |
| `rdm` | small | 0.0006 | 0.0002 |
| `rdm` | large | 0.0007 | 0.0007 |
| `vflip` | small | 0.0006 | 0.0004 |
| `vflip` | large | 0.0005 | 0.0005 |
| `vflip_from_lfp` | small | 0.0033 | 0.003 |
| `vflip_from_lfp` | large | 0.0267 | 0.0254 |
| `jrsa` | small | 0.0158 | 0.0156 |
| `jrsa` | large | 0.1063 | 0.1022 |

| Operation | Size | n_jobs=1 | 2 | 4 | 8 | -1 |
|---|---|---|---|---|---|---|
| `cluster_permutation_test` | small | 0.037 | 9.0695 | 13.1194 | 11.4585 | 16.2548 |
| `cluster_permutation_test` | large | 0.3792 | 7.1623 | 5.0336 | 7.159 | 15.4349 |
| `cross_area_coherence` | small | 0.2095 | 8.9812 | 7.0444 | 9.1778 | 11.4114 |
| `cross_area_coherence` | large | 0.5502 | 5.705 | 4.9047 | 4.3879 | 6.269 |
| `directed_network` | small | 0.7433 | 8.7717 | 10.0312 | 17.5793 | 10.5962 |
| `directed_network` | large | 3.1537 | 5.4936 | 4.8942 | 4.9813 | 5.1762 |
| `jrsa` | small | 0.0624 | 5.3169 | 4.8848 | 6.1399 | 9.8498 |
| `jrsa` | large | 0.4657 | 3.6591 | 3.8348 | 3.7563 | 6.5049 |

machine: {"python": "3.14.3", "platform": "Windows-11-10.0.26200-SP0", "numpy": "2.4.6", "jnwb": "0.2.7", "jnwb_file": "C:\\workspace\\jnwb\\.claude\\worktrees\\lane-c-08-06\\jnwb\\__init__.py", "cpu_count": 24, "cupy_cuda": true, "torch_cuda": true, "jax_metal": false, "cupy": "14.0.1", "gpu": "NVIDIA RTX A4000", "torch": "2.12.0+cu126"}

## Findings

| # | Finding | Evidence | Class |
|---|---|---|---|
| E-1 | `directed_network(method="granger")` changes its numbers with the worker count at the large size (worst relative gap 1.8e-9; absolute differences about 1e-16 on values near 0.2, up to 5e-12 on F statistics), against a stated tolerance of bit equality and fact S6. At the small size, the size `tests/test_parallel.py` uses, it is bit-identical, so that test cannot see this | `n_jobs` rows above | observed |
| E-2 | The serial result itself depends on the BLAS thread count: serial with OpenBLAS limited to one thread differs from serial at the default 24 threads by 1.8e-9, and `n_jobs=4` differs from both. So the defect is thread-count sensitivity of the Granger fits, which worker processes expose | `diagnose_blas.py`: `serial(default BLAS) vs serial(1 BLAS thread): 1.8e-09, False`; `serial(1) vs n_jobs=4: 1.8e-09, False`; `serial(default) vs n_jobs=4: 1.4e-11, False` | observed; the cause (reduction order in the least-squares fits) is inferred |
| E-3 | No operation states its own tolerance. An execution API that promises "changes no number beyond the function's stated tolerance" (goal 11) has one package-wide value per comparison to cite, not a per-function one | `stated_tolerances.py` output; the table above | observed |
| E-4 | `tests/test_execution_switch.py::_worst_relative_gap` walks a result dataclass by all fields; its branch that drops `execution` and `parameters` needs a `to_dict`, which `JRSAResult` lacks. jrsa is CPU-only, so no current comparison reaches it; a CUDA path for jrsa would be scored on its wall time | `diagnose.py`: jrsa repeat differs only in `.execution.runtime`; `AttributeError: 'JRSAResult' object has no attribute 'to_dict'` | observed |
| E-5 | At these sizes every call with workers took 3.7 to 17.6 s against 0.04 to 3.2 s serial, so each `n_jobs > 1` run above is slower than serial | timing table | observed; a speed result, not an identity one |
| E-6 | Metal is not measured: no Metal hardware, and JAX here has only the CPU platform | `jax_metal: false` in the machine record | observed |

## What this means for the execution API

Identity holds, within the stated tolerance, for every `device` path and three of the four
`n_jobs` paths. A public worker control (fact D11: public only once it changes no number) cannot
cover `directed_network` until E-1 is repaired or its tolerance is restated; and the BLAS thread
count (E-2) is a hidden execution control that no API parameter sets today.

## Proposed surface, for Hamm to rule

The measurement is the minimal base; the surface is a public API choice. Options, graded:

| Option | Shape | Grade |
|---|---|---|
| (a) Keep per-call arguments, add one policy record | `device=`, `n_jobs=` stay per call; every result that takes one records `device_used` and `n_jobs` in one field shape; a precision request stays per function (`dtype=`). No global state | 70 |
| (b) A scoped default | `with jnwb.execution(device="cuda", n_jobs=8, blas_threads=1): ...` sets defaults a call's own argument overrides; results record the resolved policy. Pins BLAS threads, which closes E-2 by construction | 55 |
| (c) A global setter | `jnwb.set_execution(...)` | 20: process-wide state changes numbers at a distance |

The cache half of 07-22 (content-addressed checkpoints, fact D3's seven categories) has no
measurement to base it on and is not proposed here.
