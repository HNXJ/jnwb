---
name: jnwb-lfp-spectral
description: LFP filtering, Morlet wavelet complex TFR, streaming accumulation, coherence,
  and artifact repair.
---

# `jnwb-lfp-spectral` — LFP, Spectral Analysis & TFR Accumulation

## 1. Trigger
Activate this skill when computing continuous or trial-aligned LFP spectra, complex Time-Frequency Representations (TFR), multi-trial accumulation, cross-area coherence, or artifact detection and repair.

## 2. Task-to-Operation Routing Matrix
- `jnwb.complex_tfr(data, fs, freqs, n_cycles)`: Complex Morlet wavelet transform returning `ComplexTFR` with `z`, `freqs`, `times`, and `coi_mask`.
- `jnwb.band_power(lfp_trace, fs=None, freq_range=(1.0, 90.0), normalize=True, baseline=None)`: Scalar Welch band power. `normalize` defaults to **True**, which requires a non-empty `baseline` and raises `ValueError` without one; pass `normalize=False` for linear power in the input's units squared.
- `jnwb.aggregate_to_db(power, baseline, *, how="mean_of_ratios"|"ratio_of_means", aggregate_over=None)`: Decibels last — ratio aggregate then `10·log10` once. `how` is keyword-only and has no default: the estimand is named, not inherited.
- `jnwb.bandpass_filter(data, fs, low_cut, high_cut)`: Zero-phase Butterworth bandpass.
- `jnwb.notch_filter(data, fs, freq=60.0, q=30.0)`: IIR notch for line noise.
- `jnwb.TFRAccumulator(shape)`: Streaming mean and variance of a multi-trial TFR without holding every trial in memory.
- `jnwb.repair_lfp_trials(segments, times_ms, z_thresh=6.0)` → `(repaired, frac_flagged, info)`: Cross-channel synchrony detection ($z > 6.0$) and cross-trial median substitution. `frac_flagged` is the fraction of (trial, time) cells substituted.
- `jnwb.repair_band_artifacts(power, freqs, band_ranges=None, z_thresh=6.0, sided="upper")` → `(repaired, frac_flagged_by_band)`: TFR-domain outlier detection per band, repaired by cross-trial median substitution at the flagged (trial, time) cells.
- `jnwb.channel_correlation_matrix(data_ch_by_time)` & `jnwb.bad_channels_from_correlation(corr, z_thresh=5.0)`: Detect disconnected or excessively noisy probe channels.
- `jnwb.cross_area_coherence(lfp_area1, lfp_area2, fs=..., freq_bands=...)`: Magnitude-squared coherence between **two 1-D traces**. A 2-D array is refused by design: call it per channel pair rather than handing it a channels-by-time matrix. `freq_bands` is required: a `{name: (fmin, fmax)}` dict or `'canonical'`.
- `jnwb.imaginary_coherency(x, y, fs, freq_range=(1.0, 90.0))`: Imaginary part of coherency, reducing sensitivity to zero-phase-lag mixing. `icoh_mean` is signed: positive means `x` leads, the convention `phase_slope_index` follows. It does not confer immunity to volume conduction: a common source with non-zero lag, source mixing, a filter delay or reference-induced phase structure all survive it.
- `jnwb.aperiodic_fit(freqs, psd, freq_range, mode="fixed")`: Separates the aperiodic 1/f component from the spectrum; `mode="knee"` fits a knee. Returns `AperiodicFitResult` for a 1-D `psd` and a nested list of them, one per leading index, for a batch. When the optimiser fails it returns `accepted=False` with `exponent` and `offset` `None` rather than a number. A fit that converges is accepted however poorly it describes the spectrum, so read `r_squared` as well. `exponent` is positive for a 1/f decay.
- `jnwb.vflip(psd, freqs, *, band_low=(8.0, 30.0), band_high=(50.0, 150.0), min_support_score=3.75, device="cpu")` and `jnwb.vflip_from_lfp(lfp, fs, *, band_low=(8.0, 30.0), band_high=(50.0, 150.0))`: Frequency-layer inversion depth from a channels-by-frequency PSD, or from a channels-by-time LFP. `vflip_from_lfp(lfp, fs)` equals `vflip(psd, freqs)` with `freqs, psd = compute_psd(lfp, fs, axis=-1)`: note the reversed order and the `axis`. Returns `VFlipResult`; below the support threshold it returns `accepted=False` and `crossover_contact=None` rather than a guess.
- `jnwb.xflip(data, *, method="pearson", n_surrogates=200, alpha=0.05, min_boundary_drop=0.05, rng=None)`: Contiguous cross-channel correlation blocks tested against autocorrelation-preserving surrogates. Returns `XFlipResult`.
- `jnwb.label_layers(vflip_result, probe_geometry, *, granular_thickness_um=400.0)`: Layer labels relative to a verified crossover contact. Every channel is `'na'` when `vflip_result.accepted` is False -- layers are never imputed onto a rejected fit.
- `jnwb.current_source_density_1d(lfp_matrix, pitch_um, conductivity_s_per_m, axis=0)` and `jnwb.voltage_curvature_1d(lfp_matrix, pitch_um, axis=0)`: CSD in $\text{A}/\text{m}^3$ and the underlying $d^2V/dz^2$. **Negative is a sink** -- inward current, the signature of excitatory input -- and positive is the return source; the opposite convention is also in common use, so state which one a figure follows.
- `jnwb.wpli(x, y, fs, freq_range=(1.0, 90.0))`: Weighted Phase Lag Index reducing sensitivity to zero-phase-lag mixing. It is unsigned ($\ge 0$) and the same whichever signal is passed first, so it carries no direction: never infer which site leads from it. `imaginary_coherency` and `phase_slope_index` are the signed estimators.
- `jnwb.zflip(lfp_matrix, fs, freq_range=(15.0, 35.0), pitch_um=...)`: Cortical depth phase gradient, latency, and apparent velocity estimation across laminar contacts. When any adjacent pair fails the linear phase-frequency gate, `accepted` is False, `directionality` is `'unidentifiable'` and `apparent_velocity_m_s` is `None`. Without `pitch_um`, `apparent_velocity_m_s` is `None` even for an accepted fit.
- `jnwb.spectral_tilt(lfp_trace, fs, freq_range=(1.0, 100.0))`: Aperiodic $1/f$ spectral slope parameterization. Its `exponent` key is the signed log-log slope, **negative** for a 1/f decay -- the opposite sign of `aperiodic_fit`'s `exponent` under the same name.
- `jnwb.bipolar_reference(channel_data, channel_order=None)`: Local differential referencing for spatial artifact reduction.

