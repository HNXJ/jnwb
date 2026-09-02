---
name: jnwb
description: Top-level router and scientific safeguard kernel for jnwb NWB electrophysiology
  analysis.
---

# `jnwb` — Neuroscience & Electrophysiology Analysis Kernel

## 1. Trigger
Activate this skill when the user asks for generic electrophysiology analysis, time-frequency analysis, spike dynamics, NWB processing, neural statistics, decoding, or directed connectivity.

## 2. Task-to-Primitive Routing Matrix
- **NWB inspection, paths, metadata, electrodes, addressing, compression**: delegate to `jnwb-nwb-data`
- **Spike raster/PSTH, latency estimation, causal smoothing, unit QC**: delegate to `jnwb-spiking`
- **LFP filtering, complex Morlet TFR, multi-trial accumulation, artifact repair**: delegate to `jnwb-lfp-spectral`
- **Bootstrap, label/trial permutation, multiple comparisons (FDR), RNG safety**: delegate to `jnwb-statistics`
- **Linear SVM decoding, neural trajectories, jRSA, population geometry**: delegate to `jnwb-population`
- **Directional coupling (Granger, PSI, transfer entropy) with strict causal language**: delegate to `jnwb-connectivity`
- **Visual QC, raster PSTH plotting, multi-format figure export**: delegate to `jnwb-figures`

## 3. Core Scientific Safeguards & Invariants
1. **Signal Class Independence**: Spikes (SUA/MUA) and continuous LFP represent distinct physical observables. Never pool across modalities.
2. **Estimand & Causal Hierarchy**: $\text{Association} \ne \text{Directionality} \ne \text{Causality}$. Granger causality and phase slope index measure temporal-lag asymmetry (predictive directionality), not anatomical/physical causality.
3. **Logarithm Last**: For spectral power or decibel changes: average raw power across trials first, normalize by baseline, and compute $10 \cdot \log_{10}(\text{power})$ at the final step.
4. **Boundary & Filter Distortions**: Mask wavelet coefficients in the Cone of Influence (`coi_mask`). Use causal exponential smoothing (`causal_exp_smooth`) to prevent future leakage.
5. **RNG Reproducibility**: Pass explicit `numpy.random.Generator` instances (e.g. `rng = np.random.default_rng(seed)`). Never mutate global `np.random.seed()`.
6. **Dataset-Agnostic Invariant**: `jnwb` is dataset-agnostic. Experiment-specific condition codes and folder layouts belong in user analysis scripts, never in `jnwb`.

## 4. Minimal Workflow
```python
import jnwb
import numpy as np

rng = np.random.default_rng(42)
data = rng.normal(size=(500,))
freqs = np.array([10.0, 20.0, 40.0])
tfr = jnwb.complex_tfr(data, fs=1000.0, freqs=freqs)
```

## 5. Verification
- All 101 exports resolve from `import jnwb`.
- `sphinx-build -W` compiles docs warning-free.

## 6. Canonical Documentation Links
- [`docs/01_architecture_and_philosophy.md`](../../docs/01_architecture_and_philosophy.md)
- [`docs/02_paths_addressing_metadata.md`](../../docs/02_paths_addressing_metadata.md)
- [`docs/03_representational_similarity_jrsa.md`](../../docs/03_representational_similarity_jrsa.md)
- [`docs/04_spectral_analysis_and_tfr.md`](../../docs/04_spectral_analysis_and_tfr.md)
- [`docs/05_artifact_detection_and_repair.md`](../../docs/05_artifact_detection_and_repair.md)
- [`docs/06_spikes_psth_and_onset_dynamics.md`](../../docs/06_spikes_psth_and_onset_dynamics.md)
- [`docs/07_statistical_inference_and_nulls.md`](../../docs/07_statistical_inference_and_nulls.md)
- [`docs/08_directed_connectivity_and_information.md`](../../docs/08_directed_connectivity_and_information.md)
- [`docs/09_decoding_and_visual_qc.md`](../../docs/09_decoding_and_visual_qc.md)
- [`docs/10_extending_jnwb_and_verification.md`](../../docs/10_extending_jnwb_and_verification.md)
