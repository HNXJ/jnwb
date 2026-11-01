# Changelog

All notable changes to `jnwb` will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases 0.2.10, 0.2.9, 0.2.8, 0.2.7, 0.2.6.1, 0.2.6, 0.2.5, 0.2.4, 0.1.8 and 0.1.7 to 0.1.0 are archived, verbatim, in [artifacts/archive/changelog_0.1.0-0.2.9.md](artifacts/archive/changelog_0.1.0-0.2.9.md).

## [Unreleased]

## [0.2.15] - 2026-10-31

### Breaking

- `jnwb/analyzers.py`, `jnwb/trajectory.py`: `psth`, `raster` and the trajectory builders require their window.
- `resolve_nwb_path` raises `FileNotFoundError` naming each probe; `suffixes=` sets the order (`jnwb/paths.py`).

### Added

- `jnwb/analyzers.py`, `jnwb/trajectory.py`: `label="right"` labels a bin (t - w, t] at t.
- Distance-binned coherence normalization (`docs/common_mistakes.md` 13, `tests/test_connectivity_pitfalls.py`).
- `jnwb.edges_near_events` (`jnwb/nwb_events.py`): nearest rising and falling edge to each event, with lags.
- `effective_rate`: exact-repeat fraction, repeat runs and power above rate/4 of a stream (`jnwb/continuous.py`).
- `gaze_departure_onsets`: per-trial gaze departure from a percentile envelope (`jnwb/continuous.py`).
- `sha256_groups`: a SHA-256 over the datasets under named HDF5 groups (`jnwb/paths.py`).
- `signal_class=` on `granger_causality`, `directed_network`, `imaginary_coherency`; omitted, warns (`jnwb/_units.py`).
- `units_table`: one row per unit with probe, area, depth class and waveform columns (`jnwb/metadata.py`).

### Changed

- `correlate_areas` reads band-power correlation, not synchrony (`tests/test_claim_vocabulary_prose.py`).
- DataFrame, metadata and gap-handling functions read NaN as missing and refuse inf (`tests/test_nonfinite_inputs.py`).
- NaN or inf in an array-math input raises `ValueError` naming the argument (`tests/test_nonfinite_inputs.py`).
- `nwb_read_io` refuses a mode other than `"r"` or a non-finite path at call, before `with` (`jnwb/nwb_io.py`).
- Each showcase replication card shows paper, library and methods verdicts (`scripts/build_dashboard.py`).

### Deprecated

- `jnwb/spiking.py`, `jnwb/statistics/_firing.py`: a positional window warns; pass it by keyword.

### Fixed

- `enrich_units_dataframe` warns a probe collision through its unread reasons (`jnwb/addressing.py`).
- `jnwb/addressing.py` resolves a peak channel through `units.electrodes` and `hardware_channel`, not `id`.

## [0.2.14] - 2026-10-27

### Added

- `curate_and_label` gains `xflip_n_blocks`, sent to `xflip` as `n_blocks` (tests/test_laminar_curation.py).
- `ExecutionRecord` and a four-function result cache (`jnwb/execution.py`).
- `cache_key`: a hex key over the operation name, inputs, parameters and jnwb version (`jnwb/execution.py`).
- `cache_store`: saves an array, scalar, dict, list or tuple as an `.npz` archive, atomically (`execution.py`).
- `cache_load`: the value under a key, or None on a miss or a stale entry (`jnwb/execution.py`).
- `cache_clear`: removes the entries `cache_store` wrote and returns their count (`jnwb/execution.py`).
- `docs/execution.md`: run records and the result cache, with signatures and staleness rules.
- `noise_correlation(counts, condition_id, *, min_trials)`: trial-based noise correlation (`jnwb/spiking.py`).
- `NWBMutationError`: the base error for a refused NWB mutation; it carries the report `issues` (`nwb_write.py`).
- `NWBVerificationError`: a written file failed its post-write `verify_nwb`; the file stays (`nwb_write.py`).
- `UnidentifiableRepairError`: a repair's identifiability precondition fails; nothing is written (`nwb_write.py`).
- `AmbiguousMappingError`, `UndeclaredUnitError`: reserved; no function raises them yet (`nwb_write.py`).
- `granger_nonparametric`: Welch and Wilson factorization, no VAR order (`jnwb/connectivity/_granger.py`).
- `granger_time_reversed`: the net direction's sign flip under time reversal (`jnwb/connectivity/_granger.py`).
- `partial_coherence`: coherence given one conditioning signal, circular-shift p (`jnwb/spectral/_coupling.py`).
- `coherence_bias_floor`: trial-pairing bias floor for coherence (`jnwb/spectral/_coupling.py`).
- `preflight(question, input_path=None)`: outcomes name the input by sha256 and path (`jnwb/ontology.py`).
- `repair_nwb`: writes the read path's in-memory repairs to a copy, refusing any it cannot identify (`nwb_write.py`).
- `transform_nwb`: copies an NWB file with declared keep, drop, cast and compression changes (`jnwb/nwb_write.py`).
- `screen_units_against_labels`: per-session held-out agreement with curator labels (`jnwb/unit_quality.py`).
- `verify_nwb`: re-reads one written NWB file and checks it (`jnwb/nwb_write.py`).
- `write_nwb`: writes a caller-built NWB file after schema validation (`jnwb/nwb_write.py`).

