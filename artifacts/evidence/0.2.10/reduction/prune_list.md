# Test reduction: prune list (10-21)

**Status: not ruled.** Nothing is deleted or changed before Hamm rules on this list (rulings
2026-09-27 and 2026-10-06). The one change made is the boundary-test rewrite, in section 5.

Measured on `9e9a4b63`. The run, its environment and the analysis output are in
`coverage_run.txt`; per-file counts in `per_file_unique_lines.tsv`; every mutant receipt in
`mutants.tsv`.

## 1. Measurement

One full pass, `COVERAGE_CORE=ctrace`, per-test contexts (`--cov-context=test`), `-n 12`,
measuring `jnwb/` and `scripts/`: 7120 passed, 30 skipped, 20 xfailed, rc 0, 457 s.

Per-test contexts were checked first on three tests calling one function under `-n 2`. The
default core recorded 2 of the 3 tests on each line (the first per worker); `ctrace` recorded all
3. The probe is at the end of `coverage_run.txt`.

A test file's unique lines are the `jnwb/` and `scripts/` lines no other test file executes.
Import-time lines carry no test context and are attributed to no file.

| Set | Files | Lines of test code | Tests | Summed test time (s) |
|---|---:|---:|---:|---:|
| Suite | 202 | 75529 | 7170 | 3740 |
| Zero unique lines, executing some measured line | 40 | 10688 | 796 | 748 |
| Executing no measured line in process | 28 | 5164 | 303 | 349 |
| Executing no `jnwb/` line in process | 61 | 16391 | 1209 | 1532 |

**The item's counts do not reproduce.** It cites 21 zero-unique files and 48 process tests from
the first audit under the default core, whose file lists are not on disk. Under `ctrace` with
`scripts/` measured too, 68 files have zero unique lines (40 + 28 above). Deleting all 68
together loses no measured line: every line any of them executes is also executed by a file
outside the set (`coverage_run.txt`, group check). Line coverage is necessary for redundancy and
not sufficient: the mutants below show it.

## 2. Candidates

A candidate has zero unique lines and at least one mutant on its stated purpose that another
test file kills. Each mutant: anchor applied exactly once, every selector passing on the pristine
tree first, serial runs, file restored and its sha256 matched, `git status` clean.

| File | Lines | Tests | Time (s) | Unique lines | Mutant (purpose) | Candidate kills | Killed elsewhere by |
|---|---:|---:|---:|---:|---|---|---|
| `tests/test_shuffle_pvalues_are_ranks.py` | 504 | 36 | 59.8 | 0 | SP1: paired shuffle count `k - 1`, p no longer a rank | yes | `test_skills_validation.py` |
| `tests/test_composition_randomness.py` | 347 | 17 | 77.2 | 0 | CR1: `draw_manifest` digest over the original labels, not the permuted | yes | `test_permutation.py`, `test_rng_control.py` |
| `tests/test_composition_failure_propagation.py` | 403 | 12 | 0.2 | 0 | FP1: `gaussian_smooth_rate` stops warning on NaN spread | yes | `test_a_silent_no_op_is_refused.py` |

One mutant per file shows each is not the sole guard of that mutant; it does not show the file
is the sole guard of no other. SP1 is killed elsewhere by a skill-example check, which is the
incidental kind of coverage `test_shuffle_pvalues_are_ranks.py` was written to replace.

**Excluded by the stop condition**

| File | Lines | Tests | Mutant | Killers |
|---|---:|---:|---|---|
| `tests/test_batch_a_regressions.py` | 217 | 17 | BA1: upper-bound censoring reported as `None` | only this file; `test_onset_fitting.py`, `test_agents_md_recipes.py`, `test_docs_call_shapes.py`, `test_docs_smoke.py` execute the line and pass |

## 3. Zero-unique files not yet judged by a mutant

Not candidates: no mutant has been run on their purpose. Executing some measured line:

