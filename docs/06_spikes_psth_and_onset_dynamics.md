# 06. Spike Extraction, PSTH & Onset Dynamics

This document details spike rate extraction, Peristimulus Time Histogram (PSTH) generation, response significance classification, spike-LFP phase locking, causal smoothing latency physics, causality-bounded exponential onset fitting, and neural population trajectories in `jnwb`.

---

## 1. Spike Analysis, Response Metrics & Phase Locking (`jnwb.spiking`, `jnwb.viz`)

`jnwb.spiking` and `jnwb.viz` provide fast, vectorized operations for binning spike timestamps, computing response metrics, and analyzing spike-LFP phase alignment.

### Raster & PSTH Construction (`raster_psth`)

```python
import jnwb

# st: sorted spike times in seconds (float array)
# onsets: trial onset timestamps in seconds (float array)
# win_ms: (start_ms, end_ms) window relative to onset
# bin_ms: bin width in milliseconds
time_bins_ms, rate_hz = jnwb.raster_psth(
    st=spike_times_s,
    onsets=trial_onsets_s,
    win_ms=(-200.0, 600.0),
    bin_ms=10.0
)
```

### Response Metrics & Significance Classification

```python
# Compute peak firing rate, baseline rate, modulation index, and latency
metrics = jnwb.compute_response_metrics(
    spike_times=spike_times_s,
    event_onsets=trial_onsets_s,
    baseline_window=(-0.2, 0.0),
    response_window=(0.0, 0.4)
)

# Classify whether unit shows statistically significant increase or decrease
sig_result = jnwb.classify_response_significance(
    spike_times=spike_times_s,
    event_onsets=trial_onsets_s,
    baseline_window=(-0.2, 0.0),
    response_window=(0.0, 0.4),
    alpha=0.01
)
print("Is responsive:", sig_result["is_responsive"])
print("Modulation direction:", sig_result["direction"])
```

### Spike-LFP Phase Locking (`phase_locking_index`)

Computes the Phase-Locking Value (PLV) and circular phase distribution of spike occurrences relative to an LFP phase time series:

```python
pli_result = jnwb.phase_locking_index(
    unit_spike_times=spike_times_s,
    lfp_phase=lfp_instantaneous_phase,
    lfp_timestamps=lfp_times_s,
    n_bins=18
)
print("Phase Locking Value (PLV):", pli_result["plv"])
print("Preferred Phase (rad):", pli_result["preferred_phase"])
```

---

## 2. Causal Exponential Smoothing & Estimator Latency (`jnwb.onset_fitting`)

### The Causal Smoothing Invariant
To determine response onset latency accurately, smoothing must be strictly **causal (forward-only)**. Centered (Gaussian or acausal boxcar) filters propagate future post-stimulus spikes backward in time, artificially shifting the apparent onset earlier than physical reality.

```python
# Causal forward-only exponential smoothing
smoothed_rate = jnwb.causal_exp_smooth(rate_hz, bin_ms=5.0, tau_ms=30.0)
```

### Mathematical Latency Properties & Hazards
A causal filter introduces an inherent, deterministic time delay:
1. **Impulse Response Centroid (Mean Delay)**:
   $$\bar{t} = \int_0^\infty t \cdot \frac{1}{\tau} e^{-t/\tau} dt \approx \tau_{\text{ms}}$$
2. **Step Response 50% Amplitude Rise Delay**:
   $$t_{50\%} = \tau_{\text{ms}} \cdot \ln(2) \approx 0.693 \cdot \tau_{\text{ms}}$$
3. **Step Response 10% Amplitude Rise Delay**:
   $$t_{10\%} = \tau_{\text{ms}} \cdot \ln\left(\frac{1}{0.9}\right) \approx 0.105 \cdot \tau_{\text{ms}}$$

$$t_{\text{observed}} = t_{\text{signal}} + t_{\text{estimator}}(\tau, \Delta t)$$

> **Hazard Warning**: Never interpret cross-band or cross-area onset latency differences as biological timing differences without accounting for estimator group delay, especially if different $\tau$ values or varying bandpass filter kinetics are involved.

---

## 3. Causality-Bounded Exponential Onset Fitting (`jnwb.onset_fitting`)

`jnwb.fit_exponential_onset` fits a parameterized rise model (`jnwb.onset_model`) to estimate the true physical takeoff time $t_0$:

$$y(t) = \begin{cases} \text{baseline}, & t < t_0 \\ \text{baseline} + \text{amplitude} \cdot \left(1 - e^{-(t - t_0)/\tau}\right), & t \ge t_0 \end{cases}$$

```python
import jnwb

# t_ms: (n_times,) array of millisecond timestamps
# rate: (n_times,) PSTH firing rate in Hz
fit = jnwb.fit_exponential_onset(
    t_ms,
    rate,
    t0_bounds=(0.0, 400.0),          # Physical causality boundaries
    baseline_window=(-100.0, 0.0)    # Pre-stimulus baseline interval
)

print(f"Onset t0: {fit['t0']:.2f} ms")
print(f"Time constant tau: {fit['tau']:.2f} ms")
print(f"Amplitude: {fit['amplitude']:.2f} Hz")
print(f"Goodness-of-fit R2: {fit['r2']:.4f}")
print(f"Optimizer Bound Status: {fit['bound_status']}")
```

### Boundary Status & Censoring Flags (`bound_status`)
When an onset lies outside the search interval (e.g. pre-stimulus noise or unconstrained drift), nonlinear least squares pins $t_0$ against the outer bounds while reporting `converged: True`. `jnwb` reports `bound_status` to distinguish unconstrained interior fits from boundary-censored solutions:

| `bound_status` Value | Interpretation | Inferential Action |
|----------------------|----------------|--------------------|
| `None` | Unconstrained interior solution | Valid unconstrained onset estimate |
| `"lower"` | Pinned at lower boundary ($t_0 \approx t_0^{\text{lo}}$) | Flagged as censored; pre-stimulus noise |
| `"upper"` | Pinned at upper boundary ($t_0 \approx t_0^{\text{hi}}$) | Flagged as censored; non-responsive or late excursion |

---

## 4. Population State-Space Trajectories (`jnwb.trajectory`)

`jnwb.trajectory` projects multi-unit population activity across time into low-dimensional latent state spaces:

```python
import jnwb

# spike_matrices: Dict[unit_id -> (n_trials, n_times)]
# Assemble time-resolved population matrix: (n_trials * n_times, n_units)
matrix, metadata = jnwb.build_time_resolved_matrix(spike_matrices)

# Compute low-dimensional population trajectory (e.g. Top 3 Principal Components)
trajectory_res = jnwb.compute_population_trajectory(matrix, n_components=3)
```
