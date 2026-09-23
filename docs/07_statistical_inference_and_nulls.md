# 07. Statistical Inference, Resampling & Null Hypothesis Modeling

This document details statistical inference, bootstrap confidence intervals, exchangeable label permutations, false discovery control, paired fire probability testing, and cycle detection in `jnwb`.

---

## 1. The `StatisticalAnalysis` Engine (`jnwb.statistics`)

`jnwb.statistics.StatisticalAnalysis` provides a unified interface for parametric, non-parametric, and resampling-based inference.

### Local RNG Injection & Global RNG Isolation

Resampling functions that draw take an optional `rng: np.random.Generator`. The exceptions
are `exploratory_compare` and `exploratory_correlate`, whose signatures carry no `rng` and
no `**kwargs`: passing one raises `TypeError`.

| Property | What it means |
|---|---|
| Isolated determinism | With `rng` omitted, the function builds its own `default_rng(42)`. Python's and NumPy's global RNG state is never read or mutated |
| Caller control | An independent `np.random.Generator` per worker makes parallel sweeps reproducible |
| Strict typing | A non-`Generator` object raises `TypeError` rather than being coerced |

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
# Exploratory dual comparison. No `rng` parameter exists on this one -- passing it
# raises TypeError. The bootstrap inside uses its own default_rng(42).
comparison = stats.exploratory_compare(
    group1,
    group2,
    paired=False,
    n_bootstrap=2000,
)
# Returns clean parametric ('parametric') and non-parametric ('non_parametric') metrics,
# alongside bootstrap mean difference confidence intervals.
```

### Benjamini-Hochberg FDR Control (`fdr_correct`)

For confirmatory hypothesis testing across cohorts of channels, frequency bins, or time lags, apply explicit FDR control:

```python
p_values = np.array([0.001, 0.004, 0.015, 0.048, 0.120])
q_values = stats.fdr_correct(p_values, method="bh")
```

### Exact Permutations & Combinatorial Attainable p-Value Floors

When analyzing paired session or unit differences where $N$ is small, asymptotic approximations fail and minimum attainable p-values are constrained by combinatorics:

```python
# Exact paired sign flip: full 2^N enumeration for N <= 20, Monte Carlo for N > 20
obs_mean, p_val, p_floor = jnwb.exact_sign_flip(paired_diffs, alternative="two-sided")

# Attainable minimal non-zero p-value floor for Mann-Whitney rank tests without ties
p_floor_mw = jnwb.mann_whitney_p_floor(n1=4, n2=6, alternative="two-sided")
# comb(10, 4) = 210 -> floor = 2 / 210 ~= 0.00952

# Exact Clopper-Pearson binomial confidence intervals via Beta quantiles
lo, hi = jnwb.clopper_pearson(k=7, n=10, alpha=0.05)
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

**What a significant cluster licenses.** The test controls the family-wise error rate over
the whole search, and the statement it supports is that the conditions differ *somewhere*
in the searched window. It does not license the cluster's own extent: its onset, its
offset, its peak and its width are not estimates with error bars, because the cluster was
defined by the same threshold that made it significant, and moving `threshold` moves all
four. Report the effect as present in the window, not as beginning at the cluster's first
sample.

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
    rng=42,
)
assert plan["scheme"] == "within_group"
assert plan["n_permutations"] == 1000
```

![Exchangeable Permutation Null Distribution](assets/figures/fig08_permutation_null.png)

That figure is a within-pair sign-flip null over 2000 draws, with the observed mean difference,
the 95th percentile and the $(1 + \Sigma)/(N + 1)$ p-value drawn on it. The exchangeability the
flips assume is what the plan above pins: a different grouping is a different null.

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
r2_ci = jnwb.shuffle_r2_ci(y_true, y_pred, groups=cycle_id, n_shuffle=200, rng=0)
assert "r2_observed" in r2_ci and "p_val" in r2_ci

# Cross-modal lag scan between aligned TFR and spike tensors. Both are reduced to a
# single series before the sweep, so TIME is the first axis: (n_times, n_trials).
tfr_data = np.random.default_rng(1).normal(size=(200, 4))
spike_data = np.random.default_rng(2).normal(size=(200, 4))
modal_res = jnwb.cross_modal_comparison(
    tfr_data, spike_data, lag_range_ms=(-100, 100), bin_ms=10.0, rng=0,
)
assert "correlation" in modal_res and "lag_ms" in modal_res
# rng seeds the circular-shift null behind lag_corrected_pvalue; without it that p moves
# from run to run, while lag_ms does not.
print(modal_res["lag_ms"], modal_res["lag_corrected_pvalue"])   # 100.0, 0.892
print(modal_res["warnings"])   # the lag window is wide for a 200-sample series
```

**The axis order, the sign of `lag_ms`, and which p-value to read.** This example used to
pass `(4, 200)` and call it `channels x time`. The reduction reads a 2-D array as
`(n_times, n_trials)`, so it produced a four-sample series, swept three lags, and returned
a correlation over four points; `lag_search_resolution_floor` was 0.75 and `warnings` said
so, and nothing on the page read either.

`lag_ms` is in milliseconds and is negative when the TFR/LFP signal leads spikes, positive
when it lags them; `lfp_leads_spikes` carries the same fact so the convention need not be
remembered. Read `lag_corrected_pvalue`, not `correlation['parametric']['pval']`: the
latter is the p at the winning lag and pays nothing for having searched the others. On
white noise over 101 lags it falls below 0.05 in 99.5% of runs. The inputs here *are*
independent white noise, and the corrected p is 0.892 -- the right answer, from the right
field.

## References

The methods on this page are cited in [References](references.md).
