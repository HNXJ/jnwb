# Figure 5 — LFP band-power hierarchy vs V1 / V4 / PFC, subject-controlled GLMM

**Built 2026-08-05, after three LFP-LFP connectivity methods (imaginary coherency, directed
Granger causality, transfer entropy) all came back null at the group level** — see
`../lfp_lfp_connectivity_supplement/README.md` for that full record, preserved as a supplement,
not discarded. Per `feedback_figures_require_significance` (figures 4-7 must carry a
group-level significant result), fig05 pivoted to this area×band contrast instead.

**Extended 2026-08-06** to three reference-area rows (vs V1, vs V4, vs PFC) x 5 band columns,
per request. The V1 row is unchanged — Model F's own dedicated 45-test family. The V4 and PFC
rows are NOT a refit: they're the same pairwise-contrast Model F fit (`F_pairwise_area_contrasts`,
already used for the `fig05_supp_pairwise*` supplements), read through the sign convention
`area - ref_area` and colored by that same 225-test pairwise family's own Holm/BH correction —
a genuinely different declared family from the V1 row's 45-test one, not conflated with it (see
`fig05_v1_area_hierarchy_glmm.py`'s `draw_multi_ref_band_panels` docstring). Sign consistency
was checked directly: e.g. PFC's vs-V1 low-gamma estimate (+0.53 dB) and V1's vs-PFC low-gamma
estimate (-0.53 dB) match exactly, as they must by construction.

## New supplement (2026-08-06): Models A-E, one figure each

