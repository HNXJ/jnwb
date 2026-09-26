# 04. Spectral Analysis, Coherence & Time-Frequency Representations (TFR)

Power spectra, decibel formation, coherence, and Morlet TFRs with streaming accumulation.

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

![Power Ratio Aggregation and Log-Last Rule](assets/figures/fig06_aggregate_to_db.png#only-light)
![Power Ratio Aggregation and Log-Last Rule](assets/figures/fig06_aggregate_to_db.dark.png#only-dark)

Panel A of that figure is synthetic per-unit power ratios on the ratio scale. Panel B puts the two
`jnwb.aggregate_to_db` contracts beside the mean of per-unit decibels, which is the Jensen error
the log-last rule forbids, and prints all three in dB so the gap is a number rather than a claim.

### Spectral Tilt, Harmonic Analysis & Referencing

```python
# Estimate 1/f spectral tilt / exponent from time series
tilt_res = jnwb.spectral_tilt(lfp_trace, fs=1000.0, freq_range=(1.0, 100.0))

# Direct aperiodic fit on pre-computed spectrum (fixed or knee mode)
# freqs: (n_freqs,) in Hz; psd: (..., n_freqs) in (U_in)^2/Hz
fit_res = jnwb.aperiodic_fit(freqs, psd, freq_range=(2.0, 40.0), mode="fixed")
# Returns jnwb.AperiodicFitResult with offset, exponent, knee, r_squared, accepted

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
falls as 1/f squared, plus a 10 Hz rhythm, and panel B is `jnwb.spectral_tilt` recovering the
aperiodic exponent from it, near -2.

### Digital Filtering (`bandpass_filter`, `notch_filter`)

Zero-phase (`zero_phase=True`, acausal forward-backward) and causal (`zero_phase=False`) filtering via Second-Order Sections (SOS):

```python
# Zero-phase Butterworth bandpass filter (14-30 Hz beta band)
beta_lfp = jnwb.bandpass_filter(lfp_trace, fs=1000.0, low_cut=14.0, high_cut=30.0, order=4, zero_phase=True)

# 60 Hz line-noise notch filter
clean_lfp = jnwb.notch_filter(lfp_trace, fs=1000.0, freq=60.0, q=30.0, zero_phase=True)
```

---

## 2. Cross-Area Coherence & Imaginary Coherency

### Cross-Area Coherence (`cross_area_coherence`)

Quantifies frequency-resolved phase synchronization between two LFP signals:

```python
coh_dict = jnwb.cross_area_coherence(
    lfp_area1,
    lfp_area2,
    fs=1000.0,
    freq_bands=jnwb.CANONICAL_BANDS
)
# Returns dict containing:
# - 'band_coherence': Dict[band_name -> float]
# - 'coherence_spectrum': np.ndarray (frequency-by-frequency coherence values)
# - 'frequencies': np.ndarray
```

### Imaginary Coherency & Weighted Phase Lag Index (`imaginary_coherency`, `wpli`)

Measures based on the imaginary cross-spectrum reduce sensitivity specifically to zero-phase-lag
coupling (instantaneous volume conduction, shared reference contamination). They do not confer
immunity to non-zero-lag common inputs, source mixing, or reference-induced phase structure.
`icoh_mean` is signed: positive means the first signal leads, the convention
`phase_slope_index` follows. `wpli` is unsigned.

```python
# Imaginary coherency (Nolte et al. 2004)
imag_coh = jnwb.imaginary_coherency(
    lfp_area1,
    lfp_area2,
    fs=1000.0,
    freq_range=(15.0, 30.0),
)

# Weighted Phase Lag Index (Vinck et al. 2011)
# Returns standard wPLI, debiased squared wPLI, and spectrum across segments
wpli_res = jnwb.wpli(
    lfp_area1,
    lfp_area2,
    fs=1000.0,
    freq_range=(15.0, 30.0),
)
```

---

## 3. High-Level Analyzers (`jnwb.analyzers`)

`jnwb.analyzers` provides object-oriented interfaces for analyzing session data:

- `TFRAnalyzer`: Time-frequency analysis and coordinate-explicit band extraction.
- `UnitAnalyzer`: Single-unit spike train autocorrelation and quality metrics.
- `PopulationAnalyzer`: Multi-unit population PSTH and cross-condition comparisons.

### Coordinate-Explicit Band Extraction (`TFRAnalyzer.extract_band`)

Requires explicit physical frequency coordinates (`freqs`) and validates frequency axis alignment:

```python
from jnwb.analyzers import TFRAnalyzer

# tfr_data: (n_channels, n_freqs, n_times)
# freqs: (n_freqs,) exact physical frequency coordinates in Hz
beta_power = TFRAnalyzer.extract_band(
    tfr_data,
    band="beta",
    freqs=freqs,
    freq_axis=1
)
```

---

## 4. Complex Morlet Time-Frequency Representations & Accumulation

### Complex Morlet Transform (`complex_tfr`, `morlet_wavelet`)

`jnwb.complex_tfr` computes complex time-frequency coefficients via Morlet wavelets with discrete $L_1$ amplitude normalization:

```python
import jnwb
import numpy as np

# raw_lfp: (n_channels, n_times)
freqs = np.linspace(10.0, 60.0, 11)  # 10 to 60 Hz in 5 Hz steps

# Compute complex coefficients with Cone of Influence (COI) mask
tfr_res = jnwb.complex_tfr(
    data=raw_lfp,
    fs=1000.0,
    freqs=freqs,
    n_cycles=5.0,
    normalization="amplitude"  # unit cosine yields peak |z| = 1.0
)

# Returns ComplexTFR dataclass:
# - tfr_res.z: np.ndarray, complex (n_channels, n_freqs, n_times)
# - tfr_res.coi_mask: np.ndarray, bool (n_channels, n_freqs, n_times)
# - tfr_res.power: np.ndarray (|z|^2)
# - tfr_res.phase: np.ndarray (angle in radians)
# - tfr_res.amplitude: np.ndarray (|z|)
```

![Complex Morlet TFR and Cone of Influence](assets/figures/fig05_complex_tfr_coi.png#only-light)
![Complex Morlet TFR and Cone of Influence](assets/figures/fig05_complex_tfr_coi.dark.png#only-dark)

Panel A of that figure is a synthetic LFP trace carrying one transient oscillatory burst and panel B is
`jnwb.complex_tfr` on it with the cone of influence drawn, so the region the next paragraph
excludes is visible as an outline rather than described.

**What `coi_mask` excludes, and why the average comes after it.** Convolution runs with
`mode="same"`, so near each edge part of the kernel hangs off the signal and is filled with
zeros. `coi_mask` is False for exactly those samples: the excluded region is the kernel
half-width, `ceil(cutoff_sigma * sigma_t * fs)`, which is what `coi_sigma=None` (the
default) derives it from. A True sample is one no zero-padding reached.

The contaminated samples are not merely noisier -- they are pulled toward zero by an amount
that depends on the signal's mean, and they sit at the ends of every trial, so they bias the
same time points in the same direction in every trial. **Average after masking, not before:**

```python
# WRONG: the edges are in the mean, and they are biased, not just noisy
mean_power = tfr_res.power.mean(axis=-1)

# CORRECT: exclude them, then average over what is left
masked = np.where(tfr_res.coi_mask, tfr_res.power, np.nan)
mean_power = np.nanmean(masked, axis=-1)

# Streaming: TFRAccumulator takes the mask directly and keeps a per-cell count
acc.add_trial(tfr_res.z, valid=tfr_res.coi_mask)
```

Low frequencies and high `n_cycles` both widen `sigma_t`, so both widen the excluded region:
at 10 Hz the kernel half-width is 191 samples at `n_cycles=3` and 637 at `n_cycles=10`
(fs = 1000 Hz). A short trial at a low frequency can be excluded end to end, which is the
correct answer -- there is no uncontaminated estimate to report.

### Streaming TFR Accumulation (`TFRAccumulator`) & NWB fp32 Compression (`compress_fp32`)

- **`TFRAccumulator` & `assert_mergeable` (`jnwb.tfr_accumulator`)**: Accumulates running sums and sum-of-squares across streaming trials (`add_trial(tfr_res.z, valid=tfr_res.coi_mask)`) without storing complete trial tensors in RAM. Its output has already averaged over trials, so `aggregate_to_db(how="mean_of_ratios")` refuses it; pass per-trial power for that estimand.
- **`compress_fp32` (`jnwb.compression`)**: On-disk NWB conversion — casts the datasets named in `select=` to `float32` inside an NWB file, irreversibly (path I/O, not in-memory array quantization). `select=` is required; omitting it raises `TypeError` before writing; `select=[]` casts nothing:

```python
# src and dst are filesystem paths to .nwb files; select names datasets by their path in the file
report = jnwb.compress_fp32(
    "raw_session.nwb", "compressed_session.nwb",
    select=["acquisition/probe_0_lfp/data"], verify=True,
)
assert report["verification"]["ok"] is True
```

## References

The methods on this page are cited in [References](references.md).
