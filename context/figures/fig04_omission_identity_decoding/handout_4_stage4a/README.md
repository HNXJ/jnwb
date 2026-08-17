# Handout 4 Stage 4A — WHAT × WHEN design/corpus audit

This directory records the design-only audit authorized by Handout 4. It uses the live 21-session
NWB catalog and bytes-aware HDF5 event parsing. No neural tensors, estimators, null draws, or
models were created.

Run:

```powershell
python scripts/audit_handout4_stage4a.py
```

Key outputs:

- `stage4a_design_receipt.json` — authorization, task definitions, nuisance proofs, modality
  contracts, corpus counts, hashes, and stop rule.
- `corpus_table.csv` — signal × task × session × area design corpus with trial/class/group support
  and explicit exclusion reasons.
- `task_session_geometry.csv` — target geometry, grouped outer folds, and inner-validation support.
- `fold_assignments.csv` — design-level held-out group assignments; no model predictions.
- `signal_area_inventory.csv` and `session_inventory.csv` — raw signal and session metadata.
- `label_nuisance_proof.csv` — p2/p3 equality, p4 A/B reversal, and explicit R-family
  non-identity handling.
- `local_alignment_contract.json` — omission-relative timing transform and prohibition on absolute
  p1-relative classifier features.

The frozen W1 p2+p3 → p4 confirmatory corpus remains the signed five-session set. A larger
common-cycle extension is reported separately as an exploratory design candidate and is not
promoted. All 21 NWBs expose raw LFP and MUAe acquisition groups, but MUAe has no current
first-class loader. The resolved live TFR directory also disagrees with stale readiness counts;
TFR-backed LFP eligibility is not trusted without resolving that discrepancy.

Stage 4A stop gates:

```text
SAFE_TO_AUDIT_FULL_WHAT_WHEN_DESIGN = YES
SAFE_TO_RUN_NEW_LINEAR_MODELS = NO
SAFE_TO_RUN_M2 = NO
SAFE_TO_RUN_M3_M4 = NO
```
