# Figure 4 — V1/V3a-d/TEO/PFC time-frequency, RXRR vs RRRR

Renamed 2026-07-29 from `fig04_area_layer_tfr/` since its scope changed entirely: the main
figure now directly compares RXRR (p2 omitted) against RRRR (p2 real), which the omission-pooled
`omission_tfr_maps_w1500/maps.npz` cannot do (it pools all nine omission conditions, aligns to
the omitted slot, and excludes RRRR entirely — RRRR has no omitted slot to align to).
**Expanded 2026-07-31 from V1/PFC only to the four areas named in the CLAUDE.md figure plan
(V1, V3a/d, TEO, PFC)** — the original two-area build was a scope gap against that plan, not a
deliberate reduction; data for all four areas already existed in
`condition_tfr_maps_p1d1p2d2p3/maps.npz`.

**Reworked 2026-08-04, unsealing the 2026-08-03 lock, across several passes the same day:**
1. **Layout**: the previous main-figure grid interleaved spectrogram and trace columns per
   area row (spec-RXRR, spec-RRRR, trace-RXRR, trace-RRRR). It is now two stacked blocks —
   every area's spectrograms first, then every area's band-power traces — per review.
2. **New data**: `extract_condition_tfr_maps.py`'s `CONDS` was extended from R-family-only
   (RXRR/RRXR/RRRR) to add the p2-matched A-family (AXAB/AAAB) and B-family (BXBA/BBBA) pairs.
   All twelve GLO conditions' `.npy` arrays already existed in `TFR_DIR`; this was a re-run of
   the same local-file aggregation over more of them, not a new NWB pass (~97 min, see
   `outputs/condition_tfr_maps_p1d1p2d2p3/receipt.json`).
3. **A GLMM section was built, then removed from the figure, same day.** Two mixed-model
   passes (a crossed `context x family` design, then a two-question reframe: "is it an
   omission?" / "does omission type matter?") were built, reviewed, and refined (see git
   history / `artifacts/.lab/fig04_*_20260804.json` for the full record) — then, per further
   review, dropped from `fig04.svg` entirely so the figure shows **spectrograms and traces
   only**, matching the originally-approved 4x4 layout. The fitting/plotting functions
   (`fit_omission_yesno_glmm`, `fit_omission_type_glmm`, `panel_omission_yesno`,
   `panel_omission_type`, `build_glmm_long_table`) are still defined in the script and still
   runnable, just not called by `build_v1_pfc_condition_figure()` — real, reviewed analysis
   kept for a possible manuscript supplement, not wired into this figure's default build.
4. **Trace SEM is now precision-weighted across sessions**, not a plain unweighted
   across-session SEM — see "Trace SEM" below.
5. **Supplement content added**: single-panel spectrogram/trace SVGs for the six areas not in
   the main figure (V2, V4, MT, MST, FST, FEF) — see "Supplement panels" below.

## Data source

`scripts/extract_condition_tfr_maps.py` → `outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz`,
keyed `session|area|layer|cond`. Reads the per-condition `.npy` arrays that already exist on
disk (`D:/workspace/data/tfr_arrays/*-RXRR.npy`, `*-RRRR.npy`) — no new NWB pass. Both
conditions align to **p1 onset** (t=0), not an omission event only RXRR has.

**Baseline is the middle third of d1 (706-856 ms from p1), not a pre-trial fixation window** —
late enough that the p1 transient has decayed, early enough that it cannot anticipate p2. Window
is -500 to +2593 ms (p1 through the p3/d3 boundary): fx-p1-d1-p2-d2-p3 exactly. Note `maps.npz`
is trial-pooled within session (sums/counts, not per-trial arrays) — session is therefore the
finest unit of inference available from this input; a per-trial test would need a different
extraction.

## Methodology

Main figure: two stacked 4x2 blocks (V1, V3a/d, TEO, PFC rows; RXRR/RRRR columns) —
spectrograms first, then band-power traces, panels a-p. Each spectrogram is autoscaled to
itself: per-panel symmetric ±|dB| limit at the 99th percentile of that panel's finite values
(`colour_scale_db_per_panel` in the receipt) — the scale is NOT common across panels, because
the four areas differ in modulation magnitude (V1 ~±8 dB, PFC ~±1 dB). Sessions with a
grossly out-of-scale map (single-channel near-zero-baseline artifacts) are dropped from display
only — see `drop_outlier_sessions()`.

