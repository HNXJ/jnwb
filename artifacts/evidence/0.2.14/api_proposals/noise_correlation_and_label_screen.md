<!-- Drafted 2026-10-20 by a read-only reviewer against 7ea17995; ruled as recorded in artifacts/rulings/2026-10-20.md. Kept as drafted. -->

# Two signature proposals for ruling (read-only; no code written)

Baseline observed: `C:/workspace/jnwb` (commit `7ea17995` stated in packet; not re-verified — inferred to hold for the file:line claims below, which were read at this session).

---

## A. `noise_correlation` — trial-based r_sc beside the time-bin form

### What exists (observed)

- Time-bin function: `spike_count_correlation(spike_times, window_s, *, bin_ms)` at `jnwb/spiking.py:725`. Docstring at `jnwb/spiking.py:731-763`: "Mean pairwise Pearson correlation of binned spike counts (Cohen and Kohn 2011)"; "The samples are time bins within one window, not repeated trials, so a rate change shared by two units (signal correlation) raises r as much as shared trial-to-trial variability. This is not the trial-based noise correlation r_sc of Cohen and Kohn (2011)" (`jnwb/spiking.py:737-740`).
- References row stating the same: `docs/references.md:101` ("The paper's r_sc is taken across trials; `spike_count_correlation` takes it across time bins of one window, so shared rate changes (signal correlation) raise it too").
- Skill routing row: `skills/jnwb-spiking/SKILL.md:24`; API table: `docs/api.md:296`.
- Spiking input helpers the new function reuses: `_unit_trains` at `jnwb/spiking.py:636` (one 1-D float array per unit; a bare train refused), `_unit_counts` at `jnwb/spiking.py:657` (stacks `bin_spikes` per unit), `bin_spikes` at `jnwb/connectivity/_trials.py:129` (the `(n_trials, n_bins)` contract; `trial_starts` epochs one continuous train, `jnwb/connectivity/_trials.py:205-208`), `whole_bin_count` at `jnwb/_bins.py:112`.
- Existing result shape to reuse: the dict at `jnwb/spiking.py:750-754` (`mean_r`, `r` `(n_units, n_units)` with NaN rows/columns/diagonal, `n_pairs`, `n_units`, `n_bins`, `excluded_units`, `n_excluded`); zero-variance units are "excluded and reported, never scored as r = 0" (`jnwb/spiking.py:742-743`).
- Agreement/CI helpers elsewhere: `fleiss_kappa` (`jnwb/spiking.py:667`), `StatisticalAnalysis.bootstrap_ci` (`jnwb/statistics/_analysis.py:508`). No `de la Rocha`, `geometric` rate-normalisation, `balanced_accuracy`, or trial-based correlation exists in `jnwb/` (grep hits only `docs/references.md:100-101`, `jnwb/spectral/_coupling.py:175`, `jnwb/spectral/_decibels.py:118-120` for the words; the de la Rocha 2007 dependence and the geometric-mean-rate correction are **inferred** from the literature, not observed in this repo).

### Proposed signature

```python
def noise_correlation(
    counts,            # (n_units, n_conditions, n_trials_max) float/int, or per-unit list of (n_trials_i,) per condition — Q1 rules
    condition_id,      # (n_trials,) labels, one entry per trial column; required, no default
    *,
    min_trials: int,   # required, no default; fewest trials per condition kept (Q2 rules value)
    rng,               # required (fact S5, S11: every randomness consumer takes rng and reports it)
) -> dict: ...
```

No default supplies scientific meaning: no default count window, no default condition labels, no default `min_trials`, no default normalisation (per AGENTS.md §4 B3 and the packet).

### Estimand (one sentence)

Pearson correlation across trials of per-condition z-scored spike counts — for each unit and condition, subtract that condition's mean count (divide by its SD when nonzero; zero-SD units refused, see below), then correlate the two units' residual vectors pooled across conditions (whether pooling is over z-scored residuals only, with no cross-condition mean left in, is Q3). Claim class `magnitude` (fact S8 vocabulary discipline).

