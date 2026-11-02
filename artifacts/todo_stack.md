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
| A | 17-83, 17-84, 17-88, then 17-93 after 17-85 and 17-78 merge | `jnwb/analyzers.py` and the files of 17-93 |
| B | 17-85, 17-106 | `jnwb/connectivity/_*.py`, the `granger` entry of `frozen_validated.json`, the connectivity skill |
| C | 17-86, 17-87, 17-107, 17-108, 17-109, 17-110, 17-111 | `jnwb/nwb_events.py`, `jnwb/nwb_inspect.py`, `jnwb/spiking.py`, `jnwb/statistics/_*.py` |
| D | 17-89, 17-90, 17-105, 17-114 | the named tests, `scripts/gates/`, `scripts/docs_form_gate.py` |
| E | 17-91, then 17-78 after 17-90 merges | `docs/*.md`, `README.md`, `skills/jnwb/SKILL.md`, `skills/jnwb-population/SKILL.md`; the connectivity skill after 17-85 and `scripts/docs_form_gate.py` after 17-90 |
| G | 17-115, 17-116, 17-117, 17-80, 17-81, 17-82 | `scripts/push_guard.py`, `scripts/jnwb_*.sh`, `scripts/verify_lane.py`, `scripts/bump_version.py`, `scripts/release_gate.py` |
| F | 17-92 | `artifacts/evidence/` |
| H | 17-112, 17-113 | `jnwb/nwb_validate.py`, `jnwb/metadata.py` |

- Batches: A, B, C; then D, E, G; then F, H and 17-93. The integrator does 17-76.
- Waiting on Hamm: 17-75, 17-77; skill lines in 17-91 and 17-116; open rows P-216-01, -05 to -08,
  -15, -17 to -20, -22, -24, -32. Open rows with no item yet: P-216-16, -21, -25, -26.
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
Role: docs-harness. Skill: none. Blocked by: 17-90 (shares `scripts/docs_form_gate.py`); `skills/` lines need Hamm's word.
Writes: `docs/*.md`, `skills/jnwb/SKILL.md`, `scripts/docs_form_gate.py`.
- 17-78: the 2026-10-31 agy sweep found form drift that blocks nothing (lane D1 fixed the wrong statements): numbered pages 02, 05, 06, 09, 10 end without the `## References` the others carry; page 08 raises operations to H2; `reading_nwb.md` and `coherence_and_tfr.md` number their headings, other concept pages do not; `um`, `µm` and `$\mu$m` all occur; `skills/jnwb/SKILL.md` adds a section 3 the other skills lack; `writing_nwb.md` repeats two refusal rows in three tables. Check: `scripts/docs_form_gate.py` gains one rule per listed form and passes.

### 17-80 The version bump leaves the figure registry behind

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/bump_version.py`, `scripts/version_surfaces.py`, `tests/test_bump_version.py`.
- 17-80: twice (0.2.14 in 56d021c3, 0.2.15 in 1b55385b) the suite failed after `bump_version.py` because `scripts/figures/figure_registry.toml` still recorded the old `jnwb_version` in 35 entries. Check: `tests/test_bump_version.py` bumps a copy and asserts every registry entry carries the new version.

### 17-81 A transient network error fails the dashboard browser test

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `tests/test_dashboard_page.py`.
- 17-81: the full suite at 13253019 failed `test_every_route_renders_in_light_and_dark_without_errors` once on `net::ERR_NO_BUFFER_SPACE` loading `assets/fig12_coherence_zero_lag.png` (1 failed, 10605 passed); the file alone passed 16 of 16 and the full rerun passed 10606. Check: a transient `net::ERR_*` load is retried once, and a test with a missing asset still fails on its 404.

### 17-82 The release gate cannot pass with no skip in one run

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/release_gate.py`, `tests/test_release_version_is_unpublished.py`, `tests/test_release_body_gate.py`.
- 17-82: before the tag run, step 0d (release body) skips because the workflow creates the release only after PyPI; after it, step 0b fails (`version 0.2.15 is already on the index`, 2026-11-02 at `5822c3e9`). In a `git clone --shared` step 0d also skips: `gh release view` cannot resolve a local-path origin (passed with `GH_REPO=hnxj/jnwb`). Check: a post-publication mode accepts an index version whose files match the tag's build, step 0d names the repository explicitly, and a test runs both modes.

