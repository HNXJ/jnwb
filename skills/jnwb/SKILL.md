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
| NWB files: inspection, event onsets by code, paths, metadata, electrode addressing, census, compression | `jnwb-nwb-data` |
| Experiment structure: interval tables, event rows, epochs around events, recording cycles, condition meaning from documented metadata | `jnwb-paradigm` |
| Spike trains: binning, raster, PSTH, onset latency, response significance, spike-field locking, causal smoothing | `jnwb-spiking` |
| LFP filtering, band power, complex Morlet TFR, multi-trial accumulation, artifact detection and repair (`bad_channels_from_correlation`, `consensus_bad_trials`, `repair_lfp_trials`) | `jnwb-lfp-spectral` |
| Laminar depth: cortical layers, crossover contacts, CSD, probe geometry | `jnwb-lfp-spectral` (its depth estimators read the spectra and correlation matrices it produces); `jnwb-nwb-data` for the electrode table |
| Bootstrap, label/trial permutation, multiple comparisons (FDR), RNG | `jnwb-statistics` |
| Linear SVM decoding, neural trajectories, jRSA, population geometry | `jnwb-population` |
| Directed coupling (Granger, PSI, transfer entropy); lag asymmetry, not causation | `jnwb-connectivity` |
| Matplotlib figures: equal raster trial counts, vector export | `jnwb-figures` |
| Quality control: unit-quality measures and classes, unit and electrode table audits, unit-quality plots, result records of what ran on which inputs | `jnwb-qc` |
| Plotly multi-panel figures with SVG/PNG/HTML export and an argument sidecar (needs the `vis` extra) | `jnwb-landmark-viz` |

Before routing, check the plan:

- `jnwb.preflight(question)`: Takes a `jnwb.Question` and returns a `Preflight` whose `outcome` is `"decline"` when `unsupported_inference` is stated, else `"request"` when `signals`, `signal_units`, `contrast` or `inference_unit` is empty (`missing` names each), else `"failure"` when `non_identifiable` is stated, else `"supported"`. `reason` says why and names the optional fields left empty.

## 3. Execution
Operations whose signature takes `device` accept `device='cuda'` and `device='metal'`. A request no GPU can serve warns and runs on the CPU.

| Operations | With `device='cuda'` |
|---|---|
| `complex_tfr`, `cross_area_coherence`, `PopulationAnalyzer.population_trajectory`, `spectral_tilt`, `harmonic_analysis`, `imaginary_coherency`, `wpli`, `granger_causality`, `UnitAnalyzer.autocorrelogram`, `compute_population_trajectory` | Compute on the GPU when one is present and record the device that ran: `device` on `complex_tfr`'s result, `device_used` on the others. `granger_causality` recomputes the whole call on the CPU if any fit falls back. |
| `band_power`, `relative_power`, `rdm`, `vflip`, `vflip_from_lfp` (whose warning names `vflip`) | Warn and run on the CPU even with a GPU present. |
| `jrsa` | Computes every metric in NumPy on the CPU whatever its `backend` or `device`; an accelerator `backend` or `device='cuda'` warns and records `execution['device'] == 'cpu'`. |

`'metal'` runs only in `complex_tfr` with `dtype=np.complex64`, through JAX; it is implemented and has not been run on Metal hardware.

`n_jobs` is accepted by the operations whose signature lists it. The default is 1 everywhere, and results are identical for any `n_jobs`. Opt in only when serial work exceeds about five seconds; the first parallel call in a process costs several seconds of start-up.

## 4. Invariants & Safeguards
1. **Signal classes**: spikes (SUA/MUA) and continuous LFP are distinct physical observables. Never pool across them.
2. **Association $\ne$ directionality $\ne$ causality**: Granger causality and phase slope index measure temporal-lag asymmetry (predictive directionality), not anatomical or physical causality.
3. **Logarithm last**: average raw power across trials, divide by baseline, and compute $10 \cdot \log_{10}$ once, at the final step.
4. **Boundaries and leakage**: mask wavelet coefficients in the cone of influence (`coi_mask`). Use causal exponential smoothing (`causal_exp_smooth`) to prevent future leakage.
5. **RNG**: pass an explicit `numpy.random.Generator` (`rng = np.random.default_rng(seed)`). Never call `np.random.seed()`.
6. **Dataset-agnostic**: experiment-specific condition codes and folder layouts belong in user analysis scripts, never in `jnwb`.
7. **Coupling vs direction vs delay**: stated in the safeguard of that name in section 3 of [`skills/jnwb-connectivity/SKILL.md`](../jnwb-connectivity/SKILL.md); it binds every coupling, direction and delay estimate, whichever skill routes the call.
8. **No volume-conduction immunity**: measures based on the imaginary cross-spectrum (wPLI, imaginary coherency) reduce sensitivity specifically to zero-phase-lag coupling; they do not establish immunity to common sources with non-zero lag, source mixing, filtering delays, or reference-induced phase structure.

## 5. Minimal Workflow
```python
# Input: deterministic array.
import jnwb
import numpy as np

fs = 1000.0
t_s = np.arange(500) / fs
data = np.sin(2 * np.pi * 10.0 * t_s)  # a 10 Hz sine, 0.5 s at 1 kHz
freqs = np.array([10.0, 20.0, 40.0])
tfr = jnwb.complex_tfr(data, fs=fs, freqs=freqs)
```

## 6. Verification
`jnwb.__all__` is the public surface; save this as `check_all.py` and run `python check_all.py` rather than quoting counts.

```python
# Input: deterministic array.
import jnwb

missing = [n for n in jnwb.__all__ if not hasattr(jnwb, n)]
assert not missing, missing
```

## 7. Documentation
- [`docs/api.md`](../../docs/api.md) — every public symbol.
- [`docs/common_mistakes.md`](../../docs/common_mistakes.md) — the failure modes jnwb guards against.
- [`docs/errors.md`](../../docs/errors.md) — every refusal and what to pass instead.
- [`docs/tutorials/00_your_own_file.md`](../../docs/tutorials/00_your_own_file.md) — discovering a file's layout instead of assuming one.
