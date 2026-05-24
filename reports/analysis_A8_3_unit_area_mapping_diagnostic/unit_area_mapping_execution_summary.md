# Phase A8.3: Diagnostic Unit-Area Mapping Integrity Audit
**Truth Status**: `truth_safe_unverified`
**Validation Status**: `diagnostic_unit_area_mapping_not_biological_claim`

> [!IMPORTANT]
> A8.3 is a diagnostic metadata audit only. No biological hierarchy claims are made.
> Area-resolution status counts are infrastructure metadata, not manuscript results.

## Input Sources
- A8.1 unit candidate labels: `reports\analysis_A8_1_spk_response_metrics\unit_candidate_labels.csv` (3521 unique unit keys)
- A8.2 stability table: `reports\analysis_A8_2_spk_response_metric_sensitivity\candidate_label_stability_by_unit.csv` (3521 unique unit keys)
- A6 unit area inventory: `reports\analysis_A6_area_probe_metadata\unit_area_inventory.csv` (3521 rows loaded)

## Join Integrity Summary
| Check | Count | Status |
| :--- | :---: | :---: |
| `A8.1_keys_total` | 3521 | **info** |
| `A8.2_keys_total` | 3521 | **info** |
| `A8.3_long_rows_total` | 3521 | **info** |
| `keys_in_A8.1_not_in_A8.2` | 0 | **PASS** |
| `keys_in_A8.2_not_in_A8.1` | 0 | **PASS** |
| `A8.1_keys_all_in_A8.3_long` | 0 | **PASS** |
| `A8.2_keys_all_in_A8.3_long` | 0 | **PASS** |
| `duplicate_long_rows` | 0 | **PASS** |

## Area Resolution Status Summary (All A8.1 Units)
| area_resolution_status | n_units |
| :--- | :---: |
| `heuristic_equal_segment` | 0 |
| `invalid_channel` | 0 |
| `invalid_probe` | 0 |
| `metadata_resolved_channel` | 0 |
| `metadata_resolved_equal_segment` | 0 |
| `provisional_unit_area_from_count_matched_row_order` | 793 |
| `unknown_area` | 0 |
| `unmapped_no_metadata` | 2728 |
| `unresolved_generic_v3` | 0 |

**Total units in A8.3 long table**: 3521
**Units with metadata-resolved area (can_support_area_claim=true)**: 0
**Units that can support hierarchy claims**: 0
**Units that are unresolved or heuristic**: 3521
**Units with unmapped_no_metadata**: 2728

## Generic V3 Audit
- Total generic-V3 flagged unit rows: **0**
- Generic V3 labels have NOT been silently split into V3d/V3a.
- Generic V3 labels have NOT been silently discarded.
- All generic V3 cases are written to `generic_v3_resolution_audit.csv`.

## DP→V4 Alias Audit
- Total DP-labeled unit rows found: **0**
- DP labels correctly resolved to V4: **0**
- All DP alias cases are written to `dp_to_v4_alias_audit.csv`.

## Area-Stratified Diagnostics Feasibility
- Area-stratified diagnostics technically possible: **NO**
- Manuscript hierarchy claims allowed: **NO** (requires validated channel-level provenance)

## Scientific Wording Lock
> [!WARNING]
> A8.3 is a diagnostic metadata audit only. Area-resolution status counts do not constitute
> biological population claims. The absence or presence of metadata-resolved units in any area
> does not support or refute predictive-routing hierarchy hypotheses.

---
Footer: Agent: Antigravity / Model: Claude Sonnet 4.6 / Role: Metadata Integrity Auditor / Plane: diagnostic / Repo or Workspace: D:\workspace\omission / Date: 2026-05-24
