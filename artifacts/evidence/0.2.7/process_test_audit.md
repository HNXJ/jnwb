# Process-test audit (07-23)

Baseline `4fac3517991b1ab390dcfbd766276679887fd7ac`, in a detached worktree. Read-only: nothing in the repository changed.

## Method

- **Scope.** 85 of the 186 `tests/test_*.py` files. A file is in scope when its main subject is docs, stacks, prose, gates or rulings. Library files that only have one doc-pinning test (`test_jrsa`, `test_onset_fitting`, `test_ontology`, `test_statistics`, `test_execution_switch`, `test_mcp_server`, `test_laminar`, `test_nwb_read_tolerance_and_visibility`) are out of scope.
- **Runtime.** Each file's time is the sum of setup, call and teardown over its testcases, taken from one full-suite junit run: `pytest tests/ -n 8 --durations=0 --junitxml`. That run gave `5626 passed, 8 skipped ... in 695.05s`. Other agents' Python processes were loaded on the machine during the run, so treat the absolute times as upper bounds. The 85 files take 2638.6 s of the suite's 3358.9 s summed test time (79%).
- **Kind.** `lib` means the file calls jnwb and checks the result. `pin` means it pins wording or structure. `tool` means it runs `scripts/` gates or tooling on constructed trees. Mixed files carry two labels.
- **Condition** refers to `AGENTS.md` §11. C1 is documentation form and truth, including public skills. C2 is code complexity and switchability. C3 is the empty problem stack and fixpoint, together with the blocker predicate's evidence-validity clauses: harness, CI, packaging and provenance. `none` means the file carries no acceptance evidence.
- **Dependencies.** `tests/test_gates_reject_the_trees_they_passed.py:26` imports `broken_links` from `test_docs_links`. `scripts/docs_form_gate.py:65-66` imports `tests.test_documentation_form` and `tests.test_figure_form`. `test_every_declaration_has_a_caller::test_every_script_has_a_caller` treats a test as a script's caller. No other test imports another test file, and `conftest.py` defines one fixture, `git_checkout_probe`.

## Totals

| Recommendation | Files |
|---|---|
| keep | 77 |
| merge | 4 |
| prune | 4 (one conditional) |

Test-level edits inside kept files: 7 tests. They are listed after the main table.

## Prune list (for Hamm's ruling; nothing deleted)

| File | Runtime | Evidence it carries no acceptance evidence | Dependents |
|---|---|---|---|
| `test_findings_ledger.py` | 0.18 s | It checks that `artifacts/evidence/0.2.6/findings_0.2.6.md` maps every identifier in `artifacts/archive/0.2.5/alignment_review_0.2.5.md`. That was the acceptance of 0.2.6 item 06-03 (docstring of `test_identifier_sets_match`), in a closed cycle, and both files are records. No 0.2.7 item cites the ledger. | `git grep` finds it only in the ledger itself and in its own file. It defines no shared fixture. |
| `test_single_agent_instruction_file.py` | 0.26 s | It pins repository process structure: no tracked root `CLAUDE.md`, `.gitignore` covers it, and `AGENTS.md` says "only repository-level". Gate 4 does not cover this, because `ALLOWED_ROOT_FILES` includes `CLAUDE.md` (`scripts/harness_gate.py:422`). No shipped artifact, public claim or release gate reads it. | Only `CHANGELOG.md:1069` names it. No fixture. |
| `test_standing_rules_name_no_cycle.py` | 0.04 s | It pins that `AGENTS.md`, the problem-stack header, `CONTRIBUTING.md` and the skills write `required-<cycle>`/`deferred-<next>` as templates. The labels that decide a release are enforced on the stack itself by the release gate, which derives them from the version: `test_release_requires_an_empty_problem_stack.py::test_an_item_deferred_to_any_cycle_but_the_next_fails` and `::test_a_release_step_for_any_other_cycle_or_in_any_other_form_is_required`. | None found by `git grep`. No fixture. |
| `test_agents_md_stays_a_router.py` (conditional) | 5.99 s | It is a duplication ratchet on `AGENTS.md`, which does not ship (`test_distribution_manifest_inspection::test_the_repositorys_own_working_rules_are_rejected`). It is process-only, and the 07-23 AGENTS.md redraft will move its baselines anyway. | It is the only tracked caller of `scripts/measure_agents_md_duplication.py`, so pruning it alone fails `test_every_declaration_has_a_caller::test_every_script_has_a_caller`. Prune the test and the script together, after the redraft lands. |

