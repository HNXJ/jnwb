# Phase A8.4: Unit-Area Provenance Recovery
**Truth Status**: `truth_safe_unverified`
**Validation Status**: `diagnostic_provenance_recovery_not_biological_claim`

> [!IMPORTANT]
> A8.4 is a metadata repair diagnostic only. Recovered heuristic area labels
> are upgrade candidates for THETA validation, not manuscript results.

## Recovery Results Summary

| Recovery Status | Count |
| :--- | :---: |
| `recovered_heuristic_equal_segment` | 2736 |
| `source_probe_resolved_but_channel_unresolvable` | 739 |
| `unresolved_no_candidate_metadata` | 46 |

**Total A8.1 units**: 3521
**Upgrade candidates (heuristic)**: 2736
**Still unresolved after recovery**: 785
**Can support manuscript area claim**: 0 (zero)

## Recovery Method
- Source: `unit_nwb_profile.csv` (NWB-extracted metadata, not raw NWB payload)
- Area map: `session-area-mapping.md` (status: canonical, source_of_truth: true)
- Method: equal-segment heuristic (128 ch/probe, 50/50 area split)
- DP → V4 alias applied
- Generic V3 preserved as-is (cannot be split to V3d/V3a without channel metadata)

## Safety Locks
> [!WARNING]
> Recovered `heuristic_equal_segment` status is NOT manuscript-safe.
> Manuscript area or hierarchy claims remain **BLOCKED**.
> No biological enrichment claims are supported by this phase.

---
Footer: Agent: Antigravity / Model: Gemini 2.5 Pro / Role: Metadata Repair Analyst / Plane: diagnostic / Repo: D:\workspace\omission / Date: 2026-05-25
