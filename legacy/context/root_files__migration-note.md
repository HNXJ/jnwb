# Migration Note: context/ Folder Reorganization (Step 1)

**Last Updated**: 2026-04-06
**Status**: Completed (2026-04-06)

This document tracks all moves, merges, archives, and deletions during the context/ folder cleanup pass.

## Duplicate Detections (Confirmed)
- `nwb-areas-table` duplicates merged into `context/specs/overview__session-area-mapping.md`
- `bhv-task-details` duplicates merged into `context/specs/task-specification.md`

## Migration Track

| Original Path | Action | Final Destination | Rationale |
|---------------|--------|-------------------|-----------|
| `readme.md` | Merged | `overview/project-overview.md` | Consolidated overview |
| `vmemory.md` | Merged | `overview/project-overview.md` | Consolidated overview |
| `docs/notes/data-availability-summary.md` | Refined | `overview/data-availability.md` | Canonical data summary |
| `docs/nwb-areas-table.md` | Merged | `overview/session-area-mapping.md` | Canonical area mapping |
| `plans/nwb-areas-table.md` | Deleted | N/A | Exact duplicate of above |
| `plans/task-details.md` | Merged | `specs/task-specification.md` | Consolidated task spec |
| `plans/task-details-full.md` | Merged | `specs/task-specification.md` | Consolidated task spec |
| `plans/gamma-task-specification.md` | Merged | `specs/task-specification.md` | Consolidated task spec |
| `plans/bhv-task-details.md` | Merged | `specs/task-specification.md` | Consolidated task spec |
| `plans/task-details-bhv.md` | Deleted | N/A | Exact duplicate of above |
| `plans/nwb-pipeline-standard.md` | Merged | `specs/pipeline-standard.md` | Consolidated pipeline spec |
| `plans/lfp-nwb-pipeline-standard.md` | Merged | `specs/pipeline-standard.md` | Consolidated pipeline spec |
| `plans/15-step-lfp-pipeline.md` | Merged | `specs/pipeline-standard.md` | Consolidated pipeline spec |
| `docs/reproducibility.md` | Moved | `specs/reproducibility.md` | Relocated to specs |
| `plans/omission-plan.md` | Merged | `analysis/roadmap.md` | Consolidated roadmap |
| `plans/omission-analysis-plan.md` | Merged | `analysis/roadmap.md` | Consolidated roadmap |
| `plans/lfp-analysis-roadmap.md` | Merged | `analysis/roadmap.md` | Consolidated roadmap |
| `plans/next-steps-plan.md` | Merged | `analysis/roadmap.md` | Consolidated roadmap |
| `plans/progress-details.md` | Merged | `analysis/roadmap.md` | Consolidated roadmap |
| `plans/omission-decoding-method.md` | Refined | `analysis/decoding-framework.md` | Refined analysis spec |
| `docs/methodology-01-spiking.md` | Renamed | `analysis/methods-spiking.md` | Normalized naming |
| `docs/methodology-02-spectral.md` | Renamed | `analysis/methods-spectral.md` | Normalized naming |
| `docs/methodology-03-rsa-cka.md` | Renamed | `analysis/methods-rsa-cka.md` | Normalized naming |
| `docs/methodology-04-behavior.md` | Renamed | `analysis/methods-behavior.md` | Normalized naming |
| `plans/high-fidelity-plots.md` | Merged | `figures/figure-suite.md` | Consolidated figure plan |
| `plans/omission-v4-figure-suite.md` | Merged | `figures/figure-suite.md` | Consolidated figure plan |
| `docs/figure_03_description.md` | Renamed | `figures/figure-03-population-firing.md` | Normalized naming |
| `docs/figure_05_description.md` | Renamed | `figures/figure-05-tfr.md` | Normalized naming |
| `docs/figure_06_description.md` | Renamed | `figures/figure-06-band-summary.md` | Normalized naming |
| `docs/reports/figures-1-to-6-summary.md` | Merged | `manuscript/results-summary.md` | Consolidated results summary |
| `docs/spiking-manuscript-synthesis.md` | Merged | `manuscript/results-summary.md` | Consolidated results summary |
| `docs/poster-01-neural-dynamics-omission-spectral.md` | Renamed | `manuscript/poster-01.md` | Normalized naming |
| `docs/poster-02-omission-neuronal-oscillations-predictive-routing.md` | Renamed | `manuscript/poster-02.md` | Normalized naming |
| `docs/notes/crucial-debugging-notes.md` | Renamed | `operations/troubleshooting.md` | Normalized naming |
| `docs/summary_1_initial_setup.md` | Merged | `operations/implementation-history.md` | Historical record |
| `docs/summary_2_lfp_pipeline_and_laminar_mapping.md` | Merged | `operations/implementation-history.md` | Historical record |
| `docs/summary_3_pipeline_orchestration_and_data_structure.md` | Merged | `operations/implementation-history.md` | Historical record |
| `docs/summary_4_figure_generation_tfr_and_band_summary.md` | Merged | `operations/implementation-history.md` | Historical record |
| `docs/summary_5_figure_generation_population_firing_rate_and_conclusion.md` | Merged | `operations/implementation-history.md` | Historical record |
