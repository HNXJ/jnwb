# Handout 4B continuation — Claude handoff

**Date:** 2026-08-11  
**Project:** `C:\workspace\omission`  
**Branch:** `dev`  
**Repository SHA at handoff:** `bd7d3cc5612bf4743e1a3d406d020a93c9e7e7b5`

This is an execution handoff, not a scientific results handout. The Stage 4B map is not
complete and no manuscript claim may be drawn from the current partial runs.

## Scientific state

Stage 4A and Stage 4A.1 were approved. Stage 4B is authorized with these frozen constraints:

- Frozen corpus: the 21 sessions in `artifacts/data/nwb_catalog.json`.
- The live extra `sub-V198o_ses-230629_rec.nwb` remains
  `AVAILABLE_BUT_NOT_IN_FROZEN_CORPUS`.
- Modalities: SUA, MUAe, and raw time-domain LFP.
- TFR-backed LFP is prohibited.
- W1 confirmatory design: train p2+p3, test p4; score expected and preceding identity;
  `G = A_expected - A_previous`.
- W2: predictable versus random context.
- W3: A/B/R sequence-family classification; never call R a third omitted identity.
- T1: p2/p3/p4 position decoding using local omission-relative coordinates.
- T1 cross-family variants: A→B, B→A, and predictable→random.
- Representations: SUA R0/R1, MUAe M0/M1, raw LFP L0/L1.
- Outer folds and eligibility come from Stage 4A. No relaxed or replacement CV scheme.
- Nulls use `jnwb.permutation.permute_labels`; grouped exchangeability is mandatory.
- M2, M3, and M4 remain closed.

## Repository implementation

Implemented files:

- `scripts/run_handout4_stage4b_linear_map.py`
- `scripts/merge_handout4_stage4b_shards.py`
- `scripts/record_handout4_stage4b_lab_node.py`
- `tests/test_handout4_stage4b.py`
- `tests/test_muae_accessor.py`
- `jnwb/analog.py`
- `context/figures/fig04_omission_identity_decoding/handout_4_stage4b_linear_map/README.md`

The analog accessor was repaired to find nested V182o `starting_time.rate` metadata. A real
V182o check returned raw LFP and MUAe epochs with shape `(1, 512, 20)` at 1000 Hz.

Targeted receipts before the long run:

```text
tests/test_muae_accessor.py                         3 passed
tests/test_structured_identity_m2a.py               passed
tests/test_permutation_lint.py                      passed
tests/test_handout4_stage4b.py                      2 passed
git diff --check                                    passed
```

## Current execution state

The current long-running shards were launched before the later batched-null-solver edit.
Therefore, even if they finish, their outputs must not be merged automatically: the runner
records the current source hash when it writes its receipt, which can differ from the source
that actually executed. Treat these runs as diagnostics only unless execution provenance is
reconstructed.

Current output root:

```text
D:/analysis/handout4_stage4b_linear_map_parts/
```

Observed active shard commands include:

```text
SUA_C31
MUAe_C31
LFP_C31
SUA_V182a
MUAe_V182a
LFP_V182a
SUA_V182bV198
MUAe_V182bV198
LFP_V182bV198
```

Terminal files are under the Cursor terminal state directory. They have been emitting
`Stage4B extracting` progress, but no final `stage4b_receipt.json` has been observed.

## Required Claude procedure

### 1. Do not interpret or merge partial outputs

First check whether any shard has a final receipt and whether its recorded runner hash
corresponds to the exact source used for that process. A progress line is not a result.

Do not create a final Labyrinth evidence node from partial outputs.

### 2. Freeze the code before rerunning

Before any restart:

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
python -m py_compile `
  scripts/run_handout4_stage4b_linear_map.py `
  scripts/merge_handout4_stage4b_shards.py `
  scripts/record_handout4_stage4b_lab_node.py
python -m pytest tests/test_muae_accessor.py tests/test_handout4_stage4b.py -q
git diff --check
```

Record the runner SHA-256 before starting every shard. Do not edit the runner while shards
are active. If a shard is stopped or source provenance is ambiguous, discard its partial
output directory and restart it from the frozen source.

### 3. Validate the batched null implementation

The batched null solver was added to reduce the runtime of grouped null refits. Before using
it for production results, compare it against the ordinary ridge implementation on a fixed
synthetic dataset:

- same folds;
- same preprocessing;
- same regularization;
- same permuted labels;
- same predicted labels/statistic within a documented numerical tolerance.

If equivalence is not demonstrated, revert to the slower reference null or mark the map
`NUMERICAL_FAILURE`; never silently mix the two.

### 4. Run the frozen shards

Use the three modality/session-group commands already encoded in
`merge_handout4_stage4b_shards.py`, with `--n-permutations 100`. Do not add the uncatalogued
22nd NWB. Keep one immutable runner source for all shards.

Each successful shard must produce:

```text
cell_results.csv
predictions.csv
folds.csv
null_distribution.csv
feature_manifest.csv
trial_fold_manifest.json
failures.csv
stage4b_receipt.json
```

### 5. Merge and audit

After all nine modality/session shards finish:

```powershell
python scripts/merge_handout4_stage4b_shards.py `
  --parts <all nine frozen shard directories> `
  --output-dir D:/analysis/handout4_stage4b_linear_map
```

Then verify:

- exactly 21 catalogued sessions;
- uncatalogued session disposition is preserved;
- no TFR path is present in feature manifests;
- no T1 feature contains absolute p1-relative time;
- every successful cell has a valid grouped null;
- every failed cell has an explicit failure status;
- W1 reports both expected and preceding scores plus G;
- matrices contain effect relative to null and eligible session N;
- session/subject and leave-one-session-out summaries exist;
- output hashes and runner hashes are internally consistent.

Only then run:

```powershell
python scripts/record_handout4_stage4b_lab_node.py
```

The final Labyrinth node must replace the implementation-progress state
`artifacts/.lab/handout-4-stage4b-linear-map-implementation-20260810.json`; do not mark
Stage 4B complete while `stage4b_receipt.json` is absent.

## Explicit stop conditions

Stop and report rather than repairing by changing the design if:

- the frozen corpus changes;
- Stage 4A trial counts or group geometry differ;
- V182o analog access fails;
- local omission alignment differs from Stage 4A.1;
- absolute sequence timing enters T1;
- grouped null exchangeability is not preserved;
- source hashes cannot establish which code ran;
- a failed cell would require relaxed eligibility.

## Handoff conclusion

Current state is **implementation complete, production execution unverified**. The only safe
next scientific action is to establish immutable code provenance, validate the batched null
against the reference implementation, then rerun and merge the complete frozen map. Do not
open M2/M3/M4 or write a biological interpretation before that receipt is reviewed.
