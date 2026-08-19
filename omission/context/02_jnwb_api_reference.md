# 02 — jnwb API Reference

Generated 2026-08-17 by repo-wide documentation audit, covering all 44 `.py` files under
`jnwb/`. `import jnwb as oa` — v1.0.0, `__status__="Stable - Public API Frozen"` (note:
`__release_date__` reads 2026-06-25 while the module docstring says 2025-06-24 — inconsistent
metadata, flagged in [09_conflicts_and_flagged_discrepancies.md](09_conflicts_and_flagged_discrepancies.md)).

**Import-time side effect**: `jnwb/__init__.py` monkeypatches
`hdmf.build.manager.BuildManager.construct` (lines 58-125) to repair known builder anomalies on
problem sessions (mostly V182o) — fixes 1-elem numpy byte-string attrs, injects a missing
`session_description`, fixes the `units` table's `colnames`, fixes VectorIndex anomalies on
`waveform_mean_index`/`spike_amplitudes_index`. Wrapped in bare `try/except: pass` — failures at
import time are silently swallowed.

## What's exported vs. what needs a direct import

`__all__` exposes ~140 names in four groups: the frozen v1.0.0 ontology/factory layer, `jrsa`,
and the much larger "legacy API" (`read`, `batch_read`, `OmissionSession`, the four canonical
analyzer classes, `functions.py`'s 20 canonical functions, connectivity, unit_classification,
decoding, trajectory, `generate_report`, analog loaders).

**Not exported — import as `jnwb.<module>` directly**: `unit_inclusion` (S1 fire-probability
criterion), `onset_fitting`, `permutation`, `trial_ontology`, `omission_identity`,
`structured_identity`/`structured_identity_m2a`, `artifact_detection`, `artifact_repair`,
`bilinear`, `nam`, `gpu_pca`, `mcp_server`.

`read(nwb_path, context='omission_glo_passive') -> OmissionSession` — main entry point.
`batch_read(nwb_dir, pattern='*.nwb', context=...) -> List[OmissionSession]` — logs and skips
files that fail to load, does not raise.

## `OmissionSession` (`jnwb/session.py`, 1029 lines)

See [01_data_topology_and_corpus.md](01_data_topology_and_corpus.md) for full method-by-method
detail (condition maps, identity footgun, TFR filename/array contract, timing invariant). Summary
of the object surface: `get_units`, `get_electrodes`, `get_epochs`, `get_trial_onsets`,
`get_spike_times`, `find_single_units`, `channel_unit_mapping`, `lfp_channel_areas`,
`tfr_from_preprocessed`, `trial_averaged_plot`, `channel_averaged_plot`, `spectrolaminar_motif`,
`plot_tfr`, `raster_suite`, `lfp_tfr_trace_suite_omission`, `lfp_tfr_trace_correlation`,
`pie_charts`, `info`, `summary`.

## `jnwb/paths.py` (217 lines)

Central path resolution — see doc01 for the full table. Always call `jnwb.paths.describe()`
after any drive remap before trusting any other path in the package.

## Classification pipelines

Full detail in [03_classification_pipelines.md](03_classification_pipelines.md). Three
independent classifiers live in the package simultaneously — always name which one produced a
given count:

1. **`jnwb/unit_classification.py`** (852 lines) — canonical shuffle-controlled S+/S−/O+/O++
   classifier. `ClassificationConfig` (seed=42, n_shuffles=2000, alpha=0.05,
   alpha_omission=0.01, min_trials=8, effect-size floors incl.
   `min_baseline_for_s_minus_hz=3.5`). `OPlusPlusTemplateConfig` (min_mean_correlation=0.60 —
   **this is the module's own default; fig03 overrides it to 0.65 with an area restriction, see
   doc05**). Key functions: `classify_unit`, `_assign_labels`, `classify_session_units`,
   `classify_all_nwbs`, `append_session_to_grand_table`.
2. **`jnwb/unit_inclusion.py`** (330 lines, NOT exported) — S1's new fire-probability inclusion
   criterion, additive alongside (1), not a replacement of it. `InclusionConfig` (seed=42,
   n_shuffles=2000, n_bootstrap=2000). `STABLE_CRITERION_VERSION = "presence_ks_snr_v2"`.
   Documents two prior bugs it fixes in its own docstring: the archived template classifier's
   fx-zero-weight template, and a first-pass duration-mismatched baseline window that inflated
   inclusion to 73.7% before being fixed (duration-matched, v2).
