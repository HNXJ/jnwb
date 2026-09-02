---
name: jnwb
description: Generic Python library for high-density electrophysiology, time-frequency analysis, and statistical neuroscience on NWB files.
---

# `jnwb` — Generic Electrophysiology & Statistical Neuroscience Library

`jnwb` is a generic, dataset-agnostic Python library for processing, analyzing, and visualizing extracellular electrophysiology, Local Field Potentials (LFP), spike trains, and behavioral covariates stored in Neurodata Without Borders (NWB) formats.

---

## 1. Quick Import & Architecture

```python
import jnwb
import numpy as np
import pandas as pd
```

All 101 core scientific functions and classes are exposed directly at the top-level `jnwb` namespace.

---

## 2. Core Functional Modules

### A. Time-Frequency Representations & Wavelets (`jnwb.complex_tfr`)

Computes complex Morlet wavelet coefficients with discrete $L_1$ amplitude normalization:

```python
# data: (n_channels, n_times) or (n_times,)
freqs = np.linspace(10.0, 60.0, 11)  # 10 to 60 Hz in 5 Hz bins

tfr_res = jnwb.complex_tfr(
    data=raw_lfp,
    fs=1000.0,
    freqs=freqs,
    n_cycles=5.0,              # scalar or array of cycles per frequency
    time_axis=-1,              # arbitrary axis supported
    normalization="amplitude"  # unit cosine yields peak |z| = 1.0
)

# Returns ComplexTFR dataclass:
# - tfr_res.z: np.ndarray, complex (n_channels, n_freqs, n_times)
# - tfr_res.coi_mask: np.ndarray, bool (n_channels, n_freqs, n_times)
# - tfr_res.power: np.ndarray, float (|z|^2)
# - tfr_res.phase: np.ndarray, float (radians in [-pi, pi])
# - tfr_res.amplitude: np.ndarray, float (|z|)
```

### B. Streaming TFR Accumulation (`jnwb.TFRAccumulator`)

Accumulates Welford running sums and cross-trial statistics without storing full trial tensors in RAM:

```python
acc = jnwb.TFRAccumulator(shape=(n_channels, len(freqs), n_times))

for trial_lfp in lfp_stream:
    tfr = jnwb.complex_tfr(trial_lfp, fs=1000.0, freqs=freqs)
    acc.add_trial(tfr.z, valid=tfr.coi_mask)

mean_power = acc.power()       # Welford arithmetic mean of power
itc = acc.itc()                # Inter-Trial Coherence (phase-locking across trials)
evoked = acc.evoked()          # Evoked power |mean(z)|^2
induced = acc.induced()        # Induced power: mean(power) - evoked
```

### C. Spikes, PSTH & Onset Dynamics (`jnwb.spiking`, `jnwb.onset_fitting`)

```python
# Compute raster PSTH
time_bins, mean_rate, sem_rate = jnwb.raster_psth(
    spike_times=unit_spikes,
    event_onsets=stim_onsets,
    win_ms=(-100.0, 500.0),
    bin_ms=10.0
)

# Causal exponential smoothing (tau_ms delay compensation)
smooth_rate = jnwb.causal_exp_smooth(mean_rate, bin_ms=10.0, tau_ms=30.0)

# Single-unit exponential onset latency fitting
fit = jnwb.fit_exponential_onset(time_bins, smooth_rate, t0_bounds=(0.0, 200.0))
# fit["t0"]: onset latency in ms
# fit["bound_status"]: "interior" | "lower_bound" | "upper_bound"
```

### D. Resampling Statistics & Hypothesis Testing (`jnwb.statistics`, `jnwb.permutation`)

```python
# Nonparametric bootstrap confidence interval
boot = jnwb.StatisticalAnalysis.bootstrap_ci(
    data,
    n_bootstrap=1000,
    rng=np.random.default_rng(42)
)

# Label permutation
shuffled_labels = jnwb.permute_labels(
    labels,
    scheme="global",  # or "within_group"
    rng=np.random.default_rng(42)
)

# Clean exploratory dual comparison
report = jnwb.exploratory_compare(group_a, group_b)
```

### E. Directed Connectivity & Information (`jnwb.connectivity`)

```python
# Bivariate Granger causality with surrogate testing
g_res = jnwb.granger(sig_x, sig_y, order=2, n_surrogates=100, seed=42)

# Phase Slope Index (PSI)
psi_val = jnwb.phase_slope_index(sig_x, sig_y, fs=1000.0, freq_range=(15.0, 30.0))

# Transfer entropy
te_res = jnwb.transfer_entropy(sig_x, sig_y, k=1, l=1, n_surrogates=50, seed=42)
```

### F. Population Decoding (`jnwb.decoding`)

```python
# Nested Cross-Validation Linear SVM
results = jnwb.nested_cv_linear_svm(
    X=feature_matrix,      # (n_trials, n_features)
    y=condition_labels,    # (n_trials,)
    n_splits=5,
    c_values=(0.01, 0.1, 1.0, 10.0),
    random_state=42
)
accuracy = results["accuracy"]
confusion = results["confusion_matrix"]
```

### G. Artifact Detection & Repair (`jnwb.artifact_detection`, `jnwb.artifact_repair`)

```python
# Multichannel correlation matrix and outlier channel detection
corr_mat = jnwb.channel_correlation_matrix(multichannel_lfp)
bad_channels = jnwb.detect_flat_or_noisy_channels(multichannel_lfp)

# Coordinate-free cross-channel linear interpolation repair
repaired_lfp, frac_repaired, diag = jnwb.repair_lfp_trials(
    lfp_trials,
    threshold_sd=4.0
)
```

### H. Anatomical Addressing & Standardization (`jnwb.addressing`, `jnwb.ontology`)

```python
# Map peak recording channel to brain area from electrodes DataFrame
area_name = jnwb.map_peak_channel_to_area(peak_channel_id, electrodes_df)
canonical_area = jnwb.canonicalize_area_name(area_name)
```

### I. Publication Vector Graphics (`jnwb.viz`)

```python
# Setup editable typography for SVG/PDF publication export
jnwb.setup_vector_graphics()

# Apply tight margins avoiding unnecessary white space
jnwb.apply_tight_auto_axis(ax, x_span=(0.0, 500.0), y_margin=0.08)

# Save multi-page / multi-format suite
jnwb.save_figure_suite(fig, output_stem="fig01_psth_dynamics", formats=("svg", "png", "pdf"))
```
