# 0.2.16

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.15
closed on 2026-11-02 (tag `v0.2.15`, `5822c3e9`; PyPI, GitHub release, omission told,
`artifacts/rulings/2026-11-01.md`). Items run fastest first; the lanes below split them into parallel
writers that share no file.

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

| Lane | Items, in order | Files |
|---|---|---|
| A | 17-84, 17-93 | `jnwb/analyzers.py`, `scripts/build_fact_graph.py` and the files of 17-93 |
| C | 17-108, 17-110, 17-111 | `jnwb/nwb_events.py`, `jnwb/nwb_inspect.py`, `jnwb/spiking.py`, `jnwb/statistics/_*.py` |
| E | 17-78 | `docs/*.md`, `scripts/docs_form_gate.py` |
| F | 17-92 | `artifacts/evidence/` |
| H | 17-112, 17-113 | `jnwb/nwb_validate.py`, `jnwb/metadata.py` |
| B | 17-118 | `jnwb/connectivity/_granger.py` |
| D | 17-119, 17-120 | `scripts/gates/` |

- Batches: A, B, C (run 2026-11-02); D, E, G (run 2026-11-03, D closed); rulings of 2026-11-03 cleared
  the remainders, and the integrator closed 17-80, 17-91 and 17-116; then C, H, F; then A, D, B; then
  E. The integrator does 17-76.
- Waiting on Hamm: 17-75, 17-77; open rows P-216-01, -05 to -08, -15, -17 to -20, -22, -24, -32. Open
  rows with no item yet: P-216-16, -21, -25, -26, -35 to -37, -40.
- Off the path, blocking nothing: Hamm reads `artifacts/evidence/0.2.15/tiered_ci_plan.md` (plan only);
  approved, a 0.2.16 item changes `workflow.yml`.

### 17-75 Workspace cleanup

Release: deferred-0.2.16.
Role: human. Skill: none. Blocked by: the agent may not delete these (classifier and push guard).
Writes: `artifacts/open_stack.md`.
- 17-75: from P-215-05 and P-215-15. Hamm deletes the origin branches `proposal/spike-qc-pt-skill` and `skill/spectrolaminar-work-bastos` (kept as `_temp_spike-qc-pt-skill`, `_temp_spectrolaminar-work-bastos`), the folder `.claude/worktrees/site-overview-326890` then `git worktree prune`, `C:/workspace/_temp_lane_*` (8 clones, each clean and contained in dev, checked 2026-10-31), `C:/workspace/_temp_oc` and the scratchpad `lanes/`. Check: `git ls-remote origin` lists neither old name and `git worktree list` shows one entry.

### 17-76 agy retry

Release: deferred-0.2.16.
Role: actor. Skill: none. Blocked by: nothing.
Writes: `artifacts/rulings/2026-10-28.md`.
- 17-76: from P-215-06. The 2026-10-28 work-routing ruling waits on a packet that needs no file reads; agy returned empty before. Check: one no-read packet run through `delegate-cli --backend agy` returns a non-empty answer, recorded under the routing ruling.

### 17-77 Stale pointers in the fact stack and standing rulings

Release: deferred-0.2.16.
Role: human. Skill: none. Blocked by: Hamm's word (the fact stack and the rulings are his).
Writes: `artifacts/fact_stack.md`, `artifacts/rulings/standing.md`.
- 17-77: from P-215-20. `standing.md:144-148` and `fact_stack.md:68,82,86` cite roadmap 17-03 to 17-08 and 17-24, which are done or in this stack; `standing.md:144` says psth keeps `(-1000, 2000)` until 0.2.15, while psth now requires `window_ms`; S13 holds `todo:12-21`, which is a roadmap row; and (audit 2026-11-02) about 20 of 40 sampled B3 Evidence `file:line` cells in `fact_stack.md:138-203` no longer land on their parameter (`_network.py:87`, `viz.py:115` are blank lines), so cells name `module.function(param)`. Check: every roadmap or todo id the two files cite resolves in `roadmap.md` or `todo_stack.md`, or is marked done with its commit.

### 17-78 Doc form across pages

