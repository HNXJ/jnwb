# 0.2.0



# 0.2.1


# 0.2.2


# 0.2.3


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

## 0.2.4 evidence reconciliation

Status at `5c2bd7f2`+ (this commit). No commit in repository history cites a `0.2.4-NN` code, so
no item below was previously sealed; several are nonetheless satisfied by mechanical gates built
under other codes. CLOSED means a gate or receipt demonstrates the item's own predicate. PARTIAL
names what is missing. Nothing here is marked from inference.

| Item | Status | Evidence / named gap |
| --- | --- | --- |
| 01 executable stack empty | OPEN | this file is non-empty by construction; closes last |
| 02 documentation minimization | PARTIAL | mechanical half closed (Gate 9 documented-API parity, Gate 10 derived version, strict MkDocs 0 warnings, `test_docs_links`, `test_docs_smoke`, `test_readme_smoke`). The editorial half -- duplicated explanation, excessive prose, internal codes leaking into user-facing text -- has had no pass and is not mechanically checkable |
| 03 tutorials vs installed wheel | CLOSED | all 8 run on the clean-venv interpreter with `PYTHONPATH` stripped and CWD outside the checkout, in CI and in release gate STEP 8; `TestInstalledArtifactVerification` fails if either is removed or reordered before install |
| 04 numerical audit of primitives | PARTIAL | 0.2.3-REV-01..11 repaired eleven externally-found numerical defects, with `test_independent_audit_semantics` / `test_audit_reproducers` as regressions. The 0.2.4 pass over `wpli`, `imaginary_coherency`, `zflip`, `rdm`, `rdm_similarity` and `jrsa(metric='rsa')` found and repaired fabricated zeros, amplitude-unit dependence, a CUDA branch that never ran, zFLIP accepting untested or partly unidentifiable delays, and undefined RDM distances set to 0 (see CHANGELOG); regressions in `test_spectral_nonfabrication`, `test_zflip_audit`, `test_rsa_oracle`. A degenerate-input and amplitude-unit sweep over the public numeric API (empty, singleton, NaN/Inf, constant, reversed windows, scale 1e-3..1e-20, CPU vs CUDA) repaired 17 more defects: zeros or p = 1/(n+1) returned for undefined results in spectral summaries, spike-window rates, shuffle p-values, PSTH, `laplacian_reference`, `network_topology`, `xflip`; unit-dependent `jrsa` CKA/RV/dCor/cosine, `vflip` and outlier detection; `jrsa` CUDA pearson/spearman disagreeing with CPU; `harmonic_ratio` double-counting (see CHANGELOG, `test_adversarial_inputs`). Not repaired, model choices: `jrsa(metric='hsic')` uses a fixed RBF bandwidth in data units, so it is unit-dependent by definition; PSTH SEM for N=1 is deferred below. zFLIP's absolute sign convention, its phase-slope formula against a cross-spectral oracle, and its N // 2 segmentation rule are pinned in `test_zflip_audit`; each RSA similarity metric is pinned to a SciPy oracle and the twelve `rdm` metrics to the wrapper's own invariants in `test_rsa_oracle`. vFLIP's centring bias and its uncontrolled, grid-dependent acceptance are repaired: min-max relative power per frequency with each band depth profile rescaled before differencing, bin-count normalization of the score, and a threshold of 3.75 recalibrated over crossover location, channel count, pitch, grid density, orientation, missing contacts and SNR (AUC 1.000, FPR 0.000, TPR 0.999). Discriminators in `TestVFlipNormalizationRepair`, 6 of which fail the pre-repair estimator |
| 05 randomness and inference | PARTIAL | no global RNG mutation anywhere in `jnwb/` (no `np.random.seed`, no `random.seed`, no `PYTHONHASHSEED` dependence); `permute_labels` rejects non-`Generator` rng, is deterministic given a seed, preserves per-group label counts, and emits a draw manifest with sequential seeds and digests. CV isolation is exercised via `nested_cv_linear_svm` but not asserted as leak-free |
| 06 NWB/addressing audit | PARTIAL | `test_nwb_synthetic_fixtures`, `test_hdmf_nwb_read_boundary`, `test_addressing`, `test_metadata`, `test_nwb_inspect` cover missing tables/columns, alternate layouts and lazy access; the electrode-region repair added out-of-range enforcement. Units/geometry/ambiguity not systematically swept |
| 07 API audit | PARTIAL | exports == documented API == generator output is gated (Gate 9 + `generate_api_md --check` + `test_api_surface`), and skills reference only existing symbols. Signature/typing/docstring parity is not mechanically compared |
| 08 boundary audit | CLOSED | Gate 6 scans `jnwb/`, `docs/` recursively, `examples/` recursively (`*.py`, `*.ipynb`), `skills/` and the root docs, with `TestGate6RecursiveCoverage` planting tokens on 8 surfaces; plus the no-project-identifiers gate and `test_jnwb_frozen_boundary` |
| 09 skills/agents adversarial | CLOSED | `test_skills_validation` covers frontmatter, routing-parameter/runtime agreement, symbol and docs-path existence, no hardcoded counts, no removed toolchain, no downstream leakage, and representative routing probes. The missing adversarial legs are added: `TestAmbiguousUnitProbes` pins that a depth unit is never inferred from magnitude (1.2 um is Superficial, 1.2 mm is Deep), that an undeclared or unsupported unit refuses to classify rather than guessing, that accepted spellings agree, that an explicit argument deterministically overrides a conflicting table column, and that `probe_geometry` takes the declared unit literally and rejects an unsupported one; `TestEvidenceConflictProbes` pins that no shipped code path can rewrite the human-authorized fact stack and that the receipts-not-consensus rule still stands |
| 10 dependency matrix | PARTIAL | base wheel installs and imports with no extras in the CI clean venv, `pip check` clean; lazy-import tests prove optional subsystems are not eager and degrade with a named error. Declared optional-extra combinations are not matrixed |
| 11 Python/OS matrix | CLOSED | run 34921221203: 3.12 and 3.14 on ubuntu-latest and windows-latest all PASS; floor consistency gated |
| 12 strict documentation build | CLOSED | `docs_build.py` strict, 0 warnings, locally and in CI; versions derive from `jnwb.__version__` |
| 13 distribution audit | CLOSED | build -> manifest scan -> `twine check` -> fresh venv -> wheel + transitive install -> `pip check` -> import from site-packages outside the checkout -> numerical workflows -> tutorials |
| 14 reproducibility | PARTIAL | CI performs checkout -> install -> tests -> docs -> build -> install -> smoke -> tutorials from a clean runner each run. Calibration regeneration is not part of that chain |
| 15 CPU/CUDA parity | CLOSED | against the RC-scoped criterion (structural/fallback tests; representative high-risk paths on one real CUDA system; parity within declared tolerances; CI verifies CPU/fallback). 9 of 13 `resolve_device` call sites executed on an RTX A4000 with no fallback warning, parity 0 to 3.6e-04; `rdm` has no GPU implementation and warns; the 3 uncovered are session-level wrappers over the same resolver, retaining structural coverage. The earlier 7-of-10 closure missed that `wpli(device='cuda')` never reached the GPU (repaired, receipt corrected). Receipt: `artifacts/benchmarks/cuda_parity_0.2.4.md` |
| 16 final critic pass | PARTIAL | the external review at 42b1450b produced the findings this stack has been repairing; it predates the electrode-region repair and these verification changes |
| 17 release seal | OPEN | blocked on the conjunction above |

