# Suite profile: 0.2.15 (bc76209c)

Run SHA: `bc76209c14e9e3fb05a96fb6d7dfc21dcf228045`.
Command: `pytest tests/ -q -n 12 -p no:cacheprovider --durations=0 --junitxml=...`.
Platform: Windows, Python 3.14.3 (integrator run, 2026-11-01).
Wall: 973.88 s. Summary: `5 failed, 10580 passed, 83 skipped, 58 xfailed`.
The five failures are known and repaired separately; the per-file table below is the
integrator's `artifacts/_temp/profile_files_bc76209c.md`, copied with every row kept
(269 files, 10726 tests, 9610.3 summed call seconds).

## Per-file table

| File | Tests | Seconds | Slowest test |
|---|---:|---:|---:|
| `tests/test_figure_form.py` | 1548 | 1843.2 | 142.7 |
| `tests/test_fact_gate.py` | 300 | 856.5 | 139.8 |
| `tests/test_release_requires_an_empty_open_stack.py` | 188 | 845.2 | 9.8 |
| `tests/test_state_reconstruction.py` | 23 | 524.7 | 178.8 |
| `tests/test_build_dashboard.py` | 67 | 334.5 | 29.9 |
| `tests/test_coherence_pitfall_estimators.py` | 25 | 248.5 | 64.0 |
| `tests/test_jrsa_sliding.py` | 26 | 238.3 | 231.3 |
| `tests/test_semantic_mutation_classes.py` | 22 | 212.5 | 212.3 |
| `tests/test_mutation_harness_validity.py` | 88 | 163.4 | 10.1 |
| `tests/test_bump_version.py` | 10 | 152.0 | 139.6 |
| `tests/test_xflip_homogeneous_null.py` | 7 | 144.9 | 116.6 |
| `tests/test_wavemap.py` | 56 | 130.7 | 40.6 |
| `tests/test_docs_operation_statements.py` | 54 | 125.6 | 55.2 |
| `tests/test_tutorial_00_foreign_shapes.py` | 28 | 123.4 | 8.3 |
| `tests/test_vflip2_recovery.py` | 12 | 122.6 | 68.1 |
| `tests/test_parallel.py` | 25 | 118.7 | 39.8 |
| `tests/test_tutorials.py` | 13 | 117.8 | 47.6 |
| `tests/test_composition_randomness.py` | 17 | 116.8 | 20.2 |
| `tests/test_curation_calibration_receipt.py` | 23 | 104.0 | 98.9 |
| `tests/test_import_provenance.py` | 21 | 102.4 | 18.0 |
| `tests/test_every_gate_runs.py` | 30 | 99.2 | 82.1 |
| `tests/test_state_basis_is_checked.py` | 8 | 96.9 | 83.8 |
| `tests/test_fusion_agreement.py` | 17 | 92.2 | 88.2 |
| `tests/test_zflip_audit.py` | 50 | 91.7 | 9.3 |
| `tests/test_learning_gate.py` | 26 | 89.1 | 85.5 |
| `tests/test_api_md_is_interpreter_independent.py` | 7 | 85.5 | 85.4 |
| `tests/test_xflip_calibration.py` | 33 | 84.5 | 27.2 |
| `tests/test_the_suite_can_qualify_an_installed_copy.py` | 45 | 80.2 | 49.1 |
| `tests/test_notebooks.py` | 10 | 71.6 | 17.0 |
| `tests/test_collection_order_stability.py` | 18 | 70.1 | 31.1 |
| `tests/test_dashboard_page.py` | 16 | 67.2 | 67.0 |
| `tests/test_figure_registry_current.py` | 37 | 66.1 | 17.3 |
| `tests/test_docs_call_shapes.py` | 59 | 64.7 | 46.4 |
| `tests/test_diagrams_render.py` | 12 | 62.6 | 14.4 |
| `tests/test_declared_return_shapes.py` | 17 | 61.1 | 49.1 |
| `tests/test_import_lazy.py` | 14 | 58.9 | 9.2 |
| `tests/test_release_recovery_gates.py` | 23 | 58.2 | 24.1 |
| `tests/test_workflow_release_policy.py` | 93 | 55.2 | 15.6 |
| `tests/test_nonfinite_inputs.py` | 281 | 54.1 | 39.6 |
| `tests/test_jrsa_correctness.py` | 323 | 51.3 | 9.8 |
| `tests/test_connectivity_pitfalls.py` | 56 | 47.9 | 4.3 |
| `tests/test_execution_switch.py` | 116 | 45.1 | 14.3 |
| `tests/test_laminar_curation.py` | 116 | 43.2 | 4.3 |
| `tests/test_optional_vis_extra.py` | 7 | 43.2 | 13.7 |
| `tests/test_vflip2_sensitivity.py` | 3 | 42.8 | 36.0 |
| `tests/test_vis_wavemap.py` | 15 | 41.8 | 41.4 |
| `tests/test_generated_figures_are_maintained.py` | 75 | 41.8 | 5.9 |
| `tests/test_nwb_write.py` | 70 | 40.9 | 1.9 |
| `tests/test_shuffle_pvalues_are_ranks.py` | 39 | 40.2 | 11.1 |
| `tests/test_axis_convention_matches_the_specification.py` | 156 | 40.2 | 31.5 |
| `tests/test_vflip2_simulation.py` | 4 | 31.9 | 29.6 |
| `tests/test_connectivity.py` | 188 | 31.2 | 4.8 |
| `tests/test_api_md_member_types.py` | 14 | 31.1 | 30.5 |
| `tests/test_nwb_inspect.py` | 70 | 27.9 | 0.9 |
| `tests/test_zflip_window.py` | 29 | 27.4 | 3.9 |
| `tests/test_release_contains_main.py` | 8 | 25.6 | 4.9 |
| `tests/test_mcp_server.py` | 27 | 23.9 | 7.6 |
| `tests/test_import_profile_receipt.py` | 16 | 21.7 | 9.9 |
| `tests/test_examples_quickstart.py` | 4 | 21.1 | 8.8 |
| `tests/test_onset_fitting.py` | 53 | 20.9 | 12.4 |
| `tests/test_acquisition_layout.py` | 38 | 20.4 | 4.4 |
| `tests/test_decoding.py` | 53 | 19.9 | 4.8 |
| `tests/test_harness_adversarial_gates.py` | 240 | 19.8 | 2.2 |
| `tests/test_lane_verifies_its_own_baseline.py` | 16 | 19.6 | 3.3 |
| `tests/test_statistics.py` | 242 | 18.7 | 5.6 |
| `tests/test_skills_validation.py` | 96 | 17.6 | 10.0 |
| `tests/test_xflip_window.py` | 26 | 17.3 | 4.3 |
| `tests/test_vflip2_nuisance.py` | 6 | 17.1 | 16.9 |
| `tests/test_open_data_example.py` | 7 | 16.3 | 5.6 |
| `tests/test_compression.py` | 159 | 15.9 | 1.3 |
| `tests/test_nwb_events.py` | 42 | 15.7 | 0.7 |
| `tests/test_jnwb_frozen_boundary.py` | 6 | 15.6 | 6.4 |
| `tests/test_vflip2.py` | 28 | 15.4 | 4.2 |
| `tests/test_vflip2_from_lfp.py` | 25 | 14.6 | 6.9 |
| `tests/test_jrsa.py` | 51 | 14.1 | 3.5 |
| `tests/test_line_endings_survive_an_edit.py` | 16 | 14.0 | 1.7 |
| `tests/test_container_type_contradiction.py` | 11 | 13.9 | 9.8 |
| `tests/test_substitution_class_sweep.py` | 41 | 13.7 | 7.5 |
| `tests/test_docs_nwb_workflow.py` | 22 | 13.5 | 8.7 |
| `tests/test_gates_reject_the_trees_they_passed.py` | 64 | 13.4 | 0.9 |
| `tests/test_release_gate_receipt_history.py` | 5 | 11.8 | 6.2 |
| `tests/test_hdmf_nwb_read_boundary.py` | 10 | 11.6 | 4.8 |
| `tests/test_computational_order_sources_agree.py` | 11 | 11.4 | 11.1 |
| `tests/test_spectral.py` | 268 | 11.4 | 1.5 |
| `tests/test_visual_qc.py` | 22 | 11.2 | 1.8 |
| `tests/test_test_imports_survive_the_wheel_leg.py` | 6 | 11.1 | 4.5 |
| `tests/test_errors_documented.py` | 82 | 11.0 | 5.9 |
| `tests/test_gate2_ignores_nested_checkouts.py` | 23 | 10.5 | 1.0 |
| `tests/test_xflip.py` | 76 | 10.5 | 5.0 |
| `tests/test_ontology.py` | 135 | 10.1 | 9.8 |
| `tests/test_zflip.py` | 50 | 10.1 | 1.2 |
| `tests/test_agents_md_stays_a_router.py` | 6 | 10.1 | 2.1 |
| `tests/test_rng_control.py` | 58 | 10.0 | 3.7 |
| `tests/test_claim_vocabulary_prose.py` | 2 | 9.9 | 5.1 |
| `tests/test_xflip_calibration_receipt.py` | 12 | 9.8 | 7.5 |
| `tests/test_claim_wording.py` | 8 | 9.4 | 7.2 |
| `tests/test_docs_form_gate.py` | 39 | 9.3 | 3.9 |
| `tests/test_nwb_synthetic_fixtures.py` | 19 | 9.2 | 0.9 |
| `tests/test_nwb_read_tolerance_and_visibility.py` | 31 | 9.0 | 0.6 |
| `tests/test_metadata.py` | 102 | 8.8 | 1.0 |
| `tests/test_laminar.py` | 79 | 8.7 | 1.7 |
| `tests/test_execution_api.py` | 23 | 8.7 | 6.3 |
| `tests/test_representative_workflow.py` | 6 | 8.5 | 7.7 |
| `tests/test_figure_theme_in_chromium.py` | 1 | 8.5 | 8.5 |
| `tests/test_rng_convention_matches_the_signatures.py` | 14 | 8.3 | 4.8 |
| `tests/test_batch_a_regressions.py` | 17 | 8.2 | 1.3 |
| `tests/test_inspect_one_schema.py` | 19 | 7.9 | 0.8 |
| `tests/test_changelog_fragments.py` | 18 | 7.6 | 3.7 |
| `tests/test_jrsa_correction_fallback.py` | 31 | 6.8 | 2.1 |
| `tests/test_jnwb_core.py` | 26 | 6.8 | 4.0 |
| `tests/test_no_fabricated_significance.py` | 21 | 6.7 | 5.1 |
| `tests/test_nam.py` | 3 | 6.7 | 3.3 |
| `tests/test_unit_quality_screen.py` | 23 | 6.4 | 2.3 |
| `tests/test_skill_examples_execute.py` | 37 | 6.3 | 2.3 |
| `tests/test_fact_graph_boundary_units.py` | 9 | 6.2 | 6.0 |
| `tests/test_gitignore_excludes_cache_by_path.py` | 19 | 6.0 | 0.7 |
| `tests/test_decoding_labels.py` | 35 | 5.8 | 1.4 |
| `tests/test_composition_band_comparison.py` | 4 | 5.5 | 1.9 |
| `tests/test_nwb_integrity.py` | 78 | 5.4 | 0.3 |
| `tests/test_addressing.py` | 103 | 5.3 | 0.9 |
| `tests/test_gpu_launch_overhead.py` | 51 | 4.9 | 0.6 |
| `tests/test_rng_parameters_by_use.py` | 5 | 4.7 | 1.7 |
| `tests/test_spiking.py` | 111 | 4.4 | 1.1 |
| `tests/test_jrsa_gpu.py` | 11 | 4.4 | 4.3 |
| `tests/test_module_docstrings_match_their_code.py` | 36 | 4.1 | 0.9 |
| `tests/test_docs_smoke.py` | 10 | 4.0 | 1.5 |
| `tests/test_vflip_calibration_receipt.py` | 9 | 3.7 | 3.2 |
| `tests/test_tests_draw_from_seeded_generators.py` | 2 | 3.6 | 3.6 |
| `tests/test_minimal_units_table.py` | 17 | 3.4 | 0.3 |
| `tests/test_docs_links.py` | 5 | 3.4 | 2.3 |
| `tests/test_nwb_validate.py` | 13 | 3.3 | 0.7 |
| `tests/test_prose_version_claims_are_live.py` | 52 | 3.2 | 1.7 |
| `tests/test_readme_smoke.py` | 7 | 3.2 | 1.6 |
| `tests/test_pca_device_parity.py` | 23 | 3.1 | 1.1 |
| `tests/test_harness_gate.py` | 23 | 3.1 | 2.4 |
| `tests/test_every_declaration_has_a_caller.py` | 7 | 3.0 | 1.7 |
| `tests/test_api_consistency.py` | 104 | 3.0 | 0.4 |
| `tests/test_agents_md_recipes.py` | 7 | 2.9 | 1.6 |
| `tests/test_open_data_through_the_agent_surface.py` | 11 | 2.8 | 1.0 |
| `tests/test_push_guard.py` | 3 | 2.6 | 1.4 |
| `tests/test_stack_edit.py` | 62 | 2.6 | 0.6 |
| `tests/test_vis.py` | 77 | 2.6 | 0.6 |
| `tests/test_statistics_api_split.py` | 35 | 2.5 | 0.2 |
| `tests/test_skill_decline_behaviour.py` | 74 | 2.5 | 0.6 |
| `tests/test_independent_audit_semantics.py` | 33 | 2.4 | 2.1 |
| `tests/test_jrsa_provenance.py` | 26 | 2.4 | 2.0 |
| `tests/test_dependency_floors_are_installable.py` | 19 | 2.3 | 0.9 |
| `tests/test_figure_interactive.py` | 6 | 2.3 | 0.7 |
| `tests/test_api_surface.py` | 11 | 2.2 | 2.0 |
| `tests/test_frozen_validated.py` | 10 | 2.2 | 1.9 |
| `tests/test_public_api_reachability.py` | 124 | 2.1 | 0.7 |
| `tests/test_vis_export_session.py` | 10 | 2.1 | 0.6 |
| `tests/test_a_silent_no_op_is_refused.py` | 12 | 2.0 | 0.5 |
| `tests/test_xflip_nuisance.py` | 6 | 2.0 | 2.0 |
| `tests/test_no_unreferenced_symbols.py` | 3 | 1.9 | 1.9 |
| `tests/test_analyzers_coverage.py` | 72 | 1.8 | 0.2 |
| `tests/test_cross_modal_comparison_faces_agree.py` | 13 | 1.8 | 0.6 |
| `tests/test_generated_files_are_byte_stable.py` | 23 | 1.8 | 0.2 |
| `tests/test_io.py` | 63 | 1.8 | 0.7 |
| `tests/test_composition_axis.py` | 16 | 1.7 | 0.4 |
| `tests/test_backend.py` | 29 | 1.7 | 0.9 |
| `tests/test_gate8_covers_every_version_surface.py` | 11 | 1.7 | 0.2 |
| `tests/test_distribution_manifest_inspection.py` | 24 | 1.6 | 1.4 |
| `tests/test_dict_access_shim.py` | 62 | 1.6 | 1.6 |
| `tests/test_release_body_script.py` | 10 | 1.5 | 0.7 |
| `tests/test_documentation_form.py` | 45 | 1.5 | 0.4 |
| `tests/test_tfr_accumulator.py` | 81 | 1.5 | 0.4 |
| `tests/test_unit_suffixed_parameters.py` | 49 | 1.5 | 0.9 |
| `tests/test_jrsa_result_io.py` | 19 | 1.4 | 0.4 |
| `tests/test_docs_interpretation_statements.py` | 10 | 1.4 | 1.3 |
| `tests/test_adversarial_inputs.py` | 104 | 1.3 | 0.6 |
| `tests/test_switch_rebinding_is_reviewed.py` | 3 | 1.3 | 1.3 |
| `tests/test_connectivity_reporting.py` | 12 | 1.3 | 0.2 |
| `tests/test_rsa.py` | 8 | 1.3 | 1.3 |
| `tests/test_testing_synth.py` | 36 | 1.2 | 0.4 |
| `tests/test_computational_contract_gate.py` | 5 | 1.2 | 0.7 |
| `tests/test_dashboard_workflow.py` | 13 | 1.2 | 0.4 |
| `tests/test_release_body_gate.py` | 53 | 1.1 | 0.7 |
| `tests/test_device_denial_contract.py` | 21 | 1.1 | 0.7 |
| `tests/test_estimator_values_are_pinned.py` | 38 | 1.1 | 0.3 |
| `tests/test_docs_user_navigation.py` | 11 | 1.0 | 0.3 |
| `tests/test_continuous.py` | 43 | 0.9 | 0.8 |
| `tests/test_r_squared.py` | 11 | 0.9 | 0.9 |
| `tests/test_viz.py` | 18 | 0.8 | 0.8 |
| `tests/test_skill_symbol_coverage.py` | 20 | 0.8 | 0.5 |
| `tests/test_estimator_discrimination.py` | 9 | 0.7 | 0.5 |
| `tests/test_precision_switch.py` | 17 | 0.7 | 0.5 |
| `tests/test_vis_drawn_data.py` | 18 | 0.6 | 0.1 |
| `tests/test_shipped_code_names_no_process_ids.py` | 2 | 0.6 | 0.6 |
| `tests/test_probe_axis_sign_is_pinned.py` | 85 | 0.6 | 0.1 |
| `tests/test_spectral_nonfabrication.py` | 23 | 0.6 | 0.4 |
| `tests/test_skill_degenerate_claims.py` | 9 | 0.5 | 0.1 |
| `tests/test_frozen_core_mutants.py` | 10 | 0.5 | 0.3 |
| `tests/test_references_resolve.py` | 18 | 0.5 | 0.2 |
| `tests/test_laminar_index_space_and_boundary.py` | 53 | 0.5 | 0.1 |
| `tests/test_nwb_inspect_silent.py` | 8 | 0.4 | 0.2 |
| `tests/test_epoch_onset_sanity.py` | 27 | 0.4 | 0.4 |
| `tests/test_complex_tfr.py` | 44 | 0.4 | 0.1 |
| `tests/test_paths.py` | 48 | 0.4 | 0.1 |
| `tests/test_artifact_repair.py` | 36 | 0.4 | 0.1 |
| `tests/test_signal_class.py` | 25 | 0.4 | 0.2 |
| `tests/test_pointer_documents_resolve.py` | 18 | 0.3 | 0.2 |
| `tests/test_vis_label_range_edges.py` | 10 | 0.3 | 0.1 |
| `tests/test_decoding_nested_cv_pins.py` | 2 | 0.3 | 0.2 |
| `tests/test_docs_decoding_chain.py` | 8 | 0.3 | 0.2 |
| `tests/test_architecture_page_reachability.py` | 12 | 0.3 | 0.1 |
| `tests/test_composition_aggregation_order.py` | 32 | 0.3 | 0.1 |
| `tests/test_stack_metadata_contradictions.py` | 66 | 0.3 | 0.0 |
| `tests/test_single_agent_instruction_file.py` | 6 | 0.3 | 0.1 |
| `tests/test_skill_routing_behaviour.py` | 6 | 0.3 | 0.2 |
| `tests/test_skills_are_findable_from_an_installed_copy.py` | 11 | 0.3 | 0.1 |
| `tests/test_channel_axis_is_not_assumed.py` | 11 | 0.3 | 0.0 |
| `tests/test_vis_shared_rules.py` | 16 | 0.2 | 0.0 |
| `tests/test_majority_baselines_agree.py` | 22 | 0.2 | 0.2 |
| `tests/test_rng_spelling.py` | 56 | 0.2 | 0.0 |
| `tests/test_ci_conclusion_gate.py` | 29 | 0.2 | 0.1 |
| `tests/test_composition_identifier_survival.py` | 9 | 0.2 | 0.1 |
| `tests/test_no_silent_truncation.py` | 25 | 0.2 | 0.1 |
| `tests/test_public_surface_manifest.py` | 4 | 0.2 | 0.1 |
| `tests/test_vis_draws_no_default_landmark.py` | 5 | 0.2 | 0.2 |
| `tests/test_paths_identity.py` | 14 | 0.2 | 0.0 |
| `tests/test_staggered_shafts.py` | 23 | 0.2 | 0.0 |
| `tests/test_xflip_null_method.py` | 13 | 0.1 | 0.0 |
| `tests/test_rsa_oracle.py` | 65 | 0.1 | 0.0 |
| `tests/test_obligation_diff.py` | 5 | 0.1 | 0.1 |
| `tests/test_skill_router_reach.py` | 35 | 0.1 | 0.0 |
| `tests/test_figure_tabs_and_state.py` | 7 | 0.1 | 0.1 |
| `tests/test_synthetic_figures_are_labelled.py` | 5 | 0.1 | 0.1 |
| `tests/test_permutation.py` | 42 | 0.1 | 0.0 |
| `tests/test_release_version_is_unpublished.py` | 14 | 0.1 | 0.1 |
| `tests/test_granger_order_validation.py` | 22 | 0.1 | 0.0 |
| `tests/test_skill_default_claims_match_signatures.py` | 2 | 0.1 | 0.1 |
| `tests/test_generation_closure_is_declared.py` | 13 | 0.1 | 0.0 |
| `tests/test_unit_quality.py` | 49 | 0.1 | 0.0 |
| `tests/test_vis_heatmap_ribbon_sem.py` | 6 | 0.1 | 0.1 |
| `tests/test_docs_runnable_prerequisites.py` | 4 | 0.1 | 0.0 |
| `tests/test_optional_dependencies.py` | 2 | 0.1 | 0.1 |
| `tests/test_composition_failure_propagation.py` | 12 | 0.1 | 0.0 |
| `tests/test_trajectory.py` | 20 | 0.1 | 0.0 |
| `tests/test_integration_0_2_1.py` | 7 | 0.1 | 0.0 |
| `tests/test_zero_spread.py` | 11 | 0.1 | 0.0 |
| `tests/test_skill_claims_match_the_router.py` | 4 | 0.1 | 0.0 |
| `tests/test_effective_sample_size.py` | 10 | 0.0 | 0.0 |
| `tests/test_artifact_detection.py` | 11 | 0.0 | 0.0 |
| `tests/test_role_files_point_to_one_contract.py` | 13 | 0.0 | 0.0 |
| `tests/test_no_fabricated_spiking_and_repair.py` | 18 | 0.0 | 0.0 |
| `tests/test_api_md_experimental_section.py` | 2 | 0.0 | 0.0 |
| `tests/test_helper_rule_names.py` | 5 | 0.0 | 0.0 |
| `tests/test_filtering.py` | 9 | 0.0 | 0.0 |
| `tests/test_nonfinite_trial_starts_are_refused.py` | 16 | 0.0 | 0.0 |
| `tests/test_git_checkout_mark.py` | 4 | 0.0 | 0.0 |
| `tests/test_jaxfne_ground_truth.py` | 4 | 0.0 | 0.0 |
| `tests/test_addressing_silent.py` | 8 | 0.0 | 0.0 |
| `tests/test_standing_rules_name_no_cycle.py` | 3 | 0.0 | 0.0 |
| `tests/test_tfr_container.py` | 9 | 0.0 | 0.0 |
| `tests/test_reference_claims_ledger.py` | 4 | 0.0 | 0.0 |
| `tests/test_findings_ledger.py` | 6 | 0.0 | 0.0 |
| `tests/test_tfr_extract_band_regressions.py` | 12 | 0.0 | 0.0 |
| `tests/test_calibration_hash_walker.py` | 2 | 0.0 | 0.0 |
| `tests/test_audit_reproducers.py` | 3 | 0.0 | 0.0 |
| `tests/test_deprecated_aliases.py` | 3 | 0.0 | 0.0 |
| `tests/test_window_default_deprecation.py` | 6 | 0.0 | 0.0 |
| `tests/test_uncovered_exports.py` | 7 | 0.0 | 0.0 |
| `tests/test_jrsa_no_fabricated_failures.py` | 7 | 0.0 | 0.0 |
| `tests/test_figure_sources_outside_docs.py` | 2 | 0.0 | 0.0 |
| `tests/test_laminar_silent.py` | 3 | 0.0 | 0.0 |
| `tests/test_gpu_pca.py` | 4 | 0.0 | 0.0 |
| `tests/test_psd_silent.py` | 2 | 0.0 | 0.0 |
| `tests/test_stack_item_length.py` | 2 | 0.0 | 0.0 |

