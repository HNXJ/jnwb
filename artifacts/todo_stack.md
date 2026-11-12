# 0.2.17

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.16
closed on 2026-11-08 (tag `v0.2.16`, `0aa220ba`; tag CI/CD run 42513450995 success, TestPyPI and PyPI
verified, GitHub release body checked by `release_gate.py` STEP 0d). Items run fastest first.

Thinning and matching from the 2026-11-02 audits, each named by SHA: seven models at `7ca5b9a6` (17-83 to 17-105) and eight auditors at `9fd2b4bd` (P-216 rows, 17-128, 17-129). Lanes form at 0.2.16's close; 17-94 waits on 17-79,
which rewrites `_xflip.py` and `_zflip.py`. Each item applies the jarness standards: `match-cleanup` for
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

### 17-150 AST scan for NaN-passing sign guards

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-147 (shared `scripts/learning_gate.py`).
Writes: `scripts/learning_gate.py`, `tests/test_nan_passes_sign_guard_scan.py`.
- 17-150: state-4 of the 2026-11-08 audit: `nan-passes-sign-guard` in `artifacts/process/defect_classes.md` still proposes an AST scan for a bare `<= 0` / `< 0` guard with no finiteness test. Check: a gate or test fails when such a guard is planted, and the eight listed sites stay covered.

### 17-147 Audit 2026-11-08: scripts and tests that cannot fail

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-143 (shared `scripts/push_guard.py`).
Writes: `scripts/push_guard.py`, `scripts/learning_gate.py`, `scripts/gates/state.py`, `scripts/stack_parse.py`, `scripts/measure_agents_md_duplication.py`, `scripts/vflip2_recovery.py`, `scripts/figures/generate_figures.py`, `tests/test_*.py`.
- 17-147: left of the audit (the rest landed 2026-11-08): scripts-2 (gate 15 passes on zero tables; `tests/test_learning_gate.py:212` pins that), -5 (move), -6, -7, -8 (`measure_agents_md_duplication.py:149,158`, `vflip2_recovery.py:978`), tests-2 (`match=`), -4, -5, -6, -9; push spellings the guard still allows: `git --namespace foo push`, a quoted `git.exe` path, `GIT`/`git.EXE`, `GIT_DIR=<jnwb>` from another cwd. Check: each by a failing-first test; `ruff check tests --select F401,F541,F821,F841` clean.

### 17-149 Fast checks first: doc form in the suite, generated state named

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/jnwb_suite.sh`, `scripts/reconstruct_state.py`, `tests/test_jnwb_suite_lock.py`, `tests/test_state_reconstruction.py`.
- 17-149 (ruled 2026-11-09): the doc-form failures surfaced after a 40-minute suite three times; `jnwb_suite.sh` runs `test_changelog_fragments`, `test_docs_form_gate` and `test_documentation_form` first and stops on a failure. The jarness workspace check reads the uncommitted `state.md` as stale; `reconstruct_state.py` writes `Generated: scripts/reconstruct_state.py`. Check: a planted bad fragment fails the suite before the full run starts; `artifacts_check.py` reports no stale stamp for jnwb.

### 17-143 A tag push through the push wrapper

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/jnwb_push.sh`, `scripts/push_guard.py`, `tests/test_push_guard.py`.
- 17-143: `push_guard.py` denied the v0.2.16 tag push (2026-11-08) and `jnwb_push.sh` pushes only a branch (`:52`), so Hamm pushed it by hand. Ruled 2026-11-09: an artifacts-only push first runs gate 15 and `tests/test_stack_item_length.py`. Check: `jnwb_push.sh <dir> --tag vX.Y.Z` pushes a `v*` tag only at `origin/main`'s tip with a successful main CI/CD run of that SHA, else refuses; an artifacts-only push with a bare directory in `Writes:` is refused; guard tests cover each.

### 17-144 The jaxfne isi_cv commits

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-144-src (open stack; `E:/cl-jnwb16e` gone, SHAs not on origin).
Writes: `artifacts/benchmarks/realdata/isi_cv_recompute.py`, `artifacts/benchmarks/realdata/isi_cv_recompute_receipt.json`, `artifacts/benchmarks/realdata/build_isi_cv_fixture.py`, `tests/fixtures/isi_cv_realdata_subsample.json`, `tests/test_isi_cv_realdata.py`.
- 17-144: three 16-12 commits were named on `E:/cl-jnwb16e` (0e06993c, 9980f58d, 5fa63dd3), promised to
  jaxfne-orchestrator for 0.2.17. Observed 2026-11-12: that path is missing and the three SHAs are not in
  this clone or on `origin`. Check: each is on `dev` (picked in that order, one per command), the suite
  passes, and jaxfne-orchestrator is told the SHAs; then `E:/cl-jnwb16e` may go.

