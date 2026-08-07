# Figure 4 — Omission identity decoding & spatial "GLMM" encoding

**Promoted 2026-08-06** from `context/figures/supplements/figS24_omission_identity_decoding`
(authored 2026-08-02, originally by a different agent — see below) into the fig04 main-figure
slot, replacing the old fig04 (V1/PFC condition TFR, renumbered to `../fig06_v1_pfc_condition_tfr/`).
Flagged at **70/100 — new promoted result, details to be discussed** (see `../REVISION_PLAN.md`).
This promotion is a relocation only; no analysis was re-run or re-verified as part of the move.

## What this figure claims

Cross-validated classification of "what was omitted?" (AXAB vs. BXBA vs. RXRR) from
noise-controlled population spiking, across time (Panel B), sequence slot P2/P3/P4 (Panel C),
and area (Panel D), plus a confusion matrix and ROC curves (Panels E1/E2).

## Source code

- `scripts/compute_omission_identity_encoding.py` — produces the three CSVs this figure reads
  (`outputs/classification/omission_identity_decoding_master.csv`,
  `omission_identity_timecourse_master.csv`, `omission_identity_glmm_coefficients.csv`).
- `jnwb/omission_identity.py` — the actual decoding engine (`decode_omission_identity_slot`):
  `build_noise_controlled_spike_matrix()` balances trial counts per class, then
  `StratifiedKFold(n_splits=5)` + `Pipeline([StandardScaler(), SVC(kernel="linear", C=1.0)])`,
  accuracy/F1/AUC with a 100-permutation-null p-value. **Docstring credits authorship to
  "Google DeepMind Antigravity Agent, Date: 2026-08-02"** — written by a different agent, at an
  earlier point in this project's history, not produced in a Claude Code session.
- `fig04_omission_identity_decoding.py` (this directory) — the plotting script, reads the three
  CSVs above for Panels B/C/D.

## Known, unresolved issues (flagged 2026-08-06 at promotion time, none fixed yet)

**0. CONFIRMED: this entire figure is currently synthetic, not analysis output.** Checked at
promotion time — none of the three source CSVs exist on disk:
`outputs/classification/omission_identity_decoding_master.csv`,
`omission_identity_timecourse_master.csv`, `omission_identity_glmm_coefficients.csv` are all
absent. That means Panels B, C, and D — not just A/E1/E2 below — are currently rendering from
the plotting script's own hardcoded fallback branches (a Gaussian-bump timecourse, a literal
`slot_summary` benchmark dict, and a literal `area_beta` dict), not from any real
`decode_omission_identity_slot()` output. `compute_omission_identity_encoding.py` has apparently
never been run to completion on this corpus. **The rendered `fig04.png`/`.svg` in this directory
right now is entirely illustrative and must not be cited or shown as a real result** until that
script is actually run and the figure is regenerated from its real output. This is the single
highest-priority item for this figure — everything else below is secondary until this is fixed.

1. **Panels A, E1, E2 are synthetic, not analysis output** (independent of item 0 above — even
   once the master CSVs exist, these three panels still won't be real without further work). The paradigm schematic (A) is fine
   (it's a diagram, not a data panel), but the confusion matrix (`conf_mat` in E1) and both ROC
   curves (`tpr_spk`/`tpr_lfp` sigmoids in E2) are hardcoded literal arrays in the plotting
   script — not read from any fitted model's actual out-of-fold predictions. This is a direct
   "no silent synthetic science" violation per project doctrine: nothing in the rendered figure
   marks these two panels as illustrative rather than real. **Must be fixed before this figure
   can be finalized**: either wire E1/E2 to real out-of-fold outputs from
   `decode_omission_identity_slot`, or visibly label them as schematic/illustrative.
2. **"GLMM" is a mislabel.** `omission_identity_glmm_coefficients.csv` and Panel D's title
   ("Spatial Hierarchy of Omitted Identity Encoding... GLMM Feature Importance") both call this
   a GLMM. The actual fit, in `compute_omission_identity_encoding.py`'s "Spatial GLMM Feature
   Importance" step, is one `sklearn.linear_model.LogisticRegression(C=1.0, penalty="l2")` fit
   on all units' P2 spike counts — a single-level, L2-regularized logistic regression, with no
   random-effects structure whatsoever. This project's own doctrine is explicit that "GLMM"
   means a true generalized linear mixed model with a stated random-effects structure; this is
   the same anti-pattern as "coefficients from a model never fitted." Needs either a real mixed
   model (session/subject random effects) or a corrected label throughout (CSV name, column
   name, panel title).
3. **No stats receipt exists.** Every other main figure in this project writes
   `svg/figNN_*_stats.md`/`.csv` via `figstats.write()`. This figure has neither — Panels B/C/D's
   real numbers (decoding accuracies, permutation p-values, AUCs) are not yet reported in the
   project's standard statistics table format, so they cannot currently be cited with a receipt.
4. **Possible band-definition drift.** `jnwb/omission_identity.py`'s `LFP_BANDS` dict is
   `{theta: 4-8, alpha: 8-14, beta: 14-30, gamma: 30-80}` (gamma unsplit) — inconsistent with the
   project's settled 5-band convention (low_gamma 30-50, high_gamma 50-80). Not yet confirmed
   whether this dict is actually used anywhere in the decoding path, or dead code.
## Output

`fig04.png` (300 DPI), `fig04.svg` — both re-copied unchanged from the former
`figS24_omission_identity_decoding.*` at promotion time. **These are the synthetic-fallback
renders described in item 0 above, not a real result.**
