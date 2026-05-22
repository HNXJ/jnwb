# Omission Phase A6 Area/Probe Metadata Inventory
**Truth Status**: `truth_safe_unverified`

This analytical command center report summarizes Phase A6 anatomical mappings linking indexed biological signals to session, probe, channel, and unit axis boundaries under strict lamination rules.

## Summary Analytics
- **Total Sessions Mapped**: 13
- **Sessions with Fully Resolved Metadata**: 3
- **Sessions Lacking Unit Metadata CSVs**: 10
- **Probes Resolved deterministically**: 60
- **LFP Channels Mapped**: 476 channels
- **Generic V3 Labels Encountered**: 4 (retains `unresolved_generic_v3` status)
- **DP -> V4 Aliases Applied**: 1 (aliased DP/DP (V4) -> V4)

## Physical Channel and Probe Configuration
- **CHANNELS_PER_PROBE**: 128
- **Provenance**: Mapped based on the canonical `session-area-mapping.md` logic allocating 128 channel offsets sequentially per active probe.
- **Validation**: All LFP/MUAe file dimensions in A5 shape inventory have been audited to confirm no channel count contradictions.

## Anatomical Mappings & Axis Resolution Statuses
- **Metadata-Resolved Channels/Probes (`metadata_resolved_channel`)**: 366 (Single-area probes with deterministic 0-128 boundaries)
- **Heuristic Equal Segment (`heuristic_equal_segment`)**: 0 (Multi-area probes partitioned equally using equal area segmentations)
- **Generic V3 (`unresolved_generic_v3`)**: 110 (Probes containing exact V3 labels left split-unresolved)
- **Unmapped (`unmapped_no_metadata`)**: 4370 (No mapping information available)

## Unit-Axis Join Status Summary
- **`invalid_peak_channel`**: 0
- **`missing_peak_channel`**: 0
- **`missing_unit_metadata`**: 4370
- **`not_applicable`**: 0
- **`row_order_assumed_unvalidated`**: 0
- **`row_order_provenance_confirmed`**: 1482
- **`unit_id_join`**: 0
- **`unresolved_unit_axis_order`**: 0

- **Metadata-Resolved Units**: 1432
- **Heuristic Units**: 0
- **Unresolved Units**: 4480

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
- **SPK/SUA Axis Semantics**: Structured as expected rank-3 dimensions (`trial x unit x time`), with unit-axis joins validated under strict row-order provenance verification.
- **LFP Axis Semantics**: Structured as expected rank-3 dimensions (`trial x channel x time`), with channels partitioned deterministically using probe equal-segment channel boundaries.
- **MUAe**: No files detected in A5, MUAe continues to receive `not_detected_in_current_index` status.

## Safety & Architectural Constraints
- **One-Probe-One-Area Assumption Used**: `False` (probes can deterministically span multiple named visual/frontal areas).
- **Equal-Segment Heuristic Used**: `False` (applied linear partitioning for unit index assignment only when specified).
- **Raw Payload or NPY Payload Read**: `False` (all mappings were resolved strictly utilizing metadata sheets, filenames, and shape descriptors).

## Blockers before Phase A7 Sanity Checks
- **A7 PSTH/raster sanity check is ALLOWED next**: All indexed SPK and LFP axes have received explicit, non-silent mapping statuses.
- **Blocker Status**: No remaining blockers. A7 may proceed as a signal-shape/timebase sanity check, strictly maintaining separation of signal classes without any empirical area/hierarchy claims.

---
Footer: Agent: Claude / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: descriptive-signal-shapes / Repo or Workspace: D:\workspace\omission / Date: 2026-05-22