### Inputs and axes

- Preferred: units × trials **counts**, because every existing jnwb spiking helper already bridges spikes to counts (`bin_spikes`, `jnwb/connectivity/_trials.py:129`; `_unit_counts`, `jnwb/spiking.py:657`). The function does **not** take raw spike times plus a window: that would retype the `bin_spikes` rule (AGENTS.md §4.7, fact S7) and smuggle a default window (B3).
- Callers bin with `bin_spikes(..., trial_starts=...)` first, then pass counts. Trial raggedness (different trial counts per condition) is carried by a mask/NaN column, never by silently dropping trials.

### Refusals (all `ValueError`, naming the unit/condition)

1. Fewer than 2 usable trials in any kept condition (Pearson r of one point is undefined; mirrors the "at least 3 bins" refusal at `jnwb/spiking.py:768-775`).
2. Zero-variance units: excluded and listed in `excluded_units`, never scored 0 (same rule as `jnwb/spiking.py:742-743`); `mean_r` NaN with fewer than two usable units.
3. NaN/non-finite counts refused (mirrors `_unit_trains` at `jnwb/spiking.py:650-653` and `bin_spikes`' non-finite warning at `jnwb/connectivity/_trials.py:193-203` — here a refusal, not a warn-and-drop, because silent dropping changes the estimand).

### Returns (reuses the existing result type)

Same dict as `spike_count_correlation` (`jnwb/spiking.py:750-754`) plus two keys: `n_trials_per_condition` (dict/ordered array) and `conditions` (the kept labels in order). No new class (fact K4: no new manifest/receipt contract where existing types carry the responsibility).

### Known pitfalls the docstring must state

- r_sc grows with firing rate and count window at fixed correlation (de la Rocha et al. 2007 — **inferred** citation, absent from `docs/references.md`; the References row must be added with it).
- Report the geometric mean firing rate of each pair's bin alongside r (the de la Rocha correction covariate — **inferred** requirement, no helper exists; state it as a reported column, not a correction the function applies).
- Signal correlation is removed only insofar as condition means are removed; residual shared rate drift *within* a condition still raises r (the existing warning at `jnwb/spiking.py:737-740` applies verbatim).

### How it is tested

- Planted shared-gain population with known r_sc: N units, per-trial gain `g ~ N(1, s)`, counts `Poisson(rate * g * T)`; analytic r_sc ≈ `s²·rate·T / (1 + s²·rate·T)`-family (derived in the test from the generator's moments, tolerance = Monte-Carlo SE of the planted value at the test's seed, **not chosen**).
- Independent-Poisson null: same rates, independent draws; |r_sc| within `z·SE` with `SE = 1/sqrt(n_trials - 3)` (Fisher z, derived), asserted per-pair-mean, not per-pair-max.
- Mutant check: test fails on pre-fix code (time-bin function called on the same fixture must return a materially different value because the shared condition means are still in).

### Existing helpers it calls (AGENTS.md §4.7)

`whole_bin_count`-style validation pattern, `resolve_rng` + seed reporting (S5/S11), and the `spike_count_correlation` return-dict shape — but **not** `spike_count_correlation` itself (different samples: trials vs bins).

### Questions to rule (recommendation first)

1. **Input shape?** (a) counts array `(n_units, n_trials)` + `condition_id` [recommended — matches every downstream consumer, thinnest bridge]; (b) per-unit per-condition lists; (c) spike times + `trial_starts` + `window_s`.
2. **Residual form?** (a) z-score within condition (subtract mean, divide SD), pool residuals [recommended — Cohen & Kohn r_sc]; (b) subtract mean only; (c) no pooling — per-condition r matrices.
3. **Zero-SD handling?** (a) exclude + report, never 0 [recommended — matches `jnwb/spiking.py:742-743`]; (b) NaN pair only; (c) refuse the whole call.
4. **`min_trials` rule?** (a) required kwarg, refuse conditions below it [recommended — B3: no defaulted scientific choice]; (b) fixed minimum of 2; (c) default 5 with cited reason.
5. **Geometric-mean-rate column?** (a) returned per pair, uncorrected [recommended — states the pitfall without choosing the correction]; (b) corrected r also returned; (c) omitted.

---

## B. 13-04 — a screen fitted to caller-supplied curation labels

### What exists (observed)

- Roadmap row: `artifacts/roadmap.md:24` ("No screen reports held-out agreement per session with a curator's labels, declines on degenerate inputs, or names its estimand").
- Unit-quality measures (one unit in, one number out; none decides kept/not-kept): module docstring `jnwb/unit_quality.py:1-14`; e.g. `isi_cv` (`jnwb/unit_quality.py:554`), `refractory_contamination` (`jnwb/unit_quality.py:591`), `presence_ratio` (`jnwb/unit_quality.py:507`), `amplitude_cutoff` (`jnwb/unit_quality.py:690`).
- Rule-based classifier (thresholds only, no fitting): `classify_unit_quality` at `jnwb/metadata.py:329` ("a convention with no cited source: pass the cut-offs your study justifies", `jnwb/metadata.py:340-342`); absent/undefined columns are `'Unknown'`, never a pass (`jnwb/metadata.py:350-355`).
- Fitted classifiers in-repo (no new dependency allowed): `nested_cv_linear_svm` at `jnwb/decoding.py:147` (linear SVC + inner `GridSearchCV` over C, `jnwb/decoding.py:294-299`; grouped folds via `groups`, `jnwb/decoding.py:176-185`; decline-shaped `status` strings `insufficient_classes_for_cv` / `insufficient_trials_for_cv` / `insufficient_groups_for_cv`, `jnwb/decoding.py:189-199`). `BilinearLogisticRegression` is **not** public (`jnwb/bilinear.py:4`: "Not in `jnwb.__all__`") — inferred unsuitable as the screen's classifier.
- Agreement/CI pieces: `fleiss_kappa` (`jnwb/spiking.py:667`, refuses constant tables, `jnwb/spiking.py:716-720`); `majority_baseline` / `fold_majority_baseline` (`jnwb/decoding.py:60`, `:76`); `StatisticalAnalysis.bootstrap_ci` (`jnwb/statistics/_analysis.py:508`, takes `rng`, reports parametric + bootstrap CIs).
- QC skill invariants the shape must respect: audits count, never certify (`skills/jnwb-qc/SKILL.md:29-31`); sorter/curator labels are inputs, never ground truth, and no agreement shows a unit is a single neuron — decline that inference (`skills/jnwb-qc/SKILL.md:40-45`); absent columns unaudited, never "no problem" (`skills/jnwb-qc/SKILL.md:31-32`).
- Fact rows read: D1–D9 at `artifacts/fact_stack.md:46-59` (notably D1: one public callable = at most one public analysis operation, else every sequenced choice is a parameter; D5/D9: ambiguity and plausible mappings reported, never resolved); S1–S14 at `artifacts/fact_stack.md:73-86` (notably S8 claim-class vocabulary, S5/S11 rng, S13/S14 delay/immunity discipline — the estimand must not use `delay`/`inference` vocabulary).
- No existing held-out-agreement-per-session screen: grep over `jnwb/` for `screen`/`agreement-per-session` finds only `fleiss_kappa` and the decoding statuses above (observed absence).

### Proposed smallest public shape

```python
def screen_units_against_labels(
    metrics,        # DataFrame: one row per unit, metric columns + session column; required
    labels,         # (n_units,) caller labels, good/not (any two values np.unique can group); required, no default
    session_id,     # (n_units,) session of each row; required, no default
    *,
    metric_columns, # required, no default (B3/D9: the caller names the mapping, the function never guesses it)
    classifier,    # "linear_svm" (= nested_cv_linear_svm, jnwb/decoding.py:147) — the only choice at first; required kwarg, no default (D1: the sequenced choice is named)
    min_units: int, # required, no default; fewest labelled units per session fitted/reported
    rng,            # required (S5/S11)
) -> dict: ...
```

Fits on all sessions but one (`groups=session_id` in `nested_cv_linear_svm`), reports per held-out session. No threshold is fitted or stored: the screen reports agreement with the caller's labels, it does not certify units (QC safeguard 5).

### Agreement measure and CI

- Report **both** balanced accuracy (mean of per-class recall — robust to the good/not imbalance curators produce) **and** Cohen's kappa (chance-corrected; Fleiss form precedent at `jnwb/spiking.py:667-672`, binary case = Cohen's), plus the `majority_baseline` on the same splits (`jnwb/decoding.py:60`) so a high number on a 95%-good session reads as chance.
- CI from the existing helper: per-session bootstrap CI over the held-out units' 0/1 correct vector via `StatisticalAnalysis.bootstrap_ci` (`jnwb/statistics/_analysis.py:508`), with `rng` threaded through and reported. (Why bootstrap over units, not trials: the screen's inference unit is the unit; sessions are the held-out groups.)
- **Inferred** (no in-repo binary kappa): Cohen's kappa computed as `(p_o − p_e)/(1 − p_e)` on the 2×2 held-out table; constant-table sessions decline (below), mirroring `fleiss_kappa`'s refusal at `jnwb/spiking.py:716-720`.

