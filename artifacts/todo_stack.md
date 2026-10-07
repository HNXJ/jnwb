# 0.2.10

Opened 2026-10-05, after 0.2.9 was published. Items are deleted when done, never ticked; git,
`CHANGELOG.md` and the receipts hold history. The previous cycle's record is
`artifacts/archive/0.2.9/todo_stack_0.2.9.md`, with its closure receipt beside it; its 0.2.9
section held only the two release-step items at the release, and every later section moves here
unchanged.

Theme: oversized modules become small packages behind the same public API, and the scientific
edges in them are closed.

Acceptance: `AGENTS.md` §11; no public symbol or parameter of 0.2.9 removed or renamed, and any
addition (a symbol, an optional parameter whose default keeps 0.2.9 results, an annotation
correction) announced in a changelog fragment (ruled 2026-10-06);
gate 19 entries re-pointed with unchanged hashes; each estimator change carries a calibration
record in `artifacts/evidence/0.2.10/`.

Every item here carries `deferred-0.2.10`, the deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.9 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet, in the contract of `artifacts/skills/jnwb-fact-action` §5; role `jnwb-developer` unless named | a batched packet redefines the hard item |
| A lane is one worktree and one writer; at most three lanes run at once; a lane's items run in the order listed | lanes never share a file, so they merge without conflict |
| A packet reproduces each bullet on its own tree first; a bullet that does not reproduce is deleted | non-reproduction is a result |
| The actor is never the verifier | every repair is re-run by someone else |
| The integrator owns the stacks, `CHANGELOG.md` and `docs/api.md` | packets report the disposition and the changelog text |
| Wave barrier: `python scripts/harness_gate.py` (count PASS lines), `python -m pytest tests/ -q`, commit, push, CI green on `dev` | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then `Do`, `Accept`, `Stop` as
needed; `AUTONOMY` and a one-line source or ruling note follow the fields they qualify. A bullet reads
`ID: defect, as input -> observed against expected, with numbers and units. Check: a predicate that
decides it, naming the file and the asserted value. Waits: why it cannot make release evidence
falsely pass.` `Waits:` appears in deferred cycles; `Waits: not stated.` marks a reason no source
gives, for the closure pass to classify.

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| G connectivity and similarity | 10-06 | `jnwb/connectivity*`, `jnwb/jrsa*`, `jnwb/rsa.py`, their tests, `tests/test_substitution_class_sweep.py`, `tests/test_connectivity_pitfalls.py`, `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-population/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md` once 10-03 is merged, `tests/test_skills_validation.py`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md` |
| H statistics, spiking and decoding | 10-18, 10-26 | `jnwb/statistics*`, `jnwb/permutation.py`, `jnwb/spiking.py`, `jnwb/onset_fitting.py`, `jnwb/analyzers.py`, `jnwb/trajectory.py`, `jnwb/gpu_pca.py`, `jnwb/bilinear.py`, `jnwb/nam.py`, `jnwb/artifact_repair.py`, `jnwb/_spread.py`, `jnwb/_bins.py`, `jnwb/_dictlike.py`, `jnwb/paths.py`, `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `jnwb/testing/**`, `artifacts/frozen_validated.json`, their tests, the statistics, spiking, landmark-viz and figures skills, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md` |
| R reduction | 10-20, 10-21 | `AGENTS.md`, `artifacts/archive/**`, `artifacts/evidence/0.2.6/**`, `artifacts/evidence/0.2.7/**`, `artifacts/evidence/0.2.8/**`, `artifacts/evidence/0.2.9/**`, `artifacts/evidence/0.2.10/reduction/**`, `tests/test_jnwb_frozen_boundary.py` |

10-01, 10-02, 10-03, 10-04, 10-05, 10-07, 10-08, 10-13, 10-19, 10-22 and 10-25 are merged, and 10-06 rounds 1 and 2; 10-06's residue, 10-18, 10-20, 10-21, 10-23, 10-24 and 10-26 are open.

### 10-06 Directed and similarity estimator edges

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `jnwb/connectivity/**`, `jnwb/jrsa/**`, `jnwb/rsa.py`, `tests/test_connectivity.py`, `tests/test_jrsa*.py`, `tests/test_rsa.py`, `tests/test_substitution_class_sweep.py`, `tests/test_adversarial_inputs.py`, `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-population/SKILL.md`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md`.
- Round-2 test reach (verified 2026-10-06, 65691a49): surviving mutants M5 (conditioning on the first other node only; no test has four or more nodes), M3b (`n_seg-1` degrees of freedom in the multi-band `z_tot`), M10 (the observed round-off term dropped from the TE one-way tie width), M17 (the `gc` alias refused) and M19 (NaN slices in `zero_detrend_residue`). Check: each killed by a test. Waits: behaviour verified correct; tests only.
- `jnwb/connectivity/_psi.py:307` states the segment jackknife rejected 0.070-0.079 on 10 trials of 400, where the default-`nperseg` record says 0.068. Check: the comment quotes the record. Waits: wording.
- `jrsa` `phase_slope` ravels to one trial, so it warns "pass 3 or more trials" on every call, which a `jrsa` caller cannot act on. Check: the warning suppressed or reworded for the `jrsa` path, with a test. Waits: a warning, no value change.
Accept: each check passes; calibration records in `artifacts/evidence/0.2.10/`.
Stop: a default change without a ruling.

### 10-26 Residue of 10-08 (decoding, aliases, paths)

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: per finding. Blocked by: none.
Writes: `jnwb/decoding.py`, `jnwb/_dictlike.py`, `jnwb/paths.py`, `jnwb/_backend.py`, `jnwb/trajectory.py`, their tests.
Left by the 10-08 verification (2026-10-06, d6d6d8b5); shipped values are unchanged by each.
- P-332 multi-class: `nested_cv_linear_svm` with three classes raises scikit-learn's "multi_class must be in ('ovo', 'ovr')". Check: a refusal naming the argument, asserted by a test. Waits: loud error.
- `layer_masks_path(subdir=...)` accepts an absolute path, `..` and `''`, and the first two escape the outputs directory its docstring says it is relative to. Check: each refused by name, with a test. Waits: caller-supplied path.
- `RenamedKeyDict`: `d |= {'old': 1}` inserts `old` beside `new` with no warning, and `pop('old')` with `new` already removed raises `KeyError('new')`. Check: each follows the alias, with a test. Waits: deprecated alias path.
- The `compute_population_trajectory` device warning gives the "DLL conflict, import cupy first" advice for a non-DLL `OSError` (a `PermissionError` on `libcuda.so`), though the exception text is shown. Check: the advice only for a loader error, with a test. Waits: wording.
- The trajectory docstring figure "relative gap 1.5e-5 moved a loading by 0.009" between CPU and CUDA (`jnwb/trajectory.py`) was not reproduced by the verifier. Check: the figure reproduced by a probe kept in the evidence, or removed. Waits: wording.
- `population_trajectory` on a constant `X` keeps NaN variances, as documented, but its components are the identity matrix, a value no computation produced. Check: Hamm rules NaN components or the documented identity. Waits: documented behaviour. AUTONOMY: none.
Accept: each check passes.
Stop: a fix changes a shipped value without a ruling.

### 10-23 `nwb_integrity` residue

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/nwb_integrity.py`, `tests/test_nwb_integrity.py`, `docs/repairing_nwb.md`.
Left by the 10-22 verification (2026-10-06); shipped behaviour is unchanged by each.
- The output-must-not-exist check at the new-file path is not atomic: a file created between the check and `os.replace` is overwritten. Check: the new file is created exclusively, or the window is stated. Waits: a race on a path the caller chose, no value change.
- `dry_run=True` with `in_place=True` and no `backup_path` raises the refusal; a dry run writes nothing. Check: a dry run ignores the missing backup, or the refusal says why. Waits: wording.
- `docs/repairing_nwb.md` says nwbinspector reports none of the ragged-index values: a claim about a third-party tool with no receipt (`AGENTS.md` 4.1). Check: removed, or traced to a run. Waits: wording.
Accept: each check passes.
Stop: none.

### 10-18 A stalled notebook kernel fails the suite instead of hanging it

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `tests/test_notebooks.py`.
- P-368: the full suite hung 40 minutes at 99% on 2026-10-06 (13f8b7e8): three notebook kernels under two xdist workers stopped answering while other jobs loaded the machine. `tests/test_notebooks.py:44` bounds each cell (`timeout=120`) but not kernel start or shutdown, and the suite has no per-test timeout. The file alone passed in 12.5 s and the rerun passed. Check: kernel start, every cell and shutdown are bounded by named constants, and a test whose kernel never answers fails by name within their sum. Waits: a hang gives no pass; fails closed.
Accept: a test with a kernel that never answers fails within the bound.
Stop: none.

### 10-24 `laminar_curation` test reach

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: none.
Writes: `tests/test_laminar_curation.py`.
Left by the 10-19 verification (2026-10-06); the behaviour is verified correct, so each is a test gap.
- Surviving mutants on the new parameters: `detect_bad_channels` `nperseg`, the CSD `min_contacts`, `min_edge_contacts` (no edge-search test exists), the erp-interpolation `max_run`, the window-vFLIP `min_contacts`, the window band routing, the grade B and D `>=` boundaries, and the low-rate refusal at `fs / 2` equality. Check: each killed by a test. Waits: tests only.
Accept: each mutant killed.
Stop: none.

### 10-20 Closed-cycle files nothing reads are deleted

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `AGENTS.md`, `artifacts/archive/**`, `artifacts/evidence/0.2.6/**`, `artifacts/evidence/0.2.7/**`, `artifacts/evidence/0.2.8/**`, `artifacts/evidence/0.2.9/**`.
Ruled 2026-10-06: closed-cycle files with no machine reader and no live citation are deleted, git holding them; the `api_proposals` files the 0.2.13 execution API cites stay.
- The list: `artifacts/evidence/0.2.10/reduction/artifacts_class.tsv` rows with class `closed`, zero readers and zero live citations: 65 files, of which 7 are `api_proposals` and stay, so 58 files, 609 KB, 6,887 lines. Check: each re-grepped against every tracked file at the item's baseline before deletion; a file a kept file cites is deleted with the citation removed, or kept. Waits: no shipped effect.
- `AGENTS.md` §0 says closed cycles are "kept as written". Check: the row states the ruled rule (kept until nothing reads or cites them). Waits: wording.
Accept: the deleted set equals the re-grepped list; every gate and the suite pass.
Stop: a file on the list has a reader the audit missed.

### 10-21 Test reduction by a corrected coverage pass

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 10-06, 10-26.
Writes: `artifacts/evidence/0.2.10/reduction/**`, `tests/test_jnwb_frozen_boundary.py`.
Ruled 2026-10-06: one full coverage pass with `COVERAGE_CORE=ctrace`, and the prune list goes to Hamm before any deletion (ruled 2026-09-27).
- Per-test contexts under the default coverage core of Python 3.14 record only the first test per line per worker, so the first audit's per-test counts are unreliable (`ctxprobe`, reproduced twice). Check: the pass runs under `COVERAGE_CORE=ctrace`, its log and per-file unique-line counts recorded here. Waits: measurement only.
- 21 test files showed zero unique lines and 48 process tests are unjudgeable by coverage (16k lines together). Check: a prune list in which each candidate carries its unique lines under ctrace and at least one mutant on its purpose, killed elsewhere; the list goes to Hamm. Waits: nothing is deleted before the ruling.
- 92 near-duplicate test clusters (`test_clusters.txt`); about 150-250 lines net after parametrize tables. Check: the pure-duplicate clusters on the prune list with their saving. Waits: nothing is changed before the ruling.
- `tests/test_jnwb_frozen_boundary.py:40-115` re-implements `check_frozen_boundary` (gate 1). Check: the test calls the gate's check; about 45 lines removed. Waits: the gate runs either way.
Accept: the prune list is recorded and ruled; the boundary test calls the owner's check.
Stop: a candidate is the only killer of some mutant.

# 0.2.11

Theme: interpretation, routing and documentation hold: every interpretational pitfall has a
synthetic test, every skill points to its sources and composes with the router, displays and
documented call shapes are checked, and the identity and scientific-choice facts are held.

Acceptance: `AGENTS.md` §11; the facts 10-10 and 09-04 hold use the ruled lexicons; the router
composes the minimal skill set for each chain 07-09 tests; each published unit measure is a public
operation by its published definition or a ruled exclusion.

Every item here carries `deferred-0.2.10`, as in 0.2.10.

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| Y identity facts | 10-10, 09-04 | `jnwb/__init__.py`, `jnwb/compression.py`, `jnwb/_declarations.py`, the fact gate and its test, `artifacts/fact_stack.md` holder cells |
| G pitfalls and skill sources | 10-11, 10-12 | `tests/test_connectivity_pitfalls.py`, `tests/test_substitution_class_sweep.py`, `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-population/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md` |
| D display, documentation and unit measures | 10-09, 10-14, 10-15 | `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `jnwb/unit_quality.py`, their tests, `skills/jnwb-landmark-viz/SKILL.md`, `skills/jnwb-figures/SKILL.md`, `skills/jnwb-qc/SKILL.md`, `docs/vis.md`, `tests/test_docs_call_shapes.py`, `scripts/docs_form_gate.py`, `tests/test_skill_symbol_coverage.py`, `artifacts/evidence/0.2.9/unit_qc_inventory.md` |
| P skills composition | 07-08, 07-09 | `skills/jnwb/SKILL.md`, `skills/jnwb/agents/openai.yaml`, `tests/test_skill_router_reach.py`, `tests/test_composition_*.py` |

Question round at the opening: the B3 choice-name lexicon (10-10) and the dB-lexicon values 09-04
reads.

### 10-10 Identity and scientific-choice facts held

Release: deferred-0.2.10.
AUTONOMY: none for the B3 lexicon values; holder cells under the standing authorization of 2026-09-29; the rest is `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `jnwb/_declarations.py`, `artifacts/fact_stack.md`.
- I1: declared signature types for every numeric public operation, and type-checked composition edges (`jnwb/_declarations.py`). Check: a planted spikes-to-LFP-only edge is reported VIOLATED by `tests/test_fact_gate.py`. Waits: fact reports UNHELD; nothing public claims it.
- B3: the lexicon and exceptions table. Check: a planted public function with a defaulted `window=` and no cited reason in the table is VIOLATED by `tests/test_fact_gate.py`. Waits: fact reports UNHELD; nothing public claims it.
Accept: the Identity table and B3 report no UNHELD fact.
Stop: a declaration would change a public signature without a ruling.

### 09-04 Science and Skills facts held

Release: deferred-0.2.10.
AUTONOMY: none for the dB-lexicon values; holder cells under the standing authorization of 2026-09-29; the scans are `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- S8: claim classes and the text check over docs, skills, figure labels and docstrings. Check: `scripts/fact_gate.py` reports the 0.2.7 fig09 unit, planted, as VIOLATED. Waits: fact reports UNHELD; nothing public claims it.
- S1, S2, S5 and S7: the scans as ruled in Q13. Check: each scan reports its own planted case in `tests/test_fact_gate.py`. Waits: fact reports UNHELD; nothing public claims it.
- K1: the partition with k = 3 exclusive operations per shipped domain skill. Check: a planted two-operation skill is VIOLATED. Waits: skill-partition check; no shipped behaviour.
- Planned skills (moved from the fact stack as plan, Q14): twelve, the ten of 0.2.6 with `jnwb-landmark-viz` included (ruled 2026-09-22, P-180), plus `jnwb-paradigm` (experiment and timing semantics) and `jnwb-qc` (independent scientific and output QC); `jnwb-data-engineering` and `jnwb-compute` wait on their public APIs and neither is a required endpoint: a capability the router routes cleanly gets no skill. Check: the fact gate reports a planned skill only when K1 and K5 hold for it. Waits: plan for future skills; no shipped behaviour.
Accept: the Science and Skills tables report no UNHELD fact.
Stop: a scan would need a scientific criterion not ruled in Q12 or Q13.

### 10-11 One synthetic test per interpretational pitfall

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 10-06.
Writes: `tests/test_connectivity_pitfalls.py`.
Source: table 2 of `artifacts/evidence/0.2.9/references/bastos_survey.md`. Each test builds the case it is named after, with a stated ground truth and an explicit `rng`.
- Common reference: a shared reference inflates coherence and Granger. Check: a test asserts both inflated against the same pair after `bipolar_reference`, with a stated ground truth and an explicit `rng`. Waits: tests only; records present behaviour.
- Volume conduction: zero-lag mixing keeps `imaginary_coherency` and `wpli` near zero while coherence is high. Check: a test asserts coherence above a stated floor and both measures below a stated bound. Waits: tests only; records present behaviour.
- SNR asymmetry: added noise on one channel yields a Granger direction with no true lag. Check: a test records today's direction and its docstring names the gap 11-04 closes. Waits: tests only; records present behaviour.
- Common input: a common driver with unequal delays makes bivariate Granger spurious, and conditional `granger` removes it. Check: a test asserts the spurious value and its removal. Waits: tests only; records present behaviour.
- Sample-size bias: the `pairwise_phase_consistency` and debiased wPLI null means stay near zero for every segment count. Check: a test asserts both below a stated bound at three or more segment counts. Waits: tests only; records present behaviour.
Accept: every pitfall statement of the `common_mistakes` pitfalls section is held by a test or names its gap.
Stop: a test would need a threshold no reference fixes.

### 10-12 Skills point to their sources

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: per skill. Blocked by: 10-06.
Writes: `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`.
- Each connectivity and spectral safeguard restates its method instead of naming its `docs/references.md` row. Check: the line test in `tests/test_skills_validation.py` finds no restated definition. Waits: pointers only.
- P-216 statistics part: the unscoped-delay paraphrase branch of `TestCausalFilterDelayIsScopedToAThresholdCrossing` (`tests/test_skills_validation.py`, lane G's file) is unpinned. Check: a test fails when that branch is removed. Waits: behaves correctly.
- A request to compare with published nonparametric Granger values meets no statement of the estimator difference. Check: a decline-behaviour case in `tests/test_skills_validation.py` finds the skill stating the difference as a decline or a qualification. Waits: skill text only.
Accept: routing rows still match signatures; the summed skill length does not grow.
Stop: a pointer would drop a safeguard's dimension that a routing row needs.

### 10-09 Display edges

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `tests/test_vis*.py`, `tests/test_visual_qc.py`, `tests/test_viz*.py`, `jnwb/unit_quality.py`, `tests/test_unit_quality.py`, `skills/jnwb-landmark-viz/SKILL.md`, `skills/jnwb-figures/SKILL.md`, `docs/vis.md`.
- P-244: `apply_tight_auto_axis` floors y at 0 (`jnwb/viz.py:46`), so data with minimum -5 is drawn outside the axes. Check: the floor applies only to non-negative data, and a test asserts `ylim[0] <= -5` for that case. Waits: display only, stated.
- P-313: the stability panel coerces with `astype(bool)` (`jnwb/visual_qc.py:323`), so a text flag plots every unit Stable. Check: a non-boolean flag raises a named error, asserted with string flags. Waits: display only.
- P-275: `tests/test_vis_draws_no_default_landmark.py` misses a `UnaryOp` default and a body fallback. Check: a planted fixture for each is rejected. Waits: the code has neither.
- Vis label edges: a full label in `plot_csd`'s `colorbar_title` doubles the unit; a whitespace-only title is accepted; the depth hover has no unit. Check: a title naming a unit raises, a whitespace-only title raises, and the depth hover names `depth_unit`, one test each. Waits: visibly contradictory, never silent.
- Vis range edges: the hierarchy hover's "%" removal is unpinned; `plot_spectrolaminar_map` draws infinities as gaps; an empty `rel_power` fails in numpy. Check: a test fails when the "%" removal is dropped, infinities raise, and an empty `rel_power` raises a named error. Waits: shipped hover correct.
- P-254: `Canvas.save_and_seal` loses its export on a loaded Windows machine when choreographer's shutdown budget expires; a serial run can hang at exit after a failed close; no test shows an export error reaching the caller. Check: one kaleido session per call; a serial run exits after a failed close; a test fails when the export error is swallowed; a later call fails fast. Waits: loud. Observed 2026-10-04 under xdist: on a loaded machine a `-n 12` run of `4be1792b` hung 17 minutes in a headless Chrome child of one worker, and after that child was killed the suite reported 0 failed, so a lost export did not reach the test that made it; whether that can make qualifying evidence falsely pass is for the closure pass to classify.
- P-280 ribbon: `docs/vis.md:73` and the `jnwb/vis/state_space.py:34` docstring promise a ribbon that `plot_decoding_timecourse` draws only when `ci_low` and `ci_high` are given. Check: both say so. Waits: wording.
- P-367: no test pins the `raster_psth` SEM value; a ddof=0 mutant and a mutant that drops the division by the square root of the trial count both pass all 423 tests in the 11 files that call it (found 2026-10-04 at `94334cb4`). Check: one hand-computed SEM test fails both mutants. Waits: display helper, value unchanged.
- P-332 display part: `plot_sorted_heatmap(category_labels=...)` is accepted and ignored (`jnwb/vis/spiking.py:245`). Check: the labels are drawn or the argument raises, asserted by a test. Waits: display.
- P-296 dated comments: `jnwb/visual_qc.py:13` names a date. Check: the line is deleted or shown to state behaviour. Waits: no behavioural effect.
- P-216 display part: the gradients crossover default and the `jnwb.vis` vocabulary beyond a grep are unpinned. Check: a test fails when the crossover default changes, and one pins the vocabulary. Waits: behaves correctly.
- Closure pass 2026-10-05: `plot_unit_waveforms(channels="peak")` takes the largest absolute deflection (`jnwb/visual_qc.py:95`) while `waveform_features` takes the largest max minus min (`jnwb/unit_quality.py:69`), so on a template where the rules differ the drawn and the reported peak channel differ. Check: both call one peak-channel rule (`AGENTS.md` 4.7), asserted on such a template. Waits: display only; the reported features are unchanged.
Accept: each check passes.
Stop: none beyond the standing ones.

### 10-14 A type oracle for documented call shapes

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `tests/test_docs_call_shapes.py`, `scripts/docs_form_gate.py`, `tests/test_skill_symbol_coverage.py`.
Split from the documentation-check item on 2026-10-04, which landed every other bullet.
- P-167 and P-84: P-79b, P-79c and P-82 are wrong-type calls that bind cleanly; the recorded call fragments use names the page never assigns (`lfp_segments`, `spike_trains`, `session_qc_list`). Ruled 2026-10-04 (Hamm): an annotation oracle over literals and page-assigned names, plus a small table of argument types for names a page never assigns. Check: `tests/test_docs_call_shapes.py` fails the oracle on all three calls. Waits: the documented calls are already corrected; the oracle guards recurrence.
- The nav reader `_nav_pages` of `tests/test_skill_symbol_coverage.py` reads commented `mkdocs.yml` lines as pages. Check: it calls the nav reader of `scripts/docs_form_gate.py`, and a planted commented line is not read as a page. Waits: no commented page exists.
Accept: each check passes.
Stop: the oracle needs a type that no annotation or table entry states.

### 10-15 Four published unit measures

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-qc. Blocked by: none.
Writes: `artifacts/evidence/0.2.9/unit_qc_inventory.md`, `jnwb/unit_quality.py`, `tests/test_unit_quality.py`, `skills/jnwb-qc/SKILL.md`.
Moved from the 0.2.9 inventory on 2026-10-04 (ruled). The code read was `E:/omission` at `c3d69375`, which copies the duration measure and the unit screen of the lab pipeline it cites (`yihan777/alpha_beta_mechanism@826e540`).
- Four published measures the copied screen applies and jnwb lacks: amplitude cut-off (Hill et al. 2011), half-width, repolarisation slope and spread (Jia et al. 2019). Check: each is a public operation by its published definition with a `docs/references.md` row, or a ruled exclusion recorded in `artifacts/evidence/0.2.9/unit_qc_inventory.md`. Waits: new capability, not a defect.
- Closure pass 2026-10-05: `refractory_contamination` says the Hill et al. (2011) derivation "is restated by Llobet et al. (2022)" (`jnwb/unit_quality.py:383`); Llobet's model differs from Hill's and the sentence was not checked against the paper. Check: the sentence matches the paper, or is deleted. Waits: citation wording; the computation follows Hill.
Accept: each check passes.
Stop: a new public operation, or a definition with more than one published form, needs Hamm's ruling.

### 07-08 The router composes the minimal skill set a task needs

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb. Blocked by: none.
Writes: `skills/jnwb/SKILL.md`, `skills/jnwb/agents/openai.yaml`, `tests/test_skill_router_reach.py`.
- 07-08: router section 2 maps each task phrase to one skill, so a multi-skill task reaches the first match. Check: a table of tasks and required skill sets passes in `tests/test_skill_router_reach.py`, with plotting supplied arrays reaching figures and QC, and a band comparison between conditions reaching paradigm, NWB data, spectral, statistics, figures and QC. Waits: router feature; no shipped behaviour changes.
Accept: the check passes.
Stop: a task needs a skill outside the fact stack's planned set.

### 07-09 Composition tests over the chains the router sequences

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: per chain. Blocked by: 07-08.
Writes: `tests/test_composition_*.py`.
- 07-09: no test composes two skills' operations in router order where each call is right and the order, an identifier or a substituted signal class is wrong. Check: the band-comparison task as one chain (the minimal base) in `tests/test_composition_*.py`; each chain runs on unequal dimensions, fails on the wrong composition and passes on the right one, and a chain correct today records its killing mutation in its docstring. Waits: new tests of new composition.
Accept: the check passes.
Stop: a chain is wrong today and its repair needs a path outside `Writes`.

# 0.2.12

Theme: the release apparatus is smaller and faster, and the repository carries no process
identifiers outside the stacks.

Acceptance: `AGENTS.md` §11; `scripts/` and the process tests are shorter than at `fe14858d` with
every gate still reported; no item or problem id outside `artifacts/` except machine-required
literals.

Every item here carries `deferred-0.2.10`, as in 0.2.10.

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| M gates | 12-09, 12-01 | `scripts/harness_gate.py` and its split, `scripts/stack_parse.py`, `scripts/stack_edit.py`, gate and stack tests |
| L release and CI | 12-02, 12-03, 12-05 | `scripts/release_gate.py`, `scripts/smoke_installed.py`, `scripts/measure_peak_memory.py`, the workflow, `CONTRIBUTING.md`, release tests, the process tests on the prune list, `scripts/measure_agents_md_duplication.py`, `scripts/reconstruct_state.py` |
| N mutation and references | 12-04, 12-08 | `scripts/mutation_harness.py`, `scripts/computational_contract_gate.py`, their tests, `scripts/build_fact_graph.py`, the fact gate test, `artifacts/fact_stack.md` |
| Z alone | 09-07, 12-07, 12-06 | the workflow, the harness and fact gates, their tests, `scripts/learning_gate.py`, `scripts/reconstruct_state.py`, `tests/test_learning_gate.py`, `tests/test_state_reconstruction.py`, `artifacts/defect_classes.md`, and every comment in `scripts/` and `tests/`; runs when no other lane is open |

12-02 starts once 12-09 is merged. Question round at the opening: the study-vocabulary values and
the 12-08 row wording.

### 12-09 One stack parser

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/stack_parse.py`, `scripts/stack_edit.py`, `scripts/harness_gate.py`, `tests/test_stack_metadata_contradictions.py`, `tests/test_stack_edit.py`.
- P-232: gates 15 and 17 read only `###` items while STEP 0a reads any depth. Check: one parser in `scripts/stack_parse.py`, imported by gates 15 and 17 and STEP 0a; a fixture with a `####` item is read by all three. Waits: the gates can only under-read.
- P-274: STEP 0a leaves four HTML heading forms unparsed. Check: the shared parser reads each form in a fixture. Waits: no HTML headings.
- Stack editor edges: `os.replace` raised WinError 5 once under load; no chained-edit test; a fence line can be removed; heading depth is capped at six where the gate takes any; non-breaking-space indents; the check-then-replace race and missing fsync. Check: a retry on a simulated WinError 5, a chained-edit test, a refused fence-line removal, one heading rule shared with the gate; each of the last two gets a test or a recorded reason. Waits: one call per edit reaches none of these.
Accept: gates 15 and 17 read `scripts/stack_parse.py` and pass; the stack tests pass.
Stop: the parser changes gate 15's or 17's verdict on any fixture.

### 12-01 Gates in their own modules

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 12-09.
Writes: `scripts/harness_gate.py`, `scripts/gates/**`, `tests/test_harness_adversarial_gates.py`, `tests/test_every_gate_runs.py`, `tests/test_gate*.py`, `tests/test_gates_reject_the_trees_they_passed.py`.
Plan: `artifacts/evidence/0.2.8/plan/restructure_plan.md` (a), scripts row.
- P-218: gate 2 excuses a counterfeit at a stale worktree registration. Check: gate 2 requires the admin `gitdir` to point back, and a planted stale registration fails. Waits: needs a counterfeit.
- P-219: gate 2's PASS message is narrower than its check. Check: the message names every condition checked. Waits: no verdict changes.
- P-235: the stated-gate-count test misses `skills/`, `docs/`, number words and ranges. Check: a planted wrong count in each of the four is reported. Waits: the live count is correct.
- P-295: gate 14's id pattern (`PROCESS_IDENTIFIER`) passes `items/06-55`, `P-1000` and `p-29`, and fails the date `09-23`. Check: the pattern flags the first three and not the date, one test each. Waits: live tree clean.
- P-311: gate 14 does not read `README.md` or follow `--8<--` includes. Check: gate 14 reads both, and a planted id in each fails. Waits: clean at `3f533574`.
- P-301: no test pins the removal of an external project's name from `jnwb/vis/sidecar.py`. Check: gate 6's token list holds the name, and a planted occurrence in that file fails. Waits: clean.
- P-342: gate 19 hashes a name's first definition only and accepts a wrongly-named killing test. Check: the last binding is hashed and each test id resolves to a collected test; a planted second binding and a planted wrong id each fail. Waits: no name bound twice.
- P-198: `run_full_preflight` (`scripts/harness_gate.py:3087`) de-duplication is unpinned. Check: a test fails when a duplicate hides a failure. Waits: a duplicate cannot hide a failure.
- P-304: gate 9's api sync is untested against a same-length drift, the contract gate against a doubly-categorised export, and `win_ms=` literals against `bin_ms`. Check: one fixture each, each reported. Waits: no evidence passes falsely.
- P-216 gate part: a second interpreter sentence (gate 8 reads the first) and `sys.modules.clear()` in the collection-order detector are unpinned. Check: a test reads the second sentence, and one fails when the call is dropped. Waits: behave correctly.
Accept: `python scripts/harness_gate.py` reports every gate PASS; the gate tests pass; the harness
is shorter.
Stop: a split changes a gate's verdict on any fixture.

### 12-02 The release gate reads the shared parser

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 12-09.
Writes: `scripts/release_gate.py`, `tests/test_release_requires_an_empty_problem_stack.py`, `tests/test_release_body_gate.py`, `tests/test_release_recovery_gates.py`, `tests/test_release_version_is_unpublished.py`, `tests/test_generation_closure_is_declared.py`.
- P-300: the STEP 0a message truncates item titles. Check: the message holds the whole title, asserted on a title longer than today's cut. Waits: wording only.
- P-302: a problem-shaped row outside `## Open` is not counted. Check: a planted row under another heading is counted. Waits: Open is fully checked.
- P-330: renaming a required id to a deferred one after the receipt reads as one done and one added. Check: STEP 0a refuses any id new since the receipt, and a planted rename fails. Waits: needs a deliberate rename.
- Readiness blind spots: a `##` section listing work outside any item; `--assume-unchanged` and `--skip-worktree` files; a job-level `continue-on-error` on TestPyPI. Check: each planted shape is refused. Waits: none present.
- RP-2: STEP 0e refused on an in-progress pull-request run while the push run for the commit passed. Check: a concluded green run for the exact commit suffices, and a test plants both runs. Waits: fails closed.
Accept: STEP 0a imports `scripts/stack_parse.py`; its tests pass.
Stop: the shared parser reads an item STEP 0a did not, or the reverse, on the live stack.

### 12-03 CI and release workflow

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 12-02.
Writes: `.github/workflows/workflow.yml`, `scripts/smoke_installed.py`, `scripts/measure_peak_memory.py`, `CONTRIBUTING.md`, `tests/test_workflow_release_policy.py`, `tests/test_ci_conclusion_gate.py`, `tests/test_import_provenance.py`, `tests/test_distribution_manifest_inspection.py`, `tests/test_dependency_floors_are_installable.py`, `tests/test_the_suite_can_qualify_an_installed_copy.py`, `tests/test_test_imports_survive_the_wheel_leg.py`.
- RP-7: no threshold on peak memory beside wall time in the suite step. Check: the workflow holds a threshold set from the recorded measurements (`artifacts/benchmarks/peak_memory.json`), and a test reads it. Waits: needs the 0.2.7 measurements first.
- CI guard hardening: exit-masking forms in the pytest steps, `set +e` in Resolve, a re-upgrade after the constrained install, only `env.FLOOR_PYTHON` checked, two copies of the browser retry. Check: a test refuses each of the five. Waits: each needs a deliberate workflow edit.
- Peak-memory reset evidence: a clear_refs write counts as a reset unobserved; the unwritable case is undocumented; the `ru_maxrss` fallback is unlabelled. Check: the write is re-read, the unwritable case has a row, the fallback has a label. Waits: every row is labelled correctly.
- Floor coverage: 3.12.0 runs only on the Ubuntu floors leg (`.github/workflows/workflow.yml:171`). Check: the workflow runs newest dependencies on 3.12.0 and a Windows 3.12.0 leg. Waits: the known defect class reaches the Ubuntu leg.
- One smoke definition: CI's smoke script and the release gate's installed-package script check different things. Check: one definition that both run; P-352 holds the suite-run half. Waits: each exercised where it runs.
- P-352: the release gate's smoke script runs only at step 7. Check: the suite runs it against the tree. Waits: fails closed.
- P-353 smoke half: the smoke step keeps `PYTHONPATH` where the tutorial step strips it. Check: the smoke step strips it. Waits: asserts a `site-packages` import.
- Release workflow edges: the smoke pass branch, export and extra checks are untested to failure; a yanked TestPyPI file passes the hash comparison; the verify job's one-wheel count is not asserted. Check: a failing test for each. Waits: each fails loudly in CI.
- P-309: the distribution tests read only `<repo>/dist` and do not reject `examples` or `data` components. Check: the tests accept an external build path and reject both components. Waits: the byte comparison held.
- P-328: `actions/*` are pinned to tags (`@v4`, `@v5`; `pypa/gh-action-pypi-publish` is already a SHA). Check: every `uses:` is a commit SHA, then the pin requirement is switched on. Waits: GitHub-owned and allow-listed.
- P-191: a contributor install without `vis` fails the `__all__` sweeps. Check: those tests skip names of absent extras. Waits: false failures only.
- P-197: the provenance scanners miss ten spellings and accept five prepend forms. Check: each is a fixture, or the installed-wheel leg is named as the check. Waits: the wheel leg catches a checkout-pinned test.
- Prepend scanner reach: slice assignment, rebinding, aliasing and non-zero indices are missed; the path-order assertion runs only when ordered after. Check: each form is flagged, and the assertion runs at session end. Waits: no such form exists.
Accept: each check passes; one CI run on `dev` is green.
Stop: a hardening would refuse the current workflow.

### 12-05 Process tests pruned and merged

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 12-01.
Writes: `artifacts/evidence/0.2.12/process_tests/**`, `tests/test_findings_ledger.py`, `tests/test_single_agent_instruction_file.py`, `tests/test_standing_rules_name_no_cycle.py`, `tests/test_agents_md_stays_a_router.py`, `scripts/measure_agents_md_duplication.py`, `tests/test_release_recovery_gates.py`, `tests/test_jrsa.py`, `tests/test_api_md_is_interpreter_independent.py`, `tests/test_workflow_release_policy.py`, `tests/test_state_reconstruction.py`, `tests/test_state_basis_is_checked.py`, `tests/test_xflip_calibration_receipt.py`, `tests/test_vflip_calibration_receipt.py`, `tests/test_test_imports_survive_the_wheel_leg.py`, `tests/test_the_suite_can_qualify_an_installed_copy.py`, `tests/test_errors_documented.py`, `tests/test_readme_smoke.py`, `scripts/reconstruct_state.py`.
Ruled 2026-09-29 (D12): the list is accepted, run after the gates split. The files are the ruled list, resolved against `artifacts/evidence/0.2.7/process_test_audit.md`.
- Process tests to prune or merge: 4 files to prune, 4 to merge, and four weaker checks a stronger test covers (the ruled list in this item's Writes). Check: each pruned case is shown held by a stronger test first, named in the audit. Waits: keeping tests cannot make evidence falsely pass.
- P-290: the ruled test taxonomy ("Testing rule", `CONTRIBUTING.md:191`) is enforced by nothing. Check: each kept process test is named under one probe class in the prune record; a taxonomy change goes to 12-06, which owns `CONTRIBUTING.md`. Waits: contributor rule only; nothing ships.
- Apparatus bound: `artifacts/goal.md` section 10 has no check. Check: `scripts/reconstruct_state.py` records the line counts of `scripts/` and the process tests, so growth is visible per release; a refusal is a new item's to add if Hamm asks. Waits: goal states it is unchecked; growth only.
Accept: the pruned files' cases are held by the stronger tests named in the audit.
Stop: a pruned test is the only one that kills some mutant.

### 12-04 Mutation and contract gate reach

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/mutation_harness.py`, `scripts/computational_contract_gate.py`, `tests/test_mutation_harness_validity.py`, `tests/test_computational_contract_gate.py`, `tests/test_substitution_class_sweep.py`.
- P-238: `collect_selector` drops node ids containing a space. Check: such an id is selectable, asserted by a test. Waits: fails closed.
- P-266: the contract gate tracks aliases without order and accepts one correct path among several. Check: aliasing is order-aware, and a planted wrong path beside a correct one fails. Waits: switch tests hold live behaviour.
Accept: each check passes.
Stop: none beyond the standing ones.

### 12-08 Every routed method cites a published source

Release: deferred-0.2.10.
AUTONOMY: none for the fact row; the graph edges are `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/build_fact_graph.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- The fact graph gains reference nodes and DOI-to-function edges read from `docs/references.md` (`scripts/build_fact_graph.py`). Check: a planted row with no function is reported. Waits: graph tooling; the fact row awaits Hamm.
- A proposed Science fact, every routed method cites a published source, held by `tests/test_references_resolve.py`. Check: Hamm approves the row and the fact gate reports it HELD. Waits: lands only on Hamm's approval.
Accept: the fact gate reports the row HELD, or it waits with Hamm's reason.
Stop: the fact stack is Hamm's; the row lands only on approval.

### 09-07 Checks for the defect classes review keeps finding

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/learning_gate.py`, `scripts/reconstruct_state.py`, `scripts/harness_gate.py`, `tests/test_learning_gate.py`, `tests/test_state_reconstruction.py`, `artifacts/defect_classes.md`.
Source: `artifacts/defect_classes.md`; each bullet is a class seen twice, or one whose check is cheap.
- ruling-cited-not-recorded: a "Ruled <date>" citation in `artifacts/` names a ruling its dated file lacks. Check: a gate reads every such citation and finds its row in `artifacts/rulings/<date>.md`; it is red on the 08-06 commit `8482c7bc`. Waits: process evidence only; no shipped behaviour.
- rewrite-drops-obligation: a rule-file rewrite loses an obligation its mapping calls kept. Check: for a mapping table with old and new columns, every obligation word (`before`, `after`, `never`, `must`, `only`) in an old rule appears in its new home; red on `8482c7bc` for D1 and D2. Waits: rule-file rewrites are rare and reviewed.
- second-home-contradiction: a ruled rule keeps its old form in another file. Check: each ruling row may name a forbidden phrase and the gate greps the repository for it; red on the pooling phrase before 08-07. Waits: every instance so far was found by review.
- Awareness in state: `artifacts/state.md` records the live worktrees and branches with their HEADs, the newest `CI/CD` run on `dev` with its conclusion, and the open defect classes. Check: the section is generated, and a stale worktree or a red run is named. Waits: the integrator reads these by hand today.
- The ledger is counted, not typed: `Seen` in `artifacts/defect_classes.md` equals its instances. Check: the gate recounts it. Waits: hand-kept today.
Accept: each check is red on the instance its bullet names and green on the live tree; the harness counts the new gate.
Stop: a check needs judgement a script cannot make; it stays a review rule instead.

### 12-07 Release and study-vocabulary facts held; no fact UNHELD

Release: deferred-0.2.10.
AUTONOMY: none for the study-vocabulary values; holder cells under the standing authorization of 2026-09-29; the rest is `max`.
Role: jnwb-developer. Skill: none. Blocked by: 12-01, 12-03, 12-05, 12-08.
Writes: `.github/workflows/workflow.yml`, `scripts/harness_gate.py`, `scripts/gates/**`, `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `tests/test_harness_gate_study_tokens.py`, `artifacts/fact_stack.md`.
- R2: a verify-pypi job after publish-pypi (fresh install from PyPI, sha256 equal to the tag run's artifact, `pip check`, the installed smoke test). Check: a planted hash mismatch fails the job's check function. Waits: the upload step checks sha256 against the verified TestPyPI copy.
- B2: gate 6 scans all of `jnwb/`, `docs/`, `skills/` and `tests/`; each hit is repaired or shown generic. Check: a planted study token in `tests/` fails. Waits: `tests/` is not in the wheel; shipped surfaces are scanned.
Accept: `scripts/fact_gate.py` prints UNHELD 0 and VIOLATED 0.
Stop: a workflow change would alter the ruled publication order.

### 12-06 No process identifiers outside the stacks

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 12-01, 12-02, 12-03, 12-04, 12-05, 12-07, 12-08, 12-09.
Writes: `scripts/*.py`, `tests/**/*.py`, `.github/workflows/workflow.yml`, `CONTRIBUTING.md`.
- P-284: 113 identifiers in 6 `scripts/` files and 562 in 87 test files cite item and problem ids (gate 14's `PROCESS_IDENTIFIER` at 72124e23; P-209 and IB-71 merged here). Check: each is removed or rewritten as a plain reason, then gate 14 reads both folders with an allowlist for machine-required literals. Waits: neither directory ships.
- P-102: line endings levelled across the tree if `artifacts/evidence/0.2.8/plan/decisions.md` D3 rules it, as the last commit of the cycle, since it touches every file. Check: gate 16 passes and one byte-mode edit per convention applies. Waits: waits on the D3 ruling; bytes only.
Accept: gate 14 passes on `scripts/` and `tests/`; the suite passes.
Stop: an id is a literal a parser fixture needs.

# 0.2.13

Theme: NWB reading and writing are complete: every container `inspect` lists is readable, and the
mutation and execution APIs ship in the shape Hamm rules.

Acceptance: `AGENTS.md` §11; 07-21 and 07-22 ship only in the ruled shape; each landed writer has a
re-read test and an ambiguity refusal.

Every item here carries `deferred-0.2.10`, as in 0.2.10.

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| I reading | 11-01 | `artifacts/evidence/0.2.11/**`, `jnwb/nwb_inspect.py`, `jnwb/nwb_io.py`, `jnwb/nwb_events.py`, `jnwb/io.py`, `jnwb/mcp_server/**`, their tests, `docs/errors.md`, `skills/jnwb-nwb-data/SKILL.md` |
| J files and tables | 11-02, 07-05 | `jnwb/compression.py`, `jnwb/metadata.py`, `jnwb/addressing.py`, `jnwb/ontology.py`, `jnwb/paths.py`, their tests, `docs/02_paths_addressing_metadata.md`, `skills/jnwb/SKILL.md`, `CONTRIBUTING.md` |
| K new APIs | 11-05, 07-21, 07-22, 11-03 | `jnwb/__init__.py`, `jnwb/_lazy_exports.py`, `mkdocs.yml`, new modules, their tests and pages, the fact gate and its test, `artifacts/fact_stack.md` holder cells |

Question round at the opening: the mutation set (07-21) and the execution and cache surface
(07-22) from 08-08's proposal.

### 11-01 Every container `inspect` lists is readable

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/nwb_inspect.py`, `jnwb/nwb_io.py`, `jnwb/nwb_events.py`, `jnwb/io.py`, `jnwb/mcp_server/**`, `tests/test_nwb_inspect.py`, `tests/test_nwb_read_tolerance_and_visibility.py`, `tests/test_nwb_events.py`, `tests/test_mcp_server.py`, `tests/test_io*.py`, `docs/errors.md`, `skills/jnwb-nwb-data/SKILL.md`.
- P-294: `acquisition_channel` does not resolve behavior containers under `processing/`. Check: it reads `processing/behavior/EyeTracking` of a planted file. Waits: loud.
- P-314: `BehavioralEvents` cannot be read by any name; `BehavioralEpochs` and ophys are unprobed. Check: one table covers every container `inspect` reports, and a test reads each. Waits: loud; same root as P-294.
- P-303: `inspect` of an in-memory file and the file walk unwrap different container sets. Check: one unwrap rule, and a test where both agree on every container. Waits: known types agree.
- P-299: `inspect` reports `packaging` `direct` for wrapped containers with nested `data_path`. Check: the label is the wrapped one, asserted by a test. Waits: vocabulary only.
- P-190: a series with `timestamps` and no constant `rate` raises `AcquisitionNotFoundError`. Check: it raises the class of `artifacts/evidence/0.2.8/plan/decisions.md` D8, asserted by a test. Waits: message true; a new class is API.
- P-204: `ContainerTypeContradictionWarning` blames the type when only the `uV` unit is wrong (78 of 96 corpus warnings). Check: a unit-scale case gives a message distinct from a type case (D8), one test each. Waits: errs toward caution.
- P-220: an empty `session_description` group raises `ValueError` under the waiver. Check: a missingness-table row and a named error, asserted by a test. Waits: fails loudly.
- P-336: no test pins the `channel_conversion` length refusal. Check: a test fails when the length check is dropped. Waits: behaves correctly.
- P-337: the unit warning names only `conversion=`, and the `starting_time` warning points at `nwb_inspect.py`. Check: the unit warning names both conversions and `stacklevel` puts both warnings at the caller, asserted by `warnings.catch_warnings` records. Waits: messages true.
- P-216 reading part: the `/acquisition` bare-name ambiguity refusal is unpinned. Check: a test fails when the refusal is dropped. Waits: behaves correctly.
- MCP signal reference edges: the reader check does not pin the channel axis; a `channel_conversion` outside the schema is reported but ignored; an infinite rate is accepted; the sweep row omits the reference tool's handler. Check: a test pins the axis, an out-of-schema `channel_conversion` and an infinite rate are refused, and the sweep row lists the handler. Waits: loud or outside the schema.
- P-289: the MCP writes-nothing test snapshots two directories, and the no-`jnwb.testing` check misses `importlib`. Check: a whole-tree snapshot and a runtime check. Waits: no current path does either.
- P-291: `stream_npz_array` accepts `Ellipsis` on 0-d where its docstring says `TypeError`. Check: the docstring says what the code does. Waits: value right.
Accept: each check passes.
Stop: reading a container would need to infer its meaning.

### 11-02 Compression, unit tables and addressing edges

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/compression.py`, `jnwb/metadata.py`, `jnwb/addressing.py`, `tests/test_compression.py`, `tests/test_metadata.py`, `tests/test_addressing.py`, `docs/02_paths_addressing_metadata.md`.
- P-296 dated comments: `jnwb/addressing.py:683` names a date. Check: the line is deleted or shown to state behaviour. Waits: no behavioural effect.
- P-283: `_timestamps_fate` does arithmetic with `None` when `rate` is absent. Check: a named refusal, asserted by a test. Waits: loud.
- P-298: a hard-linked timestamps array is neither collapsed nor refused. Check: links are resolved by object id, and a planted hard link is collapsed or refused. Waits: receipt consistent.
- P-324: `compress_fp32(select=)` on a SoftLink writes an independent copy. Check: the docstring says so or the call refuses, asserted by a test. Waits: pinned.
- P-338: a second link can open a cast irregular timestamps array. Check: refused or recorded per link, asserted by a test. Waits: opt-in, recorded.
- P-344: wall time rises 2.4x from 800 to 1600 series. Check: a measurement against HDF5 per-op cost accounts for the ratio, or the cause is found. Waits: linear op count.
- P-348: relative soft-link resolution, the soft-linked `select=` message and CUDA constant-channel NaN are unpinned. Check: a test fails when each is dropped. Waits: observed correct.
- P-192: `enrich_units_dataframe` without `peak_channel_id` fills Unknown silently. Check: a warning, and the prerequisite stated on the page (06-90). Waits: Unknown, not wrong.
- P-242: `unit_census_report` drops absent grouping columns silently. Check: a warning, asserted by a test. Waits: documented filter.
- P-312: `compare_old_new_criteria` mishandles nullable `is_stable`. Check: a nullable `is_stable` column is handled, asserted by a test. Waits: not exported.
- P-322: `get_all_units_metadata(filter_quality=True)` without `quality` raises where the CHANGELOG says a warning. Check: the call warns, asserted by a test. Waits: loud.
- `classify_layer_from_depth` reads electrode z as depth with no declared shallow end. Check: D10's ruling is applied and stated. Waits: stated; a ruling.
- P-216 addressing part: `VISp6a/b` splits into a spurious area. Check: a test of the split and a fix. Waits: no corpus here carries it.
Accept: each check passes.
Stop: a fix would name an area vocabulary.

### 07-05 A downstream paper agent can consume jnwb

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: per skill. Blocked by: 11-02.
Writes: `jnwb/ontology.py`, `jnwb/paths.py`, `tests/test_ontology.py`, `tests/test_paths.py`, `tests/test_paths_identity.py`, `skills/jnwb/SKILL.md`, `CONTRIBUTING.md`.
Ruled 2026-09-25: the paper agent lives downstream; jnwb gains only what it cannot do without.
- a. A script scores decline accuracy from `jnwb.preflight` alone: outcome, reason and missing inputs as data. Check: a test per outcome reads those three from the returned object (`tests/test_ontology.py`). Waits: new downstream capability.
- b. A result names its input's sha256 and object path, through `Provenance` or `Lineage` if they can carry it; IA-27's tests for `resolve_nwb_path`, `sha256_file` and `require` land here. Check: a round trip by path and hash passes. Waits: new downstream capability.
- c. `CONTRIBUTING.md` states the intake: a downstream miss classified as a jnwb defect enters the problem stack as a generic row with a synthetic discriminator. Check: `CONTRIBUTING.md` holds that sentence. Waits: new downstream capability.
- P-335: review the omission project's laminar curation pull request (ruled 2026-09-24) against the Boundary: composable parts, cited parameter defaults, micrometres, no project vocabulary. Check: the packet reports a pass or fail for each of the four. Waits: new downstream capability.
Accept: a test per outcome in (a); a round trip in (b) by path and hash; gate 6 passes.
Stop: a study, paradigm or DANDI id in `jnwb/`, `skills/` or `docs/`.

### 11-05 `ContainerTypeContradictionWarning` exported

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/__init__.py`, `jnwb/_lazy_exports.py`.
Ruled 2026-09-29 (D8 (a)): exported.
- P-221: `ContainerTypeContradictionWarning` (`jnwb/nwb_io.py:60`) is not exported. Check: it is in `jnwb.__all__`. Waits: changes no value.
Accept: the name is in `jnwb.__all__`; gates 5 and 9 pass.
Stop: none beyond the standing ones.

### 07-21 A public NWB mutation API

Release: deferred-0.2.10.
AUTONOMY: none until Hamm rules the set from 08-08.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/nwb_write.py`, `tests/test_nwb_write.py`, `docs/writing_nwb.md`, `mkdocs.yml`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`.
Accept: each landed operation re-reads its output and refuses an ambiguous mapping; API,
documentation and tests land before or with any skill.
Stop: anything that infers condition meaning, anatomy or units.
Waits: public API; Hamm rules the shape.

### 07-22 A public execution and cache API

Release: deferred-0.2.10.
AUTONOMY: none until Hamm rules the surface from 08-08.
Role: jnwb-developer. Skill: jnwb. Blocked by: 07-21.
Writes: `jnwb/execution.py`, `tests/test_execution_api.py`, `docs/execution.md`, `mkdocs.yml`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`.
Order, per the fact stack: numerical identity (08-08), then the public abstraction, then
performance evidence, then routing.
Accept: a cache key includes input hash, parameters and version, with an invalidation test; no
control changes a number.
Stop: a control would change a number.
Waits: public API; Hamm rules the surface.

### 11-03 Design facts held

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 07-22.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- D1: delegation edges for every public callable and each Analyzer method. Check: a planted two-step convenience is VIOLATED. Waits: fact reports UNHELD; nothing public claims it.
- D2 and D3: category tags on every operation with NWB or cache side effects, landing with 07-21 and 07-22. Check: an untagged planted writer is VIOLATED. Waits: metadata tags; waits on 07-21 and 07-22.
Accept: the Design table reports no UNHELD fact.
Stop: a category outside the ruled allowlists would be needed.

# 0.2.14

Theme: figures and tutorials, then the estimators and screens that wait on rulings or outside
inputs: the documentation shows its analyses as figures; the pitfall estimators are proposed and
land in the shapes Hamm rules; 13-04 waits for the collaborator's skill, 14-08 for access to the
lab pipeline, and 14-07 for a user who needs it.

Acceptance: `AGENTS.md` §11; every figure added follows the figure style ruled 2026-10-04, comes from
the docs generator in light and dark, and says in its caption whether it is synthetic; 13-04 and
14-07 land in the shape Hamm rules or are deleted.

Every item here carries `deferred-0.2.10`, as in 0.2.10.

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| A figures and tutorials | 14-01, 14-02, 14-03, 14-04, 14-05 | `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/03_representational_similarity_jrsa.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/coherence_and_tfr.md`, `docs/05_artifact_detection_and_repair.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md`, `docs/08_directed_connectivity_and_information.md`, `docs/common_mistakes.md`, `docs/tutorials/*.md`, `examples/tutorials/09_open_data.py`, `tests/test_synthetic_figures_are_labelled.py` |
| B estimators and screens | 11-04, 14-06, 13-04, 14-08 | `artifacts/evidence/0.2.11/pitfall_estimators_proposal.md`, `artifacts/evidence/0.2.9/unit_qc_inventory.md`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`, `jnwb/connectivity/**`, `jnwb/unit_quality.py`, their tests, `docs/references.md`, `docs/09_decoding_and_visual_qc.md`, `examples/notebooks/unit_quality.ipynb`; `docs/08_directed_connectivity_and_information.md` and `docs/common_mistakes.md` once 14-03 has landed |
| T trial correlation | 14-07 | `jnwb/spiking.py`, `tests/test_spiking.py`, `skills/jnwb-spiking/SKILL.md` |

Question round at the opening: the 11-04 shapes once its proposal exists, 13-04 against the
collaborator's skill, and whether any user needs 14-07.

### 14-01 Spectral and laminar figures

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/04_spectral_analysis_and_tfr.md`, `docs/coherence_and_tfr.md`, `docs/tutorials/06_laminar.md`.
Source: the "Top 10" list of the figure inventory of 2026-10-04, a read-only survey at `9cf0bb0f`,
numbered as there. Each figure is synthetic unless its bullet says otherwise, generated by
`docs/generate_figures.py` in the figure style ruled 2026-10-04 in light and dark, its caption naming each jnwb
function it calls.
- Inventory 10: the spectral page states Welch and multitaper PSDs in text only. Check: a figure of both with `CANONICAL_BANDS` shaded. Waits: documentation only; no number changes.
- Inventory 4: coherence, imaginary coherency and wPLI under zero-lag mixing are compared in text only. Check: a figure of the three on the coherence page. Waits: documentation only; no number changes.
- Inventory 6: the CSD and the vFLIP crossover have no figure. Check: CSD depth by time with the crossover (`current_source_density_1d`, `vflip_from_lfp`, `jnwb.testing.synth.synth_laminar_motif`, not `jnwb.vis.plot_csd`) on the spectral page and `docs/tutorials/06_laminar.md`. Waits: documentation only; no number changes.
Accept: the figure tests and `scripts/docs_form_gate.py` pass; each page shows its figures in light and dark.
Stop: a figure would need a function outside `jnwb.__all__`.

### 14-02 Spiking figures

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/common_mistakes.md`.
Source: as 14-01.
- Inventory 1: causal and Gaussian smoothing of a step differ by about 35 ms, stated in text only. Check: a figure of both (`causal_exp_smooth`, `gaussian_smooth_rate`, `fit_exponential_onset`) on the spiking page and in section 8 of `docs/common_mistakes.md`. Waits: documentation only; no number changes.
- Inventory 9: phase locking has no figure. Check: a spike-phase polar histogram with PLI and PPC on the spiking page. Waits: documentation only; no number changes.
Accept: the figure tests and `scripts/docs_form_gate.py` pass; each page shows its figures in light and dark.
Stop: a figure would need a function outside `jnwb.__all__`.

### 14-03 Inference and directed-connectivity figures

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/07_statistical_inference_and_nulls.md`, `docs/08_directed_connectivity_and_information.md`, `docs/common_mistakes.md`.
Source: as 14-01.
- Inventory 2: the cluster permutation test has no figure. Check: a TFR difference with the significant cluster outlined (`cluster_permutation_test`) on the inference page. Waits: documentation only; no number changes.
- Inventory 8: spectral Granger and the PSI trap are text only. Check: spectral Granger in both directions, and PSI narrowband against broadband, on the directed-connectivity page and in section 7 of `docs/common_mistakes.md`. Waits: documentation only; no number changes.
Accept: the figure tests and `scripts/docs_form_gate.py` pass; each page shows its figures in light and dark.
Stop: a figure would need a function outside `jnwb.__all__`.

### 14-04 Similarity and artifact figures

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/03_representational_similarity_jrsa.md`, `docs/05_artifact_detection_and_repair.md`.
Source: as 14-01.
- Inventory 5: RDMs and jRSA windows are text only. Check: two RDMs and a windowed jRSA trace against its null (`rdm`, `rdm_similarity`, `jrsa(null=)`) on the jRSA page, not through `JRSAResult.plot()`, whose figure size is fixed. Waits: documentation only; no number changes.
- Inventory 7: bad-channel and bad-trial detection have no figure. Check: the channel-correlation matrix, the flagged channels and the consensus bad-trial map on the artifact page. Waits: documentation only; no number changes.
Accept: the figure tests and `scripts/docs_form_gate.py` pass; each page shows its figures in light and dark.
Stop: a figure would need a function outside `jnwb.__all__`.

### 14-05 Tutorial figures through the docs generator

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/tutorials/*.md`, `examples/tutorials/09_open_data.py`, `tests/test_synthetic_figures_are_labelled.py`.
Ruled 2026-10-04: tutorial pages 00 to 09 get figures through the docs generator. Per the figure
inventory of 2026-10-04, tutorial 04 prints its PSD, TFR and wPLI, tutorial 06 its CSD, vFLIP, zFLIP
and xFLIP, and tutorial 09's clock table is text only.
- Tutorials 00 to 09 show no figure. Check: each page embeds a generated figure in light and dark, or this item records why the page needs none. Waits: documentation only; no number changes.
- Inventory 3, empirical: a PSTH by layer and 50-80 Hz dB by depth (`raster_psth`, `aggregate_to_db`) from the committed excerpt on the open-data tutorial. Check: the figure, and an EMPIRICAL entry for it in `tests/test_synthetic_figures_are_labelled.py`. Waits: documentation only; no number changes.
- `examples/tutorials/09_open_data.py` writes a light-only PNG to a temporary folder, outside the generator. Check: the figure comes from `docs/generate_figures.py` in light and dark. Waits: documentation only; no number changes.
Accept: the figure tests, `tests/test_open_data_example.py` and `scripts/docs_form_gate.py` pass.
Stop: a figure would need data the repository does not carry.

### 11-04 Proposals for the pitfall estimators

Release: deferred-0.2.10.
AUTONOMY: none for the shape; the proposal is `max`.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 10-11.
Writes: `artifacts/evidence/0.2.11/pitfall_estimators_proposal.md`.
Ruled 2026-09-29: all four in scope, each shape ruled before code.
- Nonparametric Granger by spectral factorization (Wilson), for comparison with the published values. Check: the proposal names the reference, the signature and a synthetic identity against the parametric path at the true order. Waits: public API; Hamm rules the shape.
- A time-reversed Granger control for SNR asymmetry. Check: the proposal states the decision rule and its reference. Waits: public API; Hamm rules the shape.
- Partial coherence conditioned on a third signal. Check: the proposal gives signature and reference. Waits: public API; Hamm rules the shape.
- A bias floor for coherence and Granger from randomly paired epochs (Vezoli et al. 2021). Check: the proposal gives signature, the pairing scheme and its `rng`. Waits: public API; Hamm rules the shape.
Accept: Hamm rules each shape; the implementation becomes its own item with API, docs and tests before any skill row.
Stop: public API; Hamm rules the shape.

### 14-06 The pitfall estimators Hamm rules

Release: deferred-0.2.10.
AUTONOMY: none until Hamm rules each shape from 11-04's proposal.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 11-04, 14-03.
Writes: `jnwb/connectivity/**`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`, `tests/test_connectivity.py`, `tests/test_connectivity_pitfalls.py`, `docs/08_directed_connectivity_and_information.md`, `docs/references.md`, `changelog.d/pitfall-estimators.added.md`.
11-04's acceptance makes the implementation its own item, with API, docs and tests before any skill row.
- The four estimators 11-04 proposes (`artifacts/evidence/0.2.11/pitfall_estimators_proposal.md`) have no implementation. Check: each ruled estimator ships with its signature, a `docs/references.md` row and a synthetic test, and the 10-11 test that names its gap asserts the repair. Waits: public API; nothing lands before the ruling.
Accept: the suite and harness pass; the packet reports the `docs/api.md` rows and the changelog text.
Stop: an estimator whose shape Hamm has not ruled.

### 13-04 A screen fitted to caller-supplied curation labels

Release: deferred-0.2.10.
AUTONOMY: none.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: the collaborator's label-learning skill, 14-03.
Writes: `jnwb/unit_quality.py`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`, `tests/test_unit_quality_screen.py`, `docs/09_decoding_and_visual_qc.md`, `docs/common_mistakes.md`, `examples/notebooks/unit_quality.ipynb`, `changelog.d/unit-quality-screen.added.md`.
Ruled 2026-10-03: decided later. When the collaborator's label-learning skill arrives, this
design and theirs go to Hamm, who rules the screen into the core or deletes this item so the
downstream skill composes 13-03's measures. Features are 13-03's measures
plus caller columns; labels are the caller's human index; `groups` is the session; `rng` is
required.
- Held-out agreement per session (balanced accuracy and Cohen's kappa against the labels), never pooled across sessions alone. Check: on a synthetic corpus whose sessions differ in label rate the pooled and per-session values differ, asserted in `tests/test_unit_quality_screen.py`. Waits: public API; nothing lands before the ruling.
- Declines when one label class is present, when fewer than two sessions exist, or when a feature is constant across units. Check: one test per refusal in `tests/test_unit_quality_screen.py`. Waits: public API; nothing lands before the ruling.
- The result names what it estimates: agreement with this curator's labels, not unit isolation. Check: the docstring and skill row say so, and a test reads the result's `estimand` field. Waits: public API; nothing lands before the ruling.
- The worked example's screen: the 0.2.9 notebook keeps the measures, the plot and the routing, and the screen with its per-session agreement table moved here on 2026-10-04. Check: `examples/notebooks/unit_quality.ipynb` applies the screen and shows held-out agreement per session, and runs under `tests/test_notebooks.py`. Waits: public API; nothing lands before the ruling.
Accept: the suite and harness pass; the downstream evaluation on the curated datasets is recorded downstream, with only its summary numbers in `artifacts/evidence/0.2.9/`.
Stop: the collaborator's skill reaches a different design; both go to Hamm.

### 14-08 Unit-curation rows only the lab pipeline holds

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-qc. Blocked by: access to the lab pipeline's code.
Writes: `artifacts/evidence/0.2.9/unit_qc_inventory.md`.
Split from 10-15 on 2026-10-05 (ruled): these rows are defined only in the lab pipeline (`yihan777/alpha_beta_mechanism@826e540`), which no one here can read.
- D1, D9 and the lab meaning of D3 ("mirrored") are defined only in the lab pipeline. Check: each row cites its code once its owner gives access. Waits: study-specific rows; jnwb's measures are unchanged.
Accept: each check passes.
Stop: none.

### 14-07 A trial-based noise correlation, if a user needs it

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: none.
Writes: `jnwb/spiking.py`, `tests/test_spiking.py`, `skills/jnwb-spiking/SKILL.md`.
Source: 09-08's conditional bullet, moved whole on 2026-10-04; 09-08 has since landed.
- A trial-based noise correlation (Cohen and Kohn's $r_{sc}$, counts per trial in a window) beside the time-bin form, if jaxfne or a study needs it. Check: Hamm rules whether it is a mode or a function. Waits: the docstring, references row and skill now say the time-bin form includes signal correlation.
Accept: the ruled form closed with a test, or the item deleted when no user needs it.
Stop: public API; Hamm rules the shape.
