# Coherence & Time-Frequency Representations (TFR)

Coherence between two signals, and complex Morlet TFRs with streaming accumulation. Power spectra and decibel formation are on [Power Spectra & Decibels](04_spectral_analysis_and_tfr.md).

---

## 1. Cross-Area Coherence & Imaginary Coherency

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

## 2. High-Level Analyzers (`jnwb.analyzers`)

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

## 3. Complex Morlet Time-Frequency Representations & Accumulation

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
`jnwb.complex_tfr` on it with the cone of influence drawn and the region outside it veiled: what
the next paragraph excludes is visible, not described.

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

- **`TFRAccumulator` & `assert_mergeable` (`jnwb.tfr_accumulator`)**: Accumulates running sums and sum-of-squares across streaming trials (`add_trial(tfr_res.z, valid=tfr_res.coi_mask)`) without storing complete trial tensors in RAM. Its output has already averaged over trials, so `aggregate_to_db(how="mean_of_ratios")` refuses it. For that estimand, add each trial with its own baseline power (`add_trial(..., baseline=...)`) and take `jnwb.to_db(acc.mean_of_ratios())`.
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
