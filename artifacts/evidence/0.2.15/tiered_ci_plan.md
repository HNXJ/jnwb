# Tiered-CI plan (plan only; `workflow.yml` unchanged)

Owner ruling 2026-10-31: plan only. No workflow, gate, or test file changes here.

## Triggers and legs (all line numbers read in `.github/workflows/workflow.yml`)

CI runs only on: push to `main` or `dev` (`:4`), `v*` tags (`:5`), pull requests
against `main` or `dev` (`:6-7`), and manual dispatch (`:8-20`). There is no run on
other branches, so no tier may be assigned to "every push".

- `qualified` (`:38-79`) finds the passed `main` push run at the tag's commit
  (`run_id`, `:51`, `:71-77`). On a `v*` tag push it matches, and every test step
  is skipped (`if: env.QUALIFIED_BY == ''`, `:110-112`, `:204-206`). A tag-only
  tier would therefore never run; the slowest tier runs on `push to main` instead.
- `test` (`:80-87`; matrix `:90-106`; `timeout-minutes: 60`, `:87`) runs
  `python scripts/ci_pytest.py tests/` (`:173-183`), which is
  `pytest -v -n auto` (`scripts/ci_pytest.py:32-33`).
- `test-floors` (`:195-202`; `timeout-minutes: 60`, `:201`) runs the suite at the
  declared floors (`:276-281`).
- `test-pandas3` (`:283-290`) is non-blocking (`continue-on-error: true`, `:289`)
  and keeps the whole suite regardless of tiering.
- `build` (`:325-329`; `needs: [test, test-floors]`, `:327`): pre-flight harness
  gate (`:357-359`), strict docs build (`:361-363`), sdist and wheel (`:365-367`),
  `twine check` (`:369-371`), archive-manifest inspection (`:373-394`), clean-venv
  wheel install plus smoke test (`:396-411`), the full suite against the
  installed wheel (`:413-440`), tutorials against the installed wheel
  (`:442-472`), artifact upload (`:474-479`).
- Tag-only chain after `build`: `publish-testpypi` (`:481`), `verify-testpypi`
  (`:512`), `publish-pypi` (`:586`), `verify-pypi` (`:658`), `github-release`
  (`:720`).

## Tier mapping (cumulative)

Tiers are cumulative: a pull request runs `fast`; a push to `dev` runs `fast` +
`full`; a push to `main` runs all three. No file in `fast` or `full` leaves the
`dev` run; only the `release` tier is main-only.

- `fast`: pull-request runs (a fast-only selection inside the `test` matrix,
  `:80`). Only process, form, and harness probes may enter this tier.
- `full`: joins `fast` on push to `dev` (`test`, `:80`, plus `test-floors`,
  `:195`). This is the dev tier: every file guarding a scientific invariant, an
  estimator, a null, a calibration receipt, or a released number stays here
  whatever its seconds.
- `release`: joins both on push to `main` (`test` plus `test-floors` plus
  `build`, `:325`), then the tag chain above reuses that run through
  `qualified`; plus the local `scripts/release_gate.py`. Holds files that check
  process, form, packaging, harness, or release policy and are slow or
  subprocess/policy-natured. Its absence from `dev` pushes is the priced
  tradeoff, listed file by file below.

## Rule

- `release`: summed seconds above 100, and the file checks process, form,
  packaging, harness, or release policy (8 files); or the file runs a
  subprocess suite, a gate, or a release/CI policy probe (named:
  `test_every_gate_runs`, `test_state_basis_is_checked`,
  `test_the_suite_can_qualify_an_installed_copy`,
  `test_collection_order_stability`, `test_release_recovery_gates`,
  `test_workflow_release_policy`); or `test_fact_gate`, whose live-tree facts
  the harness gate re-checks faster on `dev` (gate 22, fact predicates on the
  generated fact graph, `scripts/harness_gate.py:39`, run in `build`
  `:357-359`, which has no `if` and so runs on `dev` pushes after `test`
  passes, `:327`). `test_state_reconstruction` (generation determinism has no
  faster check on `dev`; gate 20 covers currency only) and
  `test_release_requires_an_empty_open_stack` (no gate or faster test checks
  open-stack emptiness; `grep open_stack scripts/harness_gate.py` is empty)
  moved to `full`.
