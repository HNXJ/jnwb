---
name: jnwb-lfp-spectral
description: LFP filtering, Morlet wavelet complex TFR, streaming accumulation, coherence,
  and artifact repair.
---

# `jnwb-lfp-spectral` — LFP, Spectral Analysis & TFR Accumulation

## 1. Trigger
Activate this skill when computing continuous or trial-aligned LFP spectra, complex Time-Frequency Representations (TFR), multi-trial accumulation, cross-area coherence, or artifact detection and repair.

## 2. Task-to-Primitive Routing Matrix
- `jnwb.complex_tfr(data, fs, freqs, n_cycles)`: Complex Morlet wavelet transform returning `ComplexTFR` with `z`, `freqs`, `times`, and `coi_mask`.
- `jnwb.TFRAccumulator(shape)`: Welford running variance accumulator for streaming multi-trial TFR without storing full $N \times C \times F \times T$ arrays in memory.
- `jnwb.repair_lfp_trials(segments, times_ms, z_thresh=6.0)`: Cross-channel synchrony detection ($z > 6.0$) and cross-trial median substitution.
- `jnwb.repair_band_artifacts(tfr_power, ...)`: TFR-domain outlier artifact detection and interpolation.
- `jnwb.channel_correlation_matrix(data)` & `jnwb.bad_channels_from_correlation(corr_matrix)`: Detect disconnected or excessively noisy probe channels.
- `jnwb.cross_area_coherence(x, y, fs, bands)`: Magnitude-squared coherence across channel pairs.
- `jnwb.imaginary_coherency(x, y, fs, ...)`: Volume-conduction-robust imaginary coherence.
- `jnwb.spectral_tilt(psd, freqs, fit_range)`: Aperiodic $1/f$ spectral slope parameterization.
- `jnwb.bipolar_reference(data, channel_pairs)`: Local differential referencing for spatial artifact reduction.

## 3. Invariants & Safeguards
1. **Cone of Influence (COI)**: Always check `coi_mask` when analyzing edge time points; edge coefficients are contaminated by boundary zero-padding.
2. **Logarithm Last**: Compute average raw power across trials first, then compute $10 \cdot \log_{10}(\text{power})$ at the reporting step.
3. **LFP Artifact Substitution vs Exclusion**: `repair_lfp_trials` uses cross-trial median substitution; inspect `frac_flagged` to ensure excessive trials (>20%) are not replaced.

## 4. Minimal Workflow
```python
import jnwb
import numpy as np

fs = 1000.0
freqs = np.linspace(10.0, 60.0, 6)
acc = jnwb.TFRAccumulator(shape=(4, len(freqs), 300))

rng = np.random.default_rng(42)
for _ in range(5):
    trial = rng.normal(size=(4, 300))
    tfr = jnwb.complex_tfr(trial, fs=fs, freqs=freqs)
    acc.add_trial(tfr.z, valid=tfr.coi_mask)

power = acc.power()
itc = acc.itc()
```

## 5. Verification
- Confirm exact Morlet $L_1$ normalization: a unit cosine at $f_0$ yields peak $|z| = 1.0$.
- Verify `TFRAccumulator.power()` matches offline batch computation.

## 6. Canonical Documentation Links
- [`docs/04_spectral_analysis_and_tfr.md`](../../docs/04_spectral_analysis_and_tfr.md)
- [`docs/05_artifact_detection_and_repair.md`](../../docs/05_artifact_detection_and_repair.md)
