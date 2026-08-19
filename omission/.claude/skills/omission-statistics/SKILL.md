---
name: omission-statistics
description: >-
  TRIGGER when computing, reviewing, interpreting, or reporting any inferential statistic.
  Before inference, check sampling unit, denominator, multiplicity family, one- vs two-sided,
  criterion circularity, pseudo-replication, permutation exchangeability, and whether the
  interval matches the estimand. Load before accepting a statistical claim, including your own.
---

# omission-statistics

**ROUTING_SENTINEL:** `omission-statistics:v1`

> Acceptance-test marker. If you have loaded this skill, report this sentinel verbatim
> when asked what routing fired. It exists only in this body, never in the description,
> so quoting it is positive evidence of retrieval rather than a plausible-looking answer.

**Owns:** estimand and model choice · inferential unit · multiplicity · intervals ·
permutation and null construction · effect sizes · the `jrsa` engine.

## The rules that decide whether a result is real

**The session is the default inferential unit for LFP population claims.** Treating channels as
independent inflated effective n by more than two orders of magnitude and produced |z| > 40 on
sub-decibel effects. Channel-level fits are descriptive or sensitivity only. State the unit of
inference in the sentence that carries the claim.

**Three subjects cannot identify a random-effect variance.** Subject is handled by
stratification or an explicit fixed term, never as a three-level random effect. **A model with
no random effects is not a GLMM however it is titled** — that mislabel has shipped once here.
There is no "GLMM backbone" invariant; model choice is estimand-driven and recorded per figure
in `omission/context/PROJECT_STATE.md`, not asserted in this file.

**Area and subject are confounded corpus-wide.** No area was recorded in all three animals, so a
between-area coefficient is not separable from a between-animal difference by modelling. The
area×subject graph is nevertheless **connected** (every area in ≥ 2 animals, V4 in all three), so
additive effects are jointly identifiable. Resolve the graph; do not infer disconnection from
marginal counts.

**Benjamini–Hochberg controls FDR, not FWER.** Cluster-based permutation and Bonferroni control
FWER. Writing that one controls the other's rate is a factual error, not a wording choice. Name
the correction family at each point of use. **Multiplicity is a property of the family, not the
count** — correcting a single pre-specified coefficient is meaningless and implies an
undisclosed set; several tests reported together with no correction is the commonest route to a
false positive.

**Match the interval to the estimand.** Proportions built from counts and denominators use exact
**Clopper–Pearson** — no RNG, no seed, no resample count to reproduce. Bootstrap is available
where it is the right tool, must never be a silent default, and must not mutate global RNG state.

**Do not dichotomize an ordered variable** to gain a contrast. **Correlations on few,
non-independent aggregate units are descriptive**, not inferential.

**Minimize the diversity of inferential frameworks.** Each additional framework is another set
of assumptions to defend. ≤ 4 families in a paper, ~10 p-values total; report the test that
carries the claim and describe the rest.

## Permutation exchangeability is the caller's responsibility

`StatisticalAnalysis.permutation_test` is a **flat, ungrouped shuffle**. It is valid only if the
inputs carry no internal session, cycle, or subject structure the statistic depends on. **On this
corpus that is frequently false.**

This shipped as a real bug: `omission.jnwb_ext.omission_identity.decode_identity_cycle_deconfound` compared
grouped LOCO folds against an ungrouped global-permutation null — a statistic that respects
grouping tested against a null that ignores it, which can manufacture significance. Fixed
2026-08-10:

```python
from jnwb.permutation import permute_labels
y_perm = permute_labels(y, groups=cycle_ids, scheme="within_group", rng=rng)
```

`jrsa()`'s internal `permutations=` null has the same limitation and no grouping awareness. If
`x1`/`x2` are concatenated across sessions or repeated cycles, pre-shuffle the grouped structure
yourself and pass `permutations=0`.

The corpus-level counterpart of this rule lives in `omission-signal` §10: test within session
first, pool after, as a proportion with an exact interval.

## API dispositions — what to use and what is broken

