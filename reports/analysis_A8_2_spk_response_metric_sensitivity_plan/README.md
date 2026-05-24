# Phase A8.2: SPK Response Metric Sensitivity Plan
**Truth Status**: `truth_safe_unverified`
**Validation Status**: `candidate_metric_execution_not_biological_claim`

This directory contains the operational design and parameters for the **Phase A8.2 SPK Response Metric Sensitivity Sweep**. The sweep is designed to systematically explore candidate unit classification stability across multiple significance levels, FDR scopes, window intervals, and condition families before biological claims are promoted.

## Core Sweep Design

To prevent arbitrary threshold selection ("p-hacking") and to identify biologically robust responses, Phase A8.2 sweeps units across a multi-dimensional parameter space:

1. **Significance & Correction Scopes**:
   - Sweeps from uncorrected `p < 0.05` to conservative false discovery rates (FDR) `q < 0.05`.
   - Explores the 3 scopes computed in Phase A8.1: `within_session_all_units_all_primary_contrasts`, `global_all_units_all_primary_contrasts`, and `per_metric_family`.
2. **Effect Size Thresholds (Cohen's d)**:
   - Evaluates unit labels under no minimum effect size (`d = 0.0`), a small effect size minimum (`d = 0.2`), and a moderate effect size minimum (`d = 0.5`).
3. **Timing Windows**:
   - Sweeps across three window intervals derived from the canonical timebase:
     - Canonical Omission Window: `1000 - 1500 ms`
     - Core Omission Window (Narrow): `1000 - 1300 ms`
     - Extended Omission Window (Wide): `1000 - 1700 ms`
4. **Stratification & Exclusions**:
   - Evaluates slot specificity (`p2`, `p3`, `p4` separately) to ensure that omission-linked responses are stable within specific prediction slots before pooling.
   - Evaluates family specificity (`A-family`, `B-family`, `R-family`) to confirm family-level predictive routing.
   - Leverages the A8.1 warning aggregation to exclude or stratify sessions that are heavily impacted by file-level loading or broadcast warnings.

## Files In This Plan
* **[README.md](file:///d:/workspace/omission/reports/analysis_A8_2_spk_response_metric_sensitivity_plan/README.md)**: This document outlining the sweep architecture and parameters.
* **[sensitivity_grid.csv](file:///d:/workspace/omission/reports/analysis_A8_2_spk_response_metric_sensitivity_plan/sensitivity_grid.csv)**: The structured parameter grid outlining all sweep configurations.
* **[acceptance_criteria.md](file:///d:/workspace/omission/reports/analysis_A8_2_spk_response_metric_sensitivity_plan/acceptance_criteria.md)**: Explicit stability definitions and criteria for candidate robust labels.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: signal-timebase-smoke / Repo or Workspace: D:\workspace\omission / Date: 2026-05-24
