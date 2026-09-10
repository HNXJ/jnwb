# 07. Statistical Inference, Resampling & Null Hypothesis Modeling

This document details statistical inference, bootstrap confidence intervals, exchangeable label permutations, false discovery control, paired fire probability testing, and cycle detection in `jnwb`.

---

## 1. The `StatisticalAnalysis` Engine (`jnwb.statistics`)

`jnwb.statistics.StatisticalAnalysis` provides a unified interface for parametric, non-parametric, and resampling-based inference.

### Local RNG Injection & Global RNG Isolation
All statistical resampling functions accept an optional `rng: np.random.Generator`.
- **Isolated Determinism**: By default, functions instantiate an internal generator (`default_rng(42)`) to ensure repeatable outputs without mutating Python or NumPy global RNG state.
- **Caller Control**: Callers can supply independent `np.random.Generator` streams for parallel sweeps.
- **Strict Typing**: Supplying a non-`Generator` object raises an explicit `TypeError`.

```python
import numpy as np
from jnwb import StatisticalAnalysis as stats

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

## 2. Group Comparisons & False Discovery Rate (FDR) Control

### Exploratory vs Confirmatory Comparisons

`StatisticalAnalysis.exploratory_compare` and `StatisticalAnalysis.exploratory_correlate` compute unadjusted dual parametric and non-parametric statistics for exploratory screening without FDR theatre:

```python
# Exploratory dual comparison
comparison = stats.exploratory_compare(
    group1,
    group2,
    paired=False,
    n_bootstrap=2000,
    rng=custom_rng
)
# Returns clean parametric ('parametric') and non-parametric ('non_parametric') metrics,
# alongside bootstrap mean difference confidence intervals.
```

### Benjamini-Hochberg FDR Control (`fdr_correct`)

For confirmatory hypothesis testing across cohorts of channels, frequency bins, or time lags, apply explicit FDR control:

```python
p_values = np.array([0.001, 0.004, 0.015, 0.048, 0.120])
significant_mask, p_adjusted = stats.fdr_correct(p_values, alpha=0.05, method="bh")
```

---

## 3. Standalone Rate Extraction & Paired Binary Fire Probability

`jnwb` exports top-level standalone statistical functions:

```python
import jnwb

# Fast spike count windowing
spike_rate = jnwb.rate_in_window(spike_times, onset_s=10.5, window_ms=(0.0, 150.0))

# Binary fire indicator (True if >= 1 spike in window)
has_fired = jnwb.fires_in_window(spike_times, onset_s=10.5, window_ms=(0.0, 150.0))
fired_array = jnwb.fire_indicator(spike_times, onsets_array, window_ms=(0.0, 150.0))

# Paired fire probability test
fire_test = jnwb.paired_fire_prob_test(
    fires_target=fired_target,
    fires_null=fired_baseline,
    n_shuffles=2000,
    n_bootstrap=2000,
    rng=custom_rng
)
print("Odds Ratio:", fire_test["odds_ratio"])
print("Shuffle p-value:", fire_test["p_value_fire_shuffle"])
```

### Fast Paired & Unpaired Shuffle p-values

```python
# Paired shuffle test
diff, p_val = jnwb.shuffle_pvalue_paired(a, b, n_shuffles=5000, rng=custom_rng)

# Unpaired shuffle test
diff, p_val_unpaired = jnwb.shuffle_pvalue_unpaired(a, b, n_shuffles=5000, rng=custom_rng)
```

### Cluster-Based Permutation Testing (`cluster_permutation_test`)

For continuous time series, spectra, and time-frequency representations (TFRs), mass-univariate testing creates severe multiple testing problems. `jnwb.cluster_permutation_test` implements Maris & Oostenveld (2007) non-parametric cluster-based permutation testing with maximum-cluster FWER control and exact finite Monte Carlo p-values:

$$p = \frac{1 + k}{B + 1}$$

```python
# X, Y: (n_trials, n_freqs, n_times) or (n_trials, n_times)
# 1. Paired differences (sign-flip exchangeability)
res_paired = jnwb.cluster_permutation_test(
    X, Y,
    paired=True,
    threshold=2.5,        # Point-wise t-statistic threshold for cluster formation
    n_permutations=1000,  # Monte Carlo permutations
    tail="both",          # "both", "greater", or "less"
    rng=custom_rng
)

# 2. Independent groups with within-session exchangeability restriction
# (prevents false discoveries caused by session baseline differences)
res_grouped = jnwb.cluster_permutation_test(
    X, Y,
    paired=False,
    groups=(session_X, session_Y),
    scheme="within_group",
    threshold=2.5,
    n_permutations=1000,
    rng=custom_rng
)

print(f"Identified {len(res_grouped['clusters'])} clusters.")
for c in res_grouped["clusters"]:
    print(f"Cluster mass: {c['statistic']:.2f}, p-value: {c['p_value']:.4f}")
```

---

## 4. Exchangeable Label Permutation Schemes (`jnwb.permutation`)

### The Grouped Exchangeability Invariant
When decoding stimulus conditions across sessions, recording blocks, or behavioral cycles, naive shuffling across the whole array violates exchangeability.

`jnwb.permute_labels` requires callers to explicitly specify the permutation `scheme`:

```python
import numpy as np
import jnwb

custom_rng = np.random.default_rng(12345)
labels = np.array(["A", "B", "A", "B", "A", "B"])
cycle_id = np.array([1, 1, 2, 2, 3, 3])

# Within-group exchangeability: shuffles labels ONLY within each cycle/block
null_labels = jnwb.permute_labels(
    labels,
    groups=cycle_id,
    scheme="within_group",
    rng=custom_rng,
)

# Pre-build permutation plan (within-group scheme only; returns draw manifest + seed)
plan = jnwb.build_permutation_plan(
    labels,
    cycle_id,
    n_permutations=1000,
    seed=42,
)
assert plan["scheme"] == "within_group"
assert plan["n_permutations"] == 1000
```

![Exchangeable Permutation Null Distribution](assets/figures/fig08_permutation_null.png)

---

## 5. Trial Cycle Detection, Subblock Stratification & Cross-Modal Comparison

```python
import pandas as pd

epochs_df = pd.DataFrame({"start_time": np.linspace(0.0, 40.0, 20)})

# Detect temporal clusters from inter-trial gaps (returns cycle id per row)
cycle_labels = jnwb.detect_trial_cycles(epochs_df, gap_factor=10.0)

# Assign temporal quantile buckets 0..n_quantiles-1 by start_time order
quartiles = jnwb.assign_subblock_quartiles(epochs_df, n_quantiles=4)

y_true = np.linspace(0.0, 1.0, 6)
y_pred = y_true + 0.05 * np.random.default_rng(0).normal(size=6)
r2_ci = jnwb.shuffle_r2_ci(y_true, y_pred, groups=cycle_id, n_shuffle=200, random_state=0)
assert "r2_observed" in r2_ci and "p_val" in r2_ci

# Cross-modal lag scan between aligned TFR and spike tensors (channels x time)
tfr_data = np.random.default_rng(1).normal(size=(4, 200))
spike_data = np.random.default_rng(2).normal(size=(4, 200))
modal_res = jnwb.cross_modal_comparison(
    tfr_data, spike_data, lag_range_ms=(-100, 100), bin_ms=10.0,
)
assert "correlation" in modal_res and "lag_ms" in modal_res
```

## References

The methods on this page are cited in [References](references.md).
