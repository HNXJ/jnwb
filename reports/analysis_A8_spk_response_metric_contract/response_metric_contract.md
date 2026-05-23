# Omission Phase A8 SPK Response Metric Contract Document
**Truth Status**: `truth_safe_unverified`
**Validation Status**: `prototype_metric_contract_only`

This document outlines the formal unit-level SPK response metrics, stimulus-relative windows, contrasts, and classification rules for visual prediction analysis.

## Stimulus-Relative Windows & Index Mappings
All indices are programmatically translated from absolute P1 onset (index 1000) using 1 ms bin resolution:
- **Baseline Fixation (`baseline_fx`)**: `[-500, 0]` ms $\rightarrow$ indices `[500, 1000]`.
- **Stimulus P1 (`stimulus_p1`)**: `[0, 531]` ms $\rightarrow$ indices `[1000, 1531]`.
- **Delay D1 (`delay_d1`)**: `[531, 1031]` ms $\rightarrow$ indices `[1531, 2031]`.
- **Omission P2 (`fr_omission_p2`)**: `[1031, 1562]` ms $\rightarrow$ indices `[2031, 2562]`.
- **Local Pre-Omission Baseline**: `[-250, -50]` ms relative to omission onset.
- **Post-Omission Local Delay**: `[531, 1000]` ms relative to omission onset.

## Registered Metric Database (12 Core Metrics)
1. `fr_baseline_fx`: Pre-stimulus baseline firing rate (Hz)
2. `fr_stimulus_p1`: Firing rate during P1 stimulus block (Hz)
3. `fr_stimulus_p2`, `fr_stimulus_p3`, `fr_stimulus_p4`: Firing rates during active stimulus slot periods (Hz)
4. `fr_omission_p2`, `fr_omission_p3`, `fr_omission_p4`: Firing rates during respective omission slots (Hz)
5. `delta_stimulus_vs_baseline`: Stimulus response delta firing rate (Hz)
6. `delta_omission_vs_baseline`: Firing rate change relative to local baseline during omission window (Hz)
7. `delta_omission_vs_matched_stimulus`: Firing rate change during omission slot compared to family-matched baseline control slot (Hz)
8. `post_omission_gain_index_prototype`: Delay-gain rate index after omission offset, labeled `hypothesis_only`.

## Candidate/Prototype Classification Schema
Units are assigned to candidate categories strictly for pipeline testing:
- **`S+` (Stimulus-positive)**: Active stimulus firing rate > 2.0 Hz and > 1.5x baseline rate.
- **`S-` (Stimulus-negative)**: Suppressed active stimulus firing rate < 0.5x baseline rate and baseline > 2.0 Hz.
- **`X_candidate` (Omission-selective candidate)**: Firing rate in omission slot > 2.0 Hz, omission > 1.2x local pre-omission baseline, AND omission > matched control stimulus.
- **`O+` (Omission-positive)**: Firing rate in omission slot > 2.0 Hz and > 1.2x local pre-omission baseline.
- **`O-` (Omission-negative)**: Firing rate in omission slot < 0.5x local pre-omission baseline and baseline > 2.0 Hz.
- **`null_or_unclassified`**: Flat response.

## Security Constraints & Blocks
- **No Biological Interpretation**: All metrics are strictly labeled `prototype_metric_output` and blocked from biological interpretation (`biological_interpretation_allowed = false`).
- **No Area/Hierarchy Claims**: No grouping of metrics by cortical areas or sorting along hierarchy is permitted, as unit-area assignments remain unvalidated (`area_hierarchy_allowed = false` while `manuscript_safe_unit_area = false`).

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: signal-timebase-smoke / Repo or Workspace: D:\workspace\omission / Date: 2026-05-23