### 17-79 Complexity of the largest functions

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: nothing (moved from 0.2.16 by the lane ruling of 2026-11-02).
Writes: `jnwb/laminar/_xflip.py`, `jnwb/laminar/_zflip.py`, `jnwb/laminar/_vflip.py`, `jnwb/jrsa/__init__.py`, `jnwb/connectivity/_psi.py`.
- 17-79: at 93fd20e1, 977 functions, median cyclomatic complexity 4; 151 above 10, 56 above 20, 13 above 40; the largest are `xflip` 109, `jrsa` 93, `zflip` 80, `vflip` 71, `phase_slope_index` 67. None has a `frozen_validated.json` entry, so gate 19 does not hold them; the suite and calibration receipts do. This is size only. Check: each named function split into helpers with the suite and its calibration receipt unchanged, and none above 40.

### 17-94 One home per helper in jnwb

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-79 (shared files).
Writes: `jnwb/**/*.py`.
- 17-94: `fs=nan` passes the `fs <= 0` guard at `filtering.py:31`, `:76`, `continuous.py:136` and `tfr.py:251`; at 2a5ef1b7 `bandpass_filter` then raises scipy's "Wn[0] must be less than Wn[1]" and `notch_filter` a `LinAlgError`, neither naming `fs` (match pass 2026-11-07). The shared check refuses NaN and Inf by name. The `fs` positive check is hand-written at about 20 sites (`filtering.py:31`, `continuous.py:136`, `tfr.py:251`, ...) beside `spectral/_common._require_positive_fs`; `jnwb/spectral` has 9 `_require_*` variants; `_bins.py:86,112` hold two onset loops differing in edge closure; three dB paths (`_decibels.py:15,24,457`); `nwb_write._sha256` equals `paths.sha256_file`; `_window_rows` twice (`_xflip.py:96`, `_zflip.py:178`). Check: one definition each, the grep returns one site, the suite passes.

### 17-95 One home per helper in scripts and tests

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-149 (shared `scripts/reconstruct_state.py`, tests).
Writes: `scripts/stack_parse.py`, `scripts/release_gate.py`, `scripts/build_fact_graph.py`, `scripts/learning_gate.py`, `scripts/build_dashboard.py`, `scripts/docs_form_gate.py`, `scripts/reconstruct_state.py`, `scripts/measure_peak_memory.py`, `scripts/mutation_harness.py`, `scripts/verify_lane.py`, `scripts/gates/boundary.py`, `tests/conftest.py`, `tests/test_*.py`.
- 17-95: the markdown table cell splitter is written 8 times in `scripts/` and only `build_dashboard.py:342` honours escaped pipes; 13 `_git` wrappers across tests and scripts. Check: one `cells()` and one `git()` each, `harness_gate.py` 22 of 22 and the named tests pass.

### 17-96 Dead code and unused constants

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: public names (`LEGACY_VIZ_BANDS`, `DEFAULT_BANDS`, `nwb_read_io(mode=)`) need Hamm's word.
Writes: `jnwb/visual_qc.py`, `jnwb/artifact_repair.py`, `jnwb/onset_fitting.py`, `jnwb/analyzers.py`, `jnwb/nwb_io.py`, `tests/test_no_unreferenced_symbols.py`.
- 17-96: five unused `MADELANE_*` constants held by an allowlist (`visual_qc.py:21-25`); `__main__` self-tests no test runs (`artifact_repair.py:466`, `onset_fitting.py:324`, about 115 lines); `TFRAnalyzer.LEGACY_VIZ_BANDS` read only by tests; a third band table `DEFAULT_BANDS`; `nwb_read_io(mode=)` accepts one value. Check: removed or moved into tests, the allowlist shrinks, the suite passes.

### 17-97 Tests named by process, split by accident

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `tests/test_*.py`.
- 17-97: `test_batch_a_regressions.py`, `test_independent_audit_semantics.py`, `test_integration_0_2_1.py`, `test_audit_reproducers.py` are named by event; 29 same-subject files (`test_rng_*` 4, `test_vflip2*` 6, `test_xflip*` 7, `test_zflip*` 3, `test_api_md_*` 3, ...) split 3 to 7 ways. Check: merged by subject with the collected test count unchanged.

### 17-98 Process vocabulary in tests, scripts and jnwb comments

