# Changelog

All notable changes to `jnwb` will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-09-09

Fixes the blocker that made 0.1.1 uninstallable, corrects three defects in
`cross_area_coherence`, renames a path constant that misled every consumer, and removes
a class of silent GPU and import failures. 0.1.2 was never released.

### Breaking

- **`jnwb.paths.REPO_ROOT` is renamed `PACKAGE_ROOT`.** It resolves from `paths.py`'s own
  location, so in a consuming project it named the *jnwb* checkout, not the caller's
  repository, and the path was well-formed enough that nothing failed. One project had 41
  live files building inputs and outputs from it. `REPO_ROOT` still resolves and warns;
  it is removed in 0.2.0. `describe()` reports both keys for this release. To get your own
  root, anchor to your own file.
- **`cross_area_coherence` returns different p-values.** The surrogate draws changed, and
  long signals now draw 50 surrogates instead of 10. Receipts quoting a p-value from this
  function will not reproduce. Pass `n_surrogates=10` for the previous cost.
- **`gpu_pca(device="cuda")` on a machine without CUDA** now computes in float64 NumPy
  rather than float32 torch-on-CPU, and warns. Previously "cpu" meant two different
  precisions depending on which device string you passed.
- **An unrecognised `device` string raises `ValueError`** instead of falling through to
  the CPU unannounced.

### Fixed

- **`requires-python` upper pin (JNWB-001).** 0.1.1 declared `>=3.12, <3.13`, so
  `pip install jnwb==0.1.1` failed on every current interpreter and silently resolved
  users to 0.1.0 -- older code than they asked for. jnwb is a pure-Python `py3-none-any`
  wheel with no ABI reason for a ceiling. Declared support is now `>=3.12` with no upper
  bound, classifiers cover 3.12/3.13/3.14, and CI tests the floor and the newest declared
  version.
- **`cross_area_coherence` surrogate null was unseedable (JNWB-003).** The generator was a
  hardcoded `default_rng(42)` with no parameter, so every caller received the same 50
  surrogates and no seed could be recorded. Adds `rng=`, and returns
  `surrogate_seed_entropy` (`None` when the caller supplied the generator).
- **`cross_area_coherence` could mix estimators inside one null (JNWB-004).** The GPU path
  sat inside the surrogate loop behind a per-iteration `except Exception`, so an
  intermittent failure produced a null assembled from two estimators with nothing logged.
  The device is resolved once; a failure discards partial work and recomputes the observed
  value and the whole null on CPU. The result reports `device_used`.
- **Surrogate count depended on input length (JNWB-005).** `n_surr` dropped from 50 to 10
  above 50,000 samples, making the smallest attainable p-value 1/11 = 0.0909 rather than
  1/51 = 0.0196. At 1 kHz that is 50 s of data, so a caller testing at alpha = 0.05 could
  not reject on a long recording and the return value said nothing. Adds `n_surrogates`
  and returns `n_surrogates_used` and `p_value_floor`.
- **Docstring named the wrong surrogate (JNWB-006).** A circular shift was described as
  phase randomization. Those are different null hypotheses.
- **`jnwb.paths.get_path()` was documented but never existed.** The example now calls
  `nwb_dir()`.

### Added

- **`n_jobs` on `cluster_permutation_test` and `cross_area_coherence`.** Results are
  identical for any `n_jobs`: each iteration is seeded from the caller's generator before
  the loop starts, so worker count cannot change a number. Default is 1 everywhere except
  `jrsa`, which keeps `-1`. Work is dispatched in chunks -- one task per iteration measured
  0.03x, i.e. slower than serial, because process startup dwarfed a 1 ms permutation.
  Chunked: 4.51x on 2000 permutations, 3.08x on 1000 surrogates.
- **Import-shadowing gate.** The editable install writes a `.pth` holding the repository
  root, so any top-level package beside `jnwb/` is importable ahead of a consumer's own
  package of that name, from any working directory (JNWB-002: 88 of 190 importing files in
  one project loaded the wrong copy, disagreeing on an anatomical label, with no error).
  A gate now rejects unowned root packages, and `docs/install.md` documents the hazard and
  the `editable_mode=strict` install.
- **Agent definitions are tracked** under `artifacts/agents/`. They were in a gitignored
  `.claude/agents/`, so a fresh clone got none of them. A root `.claude/` now fails the gate.
- **New logo** in the README, docs site, and favicon.

### Changed

- **Gate numbering is canonical.** "Gate 9" named two different gates, and "Gate 2",
  "Gate 3" and "Gate 6" were each used twice, so a gate report citing a number was
  ambiguous. Numbers are now the position in `run_full_preflight()`, checked by a test.
- **`check_python_target_consistency` is now `check_python_floor_consistency`.** The old
  gate asserted "3.12 is the sole targeted version" -- the policy that produced JNWB-001 --
  and accepted the upper pin that broke the release. It now asserts that declared support,
  classifiers and CI agree, and rejects any upper bound.