- `full`: summed seconds above 5; or the file guards a scientific invariant, an
  estimator, a null, its calibration or provenance, or a released number (10
  files moved out of `release` for this reason:
  `test_coherence_pitfall_estimators`, `test_jrsa_sliding`,
  `test_xflip_homogeneous_null`, `test_vflip2_recovery`, `test_wavemap`,
  `test_parallel` (fact S6: workers change no number),
  `test_composition_randomness`, `test_curation_calibration_receipt`,
  `test_tutorial_00_foreign_shapes`, `test_tutorials`); or the named
  calibration/browser/docs-form files below 5 s (`test_vflip_calibration_receipt`,
  `test_calibration_hash_walker`, `test_figure_interactive`,
  `test_vis_export_session`, `test_dashboard_workflow`, `test_docs_smoke`).
- `fast`: everything else (89 files, each a process, form, docs, packaging,
  skill, stack, or harness probe; audited in the trades list).

Measured totals: `release` 14 files / 4249.9 s; `full` 166 files / 5260.0 s;
`fast` 89 files / 100.2 s. Per-tier sums add to 9610.1, within 0.5 of the input
table's 9610.3 (display rounding). 269 files checked: 14 + 166 + 89.

## Wall bounds

Each tier's wall time is at least max(summed seconds / workers, the tier's
slowest single test from the input table). CI uses `-n auto`
(`scripts/ci_pytest.py:32-33`); the repository states no runner core count (only
`runs-on` labels), so 4 workers is assumed for GitHub-hosted runners, beside the
12-worker reference run. Both are lower bounds.

| Tier | Sum / slowest | 4 workers (assumed) | 12 workers |
|---|---:|---:|---:|
| release | 4249.9 / 212.3 | max(1062.5, 212.3) = 1062 s | max(354.2, 212.3) = 354 s |
| full | 5260.0 / 231.3 | max(1315.0, 231.3) = 1315 s | max(438.3, 231.3) = 438 s |
| fast | 100.2 / 3.6 | max(25.1, 3.6) = 25 s | max(8.4, 3.6) = 8.4 s |
| dev run (fast + full) | 5360.2 / 231.3 | max(1340.1, 231.3) = 1340 s | max(446.7, 231.3) = 447 s |

## Moving tiers

A file moves tiers by declaring `@pytest.mark.tier("fast" | "full" | "release")`.
Unmarked files default to this plan's rule. Every test file on disk has exactly
one tier; a new file takes the tier the rule gives it. A move needs a reason
tied to the rule (new subprocess/gate, new calibration receipt, measured
seconds crossing a bound on the reference run, or a guard reclassification) and
must keep the per-tier sums recomputable from the profile table.

## What the owner trades

Only the `release` tier leaves the `dev` push run (14 files, 4249.9 s),
one phrase each on what they check. `test_figure_form` rendered-figure ink
legibility; `test_fact_gate` fact-graph gate (same facts re-checked faster on
`dev` by harness-gate gate 22); `test_build_dashboard` dashboard data-contract
rendering; `test_semantic_mutation_classes` mutation-class demonstrations;
`test_mutation_harness_validity` mutation-harness guards; `test_bump_version`
version-surface sync; `test_docs_operation_statements` doc operation claims;
`test_import_provenance` imported-package provenance; `test_every_gate_runs` full
gate run; `test_state_basis_is_checked` state-file basis freshness claim;
`test_the_suite_can_qualify_an_installed_copy` installed-copy qualification;
`test_collection_order_stability` collection-order stability;
`test_release_recovery_gates` release-gate ordering;
`test_workflow_release_policy` CI/release policy.

