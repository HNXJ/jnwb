# 0.2.17

Context audit (2026-11-13): current priorities and midterm dependencies are indexed in `artifacts/ref/context_audit_2026-11-13.md`; existing item IDs, write scopes, release rulings and acceptance checks remain authoritative. Open blockers: OCMA-5 and 17-144-src. No item was closed or rescored by this documentation audit.


Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.16
closed on 2026-11-08 (tag `v0.2.16`, `0aa220ba`; tag CI/CD run 42513450995 success, TestPyPI and PyPI
verified, GitHub release body checked by `release_gate.py` STEP 0d). Items run fastest first.

Thinning and matching from the 2026-11-02 audits, each named by SHA: seven models at `7ca5b9a6` (17-83 to 17-105) and eight auditors at `9fd2b4bd` (P-216 rows, 17-128, 17-129). Lanes form at 0.2.16's close; 17-79 (which rewrote `_xflip.py`
and `_zflip.py`) landed at e6baac97, so 17-94 is unblocked. Each item applies the jarness standards: `match-cleanup` for
removals, `match-code-style` for code, `match-writing-style` for prose, `match-visual-style` for figures.

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet (`artifacts/agents/jnwb-developer.md`); a lane is one linked worktree (`scripts/verify_lane.py` refuses a clone) and one worker; up to three lanes at once; a lane's items run in the order listed | lanes share no file, so they merge without conflict |
| A public signature, an estimand or a skill line goes to Hamm before code, batched in one message per wave; Haiku implements a ruled signature and never chooses one | public API and skills are Hamm's |
| A packet reproduces its bullet first, writes the failing test, then the fix; a `reviewer` that did not write it verifies; the integrator commits, owns the stacks, `CHANGELOG.md` and `docs/api.md` | the actor is never the verifier |
| Wave barrier: `python scripts/harness_gate.py`, the full suite, push, CI green on `dev` at that SHA | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then one bullet:
`ID: defect with numbers. Check: a predicate naming the file and the asserted value.`
At most eight lines per item.

### 17-154 The full suite stalls at about 99%

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none (merge 7bc91d79 adds `-o faulthandler_timeout=900` to `scripts/jnwb_suite.sh`; the dump does not stop a stalled run, so a stall still needs a manual stop after its dump).
Writes: `scripts/jnwb_suite.sh`, `tests/test_*.py`.
- 17-154: from open row `17-147-hang` (ruled 2026-11-22, A6 modified): two stalls at about 99% with 12 idle workers (9479505e on 2026-11-18, 9ad92d4b on 2026-11-19), stuck test unidentified; suspects by file time only: the wheel and foreign-NWB tests. Check: two clean full-suite runs under the dump configuration, each log and SHA cited; or a dump names the stalled test and a verified repair removes the stall. A dump alone is diagnosis and closes nothing.

### 17-153 The fact gate reads each cited line

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `scripts/fact_graph/*.py`, `tests/test_fact_gate.py`.
- 17-153: ruled 2026-11-22 (A1): the fact gate passed while eight cites in six fact rows pointed at moved lines (defect class seen three times: the 17-79 split, the 17-128 docstrings, the 2026-11-21 review). Check: for each `path:line` cite in a default row of `artifacts/fact_stack.md`, the gate fails when the cited line lacks the row's default literal; a planted stale cite turns it red; the existing fact gate passing does not close this item.

### 17-150 AST scan for NaN-passing sign guards

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-147 (shared `scripts/learning_gate.py`).
Writes: `scripts/learning_gate.py`, `tests/test_nan_passes_sign_guard_scan.py`.
- 17-150: state-4 of the 2026-11-08 audit: `nan-passes-sign-guard` in `artifacts/process/defect_classes.md` still proposes an AST scan for a bare `<= 0` / `< 0` guard with no finiteness test. Check: a gate or test fails when such a guard is planted, and the eight sites of row `nan-passes-sign-guard` in `artifacts/process/defect_classes.md` stay covered.

