# Complete API Reference

All 157 core functions, classes, and constants exported in the top-level jnwb namespace.

> Generated from `jnwb.__all__`, `inspect.signature`, and runtime docstrings. Do not edit by hand — run `python scripts/generate_api_md.py --write`.

## Module: jnwb

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.CANONICAL_BANDS | constant | dict |
| jnwb.DB_AGGREGATIONS | constant | tuple |
| jnwb.DETECTION_TAILS | constant | tuple |
| jnwb.RELATIVE_POWER_MODELS | constant | tuple |
| jnwb.SKILLS_URL | constant | str |
| jnwb.io | module | *Streaming array slice reader for NPZ archives without full-file RAM allocation.* |
| jnwb.paths | module | *Central path resolution for jnwb.* |
| jnwb.vis | module | *jnwb.vis -- Publication-grade non-human primate electrophysiology visualization engine in pure Plotly.* |
| jnwb.visual_qc | module | *Visual Quality Control and Multi-Session Inspection* |

## Module: jnwb.addressing

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.ProbeGeometry | class | *Extracted contact geometry and spatial properties for an electrode array.* |
| jnwb.classify_layer_from_depth | function | (peak_channel_id: float, electrodes_df: pandas.DataFrame, depth_unit: str | None = None, threshold: float | None = None, threshold_unit: str | None = None) -> str<br>*Classify unit cortical layer using z depth coordinates.* |
| jnwb.enrich_units_dataframe | function | (units_df: pandas.DataFrame, electrodes_df: pandas.DataFrame | None, depth_unit: str | None = None, threshold: float | None = None, threshold_unit: str | None = None) -> pandas.DataFrame<br>*Enrich units DataFrame with standardized area, layer, and quality flags.* |
| jnwb.map_peak_channel_to_area | function | (peak_channel_id: float, electrodes_df: pandas.DataFrame) -> str | None<br>*Map peak channel ID to brain area location.* |
| jnwb.probe_geometry | function | (electrodes_table: typing.Any, probe_name: str | None = None, units: str = 'um', nominal_pitch: float | None = None, pitch_tolerance: float = 0.1, strict_linear: bool = False, stagger_tolerance_um: float = 100.0) -> jnwb.addressing.ProbeGeometry<br>*Extract contact geometry, linear ordering, and spacing from electrode coordinates.* |

## Module: jnwb.analyzers

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.PopulationAnalyzer | class | *Population-Level Statistics.* |
| jnwb.TFRAnalyzer | class | *Time-Frequency Representation Analysis.* |
| jnwb.UnitAnalyzer | class | *Single-Unit Spike Analysis.* |

