# 06 — Statistics and Inference

Generated 2026-08-17, synthesized from the `omission-statistics` skill and cross-checked against
`jnwb/statistics.py`, `context/figures/figstats.py`, and the connectivity/spectral audits
(doc04). This document states the **rules that decide whether a result is real** on this corpus
— read it before reporting any p-value, effect size, or interval.

## The rules

**The session is the default inferential unit for LFP population claims.** Treating channels as
independent has inflated effective n by more than two orders of magnitude and produced |z| > 40
on sub-decibel effects on this corpus. Channel-level fits are descriptive or sensitivity only.
State the unit of inference in the sentence that carries the claim.

**Three subjects cannot identify a random-effect variance.** Subject is handled by
stratification or an explicit fixed term, never a three-level random effect. **A model with no
random effects is not a GLMM however it is titled** — that mislabel has shipped once on this
project. Model choice is estimand-driven and recorded per figure in `PROJECT_STATE.md`, not
asserted generically.

**Area and subject are confounded corpus-wide, but the design graph is connected.** No area was
recorded in all three animals, so a between-area coefficient is not separable from a
between-animal difference by modelling alone. Every area is nevertheless recorded in ≥2 animals
(V4 in all 3), so additive area+subject effects are jointly identifiable — resolve the graph
structurally, do not infer disconnection from marginal counts. See doc01 for the full
area×animal coverage table.

**Benjamini–Hochberg controls FDR, not FWER.** Cluster-based permutation and Bonferroni/Holm
control FWER. Writing that one controls the other's rate is a factual error, not a wording
choice — name the correction family at each point of use. `context/figures/figstats.py::holm()`
and `bh()` deliberately report **both** `p_holm` and `q_bh` per test so a reader can see which
guarantee is being claimed.

**Multiplicity is a property of the family, not the count.** Correcting a single pre-specified
coefficient is meaningless and implies an undisclosed set; several tests reported together with
no correction is the commonest route to a false positive. `directed_network()` in
`jnwb/connectivity.py` corrects across the whole N×(N-1) ordered-pair family by default — the
project's own reference implementation of "the family is the whole thing you tested, not the
one cell you're citing."

**Match the interval to the estimand.** Proportions built from counts and denominators use exact
**Clopper–Pearson** (`jnwb.statistics.clopper_pearson`, promoted from 6 duplicated
implementations across the codebase — see doc02/doc04). No RNG, no seed, no resample count to
reproduce. Bootstrap is available where it's the right tool, must never be a silent default, and
must not mutate global RNG state (see doc02's RNG-discipline table — `statistics.py`'s own
`bootstrap_ci`/`permutation_test` violate the "not silent" half of this by hardcoding
`np.random.default_rng(42)` inline with no seed parameter).

**Do not dichotomize an ordered variable to gain a contrast.** **Correlations on few,
non-independent aggregate units are descriptive**, not inferential.

**Minimize the diversity of inferential frameworks.** ≤4 families in a paper, ~10 p-values
total; report the test that carries the claim, describe the rest.

## Permutation exchangeability is the caller's responsibility

`StatisticalAnalysis.permutation_test` is a **flat, ungrouped shuffle** — valid only if the
inputs carry no internal session/cycle/subject structure the statistic depends on. **On this
corpus that is frequently false.**

This shipped as a real bug, fixed 2026-08-10:
`jnwb.omission_identity.decode_identity_cycle_deconfound` compared grouped LOCO folds against an
ungrouped global-permutation null — a statistic that respects grouping tested against a null
that ignores it, which can manufacture significance. Fix:

```python
from jnwb.permutation import permute_labels
y_perm = permute_labels(y, groups=cycle_ids, scheme="within_group", rng=rng)
```

`jrsa()`'s internal `permutations=` null has the same limitation, no grouping awareness — if
inputs are concatenated across sessions or repeated cycles, pre-shuffle the grouped structure
yourself and pass `permutations=0`. See doc02 for the fuller `jnwb.permutation` module summary
(the type-enforced `rng` requirement, the lint test that greps for a bare
`rng.permutation(y)` reappearing outside its own `scheme="global"` path).

The corpus-level counterpart of this rule is the corrected group-pooling design in doc04: test
within session first, pool after, as a proportion with an exact interval. Both rules are the
same principle at two different scales (grouped permutation null vs grouped significance
pooling) — don't apply one and forget the other.

## API dispositions — what to use, what is broken

| Behavior | Disposition |
|---|---|
| `compare_groups`/`compare_populations`/`compare_multiple_groups` returning parametric **and** non-parametric by construction | **REJECT / REQUIRES_CODE_CHANGE.** Automatic dual testing makes the ≤4-family budget unenforceable. One question gets one pre-specified primary procedure; a second estimator appears only when it answers a distinct question or is explicitly labelled sensitivity. Until repaired, **read only the pre-specified test from the returned dict and say which one you read** — do not report both as if two tests were planned. |
| `StatisticalAnalysis.bootstrap_ci`/`permutation_test` calling `np.random.default_rng(42)` inline | **REJECT / REQUIRES_CODE_CHANGE.** Hardcoded, unparameterized seed — see doc02's RNG table. Not global-state mutation (that's `report.py`'s separate, worse defect — doc02/doc09), but every call across the codebase draws the identical sequence. |
| Deprecated `fdr_pval_parametric`/`fdr_pval_nonparametric` keys | **Do not use.** They mirror raw p-values and are NOT FDR-corrected despite the name. |
| `jnwb.permutation.permute_labels(y, groups=..., scheme="within_group")` | **Canonical** grouped-null helper. |
| `jnwb.report.fdr_correct` vs `StatisticalAnalysis.fdr_correct` | Two distinct helpers (see doc02 — `report.py` locally reimplements BH-FDR rather than calling the canonical one). Pick one per analysis and say which. |