`fast` (PR tier, also run on every `dev` and `main` push), 89 files, 100.2 s: `test_gpu_launch_overhead` GPU-launch
overhead; `test_rng_parameters_by_use` seeded-generator usage; `test_module_docstrings_match_their_code`
docstring-code agreement; `test_tests_draw_from_seeded_generators` seeded-fixture
audit; `test_docs_links` link targets; `test_prose_version_claims_are_live`
prose version pins; `test_readme_smoke` README smoke; `test_harness_gate`
gate-runner smoke; `test_every_declaration_has_a_caller` declaration
reachability; `test_api_consistency` API consistency; `test_agents_md_recipes`
agent-page recipes; `test_open_data_through_the_agent_surface` agent-surface
open-data path; `test_push_guard` push-guard behaviour; `test_stack_edit`
stack tooling; `test_statistics_api_split` statistics API split;
`test_skill_decline_behaviour` skill decline path;
`test_independent_audit_semantics` audit semantics;
`test_dependency_floors_are_installable` floor installability;
`test_api_surface` public API list; `test_frozen_validated` validated-body
register; `test_public_api_reachability` export reachability;
`test_a_silent_no_op_is_refused` no-op refusal;
`test_no_unreferenced_symbols` symbol coverage; `test_analyzers_coverage`
analyzer coverage; `test_generated_files_are_byte_stable` byte stability;
`test_backend` backend selection; `test_gate8_covers_every_version_surface`
version-surface coverage; `test_distribution_manifest_inspection` manifest
hygiene; `test_dict_access_shim` access-shim behaviour;
`test_release_body_script` release-body script; `test_documentation_form`
documentation form; `test_docs_interpretation_statements`
interpretation-statement wording; `test_switch_rebinding_is_reviewed`
switch-rebinding review; `test_testing_synth` synthetic fixtures;
`test_computational_contract_gate` computational-contract gate;
`test_release_body_gate` release-body gate; `test_device_denial_contract`
device-denial contract; `test_docs_user_navigation` user-navigation docs;
`test_viz` visualization smoke; `test_skill_symbol_coverage` skill symbol
coverage; `test_shipped_code_names_no_process_ids` shipped-code vocabulary;
`test_skill_degenerate_claims` degenerate skill claims;
`test_frozen_core_mutants` frozen-core mutants; `test_references_resolve`
reference resolution; `test_paths` path utilities;
`test_pointer_documents_resolve` pointer-document resolution;
`test_vis_label_range_edges` label-range edges; `test_docs_decoding_chain`
decoding-chain docs; `test_architecture_page_reachability` architecture-page
reachability; `test_stack_metadata_contradictions` stack-metadata consistency;
`test_single_agent_instruction_file` instruction-file singularity;
`test_skill_routing_behaviour` skill-routing behaviour;
`test_skills_are_findable_from_an_installed_copy` installed skill discovery;
`test_vis_shared_rules` shared vis rules; `test_rng_spelling` rng spelling;
`test_ci_conclusion_gate` CI-conclusion gate; `test_public_surface_manifest`
surface manifest; `test_vis_draws_no_default_landmark` default-landmark refusal;
`test_paths_identity` path identity; `test_obligation_diff` obligation-diff
script; `test_skill_router_reach` skill-router reachability;
`test_figure_tabs_and_state` figure tabs and state;
`test_synthetic_figures_are_labelled` synthetic-figure labels;
`test_release_version_is_unpublished` version-unpublished check;
`test_skill_default_claims_match_signatures` default-claim match;
`test_generation_closure_is_declared` generation closure;
`test_vis_heatmap_ribbon_sem` heatmap-ribbon appearance;
`test_docs_runnable_prerequisites` runnable-prerequisites docs;
`test_optional_dependencies` optional dependencies;
`test_composition_failure_propagation` failure propagation;
`test_skill_claims_match_the_router` skill/router claim match;
`test_role_files_point_to_one_contract` role-file contract;
`test_api_md_experimental_section` experimental API section;
`test_helper_rule_names` helper rule names;
`test_nonfinite_trial_starts_are_refused` nonfinite-start refusal;
`test_git_checkout_mark` checkout-mark helper; `test_addressing_silent` silent
addressing; `test_standing_rules_name_no_cycle` standing-rules acyclicity;
`test_reference_claims_ledger` reference-claims ledger; `test_findings_ledger`
findings ledger; `test_audit_reproducers` audit reproducers;
`test_deprecated_aliases` deprecated aliases;
`test_window_default_deprecation` window-default deprecation;
`test_uncovered_exports` export coverage; `test_figure_sources_outside_docs`
figure-source placement; `test_laminar_silent` silent laminar mode;
`test_psd_silent` silent PSD mode; `test_stack_item_length` stack-item length.

## File table (269 files)