### Open findings requiring a decision

- `artifacts/benchmarks/xflip_calibration_0.2.3.md` has no generator in the repository.
- `test_frequency_grid_resolution_invariance` uses a noise-free PSD, so it cannot measure a
  null's grid dependence; the calibration receipt does that instead.


## Handout (2026-09-15, Opus 5 session `9fe5eb2c`)

### State

`handoff metadata = persisted` (commit `c07c53fd`, pushed).
`working implementation state = UNSEALED` -- 13 uncommitted files remain outside that
commit. A pushed handoff commit does not mean the tree is sealed.

RC status: **BLOCKED on worktree reconciliation**, not on a human scientific decision. Once
exclusive ownership is established, continue automatically; no approval is pending.

### Why

Two implementation agents ran against this worktree simultaneously, both on 0.2.4-04. See
`AGENTS.md` §8 "One writable agent per worktree", added in response. Repository history is
recoverable; a shared working tree is not safe for concurrent writers. The 13 uncommitted
files are **unowned evidence**: do not discard them, do not stage them wholesale, and do not
attribute them to either agent without inspection.

### Mandatory opening sequence -- single-writer recovery protocol

Perform in order. Do not edit anything before step 5 completes.

1. Confirm no other agent or process is modifying `C:\workspace\jnwb`. If exclusive
   ownership cannot be established, STOP before editing.