### Changed

- `UnitAnalyzer.autocorrelogram` refuses NaN or infinite spike times, naming the count (`analyzers.py`).
- `TFRAnalyzer.extract_band` refuses an empty `band_defs`; `None` keeps the default bands (`analyzers.py`).
- `artifact_detection` scores a zero-MAD outlier by the mean absolute deviation, not z 0 (`jnwb/artifact_detection.py`).
- `cache_key` separates tuples from lists, int dict keys from str keys, NumPy scalars from Python (`jnwb/execution.py`).
- `cache_store` refuses a NumPy scalar or a non-str dict key; a 0-d array stores instead (`jnwb/execution.py`).
- `cache_store` refuses an int beyond int64, bytes with a NUL byte, a str ending in NUL (`jnwb/execution.py`).
- `cache_load` returns a 0-d array stored as one, not a Python scalar (`jnwb/execution.py`).
- `cache_store` retries a rename another process briefly holds, then raises, leaving no temp file (`jnwb/execution.py`).
- `cluster_permutation_test` reports `scheme='global'` for `paired=True`, groups or not (`jnwb/statistics/_cluster.py`).
- `compress_fp32` refuses a `dst` that resolves to `src`; the source is never modified (`jnwb/compression.py`).
- `epoch_continuous` takes `start_s`, the time of sample 0; default `0.0` keeps current output (`jnwb/continuous.py`).
- Event `codes=` refuses bytes and bool values with TypeError; str and int codes are unchanged (`jnwb/nwb_events.py`).
- `permutation_test` results gain `scheme`, always `'global'` (`jnwb/statistics/_analysis.py`).
- `shuffle_r2_ci` gains `scheme`: `'within_group'` with `groups`, else `'global'` (`jnwb/statistics/_regression.py`).
- `cross_modal_comparison` gains `surrogate_scheme`, `'circular_shift'` when drawn (`jnwb/statistics/_regression.py`).
- `cross_area_coherence` gains `surrogate_scheme`, `'circular_shift'` (`jnwb/spectral/_coupling.py`).
- `cluster_permutation_test` results gain `scheme` and `surrogate_seed_entropy` (`jnwb/statistics/_cluster.py`).
- `paired_fire_prob_test` results gain `scheme`, always `'sign_flip'` (`jnwb/statistics/_firing.py`).
- `paired_fire_prob_test` results gain `surrogate_seed_entropy` (`jnwb/statistics/_firing.py`).
- `permutation_test` and `bootstrap_ci` results gain `surrogate_seed_entropy` (`jnwb/statistics/_analysis.py`).
- `compare_groups` results gain `surrogate_seed_entropy` (`jnwb/statistics/_analysis.py`).
- `shuffle_r2_ci` results gain `surrogate_seed_entropy` (`jnwb/statistics/_regression.py`).
- `partial_coherence` gains `surrogate_scheme`, `'circular_shift'` (`jnwb/spectral/_coupling.py`).
- `granger` records the `order='auto'` cap in `params['order_cap']`, warning when below `max_lag` (`_granger.py`).
- `granger` refuses `max_lag` below 1 with `ValueError` instead of running order 1 (`_granger.py`).
- `jrsa` corrects only finite p-values: a NaN p no longer makes other q NaN or counts in m (`jnwb/jrsa/_inference.py`).
- `classify_layer_from_depth` raises ValueError on unknown `depth_unit` or negative `threshold` (`jnwb/addressing.py`).
- `classify_layer_from_depth` takes a declared `depth_axis` and `shallow_end`, per probe (`jnwb/addressing.py`).
- `FilteredEphys` under `processing/` is read by its container or series name (`jnwb/nwb_inspect.py`).
- A lone `FilteredEphys` under `processing/` is also chosen when the name is omitted (`jnwb/nwb_inspect.py`).
- Behavior containers under `processing/` are read by bare and `module/container` name (`jnwb/nwb_inspect.py`).
- Types: `EyeTracking`, `PupilTracking`, `Position`, `CompassDirection`, `BehavioralTimeSeries` (`nwb_inspect.py`).
- An empty container is refused by name, as `holds no electrical series` or `holds no series` (`nwb_inspect.py`).
- An empty processing `LFP` or `FilteredEphys` is listed as available and refused by that name (`nwb_inspect.py`).
- An empty behavior container is refused by name and is not chosen when the name is omitted (`nwb_inspect.py`).
- A series with `timestamps` and no `rate` is refused by name: `has no constant sampling rate` (`nwb_inspect.py`).
- Processing `BehavioralEvents` and `BehavioralEpochs` are refused the same way (`nwb_inspect.py`).
- A `rate` that is not finite and positive (inf, nan, zero, negative) is refused by name (`nwb_inspect.py`).
- The message gives the rate: `not a finite positive rate` (`nwb_inspect.py`).
- A bare name shared by a container and a series raises `AmbiguousAcquisitionError` (`nwb_inspect.py`).
- Pass the qualified name, such as `behavior/Eye` or `ecephys/probe/Eye` (`jnwb/nwb_inspect.py`).
- Two containers of one name in different processing modules raise `AmbiguousAcquisitionError` (`nwb_inspect.py`).
- Both the bare name and an omitted name are refused, where one was picked silently before (`nwb_inspect.py`).
- Pass the module-qualified name, such as `probe0/LFP` (`nwb_inspect.py`).
- The unit warning from `acquisition_channel` names `channel_conversion` and the channel (`nwb_inspect.py`).
- The unit and `starting_time` warnings point at the caller's line, not at jnwb's own code (`nwb_inspect.py`).
- `stream_npz_array` raises `TypeError` for `None` on a 0-d array, where it returned the scalar (`jnwb/io.py`).
- `...` on a 0-d array still returns the 0-d array, as NumPy does (`jnwb/io.py`).
- The MCP signal reference names no reader for a rate that is not finite and positive (`nwb_tools.py`).
- It also names no reader for a `channel_conversion` on a type other than `ElectricalSeries` (`nwb_tools.py`).
- `access_hint` says why in both cases (`nwb_tools.py`).
- A container that wraps its series is labelled `wrapped` by `inspect`, not `direct` (`jnwb/nwb_inspect.py`).
- A `session_description` stored as a group raises `MissingRequiredNWBFieldError`, not `ValueError` (`jnwb/nwb_io.py`).
- A series with `timestamps` and no `rate` says it stores no constant rate, and why (`jnwb/nwb_inspect.py`).
- A unit-scale contradiction warning opens with its own first sentence, not the type one (`jnwb/nwb_inspect.py`).
- [results change] `jnwb/statistics/_analysis.py`: bootstrap interval bounds move up to 3e-16 relative (deterministic).
- `phase_locking_index` refuses a non-finite LFP phase at a spike's sample, naming the count (`spiking.py`).
- `phase_slope_index` refuses an `nperseg` above the trial length, as `compute_psd` does (`jnwb/connectivity/_psi.py`).
- Breaking for callers reading seconds: `UnitAnalyzer.psth` returns `bin_centers_ms` in ms (`analyzers.py`).
- `repair_lfp_trials` refuses NaN or Inf `segments`, naming the count (`artifact_repair.py`).
- `repair_lfp_trials` refuses fewer than `min_trials` trials instead of returning its input (`artifact_repair.py`).
- `repair_band_artifacts` refuses fewer than 5 trials instead of returning its input (`artifact_repair.py`).
- `compute_response_metrics` refuses non-finite spike times, naming the count; they were dropped (`spiking.py`).
- A channel id that is not a number, or an unreadable depth unit, warns once per call (`jnwb/addressing.py`).
- An electrode region with no length, or an undefined-type check that cannot run, now warns (`jnwb/nwb_inspect.py`).
- A stored unit that cannot be read warns that the volts check did not run (`jnwb/nwb_inspect.py`).
- A refused series says why its file could not be read: the exception class and text (`jnwb/nwb_inspect.py`).
- `AperiodicFitResult` gains `reason`, the exception behind a failed fit, also in `to_dict()` (`jnwb/spectral/_psd.py`).
- A singular covariance in a partial correlation warns that its pseudo-inverse was used (`jnwb/laminar/_xflip.py`).
- `correlate` drops a pair with an infinite value, as with NaN; Pearson r was NaN (`jnwb/statistics/_analysis.py`).
- `compare_groups` warns with the count of non-finite values it drops from each group (`jnwb/statistics/_analysis.py`).
- `bootstrap_ci` warns with the count of non-finite values it drops (`jnwb/statistics/_analysis.py`).
- Surrogates at 7+ trials draw uniform derangements, so p-values change for a seed (`jnwb/connectivity/_common.py`).
- `TFRAccumulator.merge` raises ValueError for accumulators of different shapes (`jnwb/tfr_accumulator.py`).
- `transform_nwb` with `compression=` alone no longer raises on a scalar `starting_time` (`jnwb/nwb_write.py`).
- `verify_nwb` with `against=` compares group and root attributes, not only dataset attributes (`jnwb/nwb_write.py`).
- `plot_unit_quality_distribution` gains keyword `rng` for its by-area jitter; default unchanged (`jnwb/visual_qc.py`).
- `repair_nwb`'s `waveform_index_dtype` skips a uint8 index that already carries its VectorIndex type (`nwb_write.py`).
- Release 0.2.7 moves to artifacts/archive/changelog_0.1.0-0.2.9.md.

