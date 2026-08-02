# Figure 4 — V1/V3a-d/TEO/PFC time-frequency, RXRR vs RRRR

Renamed 2026-07-29 from `fig04_area_layer_tfr/` since its scope changed entirely: the main
figure now directly compares RXRR (p2 omitted) against RRRR (p2 real), which the omission-pooled
`omission_tfr_maps_w1500/maps.npz` cannot do (it pools all nine omission conditions, aligns to
the omitted slot, and excludes RRRR entirely — RRRR has no omitted slot to align to).
**Expanded 2026-07-31 from V1/PFC only to the four areas named in the CLAUDE.md figure plan
(V1, V3a/d, TEO, PFC)** — the original two-area build was a scope gap against that plan, not a
deliberate reduction; data for all four areas already existed in
`condition_tfr_maps_p1d1p2d2p3/maps.npz`.

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

Main figure: 4 rows (V1, V3a/d, TEO, PFC) x 4 columns (spectrogram-RXRR, spectrogram-RRRR,
band-trace-RXRR, band-trace-RRRR), panels a-p. Colour scale is common across all sixteen
spectrograms, symmetric, set to the 99th percentile of |dB| pooled across them. Sessions with a
grossly out-of-scale map (single-channel near-zero-baseline artifacts) are dropped from display
only — see `drop_outlier_sessions()`.

**Sanity check passed**: gamma/beta bursts appear at p1 and p3 in both conditions, and at p2
ONLY in RRRR (real stimulus) — flat in RXRR (omitted). This is the expected signature of the
omission manipulation itself, not a finding, and confirms the p1-aligned, middle-of-d1-baselined
extraction is working before either figure's traces are read as results.

## Statistics

`svg/fig04_condition_stats.md`, family `fig04_condition_p2`: paired-by-session test (Wilcoxon or
paired t, chosen by Shapiro-Wilk on the differences) of p2-window (1031-1562 ms) mean band power,
RRRR minus RXRR, per area x band (20 tests, 4 areas x 5 bands), corrected together. This
operationalizes the sanity check above as an inferential statistic rather than a qualitative
read of the spectrogram. The older area x layer, omission-pooled analysis (`draw_area`,
`PANEL_SET`, still feeding `figS05`-`figS16` from this same `svg/` folder) carries its own
per-panel stats files (`fig04_V1_PFC_layers_stats.md`, `supp_*_layers_stats.md`) unchanged.

## Panels

- Main figure (`fig04.svg`): the 4x4 V1/V3a-d/TEO/PFC condition comparison, 15.5 x 13.2 in.
- Old area x layer content (unchanged, no longer the main figure): feeds `figS05`-`figS16`
  (landscape-oriented, since those panels are drawn 27 inches wide — see `LANDSCAPE` in
  `build_supplements.py`).
