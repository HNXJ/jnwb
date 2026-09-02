---
name: jnwb-statistics
description: Statistical hypothesis testing, parametric/nonparametric dual reporting,
  family-wise FDR, label permutations, and exact confidence intervals.
---

# `jnwb-statistics` — Statistical Inference, Permutations & Nulls

## 1. Trigger
Activate this skill when comparing neural responses across conditions, performing label permutations, computing Benjamini-Hochberg FDR, bootstrap confidence intervals, or Clopper-Pearson binomial bounds.

## 2. Task-to-Primitive Routing Matrix
- `jnwb.StatisticalAnalysis.compare_groups(group1, group2, paired=False)`: Dual parametric (t-test) + non-parametric (Mann-Whitney/Wilcoxon) testing with explicit effect sizes (Cohen's $d$ or $d_z$).
- `jnwb.StatisticalAnalysis.fdr_correct(p_values, method="bh")`: Benjamini-Hochberg FDR correction across a hypothesis family.
- `jnwb.permute_labels(y, scheme="within_group"|"global", groups=None, rng=...)`: Permute labels under an explicit exchangeability structure.
- `jnwb.build_permutation_plan(labels, groups, n_permutations=..., seed=...)`: Generate an explicit within-group permutation manifest with SHA-256 digests.
- `jnwb.StatisticalAnalysis.clopper_pearson_ci(k, n, alpha=0.05)`: Exact binomial confidence intervals via Beta-quantile inversion.
- `jnwb.paired_fire_prob_test(pre_spikes, post_spikes)`: Paired exact test for firing probability changes.

## 3. Invariants & Safeguards
1. **Exchangeability Preservation**: For grouped/hierarchical data (e.g. trials nested in sessions or blocks), use `scheme="within_group"` with explicit `groups`. Never use global permutations when trial structure induces correlation.
2. **Exploratory vs Confirmatory**: Dual testing (`compare_groups`) reports raw p-values for both parametric and nonparametric tests. For multi-unit/multi-channel hypothesis families, run `fdr_correct()` across the collection.
3. **Explicit RNG**: Always supply an explicit `numpy.random.Generator` (e.g. `rng = np.random.default_rng(seed)`). Never mutate global seed state.

## 4. Minimal Workflow
```python
import jnwb
import numpy as np

rng = np.random.default_rng(42)
g1 = rng.normal(1.0, 1.0, 25)
g2 = rng.normal(0.0, 1.0, 25)

res = jnwb.StatisticalAnalysis.compare_groups(g1, g2)
p_raw = res["parametric"]["pval"]
q_vals = jnwb.StatisticalAnalysis.fdr_correct([p_raw, 0.03, 0.005])
```

## 5. Verification
- Verify that `StatisticalAnalysis.fdr_correct` matches `scipy.stats.false_discovery_control`.
- Verify `permute_labels` preserves within-group label marginal distributions.

## 6. Canonical Documentation Links
- [`docs/07_statistical_inference_and_nulls.md`](../../docs/07_statistical_inference_and_nulls.md)