3. **`jnwb/spiking.py::classify_omission_response`** — an older, simpler flat-p<0.05 (not FDR,
   not shuffle-controlled) stimulus-vs-omission classifier, also exported from `__init__.py`
   alongside (1). Picking the wrong one silently produces a different, uncorrected count.

## Signal processing

Full detail in [04_signal_processing_tfr_lfp.md](04_signal_processing_tfr_lfp.md).

- **`jnwb/spectral.py`** (648 lines) — `to_db` (single canonical power→dB conversion point,
  "log last"), `harmonic_analysis`, `cross_area_coherence` (2026-08-04 intentional band-default
  change to `connectivity.CANONICAL_BANDS`), `spectral_tilt`, `band_power`,
  `imaginary_coherency`, `bipolar_reference`, `laplacian_reference`.
- **`jnwb/connectivity.py`** (2022 lines) — legacy dict-returning MI/Granger functions plus the
  2026-06-30 modality-agnostic `DirectedResult` layer (`granger`, `granger_spectral`,
  `phase_slope_index`, `transfer_entropy`, `directed_connectivity`, `directed_network`). Short
  aliases `gc`/`sgc`/`psi`/`te`. `CANONICAL_BANDS` — the project's "settled" band table.
- **`jnwb/analyzers.py`** (688 lines) — `TFRAnalyzer`, `UnitAnalyzer`, `PopulationAnalyzer`. Has
  its own 7-band `BANDS` dict, non-identical to `connectivity.CANONICAL_BANDS` (see band
  fragmentation below).

## Statistics engine — `jnwb/statistics.py` (599 lines)

`StatisticalAnalysis` — three layers: exploratory (dual parametric+nonparametric, raw p-values,
not confirmatory), confirmatory (`confirmatory_compare`, requires an explicit hypothesis string,
BH q-values from the two dual-test p-values as a minimal family), legacy (`compare_groups`,
`compare_multiple_groups`, `correlate` — DeprecationWarning on `fdr_pval_*` keys, which are NOT
actually FDR-adjusted despite the name). Module-level `clopper_pearson(k, n, alpha=0.05)` —
promoted from 6 duplicated implementations; every proportion on this project uses this, never a
bootstrap. `coef_rows` flattens a fitted (Mixed)LM coefficient table.

## Visualization — `jnwb/viz.py` (1434 lines) and `jnwb/report.py` (940 lines)

`viz.py` sets global matplotlib rcParams at import time (`svg.fonttype=none`, font family,
axes styling) — a real process-wide side effect of `import jnwb.viz`. Publication raster/TFR
suites: `raster_suite_omission`, `lfp_tfr_trace_suite_omission`, `lfp_tfr_trace_correlation`
(FDR-insignificant correlations zeroed), `plot_granger_network_plotly`.

**`report.py` — confirmed defect, HIGH severity** (see doc09): `generate_report`'s
waveform/network sections **fabricate synthetic data presented as real analysis**:
- Firing rates for "fast-spiking" vs "regular-spiking" units are drawn from
  `np.random.exponential`, not measured — then run through a real Mann-Whitney test whose
  p-value is printed on the figure as if it reflected real data.
- The "Bivariate Granger Causality Directed Network" panel calls **`np.random.seed(42)`
  (global, process-wide RNG mutation — the only global-seed call found anywhere in `jnwb/`)**,
  then draws `p_values_net.append(np.random.uniform(0, 0.1))` for every directed area-pair edge
  — fabricated p-values, FDR-corrected and rendered as if real connectivity findings.

