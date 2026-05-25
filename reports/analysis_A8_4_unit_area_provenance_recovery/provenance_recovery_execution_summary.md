# Phase A8.4: Unit-Area Provenance Recovery Status Integration
**Truth Status**: `truth_safe_unverified`
**Validation Status**: `diagnostic_provenance_recovery_passed_status_integration`

> [!IMPORTANT]
> A8.4.2 is a status integration patch. Recovered heuristic area labels and modulo-resolved
> geometry candidates are upgrade candidates for THETA validation, not manuscript results.

## Recovery Results Summary

| Recovery Status | Count | Meaning |
| :--- | :---: | :--- |
| `geometry_resolved_candidate` | 739 | Diagnostic status |
| `recovered_heuristic_equal_segment` | 2736 | Diagnostic status |
| `unresolved_no_candidate_metadata` | 46 | Diagnostic status |

**Total A8.1 units**: 3521
**Upgrade candidates**: 3475
**Still unresolved after recovery**: 46
**Can support manuscript area claim**: 0 (zero)

## Recovery Method
- Source: `unit_nwb_profile.csv` (NWB-extracted metadata, not raw NWB payload)
- Area map: `session-area-mapping.md` (status: canonical, source_of_truth: true; CLI-overridable)
- Method: equal-segment heuristic plus modulo-128 channel translation for sequential global indices
- DP → V4 alias applied
- Generic V3 preserved as-is (cannot be split to V3d/V3a without channel metadata)

## Safety Locks
> [!WARNING]
> Recovered `heuristic_equal_segment` and `geometry_resolved_candidate` statuses are NOT manuscript-safe.
> Manuscript area or hierarchy claims remain **BLOCKED**.
> No biological population summaries are authorized.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Metadata Integration Agent / Plane: diagnostic / Repo: D:\workspace\omission / Date: 2026-05-25