**Sanity check passed**: gamma/beta bursts appear at p1 and p3 in both conditions, and at p2
ONLY in RRRR (real stimulus) — flat in RXRR (omitted). This is the expected signature of the
omission manipulation itself, not a finding, and confirms the p1-aligned, middle-of-d1-baselined
extraction is working before either figure's traces are read as results.

## Trace SEM (2026-08-04): precision-weighted across sessions

`draw_condition_bandtrace()` used to compute the across-session SEM unweighted (plain
`nanstd(ddof=1)/sqrt(n_sessions)`, treating every session equally regardless of how many
channels/trials/frequency bins actually went into its own mean). Review asked whether that
SEM properly reflects that a band's power estimate at each time point already pools many
channels, trials, and frequency bins within a session, and whether the ribbon could be made
narrower to reflect that.

**Literally dividing by `sqrt(channels x trials x bins)` was rejected**: those pooled
observations are not independent (same probe, same session, correlated adjacent frequency
bins), so treating them as independent replicates would manufacture precision that isn't
really there and would visually disagree with the paired/GLMM tests elsewhere in this
pipeline, which correctly use session as the unit of inference. The `weighted_band_mean_sem()`
function implements the agreed alternative instead: each session's contribution to the
across-session mean and SEM is weighted by that session's own pooled channel x trial count in
the band (summed over the band's frequency rows, from `count_maps` — `load_condition_maps()`
now returns this alongside the mean maps; it was already computed by
`extract_condition_tfr_maps.py` but discarded before 2026-08-04). Sessions built from more
data pull the estimate harder and contribute less noise. The standard error is denominated by
Kish's effective sample size across sessions (`sum(w)^2 / sum(w^2)`), not by raw pooled count
— session remains the unit of inference; the weighting only changes how much each session's
own noise level is trusted. Effect measured on V1 low-gamma at the p1 peak: SEM narrowed to
~96% of the unweighted value (modest, not dramatic — the honest cost of not claiming
channel/trial/frequency-bin independence).

## Statistics

`svg/fig04_condition_stats.md`, family `fig04_condition_p2`: paired-by-session test (Wilcoxon or
paired t, chosen by Shapiro-Wilk on the differences) of p2-window (1031-1562 ms) mean band power,
RRRR minus RXRR, per area x band (20 tests, 4 areas x 5 bands), corrected together. This
operationalizes the sanity check above as an inferential statistic rather than a qualitative
read of the spectrogram. The older area x layer, omission-pooled analysis (`draw_area`,
`PANEL_SET`, still feeding `figS05`-`figS16` from this same `svg/` folder) carries its own
per-panel stats files (`fig04_V1_PFC_layers_stats.md`, `supp_*_layers_stats.md`) unchanged.

## Supplement panels (2026-08-04): the other six areas

`build_area_condition_supplements()` draws single-panel spectrogram and band-trace SVGs
(same drawing functions, same RXRR-vs-RRRR design, same precision-weighted SEM, own
per-panel autoscaled colour limits) for `SUPP_AREAS = ["V2", "V4", "MT", "MST", "FST", "FEF"]`
— the six of the ten analysis areas not in the main figure's `CONDITION_AREAS`. 6 areas x 2
conditions x 2 panel types = 24 individual SVG/PNG files, saved in this figure's own `svg/`
folder (`fig04_supp_<area>_<cond>_spectrogram.svg` / `..._trace.svg`), not assembled into a
grid — "the supplement of this figure would be the other areas... make the single subpanel
svgs." Receipt: `svg/fig04_supp_areas.receipt.json`. FST has only 2 sessions; read its panels
as illustrative, not a population estimate. Not yet wired into `build_supplements.py`'s
`PLAN` (that assembles panels into a numbered `figSNN`) — these currently exist only as
individual assets; hooking them into a formal supplement number is a separate step if wanted.

## Slot-aligned omission-vs-stimulus supplement (2026-08-04, complete)

