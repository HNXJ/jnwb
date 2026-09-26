# Recipes

One call per common operation, on synthetic arrays, so the block below runs as written after
`pip install jnwb`. Loading from an NWB file is on [Paths & Addressing](02_paths_addressing_metadata.md)
and artifact repair on [Artifact Detection & Repair](05_artifact_detection_and_repair.md).

```python
import numpy as np
import jnwb

rng = np.random.default_rng(0)
fs = 1000.0

# Synthetic inputs, so every call below runs as written.
spike_times = np.sort(rng.uniform(0.0, 20.0, 4000))          # s
event_onsets = np.arange(1.0, 19.0, 0.5)                     # s
lfp = rng.normal(size=4000)                                  # one channel, n_times
baseline_lfp = rng.normal(size=4000)
lfp_trials = rng.normal(size=(20, 4000))                     # trials x time
baseline_trials = rng.normal(size=(20, 4000))
lfp_ch = rng.normal(size=(8, 4000))                          # channels x time
x, y = rng.normal(size=2000), rng.normal(size=2000)
g1, g2 = rng.normal(0.0, 1.0, 40), rng.normal(0.5, 1.0, 40)
p_values = rng.uniform(0.0, 1.0, 10)

# Spikes: PSTH (times in s, window in ms), causal smoothing, onset fit
t_ms, rate, sem = jnwb.raster_psth(spike_times, event_onsets, win_ms=(-200.0, 500.0), bin_ms=10.0)
smooth = jnwb.causal_exp_smooth(rate, bin_ms=10.0, tau_ms=25.0)
fit = jnwb.fit_exponential_onset(t_ms, smooth, t0_bounds_ms=(0.0, 250.0))   # dict
# fit['bound_status'] is None for an interior fit and 'lower'/'upper' when the optimizer
# stopped at a bound, where t0 is the bound rather than an estimate.

# LFP: complex TFR (mask edges with tfr.coi_mask), band power, decibels last
tfr = jnwb.complex_tfr(lfp, fs=fs, freqs=np.linspace(10, 40, 4))

# aggregate_to_db aggregates on the RATIO scale, so it needs the per-trial powers, not one
# number: band_power returns a float, and `aggregate_over=0` over a float raises AxisError.
beta_raw = np.array([
    jnwb.band_power(trial, fs=fs, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False)
    for trial in lfp_trials
])
baseline_raw = np.array([
    jnwb.band_power(trial, fs=fs, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False)
    for trial in baseline_trials
])
db = jnwb.aggregate_to_db(beta_raw, baseline_raw, how="mean_of_ratios", aggregate_over=0)

# Bad channels from inter-channel correlation (channels x time)
bad, summary, z = jnwb.bad_channels_from_correlation(jnwb.channel_correlation_matrix(lfp_ch), z_thresh=5.0)

# Directed measures: both return DirectedResult; rng fixes the surrogates
te = jnwb.transfer_entropy(x, y, n_surrogates=200, rng=42)
psi = jnwb.phase_slope_index(x, y, fs=fs, bands=(15.0, 30.0))

# Statistics
res = jnwb.StatisticalAnalysis.exploratory_compare(g1, g2)   # parametric + bootstrap
q = jnwb.StatisticalAnalysis.fdr_correct(p_values)           # Benjamini-Hochberg
```

Functions that take `device="cuda"` warn when they fall back to the CPU. `n_jobs` (default 1)
parallelizes a loop over independent items, and `n_jobs=-1` uses every core; neither changes a
number.
