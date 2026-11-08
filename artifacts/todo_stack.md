# 0.2.16

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.15
closed on 2026-11-02 (tag `v0.2.15`, `5822c3e9`; PyPI, GitHub release, omission told,
`artifacts/rulings/2026-11-01.md`). Items run fastest first; the lanes below split them into parallel
writers that share no file.

## 0.2.16 checklist and score

Scope: the 0.2.16 row of `artifacts/process/release_plan.json` (ruled 2026-11-05). Weights sum to 100: packages
70, exit gates 30. A row earns its weight only when its "Done when" check holds; partial credit is the share of
its named checks that hold. A package moved out of the cycle by ruling earns its weight, as a moved open row does in 16G. Score 2026-11-06: **80/100** (packages 70 of 70, gates 10 of 30; 72.3 before 17-77 closed, 71.5 before 17-75 closed, 56.5 before 16E moved, 44.4 before the open rows moved, 43.4 before P-216-06 closed, 34.9 before 17-70 and 17-76, 33.3 before #39 closed).

| Id | Weight | Package | Done when | Evidence 2026-11-05 | Score |
|---|---|---|---|---|---|
| 16A Audit defects | 15 | 17-83 to 17-127 of the 0.2.16 lanes | every 0.2.16 lane item landed with its failing-first test | all batches landed (2026-11-02 to -03); no 0.2.16 lane item left in this stack | 15 |
| 16B GitHub issues | 8 | hnxj/jnwb#35 to #39 | each closed on GitHub with its repro | #35 to #39 closed; #39 by a9fccc01, CI/CD green on bb068aec; #40 closed 2026-11-06 (item 4, 674aa0d8); 0 issues and 0 pull requests open | 8 |
| 16C GPU Granger | 7 | `granger(device=)`, `granger_causality` removed | parity test within its stated tolerance; CI green on `dev` | c594ae51, CI/CD run 41920337297 success | 7 |
| 16D psth bin edges | 6 | 17-70 | `UnitAnalyzer.psth` right-open, with a `[results change]` entry | landed 2026-11-06 with failing-first tests and the entry; independent review ACCEPT, the old code fails 4 tests | 6 |
| 16E External ground truth | 15 | 15-11, 12-21, 16-12 | each recovery table or receipt committed | moved to 0.2.17 (ruling of 2026-11-06, "Defer 16E, release"); handed to jaxfne-orchestrator to plan, a Haiku 5.5 subagent executes once the plan is agreed | 15 |
| 16F Workspace and pointers | 5 | 17-75, 17-76, 17-77 | each item's check holds | 17-75 done 2026-11-06 (worktree removed, its commit archived as a patch on `E:`; `git worktree list` shows one entry; 36 stale clones and `_temp_oc` deleted); 17-76 done (agy answered, ruling of 2026-10-28); 17-77 done 2026-11-06 (ebbd8ecb; S13's `todo:12-21` stays, the fact gate reads roadmap ids as live) | 5 |
| 16G Open rows | 14 | the open stack's 0.2.16 rows | each repaired, shown false or moved with its release | P-216-05 repaired; P-216-06 repaired (#40 item 4, ruling of 2026-11-06); the other 13 moved 2026-11-06 by the release plan to 17-128, 17-129 and roadmap 17-130 to 17-141; the open stack is empty | 14 |
| Gate 1 packages closed or moved | 6 | — | 16A to 16G closed, or moved by ruling | 7 of 7 closed or moved | 6 |
| Gate 2 gates, suite, CI | 8 | — | harness gates and full suite pass at the release SHA; CI green on `dev` there | no release SHA yet; at 3fb5f94b all three held | 4 |
| Gate 3 release gate | 6 | — | `python scripts/release_gate.py` passes | not run | 0 |
| Gate 4 closure pass | 5 | — | an independent blocker-focused pass finds no new blocker (`AGENTS.md` §11) | not run | 0 |
| Gate 5 tag, main, PyPI | 5 | — | v0.2.16 on PyPI from the tagged SHA | not started | 0 |

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

## Lanes

Sources: the seven-model audit of `7ca5b9a6` (17-83 to 17-105) and the eight-auditor audit of
`9fd2b4bd` (17-106 to 17-117; open rows P-216-08 to -32), each finding re-checked by the integrator.
Defects and correctness go in 0.2.16; thinning and matching in 0.2.17. Lanes ruled 2026-11-02 (Hamm,
"Yes, as proposed"): claimed by the files in their items' Writes; no file is in two lanes of one batch,
and an item that shares a file with another lane names it in Blocked by.

