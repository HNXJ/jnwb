# Changelog

All notable changes to `jnwb` will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-01

### Added
- **Core Signal & Spectral Primitives**:
  - `complex_tfr`: Complex Morlet wavelet transform with discrete $L_1$ amplitude normalization and Cone of Influence (COI) boundary validity masking.
  - `ComplexTFR`: Dataclass container providing `z`, `power`, `phase`, `amplitude`, `freqs`, `times`, and `coi_mask`.
  - `compute_psd`, `band_power`, `spectral_tilt`, `cross_area_coherence`, `imaginary_coherency`.
  - `phase_locking_value`, `bipolar_reference`, `laplacian_reference`.
- **Streaming & Accumulation**:
  - `TFRAccumulator`: Welford running variance, mean power, Inter-Trial Coherence (ITC), evoked power, and induced power.
  - `assert_mergeable`: Schema verification for merging streaming TFR datasets.
- **Spiking & Onset Dynamics**:
  - `raster_psth`, `compute_response_metrics`, `phase_locking_index`, `cross_correlation`.
  - `causal_exp_smooth`: Causal single-pole exponential filter with tau compensation.
  - `fit_exponential_onset`: Single-unit onset latency estimator with `bound_status` censoring detection.
- **Resampling Statistics & Hypothesis Testing**:
  - `StatisticalAnalysis`: `bootstrap_ci`, `paired_fire_prob_test`, `confirmatory_compare`.
  - `exploratory_compare`: Clean dual reporting of parametric and nonparametric metrics.
  - `permute_labels`: Label permutation with `'global'` and `'within_group'` support.
  - `fdr_correct`, `bonferroni_correct`.
- **Directed Connectivity & Information Theory**:
  - `granger`: Time-domain bivariate Granger causality with permutation surrogates.
  - `phase_slope_index`: Phase Slope Index with analytical standard error.
  - `transfer_entropy`: Bivariate Transfer Entropy with lag embedding.
- **Decoding & Population Dynamics**:
  - `nested_cv_linear_svm`: Nested cross-validated linear SVM classifier.
  - `compute_population_trajectory`, `time_resolved_trajectory`.
- **Artifact Detection & Repair**:
  - `channel_correlation_matrix`, `detect_flat_or_noisy_channels`, `detect_extreme_events`.
  - `repair_lfp_trials`: Outlier thresholding and cross-channel linear interpolation repair.
- **Anatomical Addressing & Ontology**:
  - `map_peak_channel_to_area`, `classify_layer_from_depth`.
- **Publication Graphics**:
  - `setup_vector_graphics`, `apply_tight_auto_axis`, `save_figure_suite`.
- **Packaging & CI**:
  - PEP 621 `pyproject.toml` with SPDX MIT license.
  - ReadTheDocs configuration (`.readthedocs.yaml`, `docs/conf.py`).
  - GitHub Actions CI workflow supporting Python 3.10 through 3.14.
  - Deterministic release gate (`scripts/release_gate.py`).