Release: deferred-0.2.17.
Role: docs-harness. Skill: none. Blocked by: 17-149 (shared scripts and tests).
Writes: `tests/*.py`, `scripts/**/*.py`, `jnwb/__init__.py`, `jnwb/_backend.py`, `jnwb/_declarations.py`.
- 17-98: 130 hits of "ruled", "ruling" or "Hamm" in 36 files under `tests/` and `scripts/` (AGENTS.md top paragraph); "harness" in `jnwb/__init__.py:20` and `_backend.py:31`; "the fact stack's" in `_declarations.py:36`; five "Important" labels in `jnwb/`. Check: the grep, minus machine literals and the tests that read the stacks, returns 0.

### 17-99 One home per invariant across rule and doc files

Release: deferred-0.2.17.
Role: human. Skill: none. Blocked by: `AGENTS.md`, `CONTRIBUTING.md` and the fact stack need Hamm's word (shared `README.md`).
Writes: `.github/CONTRIBUTING.md`, `docs/architecture.md`, `README.md`, `docs/index.md`, `docs/glossary.md`, `artifacts/agents.md`.
- 17-99: `CONTRIBUTING.md:359-370` and `docs/architecture.md:128-171` restate the invariants AGENTS.md §4 keeps in the fact stack; the spikes-and-LFP rule is in five files and no fact row; "four outcomes" in three; "toolbox, not a pipeline" on four surfaces; the Python matrix on three pages. Check: each fact has one home and the others link to it.

### 17-100 Docs and examples thinning

