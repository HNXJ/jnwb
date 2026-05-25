# A8.4.1 Geometry Validation Recommendations
**Truth Status**: `truth_safe_unverified`

> [!IMPORTANT]
> Channel resolution of the 739 unresolvable units validates NWB sequential indexing
> indexing provenance, but is NOT validated anatomical truth.

## Recommended Next Steps for A8.4.2 Metadata Repair Patch
1. **Apply the Geometry Patch**: Incorporate modulo-128 channel conversion into the primary
   recovery pipeline to upgrade the 739 units to `geometry_resolved_candidate` status.
2. **Refactor Default Paths**: Relativize or configure default paths in `run_unit_area_provenance_recovery_a8_4.py`
   to resolve the portability blocker.
3. **Probe Physical Geometry Verification**: Obtain physical probe electrode coordinates to
   verify equal-segment boundary alignments and promote candidates to `metadata_resolved_channel`.

## What Remains Blocked
- Area-stratified biological summaries: **BLOCKED**
- Higher-order omission hierarchy claims: **BLOCKED**
- PFC/FEF population enrichment claims: **BLOCKED**

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Metadata & Geometry Validation Agent / Plane: diagnostic / Repo: D:\workspace\omission / Date: 2026-05-25
