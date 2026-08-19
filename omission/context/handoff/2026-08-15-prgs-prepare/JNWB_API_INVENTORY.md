# jnwb API inventory — PRGS Prepare snapshot, 2026-08-15

Per-module public surface, as directly read (this agent, or a delegated sub-agent doing a full
file read — both are OBSERVED FACT, not summary-of-summary). "Used in scripts/" reflects grep
evidence where it was actually run; where it was not run for a given symbol, it says so rather
than guessing. See `JNWB_ARCHITECTURE.md` for narrative context.

## Core / session

| Module | Public surface | I/O contract | Consumers |
|---|---|---|---|
| `session.py` | `OmissionSession` (see architecture §2 for full method list); `condition_map_for_stem`, `CONDITION_MAP_DEFAULT`, `CONDITION_MAP_V182O` | `session.get_epochs()` → DataFrame; `get_spike_times(unit_id)` → `np.ndarray[float]` seconds or `None`; `tfr_from_preprocessed` → `(n_trials,n_channels,n_freqs,n_times)` float32 memmap or `None` | `import jnwb as oa` used ~73× in `scripts/` (delegated count) |
| `paths.py` | `REPO_ROOT`, `nwb_dir`, `tfr_dir`, `meta_dir`, `conndb_dir`, `analysis_dir`, `outputs_dir`, `artifacts_dir`, `layer_masks_path`, `resolve_nwb_path`, `sha256_file`, `require`, `describe` | pure path resolution, env-var overridable; `require()` raises `FileNotFoundError` with fix hint | tied top import, ~73× (delegated) |
| `addressing.py` | `map_peak_channel_to_area`, `classify_layer_from_depth`, `enrich_units_dataframe` | electrodes/units DataFrames in, enriched DataFrame / area string / layer string out | called from `session._load_nwb` |

## Ontology / identity (§3 in architecture doc)

| Module | Public surface | Status |
|---|---|---|
| `trial_ontology.py` | `parse_condition`, `build_trial_ontology`, `PARENT_SEQUENCES`, `CONDITION_CODES`, `CONDITION_ONTOLOGY` | live, canonical parser, raises on bad input |
| `omission_identity.py` | `OMISSION_IDENTITY_CONDITIONS`, `LFP_BANDS`, `build_noise_controlled_spike_matrix(_with_subblocks)`, `decode_omission_identity_slot` **(quarantined, `invalid_for_inference`)**, `decode_omission_identity_full` **(quarantined)**, `detect_trial_cycles`, `assign_subblock_quartiles`, `decode_identity_cycle_deconfound` (corrected, live), `shuffle_r2_ci`, `decode_time_from_features` | mixed: two functions self-flagged invalid, rest live |
| `structured_identity.py` | `build_canonical_trial_table`, `assign_outer_folds`, `build_inner_validation_partitions`, `build_representation_ladder`, `build_permutation_plan`, `build_milestone_receipt`, `TRAINING_AUTHORIZED=False` | Milestone 1, no fitting, hard-gated |
| `structured_identity_m2a.py` | `OuterFold`, `extract_rate_raster`, `representation_pair`, `build_outer_folds`, `fit_nested_linear`, `null_metric_distribution`, `permute_reversal_labels`, `permute_positive_labels`, `WINDOWS_MS`, `LABEL_TO_INT`, `BIN_SIZE_MS`, `C_GRID` | Milestone 2A, live, approved linear baseline only |
| `metadata.py` | `get_all_units_metadata`, `classify_unit_quality`, `unit_census_report`, `get_snr_analysis`, `electrode_inventory` | live; docstring vs. code mismatch on `cluster_id` column (metadata.py:44 vs :178-180) |
| `diagnostics.py` | `audit_session`, `compare_sessions`, `print_audit_report` | live |
| `ontology.py` | `Provenance`, `Lineage`, `Query`, `Alignment`, `Dataset`, `AlignedDataset`, `EpochCollection`, `Question`, `Result`, `Interpretation`, `Figure` (dataclasses) + `create_dataset_from_query`, `create_aligned_dataset`, `create_epochs`, `create_result`, `create_figure` | labeled "v1.0.0 PUBLIC API FROZEN" in `__init__.py`; **zero confirmed `scripts/` consumers**; several methods raise `NotImplementedError` by design |
| `factories.py` | `dataset_from_session`, `aligned_dataset_from_dataset`, `epochs_from_aligned_dataset`, `result_from_psth_analysis`, `result_from_tfr_analysis`, `result_from_decoding_analysis`, `result_from_spike_lfp_correlation_analysis`, `figure_from_result`, `visualize_spike_lfp_correlation` | the only concrete instantiator of `ontology.py`'s dataclasses; **zero confirmed `scripts/` consumers**, only `tests/test_factories.py` |
| `sequence_layout.py` | `BANDS_7`, `parse_probe_areas`, `normalize_area_name`, `channel_slice_for_area`, `AREA_ALIASES`, `V3_DUAL_PAIR`, `FULL_SEQUENCE_START_MS/END_MS/DURATION_MS` | live; `channel_slice_for_area`'s >2-area branch is an unweighted "legacy fallback" |

