# Omission-a: results and discussion, figure by figure

Every number below traces to a `fig0N_*_stats.csv`/`.json` receipt in that figure's own
directory (paths noted inline); nothing here is restated from memory without the file it came
from. This is a working results/discussion draft, not a manuscript section — write it into the
manuscript once fig06 has a resolution and the whole set gets a final review pass.

**RENUMBERED 2026-08-06** (see `README.md`/`FIGURE_SUMMARY.md`/`REVISION_PLAN.md`): the section
below titled "Figure 4" describes the V1/PFC condition TFR analysis, which is now **fig06**.
The old "Figure 6" section (SPK-SPK lead/lag) is now a **supplement**
(`spk_spk_coupling_supplement/`). The new fig04 (omission identity decoding, promoted from
`figS24`) has **no section here yet** — it is confirmed currently 100% synthetic (no real
analysis has been run) and must not be written up until that is fixed. Section headings below
are left as originally written (not relabeled) to avoid rewriting prose that still accurately
describes its own content under its old number; read "Figure 4" below as fig06 and "Figure 6"
below as the SPK-SPK supplement.

---

## Figure 1 — recording topology and paradigm

No inferential claim here; it's the schematic, three panels (areas, probe/hardware, block
design), and it doesn't carry a stats file for the same reason fig02 doesn't — there's nothing
to test. What it has to get right is honest geometry: the probe drawing, the area labels, the
AAAB/BBBA/RRRR grids all have to be traceable to the actual recording setup and actual condition
structure, not stylized. The whitespace/alignment pass on 2026-07-31 was exactly that kind of
correction — panel B's height was off by ~5.5pt from an arbitrary fudge constant, fixed to derive
from the real fact-block geometry instead.

**Supplements (figS01, figS02).** figS01 is the full topology panel at larger size, figS02 is
the two source vector panels the block-design grid is built from. Same status as the main
figure — descriptive, not inferential. Their only job is to survive a size reduction to a
printed page without the area labels or probe geometry becoming illegible; check that visually
before calling this figure locked, not by reading a stats file that doesn't exist.

---

## Figure 2 — exemplar rasters (S+/S-/O+/O++ x RRRR/RXRR/RRXR/RRRX)

Four columns, one unit each, picked by spec (S+ must be V1, S- must be V3a/d, O+ must be V4,
O++ must be FEF) rather than "best-looking unit anywhere" — `pick_column()` throws rather than
silently substituting an area if the required column can't be filled. n=1 per column means no
test is reported (`fig02_stats.md` says this explicitly): a raster is an existence proof that a
unit of each type looks the way the population-level claim says it should, not a population
claim itself. S+/S- here come from the legacy template-correlation classifier
(`grand_s_and_o_units.csv`); O+/O++ come from the corrected Q1 peak/trough conjunction
(`omission_grand_units.csv`). These are two different classifiers, never pooled against each
other in this figure.

The population-level version of the same question — does the omission classifier's yield exceed
chance — lives in fig03 (`fig03_questions`, below), not here. Figure 2's only real risk is a
reader mistaking "look how clean this one raster is" for a corpus-wide claim; the caption and
the stats file both have to keep saying, explicitly, that this is four named examples and
nothing else.

**Supplements.** None declared for fig02 (`Feeds supplements: none` in INVENTORY.md) — correct,
since there is no additional view of four single-unit exemplars that adds inferential content.

---

## Figure 3 — unit census (presence, functionality, peak rate, RXRR templates)

This is the population-level backbone the rest of the paper's classifier claims lean on, and it
carries real numbers now, not the retracted hardcoded ones the old staged asset had. Of 8,592
screened units (21 sessions, 3 animals): 490 (5.7%) peak or trough at the omitted slot
(`fig03_questions`, p_holm = 1.3e-59); 330 (3.8%) distinguish what was omitted (p_holm = 2.9e-13);
1,565 (18.2%) treat the post-omission stimulus differently (p_holm effectively 0); "distinguishes
when it was omitted" does not survive correction (p_holm = 0.32) — the one Q-family question
that comes back null, and it's reported as null, not dropped.

