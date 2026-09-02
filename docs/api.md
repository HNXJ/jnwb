# Complete API Reference

All 101 core functions, classes, and constants are exported at the top-level `jnwb` namespace.

---

## 1. Time-Frequency Representations & Accumulation

| Symbol | Signature / Description |
|---|---|
| `jnwb.complex_tfr` | `complex_tfr(data, fs, freqs, n_cycles=5.0, time_axis=-1, normalization="amplitude", dtype=np.complex128, coi_sigma=2.0)` |
| `jnwb.morlet_wavelet` | `morlet_wavelet(f0, fs, n_cycles=5.0, normalization="amplitude", cutoff_sigma=4.0)` |
| `jnwb.ComplexTFR` | Dataclass holding `z`, `freqs`, `times`, `coi_mask`, `fs`, `n_cycles`, `normalization`, `power`, `phase`, `amplitude` |
| `jnwb.TFRAccumulator` | Streaming Welford accumulator for single-trial TFR matrices (`power`, `variance`, `itc`, `evoked`, `induced`) |
| `jnwb.assert_mergeable` | `assert_mergeable(attrs1, attrs2, ignore_keys=None)` |
| `jnwb.TFRAnalyzer` | High-level coordinate-explicit band extractor (`extract_band`, `validate_freq_alignment`) |

---

## 2. Spectral Analysis & Oscillatory Dynamics

| Symbol | Signature / Description |
|---|---|
| `jnwb.compute_psd` | `compute_psd(x, fs, nperseg=None, noverlap=None)` |
| `jnwb.band_power` | `band_power(signal, sampling_rate, freq_range=(15.0, 30.0), nperseg=None)` |
| `jnwb.spectral_tilt` | `spectral_tilt(signal, sampling_rate, fit_range=(1.0, 100.0))` |
| `jnwb.cross_area_coherence` | `cross_area_coherence(sig1, sig2, sampling_rate, freq_bands=None)` |
| `jnwb.imaginary_coherency` | `imaginary_coherency(sig1, sig2, sampling_rate, freq_range)` |
| `jnwb.phase_locking_value` | `phase_locking_value(phases1, phases2, axis=-1)` |
| `jnwb.harmonic_analysis` | `harmonic_analysis(signal, sampling_rate, fundamental_freq, n_harmonics=4)` |
| `jnwb.bipolar_reference` | `bipolar_reference(lfp_data, channel_pairs)` |
| `jnwb.laplacian_reference` | `laplacian_reference(lfp_grid)` |
| `jnwb.to_db` | `to_db(power_ratio)` |
| `jnwb.CANONICAL_BANDS` | Dictionary of canonical frequency band definitions |

---

## 3. Spiking, PSTH & Onset Dynamics

| Symbol | Signature / Description |
|---|---|
| `jnwb.raster_psth` | `raster_psth(spike_times, event_onsets, win_ms=(-100, 300), bin_ms=10.0)` |
| `jnwb.compute_response_metrics` | `compute_response_metrics(time_bins, psth_mean, baseline_win, response_win)` |
| `jnwb.phase_locking_index` | `phase_locking_index(spike_times, lfp, lfp_times, freq_band, fs)` |
| `jnwb.cross_correlation` | `cross_correlation(spikes1, spikes2, max_lag_ms=50.0, bin_ms=1.0)` |
| `jnwb.causal_exp_smooth` | `causal_exp_smooth(signal, bin_ms, tau_ms)` |
| `jnwb.fit_exponential_onset` | `fit_exponential_onset(time_bins, psth, t0_bounds, baseline_win=None)` |
| `jnwb.UnitAnalyzer` | Object-oriented unit quality and autocorrelogram metrics |
| `jnwb.PopulationAnalyzer` | Multi-unit population PSTH and cross-condition comparisons |

---

## 4. Resampling Statistics & Hypothesis Testing