| File | Lines | Tests | Time (s) | `jnwb/` lines | `scripts/` lines |
|---|---:|---:|---:|---:|---:|
| `tests/test_agents_md_recipes.py` | 137 | 7 | 2.02 | 811 | 0 |
| `tests/test_architecture_page_reachability.py` | 231 | 12 | 0.24 | 0 | 11 |
| `tests/test_audit_reproducers.py` | 53 | 3 | 0.01 | 16 | 0 |
| `tests/test_axis_convention_matches_the_specification.py` | 285 | 129 | 3.82 | 54 | 0 |
| `tests/test_claim_wording.py` | 212 | 8 | 2.34 | 0 | 19 |
| `tests/test_composition_identifier_survival.py` | 308 | 9 | 0.34 | 578 | 0 |
| `tests/test_cross_modal_comparison_faces_agree.py` | 166 | 12 | 2.38 | 173 | 0 |
| `tests/test_declared_return_shapes.py` | 155 | 13 | 0.07 | 127 | 0 |
| `tests/test_decoding_labels.py` | 219 | 35 | 9.95 | 141 | 0 |
| `tests/test_docs_decoding_chain.py` | 456 | 8 | 0.16 | 38 | 0 |
| `tests/test_docs_interpretation_statements.py` | 148 | 10 | 1.62 | 350 | 0 |
| `tests/test_docs_nwb_workflow.py` | 268 | 21 | 11.75 | 477 | 0 |
| `tests/test_docs_smoke.py` | 302 | 10 | 5.32 | 2392 | 0 |
| `tests/test_estimator_discrimination.py` | 251 | 9 | 0.94 | 443 | 0 |
| `tests/test_examples_quickstart.py` | 103 | 4 | 26.11 | 500 | 0 |
| `tests/test_generated_files_are_byte_stable.py` | 188 | 23 | 1.79 | 65 | 154 |
| `tests/test_import_lazy.py` | 251 | 14 | 44.08 | 5 | 0 |
| `tests/test_integration_0_2_1.py` | 253 | 7 | 0.11 | 404 | 0 |
| `tests/test_module_docstrings_match_their_code.py` | 554 | 27 | 3.64 | 29 | 0 |
| `tests/test_nwb_synthetic_fixtures.py` | 257 | 19 | 16.88 | 263 | 0 |
| `tests/test_open_data_example.py` | 191 | 6 | 19.98 | 292 | 0 |
| `tests/test_optional_vis_extra.py` | 106 | 7 | 24.71 | 0 | 24 |
| `tests/test_probe_axis_sign_is_pinned.py` | 212 | 85 | 1.38 | 437 | 0 |
| `tests/test_public_api_reachability.py` | 78 | 7 | 3.39 | 279 | 0 |
| `tests/test_readme_smoke.py` | 154 | 6 | 0.96 | 255 | 0 |
| `tests/test_representative_workflow.py` | 224 | 6 | 8.07 | 578 | 0 |
| `tests/test_rng_convention_matches_the_signatures.py` | 386 | 14 | 10.33 | 788 | 0 |
| `tests/test_semantic_mutation_classes.py` | 862 | 22 | 174.62 | 0 | 220 |
| `tests/test_skill_claims_match_the_router.py` | 125 | 4 | 0.25 | 262 | 0 |
| `tests/test_skill_examples_execute.py` | 177 | 33 | 11.54 | 1892 | 0 |
| `tests/test_skill_routing_behaviour.py` | 94 | 6 | 0.64 | 275 | 0 |
| `tests/test_spectral_nonfabrication.py` | 112 | 23 | 0.63 | 164 | 0 |
| `tests/test_staggered_shafts.py` | 336 | 23 | 0.38 | 180 | 0 |
| `tests/test_state_basis_is_checked.py` | 283 | 8 | 38.71 | 0 | 93 |
| `tests/test_tutorial_00_foreign_shapes.py` | 277 | 28 | 149.22 | 213 | 0 |
| `tests/test_workflow_release_policy.py` | 803 | 56 | 24.87 | 0 | 25 |

Executing no measured line in process, so coverage cannot judge them. The mechanism column is a
grep of each file for a child-process call (`subprocess`, `sys.executable`, `runpy`, `exec(`,
notebook clients), inferred and not read:

