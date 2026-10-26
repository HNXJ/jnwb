# Prune record: process tests

Rule (ruled 2026-10-26, plant-covered only): a test is pruned only when each plant it owns fails it and a check kept whatever the verdicts also fails. No test is pruned here.
`measured` yes: a plant ran for the test. `measured` no: no plant ran, and the rule keeps the test.
Each plant edits the lane tree, runs its own tests, the test files that name the edited path and the harness gate, then restores the bytes and checks git status.
A mutual cover between two measured tests counts for neither, so both stay kept, marked undecided. `A<n>` is harness gate n; the probe class is the test's class, else its file's.

| # | file | function | measured | plant(s) | own test failed | other checks that failed | verdict | probe class |
|---|---|---|---|---|---|---|---|---|
| 1 | tests/test_findings_ledger.py | test_prose_and_index_agree_on_every_disposition | yes | FL2 | yes | - | keep (no other check fails) | ledger identity |
| 2 | tests/test_findings_ledger.py | test_every_prose_entry_is_in_the_index | yes | FL1 | yes | test_identifier_sets_match | keep (catchers are candidates too; undecided) | ledger identity |
| 3 | tests/test_findings_ledger.py | test_review_identifiers_are_extractable_and_unique | yes | FL5, FL6 | yes | test_identifier_sets_match | keep (no other check fails) | ledger identity |
| 4 | tests/test_findings_ledger.py | test_ledger_index_is_parseable_and_unique | yes | FL3 | yes | - | keep (no other check fails) | ledger identity |
| 5 | tests/test_findings_ledger.py | test_every_disposition_is_one_of_the_five | yes | FL4 | yes | - | keep (no other check fails) | ledger identity |
| 6 | tests/test_findings_ledger.py | test_identifier_sets_match | yes | FL1, FL5 | yes | test_every_prose_entry_is_in_the_index, test_review_identifiers_are_extractable_and_unique | keep (catchers are candidates too; undecided) | ledger identity |
| 7 | tests/test_single_agent_instruction_file.py | test_agents_md_is_the_only_tracked_root_instruction_file | no | none designed | - | - | keep (not measured) | instruction file |
| 8 | tests/test_single_agent_instruction_file.py | test_a_local_claude_md_is_ignored_rather_than_forbidden | yes | SA1 | yes | - | keep (no other check fails) | instruction file |
| 9 | tests/test_single_agent_instruction_file.py | test_no_live_surface_cites_a_file_that_is_no_longer_tracked | yes | SA2 | yes | - | keep (no other check fails) | instruction file |
| 10 | tests/test_single_agent_instruction_file.py | test_agents_md_states_that_it_is_the_only_one | yes | SA3 | yes | - | keep (no other check fails) | instruction file |
| 11 | tests/test_standing_rules_name_no_cycle.py | test_the_sweep_reads_the_rules_it_is_written_for | yes | S1 | yes | - | keep (no other check fails) | release labels |
| 12 | tests/test_standing_rules_name_no_cycle.py | test_no_standing_rule_names_a_literal_cycle_label | yes | S2 | yes | - | keep (no other check fails) | release labels |
| 13 | tests/test_standing_rules_name_no_cycle.py | test_the_pattern_finds_each_literal_form_and_passes_the_templates | yes | S3 | yes | - | keep (no other check fails) | release labels |
| 14 | tests/test_agents_md_stays_a_router.py | test_the_thresholds_the_counts_are_counts_of_are_pinned | yes | R1 | yes | - | keep (no other check fails) | agents router |
| 15 | tests/test_agents_md_stays_a_router.py | test_the_corpus_is_tracked_files_and_includes_the_published_agent_page | no | none designed | - | - | keep (not measured) | agents router |
| 16 | tests/test_agents_md_stays_a_router.py | test_the_script_measures_the_tree_it_lives_in | yes | R2, R3 | yes | A3 | keep (no other check fails) | agents router |
| 17 | tests/test_agents_md_stays_a_router.py | test_the_measurement_still_finds_something_to_measure | no | none designed | - | - | keep (not measured) | agents router |
| 18 | tests/test_agents_md_stays_a_router.py | test_duplicated_claims_do_not_increase | no | none designed | - | - | keep (not measured) | agents router |
| 19 | tests/test_agents_md_stays_a_router.py | test_echoed_claims_do_not_increase | no | none designed | - | - | keep (not measured) | agents router |
| 20 | tests/test_agents_md_stays_a_router.py | test_the_baseline_is_lowered_when_it_is_beaten | no | none designed | - | - | keep (not measured) | agents router |
| 21 | tests/test_release_recovery_gates.py | TestGrangercausalitytestsCompatibility::test_compat_omits_verbose_when_statsmodels_drops_it | no | none designed | - | - | keep (not measured) | statsmodels compat |
| 22 | tests/test_release_recovery_gates.py | TestGrangercausalitytestsCompatibility::test_compat_passes_verbose_when_supported | no | none designed | - | - | keep (not measured) | statsmodels compat |
| 23 | tests/test_release_recovery_gates.py | TestGrangercausalitytestsCompatibility::test_granger_ssr_ftest_works_when_statsmodels_drops_verbose | no | none designed | - | - | keep (not measured) | statsmodels compat |
| 24 | tests/test_release_recovery_gates.py | TestGrangercausalitytestsCompatibility::test_compat_takes_the_no_verbose_branch_on_real_statsmodels | no | none designed | - | - | keep (not measured) | statsmodels compat |
| 25 | tests/test_release_recovery_gates.py | TestApiMdDeterminism::test_generator_passes_on_current_interpreter | no | none designed | - | - | keep (not measured) | api page |
| 26 | tests/test_release_recovery_gates.py | TestApiMdDeterminism::test_generator_passes_on_python_floor_when_available | no | none designed | - | - | keep (not measured) | api page |
| 27 | tests/test_release_recovery_gates.py | TestApiMdDeterminism::test_optional_annotation_renders_as_pep604_union | no | none designed | - | - | keep (not measured) | api page |
| 28 | tests/test_release_recovery_gates.py | TestApiMdDeterminism::test_pandas_types_use_public_names | no | none designed | - | - | keep (not measured) | api page |
| 29 | tests/test_release_recovery_gates.py | TestReleaseGateCoverage::test_release_gate_checks_api_md_generator | no | none designed | - | - | keep (not measured) | release gate coverage |
| 30 | tests/test_release_recovery_gates.py | TestReleaseGateCoverage::test_ci_matrix_installs_docs_dependencies | no | none designed | - | - | keep (not measured) | release gate coverage |
| 31 | tests/test_release_recovery_gates.py | TestReleaseGateCoverage::test_the_documented_install_and_the_release_gate_require_the_ci_extras | no | none designed | - | - | keep (not measured) | release gate coverage |
| 32 | tests/test_release_recovery_gates.py | TestReleaseGateOrder::test_the_state_file_is_checked_before_anything_else | no | none designed | - | - | keep (not measured) | release order |
| 33 | tests/test_release_recovery_gates.py | TestReleaseGateOrder::test_the_suite_runs_after_the_smoke_script_and_the_tutorials | no | none designed | - | - | keep (not measured) | release order |
| 34 | tests/test_release_recovery_gates.py | TestReleaseGateOrder::test_step_7_runs_the_installed_smoke_script_as_ci_does | no | none designed | - | - | keep (not measured) | release order |
| 35 | tests/test_release_recovery_gates.py | TestReleaseGateOrder::test_a_stale_state_file_is_refused | no | none designed | - | - | keep (not measured) | release order |
| 36 | tests/test_release_recovery_gates.py | TestCiRunSelection::test_a_concluded_green_run_suffices_beside_one_still_executing | no | none designed | - | - | keep (not measured) | ci run selection |
| 37 | tests/test_release_recovery_gates.py | TestCiRunSelection::test_a_newer_concluded_failure_beside_an_older_green_run_still_fails | no | none designed | - | - | keep (not measured) | ci run selection |
| 38 | tests/test_release_recovery_gates.py | TestCiRunSelection::test_a_commit_with_no_concluded_run_is_held_by_its_newest | no | none designed | - | - | keep (not measured) | ci run selection |
| 39 | tests/test_release_recovery_gates.py | TestTheInstalledSmokeScriptRunsInTheSuite::test_the_script_runs_its_checks_up_to_the_location_check | no | none designed | - | - | keep (not measured) | installed smoke |
| 40 | tests/test_release_recovery_gates.py | TestTheInstalledSmokeScriptRunsInTheSuite::test_a_stale_line_fails_before_the_location_check | no | none designed | - | - | keep (not measured) | installed smoke |
| 41 | tests/test_release_recovery_gates.py | TestTheBannerNamesEachSkip::test_a_run_with_no_skip_keeps_the_verified_banner | no | none designed | - | - | keep (not measured) | suite banner |
| 42 | tests/test_release_recovery_gates.py | TestTheBannerNamesEachSkip::test_a_run_with_skips_counts_them_and_names_each | no | none designed | - | - | keep (not measured) | suite banner |
| 43 | tests/test_release_recovery_gates.py | TestTheBannerNamesEachSkip::test_an_unreachable_index_skip_is_recorded_once | no | none designed | - | - | keep (not measured) | suite banner |
| 44 | tests/test_jrsa.py | test_the_documented_quickstart_line_runs | no | none designed | - | - | keep (not measured) | jrsa output |
| 45 | tests/test_jrsa.py | test_p_and_q_have_the_same_shape_as_value | no | none designed | - | - | keep (not measured) | jrsa output |
| 46 | tests/test_jrsa.py | test_float_of_p_does_not_raise | no | none designed | - | - | keep (not measured) | jrsa output |
| 47 | tests/test_jrsa.py | test_the_parametric_path_already_agreed | no | none designed | - | - | keep (not measured) | jrsa output |
| 48 | tests/test_jrsa.py | test_multiple_lags_still_give_a_vector_p | no | none designed | - | - | keep (not measured) | jrsa output |
| 49 | tests/test_jrsa.py | test_a_scalar_field_is_a_plain_0d_array | no | none designed | - | - | keep (not measured) | jrsa output |
| 50 | tests/test_jrsa.py | test_indexing_a_scalar_field_raises | no | none designed | - | - | keep (not measured) | jrsa output |
| 51 | tests/test_jrsa.py | test_a_multi_lag_p_is_a_plain_vector | no | none designed | - | - | keep (not measured) | jrsa output |
| 52 | tests/test_jrsa.py | test_a_nonfinite_input_still_reports_a_scalar_nan | no | none designed | - | - | keep (not measured) | jrsa output |
| 53 | tests/test_jrsa.py | test_the_docstring_parser_finds_a_plausible_list | no | none designed | - | - | keep (not measured) | jrsa docs |
| 54 | tests/test_jrsa.py | test_every_documented_correction_is_actually_accepted | no | none designed | - | - | keep (not measured) | jrsa docs |
| 55 | tests/test_jrsa.py | test_every_implemented_correction_is_documented | no | none designed | - | - | keep (not measured) | jrsa docs |
| 56 | tests/test_jrsa.py | test_the_two_sets_are_equal | no | none designed | - | - | keep (not measured) | jrsa docs |
| 57 | tests/test_jrsa.py | test_the_withdrawn_methods_raise_rather_than_falling_back | no | none designed | - | - | keep (not measured) | jrsa withdrawn |
| 58 | tests/test_jrsa.py | test_align_mode_is_gone_and_passing_it_raises | no | none designed | - | - | keep (not measured) | jrsa withdrawn |
| 59 | tests/test_jrsa.py | test_a_nan_p_value_leaves_the_family_and_gets_a_nan_q | no | none designed | - | - | keep (not measured) | jrsa output |
| 60 | tests/test_jrsa.py | test_a_lag_with_an_all_zero_overlap_does_not_make_the_other_qs_nan | no | none designed | - | - | keep (not measured) | jrsa output |
| 61 | tests/test_api_md_is_interpreter_independent.py | TestPrivateSubmoduleCollapse::test_private_stdlib_submodule_collapses_when_parent_reexports | no | none designed | - | - | keep (not measured) | api page |
| 62 | tests/test_api_md_is_interpreter_independent.py | TestPrivateSubmoduleCollapse::test_public_submodule_is_left_alone | no | none designed | - | - | keep (not measured) | api page |
| 63 | tests/test_api_md_is_interpreter_independent.py | TestPrivateSubmoduleCollapse::test_a_name_the_parent_does_not_reexport_is_kept | no | none designed | - | - | keep (not measured) | api page |
| 64 | tests/test_api_md_is_interpreter_independent.py | TestPrivateSubmoduleCollapse::test_third_party_module_paths_are_untouched | no | none designed | - | - | keep (not measured) | api page |
| 65 | tests/test_api_md_is_interpreter_independent.py | TestPrivateSubmoduleCollapse::test_pathlib_path_renders_without_a_private_submodule | no | none designed | - | - | keep (not measured) | api page |
| 66 | tests/test_api_md_is_interpreter_independent.py | TestAcrossTheMatrix::test_generated_bytes_are_identical_across_available_interpreters | no | none designed | - | - | keep (not measured) | api page |
| 67 | tests/test_api_md_is_interpreter_independent.py | TestAcrossTheMatrix::test_committed_page_has_lf_endings_in_bytes | no | none designed | - | - | keep (not measured) | api page |
| 68 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_publish_pypi_runs_only_on_a_v_tag_push | no | none designed | - | - | keep (not measured) | publish trigger |
| 69 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_no_published_release_triggers_the_workflow | no | none designed | - | - | keep (not measured) | publish trigger |
| 70 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_prerelease_cannot_reach_production_pypi | no | none designed | - | - | keep (not measured) | publish trigger |
| 71 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_the_final_release_rule_agrees_with_pep_440 | no | none designed | - | - | keep (not measured) | publish trigger |
| 72 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_the_kind_step_run_in_bash_says_final_only_for_a_final_tag | no | none designed | - | - | keep (not measured) | publish trigger |
| 73 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_legacy_dual_trigger_if_is_rejected | no | none designed | - | - | keep (not measured) | publish trigger |
| 74 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_testpypi_needs_build_and_pypi_needs_the_verification | no | none designed | - | - | keep (not measured) | publish trigger |
| 75 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_every_test_leg_and_the_build_are_unconditional_and_required | no | none designed | - | - | keep (not measured) | publish trigger |
| 76 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_any_condition_makes_a_job_optional_and_none_keeps_it_required | no | none designed | - | - | keep (not measured) | publish trigger |
| 77 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_tag_push_still_triggers_validation_pipeline | no | none designed | - | - | keep (not measured) | publish trigger |
| 78 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_every_tag_push_publishes_to_testpypi | no | none designed | - | - | keep (not measured) | publish trigger |
| 79 | tests/test_workflow_release_policy.py | TestWorkflowReleasePolicy::test_the_release_event_does_not_upload_to_testpypi_again | no | none designed | - | - | keep (not measured) | publish trigger |
| 80 | tests/test_workflow_release_policy.py | TestATagPushReusesTheDevRunOfItsCommit::test_only_a_tag_push_looks_for_a_passed_dev_run | no | none designed | - | - | keep (not measured) | dev run reuse |
| 81 | tests/test_workflow_release_policy.py | TestATagPushReusesTheDevRunOfItsCommit::test_the_run_it_accepts_is_a_successful_dev_push_of_this_commit | no | none designed | - | - | keep (not measured) | dev run reuse |
| 82 | tests/test_workflow_release_policy.py | TestATagPushReusesTheDevRunOfItsCommit::test_a_failed_lookup_runs_the_tests | no | none designed | - | - | keep (not measured) | dev run reuse |
| 83 | tests/test_workflow_release_policy.py | TestATagPushReusesTheDevRunOfItsCommit::test_each_leg_skips_its_steps_exactly_when_a_run_matched | no | none designed | - | - | keep (not measured) | dev run reuse |
| 84 | tests/test_workflow_release_policy.py | TestATagPushReusesTheDevRunOfItsCommit::test_the_build_runs_in_full_on_every_push | no | none designed | - | - | keep (not measured) | dev run reuse |
| 85 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_nothing_before_the_upload_can_be_skipped_or_forgiven | no | none designed | - | - | keep (not measured) | upload order |
| 86 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_no_two_jobs_share_a_name | no | none designed | - | - | keep (not measured) | upload order |
| 87 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_pypi_receives_the_files_testpypi_received | no | none designed | - | - | keep (not measured) | upload order |
| 88 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_pypi_publishes_through_the_pypi_environment_with_trusted_publishing | no | none designed | - | - | keep (not measured) | upload order |
| 89 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_the_verify_job_runs_after_the_upload_and_only_after_it | no | none designed | - | - | keep (not measured) | upload order |
| 90 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_the_verify_job_installs_the_tags_version_from_testpypi | no | none designed | - | - | keep (not measured) | upload order |
| 91 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_the_verify_job_retries_the_install_a_bounded_number_of_times | no | none designed | - | - | keep (not measured) | upload order |
| 92 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_the_pypi_upload_needs_the_verify_job | no | none designed | - | - | keep (not measured) | upload order |
| 93 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_the_verify_job_checks_the_installed_environment | no | none designed | - | - | keep (not measured) | upload order |
| 94 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_the_build_job_and_the_verify_job_run_the_same_smoke_script | no | none designed | - | - | keep (not measured) | upload order |
| 95 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_no_job_the_pypi_upload_needs_can_be_forgiven | no | none designed | - | - | keep (not measured) | upload order |
| 96 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_the_status_function_check_sees_each_form | no | none designed | - | - | keep (not measured) | upload order |
| 97 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_the_smoke_steps_clear_pythonpath_before_they_run | no | none designed | - | - | keep (not measured) | upload order |
| 98 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_a_yanked_testpypi_file_is_refused_before_upload | no | none designed | - | - | keep (not measured) | upload order |
| 99 | tests/test_workflow_release_policy.py | TestTestPyPIBeforePyPI::test_the_verify_job_refuses_anything_but_one_wheel | no | none designed | - | - | keep (not measured) | upload order |
| 100 | tests/test_workflow_release_policy.py | TestTheInstalledSmokeScript::test_a_wrong_version_fails | no | none designed | - | - | keep (not measured) | installed smoke |
| 101 | tests/test_workflow_release_policy.py | TestTheInstalledSmokeScript::test_a_package_imported_from_the_checkout_fails | no | none designed | - | - | keep (not measured) | installed smoke |
| 102 | tests/test_workflow_release_policy.py | TestTheInstalledSmokeScript::test_an_importable_omission_fails | no | none designed | - | - | keep (not measured) | installed smoke |
| 103 | tests/test_workflow_release_policy.py | TestTheInstalledSmokeScript::test_an_absent_omission_passes_that_check | no | none designed | - | - | keep (not measured) | installed smoke |
| 104 | tests/test_workflow_release_policy.py | TestTheInstalledSmokeScript::test_the_pass_branch_names_every_export | no | none designed | - | - | keep (not measured) | installed smoke |
| 105 | tests/test_workflow_release_policy.py | TestTheInstalledSmokeScript::test_a_missing_export_fails_the_sweep | no | none designed | - | - | keep (not measured) | installed smoke |
| 106 | tests/test_workflow_release_policy.py | TestTheInstalledSmokeScript::test_a_resolving_optional_submodule_fails_the_sweep | no | none designed | - | - | keep (not measured) | installed smoke |
| 107 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_distribution_job_runs_tutorials_against_installed_wheel | no | none designed | - | - | keep (not measured) | installed artifact |
| 108 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_tutorial_step_cannot_import_from_the_checkout | no | none designed | - | - | keep (not measured) | installed artifact |
| 109 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_tutorial_step_runs_after_the_wheel_is_installed | no | none designed | - | - | keep (not measured) | installed artifact |
| 110 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_release_gate_also_runs_tutorials_against_the_installed_wheel | no | none designed | - | - | keep (not measured) | installed artifact |
| 111 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_release_gate_smoke_step_clears_pythonpath_too | no | none designed | - | - | keep (not measured) | installed artifact |
| 112 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_release_gate_installs_the_extras_the_ci_tutorial_step_has | no | none designed | - | - | keep (not measured) | installed artifact |
| 113 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_step8_check_fails_when_jnwb_resolves_outside_purelib | no | none designed | - | - | keep (not measured) | installed artifact |
| 114 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_step8_refuses_an_empty_purelib_or_an_unknown_resolution | no | none designed | - | - | keep (not measured) | installed artifact |
| 115 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_step8_probe_failure_exits_with_the_probes_stderr | no | none designed | - | - | keep (not measured) | installed artifact |
| 116 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_release_gate_does_not_hardcode_the_expected_version | no | none designed | - | - | keep (not measured) | installed artifact |
| 117 | tests/test_workflow_release_policy.py | TestInstalledArtifactVerification::test_the_version_pin_guard_would_catch_a_real_pin | no | none designed | - | - | keep (not measured) | installed artifact |
| 118 | tests/test_workflow_release_policy.py | TestShippedReleaseMetadataMatchesTheRelease::test_release_date_matches_the_changelog_entry_for_this_version | no | none designed | - | - | keep (not measured) | release metadata |
| 119 | tests/test_workflow_release_policy.py | TestShippedReleaseMetadataMatchesTheRelease::test_status_agrees_with_the_packaging_classifier | no | none designed | - | - | keep (not measured) | release metadata |
| 120 | tests/test_workflow_release_policy.py | TestShippedReleaseMetadataMatchesTheRelease::test_a_prerelease_marker_does_not_survive_into_a_final_version | no | none designed | - | - | keep (not measured) | release metadata |
| 121 | tests/test_workflow_release_policy.py | TestPublishCapablePipelineHygiene::test_a_least_privilege_floor_is_declared_at_the_workflow_level | no | none designed | - | - | keep (not measured) | workflow hygiene |
| 122 | tests/test_workflow_release_policy.py | TestPublishCapablePipelineHygiene::test_only_the_publish_jobs_raise_that_floor | no | none designed | - | - | keep (not measured) | workflow hygiene |
| 123 | tests/test_workflow_release_policy.py | TestPublishCapablePipelineHygiene::test_one_run_per_ref | no | none designed | - | - | keep (not measured) | workflow hygiene |
| 124 | tests/test_workflow_release_policy.py | TestPublishCapablePipelineHygiene::test_a_run_that_can_publish_is_never_cancelled_mid_upload | no | none designed | - | - | keep (not measured) | workflow hygiene |
| 125 | tests/test_workflow_release_policy.py | TestPublishCapablePipelineHygiene::test_a_manual_dispatch_publishes_nothing_by_default | no | none designed | - | - | keep (not measured) | workflow hygiene |
| 126 | tests/test_workflow_release_policy.py | TestPublishCapablePipelineHygiene::test_the_default_really_does_reach_no_publish_job | no | none designed | - | - | keep (not measured) | workflow hygiene |
| 127 | tests/test_workflow_release_policy.py | TestPublishCapablePipelineHygiene::test_every_third_party_action_is_pinned_to_a_commit | no | none designed | - | - | keep (not measured) | workflow hygiene |
| 128 | tests/test_workflow_release_policy.py | TestPublishCapablePipelineHygiene::test_each_pin_records_which_version_it_is | no | none designed | - | - | keep (not measured) | workflow hygiene |
| 129 | tests/test_workflow_release_policy.py | TestTheTagPushCreatesTheRelease::test_the_release_follows_the_pypi_upload_in_the_tag_push_run | no | none designed | - | - | keep (not measured) | tag release |
| 130 | tests/test_workflow_release_policy.py | TestTheTagPushCreatesTheRelease::test_the_notes_are_checked_before_the_release_is_created | no | none designed | - | - | keep (not measured) | tag release |
| 131 | tests/test_workflow_release_policy.py | TestTheTagPushCreatesTheRelease::test_no_job_that_can_write_leaves_its_token_in_the_checkout | no | none designed | - | - | keep (not measured) | tag release |
| 132 | tests/test_workflow_release_policy.py | TestTheTagPushCreatesTheRelease::test_the_notes_are_checked_before_anything_reaches_pypi | no | none designed | - | - | keep (not measured) | tag release |
| 133 | tests/test_workflow_release_policy.py | TestTheTagPushCreatesTheRelease::test_the_contributing_steps_describe_this_order | no | none designed | - | - | keep (not measured) | tag release |
| 134 | tests/test_workflow_release_policy.py | TestTheTagPushCreatesTheRelease::test_the_body_script_exists_and_reuses_the_release_gates_check | no | none designed | - | - | keep (not measured) | tag release |
| 135 | tests/test_workflow_release_policy.py | TestPython315IsBlockingOnUbuntu::test_python_315_is_in_the_test_matrix | no | none designed | - | - | keep (not measured) | python matrix |
| 136 | tests/test_workflow_release_policy.py | TestPython315IsBlockingOnUbuntu::test_the_only_excluded_leg_is_windows_315 | no | none designed | - | - | keep (not measured) | python matrix |
| 137 | tests/test_workflow_release_policy.py | TestPython315IsBlockingOnUbuntu::test_no_separate_test_py315_job_remains | no | none designed | - | - | keep (not measured) | python matrix |
| 138 | tests/test_workflow_release_policy.py | TestPython315IsBlockingOnUbuntu::test_the_hdf5_headers_are_installed_on_the_315_leg_before_pip_builds_h5py | no | none designed | - | - | keep (not measured) | python matrix |
| 139 | tests/test_workflow_release_policy.py | TestPython315IsBlockingOnUbuntu::test_the_install_step_names_the_hdf5_pkgconfig_library | no | none designed | - | - | keep (not measured) | python matrix |
| 140 | tests/test_workflow_release_policy.py | TestPython315IsBlockingOnUbuntu::test_setup_python_allows_prereleases_only_on_the_315_leg | no | none designed | - | - | keep (not measured) | python matrix |
| 141 | tests/test_workflow_release_policy.py | TestPandas3LegIsNonBlocking::test_the_leg_runs_python_313_on_ubuntu | no | none designed | - | - | keep (not measured) | python matrix |
| 142 | tests/test_workflow_release_policy.py | TestPandas3LegIsNonBlocking::test_the_leg_is_continue_on_error | no | none designed | - | - | keep (not measured) | python matrix |
| 143 | tests/test_workflow_release_policy.py | TestPandas3LegIsNonBlocking::test_the_leg_installs_pandas_3_after_jnwb | no | none designed | - | - | keep (not measured) | python matrix |
| 144 | tests/test_workflow_release_policy.py | TestPandas3LegIsNonBlocking::test_the_leg_prints_and_asserts_the_pandas_major_version | no | none designed | - | - | keep (not measured) | python matrix |
| 145 | tests/test_workflow_release_policy.py | TestPandas3LegIsNonBlocking::test_the_suite_runs_after_the_version_assertion | no | none designed | - | - | keep (not measured) | python matrix |
| 146 | tests/test_workflow_release_policy.py | TestPandas3LegIsNonBlocking::test_no_job_needs_the_leg_and_no_publish_or_release_job_is_gated_by_it | no | none designed | - | - | keep (not measured) | python matrix |
| 147 | tests/test_workflow_release_policy.py | TestContinueOnErrorJobsAreNotRequired::test_a_continue_on_error_job_is_not_listed | no | none designed | - | - | keep (not measured) | required jobs |
| 148 | tests/test_workflow_release_policy.py | TestContinueOnErrorJobsAreNotRequired::test_the_same_job_without_the_flag_is_listed | no | none designed | - | - | keep (not measured) | required jobs |
| 149 | tests/test_workflow_release_policy.py | TestContinueOnErrorJobsAreNotRequired::test_the_live_pandas_leg_is_not_required_and_no_other_job_moved | no | none designed | - | - | keep (not measured) | required jobs |
| 150 | tests/test_workflow_release_policy.py | TestActionsArePinnedToFullShas::test_every_uses_line_in_every_workflow_is_allow_listed_and_pinned | no | none designed | - | - | keep (not measured) | action pins |
| 151 | tests/test_workflow_release_policy.py | TestActionsArePinnedToFullShas::test_an_unpinned_or_unlisted_action_is_refused | no | none designed | - | - | keep (not measured) | action pins |
| 152 | tests/test_workflow_release_policy.py | TestTheHarnessGateReadsABuiltState::test_every_run_of_the_harness_gate_follows_a_state_build_in_its_job | no | none designed | - | - | keep (not measured) | harness state order |
| 153 | tests/test_workflow_release_policy.py | TestTheHarnessGateReadsABuiltState::test_a_gate_with_no_build_before_it_in_its_job_is_refused | no | none designed | - | - | keep (not measured) | harness state order |
| 154 | tests/test_state_reconstruction.py | test_package_facts_survive_an_absent_optional_extra | no | none designed | - | - | keep (not measured) | state generator |
| 155 | tests/test_state_reconstruction.py | test_the_state_file_is_not_committed | no | none designed | - | - | keep (not measured) | state generator |
| 156 | tests/test_state_reconstruction.py | test_generation_is_deterministic_apart_from_its_timestamp | no | none designed | - | - | keep (not measured) | state generator |
| 157 | tests/test_state_reconstruction.py | test_a_harness_that_times_out_is_unresolved_not_failed | no | none designed | - | - | keep (not measured) | state generator |
| 158 | tests/test_state_reconstruction.py | test_a_harness_that_crashes_is_failed_not_unresolved | no | none designed | - | - | keep (not measured) | state generator |
| 159 | tests/test_state_reconstruction.py | test_an_unresolved_row_says_why | no | none designed | - | - | keep (not measured) | state generator |
| 160 | tests/test_state_reconstruction.py | test_it_reports_the_slots_a_packet_needs | no | none designed | - | - | keep (not measured) | state generator |
| 161 | tests/test_state_reconstruction.py | test_the_measured_values_match_the_tree | no | none designed | - | - | keep (not measured) | state generator |
| 162 | tests/test_state_reconstruction.py | test_a_moved_head_reads_as_stale | no | none designed | - | - | keep (not measured) | state generator |
| 163 | tests/test_state_reconstruction.py | test_check_exits_nonzero_when_the_file_is_absent | no | none designed | - | - | keep (not measured) | state generator |
| 164 | tests/test_state_reconstruction.py | test_the_cli_check_runs_without_probing | no | none designed | - | - | keep (not measured) | state generator |
| 165 | tests/test_state_reconstruction.py | test_it_reports_worktrees_branches_the_dev_run_and_open_defect_classes | no | none designed | - | - | keep (not measured) | state generator |
| 166 | tests/test_state_reconstruction.py | test_a_failed_dev_run_reads_red_with_its_head_sha | no | none designed | - | - | keep (not measured) | state generator |
| 167 | tests/test_state_reconstruction.py | test_a_passing_dev_run_reads_its_sha_and_conclusion | no | none designed | - | - | keep (not measured) | state generator |
| 168 | tests/test_state_reconstruction.py | test_a_timed_out_dev_run_still_reads_red | no | none designed | - | - | keep (not measured) | state generator |
| 169 | tests/test_state_reconstruction.py | test_an_unreachable_runs_api_reads_unknown_never_a_pass | no | none designed | - | - | keep (not measured) | state generator |
| 170 | tests/test_state_reconstruction.py | test_a_body_without_a_concluded_run_reads_unknown | no | none designed | - | - | keep (not measured) | state generator |
| 171 | tests/test_state_reconstruction.py | test_a_prunable_worktree_and_a_merged_branch_are_named | no | none designed | - | - | keep (not measured) | state generator |
| 172 | tests/test_state_reconstruction.py | test_open_defect_classes_are_the_rows_with_no_landed_check | no | none designed | - | - | keep (not measured) | state generator |
| 173 | tests/test_state_reconstruction.py | test_growth_rows_count_the_scripts_and_each_process_test | no | none designed | - | - | keep (not measured) | state generator |
| 174 | tests/test_state_basis_is_checked.py | test_a_basis_recorded_at_the_live_head_passes | no | none designed | - | - | keep (not measured) | state basis |
| 175 | tests/test_state_basis_is_checked.py | test_a_moved_head_fails | no | none designed | - | - | keep (not measured) | state basis |
| 176 | tests/test_state_basis_is_checked.py | test_an_absent_file_fails | no | none designed | - | - | keep (not measured) | state basis |
| 177 | tests/test_state_basis_is_checked.py | test_a_file_with_no_head_row_fails | no | none designed | - | - | keep (not measured) | state basis |
| 178 | tests/test_state_basis_is_checked.py | test_the_old_predicate_cannot_tell_the_two_outcomes_apart | no | none designed | - | - | keep (not measured) | state basis |
| 179 | tests/test_state_basis_is_checked.py | test_a_state_file_in_this_tree_is_current | no | none designed | - | - | keep (not measured) | state basis |
| 180 | tests/test_state_basis_is_checked.py | test_the_gate_scan_separates_a_gate_that_names_the_file_from_one_that_does_not | no | none designed | - | - | keep (not measured) | state basis |
| 181 | tests/test_state_basis_is_checked.py | test_the_generated_prose_agrees_with_whether_a_gate_reads_the_file | no | none designed | - | - | keep (not measured) | state basis |
| 182 | tests/test_xflip_calibration_receipt.py | test_receipt_and_generator_exist | no | none designed | - | - | keep (not measured) | calibration receipt |
| 183 | tests/test_xflip_calibration_receipt.py | test_the_receipt_without_a_generator_is_gone | no | none designed | - | - | keep (not measured) | calibration receipt |
| 184 | tests/test_xflip_calibration_receipt.py | test_receipt_was_generated_from_the_current_estimator | no | none designed | - | - | keep (not measured) | calibration receipt |
| 185 | tests/test_xflip_calibration_receipt.py | test_the_receipt_covers_every_helper_xflip_reaches | no | none designed | - | - | keep (not measured) | calibration receipt |
| 186 | tests/test_xflip_calibration_receipt.py | test_an_edit_inside_a_multi_line_string_literal_changes_the_receipt | no | none designed | - | - | keep (not measured) | calibration receipt |
| 187 | tests/test_xflip_calibration_receipt.py | test_a_docstring_or_comment_edit_leaves_the_receipt_current | no | none designed | - | - | keep (not measured) | calibration receipt |
| 188 | tests/test_xflip_calibration_receipt.py | test_a_code_edit_changes_the_receipt | no | none designed | - | - | keep (not measured) | calibration receipt |
| 189 | tests/test_xflip_calibration_receipt.py | test_the_operating_point_is_the_shipped_default_where_it_claims_to_be | no | none designed | - | - | keep (not measured) | calibration receipt |
| 190 | tests/test_xflip_calibration_receipt.py | test_report_is_rendered_from_the_raw_receipt | no | none designed | - | - | keep (not measured) | calibration receipt |
| 191 | tests/test_xflip_calibration_receipt.py | test_the_surrogate_test_itself_rejects_a_smooth_gradient | no | none designed | - | - | keep (not measured) | calibration receipt |
| 192 | tests/test_vflip_calibration_receipt.py | test_the_raw_record_is_strict_json_and_states_what_null_means | no | none designed | - | - | keep (not measured) | calibration receipt |
| 193 | tests/test_vflip_calibration_receipt.py | test_receipt_and_generator_exist | no | none designed | - | - | keep (not measured) | calibration receipt |
| 194 | tests/test_vflip_calibration_receipt.py | test_the_generator_writes_minus_infinity_as_null_and_refuses_nan | no | none designed | - | - | keep (not measured) | calibration receipt |
| 195 | tests/test_vflip_calibration_receipt.py | test_receipt_was_generated_from_the_current_estimator | no | none designed | - | - | keep (not measured) | calibration receipt |
| 196 | tests/test_vflip_calibration_receipt.py | test_the_receipt_covers_everything_the_estimator_reaches | no | none designed | - | - | keep (not measured) | calibration receipt |
| 197 | tests/test_vflip_calibration_receipt.py | test_a_docstring_or_comment_edit_leaves_the_receipt_current | no | none designed | - | - | keep (not measured) | calibration receipt |
| 198 | tests/test_vflip_calibration_receipt.py | test_a_code_edit_changes_the_receipt | no | none designed | - | - | keep (not measured) | calibration receipt |
| 199 | tests/test_vflip_calibration_receipt.py | test_receipt_threshold_is_the_shipped_default | no | none designed | - | - | keep (not measured) | calibration receipt |
| 200 | tests/test_vflip_calibration_receipt.py | test_report_is_rendered_from_the_raw_receipt | no | none designed | - | - | keep (not measured) | calibration receipt |
| 201 | tests/test_test_imports_survive_the_wheel_leg.py | test_the_shipped_set_is_actually_derived | no | none designed | - | - | keep (not measured) | installed copy |
| 202 | tests/test_test_imports_survive_the_wheel_leg.py | test_scripts_is_not_shipped_so_this_invariant_is_live | no | none designed | - | - | keep (not measured) | installed copy |
| 203 | tests/test_test_imports_survive_the_wheel_leg.py | test_the_import_walk_finds_the_imports_it_is_meant_to_police | no | none designed | - | - | keep (not measured) | installed copy |
| 204 | tests/test_test_imports_survive_the_wheel_leg.py | test_the_sys_path_walk_finds_the_calls_it_is_meant_to_credit | no | none designed | - | - | keep (not measured) | installed copy |
| 205 | tests/test_test_imports_survive_the_wheel_leg.py | test_the_qualification_leg_still_clears_pythonpath | no | none designed | - | - | keep (not measured) | installed copy |
| 206 | tests/test_test_imports_survive_the_wheel_leg.py | test_no_test_module_imports_an_unshipped_path_without_reaching_for_it | no | none designed | - | - | keep (not measured) | installed copy |
| 207 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_no_test_module_puts_the_checkout_ahead_of_the_package_under_test | no | none designed | - | - | keep (not measured) | installed copy |
| 208 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_no_script_prepends_the_checkout_unconditionally | no | none designed | - | - | keep (not measured) | installed copy |
| 209 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_no_test_reads_a_repository_file_through_the_current_directory | no | none designed | - | - | keep (not measured) | installed copy |
| 210 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_every_example_guard_stands_aside_for_a_deliberate_installed_run | no | none designed | - | - | keep (not measured) | installed copy |
| 211 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_the_guard_actually_stands_aside_when_the_variable_is_set | no | none designed | - | - | keep (not measured) | installed copy |
| 212 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_every_script_a_test_imports_accepts_the_installed_copy | no | none designed | - | - | keep (not measured) | installed copy |
| 213 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_a_script_that_defers_to_the_variable_also_checks_the_copy_it_names | no | none designed | - | - | keep (not measured) | installed copy |
| 214 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_every_checkout_prepend_stands_aside_for_the_variable | no | none designed | - | - | keep (not measured) | installed copy |
| 215 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_ci_runs_the_suite_against_the_installed_wheel | no | none designed | - | - | keep (not measured) | installed copy |
| 216 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_that_leg_runs_after_the_wheel_is_installed | no | none designed | - | - | keep (not measured) | installed copy |
| 217 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_the_leg_does_not_reinstall_jnwb_from_source | no | none designed | - | - | keep (not measured) | installed copy |
| 218 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_the_test_tooling_is_read_from_pyproject_rather_than_listed_again | no | none designed | - | - | keep (not measured) | installed copy |
| 219 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_the_tutorial_step_tells_the_guard_to_stand_aside | no | none designed | - | - | keep (not measured) | installed copy |
| 220 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_the_matrix_legs_still_test_the_checkout | no | none designed | - | - | keep (not measured) | installed copy |
| 221 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_this_file_would_have_caught_the_defects_it_documents | no | none designed | - | - | keep (not measured) | installed copy |
| 222 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_no_test_module_rebinds_the_front_of_sys_path | no | none designed | - | - | keep (not measured) | installed copy |
| 223 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_only_the_designated_harness_asserts_which_jnwb_is_under_test | no | none designed | - | - | keep (not measured) | installed copy |
| 224 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_the_designated_harness_still_exists_and_supports_both_modes | no | none designed | - | - | keep (not measured) | installed copy |
| 225 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_the_module_glob_reaches_the_package_init | no | none designed | - | - | keep (not measured) | installed copy |
| 226 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_every_archived_prepend_form_is_flagged | no | none designed | - | - | keep (not measured) | installed copy |
| 227 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_the_checkout_only_directory_prepend_is_left_alone | no | none designed | - | - | keep (not measured) | installed copy |
| 228 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_every_archived_provenance_spelling_is_flagged | no | none designed | - | - | keep (not measured) | installed copy |
| 229 | tests/test_the_suite_can_qualify_an_installed_copy.py | test_every_archived_cwd_relative_spelling_is_flagged | no | none designed | - | - | keep (not measured) | installed copy |
| 230 | tests/test_errors_documented.py | TestEveryErrorClassIsExplained::test_the_error_appears_on_a_hand_written_page | no | none designed | - | - | keep (not measured) | docs pages |
| 231 | tests/test_errors_documented.py | TestEveryErrorClassIsExplained::test_the_error_appears_on_the_errors_page_specifically | no | none designed | - | - | keep (not measured) | docs pages |
| 232 | tests/test_errors_documented.py | TestEveryErrorClassIsExplained::test_there_are_fifteen_of_them | no | none designed | - | - | keep (not measured) | docs pages |
| 233 | tests/test_errors_documented.py | TestEveryErrorClassIsExplained::test_both_base_classes_are_named_so_a_caller_can_catch_a_family | no | none designed | - | - | keep (not measured) | docs pages |
| 234 | tests/test_errors_documented.py | TestTheResolversAreExplained::test_the_resolver_is_on_the_errors_page | no | none designed | - | - | keep (not measured) | docs pages |
| 235 | tests/test_errors_documented.py | TestTheErrorsPageIsReachable::test_the_index_links_to_it | no | none designed | - | - | keep (not measured) | docs pages |
| 236 | tests/test_errors_documented.py | TestTheErrorsPageIsReachable::test_it_is_in_the_mkdocs_nav | no | none designed | - | - | keep (not measured) | docs pages |
| 237 | tests/test_errors_documented.py | TestTheErrorsPageIsReachable::test_every_hand_written_page_is_in_the_nav | no | none designed | - | - | keep (not measured) | docs pages |
| 238 | tests/test_errors_documented.py | TestTheErrorsPageIsReachable::test_a_commented_out_nav_line_is_not_an_entry | no | none designed | - | - | keep (not measured) | docs pages |
| 239 | tests/test_errors_documented.py | TestTheErrorsPageIsReachable::test_the_page_exists_and_is_not_a_stub | no | none designed | - | - | keep (not measured) | docs pages |
| 240 | tests/test_errors_documented.py | TestEveryExportIsWrittenAboutSomewhere::test_no_export_lives_only_in_the_generated_reference | no | none designed | - | - | keep (not measured) | docs pages |
| 241 | tests/test_errors_documented.py | TestEveryExportIsWrittenAboutSomewhere::test_the_gate_agrees | no | none designed | - | - | keep (not measured) | docs pages |
| 242 | tests/test_errors_documented.py | TestEveryExportIsWrittenAboutSomewhere::test_the_gate_would_fail_if_the_generated_reference_were_counted | no | none designed | - | - | keep (not measured) | docs pages |
| 243 | tests/test_errors_documented.py | TestTheMessagesOnThePageAreTheRealOnes::test_the_source_read_is_every_file_that_defines_a_public_name | no | none designed | - | - | keep (not measured) | docs pages |
| 244 | tests/test_errors_documented.py | TestTheMessagesOnThePageAreTheRealOnes::test_each_quoted_fragment_is_in_the_source | no | none designed | - | - | keep (not measured) | docs pages |
| 245 | tests/test_errors_documented.py | TestTheMessagesOnThePageAreTheRealOnes::test_each_quoted_fragment_is_on_the_page | no | none designed | - | - | keep (not measured) | docs pages |
| 246 | tests/test_errors_documented.py | TestTheMessagesOnThePageAreTheRealOnes::test_detection_tails_is_quoted_correctly | no | none designed | - | - | keep (not measured) | docs pages |
| 247 | tests/test_errors_documented.py | TestTheGateWouldNoticeAMissingPage::test_docs_containing_only_the_generated_reference_are_rejected | no | none designed | - | - | keep (not measured) | docs pages |
| 248 | tests/test_errors_documented.py | TestTheGateWouldNoticeAMissingPage::test_a_page_that_covers_everything_is_accepted | no | none designed | - | - | keep (not measured) | docs pages |
| 249 | tests/test_errors_documented.py | TestTheGateWouldNoticeAMissingPage::test_a_substring_of_another_symbol_is_not_credited_to_it | no | none designed | - | - | keep (not measured) | docs pages |
| 250 | tests/test_errors_documented.py | TestTheGateWouldNoticeAMissingPage::test_one_missing_symbol_is_reported_by_name | no | none designed | - | - | keep (not measured) | docs pages |
| 251 | tests/test_readme_smoke.py | test_readme_quickstart_blocks_execute | no | none designed | - | - | keep (not measured) | readme blocks |
| 252 | tests/test_readme_smoke.py | test_readme_arrays_quickstart_recovers_the_onset_it_prints | no | none designed | - | - | keep (not measured) | readme blocks |
| 253 | tests/test_readme_smoke.py | test_readme_more_examples_recover_the_effects_they_plant | no | none designed | - | - | keep (not measured) | readme blocks |
| 254 | tests/test_readme_smoke.py | test_readme_links_resolve_from_the_page_that_renders_it | no | none designed | - | - | keep (not measured) | readme blocks |
| 255 | tests/test_readme_smoke.py | test_readme_capability_table_symbols_exist | no | none designed | - | - | keep (not measured) | readme blocks |
| 256 | tests/test_readme_smoke.py | test_readme_does_not_hardcode_public_symbol_count | no | none designed | - | - | keep (not measured) | readme blocks |
| 257 | tests/test_readme_smoke.py | test_readme_python_version_matches_policy | no | none designed | - | - | keep (not measured) | readme blocks |
