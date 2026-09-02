# Complete API Reference

All 101 core functions, classes, and constants exported in the top-level jnwb namespace.

## Module: jnwb.addressing

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.classify_layer_from_depth | function | classify_layer_from_depth(peak_channel_id: float, electrodes_df: pandas.core.frame.DataFrame) -> str<br>*Classify unit cortical layer using z depth coordinates.* |
| jnwb.enrich_units_dataframe | function | enrich_units_dataframe(units_df: pandas.core.frame.DataFrame, electrodes_df: pandas.core.frame.DataFrame | None) -> pandas.core.frame.DataFrame<br>*Enrich units DataFrame with standardized area, layer, and quality flags.* |
| jnwb.map_peak_channel_to_area | function | map_peak_channel_to_area(peak_channel_id: float, electrodes_df: pandas.core.frame.DataFrame) -> str | None<br>*Map peak channel ID to brain area location.* |

## Module: jnwb.analyzers

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.PopulationAnalyzer | class | *Population-Level Statistics.* |
| jnwb.TFRAnalyzer | class | *Time-Frequency Representation Analysis.* |
| jnwb.UnitAnalyzer | class | *Single-Unit Spike Analysis.* |

## Module: jnwb.artifact_detection

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.bad_channels_from_correlation | function | bad_channels_from_correlation(corr: 'np.ndarray', z_thresh: 'float' = 5.0) -> 'Tuple[np.ndarray, np.ndarray, np.ndarray]'<br>*corr: (n_ch, n_ch). Returns (bad_mask, summary_per_channel, z_per_channel).* |
| jnwb.bad_trials_single_channel | function | bad_trials_single_channel(trial_waveforms: 'np.ndarray', corr_z_thresh: 'float' = 5.0, amp_z_thresh: 'float' = 5.0) -> 'Tuple[np.ndarray, np.ndarray, np.ndarray]'<br>*trial_waveforms: (n_trials, n_times), single GOOD channel.* |
| jnwb.channel_correlation_matrix | function | channel_correlation_matrix(data_ch_by_time: 'np.ndarray') -> 'np.ndarray'<br>*data_ch_by_time: (n_channels, n_samples). Returns (n_channels, n_channels) Pearson corr.* |
| jnwb.consensus_bad_trials | function | consensus_bad_trials(per_channel_flags: 'np.ndarray', min_frac_channels: 'float' = 0.5) -> 'Tuple[np.ndarray, np.ndarray]'<br>*per_channel_flags: (n_good_channels, n_trials) bool. A trial is excluded only if flagged* |
| jnwb.trial_correlation_matrix | function | trial_correlation_matrix(trial_waveforms: 'np.ndarray') -> 'np.ndarray'<br>*trial_waveforms: (n_trials, n_times), single channel. Returns (n_trials, n_trials) corr.* |

## Module: jnwb.artifact_repair

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.repair_band_artifacts | function | repair_band_artifacts(power, freqs, band_ranges=None, z_thresh=6.0)<br>*Per-band, cross-trial-median substitution of sparse single-trial TFR power spikes.* |
| jnwb.repair_lfp_trials | function | repair_lfp_trials(segments, times_ms=None, z_thresh=6.0, exclude_window_ms=None, reward_window_ms=None, min_trials=5)<br>*Cross-channel-synchrony detection + cross-trial-median substitution.* |

## Module: jnwb.compression

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.compress_fp32 | function | compress_fp32(src: "'str | Path'", dst: "'str | Path | None'" = None, *, drop_convolved: 'bool' = False, verify: 'bool' = True, n_check: 'int' = 200000, overwrite: 'bool' = False) -> 'dict'<br>*Compress one NWB file: float32 LFP/MUAE, chunking, gzip1+shuffle, compaction.* |