| Symbol | Signature / Description |
|---|---|
| `jnwb.StatisticalAnalysis` | Class containing `bootstrap_ci`, `paired_fire_prob_test`, `confirmatory_compare` |
| `jnwb.exploratory_compare` | `exploratory_compare(group_a, group_b, rng=None)` |
| `jnwb.confirmatory_compare` | `confirmatory_compare(group_a, group_b, alternative="two-sided")` |
| `jnwb.permute_labels` | `permute_labels(labels, group_ids=None, scheme="global", rng=None)` |
| `jnwb.cluster_permutation_1d` | `cluster_permutation_1d(t_stat_series, surrogate_matrix, threshold)` |
| `jnwb.fdr_correct` | `fdr_correct(p_values, alpha=0.05, method="bh")` |
| `jnwb.bonferroni_correct` | `bonferroni_correct(p_values, alpha=0.05)` |
| `jnwb.clopper_pearson_ci` | `clopper_pearson_ci(k, n, alpha=0.05)` |

---

## 5. Directed Connectivity & Information Theory

| Symbol | Signature / Description |
|---|---|
| `jnwb.granger` | `granger(X, Y, order=2, n_surrogates=100, seed=42)` |
| `jnwb.phase_slope_index` | `phase_slope_index(X, Y, fs, freq_range, nperseg=None)` |
| `jnwb.transfer_entropy` | `transfer_entropy(X, Y, k=1, l=1, n_surrogates=50, seed=42)` |
| `jnwb.DirectedResult` | Dataclass holding directional connectivity metrics and surrogate p-values |

---

## 6. Population Decoding & Trajectories

| Symbol | Signature / Description |
|---|---|
| `jnwb.nested_cv_linear_svm` | `nested_cv_linear_svm(X, y, n_splits=5, c_values=(0.01, 0.1, 1.0, 10.0), random_state=42)` |
| `jnwb.compute_population_trajectory` | `compute_population_trajectory(data_tensor, n_components=3)` |
| `jnwb.time_resolved_trajectory` | `time_resolved_trajectory(data_tensor, labels, time_bins)` |
| `jnwb.majority_baseline` | `majority_baseline(labels)` |
| `jnwb.stratified_cv_splits` | `stratified_cv_splits(y, n_splits=5, random_state=42)` |

---

## 7. Artifact Detection & Repair

| Symbol | Signature / Description |
|---|---|
| `jnwb.channel_correlation_matrix` | `channel_correlation_matrix(multichannel_data)` |
| `jnwb.detect_flat_or_noisy_channels` | `detect_flat_or_noisy_channels(data, corr_thresh=0.2, var_thresh=1e-6)` |
| `jnwb.detect_extreme_events` | `detect_extreme_events(data, threshold_sd=6.0)` |
| `jnwb.repair_lfp_trials` | `repair_lfp_trials(lfp_trials, threshold_sd=4.0, exclude_window_ms=None)` |
| `jnwb.zero_nan_segments` | `zero_nan_segments(data)` |
| `jnwb.interpolate_missing_channels` | `interpolate_missing_channels(data, bad_channels)` |

---

## 8. Anatomical Addressing & Standardization

| Symbol | Signature / Description |
|---|---|
| `jnwb.map_peak_channel_to_area` | `map_peak_channel_to_area(peak_channel_id, electrodes_df)` |
| `jnwb.canonicalize_area_name` | `canonicalize_area_name(area_str)` |
| `jnwb.infer_layer` | `infer_layer(depth_um, area_name)` |
| `jnwb.standardize_units_table` | `standardize_units_table(units_df, electrodes_df)` |
| `jnwb.build_session_manifest` | `build_session_manifest(nwb_file_paths)` |
| `jnwb.compress_fp32` | `compress_fp32(input_nwb_path, output_nwb_path=None)` |

---

## 9. Publication Vector Graphics

| Symbol | Signature / Description |
|---|---|
| `jnwb.setup_vector_graphics` | `setup_vector_graphics(font_family="sans-serif", font_size=8)` |
| `jnwb.apply_tight_auto_axis` | `apply_tight_auto_axis(ax, x_span=None, y_margin=0.08)` |
| `jnwb.save_figure_suite` | `save_figure_suite(fig, output_stem, formats=("svg", "png", "pdf"))` |
| `jnwb.PUBLICATION_PALETTE` | Standard accessible color palette dictionary |
