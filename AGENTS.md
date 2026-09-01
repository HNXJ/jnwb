# AGENTS.md — Repository Operational Kernel (jnwb & omission)

Generic NWB analysis library (`jnwb/`) and sequential omission electrophysiology corpus (`omission/`).
This file is the authoritative repository operational contract for all AI agents and automated harnesses.

---

## 1. Epistemic Discipline & Authority Hierarchy

### Truth Precedence
When sources or claims conflict, authority resolves strictly in this descending order:
1. **Direct Empirical Receipts**: The exact data artifact (CSV, JSON, HDF5, NWB) written by verified code on disk, named beside the claim.
2. **Current Repository & File State**: Inspected live state of the working directory and version control.
3. **Structured Project State**: `omission/context/PROJECT_STATE.md` and `artifacts/.lab/*.json`.
4. **Narrative Memory & Prose**: Conversation transcripts, doctrine descriptions, and skill documentation.

### Core Epistemic Invariants
- **Claim Taxonomy**: Every claim belongs strictly to `claim ∈ {observed, derived, inferred, assumed, unknown}`.
- **Verification Rule**: `execution ≠ verification`. A command exiting with code 0 or writing an output is not verification. Verification requires observed empirical receipts matching the exact claim scope.
- **State Rule**: `memory ≠ current state ≠ evidence`. Never assert state based on memory of a previous turn. Re-derive from live disk inspection.
- **Pass Criterion**: `unknown ≠ PASS`. An unresolved conflict or unverified assumption is a STOP condition.
- **Harness Threshold**: Any evaluated harness score `< 80/100` triggers mandatory harness diagnosis and repair before proceeding.

---

## 2. Execution Grammar: W = P(RG)^N S

All multi-step agent actions follow the PRGS operational loop:
- **P (Prepare)**: Orient, inspect baseline repository state, identify physical constraints, locate input receipts, and establish explicit acceptance criteria before mutating any state.
- **R (Review)**: Evaluate candidate action, script output, or intermediate observation against evidence, physical invariants, and protected boundaries.
- **G (Progress)**: Execute the smallest discriminative action producing decisive empirical feedback.
- **S (Seal)**: Verify all acceptance criteria against direct empirical receipts, run regression tests, record Labyrinth nodes where claims change standing, and produce compact evidence-backed handoffs before declaring completion.

---

## 3. Scientific & Neuroscience Invariants

### Domain Invariants
1. **Signal Class Independence**:
   - Spikes (SUA/SPK), Multi-unit envelope (MUAe), Local Field Potentials (LFP), and behavioral covariates (pupil, eye gaze, lick) represent distinct physical observables.
   - **Never pool across modalities.** Preserve session, subject, area, layer, probe, and unit namespaces throughout.
2. **Estimand Disambiguation**:
   - `Prevalence ≠ Magnitude ≠ Information ≠ Mechanism`.
   - Answering "how many units respond" (prevalence) does not answer "how strong is the response" (magnitude), "can stimulus/omission be decoded" (information), or "what circuit drives the effect" (mechanism).
   - Name the exact estimand before drawing conclusions or comparing results.
3. **Causal & Directional Claims**:
   - `Association ≠ Directionality ≠ Causality`.
   - Correlation, Granger causality / phase slope index / transfer entropy, and perturbation/causal mechanisms require progressively stronger designs. Do not describe a weaker statistical metric with a stronger causal verb.
4. **Logarithm Last**:
   - When computing spectral power or decibel changes: average raw power across trials, normalize by baseline, and compute `10 · log10(power)` once at the final step. Never average pre-computed decibels across sites or animals.
5. **Unit of Inference**:
   - Explicitly declare the inferential unit (unit, channel, trial, or session/animal) for all degrees of freedom and statistical tests. Cluster/hierarchical structure must be accounted for (e.g. session-cluster bootstrap, GLMM).
6. **Valid Nulls**:
   - A valid null is an empirical finding, not a failure. Never alter an estimator, window, or threshold simply because `p ≥ α`.
7. **No Synthetic Science**:
   - No empirical value may exist in any output that no verified script computed from real data.
   - If placeholder/synthetic data is required for scaffolding, the output and figure must display an unmissable red `PLACEHOLDER-DUMMY` banner.

---

## 4. Repository Protection & Boundary Invariants

1. **The `jnwb/` Freeze**:
   - `jnwb/` is a generic, dataset-agnostic NWB library. It is strictly frozen and read-only during analysis phases.
   - Analysis code in `omission/` consumes `jnwb/`. `jnwb/` never imports from project directories (enforced by `tests/test_jnwb_frozen_boundary.py`).
2. **Protected Concurrent Paths**:
   - The following paths are protected concurrent human/session work:
     - `omission/context/figures/`
     - `omission/scripts/`
     - `omission-data/SKILL.md`
   - Do not revert, stash, overwrite, or delete uncommitted work in these paths.
3. **Mechanical Safety Gates**:
   - No destructive git operations: `git reset --hard`, `git push --force`, and wildcard additions `git add .` or `git add -A` are prohibited. Stage only exact, intended file paths.
   - Mechanically preventable errors must be guarded by executable gates or tests, not just docstrings.

---

## 5. Skills & Progressive Disclosure

- **Canonical Skill Location**: The single tracked, canonical project skill source is `omission/.claude/skills/<skill-name>/SKILL.md`.
- **Tree Consolidation Invariant**: Never recreate or mount `.agents/skills/`. This repository has an automated tripwire test (`omission/tests/test_skill_tree_consolidation.py`) that strictly prohibits `.agents/skills/` to prevent duplicate tree drift.
- **Pre-Creation Verification**: Before creating, moving, or mounting any skill trees, agents must inspect existing ownership and uniqueness tests.
- **Domain Skills**:
  - `omission-data`: Corpus manifest, file paths, NWB addressing, electrode/probe maps.
  - `omission-signal`: LFP filtering, TFR computation, artifact detection and repair.
  - `omission-spiking`: Spike extraction, PSTH, firing rate metrics, response latency.
  - `omission-statistics`: Permutation nulls, FDR correction, Clopper-Pearson CIs, GLMM.
  - `omission-figures`: Publication palette, multi-panel layouts, SVG/PNG rendering.
  - `labyrinth`: Evidence graph protocol in `omission/artifacts/.lab/`.
  - `numerical-computing`: Vectorized NumPy/SciPy operations, numerical stability, GPU backends.
  - `biophysical-modeling`: Laminar CSD, biophysical simulation primitives.
