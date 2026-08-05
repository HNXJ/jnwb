# Figure 3 — unit census: presence, functionality, and RXRR template traces

**This file previously stated the figure was synthetic and uncitable.** That was true of an
earlier staged asset (`svg/UNUSABLE_synthetic_census_2026-07-27.png`, hardcoded literals, no
data read — see History below) and is no longer true: `fig03_unit_census.py` computes every
number from `outputs/classification/omission_grand_units.csv` and the other sources below, with
exact binomial (Clopper-Pearson) intervals on proportions, session counts behind every cell, and
a receipt naming the classification pass. Do not restate the old "nothing here is citable"
framing without re-checking `svg/fig03_stats.md` first.

## Data sources

- `outputs/classification/omission_grand_units.csv` — 21 sessions, 8,592 units, `omission_class`
  (ns/O+/O++/O-/O--), `area10`, `animal`, `quality` (SUA=1/MUA=0). Changes when
  `scripts/classify_omission_units_grand.py` is re-run — check session/unit counts in the
  receipt before quoting anything.
- `outputs/classification/grand_s_and_o_units.csv` — the legacy S+/S- classifier, 15 of 21
  sessions, and only 2,921 of the grand table's units within those sessions (its own upstream
  quality/trial-count filter). `legacy_screened` is set from an actual per-unit join match
  (`is_Splus.notna()`), not session membership, so units in a legacy session that were never
  evaluated by that classifier are excluded rather than mislabeled `Null`.
- `outputs/classification/grand_stable_firing_rates.csv` — `stable_trials_keep_fraction`, used
  only for that field. Its own `quality` column disagrees with the grand table's on 1,942/6,650
  shared units (29%); `outputs/layers/unit_layers.csv` agrees with the grand table on every one
  of those, so the grand table's `quality` is treated as authoritative for the SUA/MUA split
  (`attach_stability()`).

## Methodology

**Main figure — four panels, in this order (2026-08-04 revision, see below):**

1. **Presence-per-area** — stable/unstable/mua, 100%-stacked, restricted to units with a
   resolvable presence label (`presence_evaluable`, 8,592/8,592 as of the current
   `unit_trial_presence.csv`). Legend states each class's pooled N across areas
   (`legend_show_total`), e.g. "stable (n=2611)".
2. **Functionality-per-area** — S++/S+/S-/S--/O-/O--/O+/O++/Null, 100%-stacked, restricted to
   the 2,921 legacy-screened units. MST and FST are merged into one bar (FST alone is 11 units).
   Any area with at least one O++ unit — too thin a segment to see at this scale — is marked
   with a red asterisk and a matching legend entry (V4, FEF, PFC in this corpus). Legend states
   each class's pooled N, e.g. "O++ (n=15)"; wraps onto two rows (10 legend entries no longer
   fits one row once every label carries an N — see `_stacked_pct`'s `ncol` cap).
3. **Peak-rate-per-area** (new 2026-08-04) — per-unit peak instantaneous firing rate, 100%-
   stacked into five classes: slow (<1 Hz), moderate-slow (1-5 Hz), moderate (5-10 Hz),
   moderate-fast (10-25 Hz), fast (≥25 Hz). Peak = the max mean rate in any 1-second sliding
   window of the unit's trial-averaged PSTH, maximized over all 12 `GLO_CONDITIONS` (not
   pooled) — see `compute_peak_rate_by_unit()`. Restricted to all 8,592 screened units (same
   population as panel c), not the legacy-screened subset panels 2/4 use.
4. **RXRR template trace** — three subplots: an idealized **SCHEMATIC** key (new 2026-08-04,
   `panel_ideal_template_schematic()` — hand-specified Gaussian bumps/dips on a flat baseline,
   explicitly labeled "idealized, not measured" in red on the panel itself, NOT derived from
   any unit's spike train) explaining what S+/S-/O+/O++ mean as instantaneous-firing-rate
   shapes, then the real population PSTH (mean, min-max scaled) for S++/S+/S-/S--/O-/O+/O++
   (O-- excluded, 4 units corpus-wide) split into S-family and O-family subplots, RXRR trials
   only, full trial (p1 onset to trial end), same legacy-screened restriction. Shares
   `compute_population_psth()` with panel h's 5-class, omission-aligned, all-conditions-pooled
   version — one NWB-traversal implementation, not two.

Panels a, c, d, f, g, h (four-question census, area chi-square/trend, waveform-type split,
sup/deep/Null layer composition, firing-rate/omission-effect correlation with its shuffle null,
and the 5-class omission-aligned PSTH) are unchanged but supplement-only — see `figS20`/`figS21`.

### 2026-08-04 revision

Three changes requested in review: (1) per-class N totals added to the presence,
functionality, and layer legends; (2) an idealized schematic key added alongside the real
S-family/O-family RXRR template traces, so a reader unfamiliar with the classifier has a plain
visual reference for what each class label means as a shape; (3) a new peak-instantaneous-
firing-rate-by-area panel (5 speed classes, computed across all 12 GLO conditions per unit).

Fixing (1) exposed a legend-overflow bug in the 10-entry functionality-per-area legend (text
ran past the figure's right edge once every label carried an N) and building (2) exposed a
**pre-existing** bug in `panel_template_trace_rxrr`'s legend placement, present before this
revision too: the legend's `bbox_to_anchor` offset (-0.30) didn't clear the rotated (55°) x-tick
labels below the axis, so the two overlapped. Both are fixed: `_stacked_pct`'s legend now caps
at 6 columns before wrapping to a second row, and the template-trace panel uses an explicit
`fig.subplots_adjust` with a much larger bottom margin instead of `fig.tight_layout` (which
silently refused to expand far enough and left the legend positioned past the canvas edge,
invisible in the saved file — found by rendering the panel standalone and inspecting the PNG,
not by reasoning about the layout).

## Statistics

All in `svg/fig03_stats.md`, one family per panel: `fig03_questions`, `fig03_area`,
`fig03_type`, `fig03_composition`, `fig03_layer`, `fig03_correlation`, `fig03_traces`,
`fig03_presence`, `fig03_peak_rate`, `fig03_rxrr_trace`. Each family is corrected together
(Holm-Bonferroni and Benjamini-Hochberg both reported, never conflated); unit of inference
stated per row.

## History

- `svg/UNUSABLE_synthetic_census_2026-07-27.png` — hardcoded literals throughout (class counts
  `[2158, 1565, 1178, 413, 421, 39, 2823]`, a fabricated per-area O+ vector with an invented
  `Spearman r = 0.988, p < 0.001`, Gaussian-PSTH exemplars). Retained for provenance, not
  citable, and not the current figure.
- 2026-07-29 redesign moved the population trace panel (formerly proposed for figure 1, which
  has never had trace content) into this figure as panel 3, and added the presence panel.