| File | Tests | Seconds | Tier |
|---|---:|---:|:---|
| `tests/test_figure_form.py` | 1548 | 1843.2 | release |
| `tests/test_fact_gate.py` | 300 | 856.5 | release |
| `tests/test_release_requires_an_empty_open_stack.py` | 188 | 845.2 | full |
| `tests/test_state_reconstruction.py` | 23 | 524.7 | full |
| `tests/test_build_dashboard.py` | 67 | 334.5 | release |
| `tests/test_coherence_pitfall_estimators.py` | 25 | 248.5 | full |
| `tests/test_jrsa_sliding.py` | 26 | 238.3 | full |
| `tests/test_semantic_mutation_classes.py` | 22 | 212.5 | release |
| `tests/test_mutation_harness_validity.py` | 88 | 163.4 | release |
| `tests/test_bump_version.py` | 10 | 152.0 | release |
| `tests/test_xflip_homogeneous_null.py` | 7 | 144.9 | full |
| `tests/test_wavemap.py` | 56 | 130.7 | full |
| `tests/test_docs_operation_statements.py` | 54 | 125.6 | release |
| `tests/test_tutorial_00_foreign_shapes.py` | 28 | 123.4 | full |
| `tests/test_vflip2_recovery.py` | 12 | 122.6 | full |
| `tests/test_parallel.py` | 25 | 118.7 | full |
| `tests/test_tutorials.py` | 13 | 117.8 | full |
| `tests/test_composition_randomness.py` | 17 | 116.8 | full |
| `tests/test_curation_calibration_receipt.py` | 23 | 104.0 | full |
| `tests/test_import_provenance.py` | 21 | 102.4 | release |
| `tests/test_every_gate_runs.py` | 30 | 99.2 | release |
| `tests/test_state_basis_is_checked.py` | 8 | 96.9 | release |
| `tests/test_the_suite_can_qualify_an_installed_copy.py` | 45 | 80.2 | release |
| `tests/test_collection_order_stability.py` | 18 | 70.1 | release |
| `tests/test_release_recovery_gates.py` | 23 | 58.2 | release |
| `tests/test_workflow_release_policy.py` | 93 | 55.2 | release |
| `tests/test_fusion_agreement.py` | 17 | 92.2 | full |
| `tests/test_zflip_audit.py` | 50 | 91.7 | full |
| `tests/test_learning_gate.py` | 26 | 89.1 | full |
| `tests/test_api_md_is_interpreter_independent.py` | 7 | 85.5 | full |
| `tests/test_xflip_calibration.py` | 33 | 84.5 | full |
| `tests/test_notebooks.py` | 10 | 71.6 | full |
| `tests/test_dashboard_page.py` | 16 | 67.2 | full |
| `tests/test_figure_registry_current.py` | 37 | 66.1 | full |
| `tests/test_docs_call_shapes.py` | 59 | 64.7 | full |
| `tests/test_diagrams_render.py` | 12 | 62.6 | full |
| `tests/test_declared_return_shapes.py` | 17 | 61.1 | full |
| `tests/test_import_lazy.py` | 14 | 58.9 | full |
| `tests/test_nonfinite_inputs.py` | 281 | 54.1 | full |
| `tests/test_jrsa_correctness.py` | 323 | 51.3 | full |
| `tests/test_connectivity_pitfalls.py` | 56 | 47.9 | full |
| `tests/test_execution_switch.py` | 116 | 45.1 | full |
| `tests/test_laminar_curation.py` | 116 | 43.2 | full |
| `tests/test_optional_vis_extra.py` | 7 | 43.2 | full |
| `tests/test_vflip2_sensitivity.py` | 3 | 42.8 | full |
| `tests/test_vis_wavemap.py` | 15 | 41.8 | full |
| `tests/test_generated_figures_are_maintained.py` | 75 | 41.8 | full |
| `tests/test_nwb_write.py` | 70 | 40.9 | full |
| `tests/test_shuffle_pvalues_are_ranks.py` | 39 | 40.2 | full |
| `tests/test_axis_convention_matches_the_specification.py` | 156 | 40.2 | full |
| `tests/test_vflip2_simulation.py` | 4 | 31.9 | full |
| `tests/test_connectivity.py` | 188 | 31.2 | full |
| `tests/test_api_md_member_types.py` | 14 | 31.1 | full |
| `tests/test_nwb_inspect.py` | 70 | 27.9 | full |
| `tests/test_zflip_window.py` | 29 | 27.4 | full |
| `tests/test_release_contains_main.py` | 8 | 25.6 | full |
| `tests/test_mcp_server.py` | 27 | 23.9 | full |
| `tests/test_import_profile_receipt.py` | 16 | 21.7 | full |
| `tests/test_examples_quickstart.py` | 4 | 21.1 | full |
| `tests/test_onset_fitting.py` | 53 | 20.9 | full |
| `tests/test_acquisition_layout.py` | 38 | 20.4 | full |
| `tests/test_decoding.py` | 53 | 19.9 | full |
| `tests/test_harness_adversarial_gates.py` | 240 | 19.8 | full |
| `tests/test_lane_verifies_its_own_baseline.py` | 16 | 19.6 | full |
| `tests/test_statistics.py` | 242 | 18.7 | full |
| `tests/test_skills_validation.py` | 96 | 17.6 | full |
| `tests/test_xflip_window.py` | 26 | 17.3 | full |
| `tests/test_vflip2_nuisance.py` | 6 | 17.1 | full |
| `tests/test_open_data_example.py` | 7 | 16.3 | full |
| `tests/test_compression.py` | 159 | 15.9 | full |
| `tests/test_nwb_events.py` | 42 | 15.7 | full |
| `tests/test_jnwb_frozen_boundary.py` | 6 | 15.6 | full |
| `tests/test_vflip2.py` | 28 | 15.4 | full |
| `tests/test_vflip2_from_lfp.py` | 25 | 14.6 | full |
| `tests/test_jrsa.py` | 51 | 14.1 | full |
| `tests/test_line_endings_survive_an_edit.py` | 16 | 14.0 | full |
| `tests/test_container_type_contradiction.py` | 11 | 13.9 | full |
| `tests/test_substitution_class_sweep.py` | 41 | 13.7 | full |
| `tests/test_docs_nwb_workflow.py` | 22 | 13.5 | full |
| `tests/test_gates_reject_the_trees_they_passed.py` | 64 | 13.4 | full |
| `tests/test_release_gate_receipt_history.py` | 5 | 11.8 | full |
| `tests/test_hdmf_nwb_read_boundary.py` | 10 | 11.6 | full |
| `tests/test_computational_order_sources_agree.py` | 11 | 11.4 | full |
| `tests/test_spectral.py` | 268 | 11.4 | full |
| `tests/test_visual_qc.py` | 22 | 11.2 | full |
| `tests/test_test_imports_survive_the_wheel_leg.py` | 6 | 11.1 | full |
| `tests/test_errors_documented.py` | 82 | 11.0 | full |
| `tests/test_gate2_ignores_nested_checkouts.py` | 23 | 10.5 | full |
| `tests/test_xflip.py` | 76 | 10.5 | full |
| `tests/test_ontology.py` | 135 | 10.1 | full |
| `tests/test_zflip.py` | 50 | 10.1 | full |
| `tests/test_agents_md_stays_a_router.py` | 6 | 10.1 | full |
| `tests/test_rng_control.py` | 58 | 10.0 | full |
| `tests/test_claim_vocabulary_prose.py` | 2 | 9.9 | full |
| `tests/test_xflip_calibration_receipt.py` | 12 | 9.8 | full |
| `tests/test_claim_wording.py` | 8 | 9.4 | full |
| `tests/test_docs_form_gate.py` | 39 | 9.3 | full |
| `tests/test_nwb_synthetic_fixtures.py` | 19 | 9.2 | full |
| `tests/test_nwb_read_tolerance_and_visibility.py` | 31 | 9.0 | full |
| `tests/test_metadata.py` | 102 | 8.8 | full |
| `tests/test_laminar.py` | 79 | 8.7 | full |
| `tests/test_execution_api.py` | 23 | 8.7 | full |
| `tests/test_representative_workflow.py` | 6 | 8.5 | full |
| `tests/test_figure_theme_in_chromium.py` | 1 | 8.5 | full |
| `tests/test_rng_convention_matches_the_signatures.py` | 14 | 8.3 | full |
| `tests/test_batch_a_regressions.py` | 17 | 8.2 | full |
| `tests/test_inspect_one_schema.py` | 19 | 7.9 | full |
| `tests/test_changelog_fragments.py` | 18 | 7.6 | full |
| `tests/test_jrsa_correction_fallback.py` | 31 | 6.8 | full |
| `tests/test_jnwb_core.py` | 26 | 6.8 | full |
| `tests/test_no_fabricated_significance.py` | 21 | 6.7 | full |
| `tests/test_nam.py` | 3 | 6.7 | full |
| `tests/test_unit_quality_screen.py` | 23 | 6.4 | full |
| `tests/test_skill_examples_execute.py` | 37 | 6.3 | full |
| `tests/test_fact_graph_boundary_units.py` | 9 | 6.2 | full |
| `tests/test_gitignore_excludes_cache_by_path.py` | 19 | 6.0 | full |
| `tests/test_decoding_labels.py` | 35 | 5.8 | full |
| `tests/test_composition_band_comparison.py` | 4 | 5.5 | full |
| `tests/test_nwb_integrity.py` | 78 | 5.4 | full |
| `tests/test_addressing.py` | 103 | 5.3 | full |
| `tests/test_spiking.py` | 111 | 4.4 | full |
| `tests/test_jrsa_gpu.py` | 11 | 4.4 | full |
| `tests/test_docs_smoke.py` | 10 | 4.0 | full |
| `tests/test_vflip_calibration_receipt.py` | 9 | 3.7 | full |
| `tests/test_minimal_units_table.py` | 17 | 3.4 | full |
| `tests/test_nwb_validate.py` | 13 | 3.3 | full |
| `tests/test_pca_device_parity.py` | 23 | 3.1 | full |
| `tests/test_jrsa_provenance.py` | 26 | 2.4 | full |
| `tests/test_figure_interactive.py` | 6 | 2.3 | full |
| `tests/test_vis_export_session.py` | 10 | 2.1 | full |
| `tests/test_xflip_nuisance.py` | 6 | 2.0 | full |
| `tests/test_cross_modal_comparison_faces_agree.py` | 13 | 1.8 | full |
| `tests/test_io.py` | 63 | 1.8 | full |
| `tests/test_composition_axis.py` | 16 | 1.7 | full |
| `tests/test_tfr_accumulator.py` | 81 | 1.5 | full |
| `tests/test_unit_suffixed_parameters.py` | 49 | 1.5 | full |
| `tests/test_jrsa_result_io.py` | 19 | 1.4 | full |
| `tests/test_adversarial_inputs.py` | 104 | 1.3 | full |
| `tests/test_connectivity_reporting.py` | 12 | 1.3 | full |
| `tests/test_rsa.py` | 8 | 1.3 | full |
| `tests/test_dashboard_workflow.py` | 13 | 1.2 | full |
| `tests/test_estimator_values_are_pinned.py` | 38 | 1.1 | full |
| `tests/test_continuous.py` | 43 | 0.9 | full |
| `tests/test_r_squared.py` | 11 | 0.9 | full |
| `tests/test_estimator_discrimination.py` | 9 | 0.7 | full |
| `tests/test_precision_switch.py` | 17 | 0.7 | full |
| `tests/test_vis_drawn_data.py` | 18 | 0.6 | full |
| `tests/test_probe_axis_sign_is_pinned.py` | 85 | 0.6 | full |
| `tests/test_spectral_nonfabrication.py` | 23 | 0.6 | full |
| `tests/test_laminar_index_space_and_boundary.py` | 53 | 0.5 | full |
| `tests/test_nwb_inspect_silent.py` | 8 | 0.4 | full |
| `tests/test_epoch_onset_sanity.py` | 27 | 0.4 | full |
| `tests/test_complex_tfr.py` | 44 | 0.4 | full |
| `tests/test_artifact_repair.py` | 36 | 0.4 | full |
| `tests/test_signal_class.py` | 25 | 0.4 | full |
| `tests/test_decoding_nested_cv_pins.py` | 2 | 0.3 | full |
| `tests/test_composition_aggregation_order.py` | 32 | 0.3 | full |
| `tests/test_channel_axis_is_not_assumed.py` | 11 | 0.3 | full |
| `tests/test_majority_baselines_agree.py` | 22 | 0.2 | full |
| `tests/test_no_silent_truncation.py` | 25 | 0.2 | full |
| `tests/test_staggered_shafts.py` | 23 | 0.2 | full |
| `tests/test_composition_identifier_survival.py` | 9 | 0.2 | full |
| `tests/test_xflip_null_method.py` | 13 | 0.1 | full |
| `tests/test_rsa_oracle.py` | 65 | 0.1 | full |
| `tests/test_permutation.py` | 42 | 0.1 | full |
| `tests/test_granger_order_validation.py` | 22 | 0.1 | full |
| `tests/test_unit_quality.py` | 49 | 0.1 | full |
| `tests/test_trajectory.py` | 20 | 0.1 | full |
| `tests/test_integration_0_2_1.py` | 7 | 0.1 | full |
| `tests/test_zero_spread.py` | 11 | 0.1 | full |
| `tests/test_effective_sample_size.py` | 10 | 0.0 | full |
| `tests/test_artifact_detection.py` | 11 | 0.0 | full |
| `tests/test_no_fabricated_spiking_and_repair.py` | 18 | 0.0 | full |
| `tests/test_filtering.py` | 9 | 0.0 | full |
| `tests/test_jaxfne_ground_truth.py` | 4 | 0.0 | full |
| `tests/test_tfr_container.py` | 9 | 0.0 | full |
| `tests/test_tfr_extract_band_regressions.py` | 12 | 0.0 | full |
| `tests/test_calibration_hash_walker.py` | 2 | 0.0 | full |
| `tests/test_jrsa_no_fabricated_failures.py` | 7 | 0.0 | full |
| `tests/test_gpu_pca.py` | 4 | 0.0 | full |
| `tests/test_gpu_launch_overhead.py` | 51 | 4.9 | fast |
| `tests/test_rng_parameters_by_use.py` | 5 | 4.7 | fast |
| `tests/test_module_docstrings_match_their_code.py` | 36 | 4.1 | fast |
| `tests/test_tests_draw_from_seeded_generators.py` | 2 | 3.6 | fast |
| `tests/test_docs_links.py` | 5 | 3.4 | fast |
| `tests/test_prose_version_claims_are_live.py` | 52 | 3.2 | fast |
| `tests/test_readme_smoke.py` | 7 | 3.2 | fast |
| `tests/test_harness_gate.py` | 23 | 3.1 | fast |
| `tests/test_every_declaration_has_a_caller.py` | 7 | 3.0 | fast |
| `tests/test_api_consistency.py` | 104 | 3.0 | fast |
| `tests/test_agents_md_recipes.py` | 7 | 2.9 | fast |
| `tests/test_open_data_through_the_agent_surface.py` | 11 | 2.8 | fast |
| `tests/test_push_guard.py` | 3 | 2.6 | fast |
| `tests/test_stack_edit.py` | 62 | 2.6 | fast |
| `tests/test_vis.py` | 77 | 2.6 | fast |
| `tests/test_statistics_api_split.py` | 35 | 2.5 | fast |
| `tests/test_skill_decline_behaviour.py` | 74 | 2.5 | fast |
| `tests/test_independent_audit_semantics.py` | 33 | 2.4 | fast |
| `tests/test_dependency_floors_are_installable.py` | 19 | 2.3 | fast |
| `tests/test_api_surface.py` | 11 | 2.2 | fast |
| `tests/test_frozen_validated.py` | 10 | 2.2 | fast |
| `tests/test_public_api_reachability.py` | 124 | 2.1 | fast |
| `tests/test_a_silent_no_op_is_refused.py` | 12 | 2.0 | fast |
| `tests/test_no_unreferenced_symbols.py` | 3 | 1.9 | fast |
| `tests/test_analyzers_coverage.py` | 72 | 1.8 | fast |
| `tests/test_generated_files_are_byte_stable.py` | 23 | 1.8 | fast |
| `tests/test_backend.py` | 29 | 1.7 | fast |
| `tests/test_gate8_covers_every_version_surface.py` | 11 | 1.7 | fast |
| `tests/test_distribution_manifest_inspection.py` | 24 | 1.6 | fast |
| `tests/test_dict_access_shim.py` | 62 | 1.6 | fast |
| `tests/test_release_body_script.py` | 10 | 1.5 | fast |
| `tests/test_documentation_form.py` | 45 | 1.5 | fast |
| `tests/test_docs_interpretation_statements.py` | 10 | 1.4 | fast |
| `tests/test_switch_rebinding_is_reviewed.py` | 3 | 1.3 | fast |
| `tests/test_testing_synth.py` | 36 | 1.2 | fast |
| `tests/test_computational_contract_gate.py` | 5 | 1.2 | fast |
| `tests/test_release_body_gate.py` | 53 | 1.1 | fast |
| `tests/test_device_denial_contract.py` | 21 | 1.1 | fast |
| `tests/test_docs_user_navigation.py` | 11 | 1.0 | fast |
| `tests/test_viz.py` | 18 | 0.8 | fast |
| `tests/test_skill_symbol_coverage.py` | 20 | 0.8 | fast |
| `tests/test_shipped_code_names_no_process_ids.py` | 2 | 0.6 | fast |
| `tests/test_skill_degenerate_claims.py` | 9 | 0.5 | fast |
| `tests/test_frozen_core_mutants.py` | 10 | 0.5 | fast |
| `tests/test_references_resolve.py` | 18 | 0.5 | fast |
| `tests/test_paths.py` | 48 | 0.4 | fast |
| `tests/test_pointer_documents_resolve.py` | 18 | 0.3 | fast |
| `tests/test_vis_label_range_edges.py` | 10 | 0.3 | fast |
| `tests/test_docs_decoding_chain.py` | 8 | 0.3 | fast |
| `tests/test_architecture_page_reachability.py` | 12 | 0.3 | fast |
| `tests/test_stack_metadata_contradictions.py` | 66 | 0.3 | fast |
| `tests/test_single_agent_instruction_file.py` | 6 | 0.3 | fast |
| `tests/test_skill_routing_behaviour.py` | 6 | 0.3 | fast |
| `tests/test_skills_are_findable_from_an_installed_copy.py` | 11 | 0.3 | fast |
| `tests/test_vis_shared_rules.py` | 16 | 0.2 | fast |
| `tests/test_rng_spelling.py` | 56 | 0.2 | fast |
| `tests/test_ci_conclusion_gate.py` | 29 | 0.2 | fast |
| `tests/test_public_surface_manifest.py` | 4 | 0.2 | fast |
| `tests/test_vis_draws_no_default_landmark.py` | 5 | 0.2 | fast |
| `tests/test_paths_identity.py` | 14 | 0.2 | fast |
| `tests/test_obligation_diff.py` | 5 | 0.1 | fast |
| `tests/test_skill_router_reach.py` | 35 | 0.1 | fast |
| `tests/test_figure_tabs_and_state.py` | 7 | 0.1 | fast |
| `tests/test_synthetic_figures_are_labelled.py` | 5 | 0.1 | fast |
| `tests/test_release_version_is_unpublished.py` | 14 | 0.1 | fast |
| `tests/test_skill_default_claims_match_signatures.py` | 2 | 0.1 | fast |
| `tests/test_generation_closure_is_declared.py` | 13 | 0.1 | fast |
| `tests/test_vis_heatmap_ribbon_sem.py` | 6 | 0.1 | fast |
| `tests/test_docs_runnable_prerequisites.py` | 4 | 0.1 | fast |
| `tests/test_optional_dependencies.py` | 2 | 0.1 | fast |
| `tests/test_composition_failure_propagation.py` | 12 | 0.1 | fast |
| `tests/test_skill_claims_match_the_router.py` | 4 | 0.1 | fast |
| `tests/test_role_files_point_to_one_contract.py` | 13 | 0.0 | fast |
| `tests/test_api_md_experimental_section.py` | 2 | 0.0 | fast |
| `tests/test_helper_rule_names.py` | 5 | 0.0 | fast |
| `tests/test_nonfinite_trial_starts_are_refused.py` | 16 | 0.0 | fast |
| `tests/test_git_checkout_mark.py` | 4 | 0.0 | fast |
| `tests/test_addressing_silent.py` | 8 | 0.0 | fast |
| `tests/test_standing_rules_name_no_cycle.py` | 3 | 0.0 | fast |
| `tests/test_reference_claims_ledger.py` | 4 | 0.0 | fast |
| `tests/test_findings_ledger.py` | 6 | 0.0 | fast |
| `tests/test_audit_reproducers.py` | 3 | 0.0 | fast |
| `tests/test_deprecated_aliases.py` | 3 | 0.0 | fast |
| `tests/test_window_default_deprecation.py` | 6 | 0.0 | fast |
| `tests/test_uncovered_exports.py` | 7 | 0.0 | fast |
| `tests/test_figure_sources_outside_docs.py` | 2 | 0.0 | fast |
| `tests/test_laminar_silent.py` | 3 | 0.0 | fast |
| `tests/test_psd_silent.py` | 2 | 0.0 | fast |
| `tests/test_stack_item_length.py` | 2 | 0.0 | fast |