Two more files meet both prune criteria, but I recommend keeping them.

| File | Runtime | Why kept |
|---|---|---|
| `test_gitignore_excludes_cache_by_path.py` | 3.84 s | No acceptance evidence and no dependents. It is the only guard on the P-10 path rule, which keeps 6.7 GB out of the index. |
| `test_pointer_documents_resolve.py` | 0.15 s | No acceptance evidence. It is the only resolver of AGENTS.md section references and fact-stack paths, and 07-23 is about to rewrite both. |

## Merge list

| File | Merge into | Overlap (test names) |
|---|---|---|
| `test_release_recovery_gates.py` | Split it three ways. The compat tests go to `test_jrsa.py`. The generator tests go to `test_api_md_is_interpreter_independent.py`. The CI-extras test goes to `test_workflow_release_policy.py`. | `TestApiMdDeterminism::test_generator_passes_on_current_interpreter` (19.9 s) repeats gate 9's `check_api_md_is_generated`, which runs in `test_every_gate_runs::test_the_live_repository_passes_every_gate`. `::test_generator_passes_on_python_floor_when_available` (43.8 s) repeats `test_api_md_is_interpreter_independent::test_generated_bytes_are_identical_across_available_interpreters`. `TestReleaseGateCoverage::test_release_gate_checks_api_md_generator` is a substring proxy (`"generate_api_md.py" in text and "--check" in text`): a comment would satisfy it. Delete it rather than move it, because the release gate also runs gate 9 through `harness_gate.py` (`scripts/release_gate.py:1770`). |
| `test_state_reconstruction.py` | `test_state_basis_is_checked.py` | Two tests do not check what their names say. `test_a_moved_head_reads_as_stale` never runs `--check`: it only asserts `recorded_head(zeros) != git HEAD`, and it still pays for the generator fixture (48.4 s). `test_check_exits_nonzero_when_the_file_is_absent` never removes a file or reads an exit code: it asserts the parser returns `None` on a string. The subprocess versions are `test_state_basis_is_checked::test_a_moved_head_fails`, `::test_an_absent_file_fails` and `::test_a_file_with_no_head_row_fails`. Gate 20 has its own cases in `test_harness_adversarial_gates.py` (`test_a_zeroed_head_row_fails_naming_both_commits`, `test_a_file_with_no_head_row_fails`). The file costs 242.2 s, from four generator builds of 47 to 96 s each. |
| `test_xflip_calibration_receipt.py` | `test_vflip_calibration_receipt.py` (one parametrized receipt file) | Same test names: `test_receipt_and_generator_exist`, `test_receipt_was_generated_from_the_current_estimator`, `test_the_receipt_covers_every_helper_{v,x}flip_reaches`, `test_report_is_rendered_from_the_raw_receipt`. Both guard shipped calibration numbers, so the checks stay and only the file goes. |
| `test_test_imports_survive_the_wheel_leg.py` | `test_the_suite_can_qualify_an_installed_copy.py` | `test_the_qualification_leg_still_clears_pythonpath` substring-matches `-o pythonpath=` anywhere in `workflow.yml`. `test_ci_runs_the_suite_against_the_installed_wheel` asserts the same clause on the leg's own step body, plus four more. Both files police test modules for the installed-copy leg. |

## Test-level edits inside kept files

