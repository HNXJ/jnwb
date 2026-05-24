# Omission Phase A8.1 SPK Candidate Response Metrics Execution Summary
**Truth Status**: `truth_safe_unverified`
**Validation Status**: `candidate_metric_execution_not_biological_claim`

This summary report validates that Phase A8.1 SPK response metrics, statistical tests, multiple-comparison corrections, and candidate response labels have been successfully executed over the real spiking dataset.

## Summary Analytics
- **Total Sessions Processed**: 13
- **Total SPK NumPy Files Processed**: 396 files
- **Total Unique Units Evaluated (Global)**: 3521 units
- **Total Raw Behavioral Trials Processed**: 29430 trials
- **Total Unit-Trial Observations**: 3389292 unit-trial-condition exposures
- **Total Metric Rows Generated (Long CSV)**: 39980 rows
- **Total Primary Contrast Rows**: 39232 rows
- **Total Non-Primary/Auxiliary Metric Rows**: 748 rows
- **Total Candidate Label Rows (Labels CSV)**: 3521 rows
- **Multiple-Comparison Correction**: Benjamini-Hochberg FDR
- **Raw HDF5 Reads**: 0 (Zero-tolerance passed)
- **Full NumPy Array Memory Loads**: 0 (Batch-wise memmap streaming verified)
- **Manuscript Safe Unit Areas**: 0 units

## Denominator Glossary
| Term | Definition |
| :--- | :--- |
| **`n_unique_units_global`** | Total number of unique unit keys (session_id, unit_axis_index) evaluated across all processed sessions. |
| **`n_unique_units_by_session`** | Number of unique unit records within a specific recording session. |
| **`n_raw_behavioral_trials`** | Number of raw behavioral trials recorded in a single condition session file. |
| **`n_unit_trial_observations`** | Sum of trials accumulated across all evaluated units and conditions (unit-condition-trial exposures). |
| **`n_long_metric_rows_total`** | Total number of rows in the long-format metrics database (unit_response_metrics_long.csv). |
| **`n_primary_contrast_rows`** | Number of rows in the long-format database representing primary statistical contrast tests. |
| **`n_nonprimary_or_auxiliary_metric_rows`** | Number of rows in the long-format database representing auxiliary/hypothesis metrics without primary statistical contrast tests. |
| **`n_unit_candidate_label_rows`** | Total number of unique candidate label rows in the unit candidate labels database (unit_candidate_labels.csv). |

## Candidate Response Class Summary (Session-Level Aggregates Only)
All unit classifications are strictly candidate and labeled with the suffix `_candidate`:
- **`S_plus_candidate`**: 1097 units
- **`S_minus_candidate`**: 520 units
- **`O_plus_candidate`**: 9 units
- **`O_minus_candidate`**: 14 units
- **`X_candidate` (Omission selective)**: 22 units
- **`null_or_unclassified`**: 1859 units

## Core Safety Constraints & Gating
- **Candidate Labels Only**: Firing rate metrics and classifications are candidate only. None are final or manuscript-ready.
- **No Area/Hierarchy Claims**: No anatomical area columns or sorted cortical hierarchies are exported or analyzed. The unit-area mapping remains non-manuscript-safe.
- **Batched Streaming Safety**: Batched processing via numpy memmap streams batches of default unit size 64 to protect local runtime memory.

## Phase A8.2 Stability & Sensitivity Planning Readiness
- **Allowed**: Yes, Phase A8.2 stability and sensitivity analysis planning is allowed because the full dataset candidate metrics and corrections are now computed and indexed.
- **Explore targets**: Threshold sweeps, baseline stability, slot/family stability, and session robustness.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: signal-timebase-smoke / Repo or Workspace: D:\workspace\omission / Date: 2026-05-24