## Module: jnwb.connectivity

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.DirectedResult | class | *Uniform return type for every directed connectivity estimator.* |
| jnwb.as_trials | function | as_trials(X, time_axis: 'int' = -1, name: 'str' = 'X', allow_ragged: 'bool' = True) -> 'np.ndarray'<br>*Normalize any supported signal container to a ``(n_trials, n_times)`` float array.* |
| jnwb.bin_spikes | function | bin_spikes(spike_times, window: 'Tuple[float, float]', bin_size_ms: 'float' = 10.0, trial_starts: 'Optional[Sequence[float]]' = None, output: 'str' = 'count', return_centers: 'bool' = False)<br>*Bridge spike data into the ``(n_trials, n_bins)`` contract used by every* |
| jnwb.binary_occupancy_mutual_information | function | binary_occupancy_mutual_information(spike_times1: 'np.ndarray', spike_times2: 'np.ndarray', time_window: 'Tuple[float, float]', bin_size_ms: 'float' = 10.0) -> 'float'<br>*Explicit alias for binary occupancy MI.* |
| jnwb.directed_connectivity | function | directed_connectivity(X, Y, method: 'str' = 'granger', **kwargs) -> 'DirectedResult'<br>*One entry point for all three directed estimators.* |
| jnwb.directed_network | function | directed_network(signals, method: 'str' = 'granger', labels: 'Optional[Sequence[str]]' = None, fdr: 'bool' = True, fdr_method: 'str' = 'bh', **kwargs) -> 'Dict[str, Any]'<br>*All-pairs directed connectivity over N nodes.* |
| jnwb.granger | function | granger(X, Y, order: 'Union[int, str]' = 'auto', max_lag: 'int' = 20, criterion: 'str' = 'bic', Z=None, ridge: 'float' = 0.0, detrend: 'Optional[str]' = 'zscore', n_surrogates: 'int' = 0, seed: 'Optional[int]' = 0, time_axis: 'int' = -1) -> 'DirectedResult'<br>*Bivariate or conditional Granger causality between two arbitrary signals.* |
| jnwb.granger_causality | function | granger_causality(signal1: 'np.ndarray', signal2: 'np.ndarray', order: 'Union[int, str]' = 5, device: 'str' = 'cpu', ridge: 'float' = 0.0, criterion: 'str' = 'aic') -> 'Dict[str, Union[float, dict, list]]'<br>*Compute bivariate Granger Causality (GC) values between two continuous signals.* |
| jnwb.granger_spectral | function | granger_spectral(X, Y, fs: 'float', order: 'Union[int, str]' = 'auto', max_lag: 'int' = 20, criterion: 'str' = 'bic', n_freqs: 'int' = 256, bands: 'Union[str, Dict[str, Tuple[float, float]], Tuple[float, float], None]' = None, ridge: 'float' = 0.0, detrend: 'Optional[str]' = 'zscore', n_surrogates: 'int' = 0, seed: 'Optional[int]' = 0, time_axis: 'int' = -1) -> 'DirectedResult'<br>*Frequency-resolved Granger causality (Geweke, 1982) — directionality per band.* |
| jnwb.network_topology | function | network_topology(adjacency_matrix: 'np.ndarray', threshold: 'float' = 0.3) -> 'Dict[str, Union[float, int, List[int]]]'<br>*Compute network graph metrics from a correlation or Granger causality matrix.* |
| jnwb.phase_slope_index | function | phase_slope_index(X, Y, fs: 'float', bands: 'Union[str, Dict[str, Tuple[float, float]], Tuple[float, float], None]' = None, nperseg: 'Optional[int]' = None, noverlap: 'Optional[int]' = None, window: 'str' = 'hann', detrend: 'Optional[str]' = 'demean', jackknife: 'bool' = True, n_surrogates: 'int' = 0, seed: 'Optional[int]' = 0, time_axis: 'int' = -1) -> 'DirectedResult'<br>*Phase Slope Index (Nolte et al., 2008) — which signal leads in phase.* |
| jnwb.spike_count_mutual_information | function | spike_count_mutual_information(spike_times1: 'np.ndarray', spike_times2: 'np.ndarray', time_window: 'Tuple[float, float]', bin_size_ms: 'float' = 10.0) -> 'float'<br>*Discrete MI on per-bin spike counts.* |
| jnwb.spike_mutual_information | function | spike_mutual_information(spike_times1: 'np.ndarray', spike_times2: 'np.ndarray', time_window: 'Tuple[float, float]', bin_size_ms: 'float' = 10.0, estimator: 'str' = 'binary_occupancy') -> 'float'<br>*Compute Shannon Mutual Information (MI) between two binned spike trains.* |
| jnwb.transfer_entropy | function | transfer_entropy(X, Y, k: 'int' = 1, l: 'int' = 1, delay: 'int' = 1, estimator: 'str' = 'quantile', bins: 'int' = 4, symbolic_order: 'int' = 3, bias_correction: 'Optional[str]' = 'mm', n_surrogates: 'int' = 200, seed: 'Optional[int]' = 0, detrend: 'Optional[str]' = None, time_axis: 'int' = -1) -> 'DirectedResult'<br>*Transfer entropy — model-free, nonlinear directed information flow, in bits.* |

