# 07. Statistical Inference, Resampling & Null Hypothesis Modeling

This document details statistical inference, bootstrap confidence intervals, exchangeable label permutations, false discovery control, and paired fire probability testing in `jnwb`.

---

## 1. The `StatisticalAnalysis` Engine (`jnwb/statistics.py`)

`jnwb.statistics.StatisticalAnalysis` provides a unified interface for parametric, non-parametric, and resampling-based inference.

### Local RNG Injection & Global RNG Isolation
All statistical resampling functions accept an optional `rng: np.random.Generator`.
- **Isolated Determinism**: By default, functions use an internal generator (`default_rng(42)`) to ensure historical repeatability without mutating Python or NumPy global RNG state.
- **Caller Control**: Callers can supply independent `np.random.Generator` streams for parallel sweeps.
- **Strict Typing**: Supplying a non-`Generator` object raises an explicit `TypeError`.

```python
import numpy as np
from jnwb.statistics import StatisticalAnalysis as stats

# Supply an independent, caller-controlled local Generator
custom_rng = np.random.default_rng(12345)

# Bootstrap Confidence Intervals
boot_res = stats.bootstrap_ci(
    data,
    statistic_func=np.mean,
    n_bootstrap=5000,
    ci=0.95,
    rng=custom_rng
)
print("Bootstrap 95% CI:", boot_res["bootstrap_ci"])
print("Bootstrap Std Error:", boot_res["bootstrap_std"])

# Two-Sample Permutation Test
perm_res = stats.permutation_test(
    group_a,
    group_b,
    n_permutations=5000,
    rng=custom_rng
)
print("Permutation p-value:", perm_res["pval"])
```

---

## 2. Group Comparisons & Exploratory vs. Confirmatory Dual Reporting

`StatisticalAnalysis.compare_groups` computes both parametric ($t$-test) and non-parametric (Mann-Whitney $U$ / Wilcoxon signed-rank) metrics alongside bootstrap mean-difference confidence intervals:

```python
comparison = stats.compare_groups(
    group1,
    group2,
    paired=False,
    n_bootstrap=2000,
    rng=custom_rng
)
# Returns:
# - t_stat, p_parametric
# - u_stat / wilcoxon_stat, p_nonparametric
# - mean_diff, mean_diff_ci (bootstrap 95% CI of the difference)
```

---

## 3. False Discovery Rate (FDR) Control

`StatisticalAnalysis.fdr_correct` adjusts p-values for multiple comparisons across channels, frequency bins, or time lags using the Benjamini-Hochberg (BH) procedure:

```python
p_values = np.array([0.001, 0.004, 0.015, 0.048, 0.120])
significant_mask, p_adjusted = stats.fdr_correct(p_values, alpha=0.05, method="bh")
```

---

## 4. Exchangeable Label Permutation Schemes (`jnwb/permutation.py`)

### The Grouped Exchangeability Invariant
When decoding stimulus conditions across sessions, recording blocks, or behavioral cycles, naive shuffling across the whole array violates exchangeability (known as the *cross-session leakage defect*).

`jnwb.permute_labels` requires callers to explicitly specify the permutation `scheme`:

```python
import jnwb

labels = np.array(["A", "B", "A", "B", "A", "B"])
cycle_id = np.array([1, 1, 2, 2, 3, 3])

# Within-group exchangeability: shuffles labels ONLY within each cycle/block
null_labels = jnwb.permute_labels(
    labels,
    groups=cycle_id,
    scheme="within_group",
    rng=custom_rng
)
```

| Permutation Scheme | Requirement | Valid Application |
|--------------------|-------------|-------------------|
| `"within_group"` | `groups` array mandatory | Block-randomized designs, multi-session decoding, sequence cycles |
| `"global"` | Permutes across all rows | Uniform, independent, identically distributed trials |

---

## 5. Paired Fire Probability Testing & Shuffle Nulls

For binary spike-occurrence analyses (evaluating whether a neuron fires at least one spike in an active window compared to a baseline window on the same trial):

```python
# fired_target: (n_trials,) boolean indicator array
# fired_baseline: (n_trials,) boolean indicator array
res = jnwb.paired_fire_prob_test(
    fired_target,
    fired_baseline,
    n_shuffles=2000,
    n_bootstrap=2000,
    rng=custom_rng
)
print("Odds Ratio:", res["odds_ratio"])
print("Shuffle Null p-value:", res["p_value"])
print("Odds Ratio 95% CI:", res["odds_ratio_ci"])
```