| File::test | Action | Evidence |
|---|---|---|
| `test_errors_documented.py::TestErrorsPageReachable::test_every_hand_written_page_is_in_the_nav` | delete | It is a substring test over raw `mkdocs.yml` (`... not in nav`), so it credits any mention, including `exclude_docs` and comments (probe F1). `test_docs_user_navigation::test_no_page_is_orphaned` is the stronger form of the same rule. |
| `test_readme_smoke.py::test_readme_does_not_hardcode_public_symbol_count` | delete | It is a strict subset of `test_harness_adversarial_gates.py::...::test_no_hardcoded_symbol_counts_remain_in_prose`, which covers the same `README.md` with a wider pattern. |
| `test_readme_smoke.py::test_readme_python_version_matches_policy` | delete | Gate 8 holds `README.md`, alongside four other surfaces, to the declared interpreter set (`test_gate8_covers_every_version_surface::test_the_pristine_surfaces_agree`, `::test_a_skewed_floor_fails`, `::test_a_skewed_tested_set_fails`). The README test's regex ignores matrix `exclude`, which gate 8 handles (`::test_a_version_every_leg_of_which_is_excluded_is_untested`). |
| `test_api_md_is_interpreter_independent.py::test_committed_page_has_lf_endings_in_bytes` | delete | `test_generated_files_are_byte_stable::test_the_stored_bytes_contain_no_carriage_return[docs/api.md]` checks the index bytes of the same file, and `.gitattributes` `* -text` makes the two equal. |
| `test_docs_nwb_workflow.py::test_mkdocs_strict_build` | move to `test_diagrams_render.py` | Both build the site with `--strict`: `diagrams_render`'s module fixture runs `mkdocs build --strict`, and this test runs `scripts/docs_build.py`. One build can serve both. Keep the `docs_build.py` form, because `diagrams_render` skips when mkdocs is absent. |
| `test_agents_md_recipes.py::test_every_repository_path_agents_md_cites_exists`, `::test_the_generated_path_exemption_does_not_excuse_an_ordinary_missing_file`, `::test_agents_md_does_not_point_at_a_todo_item_that_is_not_there` | move to `test_pointer_documents_resolve.py` | That file's docstring says it complements these three. Together they form one registry check on AGENTS.md, and the rest of `test_agents_md_recipes` executes `docs/recipes.md`. |
| `test_docs_user_navigation.py::_nav_targets` | repair (F1) | See the findings below. |

## Main table