### Declines (explicit outcome, not a number)

Per held-out session, `status` (extending the `nested_cv_linear_svm` status vocabulary at `jnwb/decoding.py:189-199`) is one of: `success`, `single_class` (held-out session has one label — kappa 0/0, refused as in `fleiss_kappa`), `too_few_units` (fewer than `min_units` labelled units), `constant_metric` (a used metric column constant on the training sessions — the direction is unidentifiable). Declined sessions carry NaN metrics plus the reason; a declined session never reads as 0 agreement.

### Estimand named in the result

`"estimand"`: "leave-one-session-out agreement (balanced accuracy and Cohen's kappa, with 0/1-correct bootstrap CI) between the linear-SVM screen fitted on the caller's metric columns and the caller's labels — a measure of label transfer across sessions, not of single-neuron identity" (claim class `magnitude`; S8-safe; QC safeguard 5 stated verbatim in the docstring).

### Questions to rule (recommendation first)

1. **Classifier?** (a) `nested_cv_linear_svm` only, named by a required `classifier="linear_svm"` stub for later extension [recommended — no new dependency, D1-compliant]; (b) also allow caller's fitted estimator; (c) no `classifier` param until a second one exists.
2. **Agreement?** (a) both balanced accuracy and kappa + majority baseline [recommended — imbalance-robust and chance-corrected]; (b) kappa only; (c) plain accuracy only.
3. **CI?** (a) `bootstrap_ci` over held-out 0/1-correct [recommended — existing helper, S5/S11-clean]; (b) analytic Wilson/binomial CI; (c) no CI.
4. **Decline shape?** (a) per-session `status` strings extending the decoding vocabulary [recommended — matches `jnwb/decoding.py:189-199`]; (b) raise on first degenerate session; (c) single global status.
5. **Metric columns?** (a) required `metric_columns`, absent column declines that session's report as unaudited [recommended — QC safeguard 2, D9]; (b) infer numeric columns; (c) default to the `classify_unit_quality` trio.

### Open / unknown

- Whether Hamm wants the screen to also return fitted weights or thresholds: **unknown** — the proposal returns agreement only, since returning a deployable curation rule would certify units against QC safeguard 5.
- The `min_units` value `k`: deliberately no default proposed (B3); the ruling should set whether the packet may propose one with a cited reason.