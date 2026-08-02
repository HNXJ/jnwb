Version: 2026-07-29
Status: canonical figure layout for omission-a
Truth status: `truth_safe_unverified`; verify each figure against its receipt before submission.

# Figure layout

One directory per main figure. Each directory holds exactly three kinds of thing:

| Item | Name | Role |
|---|---|---|
| Code | `figNN_<analysis_description>.py` | the only script that draws this figure's panels |
| Panels | `svg/` | every panel the script emits, main and supplementary alike, plus receipts |
| Assembly | `figNN.svg` | the assembled figure, written by the same script from `svg/` |

Run a figure script with no arguments and it draws its whole panel set and then assembles
`figNN.svg` from it. Command-line arguments exist for ad-hoc panels and do not assemble.

Three shared modules sit beside the directories. They own no analysis and draw nothing:

- `figstyle.py` — the template: trial timing, the five band colours, the ten area colours, the
  class colours, the epoch shading, Cambria, and the exact binomial interval. Imported by
  every figure script so "identical template and colouring" is a property of the code.
- `svgassemble.py` — lays panels out on a grid and writes one SVG. Ids and CSS classes are
  namespaced per panel, because two exports dropped into one document otherwise collide and
  the second silently overwrites the first.
- `figstats.py` — the statistics harness. Parametric or non-parametric chosen per test by
  Shapiro-Wilk (and Levene for equal variance), never by habit; every test reports its
  statistic, degrees of freedom, n, unit of inference, and effect size (Cohen's d/dz, r,
  r-squared, rank-biserial r, Cramer's V, epsilon/eta squared as the test calls for).
  Corrections are applied within a declared family and BOTH are reported: `p_holm`
  (Holm-Bonferroni, controls family-wise error — the one that minimises false positives) and
  `q_BH` (Benjamini-Hochberg, controls false discovery rate). They are different guarantees
  and the written tables never conflate them. Every figure script calls `figstats.write()` and
  produces `svg/figNN[_variant]_stats.md` and `.csv` beside its panels.

Supplements have no code and no directory of their own. `build_supplements.py` assembles them
from panels already sitting in the `svg/` folders and writes them to `supplements/`.

Editing rule: hand edits belong in `figNN.svg`, and re-running the script overwrites it. Freeze
a figure by not re-running its script once the template-matching pass has been done.

## Status

| # | Directory | Code | Panels | Assembled | State |
|---|---|---|---|---|---|
| 1 | `fig01_recording_topology_and_paradigm/` | yes | 3 | `fig01.svg` | built, 468 x 585 pt, exactly 4:5 |
| 2 | `fig02_spiking_exemplar_rasters/` | yes | 1 (4x4 grid) | `fig02.svg` | raster-only, S+(V1)/S-(V3a/d)/O+(V4)/O++(FEF), hard-required areas, no fallback |
| 3 | `fig03_unit_census/` | yes | 11 | `fig03.svg` = presence + functionality + RXRR template trace | main figure holds 3 panels; a/c/d/f/g/h are supplement-only |
| 4 | `fig04_v1_pfc_condition_tfr/` | yes | 13 + 1 | `fig04.svg` = V1/PFC RXRR-vs-RRRR, 2x4 | old area x layer content is supplement-only now |
| 5 | `fig05_band_power_hierarchy/` | yes | 4 + 1 | `fig05.svg` = 5 bands x RXRR/RRRR, all areas | old omission-pooled hierarchy is supplement-only now |
| 6 | `fig06_band_power_coupling/` | no | — | — | analysis not written; see its README |
| 7 | `fig07_lfp_spike_coupling/` | no | — | — | analysis not written; see its README |

Figures 2 and 3 read `outputs/classification/omission_grand_units.csv`, so both change when
`scripts/classify_omission_units_grand.py` is re-run. Check the unit and session counts in
their receipts before quoting anything from them.

**Figure 4's old area x layer supplement panels** are still drawn 27 inches wide, so their
supplements use a landscape width (see `build_supplements.py`'s `LANDSCAPE` constant); this no
longer affects the main figure, which is now its own 15.5 x 6.6 inch layout.

## Supplements

`python build_supplements.py --list` prints the plan without writing. 21 are built today; three
more are pending on figures 6 and 7 and are named in `PENDING` rather than faked. Running the
script now also deletes any `supplements/figS*` file not named by the current `PLAN` before
writing — confirmed necessary 2026-07-29, when a prior numbering pass had left 19 stale
duplicate-numbered files on disk (two different figures both called "S07", etc.) that a plain
`--list` diff would not have caught since it never compares against what already exists.

## Inventory

`python build_inventory.py` walks every figure folder plus `build_supplements.py`'s PLAN and
writes `INVENTORY.md`: code file, svg/ folder contents by type, assembled-figure dimensions,
every statistics family with its test count, which supplements pull from that folder, and a
methodology summary pulled from the figure's own `README.md`. Auto-generated, not hand-edited,
for the same staleness reason as the supplement-cleanup step above. `--check` exits 1 if a
figure with code has no README.md, or has zero statistical tests recorded with no by-design
exemption — use it as a pre-submission gate, not part of the normal build.

## Figure 2 (2026-07-29 redesign)

4x4 raster grid: columns S+(V1)/S-(V3a/d)/O+(V4)/O++(FEF) are fixed by the figure spec, not
chosen from whichever area has the strongest unit — a missing candidate in the named area is a
hard `SystemExit`, never a silent fallback. Rows are RRRR/RXRR/RRXR/RRRX. No rate-trace row;
that summary now lives in fig03's population trace panels. Shares `figstyle.mark_full_trial_axis`
/ `full_trial_ticks` with fig03's RXRR template trace instead of keeping its own duplicate copy.

## Figure 3 (2026-07-29 redesign)

**Main figure is now exactly three panels**, assembled in this order into `fig03.svg`:

1. **presence-per-area** — stable/unstable/mua composition, 100%-stacked. `mua` is the grand
   table's own `quality == 0`; `stable`/`unstable` split `quality == 1` units at
   `stable_trials_keep_fraction >= 0.90` against `grand_stable_firing_rates.csv`. That table
   carries its OWN `quality` column too, which disagrees with the grand table's on 1,942 of
   6,650 shared units (29%) — `unit_layers.csv` agrees with the grand table on every one of
   those, so the grand table's field is treated as authoritative and the stable-rates table is
   used only for the keep-fraction. See `attach_stability()`.
2. **functionality-per-area** (was panel e) — S++/S+/S-/S--/O-/O--/O+/O++/Null, 100%-stacked,
   restricted to the 2,921 legacy-screened units (see `attach_legacy()`). MST and FST are now
   merged into one bar (FST alone is 11 units) and any area containing at least one O++ unit
   (a segment too thin to see at this scale) is marked with a red asterisk, with a matching
   legend entry — V4, FEF and PFC as of this corpus.
3. **RXRR template trace** — population PSTH (mean ± SEM across units) for
   S++/S+/S-/S--/O-/O+/O++ (O-- excluded, 4 units corpus-wide), RXRR trials only, full trial
   (p1 onset to end, not just the omission window), same legacy-screened restriction.

Panels a, c, d, f, g, h (the four-question census, area chi-square/trend, waveform-type split,
sup/deep/Null layer composition, firing-rate/omission-effect correlation with its shuffle null,
and the 5-class omission-aligned PSTH) are unchanged but are supplement-only now — see
`figS20`/`figS21`. All stats, old and new, are in `svg/fig03_stats.md`, one family per panel:
`fig03_questions`, `fig03_area`, `fig03_type`, `fig03_composition`, `fig03_layer`,
`fig03_correlation`, `fig03_traces`, `fig03_presence`, `fig03_rxrr_trace`.

`compute_group_traces` was generalised into `compute_population_psth(df, class_col, order, win,
bin_ms, onset_fn)` so panel h (5 classes, all omission conditions pooled, omission-aligned) and
the RXRR trace (7 classes, RXRR only, p1-aligned) share one NWB-traversal implementation instead
of two near-identical copies.

## Figures 4 and 5 (2026-07-29 redesign) — new source: `scripts/extract_condition_tfr_maps.py`

Both now compare RXRR (omission at p2) against RRRR (no omission, p2 real) directly, which the
existing `omission_tfr_maps_w1500/maps.npz` cannot do: it pools all nine omission conditions and
aligns to the omitted slot, and RRRR has no omitted slot to align to and is excluded from it
entirely. `extract_condition_tfr_maps.py` reads the per-condition `.npy` arrays that already
exist on disk (`D:/workspace/data/tfr_arrays/*-RXRR.npy`, `*-RRRR.npy`) — no new NWB pass —
keeps RXRR and RRRR separate, and aligns both to **p1 onset** (t = 0) rather than an omission
event only one of them has. **Baseline is the middle third of d1 (706-856 ms from p1), not a
pre-trial fixation window** — the delay after the first real stimulus and before p2, late
enough that the p1 transient has decayed and early enough that it cannot anticipate p2. Window
is -500 to +2593 ms (p1 through the p3/d3 boundary), covering exactly fx-p1-d1-p2-d2-p3.
Output: `outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz`, keyed `session|area|layer|cond`.

- **Figure 4** (`fig04_v1_pfc_condition_tfr/`, renamed from `fig04_area_layer_tfr/` since its
  scope changed entirely) — 2 rows (V1, PFC) x 4 columns (spectrogram-RXRR, spectrogram-RRRR,
  band-trace-RXRR, band-trace-RRRR), panels a-h. The old area x layer, omission-pooled analysis
  (`draw_area`, `PANEL_SET`) is unchanged and still feeds supplements S05-S16 from the same
  `svg/` folder; it is simply no longer what the main figure shows.
- **Figure 5** (`fig05_band_power_hierarchy/`) — 5 rows (bands) x 2 columns (RXRR, RRRR), all
  ten areas overlaid per panel. The old omission-pooled, all-conditions-pooled hierarchy panels
  (`run()`, `PANEL_SET`) are unchanged and still feed supplements S17-S19; they are simply no
  longer what the main figure shows.

Both main-figure builders share `figstyle.mark_full_trial_axis` for the p1-aligned epoch
shading and omission marker, the same helper fig02 and fig03's RXRR trace use.

**Sanity check passed**: gamma/beta bursts appear at p1 and p3 in both conditions, and at p2
ONLY in RRRR (real stimulus) — flat at p2 in RXRR (omitted) — across V1, PFC (fig04) and all
ten areas (fig05). This is the expected signature of the omission manipulation itself, not an
analysis result, and it confirms the new p1-aligned, middle-of-d1-baselined extraction is
working correctly before either figure's traces are read as findings.

**Footgun**: fig05's RXRR/RRRR figure trips matplotlib's `tight_layout` compatibility check
(`UserWarning: This figure includes Axes that are not compatible with tight_layout`), which
silently no-ops instead of raising — three different `tight_layout(rect=...)` values produced
an identical, wrong result (a large blank band under the title) before this was traced to the
warning. Fixed by using explicit `gridspec_kw` margins (`top`/`bottom`/`left`/`right`) passed
to `plt.subplots()` instead, and dropping `bbox_inches="tight"` from `savefig`. If a future
panel in this repo needs `tight_layout` and the layout looks wrong, check for this warning in
the script's stdout before assuming the rect values are the problem.
