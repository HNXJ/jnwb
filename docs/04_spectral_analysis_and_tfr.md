# 04. Spectral Analysis, Coherence & Time-Frequency Representations (TFR)

This document details spectral power estimation, time-frequency decomposition, cross-area coherence, memory-efficient accumulation, coordinate-explicit band extraction, and the "Logarithm Last" rule in `jnwb`.

---

## 1. Canonical Frequency Bands & Spectral Decomposition (`jnwb/spectral.py`)

`jnwb.spectral` provides standard tools for computing spectral power density, Morlet wavelet scalograms, multi-taper spectrograms, cross-spectral density, and phase synchrony.

### Canonical Frequency Bands

Unless customized by the user, `jnwb` standardizes frequency bands across modules:

| Band Name | Frequency Range (Hz) | Typical Biological Association |
|-----------|----------------------|--------------------------------|
| `theta` | $4.0 - 8.0$ Hz | Hippocampal / cortical rhythmic modulation |
| `alpha` | $8.0 - 14.0$ Hz | Attentional gating / visual synchrony |
| `beta` | $15.0 - 30.0$ Hz | Top-down motor / sensory maintenance |
| `gamma_low` | $30.0 - 60.0$ Hz | Local circuit feedforward processing |
| `gamma_high` | $60.0 - 120.0$ Hz | Multi-unit spike envelope proxy |

```python
import jnwb.spectral as spec

# Access standard canonical band dictionary
bands = spec.CANONICAL_BANDS
```

---

## 2. Cross-Area Coherence & Phase-Locking Value (PLV)

`jnwb.spectral` implements cross-channel and cross-area coherence:
$$C_{xy}(f) = \frac{|P_{xy}(f)|^2}{P_{xx}(f) P_{yy}(f)}$$

```python
# Compute cross-area coherence between two LFP channels
coherence_res = spec.cross_area_coherence(
    lfp_area1, lfp_area2, fs=1000.0, nperseg=256, noverlap=128
)
freqs = coherence_res["frequencies"]
coherence_values = coherence_res["coherence"]
```

---

## 3. Coordinate-Explicit Band Extraction (`jnwb/analyzers.py:TFRAnalyzer`)

### The F1 Coordinate Contract
`TFRAnalyzer.extract_band` requires **explicit frequency coordinates** (`freqs`). It never assumes uniform $0 - 200$ Hz linear spacing or infers coordinates from tensor length:

```python
import numpy as np
from jnwb.analyzers import TFRAnalyzer

# tfr_data: (n_channels, n_freqs, n_times)
# freqs: (n_freqs,) exact physical frequency coordinates in Hz
freq_axis = 1

# Extract average power in the Beta band (15-30 Hz)
beta_power = TFRAnalyzer.extract_band(
    tfr_data,
    band="beta",
    freqs=freqs,
    freq_axis=freq_axis
)
# Output shape: (n_channels, n_times)
```

### Band Specification Flexibility
`band` can be specified as:
1. A canonical string name: `"theta"`, `"alpha"`, `"beta"`, `"gamma_low"`, `"gamma_high"`.
2. An explicit numerical 2-tuple: `(12.0, 24.0)`.

```python
# Extract custom sub-band
custom_power = TFRAnalyzer.extract_band(tfr_data, band=(12.0, 24.0), freqs=freqs)
```

---

## 4. The "Logarithm Last" Invariant

When calculating baseline-normalized spectrograms or spectral changes:
$$\text{RelPower}(f, t) = \frac{\frac{1}{N}\sum_{i=1}^N P_i(f, t)}{\bar{P}_{\text{baseline}}(f)}$$
$$\text{Decibels}(f, t) = 10 \log_{10}\left(\text{RelPower}(f, t)\right)$$

### Correct Sequential Order:
1. Compute raw power for each trial ($V^2 / \text{Hz}$).
2. Average raw power across trials within condition.
3. Divide trial-averaged raw power by baseline raw power.
4. Apply $10 \log_{10}(\cdot)$ **once at the end** for display/reporting.

> **Caution**: Never average pre-computed decibel values across trials, recording sites, or sessions. Averaging decibels computes the geometric mean of power rather than the arithmetic mean, distorting statistical inference.

---

## 5. Streaming TFR Accumulation & Compression

For long recording sessions with hundreds of trials and channels, storing full time-frequency tensors in RAM is prohibitive:

- **`jnwb.tfr_accumulator.TFRAccumulator`**: Accumulates running sum and sum-of-squares across streaming trials, yielding mean and standard error without keeping individual trial tensors in memory.
- **`jnwb.compression`**: Quantizes floating-point spectrograms to sparse integer representations with configurable dynamic range, enabling compact caching on disk.