| File | Lines | Tests | Time (s) | Mechanism |
|---|---:|---:|---:|---|
| `tests/test_api_surface.py` | 181 | 5 | 1.28 | in process |
| `tests/test_collection_order_stability.py` | 177 | 11 | 34.85 | runs a child process |
| `tests/test_diagrams_render.py` | 195 | 12 | 56.33 | runs a child process |
| `tests/test_docs_links.py` | 48 | 2 | 0.08 | in process |
| `tests/test_docs_runnable_prerequisites.py` | 97 | 4 | 0.07 | in process |
| `tests/test_every_declaration_has_a_caller.py` | 173 | 7 | 1.0 | runs a child process |
| `tests/test_findings_ledger.py` | 165 | 6 | 0.02 | in process |
| `tests/test_generated_figures_are_maintained.py` | 231 | 25 | 47.08 | runs a child process |
| `tests/test_git_checkout_mark.py` | 46 | 4 | 0.08 | in process |
| `tests/test_gitignore_excludes_cache_by_path.py` | 222 | 19 | 5.5 | runs a child process |
| `tests/test_jnwb_frozen_boundary.py` | 176 | 6 | 9.5 | runs a child process |
| `tests/test_no_unreferenced_symbols.py` | 127 | 3 | 2.45 | in process |
| `tests/test_notebooks.py` | 213 | 10 | 63.22 | runs a child process |
| `tests/test_pointer_documents_resolve.py` | 232 | 18 | 0.38 | runs a child process |
| `tests/test_prose_version_claims_are_live.py` | 229 | 39 | 3.21 | in process |
| `tests/test_references_resolve.py` | 251 | 9 | 0.22 | in process |
| `tests/test_rng_parameters_by_use.py` | 141 | 5 | 8.03 | in process |
| `tests/test_role_files_point_to_one_contract.py` | 152 | 13 | 0.11 | in process |
| `tests/test_single_agent_instruction_file.py` | 97 | 6 | 0.39 | runs a child process |
| `tests/test_skill_router_reach.py` | 211 | 25 | 0.25 | in process |
| `tests/test_skill_symbol_coverage.py` | 478 | 19 | 0.8 | in process |
| `tests/test_skills_are_findable_from_an_installed_copy.py` | 194 | 11 | 0.4 | runs a child process |
| `tests/test_standing_rules_name_no_cycle.py` | 60 | 3 | 0.03 | in process |
| `tests/test_synthetic_figures_are_labelled.py` | 122 | 5 | 0.14 | in process |
| `tests/test_test_imports_survive_the_wheel_leg.py` | 253 | 6 | 12.25 | in process |
| `tests/test_the_suite_can_qualify_an_installed_copy.py` | 527 | 16 | 29.38 | runs a child process |
| `tests/test_tutorials.py` | 120 | 12 | 71.71 | runs a child process |
| `tests/test_vis_draws_no_default_landmark.py` | 46 | 2 | 0.11 | in process |

## 4. Near-duplicate clusters

From `test_clusters.txt` as recorded, not regenerated: 92 clusters, 204 tests, an estimated
487 lines saved by parametrising (the file's own estimate, gross; the item expected 150-250 net
after parametrize tables). Parametrising keeps every case, so no mutant is needed and the test
count is unchanged. Four clusters repeat one test name (`same-name`, 10 lines); the rest are
near-duplicates by structure.