### Deprecated

- `UnitAnalyzer.psth` and `raster` warn when `window_ms` is omitted; required in 0.2.15 (`jnwb/analyzers.py`).
- Population trajectories warn when `time_window_ms` is omitted; required in 0.2.15 (`jnwb/trajectory.py`).

### Removed

- `gpu_pca` removed (breaking), deprecated in 0.2.13; use `compute_population_trajectory` (`jnwb/gpu_pca.py`).
- `create_aligned_dataset` removed (breaking), deprecated in 0.2.13; use `Dataset.with_alignment` (`jnwb/ontology.py`).
- `create_result` removed (breaking), deprecated in 0.2.13; use `Result` directly (`jnwb/ontology.py`).
- `create_figure` removed (breaking), deprecated in 0.2.13; use `Figure` directly (`jnwb/ontology.py`).

### Fixed

- A spectral Granger ratio with a zero denominator is NaN, not the 0 of no influence (`jnwb/connectivity/_granger.py`).

## [0.2.13] - 2026-10-20

### Added

- `docs/api.md` gains an Experimental section for `jnwb.bilinear` and `jnwb.nam`, with no stability promise.
- `build_permutation_plan(blocks=)` permutes one label per block among each group's blocks (`jnwb/permutation.py`).
- `exploratory_compare` and `confirmatory_compare` take `rng` for the bootstrap CI (`jnwb/statistics/_analysis.py`).
- Export `ContainerTypeContradictionWarning`, which `inspect` raises on a contradicted type (`jnwb/__init__.py`).
- `curate_and_label` reports vFLIP2 and its anchor distance; it never anchors (`jnwb/laminar_curation.py`).
- `effective_sample_size(x)`: effective sample count of autocorrelated data (`jnwb/statistics/_autocorrelation.py`).
- `fuse_laminar_anchors` reports `agreement` and `separation_contacts` (`jnwb/laminar_curation.py`).
- `jrsa(sliding=True)` runs every window in one call, with a family-wise `q` (`jnwb/jrsa/__init__.py`).
- MCP `get_event_codes_and_timings` takes `code_column=` (`jnwb/mcp_server/event_tools.py`).
- Add `synth_vflip2_crossover`, a planted vFLIP2 crossover generator (`jnwb/testing/synth.py`).
- `derive_tick_clock(tick_segments, spike_times)` and `TickClock`: acquisition ticks to seconds (`jnwb/continuous.py`).
- Add `XFlipResult.null_method` naming the surrogate null that ran (`jnwb/laminar/_xflip.py`).