Release: deferred-0.2.16.
Role: docs-harness. Skill: none. Blocked by: 17-93 (shares `docs/*.md`); forms ruled 2026-11-03.
Writes: `docs/01_architecture_and_philosophy.md`, `docs/02_paths_addressing_metadata.md`, `docs/03_representational_similarity_jrsa.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/05_artifact_detection_and_repair.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md`, `docs/08_directed_connectivity_and_information.md`, `docs/09_decoding_and_visual_qc.md`, `docs/10_operation_specifications.md`, `docs/agents.md`, `docs/architecture.md`, `docs/coherence_and_tfr.md`, `docs/common_mistakes.md`, `docs/documentation_form.md`, `docs/errors.md`, `docs/execution.md`, `docs/glossary.md`, `docs/index.md`, `docs/install.md`, `docs/laminar.md`, `docs/quickstart.md`, `docs/reading_nwb.md`, `docs/recipes.md`, `docs/references.md`, `docs/repairing_nwb.md`, `docs/unit_quality_example.md`, `docs/vis.md`, `docs/writing_nwb.md`, `scripts/docs_form_gate.py`, `tests/test_docs_form_gate.py`.
- 17-78: the heading, H2-operation and repeated-row forms landed as F10 to F12. Left: `## References` (03, 07, 08, `coherence_and_tfr` carry it; 06, `reading_nwb`, `common_mistakes`, `laminar` cite without it; 04 carries it with no citation); the micrometre form in prose (`um` 6 times in 02 and `laminar`, `$\mu$m` once in 10). Check: F13, a page that cites a source ends with `## References` and a page that cites none has none; F14, prose writes `micrometers`, identifiers in code spans unchanged; a planted page fails each; the gate passes.

### 17-84 The rng scan does not follow calls into a drawing callee

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing; `compare_criteria(units1, units2, metric='firing_rate', *, rng: RNGLike = DEFAULT_SEED)` passed to `exploratory_compare`, ruled 2026-11-03; the psth half landed in batch 1.
Writes: `scripts/build_fact_graph.py`, `tests/test_rng_parameters_by_use.py`, `jnwb/analyzers.py`.
- 17-84: `rng_scan` credits a caller with its callee's rng key, so `psth` before batch 1 (no `rng` passed to `bootstrap_ci`) was no finding. A call-site rule (flag a call to a drawing jnwb function that passes no `rng`, `seed`, `random_state` or `random_seed`) flagged on the live package: `compare_criteria` -> `exploratory_compare` (true), `granger_spectral` and `granger_time_reversed` -> `granger` with `n_surrogates=0` (no draw), `_net_surrogate_p` (generator named `surrogate_rng`). Check: the rule reads generator parameters by suffix or annotation and skips calls whose count argument is a literal 0; a planted caller without rng is flagged, the two false cases are not.

### 17-92 Closed evidence that nothing cites

Release: deferred-0.2.16.
Role: actor. Skill: none. Blocked by: nothing.
Writes: `artifacts/evidence/0.2.13/*`, `artifacts/evidence/0.2.14/*`, `artifacts/evidence/0.2.15/suite_profile.md`, `artifacts/process/plans_0.2.15.md`, `.gitignore`.
- 17-92: AGENTS.md §0, as commit `91b04aec` did for 58 files. `git grep -lF <basename>` finds no citer for `evidence/0.2.13/compress_scaling_probe.py`, `compress_scaling.json` (`.gitignore` only), `p335_laminar_curation_review.md`; `evidence/0.2.14/jaxfne_docs_dashboard_comparison.md`, `process_tests/plants.py`, `process_tests/prune_record.md` (266 lines); `evidence/0.2.15/suite_profile.md` (309 lines); `process/plans_0.2.15.md`. No gate globs `artifacts/evidence/`. Check: each removed with its `.gitignore` lines, the same grep is empty, harness 22 of 22.

### 17-93 Deprecated surfaces past their removal date

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: 17-84 (shares `jnwb/analyzers.py`); ruled 2026-11-02, `granger_causality` stays (P-216-07).
Writes: `jnwb/analyzers.py`, `jnwb/_dictlike.py`, `jnwb/spectral/__init__.py`, `jnwb/connectivity/__init__.py`, `jnwb/connectivity/_information.py`, `jnwb/statistics/_analysis.py`, `jnwb/_declarations.py`, `artifacts/process/frozen_validated.json`, `skills/jnwb-statistics/SKILL.md`, `skills/jnwb-connectivity/SKILL.md`, `docs/architecture.md`, `docs/references.md`, `tests/test_analyzers_coverage.py`, `tests/test_connectivity.py`, `tests/test_deprecated_aliases.py`, `tests/test_dict_access_shim.py`, `tests/test_nonfinite_inputs.py`, `tests/test_public_api_reachability.py`, `tests/test_skills_validation.py`, `tests/test_statistics.py`, `tests/test_substitution_class_sweep.py`, `tests/test_unit_suffixed_parameters.py`.
- 17-93: `analyzers.py:211` says the renamed `n_significant` keys "are removed in the next release" (added 2026-09-26, 8 releases ago); `RenamedKeyDict` (`_dictlike.py`; used by `analyzers.py:232`, re-imported by `spectral/__init__.py:18`) stays for them; `granger_causality`, `clopper_pearson_ci` and both MI aliases are deprecated and still extended. Check: the keys, `RenamedKeyDict`, `clopper_pearson_ci` and the two MI aliases are removed with one Breaking entry; `docs/api.md` and the skill rows lose them; `granger_causality` is unchanged.