| Saving (lines) | File | Tests | Lines in cluster | Kind | Members (name@line(lines)) |
|---:|---|---:|---:|---|---|
| 19 | `tests/test_spectral.py` | 2 | 43 | near | test_welch_csd_gpu_parity_even_nperseg@1403(21), test_welch_csd_gpu_parity_odd_nperseg@1425(22) |
| 19 | `tests/test_release_recovery_gates.py` | 2 | 43 | near | test_compat_omits_verbose_when_statsmodels_drops_it@20(21), test_compat_passes_verbose_when_supported@42(22) |
| 18 | `tests/test_stack_metadata_contradictions.py` | 4 | 31 | near | test_a_field_followed_by_ordinary_prose_is_not_flagged@96(6), test_a_backticked_identifier_after_a_field_is_not_a_truncation@103(8), test_a_count_inside_an_item_body_is_not_a_summary@380(8), test_a_count_with_no_ids_is_not_flagged@389(9) |
| 17 | `tests/test_batch_a_regressions.py` | 4 | 28 | near | test_onset_lower_bound_censored@9(7), test_onset_upper_bound_censored@17(7), test_onset_exactly_at_lower_bound@33(7), test_onset_exactly_at_upper_bound@41(7) |
| 16 | `tests/test_parallel.py` | 2 | 38 | near | test_a_default_call_does_not_start_a_process_pool@273(18), test_a_bootstrap_without_workers_does_not_start_one_either@292(20) |
| 14 | `tests/test_jrsa_provenance.py` | 4 | 26 | near | test_an_unknown_device_is_refused_like_everywhere_else@53(7), test_an_unknown_backend_is_refused@61(4), test_an_unknown_correction_is_refused_not_recorded@101(8), test_cka_refuses_a_kernel_it_does_not_implement@119(7) |
| 14 | `tests/test_jrsa_correctness.py` | 4 | 24 | near | test_pearson_raises_on_length_mismatch@578(6), test_spearman_raises_on_length_mismatch@585(6), test_kendall_raises_on_length_mismatch@592(6), test_cosine_raises_on_length_mismatch@599(6) |
| 13 | `tests/test_harness_adversarial_gates.py` | 4 | 26 | near | test_a_typo_in_a_placeholder_is_not_a_placeholder@1970(7), test_a_role_with_no_agent_file_fails@1980(4), test_a_block_on_a_retired_item_fails@1992(6), test_a_stack_that_resolves_nothing_is_reported_rather_than_passing@2079(9) |
| 11 | `tests/test_generation_closure_is_declared.py` | 2 | 28 | near | test_the_gate_catches_a_generator_that_has_been_renamed@86(15), test_the_gate_catches_a_source_that_no_longer_exists@103(13) |
| 10 | `tests/test_tfr_accumulator.py` | 2 | 24 | near | test_a_zero_baseline_raises_at_a_valid_cell_and_is_ignored_at_an_invalid_one@319(12), test_an_infinite_baseline_raises_at_a_valid_cell_and_is_ignored_at_an_invalid_one@332(12) |
| 9 | `tests/test_spectral.py` | 3 | 18 | near | test_a_mean_of_finite_ratios_that_overflows_raises@560(6), test_a_summed_baseline_that_overflows_raises@567(6), test_a_summed_power_that_overflows_is_named_and_the_baseline_is_not_blamed@574(6) |
| 9 | `tests/test_compression.py` | 2 | 22 | near | test_a_timestamps_array_the_conversion_drops_is_refused@1030(11), test_a_scalar_dataset_is_refused_before_anything_is_written@1059(11) |
| 8 | `tests/test_xflip.py` | 3 | 17 | near | test_asymmetric_precomputed_fails@76(6), test_invalid_diagonal_precomputed_fails@83(5), test_out_of_range_precomputed_fails@89(6) |
| 8 | `tests/test_release_body_gate.py` | 4 | 16 | near | test_a_wrong_ceiling_is_rejected@218(4), test_a_wrong_version_is_rejected@244(4), test_a_wrong_distribution_name_is_rejected@249(4), test_an_unpinned_install_is_rejected@258(4) |
| 8 | `tests/test_addressing.py` | 2 | 25 | near | test_map_peak_channel_to_area_two_area_probe_resolves_by_channel_position@73(10), test_dp_is_not_silently_folded_into_v4@578(15) |
| 7 | `tests/test_stack_metadata_contradictions.py` | 2 | 19 | near | test_ids_beyond_a_clause_break_belong_to_another_statement@399(10), test_each_count_governs_only_its_own_list@422(9) |
| 7 | `tests/test_skills_validation.py` | 2 | 24 | near | test_the_probe_ignores_a_comment_about_writing@1222(9), test_two_unrelated_mentions_in_one_file_are_not_a_writer@1232(15) |
| 7 | `tests/test_jnwb_core.py` | 3 | 16 | near | test_average_across_channels_shape@138(6), test_average_across_channels_single_channel@145(5), test_average_across_channels_many_channels@151(5) |
| 7 | `tests/test_harness_adversarial_gates.py` | 2 | 19 | near | test_case_and_spacing_variants_do_not_slip_through@1218(10), test_a_hyphenated_compound_is_still_the_term@1234(9) |
| 7 | `tests/test_harness_adversarial_gates.py` | 3 | 16 | near | test_an_unreadable_listing_is_reported_rather_than_passing@1876(6), test_a_missing_stack_is_reported_rather_than_passing@2089(5), test_a_missing_page_is_reported_rather_than_passing@2178(5) |
| 7 | `tests/test_complex_tfr.py` | 2 | 19 | near | test_probe04_linear_amplitude_scaling@107(10), test_probe05_quadratic_power_scaling@118(9) |
| 6 | `tests/test_synthetic_figures_are_labelled.py` | 2 | 16 | near | test_an_unlabelled_caption_is_caught@88(8), test_the_dark_variant_is_skipped_to_reach_the_caption@98(8) |
| 6 | `tests/test_spectral.py` | 2 | 16 | near | test_a_zero_baseline_under_nan_power_is_exempt_only_under_omit@502(8), test_an_infinite_baseline_under_nan_power_is_exempt_only_under_omit@531(8) |
| 6 | `tests/test_harness_adversarial_gates.py` | 2 | 17 | near | test_a_shipped_skill_yaml_is_scanned@1105(8), test_the_agent_entry_page_is_scanned_like_a_docs_page@1201(9) |
| 6 | `tests/test_gate2_ignores_nested_checkouts.py` | 2 | 21 | near | test_a_plain_duplicate_tree_still_fails@89(8), test_a_duplicate_under_dot_claude_that_is_not_a_checkout_still_fails@243(13) |
| 6 | `tests/test_epoch_onset_sanity.py` | 2 | 19 | near | test_every_event_overhanging_the_start_is_still_silent@89(11), test_every_event_overhanging_the_end_is_still_silent@101(8) |
| 6 | `tests/test_analyzers_coverage.py` | 2 | 16 | near | test_preserves_float64_dtype_and_reports_device@689(8), test_preserves_float32_dtype_and_reports_device@698(8) |
| 5 | `tests/test_tutorial_00_foreign_shapes.py` | 3 | 12 | near | test_the_rest_of_the_tutorial_still_runs@139(4), test_it_aligns_the_processing_series@156(4), test_the_rest_of_the_tutorial_still_runs@200(4) |
| 5 | `tests/test_statistics.py` | 2 | 14 | near | test_strong_paired_difference_is_significant_greater@171(7), test_strong_group_difference_is_significant@192(7) |
| 5 | `tests/test_rng_spelling.py` | 2 | 15 | near | test_granger_agrees_across_spellings@104(8), test_agreeing_values_are_not_a_conflict@149(7) |
| 5 | `tests/test_permutation.py` | 3 | 14 | near | test_rejects_unknown_scheme@41(4), test_within_group_requires_groups@46(4), test_groups_length_mismatch_raises@77(6) |
| 5 | `tests/test_no_fabricated_significance.py` | 2 | 15 | near | test_cross_area_coherence_refuses_like_its_siblings@85(7), test_cross_modal_comparison_refuses_rather_than_flipping_to_significant@108(8) |
| 5 | `tests/test_jrsa_provenance.py` | 3 | 13 | near | test_the_recorded_seed_is_the_random_state_that_was_used@140(4), test_the_seed_alias_round_trips_too@156(4), test_the_request_is_still_kept_where_requests_go@186(5) |
| 5 | `tests/test_jnwb_core.py` | 2 | 15 | near | test_extract_band_theta@122(8), test_extract_band_with_small_array@285(7) |
| 5 | `tests/test_harness_adversarial_gates.py` | 2 | 16 | near | test_phantom_api_row_is_caught@346(9), test_stale_install_pin_in_prose_is_caught@375(7) |
| 5 | `tests/test_harness_adversarial_gates.py` | 2 | 15 | near | test_a_bare_directory_in_a_writes_field_is_rejected@1562(7), test_an_unescaped_pipe_inside_a_code_span_is_rejected@1665(8) |
| 5 | `tests/test_gate8_covers_every_version_surface.py` | 3 | 12 | near | test_a_skewed_floor_fails@52(4), test_a_skewed_tested_set_fails@59(4), test_a_surface_that_stops_stating_the_floor_fails@83(4) |
| 5 | `tests/test_figure_form.py` | 2 | 16 | near | test_the_smallest_text_is_legible_where_the_page_shows_it@1170(7), test_the_smallest_text_is_legible_at_the_mobile_width@1180(9) |
| 5 | `tests/test_device_denial_contract.py` | 2 | 14 | near | test_granger_causality_says_so_too@134(7), test_select_optimal_lag_says_so_too@142(7) |
| 5 | `tests/test_container_type_contradiction.py` | 2 | 17 | near | test_the_mistyped_warning_names_the_declared_type_and_the_contents@157(10), test_the_untyped_warning_says_nothing_declares_the_type@169(7) |
| 5 | `tests/test_batch_a_regressions.py` | 2 | 14 | near | test_onset_interior_unconstrained@25(7), test_onset_just_above_lower_bound@49(7) |
| 5 | `tests/test_api_md_is_interpreter_independent.py` | 2 | 16 | near | test_private_stdlib_submodule_collapses_when_parent_reexports@53(9), test_public_submodule_is_left_alone@63(7) |
| 4 | `tests/test_visual_qc.py` | 2 | 14 | near | test_plot_unit_quality_distribution_returns_populated_figure@184(8), test_plot_noise_vs_signal_returns_2x2_figure@239(6) |
| 4 | `tests/test_tfr_extract_band_regressions.py` | 2 | 15 | near | test_mismatched_coordinates_raises_error@66(6), test_empty_requested_band_raises_error_not_zeros@102(9) |
| 4 | `tests/test_statistics.py` | 2 | 14 | near | test_naming_parametric_returns_none_of_the_other_test@796(8), test_naming_nonparametric_returns_none_of_the_other_test@806(6) |
| 4 | `tests/test_shuffle_pvalues_are_ranks.py` | 2 | 13 | same-name | test_the_value_is_neither_the_floor_nor_one@70(7), test_the_value_is_neither_the_floor_nor_one@112(6) |
| 4 | `tests/test_pca_device_parity.py` | 2 | 16 | near | test_float32_stays_float32_because_that_is_what_numpy_linalg_does@212(6), test_float16_is_promoted_rather_than_rejected@219(10) |
| 4 | `tests/test_metadata.py` | 2 | 12 | near | test_quality_one_above_thresholds_is_stable@327(6), test_quality_one_below_thresholds_is_unstable@334(6) |
| 4 | `tests/test_jnwb_core.py` | 2 | 14 | near | test_autocorrelogram_valid_spikes_returns_dict@168(6), test_quality_metrics_returns_dict@175(8) |
| 4 | `tests/test_gates_reject_the_trees_they_passed.py` | 2 | 12 | near | test_an_intact_corpus_reports_nothing@570(6), test_an_external_link_is_not_resolved@585(6) |
| 4 | `tests/test_device_denial_contract.py` | 2 | 13 | near | test_granger_causality_never_names_its_private_helper@168(7), test_select_optimal_lag_never_names_it_either@176(6) |
| 4 | `tests/test_declared_return_shapes.py` | 2 | 12 | near | test_it_returns_trials_by_bins@72(6), test_the_bin_count_follows_the_window_and_width@79(6) |
| 4 | `tests/test_composition_randomness.py` | 2 | 12 | near | test_one_seed_reproduces_byte_identically@335(6), test_n_jobs_does_not_move_a_digit@342(6) |
| 4 | `tests/test_ci_conclusion_gate.py` | 2 | 12 | near | test_one_leg_failure_fails@154(6), test_one_leg_cancelled_fails@162(6) |
| 4 | `tests/test_axis_convention_matches_the_specification.py` | 2 | 12 | near | test_an_explicit_axis_settles_it@193(6), test_a_transpose_settles_it@200(6) |
| 3 | `tests/test_statistics.py` | 2 | 12 | near | test_reversed_window_is_rejected@58(5), test_reversed_or_empty_window_is_rejected@110(7) |
| 3 | `tests/test_statistics.py` | 2 | 11 | near | test_rate_computation@84(5), test_exact_boundary_conditions_right_open@90(6) |
| 3 | `tests/test_skill_symbol_coverage.py` | 2 | 10 | near | test_excluded_ontology_types_come_from_the_ontology_module@236(5), test_excluded_analyzers_are_classes_in_the_analyzers_module@271(5) |
| 3 | `tests/test_rsa_oracle.py` | 2 | 10 | near | test_zero_variance_condition_is_rejected_under_correlation@75(5), test_zero_norm_condition_is_rejected_under_cosine@81(5) |
| 3 | `tests/test_release_body_script.py` | 2 | 12 | near | test_a_prerelease_version_is_refused@92(5), test_a_section_that_misstates_the_python_range_is_refused@98(7) |
| 3 | `tests/test_nwb_events.py` | 2 | 10 | near | test_numeric_codes@141(5), test_task_only_fallback@147(5) |
| 3 | `tests/test_mutation_harness_validity.py` | 2 | 10 | near | test_an_anchor_that_matches_nothing_is_refused@295(5), test_an_anchor_that_matches_twice_is_refused@302(5) |
| 3 | `tests/test_jrsa_no_fabricated_failures.py` | 2 | 10 | near | test_pearson_raises_on_insufficient_samples@32(5), test_spearman_raises_on_insufficient_samples@38(5) |
| 3 | `tests/test_jrsa_correctness.py` | 2 | 12 | near | test_three_dimensional_inputs_are_flattened_per_sample@555(7), test_mixed_dimensionality_matches_the_flattened_pair@568(5) |
| 3 | `tests/test_jrsa_correctness.py` | 2 | 11 | near | test_an_unknown_keyword_is_an_error_not_a_default_answer@755(5), test_a_metric_option_belonging_to_another_metric_is_rejected@761(6) |
| 3 | `tests/test_independent_audit_semantics.py` | 2 | 10 | near | test_renamed_granger_metric_rejects_legacy_alias@172(5), test_renamed_te_metric_rejects_legacy_alias@185(5) |
| 3 | `tests/test_harness_adversarial_gates.py` | 2 | 11 | near | test_an_include_that_resolves_to_nothing_is_a_failure@1371(5), test_a_page_matching_no_rows_is_reported_rather_than_passing@2160(6) |
| 3 | `tests/test_harness_adversarial_gates.py` | 2 | 10 | near | test_a_missing_todo_stack_is_reported_rather_than_passing@1623(5), test_a_missing_problem_stack_is_reported_rather_than_passing@1635(5) |
| 3 | `tests/test_execution_switch.py` | 2 | 10 | near | test_a_cuda_failure_midway_is_announced_and_recorded@275(5), test_cuda_without_a_device_warns_and_names_the_cpu@282(5) |
| 3 | `tests/test_acquisition_layout.py` | 2 | 10 | near | test_the_h5py_path_reads_the_electrode_count@279(5), test_the_pynwb_path_reads_the_electrode_count@285(5) |
| 2 | `tests/test_tutorial_00_foreign_shapes.py` | 2 | 10 | same-name | test_it_does_not_claim_to_have_aligned_anything@132(6), test_it_does_not_claim_to_have_aligned_anything@195(4) |
| 2 | `tests/test_statistics_api_split.py` | 2 | 9 | near | test_no_q_value_keys@32(5), test_no_deprecated_fdr_keys@38(4) |
| 2 | `tests/test_statistics.py` | 2 | 8 | same-name | test_too_few_trials_is_undefined@166(4), test_too_few_trials_is_undefined@187(4) |
| 2 | `tests/test_stack_edit.py` | 2 | 8 | near | test_refuses_a_prefix_matching_no_bullet@196(4), test_refuses_a_prefix_matching_a_continuation_line@215(4) |
| 2 | `tests/test_stack_edit.py` | 2 | 8 | near | test_delete_preserves_every_other_byte@72(4), test_section_selects_one_of_two_same_prefix_bullets@230(4) |
| 2 | `tests/test_spiking.py` | 2 | 8 | near | test_reversed_or_empty_baseline_window_raises@107(4), test_reversed_or_empty_response_window_raises@113(4) |
| 2 | `tests/test_spectral_nonfabrication.py` | 2 | 8 | near | test_band_without_bins_is_rejected@46(4), test_unrecognised_device_is_rejected@109(4) |
| 2 | `tests/test_spectral.py` | 2 | 10 | same-name | test_listed_in_jnwb_all@64(4), test_listed_in_jnwb_all@171(6) |
| 2 | `tests/test_spectral.py` | 2 | 8 | near | test_invalid_n_surrogates_rejected@905(4), test_unknown_band_string_raises@997(4) |
| 2 | `tests/test_spectral.py` | 2 | 23 | near | test_importable_from_top_level_jnwb@44(19), test_importable_from_top_level@642(4) |
| 2 | `tests/test_spectral.py` | 2 | 8 | near | test_drops_one_channel@347(4), test_preserves_channel_count@383(4) |
| 2 | `tests/test_release_body_gate.py` | 2 | 8 | near | test_a_bare_mention_of_an_unsupported_version_is_rejected@233(4), test_every_install_command_is_checked_not_only_the_first@263(4) |
| 2 | `tests/test_ontology.py` | 2 | 8 | near | test_failure@483(4), test_decline@488(4) |
| 2 | `tests/test_lane_verifies_its_own_baseline.py` | 2 | 8 | near | test_a_tree_at_its_baseline_passes@138(4), test_the_main_checkout_can_be_permitted_deliberately@162(4) |
| 2 | `tests/test_harness_adversarial_gates.py` | 2 | 8 | near | test_an_empty_skills_tree_is_reported_rather_than_passing@2069(4), test_an_empty_agents_directory_is_reported_rather_than_passing@2074(4) |
| 2 | `tests/test_harness_adversarial_gates.py` | 2 | 13 | near | test_an_empty_docs_tree_is_a_failure_and_not_a_pass@1244(9), test_an_empty_library_tree_is_a_failure_and_not_a_pass@1314(4) |
| 2 | `tests/test_harness_adversarial_gates.py` | 2 | 10 | near | test_a_glob_is_not_a_bare_directory@1570(4), test_an_escaped_pipe_inside_a_code_span_is_content@1674(6) |
| 2 | `tests/test_generated_files_are_byte_stable.py` | 2 | 9 | near | test_it_flags_a_write_text_that_omits_newline@85(4), test_a_keyword_named_elsewhere_does_not_count_as_passing_newline@100(5) |
| 2 | `tests/test_epoch_onset_sanity.py` | 2 | 9 | near | test_it_no_longer_returns_a_zero_width_epoch@148(5), test_every_boundary_policy_refuses_it@161(4) |
| 2 | `tests/test_dependency_floors_are_installable.py` | 2 | 8 | near | test_a_floor_whose_release_excludes_the_interpreter_is_refused@93(4), test_a_floor_above_everything_published_is_refused@133(4) |
| 2 | `tests/test_composition_randomness.py` | 2 | 8 | near | test_one_seed_reproduces_byte_identically@271(4), test_n_jobs_does_not_move_a_digit@276(4) |
| 2 | `tests/test_analyzers_coverage.py` | 2 | 8 | near | test_extract_band_alpha@66(4), test_extract_band_beta@71(4) |

