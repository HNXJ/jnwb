---
name: jnwb-statistics
description: |
  Standardised dual-test statistics for the Omission project via jnwb.
  Covers the StatisticalAnalysis object: compare_groups, compare_multiple_groups,
  correlate, bootstrap_ci, permutation_test. Every method returns the same
  structured dict: parametric test + non-parametric test + effect size + FDR.
  Use this skill any time you need a rigorous comparison between groups or metrics.
---

# jnwb-statistics: Dual Statistical Testing

Module root: `d:/workspace/omission/jnwb/`  
Primary file: `statistics.py`

## Import

```python
import sys; sys.path.insert(0, 'd:/workspace/omission')
from jnwb import StatisticalAnalysis
```

## Standard Return Dict (all comparisons)

Every comparison function returns:

```python
{
    'parametric': {
        'test': 'independent_t_test',   # or ANOVA, Pearson r, etc.
        'statistic': 2.34,
        'pval': 0.021,
        'effect_size': 0.45,            # Cohen's d, eta², R²
    },
    'non_parametric': {
        'test': 'mann_whitney_u',       # or Kruskal-Wallis, Spearman rho
        'statistic': 1200,
        'pval': 0.018,
    },
    'fdr_pval_parametric': 0.042,       # Benjamini-Hochberg α=0.05
    'fdr_pval_nonparametric': 0.036,
    'significant_parametric': True,
    'significant_nonparametric': True,
}
```

## Methods

### Compare Two Groups

```python
result = StatisticalAnalysis.compare_groups(v1_data, v4_data, paired=False)
# Paired data (e.g., pre vs post):
result = StatisticalAnalysis.compare_groups(pre, post, paired=True)
```

Parametric: independent/paired t-test  
Non-parametric: Mann-Whitney U / Wilcoxon signed-rank  
Effect size: Cohen's d

### Compare 3+ Groups

```python
groups = {'V1': v1_data, 'V4': v4_data, 'MT': mt_data}
result = StatisticalAnalysis.compare_multiple_groups(groups)
```

Parametric: one-way ANOVA  
Non-parametric: Kruskal-Wallis  
Effect size: eta²

### Correlation

```python
corr = StatisticalAnalysis.correlate(firing_rate_array, waveform_duration_array)
```

Parametric: Pearson r + p-value  
Non-parametric: Spearman rho + p-value  
Effect size: R²

### Bootstrap Confidence Intervals

```python
import numpy as np
ci = StatisticalAnalysis.bootstrap_ci(data,
                                       statistic_func=np.mean,
                                       n_bootstrap=10000,
                                       ci=0.95)
# Returns: {'statistic': 5.2, 'parametric_ci': (4.8, 5.6), 'bootstrap_ci': (4.9, 5.5)}
```

### Permutation Test

```python
perm = StatisticalAnalysis.permutation_test(group1, group2, n_permutations=5000)
# Returns: {'observed_difference': 1.2, 'pval': 0.0008, 'significant': True,
#           'null_distribution': array}
```

## Test Selection Table

| Scenario              | Parametric        | Non-parametric    | Effect Size |
|-----------------------|-------------------|-------------------|-------------|
| 2 independent groups  | t-test            | Mann-Whitney U    | Cohen's d   |
| 2 paired groups       | paired t-test     | Wilcoxon          | Cohen's d   |
| 3+ groups             | ANOVA             | Kruskal-Wallis    | eta²        |
| Correlation           | Pearson r         | Spearman rho      | R²          |
| Confidence interval   | t-based CI        | Bootstrap CI      | —           |
| Permutation           | —                 | Permutation test  | p-value     |

FDR correction: **Benjamini-Hochberg** at α = 0.05, applied to both branches.

## Design Notes

- All random seeds fixed at **42** for reproducibility.
- `significant_parametric` / `significant_nonparametric` flags use `fdr_pval < 0.05`.
- For publication, report **both** branches and both FDR-corrected p-values.