### 17-147 Audit 2026-11-08: scripts and tests that cannot fail

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none (scripts-2 runs in lane `_temp_gate15-c901`).
Writes: `scripts/push_guard.py`, `scripts/learning_gate.py`, `scripts/gates/state.py`, `scripts/stack_parse.py`, `scripts/measure_agents_md_duplication.py`, `scripts/vflip2_recovery.py`, `scripts/figures/generate_figures.py`, `scripts/figures/figure_registry.toml`, `tests/test_*.py`.
- 17-147: push_guard half landed 2026-11-21 (merge 264ea80d) and closes on its bounded requirement (ruled 2026-11-22, A6): the text guard denies the set merged there; known limit, no general push enforcement claimed: a directory reached through a variable, substitution, `env -C`, `sudo -D` or `find -execdir`; cd or push spelled through quoting, `$IFS`, an alias, `send-pack` or a glob; a junction; another interpreter. The push wrapper and CI gate stay the enforcing gate. scripts-2 landed 2026-11-22 (merge 3f6f7e86, verified): zero tables pass only when `AGENTS.md` and `CONTRIBUTING.md` lose no obligation clause against the newest `v*` tag; missing base fails. Left from its verification: D1, a deleted clause passes when another clause shares its obligation word (`AGENTS.md` "never doctrine" matched "never pooled" at Jaccard 0.11), so `scripts/learning_gate.py:13-15` and `CONTRIBUTING.md:80-82` ("keep every obligation clause") overstate the check: narrow the prose, or Hamm rules a stricter match; D2, no test pins `newest_release_tag` to an ancestor tag (`learning_gate.py:192-200`; a creation-date mutant survives); tests-4 at `tests/test_nwb_read_tolerance_and_visibility.py:230` (`_refusal` catches `Exception`; its callers assert `MissingRequiredNWBFieldError`). Check: gate 15 fails on zero tables with a lost clause or a missing base; `_refusal` catches the named error only; `ruff check tests --select F401,F541,F821,F841` clean.

### 17-144 The jaxfne isi_cv commits

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-144-src (open stack; `E:/cl-jnwb16e` gone, SHAs absent from origin).
Writes: `artifacts/benchmarks/realdata/isi_cv_recompute.py`, `artifacts/benchmarks/realdata/isi_cv_recompute_receipt.json`, `artifacts/benchmarks/realdata/build_isi_cv_fixture.py`, `tests/fixtures/isi_cv_realdata_subsample.json`, `tests/test_isi_cv_realdata.py`.
- 17-144: three 16-12 commits on `E:/cl-jnwb16e` (0e06993c, 9980f58d, 5fa63dd3) for jaxfne-orchestrator.
  Observed 2026-11-12: path missing; SHAs absent from this clone and `origin`. Check: each on `dev` in that
  order, suite passes, jaxfne-orchestrator told.

### 17-94 One home per helper in jnwb

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `jnwb/**/*.py`.
- 17-94: landed 2026-11-21 (merge 9427c84a): `_units.require_positive_fs` (bandpass, notch, spectral; NaN and Inf refused by name), `nwb_write._sha256` is `paths.sha256_file`, one `_onset_counts` in `_bins.py`, tests in `tests/test_fs_nonfinite.py`; `_decibels` is already one home (`_decibels.py:15,24,52`). Left: the `fs` positive check hand-written at 17 code lines (`grep -rnE '\bfs\s*(<=|<|>=|>)\s*0\b' jnwb`; e.g. `tfr.py:269` in `complex_tfr`, where NaN reaches `morlet_wavelet`, which refuses it at `tfr.py:136-137`); 8 `_require_*` definitions in `jnwb/spectral`; inventory in `artifacts/evidence/0.2.17/fs_inventory_17-94.md` (52 rows: SAME-CHECK 22, DIFFERENT-MESSAGE 11; REDUNDANT-WITH 7 `_require_*` definitions); `_window_rows` twice (`_xflip.py:96`, `_zflip.py:178`); the private helpers the 17-79 splits added in `_xflip.py`, `_zflip.py`, `_vflip.py`, `jrsa/__init__.py` and `_psi.py`, unsurveyed. Check: one definition each, the grep returns one site, the suite passes.

