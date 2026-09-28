# Package inventory (07-23)

Baseline `4fac3517991b1ab390dcfbd766276679887fd7ac`, detached worktree. Probe `inventory.py` imported the worktree's package: `jnwb.__file__ = ...\scratchpad\audit\wt\jnwb\__init__.py`, version `0.2.6.1`. The installed site-packages copy is stale (156 exports) and was not used. Nothing moves this cycle; this list is for Hamm.

## Totals

| Measure | Value |
|---|---|
| `len(jnwb.__all__)` | 162 (162 unique) |
| List A: exports no skill file references as a symbol | **26 of 162** |
| Plain word scan over the same files | 24 of 162 (credits `Dataset` and `Figure`) |
| List B: public modules with public names outside `__all__` | 43 modules, 182 names |

## Method for List A

- **Corpus.** All 18 files under `skills/`: 9 `SKILL.md` and 9 `agents/openai.yaml`.
- **Match.** Case-sensitive `(?<![\w])NAME(?![\w])`, one pass per export.
- **The two English-word exports.** `jnwb.ontology.Dataset` and `jnwb.ontology.Figure` count only when qualified (`jnwb.X` or `ontology.X`), or when named in an `import` line inside code. Skill word hits for these names: `Dataset` 1, in prose ("Dataset-agnostic", `skills/jnwb/SKILL.md:48`). `Figure` 2: one in a table cell (`skills/jnwb-landmark-viz/SKILL.md:14`), and one inside a code span that is matplotlib's type, "'Figure' object is not iterable" (`skills/jnwb-figures/SKILL.md:15`). A code-span-only rule counts that last hit and gives 25. Because the object is matplotlib's, 26 is the correct count.
- **Result.** IB-37's figure, 26 of 162 by symbol and 24 by word, reproduces exactly.
- **Where used.** Word-boundary counts per file across `jnwb/`, `docs/`, `examples/` and `tests/`. The table omits `docs/api.md` because it lists every export by construction. Every name in List A has one hit in `tests/test_skill_symbol_coverage.py`, which is its exclusion entry.