This directly violates the "no silent science" principle documented elsewhere in the same
package (`session.plot_tfr`'s explicit `status="missing_tfr"` refusal to fabricate) and CLAUDE.md
tripwire #1 (no empirical value in any output not computed from data). `generate_report` should
not be trusted or cited for its network/waveform panels until fixed; not fixed by this audit
(scope was documentation, not code repair) — flagged for Hamm's decision in doc09.

## RNG discipline across the package

| Discipline | Location |
|---|---|
| **Best practice** — explicit `Generator`, spawns independent child stream per unit | `unit_classification.classify_session_units` |
| **Good** — explicit rng param, threaded throughout | `unit_inclusion.py`, `permutation.permute_labels` (raises `TypeError` if `rng` isn't an explicit `Generator` — no default at all), `connectivity.granger(seed=0)`, `jrsa.py`'s permutation/bootstrap helpers |
| **Weaker** — local but hardcoded/unparameterized `np.random.default_rng(42)` inline | `statistics.bootstrap_ci`/`permutation_test` (every call across the whole codebase draws the identical sequence), `spectral.cross_area_coherence`'s surrogate test, `viz.resample_onsets(random_state=42)` (at least a real parameter) |
| **CONFIRMED GLOBAL SEEDING — the one real issue** | `report.py`'s `generate_report`, bare `np.random.seed(42)` (see above) |

`jnwb.permutation` (71 lines, not exported) was added 2026-08-10 specifically to fix an
exchangeability bug: `omission_identity.decode_identity_cycle_deconfound` used grouped
leave-one-cycle-out CV for its observed statistic but an ungrouped shuffle for its null.
`tests/test_permutation_lint.py` greps decoding-relevant modules and fails if a bare
`rng.permutation(y)` reappears outside this module's `scheme="global"` path.

## Band-definition fragmentation — four non-identical tables, not one canonical set

| Table | Edges (Hz) |
|---|---|
| `connectivity.CANONICAL_BANDS` — the "settled" table per CLAUDE.md | theta 4-8, alpha 8-14, beta 14-30, low_gamma 30-50, high_gamma 50-80 |
| `analyzers.TFRAnalyzer.BANDS` | delta 1-4, theta 4-8, alpha 8-15, beta 15-30, low_gamma 30-60, high_gamma 60-120, broadband 1-150 |
| `omission_identity.LFP_BANDS` | theta 4-8, alpha 8-14, beta 14-30, gamma 30-80 (single combined gamma, no split) |
| `artifact_repair.DEFAULT_BANDS` | keys embed their own range in the string (e.g. `"Theta(4-8Hz)"`), own naming convention entirely |

`spectral.py` imports `connectivity.CANONICAL_BANDS` directly (no duplicate) and is the one
module confirmed not to add a fifth table. See doc09 for the flagged recommendation.

## Identity-decoding and GLMM engine — `jnwb/omission_identity.py` (712 lines, not exported)

`OMISSION_IDENTITY_CONDITIONS` — per-slot (p2/p3/p4) A/B/R condition/onset/end. **Documented bug
fix (2026-08-06)**: p4's A/B labels were originally swapped (AAAX's parent is AAAB, so omitting
p4 hides a B, not an A — was backwards); every p4-specific number computed before this fix is
unreliable (p2/p3 unaffected). `decode_identity_cycle_deconfound` is the function whose null-
construction bug motivated `jnwb.permutation`'s creation (now fixed, uses
`permute_labels(scheme="within_group")`). `LFP_BANDS` here is the third band table above.

## `functions.py` — "20 Canonical Functions" (845 lines)

Grouped: TFR (1-5: `tfr_trial_average`, `tfr_compare_conditions`, `tfr_correlate_areas`,
`tfr_spectrolaminar`, `tfr_permutation_test`), Raster/PSTH (6-8: `raster_plot`, `psth_analysis`,
`autocorrelogram`), Unit finding (9-11), Population (12-15: `pie_charts`,
`compare_populations`, `population_by_area`, `network_connectivity`), Batch (16-18:
`units_across_sessions`, `lfp_channel_areas`, `summary_report`), Advanced (19-20:
`noise_vs_signal`, `cross_modal_comparison`). All exported top-level.

## Decoding, trajectory, and structured-identity governance

- **`jnwb/decoding.py`** (337 lines) — `decode_stimulus_identity`/`decode_omission_presence`.
  Explicitly **never fabricates performance metrics**: returns `NaN` accuracy with
  `status="insufficient_trials"` if a class has fewer than 2 trials. `device="cuda"` currently
  silently falls back to the same CPU path — GPU flag accepted but does not change behavior.
