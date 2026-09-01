# 04. Spectral Analysis, Coherence & Time-Frequency Representations (TFR)

This document details spectral power estimation, time-frequency decomposition, cross-area coherence, memory-efficient accumulation, coordinate-explicit band extraction, and decibel transformations in `jnwb`.

---

## 1. Canonical Frequency Bands & Spectral Decomposition (`jnwb.spectral`)

`jnwb.spectral` provides standard tools for computing spectral power density, cross-spectral density, coherence, and referencing.

### Canonical Frequency Bands (`CANONICAL_BANDS`)

Unless customized by the user, `jnwb` standardizes frequency bands across modules:

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

### Power Spectral Density (`compute_psd`) & Band Power (`band_power`)

```python
# Compute Welch PSD
freqs, psd = jnwb.compute_psd(lfp_trace, sampling_rate=1000.0, nperseg=256)

# Extract power across canonical or custom frequency bands
power_by_band = jnwb.band_power(lfp_trace, sampling_rate=1000.0, freq_bands=jnwb.CANONICAL_BANDS)
```

### Spectral Tilt, Harmonic Analysis & Referencing

```python
# Estimate 1/f spectral tilt / exponent
tilt_res = jnwb.spectral_tilt(lfp_trace, sampling_rate=1000.0, freq_range=(1.0, 100.0))

# Harmonic distortion analysis
harmonics = jnwb.harmonic_analysis(lfp_trace, sampling_rate=1000.0, harmonic_orders=3)

# Spatial referencing schemes
bipolar_data = jnwb.bipolar_reference(lfp_multichannel)
laplacian_data = jnwb.laplacian_reference(lfp_multichannel)
```

---

## 2. Cross-Area Coherence & Imaginary Coherency

### Cross-Area Coherence (`cross_area_coherence`)

Quantifies frequency-resolved phase synchronization between two LFP signals:

```python
coherence_dict = jnwb.cross_area_coherence(
    lfp_area1,
    lfp_area2,
    sampling_rate=1000.0,
    freq_bands=jnwb.CANONICAL_BANDS
)
```

### Imaginary Coherency (`imaginary_coherency`)

Computes imaginary coherency to eliminate volume conduction / zero-lag field spread artifacts:

```python
imag_coh = jnwb.imaginary_coherency(
    lfp_area1,
    lfp_area2,
    sampling_rate=1000.0,
    freq_range=(15.0, 30.0)
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

## 4. Decibel Transformation (`to_db`) & Estimand Considerations

`jnwb.to_db(ratio)` computes $10 \log_{10}(\text{ratio})$.

### Estimand Aggregation Notice
For baseline-normalized relative power estimands:
$$\text{RelPower}(f, t) = \frac{\bar{P}_{\text{response}}(f, t)}{\bar{P}_{\text{baseline}}(f)}$$
$$\text{Decibels}(f, t) = 10 \log_{10}\left(\text{RelPower}(f, t)\right) = \text{jnwb.to\_db}(\text{RelPower})$$

> **Design Note**: In relative power analyses, averaging raw power across trials before computing the ratio and applying `to_db` once at the end preserves the arithmetic mean of physical power. `jnwb` supplies the mathematical primitive `to_db` without enforcing a fixed aggregation pipeline on arbitrary workflows.

---

## 5. Streaming TFR Accumulation & Compression

- **`TFRAccumulator` & `assert_mergeable` (`jnwb.tfr_accumulator`)**: Accumulates running sums and sum-of-squares across streaming trials without storing complete trial tensors in RAM.
- **`compress_fp32` (`jnwb.compression`)**: Compresses high-dimensional single-precision floating point arrays into quantized representations.
