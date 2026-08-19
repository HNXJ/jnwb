# Figure 2 — exemplar raster grid (S+/S-/O+/O++, 4x4)

**This file previously described a 4x3 layout (S+, S-, O+ only). That is superseded.** Current
spec, rebuilt 2026-07-29: **4 rows x 4 columns**. Rows are RRRR, RXRR, RRXR, RRRX (the R-family,
maximum-entropy condition set). Columns are fixed by spec, not chosen from whichever unit looks
best: S+ (must be area V1), S- (must be V3a/d), O+ (must be V4), O++ (must be FEF). A missing
candidate unit in the required area is a hard `SystemExit`, never a silent fallback to another
area — see `pick_column()` in `fig02_spiking_exemplar_rasters.py`. The layout, colours, titles
and axes are a locked spec (see `figure2_reference_layout_spec.md` in the user's persistent
memory, or the module docstring in the script) — check there before changing anything here.

## Data source

S+/S- come from the legacy `grand_s_and_o_units.csv` classifier (`is_Splus`/`is_Sminus`,
`r_Splus`/`r_Sminus` against the standard sequence, 15 of 21 sessions). O+/O++ come from the
current Q1-conjunction class in `omission_grand_units.csv` (`omission_class`, all 21 sessions).
**These are two different classifiers on two different session sets and are never pooled or
compared statistically against each other** — the population-level test that DOES pool across
them, restricted to the legacy-screened intersection, is figure 3's `fig03_questions` and
`fig03_composition` families.

## Methodology

Each panel is one named unit's raster across all trials of that row's condition, full trial
(p1 onset to trial end, not just the omission window) via `figstyle.mark_full_trial_axis`/
`full_trial_ticks` — the same helper fig03's RXRR template trace uses, so epoch shading and the
omission marker are pixel-identical across the two figures.

No inferential test is reported for this figure: each column is a single named unit selected as
the strongest example of its class, and n = 1 supports no test. `svg/fig02_stats.md` states this
explicitly and points to figure 3 for the population-level test.

## Panels

- Main figure (`fig02.svg`): the 4x4 raster grid, one assembly, no other content.
- Supplements: none currently drawn from this folder (all four columns are shown at their
  intended size in the main figure already).

## History

Two prior states of this directory are retained for provenance, neither citable:

- `svg/fig02_rasters_2026-07-14_orphan.svg` — the asset originally staged as figure 2. No
  generating code exists anywhere in this repository for it (a repo-wide grep for its embedded
  title string returns only a script that relabels the rendered PNG).
- An earlier 2026-07-29 rebuild used a 3(block)-by-4(variant) layout (A/B/R families x
  full/omit@2/omit@3/omit@4), answering the same Q1 question but not matching the user's
  reference image. Superseded same-day once the reference was supplied.
- The immediately-prior 4x3 (S+/S-/O+ only) layout was superseded same-day by the addition of
  the O++ (FEF) column and the swap of the S- exemplar to a ~10 Hz firing-rate unit, per the
  user's explicit feedback.