A further request asked to pool ALL omission positions (not just p2) — AXAB/BXBA/RXRR (2nd
omission), AAXB/BBXA/RRXR (3rd), AAAX/BBBX/RRRX (4th) — against a matched "stimulus" pool, to
increase statistical power. This does not fit into the p1-aligned design above: pooling events
that land at different p1-relative times without re-aligning them would smear the transient
across three different clock times. `outputs/omission_tfr_maps_w1500/maps.npz` already does
the omission side correctly (all nine omission conditions, aligned to the omitted slot). The
matched stimulus-side counterpart — `scripts/extract_stimulus_pooled_tfr_maps.py`, aligning
AAAB/BBBA/RRRR to each of their own p2/p3/p4 real-stimulus onsets (9 pseudo-conditions,
matching the omission side's 9 in count and slot-position distribution) — was built and run to
completion 2026-08-04 (303 files, 353 keys, 105 min runtime; 6 files skipped for a pre-existing
"no channel segment" gap in one V182o session, same gap that affects any V3a/d extraction from
that session). This is a **separate supplement**, not a change to this figure's own p1-aligned
p2-only design, per explicit direction.

`scripts/build_omission_vs_stimulus_slot_pooled_supplement.py` draws it: per area, spectrograms
(omission-pooled | stimulus-pooled) sharing one colour scale, then band-trace panels with the
same precision-weighted SEM (`weighted_band_mean_sem`, reused directly, not reimplemented) as
the main figure above. All 10 of 10 areas plotted, matching the six-area RXRR/RRRR supplement's
own precedent: FST (2 sessions on both sides) is included but flagged directly on the panel
title as "illustrative, not a population estimate", not silently dropped by an `n>=3` floor.
Colour scale (-7.6, +7.6 dB) is common across all areas and both sides, symmetric, 99th
percentile of |dB|.

**Sanity check passed**: at every area, the stimulus-pooled side shows the expected gamma/beta
burst in the 0-531 ms window (the omitted slot's own onset-to-next-delay window) that is flat
in the omission-pooled side — the same signature the main figure's own sanity check confirms,
now pooled across all three slot positions instead of p2 only.

**Statistics**: `svg/fig04_supp_slotpooled_stats.md`, family `fig04_supp_slotpooled` — paired-
by-session test (Wilcoxon or paired t, chosen by Shapiro-Wilk on the differences) of the 0-531
ms window mean band power, stimulus-pooled minus omission-pooled, per area x band. Family is
every area x band pair with >=3 common sessions (FST's 2 sessions do not qualify and produce no
stats row, consistent with `paired_location`'s own "too few finite pairs" floor elsewhere in
this codebase) — 45 tests: 9 areas x 5 bands, corrected together. 5/45 survive Holm-Bonferroni
(MT beta/low-gamma/high-gamma, V4 beta, MT theta) — MT carries the strongest, most consistent
effect in this cut.

Output: `svg/fig04_supp_slotpooled_<area>.svg/.png` (10 files, all areas), `svg/
fig04_supp_slotpooled_stats.csv/.md` (45 rows, 9 areas), `svg/fig04_supp_slotpooled.
receipt.json`. Not wired into `build_supplements.py`'s `PLAN` — same open item as the six-area
RXRR/RRRR supplement panels above.

## Panels

- Main figure (`fig04.svg`): spectrogram block + trace block (V1/V3a-d/TEO/PFC x RXRR/RRRR),
  spectrograms and traces only.
- `fig04_v1_pfc_rxrr_rrrr.svg/.png` — same content; `fig04.svg` is a straight rescale-to-width
  wrap of this one panel via `svgassemble.assemble()`.
- `fig04_supp_<area>_<cond>_spectrogram.svg/.png`, `fig04_supp_<area>_<cond>_trace.svg/.png` —
  the six-area supplement panels described above.
- `fig04.png` is a copy of `fig04_v1_pfc_rxrr_rrrr.png` (same dpi, same content) — the
  finalized PNG, once panel content is approved, should be produced from `fig04.svg` via
  headless Chrome, same convention figs 1-3 used (see
  `context/figures/HANDOUT_NEXT_AGENT_2026-08-03.md`).
- Old area x layer content (unchanged, no longer the main figure): feeds `figS05`-`figS16`
  (landscape-oriented, since those panels are drawn 27 inches wide — see `LANDSCAPE` in
  `build_supplements.py`).