## Test-choice table

| Scenario | Parametric | Non-parametric | Effect size |
|---|---|---|---|
| 2 independent groups | t-test | Mann–Whitney U | Cohen's d |
| 2 paired groups | paired t | Wilcoxon | Cohen's dz |
| 3+ groups | ANOVA | Kruskal–Wallis | eta² |
| correlation | Pearson r | Spearman rho | R² |
| proportion | — | — | **Clopper–Pearson interval** |

For a 2D spectrotemporal grid: flatten the whole grid, correct once across the entire family,
then reshape — correcting per-row or per-column is a different (and undeclared) family.

## `jrsa` — unified similarity engine

`jrsa(x1, x2=None, metric=..., permutations=..., correction="fdr_bh", backend="auto", ...) ->
JRSAResult`. Metrics: pearson, spearman, kendall, cosine, rsa, cka, rv, hsic,
distance_correlation, mutual_information, procrustes, granger, transfer_entropy, phase_slope.
Every `_metric` returns exactly `(value, statistic, effect, p, df)`.

Known limits: `_compute_statistics` is a no-op stub; `_stack_batches` is never called
(`batch_size` cosmetic); permutation p-values are **not lag-segregated** in multi-lag mode; HSIC
assumes symmetric kernels. Fine for a quick multi-dimensional similarity check — for anything
shipping in a figure prefer `jnwb.connectivity`, which carries this corpus's stationarity and
residual-autocorrelation diagnostics (doc04). `jrsa` is the repo's only JAX consumer — JAX has
no global RNG, keys are explicit, a reused key silently yields identical draws (see
`numerical-computing` skill).

**Note (doc02)**: `jrsa(metric="granger"/"transfer_entropy"/"phase_slope")` and
`connectivity.granger()`/`transfer_entropy()`/`phase_slope_index()` are two independent code
paths computing nominally the same statistics — not confirmed to agree numerically. Treat as
separate implementations, not interchangeable, until reconciled.

## Re-derive reported statistics rather than trusting them

- Recompute the p-value from the reported statistic and n. An impossible pair at the stated
  sample size usually means two analyses were merged into one sentence.
- Re-derive the interval from the named method. If Methods say bootstrap and the intervals
  reproduce exactly under an exact formula, the Methods describe something else.
- Sum every table column and compare against every place the total is quoted. The table is
  usually right; the prose is usually stale — this project's own O+/O++ count fragmentation
  (doc03) is the largest live example of exactly this failure mode.
- Implausibly round percentages (most cells exactly X.0%) were probably back-computed rather
  than counted — demand a provenance receipt.
- Nested and disjoint categories must not be mixed: a composition summing to exactly 100% cannot
  also contain a subset nested inside one of its own slices.
- When two numbers for the same quantity disagree, trace both and surface the discrepancy — do
  not silently pick one. (See doc09 for this project's open list.)

## Report the estimate, not just the verdict

Effect size with an interval beats a p-value; neither substitutes for the other. Never write
"significant" without the estimate and its uncertainty in the same sentence. A null result is a
result only with a sensitivity analysis attached — report the positive control establishing the
measurement could have detected the effect, otherwise "no effect" is indistinguishable from "no
power." Averaging a signed effect over units that disagree in sign and reporting the null as an
absence of effect is a separate error — state magnitude and direction as two claims when they
have two answers.

## Applying this on the current corpus — worked examples from the audit

- **fig05's GLMM** (doc05): 2/45 cells survive Holm-Bonferroni, 11/45 survive BH-FDR — reported
  as two different numbers under two different guarantees, not conflated into one "significant
  count."
- **The corrected group-pooling design** (doc04) is this project's concrete instantiation of
  "test within session first, pool after, as a proportion with an exact interval" — it exists
  because pooling raw session point estimates before testing produced 0/45–0/240 null results
  six times in one week on effects later shown to be real at the session level.
- **L5/L9 in the LFP track** (doc05) both surface real applications of these rules in practice:
  L5 reports an honest `H3_simultaneous_or_ambiguous` null rather than forcing a hierarchy claim
  at n≤6 sessions/area; L9 fixed a pseudoreplication bug where a session with FEF on two probes
  was silently counted as 2-3 sessions in a bootstrap CI.
- **The six-different-O+-count problem** (doc03) is the sharpest example on this corpus of "sum
  every column and compare against every place the total is quoted" — none of the six numbers is
  wrong in isolation; the risk is citing one without naming which.
