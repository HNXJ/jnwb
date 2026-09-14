# 0.2.0



# 0.2.1


# 0.2.2


# 0.2.3

- 0.2.3-REV-10: Fix `coi_mask` broadcasting in `complex_tfr`: reshape `coi_mask` to align with arbitrary `time_axis` positions in multi-dimensional arrays (EXT-REV-010).
- 0.2.3-REV-11: Ensure `label_layers` assigns `"na"` to bad contacts and out-of-bounds channels even on accepted fits, matching documented invariants (EXT-REV-011).
- 0.2.3-01: Formalize testing.synth with reusable generators (known laminar motif, white noise, AR/autocorrelated noise, periodic shared response with no condition effect, unequal groups, missing contacts, contiguous correlation blocks, phase-gradient/coherence structures) as test infrastructure, not empirical evidence; establish canonical synthetic NWB fixture file for executable tutorials.
- 0.2.3-02: Implement xflip locking semantics first (input axis, Pearson/Spearman/partial definitions, contiguous vs unrestricted grouping, minimum block size, boundary representation, surrogate construction preserving temporal autocorrelation where declared, RNG, p-value resolution, failure behavior).
- 0.2.3-03: Calibrate xflip false-positive control and recovery across known blocks, no-block null, white noise, AR noise, periodic common response, unequal blocks, edge cases, same-seed determinism, and different-seed variation.
- 0.2.3-04: Implement zflip reusing existing complex spectral primitives (imaginary coherency / wpli); docs state exact estimator.
- 0.2.3-05: Calibrate zflip across known phase structures, gradients, zero-lag shared reference (must not manufacture imaginary coherency), independent signals, AR signals, periodic responses, same/different RNG.
- 0.2.3-RSA: Review and, if justified, factor reusable RDM/RSA primitives from `jrsa`. Inspect `jrsa`, tests, exports, dependencies, metrics, shapes, NaN/precision semantics, statistical comparison, CPU complexity/memory, condensed versus full materialization, and existing internal RDM functionality. Benchmark NumPy/SciPy, CuPy, and JAX only where available and justified. Determine the smallest generic API before implementation. Candidate surfaces are `rdm(...)` and `rdm_similarity(...)`; names/signatures are proposals, not authority. Preserve existing `jrsa` behavior unless a defect is demonstrated. If primitives are added, make `jrsa` delegate rather than retain duplicate estimators. Require full/condensed equivalence, batching equivalence, dtype behavior, nonfinite policy, symmetry/diagonal invariants, backend numerical parity, explicit backend/device reporting, complexity/memory documentation, and representative (N,D) benchmarks. Add no omission semantics. Do not add JAX/CuPy dependencies or GPU paths without measured benefit. Stop on a scientifically meaningful numerical trade-off.
- 0.2.3-06: Computational complexity, CPU parallelism, and CUDA checklist review:
  * Complexity inventory: Derive Big-O time and memory for every material primitive (PSD/TFR, connectivity, population trajectories, permutation/null, compressed NPZ streaming, vFLIP/xFLIP/zFLIP, NWB extraction) using standard symbols (C=channels, T=time, F=frequencies, R=trials, S=surrogates/permutations).
  * Hotspot benchmark: Benchmark representative small, medium, and large synthetic workloads recording wall time and peak RAM.
  * CPU parallel audit: Audit independent dimensions (channels, trials, frequencies, permutations, sessions); enforce deterministic child RNG via SeedSequence.spawn; prevent nested oversubscription.
  * CUDA audit: Classify hotspots as CPU_ONLY_JUSTIFIED, CUDA_AVAILABLE, CUDA_WORTH_ADDING, or CUDA_NOT_JUSTIFIED.
  * Transfer-cost gate: Accept GPU implementation only when end-to-end performance including host-device transfer materially improves an appropriate workload.
  * Numerical parity: Verify CPU and CUDA preserve identical estimators to declared tolerance with observable failure fallback and zero mixed-estimator partial outputs.
  * Memory scaling: Measure peak RAM/VRAM; enforce streaming APIs require memory proportional to requested output plus bounded working buffers, not full source array.
  * Stable regression gates: Retain benchmark receipts separately without fragile wall-clock thresholds in CI.
