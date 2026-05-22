# Omission Dataset Census & Taxonomy Summary Report
**Date**: 2026-05-21
**Truth Status**: `truth_safe_unverified`

## Summary Metrics
- **Total Recorded Sessions**: 13
- **Total Files Indexed**: 988
- **SPK Availability**: 13 sessions
- **MUAe Availability**: 0 sessions
- **LFP Availability**: 13 sessions

## Signal-Class Availability Table
| Session ID | SPK Availability | MUAe Availability | LFP Availability | Behavior Availability | Manifest Availability |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `230629` | `True` | `False` | `True` | `False` | `False` |
| `230630` | `True` | `False` | `True` | `False` | `False` |
| `230714` | `True` | `False` | `True` | `False` | `False` |
| `230719` | `True` | `False` | `True` | `False` | `False` |
| `230720` | `True` | `False` | `True` | `False` | `False` |
| `230721` | `True` | `False` | `True` | `False` | `False` |
| `230816` | `True` | `False` | `True` | `False` | `False` |
| `230818` | `True` | `False` | `True` | `False` | `False` |
| `230823` | `True` | `False` | `True` | `False` | `False` |
| `230825` | `True` | `False` | `True` | `False` | `False` |
| `230830` | `True` | `False` | `True` | `False` | `False` |
| `230831` | `True` | `False` | `True` | `False` | `False` |
| `230901` | `True` | `False` | `True` | `False` | `False` |

## Condition Coverage Table
| Session ID | Conditions Detected | Missing Core Conditions |
| :--- | :--- | :--- |
| `230629` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230630` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230714` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230719` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230720` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230721` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230816` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230818` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230823` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230825` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230830` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230831` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |
| `230901` | `AAAB,AAAX,AAXB,AXAB,BBBA,BBBX,BBXA,BXBA,RRRR,RRRX,RRXR,RXRR` | `None` |

## Missing Conditions by Session
The following sessions are missing standard condition families or timing sequences:
- None. All sessions have complete condition coverage.

## Candidate Sessions for A4 Trial-Count Validation
Sessions that meet basic signal class and metadata completeness criteria to enter the next trial-level parsing phase:
Candidates: `None`

## Unresolved V3 Warnings
Total occurrences: 4
The following sessions contain generic `V3` mappings on Probe 2 (unresolved to `V3d`/`V3a` laminar boundaries):
- **Session `230630`**: Probe 2 uses generic V3. This area remains UNRESOLVED (not split into V3d/V3a).
- **Session `230816`**: Probe 2 uses generic V3. This area remains UNRESOLVED (not split into V3d/V3a).
- **Session `230823`**: Probe 2 uses generic V3. This area remains UNRESOLVED (not split into V3d/V3a).
- **Session `230830`**: Probe 2 uses generic V3. This area remains UNRESOLVED (not split into V3d/V3a).

## DP->V4 Warnings
Total occurrences: 1
The following sessions contain `DP` alias labels normalized to `V4`:
- **Session `230719`**: Probe 1 uses DP alias, normalized to V4.

## Bounding & Payload Read Guard Verification Note
> [!IMPORTANT]
> Under the Phase 2/3 contracts, no high-density raw array payloads were loaded into local memory.
> `.npy` files were lightly shape-inspected strictly using numpy memory mapping (`mmap_mode='r'`).
> Non-npy formats (e.g. `.nwb`, `.mat`, `.h5`) were logged via file existence and size metadata only.

## No Biological Claims Note
This is a contract-level structural census and descriptive summary only. No average neural effect sizes, response latencies, tuning curves, or biological interpretations are proposed.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: descriptive-census / Repo or Workspace: D:\workspace\omission / Date: 2026-05-21