Release: deferred-0.2.17.
Role: docs-harness. Skill: none. Blocked by: none (shared `docs/references.md`, `README.md` with 17-129).
Writes: `docs/01_architecture_and_philosophy.md`, `docs/02_paths_addressing_metadata.md`, `docs/03_representational_similarity_jrsa.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/05_artifact_detection_and_repair.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md`, `docs/08_directed_connectivity_and_information.md`, `docs/09_decoding_and_visual_qc.md`, `docs/10_operation_specifications.md`, `docs/agents.md`, `docs/architecture.md`, `docs/coherence_and_tfr.md`, `docs/common_mistakes.md`, `docs/documentation_form.md`, `docs/errors.md`, `docs/execution.md`, `docs/glossary.md`, `docs/index.md`, `docs/install.md`, `docs/laminar.md`, `docs/quickstart.md`, `docs/reading_nwb.md`, `docs/recipes.md`, `docs/references.md`, `docs/repairing_nwb.md`, `docs/unit_quality_example.md`, `docs/vis.md`, `docs/writing_nwb.md`, `docs/assets/**`, `README.md`, `examples/**/*.py`, `mkdocs.yml`.
- 17-100: figures fig14 and fig18 repeated in `common_mistakes.md` and pages 06 and 08; the README quickstart repeats `docs/quickstart.md:38-60`; the redirect stub `docs/01_architecture_and_philosophy.md`; `docs/vis.md:51` alone under `assets/vis/`; the 10-line `sys.path` guard in 11 example scripts; the check log in `references.md:5-11`; "labelled" 37 times beside "labeled" 12; `CHANGELOG.md` path forms mixed (the integrator's file); figure ids skip fig22 and fig23. Check: `docs_build.py` strict passes and each listed grep returns its one form.

### 17-101 Tracked rules that depend on untracked local files

Release: deferred-0.2.17.
Role: human. Skill: none. Blocked by: Hamm decides: track or drop.
Writes: `artifacts/process/cooperation.md`, `artifacts/rulings/standing.md`, `artifacts/benchmarks/calibration/cuda_parity_0.2.4.md`.
- 17-101: verifier dispatch lives only in git-ignored `.claude/agents/` (`cooperation.md:79`, `standing.md:37`); 14 tracked files cite `scratchpad` or `C:/Users/nejath` paths, e.g. `cuda_parity_0.2.4.md:67` cites `scratchpad/parity44.py`. Check: `git grep -lE 'scratchpad|C:/Users/nejath'` over tracked rules returns only records.

### 17-102 Showcase and calibration files nothing names

Release: deferred-0.2.17.
Role: human. Skill: none. Blocked by: Hamm rules which are receipts of record.
Writes: `artifacts/showcases/openscope_glo/**`, `artifacts/benchmarks/calibration/curation_calibration_0.2.13_raw.json`.
- 17-102: 14 of 24 `openscope_glo/scripts/` files and 8 of its 23 `receipts/` (823 KB) are named by no tracked file (`aggregate_s2` is cited by `results/s2v2/receipt.json`); `curation_calibration_0.2.13_raw.json` (49,820 lines) is named by nothing. Check: each kept file is named by a receipt or `openscope_glo.json`, the rest removed.

### 17-103 CONTRIBUTING pointers out of date

Release: deferred-0.2.17.
Role: docs-harness. Skill: none. Blocked by: nothing; a change of meaning needs Hamm's word.
Writes: `.github/CONTRIBUTING.md`.
- 17-103: `CONTRIBUTING.md:343` names `harness_gate.py` as the root allowlist's home (it is `scripts/gates/boundary.py:335-336`); `:350-356` lists three `artifacts/` entries of nine folders; `:117` states the peak-memory margin (25%) but not `release_gate.py`'s 20% growth limit. Check: each pointer resolves to the defining symbol.

### 17-104 Two oversized structures

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/build_fact_graph.py`, `jnwb/__init__.py`.
- 17-104: `scripts/build_fact_graph.py` is one 3,410-line file of parsing, unit factors and graph; `jnwb/__init__.py` imports submodules eagerly beside `_lazy_exports` (inferred: measure import time first). Check: the script splits into a module and a driver with the harness gate unchanged; the import receipt (`scripts/benchmark_import.py`) records the change.

### 17-127 The fact graph build takes four minutes

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-104 (shares `scripts/build_fact_graph.py`).
Writes: `scripts/build_fact_graph.py`, `tests/test_fact_gate.py`.
- 17-127: one `build_fact_graph.py` run took 264 s at `2e069118` and 217 s at `a5345f79` on the Windows host (one sample each; the 17-84 call-site rule landed between); under a full suite it passed the test's 300 s cap twice, now 900 s. Check: a profile names the phases; the build runs under 60 s with the graph byte-identical.

### 17-128 Docstrings and constants against the code style

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-94 (shares `jnwb/**/*.py`).
Writes: `jnwb/**/*.py`.
- 17-128: from P-216-25 (the names went to roadmap 17-130). 17 public functions raise without a Raises section; filtering docstrings lack units and Args (`filtering.py`); unnamed band constants in `_vflip2.py`; 98 uncited float defaults and 43 tolerance literals (`_psd.py:216` `fundamental_freq * 0.1`). Check: each public raise site has a Raises entry, each float default and tolerance is a named constant with its source, the suite passes.

### 17-142 Unused names, stale pointers and two duplicate helpers

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-94 and 17-95 (shared files).
Writes: `jnwb/jrsa/__init__.py`, `jnwb/statistics/_regression.py`, `jnwb/statistics/__init__.py`, `jnwb/connectivity/_granger.py`, `jnwb/jrsa/_backends.py`, `scripts/gates/boundary.py`, `scripts/gates/vocabulary.py`, `scripts/mutation_harness.py`, `scripts/learning_gate.py`.
- 17-142: match pass 2026-11-07 at 2a5ef1b7, each confirmed by `ruff check --select F401,F811,F821,F841`: `p_parametric` assigned and never read (`jrsa/__init__.py:667`); `resolve_rng` (`statistics/_regression.py:8`) and `MIN_COHERENCE_NPERSEG` (`connectivity/_granger.py:16`) imported and unused; `RNGLike` imported twice (`statistics/__init__.py:33`); `Union` undefined in an annotation (`scripts/gates/boundary.py:421`). Comments name functions that no longer exist: `_autodetect_backend` (`jrsa/_backends.py:40`), `_read_journal` (`scripts/mutation_harness.py:592`); `scripts/gates/vocabulary.py:80` cites "batch jobs" at `docs/02:11`, which now sits in `docs/reading_nwb.md:33`. `_mean_over` is defined twice in `_granger.py` (:1082, :1325); `_cells` in `scripts/learning_gate.py:52` equals `scripts/build_fact_graph.py:224`. Re-exports in `__init__` files are out of scope. Check: ruff F811, F821 and F841 report zero over `jnwb/` and `scripts/`, F401 reports no name outside a re-exporting `__init__.py`, each named pointer resolves, each helper has one definition; the suite passes.

### 17-129 Prose against the writing style

Release: deferred-0.2.17.
Role: docs-harness. Skill: none. Blocked by: 17-99 and 17-100 (shared files); Hamm's word for `skills/`, `AGENTS.md` and the spelling.
Writes: `.github/CONTRIBUTING.md`, `README.md`, `docs/quickstart.md`.
- 17-129: from P-216-26. The 2026-11-07 match pass adds: `docs/agents.md:79-94` repeats `skills/jnwb/SKILL.md:13-25`; `CONTRIBUTING.md:39` repeats `:36` and `:64`. Sentences over 40 words in 12 skills, `AGENTS.md` (:5, :51, :85, :93, :105), `CONTRIBUTING.md` (:72-88, :107-127, :417-428; em dashes on 15 lines), README and quickstart; "behaviour" and "behavior" both occur. Check: no sentence over 40 words in the listed files and one spelling, by grep.