### 17-95 One home per helper in scripts and tests

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/stack_parse.py`, `scripts/release_gate.py`, `scripts/build_fact_graph.py`, `scripts/learning_gate.py`, `scripts/build_dashboard.py`, `scripts/docs_form_gate.py`, `scripts/reconstruct_state.py`, `scripts/measure_peak_memory.py`, `scripts/mutation_harness.py`, `scripts/verify_lane.py`, `scripts/gates/boundary.py`, `tests/conftest.py`, `tests/test_*.py`.
- 17-95: landed 2026-11-21 (merge 91424ae7): 10 test splitters use `stack_parse.cells`; git calls in `release_gate`, `build_dashboard`, `build_fact_graph`, `fact_graph/source_scans` and 8 test `_git` helpers use `gates.boundary.git`. Kept raw, with reason: byte capture (`learning_gate.py:131`, `release_gate.py:1534,1623`, `gates/boundary.py:579,601`, 4 test helpers); injected runner (`release_gate.py:317,782,1251,1273`); `reconstruct_state.py` (tests copy it alone); `verify_lane._git` (lane fixture clones lack `scripts/gates`); `mutation_harness._git` (its validity test forbids root from `__file__`); `measure_peak_memory._git` (a `sys.path` append changes the jnwb its control measures); `obligation_diff.py:76` (never edits `sys.path`). Left, convertible: `measure_order.py:723,725`, `vflip2_sensitivity.py:105` (function-local import), `release_gate.py:1704`, `learning_gate.py:242`, `measure_agents_md_duplication.py:35`, `gates/boundary.py:585,636`; inline `row.split("|")[n]` in 5 test files; `from scripts ...` inside test functions with no `sys.path` guard (`test_generated_files_are_byte_stable.py:179`, `test_single_agent_instruction_file.py:69`, `test_stack_edit.py:465`; the wheel leg passes them only when an earlier module appended the root). `cells` also changes `build_dashboard` on an unterminated row and a `>`-prefixed line, with no real input affected and no test. Check: one `cells()` and one `git()` each, or each remaining site named with its reason; `harness_gate.py` 22 of 22, `tests/test_table_cells.py` and `tests/test_test_imports_survive_the_wheel_leg.py` pass.

### 17-96 Dead code and unused constants

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `jnwb/visual_qc.py`, `jnwb/artifact_repair.py`, `jnwb/onset_fitting.py`, `jnwb/analyzers.py`, `jnwb/nwb_io.py`, `tests/test_no_unreferenced_symbols.py`, a deprecation test file, `artifacts/changelog.d/*.md`.
- 17-96: five unused `MADELANE_*` constants held by an allowlist (`visual_qc.py:21-25`); `__main__` self-tests no test runs (`artifact_repair.py:468`, `onset_fitting.py:327`, 115 lines); `TFRAnalyzer.LEGACY_VIZ_BANDS` read only by tests; a third band table `DEFAULT_BANDS`; `nwb_read_io(mode=)` accepts one value. Ruled 2026-11-22: the three public names are deprecated in 0.2.17, behaviour kept; removal in 0.2.18 needs a check of compatibility commitments and downstream use (roadmap 17-155). Check: the internal four removed or moved into tests, the allowlist shrinks; each public name warns `DeprecationWarning` and returns its old value or behaviour, by test; a changelog fragment announces it; the suite passes.

### 17-97 Tests named by process, split by accident

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none (ruled 2026-11-22: merge the seven; dated records stay unchanged).
Writes: `tests/test_*.py`.
- 17-97: slice 1 landed 2026-11-22 (merge 4f84cf5c): the four event-named files, `test_rng_*` and `test_api_md_*` merged by subject; 11201 collected before and after, test-name set equal. Left: seven laminar files named only by `artifacts/evidence/0.2.15/tiered_ci_plan.md` and `artifacts/evidence/0.2.14/verification_inventory.md:84` (`test_vflip2_nuisance`, `_sensitivity`, `_simulation`, `test_xflip_homogeneous_null`, `_nuisance`, `_null_method`, `test_zflip_audit`); the other nine laminar files keep their names, cited by `standing.md`, a calibration receipt, `scripts/`, `jnwb/laminar/_vflip2.py`, a fixture or `CHANGELOG.md`. Event-named classes (`TestIntegration021`, `TestFinalAuditRecurrence`) stay to keep node ids. Check: the seven merged or ruled to stay, collected count unchanged.

### 17-99 One home per invariant across rule and doc files

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: Hamm adds the spikes-and-LFP fact row (the fact stack is his; ruled 2026-11-22: the fact stack is each invariant's home, other files link); shared `README.md`.
Writes: `.github/CONTRIBUTING.md`, `docs/architecture.md`, `README.md`, `docs/index.md`, `docs/glossary.md`, `artifacts/agents.md`.
- 17-99: `CONTRIBUTING.md:368-380` and `docs/architecture.md:128-171` restate the invariants AGENTS.md §4 keeps in the fact stack; the spikes-and-LFP rule ("never pool") is in 17 tracked files (`git grep -il 'never pool'`) and no fact row; "four outcomes" in three of the Writes files; the Python matrix on four pages. Check: each fact has one home and the others link to it.

### 17-100 Docs and examples thinning

Release: deferred-0.2.17.
Role: docs-harness. Skill: none. Blocked by: none (shared `docs/references.md`, `README.md` with 17-129).
Writes: `docs/01_architecture_and_philosophy.md`, `docs/02_paths_addressing_metadata.md`, `docs/03_representational_similarity_jrsa.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/05_artifact_detection_and_repair.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md`, `docs/08_directed_connectivity_and_information.md`, `docs/09_decoding_and_visual_qc.md`, `docs/10_operation_specifications.md`, `docs/agents.md`, `docs/architecture.md`, `docs/coherence_and_tfr.md`, `docs/common_mistakes.md`, `docs/documentation_form.md`, `docs/errors.md`, `docs/execution.md`, `docs/glossary.md`, `docs/index.md`, `docs/install.md`, `docs/laminar.md`, `docs/quickstart.md`, `docs/reading_nwb.md`, `docs/recipes.md`, `docs/references.md`, `docs/repairing_nwb.md`, `docs/unit_quality_example.md`, `docs/vis.md`, `docs/writing_nwb.md`, `docs/assets/**`, `README.md`, `examples/**/*.py`, `mkdocs.yml`.
- 17-100: landed 2026-11-21 (merge 63b1874c): `docs/assets/jnwb_vis_sorted_heatmap.png`, the check log cut from `references.md`. Left, each blocked by a test outside Writes: fig14 and fig18, repeated in `common_mistakes.md` and pages 06 and 08 (`tests/test_figure_form.py:817-818`); the redirect stub `docs/01_architecture_and_philosophy.md` (`tests/test_docs_user_navigation.py:130`); the 10-line `sys.path` guard in 12 example scripts (`tests/test_import_provenance.py`); figure ids skip fig22 and fig23 (renumbering breaks AWAITING keys). Also left: "labelled" 3 times beside "labeled" 3 in docs, README and examples (the spelling needs Hamm's word); `CHANGELOG.md` path forms mixed (the integrator's file). Check: `docs_build.py` strict passes and each listed grep returns its one form.

### 17-101 Tracked rules that depend on untracked local files

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none (ruled 2026-11-22: rules point to the tracked `artifacts/agents/` roles; machine paths stay only in dated records).
Writes: `artifacts/process/cooperation.md`, `artifacts/rulings/standing.md`, `artifacts/benchmarks/calibration/cuda_parity_0.2.4.md`.
- 17-101: verifier dispatch lives only in git-ignored `.claude/agents/` (`cooperation.md:79`, `standing.md:37`); 15 tracked files cite `scratchpad` or `C:/Users/nejath` paths, e.g. `cuda_parity_0.2.4.md:67` cites `scratchpad/parity44.py`. Check: `git grep -lE 'scratchpad|C:/Users/nejath'` over tracked rules returns only records.

### 17-104 Two oversized structures

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/build_fact_graph.py`, `jnwb/__init__.py`.
- 17-104: script half landed 2026-11-21 (merge 2a1814a0): `scripts/fact_graph/` and a 442-line driver; graph differs only in head, python list and claim labels 393 to 392 (a false `set(RNG_KEYS)` site). Left: `jnwb/__init__.py` imports submodules eagerly beside `_lazy_exports` (import at 0.2.16: 11775 ms warm median, 70076 ms cold, 1381 modules, `artifacts/benchmarks/performance/import_breakdown.json`); `scripts/fact_graph/__init__.py` is committed with CRLF (the EOL guard restores it; needs Hamm's word); `reconstruct_state.growth_rows` globs `scripts/*.py` only. Check: the script splits into a module and a driver with the harness gate unchanged; the import receipt (`scripts/benchmark_import.py`) records the change.

### 17-127 The fact graph build takes four minutes

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-104 (shares `scripts/build_fact_graph.py`).
Writes: `scripts/build_fact_graph.py`, `scripts/fact_graph/*.py`, `tests/test_fact_gate.py`.
- 17-127: one `build_fact_graph.py` run took 264 s at `2e069118` and 217 s at `a5345f79` on the Windows host (one sample each; the 17-84 call-site rule landed between); under a full suite it passed the test's 300 s cap twice, now 900 s. Check: a profile names the phases; the build runs under 60 s with the graph byte-identical.

### 17-128 Docstrings and constants against the code style

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-94 (shares `jnwb/**/*.py`).
Writes: `jnwb/**/*.py`.
- 17-128: landed 2026-11-21 (merge c8bbee69): Raises sections on 24 public functions, filtering Args with units, 20 tolerance literals named in 13 modules (values equal, signatures unchanged). Left: Raises for `inspect`, `bipolar_reference`, `granger`, `assert_mergeable` (an INTERNAL name in `tests/test_skill_symbol_coverage.py`; documenting it needs a skill row), helper-raised exceptions and `FileNotFoundError` not listed; the `_vflip2` band literals and the `_vflip.py`, `_xflip.py`, `_bins.py` sites, whose code the curation, vflip and xflip calibration receipts hash (a change needs the calibrate script rerun); `harmonic_analysis` (frozen); the 96 float defaults in the signatures of the 163 functions in `jnwb.__all__` keep their text (ruled 2026-11-22: the Check covers tolerance literals and raise sites only). From P-216-25 (the names went to roadmap 17-130): 23 of those 163 functions raise in their own body without a Raises section (AST count, 2026-11-21); unnamed band constants in `_vflip2.py`; 98 uncited float defaults and 43 tolerance literals at P-216-25 (`_psd.py:217` `fundamental_freq * 0.1`). Check: each public raise site has a Raises entry, each tolerance literal is a named constant with its source, the suite passes.

### 17-142 Unused names, stale pointers and two duplicate helpers

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: the `_temp_17-95-left` lane, which edits `scripts/gates/boundary.py`.
Writes: `scripts/gates/boundary.py`.
- 17-142: landed 2026-11-22 (merge ff703205): 12 unused imports removed; 37 kept in `scripts/harness_gate.py` with `# noqa: F401` naming the test that reads each through the module; one module-level `_mean_over` in `_granger.py` (granger outputs bitwise-equal); the three stale pointers fixed. Left: `Union` undefined in an annotation (`scripts/gates/boundary.py:432`). Check: ruff F811, F821 and F841 report zero over `jnwb/` and `scripts/`, F401 reports no name outside a re-exporting `__init__.py`, each named pointer resolves, each helper has one definition; the suite passes.

### 17-129 Prose against the writing style

Release: deferred-0.2.17.
Role: docs-harness. Skill: none. Blocked by: 17-99 and 17-100 (shared files); Hamm's word for `skills/`, `AGENTS.md` and the spelling.
Writes: `.github/CONTRIBUTING.md`, `README.md`, `docs/quickstart.md`.
- 17-129: from P-216-26. The 2026-11-07 match pass adds: `docs/agents.md:79-94` repeats `skills/jnwb/SKILL.md:13-25`; `CONTRIBUTING.md:39` repeats `:36` and `:64`. Sentences over 40 words in 8 of 12 skills, `AGENTS.md` (:85, :105), `CONTRIBUTING.md` (:111, :179, :185, :379; em dashes on 17 lines); "behaviour" (113 lines) and "behavior" (105) both occur (`git grep -icw`, tracked tree). Check: no sentence over 40 words in the listed files and one spelling, by grep.
