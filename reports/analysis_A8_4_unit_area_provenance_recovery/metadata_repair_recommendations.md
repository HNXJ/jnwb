# A8.4 Metadata Repair Recommendations
**Truth Status**: `truth_safe_unverified`

> [!IMPORTANT]
> These are recovery candidates, not validated manuscript results.
> `recovered_heuristic_equal_segment` is NOT manuscript-safe without THETA validation.

## What Was Recovered

| Recovery Status | Count |
| :--- | :---: |
| `recovered_heuristic_equal_segment` | 2736 |
| `source_probe_resolved_but_channel_unresolvable` | 739 |
| `unresolved_no_candidate_metadata` | 46 |

**Total A8.1 units processed**: 3521
**Units with upgrade candidate (heuristic)**: 2736
**Units remaining unresolved**: 785
**Units that can support manuscript area claim**: 0 (zero; heuristic is not manuscript-safe)

## Recovery Method: Equal-Segment Heuristic
The NWB unit_nwb_profile.csv provides `peak_channel_id` for each unit.
The session-area-mapping.md (canonical, source_of_truth) defines probe-to-area
mappings with 128 channels per probe, split equally between areas.
Channel-to-area resolution uses this equal-segment split (NOT per-channel metadata).

This is `heuristic_equal_segment` status — the same as A6 heuristic.
It cannot support manuscript-level area claims without further validation.

## Recommended Next Steps for THETA Validation
1. **Confirm NWB peak channel provenance**: Verify that `peak_channel_id` in
   `unit_nwb_profile.csv` matches the Kilosort/Phy `peak_channel` for each unit.
2. **Confirm channel map**: Verify the 0–127 channel IDs match the physical probe
   geometry (electrode site order may differ from channel index order).
3. **Validate equal-segment split**: The 50/50 area split assumes uniform electrode
   density. If the probe has non-uniform geometry, the split boundary may be off.
4. **Promote to metadata_resolved_channel**: Only after steps 1–3 can any unit
   be promoted from `recovered_heuristic_equal_segment` to `metadata_resolved_channel`.

## What Remains Blocked
- Manuscript area or hierarchy claims: **BLOCKED**
- Area-stratified biological population summaries: **BLOCKED**
- Higher-order omission coding claims: **BLOCKED**
- PFC enrichment claims: **BLOCKED**

---
Footer: Agent: Antigravity / Model: Gemini 2.5 Pro / Role: Metadata Repair Analyst / Plane: diagnostic / Repo: D:\workspace\omission / Date: 2026-05-25
