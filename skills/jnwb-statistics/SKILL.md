---
name: jnwb-statistics
description: Statistical hypothesis testing, parametric/nonparametric dual reporting,
  FDR (Benjamini-Hochberg), label permutations, and exact confidence intervals.
---

# `jnwb-statistics` — Statistical Inference, Permutations & Nulls

## 1. Trigger
Comparing neural responses across conditions, label permutations, Benjamini-Hochberg FDR, bootstrap confidence intervals, or Clopper-Pearson binomial bounds.

## 2. Routing
- `jnwb.StatisticalAnalysis.exploratory_compare(group1, group2, paired=False, n_bootstrap=2000, test="both"|"parametric"|"nonparametric")`: Parametric (t-test) and non-parametric (Mann-Whitney/Wilcoxon) tests with effect sizes (Cohen's $d$ or $d_z$). It is `compare_groups` without the `multiple_comparison` block; the two return different keys. `test` names the primary test and the other is then not computed; the default runs two and spends two. An empty group, one value per group, two identical constant groups, or paired groups whose every difference is zero is not refused: the test it cannot support reads `statistic` and `pval` NaN, and its `significant_*` flag is False.
- `jnwb.StatisticalAnalysis.exploratory_correlate(x, y, method="both"|"pearson"|"spearman")`: Pearson $r$ under `parametric` and Spearman $\rho$ under `non_parametric`, with raw p-values and `correction: "none"`. `method` names the correlation and the other is then not computed; `method="both"` computes two and spends two. `StatisticalAnalysis.correlate` takes the same `method=`.
- `jnwb.StatisticalAnalysis.fdr_correct(p_values, method="bh")`: Benjamini-Hochberg FDR correction across a hypothesis family.
- `jnwb.permute_labels(y, scheme="within_group"|"global", groups=None, rng=...)`: Permutes labels under a named exchangeability structure.
- `jnwb.build_permutation_plan(labels, groups, n_permutations=..., rng=...)`: Within-group permutation manifest: `draw_manifest` holds one row per draw with its seed and the SHA-256 `label_digest` of the permuted labels.
- `jnwb.cluster_permutation_test(X, Y, *, paired=False, groups=None, threshold=2.0, n_permutations=1000, rng=0, n_jobs=1)`: Mass-univariate testing over time or frequency with maximum-cluster FWER control. A significant cluster licenses "the conditions differ somewhere in the searched window" and nothing about where: the cluster's onset, offset, peak and width are not estimates, because `threshold` defined its edges.
- `jnwb.StatisticalAnalysis.clopper_pearson_ci(k, n, alpha=0.05)` and `jnwb.clopper_pearson(k, n, alpha=0.05)`: Exact (Clopper-Pearson) binomial interval for `k` successes in `n` trials, as a method and as a free function; one computation.
- `jnwb.paired_fire_prob_test(fires_target, fires_null, n_shuffles, n_bootstrap, rng)`: Paired bootstrap test for firing-probability changes between conditions. All five are required and `rng` must be a `Generator`, not a seed. **Target first.** Swapping the first two arguments returns a valid result with `risk_difference` negated and `odds_ratio` inverted, and raises nothing.
- `jnwb.exact_sign_flip(diffs, alternative="two-sided", n_mc=10000, rng=42)` → `(observed_mean, p_value, p_floor)`: Paired sign-flip permutation test on differences. Up to 20 differences it enumerates all $2^N$ sign flips and uses no RNG, so the p-value is exact; above 20 it draws `n_mc` Monte-Carlo flips from `rng`. `p_floor` is the smallest non-zero p the sample can attain.
- `jnwb.mann_whitney_p_floor(n1, n2, alternative="two-sided")`: The smallest non-zero p-value those sample sizes can attain without ties. A p at the floor means the test is saturated, not that the effect is that strong.
- `jnwb.shuffle_pvalue_paired(a, b, n_shuffles, rng, alternative="two-sided")` and `jnwb.shuffle_pvalue_unpaired(a, b, n_shuffles, rng, alternative="two-sided")`: Shuffle-controlled p-values for `mean(a - b)` and `mean(a) - mean(b)`, each returned as `(observed_diff, p_value)`. `n_shuffles` and `rng` are required; the smallest obtainable p is `1 / (n_shuffles + 1)`.
- `jnwb.shuffle_r2_ci(y_true, y_score, groups=None, n_shuffle=200, rng=42)`: $R^2$ between a continuous score and a 0/1 label with a shuffle-null CI. The interval is a percentile of the **null**, not of the estimate. Pass `groups` whenever trials nest, or the null pools across structure the data has. A single-class label or a constant score has no $R^2$: `r2_observed`, `p_val` and the null fields are NaN.

## 3. Invariants & Safeguards
1. **Exchangeability**: for grouped or hierarchical data (e.g. trials nested in sessions or blocks), use `scheme="within_group"` with explicit `groups`. Never permute globally when trial structure induces correlation.
2. **Exploratory vs confirmatory**: `exploratory_compare`, `exploratory_multi` and `exploratory_correlate` report raw p-values, and their results carry `correction: "none"`. By default it performs two tests and reports both; `test=` (or `method=` for `exploratory_correlate`) declares the one primary test a pre-registered family budget has to state. Across multi-unit or multi-channel families, run `fdr_correct()` over the collection.
3. **Explicit RNG**: pass a `numpy.random.Generator` (`rng = np.random.default_rng(seed)`). Never mutate global seed state.

## 4. Minimal Workflow
```python
import jnwb
import numpy as np

rng = np.random.default_rng(42)
g1 = rng.normal(1.0, 1.0, 25)
g2 = rng.normal(0.0, 1.0, 25)

res = jnwb.StatisticalAnalysis.exploratory_compare(g1, g2)
p_raw = res["parametric"]["pval"]
q_vals = jnwb.StatisticalAnalysis.fdr_correct([p_raw, 0.03, 0.005])
```

## 5. Verification
- `StatisticalAnalysis.fdr_correct` matches `scipy.stats.false_discovery_control`.
- `permute_labels` preserves within-group label marginals.

## 6. Documentation
- [`docs/07_statistical_inference_and_nulls.md`](../../docs/07_statistical_inference_and_nulls.md)