| File | What it checks | Kind | Cond. | Runtime | Rec. |
|---|---|---|---|---|---|
| `test_agents_md_recipes.py` | `docs/recipes.md` blocks run outside the checkout; AGENTS.md paths and todo ids resolve | lib + pin | C1 | 1.76 s | keep (move 3 pointer tests) |
| `test_agents_md_stays_a_router.py` | duplication ratchet on AGENTS.md via `measure_agents_md_duplication.py` | tool + pin | none | 5.99 s | prune (with script) |
| `test_api_md_is_interpreter_independent.py` | `docs/api.md` generator is interpreter-independent | tool | C1 | 22.97 s | keep (receives merge) |
| `test_api_md_member_types.py` | api.md Type column true of runtime objects; gate 18 | lib + tool | C1 | 0.41 s | keep |
| `test_api_surface.py` | module disposition vs exports; module-map page rows | lib + pin | C1 | 0.86 s | keep |
| `test_architecture_page_reachability.py` | architecture page on nav; diagrams do not route researchers through agents | pin | C1 | 0.12 s | keep |
| `test_axis_convention_matches_the_specification.py` | spec §5 axis line matches code; calls referencing functions | lib + pin | C1 | 0.97 s | keep |
| `test_ci_conclusion_gate.py` | release gate resolves CI for the exact commit | tool | C3 | 0.12 s | keep |
| `test_claim_wording.py` | causal or delay words on public surfaces only in listed uses | pin | C1 | 0.80 s | keep |
| `test_collection_order_stability.py` | an ad-hoc subset does not segfault; no `sys.modules` clear | tool | C3 | 23.54 s | keep |
| `test_computational_contract_gate.py` | gate 21 fails on seeded violations | tool | C2 | 0.78 s | keep |
| `test_computational_order_sources_agree.py` | order inventory vs benchmark labels; jackknife and streaming-reader facts | lib + pin | C2 | 4.08 s | keep |
| `test_cross_modal_comparison_faces_agree.py` | both `bin_ms` estimators vs the connectivity skill's text | lib + pin | C1 | 1.34 s | keep |
| `test_dependency_floors_are_installable.py` | floor check in the release gate; CI floors leg | tool | C3 | 0.91 s | keep |
| `test_diagrams_render.py` | mermaid fences become diagrams in the built HTML | tool | C1 | 59.21 s | keep (receives strict build) |
| `test_distribution_manifest_inspection.py` | wheel and sdist pollution matcher, shared with CI | tool | C3 | 0.40 s | keep |
| `test_docs_call_shapes.py` | documented calls bind live signatures; runnable blocks execute | lib + pin | C1 | 12.86 s | keep |
| `test_docs_decoding_chain.py` | mermaid composition edges vs signatures; partition chain runs | lib + pin | C1 | 0.07 s | keep |
| `test_docs_form_gate.py` | `scripts/docs_form_gate.py` seeded violations and live tree | tool | C1 | 1.85 s | keep |
| `test_docs_interpretation_statements.py` | page caveats checked against units, signs and signatures | lib + pin | C1 | 0.85 s | keep |
| `test_docs_links.py` | internal links in `docs/` and `artifacts/agents.md` resolve | pin | C1 | 0.06 s | keep (dependency) |
| `test_docs_nwb_workflow.py` | README NWB block executes; nav order; skill routes; strict build | lib + pin | C1 | 7.60 s | keep (move strict build) |
| `test_docs_operation_statements.py` | method and troubleshooting statements vs calls | lib + pin | C1 | 4.30 s | keep |
| `test_docs_runnable_prerequisites.py` | run instructions state that a clone is required | pin | C1 | 0.06 s | keep |
| `test_docs_smoke.py` | executes each doc page's snippets | lib | C1 | 1.54 s | keep |
| `test_docs_user_navigation.py` | nav: no dead, duplicate, orphan or contributor pages | pin | C1 | 0.07 s | keep; repair F1 |
| `test_documentation_form.py` | F1, F5, N1, N2 of `documentation_form.md` | pin | C1 | 1.16 s | keep (imported by gate script) |
| `test_errors_documented.py` | error classes on `docs/errors.md`; gate 5; quoted messages exist in source | lib + pin | C1 | 0.96 s | keep (delete 1 test) |
| `test_every_declaration_has_a_caller.py` | declared test deps and scripts have callers | pin | none | 0.61 s | keep (it guards the prunes above) |
| `test_every_gate_runs.py` | harness reports every gate; live tree passes all | tool | C3 | 9.61 s | keep |
| `test_examples_quickstart.py` | `examples/quickstart_jnwb.py` runs end to end | lib | C1 | 14.75 s | keep |
| `test_figure_form.py` | G1 and G2: transparent backgrounds, contrast, both variants, legends | lib + pin | C1 | 7.76 s | keep (imported by gate script) |
| `test_findings_ledger.py` | 0.2.6 ledger resolves 0.2.5 review identifiers | pin | none | 0.18 s | prune |
| `test_frozen_validated.py` | gate 19 frozen-validated hashes | tool | C3 | 0.19 s | keep |
| `test_gate2_ignores_nested_checkouts.py` | gates 2 and 4 with worktrees and duplicates | tool | C3 | 9.74 s | keep |
| `test_gate8_covers_every_version_surface.py` | gate 8 holds README, install page and CI to the interpreter set | tool | C1, C3 | 0.99 s | keep |
| `test_gates_reject_the_trees_they_passed.py` | gates 1-13 reject the trees they once accepted | tool | C3 | 2.75 s | keep |
| `test_generated_figures_are_maintained.py` | committed figures equal generator output, compared on pixels | lib | C1 | 110.64 s | keep |
| `test_generated_files_are_byte_stable.py` | generated files are LF in the index; writers pass `newline` | tool | C3 | 1.17 s | keep |
| `test_generation_closure_is_declared.py` | derived-file closure gate; mutation harness named | tool | C3 | 0.46 s | keep |
| `test_git_checkout_mark.py` | `requires_git_checkout` skips only without `.git` | tool | C3 | 0.02 s | keep |
| `test_gitignore_excludes_cache_by_path.py` | cache excluded by a path rule | pin | none | 3.84 s | keep (prune-eligible) |
| `test_harness_adversarial_gates.py` | adversarial probes for gates 1-20, stack parser, role and skill files | tool + pin | C3, C1 | 13.43 s | keep |
| `test_import_lazy.py` | eager import surface; extras; `docs/install.md` statement | lib | C2, C1 | 34.97 s | keep |
| `test_import_profile_receipt.py` | import profile and peak-memory record describe this release | lib + tool | C2, C3 | 11.39 s | keep |
| `test_import_provenance.py` | the suite asserts which jnwb it tests | tool | C3 | 77.72 s | keep |
| `test_lane_verifies_its_own_baseline.py` | `verify_lane.py` refuses distances, drift and the main tree | tool | C3 | 15.47 s | keep |
| `test_line_endings_survive_an_edit.py` | gate 16 rule 2: wholesale line-ending conversion | tool | C3 | 11.39 s | keep |
| `test_module_docstrings_match_their_code.py` | harness docstrings plus library docstrings (divisors, return names, dtypes) | lib + pin | C1 | 2.40 s | keep |
| `test_mutation_harness_validity.py` | mutation-harness guards against false kills; release known-gaps step | tool | C3 | 136.78 s | keep |
| `test_no_unreferenced_symbols.py` | no uncalled module-level symbol without a listed reason | pin | C2 | 0.82 s | keep |
| `test_notebooks.py` | notebooks execute | lib | C1 | 8.88 s | keep |
| `test_open_data_example.py` | open-data excerpt identity; clock derived from the file | lib | C1 | 12.18 s | keep |
| `test_pointer_documents_resolve.py` | AGENTS.md, stack and fact pointers resolve; no finished work in todo | pin | none | 0.15 s | keep (receives 3 tests; prune-eligible) |
| `test_precision_switch.py` | precision registry vs live dtypes | lib | C2 | 0.74 s | keep |
| `test_prose_version_claims_are_live.py` | versions written in prose are live or declared | pin | C1 | 1.73 s | keep |
| `test_readme_smoke.py` | README blocks execute; links; capability-table symbols | lib + pin | C1 | 0.66 s | keep (delete 2 tests) |
| `test_references_resolve.py` | DOIs on the references page vs docstring citations | lib + pin | C1 | 0.12 s | keep |
| `test_release_body_gate.py` | GitHub Release body vs metadata | tool | C3 | 2.27 s | keep |
| `test_release_recovery_gates.py` | Granger compat, api.md generator, release-gate substring, CI extras | lib + tool | C1, C3 | 63.73 s | merge (split) |
| `test_release_requires_an_empty_problem_stack.py` | condition 3 STEP 0a on constructed repositories | tool | C3 | 386.14 s | keep |
| `test_release_version_is_unpublished.py` | version not already on the index | tool | C3 | 0.09 s | keep |
| `test_rng_convention_matches_the_signatures.py` | documented RNG convention vs signatures and calls | lib + pin | C1, C2 | 6.37 s | keep |
| `test_semantic_mutation_classes.py` | 14 mutation classes killed over the composition subset | tool + lib | C3 | 460.14 s | keep |
| `test_single_agent_instruction_file.py` | AGENTS.md is the only tracked root instruction file | pin | none | 0.26 s | prune |
| `test_skill_claims_match_the_router.py` | skill safeguards no stronger than the router; PSI receipt re-run | lib + pin | C1 | 0.04 s | keep |
| `test_skill_decline_behaviour.py` | every skill outcome settled by a real call | lib | C1 | 3.64 s | keep |
| `test_skill_default_claims_match_signatures.py` | prose defaults in skills vs signatures | lib + pin | C1 | 0.05 s | keep |
| `test_skill_router_reach.py` | router names every skill; openai.yaml description equals SKILL.md | pin | C1 | 0.04 s | keep |
| `test_skill_routing_behaviour.py` | six corrected routing rows executed | lib | C1 | 0.25 s | keep |
| `test_skill_symbol_coverage.py` | every export routed or excluded with a checked reason | lib + pin | C1 | 0.06 s | keep |
| `test_skills_are_findable_from_an_installed_copy.py` | `SKILLS_URL`, sdist graft, docs statements | lib + pin | C1, C3 | 0.24 s | keep |
| `test_skills_validation.py` | routing rows bind and return what they say; skill form | lib + pin | C1 | 10.14 s | keep |
| `test_stack_metadata_contradictions.py` | gate 15: truncated write sets, false `none`, miscounts | tool | C3 | 0.46 s | keep |
| `test_standing_rules_name_no_cycle.py` | standing rules write release labels as templates | pin | none | 0.04 s | prune |
| `test_state_basis_is_checked.py` | `reconstruct_state --check` exit codes; generated prose vs gate scan | tool | C3 | 52.35 s | keep (receives merge) |
| `test_state_reconstruction.py` | state generator determinism, slots, not committed | tool | C3 | 242.22 s | merge |
| `test_synthetic_figures_are_labelled.py` | figure captions say synthetic | pin | C1 | 0.06 s | keep |
| `test_test_imports_survive_the_wheel_leg.py` | no module-scope import of unshipped paths | tool | C3 | 6.14 s | merge |
| `test_the_suite_can_qualify_an_installed_copy.py` | suite can test the installed wheel; CI leg shape | tool | C3 | 11.73 s | keep (receives merge) |
| `test_tutorial_00_foreign_shapes.py` | tutorial 00 on irregular or processing-module files | lib | C1 | 408.23 s | keep |
| `test_tutorials.py` | every tutorial executes | lib | C1 | 250.18 s | keep |
| `test_vflip_calibration_receipt.py` | vFLIP receipt hash covers the shipped estimator | lib + tool | C1, C2 | 0.31 s | keep (receives merge) |
| `test_workflow_release_policy.py` | CI publish topology, pins, concurrency | tool | C3 | 85.77 s | keep (receives CI-extras test) |
| `test_xflip_calibration_receipt.py` | xFLIP receipt hash covers the shipped estimator | lib + tool | C1, C2 | 0.46 s | merge |

