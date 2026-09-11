---
name: jnwb
description: Top-level router, scientific safeguard kernel, and memory bank for jnwb NWB electrophysiology analysis.
---

# jnwb — Neuroscience & Electrophysiology Analysis Kernel

## 1. Trigger
Activate this skill when the user asks for generic electrophysiology analysis, time-frequency analysis, spike dynamics, NWB processing, neural statistics, decoding, artifact rejection, or directed connectivity.

## 2. Task-to-Primitive Routing Matrix
- **Substantial, multi-step, or consequential repository tasks**: (feature implementation, defect investigation, API modification, refactoring, release gates) -> delegate to `jnwb-fact-action` (enforces $F \to R \to A \to V \to S$, authority loading order, and role/domain separation).
- **Simple, bounded domain queries**:
  - **NWB inspection, paths, metadata, electrodes, addressing, compression**: delegate to `jnwb-nwb-data`
  - **Spike raster/PSTH, latency estimation, causal smoothing, unit QC**: delegate to `jnwb-spiking`
  - **LFP filtering, complex Morlet TFR, multi-trial accumulation, artifact repair**: delegate to `jnwb-lfp-spectral`
  - **Bootstrap, label/trial permutation, multiple comparisons (FDR), RNG safety**: delegate to `jnwb-statistics`
  - **Linear SVM decoding, neural trajectories, jRSA, population geometry**: delegate to `jnwb-population`
  - **Directional coupling (Granger, PSI, transfer entropy) with strict causal language**: delegate to `jnwb-connectivity`
  - **Visual QC, raster PSTH plotting, multi-format figure export**: delegate to `jnwb-figures`

## 3. High-Performance Acceleration (CuPy & Joblib)
- **GPU**: Operations supporting GPU execution accept `device='cuda'`, resolved once per call. If no CUDA device is present the call warns and runs on CPU; the result records which device produced it. Use `backend='cupy'` for distance-matrix speedups in `jrsa`.
- **Parallel CPU**: `n_jobs` is available on `cluster_permutation_test`, `cross_area_coherence`, and the `jrsa` permutation/bootstrap paths. Default is 1 everywhere except `jrsa`, which defaults to -1. Results are identical for any `n_jobs`. It pays only when serial work exceeds about a second.
- **Artifact Rejection & Repair**: Pre-filter LFP matrices using `bad_channels_from_correlation`, `consensus_bad_trials`, and `repair_lfp_trials`.

## 4. Core Scientific Safeguards & Invariants
1. **Signal Class Independence**: Spikes (SUA/MUA) and continuous LFP represent distinct physical observables. Never pool across modalities.
2. **Estimand & Causal Hierarchy**: $\text{Association} \ne \text{Directionality} \ne \text{Causality}$. Granger causality and phase slope index measure temporal-lag asymmetry (predictive directionality), not anatomical/physical causality.
3. **Logarithm Last**: For spectral power or decibel changes: average raw power across trials first, normalize by baseline, and compute $10 \cdot \log_{10}(\text{power})$ at the final step.
4. **Boundary & Filter Distortions**: Mask wavelet coefficients in the Cone of Influence (`coi_mask`). Use causal exponential smoothing (`causal_exp_smooth`) to prevent future leakage.
5. **RNG Reproducibility**: Pass explicit `numpy.random.Generator` instances (e.g. `rng = np.random.default_rng(seed)`). Never mutate global `np.random.seed()`.
6. **Dataset-Agnostic Invariant**: `jnwb` is dataset-agnostic. Experiment-specific condition codes and folder layouts belong in user analysis scripts, never in `jnwb`.

## 5. Agent Memory & Operational Guidance
For detailed workflow recipes, memory conventions, and common AI agent pitfalls, see:
- [AGENTS.md](../../AGENTS.md) — Repository map, working rules, and recipes.

## 6. Minimal Workflow
```python
import jnwb
import numpy as np

rng = np.random.default_rng(42)
data = rng.normal(size=(500,))
freqs = np.array([10.0, 20.0, 40.0])
tfr = jnwb.complex_tfr(data, fs=1000.0, freqs=freqs)
```

## 7. Verification
Run these rather than quoting counts; `jnwb.__all__` is the source of truth for the public surface.

```bash
python -c "import jnwb; assert all(hasattr(jnwb, n) for n in jnwb.__all__)"
python scripts/harness_gate.py
python -m pytest tests/ -q
python scripts/docs_build.py
```