## Module: jnwb.core

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.CANONICAL_BANDS | constant/module | dict |
| jnwb.paths | constant/module | module |
| jnwb.visual_qc | constant/module | module |

## Module: jnwb.decoding

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.assign_outer_folds | function | assign_outer_folds(trials: 'pd.DataFrame', *, analysis_cols: 'tuple' = ('session', 'analysis', 'slot_key'), group_col: 'str' = 'cycle') -> 'pd.DataFrame'<br>*Assign deterministic leave-one-group-out outer folds without touching features.* |
| jnwb.build_inner_validation_partitions | function | build_inner_validation_partitions(outer_trials: 'pd.DataFrame', *, analysis_cols: 'tuple' = ('session', 'analysis', 'slot_key')) -> 'pd.DataFrame'<br>*Build nested inner train/validation partitions from outer-training groups.* |
| jnwb.build_representation_ladder | function | build_representation_ladder(raster: 'np.ndarray', *, modality: 'str' = 'SPK', spatial_axis_metadata: 'Union[Mapping[str, object], None]' = None) -> 'Dict[str, object]'<br>*Return R0/R1/R2 representation contracts without fitting a model.* |
| jnwb.fold_majority_baseline | function | fold_majority_baseline(y_train: 'np.ndarray', y_test: 'np.ndarray') -> 'float'<br>*Accuracy of predicting the training-fold majority class on the held-out fold.* |
| jnwb.majority_baseline | function | majority_baseline(labels: 'np.ndarray') -> 'float'<br>*Accuracy of always predicting the most frequent class in ``labels``.* |
| jnwb.nested_cv_linear_svm | function | nested_cv_linear_svm(X: 'np.ndarray', labels: 'np.ndarray', n_splits: 'int') -> 'Dict[str, Union[float, np.ndarray, dict, str]]'<br>*Outer stratified CV; inner GridSearchCV for C. No synthetic metrics.* |

## Module: jnwb.jrsa

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.JRSAResult | class | *Container returned by jrsa().* |
| jnwb.jrsa | function | jrsa(x1, x2=None, adim=-1, labels=None, align='auto', align_mode='fraction', reduction=None, metric='rsa', lag=0, window=None, sliding=False, normalize=False, standardize=False, detrend=False, nan_policy='omit', stats=True, permutations=1000, bootstrap=0, correction='fdr_bh', alpha=0.05, alternative='two-sided', backend='auto', device='auto', n_jobs=-1, batch_size=None, random_state=None, return_type='result', return_null=False, return_input=False, verbose=False, **kwargs) -> 'JRSAResult'<br>*Unified representational similarity / cross-area analysis.* |

