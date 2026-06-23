---
status: active
scope: figure-provenance
source_of_truth: true
last_reviewed: 2026-06-23
---

# Pie Charts Summary Provenance

## Legacy figure

The file `outputs/publication_visual_review/pie_charts_summary.svg` is a Matplotlib SVG
(`Matplotlib v3.10.8`) created on `2026-06-22T15:27:18Z`.

The legacy SVG mixed two scopes:

- panels A-D: all 6,040 units
- panels E-H: stable-only subset

### Extracted legacy counts

- A. Present / Low Presence: 5,302 / 738
- B. Stable / Unstable-MUA: 3,071 / 2,969
- C. S+ / S- / Other: 1,790 / 1,366 / 2,884
- D. Superficial / Deep / Other-Unresolved: 614 / 1,813 / 3,613
- E. Firing-rate tiers: 22 / 315 / 729 / 1,398 / 607
- F. Waveform durations: 992 / 497 / 373 / 248 / 961
- G. Bursty / Non-bursty: 12 / 3,059
- H. Fano tiers: 834 / 1,363 / 874

## Evaluation

The legacy panel A split is not tied to an explicit repository boolean field. It appears
threshold-derived from firing-rate-like values, but the exact cut is opaque. That makes it
less suitable as a reproducible analysis criterion.

## Revised remake

The repo now includes `scripts/remake_pie_charts_summary.py`, which rebuilds the summary
with explicit inputs:

- `outputs/publication_figures/grand_database_6040_units.csv`
- `outputs/publication_figures/stable_units_calculated_metrics.csv`

### Revised criteria

- Panel A: stable-plus gate
- Panel B: stable vs unstable/MUA
- Panel C: stimulus modulation
- Panel D: laminar assignment
- Panels E-H: stable-only metrics with explicit bins

The rebuilt figure is written to:

- `outputs/publication_visual_review/pie_charts_summary_revised.svg`
- `outputs/publication_visual_review/pie_charts_summary_revised.csv`
- `outputs/publication_visual_review/pie_charts_summary_revised.md`

