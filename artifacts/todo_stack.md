# 0.2.17

Work order, roles, gates and owner questions toward the release candidate: `artifacts/process/release_checklist.md` (sections 4 and 9). The items below hold the defects and Checks; the checklist never restates a Check.


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
- 17-94: landed 2026-11-21 (merge 9427c84a): `_units.require_positive_fs` (bandpass, notch, spectral; NaN and Inf refused by name), `nwb_write._sha256` is `paths.sha256_file`, one `_onset_counts` in `_bins.py`, tests in `tests/test_fs_nonfinite.py`; `_decibels` is already one home (`_decibels.py:15,24,52`). Landed 2026-11-23 (merge 950a9fb5, verifier ACCEPT on 029a6c4d): 16 `fs` sites on the helper, which also refuses a string `fs`; the grep returns the helper's docstring and `spectral/_psd.py:74` in `compute_psd`, kept because `compute_psd` is frozen (`frozen_validated.json`), routed only with its re-verification; `vflip2_from_lfp` keeps its earlier real-number check, unnamed. The 8 `_require_*` in `jnwb/spectral` are distinct checks (2026-11-23, author's probe `artifacts/evidence/0.2.17/probe_pair_vs_trace_17-94.py`: `_trace` and `_pair` differ on a one-sided empty, string, 0-d and complex input, against the inventory's REDUNDANT-WITH). Landed 2026-11-23 (merge 6bcf22cd, verifier ACCEPT on a58137a2): `partial_coherence` on `_require_1d_traces`; the inventory's other REDUNDANT-WITH pairs each differ (probe `artifacts/evidence/0.2.17/probe_inline_1d_17-94.py`, section B). Left: `cross_area_coherence` (`_coupling.py:417`) retypes the 1-D and length checks, kept because it is frozen; `_window_rows` in `_xflip.py:96` and `_zflip.py:178` are two checks, not one (a malformed pair raises TypeError in xflip and ValueError in zflip, zflip refuses fewer than 3 rows, `np.bool_` and messages differ); the private helpers the 17-79 splits added in `_xflip.py`, `_zflip.py`, `_vflip.py`, `jrsa/__init__.py` and `_psi.py`, unsurveyed. Check: one definition each, the grep returns one site, the suite passes.

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
Role: jnwb-developer. Skill: none. Blocked by: Hamm's word on the roadmap row that vendors the lock helper or names the dependency (`artifacts/memory.md:7`) and on the wording of the 2026-09-22 ruling (`artifacts/rulings/standing.md:20`).
Writes: `artifacts/memory.md`, `artifacts/rulings/standing.md`.
- 17-101: merge 22eca3d2 (lane `7ef15176`, verifier ACCEPT): rules cite `artifacts/agents/` roles, each tier bound to one; five live "scratchpad" concept uses reworded; `parity44.py` marked not retained. Left, live non-record hits: `memory.md:7` (roadmap 17-138) cites `C:/Users/nejath/.claude/bin/suite_lock.py`; `standing.md:20` (corpus-access ruling) says "the scratchpad", no path. Check: `git grep -lE 'scratchpad|C:/Users/nejath'` over tracked rules returns only records.

### 17-127 The fact graph build takes four minutes

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none. `scripts/fact_graph/__init__.py` keeps its CRLF line endings (ruled 2026-11-22, Q6).
Writes: `scripts/build_fact_graph.py`, `scripts/fact_graph/*.py`, `tests/test_fact_gate.py`.
- 17-127: one `build_fact_graph.py` run took 264 s at `2e069118` and 217 s at `a5345f79` on the Windows host (one sample each; the 17-84 call-site rule landed between); under a full suite it passed the test's 300 s cap twice, now 900 s. Landed 2026-11-23 (merge 790b1a10, verifier ACCEPT): each unit walked and parsed once per scan; graph identical but the HEAD stamp; planted positives in the four scans empty on the live tree match base. Profile at base (s): rng_scan 6.4, source scans 4.2, owned rules 4.1, tests 3.9, text scans 3.2; `ast.walk` 47 of 88 s under cProfile. Timing: author 35.5 s base, 27-29 s after on an idle host; at 100% host load 88-114 s (three runs, 790b1a10). Left: three runs under 60 s on an idle host by someone other than the author, or one shared parse per file across scans. Check: a profile names the phases; the build runs under 60 s with the graph byte-identical.

### 17-128 Docstrings and constants against the code style

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-94 (shares `jnwb/**/*.py`).
Writes: `jnwb/**/*.py`.
- 17-128: landed 2026-11-21 (merge c8bbee69): Raises sections on 24 public functions, filtering Args with units, 20 tolerance literals named in 13 modules (values equal, signatures unchanged). Left: Raises for `inspect`, `bipolar_reference`, `granger`, `assert_mergeable` (an INTERNAL name in `tests/test_skill_symbol_coverage.py`; documenting it needs a skill row), helper-raised exceptions and `FileNotFoundError` not listed; the `_vflip2` band literals and the `_vflip.py`, `_xflip.py`, `_bins.py` sites, whose code the curation, vflip and xflip calibration receipts hash (a change needs the calibrate script rerun); `harmonic_analysis` (frozen); the 96 float defaults in the signatures of the 163 functions in `jnwb.__all__` keep their text (ruled 2026-11-22: the Check covers tolerance literals and raise sites only). From P-216-25 (the names went to roadmap 17-130): 23 of those 163 functions raise in their own body without a Raises section (AST count, 2026-11-21); unnamed band constants in `_vflip2.py`; 98 uncited float defaults and 43 tolerance literals at P-216-25 (`_psd.py:217` `fundamental_freq * 0.1`). Check: each public raise site has a Raises entry, each tolerance literal is a named constant with its source, the suite passes.

### 17-129 Prose against the writing style

Release: deferred-0.2.17.
Role: docs-harness. Skill: none. Blocked by: 17-99 and 17-100 (shared files); Hamm's word for `skills/` and `AGENTS.md`. Ruled 2026-11-22 (Q5): American English for new prose; no repository-wide conversion.
Writes: `.github/CONTRIBUTING.md`, `README.md`, `docs/quickstart.md`.
- 17-129: from P-216-26. The 2026-11-07 match pass adds: `docs/agents.md:79-94` repeats `skills/jnwb/SKILL.md:13-25`; `CONTRIBUTING.md:39` repeats `:36` and `:64`. Sentences over 40 words in 8 of 12 skills, `AGENTS.md` (:85, :105), `CONTRIBUTING.md` (:111, :179, :185, :379; em dashes on 17 lines); "behaviour" (113 lines) and "behavior" (105) both occur (`git grep -icw`, tracked tree). Check: no sentence over 40 words in the listed files, by grep; prose added in this cycle uses American spelling.
