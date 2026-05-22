# Omission Phase A4 Trial-Count Validation Report
**Truth Status**: `truth_safe_unverified`

This analytical command center report verifies the structural completeness, trial count balances, and matched-control ratios across recording sessions using metadata inventories and filename maps.

## Summary Analytics
- **Total Sessions Analyzed**: 13
- **Metadata Sources Available**: 0 explicit files
- **Observed Trial Counts**: 24 session-condition entries
- **Inferred (File-Only) Conditions**: 132 session-condition entries
- **Missing Conditions**: 0 entries
- **Ambiguous Configurations**: 0 entries
- **Total Diagnostic Warnings**: 137

## Session Completeness & Readiness
| Session ID | Conditions Detected (out of 12) | Ready for A5 | All A Family | All B Family | All R Family |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `230629` | 12 | yes | yes | yes | yes |
| `230630` | 12 | yes | yes | yes | yes |
| `230714` | 12 | yes | yes | yes | yes |
| `230719` | 12 | yes | yes | yes | yes |
| `230720` | 12 | yes | yes | yes | yes |
| `230721` | 12 | yes | yes | yes | yes |
| `230816` | 12 | yes | yes | yes | yes |
| `230818` | 12 | yes | yes | yes | yes |
| `230823` | 12 | yes | yes | yes | yes |
| `230825` | 12 | yes | yes | yes | yes |
| `230830` | 12 | yes | yes | yes | yes |
| `230831` | 12 | yes | yes | yes | yes |
| `230901` | 12 | yes | yes | yes | yes |

## Condition Balance & Control Match Status
For all sessions, condition trial-counts are descriptive filename-derived or explicit.
No neural effect sizes have been computed.

## Diagnostic Warnings & Alerts
| Session ID | Warning Type | Condition | Detail |
| :--- | :--- | :--- | :--- |
| `230629` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230629` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |
| `230630` | `unresolved_v3_area` | `None` | Probe 2 uses generic V3. This area remains UNRESOLVED (not split into V3d/V3a). |
| `230714` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230714` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |
| `230719` | `normalized_dp_area` | `None` | Probe 1 uses DP alias, normalized to V4. |
| `230720` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230720` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230721` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `unresolved_v3_area` | `None` | Probe 2 uses generic V3. This area remains UNRESOLVED (not split into V3d/V3a). |
| `230816` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230816` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230818` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `unresolved_v3_area` | `None` | Probe 2 uses generic V3. This area remains UNRESOLVED (not split into V3d/V3a). |
| `230823` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230823` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230825` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `unresolved_v3_area` | `None` | Probe 2 uses generic V3. This area remains UNRESOLVED (not split into V3d/V3a). |
| `230830` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230830` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230831` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `AAAB` | Condition AAAB trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `AXAB` | Condition AXAB trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `AAXB` | Condition AAXB trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `AAAX` | Condition AAAX trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `BBBA` | Condition BBBA trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `BXBA` | Condition BXBA trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `BBXA` | Condition BBXA trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `BBBX` | Condition BBBX trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `RRRR` | Condition RRRR trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `RXRR` | Condition RXRR trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `RRXR` | Condition RRXR trial count inferred from file inventory presence; no explicit metadata found |
| `230901` | `inferred_trial_count` | `RRRX` | Condition RRRX trial count inferred from file inventory presence; no explicit metadata found |

## Light Metadata Bounding Note
> [!IMPORTANT]
> Under predictive routing execution guidelines, no high-density neural array payloads were loaded.
> Trial counts are parsed purely from high-level metadata catalogs and file naming schemas.

## No Biological Claims Note
This validation table is generated strictly for structural checks and matched balance reporting. No physiological hypotheses or empirical conclusions are drawn.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: descriptive-trial-counts / Repo or Workspace: D:\workspace\omission / Date: 2026-05-22
