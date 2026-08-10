# Handout 3 — Structured Identity Experiment v1 (Frozen Specification)

**Status: FROZEN SPECIFICATION. Not an implementation. No training, fitting, or model code
exists yet as of this document's authorship (2026-08-10, commit `1b52315`).** This document
requires explicit sign-off from Sol and Hamm before any implementation work begins. Changing
any section after sign-off is a new version (`v1.1`, `v2`, ...), not a silent edit — the whole
point of freezing it is that the decision rule can't be adjusted after seeing results.

Gate this specification depends on: `SAFE_TO_RUN_STRUCTURED_DECODING = YES`, established in
`artifacts/.lab/handout-2.5-runtime-audit-20260810.json`, accepted by Sol/Hamm with two
qualifications carried into this spec (§4.4, §11.2).

---

## 1. Scientific question

Sharper than the original Figure 4 question ("can omitted identity be decoded?"), per Sol's
framing:

> Does the neural population encode the identity of the missing expected event beyond
> information attributable to the preceding stimulus, temporal position, sequence family, and
> cycle?

Formally, contrast two hypotheses:

```
H_flat:       I(Y_expected ; X_flat)        ≈ 0   (after conditioning on the confounds below)
H_structured: I(Y_expected ; X_space×time)  > 0   (after conditioning on the confounds below)
```

"After conditioning on the confounds" is not decorative — §5 makes every confound an explicit,
separately-labeled target so an apparent `Y_expected` effect can be checked against whether it
is actually `Y_previous`, `Y_position`, `Y_family`, or `Y_cycle` leaking through.

Current established state (not re-litigated by this document, inherited as fact):
flattened omitted-identity decoding is chance-compatible under grouped CV
(`compute_omission_identity_cycle_deconfound_v3.py`, `compute_omission_identity_leakage_safe.py`);
presented-stimulus identity is the positive control and is expected to be trivially decodable.
Structured population coding of omitted identity remains an open hypothesis — this experiment
is the first properly-controlled test of it, not a foregone conclusion in either direction.

---

## 2. Design: an explicit factorial, not "try a CNN"

```
modality × representation × model_class × control
```

- **modality** ∈ {SPK, LFP} — analyzed and reported separately, never pooled. They are
  different sensors with different noise models, different existing doctrine
  (`jnwb-tfr`/`jnwb-core` skills), and — critically for representation choice (§4) — different
  physical topology along their non-time axis.
- **representation** ∈ {X_flat, X_temporal, X_structured} — §4.
- **model_class** ∈ {M0, M1, M2, M3, M4} — the ladder in §7.
- **control** ∈ {none, unit/channel-order permutation, time-bin permutation, within-trial
  scrambling, label permutation (exchangeable)} — §9.

The factorial is deliberate: a structured model beating a flat linear baseline is, by itself,
uninformative about *why*. Nonlinearity, added parameters, and genuine spatial structure are
three different explanations, and only the full ladder (§7) plus ablations (§9) can distinguish
them. **No single cell of this factorial authorizes a scientific claim on its own — only the
pattern across the full ladder does (§10).**

---

## 3. Eligible trials

Built from `jnwb.trial_ontology.build_trial_ontology(session, slot_keys=("p2","p3","p4"))`
(added Handout 2, unit-tested against all 12 condition codes). A trial is eligible for this
experiment iff:

- `correct_trial is True` (from the NWB `correct` field, not inferred),
- `sequence_family in ("A", "B")` — R-family trials have no `expected_identity`/
  `preceding_identity` (§1's target requires a real identity; R trials remain available as a
  *separate* diagnostic, not part of the main decode — see §11.3),
- the session/area/slot cell has `n_cycles >= 2` (the minimum for leave-one-cycle-out CV to mean
  anything) and passes whatever minimum-unit/minimum-channel count the modality-specific
  feature extraction requires (§4) — report the exclusion, do not silently drop.

Session eligibility itself is gated the same way `compute_omission_identity_leakage_safe.py`
already gates it: `artifacts/data/session_readiness.csv` (`nwb_ok`, `sidecar_ok`). Do not invent
a second eligibility mechanism.

---

## 4. Representation construction

### 4.1 X_flat (baseline, both modalities)

Existing contract, unchanged from `compute_omission_identity_leakage_safe.py`: one scalar
feature per unit (SPK: spike count in the omission-slot window) or per channel×band (LFP:
band-limited power in the omission-slot window), flattened to a `(n_trials, n_features)` matrix.
This is the representation the current chance-compatible result was established on — it is the
reference every other representation is compared against, not a strawman.

### 4.2 X_temporal (both modalities)