- 0.2.3-07: Public documentation and tutorial inventory:
  * Audit documentation surface for completeness: README, Installation, NWB workflow, API reference, Concept pages, Common mistakes, References. Every public feature satisfies API entry + minimal example + units/shapes + failure semantics + composition path.
  * Build executable synthetic NWB tutorial suite (01 NWB basics, 02 Addressing and metadata, 03 Spiking, 04 LFP and spectral, 05 Statistics, 06 Laminar, 07 Ensembles, 08 End-to-end pipeline).
- 0.2.3-08: Complete public-surface review auditing every module/export for naming, typing, units, axes, randomness, errors, docs, examples, deprecated names, duplicate implementations, dead code, and boundary leakage.
- 0.2.3-09: Skills review comparing disk assertions with live exports, testing routing, verifying boundary preservation, and running skill validation.
- 0.2.3-10: Agent review exercising authority, actor, critic, verifier, docs-harness on representative adversarial tasks verifying role separation (actor is not its own verifier).
- 0.2.3-11: Final discovery audit repeating defect-class audit over expanded package; every demonstrated problem repaired or entered into todo_stack.md; close 0.2 feature intake.
- 0.2.3 release gate: Feature-complete API, calibrated estimators, all unresolved work represented exactly once in todo stack, full configured gates PASS.

# 0.2.4

- 0.2.4-01: Empty the executable todo stack (zero unresolved package tasks unless explicit human decision blocks release).
- 0.2.4-02: Documentation minimization pass: Audit and eliminate duplicated explanations, stale version statements, excessive prose, internal codes, unsupported claims, drifting screenshots, and non-executing examples; verify small, accessible docs without internal engineering manual overhead.
- 0.2.4-03: Executable tutorial verification against installed wheel: Run all 8 tutorials (01 basics through 08 end-to-end) in a clean environment against the installed wheel without repo-relative imports; verify synthetic expected truth is known by construction and labeled synthetic.
- 0.2.4-04: Independent numerical audit of every high-risk primitive and composition for sign, scale, units, axes, complex preservation, aggregation order, failure, boundary, and determinism.
- 0.2.4-05: Randomness and inference audit verifying caller control of RNG, no global RNG mutation, no salted hash seeds, verified permutation exchangeability, and CV isolation.
- 0.2.4-06: NWB/addressing audit with synthetic fixtures covering missing tables/columns, alternate layouts, identifiers, malformed labels, units, geometry, ambiguity, and lazy access (no missing metadata becomes valid-looking science).
- 0.2.4-07: API audit verifying implementation == exports == signatures == typing == docstrings == reference docs == examples == skills with zero leaked deprecated symbols.
- 0.2.4-08: Boundary audit scanning code, tests, docs, examples, skills, agents, defaults, and artifacts for zero downstream semantic leakage.
- 0.2.4-09: Skills and agents adversarial acceptance testing against stale APIs, ambiguous units, downstream requests, invalid assumptions, and evidence conflicts.
- 0.2.4-10: Dependency matrix audit verifying base install and declared optional dependency combinations, plus import-time optional dependency behavior.
- 0.2.4-11: Supported Python and OS matrix audit derived from live metadata/CI; every required remote CI job must PASS.
- 0.2.4-12: Strict documentation build audit with all examples/API references resolved, zero stale names, zero contradictory definitions, zero unsupported claims.
- 0.2.4-13: Distribution audit building sdist and wheel from clean checkout, inspecting manifests, installing into clean environments, verifying site-packages resolution, and running representative numerical workflows against installed wheel.
- 0.2.4-14: Reproducibility audit from fresh checkout -> install -> tests -> docs -> calibration -> representative workflows with zero undocumented local state.
- 0.2.4-15: CPU/CUDA/parallelism independent verification: Confirm performance decisions and numerical parity across CPU and GPU backends on clean test systems.
- 0.2.4-16: Independent final critic pass attempting to falsify numerical correctness, boundary, API consistency, docs, skills, agents, packaging, CI, and release state.
- 0.2.4-17: Release seal verifying acceptance predicate Q_release = Q_science & Q_API & Q_performance & Q_CPU/GPU & Q_NWB & Q_docs & Q_tutorials & Q_skills/agents & Q_distribution, changelog/version bump, clean tree, commit, push dev, remote CI PASS, merge/release per policy, tag, build, install, smoke-test, and reconcile.

# Before 1.0

- Replace example-based estimator coverage with analytic/property-based tests.
- PSTH SEM policy for `N=1` trials (zero vs NaN) if statistical contract tightened.
- Processing-module discovery generalization beyond LFP if corpus requires it.

# Unversioned

- File omission-side expert-feedback items in the omission repository.
