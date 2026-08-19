# Structured Identity Experiment v1

Milestone 1 is the signed-off infrastructure gate. It materializes:

- the canonical trial ontology and target/confound columns from `jnwb.trial_ontology`;
- deterministic leave-one-cycle-out outer folds;
- inner partitions that exclude the outer test cycle;
- R0 (`X_rate`), R1 (`X_vec`), and R2 (`X_structured`) representation contracts;
- within-cycle permutation-null manifests through `jnwb.permutation.permute_labels`;
- class-balance and machine-readable provenance receipts.

No decoder is fitted by this milestone. M2/M3 training remains unauthorized until the receipt is
reviewed.

Run the full readiness-gated metadata pass with:

```powershell
python scripts/materialize_structured_identity_milestone1.py `
  --permutations 20
```

Artifacts are written to `milestone_1/`. The current receipt records the full eligible corpus
scope, exclusions, fold geometry, null scheme, output hashes, and the explicit
`training_authorized: false` gate.

## Milestone 1B — cross-position reversal design

The original pooled expected-identity estimand was rejected after the Milestone 1 inspection
showed deterministic nuisance identifiability. The versioned v1.1 amendment instead defines
cross-position rule generalization:

```powershell
python scripts/inspect_structured_identity_reversal_design.py
```

The primary contrast is `p2+p3 -> p4`. It persists the exact common-cycle assignments, p2/p3
equality and p4 reversal proof, session/contrast eligibility, and outer/inner fold geometry under
`milestone_1/reversal_design/`. Sessions with missing required slots, insufficient common cycles,
missing classes, or insufficient nested partitions are marked `INELIGIBLE_DESIGN`; no random-trial
fallback is used. This pass does not materialize neural tensors or train models.

## Milestone 2A — approved validation/baseline run

After v1.1 scientific sign-off, the authorized baseline command is:

```powershell
python scripts/run_structured_identity_milestone2a.py `
  --permutations 1000
```

This run uses only the frozen five-session `p2+p3 -> p4` primary corpus and the repaired
presented-identity positive control. It extracts real NWB unit spike trains into R0 mean-rate and
R1 9-ms vectorized raster features, fits a regularized linear ridge decoder with inner grouped
cycle selection, scores both expected and previous identity on p4, and constructs the null with
`jnwb.permutation.permute_labels` within cycle/slot groups. The null freezes the observed-fold
regularization choice; it does not repeat post hoc model selection.

Outputs are written to `milestone_2a/`. The receipt retains fold → session → subject identity,
feature shapes, estimator parameters, permutation seeds/units, session and subject summaries,
and leave-one-session-out diagnostics. M2 nonlinear, M3 structured, M4 ablation, architecture
search, and broad hyperparameter search remain closed.

## Milestone 2A — diagnostic decomposition

The approved no-retraining review pass is:

```powershell
python scripts/inspect_structured_identity_milestone2a.py
```

It reads the persisted cells, OOF predictions, fold diagnostics, grouped nulls, and source
receipt, then writes `milestone_2a/diagnostic_review/`. The review includes the session × area
positive-control accuracy and null percentile, paired R0/R1 `G_balanced` and
`Delta_temporal_R1_minus_R0`, session/area summaries, label-stratum summaries, continuous signed
ridge decision-score diagnostics, and leave-one-session-out aggregate/paired tables. The primary
reversal test is fixed at p4, so position is recorded as a design limitation rather than treated
as an independent decomposition factor. Decision scores are not calibrated probabilities, and
the continuous score remains secondary to `G_balanced`.
