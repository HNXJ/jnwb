---
name: jnwb-statistics
description: |
  Standardised dual-test statistics for the Omission project via jnwb.
  Covers the StatisticalAnalysis object: compare_groups, compare_multiple_groups,
  correlate, bootstrap_ci, permutation_test. Every method returns the same
  structured dict: parametric test + non-parametric test + named effect size.
  Family-wise FDR via StatisticalAnalysis.fdr_correct(p_values) across hypotheses.
  Use this skill any time you need a rigorous comparison between groups or metrics.
---

# jnwb-statistics: Dual Statistical Testing

Module root: `jnwb/` (repo root: `oa.paths.REPO_ROOT`)  
Primary file: `statistics.py`

## Import

```python
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
        'effect_size': 0.45,
        'effect_size_name': 'cohens_d_pooled',  # or cohens_dz when paired
    },
    'non_parametric': {
        'test': 'mann_whitney_u',       # or Kruskal-Wallis, Spearman rho
        'statistic': 1200,
        'pval': 0.018,
    },
    # Deprecated aliases: mirror raw p (NOT FDR). See multiple_comparison note.
    'fdr_pval_parametric': 0.021,
    'fdr_pval_nonparametric': 0.018,
    'significant_parametric': True,     # uncorrected alpha=0.05
    'significant_nonparametric': True,
    'multiple_comparison': {'applied': False, 'reason': 'single_comparison_dual_report'},
    'mean_diff_ci': {'observed_mean_diff': ..., 'bootstrap_ci': (lo, hi)},
}
```

Family-wise FDR (units / channels / freqs / time):

```python
q = StatisticalAnalysis.fdr_correct(raw_p_values)  # Benjamini-Hochberg
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
Effect size: Cohen's d_pooled (independent) or Cohen's dz (paired); see `effect_size_name`

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

**This is a flat, ungrouped shuffle -- exchangeable only if `group1`/`group2` contain no
internal session/cycle/subject structure the test statistic depends on.** On this corpus that
is frequently false: sessions, temporal cycles, and subjects are real dependency structure, and
naively pooling+shuffling across them can manufacture false negatives or positives (see
`jnwb-functional-connectivity/SKILL.md`'s within-session-then-Clopper-Pearson design for the
correct pattern when session grouping matters). If your samples have grouping structure the
permutation null must respect, do NOT call this function directly on the pooled data -- use
`jnwb.permutation.permute_labels(y, groups=..., scheme="within_group", rng=...)` to build a
group-respecting null instead (added 2026-08-10 after `jnwb.omission_identity
.decode_identity_cycle_deconfound` shipped exactly this bug: grouped LOCO folds compared against
an ungrouped global-permutation null -- see
`artifacts/.lab/agent-harness-audit-20260810.json`).

## Test Selection Table

| Scenario              | Parametric        | Non-parametric    | Effect Size |
|-----------------------|-------------------|-------------------|-------------|
| 2 independent groups  | t-test            | Mann-Whitney U    | Cohen's d   |
| 2 paired groups       | paired t-test     | Wilcoxon          | Cohen's dz  |
| 3+ groups             | ANOVA             | Kruskal-Wallis    | eta²        |
| Correlation           | Pearson r         | Spearman rho      | R²          |
| Confidence interval   | t-based CI        | Bootstrap CI      | —           |
| Permutation           | —                 | Permutation test  | p-value     |

FDR correction: **Benjamini-Hochberg** via `fdr_correct(p_values)` across a
hypothesis family — **not** across the parametric/nonparametric pair from one comparison.

## Design Notes

- All random seeds fixed at **42** for reproducibility.
- Dual parametric + nonparametric results are exploratory dual reports.
- `significant_*` flags use uncorrected `pval < 0.05` for a single comparison.
- Deprecated `fdr_pval_*` keys mirror raw p-values; do not treat them as FDR.
- For publication families (many units/bins), call `fdr_correct` on the p-vector.
- `compare_groups` also returns `mean_diff_ci` (bootstrap CI on mean difference).

## 2D Spectrotemporal Grid FDR Correction
When executing comparisons across many time-frequency bins (e.g. 2D spectrogram heatmaps or LFP trace grids), executing multiple comparisons without correction creates false positives. Always flatten the 2D grid of p-values, apply Benjamini-Hochberg FDR correction, and reshape it back to mask the grid:

```python
import numpy as np
from jnwb import StatisticalAnalysis

# Shape: (n_frequencies, n_times)
p_grid = np.zeros((99, 100)) 

# ... compute raw p-values for all bins into p_grid ...

# Flatten the 2D array to correct across the entire Spectrotemporal family together
p_flat = p_grid.flatten()

# Apply Benjamini-Hochberg correction
rejected, p_adjusted = StatisticalAnalysis.fdr_correct(p_flat, alpha=0.05)

# Reshape back to the original 2D spectrotemporal grid shape
p_grid_adjusted = p_adjusted.reshape(p_grid.shape)
rejected_grid = rejected.reshape(p_grid.shape)

# Use rejected_grid mask to flat-line or mask non-significant pixels in plots
```