### 17-108 cross_modal_comparison at n_permutations=0

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing; 0 stays the run that draws no null, ruled 2026-11-03; the rest of 17-108 landed in batch 1.
Writes: `jnwb/statistics/_regression.py`, `tests/test_statistics_refusals.py`, `tests/test_cross_modal_comparison_faces_agree.py`.
- 17-108: from P-216-28. `cross_modal_comparison` gives `lag_corrected_pvalue` 1.0 at `n_permutations=0` (`_regression.py:333-339`), a null result no draw made; `test_cross_modal_comparison_faces_agree.py:177-179` pins 0 as the undrawn mode (`surrogate_scheme` None). Check: at `n_permutations=0`, `lag_corrected_pvalue` is NaN and `surrogate_scheme` None, and the pinned test asserts both.

### 17-110 A missing response z classified 'none'

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: nothing; `'undefined'` with a `UserWarning`, ruled 2026-11-03; the `lfp_timestamps` half landed in batch 1.
Writes: `jnwb/spiking.py`, `tests/test_spiking_inputs.py`.
- 17-110: from P-216-31. `classify_response_significance` reads a `metrics` dict with no `response_zscore` as z = 0 (`spiking.py:299`, `metrics.get('response_zscore', 0.0)`) and classifies `'none'`, while a missing count key classifies `'undefined'` with a `UserWarning` (`:285-297`). Check: the missing z classifies `'undefined'` with a `UserWarning`, and a test separates it from z = 0.

