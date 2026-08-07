# [DEMOTED 2026-08-06] SPK-SPK lead/lag correlation + directed Granger — now a supplement

**Demoted from main figure slot 2026-08-06.** This was fig06; `figS24_omission_identity_decoding`
was promoted to fig04, the old fig04 (V1/PFC TFR) moved into fig06's vacated slot, and this
figure moved here (`spk_spk_coupling_supplement/`) to make room — same rename-only pattern as
`../band_power_hierarchy_supplement/`'s earlier demotion. Internal script/output filenames below
still say `fig06` (`fig06_spk_spk_coupling.py`, `fig06.svg`, `svg/fig06_stats.md`) and are NOT
renamed; the directory name is the source of truth for figure status, not the internal names.
Demotion reason: with 4/12,033 Holm survivors all clustered at lag 0, this result reads as
near-simultaneous population coupling, not the lead/lag structure the figure was built to show —
a real, correctly-reported finding, but not one that carries a main-figure slot as well as the
identity-decoding result does. Nothing below this notice was rewritten.

---

# Figure 6 — SPK-SPK lead/lag correlation (headline) + directed Granger (supplement)

**Layout expanded 2026-08-06 (second pass, same day).** `fig06.svg` is now three rows: (1) the
lead/lag correlation headline, unchanged; (2) the rate-ratio network diagrams, one per condition
group (baseline/stim/omission); (3) the rate-ratio lag-profile plot for the 3 Holm-Bonferroni
survivor pairs. Rows 2-3 were built first as a supplement (`fig06_supp_rateratio.svg`, still
exists in full — see that section below, plus a third panel type, the full-family heatmap, kept
supplement-only) and then pulled into the main figure per explicit direction ("rate-ratio
network is good; and lag profile, to be added in the second row of figure 6"). `fig06_finalized.
svg`/`.png` re-snapshotted from this new `fig06.svg` (PNG composited from the same panel PNGs
matplotlib already writes — no working SVG rasterizer on this machine, same constraint noted for
fig03's finalized PNG).

**Redesigned 2026-08-06.** Headline is now `scripts/extract_population_spk_spk_lag_corr.py`'s
trial-matched lead/lag correlation between (area, functional_type) population-rate nodes, per
direction to keep directed Granger causality for LFP-LFP (figure 5) only and use sliding
correlation for SPK-SPK. Full design and result: `outputs/population_spk_spk_lag_corr/README.md`.

**Result, stated plainly**: of the corrected family (12,033 cells: scope x node-pair x lag x
condition-group, all cells with >=3 sessions), **4 survive Holm-Bonferroni, 35 survive BH-FDR**.
The lag values argue against an actual lead/lag relationship: all 4 Holm survivors sit at lag 0
or +-10ms, and most BH survivors are within +-30ms of zero. What's real here is near-simultaneous
population coupling in a handful of specific (area, functional-type) pairs — V4 Null vs S-, V4
S+ vs S-, FEF Null vs S- — not a directional lead/lag signal. Session counts behind every
survivor are small (3-7 of up to 17 available).

The directed Granger analysis below is now a **supplement** (`fig06_supp_granger.svg`) — it is
the originally-planned method this headline replaces, kept for completeness, not because it
found a group-level effect (it did not: 0/27, unchanged).

---

## Supplement: directed Granger causality

Built 2026-08-04, same directed Granger-causality engine and design as
`fig05_lfp_lfp_coupling/fig05_lfp_lfp_coupling.py` — see that script's own docstring for the
shared statistical rationale.

## Data source

`scripts/extract_condition_spike_trials.py` (new 2026-08-04) → `outputs/condition_spike_trials/
trials.npz` — per-trial, per-area10 **population-pooled** spike-rate (Hz) time series, RXRR vs
RRRR, p1-aligned, same window (-500..+2593 ms) and 10 ms bins as fig05's LFP input so the two
networks share identical nodes and time base. All units in `omission_grand_units.csv` per
session contribute (quality 0 and 1 both — a population-rate connectivity node is not the same
use case as a single-unit classification claim; restricting to quality==1 would silently thin
some areas more than others).

**Bug caught before the full run counted as final**: the first extraction attempt silently
processed only 11 of 21 sessions (92 keys) because the NWB filename pattern assumed a uniform
`..._rec.nwb` suffix — true for C31o/V198o sessions but not V182o (`sub-V182o_ses-260629.nwb`,
no `_rec`). Confirmed by listing `D:/analysis/nwb` directly, not by inspection of the code
alone. Fixed to try both suffixes; re-run recovered all 10 missing V182o sessions (166 keys, 21
sessions).

## Method

`jnwb.connectivity.directed_network()`, `method='granger'` (`order='auto'` by BIC, `max_lag=10`,
`zscore` detrend — identical settings to fig05, not re-tuned per result). One
`directed_network()` call per (session, condition) — no band dimension, spikes have none — over
every area present (up to all 10). 42 calls across 21 sessions, 56s runtime.

## Statistics

Same three-family design as fig05: `fig06_RXRR` and `fig06_RRRR` (net directionality != 0
within one condition, paired by session vs zero) and `fig06_delta` (RRRR vs RXRR paired
difference), corrected together (Holm + BH) across the full directed-edge grid per family.
`diagnostics_warning_rate` = 0.70 (70% of individual session-level Granger fits carried a
non-stationarity or residual-autocorrelation diagnostic warning — lower than fig05's 100%, but
still substantial; the group-level test uses session-level point estimates, not these
within-session p-values, so this doesn't invalidate the result, but any single edge's raw p is
descriptive only).

## Result, stated plainly

**Also null.** 0/27 tests survive Holm-Bonferroni across all three families (9 area pairs each
for RXRR, RRRR, and the RRRR-vs-RXRR delta). Smallest raw p:
`MT<->TEO` net directionality, RXRR (p=0.036, p_holm=0.32, n=8) and RRRR (p=0.050, p_holm=0.45,
n=8) — the same area pair, both conditions, in the same direction. Descriptively interesting
(and notably, `MT<->TEO` was also fig05's smallest-p edge, `low_gamma` band, RRRR-vs-RXRR
delta) but neither survives correction and this is not reported as a finding.

**This is the third of three connectivity methods attempted on this corpus (as of 2026-08-04)
to come back null at the group level for a figures-4-7 slot**: LFP-LFP imaginary coherency
(0/240), LFP-LFP directed Granger (0/150), SPK-SPK directed Granger (0/27). Per
[[feedback-figures-require-significance]], flagged to the user rather than silently accepting a
null main figure or launching a fourth expensive method (e.g. transfer entropy, already running
for fig05 as a multi-hour job) without a decision on strategy.

## Output

`fig06_spk_spk_coupling.py` reads `outputs/condition_spike_trials/trials.npz`, writes
`outputs/spk_spk_granger_network/edges.csv` (checkpointed per session) and `net_directionality.
csv`, draws `svg/fig06_rxrr_network.svg` / `svg/fig06_rrrr_network.svg`, assembles `fig06.svg`,
writes `svg/fig06_stats.md`/`.csv` via `figstats.write()`.

---

## Supplement: rate-ratio (negative-binomial), added 2026-08-06

Three new panels, assembled into `fig06_supp_rateratio.svg`, drawing on the already-computed,
already-corrected NB rate-ratio family (`outputs/population_spk_spk_rateratio_nb/
rateratio_hit_rates.csv`, 30/13,790 Holm, 3,963/13,790 BH-FDR -- see that output directory's own
README for the full extraction/aggregation design). This is a visualization pass only; no new
statistical test was run for this addition. Sits alongside the lead/lag-correlation headline,
not replacing it -- same relationship as the rate-ratio model has to the headline throughout
this project.

1. **`fig06_rateratio_lag_profile.svg`** -- rate ratio vs. lag for the 3 Holm-Bonferroni
   survivor pairs, one subplot each, with BH-only and Holm points marked distinctly. Confirms
   visually what the aggregate README states in words: FEF/Other-TEO/Other (baseline) is
   BH-significant at 98% of the 41 tested lags with a rate ratio that trends smoothly from
   ~1.00 at negative lags to ~0.92 at +200 ms (Holm survives only at the 170-200 ms edge, where
   the effect is largest); TEO/Other-TEO/S- (stim) is BH-significant at 95% of lags in a tight
   1.05-1.08 band; V4/Other-V4/S+ (stim) is BH-significant at 100% of lags, rising smoothly from
   ~1.08 to ~1.13. None of the three shows a peak-and-decay shape at an interior lag -- the
   signature a genuine fixed-delay coupling would produce.
2. **`fig06_rateratio_network_{baseline,stim,omission}.svg`** -- circular graph, nodes =
   (area, functional_type), one condition group per panel. Edge width encodes the fraction of
   tested lags reaching BH-FDR significance (wide = significant almost everywhere = the
   shared-context-like pattern); edge colour encodes mean rate ratio at the significant lags
   (RdBu_r, matching the Granger network's red = facilitative / blue = suppressive convention);
   Holm-Bonferroni survivors get a black diamond at the edge midpoint. Baseline carries 57
   BH-significant edges across 24 nodes, stim carries 67 across 25 nodes -- confirming the
   pattern is not confined to the 3 Holm survivors but widespread at the more permissive
   threshold, consistent with a shared-context account rather than a handful of isolated
   couplings.
3. **`fig06_rateratio_heatmap_{baseline,stim,omission}.svg`** -- same visual grammar as the
   headline's lag x pair heatmap (viridis hit-rate fill, red boxes for Holm, dashed for
   BH-only), but built from the rate-ratio family and restricted to the pairs that reach BH-FDR
   significance at least once (57/114 tested pairs at baseline). Rows where the red boxes span
   nearly the full width are the visual definition of "flat significance" the interpretation
   above depends on.

**Sidecar**: `svg/fig06_rateratio_summary.md` lists the 30 Holm survivors with their full
statistics, pointing back to the complete 13,790-row family table rather than reproducing it
(same rationale as `fig06_lag_corr_summary.md` for the headline -- see the module docstring).

**Not built**: a genuine time-resolved (smoothed, moving-window) SPK-SPK correlation --
`scripts/extract_within_session_spk_spk_sliding_corr.py` exists but has never been run, is
untracked, and has no aggregation or figure step. Its LFP-LFP sibling was run once (2026-08-05)
but is equally unfinished downstream. Not added here; flagged separately.
