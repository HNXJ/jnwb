# Omission Repository Function Catalog

**Generated:** 2026-06-08  
**Repo SHA:** `52461b8e06890033c93c6dbfb2453a4699a732c2`  
**Branch:** `rewritten-history`

This catalog lists all major functions, classes, and tools in the omission repository with descriptions and usage contexts.

---

## Table of Contents

1. [Core Data I/O](#core-data-io)
2. [Figure Modules (f001-f050)](#figure-modules)
3. [LFP Analysis](#lfp-analysis)
4. [Spiking Analysis](#spiking-analysis)
5. [Statistics & Decoding](#statistics--decoding)
6. [Visualization](#visualization)
7. [Contract System](#contract-system)
8. [Validation & Audit Scripts](#validation--audit-scripts)
9. [Analysis Scripts](#analysis-scripts)
10. [Tests](#tests)

---

## Core Data I/O

### `src/analysis/io/loader.py`

| Function/Class | Description | When to Use |
|----------------|-------------|-------------|
| `normalize_area_resolution_status(status)` | Maps legacy resolution statuses to contract-standard ones | Data provenance normalization |
| `class DataLoader` | Core data loader with lazy mmap for `.npy` files, parses session-area mapping | Primary data access interface |
| `DataLoader.__init__(data_dir, mapping_file)` | Initialize with data directory and mapping file | Starting analysis |
| `DataLoader.get_subject_id(session)` | Returns subject ID (NHP_A/NHP_B) for session | Subject-level grouping |
| `DataLoader.get_eye_data_path(session)` | Resolves `.bhv2.mat` behavioral file for oculomotor analysis | Eye/pupil tracking |
| `DataLoader._parse_mapping()` | Parses markdown table to build area→(session,probe,channels) mapping | Internal mapping construction |
| `DataLoader.get_area_channels(area, session)` | Returns channel indices for area in session | Area-based signal extraction |
| `DataLoader.get_signal(mode, condition, area, align_to)` | Extracts SPK/LFP/MUAe signal for given condition/area | Main signal retrieval |
| `DataLoader._load_data(mode, condition, area, session)` | Loads numpy array from file system | Low-level data access |
| `DataLoader.load_unit_spikes(unit_id, condition, epoch)` | Loads spike train for single unit | Single-unit analysis |
| `DataLoader.resolve_unit_area_metadata(session, probe, unit_idx)` | Resolves anatomical assignment for unit | Unit area provenance |
| `DataLoader.get_omission_onset(condition)` | Returns omission onset in ms for condition (P2=1031, P3=2062, P4=3093) | Omission timing alignment |
| `DataLoader.normalize_area(area)` | Normalizes area labels (DP→V4) | Area name standardization |

### `src/analysis/io/eye_mapper.py`

| Function/Class | Description | When to Use |
|----------------|-------------|-------------|
| `class EyeDataMapper` | Manages mapping of behavioral `.bhv2.mat` files | Oculomotor/pupil analysis |
| `EyeDataMapper.get_behavioral_file(session_id)` | Returns exact behavioral file path | Eye data loading |

### `src/analysis/io/logger.py`

| Function/Class | Description | When to Use |
|----------------|-------------|-------------|
| `class OmissionLogger` | Structured logging for analysis actions | Tracking analysis steps |

---

## Figure Modules

### Registry: `src/analysis/registry.py`

| Function/Class | Description | When to Use |
|----------------|-------------|-------------|
| `class FigureRegistry` | Central registry for all f001-f050 figures | Figure discovery and metadata |
| `FigureRegistry.get_all()` | Returns all figure metadata | Listing available figures |
| `FigureRegistry.get_by_id(fid)` | Returns metadata for specific figure | Getting figure info |
| `FigureRegistry.get_by_phase(phase_num)` | Returns figures in analysis phase | Phase-based workflows |
| `FigureRegistry.should_include_file(fig_id, filename)` | Policy enforcement for stale artifact filtering | Artifact validation |

### Phase 1: Schematic/PSTH

#### `src/f001_theory/`
| Function | Description | When to Use |
|----------|-------------|-------------|
| `analysis.py` | Theory/model analysis functions | Computational modeling |
| `plot.py` | Schematic figure generation | Manuscript Fig 1 |
| `script.py::run_f001()` | Execute f001 pipeline | Theory figure generation |

#### `src/f002_psth/`
| Function | Description | When to Use |
|----------|-------------|-------------|
| `analysis.py::analyze_area_psths(loader, areas)` | Computes PSTHs across areas | Population firing rates |
| `plot.py::plot_area_psths(results, output_dir)` | Plots area PSTH panels | Fig 2 generation |
| `script.py::run_f002()` | Execute f002 pipeline | PSTH figure generation |

### Phase 2: Unit Coding/Surprise

#### `src/f003_surprise/`
| Function | Description | When to Use |
|----------|-------------|-------------|
| `analysis.py` | Surprise/expectation violation analysis | R-family sequence analysis |
| `plot.py` | R-family raster/PSTH plots | Fig 6 generation |
| `script.py::run_f003()` | Execute f003 pipeline | Random control analysis |

#### `src/f004_coding/`
| Function | Description | When to Use |
|----------|-------------|-------------|
| `analysis.py::smooth_fr(data, sigma)` | Gaussian smoothing for firing rates | Rate preprocessing |
| `analysis.py::analyze_unit_coding(loader, unit_id)` | Single-unit coding analysis | Unit characterization |
| `plot.py::plot_raster_suite(results, unit_id, tag, area, output_dir)` | 6-panel raster+PSTH suite | Fig 4/5 generation |
| `find_stable_units.py::find_highly_responsive_units(min_fr)` | Find responsive units | Unit selection |
| `find_stable_units.py::compute_area_coding_stats()` | Area-level coding statistics | Population summaries |
| `script.py::run_f004()` | Execute f004 pipeline | Coding figure generation |

### Phase 3: TFR/Band Power

#### `src/f005_tfr/`
| Function | Description | When to Use |
|----------|-------------|-------------|
| `analysis.py::analyze_area_tfrs(areas, conditions)` | Computes multitaper TFRs per area | Time-frequency analysis |
| `plot.py::plot_area_tfrs(results, output_dir)` | Plots TFR spectrograms | Fig 7 generation |
| `script.py::run_f005()` | Execute f005 pipeline | TFR figure generation |

#### `src/f006_band_power/`
| Function | Description | When to Use |
|----------|-------------|-------------|
| `analysis.py` | Band-specific power analysis | Theta/alpha/beta/gamma power |
| `plot.py` | Band power trajectory plots | Fig 8 generation |
| `script.py::run_f006()` | Execute f006 pipeline | Band power figure generation |

### Phase 4: Connectivity/SFC

#### `src/f007_sfc/`
| Function | Description | When to Use |
|----------|-------------|-------------|
| `analysis.py` | Spike-Field Coherence analysis | SFC computation |
| `plot.py` | SFC spectrum plots | Supplementary SFC figures |
| `script.py` | Execute f007 pipeline | SFC analysis (CuPy accelerated) |

#### `src/f008_coordination/`
| Function | Description | When to Use |
|----------|-------------|-------------|
| `analysis.py` | Cross-area coordination analysis | Beta/gamma harmony |
| `plot.py` | Coordination matrix plots | Fig 9 (METHOD_PENDING) |
| `script.py` | Execute f008 pipeline | Harmony analysis |

#### `src/f009_individual_sfc/`
| Function | Description | When to Use |
|----------|-------------|-------------|
| `analysis.py`, `plot.py`, `script.py` | Unit-level SFC analyses | Individual unit coupling |

#### `src/f010_sfc_delta/`
| Function | Description | When to Use |
|----------|-------------|-------------|
| `analysis.py`, `plot.py`, `script.py` | Delta-SFC (surprise) analysis | SFC change metrics |

### Phase 5: Advanced Analyses (f011-f046)

| Module | Purpose | When to Use |
|--------|---------|-------------|
| `f011_laminar/` | Laminar mapping and CSD | Layer-resolved analysis |
| `f012_csd_profiling/` | Current source density | Sink/source identification |
| `f013_rhythmic_evolution/` | Rhythm dynamics | Temporal evolution patterns |
| `f014_spiking_granger/` | Granger causality on spikes | Directional connectivity |
| `f015_spectral_granger/` | Spectral Granger causality | Frequency-resolved causality |
| `f016_impedance_profiles/` | Impedance estimation | Tissue properties |
| `f017_prediction_errors/` | Prediction error scaling | Error magnitude analysis |
| `f018_ghost_signals/` | Artifact detection | Quality control |
| `f019_pac_analysis/` | Phase-amplitude coupling | Cross-frequency coupling |
| `f020_effective_connectivity/` | Effective connectivity | Network inference |
| `f021_madelamo/` | MaDeLaMo schematic | Model diagrams |
| `f022_madelane/` | MaDeLaNe projection | Dimensionality reduction |
| `f023_spectral_fingerprints/` | Spectral fingerprints | Area-specific signatures |
| `f024_fano_factor/` | Fano factor analysis | Variability metrics |
| `f025_state_decoding/` | State decoding | Latent state inference |
| `f026_state_latency/` | State latency | Timing metrics |
| `f027_identity_coding/` | Identity coding | Stimulus identity |
| `f028_state_manifolds/` | State-space trajectories | Dimensionality reduction |
| `f029_info_bottleneck/` | Information bottleneck | Compression analysis |
| `f030_putative_cell_type/` | Cell type classification | Interneuron/PYRAMIDAL |
| `f031_spike_phase_locking/` | Spike-LFP locking | Phase-locking analysis |
| `f032_spike_triggered_average/` | STA computation | Spike-triggered LFP |
| `f033_spike_field_coherence/` | Alternative SFC | Coherence measures |
| `f034_pev_analysis/` | Percent explained variance | Variance decomposition |
| `f035_deviance_scaling/` | Deviance scaling | Model comparison |
| `f036_interneuron_dynamics/` | Interneuron analysis | Cell-type specific |
| `f037_selectivity_index/` | Selectivity metrics | Tuning strength |
| `f038_layer_granger/` | Laminar Granger | Layer-resolved causality |
| `f039_spike_field_coherence/` | PPC analysis | Pairwise phase consistency |
| `f040_onset_latency/` | Onset latency | Response timing |
| `f044_laminar_pac/` | Laminar PAC | Layer CFC |
| `f045_laminar_coherence/` | Laminar coherence | Layer synchrony |
| `f046_state_space_trajectories/` | State trajectories | PC projections |

### Phase 6: Audits/Profiles (f047-f050)

| Module | Purpose | When to Use |
|--------|---------|-------------|
| `f047_stability_audit/` | Pipeline stability audit | Session-level validation |
| `f048_profile_analysis/` | Profile search utility | Effect size exploration |
| `f049_omission_profiles/` | Omission response profiles | CLM-001 validation |
| `f050_conjunction_profiles/` | Conjunction analysis | Combined condition effects |

---

## LFP Analysis

### `src/analysis/lfp/lfp_tfr.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `compute_multitaper_tfr(data, fs, freq_range, n_cycles)` | Compute multitaper TFR | Time-frequency decomposition |
| `compute_band_power_efficiently(data, fs, freqs)` | Band power via Welch | Efficient power computation |
| `get_band_power(freqs, power, band_limits)` | Extract band power | Theta/alpha/beta/gamma isolation |
| `collapse_band_power(freqs, power)` | Collapse to canonical bands | Standard band aggregation |

### `src/analysis/lfp/lfp_preproc.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `preprocess_lfp(lfp, fs)` | Bandpass and notch filter | Standard LFP preprocessing |
| `baseline_normalize(power, times, baseline_window)` | dB normalization | Baseline correction |

### `src/analysis/lfp/lfp_pipeline.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `get_lfp_signal(lfp_arr, times_ms, selection_window)` | Extract time window | LFP epoching |
| `run_lfp_spectral_pipeline(area, condition, allow_channel_trim)` | Full spectral pipeline | End-to-end LFR processing |

### `src/analysis/lfp/lfp_laminar_mapping.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `compute_spectrolaminar_profiles(lfp_data_probe, fs)` | Spectral profiles per channel | Laminar spectral analysis |
| `find_crossover(profiles)` | Find layer boundaries | Laminar boundary detection |
| `get_laminar_crossover(...)` | Full crossover analysis | Layer identification |
| `map_channels_to_layers(...)` | Map channels to layers | Laminar assignment |

### `src/analysis/lfp/sfc.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `compute_ppc(phases, min_spikes)` | Pairwise phase consistency | SFC metric |
| `calculate_plv(lfp, spikes, fs, freq_band)` | Phase-locking value | PLV computation |
| `get_plv_spectrum(lfp, spikes, fs, n_bins, metric)` | Spectrum of PLV | Frequency-resolved coupling |
| `select_top_units(loader, area, mode, top_n)` | Select responsive units | Unit selection for SFC |
| `get_matched_sfc_data(loader, unit_info)` | Get SFC data for units | Data preparation |
| `apply_subsampling(spikes_list, target_count)` | Rate matching | Bias correction |

### `src/analysis/lfp/connectivity.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `apply_rate_matching(src_pop, tgt_pop)` | Match firing rates | Bias correction |
| `compute_granger_causality(src_signal, tgt_signal, maxlag)` | Granger causality | Directional inference |

### `src/analysis/lfp/lfp_connectivity.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `compute_coherence(x, y)` | Coherence magnitude | Synchrony measure |
| `compute_granger(x, y)` | Granger causality wrapper | Causality wrapper |

### `src/analysis/lfp/lfp_constants.py`

| Constant/Class | Description | When to Use |
|----------------|-------------|-------------|
| `TIMING_MS` | Epoch timing constants (fx, p1, d1, p2, etc.) | Temporal alignment |
| `CONDITION_NUMBER_MAP` | Maps condition numbers to codes | Condition decoding |
| `ALL_CONDITIONS` | Canonical 12 condition codes | Condition enumeration |
| `OMISSION_CONDITIONS` | Subset with X (omission) | Omission conditions |
| `class FigureSpec` | Figure specification dataclass | Figure configuration |

### `src/analysis/lfp/signal.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `_process_lfp(data, fs, nperseg, noverlap)` | Spectrogram computation | Time-frequency |
| `_process_spikes(data, sigma_ms)` | Spike rate smoothing | Rate estimation |

### `src/analysis/lfp/stats.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `compute_modulation_index(phase_signal, amplitude_signal, n_bins)` | PAC computation | Phase-amplitude coupling |
| `extract_phase_amplitude(lfp, fs, f_phase, f_amp)` | Extract phase/amp signals | PAC preparation |

---

## Spiking Analysis

### `src/analysis/spiking/stats.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `compute_unit_metrics(spk_arr, baseline_window, response_window)` | FR, modulation, reliability | Unit characterization |
| `compute_mutual_info(spk_binary, lfp_power, n_bins)` | Spike-LFP MI | Information metrics |
| `compute_connectivity_matrix(spk_data, lfp_data, mode)` | Area connectivity | Population coupling |
| `fast_mi_plugin(x_binary, y_binned, n_bins)` | Fast MI computation | Efficient MI |
| `compute_omission_connectivity_tensor(...)` | Session-area connectivity | Multi-dimensional connectivity |
| `aggregate_connectivity_matrix(...)` | Aggregate across sessions | Meta-analysis |
| `detect_ramping_units(spk_arr, window)` | Ramping detection | Temporal pattern |
| `classify_omission_units(spk_dict, baseline_window, omission_window, rates)` | O+ / O- / neutral classification | Response typing |
| `compute_statistics(data, stat_type, **kwargs)` | Generic statistics wrapper | Statistical summaries |
| `_compute_fano(data)` | Fano factor | Variability |
| `_compute_zscore(data)` | Z-score normalization | Standardization |
| `_compute_kmeans(data, n_clusters)` | K-means clustering | Clustering |
| `_compute_gmm(data, n_components)` | Gaussian mixture model | Probabilistic clustering |
| `_compute_pca(data, n_components)` | PCA | Dimensionality reduction |

### `src/analysis/spiking/putative_classification.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `compute_waveform_metrics(waveform_mean, fs)` | Spike waveform analysis | Cell type classification |
| `is_stable_plus(unit_metrics, spk_train, min_fr, min_pr, min_snr)` | Stable-Plus filter | Quality filtering |
| `assign_putative_type(metrics, threshold_us)` | PYRAMIDAL vs INTERNEURON | Cell typing |

### `src/analysis/spiking/omission_hierarchy_utils.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `get_unit_to_area_map(nwb_path)` | Unit→area mapping from NWB | Area assignment |
| `extract_unit_traces(session_id, conds, sigma)` | Smooth firing rate traces | Rate extraction |
| `classify_unit_types(nwb_path)` | Unit type classification | Type annotation |
| `compute_area_mmff(all_unit_stats, areas, conds, win_size, step)` | Multi-resolution analysis | Temporal evolution |

---

## Statistics & Decoding

### `src/analysis/stats/tiers.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `get_significance_tier(p_value)` | Tier assignment (T1-T4) | Evidence grading |
| `format_stats_proof(test_name, p_value, n_sessions, n_units)` | Formatted stats string | Reporting |
| `run_permutation_test(data_a, data_b, n_permutations, unit_of_inference)` | Permutation testing | Non-parametric stats |
| `run_frequency_wise_comparison(spec_a, spec_b, alpha)` | Frequency-resolved tests | Spectral stats |
| `compute_granger_bootstrapped_null(target_pool, source_pool, gc_func, n_boots)` | Null distribution | GC significance |

### `src/analysis/stats/decoding.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `sliding_window_decoder(data_cond1, data_cond2, window_size, step_size)` | Moving window decoding | Temporal decoding |

### `src/analysis/profile_search.py`

| Function/Class | Description | When to Use |
|----------------|-------------|-------------|
| `get_band_power(lfp, fs)` | Band power extraction | Feature extraction |
| `class ProfileSearcher` | Search for omission-sensitive profiles | Profile discovery |

---

## Visualization

### `src/analysis/visualization/plotting.py`

| Function/Class | Description | When to Use |
|----------------|-------------|-------------|
| `class OmissionPlotter` | Main plotting interface | General plotting |

### `src/analysis/visualization/lfp_plotting.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `create_tfr_figure(freqs, times_ms, power, title, area)` | TFR heatmap | TFR visualization |
| `create_band_plot(times_ms, mean_pwr, sem_pwr, title, color, area)` | Band trajectory | Power time course |
| `plot_band_trajectories(bands, times_ms)` | Multi-band plot | Comparative bands |
| `plot_coherence_network(coh, band_name)` | Network visualization | Connectivity graph |
| `make_multi_area_band_figure(grouped, time_ms, out_html, title, area_order)` | Multi-area bands | Population summary |

### `src/analysis/visualization/poster_figures.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `plot_band_power_hierarchy(...)` | Hierarchical band power | Fig 8-style panels |
| `plot_mua_tfr_panel(...)` | MUA TFR panel | MUA spectrogram |
| `plot_spectral_corr_matrices(...)` | Correlation matrices | Cross-area correlation |
| `plot_r2_change_bars(...)` | R² change bars | Explained variance |
| `plot_spectral_network(...)` | Spectral network graph | Network diagram |
| `plot_neuron_group_traces(...)` | Grouped neuron traces | PSTH summaries |
| `plot_omission_fraction_bars(...)` | O+ / O- fractions | Response classification |
| `plot_spectral_harmony_matrices(...)` | Harmony matrices | Beta/gamma coordination |
| `plot_beta_gamma_shift_bars(...)` | BG shift bars | Harmony change |
| `plot_gamma_beta_dissociation(...)` | GB dissociation | Separate gamma/beta effects |

---

## Contract System

### `src/analysis/contracts/signal_block.py`

| Function/Class | Description | When to Use |
|----------------|-------------|-------------|
| `class SignalBlock` | Typed signal container with metadata | Data passing between stages |
| `make_signal_block(...)` | Factory for SignalBlock | Block creation |

### `src/analysis/contracts/bounded_slice.py`

| Function/Class | Description | When to Use |
|----------------|-------------|-------------|
| `class BoundedSliceRequest` | Request for bounded time slice | Slice specification |
| `class BoundedSliceResult` | Result container with provenance | Slice results |
| `make_bounded_fixture_slice(request)` | Create fixture slice | Testing |
| `load_bounded_real_slice(request)` | Load real data slice | Production |

### `src/analysis/contracts/tiny_readers.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `can_read_tiny_npy_slice(request)` | Check if slice is readable | Pre-read validation |
| `infer_signal_class_from_path(path)` | SPK/LFP/MUAe from path | Path parsing |
| `is_compatible_signal_class(inferred, requested)` | Check compatibility | Request validation |
| `read_tiny_npy_slice(request)` | Read numpy slice | Memory-efficient access |

### `src/analysis/contracts/signal_block_adapters.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `as_array(signal_block)` | Convert to numpy array | Array extraction |
| `assert_signal_dims(signal_block, expected_dims)` | Validate dimensions | Shape checking |
| `summarize_signal_block(signal_block)` | Metadata summary | Provenance logging |
| `split_signal_axis(signal_block)` | Split by axis | Dimension analysis |

### `src/analysis/contracts/session_manifest.py`

| Class | Description | When to Use |
|-------|-------------|-------------|
| `ConditionInfo` | Condition metadata container | Condition provenance |
| `AreaMapping` | Area mapping metadata | Area provenance |
| `UnitMetadata` | Unit-level metadata | Unit provenance |
| `SessionManifest` | Session-level manifest | Session aggregation |

### `src/analysis/contracts/data_source_index.py`

| Class | Description | When to Use |
|-------|-------------|-------------|
| `DataSourceRecord` | Single data source record | Source tracking |
| `DataSourceIndex` | Index of all sources | Discovery |

### `src/analysis/contracts/fixture_signal_blocks.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `_normalize_area(area)` | Area normalization | Consistent naming |
| `make_fixture_signal_block(...)` | Create synthetic signal | Testing |
| `make_fixture_signal_blocks_for_all_signals(...)` | Full fixture set | Comprehensive testing |

### `src/analysis/contracts/manifest_scaffold.py`

| Class | Description | When to Use |
|-------|-------------|-------------|
| `ManifestScaffoldCandidate` | Scaffold candidate record | Manifest building |
| `ManifestScaffoldReport` | Full scaffold report | Validation |

### `src/analysis/contracts/constants.py`

| Content | Description |
|---------|-------------|
| Timing constants, band definitions, area orders | Shared constants across modules |

---

## Validation & Audit Scripts

### `scripts/validate_task_taxonomy.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `validate_manifest_taxonomy(manifest_path)` | Validate condition taxonomy | Phase 00-02 gate |
| `render_md_report(results_list)` | Markdown validation report | Reporting |
| `main()` | CLI entry point | Command-line validation |

### `scripts/build_dataset_census.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `discover_session(name)` | Session discovery | Inventory |
| `detect_condition(name)` | Condition code extraction | Parsing |
| `get_condition_family(cond)` | A/B/R family | Family assignment |
| `get_omission_position(cond)` | P2/P3/P4 slot | Slot assignment |
| `get_matched_control(cond)` | Control condition | Control mapping |
| `main()` | Census generation | Full inventory |

### `scripts/build_area_probe_metadata_inventory.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `parse_mapping(mapping_file)` | Parse area mapping | Metadata extraction |
| `main()` | Build area inventory | A6 pipeline |

### `scripts/build_signal_shape_inventory.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `infer_signal_class(basename)` | Class from filename | Type inference |
| `get_expected_dims(sig_class)` | Expected dimensions | Shape validation |
| `inspect_npy_shape(file_path)` | Get numpy shape | File inspection |
| `main()` | Build shape inventory | A5 pipeline |

### `scripts/build_trial_count_validation.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `extract_trial_counts(path, file_type, session_id)` | Extract trial counts | Validation |
| `main()` | Trial count validation | A3 pipeline |

### `scripts/build_spk_psth_smoke_inventory.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `main()` | PSTH smoke test inventory | A7 gate |

### `scripts/build_spk_response_metric_contract.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `generate_synthetic_spikes(condition, trials, units, timepoints)` | Synthetic data | Contract testing |
| `main()` | Response metric contract | A8 contract |

### `scripts/run_spk_response_metrics_a8_1.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `compute_cohens_d(x, y)` | Effect size | Statistics |
| `classify_prototype_unit(rates)` | O+ / O- / X classification | Unit typing |
| `run_paired_test(x, y)` | Paired statistics | Condition comparison |
| `run_unpaired_test(x, y)` | Unpaired statistics | Group comparison |
| `main()` | Response metrics (A8.1) | Main analysis |

### `scripts/run_spk_response_metric_sensitivity_a8_2.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `compute_entropy(labels_list)` | Label entropy | Stability metric |
| `resolve_priority_label(labels_set)` | Priority resolution | Label consolidation |
| `main()` | Sensitivity analysis (A8.2) | Robustness testing |

### `scripts/run_spk_sua_response_class_table.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `get_post_omission_rate(...)` | Post-omission firing rate | Response quantification |
| `main()` | Response class table | Unit categorization |

### `scripts/run_unit_area_provenance_recovery_a8_4.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `channel_to_area(session, probe, channel_id)` | Channel→area mapping | Geometry-based assignment |
| `build_recovery_table(...)` | Build provenance table | Area recovery |
| `main()` | Unit area recovery (A8.4) | Provenance reconstruction |

### `scripts/run_unit_area_geometry_validation_a8_4_1.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `evaluate_channel_interpretations(session, probe, peak_ch_str)` | Channel interpretation | Geometry validation |
| `run_geometry_validation(a8_4_long_csv)` | Full validation | A8.4.1 audit |
| `main()` | Geometry validation | Channel mapping audit |

### `scripts/run_unit_area_mapping_diagnostic_a8_3.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `resolve_area_group(canonical_area)` | Group resolution | Area grouping |
| `resolve_claim_flags(area_resolution_status, canonical_area_label)` | Claim eligibility | Hierarchy gating |
| `build_long_mapping_table(...)` | Long-format table | Diagnostic output |
| `build_join_integrity_report(...)` | Join validation | Referential integrity |
| `main()` | Area mapping diagnostic (A8.3) | Join audit |

### `scripts/audit_artifact_contract_v2.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `audit_artifact_directory(dir_path)` | Directory audit | Contract validation |
| `main()` | Artifact audit | Quality control |

### `scripts/validate_bounded_signal_slice.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `main()` | Bounded slice validation | Smoke test |

### `scripts/validate_data_source_index.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `generate_report(results, out_path)` | Index report | Validation reporting |
| `main()` | Data source validation | Index verification |

### `scripts/validate_fixture_signal_blocks.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `main()` | Fixture validation | Test data verification |

### `scripts/validate_session_manifest_contract.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `validate_single_manifest_file(manifest_path, expect_real)` | Manifest validation | Schema compliance |
| `generate_report(results, out_path)` | Report generation | Validation output |
| `main()` | Session manifest validation | Contract verification |

### `scripts/validate_signalblock_downstream_smoke.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `main()` | SignalBlock smoke test | Downstream compatibility |

### `scripts/validate_task_taxonomy.py`

| Function | Description | When to Use |
|----------|-------------|-------------|
| `validate_manifest_taxonomy(manifest_path)` | Taxonomy validation | Condition validation |
| `render_md_report(results_list)` | Markdown report | Reporting |
| `main()` | Task taxonomy validation | Phase 00-02 gate |

---

## Tests

### Core Tests

| Test File | Purpose | Key Functions |
|-----------|---------|---------------|
| `test_skill_paths.py` | Skill file path validation | `test_skill_paths()`, `test_skill_required_sections_selected()` |
| `test_unit_area_mapping.py` | Area mapping logic | `test_resolve_unit_area_metadata_resolved()`, `test_normalize_area()` |
| `test_unit_area_provenance_recovery_a8_4.py` | A8.4 provenance | `test_probe_extraction_is_deterministic()`, `test_dp_maps_to_v4_in_recovery()` |
| `test_unit_area_geometry_validation_a8_4_1.py` | A8.4.1 geometry | `test_0_based_channel_interpretation()`, `test_modulo_128_conversion_explicit()` |
| `test_unit_area_mapping_diagnostic_a8_3.py` | A8.3 diagnostic | `test_join_integrity_one_to_one()`, `test_heuristic_mapping_blocks_hierarchy()` |
| `test_spk_response_metrics_a8_1.py` | A8.1 metrics | `test_end_to_end_metrics_execution()`, `test_benjamini_hochberg_correction()` |
| `test_spk_response_metric_sensitivity_a8_2.py` | A8.2 sensitivity | `test_sensitivity_grid_parser()`, `test_session_dominance_detection()` |
| `test_spk_response_metric_contract.py` | A8 contract | `test_window_index_mappings()`, `test_matched_control_mappings()` |
| `test_spk_psth_smoke_inventory.py` | A7 smoke test | `test_condition_family_and_omission_slot_parsing()`, `test_timing_constants()` |
| `test_trial_count_validation.py` | A3 trial counts | `test_extract_trial_counts_json()`, `test_full_validation_run()` |
| `test_f007_sfc.py` | SFC testing | `test_get_band_phases_cpu_correctness()`, `test_analyze_circular_sfc_smoke()` |
| `test_bounded_signal_slice.py` | Bounded slice | Slice request/result validation |
| `test_contracts.py` | Contract system | SignalBlock, manifest contracts |
| `test_data_source_index.py` | Data source | Index validation |
| `test_fixture_signal_blocks.py` | Fixtures | Fixture block validation |
| `test_loader_manifest_discovery.py` | Loader/manifest | Manifest discovery |
| `test_loader_resolution_status_normalization.py` | Status normalization | Legacy status mapping |
| `test_manifest_scaffold.py` | Scaffold | Manifest scaffold validation |
| `test_session_manifest_schema.py` | Session manifest | Schema compliance |
| `test_session_manifest_validator.py` | Validation | Session validator |
| `test_signal_shape_inventory.py` | Shape inventory | A5 validation |
| `test_signalblock_downstream_smoke.py` | Downstream | Compatibility testing |
| `test_import_safety.py` | Import safety | No-dependency imports |

---

## Usage Patterns

### Basic Data Loading
```python
from src.analysis.io.loader import DataLoader
loader = DataLoader()
subject = loader.get_subject_id("230630")
signal = loader.get_signal("spk", "AXAB", "V1", align_to="p1")
```

### LFP Analysis Pipeline
```python
from src.analysis.lfp.lfp_pipeline import run_lfp_spectral_pipeline
results = run_lfp_spectral_pipeline("V1", "AXAB", allow_channel_trim=False)
```

### TFR Computation
```python
from src.analysis.lfp.lfp_tfr import compute_multitaper_tfr
tfr = compute_multitaper_tfr(lfp_data, fs=1000, freq_range=(1, 100), n_cycles=7)
```

### Unit Classification
```python
from src.analysis.spiking.stats import classify_omission_units
unit_types = classify_omission_units(spk_dict, baseline_window=(531, 1031), omission_window=(1031, 1531))
```

### SFC Computation
```python
from src.analysis.lfp.sfc import compute_ppc, calculate_plv
ppc_value = compute_ppc(phases, min_spikes=5)
plv = calculate_plv(lfp, spikes, fs=1000, freq_band=(13, 30))
```

### Figure Generation
```python
from src.f004_coding.plot import plot_raster_suite
plot_raster_suite(results, unit_id="unit_001", tag="O+", area="V4", output_dir="figures/")
```

### Registry Query
```python
from src.analysis.registry import FigureRegistry
fig_info = FigureRegistry.get_by_id("f005")
phase_3_figs = FigureRegistry.get_by_phase(3)
```

---

## Key Constants Reference

### Timing (ms from p1 onset)
| Epoch | Start | End |
|-------|-------|-----|
| fx (baseline) | -500 | 0 |
| p1 | 0 | 531 |
| d1 | 531 | 1031 |
| p2 | 1031 | 1562 |
| d2 | 1562 | 2062 |
| p3 | 2062 | 2593 |
| d3 | 2593 | 3093 |
| p4 | 3093 | 3624 |
| d4 | 3624 | 4124 |

### Omission Onsets (ms from p1)
| Slot | Onset |
|------|-------|
| P2 (AXAB, BXBA, RXRR) | 1031 |
| P3 (AAXB, BBXA, RRXR) | 2062 |
| P4 (AAAX, BBBX, RRRX) | 3093 |

### Frequency Bands
| Band | Range (Hz) |
|------|------------|
| Theta | 4-8 |
| Alpha | 8-13 |
| Beta | 13-30 (widened) |
| Gamma | 35-70 |

### Canonical Areas (hierarchical order)
```
V1 → V2 → V3d → V3a → V4 → MT → MST → TEO → FST → FEF → PFC
```

### Condition Codes
| Family | Standard | P2 Omission | P3 Omission | P4 Omission |
|--------|----------|-------------|-------------|-------------|
| A | AAAB | AXAB | AAXB | AAAX |
| B | BBBA | BXBA | BBXA | BBBX |
| R | RRRR | RXRR | RRXR | RRRX |

---

## Notes

- **Blacklisted Sessions:** `230901` (PFC clipping artifact)
- **Area Aliases:** `DP`, `DP (V4)` → normalized to `V4`
- **V3 Handling:** `V3d` and `V3a` explicit, not collapsed to generic `V3`
- **Stable-Plus Criteria:** FR>1Hz, PR>0.98, SNR>0.5 (configurable)
- **Claim Ledger:** See `docs/claim_ledger.md` for active claims CLM-001 to CLM-010

---

*End of Function Catalog*
