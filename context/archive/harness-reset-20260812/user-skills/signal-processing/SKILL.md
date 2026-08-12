---
name: signal-processing
description: |
  Filtering, resampling, spectral estimation, time-frequency, phase measures
  (coherence/PLV/ITC), baseline normalization, and the log-order (dB) trap for
  neural time series. Use before writing or reviewing code that filters, resamples,
  or computes any spectrum, spectrogram, TFR, coherence, or band power.
---

# Signal processing

Ordered by how much damage the mistake does when it goes unnoticed.

## 1. Take the logarithm last

A decibel change can be formed several ways and they are **not** equivalent.

```python
#            RIGHT                                    WRONG
p = power.mean(axis=trials)                 # db = 10*log10(power/base)
db = 10*np.log10(p / baseline)              # db.mean(axis=trials)
```

Averaging decibels computes `E[log X]`, which by Jensen sits below `log E[X]` by roughly
`Var(log X)/2`. So a **noisier** session or subject is pushed downward relative to a quieter
one *at identical mean power*. Measured on one real corpus the bias ran **−0.17 to −1.98 dB
across subjects — enough to reverse a subject's sign.** Averaging ratios biases the other way.

Same rule for any nonlinear summary: average in the linear domain, transform once at the end.
If you must average logs (e.g. log-normal data by design), say so and justify it.

## 2. Phase is irreversible — decide the representation up front

Power discards phase. Nothing downstream recovers it.

| Quantity | Needs |
|---|---|
| total power | `\|z\|²` |
| evoked / phase-locked power | complex sum of `z` |
| ITC / PLV | complex sum of `z/\|z\|` |
| coherence, PSI, Granger | full complex cross-spectrum |

If there is any chance a phase measure will be wanted, keep `complex64` at minimum. Adding it
later means recomputing everything. Accumulate complex sums in `complex128`.

**Prefer imaginary coherence over magnitude coherence for sensor/electrode pairs** — it is
insensitive to zero-lag common reference, which is exactly what volume conduction and a shared
reference produce. Magnitude coherence between nearby channels is often measuring the
reference.

## 3. Filtering

- **Zero-phase (`filtfilt`) unless causality is the point.** A single-pass IIR imposes
  frequency-dependent group delay, which corrupts latency, lead-lag, and directionality
  results without changing the amplitude spectrum much — so it looks fine. State which you
  used. Note `filtfilt` doubles the effective filter order and cannot be used when the
  analysis claims temporal precedence (Granger, PSI, cross-correlation lag).
- **Filter before decimating.** Decimation without an anti-alias filter folds high-frequency
  content into your band. `scipy.signal.decimate` filters by default; a bare slice `x[::k]`
  does not.
- **Edge effects land inside the epoch if you cut first.** Filter continuous data, then epoch.
  If you must filter epochs, pad by several times the filter's impulse-response length and
  discard the padding — and check that the pad region is real data, not zeros or reflections
  that manufacture a transient.
- **Notch filters ring.** A narrow notch at line frequency has a long impulse response and
  smears line-noise transients across time. Prefer regression/CleanLine-style removal, or a
  wider stopband, and inspect the spectrum after.
- Report filter type, order, cutoffs, and direction. "Bandpass filtered 8–12 Hz" is not
  reproducible.

## 4. Spectral estimation

Name the estimator and every parameter. "Spectrogram" and "wavelet transform" are families.

- **Welch**: window, length, overlap, detrending, scaling (`density` vs `spectrum`).
- **Multitaper**: time-bandwidth product and number of tapers — these set the frequency
  smoothing, which is the whole point of choosing it.
- **Morlet/wavelet**: cycles per frequency (fixed or frequency-dependent), and whether the
  output is amplitude or power. Time resolution at frequency `f` with `n` cycles is `~n/f` —
  this bounds how finely you can bin time, and it is usually far coarser than the sampling
  rate suggests. A 1 ms time bin on a 7-cycle 80 Hz wavelet is oversampled by ~87×.
- **Frequency resolution is set by window length**, not by the number of output bins. Zero-
  padding interpolates; it does not add information.
- Log-spaced frequencies for broadband work; state the spacing.

## 5. Baseline normalization is a modelling choice

`(x - b)/b`, `x/b`, `10·log10(x/b)`, and z-score against baseline distribution answer different
questions and have different variance properties near zero. State which, and the baseline
window. A baseline that overlaps the response, or that is shorter than the lowest frequency's
period, is not a baseline.

## 6. Trial counts and artifact rejection

- **Per-bin valid counts differ** once artifact rejection is per-channel or per-timepoint.
  A scalar `n` misstates every SEM downstream. Carry `n` with the data's shape.
- Unequal trial counts across conditions bias variance-based measures (coherence, PLV, ITC are
  all biased upward at small `n`). Equalize, or use a bias-corrected estimator, and say which.

## 7. Sanity checks that catch real errors

- Plot the raw trace before trusting any derived measure. Synchronous, large, broadband
  deflections across *all* channels at once are a movement/electrode artifact, not neural
  signal — genuine LFP varies with depth and area.
- Check sampling regularity (`std(diff(t))`) before assuming a rate; if it is regular to
  numerical precision, store `rate` + `starting_time` rather than a timestamp array.
- Verify a new spectral implementation against a synthetic signal with known frequency,
  amplitude, and phase before running it on data.
- Round-trip check any dtype cast: re-read and compare against the original within a stated
  tolerance.
