---
name: jnwb-lfp-spectral
description: LFP filtering, Morlet wavelet complex TFR, streaming accumulation, coherence,
  and artifact repair.
---

# `jnwb-lfp-spectral` — LFP, Spectral Analysis & TFR Accumulation

## 1. Trigger
Continuous or trial-aligned LFP spectra, complex time-frequency representations (TFR), multi-trial accumulation, cross-area coherence, laminar depth, or artifact detection and repair.

## 2. Routing

The "Spectra and TFR" routing rows live in [`references/spectra_and_tfr.md`](references/spectra_and_tfr.md).

The "Power and decibels" routing rows live in [`references/power_and_decibels.md`](references/power_and_decibels.md).

The "Filtering and referencing" routing rows live in [`references/filtering_and_referencing.md`](references/filtering_and_referencing.md).

The "Coupling" routing rows live in [`references/coupling.md`](references/coupling.md).

The "Artifacts" routing rows live in [`references/artifacts.md`](references/artifacts.md).

The "Laminar depth" routing rows live in [`references/laminar_depth.md`](references/laminar_depth.md).

## 3. Invariants & Safeguards
1. **Cone of influence**: check `coi_mask` at edge time points; edge coefficients are contaminated by boundary zero-padding.
2. **Depth estimates report non-identifiability rather than a number.** `vflip`, `xflip` and `zflip` return `accepted=False` when the data does not support the motif, and `label_layers` then labels every channel `'na'`. Read `accepted` before reading any depth. A crossover contact is a depth on this probe, not an anatomical layer boundary, and `zflip`'s `apparent_velocity_m_s` is an apparent phase velocity, not a conduction velocity.
3. **Logarithm last**: average raw power across trials, divide by baseline, then take $10 \cdot \log_{10}$ once, at the reporting step. Never average decibels.
4. **Artifact substitution**: `repair_lfp_trials` substitutes the cross-trial median. `info` has no `frac_flagged` key: that value is the second return, and `info.get('frac_flagged', 0)` skips the check silently. The reported value is `max_fraction_trials_flagged_at_a_sample`, and the guard that acts on it is the `max_trial_fraction` argument (default 0.5): a sample flagged on more than that fraction of trials is treated as time-locked signal and never substituted, because past half the median is drawn mostly from flagged trials.
5. **Band edges**: `jnwb.CANONICAL_BANDS` is theta (4.0, 8.0), alpha (8.0, 14.0), beta (14.0, 30.0), low_gamma (30.0, 50.0) and high_gamma (50.0, 80.0) Hz. The band masks keep a bin when `lo <= f <= hi`, so both edges are inclusive, and a grid bin exactly at a shared edge (8 Hz, when the grid has one) counts in both adjacent bands.

## 4. Minimal Workflow
```python
# Input: stochastic synthetic.
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
- Morlet $L_1$ normalization: a unit cosine at $f_0$ yields peak $|z| = 1.0$.
- `TFRAccumulator.power()` matches the offline batch computation.

## 6. Documentation
- [`docs/04_spectral_analysis_and_tfr.md`](../../docs/04_spectral_analysis_and_tfr.md)
- [`docs/coherence_and_tfr.md`](../../docs/coherence_and_tfr.md)
- [`docs/05_artifact_detection_and_repair.md`](../../docs/05_artifact_detection_and_repair.md)
