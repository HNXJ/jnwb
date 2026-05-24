# Phase A8.2: Stability & Sensitivity Acceptance Criteria
**Truth Status**: `truth_safe_unverified`
**Validation Status**: `candidate_metric_execution_not_biological_claim`

This document outlines the strict acceptance criteria to determine if a candidate prediction response class (e.g. `X_candidate`) is considered **robust** and **stable** under parametric perturbation in Phase A8.2.

## Core Stability Criteria

For any candidate predictive unit to be considered biologically robust and suitable for downstream research (such as future mapping or laminar profiling), it must satisfy the following strict conditions:

1. **Unit Identity Survival across FDR Scopes**:
   - The candidate unit classification must survive under at least one corrected FDR scope (`q < 0.05` for `within_session` or `global` scopes).
   - Boundary cases that are only significant under uncorrected `p < 0.05` must be flagged as "boundary" or "fragile".
2. **Standardized Effect-Size Minimum**:
   - The contrast effect size must satisfy the moderate Cohen's d threshold (`|d| >= 0.3` canonical baseline).
   - Any candidate unit with an effect size of `|d| < 0.2` will be classified as "unstable" and excluded from robust counts.
3. **Omission Timing Window Invariance**:
   - The classification must remain consistent across timing window variations: it must satisfy the X_candidate criteria in both the canonical window (`1000 - 1500 ms`) and the core narrow window (`1000 - 1300 ms`).
4. **Slot Specificity Stability**:
   - Since pooled analysis can mask slot-specific noise, a candidate `X_candidate` unit is considered robust only if it demonstrates slot-level stability (i.e. it passes significance in its specific omission slot: `p2`, `p3`, or `p4` separately).
   - No pooled `p2/p3/p4` or `A/B/R` claim is valid unless slot-specific stability is explicitly demonstrated at the unit level.
5. **Session Robustness & Denial of single-session bias**:
   - The candidate response class count must not be driven by a single outlier recording session. If more than 75% of a specific candidate class (such as `X_candidate`) is localized to a single session, the classification is flagged as "session-dependent" and is blocked from manuscript-level hierarchy claims.
6. **Warning-Aware Stratification**:
   - Any session or condition heavily impacted by load failures or broadcast warnings (e.g., sessions `230629`, `230714`, `230719` etc.) must be evaluated separately. In downstream sweeps, warnings are analyzed to verify that shape mismatches did not introduce silent bias.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: signal-timebase-smoke / Repo or Workspace: D:\workspace\omission / Date: 2026-05-24