## Findings

| Id | Finding | Class | Receipt |
|---|---|---|---|
| F1 | `test_docs_user_navigation.py::_nav_targets` reads the nav with a regex over raw text, not YAML. A commented-out nav line therefore counts as a live entry, and `test_no_page_is_orphaned` passes on a page that is on no nav entry. The only other orphan check, `test_errors_documented::test_every_hand_written_page_is_in_the_nav`, is a substring test and passes the same tree. Gate 13 catches commented-out entries only for the NWB tutorial pages (`test_gates_reject_the_trees_they_passed::test_a_commented_out_nav_entry_is_rejected`). The live tree is currently right: a YAML walk and the regex both give 32 targets and no orphans. | proposed required-0.2.7: a check that condition 1's navigation evidence relies on can pass falsely. Smallest repair: `_nav_targets` walks `yaml.safe_load(...)["nav"]`, as `_excluded_from_the_site` already does, with a fixture carrying a commented entry. | `probe_nav.py`: YAML nav `[{'Home': 'index.md'}]`; `_nav_targets()` returns `['index.md', 'hidden.md']`; `test_no_page_is_orphaned: PASSED on a tree whose hidden.md is on no live nav entry`; the substring predicate gives `missing = []`. `probe_nav_live.py`: `yaml targets 32 regex targets 32`, `orphans by YAML: []`. |
| F2 | `test_state_reconstruction::test_a_moved_head_reads_as_stale` and `::test_check_exits_nonzero_when_the_file_is_absent` do not run `--check`. | deferred-0.2.8: `test_state_basis_is_checked` and gate 20's tests hold the invariant with subprocess calls. | See the merge list. |
| F3 | `test_release_recovery_gates::test_release_gate_checks_api_md_generator` is a substring proxy. | deferred-0.2.8: the release gate also runs gate 9 through `harness_gate.py`. | `scripts/release_gate.py:979-985` holds the real call; `:1770` runs the harness. |
| F4 | `test_every_declaration_has_a_caller::test_every_script_has_a_caller` counts any mention in tracked text as a caller, so a changelog line keeps a script alive. | deferred-0.2.8: it covers no release evidence. | `tests/test_every_declaration_has_a_caller.py:124`: `elsewhere = corpus.count(stem) - ...`. |
| F5 | `test_test_imports_survive_the_wheel_leg::test_the_qualification_leg_still_clears_pythonpath` matches `-o pythonpath=` anywhere in `workflow.yml`, not on the leg. | deferred-0.2.8: `test_the_suite_can_qualify_an_installed_copy::test_ci_runs_the_suite_against_the_installed_wheel` asserts it on the step body. | `tests/test_test_imports_survive_the_wheel_leg.py:224` |

## Not covered

| Item | Why |
|---|---|
| Every assertion in `test_harness_adversarial_gates.py` (211 cases) and `test_release_requires_an_empty_problem_stack.py` (162 cases) | Reviewed by test name and docstring only. No proxy hunt per assertion. |
| Serial per-file timings | Timed from one `-n 8` run on a loaded machine. No `--durations=0 <file>` rerun per file. |
