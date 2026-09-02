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
# Compute Welch PSD (returns frequencies and psd arrays)
freqs, psd = jnwb.compute_psd(lfp_trace, fs=1000.0)

# Extract scalar mean power in a specific frequency range (e.g. beta: 14-30 Hz)
beta_power_val = jnwb.band_power(lfp_trace, sampling_rate=1000.0, freq_range=(14.0, 30.0))
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
coh_dict = jnwb.cross_area_coherence(
    lfp_area1,
    lfp_area2,
    sampling_rate=1000.0,
    freq_bands=jnwb.CANONICAL_BANDS
)
# Returns dict containing:
# - 'band_coherence': Dict[band_name -> float]
# - 'coherence_spectrum': np.ndarray (frequency-by-frequency coherence values)
# - 'frequencies': np.ndarray
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

## 5. Complex Morlet Time-Frequency Representations & Accumulation

### Complex Morlet Transform Primitive (`complex_tfr`, `morlet_wavelet`)

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

### Streaming TFR Accumulation (`TFRAccumulator`) & Compression (`compress_fp32`)

- **`TFRAccumulator` & `assert_mergeable` (`jnwb.tfr_accumulator`)**: Accumulates running sums and sum-of-squares across streaming trials (`add_trial(tfr_res.z, valid=tfr_res.coi_mask)`) without storing complete trial tensors in RAM.
- **`compress_fp32` (`jnwb.compression`)**: Compresses high-dimensional single-precision floating point arrays into quantized representations.