### 17-83 psth puts an onset spike in the bin before the onset

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: nothing.
Writes: `jnwb/analyzers.py`, `tests/test_analyzer_windows.py`.
- 17-83: `UnitAnalyzer.psth` builds edges with `np.linspace` in seconds (`analyzers.py:405`); for `window_ms=(-100, 200)`, 10 ms bins, `edges[10] = 1.39e-17`, so a spike exactly at the onset counts in the bin centred at -5 ms (probe 2026-11-02 at `7ca5b9a6`). `quality_metrics` has the same defect (P-216-30, `analyzers.py:676-684`): t0 = 2.15, spikes 1 s apart count `[2 0 2]` against `[1 1 2]`, and `int(duration)` turns a 2 s span into 1.9999999999999998 and a NaN Fano. Related: roadmap 17-70. Check: edges built as `start + k*bin` (as `viz.py:160`), the 1 ns tolerance (`analyzers.py:626-627`) before `int()`; tests find the onset spike at +5 ms and counts `[1 1 2]` at t0 = 2.15.

### 17-84 psth bootstraps without an rng

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: nothing (shape ruled 2026-11-02, `artifacts/rulings/2026-11-02.md`).
Writes: `jnwb/analyzers.py`, `scripts/build_fact_graph.py`, `tests/test_rng_parameters_by_use.py`.
- 17-84: `UnitAnalyzer.psth` returns `bootstrap_ci` from `StatisticalAnalysis.bootstrap_ci(...)` with no `rng` (`analyzers.py:428`), so draws use the default seed (fact S5); the `rng` scan checks direct draws only. Check: `psth(..., rng=)` passes it through, two seeds give different CIs, and the scan flags the pre-fix `psth`.

### 17-85 The no-pooling guard is only on the deprecated Granger function

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing (ruled 2026-11-02: the 2026-10-28 rule on the four estimators).
Writes: `jnwb/connectivity/_granger.py`, `jnwb/connectivity/_psi.py`, `jnwb/connectivity/_transfer_entropy.py`, `jnwb/connectivity/_network.py`, `artifacts/process/frozen_validated.json`, `skills/jnwb-connectivity/SKILL.md`, `tests/test_signal_class.py`.
- 17-85: `signal_class` exists on deprecated `granger_causality` (`_granger.py:344`) and on `directed_network`, not on its replacement `granger` (`:558`) or on `directed_connectivity`; a caller who follows the DeprecationWarning loses the spikes-vs-LFP guard (AGENTS.md §5). Check: `granger`, `granger_spectral`, `phase_slope_index` and `transfer_entropy` take keyword-only `signal_class`, warn when it is omitted and refuse a mixed pair, also through `directed_connectivity`; a test covers each.

### 17-86 edges_near_events thresholds raw stored values

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: nothing.
Writes: `jnwb/nwb_events.py`, `tests/test_nwb_events.py`.
- 17-86: `_series_samples` reads `series.data[:]` with no `conversion` or `offset` (`nwb_events.py:396`), while its docstring cites `acquisition_channel`, which applies them (`nwb_inspect.py:863`); an int16 photodiode with `conversion=1e-3` and a threshold in volts finds no edges. Check: a test with `conversion=1e-3` finds the edges, and the docstring names the threshold's unit.

### 17-87 fires_in_window retypes the onset-window rule

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: nothing.
Writes: `jnwb/statistics/_firing.py`, `tests/test_adversarial_inputs.py`.
- 17-87: `fires_in_window` and `rate_in_window` add the onset to the window edges (`_firing.py:30`); `_bins.onset_window` (`_bins.py:71-75`) documents that this drops a spike at the ulp edge (onset 0.03, spike 0.3, start 270 ms); AGENTS.md §4.7. Also dead slices `t[:n]`, `u[:n]` (`:54-55`, `:135-136`). Check: reproduce the ulp case first; both functions select through `onset_window` and the case passes.