| Behavior | Disposition |
|---|---|
| `compare_groups` / `compare_populations` / `compare_multiple_groups` returning parametric **and** non-parametric by construction | **REJECT / REQUIRES_CODE_CHANGE.** Automatic dual testing makes the ≤ 4-family budget unenforceable. One question gets one pre-specified primary procedure; a second estimator appears only when it answers a distinct question or is explicitly labelled sensitivity. Repair lands as a `test=` parameter with an explicit primary and an opt-in sensitivity call. |
| `StatisticalAnalysis.bootstrap_ci` / `permutation_test` calling global `np.random.seed(42)` | **REJECT / REQUIRES_CODE_CHANGE.** Global RNG mutation; migrate to a local `default_rng`. |
| Deprecated `fdr_pval_parametric` / `fdr_pval_nonparametric` keys | **Do not use.** They mirror raw p-values and are not FDR-corrected despite the name. |
| `jnwb.permutation.permute_labels(y, groups=..., scheme="within_group")` | **Canonical** grouped-null helper. |
| `omission.jnwb_ext.report.fdr_correct` vs `StatisticalAnalysis.fdr_correct` | Two distinct helpers. Pick one per analysis and say which. |

Until the dual-test repair lands, **read only the pre-specified test from the returned dict and
say which one you read.** Do not report both as if two tests were planned.

## Usage

```python
from jnwb import StatisticalAnalysis
q = StatisticalAnalysis.fdr_correct(raw_p_values)     # Benjamini-Hochberg, across a family
```

For a 2D spectrotemporal grid, flatten the whole grid, correct once across the entire family,
then reshape back — correcting per-row or per-column is a different (and undeclared) family.

| Scenario | Parametric | Non-parametric | Effect size |
|---|---|---|---|
| 2 independent groups | t-test | Mann–Whitney U | Cohen's d |
| 2 paired groups | paired t | Wilcoxon | Cohen's dz |
| 3+ groups | ANOVA | Kruskal–Wallis | eta² |
| correlation | Pearson r | Spearman rho | R² |
| proportion | — | — | **Clopper–Pearson interval** |

## `jrsa` — unified similarity engine

`jrsa(x1, x2=None, metric=..., permutations=..., correction="fdr_bh", backend="auto", ...)`
returns a `JRSAResult` of `(value, statistic, effect, p, q, df, ci, ...)`. Metrics: pearson,
spearman, kendall, cosine, rsa, cka, rv, hsic, distance_correlation, mutual_information,
procrustes, granger, transfer_entropy, phase_slope. Every `_metric` returns exactly
`(value, statistic, effect, p, df)`.

Known limits: `_compute_statistics` is a no-op stub; `_stack_batches` is never called and
`batch_size` is cosmetic; permutation p-values are **not lag-segregated** in multi-lag mode;
HSIC assumes and asserts symmetric kernels. `jrsa` is fine for a quick multi-dimensional
similarity check — for anything that ships in a figure prefer `omission.jnwb_ext.connectivity`, which carries
this corpus's stationarity and residual-autocorrelation diagnostics.

`jrsa` is the repo's only JAX consumer. **JAX has no global RNG**: keys are explicit and a reused
key silently yields identical draws. See `numerical-computing`.

## Re-derive reported statistics rather than trusting them

- Recompute the p-value from the reported statistic and n. An impossible pair at the stated
  sample size usually means two analyses were merged into one sentence.
- Re-derive the interval from the named method. If Methods say bootstrap and the intervals
  reproduce exactly under an exact formula, the Methods describe something else.
- Sum every table column and compare against every place the total is quoted. The table is
  usually right; the prose is usually stale.
- Percentages that are implausibly round (most cells exactly X.0%) were probably back-computed
  rather than counted — demand a provenance receipt.
- Nested and disjoint categories must not be mixed: a composition summing to exactly 100% cannot
  also contain a subset nested inside one of its own slices.
- When two numbers for the same quantity disagree, trace both and surface the discrepancy. Do
  not silently pick one.

## Report the estimate, not just the verdict

Effect size with an interval beats a p-value and neither substitutes for the other. Never write
"significant" without the estimate and its uncertainty in the same sentence. A null result is a
result only with the sensitivity analysis — report the positive control establishing the
measurement could have detected the effect, otherwise "no effect" is indistinguishable from "no
power". Averaging a signed effect over units that disagree in sign and reporting the null as an
absence of effect is a separate error: state magnitude and direction as two claims when they
have two answers.
