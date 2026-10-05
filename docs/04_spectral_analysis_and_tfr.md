# 04. Power Spectra & Decibels

Power spectra, band power, decibel formation, spectral tilt, referencing, CSD and filtering. Coherence and Morlet TFRs are on [Coherence & TFR](coherence_and_tfr.md). The [LFP and spectral tutorial](tutorials/04_lfp_and_spectral.md) runs them end to end.

---

## 1. Canonical Frequency Bands & Spectral Decomposition (`jnwb.spectral`)

### Canonical Frequency Bands (`CANONICAL_BANDS`)

One band table, shared across modules:

```python
import jnwb

bands = jnwb.CANONICAL_BANDS
# Default:
# - theta: (4.0, 8.0) Hz
# - alpha: (8.0, 14.0) Hz
# - beta: (14.0, 30.0) Hz
# - low_gamma: (30.0, 50.0) Hz
# - high_gamma: (50.0, 80.0) Hz
```

### Power Spectral Density (`compute_psd`, `compute_multitaper_psd`) & Band Power (`band_power`)

```python
# Compute Welch PSD (returns frequencies and psd arrays)
freqs, psd = jnwb.compute_psd(lfp_trace, fs=1000.0)

# Compute DPSS multitaper PSD with explicit energy normalization
# nw: time-half-bandwidth product; k_tapers defaults to int(2*nw - 1)
freqs_mt, psd_mt = jnwb.compute_multitaper_psd(lfp_trace, fs=1000.0, nw=3.0, k_tapers=5)

# Extract the scalar mean PSD over a frequency range (e.g. beta: 14-30 Hz)
beta_power_val = jnwb.band_power(
    lfp_trace, fs=1000.0, freq_range=(14.0, 30.0), normalize=False,
)
```

`band_power` returns `mean(PSD[mask])` -- a spectral **density**, in input-units^2/Hz. It is
independent of the bandwidth, so bands of different widths are comparable to each other as
densities but are *not* band powers: on white noise a 2 Hz band and a 30 Hz band return
nearly the same number. If you want power in the band, integrate the PSD yourself:

```python
freqs, psd = jnwb.compute_psd(lfp_trace, fs=1000.0)
mask = (freqs >= 14.0) & (freqs <= 30.0)
beta_power_integrated = np.trapezoid(psd[mask], freqs[mask])  # input-units^2
```

With `normalize=True` the per-Hz factor cancels, because the result is a ratio of two
densities over the same band.

### Decibel Formation (`aggregate_to_db`, `to_db`, `DB_AGGREGATIONS`)

Take the logarithm **last**. Form the per-unit ratio `P / P0`, aggregate the *ratios*, and
convert once. Averaging decibels is a Jensen error -- `mean(log x) != log(mean x)` -- and it
biases every unit by its own noisiness, so a noisier channel is pulled toward a different
answer than a quiet one measuring the same effect.

`to_db(ratio)` is the bare conversion and cannot enforce anything: by the time a caller holds
decibels, the mistake is already available. `aggregate_to_db` is the enforcing form -- it owns
the whole ratio-aggregate-log sequence, so the correct order is the only order reachable
through it.

```python
# power, baseline: (n_units, n_trials), ratio-scale and non-negative
db = jnwb.aggregate_to_db(power, baseline, how="mean_of_ratios", aggregate_over=1)

# Element-wise conversion, no aggregation -- still logs exactly once
db_per_trial = jnwb.aggregate_to_db(power, baseline, how="mean_of_ratios")
```

**`how` has no default, on purpose.** The two members of `DB_AGGREGATIONS` are different
estimands, not implementation details:

| `how` | Estimand | Weighting |
|---|---|---|
| `"mean_of_ratios"` | mean of each unit's own ratio | every unit counts equally |
| `"ratio_of_means"` | summed power over summed baseline | each unit weighted by its baseline power |

They coincide only when the baseline is constant across the aggregated axis. In general
`sum_c P_c / sum_c P0_c = sum_c w_c (P_c / P0_c)` with `w_c = P0_c / sum_j P0_j`, so
`"ratio_of_means"` is a baseline-weighted version of the very same per-unit ratios. A silent
default would pick one of these for you.

**Geometric mean is deliberately rejected** rather than offered as a third option, because
`10*log10(geomean(r))` is *identically* `mean(10*log10(r))` -- it is mean-of-decibels wearing a
respectable name. Passing `how="geomean"` raises and says so.

**Negative input raises.** Ratio-scale power is non-negative by definition, whereas decibel
arrays routinely carry negative values, so handing decibels to this function usually fails
loudly instead of returning a plausible wrong number. Treat that as a guard, not a proof: an
all-positive decibel array is indistinguishable from power by inspection, so the contract still
stands -- pass power and baseline, never decibels.

`nan_policy="omit"` aggregates over non-NaN entries only. Artifact repair legitimately leaves
NaNs behind, so this is a real choice, but never a silent one.

### Direct Relative Power (`relative_power`)

`relative_power` forms the ratio against baseline under a named model:

