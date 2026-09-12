# 0.2.0

- 0.2.0-03: Resolve REPO_ROOT for 0.2 API. Inspect exports and call sites; if removal commitment is authoritative, remove REPO_ROOT, preserve PACKAGE_ROOT, test absence/presence, remove stale docs/skill references, verify no internal dependency remains.
- 0.2.0-04: Eliminate unsafe layer classifier behavior (classify_layer_from_depth). Review call sites and choose between (A) explicit units + defined threshold semantics or (B) deprecate/remove in favor of forthcoming laminar API; no heuristic unit guessing; test mm, um, boundary, unsupported, NaN/Inf, implausible coordinates, and constant-label regression.
- 0.2.0-05: Existing-code silent-science audit. Exhaustive inventory of except Exception, bare pass, fallback estimator substitution, synthetic/fabricated empirical values, global RNG mutation, salted hash() seeds, hidden fixed seeds, silent empty selections, hardcoded empirical outputs, implicit unit/axis assumptions, log/aggregation-order ambiguity, project identifiers/defaults/paths, missing-data -> valid-looking empty output, API/docs disagreement; classify each hit as safe/justified, defect, or unknown.
- 0.2.0-06: Package-boundary audit. Mechanically inspect code, tests, docs, examples, skills, and agents for downstream leakage; verify strict editable-install behavior and wheel contents independently (no shadow packages at root).
- 0.2.0-07: Freeze 0.2 API rules. Define problem -> input -> shape -> units -> axes -> estimator -> aggregation -> output -> failure -> randomness -> composition -> compatibility -> tests before implementation; resolve naming for jnwb.laminar, result types, session_level namespace/module location, random-state convention, and public vs internal synthetic generators.
- 0.2.0 release gate: Run targeted regression tests, adjacent suites, full configured suite, harness/boundary gates, docs build, build/install smoke tests, and supported remote CI; exit only when 0.1.x behavior has no known blocker and every 0.2 breaking change is explicit.

# 0.2.1

- 0.2.1-01: Implement spectral.aperiodic_fit(freqs, psd, freq_range, mode=...) operating on existing spectrum without silently recomputing Welch; specify fixed vs knee, shapes, axis constraints, nonpositive PSD, NaN/Inf, insufficient points, fit failure, output parameters, and units; test against analytic/synthetic spectra and malformed axes.
- 0.2.1-02: Implement spectral.relative_power(power, baseline, model=...) with explicit estimand; test numerical distinction between mean of ratios, ratio of sums, and mean dB; prevent silent estimand substitution.
- 0.2.1-03: Implement session-level exact statistics: exact sign-flip, Mann-Whitney attainable p-value floor, Clopper-Pearson, BH correction; caller-visible inferential unit and multiplicity family; test against tiny direct enumeration, n=0/1, ties, and known p-value floors.
- 0.2.1-04: Implement io.stream_npz_array defining supported compressed NPZ representations; test full-load parity, chunk-boundary parity, dtype/order preservation, missing key, corrupt archive, unsupported compression/layout, and measured bounded peak memory (no silent full-load fallback).
- 0.2.1-05: Implement addressing.probe_geometry extracting contact geometry from NWB coordinates with explicit units; handle multiple probes, irregular spacing, missing/duplicate coordinates, orientation, tolerance for nominal spacing, and ambiguous geometry without inferring cortical identity.
- 0.2.1-06: Primitive integration review for all five additions (exports, typing, docstrings, examples, invalid-input behavior, boundary neutrality, adjacent composition, independent numerical review).
- 0.2.1 release gate: All five APIs individually PASS public-API checklist; full suite, harness gates, docs build, release gate PASS.

# 0.2.2

- 0.2.2-01: Establish vFLIP reference by creating explicit difference table comparing contributed implementation, publication/reference algorithm, and proposed API; no downstream empirical choices adopted without justification.
- 0.2.2-02: Implement jnwb.laminar.vflip with explicit frequency axis, required contact spacing, explicit orientation, support score returned even on rejection, no crossover on failed support, and reported missing-contact handling; no interactive input(), no omega=-inf implicit acceptance.
- 0.2.2-03: Implement vflip_from_lfp as strict composition (LFP -> PSD -> vflip); test numerical agreement with manual composition.
- 0.2.2-04: Implement label_layers where only accepted fits produce layer assignments; rejected or non-identifiable fits produce 'na', never guessed labels.
- 0.2.2-05: vFLIP recovery tests on known crossover, reversed probe orientation, no-motif 1/f, white noise, missing interior contacts, frequency-grid equivalence, irregular frequency axis, insufficient channels, invalid spacing, and failed support gate.
- 0.2.2-06: Measure calibration and false-positive behavior under deterministic synthetic ensembles reproducible from code.
- 0.2.2-07: Test geometry composition (generic NWB -> probe_geometry -> PSD/vflip -> label_layers) with known geometry and expected result.
- 0.2.2 release gate: Numerical behavior, rejection semantics, geometry composition, docs, API, calibration, full suite, packaging, and CI PASS independently.

