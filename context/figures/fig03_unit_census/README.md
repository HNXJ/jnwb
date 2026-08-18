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

### Upstream trial-minimum / classification contract (added 2026-08-11, fig03 closure)

`fig03_unit_census.py` does not itself apply a per-unit trial-count floor -- both source
tables are pre-filtered by their own upstream classifiers before this script ever loads them:

- **O-family** (`omission_class`, `outputs/classification/omission_grand_units.csv`): built by
  `scripts/classify_omission_units_grand.py`, which requires `MIN_TR = 6` trials in each
  compared slot/condition (e.g. `scripts/classify_omission_units_grand.py:186`,
  `if rs.size < MIN_TR or rf.size < MIN_TR: <exclude>`) before a unit can be scored against any
  of the four questions. A unit failing this floor is not counted as `ns`; it is absent from
  that question's own denominator (see `units_answering_each_question` in
  `svg/fig03_receipt.json`, which is smaller than `n_units` for every question).
- **Legacy S-family** (`grand_s_and_o_units.csv`, feeding the 2,921 `legacy_screened`
  population panels A-F use): applies its own upstream quality/trial-count filter in
  `scripts/archive_oneoff/find_all_s_and_o_units.py` before a unit is ever scored -- this
  script was not re-derived line-by-line as part of the 2026-08-11 closure pass (no `MIN_TR`-
  style constant was found by inspection); if the legacy classifier's own trial floor needs to
  be quoted precisely, re-read that script rather than assuming it matches `MIN_TR = 6`.

Any per-panel N difference from `n_units` (8,592) or `legacy_screened` (2,921) reflects one of
these upstream floors, not a bug in this script.

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

### 2026-08-06 revision — main figure rebuilt as 3 rows x 2 columns

Per direction, the main figure's four-panel layout (presence, composition, peak-rate, RXRR
template trace + UMAP) is replaced with six panels:

- **A** — composition-by-area (unchanged, formerly panel "e" / `panel_composition8_by_area`).
- **B** — O+-only zoom of the same composition and denominator, since O+ is a ~0-2% sliver too
  thin to read at panel A's scale (`panel_composition_oplus_zoom`, exact binomial CI per area).
- **C/D/E/F** — grand average ± SEM firing rate, full trial (p1-aligned), for S+/S++ pooled,
  S-/S-- pooled, O+, and O++ respectively, each panel overlaying all four R-family conditions
  (RRRR/RXRR/RRXR/RRRX) so the reader sees, per class, both the real-stimulus response AND the
  omission-evoked change at whichever slot that condition omits
  (`compute_population_psth_multi_condition` + `panel_grand_average_by_condition`). This
  replaces the old single pooled-RXRR template-trace panel (min-max-scaled shape comparison)
  with real, unscaled rate traces split by condition.

