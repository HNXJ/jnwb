# Figure 5 — band-power hierarchy, RXRR vs RRRR, all areas

Main figure redesigned 2026-07-29 to the same RXRR-vs-RRRR comparison as figure 4, generalized
across all ten areas and all five canonical bands (theta 4-8, alpha 8-14, beta 14-30, low gamma
30-50, high gamma 50-80 Hz — see project `CLAUDE.md`, "Band definitions — settled, do not
re-drift").

## Data source

Same as figure 4: `outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz` from
`scripts/extract_condition_tfr_maps.py` — p1-aligned, middle-of-d1 baseline, trial-pooled within
session. See `fig04_v1_pfc_condition_tfr/README.md` for the full extraction rationale; both
main-figure builders share `figstyle.mark_full_trial_axis` for identical epoch shading and the
omission marker.

## Methodology

5 rows (bands) x 2 columns (RXRR, RRRR), all ten areas overlaid per panel by line colour
(`AREA_COLORS`). Uses explicit `gridspec_kw` margins rather than `tight_layout` — this axes
configuration trips matplotlib's `tight_layout` compatibility check, which warns and silently
no-ops instead of raising, and produced an identical wrong result (a blank band under the title)
across three different `rect=` attempts before being traced to the warning text in the script's
stdout. If a future panel here needs `tight_layout` and the layout looks wrong, check for that
warning before assuming the `rect` values are the problem.

**Sanity check passed**: same p1/p3-present, p2-only-in-RRRR gamma/beta signature as figure 4,
confirmed across all ten areas, not just V1/PFC.

## Statistics

`svg/fig05_condition_stats.md`, family `fig05_condition_p2`: same paired-by-session
Wilcoxon/paired-t construction as figure 4's `fig04_condition_p2`, extended to all ten areas x
five bands (50 tests, one family, Holm and BH-FDR both reported). Strongest, most significant
effects are gamma/beta in MT, V4, MST (p2 real > p2 omitted); FEF is the only area trending
negative, and does not survive correction (p_holm = 1.0) — reported, not overclaimed. FST has
only 2 sessions with both conditions and returns no test ("too few finite pairs") rather than a
number nobody could interpret.

The old omission-pooled, all-conditions-pooled hierarchy panels (`run()`, `PANEL_SET`, still
feeding `figS17`-`figS19` from this same `svg/` folder) carry their own stats file
(`fig05_band_hierarchy_stats.md` and per-layer variants) unchanged.

## Panels

- Main figure (`fig05.svg`): the 5x2 band x condition grid, all areas overlaid, 468 x 459 pt.
- Old omission-pooled hierarchy panels (unchanged, no longer the main figure): feed `figS17`,
  `figS18`, `figS19`.
