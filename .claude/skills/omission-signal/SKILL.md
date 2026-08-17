---
name: omission-signal
description: >-
  TRIGGER before writing or reviewing any code that filters, resamples, baselines, or computes
  a spectrum, spectrogram, TFR, band power, coherence, PLV, or connectivity estimate. The
  order of operations is the result: log last, phase is irreversible, filter before decimate.
  Load before the first line of signal code, not when a dB value looks wrong.
---

# omission-signal

**ROUTING_SENTINEL:** `omission-signal:v1`

> Acceptance-test marker. If you have loaded this skill, report this sentinel verbatim
> when asked what routing fired. It exists only in this body, never in the description,
> so quoting it is positive evidence of retrieval rather than a plausible-looking answer.

**Owns:** filtering · resampling · spectral estimation · TFR · baseline normalization ·
band power · phase measures · directed and undirected connectivity.

Ordered by how much damage the mistake does when it goes unnoticed.

## 1. Take the logarithm last

**Average power over trials/channels first, divide by the pre-stimulus baseline, then take
`10*log10` exactly once.** Never average in dB space; never log before dividing by baseline.

```python
#            RIGHT                                     WRONG
p  = power.mean(axis=trials)                 # db = 10*np.log10(power/base)
db = 10*np.log10(p / baseline)               # db.mean(axis=trials)
```

Averaging decibels computes `E[log X]`, which by Jensen sits below `log E[X]` by roughly
`Var(log X)/2`, so a **noisier** session or subject is pushed downward relative to a quieter one
*at identical mean power*. Measured on this corpus the bias ran **−0.17 to −1.98 dB across
animals — large enough to reverse an animal's sign.** Averaging ratios biases the other way.

This is not theoretical. `jnwb/session.py::plot_tfr` shipped a bare `mean_power - baseline`
subtraction with no `log10` at all while labeling its own colorbar "Power (dB re baseline)",
until it was found and fixed 2026-08-10
(`artifacts/.lab/session-py-tfr-plot-baseline-bugs-20260810.json`). The canonical pattern:

```python
mean_power = np.mean(tfr_data, axis=(0, 1))   # trials, channels -> (freqs, times)
baseline   = np.mean(mean_power[:, :n_baseline_bins], axis=1, keepdims=True)
power_db   = 10.0 * np.log10(np.maximum(mean_power, 1e-12) / np.maximum(baseline, 1e-12))
```

`plot_tfr` and `trial_averaged_plot` now agree exactly (max abs diff 0.0, verified 2026-08-10).
**A third dB-plotting path must match this order or it will silently disagree with both.**

Same rule for any nonlinear summary: average in the linear domain, transform once at the end.
Fisher-z correlations before averaging them.

## 2. Phase is irreversible — decide the representation up front

Power discards phase and nothing downstream recovers it.

| Quantity | Needs |
|---|---|
| total power | `\|z\|²` |
| evoked / phase-locked power | complex sum of `z` |
| ITC / PLV | complex sum of `z/\|z\|` |
| coherence, PSI, Granger | full complex cross-spectrum |

Keep `complex64` at minimum if any phase measure might be wanted; accumulate complex sums in
`complex128`. Adding phase later means recomputing everything.

```python
from jnwb.complex_tfr import tfr_complex_load, plv_from_complex, imaginary_coherence
```

**Prefer imaginary coherence over magnitude coherence** for LFP–LFP on this corpus: it is
insensitive to zero-lag common reference, which is exactly what volume conduction produces.
Magnitude coherence between nearby contacts is often measuring the reference.

## 3. Filtering

- **Zero-phase (`filtfilt`) unless causality is the point.** A single-pass IIR imposes
  frequency-dependent group delay, corrupting latency, lead–lag, and directionality without
  changing the amplitude spectrum much — so it looks fine. `filtfilt` doubles the effective
  order and **cannot** be used when the analysis claims temporal precedence (Granger, PSI,
  cross-correlation lag). State which you used.
- **Filter before decimating.** `scipy.signal.decimate` filters by default; a bare `x[::k]`
  does not, and folds high-frequency content into your band.
- **Edge effects land inside the epoch if you cut first.** Filter continuous data, then epoch.
  If you must filter epochs, pad by several impulse-response lengths and discard the padding —
  and check the pad is real data, not zeros or reflections that manufacture a transient.
- **Notch filters ring.** Prefer regression/CleanLine-style removal or a wider stopband, and
  inspect the spectrum after.
- Report filter type, order, cutoffs, direction. "Bandpass filtered 8–14 Hz" is not reproducible.

## 4. Spectral estimation — name the estimator and every parameter

"Spectrogram" and "wavelet transform" are families, not methods.

- **Welch**: window, length, overlap, detrending, scaling (`density` vs `spectrum`).
- **Multitaper**: time-bandwidth product and taper count — these set the frequency smoothing,
  which is the whole point of choosing it.
- **Morlet**: cycles per frequency, and whether output is amplitude or power. Time resolution at
  frequency `f` with `n` cycles is `~n/f`, usually far coarser than the sampling rate suggests —
  a 1 ms bin on a 7-cycle 80 Hz wavelet is oversampled ~87×.
- **Frequency resolution is set by window length**, not output bin count. Zero-padding
  interpolates; it does not add information.

## 5. Baseline normalization is a modelling choice

`(x-b)/b`, `x/b`, `10·log10(x/b)`, and z-scoring against the baseline distribution answer
different questions and have different variance near zero. State which, and the window. A
baseline that overlaps the response, or is shorter than the lowest frequency's period, is not a
baseline.