## Module: jnwb.metadata

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.assign_quality_tier | function | assign_quality_tier(quality: pandas.core.series.Series, trial_presence_fraction: pandas.core.series.Series, snr: pandas.core.series.Series, presence_threshold: float = 0.98, snr_threshold: float = 0.5) -> pandas.core.series.Series<br>*Tier units into 'mua' / 'stable' / 'unstable' from quality code, trial presence, and SNR.* |
| jnwb.audit_electrodes | function | audit_electrodes(elec_df: pandas.core.frame.DataFrame, units_df: pandas.core.frame.DataFrame | None = None) -> Dict<br>*Audit electrode configuration and unit-to-electrode mapping coverage.* |
| jnwb.audit_units | function | audit_units(units_df: pandas.core.frame.DataFrame) -> Dict<br>*Audit unit quality and completeness: spike-time coverage, and quality/SNR/firing-rate* |
| jnwb.classify_unit_quality | function | classify_unit_quality(units_df: pandas.core.frame.DataFrame, thresholds: Dict[str, float] | None = None) -> pandas.core.frame.DataFrame<br>*Classify units by quality based on metrics.* |
| jnwb.compare_old_new_criteria | function | compare_old_new_criteria(new_df: pandas.core.frame.DataFrame, old_df: pandas.core.frame.DataFrame, new_key: Tuple[str, str] = ('session', 'unit_row'), old_key: Tuple[str, str] = ('session_prefix', 'unit_row_idx'), class_col_new: str = 'is_omission_inclusion_new', class_col_old: str = 'is_Oplus') -> pandas.core.frame.DataFrame<br>*Diff two boolean unit-classification columns across two DataFrames on a join key.* |
| jnwb.electrode_inventory | function | electrode_inventory(nwb_paths: str | pathlib.Path | List[str | pathlib.Path]) -> pandas.core.frame.DataFrame<br>*Build inventory of electrodes, mapping to units and areas.* |
| jnwb.filter_by_criteria | function | filter_by_criteria(df: pandas.core.frame.DataFrame, criteria: Dict) -> pandas.core.frame.DataFrame<br>*Apply a criteria dict to a DataFrame (units, electrodes, or any other table).* |
| jnwb.get_all_units_metadata | function | get_all_units_metadata(nwb_paths: str | pathlib.Path | List[str | pathlib.Path], filter_quality: bool = False, quality_threshold: float = 1.0) -> pandas.core.frame.DataFrame<br>*Extract all units and metadata from one or more NWB files.* |
| jnwb.get_snr_analysis | function | get_snr_analysis(units_df: pandas.core.frame.DataFrame, snr_threshold: float = 1.0, detail: bool = False) -> Dict<br>*Analyze SNR distribution and quality.* |
| jnwb.old_new_summary_table | function | old_new_summary_table(compared: pandas.core.frame.DataFrame, group_cols: Tuple[str, ...] = ('area', 'quality_tier')) -> pandas.core.frame.DataFrame<br>*Explicit gained/lost/unchanged counts per class per grouping column.* |
| jnwb.unit_census_report | function | unit_census_report(units_df: pandas.core.frame.DataFrame, group_by: List[str] | None = None) -> pandas.core.frame.DataFrame<br>*Generate a census/summary report of units grouped by session/area/layer.* |

## Module: jnwb.onset_fitting

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.causal_exp_smooth | function | causal_exp_smooth(rate: 'np.ndarray', bin_ms: 'float', tau_ms: 'float' = 30.0) -> 'np.ndarray'<br>*Causal (forward-only) exponential-kernel smoothing of an already-binned rate trace.* |
| jnwb.fit_exponential_onset | function | fit_exponential_onset(t_ms: 'np.ndarray', rate: 'np.ndarray', t0_bounds: 'tuple[float | None, float | None]' = (0.0, None), tau_bounds: 'tuple[float, float]' = (1.0, 150.0), baseline_window: 'tuple[float, float] | None' = None, min_amplitude: 'float' = 0.0, t0_grid_step: 'float' = 5.0) -> 'dict'<br>*Grid-search-over-t0, then bounded nonlinear least-squares fit of ``onset_model``.* |
| jnwb.onset_model | function | onset_model(t: 'np.ndarray', t0: 'float', tau: 'float', amplitude: 'float', baseline: 'float') -> 'np.ndarray'<br>*rate(t) = baseline for t < t0, baseline + amplitude*(1-exp(-(t-t0)/tau)) for t >= t0.* |