**Panels visually verified** (rendered via headless-Chrome-equivalent browser preview, per this
project's own falsifier convention) before calling this done:
- **C (S+/S++)**: clean, expected pattern — each condition's own omitted slot shows a flat,
  suppressed trace while the other three conditions show a real stimulus-evoked peak there.
- **D (S-/S--)**: mirror-image of C (real stimulus suppresses these units; the omitted slot
  shows a lack of suppression instead), equally clean.
- **E (O+)**: the interesting, condition-specific pattern this class is defined by — e.g. RXRR
  (omits p2) shows an elevated bump specifically during the p2 window relative to the other
  three conditions, and RRXR (omits p3) shows the same at p3. Wide CI bands reflect n=70.
- **F (O++)**: **n=3 units** (this class's own 4-condition/legacy-screened intersection, far
  below the class's corpus-wide n=15) — pure noise, no discernible pattern, included for
  completeness per direction ("keep O++ too since it is not a large group") but **not
  interpretable**. State this plainly wherever F is cited; do not read shape into it.

### 2026-08-06, same day: smoothing + panel B redenominated, checked against direction

Two follow-up changes, both applied and verified by rendering:
- **C-F smoothed** (`_gaussian_smooth`, same sigmas the old template-trace panel already used:
  3 bins for S-family, 6 for O-family) — both the mean and the SEM band. Real improvement, not
  cosmetic: E (O+)'s condition-specific omission-evoked bump is now clearly visible where it was
  previously buried in bin-to-bin noise. F (O++, n=3) stays uninterpretable even after
  smoothing — smoothing cannot manufacture a signal that isn't in 3 units' worth of data, and
  none appears.
- **Panel B redenominated**: O+'s share of (O+, S+, S-) only, not of the whole legacy-screened
  population. **Checked against the stated prediction (share should rise toward higher-order
  areas) and it does not hold in this corpus**: V2 (early visual) is highest at 50% (10/20), FEF
  (frontal) is one of the lowest at 14% (7/50), PFC sits at 19% (17/88) — comparable to V1's 23%
  (5/22), not higher. No monotonic order effect is visible. Also worth flagging plainly: every
  area's denominator here is tiny (11-88 units, since it excludes S++/S--/O-/O++/Other), so the
  95% CIs overlap almost completely across all nine areas — none of these are statistically
  distinguishable from each other at this n, independent of whether the point estimates happen
  to trend in one direction or another.

### 2026-08-13 — panel-tag fix, panel B replaced, panel E/F trial-pooled SEM added

- **Panel tags fixed a,b,a,b,a,b -> a,b,c,d,e,f.** `svgassemble.assemble()` letters panels
  `chr(97+k)` local to each call; `main()` calls it three times (row1/row2/row3, 2 panels each),
  so every row restarted at 'a'. Added a `letter_offset` parameter to `assemble()` and pass
  0/2/4 for row1/row2/row3. Panel identities are unchanged (a=e/composition-by-area, b=the
  panel B slot, c=S+/S++, d=S-/S--, e=O+, f=O++) -- only the printed letters were wrong.
- **Panel B's ambiguous title fixed.** The old title read "low->high order, left->right",
  which reads as "bars sorted ascending by value" but actually meant "areas ordered by visual
  hierarchy, V1 to PFC" (they are NOT value-sorted -- V2 sits at 50% between smaller
  neighbors). Reworded to "V1->PFC visual hierarchy, left->right"; bars/data unchanged.
- **Panel B replaced.** No longer O+'s share of (O+, S+, S-) (previous section, 2026-08-06).
  Now `panel_composition_oplusplus_by_area`: O++'s share of (O+, O++) only, by area -- among
  units that show any omission effect, what fraction show the strong/++ version. Same
  hierarchy-ordered x-axis and Clopper-Pearson 95% CI convention as before. O++ is vanishingly
  rare (15 units corpus-wide, see panel A), so per-area n's are small and most CIs are wide;
  read the printed k/n, not just bar height.
- **Panels E/F (O+, O++) SEM changed to trial-pooled, by explicit request.** Previously (and
  still for C/D) the SEM band is std-across-per-unit-means / sqrt(n_units) -- the unit is the
  level of replication, since a unit's own trials are not independent samples of the population
  effect. For E/F only, the band now pools every trial from every unit as a flat replicate:
  std over the concatenated (n_trials_total, n_bins) matrix / sqrt(n_eff) per bin. This was
  flagged before implementing -- pooling trials this way is the same pseudo-replication pattern
  this project's statistics doctrine warns against elsewhere (channel-within-probe in the fig05
  GLMM), and it is most consequential for F (O++, n=3 units): the band gets much tighter, but it
  quantifies trial-to-trial spread pooled across a nearly-fixed 3-unit set, not uncertainty about
  the population-level O++ effect, which 3 units cannot resolve regardless of trial count.
  Requested and confirmed anyway; implemented literally, and both the panel's y-axis label and
  its per-condition legend now say "trials=" instead of "n=" and state explicitly this band is
  descriptive, not a unit-level uncertainty estimate, so it cannot be misread as more units. Mean
  lines (`mu`) are unchanged -- still the mean of per-unit means, for every class including
  O+/O++; only the SEM band's basis changed. See `compute_population_psth_multi_condition`'s
  `trial_pooled_classes` parameter and `panel_grand_average_by_condition`'s `sem_kind` handling.

**Moved to supplement** (`svg/fig03_supp_presence_by_area.*`, `svg/fig03_supp_peak_rate_by_area.*`,
`svg/fig03_supp_class_embedding.*`, assembled together as
`svg/fig03_supp_presence_peakrate_umap.svg`): the presence/stability panel, the peak-rate panel,
and the UMAP embedding. UMAP was kept conditional on visibly clustering by supergroup (O+/O++
together, S+/S++ together, S-/S-- together, Other surrounding) — **checked directly against the
rendered panel, and it does not**: O+ units (magenta) are scattered throughout with no distinct
cluster, "Other" (gray) is intermixed rather than surrounding the other groups, though S++ and
S-- do occupy loosely separated regions (bottom vs. top). Per the stated condition, it stays in
the supplement rather than being forced into the main figure or artificially re-clustered.

Internal script/output filenames were not renamed (`compute_population_psth`,
`panel_template_trace_rxrr`, etc. remain even though `panel_template_trace_rxrr`'s own output is
now supplement-only, not part of the assembled main figure) — same convention used elsewhere in
this project (directory/figure identity is tracked externally, not by internal names).

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