## Signal processing

| Module | Public surface | Notes |
|---|---|---|
| `analog.py` | `EpochBatch` (dataclass), `load_analog_epochs`, `load_lfp_epochs`, `load_muae_epochs` | hard LFP/MUAe split at the h5py-key level; no SPK access here |
| `spectral.py` | `to_db`, `harmonic_analysis`, `cross_area_coherence`, `spectral_tilt`, `band_power`, `imaginary_coherency`, `bipolar_reference`, `laplacian_reference` | single canonical `10·log10` point; empty-input → zero/NaN dict pattern pervasive |
| `connectivity.py` | `granger`, `granger_spectral`, `phase_slope_index`, `transfer_entropy`, `granger_causality` (legacy dict-return, parallel implementation), `directed_connectivity`, `directed_network`, `network_topology`, `bin_spikes`, `as_trials`, `CANONICAL_BANDS`, `spike_mutual_information`, `binary_occupancy_mutual_information`, `spike_count_mutual_information` | deliberately signal-class-agnostic estimator layer; `CANONICAL_BANDS` disagrees numerically with `sequence_layout.BANDS_7` |
| `spiking.py` | `compute_response_metrics`, `classify_response_significance`, `classify_omission_response`, `phase_locking_index` | pure numeric, no identity/addressing logic, all times in seconds |
| `unit_classification.py` | `classify_unit`, `_assign_labels` (S+/S-/O+/O++), `assign_o_plusplus_from_template_table` (a **second, independently-thresholded O++ definition** — naming collision, not the same computation), `ClassificationConfig`, `OPlusPlusTemplateConfig`, `stimulus_present_events`, `omission_events`, `precompute_condition_onsets`, `classify_all_nwbs` | canonical response-class assignment; per-file `except Exception: continue` in the batch driver with no aggregate failure count returned |
| `artifact_repair.py` **(untracked)** | `flagged_to_intervals`, `interpolate_intervals`, `repair_lfp_trials`, `repair_band_artifacts`, `Z_THRESH=6.0`, `DEFAULT_BANDS` | canonical artifact-repair home per its own docstring, consolidating 3 prior duplicate implementations; `repair_band_artifacts`'s `n_trials<5` skip returns unmodified input + an **empty** dict with no diagnostics (contrast: `repair_lfp_trials`'s equivalent skip populates a `skipped_reason`) |
| `onset_fitting.py` **(untracked)** | `causal_exp_smooth`, `onset_model`, `fit_exponential_onset`, `DEFAULT_TAU_MS=30.0` | pure array in/dict out, no session dependency, raises on malformed input |
| `tfr_accumulator.py` | `TFRAccumulator` (Welford online mean/var + complex accumulation for ITC/evoked power), `assert_mergeable` | `mag==0` samples silently contribute 0 to `sum_unit_z` rather than being excluded/flagged (phase-undefined edge case) |

## Statistics / decoding / similarity

| Module | Public surface | Notes |
|---|---|---|
| `statistics.py` | `clopper_pearson`, `StatisticalAnalysis.{compare_groups, compare_multiple_groups, correlate, bootstrap_ci, permutation_test, fdr_correct}`, `exploratory_compare/correlate/multi`, `confirmatory_compare` | layered exploratory/confirmatory/legacy API; `correlate`'s `n<3` branch returns a structurally different error-dict shape than its success path — inconsistent return type |
| `decoding.py` | `build_spike_count_matrix`, `decode_stimulus_identity`, `decode_omission_presence` | fixed seed 42 throughout, not caller-configurable; `device="cuda"` accepted but always falls back to CPU nested-CV with a logged message (not silent) |
| `permutation.py` | `permute_labels(y, *, groups=None, scheme, rng)` | cleanest file in the package against the fallback-value pattern — every malformed input raises; built specifically to fix a prior audit-flagged exchangeability bug |
| `jrsa.py` | `jrsa()` (unified RSA/similarity dispatcher, 14 metrics), `JRSAResult` | **`_pearson`/`_spearman` fabricate a literal `(r=0, p=1.0)` on internal computation failure** (jrsa.py:1040, 1086) rather than raising/NaN — flagged as the clearest "no silent synthetic values" violation found in this layer; **`_procrustes`** similarly fabricates `disparity=1.0` on any exception (jrsa.py:1273); CuPy-path permutation/bootstrap RNG is **not seeded from the caller's `random_state`** (jrsa.py:725, 784) — GPU results not reproducible the way CPU results are |
| `bilinear.py` | `BilinearLogisticRegression` (rank-K bilinear logistic regression, sklearn-style estimator) | no session/file dependency, pure array API |
| `nam.py` | `LaminarNAM` (per-unit-interpretable neural additive model), `unit_importance`, `predict`, `train_nam` | requires torch unconditionally, no CPU/GPU availability check — will raise from inside torch if CUDA requested without CUDA present, not a graceful degrade |
| `gpu_pca.py` | `gpu_pca` | standalone GPU/CPU-fallback PCA; silently runs on CPU-via-torch if CUDA unavailable with no log (contrast: the further `except Exception → NumPy SVD` fallback **is** logged) |
| `trajectory.py` | `build_time_resolved_matrix`, `compute_population_trajectory` | imports `gpu_pca.gpu_pca` but never calls it — reimplements SVD inline instead (unconfirmed why) |