### 17-111 TimeIntervals in a processing module

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: nothing; ruled 2026-11-03: an `interval_tables` entry for a processing table has the bare `name` plus a `module` key, as `processing_continuous` entries carry.
Writes: `jnwb/nwb_events.py`, `jnwb/nwb_inspect.py`, `tests/test_nwb_events.py`, `tests/test_nwb_inspect.py`.
- 17-111: from P-216-03 (hnxj/jnwb#37). `inspect(...)["interval_tables"]` is `[]` for a `TimeIntervals` under `processing/behavior`, and `events(table="processing/behavior/events")` raises `IntervalTableNotFoundError` (reproduced at `26b3e98e`; four tests written and failing, held until the ruling). Siblings: `mcp_server/event_tools.py:91-97` reads `nwb.intervals` only. Check: the issue's repro lists the table in `inspect` with `name` `events` and `module` `behavior`, `events(table="processing/behavior/events")` reads it, and `table="events"` still reads `intervals/events` when both exist.

### 17-112 validate_nwb reports the wrong version and hides read warnings

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: nothing.
Writes: `jnwb/nwb_validate.py`, `tests/test_nwb_validate.py`.
- 17-112: from P-216-02 (hnxj/jnwb#36). `nwb_validate.py:273` reads `metadata.version` (the installed distribution, not `jnwb.__version__`); the repro prints one read warning with layer counts 0. Check: the report carries `jnwb.__version__` from a source checkout, and the read layer counts its warnings.

### 17-113 electrode_inventory prints container reprs

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: nothing.
Writes: `jnwb/metadata.py`, `tests/test_metadata.py`.
- 17-113: from P-216-04 (hnxj/jnwb#38). The `group` column holds `probeA pynwb.ecephys.ElectrodeGroup at 0x...`. Check: the issue's repro gives `probeA`, and no cell of the inventory contains ` at 0x`.

### 17-118 granger_time_reversed takes no signal class

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing; keyword ruled 2026-11-03.
Writes: `jnwb/connectivity/_granger.py`, `tests/test_signal_class.py`; the integrator updates the `skills/jnwb-connectivity` row.
- 17-118: from P-216-34. `granger_time_reversed` calls `granger` twice with no class, so an omitted class warns twice naming `granger`. Check: keyword-only `signal_class` reaches both calls; omitted, exactly one `FutureWarning` names `granger_time_reversed`; a mixed pair raises `ValueError`.

### 17-119 A Writes glob that covers an integration path

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing; a glob counts, ruled 2026-11-03.
Writes: `scripts/gates/stacks_closure.py`, `tests/test_generation_closure_is_declared.py`, `artifacts/todo_stack.md` (the Writes of 17-78 and 17-100 only).
- 17-119: from P-216-39. `integration_path_writes` matches `docs/api.md` and `CHANGELOG.md` literally, so `docs/*.md` in a Writes passes. Check: a planted Writes `docs/*.md` fails gate 15, and 17-78 and 17-100 exclude `docs/api.md` so the gate passes.

### 17-120 Gate 21 passes with nothing declared

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: nothing; zero examined fails, ruled 2026-11-03.
Writes: `scripts/gates/boundary.py`, `scripts/harness_gate.py`, `tests/test_harness_adversarial_gates.py`, docstrings of the jnwb functions that average power before dB.
- 17-120: from P-216-41. Gate 21 reads "examined: 0 declared raw-power estimands" and passes. Check: zero declarations fails gate 21; each function that averages power before `aggregate_to_db` declares `estimand: raw_power` in its docstring; the gate examines them and passes.

### 17-121 unit_census_report on a file with no units table

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: nothing; the integrity checks' `KeyError` waits on Hamm (P-216-05).
Writes: `jnwb/metadata.py`, `tests/test_metadata.py`.
- 17-121: from P-216-05 (hnxj/jnwb#39). `unit_census_report` on a file with no `/units` raises `ValueError: Cannot describe a DataFrame without columns` inside pandas. Check: it returns its usual report shape with zero units and empty tables; a test writes a file with no units and reads that report.

### 17-122 The signal-class sentinel does not pickle

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing.
Writes: `jnwb/_units.py`, `jnwb/connectivity/_network.py`, `tests/test_signal_class.py`.
- 17-122: from P-216-36. `_units._OMITTED` does not pickle, so `directed_network` forwards `signal_class` to workers only when the caller gave one. Check: the sentinel round-trips through `pickle` as the same object; `directed_network(..., n_jobs=2)` with the class omitted warns as `n_jobs=1` does and returns identical numbers.

### 17-123 The push wrapper reads one completed run per SHA

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/jnwb_push.sh`, `scripts/push_guard.py`, `tests/test_push_guard.py`, `tests/test_jnwb_push.py`.
- 17-123: from P-216-33 and P-216-40. The wrapper took the first completed run, so a green `dashboard` run beside a red `CI/CD` run at one SHA let a push through; `push_guard.py` misses `git --git-dir=`/`--work-tree=` pushes and ends in a traceback when stdin is unreadable. Check: the wrapper refuses when any completed run at the newest SHA failed (a test with two runs at one SHA, one failed); each guard case is planted and denied.

### 17-124 quality_metrics drops a spike on a window's closing edge

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: 17-93 (shares `jnwb/analyzers.py`).
Writes: `jnwb/analyzers.py`, `tests/test_analyzers_coverage.py`.
- 17-124: from P-216-35. `quality_metrics` drops the last spike on the closing edge of its 1 s windows at the ulp, in 962 of 200000 random spans. Check: the edge tolerance `_bins` documents; a test places the spike on the closing edge and counts it.

### 17-125 Counts below 1 in StatisticalAnalysis

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: 17-93 (shares `jnwb/statistics/_analysis.py`).
Writes: `jnwb/statistics/_analysis.py`, `tests/test_statistics_refusals.py`.
- 17-125: from P-216-37. `n_bootstrap` and `n_permutations` in `_analysis.py` (`:157,545,603,710,800`) take 0 and negatives unchecked. Check: each refuses a count below 1 by name with `ValueError`, as 17-108's siblings do; one test per parameter.

### 17-126 The frozen granger entry does not see direction

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: 17-93 (shares `tests/test_connectivity.py`).
Writes: `artifacts/process/frozen_validated.json`, `tests/test_connectivity.py`.
- 17-126: from P-216-38. Swapping `x_to_y` and `y_to_x` in `granger`'s return passes the entry's `killed_by` test. Check: `killed_by` names a test with a known driver direction, and the swap mutant fails it.

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
- 17-94: the `fs` positive check is hand-written at about 20 sites (`filtering.py:31`, `continuous.py:136`, `tfr.py:251`, ...) beside `spectral/_common._require_positive_fs`; `jnwb/spectral` has 9 `_require_*` variants; `_bins.py:86,112` hold two onset loops differing in edge closure; three dB paths (`_decibels.py:15,24,457`); `nwb_write._sha256` equals `paths.sha256_file`; `_window_rows` twice (`_xflip.py:96`, `_zflip.py:178`). Check: one definition each, the grep returns one site, the suite passes.

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
Role: docs-harness. Skill: none. Blocked by: 17-78.
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