- `jnwb.to_db(ratio)`: Turns a power ratio into decibels. Average power, divide by baseline, take the logarithm exactly once -- never average decibels. `relative_power(model="log_ratio")` takes the same logarithm itself.
- `jnwb.relative_power(power, baseline, *, model="mean_of_ratios", axis=None, device="cpu")`: Power against baseline under an explicit estimand. `"mean_of_ratios"` and `"ratio_of_means"` are different quantities, not two routes to one. It returns a bare array and records no model, so nothing downstream can recover which estimand produced a value: carry the model yourself wherever the value is stored or reported.
- `jnwb.compute_multitaper_psd(data, fs, nw=3.0, k_tapers=None, axis=-1)`: PSD by the DPSS multitaper method. `nw` sets the bandwidth-time product, so it sets the frequency resolution the estimate can support.
- `jnwb.morlet_wavelet(f0, fs, n_cycles=5.0, normalization="amplitude", cutoff_sigma=4.0)`: The complex Morlet kernel underneath the TFR. `n_cycles` trades frequency resolution against time resolution at every frequency.
- `jnwb.laplacian_reference(channel_data, channel_order=None)`: 1-D nearest-neighbor Laplacian re-reference along the probe's depth order. Pass `channel_order` unless the array is already in depth order, or the reference is spatially meaningless.
- `jnwb.harmonic_analysis(lfp_trace, fs=None, sampling_rate=None, freq_range=(1.0, 90.0), harmonic_orders=3, device="cpu")`: Fundamental and harmonic decomposition. A harmonic is evidence of a non-sinusoidal waveform, not of a second oscillator.
- `jnwb.pairwise_phase_consistency(phases, axis=-1)`: PPC (Vinck et al., 2010) across angular samples. Unlike the phase-locking value it is unbiased by sample count, which is why it is the right statistic when trial counts differ between conditions.
- `jnwb.detect_band_outliers(band_trace, z_thresh=6.0, sided="upper")`: Flags `(trial, time)` cells departing from the cross-trial trend.
- `jnwb.bad_trials_single_channel(trial_waveforms, corr_z_thresh=5.0, amp_z_thresh=5.0)`: Flags trials of one good channel, shaped `(n_trials, n_times)`, by correlation to the trial mean and by amplitude.
- `jnwb.trial_correlation_matrix(trial_waveforms)`: The `(n_trials, n_trials)` correlation matrix of one channel's trials, which is what the flagging above reads.

- `jnwb.compute_psd(lfp_data, fs, axis=0)` → `(freqs, psd)`: Welch PSD of a plain LFP array, with time along `axis`. `axis=0` reads `(n_times, n_channels)` and returns frequency-by-channels. For the channels-by-frequency input `vflip` expects, pass a `(n_channels, n_times)` array with `axis=-1`. A channels-by-time array left at `axis=0` is segmented across channels and returns a spectrum of a few bins without raising.
- `jnwb.consensus_bad_trials(per_channel_flags, min_frac_channels=0.5)`: Reduces `(n_good_channels, n_trials)` per-channel flags to a trial verdict; a trial is excluded only when at least `min_frac_channels` of channels flag it, so one bad channel cannot delete the session.

## 3. Invariants & Safeguards
1. **Cone of Influence (COI)**: Always check `coi_mask` when analyzing edge time points; edge coefficients are contaminated by boundary zero-padding.
0. **Depth estimates report non-identifiability rather than a number.** `vflip`, `xflip` and `zflip` all return `accepted=False` when the data does not support the motif, and `label_layers` then labels every channel `'na'`. Read `accepted` before reading any depth. A crossover contact is a depth on this probe, not an anatomical layer boundary, and `zflip`'s `apparent_velocity_m_s` is an apparent phase velocity, not a conduction velocity.
2. **Logarithm Last**: Compute average raw power across trials first, then compute $10 \cdot \log_{10}(\text{power})$ at the reporting step.
3. **LFP Artifact Substitution vs Exclusion**: `repair_lfp_trials` uses cross-trial median substitution. `info` has no `frac_flagged` key -- that value is the second return, and `info.get('frac_flagged', 0)` skips the check silently. The reported value is `max_fraction_trials_flagged_at_a_sample`, and the guard that acts on it is the `max_trial_fraction` argument (default 0.5): a sample flagged on more than that fraction of trials is treated as time-locked signal and never substituted, because past half the median is drawn mostly from flagged trials.

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