## Analyzers / functions / reporting (delegated, full reads)

| Module | Public surface | Notes |
|---|---|---|
| `analyzers.py` | `TFRAnalyzer` (static-method namespace: `extract_band`, `average_across_channels`, `trial_average`, `compare_conditions`, `by_layer`, `correlate_areas`), `UnitAnalyzer` (`raster`, `psth`, `autocorrelogram`, `quality_metrics`), `PopulationAnalyzer` (`compare_criteria`, `distribution_by_area`, `pie_chart_data`, `network_connectivity`, `population_trajectory`) | **all three are pure static-method namespaces, no instance state**; `average_across_channels`'s changelog (analyzers.py:7) claims a "hard error on channel-count mismatch" that the code (analyzers.py:97-99) does not actually implement — still silently falls back to a global average; `_acg_pearson` is a bare alias to `_acg_vectorized`, not a Pearson computation despite the name |
| `functions.py` | The "20 canonical functions" — full list in architecture §7. Two functions accept a dead/unused parameter (`pie_charts(..., by_layer=...)` never passed through; `summary_report(..., output_dir=...)` never referenced) | `unit_quality_scores` substitutes hardcoded `waveform_duration=300.0µs`/`firing_rate=1.0Hz` for missing/NaN metadata with **no flag in the output** distinguishing measured from assumed (functions.py:459-467) — direct tripwire-1 tension; `summary_report` reports `0` (not NaN) when a metric column is absent (functions.py:724-726) |
| `permutation.py` | see above | |
| `report.py` | `generate_notebook_json`, `compute_psd`, `fdr_correct`, `apply_madelane_style`, `generate_report` | **four report sections run real stats on `np.random`-generated synthetic data**, badged only with a non-conforming orange pill instead of the mandated red title — see architecture §9; one section (identity decoding) is genuinely computed and correctly badged, proving the gap is inconsistency, not incapability |
| `compression.py` | `compact`, `convert`, `verify_roundtrip`, `compress_fp32` | file-to-file NWB fp32 compression; deliberately raises loudly (`KeyError`) rather than skipping on unrecognized HDF5 structure — cleanest failure-behavior file in the signal-adjacent layer per its own stated design philosophy |
| `visual_qc.py` | `plot_unit_waveforms`, `plot_unit_quality_distribution`, `plot_noise_vs_signal`, `compare_session_quality` | pure plotting layer on already-extracted tabular data; several silent `.get(col, [])`/`errors='coerce'` fallbacks that discard missing/malformed data with no caller-visible signal |

## Dead / legacy

| Module | Status |
|---|---|
| `_unused/complex_tfr.py` | **live** — imported by `tests/test_tfr_complex.py`; moved verbatim from `jnwb/complex_tfr.py`, git-move incomplete (staged add, unstaged delete) |
| `_unused/markdown_report.py` | **dead** — zero test coverage, zero script consumer found |
| `mcp_server/` (5 files) | not deep-audited; contains an `add_tool` (`mcp_server/meta_tools.py:8`, delegated) that writes arbitrary user-supplied Python source to disk when `ALLOW_DYNAMIC_TOOLS=1` — gated off by default, worth knowing about, not evaluated for current use |

## Not independently verified this pass

- `viz.py` (imported ~4-5× in the frequency table but not deep-read by any agent this session)
- `jnwb/__init__.py`'s full re-export surface (referenced by multiple sub-agents, not read end-to-end by this document's author)
- `jnwb/mcp_server/` beyond the one `add_tool` finding above
