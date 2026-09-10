# Common Mistakes

A guide for failure modes in neuronal data analysis, and how `jnwb` prevents them.

Every item corresponds to a real issue identified during the auditing of `jnwb`.

---

## 1. Averaging Decibels Instead of Power (Jensen's Inequality)

### The Mistake
Converting individual trials or channels to decibels ($10 \log_{10}(P / P_0)$) and then averaging the decibel values:

```python
# WRONG: Jensen's inequality error
db_trials = 10 * np.log10(power / baseline)
mean_db = np.mean(db_trials)  # Biased by individual trial noisiness!
```

Because the logarithm is strictly concave, Jensen's inequality guarantees:
$$\mathbb{E}[\log_{10}(X)] \le \log_{10}(\mathbb{E}[X])$$

Averaging decibels underestimates physical power and disproportionately weights noisy trials with near-zero baseline power, pulling the aggregate away from the true population effect.

### The Correct Pattern
Form the ratio on the linear power scale, aggregate the *ratios*, and take the logarithm **exactly once** at the very end:

```python
# CORRECT: Log-last rule via jnwb.aggregate_to_db
import jnwb

# Option A: Every unit/trial weighted equally
db_mean = jnwb.aggregate_to_db(power, baseline, how="mean_of_ratios", aggregate_over=0)

# Option B: Weighted by baseline power (conserves total physical energy)
db_weighted = jnwb.aggregate_to_db(power, baseline, how="ratio_of_means", aggregate_over=0)
```

`jnwb.aggregate_to_db` strictly enforces this: negative inputs raise an immediate error, preventing callers from accidentally passing decibels.

---

## 2. Inclusive Bin Boundaries Double-Counting Spikes

### The Mistake
Using right-closed or inclusive bin intervals $[t_k, t_{k+1}]$ when binning spikes across contiguous time windows:

```python
# WRONG: Spike at 100.0 ms falls into BOTH [0.0, 100.0] and [100.0, 200.0]
window_1 = (spikes >= 0.0) & (spikes <= 100.0)
window_2 = (spikes >= 100.0) & (spikes <= 200.0)
```

A spike landing precisely on the bin boundary ($t = 100.0\text{ ms}$) is counted twice, artificially inflating firing rates and distorting latency estimates.

### The Correct Pattern
Use uniform **right-open intervals** $[t_k, t_{k+1}) = [t_0 + k\Delta,\; t_0 + (k+1)\Delta)$:

```python
# CORRECT: jnwb.bin_spikes, jnwb.fires_in_window, and jnwb.rate_in_window
# Spikes at 100.0 ms are counted in window 2, never in window 1
rate_w1 = jnwb.rate_in_window(spikes, onset_s=0.0, window_ms=(0.0, 100.0))
rate_w2 = jnwb.rate_in_window(spikes, onset_s=0.0, window_ms=(100.0, 200.0))

# Or vectorized across multiple trials:
rates, centers = jnwb.bin_spikes(spikes_list, window=(0.0, 0.5), bin_size_ms=10.0, output="rate", return_centers=True)
```

---

## 3. Global Shuffling on Structured Trials (Exchangeability Violations)

### The Mistake
Using an unconstrained global permutation (`np.random.permutation(y)`) to construct a null distribution when data has hierarchical structure (e.g. repeated stimulus blocks, sessions, or animals):

```python
# WRONG: Breaks exchangeability when labels are correlated with session/cycle
y_null = np.random.permutation(y_true)
```

If class proportions vary across sessions or cycles, global shuffling destroys the covariance structure between trial covariates and labels, yielding an overly optimistic null distribution and severely inflated false positive rates ($p < 0.05$ under the null).

### The Correct Pattern
Permute labels **within each group independently**, preserving each block's internal marginal composition:

```python
# CORRECT: jnwb.permute_labels with explicit within_group scheme
rng = np.random.default_rng(42)
y_null = jnwb.permute_labels(
    y_true,
    groups=cycle_ids,
    scheme="within_group",
    rng=rng
)
```

`jnwb.permute_labels` requires an explicit `scheme` (`"within_group"` or `"global"`) and rejects implicit defaults.

---

## 4. Pre-Split Feature Scaling & Cross-Validation Leakage

### The Mistake
Normalizing (z-scoring) the entire feature matrix $X$ before partitioning into cross-validation folds:

```python
# WRONG: Information from test fold leaks into training normalization
from sklearn.preprocessing import StandardScaler
X_scaled = StandardScaler().fit_transform(X)

for train_idx, test_idx in kfold.split(X_scaled, y):
    clf.fit(X_scaled[train_idx], y[train_idx])
```

The mean and variance of held-out test trials leak into the training features, leading to overly optimistic cross-validation accuracy that collapses when tested on genuinely independent data.

### The Correct Pattern
Fit scalers and feature transformers strictly on training folds inside a `Pipeline`:

```python
# CORRECT: jnwb.nested_cv_linear_svm handles inner & outer CV without leakage
res = jnwb.nested_cv_linear_svm(X, labels, n_splits=5)
print("Unbiased Outer CV Accuracy:", res["accuracy"])
print("Fold Majority Baseline:", res["majority_baseline_accuracy"])
```

---

## 5. Conflating Hardware Channel ID with DataFrame Row Index

### The Mistake
Assuming that electrode channel IDs match DataFrame row indices:

```python
# WRONG: If electrodes_df was filtered or reset_index() was called,
# row 10 does not necessarily correspond to channel ID 10!
location = electrodes_df.loc[10, "location"]
```