Files 269; tests 10726; summed seconds 9610.3

## 0.2.14 comparison (rows D13-D19)

0.2.14 inventory (`artifacts/evidence/0.2.14/verification_inventory.md`, baseline
7e25090b, 2026-10-21) measures D1-D10 under release-gate load (runtimes "from _rgm4.txt
timestamps", the `scripts/release_gate.py` log) and D11-D20 from a `-n 4` run's
`durations.txt`. The comparison below is directional: different load, different
parallelism (`-n 4` vs `-n 12`), and different phase mixes.

| Row | 0.2.14 (phase, value) | 0.2.15 (phase, value) | Phase match |
|---|---|---|---|
| D13-D16 `figure_form` faint-ink setups | setup, 78.55-79.73 s each | setup, 133.6-142.3 s each (`slowest_60`); per-file slowest 142.7 s | setup both |
| D17 `vflip2_recovery` recovery table | call, 36.39 s | call, 68.08 s (per-file slowest 68.1 s) | call both |
| D18 `fact_gate` two-builds byte-identical | call, 35.28 s | call, 139.75 s (per-file slowest 139.8 s) | call both |
| D19 `state_reconstruction` deterministic generation | setup, 33.33 s | slowest single phase is call, 94.75 s; per-file slowest 178.8 s sums that call with the same test's 84.06 s setup (both phases appear in `slowest_60`) | differs: setup then, summed phases now |

The shape is unchanged: figure rendering, generation determinism, and byte-identity
probes hold the tail in both runs.

## Where the time goes

`tests/test_figure_form.py` alone holds 1843.2 of 9610.3 summed seconds (19.2%).
The top 5 files hold 4404.1 s (45.8%); the top 10 hold 5418.8 s (56.4%).
The 14 release-tier files of the tiered plan hold 4249.9 s (44.2%); the other 255 hold 55.8%.