- **One GPU probe.** Fifteen call sites across seven modules each carried their own, some
  treating a bare `import cupy` as proof of a device. CuPy imports fine with no driver, so
  those sites disagreed about the same machine. `jnwb/_backend.py` decides once, and warns
  whenever a requested accelerator cannot be delivered.
- **Sphinx removed.** It built the same markdown a second way and was never published;
  Read the Docs builds mkdocs. `mkdocs build --strict` remains the gate. Removes
  `docs/conf.py`, `docs/_static/`, and three documentation dependencies.
- **One `AGENTS.md`.** The root file and `artifacts/AGENTS.md` were near-duplicates that
  had drifted apart. The root file is jnwb-scoped and carries a tool inventory.
- **Skill counts removed.** `skills/jnwb/SKILL.md` claimed 101 exports against a live 111
  and 446+ tests against 527, and advertised `n_jobs` on functions that lacked it. Counts
  are replaced by the commands that check them, enforced by a test.
- **Thinner repository root.** The root allowlist is split into tracked-source and
  ephemeral directories, and no longer permits `omission` -- the one entry that
  contradicted the import-shadowing gate.

## [0.1.1] - 2026-09-07

### Added
- **Power & Logarithmic Decibel Aggregation**:
  - `aggregate_to_db`: Core statistical primitive to compute arithmetic mean raw power across trials/channels before logarithmic transformation ($10 \log_{10} \mathbb{E}[P]$), guarding against Jensen's inequality bias. Callers must name the estimand (`how="mean_of_ratios"` or `"ratio_of_means"`); geometric-mean aggregation is rejected because it is mean-of-decibels.
- **Landmark electrophysiology primitives**:
  - `compute_multitaper_psd`: DPSS multitaper PSD (Thomson 1982) with one-sided scaling that preserves Parseval variance.
  - `pairwise_phase_consistency`: Vinck et al. (2010) unbiased phase-synchronization estimator, independent of spike count.
  - `gaussian_smooth_rate`: Acausal Gaussian PSTH smoothing, distinct from causal exponential smoothing.
  - `voltage_curvature_1d` / `current_source_density_1d`: Discrete second spatial derivative in V/m², and physical 1D CSD in A/m³ with required conductivity (S/m).
  - `cluster_permutation_test`: Maris & Oostenveld (2007) cluster FWER control with paired sign-flip, independent label shuffle, and within-group exchangeability.
  - SOS Butterworth `bandpass_filter` and IIR `notch_filter` with explicit zero-phase vs causal modes.
- **Documentation & Figures**:
  - 10 deterministic executable scientific figures (`docs/assets/figures/`) generated directly by `docs/generate_figures.py` using public jnwb APIs.
  - `docs/common_mistakes.md`: Guide to common electrophysiology pitfalls (Jensen's inequality, right-open bins, exchangeability, CV leakage, channel ID vs. index, causality vs. predictability, PSI bandwidth, causal filter delay).

### Changed
- **Boundary Semantics**:
  - `fires_in_window` and `rate_in_window` in `jnwb/statistics.py`: Enforced strict right-open intervals $[t_0, t_1)$ using left-side binary searches at both boundaries, preventing double-counting across contiguous time bins.
  - `compute_response_metrics` in `jnwb/spiking.py`: Enforced strict right-open intervals $[t_0, t_1)$ for baseline and response windows.
  - `bin_spikes` in `jnwb/connectivity.py`: Explicit right-open binning semantics $B_k = [t_0 + k\Delta, t_0 + (k+1)\Delta)$ with exact centers $c_k = t_0 + (k + 1/2)\Delta$.
- **Path Resolution & Packaging**:
  - `jnwb/paths.py`: Repaired `outputs_dir()` to avoid resolving into `site-packages` when installed, prioritizing explicit overrides and `JNWB_OUTPUTS_DIR` environment variable with clean local fallback.
  - `pyproject.toml`: Conformed license metadata to PEP 621 table specification (`license = { text = "MIT" }`).
- **Public return keys**:
  - `paired_fire_prob_test` reports the paired control rate as `p_fire_baseline` (replacing the dataset-specific `p_fire_pre_omission_baseline`).

### Fixed
- **Addressing & Indexing**:
  - `jnwb/addressing.py`: Repaired channel ID vs. DataFrame integer row index conflation in `_resolve_electrode_row` and multi-area probe partitioning.
- **Numerical Safety**:
  - `jnwb/spectral.py`: Repaired `spectral_tilt` numerical stability, guarding against flat/zero PSDs and non-positive powers.
- **Cluster permutation**:
  - `cluster_permutation_test` reported each observed cluster twice (copy-paste duplicate append). Tests now assert unique cluster masks.
- **Release verification**:
  - CI no longer hardcodes a stale public-export count (was 101; live surface is 111).
  - Local `scripts/release_gate.py` now uses a venv without `--system-site-packages` and installs the wheel with declared dependencies.
  - `scripts/harness_gate.py` puts the repository root on `sys.path` before importing `jnwb`, so documentation completeness is checked against the candidate rather than a leftover site-packages install.

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
