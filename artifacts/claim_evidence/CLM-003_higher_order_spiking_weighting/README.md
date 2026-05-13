# CLM-003: Higher-Order Spiking Weighting

## Status: PROTOTYPE EVIDENCE
**Truth Status**: `truth_safe_unverified`

## Summary
This artifact contains unit-level response classifications for omission sensitivity across the HNXJ/omission dataset.

## Definitions
- **Omission-Positive (O+)**: A broad descriptive screen for units showing significant increase in firing rate during the 500ms omission window compared to baseline and control stimuli.
  - Thresholds: Omission Rate > 2.0Hz, Increase > 20%, Effect Size > 2.0Hz.
  - **WARNING**: This is NOT a classification of robust "X" neurons. It represents a candidate pool for descriptive analysis.

## Inclusion/Exclusion Criteria
- **Blacklisted**: Session 230901 (PFC clipping artifact) is EXCLUDED from all summaries.
- **Unresolved V3**: Generic V3 mappings are EXCLUDED from hierarchy area-groups to prevent ambiguous assignment.
- **Heuristic Fallback**: Included in `session_area_group_summary.csv` but tagged in `unit_response_summary.csv`.

## Sensitivity Results
The O+ proportion is highly session-dependent. 
- Session `230630`: Shows high O+ proportion in higher-order (0.092).
- Session `230830`: Shows ZERO O+ units in higher-order (0.000) but enrichment in lower-visual (0.051).

Hierarchy claims (Higher Order > Lower/Intermediate) are fragile and vary by metadata resolution tier.
