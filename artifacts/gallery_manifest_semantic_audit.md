# Gallery Manifest Semantic Audit - Phase 2A

## Summary
- **Total Indexed Items**: 352
- **Skipped Items**: 5 (Reasons: `unsafe` content, `oversized` >25MB)
- **File Types**: `html`, `png`, `csv`, `json`
- **Security Pass**: **PASSED** (No absolute Windows paths or private user paths detected)

## Semantic Completeness

| Metadata Field | Status | Notes |
|---|---|---|
| **Figure IDs** | **PARTIAL** | Inferred from directory names (e.g., `f005`) but not explicitly keyed. |
| **Signal Class** | **MISSING** | `LFP`, `SPK/SUA` are occasionally in tags, but inconsistent. |
| **Time Base** | **MISSING** | `omission-relative` vs `p1-relative` not explicitly tracked. |
| **Inference Tier** | **MISSING** | No distinction between descriptive, session-level, or population-level. |
| **Baseline/Contrast** | **MISSING** | Not present in manifest metadata. |
| **Artifact Hashes** | **VERIFIED** | SHA256 hashes present for all items. |

## Risk Assessment
- **Oversized Assets**: `conjunction_stable_top100.html` (33MB) is correctly skipped.
- **Unpublished Data**: `.csv` files with `_spk` suffixes are correctly skipped by `--public-safe` logic.
- **Ambiguity**: Without `inference_tier`, the gallery is a flat collection of files rather than a scientific hierarchy.

## Recommendations
1.  **Enhance Build Tool**: Update `tools/gallery/build_gallery.py` to parse `manifest.json` files within figure folders to extract semantic metadata.
2.  **Tag Normalization**: Enforce a strict vocabulary for `signal`, `time`, and `analysis` tags.