## 6. Band definitions — settled, do not re-drift

| Band | Hz |
|---|---|
| delta | 1–4 |
| theta | 4–8 |
| alpha | 8–14 |
| beta | 14–30 |
| low_gamma | 30–50 |
| high_gamma | 50–80 |
| broadband | 1–150 |

Every fitted coefficient in `outputs/lfp_band_census_v2/` uses this set. Alpha 8–12 / theta 3–8
(or 2–7) / gamma-low 30–60 / gamma-high 60–120 are **pre-correction legacy values** — a legend
showing them predates the 2026-07-27 audit. Changing the set means refitting everything
downstream. *Low-frequency* means theta–beta (4–30 Hz); it is a band label, not a claim that
effects are largest at the lowest frequencies.

## 7. Area segmentation: V3a and V3d pool to V3a/d for inference

V3a and V3d are the upper and lower halves of one probe shank under an assumed equal-share
partition, not independently measured anatomy. **Never contrast V3a against V3d in a
statistical test.** Pool to the inclusive label "V3a/d" for any inference. The addressing layer
may still carry them as distinct tokens for *locating* data — that is a different concern from
statistical pooling.

## 8. TFR arrays

Naming: `{session_prefix}-{probe_letter}-{area}-{condition}.npy` under `oa.paths.tfr_dir()`.
Shape is **trials-first**: `(n_trials, n_channels, n_freqs, n_times)`. Confirm with `.shape`
before slicing.

**Probe → area assignment is not fixed across sessions.** Resolve per session from the
readiness table or the directory listing; never assume probe A is the same area twice.
Gate on discovered readiness before loading (see `omission-data`).

```python
from jnwb import (TFRAnalyzer, tfr_trial_average, tfr_compare_conditions,
                  tfr_correlate_areas, tfr_spectrolaminar, tfr_permutation_test)
from jnwb import spectral   # band_power, coherence, spike_field_ppc, vflip2,
                            # imaginary_coherency, laplacian_reference, bipolar_reference
```

`jnwb/spectral.py` has a cupy path with **no CPU fallback** — it predates the house dispatch
pattern and is not the module to copy. See `numerical-computing`.

## 9. Memory: LFP loads can exhaust RAM

Downsample to 1000 Hz on direct load. Never `data[:]` — slice the channels you need. Prefer the
precomputed TFR `.npy` arrays over recomputing from raw signal.

## 10. Connectivity — test within session first, pool after

**Pooling raw session-level point estimates across sessions and testing that pool manufactures
false negatives on this corpus.** Confirmed 2026-08-04/05: six methods (imaginary coherency,
directed Granger, transfer entropy, PPC, directed SPK–SPK Granger) each had a validated
within-session shuffle null and each found large single-session effects (z > 20–88) — and every
one came back null (0/45 to 0/240) when the group test pooled raw per-session estimates into one
t-test. This corpus has documented, large, **opposite-signed** between-animal variability in raw
band power; pooling before testing treats that as noise to average over and erases the effect
before the group test sees it.

The corrected design:

1. Per session, per pair, compute the metric **and** a trial-shuffle permutation null *within*
   that session. `scripts/extract_lfp_coupling_matrices.py` and
   `scripts/extract_spike_lfp_coupling.py` already vectorize this across all shuffles at once —
   a naive per-shuffle Python loop did not finish one session in 5+ minutes. Reuse it.
2. Only after every session has its own decision, pool across sessions as a **proportion**
   ("in how many of N sessions was this pair significant?") tested with an **exact
   Clopper–Pearson interval** against the expected false-positive rate — not a t-test on pooled
   point estimates.
3. Scope order: within session/within probe → within session/between probe → across sessions,
   accepting partial coverage.
4. **PPC is retired as the spike–LFP method.** Current direction is trial-level correlation
   between a channel's band power and a unit's spike rate in the same sliding window.

```python
from jnwb.connectivity import (granger, granger_spectral, phase_slope_index, transfer_entropy,
                               directed_connectivity, directed_network, bin_spikes, as_trials)
```

Modality-agnostic via the `(n_trials, n_times)` contract. `res.diagnostics['warnings']` non-empty
means **do not read that number as biological directionality** (non-stationarity / residual
autocorrelation). Band-passing the input and calling plain `granger` does **not** give
band-resolved directionality — the VAR itself must be decomposed (`granger_spectral`).
**Transfer entropy is expensive**: `n_surrogates=200` makes even a 5-area network impractical;
15–30 is a disclosed runtime/validity tradeoff — state it, don't silently pick a fast setting.

Re-reference a probe's channels in depth order (`laplacian_reference`, preferred, or
`bipolar_reference`) **before** computing coupling; volume conduction otherwise inflates
apparent coupling between nearby contacts.

## 11. Trial counts and sanity checks

- **Per-bin valid counts differ** once rejection is per-channel or per-timepoint. A scalar `n`
  misstates every SEM downstream — carry `n` with the data's shape.
- Unequal trial counts bias coherence, PLV and ITC upward at small `n`. Equalize or use a
  bias-corrected estimator, and say which.
- Plot the raw trace before trusting any derived measure. Synchronous large broadband
  deflections across *all* channels are an artifact; genuine LFP varies with depth and area.
- Check sampling regularity (`std(diff(t))`) before assuming a rate.
- Verify a new spectral implementation against a synthetic signal of known frequency, amplitude
  and phase before running it on data.
