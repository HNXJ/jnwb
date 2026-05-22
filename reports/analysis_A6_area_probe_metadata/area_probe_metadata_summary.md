# Omission Phase A6 Area/Probe Metadata Inventory
**Truth Status**: `truth_safe_unverified`

This analytical command center report summarizes Phase A6 anatomical mappings linking indexed biological signals to session, probe, channel, and unit axis boundaries.

## Summary Analytics
- **Total Sessions Mapped**: 13
- **Sessions with Fully Resolved Metadata**: 3
- **Sessions Lacking Unit Metadata CSVs**: 10
- **Probes Resolved deterministically**: 60
- **LFP Channels Mapped**: 4352 resolved (`0` unmapped)
- **SPK Units Mapped**: 1482 resolved (`4370` unmapped)
- **Generic V3 Labels Encountered**: 4 (retains `unresolved_generic_v3` status)
- **DP -> V4 Aliases Applied**: 1 (aliased DP/DP (V4) -> V4)

## Session Metadata Inventory
| Session ID | Subject ID | Recording Date | Metadata Status | Warnings / Context |
| :--- | :--- | :--- | :--- | :--- |
| `230629` | `NHP_A` | `2023-06-29` | `partial_no_unit_metadata` | `No unit metadata CSV found; unit resolution unmapped` |
| `230630` | `NHP_A` | `2023-06-30` | `resolved` | `None` |
| `230714` | `NHP_A` | `2023-07-14` | `partial_no_unit_metadata` | `No unit metadata CSV found; unit resolution unmapped` |
| `230719` | `NHP_A` | `2023-07-19` | `partial_no_unit_metadata` | `No unit metadata CSV found; unit resolution unmapped` |
| `230720` | `NHP_A` | `2023-07-20` | `partial_no_unit_metadata` | `No unit metadata CSV found; unit resolution unmapped` |
| `230721` | `NHP_A` | `2023-07-21` | `partial_no_unit_metadata` | `No unit metadata CSV found; unit resolution unmapped` |
| `230816` | `NHP_B` | `2023-08-16` | `partial_no_unit_metadata` | `No unit metadata CSV found; unit resolution unmapped` |
| `230818` | `NHP_B` | `2023-08-18` | `resolved` | `None` |
| `230823` | `NHP_B` | `2023-08-23` | `partial_no_unit_metadata` | `No unit metadata CSV found; unit resolution unmapped` |
| `230825` | `NHP_B` | `2023-08-25` | `partial_no_unit_metadata` | `No unit metadata CSV found; unit resolution unmapped` |
| `230830` | `NHP_B` | `2023-08-30` | `resolved` | `None` |
| `230831` | `NHP_B` | `2023-08-31` | `partial_no_unit_metadata` | `No unit metadata CSV found; unit resolution unmapped` |
| `230901` | `NHP_B` | `2023-09-01` | `partial_no_unit_metadata` | `No unit metadata CSV found; unit resolution unmapped` |

## Probe and Axis Semantics Note
- **SPK/SUA Axis Semantics**: Structured as expected rank-3 dimensions (`trial x unit x time`), with units mapped via metadata `peak_channel_id` where available.
- **LFP Axis Semantics**: Structured as expected rank-3 dimensions (`trial x channel x time`), with channels partitioned deterministically using probe equal-segment channel boundaries.
- **MUAe**: No files detected in A5, MUAe continues to receive `not_detected_in_current_index` status.

## Safety & Architectural Constraints
- **One-Probe-One-Area Assumption Used**: `False` (probes can deterministically span multiple named visual/frontal areas).
- **Equal-Segment Heuristic Used**: `False` (applied linear partitioning for unit index assignment only when specified).
- **Raw Payload or NPY Payload Read**: `False` (all mappings were resolved strictly utilizing metadata sheets, filenames, and shape descriptors).

## Blockers before Phase A7 Sanity Checks
- Verification and approval of A6 area mappings must be finalized.
- Target unit and channel mapping profiles must match baseline predictions. No empirical rasters/PSTHs can be constructed until this inventory gate is accepted.

---
Footer: Agent: Claude / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: descriptive-signal-shapes / Repo or Workspace: D:\workspace\omission / Date: 2026-05-22
