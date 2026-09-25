---
name: jnwb
description: Top-level router and scientific safeguard kernel for jnwb NWB electrophysiology analysis.
---

# jnwb — Router and Scientific Safeguards

## 1. Trigger
Electrophysiology analysis in general: NWB processing, spike dynamics, time-frequency analysis, laminar depth, statistics, decoding, artifact rejection, directed connectivity and figures.

## 2. Routing

| Task | Skill |
|---|---|
| Multi-step or consequential repository work: features, defect investigation, API changes, refactoring, release gates | `jnwb-fact-action` (enforces $F \to R \to A \to V \to S$, authority loading order and role/domain separation) |
| NWB inspection, paths, metadata, electrodes, addressing, compression | `jnwb-nwb-data` |
| Spike raster/PSTH, latency, causal smoothing, unit QC | `jnwb-spiking` |
| LFP filtering, complex Morlet TFR, multi-trial accumulation, artifact detection and repair (`bad_channels_from_correlation`, `consensus_bad_trials`, `repair_lfp_trials`) | `jnwb-lfp-spectral` |
| Laminar depth: cortical layers, crossover contacts, CSD, probe geometry | `jnwb-lfp-spectral` (its depth estimators read the spectra and correlation matrices it produces); `jnwb-nwb-data` for the electrode table |
| Bootstrap, label/trial permutation, multiple comparisons (FDR), RNG | `jnwb-statistics` |
| Linear SVM decoding, neural trajectories, jRSA, population geometry | `jnwb-population` |
| Directed coupling (Granger, PSI, transfer entropy) | `jnwb-connectivity` |
| Matplotlib figures: visual QC, raster/PSTH plots, vector export | `jnwb-figures` |
| Multi-panel Plotly publication figures through `jnwb.vis` (optional `vis` extra) | `jnwb-landmark-viz` |

## 3. Execution: GPU and Parallel CPU
Operations whose signature takes `device` accept `device='cuda'` and `device='metal'`. A request no GPU can serve warns and runs on the CPU.

| Operations | With `device='cuda'` |
|---|---|
| `complex_tfr`, `cross_area_coherence`, `PopulationAnalyzer.population_trajectory`, `spectral_tilt`, `harmonic_analysis`, `imaginary_coherency`, `wpli`, `granger_causality`, `UnitAnalyzer.autocorrelogram`, `compute_population_trajectory` | Compute on the GPU when one is present and record the device that ran: `device` on `complex_tfr`'s result, `device_used` on the others. `granger_causality` recomputes the whole call on the CPU if any fit falls back. |
| `band_power`, `relative_power`, `rdm`, `vflip`, `vflip_from_lfp` (whose warning names `vflip`) | Warn and run on the CPU even with a GPU present. |
| `jrsa` | Computes every metric in NumPy on the CPU whatever its `backend` or `device`; an accelerator `backend` or `device='cuda'` warns and records `execution['device'] == 'cpu'`. |

`'metal'` runs only in `complex_tfr` with `dtype=np.complex64`, through JAX; it is implemented and has not been run on Metal hardware.

`n_jobs` is accepted by the operations whose signature lists it. The default is 1 everywhere, and results are identical for any `n_jobs`. Opt in only when serial work exceeds about five seconds; the first parallel call in a process costs several seconds of start-up.

## 4. Scientific Safeguards
1. **Signal classes**: spikes (SUA/MUA) and continuous LFP are distinct physical observables. Never pool across them.
2. **Association $\ne$ directionality $\ne$ causality**: Granger causality and phase slope index measure temporal-lag asymmetry (predictive directionality), not anatomical or physical causality.
3. **Logarithm last**: average raw power across trials, divide by baseline, and compute $10 \cdot \log_{10}$ once, at the final step.
4. **Boundaries and leakage**: mask wavelet coefficients in the cone of influence (`coi_mask`). Use causal exponential smoothing (`causal_exp_smooth`) to prevent future leakage.
5. **RNG**: pass an explicit `numpy.random.Generator` (`rng = np.random.default_rng(seed)`). Never call `np.random.seed()`.
6. **Dataset-agnostic**: condition codes and folder layouts belong in user analysis scripts, never in `jnwb`.
7. **Coupling vs direction vs delay**: unsigned coupling magnitude (e.g. wPLI $\ge 0$) does not determine propagation direction; direction requires a signed phase or phase-slope estimator. Latency delay ($d\phi/df = -2\pi \Delta\tau$) and apparent velocity ($v = \Delta z / \Delta\tau$) require verified linear unwrapped phase across the fitted band and explicit identifiability criteria; report unavailable otherwise.
8. **No volume-conduction immunity**: measures based on the imaginary cross-spectrum (wPLI, imaginary coherency) reduce sensitivity specifically to zero-phase-lag coupling; they do not establish immunity to common sources with non-zero lag, source mixing, filtering delays, or reference-induced phase structure.

## 5. Repository Guide
- [AGENTS.md](../../AGENTS.md) — repository map, working rules and recipes.

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
`jnwb.__all__` is the public surface; run these rather than quoting counts.

```bash
python -c "import jnwb; assert all(hasattr(jnwb, n) for n in jnwb.__all__)"
python scripts/harness_gate.py
python -m pytest tests/ -q
python scripts/docs_build.py
```