### Changed

- `enrich_units_dataframe` takes `group_name` from the `group`/`probe`/`device` key column (`jnwb/addressing.py`).
- [results change] `jnwb/continuous.py`: window edges are containment bounds, not rounded to even (deterministic).
- [results change] jnwb/laminar_curation.py: `fuse_laminar_anchors` grades A as B with both landmarks (deterministic).
- `jrsa(window=w)` warns when w exceeds the axis, naming w and n; it still covers the axis (`jnwb/jrsa/_stages.py`).
- The warning for `standardize=True` with `normalize=True` now states the [0, 1] output (`jnwb/jrsa/_stages.py`).
- `plot_opposing_gradients` alpha/beta legend reads 8–30 Hz, the vFLIP low band (`jnwb/vis/laminar.py`).
- `plot_opposing_gradients` gains `gamma_band` and `alphabeta_band` in Hz (`jnwb/vis/laminar.py`).
- Two-sided permutation p is twice the smaller tail, capped at 1, for every metric (`jnwb/permutation.py`).
- `phase_slope_index` refuses a `noverlap` outside [0, nperseg) instead of clipping it (`jnwb/connectivity/_psi.py`).
- `docs/references.md` gains core texts and studies jnwb reproduces, each marked replicated or partially replicated.
- `plot_rsm_heatmap` defaults to the title "Representational Dissimilarity Matrix (RDM)" (`jnwb/vis/state_space.py`).
- Releases 0.2.6.1 and 0.2.6 move to artifacts/archive/changelog_0.1.0-0.2.9.md.

### Deprecated

- `gpu_pca` is deprecated in 0.2.13 and removed in 0.2.14; use `compute_population_trajectory` (`jnwb/gpu_pca.py`).
- `create_aligned_dataset`, `create_result` and `create_figure` will be removed in 0.2.14 (`jnwb/ontology.py`).

### Removed

- `jrsa(align_mode=...)` is removed, as announced in 0.2.11; passing it raises `TypeError` (`jnwb/jrsa/__init__.py`).
- jnwb/paths.py: the deprecated OMISSION_*_DIR environment variables and LEGACY_ENV_* constants; set JNWB_*_DIR.

### Fixed

