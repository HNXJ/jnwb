---
name: jnwb-spiking
description: Spike extraction, PSTH binning, physiological latency estimation, causal
  smoothing, and unit response classification.
---

# `jnwb-spiking` — Spike Dynamics, PSTH & Latency Estimation

## 1. Trigger
Activate this skill when computing spike rasters, PSTHs, causal firing rate smoothing, physiological onset latencies, or unit response significance.

## 2. Task-to-Primitive Routing Matrix
- `jnwb.raster_psth(st, onsets, win_ms, bin_ms)`: Compute trial-aligned PSTH and SEM firing rates in Hz.
- `jnwb.causal_exp_smooth(rate, bin_ms, tau_ms)`: Apply forward-only finite exponential smoothing kernel ($5\tau$) with zero future leakage.
- `jnwb.fit_exponential_onset(t_ms, rate, t0_bounds, tau_bounds)`: Grid-search + bounded nonlinear least-squares fit of onset latency $t_0$.
- `jnwb.compute_response_metrics(spikes, onsets, baseline_win, response_win)`: Compute baseline/response rates, modulation index, and z-score.
- `jnwb.classify_response_significance(spikes, onsets, baseline_win, response_win)`: Statistical classification of responsive units.
- `jnwb.phase_locking_index(spike_times, lfp_phase, lfp_times)`: Quantify spike-field phase synchronization.

## 3. Invariants & Safeguards
1. **Causal Filter Geometry**: Never use acausal Gaussian smoothing when estimating response latency. `causal_exp_smooth` strictly operates on past bins ($t \le t_0$).
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
fit = jnwb.fit_exponential_onset(time_bins, smooth_hz, t0_bounds=(0.0, 200.0))
```

## 5. Verification
- Check that synthetic step/ramp signals recover true $t_0$ within grid tolerance.
- Verify `causal_exp_smooth` impulse response is strictly zero for $t < 0$.

## 6. Canonical Documentation Links
- [`docs/06_spikes_psth_and_onset_dynamics.md`](../../docs/06_spikes_psth_and_onset_dynamics.md)