## Module: jnwb.artifact_detection

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.bad_channels_from_correlation | function | (corr: 'np.ndarray', z_thresh: 'float' = 5.0) -> 'Tuple[np.ndarray, np.ndarray, np.ndarray]'<br>*corr: (n_ch, n_ch). Returns (bad_mask, summary_per_channel, z_per_channel).* |
| jnwb.bad_trials_single_channel | function | (trial_waveforms: 'np.ndarray', corr_z_thresh: 'float' = 5.0, amp_z_thresh: 'float' = 5.0) -> 'Tuple[np.ndarray, np.ndarray, np.ndarray]'<br>*trial_waveforms: (n_trials, n_times), single GOOD channel.* |
| jnwb.channel_correlation_matrix | function | (data_ch_by_time: 'np.ndarray') -> 'np.ndarray'<br>*data_ch_by_time: (n_channels, n_samples). Returns (n_channels, n_channels) Pearson corr.* |
| jnwb.consensus_bad_trials | function | (per_channel_flags: 'np.ndarray', min_frac_channels: 'float' = 0.5) -> 'Tuple[np.ndarray, np.ndarray]'<br>*per_channel_flags: (n_good_channels, n_trials) bool. A trial is excluded only if flagged on at least `min_frac_channels` of the good channels independently -- the cross-channel- consensus requirement (real artifacts are shared events, not one channel's quirk).* |
| jnwb.trial_correlation_matrix | function | (trial_waveforms: 'np.ndarray') -> 'np.ndarray'<br>*trial_waveforms: (n_trials, n_times), single channel. Returns (n_trials, n_trials) corr.* |

## Module: jnwb.artifact_repair

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.detect_band_outliers | function | (band_trace, z_thresh = 6.0, sided = 'upper')<br>*Flag (trial, time) cells whose power departs from the cross-trial trend.* |
| jnwb.repair_band_artifacts | function | (power, freqs, band_ranges = None, z_thresh = 6.0, sided = 'upper')<br>*Per-band, cross-trial-median substitution of sparse single-trial TFR power spikes.* |
| jnwb.repair_lfp_trials | function | (segments, times_ms = None, z_thresh = 6.0, exclude_window_ms = None, reward_window_ms = None, min_trials = 5, max_trial_fraction = 0.5)<br>*Cross-channel-synchrony detection + cross-trial-median substitution.* |

## Module: jnwb.compression

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.compress_fp32 | function | (src: "'str | Path'", dst: "'str | Path | None'" = None, drop_convolved: 'bool' = False, verify: 'bool' = True, n_check: 'int' = 200000, overwrite: 'bool' = False) -> 'dict'<br>*Compress one NWB file: float32 LFP/MUAE, chunking, gzip1+shuffle, compaction.* |

## Module: jnwb.connectivity

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.DirectedResult | class | *Uniform return type for every directed connectivity estimator.* |
| jnwb.as_trials | function | (X, time_axis: 'int' = -1, name: 'str' = 'X', allow_ragged: 'bool' = True) -> 'np.ndarray'<br>*Normalize any supported signal container to a ``(n_trials, n_times)`` float array.* |
| jnwb.bin_spikes | function | (spike_times, window_s: 'Optional[Tuple[float, float]]' = None, bin_size_ms: 'float' = 10.0, trial_starts: 'Optional[Sequence[float]]' = None, output: 'str' = 'count', return_centers: 'bool' = False, window: 'Optional[Tuple[float, float]]' = None)<br>*Bridge spike data into the ``(n_trials, n_bins)`` contract used by every estimator.* |
| jnwb.binary_occupancy_mutual_information | function | (spike_times1: 'np.ndarray', spike_times2: 'np.ndarray', time_window_s: 'Optional[Tuple[float, float]]' = None, bin_size_ms: 'float' = 10.0, time_window: 'Optional[Tuple[float, float]]' = None) -> 'float'<br>*Explicit alias for binary occupancy MI. `time_window_s` is in seconds.* |
| jnwb.directed_connectivity | function | (X, Y, method: 'str' = 'granger', kwargs) -> 'DirectedResult'<br>*One entry point for all three directed estimators.* |
| jnwb.directed_network | function | (signals, method: 'str' = 'granger', labels: 'Optional[Sequence[str]]' = None, fdr: 'bool' = True, fdr_method: 'str' = 'bh', n_jobs: 'int' = 1, kwargs) -> 'Dict[str, Any]'<br>*All-pairs directed connectivity over N nodes.* |
| jnwb.granger | function | (X, Y, order: 'Union[int, str]' = 'auto', max_lag: 'int' = 20, criterion: 'str' = 'bic', Z = None, ridge: 'float' = 0.0, detrend: 'Optional[str]' = 'zscore', n_surrogates: 'int' = 0, rng: 'RNGLike' = 0, time_axis: 'int' = -1, seed: 'Any' = 0) -> 'DirectedResult'<br>*Bivariate or conditional Granger causality between two arbitrary signals.* |
| jnwb.granger_causality | function | (signal1: 'np.ndarray', signal2: 'np.ndarray', order: 'Union[int, str]' = 5, device: 'str' = 'cpu', ridge: 'float' = 0.0, criterion: 'str' = 'aic') -> 'Dict[str, Union[float, dict, list]]'<br>*Compute bivariate Granger Causality (GC) values between two continuous signals.* |
| jnwb.granger_spectral | function | (X, Y, fs: 'float', order: 'Union[int, str]' = 'auto', max_lag: 'int' = 20, criterion: 'str' = 'bic', n_freqs: 'int' = 256, bands: 'Union[str, Dict[str, Tuple[float, float]], Tuple[float, float], None]' = None, ridge: 'float' = 0.0, detrend: 'Optional[str]' = 'zscore', n_surrogates: 'int' = 0, rng: 'RNGLike' = 0, time_axis: 'int' = -1, seed: 'Any' = 0) -> 'DirectedResult'<br>*Frequency-resolved Granger causality (Geweke, 1982) — directionality per band.* |
| jnwb.network_topology | function | (adjacency_matrix: 'np.ndarray', threshold: 'float' = 0.3) -> 'Dict[str, Union[float, int, List[int]]]'<br>*Compute network graph metrics from a correlation or Granger causality matrix.* |
| jnwb.phase_slope_index | function | (X, Y, fs: 'float', bands: 'Union[str, Dict[str, Tuple[float, float]], Tuple[float, float], None]' = None, nperseg: 'Optional[int]' = None, noverlap: 'Optional[int]' = None, window: 'str' = 'hann', detrend: 'Optional[str]' = 'demean', jackknife: 'bool' = True, n_surrogates: 'int' = 0, rng: 'RNGLike' = 0, time_axis: 'int' = -1, seed: 'Any' = 0) -> 'DirectedResult'<br>*Phase Slope Index (Nolte et al., 2008) — which signal leads in phase.* |
| jnwb.spike_count_mutual_information | function | (spike_times1: 'np.ndarray', spike_times2: 'np.ndarray', time_window_s: 'Optional[Tuple[float, float]]' = None, bin_size_ms: 'float' = 10.0, time_window: 'Optional[Tuple[float, float]]' = None) -> 'float'<br>*Discrete MI on per-bin spike counts. `time_window_s` is in seconds.* |
| jnwb.spike_mutual_information | function | (spike_times1: 'np.ndarray', spike_times2: 'np.ndarray', time_window_s: 'Optional[Tuple[float, float]]' = None, bin_size_ms: 'float' = 10.0, estimator: 'str' = 'binary_occupancy', time_window: 'Optional[Tuple[float, float]]' = None) -> 'float'<br>*Compute Shannon Mutual Information (MI) between two binned spike trains.* |
| jnwb.transfer_entropy | function | (X, Y, k: 'int' = 1, l: 'int' = 1, delay: 'int' = 1, estimator: 'str' = 'quantile', bins: 'int' = 4, symbolic_order: 'int' = 3, bias_correction: 'Optional[str]' = 'mm', n_surrogates: 'int' = 200, rng: 'RNGLike' = 0, detrend: 'Optional[str]' = None, time_axis: 'int' = -1, seed: 'Any' = 0) -> 'DirectedResult'<br>*Transfer entropy — model-free, nonlinear directed information flow, in bits.* |

## Module: jnwb.continuous

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.epoch_continuous | function | (data: 'np.ndarray', onsets: 'np.ndarray | Sequence[float]', win_s: 'tuple[float, float]', fs: 'float', onset_unit: 'OnsetUnit' = 'seconds', boundary_policy: 'BoundaryPolicy' = 'nan', return_indices: 'bool' = False) -> 'tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, np.ndarray]'<br>*Extract fixed-duration epochs from a continuous signal aligned to event onsets.* |

## Module: jnwb.decoding

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.assign_outer_folds | function | (trials: 'pd.DataFrame', analysis_cols: 'tuple' = ('session', 'analysis', 'slot_key'), group_col: 'str' = 'cycle') -> 'pd.DataFrame'<br>*Assign deterministic leave-one-group-out outer folds without touching features.* |
| jnwb.build_inner_validation_partitions | function | (outer_trials: 'pd.DataFrame', analysis_cols: 'tuple' = ('session', 'analysis', 'slot_key')) -> 'pd.DataFrame'<br>*Build nested inner train/validation partitions from outer-training groups.* |
| jnwb.build_representation_ladder | function | (raster: 'np.ndarray', modality: 'str' = 'SPK', spatial_axis_metadata: 'Union[Mapping[str, object], None]' = None) -> 'Dict[str, object]'<br>*Return R0/R1/R2 representation contracts without fitting a model.* |
| jnwb.fold_majority_baseline | function | (y_train: 'np.ndarray', y_test: 'np.ndarray') -> 'float'<br>*Accuracy of predicting the training-fold majority class on the held-out fold.* |
| jnwb.majority_baseline | function | (labels: 'np.ndarray') -> 'float'<br>*Accuracy of always predicting the most frequent class in ``labels``.* |
| jnwb.nested_cv_linear_svm | function | (X: 'np.ndarray', labels: 'np.ndarray', n_splits: 'int', rng: 'RNGLike' = 42) -> 'Dict[str, Union[float, np.ndarray, dict, str]]'<br>*Outer stratified CV; inner GridSearchCV for C. No synthetic metrics.* |

## Module: jnwb.filtering

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.bandpass_filter | function | (data: 'np.ndarray', fs: 'float', low_cut: 'float', high_cut: 'float', order: 'int' = 4, zero_phase: 'bool' = True, axis: 'int' = -1) -> 'np.ndarray'<br>*Apply a Butterworth bandpass filter using Second-Order Sections (SOS).* |
| jnwb.notch_filter | function | (data: 'np.ndarray', fs: 'float', freq: 'float' = 60.0, q: 'float' = 30.0, zero_phase: 'bool' = True, axis: 'int' = -1) -> 'np.ndarray'<br>*Apply an IIR notch filter using Second-Order Sections (SOS) conversion.* |

## Module: jnwb.io

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.stream_npz_array | function | (file_path: 'Union[str, Path]', key: 'str', slice_tuple: 'Union[slice, int, Tuple[Union[slice, int], ...]]' = (slice(None, None, None),)) -> 'np.ndarray'<br>*Stream a memory-bounded slice from an uncompressed or compressed NPZ archive.* |

## Module: jnwb.jrsa

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.JRSAResult | class | *Container returned by jrsa().* |
| jnwb.jrsa | function | (x1, x2 = None, adim = -1, labels = None, align = 'auto', align_mode = 'fraction', reduction = None, metric = 'rsa', lag = 0, window = None, sliding = False, normalize = False, standardize = False, detrend = False, nan_policy = 'omit', stats = True, permutations = 1000, bootstrap = 0, correction = 'fdr_bh', alpha = 0.05, alternative = 'two-sided', backend = 'auto', device = 'auto', n_jobs = 1, batch_size = None, rng: 'RNGLike' = None, return_type = 'result', return_null = False, return_input = False, verbose = False, kwargs) -> 'JRSAResult'<br>*Unified representational similarity / cross-area analysis.* |

## Module: jnwb.laminar

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.VFlipResult | class | *Container for Vectorized Frequency-based Laminar Identity Profile (vFLIP) results.* |
| jnwb.XFlipResult | class | *Container for Cross-Channel Laminar Correlation Profile (xFLIP) results.* |
| jnwb.ZFlipResult | class | *Container for zFLIP Cortical Depth Phase-Gradient & Delay Estimation results.* |
| jnwb.label_layers | function | (vflip_result: 'VFlipResult', probe_geometry: 'Any', granular_thickness_um: 'float' = 400.0, bad_channel_mask: 'Optional[np.ndarray]' = None, depth_range_um: 'Optional[Tuple[float, float]]' = None, contact_range: 'Optional[Tuple[float, float]]' = None) -> 'Dict[Any, str]'<br>*Assign cortical layer labels (superficial, input, deep) to probe contacts.* |
| jnwb.vflip | function | (psd: 'np.ndarray', freqs: 'np.ndarray', band_low: 'Tuple[float, float]' = (8.0, 30.0), band_high: 'Tuple[float, float]' = (50.0, 150.0), contact_spacing: 'Optional[float]' = None, probe_geometry: 'Optional[Any]' = None, orientation: 'str' = 'auto', min_support_score: 'float' = 3.75, bad_channel_mask: 'Optional[np.ndarray]' = None, min_channels: 'int' = 8, min_peak_distance: 'int' = 2, device: 'str' = 'cpu') -> 'VFlipResult'<br>*Vectorized Frequency-based Laminar Identity Profile (vFLIP).* |
| jnwb.vflip_from_lfp | function | (lfp: 'np.ndarray', fs: 'float', nperseg: 'Optional[int]' = None, noverlap: 'Optional[int]' = None, window: 'str' = 'hann', detrend: 'Union[str, bool]' = 'constant', scaling: 'str' = 'density', band_low: 'Tuple[float, float]' = (8.0, 30.0), band_high: 'Tuple[float, float]' = (50.0, 150.0), contact_spacing: 'Optional[float]' = None, probe_geometry: 'Optional[Any]' = None, orientation: 'str' = 'auto', min_support_score: 'float' = 3.75, bad_channel_mask: 'Optional[np.ndarray]' = None, min_channels: 'int' = 8, min_peak_distance: 'int' = 2, device: 'str' = 'cpu') -> 'VFlipResult'<br>*Vectorized Frequency-based Laminar Identity Profile from raw LFP time series.* |
| jnwb.xflip | function | (data: 'np.ndarray', method: 'str' = 'pearson', contiguous: 'bool' = True, n_blocks: 'Optional[int]' = 2, min_block_size: 'int' = 2, n_surrogates: 'int' = 200, surrogate_method: 'str' = 'auto', alpha: 'float' = 0.05, min_contrast: 'float' = 0.05, min_boundary_drop: 'float' = 0.05, channel_axis: 'int' = 0, is_corr_matrix: 'Optional[bool]' = None, rng: 'Optional[Union[np.random.Generator, int]]' = None) -> 'XFlipResult'<br>*Cross-Channel Laminar Correlation Profile (xFLIP).* |
| jnwb.zflip | function | (lfp_matrix: 'np.ndarray', fs: 'float', freq_range: 'Tuple[float, float]' = (15.0, 35.0), pitch_um: 'Optional[float]' = None, nperseg: 'Optional[int]' = None, noverlap: 'Optional[int]' = None, min_linearity_r2: 'float' = 0.7, min_wpli: 'float' = 0.15, n_surrogates: 'int' = 50, alpha: 'float' = 0.05, rng: 'RNGLike' = 0, seed: 'Any' = 0) -> 'ZFlipResult'<br>*Estimate cortical depth phase gradients, propagation delay, and apparent velocity.* |

## Module: jnwb.metadata

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.assign_quality_tier | function | (quality: pandas.Series, trial_presence_fraction: pandas.Series, snr: pandas.Series, presence_threshold: float = 0.98, snr_threshold: float = 0.5) -> pandas.Series<br>*Tier units into 'mua' / 'stable' / 'unstable' from quality code, trial presence, and SNR.* |
| jnwb.audit_electrodes | function | (elec_df: pandas.DataFrame, units_df: pandas.DataFrame | None = None) -> Dict<br>*Audit electrode configuration and unit-to-electrode mapping coverage.* |
| jnwb.audit_units | function | (units_df: pandas.DataFrame) -> Dict<br>*Audit unit quality and completeness: spike-time coverage, and quality/SNR/firing-rate summary statistics.* |
| jnwb.classify_unit_quality | function | (units_df: pandas.DataFrame, thresholds: Dict[str, float] | None = None) -> pandas.DataFrame<br>*Classify units by quality based on metrics.* |
| jnwb.electrode_inventory | function | (nwb_paths: str | pathlib.Path | List[str | pathlib.Path], on_read_error: Literal['skip', 'raise'] = 'skip') -> pandas.DataFrame<br>*Build inventory of electrodes, mapping to units and areas.* |
| jnwb.filter_by_criteria | function | (df: pandas.DataFrame, criteria: Dict, unknown: Literal['ignore', 'raise'] = 'ignore') -> pandas.DataFrame<br>*Apply a criteria dict to a DataFrame (units, electrodes, or any other table).* |
| jnwb.get_all_units_metadata | function | (nwb_paths: str | pathlib.Path | List[str | pathlib.Path], filter_quality: bool = False, quality_threshold: float = 1.0, on_read_error: Literal['skip', 'raise'] = 'skip') -> pandas.DataFrame<br>*Extract all units and metadata from one or more NWB files.* |
| jnwb.get_snr_analysis | function | (units_df: pandas.DataFrame, snr_threshold: float = 1.0, detail: bool = False) -> Dict<br>*Analyze SNR distribution and quality.* |
| jnwb.unit_census_report | function | (units_df: pandas.DataFrame, group_by: List[str] | None = None) -> pandas.DataFrame<br>*Generate a census/summary report of units grouped by session/area/layer.* |

## Module: jnwb.nwb_events

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.AmbiguousIntervalTableError | class | *Several interval tables are present and ``table`` was not specified.* |
| jnwb.ColumnNotFoundError | class | *A required interval-table column is missing.* |
| jnwb.EventTable | class | *Structured event rows from one NWB interval table.* |
| jnwb.IntervalTableNotFoundError | class | *The requested interval table does not exist.* |
| jnwb.InvalidOnsetValueError | class | *A selected row has a missing or non-finite onset timestamp.* |
| jnwb.NWBEventError | class | *Base class for event/onset extraction errors.* |
| jnwb.event_onsets | function | (path_or_nwb: 'NWBInput', table: 'str | None' = None, codes: 'CodeSequence | None' = None, code_column: 'str | None' = 'codes', onset_column: 'str' = 'start_time') -> 'np.ndarray'<br>*Return onset timestamps (seconds) for rows matching ``codes``.* |
| jnwb.events | function | (path_or_nwb: 'NWBInput', table: 'str | None' = None, code_column: 'str | None' = 'codes', onset_column: 'str' = 'start_time') -> 'EventTable'<br>*Read event codes and onset timestamps from one interval table.* |
| jnwb.resolve_interval_table | function | (path_or_nwb: 'NWBInput', table: 'str | None' = None) -> 'str'<br>*Resolve an interval table name using jnwb addressing rules.* |

## Module: jnwb.nwb_inspect

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.AcquisitionNotFoundError | class | *The requested acquisition does not exist.* |
| jnwb.AmbiguousAcquisitionError | class | *Several acquisitions are present and ``name`` was not specified.* |
| jnwb.AmbiguousLayoutError | class | *The channel axis of a 2-D continuous series cannot be determined.* |
| jnwb.ChannelIndexError | class | *The requested channel index is out of range for the continuous series.* |
| jnwb.NWBInspectError | class | *Base for every error raised while addressing an NWB file's contents.* |
| jnwb.UnitNotFoundError | class | *The requested units-table row does not exist.* |
| jnwb.acquisition_channel | function | (path_or_nwb: 'InspectInput', name: 'str | None' = None, channel: 'int' = 0) -> 'tuple[np.ndarray, float]'<br>*Return one continuous acquisition channel and its sampling rate in Hz.* |
| jnwb.inspect | function | (path_or_nwb: 'InspectInput') -> 'dict[str, Any]'<br>*Return structured metadata about an NWB file or in-memory NWB object.* |
| jnwb.resolve_acquisition | function | (path_or_nwb: 'InspectInput', name: 'str | None' = None) -> 'str'<br>*Resolve an acquisition or processing continuous series name.* |
| jnwb.unit_spike_times | function | (path_or_nwb: 'InspectInput', unit_index: 'int' = 0) -> 'np.ndarray'<br>*Return spike times (seconds) for one units-table row.* |

## Module: jnwb.nwb_io

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.MissingRequiredNWBFieldError | class | *A required NWB field is absent from the on-disk builder tree.* |

## Module: jnwb.onset_fitting

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.causal_exp_smooth | function | (rate: 'np.ndarray', bin_ms: 'float', tau_ms: 'float' = 30.0) -> 'np.ndarray'<br>*Causal (forward-only) exponential-kernel smoothing of an already-binned rate trace.* |
| jnwb.fit_exponential_onset | function | (t_ms: 'np.ndarray', rate: 'np.ndarray', t0_bounds_ms: 'tuple[float | None, float | None] | None' = None, tau_bounds_ms: 'tuple[float, float] | None' = None, baseline_window_ms: 'tuple[float, float] | None' = None, min_amplitude: 'float' = 0.0, t0_grid_step_ms: 'float | None' = None, t0_bounds: 'tuple[float | None, float | None] | None' = None, tau_bounds: 'tuple[float, float] | None' = None, baseline_window: 'tuple[float, float] | None' = None, t0_grid_step: 'float | None' = None) -> 'dict'<br>*Grid-search-over-t0, then bounded nonlinear least-squares fit of ``onset_model``.* |
| jnwb.onset_model | function | (t: 'np.ndarray', t0: 'float', tau: 'float', amplitude: 'float', baseline: 'float') -> 'np.ndarray'<br>*rate(t) = baseline for t < t0, baseline + amplitude*(1-exp(-(t-t0)/tau)) for t >= t0.* |

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
| jnwb.build_permutation_plan | function | (labels: 'Iterable[object]', groups: 'Iterable[object]', n_permutations: 'int', rng: 'int' = <required>, seed: 'Any' = <required>) -> 'dict'<br>*Create an explicit within-group null plan (a manifest of digested draws); no model fitting occurs.* |
| jnwb.permute_labels | function | (y, groups = None, scheme: 'str', rng: 'np.random.Generator')<br>*Permute labels under an explicitly named exchangeability scheme.* |

## Module: jnwb.rsa

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.rdm | function | (X: 'np.ndarray', metric: 'str' = 'correlation', condensed: 'bool' = True, device: 'str' = 'cpu') -> 'np.ndarray'<br>*Compute a Representational Dissimilarity Matrix (RDM) from feature vectors.* |
| jnwb.rdm_similarity | function | (rdm1: 'np.ndarray', rdm2: 'np.ndarray', metric: 'str' = 'spearman') -> 'Tuple[float, float]'<br>*Compute second-order representational similarity between two RDMs.* |

## Module: jnwb.spectral

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.AperiodicFitResult | class | *Container for 1/f aperiodic spectral parameter estimates.* |
| jnwb.aggregate_to_db | function | (power, baseline, how: str, aggregate_over = None, nan_policy: str = 'propagate')<br>*Form a power ratio, aggregate on the RATIO scale, and take ``10*log10`` exactly once.* |
| jnwb.aperiodic_fit | function | (freqs: numpy.ndarray, psd: numpy.ndarray, freq_range: Tuple[float, float], mode: str = 'fixed') -> jnwb.spectral.AperiodicFitResult | List[typing.Any]<br>*Fit aperiodic 1/f spectral parameters directly to an existing power spectrum.* |
| jnwb.band_power | function | (lfp_trace: numpy.ndarray, fs: float | None = None, sampling_rate: float | None = None, freq_range: Tuple[float, float] = (1.0, 90.0), normalize: bool = True, baseline: numpy.ndarray | None = None, device: str = 'cpu') -> float<br>*Mean power spectral density over a frequency band.* |
| jnwb.bipolar_reference | function | (channel_data: numpy.ndarray, channel_order: numpy.ndarray | None = None) -> numpy.ndarray<br>*Bipolar (adjacent-channel difference) re-reference along a probe's depth order.* |
| jnwb.compute_multitaper_psd | function | (data: numpy.ndarray, fs: float, nw: float = 3.0, k_tapers: int | None = None, axis: int = -1) -> Tuple[numpy.ndarray, numpy.ndarray]<br>*Compute power spectral density via the Discrete Prolate Spheroidal Sequences (DPSS) multitaper method.* |
| jnwb.compute_psd | function | (lfp_data: numpy.ndarray, fs: float, axis: int = 0)<br>*Welch power spectral density of a plain LFP array.* |
| jnwb.cross_area_coherence | function | (lfp_area1: numpy.ndarray, lfp_area2: numpy.ndarray, fs: float | None = None, sampling_rate: float | None = None, freq_bands: Dict[str, Tuple[float, float]] | str | None = None, device: str = 'cpu', rng: int | numpy.random._generator.Generator | None = 42, n_surrogates: int = 50, n_jobs: int = 1, nperseg: int | None = None, noverlap: int | None = None) -> Dict<br>*Compute frequency-resolved coherence between two LFP signals.* |
| jnwb.current_source_density_1d | function | (lfp_matrix: numpy.ndarray, pitch_um: float, conductivity_s_per_m: float, axis: int = 0) -> numpy.ndarray<br>*Compute physical 1D Current Source Density (CSD) along a laminar electrode array.* |
| jnwb.harmonic_analysis | function | (lfp_trace: numpy.ndarray, fs: float | None = None, sampling_rate: float | None = None, freq_range: Tuple[float, float] = (1.0, 90.0), harmonic_orders: int = 3, device: str = 'cpu') -> Dict<br>*Decompose LFP trace into fundamental and harmonic components.* |
| jnwb.imaginary_coherency | function | (x: numpy.ndarray, y: numpy.ndarray, fs: float | None = None, sampling_rate: float | None = None, freq_range: Tuple[float, float] = (1.0, 90.0), nperseg: int | None = None, noverlap: int | None = None, device: str = 'cpu') -> Dict[str, float]<br>*Imaginary part of coherency (Nolte et al. 2004) between two continuous signals.* |
| jnwb.laplacian_reference | function | (channel_data: numpy.ndarray, channel_order: numpy.ndarray | None = None) -> numpy.ndarray<br>*1D nearest-neighbor Laplacian re-reference along a probe's depth order.* |
| jnwb.relative_power | function | (power: numpy.ndarray, baseline: numpy.ndarray, model: str = 'mean_of_ratios', axis: int | Tuple[int, ...] | None = None, device: str = 'cpu') -> numpy.ndarray<br>*Compute relative power of a signal against baseline under an explicit mathematical estimand.* |
| jnwb.spectral_tilt | function | (lfp_trace: numpy.ndarray, fs: float | None = None, sampling_rate: float | None = None, freq_range: Tuple[float, float] = (1.0, 100.0), device: str = 'cpu') -> Dict<br>*Fit 1/f spectral tilt via linear regression of log10 power versus log10 frequency.* |
| jnwb.to_db | function | (ratio)<br>*``10*log10(ratio)``, the single point every power-ratio-to-dB conversion should pass through — average power, divide by baseline, then take the logarithm exactly once.* |
| jnwb.voltage_curvature_1d | function | (lfp_matrix: numpy.ndarray, pitch_um: float, axis: int = 0) -> numpy.ndarray<br>*Compute the discrete second spatial derivative of extracellular potential along a laminar probe.* |
| jnwb.wpli | function | (x: numpy.ndarray, y: numpy.ndarray, fs: float | None = None, sampling_rate: float | None = None, freq_range: Tuple[float, float] = (1.0, 90.0), nperseg: int | None = None, noverlap: int | None = None, device: str = 'cpu') -> Dict[str, typing.Any]<br>*Weighted Phase Lag Index (wPLI) between two continuous signals.* |

## Module: jnwb.spiking

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.classify_response_significance | function | (metrics: Dict[str, float], zscore_threshold: float = 1.96, min_spike_count: int = 5) -> Dict[str, bool | float]<br>*Classify unit response as significant based on metrics.* |
| jnwb.compute_response_metrics | function | (spike_times: numpy.ndarray, epoch_onsets: numpy.ndarray, baseline_window_s: Tuple[float, float] | None = None, response_window_s: Tuple[float, float] | None = None, z_score: bool = True, baseline_window: Tuple[float, float] | None = None, response_window: Tuple[float, float] | None = None) -> Dict[str, float]<br>*Compute firing rate and spike count metrics for stimulus responses.* |
| jnwb.gaussian_smooth_rate | function | (rate: numpy.ndarray, bin_ms: float, sigma_ms: float = 20.0, axis: int = -1) -> numpy.ndarray<br>*Apply symmetrical, acausal Gaussian smoothing to a binned firing rate trace.* |
| jnwb.pairwise_phase_consistency | function | (phases: numpy.ndarray, axis: int = -1) -> float | numpy.ndarray<br>*Compute the Pairwise Phase Consistency (PPC) across angular samples (Vinck et al., 2010).* |
| jnwb.phase_locking_index | function | (unit_spike_times: numpy.ndarray, lfp_phase: numpy.ndarray, lfp_timestamps: numpy.ndarray, n_bins: int = 18) -> Dict[str, float | numpy.ndarray]<br>*Compute circular phase distribution and Rayleigh non-uniformity test of spikes relative to LFP phase.* |

## Module: jnwb.statistics

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.StatisticalAnalysis | class | *Dual statistical testing with honest multiple-comparison handling.* |
| jnwb.assign_subblock_quartiles | function | (epochs_df: 'pd.DataFrame', n_quantiles: 'int' = 4) -> 'np.ndarray'<br>*Assign each row a temporal quantile bucket 0..n_quantiles-1 by its own start_time order.* |
| jnwb.clopper_pearson | function | (k: 'int', n: 'int', alpha: 'float' = 0.05) -> 'Tuple[float, float]'<br>*Exact (Clopper-Pearson) binomial confidence interval via the Beta-quantile form.* |
| jnwb.cluster_permutation_test | function | (X: 'np.ndarray', Y: 'np.ndarray', paired: 'bool' = False, groups: 'Optional[Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]]' = None, scheme: 'Optional[str]' = None, threshold: 'float' = 2.0, n_permutations: 'int' = 1000, tail: 'str' = 'both', rng: 'RNGLike' = 0, n_jobs: 'int' = 1) -> 'Dict[str, Union[np.ndarray, List[Dict[str, Union[float, np.ndarray]]]]]'<br>*Non-parametric cluster-based permutation test for multidimensional signals (Maris & Oostenveld, 2007).* |
| jnwb.cross_modal_comparison | function | (tfr_data: 'np.ndarray', spike_data: 'np.ndarray', lag_range_ms: 'Tuple[int, int]' = (-500, 500), bin_ms: 'Optional[float]' = None, n_permutations: 'int' = 1000, rng: 'RNGLike' = None, seed: 'Any' = None) -> 'Dict'<br>*Trial-averaged correlation between a TFR-derived signal and a spike-count signal.* |
| jnwb.detect_trial_cycles | function | (epochs_df: 'pd.DataFrame', gap_factor: 'float' = 10.0) -> 'np.ndarray'<br>*Detect temporal cluster ("cycle") boundaries in a trial table via a gap threshold.* |
| jnwb.exact_sign_flip | function | (diffs: 'Union[Sequence[float], np.ndarray]', alternative: 'str' = 'two-sided', n_mc: 'int' = 10000, rng: 'RNGLike' = 42) -> 'Tuple[float, float, float]'<br>*Exact paired sign-flip permutation test for paired sample differences.* |
| jnwb.fdr_correct | function | (p_values: 'Union[Sequence[float], np.ndarray]', method: 'str' = 'bh') -> 'np.ndarray'<br>*Benjamini-Hochberg (or compatible) FDR across a hypothesis family.* |
| jnwb.fire_indicator | function | (spike_times: 'np.ndarray', onsets_s: 'np.ndarray', window_ms) -> 'np.ndarray'<br>*Vectorized boolean fire indicator, one entry per onset, constant window.* |
| jnwb.fires_in_window | function | (spike_times: 'np.ndarray', onset_s: 'float', window_ms) -> 'bool'<br>*True iff >=1 spike falls in [onset_s + window_ms[0]/1000, onset_s + window_ms[1]/1000).* |
| jnwb.mann_whitney_p_floor | function | (n1: 'int', n2: 'int', alternative: 'str' = 'two-sided') -> 'float'<br>*Attainable minimal non-zero p-value floor for a Mann-Whitney U test without ties.* |
| jnwb.paired_fire_prob_test | function | (fires_target: 'np.ndarray', fires_null: 'np.ndarray', n_shuffles: 'int', n_bootstrap: 'int', rng: 'np.random.Generator') -> 'Dict'<br>*Paired binary test: P(fire | target window) vs P(fire | paired baseline window).* |
| jnwb.rate_in_window | function | (spike_times: 'np.ndarray', onset_s: 'float', window_ms: 'Tuple[float, float]') -> 'float'<br>*Firing rate (Hz) in ``[onset_s + window_ms[0]/1000, onset_s + window_ms[1]/1000)``.* |
| jnwb.shuffle_pvalue_paired | function | (a: 'np.ndarray', b: 'np.ndarray', n_shuffles: 'int', rng: 'np.random.Generator', alternative: 'str' = 'two-sided') -> 'Tuple[float, float]'<br>*Shuffle-controlled p-value for ``mean(a - b)`` via paired sign-flips.* |
| jnwb.shuffle_pvalue_unpaired | function | (a: 'np.ndarray', b: 'np.ndarray', n_shuffles: 'int', rng: 'np.random.Generator', alternative: 'str' = 'two-sided') -> 'Tuple[float, float]'<br>*Shuffle-controlled p-value for ``mean(a) - mean(b)`` via label-shuffling.* |
| jnwb.shuffle_r2_ci | function | (y_true: 'np.ndarray', y_score: 'np.ndarray', groups: 'Optional[np.ndarray]' = None, n_shuffle: 'int' = 200, rng: 'RNGLike' = 42, random_state: 'Any' = 42) -> 'Dict[str, float]'<br>*R^2 (squared Pearson correlation) between a continuous score and a 0/1 label, with a shuffle-null 95% CI.* |

## Module: jnwb.tfr

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.ComplexTFR | class | *Container for complex Time-Frequency Representation outputs.* |
| jnwb.complex_tfr | function | (data: 'np.ndarray', fs: 'float', freqs: 'np.ndarray', n_cycles: 'Union[float, np.ndarray]' = 5.0, time_axis: 'int' = -1, normalization: 'str' = 'amplitude', dtype: 'np.dtype' = <class 'numpy.complex128'>, coi_sigma: 'Optional[float]' = None, device: 'str' = 'cpu') -> 'ComplexTFR'<br>*Compute complex Time-Frequency Representation via Morlet wavelet convolution.* |
| jnwb.morlet_wavelet | function | (f0: 'float', fs: 'float', n_cycles: 'float' = 5.0, normalization: 'str' = 'amplitude', cutoff_sigma: 'float' = 4.0) -> 'Tuple[np.ndarray, np.ndarray]'<br>*Generate a discrete complex Morlet wavelet kernel.* |

## Module: jnwb.tfr_accumulator

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.TFRAccumulator | class | *Poolable sufficient statistics for complex TFR. Accumulate in float64/complex128.* |
| jnwb.assert_mergeable | function | (attrs_a: 'Dict', attrs_b: 'Dict') -> 'None' |

## Module: jnwb.trajectory

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.build_time_resolved_matrix | function | (session, area: str, epochs_df: pandas.DataFrame, time_window_ms: Tuple[float, float] = (-1000.0, 2000.0), bin_size_ms: float = 20.0, quality: str | None = None) -> Tuple[numpy.ndarray, List[int], numpy.ndarray]<br>*Build a trial-by-trial time-resolved population spike count matrix.* |
| jnwb.compute_population_trajectory | function | (session, area: str, epochs_df: pandas.DataFrame, time_window_ms: Tuple[float, float] = (-1000.0, 2000.0), bin_size_ms: float = 20.0, n_components: int = 3, quality: str | None = None, device: str = 'cpu') -> Dict[str, numpy.ndarray | List[int] | float]<br>*Compute population trajectory using standardized correlation PCA (SVD). Supports GPU SVD acceleration via PyTorch if device='cuda' and CUDA is available.* |

## Module: jnwb.viz

| Symbol | Type | Signature / Description |
|---|---|---|
| jnwb.apply_tight_auto_axis | function | (ax, x_span: Tuple[float, float] = (-500, 4124), y_margin: float = 0.12)<br>*Apply tight temporal bounds and auto-scale y-axis without empty margins.* |
| jnwb.raster_psth | function | (st, onsets, win_ms, bin_ms: float = 10.0)<br>*Trial-averaged PSTH (mean + SEM firing rate per bin) for a raw spike-time array against an explicit onset array -- raw arrays in, no session/unit_id lookup. Distinct from :func:`jnwb.spiking.compute_response_metrics`'s single-response-window-scalar contract: this returns the full time-binned PSTH curve.* |
| jnwb.resample_onsets | function | (onsets: numpy.ndarray, target_n: int = 100, rng: int | numpy.random._generator.Generator | None = 42, random_state: typing.Any = 42) -> numpy.ndarray<br>*Resample a trial-onset array to exactly ``target_n`` onsets (with replacement if there are fewer than ``target_n`` available), for a consistent raster trial count across units with different trial counts.* |
| jnwb.save_figure_suite | function | (figures: List[matplotlib.figure.Figure], output_dir: str | pathlib.Path, basename: str, dpi: int = 300, formats: List[str] = ['png', 'pdf']) -> None<br>*Save a suite of figures to disk with consistent naming.* |
| jnwb.setup_vector_graphics | function | ()<br>*Enforce editable vector SVG font rendering in Adobe Illustrator / Inkscape.* |