- A fractional channel id such as 2.7 is refused, not truncated to channel 2 (`jnwb/addressing.py`).
- Multi-area labels are refused without a `group_name`, `group`, `probe` or `device` column (`jnwb/addressing.py`).
- A multi-area contact with no probe key is refused, not given the first listed area (`jnwb/addressing.py`).
- `enrich_units_dataframe` keeps text unit ids such as 'u1' instead of making them NaN (`jnwb/addressing.py`).
- `aperiodic_fit` gives a NaN `r_squared` for a spectrum flat to round-off (`jnwb/spectral/_psd.py`).
- `audit_electrodes` counts each contact's area by the addressing rule (`jnwb/metadata.py`).
- `detect_bad_channels` no longer flags a whole short probe for one dead contact (`jnwb/laminar_curation.py`).
- `cluster_permutation_test` refuses a NaN or infinite `threshold` (`jnwb/statistics/_cluster.py`).
- `coef_rows` keeps every fixed effect and drops every random-effect variance (`jnwb/statistics/_regression.py`).
- compress_fp32 repairs references under soft links; dangling ones are dropped with a warning (`jnwb/compression.py`).
- `compress_fp32` casts a hard-linked dataset once, and every hard-link name opens it (`jnwb/compression.py`).
- `evoked_csd_sink` returns NaN on a flat baseline instead of z-scoring by 1.0 (`jnwb/laminar_curation.py`).
- `paired_fire_prob_test` gives a NaN shuffle p for fewer than 2 trials, not 1.0 (`jnwb/statistics/_firing.py`).
- `flagged_to_intervals` returns `[]` for an empty input instead of raising `IndexError` (`jnwb/artifact_repair.py`).
- Deprecated `granger_causality` reports NaN, not 0.0, for a zero residual variance (`jnwb/connectivity/_granger.py`).
- `granger` refuses a NaN or infinite `ridge` (`jnwb/connectivity/_granger.py`).
- `inspect` warns on a `neurodata_type` no namespace defines; the read refusal says why (`jnwb/nwb_inspect.py`).
- `jrsa` refuses complex x1 or x2 instead of dropping the imaginary part (`jnwb/jrsa/_backends.py`).
- Sliding-window family-wise p counts +inf and -inf null draws and drops only NaN (`jnwb/jrsa/_inference.py`).
- `jrsa(window=w)` refuses w below 1 instead of analysing an empty window (`jnwb/jrsa/_stages.py`).
- `jrsa(window=w)` keeps exactly w samples; an odd width was one short and window=1 was empty (`jnwb/jrsa/_stages.py`).
- Paired metric helpers refuse unequal rows; procrustes also refuses unequal features (`jnwb/jrsa/_metrics.py`).
- `jrsa` permutation p leaves NaN draws out of n and refuses an all-NaN null (`jnwb/jrsa/_inference.py`).
- `jrsa` pearson and spearman t is +-inf at |r| = 1, not a large finite value (`jnwb/jrsa/_metrics.py`).
- `label_layers` refuses a non-finite `nominal_pitch`, which labelled every contact 'deep' (`jnwb/laminar/_labels.py`).
- `phase_locking_index` refuses non-increasing `lfp_timestamps` instead of dropping every spike (`jnwb/spiking.py`).
- `get_snr_analysis` and `get_all_units_metadata` refuse a NaN or infinite cut-off (`jnwb/metadata.py`).
- `compute_multitaper_psd` refuses a non-finite `fs` (`jnwb/spectral/_psd.py`).
- `plot_noise_vs_signal` raises a `ValueError` naming each absent column it needs (`jnwb/visual_qc.py`).
- NaN trial starts and epoch onsets are refused, not counted as zero spikes (`jnwb/_bins.py`).
- `/intervals/<table>/<column>` is refused under its full name, not read as table `<column>` (`jnwb/nwb_events.py`).
- `old_new_summary_table` counts units with a missing area or tier instead of dropping them (`jnwb/metadata.py`).
- `interpolate_intervals` no longer skips a one-sample interval at an array edge (`jnwb/artifact_repair.py`).
- `fit_exponential_onset` accepts a `min_amplitude` above the rise; start guesses are clipped (`jnwb/onset_fitting.py`).
- `epoch_continuous` refuses a bad `onset_unit` or `boundary_policy` even when `onsets` is empty (`jnwb/continuous.py`).
- `plot_opposing_gradients` ends its crossover line at a finite x when a trace holds NaN (`jnwb/vis/laminar.py`).
- `permute_labels` and `build_permutation_plan` refuse a NaN or None group id (`jnwb/permutation.py`).
- The 1-D CSD functions refuse a NaN or infinite `pitch_um` or `conductivity_s_per_m` (`jnwb/spectral/_reference.py`).
- `refractory_contamination` returns NaN with a reason for one or two spikes, not 0.0 (`jnwb/unit_quality.py`).
- The Monte Carlo two-sided `p_floor` of `exact_sign_flip` is 2 / (n_mc + 1) (`jnwb/statistics/_tests.py`).
- `compare_groups`, `compare_multiple_groups` and `bootstrap_ci` exclude Inf like NaN (`jnwb/statistics/_analysis.py`).
- `assign_subblock_quartiles` refuses a NaN start_time instead of the last quartile (`jnwb/statistics/_trials.py`).
- Surrogate p-values count only non-NaN draws; an all-NaN null is refused (`jnwb/connectivity/_common.py`).
- `synth_periodic_response` refuses a NaN `freq_hz` (`jnwb/testing/synth.py`).
- `transfer_entropy` refuses unknown `bias_correction` values (`jnwb/connectivity/_transfer_entropy.py`).
- Units column names stored as bytes read as the same names as str, not as duplicates (`jnwb/nwb_io.py`).
- `vflip2_from_lfp` refuses trials too short for 1 Hz bins and names the minimum length (`jnwb/laminar/_vflip2.py`).
- `vflip2_from_lfp` refuses `fs` below 300 Hz, where 150 Hz lies above Nyquist (`jnwb/laminar/_vflip2.py`).
- `vflip2` refuses `contact_spacing` above 200 um, where no window was searched (`jnwb/laminar/_vflip2.py`).
- `jnwb/vis/laminar.py`: `plot_csd` sets its colour range from finite values; an all-non-finite matrix raises.
- `jnwb/vis/state_space.py`: `plot_decoding_timecourse` labels cluster bars "cluster", not "p < 0.05".
- `jnwb/vis/laminar.py`: a depth marker outside the depth range now warns; nothing is drawn for it, as before.
- `jnwb/vis/hierarchy.py`: a fractional rank keeps its value in the tick label; rank 0.5 was labelled '0'.
- `jnwb/vis/hierarchy.py`: NaN points leave the fit with a warning; a CI missing its value is drawn from its bounds.
- `jnwb/vis/hierarchy.py`: the statistic note sits above the drawn data, including when every interval is negative.
- `jnwb/vis/laminar.py`: `plot_opposing_gradients` and `plot_csd` refuse data shaped unlike their depth or time axes.
- `jnwb/vis/laminar.py`: `plot_spectrolaminar_map` refuses a square `rel_power`, which does not state its layout.
- `jnwb/vis/spectral.py`: the modulation colour range ignores NaN; Granger and significance-mask shapes are checked.
- `jnwb/vis/laminar.py`: opposing-gradient intervals must hold one [lower, upper] pair per depth, or ValueError.
- `jnwb/vis/state_space.py`: an RSM matrix must match its condition labels; a mismatch raises ValueError.
- `jnwb/vis/sidecar.py`: a string `SOURCE ARTIFACTS` is one path, not one entry per character.
- `jnwb/vis/spectral.py`: a NaN cell in `sig_mask` raises ValueError; it was cast to True and marked.
- `jnwb/vis/spiking.py`: a time axis of the wrong length, or more conditions than default colours, raises ValueError.
- `jnwb/vis/sidecar.py`: an empty SOURCE ARTIFACTS entry, such as an empty string, raises ValueError.
- `jnwb/vis/spectral.py`: `plot_spectral_modulation_matrix` refuses a matrix not shaped (areas, bands).
- `check_waveform_blocks` gives a finite `best_dev` when one block row is NaN (`jnwb/nwb_integrity.py`).
- `xflip` refuses a NaN, infinite or non-integer `n_surrogates` (`jnwb/laminar/_xflip.py`).