2. Record `HEAD`, `origin/dev`, `git status --porcelain=v2`, `git diff --stat`, the full
   unstaged diff, the staged diff, and recent reflog/log. This is the only snapshot of the
   unsealed state.
3. Read this handout at `c07c53fd`.
4. Treat every pre-existing uncommitted modification as foreign and unresolved. Classify each
   by provenance and scientific intent before changing it.
5. Do NOT `stash`, `reset`, `restore`, check out files, or reformat while foreign changes
   exist. A `git stash push`/`pop` pair is what lost work here.
6. Reconstruct the other agent's work from `5ff7f8d1`, current `HEAD`, the working-tree
   diff, tests, and receipts. Preserve the superior verified work, whichever session wrote it.
7. Recover the lost zFLIP discriminators by REWRITING them from the specification below.
   Do not restore an old file version blindly.
8. Resolve the competing zFLIP segmentation rule by mathematical and test evidence. Exactly
   one rule must remain in `jnwb/laminar.py`.
9. Partition the understood foreign changes into coherent validated commits. Never
   `git add -A` across unresolved ownership; stage exact paths.
10. Push each validated checkpoint to `dev`, verify `HEAD == origin/dev`, and only then
    resume 0.2.4-04.

### Sealed with green CI (3.12/3.14 x ubuntu/windows), do not redo

`bf26b0cf` 2-D rejection + first CUDA receipt; `e5a7eecc` coherence single-segment repair;
`4e427ad1` mismatched-length `ValueError`; `d754e895` 0.2.4-15 closed under its narrowed
criterion; `d7d06107` unpaired-trace rejection in `wpli`/`imaginary_coherency`.

Headline result: `cross_area_coherence`, `imaginary_coherency`, `wpli` and `zflip` all
reported perfect coupling for independent signals whenever the segmentation yielded a single
Welch segment, because the cross-spectrum is then an exact function of the auto-spectra. All
four now refuse `K < 2`.

### Lost, and how to rebuild it

`1a15207f` was meant to carry 26 zFLIP audit tests. `tests/test_zflip.py` was overwritten
between the green test run and the commit, so the commit contains `jnwb/laminar.py` and
`CHANGELOG.md` only. The code change IS in `HEAD` and the other agent's
`tests/test_zflip_audit.py` (21 tests) passes against it -- 42 passed when both files were
run -- but these assertions no longer exist and must be rewritten:

- per-contact delay and apparent velocity against a synthetic travelling wave with a KNOWN
  delay, built by frequency-domain shift (`exp(-2j*pi*f*c*dt)`) independently of the
  implementation. Recovery was within 6 % for delay and 5 % for `pitch/dt` velocity;
- the source band must be WIDER than the fit window, or band-edge phase noise produces a
  spurious ~10 % velocity error that is an artifact of the test, not of `zflip`;
- reversing channel order exactly negates and reverses `adjacent_delays_s` and flips
  `directionality`;
- independent noise, zero-lag input and constant input are all refused;
- a true delay of 200 ms/contact aliases to ~12.6 ms and is caught only by the surrogate
  test, not by the `|tau| < 1/(2 df)` bound, which constrains the ESTIMATE;
- amplitude scaling does not change the estimate; doubling `pitch_um` doubles velocity and
  leaves delay unchanged;
- `seed` is reproducible and the global numpy RNG is not mutated.

### Next

Finish 0.2.4-04 -- vFLIP normalization/calibration is the open leg; the other agent records
vFLIP acceptance as not false-positive controlled. Then 09 -> 16 -> 01 -> RC decision. No new
features, no optimization projects, no speculative API changes. Do not tag, merge to `main`,
publish, or call the RC qualified.

# Before 1.0

- Replace example-based estimator coverage with analytic/property-based tests.
- PSTH SEM policy for `N=1` trials (zero vs NaN) if statistical contract tightened.
- Processing-module discovery generalization beyond LFP if corpus requires it.

# Unversioned

- File omission-side expert-feedback items in the omission repository.
