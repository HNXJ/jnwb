# Registry Reconciliation Plan - Phase 2A

This document classifies all existing `src/f*` folders against the `FigureRegistry` defined in `src/analysis/registry.py`.

## Multiplicity Resolution

| ID | Folder Path | Classification | Rationale |
|---|---|---|---|
| **f021** | `src/f021_madelamo` | **ACTIVE_CANONICAL** | Primary schematic for model architecture. |
| **f021** | `src/f021_pupil_decoding` | **EXPLORATORY_UNREGISTERED** | Secondary analysis, not part of canonical manuscript flow. |
| **f028** | `src/f028_spectral_identity` | **ACTIVE_CANONICAL** | Main spectral fingerprint correlation analysis. |
| **f028** | `src/f028_state_manifolds` | **EXPLORATORY_UNREGISTERED** | Experimental dimensionality reduction. |
| **f029** | `src/f029_effective_connectivity`| **ACTIVE_CANONICAL** | Canonical connectivity analysis (inter-area). |
| **f029** | `src/f029_info_bottleneck` | **EXPLORATORY_UNREGISTERED** | Information theory pilot. |
| **f030** | `src/f030_recurrence_dynamics` | **ACTIVE_CANONICAL** | Recurrence analysis for stability. |
| **f030** | `src/f030_putative_cell_type` | **EXPLORATORY_UNREGISTERED** | Cell type classification (PV/SST focus). |

## Orphan Classification (Unregistered)

| Folder Path | Classification | Rationale |
|---|---|---|
| `src/f021_pupil_decoding` | **EXPLORATORY_UNREGISTERED** | Duplicate ID f021. |
| `src/f028_state_manifolds` | **EXPLORATORY_UNREGISTERED** | Duplicate ID f028. |
| `src/f029_info_bottleneck` | **EXPLORATORY_UNREGISTERED** | Duplicate ID f029. |
| `src/f030_putative_cell_type` | **EXPLORATORY_UNREGISTERED** | Duplicate ID f030. |

## Proposed Actions

1.  **Registry Update**: Keep `src/analysis/registry.py` as the truth.
2.  **Manifest Exclusion**: Ensure `build_gallery.py` only indexes **ACTIVE_CANONICAL** folders unless explicitly overridden.
3.  **Future Re-assignment**: Exploratory folders will be assigned new unique IDs (e.g., `f051+`) if promoted to canonical status.
4.  **No Deletions**: No folders will be deleted in this phase to preserve pilot data.
