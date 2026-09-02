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

### Scientific Writing, Vocabulary & Tone Discipline
1. **Scientific Voice over Process Jargon**:
   - Prefer direct, compact, quantitative, skeptical scientific vocabulary: `result`, `test`, `analysis`, `table`, `figure`, `source`, `method`, `limit`, `condition`.
   - Avoid governance/process jargon in scientific prose: avoid `framework`, `doctrine`, `contract`, `ontology`, `evidence architecture`, `claim machinery`, `pipeline governance`.
   - Avoid promotional, marketing, or exaggerated language ("striking", "compelling majority", "revolutionary").
2. **Critical Scientific & Temporal Distinctions**:
   - **Response Magnitude ≠ Temporal Resolution**: Low-frequency LFP power can change strongly while its onset remains poorly localized in time. Poor temporal resolution does not mean weak modulation.
   - **Detected ≠ Resolved**: Being detected in power does not equal being temporally resolved with an admissible latency. Never substitute one state for the other.
   - **Terminology Precision**:
     - `temporal resolution`: Precision supported by the signal/transform.
     - `temporally resolved`: Analysis classification for a response with an admissible latency.
     - `latency`: Estimated event-relative timing.
     - `estimator spread`: Disagreement among latency estimators.
     - Avoid repeating `resolvability`; use `fraction temporally resolved` where clearer.
   - **Unit-Level vs. Session-Level Inference**: Descriptive unit-level percentages (e.g., 74.8% positive $\Delta T$) must not be reported as population-level latency shifts when the session-level test is not significant ($p = 0.053$).
   - **Sign Timing**: Session-level increase vs. decrease timing differences that do not reach significance ($p = 0.875$) must not imply a stable early-decrease / late-increase hierarchy.
   - **LFP Frequency Resolvability**: `beta/gamma temporal resolvability > theta/alpha temporal resolvability` at the session level does not mean "gamma responds earlier" or "theta responds later".
   - **Left-Censoring**: Onset values pinned to search boundaries (e.g. beta onsets) are left-censored bounds, not ordinary measured latencies.
   - **Area Hierarchy**: Do not state or visually imply an area latency hierarchy when area and subject are partially confounded.
   - **Causality Ban**: Do not use `LFP drives SPK`, `SPK drives LFP`, `causal direction`, or `information flow` for descriptive temporal analyses.

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
   - No destructive git operations: `git reset --hard`, `git push --force`, and wildcard additions `git add .` or `git add -A` are prohibited. Stage only exact, intended file paths. `git commit -a` is prohibited for the same reason: it stages every modified tracked file without using a wildcard, so the rule above does not catch it.
   - **Verify the index before every commit.** This is a shared working tree: another session's uncommitted edits to a file you also touched are indistinguishable from your own. Run `git diff --cached --name-only` and confirm that *every* listed path belongs to your declared task. If one does not, unstage it (`git restore --staged <path>`) and say so — do not commit it "because it was already dirty".
     - Receipt (2026-09-02): commit `29ed345` swept an in-progress `README.md` edit from a concurrent session into an unrelated docs commit. The committed README then referenced `examples/quickstart_jnwb.py` and a PNG that were never tracked, so on a fresh clone the image did not render and the documented command failed. Repaired by `8ca5567`. The `git add .` ban was already in force and did not prevent it, because the staging was path-explicit — what was missing was the check on *what ended up staged*.
     - This one cannot be fully mechanized: "belongs to my declared task" is not machine-readable, and `scripts/harness_gate.py::check_protected_paths` only guards the declared protected paths (`README.md` is not one) and runs in CI, after the push. Treat the check as a required manual step.
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
