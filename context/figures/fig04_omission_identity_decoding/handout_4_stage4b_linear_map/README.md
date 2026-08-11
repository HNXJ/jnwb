# Handout 4B — Full-corpus linear WHAT × WHEN map

This directory documents the Stage 4B runner. Large result tables are written to the
analysis output root (`D:/analysis/handout4_stage4b_linear_map` by default), not into the
repository.

## Contract

- The frozen input corpus is `handout_4_stage4a/task_session_geometry.csv` plus
  `signal_area_inventory.csv`, restricted to the 21 catalogued NWBs.
- The live `sub-V198o_ses-230629_rec.nwb` is recorded as
  `AVAILABLE_BUT_NOT_IN_FROZEN_CORPUS`; it is never loaded by the map.
- SUA uses R0/R1 spike-rate tensors; MUAe uses MUAe0/MUAe1; raw LFP uses LFP0/LFP1.
- LFP features are raw time-domain epochs only. TFR arrays and readiness-product counts are
  not read.
- Omission features are aligned to the local expected omission onset. Absolute p1-relative
  time is metadata only and is not part of any feature vector.
- Outer folds are the Stage 4A group geometry. Regularization selection is nested inside each
  outer training partition. PCA, when needed, is fit on training data only.
- Null labels use `jnwb.permutation.permute_labels` within cycle; W1 additionally preserves
  the cycle × slot reversal contract and p4 complement.

## Fixed coarse windows

The receipt records these windows before decoding:

| Name | Local milliseconds |
| --- | --- |
| late pre-omission | `[-297, 0)` |
| early omission | `[0, 180)` |
| late omission | `[351, 531)` |
| post-omission delay | `[531, 828)` |

The full omission epoch is `[0, 531)`. Positive controls are run on the full epoch; the
coarse map is reserved for the authorized WHAT and WHEN tasks.

## Runner and outputs

```text
scripts/run_handout4_stage4b_linear_map.py
```

The runner writes:

- `cell_results.csv`
- `predictions.csv`
- `folds.csv`
- `null_distribution.csv`
- `feature_manifest.csv`
- `trial_fold_manifest.json`
- `session_summary.csv`
- `subject_summary.csv`
- `leave_one_session_out.csv`
- `what_when_signal_matrix.csv`
- `coarse_window_map.csv`
- `failures.csv`
- `stage4b_receipt.json`

The receipt is the source of truth for hashes, model/null parameters, corpus disposition,
success/failure counts, and the final `SAFE_TO_RUN_STAGE4B_LINEAR` gate. M2, M3, and M4
remain closed.