### 17-88 Stale API statements in code docstrings

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/analyzers.py`.
- 17-88: `UnitAnalyzer`'s method list (`analyzers.py:313-318`) names a `firing_rate` method that does not exist and old signatures; the `_network.py` part is 17-106. Check: the method list is deleted, and the integrator's `scripts/generate_api_md.py` run leaves `docs/api.md` equal to its output.

### 17-106 Stale statements in `_network.py`

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 17-85.
Writes: `jnwb/connectivity/_network.py`.
- 17-106: from 17-88. `directed_connectivity` says "all three directed estimators" (`_network.py:91`) over four (`DIRECTED_METHODS`); `directed_network`'s annotation admits a pair the body refuses (`:120`). Check: the count is dropped, the annotation is `str`, and `docs/api.md` regenerates to match.

### 17-89 Tests that cannot fail

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `tests/test_jnwb_core.py`, `tests/test_docs_smoke.py`, `tests/test_api_consistency.py`.
- 17-89: `test_jnwb_core.py:81-83` asserts `bootstrap_ci` only `if` the key is present; its `extract_band` tests (`:102,112,121,285`) assert non-None or shape only; `test_docs_smoke.py:80,182,188,199,204,297,301` and `test_api_consistency.py:245` assert `is not None` on always-set attributes. Check: each assertion names a value, and a mutant of the function under test turns each red.

### 17-90 Two doc gates miss files they claim to cover

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/gates/docs.py`, `scripts/docs_form_gate.py`, `tests/test_docs_form_gate.py`.
- 17-90: gate 18's `expected_scripts` (`scripts/gates/docs.py:301-311`) lists tutorials 00 to 08; `09_open_data.py` and `10_wavemap.py` exist and go unchecked. The F5/F8 corpus (`docs_form_gate.py:219-220`) reads `examples/tutorials/*.py` only, so `examples/quickstart_jnwb.py:6` ("Six primitives") passes. Check: the gate derives its list from the folder, and a planted "primitives" in the quickstart fails.

### 17-91 Wrong or internal statements on the public surface