```python
# Linear mean of ratios: E[P / B] (equal unit weighting)
rel_linear = jnwb.relative_power(power, baseline, model="mean_of_ratios", axis=0)

# Linear ratio of means: E[P] / E[B] (baseline-power-weighted average)
rel_weighted = jnwb.relative_power(power, baseline, model="ratio_of_means", axis=0)

# Decibels without spatial/trial aggregation: 10 * log10(P / B)
rel_db = jnwb.relative_power(power, baseline, model="log_ratio")
```

The model names are in `jnwb.RELATIVE_POWER_MODELS`. The returned estimand is the requested
one; nothing converts silently between linear and decibel.

`baseline` is a scalar or has `power`'s number of dimensions; a per-frequency baseline against
`(n_freqs, n_times)` power is `baseline[:, None]`. A baseline with fewer dimensions aligns with
the trailing axes and is broadcast with a `FutureWarning`; the next release raises
`ValueError`, as `aggregate_to_db` does.

![Power Ratio Aggregation and Log-Last Rule](assets/figures/fig06_aggregate_to_db.png#only-light)
![Power Ratio Aggregation and Log-Last Rule](assets/figures/fig06_aggregate_to_db.dark.png#only-dark)

Panel A of that figure is synthetic per-unit power ratios on the ratio scale. Panel B puts the two
`jnwb.aggregate_to_db` contracts beside the mean of per-unit decibels, which is the Jensen error
the log-last rule forbids, and prints all three in dB so the gap is a number rather than a claim.

### Spectral Tilt, Harmonic Analysis & Referencing

```python
# Log-log slope of the spectrum from a time series (negative for 1/f; see below)
tilt_res = jnwb.spectral_tilt(lfp_trace, fs=1000.0, freq_range=(1.0, 100.0))
slope = tilt_res["slope"]

# Direct aperiodic fit on pre-computed spectrum (fixed or knee mode)
# freqs: (n_freqs,) in Hz; psd: (..., n_freqs) in (U_in)^2/Hz
fit_res = jnwb.aperiodic_fit(freqs, psd, freq_range=(2.0, 40.0), mode="fixed")
# Returns jnwb.AperiodicFitResult with offset, exponent (positive for 1/f decay), knee, r_squared, accepted

# Harmonic distortion analysis
harmonics = jnwb.harmonic_analysis(lfp_trace, fs=1000.0, harmonic_orders=3)

# Spatial referencing schemes
bipolar_data = jnwb.bipolar_reference(lfp_multichannel)
laplacian_data = jnwb.laplacian_reference(lfp_multichannel)

# 1D Voltage Curvature (d2V/dz2 in V/m^2) and Current Source Density (CSD in A/m^3)
# lfp_probe: (n_channels, n_times) in Volts, ordered along probe depth
curv = jnwb.voltage_curvature_1d(lfp_probe, pitch_um=100.0, axis=0)
# CSD requires explicit extracellular conductivity (e.g. 0.3 S/m for cortex)
csd = jnwb.current_source_density_1d(lfp_probe, pitch_um=100.0, conductivity_s_per_m=0.3, axis=0)
```

**The CSD sign is the interpretation.** Output is in $\text{A}/\text{m}^3$, and the sign
convention is fixed: *negative* is a current **sink**, inward transmembrane current, the
signature of excitatory synaptic input; *positive* is a current **source**, the outward
return current. Reading the map with the opposite sign inverts every conclusion about
which depth receives input, so check the convention before comparing against a figure
from elsewhere -- the opposite convention is also in common use. A sink at a given depth
is evidence of current entering there, not of which structure supplied it.

![Power Spectral Density and Aperiodic Tilt](assets/figures/fig04_psd_spectral_tilt.png#only-light)
![Power Spectral Density and Aperiodic Tilt](assets/figures/fig04_psd_spectral_tilt.dark.png#only-dark)

Panel A of that figure is a synthetic trace built as a random-walk background, whose spectrum
falls as 1/f squared, plus a 10 Hz rhythm, and panel B is `jnwb.aperiodic_fit` recovering the
log-log slope, near -2, from the `jnwb.compute_psd` spectrum drawn under it, over 15-90 Hz
because the fit removes no peaks.

**Two signs for one spectrum.** The aperiodic exponent is positive, as in FOOOF: slope =
-exponent. `aperiodic_fit` returns that exponent, near +2 for this trace. `spectral_tilt`
returns the slope, near -2, under the key `slope`; `exponent` reads it with a
`DeprecationWarning` until the next release.

### Digital Filtering (`bandpass_filter`, `notch_filter`)

Zero-phase (`zero_phase=True`, acausal forward-backward) and causal (`zero_phase=False`) filtering via Second-Order Sections (SOS):

```python
# Zero-phase Butterworth bandpass filter (14-30 Hz beta band)
beta_lfp = jnwb.bandpass_filter(lfp_trace, fs=1000.0, low_cut=14.0, high_cut=30.0, order=4, zero_phase=True)

# 60 Hz line-noise notch filter
clean_lfp = jnwb.notch_filter(lfp_trace, fs=1000.0, freq=60.0, q=30.0, zero_phase=True)
```

## References

The methods on this page are cited in [References](references.md).
