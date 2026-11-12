# OCMA card spec: `gpu_launch_overhead_0.2.5`

STATUS: draft-awaiting-Hamm

Drafted 2026-11-12 at jnwb `92d118ea` (ocma plan decision 5). No card code exists for this spec. Hamm rules it before any code.

| Field | Value |
|---|---|
| id | `gpu_launch_overhead_0.2.5` |
| objective | Performance card for todo 05-45: the paired CUDA/CPU ratio `R` before and after the launch-overhead repairs of `UnitAnalyzer._acg_vectorized` and `_welch_csd_gpu`, and the measured Welch crossover (receipt, header and "The crossover"). Card kind: validation, section `performance`. The item's original Accept ("no `device='cuda'` path is slower than its CPU sibling") is stated in the receipt as not achievable and is not carried into the card. |
| reference | Todo item 05-45 (receipt header). External references: UNKNOWN. |
| observable | `R = T_cuda / T_cpu`, dimensionless, paired inside one process. Two blocks, never pooled: (a) ACG, axis spikes: 5000 and 35000 (receipt, section 1); (b) Welch, axis samples: 12288 to 4194304 at 1 kHz, and `nperseg` 256, 1024, 4096 (receipt, sections 2 and 3). Absolute milliseconds are not an observable: the receipt says they are not representative. |
| signal_class | Two classes, presented as separate blocks, never pooled (ocma plan, Ontology O; `AGENTS.md` §5). (a) spikes: `UnitAnalyzer._acg_vectorized`, spike-train ACG. (b) LFP or trace: `harmonic_analysis`, `spectral_tilt`, `band_power` through `_welch_csd_gpu`. The receipt does not say the Welch input is LFP: UNKNOWN. |
| claim_class | UNKNOWN. Performance is not one of the claim classes in `AGENTS.md` §5 (magnitude, lag asymmetry, delay, inference). See Flags. |
| dataset | UNKNOWN. Spike-train source and trace source are not named. The receipt names the sizes only: spikes 5000 and 35000 (ACG); a "16384-sample trace" and sizes 12288 to 4194304 (Welch). Environment (receipt, Environment): NVIDIA RTX A4000, driver 595.95, CUDA runtime 12.9, CuPy 14.0.1, PyTorch 2.12.0+cu126, Python 3.14.3, NumPy 2.4.6, SciPy 1.18.0. A peer process (`scripts/e3_condition_6b.py`, not a jnwb script) ran throughout. |
| operations[] | `harmonic_analysis`, `spectral_tilt`, `band_power`, `UnitAnalyzer` (all quoted in `jnwb/__init__.py`). `_acg_vectorized` and `_welch_csd_gpu` are private helpers, not public symbols, and are listed as the code under measurement only. |
| estimand | Paired ratio `R` per input size, `R < 1` meaning the CUDA route is faster; the crossover is the input size where `R` passes 1 (receipt, "Where the two devices cross"). |
| controls[] | CPU sibling in the same process on identical inputs (receipt, header). Warm-up 3, 7 repetitions, median, `cudaDeviceSynchronize` after each CUDA repetition (receipt, Reproducing). Parity: ACG counts bit-identical to the old CPU loop and to the old CUDA loop at 5000 and 35000 spikes (section 1). Welch: 112 of 112 arrays bit-identical over 28 cases (section 2). |
| tolerance | Parity: bit-identical, except at `nperseg` 4096 and 8192, where the outputs shift by up to 1.43e-13 relative (receipt, section 2). Timing tolerance: UNKNOWN (not in receipt). |
| verdict_rule | UNKNOWN as a pass or fail. The receipt reports the measured crossover and states no timing verdict (receipt, "Why this is documented and not automated"). |
| writes[] | Proposed, not in receipt: one `validations` entry with `section: "performance"`. The existing `performance` object in `scripts/dashboard/data.schema.json` holds `baseline`, `peak_memory` and `import` only, and has no field for a paired ratio. A new field would change the schema: Hamm rules. |
| receipt path | `artifacts/benchmarks/performance/gpu_launch_overhead_0.2.5.md` (tracked; last changed by `d50680f4`) |
| sha256 | `6fe8ece04f0539dc400aa45fdc886b5a8aeec463d8820bd09c16da69b71d6120` (hashlib, receipt file) |
| recorded_commit | `c269b7d9a8805447487aa4bd5d3d257801ee1919` (the receipt's "working tree at `c269b7d9`", resolved by `git rev-parse`). The receipt measured a working tree, `c269b7d9` plus the 05-45 repair. The committed state of that repair is UNKNOWN. |

## Flags for Hamm (not resolved here)

1. **Claim class.** No claim class in `AGENTS.md` §5 fits a timing ratio. Hamm rules whether this card is a validation at all, and under which class.
2. **Two signal classes.** The card mixes spike ACG (section 1) and Welch on a trace (sections 2 and 3). The card needs two blocks, each with its own dataset. The Welch input's signal class is UNKNOWN.
3. **Dataset not named.** Spike and trace sources are absent. The receipt cannot be reproduced from its own text beyond the test file it cites (`tests/test_gpu_launch_overhead.py`, exists).
4. **Working tree, not commit.** The receipt measured an uncommitted repair. The committed hash of that repair is UNKNOWN. Hamm rules whether a card may cite a working tree.
5. **Crossover wording.** The receipt says "the crossover is near 22500 samples" (section 3). Its table has `harmonic_analysis` at 1.009 for 22528 and 0.911 for 24576, so that function's crossing lies between 22528 and 24576. `spectral_tilt` (1.009 to 0.973 at 22528) and `band_power` (1.029 to 0.986) cross between 20480 and 22528. The card should state the per-function crossings, not one number.
6. **Parity wording elsewhere.** `artifacts/benchmarks/performance/complexity_inventory.md` (section 4) says `band_power` and `_welch_csd_gpu` have "exact SciPy parity". This receipt (section 2) reports a CPU/CUDA disagreement with SciPy from 2.566e-15 to 4.146e-13, pre-existing. The two statements conflict unless "exact" has a tolerance, which is not stated.
7. **Contention.** The receipt says the machine was contended for every number. Single-run absolute values are not quotable; only paired ratios are.

## Figure (proposed)

UNKNOWN. Candidate: `R` against samples, one line per function, log x axis, with the 1.0 line. Hamm rules.
