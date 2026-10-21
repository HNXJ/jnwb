# Changelog

All notable changes to `jnwb` will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases 0.2.9, 0.2.8, 0.2.6.1, 0.2.6, 0.2.5, 0.2.4, 0.1.8 and 0.1.7 to 0.1.0 are archived, verbatim, in [artifacts/archive/changelog_0.1.0-0.2.9.md](artifacts/archive/changelog_0.1.0-0.2.9.md).

## [Unreleased]

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
- docs/generate_figures.py: figures of a cluster permutation test, spectral Granger and the narrowband PSI trap
- The jnwb-laminar skill routes the laminar rows of jnwb-lfp-spectral; skills/jnwb-laminar/SKILL.md (pull request #31)
- `map_peak_channel_to_layer` gives each unit its peak channel's curated layer; tests/test_laminar_curation.py
- docs/references.md: 28 more routed methods cite their published source; each docstring cites the same DOI
- docs/generate_figures.py: figures of RDMs with a windowed jRSA trace, and of bad channel and bad trial detection
- docs/generate_figures.py: figures of Welch and multitaper PSDs, zero-lag coherence measures and vFLIP profiles
- docs/generate_figures.py: figures of a smoothed rate step, causal against Gaussian, and of spike phase locking
- The dashboard's OpenScope GLO tab: one card per work, its replications as rows; scripts/build_dashboard.py
- docs/generate_figures.py: fig21, the open-data PSTH by layer and 50 to 80 Hz power by depth, from its analysis
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

## [0.2.10] - 2026-10-07

### Breaking

- `directed_network` gives each pair its own child seed when `rng` (or `seed`) is an int, the estimators' default 0 included, drawn in pair order from `default_rng(rng)`; it passed the int to every pair unchanged, so every pair drew the same surrogate stream. Surrogate p-values from an int or default seed change. A `Generator` gives the same per-pair seeds as before, and `None` still lets each pair draw fresh entropy. The new `pair_seeds` key records the seed each pair ran with.
- `jrsa(window=...)` without `adim` now cuts the observations of `rsa`, `cka`, `rv`, `hsic`, `distance_correlation` and `procrustes` (axis 0, the axis `lag` and the null act on) instead of their features (the last axis). Results of such calls change. Pass `adim=-1` to window the features as before; the paired metrics are unchanged.
- `spike_count_correlation` raises `ValueError` for a window of fewer than 3 bins, naming the bin count and the minimum of 3. With 2 bins every pairwise Pearson r is +1 or -1, so `mean_r` measured nothing; there is no old behaviour to keep, so widen `window_s` or narrow `bin_ms` to reach 3 bins.
- **`compute_population_trajectory`'s `explained_variance` (breaking).** Deprecated in 0.2.7, it was one float, the fraction of variance the kept components explain together, `np.nansum(explained_variance_ratio)`. It is now an array `(n_components,)`, each component's variance `S**2 / (n_samples - 1)`: the values of `explained_variance_per_component`, scikit-learn's `explained_variance_`, as in `PopulationAnalyzer.population_trajectory`. Reading it no longer warns, and the result is a plain `dict`. For the old value read `np.nansum(res['explained_variance_ratio'])`.

### Added

- `aperiodic_fit(..., robust=True)`, keyword-only and False by default: FOOOF's robust aperiodic fit (`FOOOF._robust_ap_fit`). After the first fit it refits only the bins whose residual above that fit, clipped at 0, is at or below its 0.025th percentile, so a peak inside `freq_range` biases `exponent` less (a 10 Hz peak on a 1/f^2 spectrum gives 2.16 by default and 2.02 with it). It detects and subtracts no peak; `r_squared` is over the kept bins, and fewer than 4 kept bins reject the fit. The default fit is unchanged.
- `directed_network(..., conditional=True)` conditions each Granger pair on every other node through `Z` (Geweke 1984), so an indirect path or a common driver among the recorded nodes no longer shows as a direct edge. Only `method='granger'` conditions; PSI, transfer entropy and spectral Granger stay pairwise and raise `ValueError` for `conditional=True`. The result records `conditional`.
- `curate_and_label` takes `max_interpolate_run`, `min_contacts`, `min_edge_contacts` and `nperseg`, and `detect_bad_channels` takes `nperseg`; each default is the value used before, so default results are unchanged. `LaminarCurationResult.xflip` holds the `XFlipResult`, `xflip_distance_um` is NaN when that fit is rejected, and `parameters` records `fs`, `rng` and `xflip_surrogate_seed_entropy`. A band that does not end below `fs / 2` is refused by name, so `fs` of 300 Hz or less needs narrower bands.
- `jnwb.laminar_curation`: `curate_and_label(lfp, fs, *, pitch_um, ...)` curates a laminar LFP recording and labels every contact `"superficial"`, `"input"`, `"deep"`, `"WM"`, `"outside_cortex"` or `"na"`, returning a `LaminarCurationResult` with a grade (`"A"` to `"D"`, `"F"`) from the stability of the anchor across blocks of epochs and from spectral consistency. Its parts are public: `detect_bad_channels`, `interpolate_channel_runs`, `evoked_csd_sink` and `fuse_laminar_anchors`. Every width is in micrometers and every threshold is a parameter; the defaults are working values from 25 and 40 um probes, not published values. xFLIP and the evoked CSD are reported as distances to the anchor and never move it, a shaft with more than one spectral crossing is reported and not split, and grade `"F"` labels every contact `"na"`.
- `jnwb.paths.layer_masks_path(subdir=...)`: the folder under the outputs directory that holds `layer_masks.json`. The default, `publication_visual_review/area_layer_tfr`, is the path it always returned.
- `check_ragged_indices(path, *, table="units", probe_starts=None, probe_column=None)`: read-only check of every `<column>_index` of an NWB table against the HDMF `VectorIndex` rules, returning a `RaggedIndexReport` of `RaggedIndexCheck` rows with the flags `monotonic`, `nonnegative`, `ends_at_data_len` (an empty index over empty data passes), `length_fits` and `offset_bug` (the multi-probe defect in which later probes' indices are offset by the first index element instead of the running total), plus ragged columns missing from `colnames`.
- `repair_ragged_index(path, column, *, ..., dry_run=True, output_path=None, in_place=False, backup_path=None)`: corrects one index only when the old index equals that defect's formula and the corrected index fits the dtype, raising `RaggedIndexRepairRefused` otherwise. A dry run by default; to write, `output_path` creates a new file, or `in_place=True` with `backup_path` replaces the input. Either way the index is written to a copy that is re-read and checked before an atomic `os.replace`, `written` is True only after that check, and any failure leaves the input byte-identical.
- A docs page, "Repairing NWB files", on ragged-index defects, schema consistency and the validation stack, and an errors-page section listing every message of the two functions.
- `validate_nwb(path, *, layers=None, dandi_ignore=("DANDI.NO_DANDISET_FOUND",), max_messages=50)`: validates one NWB file in six layers (`read`, `pynwb_schema`, `pynwb_core`, `integrity`, `nwbinspector`, `dandi`) and returns an `NWBValidationReport` whose `ok`, `complete` and `dandi_ready` say whether any layer failed, any was skipped, and whether the `read`, both `pynwb` and the `dandi` layers ran and passed. `pynwb_core` validates against the core namespace of the installed pynwb, so a file is checked against the newest schema that release knows. The NWB Inspector and DANDI layers need the `validate` extra and are reported skipped, never passed, without it. Both layers were exercised with nwbinspector 0.7.2 and dandi 0.81.0 only; the older releases the extra allows are untested.

### Changed

- `jnwb.bilinear.BilinearLogisticRegression` fits one model for two classes, and `predict_proba` returns its own probability, sigmoid(D). It was the softmax of two mirrored one-vs-rest models, about sigmoid(2 D) and overconfident: on held-out simulated trials its 0.8 to 0.9 bin predicted 0.85 where 0.65 was observed, and the count-weighted gap between predicted and observed frequency falls from 0.085-0.19 to 0.02-0.09 across ten simulated populations. Two-class labels and decision values are unchanged (the mirrored models are negations of each other; they agreed to 1e-13 on six simulations), and `n_parameters()` counts the one model, half its old value. Strong regularisation or class weights can still leave the probabilities less calibrated, as the docstring says. With three or more classes nothing changes.
- `StatisticalAnalysis.bootstrap_ci` draws its resamples in blocks and, for the default `np.mean`, takes their means in one call: 8.9 times faster at 200 values and 10,000 resamples. The random stream is unchanged: a seed or `Generator` gives the same resamples, the same result and the same final `Generator` state as before.
- `cross_area_coherence(rng=<Generator>)` draws one child seed from the `Generator`, runs the surrogate shifts on it and records it in `surrogate_seed_entropy`, which was `None`; passing it back as `rng` reproduces the p-values. For a `Generator` input the p-values therefore change, and the caller's stream advances by 1 draw instead of `n_surrogates`. An `int` seed, `None` and the default are unchanged.
- `StatisticalAnalysis.confirmatory_compare` returns `correction: "bh"`, the Benjamini-Hochberg step that produced `q_parametric` and `q_nonparametric`; it returned `"none"` beside those q-values. The `pval` keys stay raw, and the `exploratory_*` results keep `correction: "none"`.
- `directed_network(fdr=True)` warns when no pair returned a p-value (PSI with `jackknife=False`, TE with `n_surrogates=0`) and records `fdr_requested_but_no_pair_has_a_p_value` in `warnings`; the all-NaN `q_matrix` came back silently.
- `jrsa(..., metric='phase_slope')` no longer warns "pass 3 or more trials" on every call. The metric ravels its input to one series, so a caller had no trials to add; `phase_slope_index` called directly still warns. No value changes.
- `fano_factor`, `compute_response_metrics`, `raster_psth`, `UnitAnalyzer.psth` and `UnitAnalyzer.raster` select a spike by its time minus the onset, as `bin_spikes` does, instead of comparing it with the onset added to each window edge. The two round differently for a spike within an ulp of an edge: with onset 0.03 s, a spike at 0.3 s is exactly 0.27 s after it and is now counted in a window starting at 0.27 s, where 0.03 + 0.27 rounded above 0.3. Counts, and a `compute_response_metrics` latency, change only for such edge spikes. `UnitAnalyzer.raster` now also accepts spike times and onsets as lists, which it refused with a `TypeError` before.
- `PopulationAnalyzer.population_trajectory` on centred data with exactly zero total variance returns NaN `components` and a NaN `projection`, as it already returned NaN variances. It returned the identity matrix, which the decomposition of all-zero data yields and no property of the data determines, and a zero projection on it. Centring a constant can leave rounding residue (a constant 0.1 does), which counts as variance. `compute_population_trajectory` likewise returns a NaN `trajectory` when the z-scored data have exactly zero total variance, as for a population of constant units; it returned zeros. Results for data with variance are unchanged.
- `phase_slope_index(nperseg=None)` shortens the default segment from `n_times // 4` until the trials hold at least 20 Welch segments, down to 16 samples. One 2000-sample trial now gets `nperseg` 190 (20 segments) instead of 500 (7), so its values, z and p change; records whose default already left 20 segments, such as 10 trials of 400 samples, are unchanged. Under zero-lag mixing the lead p over 5 to 100 Hz rejects at 0.057 (4000 pairs); a 5-sample lead is detected in every pair, against 0.59 before.
- `phase_slope_index` jackknife leaves out one trial when there are three or more trials, as Nolte et al. leave out one epoch, and one Welch segment below that, now with a `RuntimeWarning`; `params['jackknife_unit']` records which. With three or more trials `sd`, `z` and the lead p change, and the t test has one degree of freedom fewer than the trials. Under zero-lag mixing over 5 to 100 Hz the lead p rejects at 0.040 to 0.059 on 3 to 30 trials (2000 pairs), against 0.059 to 0.068 leaving out segments.
- `UnitAnalyzer.quality_metrics` counts a refractory violation by the rule of `refractory_contamination`: an inter-spike interval within 1 ns of `refractory_ms` counts as equal to it, where it was a violation. Spikes at 0, 0.002 + 5e-10, 1 and 1.002 - 5e-10 s at `refractory_ms=2` gave `refr_violations_pct` 33.3 and now give 0. Only intervals within 1 ns of the period change. The docstring now states that the Fano factor's 1-s windows are the whole seconds from the first spike, so spikes after the last whole second are not counted.
- `vflip`, `vflip_from_lfp` and `label_layers` raise `ValueError` when the declared `depth_axis` is not monotone along the shaft, as the lateral column of a staggered shaft is not. Only the two end contacts were compared, so on a staggered shaft with an even number of contacts the lateral column was accepted as depth.
- `xflip(rng=<Generator>)` draws one child seed from the `Generator`, runs the surrogates on it and records it in `surrogate_seed_entropy`, which was `None`; passing it back as `rng` reproduces the p-values. For a `Generator` input the p-values therefore change, and the caller's stream advances by 1 draw instead of the surrogates' draws. An `int` seed, `None` and the default are unchanged.
- `zflip` draws surrogates for the adjacent pairs a constant or linear-in-time contact does not touch, so those pairs can be identifiable and report a delay. One such contact used to skip the surrogates for the whole shaft and left every pair unidentifiable. `accepted`, `p_value` and `mean_wpli` are unchanged: the recording is still rejected, because the pairs touching the flat contact have no wPLI. `surrogate_seed_entropy` is now recorded for such a recording.
- `zflip(rng=<Generator>)` draws one child seed from the `Generator`, runs the surrogates on it and records it in `surrogate_seed_entropy`, which was `None`; passing it back as `rng` reproduces the p-values. For a `Generator` input the p-values therefore change, and the caller's stream advances by 1 draw instead of the surrogates' draws. An `int` seed, `None` and the default are unchanged.
- `zflip` flags a contact as linear in time when the rms of its second difference is at most 4 eps of its largest magnitude. The rule was the rms residual of a fitted line at most 1000 eps, which a ramp built by cumulative summation exceeded at 1e5 samples (about 3400 eps), so such a contact was measured and could give a delay. The new rule flags every ramp measured (largest 1.0 eps, up to 1e5 samples; 2.2 eps with 1-ulp noise per sample) and keeps a unit-SD signal on a larger offset than before: white noise to about 2.8e15 rather than about 4.5e12.
- `parse_probe_areas` keeps a slash followed by one lowercase letter in the label before it when that label ends in a digit and a lowercase letter, the sublayer alternation of `VISp6a/b`: `"VISp6a/b"` gives `('VISp6a/b',)`, where it gave the areas `('VISp6a', 'b')`, so `map_peak_channel_to_area` reports such a location as one area. The rule reads the characters only; `"VISp6a/bc"` still splits.
- A Laminar Depth page calls `vflip`, `label_layers`, `xflip` and `zflip` once each on synthetic data, and states how `vflip` differs from the published FLIP and vFLIP whose name it shares; the `vflip` docstring states it too.

### Removed

- `jnwb.artifact_repair.REWARD_WINDOW_MS`, a module constant outside `jnwb.__all__` that no function read: `repair_lfp_trials` takes the window as `exclude_window_ms` (or `reward_window_ms`), which defaults to `None`. Pass `exclude_window_ms=(4000.0, 4300.0)` for the window it held.
- **A `relative_power` baseline with fewer dimensions than `power` (breaking).** Deprecated in 0.2.7, such a baseline other than a scalar was broadcast along `power`'s trailing axes with a `FutureWarning`, so a `(n_freqs,)` baseline against `(n_freqs, n_times)` power divided along time. It raises `ValueError`, as in `aggregate_to_db` and `TFRAccumulator.add_trial`; pass `baseline[:, None]` for a per-frequency baseline.
- **`spectral_tilt`'s key `exponent` (breaking).** Deprecated in 0.2.7, it returned the signed log-log slope, the opposite sign of `aperiodic_fit`'s `exponent`. Reading it raises `KeyError`; read `slope`, negative for a 1/f decay.

### Fixed

- `cross_area_coherence` returns NaN for the coherence spectrum, every band coherence and p-value, and the peak, when either trace is constant. Mean removal left rounding residue that the ratio turned into a coherence: about 0.05 per band on the CPU and 0.0 on CUDA, each with a p-value.
- A linearly detrended trial or `jrsa` row that is a straight line is now exactly zero, so `granger` reports it as a degenerate residual variance (NaN) and `jrsa` with `standardize=True` returns NaN, where both read the fit's round-off (1e-15 to 1e-11) as signal. The bound is `4 * n * eps * max|x|` per slice. `transfer_entropy` p-values count a surrogate as a tie within the round-off of the four entropies each value cancels (`4 * n_cells * eps * max(1, sum of entropies)`), where the net p used `100 * eps * (|TE_xy| + |TE_yx|)`.
- `JRSAResult.save` writes every field in every format; nothing it wrote before is removed. `fmt="csv"` adds the arrays (`value`, `statistic`, `effect`, `p`, `q`, `df`, `ci`, `null_distribution`, `aligned_x1`, `aligned_x2`): a 0-d array as a `field,value` row, a 1-D array as one `name[:]` row, a larger array as a `name.shape` row followed by one `name[i]` row per index of its leading axes; it also adds a `jnwb_csv_format,2` row, and writes tuple, list and dict cells (`axes`, `labels`, `parameters`, `execution`) as JSON instead of Python text. `fmt="npz"` adds `metric`, `axes`, `aligned_axes`, `labels`, `parameters` and `execution`, with its `seed`, as one JSON string under `fields_json`, and stores a `value` that is a NumPy scalar. `fmt="json"` writes NumPy integer scalars as numbers instead of strings.
- `JRSAResult.plot` centres its diverging colormap on 0 (symmetric `vmin` and `vmax`) when a 2-D value has both signs, and passes `vmin` and `vmax` given by the caller to the image.
- `nested_cv_linear_svm` refuses more than two classes in `labels` by name; scikit-learn raised an error naming `multi_class`, an argument it does not take, after every fold had been fitted.
- `layer_masks_path` refuses an empty, absolute or `..`-containing `subdir`; the last two resolved outside the outputs directory.
- A renamed result key written with `d |= {old: value}` writes the current key with a `DeprecationWarning`, as `update` does, and `pop` of a renamed key whose current key is gone returns the default or raises `KeyError` for the key asked for.
- The CPU fallback warning for `device="cuda"` gives the library-conflict advice only for a library that failed to load; another `OSError`, such as a `PermissionError`, is reported without it.
- `causal_exp_smooth` raises `ValueError` naming `tau_ms` when it is not finite and positive. `tau_ms=0` returned an all-NaN trace with a `RuntimeWarning`.
- `build_permutation_plan` with `groups=None` raises a `TypeError` that names `groups`, where it raised `'NoneType' object is not iterable`.
- `UnitAnalyzer.psth` refuses a reversed or empty `window_ms` with a message saying which; a reversed window read "Use , or a bin width that divides the span". The refusal of a window that is not a whole number of bins prints windows with every digit they need, so a refused window at 3e12 ms and its suggested replacements no longer print alike.
- `jnwb.nam.train_nam` leaves torch's global random state as it found it; it seeded it with `seed`. The trained model is unchanged for the same `seed`.
- `fit_exponential_onset` refuses a constant `rate` by name. Every onset time fits a flat trace equally well, and it returned the upper `t0` bound, an amplitude of 1e-6 and `r2` NaN as a fit. It also names `t_ms` and `rate` when they are not 1-D of one length, where SciPy and NumPy raised about `f0` or broadcasting.
- `PopulationAnalyzer.population_trajectory` refuses an `X` that is not 2-D by name; a 1-D `X` raised NumPy's `LinAlgError`. Its device warnings name `PopulationAnalyzer.population_trajectory` rather than `population_trajectory`.
- `UnitAnalyzer.psth` and `build_time_resolved_matrix` refuse a `bin_size_ms` of 0, below 0 or not finite by name; 0 raised `ZeroDivisionError`.
- `compute_population_trajectory` reports `device_used` (`'cpu'`) for an area with no units, as it does for every other result.
- When PyTorch or CuPy fails to load its libraries, a `device='cuda'` request warns with the loader's error and names the likely cause, a CUDA library another package loaded first in the process (a DLL conflict on Windows). It said no usable CUDA device was found.
- `StatisticalAnalysis.permutation_test` returns `pval` NaN and `significant` False when the pooled samples are not finite once centred on their mean, as when their sum overflows. `x = [1e308, 1.7e308, 1e308]` against `y = [-1e308, -1.7e308, -1.5e308]` returned `significant` True at the p floor, `1 / (n_permutations + 1)` (0.005 at 199 permutations, about 0.0002 at the default 5000), beside a NaN `observed_difference`.
- The one-test note in `multiple_comparison` of `StatisticalAnalysis.correlate` names `method=`, the argument `correlate` takes; it said `test=`.
- `compute_psd` and `compute_multitaper_psd` return an exactly zero PSD for a trace constant along the time axis, where mean removal left rounding residue (about 1e-33 to 1e-23). Every other trace's PSD is unchanged to the bit.
- `RenamedKeyDict.setdefault` on a key that is changing now emits the `FutureWarning` that `get` and `[]` emit, and `whole_bin_count` with an infinite window bound raises `ValueError` where it raised `OverflowError`.
- `setdefault` on a result dict with a renamed key reads the current key: `setdefault('old', 99)` on a dict holding `new` returns the value of `new` with the `DeprecationWarning` that reading `old` gives, and inserts nothing. It returned 99 and inserted a key `old` beside `new`.
- Writes to a result dict with a renamed key follow the old name to the current key, with the `DeprecationWarning` that reading the old name gives: `d['old'] = v` and `d.update({'old': v})` set `new`, where they inserted a key `old` beside it, and `d.pop('old')` removes and returns `new`, where it raised `KeyError`.
- `repair_ragged_index` claims a new `output_path` exclusively before moving the verified copy onto it, so a file created there after the existence check is refused instead of overwritten; a dry run with `in_place=True` no longer needs or checks `backup_path`.
- `jrsa(metric='cka')` and `metric='rv'` return NaN for a constant pattern, where rounding residue gave about 1e-33.
- `rdm` refuses a constant condition under the correlation distance whatever its value and names it; a constant row of 0.1 gave finite distances where 0.3 raised. `jrsa(metric='rsa')` returns NaN there.
- `jrsa(align=...)` raises for an unrecognized value when the lengths already agree; it ran unchecked. An interpolating `align` raises `ImportError` without SciPy instead of downsampling under the requested label.
- `binary_occupancy_mutual_information` and `spike_count_mutual_information` name themselves in their errors, which named `spike_mutual_information`.
- A hand-built `ComplexTFR` raises `ValueError` for a `device` other than `'cpu'`, `'cuda'` or `'metal'`; any string was accepted as the record of what computed `z`. `complex_tfr` always set a valid one.
- `aggregate_to_db(how="mean_of_ratios")` refuses `TFRAccumulator` trial-mean power at any depth of list or tuple nesting and inside a memoryview held in a list, such as `[[P[0]], [P[1]]]`; it looked one level deep.
- `vflip` reports `support_score` as the logarithm of its support metric without a floor, and `-inf` when the metric is zero. It was `log(max(1e-12, metric))`, so every metric below `1e-12` read as -27.63, and a caller `min_support_score` at or below that accepted a fit with no support. The default threshold, 3.75, rejected those fits before and after.
- A z-scored slice that holds inf or -inf and is not constant is NaN throughout at the z-score step, wherever an inf reaches it (visibly `jrsa(standardize=True)`): `[1, inf, 2]` gave `[-inf, nan, -inf]`, its NaN standard deviation having been replaced by 1.
- `compress_fp32` and `jnwb.compression.convert` refuse a regular `timestamps` array beside a `starting_time` that has no `rate` attribute with a `ValueError` naming both, before anything is written. They raised a `TypeError` from arithmetic on the missing rate and left a temporary file in the output directory. An irregular array beside such a `starting_time` still converts.
- `compress_fp32` finds a `timestamps` array under every hard-link name. An array whose first name was another hard link was not listed in `timestamps_kept_linked`, and `select=` cast it; it is now kept at its source dtype, listed, and refused in `select=`.
- `compress_fp32(select=...)` refuses an irregular `timestamps` array that a cast would leave reading differently under another name: one with a second hard link, one named through a soft link, or one that a top-level soft link opens, directly or through a group, when another link also opens it. The selected name was cast to float32 while the other name kept the float64 sample times. Selecting the target of a soft link elsewhere in the file still casts it, both names then read the same float32 values, and the result lists it in `cast_paths` only, where it was also listed in `timestamps_kept_linked`.
- `get_all_units_metadata(filter_quality=True)` on a file whose units table has no `quality` column emits the `RuntimeWarning` given for a `quality` column with no usable value and excludes that file's units. It raised `KeyError`, which the default `on_read_error="skip"` logged as a failed read, so a call on that file alone raised `RuntimeError`.
- `unit_census_report` with the default grouping warns when the frame lacks `session_id`, `area` or `depth_class` and groups by the remaining default columns, as an explicit `group_by` already warned; it dropped them silently. A frame with `layer` and no `depth_class` keeps its one warning.
- `enrich_units_dataframe` warns when `units_df` has no `peak_channel_id` beside a non-empty electrodes table and it fills `area`, `depth_class` or `group_name` on every row (None, or `'Unknown'` for `depth_class`); it filled them silently.

## [0.2.7] - 2026-09-29

### Added

- `jnwb.vflip`, `jnwb.vflip_from_lfp` and `jnwb.label_layers` take keyword-only
  `depth_axis=` (`"x"`, `"y"` or `"z"`, the geometry column that is depth) and `shallow_end=`
  (`"min"` or `"max"`, the end of that column nearest the surface), declared together.
  `"x"`, `"y"` and `"z"` are columns 0, 1 and 2 of `contact_positions`, so `"z"` is `rel_z`
  for a table without `x`/`y`/`z`. With a declaration the fit runs from the shallow contact:
  `crossover_contact`, `low_peak_contact`, `high_peak_contact`, `profile`, the `orientation`
  argument and result, and `crossover_depth_um` are all in that order, so the same probe
  gives one fit, one depth and one labelling whatever order the electrode table lists it in.
  `VFlipResult` records `depth_anchor` (`"shallowest"`, or `"row_order"` without a
  declaration) with the `depth_axis` and `shallow_end` it used. Without a declaration nothing
  changes: depth runs from the first contact of `linear_order`, which follows the table's
  rows. An unknown axis or end, only one of the two, a declaration without a
  `probe_geometry`, an axis whose values at the two end contacts are within 1e-6 um of each
  other, or a `label_layers` declaration that differs from the one the fit was made with
  raises `ValueError`. `ProbeGeometry` is unchanged.
- A declared fit whose motif resolves as `"deep_to_superficial"`, which puts the deep layers
  at the declared shallow end, is rejected with `rejection_reason="declaration_contradicted"`;
  `label_layers` then labels every channel `'na'`. The reason is checked after every other
  acceptance test, so a fit without support reports `"insufficient_support"` and an
  `orientation` argument the peaks disagree with reports `"orientation_mismatch"`. A
  declaration passed with `orientation="deep_to_superficial"` raises `ValueError` before any
  fitting, in `vflip` and `vflip_from_lfp`. Undeclared fits are unaffected.
- `jnwb.preflight(question)` and `jnwb.Preflight`: check a planned analysis before it runs.
  The result's `outcome` is one of `"supported"`, `"request"`, `"failure"` and `"decline"`,
  with a `reason` and, for a request, the `missing` inputs; `to_dict()` is JSON-ready. Checked
  in order: a stated `unsupported_inference` declines; an empty `signals`, `signal_units`,
  `contrast` or `inference_unit`, a blank signal name (named as `signals[<index>]`), or a
  signal without a unit (absent, blank or `None`), requests; a stated `non_identifiable` reports
  a failure; anything else is supported. A unit in `signal_units` that is neither a string nor
  `None` raises `TypeError`.
- `jnwb.Question` gains optional fields, all empty by default so existing constructions are
  unchanged: `signal_units`, `data`, `paradigm`, `axes`, `conditions`, `required_skills`,
  `verification_plan`, `unsupported_inference` and `non_identifiable`. `to_dict()` includes them.
- `TFRAccumulator.add_trial` takes a keyword-only `baseline=`, the trial's own baseline power,
  and `TFRAccumulator.mean_of_ratios()` returns the mean over trials of each trial's power
  ratio, so `to_db(acc.mean_of_ratios())` streams `aggregate_to_db(how="mean_of_ratios")`
  without holding the trials. With a `valid` mask the stacked equivalent sets the invalid cells
  to NaN and passes `nan_policy="omit"`. Either every trial carries a baseline or none does;
  `merge` pools the ratio sums and `write` stores them as `sum_ratio`. `aggregate_to_db` still
  refuses `how="mean_of_ratios"` on `power()`.
- `nested_cv_linear_svm` takes keyword-only `groups=` (one id per trial) to hold out whole
  groups. Outer and inner folds become `StratifiedGroupKFold` over the groups in an order drawn
  from `rng`, `n_splits` is clipped to the minority-class count and the group count, and
  `cv_scheme` is `"nested_stratified_group"`. The inner search falls back to `C=1.0` when an
  inner training split would hold one class. Fewer than two groups returns status
  `"insufficient_groups_for_cv"`; a missing id, NaN or infinity in a float array of ids, ids
  that cannot be compared, and
  an outer training fold with a single class raise `ValueError`. A call without `groups`
  returns the same numbers as before.
- `XFlipResult.surrogate_seed_entropy` records the entropy the surrogate generator was built
  from: the seed for an int `rng`, the fresh OS entropy drawn for `rng=None`. Passing it back as
  `rng` reproduces `p_values`. It is `None` for a caller's `Generator` and when no surrogates
  ran. `to_dict()` includes it. An int seed draws the same stream as before.
- `ZFlipResult.surrogate_seed_entropy`, on the same rule as `XFlipResult`'s: passing it back as
  `rng` reproduces `p_value`; `None` for a caller's `Generator` and when no surrogates ran.
  `to_dict()` includes it. An int seed draws the same stream as before.
- `nested_cv_linear_svm` returns `seed`, the int its folds, group order and `SVC` were seeded
  with: `rng` itself for an int, the int drawn for a `Generator` or `None`. Passing it back as
  `rng` reproduces the folds and scores. It is `None` for a status other than `"success"`.
- `compute_population_trajectory` returns `explained_variance_ratio` (each component's share of
  the total) and `explained_variance_per_component` (each component's variance,
  `S**2 / (n_samples - 1)` of the z-scored data), both `(n_components,)` as scikit-learn's
  `PCA` defines `explained_variance_ratio_` and `explained_variance_`, and NaN where a
  component could not be estimated.
- `compute_response_metrics` returns the per-trial `baseline_rates`, `response_rates`,
  `baseline_counts` and `response_counts` (integers), in onset order and zero when there are no
  spikes, and the window lengths `baseline_duration_s` and `response_duration_s`. No key is
  removed.
- `VFlipResult.crossover_z_um`: the crossover's z coordinate in the probe geometry's own frame
  (um), interpolated along the shaft. `None` without a `probe_geometry`, when z does not vary
  along the shaft, or when the fit is rejected. `to_dict()` includes it.

### Changed

- **`transfer_entropy` p-values change (breaking).** The surrogate test compares plug-in TE,
  for the data and for every surrogate, whatever `bias_correction` is; Miller-Madow applies
  only to the reported `x_to_y`, `y_to_x`, `net` and `bias_corrected_*`, whose values do not
  change. A surrogate removes the zero-lag X-Y dependence and occupies more joint cells, so a
  correction applied to both made two noisy copies of one white source test significant in
  0.11 of cases at 4 bins and 0.37 at 8 bins (n = 2000). Under that null the p now rejects at
  0.025 to 0.06 for a nominal 0.05 (4 bins, n = 500 to 8000; about 0.06 near n = 4000 to 8000,
  decaying at larger n) and is conservative at large state
  spaces. `diagnostics['surrogates']['p_statistic']` is `"plug_in"`. Migration: none needed to
  run; a p computed before this release under the default `bias_correction="mm"` on correlated
  inputs is not comparable, so recompute it. The p now equals the one given by
  `bias_correction=None`.
- **`phase_slope_index` p-values change (breaking).** `p_net`, `p_x_to_y` and `p_y_to_x` are
  the jackknife t test of a non-zero PSI whenever `jackknife=True`, with or without
  `n_surrogates`; they were the surrogate p whenever `n_surrogates > 0`. A shifted or re-paired
  Y removes all X-Y dependence, so the surrogate p tests coupling, not a lead: under a zero-lag
  common source it rejected in 0.00 to 0.46 of cases depending on segment length and band. It
  is now `diagnostics['p_coupling_surrogate']` (per band, still `per_band[name]['p_surrogate']`).
  With `jackknife=False` the three p fields are None. The lead p rejects a zero-lag common source
  at 0.06 to 0.08 for a nominal 0.05. `diagnostics['p_source']` is `"jackknife_z"` or None.
  Migration: read `diagnostics['p_coupling_surrogate']` where the surrogate p was meant, and
  keep `jackknife=True` for a lead p; `directed_network(method="psi")` then corrects the
  jackknife p.
- `classify_response_significance` reports the conditional binomial `pvalue` when
  `response_zscore` is NaN, a baseline with no across-trial variance; it returned NaN. The test
  needs no baseline variance: 40 trials of 3 response spikes over a silent baseline give
  p = 7e-45 at the default windows. `confidence` stays `'undefined'` and `is_significant` False, because the
  effect-size cutoff cannot be evaluated. Malformed counts or window lengths now raise
  `ValueError` in that case too, where the NaN z-score returned before they were checked. The
  docstring states the bursting limit: with no effect, 5 Hz firing in bursts of four spikes over
  200 trials puts about 30% of units below p = 0.05.
- **`jrsa` row metrics need a named `null=` to form a permutation null (breaking).** For `rsa`,
  `cka`, `rv`, `hsic`, `distance_correlation` and `procrustes`, `null=None` with `stats=True`
  and `permutations > 0` raises `ValueError`; in 0.2.6.1 it warned and permuted the rows as
  exchangeable. `rsa` is the default metric, so a bare `jrsa(x1, x2)` raises. Name
  `null="iid"` for exchangeable conditions, which gives the 0.2.6.1 numbers, and
  `null="circular_shift"` when axis 0 is time. The guidance no longer offers `"block"` for these
  metrics: at `block_len=20` it rejected `cka` for 0.30 of independent AR(1) pairs.
- **`jrsa(metric="transfer_entropy_histogram_nats")` refuses several rows (breaking).** It
  flattened the input, which made the last sample of each row the past of the first sample of
  the next, so every join between rows counted as a time transition. It raises `ValueError` for
  an input with more than one row; pass one series per call, or use `jnwb.transfer_entropy` for
  `(n_trials, n_times)`.
- **`jrsa(metric="granger_ssr_ftest")` and `jrsa(metric="phase_slope")` refuse several rows
  (breaking).** Both flattened the input into one series, so each join between rows entered as
  a time step, and the value depended on the order of the rows. Both raise `ValueError` for
  more than one row; a 1-D or `(1, n)` input gives the value it gave before. For trials use
  `jnwb.granger` or `jnwb.phase_slope_index`, which take `(n_trials, n_times)`.
- **`jrsa(nan_policy="omit")` drops the observation of a row metric.** For the six metrics
  above it dropped the last-axis column holding the NaN, which removed a feature from every
  observation; it now drops the row of axis 0. Values change wherever such an input held a NaN.
- **The core dependency floors are raised to the lowest releases the test suite passes on
  (breaking for older environments).** The previous floors were installable but untested, and
  on Python 3.12 they failed: they could not be installed together (`pynwb 2.0.0` requires
  `pandas<2`), `joblib 1.1` hangs `n_jobs` loops, `scipy` before 1.17 raises on constant groups
  in `compare_multiple_groups` where 1.17 returns NaN, `enrich_units_dataframe` disagreed with
  `map_peak_channel_to_area` on a float32 or float16 identifier column under NumPy 1.x
  promotion, and `pynwb` before 3.1 cannot read files that use `ElectrodesTable`. Those
  releases then set the rest: `scipy 1.17` needs `numpy>=1.26.4`, and `statsmodels` before
  0.14.5 does not import against it; `pandas`, `h5py`, `matplotlib` and `scikit-learn` below
  the new floors do not import under NumPy 2; `pynwb 3.1` needs `hdmf>=4.1`. New floors:

  | Package | Was | Now |
  |---|---|---|
  | numpy | 1.26.0 | 2.0.0 |
  | scipy | 1.11.2 | 1.17.0 |
  | pandas | 2.1.1 | 2.2.2 |
  | h5py | 3.10.0 | 3.11.0 |
  | pynwb | 2.0.0 | 3.1.0 |
  | hdmf | 3.1.0 | 4.1.0 |
  | matplotlib | 3.7.3 | 3.8.4 |
  | scikit-learn | 1.3.1 | 1.4.2 |
  | statsmodels | 0.14.0 | 0.14.5 |
  | joblib | 1.1.0 | 1.2.0 |

  A CI job now installs these floors on Python 3.12 and runs the suite, so a floor that stops
  holding fails the build.
- **`map_peak_channel_to_area`, `classify_layer_from_depth` and `enrich_units_dataframe` search
  only the first identifier column present (breaking).** The order is `channel_id`, then `id`,
  then `electrode_id`. A channel missing from `channel_id` was looked up in `id`, which can
  number channels differently, and returned another channel's area and depth; it now resolves
  to `None` and its depth class to `"Unknown"`. Where the two columns do number the same
  channels, fill the gaps before the call to keep the old result:
  `electrodes_df["channel_id"] = electrodes_df["channel_id"].fillna(electrodes_df["id"])`.
- **`aggregate_to_db` refuses a `baseline` that is neither a scalar nor of `power`'s number of
  dimensions (breaking).** numpy aligned a shorter baseline with the trailing axes, so a
  per-frequency `(n_freqs,)` baseline against `(n_freqs, n_times)` power divided along time,
  silently whenever the two counts were equal. It raises `ValueError`; pass `baseline[:, None]`.
  `TFRAccumulator.add_trial(baseline=)` refuses the same shapes.
- **`aggregate_to_db` raises `ValueError` on a zero baseline (breaking).** It returned +inf dB
  there with the divide warning suppressed, where `relative_power` raised on the same input.
  Exclude those units, or set their power to NaN and pass `nan_policy="omit"`: under `"omit"` a
  zero where power is NaN is omitted with its cell and not refused.
  `TFRAccumulator.add_trial(baseline=)` raises on a zero baseline at a cell `valid` marks; a
  zero at an invalid cell never enters the sums, so `to_db(acc.mean_of_ratios())` still equals
  `aggregate_to_db(nan_policy="omit")` over the stacked trials with invalid power set to NaN.
- **`aggregate_to_db` and `TFRAccumulator.add_trial(baseline=)` raise `ValueError` on an
  infinite baseline and on a ratio that overflows (breaking).** An infinite baseline gave a
  ratio of 0, and -inf dB, where `relative_power` raised on the same input; it now raises at
  every cell where a zero baseline would, and is ignored where a zero would be (a cell `valid`
  excludes, or NaN power under `nan_policy="omit"`). A NaN baseline keeps its meaning. A
  baseline small enough that the ratio overflows -- finite power over it, or the mean of such
  ratios, past the float64 range -- returned +inf dB with only a `RuntimeWarning`; it raises in
  both, and in `relative_power`. Under `"ratio_of_means"` a summed baseline that overflows gave
  0 (-inf dB) and a summed finite power that overflows gave +inf; each raises, naming the sum
  that overflowed, in `aggregate_to_db` and `relative_power`. An infinite power under
  `nan_policy="propagate"` still gives +inf dB. Values are otherwise unchanged.
- **`network_topology` raises `TypeError` on a complex matrix (breaking).** It cast to float,
  keeping the real part with only a `ComplexWarning`, so a purely imaginary coupling counted as
  no edge. Pass `np.abs(matrix)` to threshold the magnitude. `network_connectivity` already takes
  the magnitude first and is unchanged.
- **`VFlipResult.crossover_depth_um` is always shaft rank times contact spacing (breaking).**
  When the geometry's z varied along the shaft it was the absolute z, which carries the
  table's origin and direction, while `label_layers(depth_range_um=)` compares against rank
  times pitch; on a shaft whose z falls with depth the two ran in opposite directions. It now
  is `crossover_contact` times the spacing, from the first contact of `linear_order`, whose
  direction follows the table's row order. Callers whose z varied along the shaft and who read
  it as absolute z read `crossover_z_um` instead. With a `probe_geometry`, `vflip` and
  `vflip_from_lfp` raise `ValueError` when `contact_spacing` disagrees with the geometry's
  `nominal_pitch`, which `label_layers` measures depth with: `contact_spacing=50` on a 100 um
  geometry gave a depth that selected half the contacts through `depth_range_um`.
- **`classify_response_significance` tests the response against its baseline (breaking).**
  `pvalue` is the two-sided conditional binomial test of two Poisson counts: with `K_r`
  response and `K_b` baseline spikes summed over trials, `K_r` is Binomial(`K_r + K_b`,
  `d_r / (d_r + d_b)`) under equal rates, where `d_r` and `d_b` are the window lengths
  (`scipy.stats.binomtest`). It is exact for windows of different lengths, assumes Poisson
  firing within a trial, and falls as trials accumulate. It was a normal p derived from
  `response_zscore`, an effect size whose p did not depend on the trial count. Significance now
  needs `p < alpha` (new keyword-only `alpha=0.05`, strict) as well as
  `|response_zscore| >= zscore_threshold`, so a unit with few trials that passed the z cutoff
  alone can be classified 'none'. A dict without the per-trial counts and window lengths, such
  as one built by hand from summary values, is 'undefined' with a `UserWarning` and a NaN
  `pvalue`; pass the dict `compute_response_metrics` returns. A NaN count is 'undefined';
  count arrays that are not 1-D or differ in shape, a negative or fractional count, and a
  window length that is not positive and finite raise `ValueError`.
- `jrsa`: a nonzero `lag` compares only the overlapping samples, x1[t] with x2[t - lag],
  dropping |lag| samples, instead of rolling x2 circularly, which paired each series' end with
  its start (on a trended series the realigning lag gave r well below 1). The null and bootstrap
  run on the shortened series; `execution['n_overlap']` records the samples used; |lag| >= n
  raises. Values at a nonzero lag change.
- **`jnwb.vis` laminar plots require `depth_unit=` (breaking).** `plot_spectrolaminar_map`,
  `plot_opposing_gradients` and `plot_csd` take a keyword-only `depth_unit` (`'mm'`, `'um'` or
  `'relative'`) with no default, label the depth axis from it, and raise `ValueError` for any
  other value. They used to infer the unit from the largest depth, so a 0 to 1.55 mm probe was
  labelled relative depth. Callers add `depth_unit=` to each call.
- **`jnwb.vis.plot_csd` requires `value_unit=` (breaking).** The colorbar read "CSD (mV/mm²)"
  by default, but `current_source_density_1d` returns A/m³ and `voltage_curvature_1d` returns
  V/m², so a default call mislabelled either input. `value_unit` is keyword-only with no
  default; the colorbar reads `value_unit` alone, or `"<colorbar_title> (<value_unit>)"` when
  `colorbar_title` names the quantity, and the hover text carries the unit. An empty or blank
  unit raises `ValueError`. `title` now defaults to None (no panel title) instead of "Current
  Source Density (CSD)", which was wrong for a curvature input. Callers add `value_unit=`, for
  example `"A/m³"` or `"V/m²"`, and pass `title=` to keep a panel title.
- **`jnwb.vis.plot_sorted_heatmap` requires `value_unit=` (breaking).** The colorbar read
  "Rate (Δz)" by default whatever `rate_matrix` held. `value_unit` is keyword-only with no
  default and follows `plot_csd`: the colorbar reads `value_unit`, or
  `"<colorbar_title> (<value_unit>)"`; the hover text carries the unit; an empty or blank unit
  raises `ValueError`. `colorbar_title` now defaults to None and names only the quantity.
  Callers add `value_unit=` (for example `"spikes/s"` or `"z"`) and replace a full label such
  as `colorbar_title="Rate (z)"` with `colorbar_title="Rate", value_unit="z"`.
- **`jnwb.vis.plot_hierarchy_regression` requires `y_label=` (breaking).** The y axis read
  "Prevalence (%)" by default, and the hover appended "%" to every value, although `values`
  may be onset latency. `y_label` is now keyword-only with no default, an empty or blank label
  raises `ValueError`, and the hover shows the value without a unit. `y_label` moved behind
  `title`, `marker_color` and `fit_line_color`: a call that passed it positionally, as the
  thirteenth argument, passes it by keyword instead. Callers add `y_label=`, for example
  `"Prevalence (%)"` or `"Onset latency (ms)"`.
- **`jnwb.vis.plot_spectrolaminar_map` refuses values outside [0, 1] (breaking).** The colour
  scale is fixed to [0, 1], so a larger or negative value was clipped to the end of the scale
  without a word; `jnwb.relative_power` returns an unbounded ratio to baseline, or dB. A finite
  value of `rel_power` below 0 or above 1 now raises `ValueError`; non-finite values are still
  drawn as gaps. Callers pass fractions in [0, 1], for example power normalised across
  contacts per frequency.
- **`compress_fp32` and `jnwb.compression.convert` require `select=` (breaking).** `select=` is
  keyword-only with no default in both; a call that omits it, or passes `select=None`, raises
  `TypeError` before anything is written. The anchored LFP/MUAE preset and its `FutureWarning`
  are removed. Callers name the floating-point datasets to cast, or pass `select=[]` to cast
  nothing, which is also the route for a file whose LFP is stored as integers. A refused
  `select=` no longer leaves the destination's new parent directory behind.
- **`jnwb.compression.verify_roundtrip` requires `cast=` (breaking).** `cast=` is keyword-only
  with no default and names the datasets to check, normally `stats["cast_paths"]`. Without it
  the function checked the LFP/MUAE preset, reporting arrays a `select=` call never cast.
- **`jnwb.compression.verify_roundtrip` requires `collapsed=` (breaking).** `collapsed=` is
  keyword-only with no default, normally `stats["timestamps_collapsed"]`. Without it the
  function checked two hardcoded groups and reported `ok=True` with the collapsed timestamps
  never checked. A `cast=` path absent from the destination is now a failed check; it was
  skipped. Direct callers pass `collapsed=` by keyword; `compress_fp32` is unchanged.
- **`TFRAnalyzer.compare_conditions` counts only locations with a p-value (breaking).**
  `n_tests` and the denominator of `fraction_significant_uncorrected` now use the family the FDR
  correction already used, so a location constant in both conditions no longer counts as a test
  that could not pass. With no such location the fraction is NaN; it was 0.0.
- **`PopulationAnalyzer.population_trajectory` returns `n_components` components (breaking).**
  A requested component beyond `min(n_time_bins, n_units)` is a NaN column of `projection`, a
  NaN row of `components` and NaN variances, as in `compute_population_trajectory`; the arrays
  were shorter than `n_components`.
- **`PopulationAnalyzer.population_trajectory` has no variances without variance (breaking).**
  With no total variance `explained_variance` and `explained_variance_ratio` are NaN; both were
  zeros. `explained_variance_ratio` is now `S**2 / sum(S**2)`, as in
  `compute_population_trajectory`, which can change its last digit.
- **The sdist no longer ships `AGENTS.md` or the `jnwb-fact-action` skill.** Both describe how
  the jnwb repository itself is changed rather than how jnwb is used. The sdist carries the nine
  analysis skills under `skills/`; `jnwb.SKILLS_URL` names them for an installed copy. The wheel
  is unchanged.
- **`xflip` partitions by a new objective (cuts can change on existing data).** The
  contiguous search maximises the sum over blocks of S²/P, a block's within-block
  correlation sum squared over its pair count: the block-constant least-squares fit. It
  replaces the sum of each within-block correlation minus the probe-wide mean, which favoured
  blocks of equal size: beside an uncorrelated background it cut toward the middle of the
  probe, and the surrogate test could still accept that cut (3 of 10 seeds with 16 contacts
  and a block of 6). Squaring discards sign, so a block of negative mean correlation scores as
  a positive one. The calibration record is regenerated: power on every alternative is
  unchanged at 1.000, and the smooth-gradient null accepts 1 of 30 seeds (0.033) where it
  accepted none, below `alpha=0.05`.
- **`xflip(n_blocks=None)` chooses the block count by the smallest surrogate p, and its p
  accounts for the choice (the count and p can change on existing data).** Each count from 2
  to `min(4, n_channels // min_block_size)` is partitioned and tested against the same
  surrogates, the count with the smallest p is reported, and the omnibus p repeats that
  choice on every surrogate. It took the count with the highest contrast and reported that
  count's p as though it had been fixed in advance, so the p was too small: at 200
  surrogates, 0.105 of AR(1) null seeds and 0.074 of white-noise seeds had p at or below
  0.05. The calibration record now carries these null rows over 1000 seeds and 200
  surrogates on both `contiguous` paths: with the choice repeated, AR(1) 0.060 and 0.054
  against 0.054 and 0.061 at a fixed count of 2, and white noise 0.030 and 0.046 against
  0.040 and 0.048. Ties at the smallest p go to the count whose contrast lies the most
  surrogate standard deviations above the surrogate mean, then to the smallest count. When a
  count's partition beats every surrogate, every count sits at the floor and the
  standardised contrast decides; the omnibus p does not depend on the tie-break. The
  per-boundary p-values are the chosen count's own. On 16 to 18 contacts at a within-block
  correlation of 0.8, the true count of blocks of 4, 6 or 8 is recovered in 10 of 10 seeds at
  a shared background correlation up to 0.3; at 0.5, three blocks of 6 are cut into four and
  rejected. A call costs about one fixed-count call at each candidate count. Calls with an
  integer `n_blocks` return the same values as before.
- `xflip` accepts only an int, a Generator or None; bool, SeedSequence, bit generators, lists and
  RandomState now raise TypeError (a float already did).
- **`zflip` accepts only an int, a Generator or None as `rng` (breaking).** A bool, SeedSequence,
  bit generator, list or RandomState now raises `TypeError` (a float already did). An int, a
  Generator and None draw the same streams as before.
- **`zflip` reports no delay without surrogates (behaviour change).** A pair's delay is
  identifiable only against its own surrogate null, so with `n_surrogates=0`, or with a
  constant or linear-in-time contact, which skips the surrogates, every entry of
  `adjacent_identifiable` is False, `adjacent_delays_s` and `tau_per_channel_s` are NaN,
  `delay_identifiable` is False and `directionality` is `"unidentifiable"`. `rejection_reason`
  says surrogates are needed to establish a delay. Before, `n_surrogates=0` still reported a
  delay while `accepted` was False; pass `n_surrogates` to obtain one.
- **`jrsa` accepts only an int, a Generator or None as `rng` (breaking).** A bool, SeedSequence,
  bit generator, list or RandomState now raises `TypeError`, under every spelling of the
  argument. An int, a Generator and None draw the same streams as before.
- **`cross_modal_comparison` accepts only an int, a Generator or None as `rng` (breaking).** A
  bool, SeedSequence, bit generator, list or RandomState now raises `TypeError` when the lag
  sweep draws its null. An int, a Generator and None draw the same streams as before.
- **`shuffle_r2_ci` accepts only an int, a Generator or None as `rng` (breaking).** A bool,
  SeedSequence, bit generator, list or RandomState now raises `TypeError`. An int, a Generator
  and None draw the same streams as before.
- **The `jnwb.testing.synth` builders accept only an int, a Generator or None as `rng`
  (breaking).** `synth_white_noise`, `synth_ar_noise`, `synth_periodic_response`,
  `synth_correlation_blocks`, `synth_phase_gradient`, `synth_unequal_groups` and
  `synth_laminar_motif` raise `TypeError` for a bool, SeedSequence, bit generator, list or
  RandomState. An int, a Generator and None give the same data as before.
- **`jnwb.testing.build_canonical_tutorial_nwb(seed=)` and `build_synth_nwb` with
  `SynthNWBBuildOptions(seed=)` accept only an int, a Generator or None as `seed`
  (breaking).** A bool, SeedSequence, bit generator, list or RandomState now raises
  `TypeError`. An int and a Generator build the same file as before.
- `permute_labels`, `shuffle_pvalue_paired`, `shuffle_pvalue_unpaired` and
  `paired_fire_prob_test` accept an int seed or None as `rng` as well as a Generator. An int
  seed draws the stream `np.random.default_rng(seed)` draws, and a Generator is advanced as
  before. `rng` is still required. A float, bool, SeedSequence or list raises `TypeError`
  where the last three raised `AttributeError`.
- **`shuffle_pvalue_paired` and `shuffle_pvalue_unpaired` refuse a legacy
  `np.random.RandomState` (breaking).** They called its `choice` and `shuffle` methods, so it
  ran; it now raises `TypeError`. Pass `np.random.default_rng(seed)` or the int seed.
- `build_permutation_plan` accepts a Generator or None as `rng` as well as an int. Either gives
  one int base seed, drawn from the Generator or from a fresh `default_rng()`, which the plan
  returns as `seed`; passing it back as `rng` reproduces the manifest. An int is the base
  seed as before. `rng` is still required.
- `xflip`'s contiguous partition search scores every split point of a block count as one array.
  On a given objective the cuts are identical to a scalar loop's. The search is 3 to 29 times faster from 32 to
  256 channels; a whole `xflip` call on 32 channels is about 1.3 times faster, because the
  surrogates and their correlation matrices dominate it.
- `unit_census_report`: the warning for a default call on a frame with a `layer` column and no
  `depth_class` is a `UserWarning`, not a `FutureWarning`. It says the census is not split by
  depth, that `layer` is not read, and that `enrich_units_dataframe` supplies `depth_class`.
- `granger(order="auto")` scores every candidate order on one sample, trimmed by the largest
  candidate, with the maximum-likelihood residual variance `RSS / N` (Lütkepohl 2005, section
  4.3). It used to divide by `N - k` and fit each order to its own sample, so candidates were
  compared on different data. Selected orders, and the values computed at them, can change;
  `granger_spectral(order="auto")` and `directed_connectivity`/`directed_network` with
  `method="granger"` select through the same path. A fixed `order` is unaffected.
- `transfer_entropy` numbers joint states through one integer key per row instead of a
  row-wise `np.unique`: 7 to 15 times faster on 4 to 12 trials, with identical values,
  p-values and surrogate statistics.
- `TFRAnalyzer.compare_conditions` reports a corrected count beside the uncorrected one. One
  t-test per location counts about 5% of locations on null data (796 of 16000 in a seeded
  run). `n_significant_uncorrected` and `fraction_significant_uncorrected` hold those values;
  `n_significant_fdr` counts locations whose Benjamini-Hochberg adjusted p-value, in the new
  `q_values` array from `fdr_correct` over the locations with a finite p, is below 0.05 (0 in
  the same run). `summary` names both counts.
- `PopulationAnalyzer.pie_chart_data` raises `ValueError` when a `criteria` key names a column
  the table does not have. The filter was skipped, so the counts covered every unit. It filters
  through `filter_by_criteria`; the counts for present columns are unchanged.
- `PopulationAnalyzer.network_connectivity` computes the graph through `network_topology` and
  so raises `ValueError` as it does, for a matrix that is not square 2-D, a NaN or Inf off the
  diagonal (it read as no edge) or a threshold that is not finite. Values for a valid matrix,
  complex ones included, are unchanged.
- `raster_psth` finds each trial's spikes by binary search on the sorted train instead of
  masking the whole train per onset: 0.44 s to 0.05 s at 200,000 spikes and 2,000 onsets, with
  byte-identical output under NumPy 2. Spike times are compared in float64; NumPy 1.x compared
  a float32 train in float32, so a spike within float32 rounding of a window edge can move.
- `enrich_units_dataframe` resolves and classifies each peak channel once, from one pass over the
  electrode table, instead of comparing against the whole table three times per unit: 4.5 s to
  0.13 s at 4,000 units and 1,536 electrodes, with identical output.
- `cluster_permutation_test` sums each cluster from one sort of the suprathreshold points
  instead of masking the whole map once per cluster, and a permutation draw builds no masks:
  20.0 s to 2.6 s on a 200 by 200 map with about 10,000 clusters and 20 permutations. Cluster
  statistics, p-values and `max_null_stats` are bitwise identical.

### Deprecated

- The meaning of `compute_population_trajectory`'s `explained_variance`. It is still one
  fraction for all kept components together, `np.nansum(explained_variance_ratio)`, and reading
  it emits a `FutureWarning`: in the next release the key carries each component's variance, as
  in scikit-learn and `PopulationAnalyzer.population_trajectory`. Read
  `explained_variance_ratio` or `explained_variance_per_component` instead. A copy made through
  `dict(...)`, iteration or JSON keeps the old value without a warning.
- `TFRAnalyzer.compare_conditions` keys `n_significant` and `fraction_significant`. They still
  read, as the uncorrected values, with a `DeprecationWarning`, and are no longer listed among
  the result's keys. They are removed in the next release.
- `spectral_tilt`'s key `exponent`. The log-log slope is now under `slope`, negative for a 1/f
  decay; `exponent` still reads the same value with a `DeprecationWarning` and is removed in the
  next release, so that `exponent` means the positive decay rate `aperiodic_fit` reports, which
  is `-slope`. `exponent` is no longer listed among the result's keys, so a copy made through
  `dict(...)`, iteration or JSON carries `slope` only.
- A `relative_power` baseline with fewer dimensions than `power`, other than a scalar. numpy
  aligns it with the trailing axes, so a `(n_freqs,)` baseline against `(n_freqs, n_times)` power
  divided along time. It is still broadcast, with a `FutureWarning`, and raises `ValueError` in
  the next release, as `aggregate_to_db` and `TFRAccumulator.add_trial` already do. Pass
  `baseline[:, None]` for a per-frequency baseline.

### Removed

- **The `layer` column of `enrich_units_dataframe` and `get_all_units_metadata` (breaking).**
  Deprecated in 0.2.6, it was an exact copy of `depth_class`; read `depth_class` instead. Code
  that reads `layer` from their output now raises `KeyError`. The `FutureWarning` about it is
  gone, and a `layer` column already on the input is returned unchanged, where the electrode
  path used to overwrite it with the depth class.
- **`JRSAResult.p[0]` and `JRSAResult.q[0]` on a single-lag result (breaking).** `p` and `q`
  are plain 0-d arrays like `value`, so `[0]` raises `IndexError` where it returned the scalar
  with a `FutureWarning`. Use `float(result.p)` or `result.p[()]`.
- **The refractory keys of `UnitAnalyzer.autocorrelogram` (breaking).** Deprecated in 0.2.6,
  `refractory_period_violation`, `is_single_unit`, `refr_count` and `baseline_count` are no
  longer returned, and the `FutureWarning` about them is gone; reading one raises `KeyError`.
  The result holds `acg`, `lag_times_ms` and `device_used`. The single-unit check is
  `UnitAnalyzer.quality_metrics`.

### Fixed

- Permutation and surrogate p-values count a null draw that reproduces the observed statistic
  as reaching it when the two agree to within 100 machine epsilons of the observed value, the
  width `scipy.stats.permutation_test` uses. A draw that swaps tied values sums the same terms
  in another order and can land an ulp short of the observed value; a bare comparison skipped
  it, so p came out too small. **p-values change on tied or repeated input**, and rise:
  `jrsa` with ties in `x1` (0.006 to 0.013 where the exact p is 0.05), `shuffle_r2_ci` with
  tied scores, `cross_modal_comparison` with periodic spikes, `cluster_permutation_test` when
  a row of X equals a row of Y, `granger`, `granger_spectral` and `phase_slope_index` when one
  signal's trials are identical, and `xflip` at a fixed `n_blocks`. Under `n_blocks=None`,
  `xflip` ranks every draw against the others with the same width before comparing the
  integer counts, which re-ranks the surrogates too, so a tied p can move either way (on
  ulp-tied draws over two counts, 0.892 fell to 0.838); it stays a valid p over the S + 1
  exchangeable draws. `transfer_entropy`,
  the band surrogates of `cross_area_coherence`, `zflip`, `paired_fire_prob_test`,
  `shuffle_pvalue_paired`,
  `shuffle_pvalue_unpaired`, `exact_sign_flip` and `StatisticalAnalysis.permutation_test` use
  the same rule; the mean-difference tests keep their existing width, which is wider. A
  statistic that cancels takes an absolute floor on the width: 100 eps for the `xflip`
  contrast; 100 eps for each `granger` and `granger_spectral` direction and band, whose value
  `log(var_r / var_f)` rounds at the scale of the variance ratio rather than its own, and
  100 eps times `max(1, |x_to_y|) + max(1, |y_to_x|)` for the `granger` net p; 100 eps times
  both directions' sum for the `transfer_entropy` net p; and 100 eps times the bin-pair count
  for `phase_slope_index`. With identical target trials and no coupling, `granger` gave
  p_x_to_y 0.0198 where the exact p is 1.0. One repeated X trial against Y trials that pair
  x + h with x - h makes every PSI zero in exact arithmetic; its p rose from 0.085 to 1.0,
  the exact p. Untied continuous input counts the same draws as before.
- `phase_slope_index` reports `z` and `sd` as NaN, the jackknife p as None and
  `ok_for_interpretation=False`, with a `RuntimeWarning`, when the leave-one-segment-out
  replicates agree to rounding. Identical segments (a periodic signal) with Y equal to X gave
  sd 8e-32, z -7.8e13, p 0.0 and `ok_for_interpretation=True`. The width is
  `8 * eps * n_segments * (n_bins - 1)`, twice the rounding bound of a replicate whose
  coherencies have magnitude at most 1.
- `zflip` reports a pair with a constant contact as not identifiable, with NaN
  `adjacent_delays_s` and `adjacent_linearity_r2`. The constant contact's spectrum is
  rounding residue whose phase can be linear in frequency, and such a pair was marked
  identifiable with a finite delay (R^2 0.997 and 0.11 s on a noiseless wave).
- `zflip` requires each adjacent pair's wPLI to be at least `min_wpli` for that pair's delay to
  be identifiable, so `accepted` now also depends on each pair's coupling, not only on
  `mean_wpli`. A weakly coupled pair with a linear phase entered the depth fit, and a
  well-coupled mean accepted the result; `rejection_reason` names such pairs.
- `zflip` takes `min_band_power_fraction=0.01`: a contact carrying less than that fraction of
  its power inside `freq_range`, read from the detrended segment spectra the phase slope
  uses, makes both of its adjacent pairs unidentifiable, and `rejection_reason` names it. A
  contact carrying only an out-of-band sinusoid passed the pair wPLI gate through window
  leakage (pair wPLI 0.16 to 0.31) and was accepted with a delay 10 to 13 times the true
  one. For the default band, a sinusoid from about 9.5 Hz up to the lower edge, and from the
  upper edge to about 38 Hz, i.e. within the main lobe of an edge bin, can carry 0.01 to 0.7
  of its power in the band and still pass.
- `zflip`'s delay, wPLI and surrogate null now come from an STFT whose segments are linearly
  detrended. Shared slow power leaked into the band through the window and biased the delay
  upward (a shared 2 Hz component at 30 SD by 12%, a 1 Hz one at 100 SD by 34%; now 1.3% and
  1.2%). Shared slow power also lowered the observed wPLI and, once each contact's phases
  were randomised, inflated the surrogate null, which could suppress significance (p 0.76,
  now 0.02, for a weak wave in noise with a shared 2 Hz component at 30 SD). Delays, wPLI
  values and p-values change for every input: by a small amount, unless it carries a DC
  offset, drift or slow power. Broadband background independent at each contact is not
  removed and can still bias the delay (about +7% for a 1/f^2 background three times the
  wave).
- `zflip` refuses a contact that is a straight line in time to within round-off as it
  refuses a constant one, and `rejection_reason` names it. The per-segment detrend reduced
  such a ramp to round-off residue, which passed the gates and was accepted with a delay five
  to six times the true one. A ramp built by cumulative summation leaves round-off that grows
  with its length; from about 32000 samples it can exceed the width and is measured rather
  than refused.
- `zflip` requires each adjacent pair's wPLI to be significant against its own
  phase-randomised surrogate null at `alpha` for that pair's delay to be identifiable. The
  pair nulls come from the surrogates the mean is already tested against, so no further
  random draws are made and `p_value` is unchanged. A contact carrying a signal independent
  of the others, such as a contact outside cortex or on a broken channel, can fit a linear
  phase (R^2 0.7 from 5 in-band bins) and reach pair wPLI 0.15, while the coupled pairs carry
  the mean past its test; on a 5-contact wave with one end contact replaced by independent
  noise, 7 in 100 recordings were accepted with a delay 3.2 to 5.3 times the true one, now 1
  in 100. Each pair is tested at `alpha` without a multiplicity correction. A record of 256
  samples is no longer accepted at the default band: its 3 in-band bins let about 10% of
  independent-phase surrogates tie a pair wPLI of 1.0, so no pair passes.
- `zflip` treats a delay gradient within round-off of zero as no gradient: identical contacts
  gave phase residue near 1e-21 s per contact, `delay_identifiable=True` and a direction.
- `zflip`'s `rejection_reason` says the phase-frequency gate failed only when a pair failed
  its linearity or unambiguous-interval check, and names a failed depth fit (cumulative delay
  not linear in contact index, or a zero gradient) on its own. It reported the phase gate for
  any non-identifiable delay, including one refused only for weak coupling.
- `granger`, `granger_spectral`, `phase_slope_index`, `transfer_entropy` and
  `cross_modal_comparison` given a `Generator` draw one child seed from it, run their
  surrogates on `default_rng(child)` and record the child as `surrogate_seed_entropy`, so
  passing it back as `rng` reproduces the p-values. The Generator was used in place and
  `surrogate_seed_entropy` was `None`, so the result alone could not reproduce p. The p-values
  for a given Generator change; an `int` seed or `None` draws what it drew before.
- `cross_modal_comparison` reports `surrogate_seed_entropy`, the seed of the circular-shift
  null behind `lag_corrected_pvalue`, and `None` when no lag sweep ran. With the default
  `rng=None` the seed was drawn and not reported.
- `jrsa` raises `ValueError` for an `adim` other than the default that does not name the axis
  its permutation null, `bootstrap` and `lag` act on (the last axis for the paired metrics,
  axis 0 for rsa, cka, rv, hsic, distance_correlation and procrustes). Those act on that axis
  whatever `adim` names, so `adim=0` with pearson returned the value and p of `adim=-1`. Without
  any of the three, every `adim` runs as before.
- `jrsa` reads a NumPy integer `adim`, alone or in a tuple, as that axis. `np.int64(0)` failed an
  `int` check and ran as `adim=-1`, so `window=(0, 5)` windowed the last axis instead of axis 0.
  An `adim` that is not an integer, a string, or a tuple or list of them, including
  `None`, a float and a bool, raises `TypeError`; it was read as `adim=-1`.
- `jrsa`'s docstring and the jrsa page state that at the default `adim=-1` the six axis-0
  metrics window the features while `lag` and the null act on the observations, and that
  `adim=0` windows the observations.
- `select_optimal_lag`, which `granger_causality(order='auto')` uses, scores every order on one
  sample, the targets left after trimming the largest candidate order, as `granger` does. Each
  order was scored on its own `n - p` targets; on 60-sample pairs that selected another order
  than the common-sample criteria in 53 of 200 cases.
- `UnitAnalyzer.quality_metrics` sorts the spike times first. Unsorted, a backward step was a
  negative interval counted as a refractory violation, and the first and last entries were read
  as the recording's span: a shuffled 500-spike train read 51% violations where the sorted one
  read 1%. A train that is not 1-D or holds a NaN or an infinity raises `ValueError`: a NaN read
  as a good single unit, an infinity raised `OverflowError` and a 2-D array was pooled into one
  train.
- `UnitAnalyzer.psth` counts a spike on either edge of `[pre, post]`. Subtracting the onset
  rounded it just outside the outer bin edges and the histogram dropped it: with a spike on each
  edge of 405 trials 0.7 s apart, 114 were lost at the left edge and 147 at the right. It now bins as
  `jnwb.viz.raster_psth` does, clipping each selected spike's relative time to the outer edges,
  with its right edge still inclusive. With no onsets it returns NaN rates where it raised.

- `jrsa` raises `ValueError` for a `reduction` key that names no axis of `adim`, and the
  message lists the axes that exist. The key was skipped, so the unreduced value came back while
  `parameters['reduction']` recorded the request: with `adim=(-3, -2)` the keys are `"axis_-3"`
  and `"axis_-2"`, and `{"axis_0": "mean"}` or `{0: "mean"}` reduced nothing.
- `jrsa`'s `mutual_information`, `granger_ssr_ftest`, `transfer_entropy_histogram_nats` and
  `phase_slope` estimators raise `ValueError` when the two inputs differ in shape. They paired
  the flattened samples by truncating the second input to the length of the first and returned
  a number. `jrsa` already refused the mismatch at its entry; matched inputs give the same values.
- `jrsa`: a `reduction` over axis 0 of `rsa`, `cka`, `rv`, `hsic`, `distance_correlation` or
  `procrustes` removes that axis, so the next axis becomes the observations. It kept the axis
  at length 1, which left one observation: averaging the trials of a `(trials, conditions,
  units)` input returned NaN for `cka` (0.69 on `x.mean(0)`) and raised for `rsa`. The value now
  equals the metric of `x.mean(0)`; `lag`, the null and `window` act on the reduced input, and
  a `window` on the removed axis raises `ValueError`. The paired metrics are unchanged.
- `raster_psth` counts every spike its window selects. The selection is in seconds and the
  binning in ms, and the conversion could round a selected spike just past an outer edge:
  onset 2.0 s and a spike at 1.9 s gave -100.00000000000009 ms against a first edge of -100, and
  the spike was dropped. Only such spikes move, into the first or last bin.
- `TFRAccumulator`: assigning `M2`, `sum_z`, `sum_unit_z` or `sum_ratio` casts to float64 or
  complex128, as assigning `mean` already did, so a summary read back from `write`'s
  float32/complex64 datasets keeps accumulating at double precision. `add_trial` casts an
  integer `z` to complex128 before any state changes; it raised after the running mean had
  taken the trial.
- `TFRAccumulator`: assigning `n` stores an int64 copy of non-negative whole counts within
  int64, and raises `ValueError` for anything else.
  - `write` stores `n` as int32, and `merge` of two reloaded accumulators multiplied the counts
    in int32, which overflows from 46341 trials per cell and returned a wrong `M2` without an
    error.
  - Refused: a fraction (2.7 was stored as 2), NaN or inf, a negative count, a boolean (True was
    stored as 1), an unsigned value above the int64 maximum (`np.uint64(2**64 - 1)` wrapped to
    -1), and a larger integer or float, which raised `OverflowError` or wrapped. An object array
    is accepted only when every element is a non-negative Python int within int64; any other
    object array is refused (a float element such as 2.5 was cast to 2).
  - A whole float such as 3.0 is stored as the int64 3, and a non-negative integer is unchanged.
  - An int64 array was stored as the caller's own array, so writing to that array afterwards
    changed the accumulator's counts.
- `XFlipResult.boundaries` and `block_bounds` hold Python ints. They held NumPy int64 from the
  contiguous search, so `json.dumps` of `to_dict()` failed on them and on the `boundary_drops`
  keys.
- `jrsa`: a NumPy integer or 0-d array `lag` is one lag; it raised `TypeError`.
- `jrsa`: `lag` now shifts the observation axis (axis 0) for `rsa`, `cka`, `rv`,
  `hsic`, `distance_correlation` and `procrustes`. It used to roll the feature axis, which these
  metrics are invariant to, so every lag returned the lag-0 value. The lag axis of the paired metrics is unchanged.
- `cross_area_coherence`: when the CUDA path fails part-way through the surrogate null, the CPU
  fallback reuses the shifts already drawn, so p equals a CPU run under the same seed and a
  caller's generator advances once. Before, the fallback drew new shifts from the advanced
  generator.
- `jnwb.compression.verify_roundtrip` (and so `compress_fp32(verify=True)`) requires each cast
  dataset to equal `source.astype(float32)` exactly. It accepted any destination within an
  absolute 1e-3, so a zeroed destination passed at volt scale and a correct cast near 5e4, where
  the float32 spacing is 3.9e-3, failed.
- `jnwb.compression.verify_roundtrip` fails a cast dataset that is not float32 in the
  destination, whose shape differs from the source's, or that is absent from the source. It fails
  a collapsed timestamps group without `starting_time` in the destination or `timestamps` in the
  source; it skipped that group and could return `ok=True` with its timestamps never checked.
- `jrsa`: an input with no values left, from a zero-length axis under any `nan_policy` or from
  `nan_policy="omit"` dropping every sample because one condition is NaN throughout, raises
  `ValueError` naming the metric, and under `omit` that condition, for every metric. `hsic`,
  `mutual_information` and
  `transfer_entropy_histogram_nats` returned 0.0 computed from zero samples, six metrics
  returned NaN and five raised unrelated errors.
- `nested_cv_linear_svm(rng=None)` draws one seed from a fresh `numpy.random.default_rng()` for
  its folds, group order and `SVC`. It passed `None` to scikit-learn, which read and advanced
  NumPy's global `RandomState`. An int `rng` gives the same folds as before. A global
  `np.random.seed` no longer makes `rng=None` reproducible; pass an int.
- `compute_response_metrics` raises `ValueError` when either window's start is at or after its
  stop. A reversed window returned a negative spike count with a positive rate.
- `raster_psth` accepts a list of spike times; it raised an unrelated `TypeError`.
- MCP `prepare_signal_reference` returns the series' `conversion`, `offset`,
  `channel_conversion`, `unit`, `rate_hz`, `starting_time` or `timestamps_path`, `n_channels`,
  `layout`, `layout_basis` and `reader`, and its `access_hint` gives the physical-value formula and
  the sample times. Its hint told the caller to slice the stored `data` directly, which skips the
  scaling and the start time, and read the channel axis from which dimension was longer.
  `layout` is `"unknown"` unless the electrode region or the schema decides it. `reader` names
  `jnwb.acquisition_channel` only when the layout is known, the series has a finite constant
  rate, any `channel_conversion` has one factor per channel, and `jnwb.resolve_acquisition`
  accepts the series' path as its name; otherwise it is `None`. A file the resolver cannot open,
  such as HDF5 that is not NWB, still returns the reference, with no reader.
- `jnwb.bilinear`: the documentation no longer calls two-class `predict_proba` calibrated. It is
  sigmoid(D_1 - D_0) of two mirrored one-vs-rest scores, about sigmoid(2 D_1), and overconfident
  on held-out trials.
- Documentation figures 1, 3, 5, 7 and 10: no legend is drawn over data. A legend without a box
  had nothing between its text and the bars or traces under it on the transparent background, and
  figure 5's boxed legend hid the top of the cone-of-influence contour. Figure 10 shades the
  samples `repair_lfp_trials` replaced, not the injected window.