## 5. Boundary test calls the gate's check (done)

`tests/test_jnwb_frozen_boundary.py` re-implemented the import scan of `check_frozen_boundary`
in `scripts/harness_gate.py`. It now calls it, for `jnwb/` and for `tests/`, and exercises it on
a fixture tree with imports at module level and in a function body, with and without two
authorized exceptions. The earlier lazy-exception test iterated an empty set; the fixture now
reaches the `NON_LAZY_IMPORT` branch. 176 to 137 lines, 6 to 5 tests.

| Mutant | Change | Selector | Pristine | Mutant |
|---|---|---|---|---|
| GB1 | the scan matches no omission import | fixture test | pass | killed |
| GB2 | an authorized module-level import is no longer refused | fixture test | pass | killed |
| GB3 | no import counts as module level | fixture test | pass | killed |
| GB4 | `jnwb/_backend.py` gains a function-local `import omission.alpha` | `jnwb/` scan test | pass | killed |
| GB5 | `tests/test_import_lazy.py` gains a function-local `import omission.beta` | `tests/` scan test | pass | killed |

## 6. Saving if every proposal is accepted

| Proposal | Lines | Tests | Summed test time (s) |
|---|---:|---:|---:|
| Delete the three candidates | 1254 | 65 | 137 (about 11 s wall at `-n 12`) |
| Parametrise the 92 clusters | about 487 gross | 0 | about 0 |
| Boundary rewrite (done) | 39 | 1 | under 1 |
| Total | about 1780 | 66 | about 138 |

Of the 75529 lines and 7170 tests in `tests/`, that is about 2.4% of lines and 0.9% of tests.
The other 64 zero-unique files (14381 lines, 1017 tests) stay until a mutant on each one's
purpose is run.
