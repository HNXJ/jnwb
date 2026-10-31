# Preregistration: showcase 2, version 2 (all quality units, block-position covariate)

Committed before any output of the analysis below exists (`DECISIONS.md` ruling 3, 2026-10-12).
It replaces the confirmatory part of showcase 2 in `PREREGISTRATION.md`; condition labels, unit
quality criteria, area assignment, inputs, software and seeds stay as written there. Seen before
this file: the version-1 results (responsive population untestable; the post-hoc all-units run,
unadjusted, in `RESULTS_AND_LIMITATIONS.md`). Those results set no parameter below except the
choices ruling 3 names.

## Data

- Sessions: the 13 that passed inclusion; 1186358749 stays excluded (ruling 5).
- Population: every unit in `counts.npz` (all quality-passing units in the six visual areas), no
  responsiveness filter. An area enters a session with at least 20 units.
- Trials: xxxx sequences of main 2 (label 1) and of the sequenced control (label 0). Groups:
  `stimulus_block`.
- Features: spike counts per unit in four 50-ms bins, 50–250 ms after P4 (and, separately, after
  P3), as in version 1.

## Block-position covariate

Block position = the trial's `stimulus_block` number (blocks are numbered in session order).
Per session, area and onset (P3, P4), each feature column is replaced by its residual from an
ordinary least-squares fit on [1, block position] over all decoded trials (`numpy.linalg.lstsq`).
The fit uses no context label. The sequenced blocks all precede the main-2 blocks, so the
adjustment also removes the part of any context difference that a linear trend in block position
explains: what remains decodable is context signal beyond linear drift. This OLS step is the
second numpy analysis operation, beside the bootstrap; jnwb has no public residualisation
function, and `nested_cv_linear_svm` takes no covariate.

## Classifier and scores

`nested_cv_linear_svm(X_resid, labels, n_splits=5, rng=20261012, groups=block)`. Per cell (session
× area × onset): accuracy, AUC (pooled out-of-fold decision scores; chance 0.5 at any class
balance) and the majority baseline on the same folds.

## Confirmatory tests (across mice, one session per mouse)

Two-sided `exact_sign_flip` over mice; an area is tested with at least 6 mice. Mean over mice,
95 % percentile bootstrap over mice (10,000 draws, seed 20261012).

- Family A, decodability against the majority baseline: d_P4 = A_P4 − baseline_P4 and
  d_P3 = A_P3 − baseline_P3, per area. BH (`fdr_correct`) over the tested area × onset cells
  (at most 12), q < 0.05.
- Family B, deviance gain: A_P4 − A_P3, per area. BH over the tested areas (at most 6), q < 0.05.
- AUC_P4, AUC_P3 and AUC_P4 − AUC_P3 are reported per area (mean, bootstrap CI), not tested.

Reading: context is called decodable at an onset in an area only if Family A rejects there with a
positive mean. A deviance-specific gain needs Family B to reject with a positive mean.

## Exploratory

- Drift check of the covariate: main 1 vs main 2 xxxx at P4, decoded with the same adjustment
  (block position fitted over main 1 and main 2 trials), beside the unadjusted drift accuracy.
- Unadjusted all-quality-units accuracy at P4 and P3 on the same run, for comparison with the
  adjusted scores.

No within-session permutation null (version 1's block-exchange null was miscalibrated against the
majority baseline).

## Stops

A session or area whose fit returns a status other than `success` is reported and dropped from
that cell; any further choice that would change an estimand stops the analysis.