## List A
| # | Name | Kind | Defined in | Skill word hits | jnwb / docs / examples / tests (total refs) | Files, count (excluding `docs/api.md`, which lists every export) |
|---|---|---|---|---|---|---|
| 1 | `JRSAResult` | class | `jnwb.jrsa` | 0 | 12 / 10 / 0 / 6 | `jnwb/jrsa.py` 10; `docs/03_representational_similarity_jrsa.md` 4; `tests/test_docs_decoding_chain.py` 4; `docs/10_operation_specifications.md` 2; `jnwb/__init__.py` 2; `docs/01_architecture_and_philosophy.md` 1; `docs/quickstart.md` 1; `tests/test_docs_smoke.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 2 | `Query` | class | `jnwb.ontology` | 0 | 10 / 6 / 0 / 13 | `tests/test_ontology.py` 10; `jnwb/ontology.py` 8; `docs/02_paths_addressing_metadata.md` 4; `docs/01_architecture_and_philosophy.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `tests/test_docs_smoke.py` 1; `tests/test_import_lazy.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 3 | `Dataset` | class | `jnwb.ontology` | 1 | 47 / 13 / 0 / 35 | `tests/test_ontology.py` 31; `jnwb/ontology.py` 19; `jnwb/nwb_inspect.py` 15; `jnwb/mcp_server/nwb_tools.py` 8; `docs/02_paths_addressing_metadata.md` 7; `jnwb/compression.py` 3; `tests/test_errors_documented.py` 2; `docs/01_architecture_and_philosophy.md` 1; `docs/architecture.md` 1; `docs/index.md` 1; `docs/tutorials/09_open_data.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `tests/test_compression.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 4 | `AlignedDataset` | class | `jnwb.ontology` | 0 | 11 / 4 / 0 / 9 | `jnwb/ontology.py` 9; `tests/test_ontology.py` 7; `docs/02_paths_addressing_metadata.md` 2; `docs/01_architecture_and_philosophy.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `tests/test_errors_documented.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 5 | `Alignment` | class | `jnwb.ontology` | 0 | 17 / 8 / 2 / 18 | `jnwb/ontology.py` 11; `tests/test_docs_decoding_chain.py` 9; `tests/test_ontology.py` 8; `docs/02_paths_addressing_metadata.md` 3; `jnwb/jrsa.py` 3; `examples/tutorials/06_laminar.py` 2; `docs/01_architecture_and_philosophy.md` 1; `docs/03_representational_similarity_jrsa.md` 1; `docs/documentation_form.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `jnwb/vis/hierarchy.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 6 | `EpochCollection` | class | `jnwb.ontology` | 0 | 7 / 6 / 0 / 9 | `tests/test_ontology.py` 8; `jnwb/ontology.py` 5; `docs/02_paths_addressing_metadata.md` 4; `docs/01_architecture_and_philosophy.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 7 | `Result` | class | `jnwb.ontology` | 0 | 22 / 17 / 0 / 24 | `tests/test_ontology.py` 22; `jnwb/ontology.py` 18; `docs/references.md` 6; `docs/02_paths_addressing_metadata.md` 3; `docs/03_representational_similarity_jrsa.md` 3; `docs/01_architecture_and_philosophy.md` 1; `docs/10_operation_specifications.md` 1; `docs/architecture.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `jnwb/_parallel.py` 1; `jnwb/spectral.py` 1; `tests/test_jnwb_core.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 8 | `Interpretation` | class | `jnwb.ontology` | 0 | 10 / 7 / 0 / 10 | `tests/test_ontology.py` 9; `jnwb/ontology.py` 8; `docs/02_paths_addressing_metadata.md` 3; `docs/01_architecture_and_philosophy.md` 1; `docs/06_spikes_psth_and_onset_dynamics.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 9 | `Figure` | class | `jnwb.ontology` | 2 | 24 / 20 / 2 / 16 | `docs/generate_figures.py` 10; `tests/test_ontology.py` 10; `jnwb/ontology.py` 9; `jnwb/visual_qc.py` 8; `docs/02_paths_addressing_metadata.md` 4; `tests/test_visual_qc.py` 3; `docs/quickstart.md` 2; `examples/tutorials/09_open_data.py` 2; `jnwb/vis/canvas.py` 2; `jnwb/vis/theme.py` 2; `tests/test_skills_validation.py` 2; `docs/01_architecture_and_philosophy.md` 1; `docs/09_decoding_and_visual_qc.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `jnwb/viz.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 10 | `Provenance` | class | `jnwb.ontology` | 0 | 9 / 5 / 0 / 21 | `tests/test_ontology.py` 15; `jnwb/ontology.py` 5; `docs/02_paths_addressing_metadata.md` 3; `tests/test_the_suite_can_qualify_an_installed_copy.py` 2; `docs/01_architecture_and_philosophy.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `jnwb/compression.py` 1; `jnwb/tfr_accumulator.py` 1; `tests/test_composition_axis.py` 1; `tests/test_execution_switch.py` 1; `tests/test_rng_spelling.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 11 | `Lineage` | class | `jnwb.ontology` | 0 | 6 / 5 / 0 / 10 | `tests/test_ontology.py` 9; `jnwb/ontology.py` 4; `docs/02_paths_addressing_metadata.md` 3; `docs/01_architecture_and_philosophy.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 12 | `assert_mergeable` | function | `jnwb.tfr_accumulator` | 0 | 3 / 3 / 0 / 6 | `tests/test_tfr_accumulator.py` 5; `jnwb/__init__.py` 2; `docs/01_architecture_and_philosophy.md` 1; `docs/04_spectral_analysis_and_tfr.md` 1; `jnwb/tfr_accumulator.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 13 | `NWBInspectError` | class | `jnwb.nwb_inspect` | 0 | 8 / 5 / 1 / 9 | `jnwb/nwb_inspect.py` 6; `docs/errors.md` 4; `jnwb/__init__.py` 2; `tests/test_api_consistency.py` 2; `tests/test_errors_documented.py` 2; `tests/test_mcp_server.py` 2; `examples/tutorials/00_your_own_file.py` 1; `tests/test_acquisition_layout.py` 1; `tests/test_skill_symbol_coverage.py` 1; `tests/test_tutorial_00_foreign_shapes.py` 1 |
| 14 | `ChannelIndexError` | class | `jnwb.nwb_inspect` | 0 | 7 / 3 / 0 / 18 | `tests/test_nwb_inspect.py` 6; `jnwb/nwb_inspect.py` 5; `tests/test_acquisition_layout.py` 4; `tests/test_api_consistency.py` 3; `tests/test_errors_documented.py` 3; `docs/errors.md` 2; `jnwb/__init__.py` 2; `tests/test_docs_operation_statements.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 15 | `UnitNotFoundError` | class | `jnwb.nwb_inspect` | 0 | 6 / 3 / 0 / 3 | `jnwb/nwb_inspect.py` 4; `docs/errors.md` 2; `jnwb/__init__.py` 2; `tests/test_api_consistency.py` 1; `tests/test_errors_documented.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 16 | `SqueezedAttributeWarning` | class | `jnwb.nwb_io` | 0 | 6 / 3 / 0 / 9 | `tests/test_nwb_read_tolerance_and_visibility.py` 5; `jnwb/nwb_io.py` 4; `tests/test_public_api_reachability.py` 3; `jnwb/__init__.py` 2; `docs/01_architecture_and_philosophy.md` 1; `docs/errors.md` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 17 | `NWBEventError` | class | `jnwb.nwb_events` | 0 | 7 / 4 / 0 / 6 | `jnwb/nwb_events.py` 5; `docs/errors.md` 3; `tests/test_api_consistency.py` 3; `jnwb/__init__.py` 2; `tests/test_errors_documented.py` 2; `tests/test_skill_symbol_coverage.py` 1 |
| 18 | `IntervalTableNotFoundError` | class | `jnwb.nwb_events` | 0 | 7 / 3 / 0 / 7 | `jnwb/nwb_events.py` 3; `docs/errors.md` 2; `jnwb/__init__.py` 2; `jnwb/mcp_server/event_tools.py` 2; `tests/test_nwb_events.py` 2; `tests/test_api_consistency.py` 1; `tests/test_errors_documented.py` 1; `tests/test_minimal_units_table.py` 1; `tests/test_skill_symbol_coverage.py` 1; `tests/test_substitution_class_sweep.py` 1 |
| 19 | `InvalidOnsetValueError` | class | `jnwb.nwb_events` | 0 | 10 / 4 / 0 / 15 | `tests/test_epoch_onset_sanity.py` 9; `jnwb/continuous.py` 3; `jnwb/nwb_events.py` 3; `docs/errors.md` 2; `jnwb/__init__.py` 2; `jnwb/mcp_server/event_tools.py` 2; `tests/test_nwb_events.py` 2; `docs/common_mistakes.md` 1; `tests/test_api_consistency.py` 1; `tests/test_errors_documented.py` 1; `tests/test_skill_symbol_coverage.py` 1; `tests/test_substitution_class_sweep.py` 1 |
| 20 | `ProbeGeometry` | class | `jnwb.addressing` | 0 | 12 / 6 / 0 / 17 | `tests/test_laminar.py` 8; `jnwb/addressing.py` 5; `docs/10_operation_specifications.md` 3; `jnwb/laminar.py` 3; `tests/test_integration_0_2_1.py` 3; `jnwb/__init__.py` 2; `jnwb/testing/synth.py` 2; `tests/test_addressing.py` 2; `docs/02_paths_addressing_metadata.md` 1; `tests/test_docs_operation_statements.py` 1; `tests/test_laminar_index_space_and_boundary.py` 1; `tests/test_precision_switch.py` 1; `tests/test_skill_symbol_coverage.py` 1 |
| 21 | `ZFlipResult` | class | `jnwb.laminar` | 0 | 8 / 6 / 1 / 7 | `jnwb/laminar.py` 6; `tests/test_docs_call_shapes.py` 3; `docs/10_operation_specifications.md` 2; `jnwb/__init__.py` 2; `docs/01_architecture_and_philosophy.md` 1; `docs/02_paths_addressing_metadata.md` 1; `examples/tutorials/06_laminar.py` 1; `tests/test_a_silent_no_op_is_refused.py` 1; `tests/test_skill_decline_behaviour.py` 1; `tests/test_skill_symbol_coverage.py` 1; `tests/test_zflip.py` 1 |
| 22 | `TFRAnalyzer` | class | `jnwb.analyzers` | 0 | 11 / 7 / 0 / 83 | `tests/test_tfr_extract_band_regressions.py` 27; `tests/test_analyzers_coverage.py` 22; `tests/test_jnwb_core.py` 15; `tests/test_audit_reproducers.py` 11; `jnwb/analyzers.py` 8; `docs/04_spectral_analysis_and_tfr.md` 4; `tests/test_uncovered_exports.py` 3; `tests/test_docs_smoke.py` 2; `docs/01_architecture_and_philosophy.md` 1; `docs/common_mistakes.md` 1; `jnwb/__init__.py` 1; `jnwb/_lazy_exports.py` 1; `jnwb/trajectory.py` 1; `tests/test_import_lazy.py` 1; `tests/test_skill_symbol_coverage.py` 1; `tests/test_trajectory.py` 1 |
| 23 | `DETECTION_TAILS` | tuple | `None` | 0 | 5 / 4 / 0 / 8 | `tests/test_artifact_repair.py` 4; `docs/05_artifact_detection_and_repair.md` 3; `jnwb/artifact_repair.py` 3; `tests/test_errors_documented.py` 3; `jnwb/__init__.py` 2; `tests/test_skill_symbol_coverage.py` 1 |
| 24 | `DB_AGGREGATIONS` | tuple | `None` | 0 | 7 / 3 / 0 / 12 | `tests/test_spectral.py` 11; `jnwb/spectral.py` 5; `docs/04_spectral_analysis_and_tfr.md` 2; `jnwb/__init__.py` 2; `tests/test_skill_symbol_coverage.py` 1 |
| 25 | `RELATIVE_POWER_MODELS` | tuple | `None` | 0 | 5 / 2 / 0 / 5 | `jnwb/spectral.py` 3; `tests/test_spectral.py` 3; `jnwb/__init__.py` 2; `docs/04_spectral_analysis_and_tfr.md` 1; `tests/test_skill_symbol_coverage.py` 1; `tests/test_substitution_class_sweep.py` 1 |
| 26 | `SKILLS_URL` | str | `None` | 0 | 2 / 3 / 0 / 24 | `tests/test_skills_are_findable_from_an_installed_copy.py` 17; `tests/test_skill_symbol_coverage.py` 3; `docs/agents.md` 2; `jnwb/__init__.py` 2; `tests/test_api_md_member_types.py` 2; `tests/test_prose_version_claims_are_live.py` 2 |

Grouped: 10 ontology types (`Query`, `Dataset`, `AlignedDataset`, `Alignment`, `EpochCollection`, `Result`, `Interpretation`, `Figure`, `Provenance`, `Lineage`; `Dataset` and `Figure` included), 7 error or warning classes, 4 result or container classes (`JRSAResult`, `ProbeGeometry`, `ZFlipResult`, `TFRAnalyzer`), 4 constants (`DETECTION_TAILS`, `DB_AGGREGATIONS`, `RELATIVE_POWER_MODELS`, `SKILLS_URL`) and 1 function (`assert_mergeable`). Each is named exactly once in `tests/test_skill_symbol_coverage.py` (its exclusion entry; category assertions not re-checked here). "Defined in" reads `None` for constants, which carry no `__module__`.

## List B: public modules whose public names are not all in `__all__`

A public module is any `jnwb/**/*.py` with no `_`-led path component, plus subpackage `__init__.py` files. The package root and `__main__.py` are left out. Public names are top-level `def`, `class` and assignment targets not starting with `_`; imported names are excluded. The use column gives word-boundary counts outside the defining module as jnwb / docs / examples / tests. Short generic names (`log`, `predict`, `convert`, `compact`, `mcp`, `PathLike`) are overcounted by that match, and `log`, the module logger in 17 modules, is not counted at all.

| Module | Public names | Module `__all__` | Missing from `jnwb.__all__` | Name: uses outside the defining module (jnwb / docs / examples / tests) |
|---|---|---|---|---|
| `jnwb/addressing.py` | 7 | none | 2 | `log` (module logger; word count not meaningful); `parse_probe_areas` 0/0/0/9 |
| `jnwb/analyzers.py` | 4 | none | 1 | `log` (module logger; word count not meaningful) |
| `jnwb/artifact_detection.py` | 6 | none | 1 | `MAD_SCALE` 0/0/0/0 |
| `jnwb/artifact_repair.py` | 10 | none | 6 | `Z_THRESH` 0/0/0/0; `REWARD_WINDOW_MS` 0/0/0/0; `flagged_to_intervals` 0/0/0/2; `interpolate_intervals` 0/0/0/7; `DEFAULT_BANDS` 0/0/0/3; `TFR_Z_THRESH` 0/0/0/0 |
| `jnwb/bilinear.py` | 1 | none | 1 | `BilinearLogisticRegression` 0/0/0/4 |
| `jnwb/compression.py` | 8 | none | 7 | `FILT` 0/0/0/0; `CONVERSION_ENTRY_POINT` 0/0/0/0; `SPIKE_TRAIN_PATH` 0/0/0/9; `CONVOLVED_PATH` 0/0/0/19; `compact` 1/1/0/0; `convert` 3/2/0/27; `verify_roundtrip` 0/0/0/36 |
| `jnwb/connectivity.py` | 18 | none | 4 | `log` (module logger; word count not meaningful); `fit_var_bivariate` 0/0/0/16; `select_optimal_lag` 0/0/0/11; `DIRECTED_METHODS` 0/0/0/2 |
| `jnwb/continuous.py` | 3 | none | 2 | `BoundaryPolicy` 0/1/0/0; `OnsetUnit` 0/1/0/0 |
| `jnwb/decoding.py` | 7 | none | 1 | `log` (module logger; word count not meaningful) |
| `jnwb/gpu_pca.py` | 3 | none | 3 | `log` (module logger; word count not meaningful); `pin_component_signs` 4/0/0/14; `gpu_pca` 6/0/0/60 |
| `jnwb/io.py` | 2 | yes | 1 | `SUPPORTED_COMPRESSIONS` 0/0/0/0 |
| `jnwb/jrsa.py` | 6 | none | 4 | `ALIGN_MODES` 0/0/0/0; `REDUCTION_OPS` 0/0/0/0; `NULL_SCHEMES` 0/0/0/0; `ALTERNATIVES` 0/0/0/1 |
| `jnwb/laminar.py` | 11 | none | 3 | `log` (module logger; word count not meaningful); `CANONICAL_VFLIP_BANDS` 0/0/0/0; `LAYER_BOUNDARY_TOL_CONTACTS` 0/0/0/1 |
| `jnwb/mcp_server/event_tools.py` | 1 | none | 1 | `get_event_codes_and_timings` 2/1/0/7 |
| `jnwb/mcp_server/nwb_tools.py` | 2 | none | 2 | `inspect_nwb` 2/1/0/4; `prepare_signal_reference` 2/1/0/12 |
| `jnwb/mcp_server/server.py` | 1 | none | 1 | `mcp` 10/3/0/19 |
| `jnwb/metadata.py` | 12 | none | 3 | `log` (module logger; word count not meaningful); `compare_old_new_criteria` 0/0/0/2; `old_new_summary_table` 0/0/0/1 |
| `jnwb/nam.py` | 4 | none | 4 | `LaminarNAM` 0/0/0/1; `unit_importance` 0/0/0/1; `predict` 4/0/0/3; `train_nam` 0/0/0/3 |
| `jnwb/nwb_events.py` | 12 | none | 3 | `CodeValue` 0/0/0/0; `CodeSequence` 0/1/0/0; `codes_equal` 0/0/0/5 |
| `jnwb/nwb_inspect.py` | 15 | none | 5 | `InspectInput` 0/4/0/0; `TIME_BY_CHANNEL` 0/0/0/10; `CHANNEL_BY_TIME` 0/0/0/10; `AMBIGUOUS_LAYOUT` 2/0/0/5; `CONTINUOUS_KEYS` 0/0/0/9 |
| `jnwb/nwb_io.py` | 10 | none | 6 | `PathLike` 11/0/0/0; `NWBInput` 7/3/0/0; `WAIVED_REQUIREMENTS_ATTR` 0/0/0/8; `ContainerTypeContradictionWarning` 2/0/0/4; `TOLERABLE_MISSING_FIELDS` 0/0/0/0; `hdmf_build_repair_context` 0/0/0/6 |
| `jnwb/onset_fitting.py` | 4 | none | 1 | `DEFAULT_TAU_MS` 0/0/0/2 |
| `jnwb/ontology.py` | 16 | yes | 3 | `create_aligned_dataset` 0/1/0/4; `create_result` 0/1/0/4; `create_figure` 0/1/0/4 |
| `jnwb/paths.py` | 32 | yes | 32 | `PACKAGE_ROOT` 0/1/0/24; `ENV_NWB_DIR` 0/0/0/8; `ENV_TFR_DIR` 0/0/0/3; `ENV_META_DIR` 0/0/0/3; `ENV_CONNDB_DIR` 0/0/0/3; `ENV_ANALYSIS_DIR` 0/0/0/3; `ENV_OUTPUTS_DIR` 0/0/0/3; `ENV_ARTIFACTS_DIR` 0/0/0/2; `LEGACY_ENV_NWB_DIR` 0/0/0/3; `LEGACY_ENV_TFR_DIR` 0/0/0/2; `LEGACY_ENV_META_DIR` 0/0/0/2; `LEGACY_ENV_CONNDB_DIR` 0/0/0/2; `LEGACY_ENV_ANALYSIS_DIR` 0/0/0/2; `LEGACY_ENV_OUTPUTS_DIR` 0/0/0/3; `LEGACY_ENV_ARTIFACTS_DIR` 0/0/0/2; `DEFAULT_NWB_DIR` 0/0/0/1; `DEFAULT_ANALYSIS_DIR` 0/0/0/1; `TFR_SUBDIR` 0/0/0/2; `META_SUBDIR` 0/0/0/2; `CONNDB_SUBDIR` 0/0/0/2; `nwb_dir` 0/3/0/10; `analysis_dir` 0/1/0/1; `tfr_dir` 0/0/0/5; `meta_dir` 0/0/0/5; `conndb_dir` 0/0/0/5; `outputs_dir` 0/1/0/7; `artifacts_dir` 0/1/0/6; `layer_masks_path` 0/0/0/1; `resolve_nwb_path` 0/0/0/3; `sha256_file` 0/0/0/19; `require` 4/0/0/13; `describe` 11/1/0/27 |
| `jnwb/permutation.py` | 3 | none | 1 | `SCHEMES` 0/0/0/0 |
| `jnwb/rsa.py` | 3 | none | 1 | `log` (module logger; word count not meaningful) |
| `jnwb/spectral.py` | 25 | none | 5 | `log` (module logger; word count not meaningful); `ZERO_LAG_RTOL` 0/0/0/0; `MIN_IDENTIFIABLE_SEGMENTS` 0/0/0/2; `MIN_COHERENCE_NPERSEG` 2/0/0/0; `welch_segment_count` 0/0/0/4 |
| `jnwb/spiking.py` | 6 | none | 1 | `log` (module logger; word count not meaningful) |
| `jnwb/statistics.py` | 18 | none | 2 | `log` (module logger; word count not meaningful); `coef_rows` 0/0/0/4 |
| `jnwb/testing/nwb_fixtures.py` | 23 | none | 23 | `TASK_TABLE` 0/0/16/34; `RF_TABLE` 0/0/0/8; `FLASH_TABLE` 0/0/0/8; `CODE_LABEL_A` 0/0/13/13; `CODE_LABEL_B` 0/0/6/6; `CODE_NUMERIC_A` 0/0/0/4; `CODE_NUMERIC_B` 0/0/0/3; `AcquisitionStyle` 0/0/0/0; `CodesDtype` 0/0/0/0; `IntervalLayout` 0/0/0/0; `DEFAULT_FS_HZ` 0/0/0/0; `DEFAULT_N_CHANNELS` 0/0/0/0; `DEFAULT_N_EVENTS` 0/0/0/0; `DEFAULT_SEED` 15/0/0/11; `SynthNWBBuildOptions` 2/2/0/7; `SynthNWBReceipt` 2/0/0/0; `canonical_co_resident_options` 2/0/10/18; `lfp_wrapped_options` 2/0/0/8; `numeric_codes_options` 2/0/0/6; `task_only_options` 2/0/0/8; `processing_lfp_options` 0/0/0/3; `build_synth_nwb` 2/0/0/10; `write_synth_nwb` 2/0/10/36 |
| `jnwb/testing/synth.py` | 11 | none | 11 | `SynthLaminarReceipt` 2/2/0/3; `synth_white_noise` 2/1/0/17; `synth_ar_noise` 2/1/0/15; `synth_periodic_response` 2/1/0/7; `synth_correlation_blocks` 2/1/0/21; `synth_phase_gradient` 2/1/0/5; `synth_unequal_groups` 2/1/0/4; `synth_laminar_motif` 2/2/0/19; `TUTORIAL_UNIT_DEPTH_FRACTIONS` 0/0/0/0; `TUTORIAL_CROSSOVER_CONTACT` 0/0/0/0; `build_canonical_tutorial_nwb` 2/2/0/13 |
| `jnwb/tfr_accumulator.py` | 3 | none | 1 | `REQUIRED_MATCH` 0/0/0/0 |
| `jnwb/trajectory.py` | 3 | none | 1 | `log` (module logger; word count not meaningful) |
| `jnwb/vis/canvas.py` | 5 | none | 5 | `log` (module logger; word count not meaningful); `MM_TO_PX` 0/0/0/3; `STANDARD_LAYOUT_WIDTHS_MM` 0/0/0/2; `MAX_HEIGHT_MM` 0/0/0/0; `PlotlyPublicationCanvas` 27/1/0/22 |
| `jnwb/vis/hierarchy.py` | 1 | none | 1 | `plot_hierarchy_regression` 2/1/0/2 |
| `jnwb/vis/laminar.py` | 3 | none | 3 | `plot_spectrolaminar_map` 2/1/0/6; `plot_opposing_gradients` 2/1/0/3; `plot_csd` 2/1/0/3 |
| `jnwb/vis/sidecar.py` | 2 | none | 2 | `EpistemicArgumentObject` 4/1/0/4; `serialize_argument_sidecar` 4/0/0/2 |
| `jnwb/vis/spectral.py` | 2 | none | 2 | `plot_spectral_modulation_matrix` 2/1/0/2; `plot_granger_spectra` 2/1/0/2 |
| `jnwb/vis/spiking.py` | 2 | none | 2 | `plot_multi_condition_raster_psth` 2/1/0/4; `plot_sorted_heatmap` 2/2/0/1 |
| `jnwb/vis/state_space.py` | 2 | none | 2 | `plot_decoding_timecourse` 2/1/0/2; `plot_rsm_heatmap` 2/1/0/3 |
| `jnwb/vis/theme.py` | 10 | none | 10 | `TOL_MUTED` 2/0/0/1; `OKABE_ITO` 2/0/0/1; `NATURE_ACCENTS` 2/0/0/1; `COLOR_PALETTES` 2/0/0/1; `FONT_FAMILY` 24/0/0/1; `FONT_SIZES` 24/0/0/1; `COLORS` 26/0/0/0; `get_publication_layout_template` 4/0/0/1; `apply_publication_theme` 1/0/0/1; `configure_axis` 31/0/0/0 |
| `jnwb/visual_qc.py` | 11 | none | 11 | `log` (module logger; word count not meaningful); `MADELANE_GOLD` 0/0/0/5; `MADELANE_VIOLET` 0/0/0/1; `MADELANE_WHITE` 0/0/0/1; `MADELANE_GRAY` 0/0/0/1; `MADELANE_TEAL` 0/0/0/1; `MADELANE_ORANGE` 0/0/0/1; `plot_unit_waveforms` 0/0/0/3; `plot_unit_quality_distribution` 0/1/0/6; `plot_noise_vs_signal` 0/1/0/3; `compare_session_quality` 0/1/0/7 |
| `jnwb/viz.py` | 6 | none | 1 | `log` (module logger; word count not meaningful) |

### Reading List B

| Pattern | Modules |
|---|---|
| Namespace-only subpackages: all their public names are outside `__all__`, reached as `jnwb.vis.*` or `jnwb.testing.*` | `vis/*` (8 modules), `testing/nwb_fixtures.py`, `testing/synth.py`, `mcp_server/*` |
| Module constants and env names reached as `jnwb.paths.X`; the module has its own `__all__` | `paths.py` (32) |
| Public-named helpers with test-only callers (0 uses in jnwb/docs/examples) | e.g. `artifact_repair.interpolate_intervals`, `connectivity.fit_var_bivariate`, `connectivity.select_optimal_lag`, `compression.verify_roundtrip`, `nam.*`, `bilinear.BilinearLogisticRegression`, `statistics.coef_rows`, `spectral.welch_segment_count` |
| Public-named constants with no use anywhere outside their module | e.g. `artifact_detection.MAD_SCALE`, `artifact_repair.Z_THRESH`/`REWARD_WINDOW_MS`/`TFR_Z_THRESH`, `jrsa.ALIGN_MODES`/`REDUCTION_OPS`/`NULL_SCHEMES`, `permutation.SCHEMES`, `io.SUPPORTED_COMPRESSIONS`, `tfr_accumulator.REQUIRED_MATCH`, `laminar.CANONICAL_VFLIP_BANDS` |
| Project-flavoured names in the library namespace | `visual_qc.MADELANE_*` (6 colour constants) |

Machine-readable data: `inventory.json`, beside this file.