## Module: jnwb.ontology

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.AlignedDataset | class | *Dataset with explicit Alignment.* |
| jnwb.Alignment | class | *Reference frame for time-series data.* |
| jnwb.Dataset | class | *Aggregated query result: immutable collection of data.* |
| jnwb.EpochCollection | class | *Filtered set of trials: immutable.* |
| jnwb.Figure | class | *Visualization: rendering of Result + Interpretation.* |
| jnwb.Interpretation | class | *Meaning and claims: what does the result mean?* |
| jnwb.Lineage | class | *Artifact dependencies: where did this come from?* |
| jnwb.Provenance | class | *Execution context and metadata.* |
| jnwb.Query | class | *Data selection rules: what subset of data?* |
| jnwb.Question | class | *Scientific hypothesis: what are we asking?* |
| jnwb.Result | class | *Analysis output: statistics, provenance, lineage.* |

## Module: jnwb.permutation

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.build_permutation_plan | function | build_permutation_plan(labels: 'Iterable[object]', groups: 'Iterable[object]', *, n_permutations: 'int', seed: 'int') -> 'dict'<br>*Create an explicit within-group null plan (a manifest of digested draws); no model* |
| jnwb.permute_labels | function | permute_labels(y, *, groups=None, scheme: 'str', rng: 'np.random.Generator')<br>*Permute labels under an explicitly named exchangeability scheme.* |

## Module: jnwb.spectral

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.band_power | function | band_power(lfp_trace: numpy.ndarray, sampling_rate: float, freq_range: Tuple[float, float], normalize: bool = True, baseline: numpy.ndarray | None = None, device: str = 'cpu') -> float<br>*Compute power in a frequency band.* |
| jnwb.bipolar_reference | function | bipolar_reference(channel_data: numpy.ndarray, channel_order: numpy.ndarray | None = None) -> numpy.ndarray<br>*Bipolar (adjacent-channel difference) re-reference along a probe's depth order.* |
| jnwb.compute_psd | function | compute_psd(lfp_data: numpy.ndarray, fs: float)<br>*Welch power spectral density of a plain LFP array.* |
| jnwb.cross_area_coherence | function | cross_area_coherence(lfp_area1: numpy.ndarray, lfp_area2: numpy.ndarray, sampling_rate: float, freq_bands: Dict[str, Tuple[float, float]] | None = None, device: str = 'cpu') -> Dict<br>*Compute frequency-resolved coherence between two LFP signals.* |
| jnwb.harmonic_analysis | function | harmonic_analysis(lfp_trace: numpy.ndarray, sampling_rate: float, freq_range: Tuple[float, float] = (1.0, 90.0), harmonic_orders: int = 3, device: str = 'cpu') -> Dict<br>*Decompose LFP trace into fundamental and harmonic components.* |
| jnwb.imaginary_coherency | function | imaginary_coherency(x: numpy.ndarray, y: numpy.ndarray, sampling_rate: float, freq_range: Tuple[float, float], nperseg: int | None = None, noverlap: int | None = None, device: str = 'cpu') -> Dict[str, float]<br>*Imaginary part of coherency (Nolte et al. 2004) between two continuous signals.* |
| jnwb.laplacian_reference | function | laplacian_reference(channel_data: numpy.ndarray, channel_order: numpy.ndarray | None = None) -> numpy.ndarray<br>*1D nearest-neighbor Laplacian re-reference along a probe's depth order.* |
| jnwb.spectral_tilt | function | spectral_tilt(lfp_trace: numpy.ndarray, sampling_rate: float, freq_range: Tuple[float, float] = (1.0, 100.0), device: str = 'cpu') -> Dict<br>*Analyze 1/f spectral tilt (aperiodic component).* |
| jnwb.to_db | function | to_db(ratio)<br>*``10*log10(ratio)``, the single point every power-ratio-to-dB conversion should pass* |