Area predicts responsiveness, but the effect is small (Cramer's V = 0.055, chi2 p_holm = 0.0056)
— real, not a strong organizing variable on its own. Area predicts S/O composition and layer
composition much more strongly (V = 0.199 and V = 0.287, both p ≈ 0), and omission effect size
differs sharply across the S+/S-/O+/Null functional groups (Kruskal-Wallis H = 309.8,
p ≈ 8e-66) and again across the five RXRR-pooled classes (H = 258.1, p ≈ 1e-54) — the
functional-group split this whole project's later figures use (fig07 included) is doing real
work, not just relabeling noise. Waveform type does not predict responsiveness (odds ratio ≈
0.92, p_holm = 0.73) and overall firing rate barely correlates with omission effect size
(r² < 0.001, p = 0.37) — two negative controls that came back appropriately negative.

**Supplements (figS03, figS04, figS20, figS21).** figS03/figS04 are the same panels reorganized
by question and re-rendered at print size — no new numbers, just readability. figS20 adds the
presence/layer/correlation panels and the full RXRR template traces at full width (figS21);
these exist because the main figure's grid can't fit every panel at a legible size, not because
they carry a separate inferential claim. Read them as "the main figure's own numbers, easier to
see," not as independent results.

---

## Figure 4 — V1/V3a-d/TEO/PFC time-frequency, RXRR vs RRRR

Main comparison: band power at the omitted (RXRR) vs. real (RRRR) p2 slot, four areas x five
bands, paired across sessions. Every uncorrected p worth noting is small-to-moderate (e.g. V1
low-gamma dz = 1.37, p = 0.0034; PFC alpha dz = 0.93, p = 0.0041) but **0/20 survive
Holm-Bonferroni** once the full area x band family is corrected together
(`fig04_condition_stats.csv`, min p_holm ≈ 0.068). This is the corpus's now-documented pattern:
real, large within-session/within-animal effects that don't survive correction once pooled
naively across sessions — the same failure mode that drove the fig05/06/07 methodological pivot
this week (pool-after-testing, not before). The laminar splits (superficial vs. deep, V1/V4,
MT/FEF, TEO/PFC) are flatly null across all ten tests checked (p_holm = 1.0 throughout) — worth
stating plainly rather than hedging, since a laminar claim on this data would be unsupported.

The honest read: this figure documents a real phenomenon (the omission slot's LFP looks
different from the matched real-stimulus slot, in every animal, often by more than a full SD)
that this project's classical per-session-paired-test framework cannot certify at the group
level. That's exactly why fig05 exists as a follow-up with a different statistical backbone
(GLMM) rather than a fifth area added to this same test family.

**Supplements (17 total: figS05-16, figS25-29).** These split the same RXRR/RRRR comparison out
by area pair (figS05-09), assemble the full ten-area grid (figS10), add the laminar splits for
three more area pairs (figS11-13), regroup by early/mid/frontal hierarchy tier (figS14-16), and
add six-area spectrograms/traces for both conditions plus the slot-pooled omission-vs-stimulus
comparison (figS25-29). None of these change the headline (still null after correction); they
exist so a reader can check any specific area or layer split without re-deriving it, and so the
main figure doesn't have to carry ten areas at once.

---

## Figure 5 — LFP band-power hierarchy vs V1 (subject-controlled GLMM)

This is the figure that forced the week's methodological pivot. Three connectivity methods —
imaginary coherency, directed Granger causality, transfer entropy — were tried first and all
came back null at the group level (0/240, 0/150, 0/150 respectively; preserved, not deleted, in
`lfp_lfp_connectivity_supplement/`). Per this project's own rule that figures 4-7 need a
group-level significant result, fig05 pivoted to a different question entirely: not "are two
areas coupled" but "does band power differ from V1, area by area, holding subject constant."

That question has an answer: a subject-controlled GLMM (MixedLM/REML, session random intercept,
subject as an additive fixed effect, all 23 sessions) finds **FEF and PFC low-gamma elevated
relative to V1** and survives Holm-Bonferroni (p_holm = 0.0076 and 0.0088 respectively,
+0.57 dB and +0.53 dB). (Headline layout revised 2026-08-06 to 5 subpanels, one per band,
area-vs-V1 bars with SE — same 45-cell family and numbers, the single combined heatmap moved to
the supplement below.) **Extended 2026-08-06** with two more rows, vs V4 and vs PFC, from the
same pairwise-contrast fit already used for the pairwise supplement (not a refit): vs V4, V1 and
V2 sit lowest in beta/low-gamma (V1 -1.0 dB, V2 -1.2 dB low-gamma relative to V4) while frontal
areas (FST, FEF) sit highest in theta/alpha; vs PFC, essentially everything is negative in
theta/alpha/low-gamma (PFC sits at or near the top of the hierarchy in those bands), consistent
with — not independent of — the vs-V1 row's own frontal elevation. These two rows are read
through the 225-test pairwise family's own correction, not the V1 row's dedicated 45-test
family, so their color-coding answers a related but distinct question (is this particular pair
different, among all 45 pairs) from the V1 row's (is this area different from V1 specifically). Eleven of the 45 area x band cells survive the more permissive BH-FDR
threshold, adding alpha (FEF, MT, PFC), beta (V3a/d), low-gamma (MT, TEO, V3a/d, V4) and
high-gamma (FEF) to the picture — a broader, gamma/alpha-leaning frontal-and-mid-level elevation
above V1, with low-gamma the only band where two cells clear the stricter FWER bar. Two real
bugs in the GLMM script were caught and fixed before trusting these numbers (see that
directory's README) — worth remembering when citing this figure, since every `glmm_summary.csv`
row written before that fix is wrong, not just the row that surfaced it.

**Supplements.** The three null connectivity methods (`lfp_lfp_connectivity_supplement/`) stay
attached as the honest record of what was tried and ruled out before the GLMM pivot — a reader
should be able to see that the directed-connectivity route was tried and failed, not just that
it was skipped. figS31-33 carry the full pairwise area x area contrast matrix (both windows) and
the stimulus-window replicate of the main GLMM — the stimulus-window version doesn't change the
qualitative story (still frontal/mid-level elevated over V1, not evenly spread), which is itself
worth stating since it means the effect isn't an omission-specific artifact. The retired
band-power-hierarchy figure (`band_power_hierarchy_supplement/`, the pre-2026-08-04 fig05) is
kept as a supplement for the same reason as the connectivity methods: it was a real analysis
that didn't clear the significance bar, not a mistake to erase.

---

## Figure 6 — SPK-SPK lead/lag correlation (headline), directed Granger (supplement)

**Redesigned 2026-08-06.** The Granger causality attempt (same engine as fig05, nine area pairs,
RXRR/RRRR/delta) was fully null — 0/27 cells survive correction, min p_holm ≈ 0.32 at RXRR's
MT<->TEO cell — and unlike fig05, no alternative area-level question rescued it. Per direction
to keep Granger for LFP-LFP only and move to sliding correlation for SPK-SPK, the headline is
now a trial-matched lead/lag correlation between (area, functional_type) population-rate nodes:
node A's window held fixed, node B's slid across ±100ms of lag, against the same trial-mismatch
shuffle null validated for the LFP-LFP sliding-window work.

The corrected family here is large — 12,033 cells (scope × node-pair × lag × condition-group,
all with ≥3 sessions) — because 21 lags are tested per pair; that family size was declared
before looking at results, specifically to avoid the obvious trap of taking each pair's best lag
post-hoc (which alone would flag 76-84% of pairs as "significant" by chance). **4/12,033 survive
Holm-Bonferroni, 35/12,033 survive BH-FDR.** The honest reading of *where* those survivors sit
matters more than the count: all 4 Holm survivors and most BH survivors cluster at lag 0 or
within ±30ms — there is no corrected evidence of an actual lead/lag delay anywhere in this
corpus. What's real is near-simultaneous population coupling in a small number of specific
pairs — V4 Null vs S-, V4 S+ vs S-, FEF Null vs S- — all within-area, with small session counts
(3-7 of up to 17) behind each. This is a second, independent method (after Granger) converging
on "no strong SPK-SPK connectivity signal on this corpus," which is itself worth noting rather
than treating the two null-ish results as unrelated.

**Supplement: directed Granger.** Retained as `fig06_supp_granger.svg` (three panels: RXRR,
RRRR, and the RRRR-minus-RXRR delta added 2026-08-06) — the originally-planned method this
headline replaces, kept for completeness, not because it found anything.

---

## Figure 7 — population firing rate x LFP band power (headline), spike-LFP PPC (supplement)

Redesigned 2026-08-05, same day as fig05/06's connectivity work, but resolved differently: this
headline is population-pooled (mean per-unit rate across a functional group's qualifying units
in an area), not per-unit or per-channel, and it is trial-matched within session before any
cross-session pooling — exactly the corrected design this week's other methods converged on.
Across 20 sessions, area x band x functional-group (S+/S-/O+/Null) x condition-group
(baseline/stim/omission) — 480 testable cells with 3+ sessions — **19 survive Holm-Bonferroni,
142 survive BH-FDR** at the hit-rate stage alone, before any model is fit.

The GLMM built on top of that (same backbone as fig05) sharpens the story considerably. Band is
the dominant factor: high-gamma and low-gamma sit far above theta/alpha/beta (every pairwise
contrast against them clears Holm at p < 1e-5), so whatever this coupling is, it's concentrated
in the gamma range and not a general property of LFP power. Functional group matters in a
direction I did not expect going in: **O+ units are less coupled to band power than either Null
or S+ units** (both contrasts Holm p < 2e-5), not more — an omission-responsive unit's
population rate tracks ongoing LFP state more loosely than an unclassified or stimulus-responsive
unit's does, the opposite of a "omission cells are more state-dependent" prior. Area separates
MT/MST from FEF/PFC/TEO (all Holm-significant), a different split than fig05's V1-vs-frontal
pattern. And condition group has no detectable effect at all (p > 0.4 uncorrected on both
comparisons) — this coupling is a property of ongoing activity, present just as much at baseline
as during the stimulus or omission window, not something the omission manipulation switches on.

**Supplement: PPC.** The originally-planned per-unit method (pairwise phase consistency between
each SUA's spikes and its own area's LFP phase) is retained as `svg/fig07_supp_ppc.svg`, kept
because it's the method this headline replaces, not because it found anything: 0/60 in both the
omission and stimulus windows, and the A/B/R stimulus-identity extension is 0/25 as well (min
p_holm = 1.0). Same pattern as fig06 — real per-unit/per-session effects exist (one MT unit hit
z > 88 against its own shuffle null in a pilot session) but do not survive correction once
pooled the naive way. The population-level headline above is, in effect, the successful
replacement for this exact failure mode.
