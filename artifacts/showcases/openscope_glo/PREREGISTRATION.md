# Preregistration: showcases 1 and 2 (DANDI 000253, mouse units)

Committed before any spike time is analysed. The LFP clock check (Gate B question 2, commit
`786f877`, one session's probe-1 LFP) came before this file; none of its values set a
pre-registered parameter. One numeric coincidence exists: the 0.25 in the main xxxx share bound
(validation, item 4 below) equals `vep_new_axis.mean_uV[79]` (0.25 µV at −36.8 ms) in
`receipts/lfp_clock_check_sub-649323.json`, a fraction against a voltage; the bound is the 20 %
design share ± 0.05. (Correction 2026-10-12, `DECISIONS.md` ruling 1.) Gate B passed 2026-10-12 with
every recommended option (`SHOWCASE_PLAN.md`, "Questions for Hamm at Gate B"; Hamm: "let's do as
much as possible"). This file fixes the confirmatory estimands, windows, thresholds, tests and
multiplicity. Anything not listed under **Confirmatory** is exploratory.

## Inputs and software

- 14 `_ogen.nwb` assets of 000253 at 0.240503.0152, asset ids and SHA-256 in
  `receipts/download_000253_ogen.jsonl` (all 14 match DANDI's digest; identical asset ids in
  0.240923.1441).
- jnwb imported from the checkout `C:/workspace/jnwb` (branch `dev`), never the copy in
  site-packages; every result records `jnwb.__file__` and the checkout's commit.
- Study code calls jnwb public functions (`jnwb.__all__`) for every analysis operation; numpy,
  pandas and h5py only for reading and reshaping, and numpy for the percentile bootstrap of a
  mean, which jnwb has no function for.

## Condition labels (per session, from `intervals/init_grating_presentations`)

1. Sequences: consecutive grating rows with finite orientation, split at NaN-orientation rows; a
   sequence is kept only if it has 4 rows, all in one `stimulus_block`, with onset steps of
   0.9–1.1 s.
2. x = the orientation of P1–P3 in the first block (habituation); y = the other orientation.
   Patterns are written in x/y.
3. Contexts, in session order, matched to the stimulus code (`ephysrecording-FINAL.py`):
   habituation = the first block; main 1 = the following blocks holding only xxxx and xxxy;
   randomized control = the following run of blocks holding other patterns; sequenced control =
   the following run of blocks holding only xxxx and yyyy; main 2 = the remaining blocks holding
   only xxxx and xxxy. A session whose blocks do not split into these five runs, in this order,
   is reported and excluded.
4. Validation per session: main xxxx share in [0.15, 0.25]; randomized control holds at least 8
   distinct patterns; sequenced control xxxx share in [0.45, 0.55]. A failing session is excluded
   and reported.
5. Exclusions: habituation; any grating row overlapping a
   `create_receptive_field_mapping_presentations` row or an `invalid_times` interval of nonzero
   span.
6. P*k* onset = `start_time` of the *k*-th row of the sequence (session clock, s).
7. Clock check: each grating `start_time` against the nearest `processing/stimulus/timestamps`
   value; a session whose median absolute difference exceeds 10 ms stops the analysis.

## Units

- `quality == "good"`, `presence_ratio > 0.95`, `isi_violations < 0.33`,
  `amplitude_cutoff < 0.1`, `firing_rate > 0.1` (via `filter_by_criteria`).
- Area: the `location` of the unit's `peak_channel_id` in the electrodes table, matched to
  `^(VISpm|VISp|VISl|VISrl|VISal|VISam)` followed by a digit or the end of the label.
- Visually responsive: `compute_response_metrics` on P1 onsets of habituation and main-1
  sequences, baseline −250 to 0 ms, response 50–250 ms; `classify_response_significance`
  with its defaults (|z| ≥ 1.96 and p < 0.05). These trials are P1 epochs only; no test below uses
  P1.

## Confirmatory estimands

### Showcase 1: the identical sequence in three contexts

- Per unit and context c: Δ_c = mean over sequences of [rate(P4, 50–250 ms) − rate(P3,
  50–250 ms)], rates by `rate_in_window` (Hz).
- Main = main 1 ∪ main 2. Four contrasts, per unit:
  C1 = Δ_main(xxxx) − Δ_random(xxxx); C2 = Δ_main(xxxx) − Δ_seq(xxxx);
  C3 = Δ_random(xxxx) − Δ_seq(xxxx); C4 = Δ_random(yyyy) − Δ_seq(yyyy).
- Per mouse and area: the median of the contrast over included units; the mouse enters an area
  when it has at least 5 included units there.
- Test: `exact_sign_flip` over mice, two-sided; an area is tested when at least 6 mice enter
  (the smallest n with a two-sided floor below 0.05). Effect = mean over mice, interval =
  2.5th–97.5th percentile of the mouse-level bootstrap of that mean (10,000 draws, seed 20261012).
- Multiplicity: Benjamini–Hochberg (`fdr_correct`) over all tested area × contrast cells (at most
  24), q < 0.05.
- Drift bound: D = Δ_main1(xxxx) − Δ_main2(xxxx), same per-mouse median. A significant C1 or C2
  in an area is called *identified* only if |mean C| > |mean D| in that area; otherwise *not
  identified from drift*.

### Showcase 2: decoding context from identical input

- Trials: xxxx sequences of main 2 and of the sequenced control. Labels: context. Groups:
  `stimulus_block`.
- Features: spike counts per included unit in four 50-ms bins, 50–250 ms after P4 (and, for
  the baseline, after P3), from `bin_spikes`.
- Areas per session with at least 20 included units.
- Classifier: `nested_cv_linear_svm(X, labels, n_splits=5, rng=seed, groups=block)`
  (StandardScaler inside the pipeline, grouped outer and inner folds). Score = outer-fold
  accuracy; `majority_baseline_accuracy` reported beside it.
- Estimand per session and area: A_P4 − A_P3. Per mouse = that session (one per mouse).
- Test: `exact_sign_flip` over mice, two-sided, an area tested when at least 6 mice enter;
  BH over the tested areas (at most 6), q < 0.05.
- Within-session null (reported, not the confirmatory test): context labels exchanged between
  whole blocks (block labels permuted with `permute_labels(scheme="global")` over blocks, then
  expanded to trials), 1,000 draws for P4 and for P3; p = (1 + k)/(1 + 1000).
  `build_permutation_plan` is not used: its within-group scheme cannot move a block-constant
  label.
- Seeds: decoding `rng = 20261012`; permutation draw *i* uses seed 20261012 + *i*.

## Exploratory (labelled as such everywhere)

- Showcase 1: history-matched variant (main xxxx preceded by xxxy); state control (running speed,
  −1 to 0 s before P4, trials outside the range shared by all contexts dropped); per-unit
  prevalence of C2 with `clopper_pearson` intervals; population PSTH and
  `fit_exponential_onset`; time-resolved C2 by `cluster_permutation_test` (paired, over mice).
- Showcase 2: drift decoding (main 1 vs main 2, xxxx, P4); gain-removed features (trial mean
  subtracted); unit-shuffled features (unit order permuted per trial); time-resolved accuracy
  in 50-ms bins 0–500 ms without a null; `rdm` geometry.

## Stops

A condition label not derivable as above in fewer than 10 sessions; a clock disagreement above
10 ms; fewer than 10 sessions passing inclusion; any decision outside this file that changes an
estimand.