Preserve the time axis within the omission-slot window (do not collapse to a scalar count/power),
still flattened across the space axis (unit or channel): `(n_trials, n_space, n_time)` reshaped
to `(n_trials, n_space * n_time)` for M1/M2, or kept as `(n_trials, n_space, n_time)` for a
temporal-only model (1D conv or comparable over time, pooled/shared across space). This isolates
whether *temporal profile* carries information the scalar summary destroys, independent of
whether cross-unit/cross-channel *spatial* structure matters.

### 4.3 X_structured — modality-specific, and NOT the same design for SPK and LFP

**This is the single most important methodological point in this specification, stated
explicitly per Sol's review — do not default to "reshape to 2D, hand it to a CNN" for both
modalities identically.**

- **LFP**: `(n_trials, n_channels, n_time)` with channel order following actual probe/depth
  position (from the electrode/layer metadata already used by `jnwb-tfr`'s spectrolaminar
  functions — channel *k* and *k+1* are physically adjacent recording sites). A 2D
  spatiotemporal convolution (channel × time) is a defensible starting architecture here
  *because the spatial axis has real topology*.
- **SPK**: unit index has **no default topology**. Unit 37 and unit 38 being adjacent in
  `session.get_units(area).index` is an artifact of sorting/storage order, not anatomy (already
  flagged in `compute_omission_identity_leakage_safe.py`'s own output metadata:
  `unit_identity: "session.get_units(area).index row position"`). Two acceptable starting
  points, in preference order:
  1. **Temporal-structure-preserved, unit-permutation-equivariant**: treat units as an
     unordered set — e.g. a shared 1D temporal filter applied per-unit followed by a
     permutation-invariant pooling (mean/max/attention) across units, or a set-transformer-style
     architecture. This makes no topology assumption at all.
  2. **Metadata-ordered structure**: if a genuine, preregistered ordering exists (area, probe,
     depth-within-probe from the layer-mask metadata already used elsewhere in this project),
     order units by that coordinate and treat the result as a 1D spatial axis (unit-position ×
     time), analogous to but weaker than LFP's channel ordering (probe depth is finer-grained
     and more physically grounded than "which probe").
  A unit-index-order 2D CNN (treating raw row position as if it were pixel adjacency) is
  **not** an acceptable default and must not be run without an explicit, separately-justified
  reason recorded in the experiment receipt.

### 4.4 Presented-identity positive control — same outer-fold machinery, not the existing function

Per Sol's explicit qualification: **do not reuse `jnwb.decoding.decode_stimulus_identity` as
the formal positive control** — it uses ungrouped `StratifiedKFold(shuffle=True)` (found during
Handout 2.5, `artifacts/.lab/handout-2.5-runtime-audit-20260810.json` issues list), the same
defect class this whole repair pass exists to close. Presented identity being trivially
decodable does not exempt its estimator from the CV contract; an asymmetric standard between
the positive control and the main test would be an unforced, easily-avoided inconsistency.
**Implementation of Handout 3 must build the positive-control decode using the identical
outer-fold (leave-one-cycle-out), inner-validation, and permutation-null machinery as the main
omitted-identity decode (§6–9) — same code path, different label column
(`presented_identity` instead of `expected_identity`).** This is a concrete, scoped
implementation requirement for whoever executes this spec, not optional polish.

---

## 5. Targets (from `jnwb.trial_ontology`)

Every trial in the eligible set carries all of:

```
Y_expected   = expected_identity     (the target of primary scientific interest)
Y_previous   = preceding_identity    (confound candidate: was the classifier just re-decoding
                                       the physically-different stimulus one slot earlier?)
Y_position   = omission_position     (p2 / p3 / p4 — confound candidate: order-locked transient)
Y_family     = sequence_family       (A / B — confound candidate: any family-level nuisance)
Y_cycle      = cycle                 (confound candidate: monotonic drift / fatigue / gain shift)
```

**Every reported decode of `Y_expected` must be accompanied by the same decode run against
`Y_previous`, `Y_position` (as a categorical target within a fixed family/slot stratum), and
`Y_family`**, using the identical representation/model/fold pipeline. A structured-model result
that "succeeds" on `Y_expected` but succeeds equally well on `Y_previous` has not demonstrated
expected-identity coding — it has demonstrated that *some* nuisance-correlated signal is present
and the representation captures it, exactly the ambiguity `decode_identity_cycle_deconfound`'s
per-cycle mean-centering was built to rule out at the flat level (§1's "HONEST LIMIT" note,
carried forward: this still cannot rule out a fixed order-locked transient common to every
cycle, since A always precedes B always precedes R in every cycle — this experiment's `Y_family`
control is the direct successor to that limitation, not a new idea).

`Y_cycle` is not decoded as a target of interest — it is the **grouping variable** for the outer
fold (§6). Reporting `Y_cycle`'s own decodability is a diagnostic (§11.3, the "confound
hierarchy" exploratory hypothesis), not part of the main analysis.