No lane is open. Batches: A, B, C (2026-11-02); D, E, G, then C, H, F, then A, D, B, then I, E, K
(2026-11-03), all landed.

- No item blocks the 0.2.16 tag; the release steps remain (Gates 2 to 5). The open stack is empty: its 13 rows moved on 2026-11-06 to
  17-128 and 17-129 here and to roadmap 17-130 to 17-141, by the release plan.
- Off the path, blocking nothing: Hamm reads `artifacts/evidence/0.2.15/tiered_ci_plan.md` (plan only);
  approved, a 0.2.16 item changes `workflow.yml`.

# 0.2.17

Thinning and matching from the 2026-11-02 audit. Lanes form at 0.2.16's close; 17-94 waits on 17-79,
which rewrites `_xflip.py` and `_zflip.py`. Each item applies the jarness standards: `match-cleanup` for
removals, `match-code-style` for code, `match-writing-style` for prose, `match-visual-style` for figures.

### 17-79 Complexity of the largest functions

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: nothing (moved from 0.2.16 by the lane ruling of 2026-11-02).
Writes: `jnwb/laminar/_xflip.py`, `jnwb/laminar/_zflip.py`, `jnwb/laminar/_vflip.py`, `jnwb/jrsa/__init__.py`, `jnwb/connectivity/_psi.py`.
- 17-79: at 93fd20e1, 977 functions, median cyclomatic complexity 4; 151 above 10, 56 above 20, 13 above 40; the largest are `xflip` 109, `jrsa` 93, `zflip` 80, `vflip` 71, `phase_slope_index` 67. None has a `frozen_validated.json` entry, so gate 19 does not hold them; the suite and calibration receipts do. This is size only. Check: each named function split into helpers with the suite and its calibration receipt unchanged, and none above 40.

### 17-94 One home per helper in jnwb

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-79.
Writes: `jnwb/**/*.py`.
- 17-94: `fs=nan` passes the `fs <= 0` guard at `filtering.py:31`, `:76`, `continuous.py:136` and `tfr.py:251`; at 2a5ef1b7 `bandpass_filter` then raises scipy's "Wn[0] must be less than Wn[1]" and `notch_filter` a `LinAlgError`, neither naming `fs` (match pass 2026-11-07). The shared check refuses NaN and Inf by name. The `fs` positive check is hand-written at about 20 sites (`filtering.py:31`, `continuous.py:136`, `tfr.py:251`, ...) beside `spectral/_common._require_positive_fs`; `jnwb/spectral` has 9 `_require_*` variants; `_bins.py:86,112` hold two onset loops differing in edge closure; three dB paths (`_decibels.py:15,24,457`); `nwb_write._sha256` equals `paths.sha256_file`; `_window_rows` twice (`_xflip.py:96`, `_zflip.py:178`). Check: one definition each, the grep returns one site, the suite passes.

### 17-95 One home per helper in scripts and tests

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
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
Role: docs-harness. Skill: none. Blocked by: nothing.
Writes: `tests/*.py`, `scripts/**/*.py`, `jnwb/__init__.py`, `jnwb/_backend.py`, `jnwb/_declarations.py`.
- 17-98: 130 hits of "ruled", "ruling" or "Hamm" in 36 files under `tests/` and `scripts/` (AGENTS.md top paragraph); "harness" in `jnwb/__init__.py:20` and `_backend.py:31`; "the fact stack's" in `_declarations.py:36`; five "Important" labels in `jnwb/`. Check: the grep, minus machine literals and the tests that read the stacks, returns 0.

### 17-99 One home per invariant across rule and doc files

Release: deferred-0.2.17.
Role: human. Skill: none. Blocked by: `AGENTS.md`, `CONTRIBUTING.md` and the fact stack need Hamm's word.
Writes: `.github/CONTRIBUTING.md`, `docs/architecture.md`, `README.md`, `docs/index.md`, `docs/glossary.md`, `artifacts/agents.md`.
- 17-99: `CONTRIBUTING.md:359-370` and `docs/architecture.md:128-171` restate the invariants AGENTS.md §4 keeps in the fact stack; the spikes-and-LFP rule is in five files and no fact row; "four outcomes" in three; "toolbox, not a pipeline" on four surfaces; the Python matrix on three pages. Check: each fact has one home and the others link to it.

### 17-100 Docs and examples thinning

Release: deferred-0.2.17.
Role: docs-harness. Skill: none. Blocked by: nothing.
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