- **`jnwb/trajectory.py`** (191 lines) — GPU-accelerated PCA population trajectories.
- **`jnwb/structured_identity.py`** / **`structured_identity_m2a.py`** (not exported) — both
  encode a **hard governance gate in their own module docstrings**: `structured_identity.py`
  states it fits no models at all ("training remains explicitly unauthorized until the
  Milestone 1 receipt is reviewed"); `structured_identity_m2a.py` states it contains only the
  approved validation/baseline linear path, deliberately no nonlinear/structured model. Do not
  extend either beyond its stated approved scope without the documented review.

## `jrsa.py` — unified Representational Similarity Analysis (1549 lines)

Single public function `jrsa(x1, x2, metric=..., stats=True, ...) -> JRSAResult`, dispatching to
~15 private metric backends (`_pearson`, `_spearman`, `_rsa`, `_cka`, `_hsic`,
`_distance_correlation`, `_mutual_information`, `_procrustes`, `_granger`,
`_transfer_entropy`, `_phase_slope`, ...) across numpy/cupy/jax/torch backends. **Note**:
`jrsa(metric="granger")` and `oa.granger()` (`connectivity.py`) are two independent code paths
computing nominally the same statistic — not confirmed to agree numerically; treat as separate
implementations, not interchangeable.

Known limits (per `omission-statistics` skill): `_compute_statistics` is a no-op stub;
`_stack_batches` is never called (`batch_size` is cosmetic); permutation p-values are not
lag-segregated in multi-lag mode; HSIC assumes symmetric kernels. Prefer `jnwb.connectivity` for
anything shipping in a figure — it carries this corpus's stationarity/residual-autocorrelation
diagnostics; `jrsa` is best for a quick exploratory similarity check.

## Support modules (brief)

| Module | Exported? | Purpose |
|---|---|---|
| `addressing.py` | partial | `map_peak_channel_to_area`, `classify_layer_from_depth`, `enrich_units_dataframe` (called by every session load) |
| `metadata.py` | partial | `get_all_units_metadata`, `classify_unit_quality`, `unit_census_report`, `electrode_inventory` |
| `diagnostics.py` | partial | `audit_session`, `compare_sessions`, `print_audit_report` |
| `sequence_layout.py` | most constants exported | Canonical timing contract (fx=-500…end=4124 ms), `EPOCH_ONSETS_MS`, `CANONICAL_AREAS_11`, area/channel-slice helpers, `BANDS_7` (used by `session.tfr_from_preprocessed`) |
| `analog.py` | yes (3 loaders) | `load_analog_epochs`/`load_muae_epochs`/`load_lfp_epochs` — deliberately bypasses `pynwb` via raw h5py for known-broken NWB builders; records git SHA + file SHA256 provenance per load |
| `permutation.py` | no | `permute_labels` — canonical grouped-null primitive |
| `onset_fitting.py` | no | Causal exponential PSTH smoothing + onset-latency fit; documents a real non-identifiability bug it fixed (naive joint 4-param fit slid to a degenerate corner) |
| `trial_ontology.py` | no | `parse_condition`, `build_trial_ontology` — consolidates condition-code parsing that was previously re-derived ad hoc in ≥3 places (including the exact p4 swap bug above) |
| `compression.py` | partial (`compress_fp32`) | Lossless-except-fp32-cast NWB compression, ~2.8× on this corpus |
| `tfr_accumulator.py` | yes | `TFRAccumulator`, `assert_mergeable` — poolable Welford-merge sufficient statistics for complex TFR |
| `artifact_detection.py` | no | Bad-channel/bad-trial exclusion decisions (distinct from repair) |
| `artifact_repair.py` | no | Canonical cross-channel-synchrony detection + cross-trial-median substitution; single source of truth, do not duplicate |
| `bilinear.py` / `nam.py` / `gpu_pca.py` | no | Rank-K bilinear logistic regression / Neural Additive Model / standalone GPU PCA decoders |
| `visual_qc.py` | module-level | QC visualization (waveforms, quality distributions, noise-vs-signal, cross-session comparison) |
| `ontology.py` / `factories.py` | yes | Frozen v1.0.0 scientific data model (`Provenance`, `Lineage`, `Query`, `Dataset`, `Result`, ...) + the internal bridge layer to `OmissionSession` |
| `mcp_server/` | separate | FastMCP tool server for NWB inspection — not part of the analysis API, documented separately |

## Quarantined — `jnwb/_unused/` (zero confirmed production importers, grepped 2026-08-14)

Moved, not deleted, per the project's archive-don't-delete convention. **Do not document as live
API.**

- `_unused/complex_tfr.py` — superseded by `spectral.imaginary_coherency`.
- `_unused/markdown_report.py` — despite its own docstring calling markdown/SVG "canonical,"
  this module is quarantined; `report.py` (HTML) is the live, exported reporting path. **Two
  skills still reference the quarantined imports** (`omission-signal` → `jnwb.complex_tfr`,
  `omission-figures` → `jnwb.markdown_report`) — flagged in doc09.
