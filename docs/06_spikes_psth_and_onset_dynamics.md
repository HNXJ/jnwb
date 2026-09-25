# 06. Spike Extraction, PSTH & Onset Dynamics

PSTHs, response metrics, spike-LFP phase locking, causal smoothing, onset fitting and population trajectories.

---

## 1. Spike Analysis, Response Metrics & Phase Locking (`jnwb.spiking`, `jnwb.viz`)

### Raster & PSTH Construction (`raster_psth`)

```python
import jnwb

# st: sorted spike times in seconds (float array)
# onsets: trial onset timestamps in seconds (float array)
# win_ms: (start_ms, end_ms) window relative to onset
# bin_ms: bin width in milliseconds
# Returns: (bin_centers_ms, mean_rate_hz, sem_rate_hz)
time_bins_ms, rate_hz, sem_hz = jnwb.raster_psth(
    st=spike_times_s,
    onsets=trial_onsets_s,
    win_ms=(-200.0, 600.0),
    bin_ms=10.0
)
```

![Spike Raster and PSTH](assets/figures/fig02_raster_psth.png#only-light)
![Spike Raster and PSTH](assets/figures/fig02_raster_psth.dark.png#only-dark)

Panel A of that figure is a synthetic raster over 30 trials and panel B is `jnwb.bin_spikes` on the same
spikes. Both panels share one time axis, so what the binning discards is read off the pair; the
bins are right-open, which is why a spike on a bin edge falls in the later bin.

### Response Metrics & Significance Classification

```python
# Returns baseline_rate, response_rate, response_count, response_zscore, latency
# and n_trials. The windows are in SECONDS, as their names say; raster_psth(win_ms=)
# above is in milliseconds, and both take a float 2-tuple, so the suffix is the
# only guard against a factor of 1000.
metrics = jnwb.compute_response_metrics(
    spike_times=spike_times_s,
    epoch_onsets=trial_onsets_s,
    baseline_window_s=(-0.2, 0.0),
    response_window_s=(0.0, 0.4),
)

# Classification consumes the metrics computed above -- not the spike times again.
# The two calls compose in one direction only: measure, then classify.
# zscore_threshold is the cutoff on the response z-score; 2.58 is the two-sided
# 99% cutoff, the equivalent of alpha = 0.01.
sig_result = jnwb.classify_response_significance(metrics, zscore_threshold=2.58)
print("Significant:", sig_result["is_significant"])
print("Approximate p-value:", sig_result["pvalue"])
# "undefined" means the baseline had no across-trial variance, so the z-score is
# NaN and no classification was made. It is not a weak response.
print("Confidence:", sig_result["confidence"])
```

### Spike-LFP Phase Locking (`phase_locking_index`)

Computes circular phase distribution, Rayleigh circular non-uniformity test, and descriptive peak-to-mean histogram contrast of spike occurrences relative to an LFP phase time series. Key `'pli'` is maintained strictly as a backwards-compatibility alias for `'peak_to_mean_contrast'`:

```python
pli_result = jnwb.phase_locking_index(
    unit_spike_times=spike_times_s,
    lfp_phase=lfp_instantaneous_phase,
    lfp_timestamps=lfp_times_s,
    n_bins=18
)
print("Peak-to-mean contrast:", pli_result["peak_to_mean_contrast"])
print("Preferred Phase (rad):", pli_result["preferred_phase"])
print("Rayleigh z:", pli_result["rayleigh_z"], "p-value:", pli_result["rayleigh_pvalue"])
```

### Pairwise Phase Consistency (`pairwise_phase_consistency`)
Unlike heuristic histogram contrast or PLV/PLI, which has substantial positive sample-size bias ($\mathbb{E}[\text{PLV}] \sim 1/\sqrt{N}$ under noise), Vinck et al. (2010)'s Pairwise Phase Consistency (PPC) is an asymptotically unbiased estimator of squared phase synchronization and is the **recommended estimator** for population and across-unit comparisons:

$$\text{PPC} = \frac{2}{N(N-1)} \sum_{j=1}^{N-1} \sum_{k=j+1}^N \cos(\theta_j - \theta_k)$$

```python
# phases: 1D array of spike phase angles in radians
ppc_val = jnwb.pairwise_phase_consistency(spike_phases_rad)
```

---

## 2. Smoothing: Causal vs. Acausal Profiles (`jnwb.onset_fitting`, `jnwb.spiking`)

### Symmetrical Acausal Smoothing (`gaussian_smooth_rate`)
For display PSTHs, firing rate profiles, and latent trajectories where temporal centering without phase delay is desired:

```python
# Symmetrical Gaussian smoothing (sigma_ms kernel standard deviation)
smooth_psth = jnwb.gaussian_smooth_rate(rate_hz, bin_ms=10.0, sigma_ms=20.0)
```

### The Causal Smoothing Invariant (`causal_exp_smooth`)
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

> **Hazard Warning**: Compare onsets only between traces smoothed with the same `tau_ms`. The delays above belong to a latency read as a threshold crossing on the smoothed trace, and only such a latency is corrected by them. A fitted $t_0$ is not a crossing: on a step response it is independent of $\tau$, and on a graded rise it moves with $\tau$ by an amount that depends on the rise, so no fixed correction applies. A difference between traces smoothed at different $\tau$, or between bandpass envelopes with different rise kinetics, is a difference between the filters.

---

## 3. Causality-Bounded Exponential Onset Fitting (`jnwb.onset_fitting`)

`jnwb.fit_exponential_onset` fits a parameterized rise model (`jnwb.onset_model`) to estimate the takeoff time $t_0$ of the trace it is given; on a smoothed trace with a graded rise, $t_0$ moves with `tau_ms`:

$$y(t) = \begin{cases} \text{baseline}, & t < t_0 \\ \text{baseline} + \text{amplitude} \cdot \left(1 - e^{-(t - t_0)/\tau}\right), & t \ge t_0 \end{cases}$$

```python
import jnwb

# t_ms: (n_times,) array of millisecond timestamps
# rate: (n_times,) PSTH firing rate in Hz
fit = jnwb.fit_exponential_onset(
    t_ms,
    rate,
    t0_bounds_ms=(0.0, 400.0),          # Physical causality boundaries
    baseline_window_ms=(-100.0, 0.0)    # Pre-stimulus baseline interval
)

print(f"Onset t0: {fit['t0']:.2f} ms")
print(f"Time constant tau: {fit['tau']:.2f} ms")
print(f"Amplitude: {fit['amplitude']:.2f} Hz")
print(f"Goodness-of-fit R2: {fit['r2']:.4f}")
print(f"Optimizer Bound Status: {fit['bound_status']}")
```

![Causal Exponential Smoothing and Onset Latency Fit](assets/figures/fig03_onset_fitting.png#only-light)
![Causal Exponential Smoothing and Onset Latency Fit](assets/figures/fig03_onset_fitting.dark.png#only-dark)

That figure draws one `jnwb.fit_exponential_onset` result over the causally smoothed synthetic rate it
was fitted to, with the recovered $t_0$ beside the ground-truth $t_0$ the signal was built from. The
gap between the two lines is the fit's bias on this rise; it depends on the rise as well as $\tau$, so it is not a filter delay to subtract.

### Boundary Status & Censoring Flags (`bound_status`)
When an onset lies outside the search interval (e.g. pre-stimulus noise or unconstrained drift), nonlinear least squares pins $t_0$ against the outer bounds while reporting `converged: True`. `bound_status` reports whether $t_0$ sits at an end of `t0_bounds_ms`. It checks $t_0$ alone: `tau`, `amplitude` and the quality of the fit do not enter it.

| `bound_status` Value | Interpretation | Inferential Action |
|----------------------|----------------|--------------------|
| `None` | $t_0$ is inside `t0_bounds_ms` | Read `r2` and `tau` before reporting $t_0$: a fit to a flat noise PSTH usually reads `None`, with `tau` at an end of `tau_bounds_ms` and `r2` near 0 |
| `"lower"` | Pinned at lower boundary ($t_0 \approx t_0^{\text{lo}}$) | Flagged as censored; pre-stimulus noise |
| `"upper"` | Pinned at upper boundary ($t_0 \approx t_0^{\text{hi}}$) | Flagged as censored; non-responsive or late excursion |

---

## 4. Population State-Space Trajectories (`jnwb.trajectory`)

`jnwb.trajectory` projects multi-unit population activity across time into low-dimensional latent state spaces:

```python
import jnwb

# Both functions read the session themselves. They take the same three inputs --
# an open session, an area, and a trial table -- and neither consumes the other's
# output; `compute_population_trajectory` is not `build_time_resolved_matrix`
# followed by PCA on the returned matrix.

# Assemble the time-resolved population tensor: (n_trials, n_units, n_bins)
X, unit_ids, bin_centers = jnwb.build_time_resolved_matrix(
    session, area="V1", epochs_df=trials_df,
)

# Low-dimensional population trajectory, from the same three inputs.
# Returns a dict: trajectory (n_trials, n_components, n_bins), explained_variance,
# unit_ids, bin_centers.
trajectory_res = jnwb.compute_population_trajectory(
    session, area="V1", epochs_df=trials_df, n_components=3,
)
```