## Module: jnwb.spiking

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.classify_response_significance | function | classify_response_significance(metrics: Dict[str, float], zscore_threshold: float = 1.96, min_spike_count: int = 5) -> Dict[str, bool | float]<br>*Classify unit response as significant based on metrics.* |
| jnwb.compute_response_metrics | function | compute_response_metrics(spike_times: numpy.ndarray, epoch_onsets: numpy.ndarray, baseline_window: Tuple[float, float] = (-0.25, -0.05), response_window: Tuple[float, float] = (0.0, 0.15), z_score: bool = True) -> Dict[str, float]<br>*Compute firing rate and spike count metrics for stimulus responses.* |
| jnwb.phase_locking_index | function | phase_locking_index(unit_spike_times: numpy.ndarray, lfp_phase: numpy.ndarray, lfp_timestamps: numpy.ndarray, n_bins: int = 18) -> Dict[str, float | numpy.ndarray]<br>*Compute phase-locking index (PLI) between spikes and LFP phase.* |

## Module: jnwb.statistics

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.StatisticalAnalysis | class | *Dual statistical testing with honest multiple-comparison handling.* |
| jnwb.assign_subblock_quartiles | function | assign_subblock_quartiles(epochs_df: 'pd.DataFrame', n_quantiles: 'int' = 4) -> 'np.ndarray'<br>*Assign each row a temporal quantile bucket 0..n_quantiles-1 by its own start_time order.* |
| jnwb.cross_modal_comparison | function | cross_modal_comparison(tfr_data: 'np.ndarray', spike_data: 'np.ndarray', lag_range_ms: 'Tuple[int, int]' = (-500, 500), bin_ms: 'Optional[float]' = None) -> 'Dict'<br>*Trial-averaged correlation between a TFR-derived signal and a spike-count signal.* |
| jnwb.detect_trial_cycles | function | detect_trial_cycles(epochs_df: 'pd.DataFrame', gap_factor: 'float' = 10.0) -> 'np.ndarray'<br>*Detect temporal cluster ("cycle") boundaries in a trial table via a gap threshold.* |
| jnwb.fire_indicator | function | fire_indicator(spike_times: 'np.ndarray', onsets_s: 'np.ndarray', window_ms) -> 'np.ndarray'<br>*Vectorized boolean fire indicator, one entry per onset, constant window.* |
| jnwb.fires_in_window | function | fires_in_window(spike_times: 'np.ndarray', onset_s: 'float', window_ms) -> 'bool'<br>*True iff >=1 spike falls in [onset_s + window_ms[0]/1000, onset_s + window_ms[1]/1000).* |
| jnwb.paired_fire_prob_test | function | paired_fire_prob_test(fires_target: 'np.ndarray', fires_null: 'np.ndarray', n_shuffles: 'int', n_bootstrap: 'int', rng: 'np.random.Generator') -> 'Dict'<br>*Paired binary test: P(fire | target window) vs P(fire | paired baseline window).* |
| jnwb.rate_in_window | function | rate_in_window(spike_times: 'np.ndarray', onset_s: 'float', window_ms: 'Tuple[float, float]') -> 'float'<br>*Firing rate (Hz) in ``[onset_s + window_ms[0]/1000, onset_s + window_ms[1]/1000)``.* |
| jnwb.shuffle_pvalue_paired | function | shuffle_pvalue_paired(a: 'np.ndarray', b: 'np.ndarray', n_shuffles: 'int', rng: 'np.random.Generator', alternative: 'str' = 'two-sided') -> 'Tuple[float, float]'<br>*Shuffle-controlled p-value for ``mean(a - b)`` via paired sign-flips.* |
| jnwb.shuffle_pvalue_unpaired | function | shuffle_pvalue_unpaired(a: 'np.ndarray', b: 'np.ndarray', n_shuffles: 'int', rng: 'np.random.Generator', alternative: 'str' = 'greater') -> 'Tuple[float, float]'<br>*Shuffle-controlled p-value for ``mean(a) - mean(b)`` via label-shuffling.* |
| jnwb.shuffle_r2_ci | function | shuffle_r2_ci(y_true: 'np.ndarray', y_score: 'np.ndarray', groups: 'Optional[np.ndarray]' = None, n_shuffle: 'int' = 200, random_state: 'int' = 42) -> 'Dict[str, float]'<br>*R^2 (squared Pearson correlation) between a continuous score and a 0/1 label, with a* |

