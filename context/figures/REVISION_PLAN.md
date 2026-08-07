Version: 2026-08-06
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
| 4 | Omission identity decoding | 70/100 | new promoted result, details to discuss | **entire figure is currently synthetic — see below** |
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

- **Figure 4 — fix the synthetic-data problem before anything else.** Confirmed 2026-08-06: none
  of `omission_identity_decoding_master.csv`, `omission_identity_timecourse_master.csv`,
  `omission_identity_glmm_coefficients.csv` exist. `scripts/compute_omission_identity_encoding.py`
  has never been run to completion on this corpus. Until it is, Panels B/C/D render fallback
  numbers and Panels A/E1/E2 render hardcoded arrays — none of it is real. This blocks any
  "details to discuss" conversation about the figure's actual finding, because there is no
  finding yet. Sequenced first regardless of the 7→6→5→4→3→1→2 score order, since it gates
  whether fig04 can be discussed at all.
- **Figure 4 — resolve the "GLMM" mislabel** once real data exists: either fit an actual mixed
  model (session/subject random effects) for the spatial-hierarchy panel, or rename every
  artifact (`omission_identity_glmm_coefficients.csv`, the column, the panel title) to describe
  what it actually is (an L2-regularized logistic regression).
- **Figure 4 — add a stats receipt** (`figstats.write()`) once real data exists, matching every
  other main figure's convention.

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
