---
name: jnwb
description: Top-level router, scientific safeguard kernel, and memory bank for jnwb NWB electrophysiology analysis.
---

# jnwb — Neuroscience & Electrophysiology Analysis Kernel

## 1. Trigger
Activate this skill when the user asks for generic electrophysiology analysis, time-frequency analysis, spike dynamics, NWB processing, neural statistics, decoding, artifact rejection, or directed connectivity.

## 2. Task-to-Operation Routing Matrix
- **Substantial, multi-step, or consequential repository tasks**: (feature implementation, defect investigation, API modification, refactoring, release gates) -> delegate to `jnwb-fact-action` (enforces $F \to R \to A \to V \to S$, authority loading order, and role/domain separation).
- **Simple, bounded domain queries**:
  - **NWB inspection, paths, metadata, electrodes, addressing, compression**: delegate to `jnwb-nwb-data`
  - **Spike raster/PSTH, latency estimation, causal smoothing, unit QC**: delegate to `jnwb-spiking`
  - **LFP filtering, complex Morlet TFR, multi-trial accumulation, artifact repair**: delegate to `jnwb-lfp-spectral`
  - **Laminar depth: assigning cortical layers, crossover contacts, CSD, probe geometry**: delegate to `jnwb-lfp-spectral` (depth estimators consume the spectra and correlation matrices that skill produces) and `jnwb-nwb-data` for the electrode table
  - **Bootstrap, label/trial permutation, multiple comparisons (FDR), RNG safety**: delegate to `jnwb-statistics`
  - **Linear SVM decoding, neural trajectories, jRSA, population geometry**: delegate to `jnwb-population`
  - **Directional coupling (Granger, PSI, transfer entropy) with strict causal language**: delegate to `jnwb-connectivity`
  - **Visual QC, raster PSTH plotting, multi-format figure export**: delegate to `jnwb-figures`

## 3. High-Performance Acceleration (CuPy & Joblib)
- **GPU**: Operations whose signature takes `device` accept `device='cuda'` and `device='metal'`. With a GPU present, `complex_tfr`, `cross_area_coherence`, `PopulationAnalyzer.population_trajectory`, `spectral_tilt`, `harmonic_analysis`, `imaginary_coherency`, `wpli`, `granger_causality`, `UnitAnalyzer.autocorrelogram` and `compute_population_trajectory` compute on it and record the device that ran (`device` on `complex_tfr`'s result, `device_used` on the others). `granger_causality` recomputes the whole call on the CPU if any fit falls back. A request no GPU can serve warns and runs on the CPU. `band_power`, `relative_power`, `rdm`, `vflip` and `vflip_from_lfp` (whose warning names `vflip`) warn and run on the CPU even with a GPU present. `jrsa` computes every metric in NumPy on the CPU whatever its `backend` or `device`; an accelerator `backend` or `device='cuda'` warns and records `execution['device'] == 'cpu'`. `'metal'` runs only in `complex_tfr` with `dtype=np.complex64`, through JAX; it is implemented and has not been run on Metal hardware.
- **Parallel CPU**: `n_jobs` is accepted by the operations whose signature lists it. The default is 1 everywhere, and results are identical for any `n_jobs`. Opt in only when serial work exceeds about five seconds; the first parallel call in a process has a start-up cost of several seconds.
- **Artifact Rejection & Repair**: Pre-filter LFP matrices using `bad_channels_from_correlation`, `consensus_bad_trials`, and `repair_lfp_trials`.

## 4. Core Scientific Safeguards & Invariants
1. **Signal Class Independence**: Spikes (SUA/MUA) and continuous LFP represent distinct physical observables. Never pool across modalities.
2. **Estimand & Causal Hierarchy**: $\text{Association} \ne \text{Directionality} \ne \text{Causality}$. Granger causality and phase slope index measure temporal-lag asymmetry (predictive directionality), not anatomical/physical causality.
3. **Logarithm Last**: For spectral power or decibel changes: average raw power across trials first, normalize by baseline, and compute $10 \cdot \log_{10}(\text{power})$ at the final step.
4. **Boundary & Filter Distortions**: Mask wavelet coefficients in the Cone of Influence (`coi_mask`). Use causal exponential smoothing (`causal_exp_smooth`) to prevent future leakage.
5. **RNG Reproducibility**: Pass explicit `numpy.random.Generator` instances (e.g. `rng = np.random.default_rng(seed)`). Never mutate global `np.random.seed()`.
6. **Dataset-Agnostic Invariant**: `jnwb` is dataset-agnostic. Experiment-specific condition codes and folder layouts belong in user analysis scripts, never in `jnwb`.
7. **Phase Coupling vs Directionality vs Delay**: Unsigned coupling magnitude (e.g. wPLI $\ge 0$) does not determine propagation direction. Direction requires a signed phase or phase-slope estimator. Latency delay ($d\phi/df = -2\pi \Delta\tau$) and apparent velocity ($v = \Delta z / \Delta\tau$) require verified linear unwrapped phase across the fitted band and explicit identifiability criteria; report unavailable otherwise.
8. **No Volume Conduction Immunity**: Measures based on the imaginary cross-spectrum (wPLI, imaginary coherency) reduce sensitivity specifically to zero-phase-lag coupling; they do not establish immunity to common sources with non-zero lag, source mixing, filtering delays, or reference-induced phase structure.

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