Release: deferred-0.2.16.
Role: docs-harness. Skill: none. Blocked by: 17-85 (shares the connectivity skill); skill lines need Hamm's word.
Writes: `README.md`, `docs/quickstart.md`, `docs/agents.md`, `docs/documentation_form.md`, `skills/jnwb-population/SKILL.md`, `skills/jnwb-connectivity/SKILL.md`.
- 17-91: `CHANGELOG.md:21` lists "Distance-binned coherence normalization" under Added, but no function exists (`docs/common_mistakes.md:447`: the normalization is the caller's); `skills/jnwb-population/SKILL.md:23-24` omit `label=`, added in 0.2.15; `README.md:200` links `artifacts/agents.md`; `docs/quickstart.md:5` cites the `dev` branch; `docs/agents.md:15` lists `AGENTS.md`; `documentation_form.md:23` says 37 nav pages, `mkdocs.yml` has 39; the integrator corrects the CHANGELOG line. Check: each line corrected, `test_skills_validation.py` and gate 14 pass.

### 17-92 Closed evidence that nothing cites

Release: deferred-0.2.16.
Role: actor. Skill: none. Blocked by: nothing.
Writes: `artifacts/evidence/0.2.13/*`, `artifacts/evidence/0.2.14/*`, `artifacts/evidence/0.2.15/suite_profile.md`, `artifacts/process/plans_0.2.15.md`, `.gitignore`.
- 17-92: AGENTS.md §0, as commit `91b04aec` did for 58 files. `git grep -lF <basename>` finds no citer for `evidence/0.2.13/compress_scaling_probe.py`, `compress_scaling.json` (`.gitignore` only), `p335_laminar_curation_review.md`; `evidence/0.2.14/jaxfne_docs_dashboard_comparison.md`, `process_tests/plants.py`, `process_tests/prune_record.md` (266 lines); `evidence/0.2.15/suite_profile.md` (309 lines); `process/plans_0.2.15.md`. No gate globs `artifacts/evidence/`. Check: each removed with its `.gitignore` lines, the same grep is empty, harness 22 of 22.

### 17-93 Deprecated surfaces past their removal date

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: 17-85, 17-78 (shared files; ruled 2026-11-02, `granger_causality` stays, P-216-07).
Writes: `jnwb/analyzers.py`, `jnwb/_dictlike.py`, `jnwb/spectral/__init__.py`, `jnwb/connectivity/__init__.py`, `jnwb/connectivity/_information.py`, `jnwb/statistics/_analysis.py`, `jnwb/_declarations.py`, `artifacts/process/frozen_validated.json`, `skills/jnwb-statistics/SKILL.md`, `skills/jnwb-connectivity/SKILL.md`, `docs/architecture.md`, `docs/references.md`, `tests/test_analyzers_coverage.py`, `tests/test_connectivity.py`, `tests/test_deprecated_aliases.py`, `tests/test_dict_access_shim.py`, `tests/test_nonfinite_inputs.py`, `tests/test_public_api_reachability.py`, `tests/test_skills_validation.py`, `tests/test_statistics.py`, `tests/test_substitution_class_sweep.py`, `tests/test_unit_suffixed_parameters.py`.
- 17-93: `analyzers.py:211` says the renamed `n_significant` keys "are removed in the next release" (added 2026-09-26, 8 releases ago); `RenamedKeyDict` (`_dictlike.py`; used by `analyzers.py:232`, re-imported by `spectral/__init__.py:18`) stays for them; `granger_causality`, `clopper_pearson_ci` and both MI aliases are deprecated and still extended. Check: the keys, `RenamedKeyDict`, `clopper_pearson_ci` and the two MI aliases are removed with one Breaking entry; `docs/api.md` and the skill rows lose them; `granger_causality` is unchanged.

### 17-105 The stack gate passes an integrator-owned write set

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/gates/stacks_closure.py`, `tests/test_generation_closure_is_declared.py`.
- 17-105: `docs/api.md` went into a todo Writes field three times (2026-10-11, 2026-10-27, 2026-11-02); harness gate 17 passed each and only `tests/test_generation_closure_is_declared.py` caught it, after a suite. The stack rules make `CHANGELOG.md` integrator-owned too. Check: gate 17's STACK_FORM rejects either path in Writes, and a planted item fails it.

### 17-107 assign_subblock_quartiles returns uninitialised memory

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/statistics/_trials.py`, `tests/test_statistics_refusals.py`.
- 17-107: from P-216-27. `q = np.empty(n)` and the loop over `range(n_quantiles)` writes nothing at `n_quantiles=0` (`_trials.py:61-64`); five start times returned `[4725103939736093674 -4489260897863941142 ...]` (probe at `9fd2b4bd`). Check: `n_quantiles < 1` raises `ValueError`, tested at 0 and -1.

### 17-108 Counts below 1 pass silently

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: 17-87 (shares `_firing.py`).
Writes: `jnwb/statistics/_firing.py`, `jnwb/statistics/_regression.py`, `jnwb/statistics/_tests.py`, `tests/test_statistics_refusals.py`.
- 17-108: from P-216-28. `paired_fire_prob_test` gives p = 1.0 at `n_shuffles=0` and `IndexError` at `n_bootstrap=0` (`_firing.py:143-149`); `cross_modal_comparison` gives `lag_corrected_pvalue` 1.0 at `n_permutations=0` (`_regression.py:333,337`); `shuffle_pvalue_paired` and `_unpaired` return `(nan, nan)` at n < 2 before checking `alternative` (`_tests.py:293-296,353-355`). Siblings refuse (`spectral/_coupling.py:383,673`). Check: each count < 1 raises a named `ValueError`, and a bad `alternative` raises at n = 1.

### 17-109 mann_whitney_p_floor overflows

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: 17-108 (shares `_tests.py`).
Writes: `jnwb/statistics/_tests.py`, `tests/test_statistics_refusals.py`.
- 17-109: from P-216-29. `1.0 / float(math.comb(n1 + n2, n1))` (`_tests.py:98-99`) raises `OverflowError` at n1 = n2 = 520; n = 510 gives `7.1e-306`. Check: computed in log space; n = 510 matches today's value to `rtol=1e-12`, and n = 520 returns a float without raising.

### 17-110 spiking inputs read as a wrong state

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: nothing; labelling a missing `response_zscore` `'undefined'` (today `'none'`, `spiking.py:297-299`) needs Hamm's word.
Writes: `jnwb/spiking.py`, `tests/test_spiking_inputs.py`.
- 17-110: from P-216-31 and P-216-24. `phase_locking_index` accepts NaN `lfp_timestamps` (`steps <= 0` is False for NaN, `spiking.py:428-429`) and blames `lfp_phase` for a NaN beside spikes (`:480-488`); the comment at `:651-653` calls a question AGENTS.md §8 decides "not yet decided". Check: non-finite `lfp_timestamps` raise `ValueError` naming them; the comment is removed.

### 17-111 TimeIntervals in a processing module

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: 17-86 (shares `nwb_events.py`).
Writes: `jnwb/nwb_events.py`, `jnwb/nwb_inspect.py`, `tests/test_nwb_events.py`, `tests/test_nwb_inspect.py`.
- 17-111: from P-216-03 (hnxj/jnwb#37). `inspect(...)["interval_tables"]` is `[]` for a `TimeIntervals` under `processing/behavior`, and `events(table="processing/behavior/events")` raises `IntervalTableNotFoundError`. Check: the issue's repro lists the table in `inspect` and `events` reads it by its slash path.

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

### 17-114 The log-last gate passes on an empty set

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: whether zero declarations fails is Hamm's (P-216-09); the count needs no ruling.
Writes: `scripts/gates/boundary.py`, `scripts/harness_gate.py`, `tests/test_harness_adversarial_gates.py`.
- 17-114: from P-216-09. No module of `jnwb/` declares `estimand: raw_power`, so `check_logarithm_last_in_package` (`boundary.py:481-497`) examines nothing and the pass line names no count. Check: the pass line prints the number of declared estimands examined, and a planted declaration that logs before its mean fails.

### 17-115 push_guard misses copies and chained pushes

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/push_guard.py`, `tests/test_push_guard.py`.
- 17-115: from P-216-13. The guard matches only a path component `jnwb` (`push_guard.py:37`), so a plain push from `_temp_integ` passes, and any command containing `jnwb_push.sh` passes whole (`:33-34`), e.g. `bash jnwb_push.sh ...; git push origin dev`. Check: tests expect deny for a jnwb clone under another name and for the chained command.

### 17-116 The seal order the wrappers enforce

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: the skill line needs Hamm's word.
Writes: `artifacts/skills/jnwb-fact-action/SKILL.md`, `scripts/jnwb_suite.sh`.
- 17-116: from P-216-14. The skill seals with gates, commit, push (`SKILL.md:56-60`), but `jnwb_suite.sh` stamps only a clean tracked tree (`:30-33`), so the suite runs after the commit; the suite takes no machine lock (`artifacts/memory.md:7`). Check: the skill reads commit, suite, push; `jnwb_suite.sh` runs pytest through the suite lock when it exists and says so when it does not.

### 17-117 Flow steps with no performer

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: 17-115 (shares the lane); the `artifacts/`-only exemption is Hamm's (P-216-22).
Writes: `scripts/verify_lane.py`, `scripts/jnwb_push.sh`, `tests/test_lane_verifies_its_own_baseline.py`.
- 17-117: from P-216-22. Prepare regenerates `state.md` "if `--check` fails" but nothing runs it (`AGENTS.md:51`, `verify_lane.py`); no step compares a lane's diff with its item's Writes. Check: `verify_lane.py` runs `reconstruct_state.py --check` and regenerates on failure; `jnwb_push.sh` refuses a diff outside the named Writes when given an item id; a test plants each case.

# 0.2.17

Thinning and matching from the 2026-11-02 audit. Lanes form at 0.2.16's close; 17-94 waits on 17-79,
which rewrites `_xflip.py` and `_zflip.py`. Each item applies the jarness standards: `match-cleanup` for
removals, `match-code-style` for code, `match-writing-style` for prose, `match-visual-style` for figures.

### 17-79 Complexity of the largest functions

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-85 (shares `_psi.py`; moved from 0.2.16 by the lane ruling of 2026-11-02).
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
Writes: `docs/*.md`, `docs/assets/**`, `README.md`, `examples/**/*.py`, `mkdocs.yml`.
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
