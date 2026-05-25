# A8.4 Metadata Repair Recommendations
**Truth Status**: `truth_safe_unverified`

> [!IMPORTANT]
> These are recovery candidates, not validated manuscript results.
> Modulo-128 channel interpretation confirms NWB sequential indexing provenance,
> but is NOT validated anatomical truth. `geometry_resolved_candidate` status remains blocked
> from manuscript biological claims.

## What Was Recovered

| Recovery Status | Count | Meaning |
| :--- | :---: | :--- |
| `geometry_resolved_candidate` | 739 | Propagated diagnostic status |
| `recovered_heuristic_equal_segment` | 2736 | Propagated diagnostic status |
| `unresolved_no_candidate_metadata` | 46 | Propagated diagnostic status |

**Total A8.1 units processed**: 3521
**Units with upgrade candidate (heuristic/modulo)**: 3475
**Units remaining unresolved**: 46
**Units that can support manuscript area claim**: 0 (zero; heuristic and modulo resolutions are not manuscript-safe)

## Recovery Method: Modulo-128 Geometry Integration
The NWB unit_nwb_profile.csv provides `peak_channel_id` for each unit.
For global channel sequential mappings (index >= 128), applying `peak_channel_id % 128` maps
them to valid probe-local channel bounds `0-127` under the canonical session area map.

This resolves the 739 formerly unresolvable units as `geometry_resolved_candidate`.
All safety locks and disclaimers remain strictly active.

## Recommended Next Steps for THETA Validation
1. **Confirm NWB peak channel provenance**: Verify that `peak_channel_id` in
   `unit_nwb_profile.csv` matches the Kilosort/Phy `peak_channel` for each unit.
2. **Confirm channel map**: Verify the 0–127 channel IDs match the physical probe
   geometry (electrode site order may differ from channel index order).
3. **Validate equal-segment split**: The 50/50 area split assumes uniform electrode
   density. If the probe has non-uniform geometry, the split boundary may be off.
4. **Promote to metadata_resolved_channel**: Only after steps 1–3 can any unit
   be promoted from `recovered_heuristic_equal_segment` or `geometry_resolved_candidate` to `metadata_resolved_channel`.

## What Remains Blocked
- Manuscript area or hierarchy claims: **BLOCKED**
- Area-stratified biological population summaries: **BLOCKED**
- Higher-order omission coding claims: **BLOCKED**
- PFC enrichment claims: **BLOCKED**

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Metadata Integration Agent / Plane: diagnostic / Repo: D:\workspace\omission / Date: 2026-05-25