In high-density probes where noisy or non-connected channels are removed, `electrodes_df` has non-contiguous channel IDs or a standard `0..N-1` `RangeIndex`. Looking up by integer index returns the wrong contact or throws a `KeyError`.

### The Correct Pattern
Use `jnwb`'s robust channel resolution functions, which prioritize explicit identifier columns (`channel_id`, `id`, `electrode_id`) before falling back to index lookup:

```python
# CORRECT: Robust addressing handles filtered, non-contiguous, or multi-area probes
area = jnwb.map_peak_channel_to_area(peak_channel_id=10, electrodes_df=electrodes_df)
layer = jnwb.classify_layer_from_depth(peak_channel_id=10, electrodes_df=electrodes_df)
```

---

## 6. Conflating Statistical Predictability with Physical Causality

### The Mistake
Interpreting Granger causality, Phase Slope Index (PSI), or Transfer Entropy (TE) as perturbational causal mechanisms:

$$\text{Association} \neq \text{Directionality} \neq \text{Causality}$$

- **Granger causality**: Evaluates whether past values of $X$ improve linear autoregressive prediction of $Y$. It can be confounded by unobserved common inputs or differing signal-to-noise ratios.
- **Phase Slope Index**: Quantifies whether phase differences between $X$ and $Y$ increase linearly with frequency (indicating a consistent time delay). It cannot rule out a common driver with asymmetric conduction delays.
- **Transfer Entropy**: Information-theoretic reduction in uncertainty of $Y$ given $X$'s past. Non-parametric, but still observational.

### The Correct Pattern
Report directed metrics as **statistical predictability** or **phase-lead asymmetries**, reserving causal claims for perturbation experiments (e.g. optogenetics, microstimulation, lesioning):

```python
# CORRECT: Explicit directional reporting
gc = jnwb.granger(x, y, order=10)
print(f"X -> Y log variance ratio: {gc.x_to_y:.4f} (p = {gc.p_x_to_y:.4f})")
print(f"Y -> X log variance ratio: {gc.y_to_x:.4f} (p = {gc.p_y_to_x:.4f})")
```

---

## 7. Misinterpreting Phase Slope Index on Narrowband Signals

### The Mistake
Interpreting a near-zero Phase Slope Index ($|z| < 2$) on a pure sinusoid or very narrowband signal as evidence of no directional lead:

```python
# TRAP (receipt, seed=42, n_surrogates=50): a 20 Hz sinusoid with 10 ms delay
# in a 19–21 Hz band gives net PSI = 0 and band z = nan (single frequency bin).
# The same delay on 15–30 Hz broadband noise gives net ≈ 0.93 and band z ≈ 9.8.
```

At a single discrete frequency $f_0$, a time delay $\Delta t$ and a constant phase offset $\Delta \phi = 2\pi f_0 \Delta t$ are indistinguishable. PSI requires phase information across **multiple neighboring frequency bins** to estimate a phase slope ($\frac{d\phi}{df}$).

### The Correct Pattern
Evaluate PSI over a broadband band with multiple frequency bins; inspect `per_band` and `spectrum` — not a single-bin z-score:

```python
import numpy as np
import jnwb

rng = np.random.default_rng(42)
fs = 1000.0
t = np.arange(2000) / fs
x = np.sin(2 * np.pi * 20 * t)
y = np.roll(x, int(0.01 * fs))  # 10 ms delay

psi_narrow = jnwb.phase_slope_index(x, y, fs=fs, bands=(19.0, 21.0), n_surrogates=50, seed=0)

noise_x = rng.normal(size=2000)
noise_y = np.roll(noise_x, int(0.01 * fs)) + 0.3 * rng.normal(size=2000)
psi_broad = jnwb.phase_slope_index(
    noise_x, noise_y, fs=fs, bands=(15.0, 30.0), n_surrogates=50, seed=0,
)

print("Narrow band net:", psi_narrow.net)          # ~0.0
print("Broad band net:", psi_broad.net)            # >> 0 for broadband noise + delay
print("Broad band z:", psi_broad.per_band["band"]["z"])
# Directional association only — not perturbational causality.
```

---

## 8. Ignoring Causal Filter Group Delay in Onset Latency

### The Mistake
Comparing onset latencies across frequency bands or conditions when different smoothing filters or filter orders were used:

```python
# TRAP: A causal exponential filter with tau=50 ms shifts the step response by ~35 ms!
# Interpreting t_observed = 85 ms as an 85 ms biological latency is erroneous.
```

A causal filter introduces a deterministic group delay:
- **Impulse response centroid (mean delay)**: $\bar{t} = \tau_{\text{ms}}$
- **Step response 50% amplitude rise delay**: $t_{50\%} = \tau_{\text{ms}} \ln(2) \approx 0.693 \cdot \tau_{\text{ms}}$
- **Step response 10% amplitude rise delay**: $t_{10\%} = \tau_{\text{ms}} \ln(1/0.9) \approx 0.105 \cdot \tau_{\text{ms}}$

$$t_{\text{observed}} = t_{\text{signal}} + t_{\text{filter}}(\tau, \Delta t)$$

### The Correct Pattern
1. Fix $\tau$ and $\Delta t$ uniformly across all conditions being compared.
2. Use causality-bounded parametric fitting (`jnwb.fit_exponential_onset`) which models $t_0$ as the true takeoff point rather than taking arbitrary threshold-crossing latencies.
3. Check `fit["bound_status"]` to confirm the estimate is not pinned to the outer parameter bounds.