---

## 6. Outer fold / group semantics

**Leave-one-cycle-out, identically for every representation, model, and target in this
experiment — no exceptions, including the positive control (§4.4).** A held-out fold is an
entire cycle; a trial's fold assignment never depends on model class or representation. This is
the single fold assignment computed once (via `jnwb.trial_ontology.build_trial_ontology`'s
`cycle` column) and reused everywhere, so that every reported number in the experiment receipt
is comparable — a representation "winning" cannot be an artifact of a different, more generous
fold scheme.

The outer held-out fold is **never** used for: hyperparameter selection, early stopping,
normalization fitting, feature/unit selection, or window selection. It is touched exactly once,
after model selection is complete, to produce the single reported held-out score for that cell.

---

## 7. Inner validation / model ladder

```
OUTER: leave-one-cycle-out (held-out generalization set, touched once, per §6)
  INNER: further split the OUTER-TRAINING cycles (not the held-out one) into a
         training/validation partition for:
           - early stopping (M2/M3/M4)
           - hyperparameter selection (regularization strength, architecture width, etc.)
           - normalization fitting (scaler fit on inner-train only)
```

Model ladder, deliberately boring (Sol's phrase, carried forward from the original Handout 1
proposal — the ordering is the point, not any single model's accuracy):

```
M0  majority/chance baseline           -- sanity floor, not a model
M1  regularized linear classifier      -- on X_flat (and X_temporal where applicable)
M2  small MLP                          -- on the same flattened representation as M1
M3  small structure-aware model        -- on X_structured (§4.3, modality-specific)
M4  M3 + regularization selected by inner CV
```

Reading the ladder (§10 has the full decision table):
- `M2 ≈ M3 > M1` → more plausibly nonlinear information, not specifically spatial structure.
- `M3 > M2` **and** destroying the structure (§9 ablations) eliminates M3's advantage → the
  structured-code interpretation is supported.
- `M3 > M2` but ablations do **not** reduce M3's performance → M3's advantage was not actually
  using the structure it was given; do not credit "structure" as the explanation.

---

## 8. Regularization search space

Kept deliberately small and stated in advance (this is a frozen spec — the search space is not
adjusted after seeing which value "works"):

- M1 (linear): L2 strength over a fixed geometric grid (e.g. `{0.01, 0.1, 1, 10}` × baseline C),
  selected by inner CV, one value per outer fold (the value may differ per fold — that is
  expected and correct, not a bug to "fix" by picking one global value after the fact).
- M2/M3/M4: weight decay + dropout over a small fixed grid; early-stopping patience fixed in
  advance, not tuned; architecture width/depth fixed in advance per modality (not searched) —
  if a width/depth search is later judged necessary, that is a new experiment version, not a
  mid-run addition.

---

## 9. Permutation nulls and structural ablations

### 9.1 Label permutation (the null hypothesis test)

`jnwb.permutation.permute_labels(y, groups=cycle, scheme="within_group", rng=...)` — mandatory,
no exceptions, for every target in §5 and every representation/model cell. A bare
`rng.permutation(y)` anywhere in this experiment's implementation is a defect by definition
(`tests/test_permutation_lint.py`'s scope should be extended to cover the new experiment module
when it exists).

### 9.2 Structural ablations (falsification controls, not optional extras)

Required, per representation where applicable:

- **Unit-order / channel-order permutation**: shuffle the space axis before the structured
  model sees it (fit fresh, not just at inference). If M3's performance is unaffected, the model
  was not using spatial adjacency — its "structure" advantage (if any) is nonlinearity/capacity,
  not the hypothesis this experiment is testing.
- **Time-bin permutation**: shuffle the time axis. Tests whether temporal ordering (not just
  presence of temporal information) matters.
- **Within-trial temporal scrambling**: a milder version of the above — local jitter rather than
  full shuffle, to test sensitivity to fine- vs coarse-grained temporal structure.
- **Capacity-matched MLP control**: M2 must be parameter-matched (or reported alongside a
  parameter-matched variant) to the M3 being compared against it, so "M3 wins" cannot be
  trivially "M3 has more parameters."

None of these ablations exist in the codebase yet (confirmed absent,
`artifacts/.lab/agent-harness-audit-20260810.json` §J) — implementing them is explicitly part of
what Handout 3's execution requires, not something to skip because it's new work.

---

## 10. Decision table

Every cell reports: outer LOCO accuracy (or AUC), permutation p-value (within-group null,
§9.1), and — for M3/M4 — the ablation-sensitivity result (§9.2). Read top-to-bottom; stop at
the first row that matches.

| Pattern observed | Interpretation | Action |
|---|---|---|
| M1 chance, M2 chance, M3 chance (all targets, all reps) | No decodable information in this modality/representation at all | Report null. Do not proceed to M4 tuning — there is nothing to tune. |
| M1 significant | The flat linear baseline already succeeds | **Stop and re-verify before celebrating**: re-run the exact confound checks that caught the original 0.601 confound (per-cycle mean-centering, `Y_previous`/`Y_position`/`Y_family` decode). If those are clean, this is a real, simpler finding than structure was ever needed for — report it as such, do not reach for M3 to "confirm" a result M1 already gives. If those are NOT clean, this is the confound resurfacing under a new name — do not report as identity decoding. |
| M1/M2 chance, M3 significant, ablations eliminate the effect | Structure-specific coding — the strongest support for `H_structured` this design can produce | Report as a positive, ablation-validated finding. Still requires: `Y_previous`/`Y_position`/`Y_family` clean, permutation null clean, cross-session replication before any manuscript claim. |
| M1/M2 chance, M3 significant, ablations do NOT eliminate the effect | M3's "advantage" does not depend on the structure it was given | Do not credit spatial/temporal structure. Re-examine as an M2-class (nonlinear-but-unstructured) finding, or as a capacity artifact if the capacity-matched control also succeeds. |
| M2 significant, M3 ≈ M2 | Nonlinear decodability, not specifically structured population coding | Report as evidence for `H_flat`-adjacent nonlinear information, explicitly distinct from `H_structured`. Do not conflate with the structured hypothesis in any write-up. |
| Effect present on `Y_expected` but equally present on `Y_previous`/`Y_position`/`Y_family` | The "expected identity" signal is confound-attributable | Do not report as expected-identity coding at any model level. This is exactly the ambiguity §5 exists to catch. |
| Effect present only on R-family diagnostic trials (§11.3) or only in `Y_cycle` | Cycle/nuisance-structure finding, not identity coding | Route to §11.3's separate exploratory track. Never merged into the main identity-decoding claim. |

---

## 11. Scope boundaries

### 11.1 Per-area vs. cross-area

Primary analysis is per-area (matching the existing `AREAS` list in
`compute_omission_identity_leakage_safe.py`: FEF, PFC, TEO, V4, V3, V2, V1 — with V3a/d pooling
per `jnwb-tfr`'s doctrine, never split). Cross-area comparison (e.g. "is the effect
frontal-biased") is a secondary analysis, run only after the primary per-area result exists, and
is itself subject to the corpus's own documented denominator-effects lesson (CLAUDE.md: "Apply
the denominator before claiming enrichment") — report per-area sample sizes alongside any
cross-area ranking claim.

### 11.2 Runtime-audit qualifications carried forward

Per Sol's Handout 2.5 acceptance: the 2-session reproduction run in Handout 2.5
(`context/figures/_handout25_runtime_audit/`) is a **runtime sanity check that the repaired
pipeline behaves qualitatively as expected — it is not a corpus-level scientific estimate and
does not substitute for a full-corpus run of this experiment.** Handout 3's execution must run
against the full eligible corpus, gated by `session_readiness.csv`, not a `--limit`-truncated
subset.

### 11.3 The confound hierarchy — a separate, explicitly-labeled exploratory track

The original invalid random-CV result (0.601, confounded) must **never** be resurrected as
identity-decoding evidence — that door stays closed regardless of any result from this
experiment. But the observation that motivated investigating it — that slow/cycle-related
nuisance structure might differ systematically across cortical hierarchy — is a separate,
potentially genuine, exploratory hypothesis in its own right, and should not be discarded as
"garbage from a failed classifier" (Sol's phrase). If pursued, it must be:

- Explicitly framed as a study of **nuisance/cycle-structure magnitude and its area
  distribution**, never as identity decoding.
- Run with its own falsifier and its own labyrinth node, `derived_from`-linked to this
  specification but not `supersedes`-linked to the main result (they are answering different
  questions, not competing answers to the same one).
- Kept out of any figure or claim that also reports the `H_flat`/`H_structured` contrast, to
  avoid exactly the kind of scope-mixing this whole repair pass exists to prevent.

### 11.4 What this document does not authorize

This is a specification, not a work order. It does not authorize: writing the structured-model
code, running any training, allocating GPU time, or drafting manuscript language about
structured coding. Execution begins only after explicit sign-off, and any deviation from this
spec discovered necessary during implementation (e.g. a representation that turns out
infeasible, a fold scheme that needs adjustment for a specific area's low trial count) is
reported back as a proposed amendment, not silently implemented.

---

## Receipt

Structured record: `artifacts/.lab/handout-3-structured-identity-experiment-v1-spec-20260810.json`.
