---
name: jnwb-spiking
description: Spike extraction, PSTH binning, physiological latency estimation, causal
  smoothing, and unit response classification.
---

# `jnwb-spiking` — Spike Dynamics, PSTH & Latency Estimation

## 1. Trigger
Activate this skill when computing spike rasters, PSTHs, causal firing rate smoothing, physiological onset latencies, or unit response significance.

## 2. Task-to-Operation Routing Matrix
- `jnwb.raster_psth(st, onsets, win_ms, bin_ms)`: Compute trial-aligned PSTH and SEM firing rates in Hz.
- `jnwb.causal_exp_smooth(rate, bin_ms, tau_ms)`: Apply forward-only finite exponential smoothing kernel ($5\tau$) with zero future leakage.
- `jnwb.fit_exponential_onset(t_ms, rate, t0_bounds_ms=None, tau_bounds_ms=None)`: Grid-search + bounded nonlinear least-squares fit of onset latency $t_0$.
- `jnwb.compute_response_metrics(spike_times, epoch_onsets, baseline_window=..., response_window=...)`: Baseline/response rates, modulation index, and z-score.
- `jnwb.classify_response_significance(metrics, zscore_threshold=1.96)`: Significance classification from precomputed response metrics.
- `jnwb.phase_locking_index(unit_spike_times, lfp_phase, lfp_timestamps, n_bins=18)`: Spike-field phase locking index.

- `jnwb.bin_spikes(spike_times, window_s=None, bin_size_ms=10.0, trial_starts=None, output="count", return_centers=False)`, `jnwb.fires_in_window(spike_times, onset_s, window_ms)`, `jnwb.rate_in_window(spike_times, onset_s, window_ms)` and `jnwb.fire_indicator(spike_times, onsets_s, window_ms)`: The half-open binning family. Every window is `[start, end)`, so a spike on a boundary belongs to exactly one bin and adjacent windows cannot both count it -- the double count `docs/common_mistakes.md` section 2 exists for. Use these rather than open-ended comparisons.

- `jnwb.gaussian_smooth_rate(rate, bin_ms, sigma_ms=20.0, axis=-1)`: Symmetrical **acausal** Gaussian smoothing of a binned rate. It moves signal backwards in time, so never measure an onset latency on a smoothed trace -- fit the unsmoothed rate.
- `jnwb.onset_model(t, t0, tau, amplitude, baseline)`: The model `fit_exponential_onset` fits, defined in `docs/06_spikes_psth_and_onset_dynamics.md`. Use it to draw a fit, not to estimate one.

## 3. Invariants & Safeguards
1. **Causal Filter Geometry**: Never use acausal Gaussian smoothing when estimating response latency. `causal_exp_smooth` strictly operates on past bins ($t \le t_0$).
1b. **The filter delay belongs to a threshold crossing**: `causal_exp_smooth` leaks nothing from the future, but it holds the smoothed trace below the level the raw trace has already reached. Subtract the filter delay only from a latency read as a threshold crossing on the smoothed trace. `jnwb.fit_exponential_onset`, which is the operation this skill routes onsets to, is not a threshold crossing -- it fits $t_0$ as the takeoff parameter of `onset_model` -- so no filter delay is subtracted from its $t_0$. Sweep `tau_ms` to tell the two readouts apart: on a 1 ms unit step at $t_0 = 100$ ms the half-amplitude crossing lands $+6$ ms late at `tau_ms=10`, $+17$ ms at `tau_ms=25`, $+34$ ms at `tau_ms=50` and $+68$ ms at `tau_ms=100`, tracking the filter at about $\tau\ln 2$, while the fitted $t_0$ on that step holds a $\tau$-invariant $-0.9$ ms that follows `bin_ms` instead. That invariance belongs to the step response: on a graded rise the smoothed trace no longer has the model's shape, and the fitted $t_0$ moves with `tau_ms` by an amount that depends on the rise as well as the filter, so no fixed correction removes it. Hold `tau_ms` fixed across every condition and band being compared, for either readout; a latency difference between two traces smoothed at different `tau_ms` is a difference between the filters. `docs/common_mistakes.md` section 8 gives the 10% and centroid delays.
2. **Onset Bound Checking**: Inspect `fit['bound_status']`. If $t_0$ reaches bounds (`'lower'` or `'upper'`), mark as censored/boundary-constrained; do not report as interior physiological onset.
3. **Time Base Units**: `st` and `onsets` are in seconds; `win_ms`, `bin_ms`, and `tau_ms` are in milliseconds.

## 4. Minimal Workflow
```python
import jnwb
import numpy as np

rng = np.random.default_rng(42)
spikes = np.sort(rng.uniform(0.0, 10.0, 100))
events = np.array([1.0, 3.0, 5.0, 7.0])

time_bins, rate_hz, sem_hz = jnwb.raster_psth(spikes, events, win_ms=(-100.0, 400.0), bin_ms=10.0)
smooth_hz = jnwb.causal_exp_smooth(rate_hz, bin_ms=10.0, tau_ms=25.0)
fit = jnwb.fit_exponential_onset(time_bins, smooth_hz, t0_bounds_ms=(0.0, 200.0))
```

## 5. Verification
- Check that synthetic step/ramp signals recover true $t_0$ within grid tolerance.
- Verify `causal_exp_smooth` impulse response is strictly zero for $t < 0$.

## 6. Canonical Documentation Links
- [`docs/06_spikes_psth_and_onset_dynamics.md`](../../docs/06_spikes_psth_and_onset_dynamics.md)