`fig05_supp_models_AE.py` draws each of Models A-E from `fit_omission_band_power_glmm.py`
(see that script's own docstring for the full model definitions) as its own standalone
figure, same visual style as the main figure (one bar-chart subpanel per band, dark
orange/light orange/gray for Holm/BH/neither), each with its OWN declared correction family
(never pooled across models or with Model F's own family):

- **Model A** (corpus-wide, all areas/subjects pooled): 1/5 Holm, 1/5 BH-FDR.
- **Model B** (per subject): **9/15 Holm** — reproduces the already-documented finding
  directly: C31o falls in every band (all Holm-significant, negative), V182o rises in every
  band (4/5 Holm-significant, positive), V198o is mixed and mostly not significant.
- **Model C** (area vs V1, descriptive, confounded with subject): 5/45 Holm, 16/45 BH-FDR —
  broader, less controlled elevation than Model F's subject-controlled result, as expected
  since this is exactly the comparison Model F was built to improve on.
- **Model D** (V3a/d vs V1/V2, within V198o only): 0/5 Holm, 0/5 BH-FDR — null, consistent
  with this design supporting only one subject and 5 sessions.
- **Model E** (laminar, channel-level): 7/10 Holm, 7/10 BH-FDR.

Output: `svg/fig05_supp_modelA.svg/.png` through `fig05_supp_modelE.svg/.png`, each with its
own `svg/fig05_supp_model{A-E}_stats.md/.csv`.

## The two bugs that had to be found and fixed first

Before building anything, `CLAUDE.md`'s claim ("V3a/d beta replicated at +1.11 dB on both the
17- and 23-session corpora") was checked against the actual analysis outputs rather than
trusted from memory, per this project's own "no assertion without receipt" rule. It didn't
match either existing number: `CONTEXT.md`'s descriptive area model reports +1.78 dB
(confounded with animal, stated explicitly there), and the one animal-controlled test in the
existing pipeline (a single V3-vs-V1/V2 probe pair, 5 sessions, one subject) reported
+1.59 dB at P=0.076 — not significant.

Investigating why turned up two real bugs in `scripts/fit_omission_band_power_glmm.py`, both
now fixed (full receipt: `artifacts/.lab/v3ad_beta_glmm_two_bugs_fixed_20260805.json`):

1. **Area-pooling bug**: the script's local `area_infer` dict was `{"V3d": "V3a/d", "V3a":
   "V3a/d"}` — missing the raw `"V3"` label itself (C31o's 5 unsplit sessions), silently
   excluding them from the pooled `V3a/d` group and limiting the animal-controlled contrast to
   one subject (V198o) when it didn't need to be. `context/figures/figstyle.py`'s own
   `AREA_POOL` already had this right; this script had independently reinvented an incomplete
   version.
2. **Benjamini-Hochberg bug**: the script's local `bh()` function divided by an inverted rank
   order (`np.arange(n, 0, -1)` instead of `np.arange(1, n+1)`), so the smallest p-value in any
   family received *no correction at all* rather than the largest multiplier it should have.
   Confirmed against `figstats.py`'s independently-implemented `bh()` (used by every
   `fig0N_*.py` script this session, confirmed correct) and by hand-deriving the correct BH
   values for the family that surfaced this. **Every `q_bh` value this script wrote before this
   fix is wrong**, not just the one that surfaced it.

## Model

**Model F** (new, added alongside the existing Models A-E in
`scripts/fit_omission_band_power_glmm.py`): `db ~ C(area, Treatment('V1')) + C(subject)`,
session-level (one row per session×area, avoiding channel-level pseudo-replication), **all 23
sessions, all 3 subjects** — not the 5-session/1-subject subset Model D is stuck with by the
recording design (C31o and V182o never recorded V3a/d and V1/V2 on separate probes in the same
session). Subject is an explicit additive fixed effect. Identifiable because the area×subject
design is connected (every area recorded in ≥2 subjects; V4 alone spans all three) — per
`CLAUDE.md`'s own verification doctrine, already established for this exact corpus.

Fit via MixedLM (REML, session random intercept) where it converges (low_gamma, high_gamma);
falls back to OLS with session-cluster-robust SEs where MixedLM hits a singular matrix (theta,
alpha, beta — the between-session variance component becomes non-identifiable once area+subject
already absorb most of the structure for those bands). Which estimator produced each row is
recorded, not hidden (`estimator` column).

## Statistics

All 9 areas × 5 bands = 45 tests are **one declared family**, corrected together via
`figstats.correct()` — not the per-area-across-5-bands correction the source script's own
`glmm_summary.csv` applies for its own bookkeeping (a different, narrower family that isn't
this figure's declared one).

## Result, stated plainly

**2/45 survive Holm-Bonferroni**: FEF low-gamma (p_holm=0.0076) and PFC low-gamma
(p_holm=0.0088) — the strongest, most defensible claim, family-wise error rate controlled.
**11/45 survive Benjamini-Hochberg FDR**, including V3a/d beta (q_BH=0.030) and V3a/d low-gamma
(q_BH=0.030) — reported as FDR-level evidence (expected proportion of false discoveries among
rejections), a weaker guarantee than the two Holm survivors, never folded into the same claim.
Solid outline = Holm-significant; dashed outline = BH-significant only.

## Supplement: full area x area pairwise matrix (2026-08-05)

The main figure only shows each area's contrast against V1 (the reference level, chosen for
readability). Every OTHER pairwise difference (e.g. FEF vs PFC) is recoverable from the SAME
Model F fit as a linear contrast of its coefficients — `scripts/area_subject_glmm.py`'s
`fit_area_subject_and_pairwise()` computes all C(10,2)=45 area pairs per band from one fit,
not 45 separate refits. Declared as its own family (225 tests: 45 pairs x 5 bands) since "which
area pairs differ" is a different question from the main figure's "which areas differ from V1"
— **8/225 survive Holm-Bonferroni, 34/225 survive BH-FDR**. `svg/fig05_supp_pairwise_
omission.svg/.png`, `svg/fig05_supp_pairwise_stats.md/.csv`.

**Bug found and fixed while building this**: the pairwise contrast vector was constructed
backwards relative to its own term label (`"B - A"` labeled but actually computing `A - B`) —
caught by a sign sanity check against Model F's own vs-V1 coefficients (a pairwise contrast
against the reference area should exactly reproduce that area's Model F coefficient; it didn't,
until this was fixed). Fixed in `scripts/area_subject_glmm.py`; the fig05 main figure's own
numbers were never affected (they don't use the pairwise contrast path).

## Supplement: stimulus-window counterpart (2026-08-05)

Matched design, same Model F, same estimator choices, fit on a new real-stimulus census
(`scripts/compute_stim_channel_band_power_census.py` — RRRR/AAAB/BBBA at slots 2/3/4, same
measure/window/baseline convention as the omission side) via
`scripts/fit_stim_band_power_glmm.py`.

**vs-V1 (45-cell family): NULL.** 0/45 Holm, 0/45 BH-FDR — despite some visually large point
estimates (e.g. PFC low-gamma −3.5 dB, MST low-gamma +3.3 dB), none survive correction (raw
p's of 0.008–0.05, wide CIs). This is itself informative: **the area hierarchy that survives
correction during omission does not survive correction for a real stimulus**, at least not
relative to V1 specifically — the omission-linked effect looks more specific than a generic
baseline area difference that would show up regardless of condition.

**Full pairwise (225-cell family): significant.** 30/225 Holm, 55/225 BH-FDR — areas differ
strongly from *each other* in the stimulus window (e.g. FEF vs MT beta p_holm=1.5e-11, FST vs
PFC beta p_holm=7e-10, MST vs PFC/TEO low-gamma p_holm≈1e-8), just not specifically relative to
V1. MST stands out as an outlier from most other areas in low/high-gamma. A real, well-powered,
structured effect (n=23 sessions, tiny p-values) — reported here as a supplement finding since
it answers a different question ("do areas differ from each other in general") than the main
figure's ("does the omission-linked hierarchy hold").

`svg/fig05_supp_area_band_heatmap_stim.svg/.png`, `svg/fig05_supp_pairwise_stim.svg/.png`,
`svg/fig05_supp_stim_stats.md/.csv`, `svg/fig05_supp_pairwise_stim_stats.md/.csv`.

## Output

`fig05_v1_area_hierarchy_glmm.py` reads `outputs/lfp_band_census_v2/glmm_summary.csv` (omission,
main figure) and `outputs/lfp_band_census_stim/glmm_summary.csv` (stimulus, supplement) —
both Model F and `F_pairwise_area_contrasts` rows — draws `svg/fig05_area_band_heatmap.svg/.png`
(main), `svg/fig05_supp_pairwise_omission.svg/.png`, `svg/fig05_supp_area_band_heatmap_stim.
svg/.png`, and `svg/fig05_supp_pairwise_stim.svg/.png` (supplements), assembles `fig05.svg`,
writes all four stats files via `figstats.write()`.
