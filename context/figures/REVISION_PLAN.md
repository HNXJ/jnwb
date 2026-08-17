Version: 2026-08-09
Status: canonical revision plan — supersedes ad-hoc figure-by-figure requests until amended
Truth status: `truth_safe_unverified`

# Omission-a: revision plan

Set 2026-08-06, to be followed strictly until explicitly revised. Scores are 0-100, assigned by
the user, not derived — this file records them and sequences the work they imply. A score is
not a grade on quality of past work; it is a statement of how much is left before the figure can
lock.

## Score table

| # | Figure | Score | Meaning | Blocking issue |
|---|---|---|---|---|
| 2 | Spiking exemplar rasters | 100/100 | final | none |
| 1 | Recording topology and paradigm | 90/100 | semi-final | none stated |
| 3 | Unit census | 80/100 | revision on subplots needed | which subplots, not yet specified |
| 4 | Omission identity decoding | 70/100 | new promoted result, details to discuss | **current renderer is invalid: real `_v2` tables exist, but random-CV is confounded and hardcoded panels remain — see below** |
| 5 | LFP band-power hierarchy GLMM | 60/100 | minor revision on subplots needed | which subplots, not yet specified |
| 6 | V1/PFC condition TFR | 50/100 | moderate revision on subplots needed | which subplots, not yet specified; lock is stale regardless |
| 7 | Population firing x LFP power | 10/100 | major revision | not yet specified |

Ordered by score ascending (least-ready first) — the sequence this plan follows:
**7 → 6 → 5 → 4 → 3 → 1 → 2.**

## Rule for this plan

1. **No figure is touched out of order** unless a blocking dependency forces it (e.g. fig04's
   synthetic-data problem must be fixed regardless of queue position, since "70/100, details to
   be discussed" cannot be discussed against fake numbers).
2. **Every revision item needs a stated subplot/target before work starts.** Four of the seven
   scores above currently say "revision needed" with no named subplot — that is not yet
   actionable. The next step for each of fig03, fig05, fig06, fig07 is a scoping conversation
   (which subplot, what's wrong with it), not code.
3. **A score only moves up with a receipt** — a re-run, a fixed panel, a stats file — never by
   re-stating intent. This file gets an entry in its changelog (below) every time a score
   changes, naming what closed it.
4. **No figure is re-locked (`fig0N_finalized.*` regenerated) until its score is agreed at
   ≥90** and the user has visually confirmed the re-rendered panels, per the existing
   "falsifier for figure done" rule in `README.md`.

## Immediate, unblocked work (does not need scoping input)

- **Figure 4 — replace the invalid decoding evidence chain before anything else.** The 2026-08-08
  audit corrected the earlier diagnosis: the three real `_v2` source tables do exist. However,
  simply wiring them into the renderer would still be scientifically invalid. Their random-CV
  mean accuracy (~0.601) is confounded by sequence/cycle structure, while the leave-one-cycle-out
  mean-centered deconfound is approximately chance (~0.495). Panels A/E1/E2 also retain hardcoded
  arrays, and the available permutation-null output is only a one-session, `n_perm=5` smoke run.
  Rerun after the p4 label fix with grouped/cycle-safe CV, corpus-scale permutation nulls, and
  provenance; then regenerate every panel from real tables. A null result is an acceptable
  scientific outcome and must not be replaced by the old frontal-gradient placeholder story.
- **Figure 4 — resolve the "GLMM" mislabel** after the deconfounded rerun: either fit an actual mixed
  model (session/subject random effects) for the spatial-hierarchy panel, or rename every
  artifact (`omission_identity_glmm_coefficients.csv`, the column, the panel title) to describe
  what it actually is (an L2-regularized logistic regression).
- **Figure 4 — add a stats receipt** (`figstats.write()`) after the deconfounded rerun, matching every
  other main figure's convention and recording CV grouping, permutation count, seed, corpus, and p4-label provenance.

## Scoping needed before code starts (figures 3, 5, 6, 7)

Each of these needs one short answer before any subplot work begins — batching into a single
round rather than trickling:
- **Fig07 (10/100, major revision)**: which panel(s) are wrong, and is it the headline
  (population firing x band power GLMM) or the layout/visual presentation?
- **Fig06 (50/100, moderate revision)**: which of the TFR figure's subplots need revision —
  the spectrogram block, the trace block, the GLMM section, or the stale-lock re-review itself?
- **Fig05 (60/100, minor revision)**: which subplot(s) — the 3-row (V1/V4/PFC) headline, the
  Models A-E supplement, or the pairwise/stim supplements?
- **Fig03 (80/100, revision on subplots needed)**: which subplot(s) — likely candidates given
  recent history are the new UMAP embedding panel's placement/sizing, or the composition panels,
  but not yet confirmed.

## Changelog

- 2026-08-06: Plan created. Figures renumbered (fig04↔identity-decoding promoted,
  old fig04→fig06, old fig06→supplement). Scores recorded as given. Fig04's synthetic-data
  problem confirmed and flagged as the sole immediate blocking item.

- 2026-08-09: Integrated the 2026-08-08 Figure 4 audit. Corrected the stale claim that source CSVs
  were absent: `_v2` tables exist, but random-CV is confounded; cycle-deconfounded accuracy is
  approximately chance, hardcoded panels remain, and the permutation null is only a smoke run.
  Added explicit deconfounded-rerun acceptance criteria.

- 2026-08-11: Fig03 closure pass (not a re-lock). Fixed two bugs that were silently blocking the
  script from running at all under the current data layout (stale D:/workspace/omission paths;
  a missing umap-learn dependency that failed the whole pipeline at the last, non-essential
  panel). Re-ran to completion; verified every panel prints its own denominator and every set of
  per-area/per-class N's sums exactly to its documented population (2,921 legacy-screened main
  figure; 8,592 grand-table supplement); confirmed FIGURE_SUMMARY.md's caption numbers still
  match exactly; documented the upstream trial-minimum contract (MIN_TR=6 for the O-family
  classifier) in the fig03 README. No discrepancy found. Per rule 4, re-lock still requires the
  user's own visual confirmation of context/figures/fig03_unit_census/fig03.svg -- this pass did
  not regenerate fig03_finalized.*. Receipt: artifacts/.lab/fig03-closure-verification-20260811.json.

- 2026-08-09/10: Applied the evidence-architecture patch and added a separate leakage-safe
  SPK/SUA decoder plus fail-closed renderer. Three-session validation passed with persisted
  folds, held-out predictions, and within-cycle null draws; the complete eligible-corpus run
  and production render remain pending.

- 2026-08-11: Corpus-size change (21->22 sessions, sub-V198o_ses-230629_rec added by explicit
  user decision) re-verified against fig03's re-render. Main-figure (legacy-screened) denominator
  confirmed unchanged at 2,921; supplement denominators confirmed at 8,702/9,056 evaluable
  (up from 8,592-based), with all per-area/per-class counts summing exactly. No other panel
  drift. Receipt: artifacts/.lab/fig03-corpus-22-sessions-20260811.json (falsifier now CLOSED).
  As with the 2026-08-11 closure pass, re-lock still requires the user's own visual confirmation
  per rule 4 -- fig03_finalized.* was not regenerated.