# 0.2.3

- 0.2.3-01: Formalize testing.synth with reusable generators (known laminar motif, white noise, AR/autocorrelated noise, periodic shared response with no condition effect, unequal groups, missing contacts, contiguous correlation blocks, phase-gradient/coherence structures) as test infrastructure, not empirical evidence.
- 0.2.3-02: Implement xflip locking semantics first (input axis, Pearson/Spearman/partial definitions, contiguous vs unrestricted grouping, minimum block size, boundary representation, surrogate construction preserving temporal autocorrelation where declared, RNG, p-value resolution, failure behavior).
- 0.2.3-03: Calibrate xflip false-positive control and recovery across known blocks, no-block null, white noise, AR noise, periodic common response, unequal blocks, edge cases, same-seed determinism, and different-seed variation.
- 0.2.3-04: Implement zflip reusing existing complex spectral primitives (imaginary coherency / wpli); docs state exact estimator.
- 0.2.3-05: Calibrate zflip across known phase structures, gradients, zero-lag shared reference (must not manufacture imaginary coherency), independent signals, AR signals, periodic responses, same/different RNG.
- 0.2.3-06: Performance review and benchmarking of vFLIP/xFLIP/zFLIP, permutation/statistics, streaming NPZ, and expensive spectral paths; parallel implementations verified for numerical/stochastic equivalence; no estimator changes for speed.
- 0.2.3-07: Complete public-surface review auditing every module/export for naming, typing, units, axes, randomness, errors, docs, examples, deprecated names, duplicate implementations, dead code, and boundary leakage.
- 0.2.3-08: Skills review comparing disk assertions with live exports, testing routing, verifying boundary preservation, and running skill validation.
- 0.2.3-09: Agent review exercising authority, actor, critic, verifier, docs-harness on representative adversarial tasks verifying role separation (actor is not its own verifier).
- 0.2.3-10: Final discovery audit repeating defect-class audit over expanded package; every demonstrated problem repaired or entered into todo_stack.md; close 0.2 feature intake.
- 0.2.3 release gate: Feature-complete API, calibrated estimators, all unresolved work represented exactly once in todo stack, full configured gates PASS.

# 0.2.4

- 0.2.4-01: Empty the executable todo stack (zero unresolved package tasks unless explicit human decision blocks release).
- 0.2.4-02: Independent numerical audit of every high-risk primitive and composition for sign, scale, units, axes, complex preservation, aggregation order, failure, boundary, and determinism.
- 0.2.4-03: Randomness and inference audit verifying caller control of RNG, no global RNG mutation, no salted hash seeds, verified permutation exchangeability, and CV isolation.
- 0.2.4-04: NWB/addressing audit with synthetic fixtures covering missing tables/columns, alternate layouts, identifiers, malformed labels, units, geometry, ambiguity, and lazy access (no missing metadata becomes valid-looking science).
- 0.2.4-05: API audit verifying implementation == exports == signatures == typing == docstrings == reference docs == examples == skills with zero leaked deprecated symbols.
- 0.2.4-06: Boundary audit scanning code, tests, docs, examples, skills, agents, defaults, and artifacts for zero downstream semantic leakage.
- 0.2.4-07: Skills and agents adversarial acceptance testing against stale APIs, ambiguous units, downstream requests, invalid assumptions, and evidence conflicts.
- 0.2.4-08: Dependency matrix audit verifying base install and declared optional dependency combinations, plus import-time optional dependency behavior.
- 0.2.4-09: Supported Python and OS matrix audit derived from live metadata/CI; every required remote CI job must PASS.
- 0.2.4-10: Strict documentation build audit with all examples/API references resolved, zero stale names, zero contradictory definitions, zero unsupported claims.
- 0.2.4-11: Distribution audit building sdist and wheel from clean checkout, inspecting manifests, installing into clean environments, verifying site-packages resolution, and running representative numerical workflows against installed wheel.
- 0.2.4-12: Reproducibility audit from fresh checkout -> install -> tests -> docs -> calibration -> representative workflows with zero undocumented local state.
- 0.2.4-13: Independent final critic pass attempting to falsify numerical correctness, boundary, API consistency, docs, skills, agents, packaging, CI, and release state.
- 0.2.4-14: Release seal verifying acceptance predicate Q_0.2.4 = T & N & A & B & D & S & G & P & C & R, changelog/version bump, clean tree, commit, push dev, remote CI PASS, merge/release per policy, tag, build, install, smoke-test, and reconcile.

# Before 1.0

- Replace example-based estimator coverage with analytic/property-based tests.
- PSTH SEM policy for `N=1` trials (zero vs NaN) if statistical contract tightened.
- Processing-module discovery generalization beyond LFP if corpus requires it.

# Unversioned

- File omission-side expert-feedback items in the omission repository.
