# Omission Phase A5 Signal Availability & Shape Census
**Truth Status**: `truth_safe_unverified`

This analytical command center report summarizes signal-class availability, array shape status, rank-3 dimension validations, and blocked raw formats across recording sessions.

## Summary Analytics
- **Total Sessions Analyzed**: 13
- **NPY Files Shape-Inspected**: 972 files
- **Blocked Raw Formats**: 13 files (`.h5` formats)
- **Unexpected Shape Ranks**: 0 files
- **Sessions Complete & Ready for A6**: 13 sessions (SPK and LFP complete)
- **Total Diagnostic Warnings**: 0

## Session Signal Availability & Readiness Matrix
| Session ID | SPK Availability | MUAe Availability | LFP Availability | Ready for A6 |
| :--- | :---: | :---: | :---: | :---: |
| `230629` | `complete` | `missing` | `complete` | yes |
| `230630` | `complete` | `missing` | `complete` | yes |
| `230714` | `complete` | `missing` | `complete` | yes |
| `230719` | `complete` | `missing` | `complete` | yes |
| `230720` | `complete` | `missing` | `complete` | yes |
| `230721` | `complete` | `missing` | `complete` | yes |
| `230816` | `complete` | `missing` | `complete` | yes |
| `230818` | `complete` | `missing` | `complete` | yes |
| `230823` | `complete` | `missing` | `complete` | yes |
| `230825` | `complete` | `missing` | `complete` | yes |
| `230830` | `complete` | `missing` | `complete` | yes |
| `230831` | `complete` | `missing` | `complete` | yes |
| `230901` | `complete` | `missing` | `complete` | yes |

## SPK/LFP/MUAe Status Note
- **SPK/SUA**: Mapped to expected rank-3 dimensions (`trial, unit, time`) under shape validation.
- **LFP**: Mapped to expected rank-3 dimensions (`trial, channel, time`) under shape validation.
- **MUAe**: Not detected in current index (`not_detected_in_current_index`) across all 13 sessions.

## Blocked Raw Formats
- 13 large `.h5` files (1 per session) remain strictly unopened with no payload reads (`blocked_no_payload_read`).

## Diagnostic Warnings & Alerts
| Session ID | File Basename | Warning Type | Detail |
| :--- | :--- | :--- | :--- |
| None | - | - | All shape and signal checks passed perfectly |

## Safe Metadata Bounding Note
> [!IMPORTANT]
> No raw neural payloads were loaded into local memory or materialized.
> Array shape and dimension inspections were safely performed utilizing numpy's `mmap_mode="r"` or cached metadata entries.
> All `payload_read` flags are verified as `False`.

## No Biological Claims Note
This validation table is generated strictly for structural checks and matched shape reporting. No physiological hypotheses or empirical conclusions are drawn.

---
Footer: Agent: Claude / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: descriptive-signal-shapes / Repo or Workspace: D:\workspace\omission / Date: 2026-05-22
