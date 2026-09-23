---
name: jnwb-statistics
description: Statistical hypothesis testing, parametric/nonparametric dual reporting,
  family-wise FDR, label permutations, and exact confidence intervals.
---

# `jnwb-statistics` — Statistical Inference, Permutations & Nulls

## 1. Trigger
Activate this skill when comparing neural responses across conditions, performing label permutations, computing Benjamini-Hochberg FDR, bootstrap confidence intervals, or Clopper-Pearson binomial bounds.

## 2. Task-to-Operation Routing Matrix
- `jnwb.StatisticalAnalysis.exploratory_compare(group1, group2, paired=False, n_bootstrap=2000, test="both"|"parametric"|"nonparametric")`: Dual parametric (t-test) + non-parametric (Mann-Whitney/Wilcoxon) testing with explicit effect sizes (Cohen's $d$ or $d_z$). This is `compare_groups` without the `multiple_comparison` block, and is the entry point `AGENTS.md` §10 uses; the two return different keys, so routing to both split the contract. `test` names the primary test and the other is then not computed; the default runs two and spends two.
- `jnwb.StatisticalAnalysis.exploratory_correlate(x, y, method="both"|"pearson"|"spearman")`: Pearson $r$ under `parametric` and Spearman $\rho$ under `non_parametric`, raw p-values. `method` names the correlation and the other is then not computed; `method="both"` computes two and spends two. `StatisticalAnalysis.correlate` takes the same `method=`.
- `jnwb.StatisticalAnalysis.fdr_correct(p_values, method="bh")`: Benjamini-Hochberg FDR correction across a hypothesis family.
- `jnwb.permute_labels(y, scheme="within_group"|"global", groups=None, rng=...)`: Permute labels under an explicit exchangeability structure.
- `jnwb.build_permutation_plan(labels, groups, n_permutations=..., rng=...)`: Generate an explicit within-group permutation manifest with SHA-256 digests.
- `jnwb.cluster_permutation_test(X, Y, *, paired=False, groups=None, threshold=2.0, n_permutations=1000, rng=0, n_jobs=1)`: Mass-univariate testing over time or frequency with maximum-cluster FWER control. A significant cluster licenses "the conditions differ somewhere in the searched window" and nothing about where: the cluster's onset, offset, peak and width are not estimates, because `threshold` defined its edges.
- `jnwb.StatisticalAnalysis.clopper_pearson_ci(k, n, alpha=0.05)`: Exact (Clopper-Pearson) binomial confidence interval for `k` successes in `n` trials.
- `jnwb.paired_fire_prob_test(fires_target, fires_null, n_shuffles, n_bootstrap, rng)`: Paired bootstrap test for firing-probability changes between conditions. All five are required and `rng` must be a `Generator`, not a seed. **Target first.** Swapping the first two arguments returns a valid result with `risk_difference` negated and `odds_ratio` inverted, and raises nothing.

- `jnwb.clopper_pearson(k, n, alpha=0.05)`: The exact binomial interval as a free function; `StatisticalAnalysis.clopper_pearson_ci` is the method form of the same computation.
- `jnwb.exact_sign_flip(diffs, alternative="two-sided", n_mc=10000, rng=42)`: Exact paired sign-flip permutation test on differences. Exact enumeration below the Monte-Carlo threshold, so a p-value can be exactly attainable rather than estimated.
- `jnwb.mann_whitney_p_floor(n1, n2, alternative="two-sided")`: The smallest non-zero p-value those sample sizes can attain without ties. A reported p at the floor means the test is saturated, not that the effect is that strong.
- `jnwb.shuffle_pvalue_paired(a, b, n_shuffles, rng, alternative="two-sided")` and `jnwb.shuffle_pvalue_unpaired(a, b, n_shuffles, rng, alternative="two-sided")`: Shuffle-controlled p-values for `mean(a - b)` and `mean(a) - mean(b)`. `n_shuffles` and `rng` are required, and `n_shuffles` bounds the smallest p obtainable.
- `jnwb.shuffle_r2_ci(y_true, y_score, groups=None, n_shuffle=200, rng=42)`: $R^2$ between a continuous score and a 0/1 label with a shuffle-null CI. The interval is a percentile of the **null**, not of the estimate. Pass `groups` whenever trials nest, or the null pools across structure the data has.

## 3. Invariants & Safeguards
1. **Exchangeability Preservation**: For grouped/hierarchical data (e.g. trials nested in sessions or blocks), use `scheme="within_group"` with explicit `groups`. Never use global permutations when trial structure induces correlation.
2. **Exploratory vs Confirmatory**: `exploratory_compare` and `exploratory_multi` report raw p-values, and their results carry `correction: "none"` to say so. By default it performs two tests and reports both; pass `test=` to declare one primary test, which is what a pre-registered family budget has to be able to state. `exploratory_correlate` declares its one correlation with `method=`. For multi-unit/multi-channel hypothesis families, run `fdr_correct()` across the collection.
3. **Explicit RNG**: Always supply an explicit `numpy.random.Generator` (e.g. `rng = np.random.default_rng(seed)`). Never mutate global seed state.

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
- Verify that `StatisticalAnalysis.fdr_correct` matches `scipy.stats.false_discovery_control`.
- Verify `permute_labels` preserves within-group label marginal distributions.

## 6. Canonical Documentation Links
- [`docs/07_statistical_inference_and_nulls.md`](../../docs/07_statistical_inference_and_nulls.md)