## Module: jnwb.tfr

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.ComplexTFR | class | *Container for complex Time-Frequency Representation outputs.* |
| jnwb.complex_tfr | function | complex_tfr(data: 'np.ndarray', fs: 'float', freqs: 'np.ndarray', n_cycles: 'Union[float, np.ndarray]' = 5.0, time_axis: 'int' = -1, normalization: 'str' = 'amplitude', dtype: 'np.dtype' = <class 'numpy.complex128'>, coi_sigma: 'float' = 2.0) -> 'ComplexTFR'<br>*Compute complex Time-Frequency Representation via Morlet wavelet convolution.* |
| jnwb.morlet_wavelet | function | morlet_wavelet(f0: 'float', fs: 'float', n_cycles: 'float' = 5.0, normalization: 'str' = 'amplitude', cutoff_sigma: 'float' = 4.0) -> 'Tuple[np.ndarray, np.ndarray]'<br>*Generate a discrete complex Morlet wavelet kernel.* |

## Module: jnwb.tfr_accumulator

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.TFRAccumulator | class | *Poolable sufficient statistics for complex TFR. Accumulate in float64/complex128.* |
| jnwb.assert_mergeable | function | assert_mergeable(attrs_a: 'Dict', attrs_b: 'Dict') -> 'None'<br>** |

## Module: jnwb.trajectory

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.build_time_resolved_matrix | function | build_time_resolved_matrix(session, area: str, epochs_df: pandas.core.frame.DataFrame, time_window_ms: Tuple[float, float] = (-1000.0, 2000.0), bin_size_ms: float = 20.0, quality: str | None = None) -> Tuple[numpy.ndarray, List[int], numpy.ndarray]<br>*Build a trial-by-trial time-resolved population spike count matrix.* |
| jnwb.compute_population_trajectory | function | compute_population_trajectory(session, area: str, epochs_df: pandas.core.frame.DataFrame, time_window_ms: Tuple[float, float] = (-1000.0, 2000.0), bin_size_ms: float = 20.0, n_components: int = 3, quality: str | None = None, device: str = 'cpu') -> Dict[str, numpy.ndarray | List[int] | float]<br>*Compute population trajectory using SVD/PCA.* |

## Module: jnwb.viz

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.apply_tight_auto_axis | function | apply_tight_auto_axis(ax, x_span: Tuple[float, float] = (-500, 4124), y_margin: float = 0.12)<br>*Apply tight temporal bounds and auto-scale y-axis without empty margins.* |
| jnwb.raster_psth | function | raster_psth(st, onsets, win_ms, bin_ms: float = 10.0)<br>*Trial-averaged PSTH (mean + SEM firing rate per bin) for a raw spike-time array against* |
| jnwb.resample_onsets | function | resample_onsets(onsets: numpy.ndarray, target_n: int = 100, random_state: int = 42) -> numpy.ndarray<br>*Resample a trial-onset array to exactly ``target_n`` onsets (with replacement if there* |
| jnwb.save_figure_suite | function | save_figure_suite(figures: List[matplotlib.figure.Figure], output_dir: str | pathlib.Path, basename: str, dpi: int = 300, formats: List[str] = ['png', 'pdf']) -> None<br>*Save a suite of figures to disk with consistent naming.* |
| jnwb.setup_vector_graphics | function | setup_vector_graphics()<br>*Enforce editable vector SVG font rendering in Adobe Illustrator / Inkscape.* |