## [0.2.12] - 2026-10-14

### Added

- A non-blocking CI job runs the suite on pandas 3; docs/install.md gives the install step for it.
- `causal_gaussian_smooth` returns a causal smooth and its kernel's mean lag in bins; tests/test_onset_fitting.py
- `fuse_laminar_anchors` takes `vflip2_um` and anchors on it before `vflip_um`; `jnwb/laminar_curation.py`.
- `fuse_laminar_anchors`'s `distance_um` gains `vflip` and `vflip2`; `tests/test_laminar_curation.py`.
- scripts/figures/generate_figures.py: figures of a cluster permutation test, spectral Granger and narrowband PSI trap
- The jnwb-laminar skill routes the laminar rows of jnwb-lfp-spectral; skills/jnwb-laminar/SKILL.md (pull request #31)
- `map_peak_channel_to_layer` gives each unit its peak channel's curated layer; tests/test_laminar_curation.py
- docs/references.md: 28 more routed methods cite their published source; each docstring cites the same DOI
- scripts/figures/generate_figures.py: figures of RDMs with a windowed jRSA trace, and bad channel and trial detection
- scripts/figures/generate_figures.py: figures of Welch and multitaper PSDs, zero-lag coherence and vFLIP profiles
- scripts/figures/generate_figures.py: figures of a smoothed rate step, causal against Gaussian, and spike phase locking
- The dashboard's OpenScope GLO tab: one card per work, its replications as rows; scripts/build_dashboard.py
- scripts/figures/generate_figures.py: fig21, the open-data PSTH by layer and 50 to 80 Hz power by depth
- `vflip2_from_lfp` runs `vflip2` on LFP with vFLIP2.m's raw and raw_cut PSD; tests/test_vflip2_from_lfp.py
- `jnwb/laminar/_vflip2.py`: `vflip2`, a port of vFLIP2.m (Major et al. 2025); omega matches MATLAB
- `xflip` takes `layer4_thickness_mm`, the layer 4 default for `min_block_size` (`jnwb/laminar/_xflip.py`).
- `xflip` takes `window=`, an accepted `VFlip2Result` or a row pair; it reports probe rows; tests/test_xflip_window.py
- `xflip`'s `contact_spacing` (um) adds `boundaries_um` from row 0; tests/test_xflip_window.py
- `xflip`'s `min_block_size` defaults to None: 2, or the layer 4 thickness in contacts; jnwb/laminar/_xflip.py
- `xflip` names a window outside the probe by its sorted rows; `tests/test_xflip_window.py`.
- `zflip` takes `window=` and an accepted `VFlip2Result` as `orientation`; `tests/test_zflip_window.py`.
- `zflip` refuses two different `VFlip2Result`s as `window` and `orientation`; `tests/test_zflip_window.py`.

### Changed

- docs/architecture.md drops its claim that no synthetic value enters the library.
- Gate 14 also reads CHANGELOG.md: no process terms, six kind headings, one named file per entry line.
- docs/install.md: the extras table lists `validate`, the NWB Inspector and DANDI layers of `jnwb.validate_nwb`
- docs/laminar.md: a `vflip2` section (bands, omega and its cut, rows, the LFP path, xflip and zflip hand-off).
- scripts/smoke_installed.py: STEP 7 runs it as CI does; actions SHA-pinned; peak memory has a threshold
- `gpu_pca` and `compute_population_trajectory` share one NumPy SVD fallback; jnwb/gpu_pca.py
- Private helpers that shared a name now state their rule; tests/test_helper_rule_names.py
- scripts/release_gate.py: index-hidden edits count; publication jobs refuse continue-on-error; 0e takes a concluded run
- scripts/release_gate.py: condition 6 refuses twine and reusable publication jobs; examples/, data/ never ship
- Releases 0.2.9, 0.2.8, 0.2.5, 0.2.4 and 0.1.8 to 0.1.0 move to artifacts/archive/changelog_0.1.0-0.2.9.md.
- `scripts/release_gate.py` step 8 checks that the tutorials import the built wheel.
- scripts/stack_parse.py: gates 15, 17 and STEP 0a share one stack reader; HTML and deep headings read.
- skills/jnwb-qc/SKILL.md moves routing rows to references/ pages.
- skills/jnwb-lfp-spectral/SKILL.md moves routing rows to references/ pages.
- skills/jnwb-nwb-data/SKILL.md moves routing rows to references/ pages.
- skills/jnwb-laminar/SKILL.md moves routing rows to references/ pages.
- jnwb/laminar/_vflip.py: `vflip` no longer calls its support score Omega, the name of vFLIP2's statistic
- [results change] jnwb/laminar/_xflip.py: `xflip` defaults to a homogeneous null; p-values move at a fixed int seed.
- [results change] jnwb/laminar_curation.py: `curate_and_label`'s xFLIP p-values follow that null at a fixed int seed.
- jnwb/laminar/_xflip.py: `surrogate_method='autocorr_preserving'` keeps the old independent-channel null.
- jnwb/laminar/_xflip.py: `n_samples` gives a matrix the homogeneous null; without it, a warning.

### Deprecated

- `StatisticalAnalysis.clopper_pearson_ci` warns; use `clopper_pearson`. tests/test_deprecated_aliases.py
- The two spike MI aliases warn; use `spike_mutual_information`. tests/test_deprecated_aliases.py

### Fixed

- jnwb/onset_fitting.py: causal_exp_smooth refuses non-positive bin_ms and non-1-D rate
- `check_waveform_blocks` takes `largest_row` over finite rows only; tests/test_nwb_integrity.py
- scripts/build_dashboard.py: figure, API and showcase links open their Read the Docs pages instead of a 404
- scripts/build_dashboard.py: the figure sources list docs pages as repository paths again, not Read the Docs URLs
- jnwb/spiking.py: gaussian_smooth_rate refuses a NaN or Inf sigma_ms or bin_ms by name
- jnwb/filtering.py: bandpass_filter, notch_filter and compute_multitaper_psd refuse Inf as well as NaN
- jnwb/onset_fitting.py, jnwb/laminar_curation.py: a 2-D rate and an array-like electrode id raise their own ValueError
- skills/jnwb-statistics/SKILL.md states Mann-Whitney's `statistic` as the first group's U.
- Under `value_unit="z"` a colorbar may say "z-score"; tests/test_vis_shared_rules.py

## [0.2.11] - 2026-10-11

### Added

- `jnwb.get_all_units_metadata` takes an open `NWBFile` as well as paths, and an `allow_missing=` waiver with `read_nwb`'s semantics for files missing a required field. The waivers a read used are recorded in the frame's `attrs["jnwb_waived_requirements"]`, keyed by input name; nothing is recorded when nothing was waived (GitHub issue #29).
- `jnwb.vis.plot_wavemap(result, waveforms)` draws a `WaveMAPResult`: the 2-d embedding colored by cluster beside each cluster's mean normalized waveform; `layout` and `height_mm` are keyword-only. Each cluster gets its own color, from the smallest palette that holds them all, up to 24. It refuses more clusters than that, an empty result, and labels, waveforms or an embedding of different lengths with `ValueError`. Tutorial 10 runs it on the DANDI 000253 excerpt, which now carries the source's mean waveforms; the source labels them volts, and the values read as microvolts.
- Four published unit measures, each in the form AllenInstitute `ecephys_spike_sorting` implements (at `919992748a53`): `jnwb.waveform_halfwidth`, `jnwb.repolarization_slope` and `jnwb.waveform_spread` from its waveform metrics (Jia et al. 2019), and `jnwb.amplitude_cutoff` from its quality metrics, after Hill et al. (2011). Each agrees with Allen's function on synthetic units to 1e-12 relative or better, Allen's time scaling and its exclusion of channel 0 from the spread included; jnwb takes the peak channel from the mean waveform where Allen takes it from the Kilosort template, and refuses a flat or NaN waveform where Allen returns NaN.
- `jnwb.check_waveform_blocks` reports, per unit, whether its index-sliced `waveform_mean` block is owned, unowned, or unknown against the stored `amplitude`, so blocks stored out of unit order are detected instead of read silently wrong. It repairs and reassigns nothing (GitHub issue #27).
- `jnwb.check_waveform_blocks` also reads the dense layout: a `waveform_mean` of shape `(units, samples, channels)` with no `waveform_mean_index`, in NWB schema order. Each unit gets the same owned, unowned or unknown verdict against its `amplitude`; ragged files give the same results as before.
- `wavemap_resolution_sweep` takes `metric=`, the UMAP input metric `wavemap` takes, default `"euclidean"`; the sweep built every graph with the euclidean metric, so a resolution chosen by the sweep did not apply to a `wavemap` call with another metric. Default calls are unchanged.
- `wavemap_resolution_sweep` returns `units`, the rows each run drew, and `umap_seed` and `louvain_seed` per run, so a sweep run with `rng=None` can be repeated; the scores are unchanged.
- `jnwb.wavemap`, `jnwb.wavemap_resolution_sweep`, `jnwb.align_waveforms`, `jnwb.normalize_waveforms` and `jnwb.WaveMAPResult`: WaveMAP (Lee et al. 2021, eLife 10:e67490) clustering of mean waveforms with Louvain on the UMAP nearest-neighbor graph, with the resolution in the published Markov-time convention (networkx is passed `1 / resolution`). The sweep reports the smallest cluster of each run, so the published rule for choosing the resolution can be applied. The two clustering functions need the new `wavemap` extra (umap-learn, networkx), which CI now installs.

### Changed

- Python 3.15 is supported: it joins the classifiers and the blocking CI matrix on Ubuntu, where h5py builds from source. The Windows 3.15 leg waits for an h5py CPython 3.15 wheel.
- `jrsa(align_mode=...)` is deprecated: it never had an effect, and passing it now emits a `DeprecationWarning`. It will be removed in 0.2.13; alignment is set by `align`. Results are unchanged.
- `phase_slope_index` reads a jackknife spread at or below `4 * n_seg * eps * n_pairs * sqrt(U - 1)`, with `U` the jackknife units (trials or segments), as rounding and reports `sd` and `z` as NaN and the lead p as None; before 0.2.10 the bound was `8 * n_seg * eps * n_pairs`, which left out the jackknife's `sqrt(U - 1)`. The bound is lower for 3 or 4 units, unchanged for 5, and higher from 6, so `sd`, `z` and p change only for a spread between the two bounds, at rounding level. The change shipped in 0.2.10 and its section did not list it.

### Fixed

- `StatisticalAnalysis.exploratory_compare` reads `pval` NaN for the Mann-Whitney test of two unpaired groups that share one constant value, on every supported scipy: scipy 1.17, the declared floor, returned 1.0 and 1.18 returns NaN. The statistic is unchanged.
- `normalize_waveforms` returns NaN for every row whose samples are all equal, as its docstring said; the mean subtraction left rounding residue that was scaled to a row of +-1, for 604 of 1001 constant 82-sample rows drawn from [-5, 5]. With `subtract_mean=False` only a row of zeros reads NaN, as before.
- `jnwb.inspect` no longer raises `TypeError` on an interval table holding a non-float column: a compound row, a string and any other scalar dtype are sampled as stored, while a float NaN still reads as `None`. A nonnumeric column used to make the whole file unreadable (GitHub issue #28).
- `plot_unit_waveforms(channels="peak")` draws the peak channel that `waveform_features` reports, the channel of largest maximum minus minimum. It drew the channel of largest absolute deflection, so on a template where the two rules differ, the drawn and the reported peak channel could differ. The reported features are unchanged.
- `PlotlyPublicationCanvas.save_and_seal` validates the argument object before anything renders, renders the SVG and PNG in one kaleido session and writes the argument sidecar last, so a failed export raises and seals nothing; files from an earlier call at the same paths are removed first, and each export must read as its format (PNG signature, `<svg`, `<html`). A browser shutdown that times out after both images are written emits a `RuntimeWarning` and keeps them.
- `plot_sorted_heatmap` refuses a `colorbar_title` that is blank or names `value_unit`, as `jnwb.vis.plot_csd` already does. Before, a title that named the unit doubled it on the colorbar, and a blank title was accepted. Pass the quantity alone, for example `colorbar_title="Rate"`; `None`, the default, still labels the colorbar with `value_unit` alone.
- `plot_sorted_heatmap` raises `ValueError` when `category_labels` is given, naming the argument. Before, the labels were accepted and never drawn. Pass `None`, the default, to draw as before.
- `visual_qc.plot_unit_quality_distribution` raises `ValueError`, naming the column, when its stability flag (`stable_plus`, else `is_stable`) holds a value that is not a boolean. It used to coerce with `astype(bool)`, so a text flag such as `"no"` drew every unit as Stable. Real booleans (numpy, Python or pandas `boolean`) plot as before. Numeric flags raise too, including 0.0/1.0 floats such as a flag column read from CSV with missing values; convert them with `.astype("boolean")` first.
- `apply_tight_auto_axis` floors the y lower limit at 0 only when every plotted value is non-negative. Before, a line with a minimum of -5 was drawn below the axes; the lower limit now sits one margin below the minimum. Non-negative data keeps the floor at 0.
- `apply_tight_auto_axis` accepts a line whose y data was set from a list with `set_ydata`; it raised `TypeError` before.
- `jnwb.vis.plot_csd` refuses a `colorbar_title` that names `value_unit` (the colorbar read "CSD (A/m³) (A/m³)"). Pass the quantity alone, for example `colorbar_title="CSD"`. A blank title, including `""`, now raises too; `None` still labels the colorbar with `value_unit` alone.
- `jnwb.vis.plot_csd` depth hover names `depth_unit` after the depth value.
- `jnwb.vis.plot_spectrolaminar_map` refuses `+inf` and `-inf` in `rel_power`, which were drawn as gaps. NaN is still drawn as a gap.
- `jnwb.vis.plot_spectrolaminar_map` raises a `ValueError` naming `rel_power` when it is empty; with the default `log_freq=True` numpy raised a reduction error.
- `jnwb.check_waveform_blocks` raises `ValueError` naming a unit mismatch when the median ratio of stored `amplitude` to largest block peak-to-peak is 1000 or more, or 1/1000 or less; it used to report every unit unowned in that case. A 2-D dense `waveform_mean` is still refused, now with a message that names the electrodes axis. Files whose units agree keep their results.
