# 0.2.17

Work order, roles, gates and owner questions toward the release candidate: `artifacts/process/release_checklist.md` (sections 4 and 9). The items below hold the defects and Checks; the checklist never restates a Check.


Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.16
closed on 2026-11-08 (tag `v0.2.16`, `0aa220ba`; tag CI/CD run 42513450995 success, TestPyPI and PyPI
verified, GitHub release body checked by `release_gate.py` STEP 0d). Items run fastest first.

Thinning and matching from the 2026-11-02 audits, each named by SHA: seven models at `7ca5b9a6` (17-83 to 17-105) and eight auditors at `9fd2b4bd` (P-216 rows, 17-128, 17-129). Lanes form at 0.2.16's close; 17-79 (which rewrote `_xflip.py`
and `_zflip.py`) landed at e6baac97. Each item applies the jarness standards: `match-cleanup` for
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

### 17-144 The jaxfne isi_cv commits

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-144-src (open stack; `E:/cl-jnwb16e` gone, SHAs absent from origin).
Writes: `artifacts/benchmarks/realdata/isi_cv_recompute.py`, `artifacts/benchmarks/realdata/isi_cv_recompute_receipt.json`, `artifacts/benchmarks/realdata/build_isi_cv_fixture.py`, `tests/fixtures/isi_cv_realdata_subsample.json`, `tests/test_isi_cv_realdata.py`.
- 17-144: three 16-12 commits on `E:/cl-jnwb16e` (0e06993c, 9980f58d, 5fa63dd3) for jaxfne-orchestrator.
  Observed 2026-11-12: path missing; SHAs absent from this clone and `origin`. Check: each on `dev` in that
  order, suite passes, jaxfne-orchestrator told.

### 17-99 One home per invariant across rule and doc files

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: Hamm adds the spikes-and-LFP fact row (the fact stack is his; ruled 2026-11-22: the fact stack is each invariant's home, other files link); shared `README.md`.
Writes: `.github/CONTRIBUTING.md`, `docs/architecture.md`, `README.md`, `docs/index.md`, `docs/glossary.md`, `artifacts/agents.md`.
- 17-99: `CONTRIBUTING.md:368-380` and `docs/architecture.md:128-171` restate the invariants AGENTS.md §4 keeps in the fact stack; the spikes-and-LFP rule ("never pool") is in 17 tracked files (`git grep -il 'never pool'`) and no fact row; "four outcomes" in three of the Writes files; the Python matrix on four pages. Check: each fact has one home and the others link to it.

### 17-100 Docs and examples thinning

Release: deferred-0.2.17.
Role: docs-harness. Skill: none. Blocked by: Hamm's ruling D5 (release checklist section 9) on the three parts below; shared `docs/references.md`, `README.md` with 17-129.
Writes: `docs/01_architecture_and_philosophy.md`, `docs/02_paths_addressing_metadata.md`, `docs/03_representational_similarity_jrsa.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/05_artifact_detection_and_repair.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md`, `docs/08_directed_connectivity_and_information.md`, `docs/09_decoding_and_visual_qc.md`, `docs/10_operation_specifications.md`, `docs/agents.md`, `docs/architecture.md`, `docs/coherence_and_tfr.md`, `docs/common_mistakes.md`, `docs/documentation_form.md`, `docs/errors.md`, `docs/execution.md`, `docs/glossary.md`, `docs/index.md`, `docs/install.md`, `docs/laminar.md`, `docs/quickstart.md`, `docs/reading_nwb.md`, `docs/recipes.md`, `docs/references.md`, `docs/repairing_nwb.md`, `docs/unit_quality_example.md`, `docs/vis.md`, `docs/writing_nwb.md`, `docs/assets/**`, `README.md`, `examples/**/*.py`, `mkdocs.yml`.
- 17-100: landed 2026-11-21 (merge 63b1874c): `docs/assets/jnwb_vis_sorted_heatmap.png`, the check log cut from `references.md`. 2026-11-23 (merge 6a7baf41, verifier ACCEPT on ac2c02ee): fig14 and fig18 have one home, `common_mistakes.md`; pages 06 and 08 link to it. Left, each kept for a reason the verifier confirmed: the redirect stub `docs/01_architecture_and_philosophy.md` serves a published URL (readthedocs latest and stable return 200); the 10-line `sys.path` guard in 12 example scripts is required inline by `tests/test_the_suite_can_qualify_an_installed_copy.py:347-366`; figure ids skip fig22 and fig23 (the ids are file keys in `figure_registry.toml`, AWAITING keys and committed PNGs). "labelled" stays (Q5: no conversion). Check: `docs_build.py` strict passes and each listed grep returns its one form.

### 17-101 Tracked rules that depend on untracked local files

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: Hamm's word on the roadmap row that vendors the lock helper or names the dependency (`artifacts/memory.md:7`) and on the wording of the 2026-09-22 ruling (`artifacts/rulings/standing.md:20`).
Writes: `artifacts/memory.md`, `artifacts/rulings/standing.md`.
- 17-101: merge 22eca3d2 (lane `7ef15176`, verifier ACCEPT): rules cite `artifacts/agents/` roles, each tier bound to one; five live "scratchpad" concept uses reworded; `parity44.py` marked not retained. Left, live non-record hits: `memory.md:7` (roadmap 17-138) cites `C:/Users/nejath/.claude/bin/suite_lock.py`; `standing.md:20` (corpus-access ruling) says "the scratchpad", no path. Check: `git grep -lE 'scratchpad|C:/Users/nejath'` over tracked rules returns only records.

### 17-129 Prose against the writing style

Release: deferred-0.2.17.
Role: docs-harness. Skill: none. Blocked by: Hamm's word for `skills/` and `AGENTS.md` (D6, release checklist section 9). Ruled 2026-11-22 (Q5): American English for new prose; no repository-wide conversion.
Writes: `.github/CONTRIBUTING.md`, `README.md`, `docs/quickstart.md`.
- 17-129: from P-216-26. Landed 2026-11-23 (merge 0621da87, verifier ACCEPT on 368df360): `CONTRIBUTING.md`, `README.md`, `docs/quickstart.md` hold no sentence over 40 words by `tests/test_prose_sentence_length.py` (code span = one word; 16 to 0 in CONTRIBUTING); the `:39` repeat has one home. Left: sentences over 40 words in 8 of 12 skills and `AGENTS.md` (:85, :105), Hamm's files; `docs/agents.md:82-94` repeats `skills/jnwb/SKILL.md:13-25`. Check: no sentence over 40 words in the listed files, by grep; prose added in this cycle uses American spelling.

### 17-166 Interval-table fallback duplicated in two modules

Release: deferred-0.2.18 (found by the 17-165 reviewer, 2026-11-24; does not block 0.2.17; relabelled 2026-11-25, the 0.2.17 gate counts deferred-0.2.17 as required).
Role: jnwb-developer. Skill: none. Blocked by: none. Lane: new `_temp_` lane from `dev`.
Writes: `jnwb/nwb_events.py`, `jnwb/nwb_inspect.py`.
- 17-166: the `("trials", "epochs", "invalid_times")` attribute fallback is written twice, `_interval_tables` in `nwb_events.py` and the loop at `nwb_inspect.py:1204-1210`. Check: `grep -n '"invalid_times"' jnwb/*.py` returns one site, and `nwb_inspect` imports the shared helper; the 55 tests in `tests/test_nwb_events.py` and the inspect tests stay green.

