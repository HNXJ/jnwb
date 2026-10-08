# 0.2.11

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. This
stack holds the current window only. Cycles 0.2.12 to 0.2.14 are one row per item in
`artifacts/roadmap.md`, and the full text of each is in `artifacts/archive/0.2.10/todo_stack_0.2.10.md`,
the stack as it stood when 0.2.10 closed. The previous cycle's record is
`artifacts/archive/0.2.9/todo_stack_0.2.9.md`, with its closure receipt beside it.

Theme: interpretation, routing and documentation hold: every interpretational pitfall has a
synthetic test, every skill points to its sources and composes with the router, displays and
documented call shapes are checked, and the identity and scientific-choice facts are held.

Acceptance: `AGENTS.md` §11; the facts 10-10 and 09-04 hold use the ruled lexicons; the router
composes the minimal skill set for each chain 07-09 tests; each published unit measure is a public
operation by its published definition or a ruled exclusion.

Every item here carries `deferred-0.2.11`, the one deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.10 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet, in the contract of `artifacts/skills/jnwb-fact-action` §5; role `jnwb-developer` unless named | a batched packet redefines the hard item |
| A lane is one worktree and one writer; lanes run one at a time per agent slot: one Claude subagent plus one opencode worker (ruling 2026-10-06); a lane's items run in the order listed | lanes never share a file, so they merge without conflict |
| A packet reproduces each bullet on its own tree first; a bullet that does not reproduce is deleted | non-reproduction is a result |
| The actor is never the verifier | every repair is re-run by someone else |
| The integrator owns the stacks, `CHANGELOG.md` and `docs/api.md` | packets report the disposition and the changelog text |
| Wave barrier: `python scripts/harness_gate.py` (count PASS lines), `python -m pytest tests/ -q`, commit, push, CI green on `dev` | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then `Do`, `Accept`, `Stop` as
needed; `AUTONOMY` and a one-line source or ruling note follow the fields they qualify. A bullet reads
`ID: defect, as input -> observed against expected, with numbers and units. Check: a predicate that
decides it, naming the file and the asserted value. Waits: why it cannot make release evidence
falsely pass.` `Waits:` appears in deferred cycles; `Waits: not stated.` marks a reason no source
gives, for the closure pass to classify. An item holds one defect and one check, in at most eight
lines.

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| Y identity facts | 10-10, 11-06, 09-04, 11-07, 11-08, 11-09, 11-32 | `jnwb/__init__.py`, `jnwb/compression.py`, `jnwb/_declarations.py`, the fact gate and its test, `artifacts/fact_stack.md` holder cells |
| G pitfalls and skill sources | 10-11, 11-10, 11-11, 11-12, 11-13, 11-31, 10-12, 11-14, 11-29 | `tests/test_connectivity_pitfalls.py`, `tests/test_substitution_class_sweep.py`, `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-population/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md` |
| D display, documentation and unit measures | 11-34, 10-29, 10-09, 11-16, 11-17, 11-18, 11-19, 11-20, 11-21, 11-22, 11-30, 11-24, 11-25, 11-26, 10-14, 11-27, 10-15, 11-28 | `jnwb/wavemap.py`, `tests/test_wavemap.py`, `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `jnwb/unit_quality.py`, their tests, `skills/jnwb-landmark-viz/SKILL.md`, `skills/jnwb-figures/SKILL.md`, `skills/jnwb-qc/SKILL.md`, `docs/vis.md`, `tests/test_docs_call_shapes.py`, `scripts/docs_form_gate.py`, `tests/test_skill_symbol_coverage.py`, `artifacts/evidence/0.2.9/unit_qc_inventory.md`, `artifacts/changelog.d/psi-roundoff-width.changed.md` |
| P skills composition | 07-08, 07-09 | `skills/jnwb/SKILL.md`, `skills/jnwb/agents/openai.yaml`, `tests/test_skill_router_reach.py`, `tests/test_composition_*.py` |

Question round at the opening: the B3 choice-name lexicon (10-10) and the dB-lexicon values 09-04
reads.

### 10-29 The PSI round-off width change is in the changelog

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/changelog.d/psi-roundoff-width.changed.md`.
Left by the 0.2.10 closure pass (2026-10-07); shipped values change only when the jackknife spread is at rounding level.
- The PSI round-off width changed from `8 n eps P` to `4 n eps P sqrt(U-1)` (commit `c62fa430`) and the 0.2.10 section does not say so. Check: a changelog entry names the change and its effect on the NaN decision. Waits: it decides NaN against finite z only at rounding-level spread.
Accept: the entry is in the changelog. Stop: none.

### 10-10 Every numeric public operation declares signature types that compose

Release: deferred-0.2.11.
AUTONOMY: none for the B3 lexicon values; holder cells under the standing authorization of 2026-09-29; the rest is `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `jnwb/_declarations.py`, `artifacts/fact_stack.md`.
- I1: declared signature types for every numeric public operation, and type-checked composition edges (`jnwb/_declarations.py`). Check: a planted spikes-to-LFP-only edge is reported VIOLATED by `tests/test_fact_gate.py`. Waits: fact reports UNHELD; nothing public claims it.
Accept: the planted spikes-to-LFP-only edge is reported VIOLATED and the Identity table reports no UNHELD fact. Stop: a declaration would change a public signature without a ruling.

### 11-06 A defaulted `window=` in a public function has a cited reason in the B3 table

Release: deferred-0.2.11.
AUTONOMY: none for the B3 lexicon values; holder cells under the standing authorization of 2026-09-29; the rest is `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `jnwb/_declarations.py`, `artifacts/fact_stack.md`.
- B3: the lexicon and exceptions table. Check: a planted public function with a defaulted `window=` and no cited reason in the table is VIOLATED by `tests/test_fact_gate.py`. Waits: fact reports UNHELD; nothing public claims it.
Accept: the planted defaulted-`window=` function with no cited reason is VIOLATED and B3 reports no UNHELD fact. Stop: a declaration would change a public signature without a ruling.

### 09-04 The claim-class text check reports the planted 0.2.7 fig09 unit as VIOLATED

Release: deferred-0.2.11.
AUTONOMY: none for the dB-lexicon values; holder cells under the standing authorization of 2026-09-29; the scans are `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- S8: claim classes and the text check over docs, skills, figure labels and docstrings. Check: `scripts/fact_gate.py` reports the 0.2.7 fig09 unit, planted, as VIOLATED. Waits: fact reports UNHELD; nothing public claims it.
Accept: the planted 0.2.7 fig09 unit is reported VIOLATED by `scripts/fact_gate.py` and S8 reports no UNHELD fact. Stop: a scan would need a scientific criterion not ruled in Q12 or Q13.

### 11-07 Each of the S1, S2, S5 and S7 scans reports its own planted case

Release: deferred-0.2.11.
AUTONOMY: none for the dB-lexicon values; holder cells under the standing authorization of 2026-09-29; the scans are `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- S1, S2, S5 and S7: the scans as ruled in Q13. Check: each scan reports its own planted case in `tests/test_fact_gate.py`. Waits: fact reports UNHELD; nothing public claims it.
Accept: each scan reports its own planted case in `tests/test_fact_gate.py` and S1, S2, S5 and S7 report no UNHELD fact. Stop: a scan would need a scientific criterion not ruled in Q12 or Q13.

### 11-08 A domain skill with fewer than three exclusive operations is VIOLATED by K1

Release: deferred-0.2.11.
AUTONOMY: none for the dB-lexicon values; holder cells under the standing authorization of 2026-09-29; the scans are `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- K1: the partition with k = 3 exclusive operations per shipped domain skill. Check: a planted two-operation skill is VIOLATED. Waits: skill-partition check; no shipped behaviour.
Accept: the planted two-operation skill is VIOLATED and K1 reports no UNHELD fact. Stop: a scan would need a scientific criterion not ruled in Q12 or Q13.

### 11-09 A planned skill is reported only when K1 and K5 hold for it

Release: deferred-0.2.11.
AUTONOMY: none for the dB-lexicon values; holder cells under the standing authorization of 2026-09-29; the scans are `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- Planned skills (moved from the fact stack as plan, Q14): twelve, the ten of 0.2.6 with `jnwb-landmark-viz` included (ruled 2026-09-22, P-180), plus `jnwb-paradigm` (experiment and timing semantics) and `jnwb-qc` (independent scientific and output QC); `jnwb-data-engineering` and `jnwb-compute` wait on their public APIs and neither is a required endpoint: a capability the router routes cleanly gets no skill. Check: the fact gate reports a planned skill only when K1 and K5 hold for it. Waits: plan for future skills; no shipped behaviour.
Accept: the fact gate reports a planned skill only when K1 and K5 hold for it, and the planned-skill fact reports no UNHELD. Stop: a scan would need a scientific criterion not ruled in Q12 or Q13.

### 10-11 A shared reference inflates coherence and Granger on the same pair

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `tests/test_connectivity_pitfalls.py`.
Source: table 2 of `artifacts/evidence/0.2.9/references/bastos_survey.md`. Each test builds the case it is named after, with a stated ground truth and an explicit `rng`.
- Common reference: a shared reference inflates coherence and Granger. Check: a test asserts both inflated against the same pair after `bipolar_reference`, with a stated ground truth and an explicit `rng`. Waits: tests only; records present behaviour.
Accept: a test asserts both inflated against the same pair after `bipolar_reference`, and this pitfall statement of the `common_mistakes` pitfalls section is held by a test or names its gap. Stop: a test would need a threshold no reference fixes.

### 11-10 Zero-lag mixing keeps `imaginary_coherency` and `wpli` near zero while coherence is high

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `tests/test_connectivity_pitfalls.py`.
Source: table 2 of `artifacts/evidence/0.2.9/references/bastos_survey.md`. Each test builds the case it is named after, with a stated ground truth and an explicit `rng`.
- Volume conduction: zero-lag mixing keeps `imaginary_coherency` and `wpli` near zero while coherence is high. Check: a test asserts coherence above a stated floor and both measures below a stated bound. Waits: tests only; records present behaviour.
Accept: a test asserts coherence above a stated floor and both measures below a stated bound. Stop: a test would need a threshold no reference fixes.

### 11-11 Added noise on one channel yields a Granger direction with no true lag, recorded by a test

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `tests/test_connectivity_pitfalls.py`.
Source: table 2 of `artifacts/evidence/0.2.9/references/bastos_survey.md`. Each test builds the case it is named after, with a stated ground truth and an explicit `rng`.
- SNR asymmetry: added noise on one channel yields a Granger direction with no true lag. Check: a test records today's direction and its docstring names the gap 11-04 closes. Waits: tests only; records present behaviour.
Accept: a test records today's direction and its docstring names the gap 11-04 closes. Stop: a test would need a threshold no reference fixes.

### 11-12 A common driver with unequal delays makes bivariate Granger spurious and conditional `granger` removes it

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `tests/test_connectivity_pitfalls.py`.
Source: table 2 of `artifacts/evidence/0.2.9/references/bastos_survey.md`. Each test builds the case it is named after, with a stated ground truth and an explicit `rng`.
- Common input: a common driver with unequal delays makes bivariate Granger spurious, and conditional `granger` removes it. Check: a test asserts the spurious value and its removal. Waits: tests only; records present behaviour.
Accept: a test asserts the spurious value and its removal. Stop: a test would need a threshold no reference fixes.

### 11-13 The `pairwise_phase_consistency` and debiased wPLI null means stay near zero at every segment count

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `tests/test_connectivity_pitfalls.py`.
Source: table 2 of `artifacts/evidence/0.2.9/references/bastos_survey.md`. Each test builds the case it is named after, with a stated ground truth and an explicit `rng`.
- Sample-size bias: the `pairwise_phase_consistency` and debiased wPLI null means stay near zero for every segment count. Check: a test asserts both below a stated bound at three or more segment counts. Waits: tests only; records present behaviour.
Accept: a test asserts both null means below a stated bound at three or more segment counts. Stop: a test would need a threshold no reference fixes.

### 11-31 Every pitfall row of the `common_mistakes` pitfalls table is held by a test or names its gap

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `tests/test_connectivity_pitfalls.py`.
Source: `docs/common_mistakes.md` lines 427-437, the nine rows: common reference, volume conduction, signal-to-noise asymmetry, common input, bivariate against conditional Granger, sample-size bias, phase slope as direction, filtering before Granger and non-stationarity.
- Phase slope as direction, filtering before Granger and non-stationarity are named by none of 10-11 and 11-10 to 11-13. Check: a test in `tests/test_connectivity_pitfalls.py` holds each of the nine rows, or its docstring names the gap. Waits: tests only; records present behaviour.
Accept: every pitfall statement of the `common_mistakes` pitfalls section is held by a test or names its gap. Stop: a test would need a threshold no reference fixes.

### 10-12 Each connectivity and spectral safeguard names its `docs/references.md` row

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: per skill. Blocked by: none.
Writes: `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`.
- Each connectivity and spectral safeguard restates its method instead of naming its `docs/references.md` row. Check: the line test in `tests/test_skills_validation.py` finds no restated definition. Waits: pointers only.
Accept: the line test in `tests/test_skills_validation.py` finds no restated definition; routing rows still match signatures and the summed skill length does not grow. Stop: a pointer would drop a safeguard's dimension that a routing row needs.

### 11-14 The unscoped-delay branch of `TestCausalFilterDelayIsScopedToAThresholdCrossing` is pinned

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: per skill. Blocked by: none.
Writes: `tests/test_skills_validation.py`.
- P-216 statistics part: the unscoped-delay paraphrase branch of `TestCausalFilterDelayIsScopedToAThresholdCrossing` (`tests/test_skills_validation.py`, lane G's file) is unpinned. Check: a test fails when that branch is removed. Waits: behaves correctly.
Accept: a test fails when the unscoped-delay branch is removed. Stop: none.

### 11-29 A request for published nonparametric Granger values meets a statement of the estimator difference

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: per skill. Blocked by: none.
Writes: `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`.
- A request to compare with published nonparametric Granger values meets no statement of the estimator difference. Check: a decline-behaviour case in `tests/test_skills_validation.py` finds the skill stating the difference as a decline or a qualification. Waits: skill text only.
Accept: a decline-behaviour case in `tests/test_skills_validation.py` finds the skill stating the difference as a decline or a qualification; routing rows still match signatures and the summed skill length does not grow. Stop: none.

### 10-09 `apply_tight_auto_axis` draws data with minimum -5 inside the axes

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/viz.py`, `tests/test_viz*.py`, `skills/jnwb-landmark-viz/SKILL.md`, `skills/jnwb-figures/SKILL.md`.
- P-244: `apply_tight_auto_axis` floors y at 0 (`jnwb/viz.py:46`), so data with minimum -5 is drawn outside the axes. Check: the floor applies only to non-negative data, and a test asserts `ylim[0] <= -5` for that case. Waits: display only, stated.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-16 A text flag in the stability panel raises instead of plotting every unit Stable

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/visual_qc.py`, `tests/test_visual_qc.py`.
- P-313: the stability panel coerces with `astype(bool)` (`jnwb/visual_qc.py:323`), so a text flag plots every unit Stable. Check: a non-boolean flag raises a named error, asserted with string flags. Waits: display only.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-17 `tests/test_vis_draws_no_default_landmark.py` rejects a `UnaryOp` default and a body fallback

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `tests/test_vis_draws_no_default_landmark.py`.
- P-275: `tests/test_vis_draws_no_default_landmark.py` misses a `UnaryOp` default and a body fallback. Check: a planted fixture for each is rejected. Waits: the code has neither.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-18 `plot_csd` rejects a unit-bearing or blank `colorbar_title` and the depth hover names `depth_unit`

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/vis/**`, `tests/test_vis*.py`.
- Vis label edges: a full label in `plot_csd`'s `colorbar_title` doubles the unit; a whitespace-only title is accepted; the depth hover has no unit. Check: a title naming a unit raises, a whitespace-only title raises, and the depth hover names `depth_unit`, one test each. Waits: visibly contradictory, never silent.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-19 The hierarchy hover's "%" removal is pinned, infinities raise and an empty `rel_power` raises

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/vis/**`, `tests/test_vis*.py`.
- Vis range edges: the hierarchy hover's "%" removal is unpinned; `plot_spectrolaminar_map` draws infinities as gaps; an empty `rel_power` fails in numpy. Check: a test fails when the "%" removal is dropped, infinities raise, and an empty `rel_power` raises a named error. Waits: shipped hover correct.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-20 `Canvas.save_and_seal` loses no export on a loaded machine and an export error reaches the caller

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/vis/**`, `tests/test_vis*.py`, `tests/test_viz*.py`.
- P-254: `Canvas.save_and_seal` loses its export on a loaded Windows machine when choreographer's shutdown budget expires; a serial run can hang at exit after a failed close; no test shows an export error reaching the caller. Check: one kaleido session per call; a serial run exits after a failed close; a test fails when the export error is swallowed; a later call fails fast. Waits: loud. Observed 2026-10-04 under xdist: on a loaded machine a `-n 12` run of `4be1792b` hung 17 minutes in a headless Chrome child of one worker, and after that child was killed the suite reported 0 failed, so a lost export did not reach the test that made it; whether that can make qualifying evidence falsely pass is for the closure pass to classify.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-21 `docs/vis.md` and the `state_space.py` docstring say the ribbon needs `ci_low` and `ci_high`

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `docs/vis.md`, `jnwb/vis/state_space.py`.
- P-280 ribbon: `docs/vis.md:73` and the `jnwb/vis/state_space.py:34` docstring promise a ribbon that `plot_decoding_timecourse` draws only when `ci_low` and `ci_high` are given. Check: both say so. Waits: wording.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-22 A hand-computed `raster_psth` SEM test kills the ddof=0 and the no-square-root mutants

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `tests/test_vis*.py`, `tests/test_viz*.py`.
- P-367: no test pins the `raster_psth` SEM value; a ddof=0 mutant and a mutant that drops the division by the square root of the trial count both pass all 423 tests in the 11 files that call it (found 2026-10-04 at `94334cb4`). Check: one hand-computed SEM test fails both mutants. Waits: display helper, value unchanged.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-30 `plot_sorted_heatmap(category_labels=...)` draws the labels or raises

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/vis/spiking.py`, `tests/test_vis*.py`.
- P-332 display part: `plot_sorted_heatmap(category_labels=...)` is accepted and ignored (`jnwb/vis/spiking.py:245`). Check: the labels are drawn or the argument raises, asserted by a test. Waits: display.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-24 `jnwb/visual_qc.py:13` names no date

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/visual_qc.py`.
- P-296 dated comments: `jnwb/visual_qc.py:13` names a date. Check: the line is deleted or shown to state behaviour. Waits: no behavioural effect.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-25 The gradients crossover default and the `jnwb.vis` vocabulary are pinned by tests

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/vis/**`, `tests/test_vis*.py`.
- P-216 display part: the gradients crossover default and the `jnwb.vis` vocabulary beyond a grep are unpinned. Check: a test fails when the crossover default changes, and one pins the vocabulary. Waits: behaves correctly.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-26 `plot_unit_waveforms` and `waveform_features` use one peak-channel rule

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/visual_qc.py`, `jnwb/unit_quality.py`, `tests/test_visual_qc.py`, `tests/test_unit_quality.py`.
- Closure pass 2026-10-05: `plot_unit_waveforms(channels="peak")` takes the largest absolute deflection (`jnwb/visual_qc.py:95`) while `waveform_features` takes the largest max minus min (`jnwb/unit_quality.py:69`), so on a template where the rules differ the drawn and the reported peak channel differ. Check: both call one peak-channel rule (`AGENTS.md` 4.7), asserted on such a template. Waits: display only; the reported features are unchanged.
Accept: the check passes. Stop: none beyond the standing ones.

### 10-14 The documented call shapes are type-checked by an annotation oracle

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `tests/test_docs_call_shapes.py`, `scripts/docs_form_gate.py`, `tests/test_skill_symbol_coverage.py`.
Split from the documentation-check item on 2026-10-04, which landed every other bullet.
- P-167 and P-84: P-79b, P-79c and P-82 are wrong-type calls that bind cleanly; the recorded call fragments use names the page never assigns (`lfp_segments`, `spike_trains`, `session_qc_list`). Ruled 2026-10-04 (Hamm): an annotation oracle over literals and page-assigned names, plus a small table of argument types for names a page never assigns. Check: `tests/test_docs_call_shapes.py` fails the oracle on all three calls. Waits: the documented calls are already corrected; the oracle guards recurrence.
Accept: the check passes. Stop: the oracle needs a type that no annotation or table entry states.

### 11-27 `_nav_pages` does not read commented `mkdocs.yml` lines as pages

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `tests/test_skill_symbol_coverage.py`, `scripts/docs_form_gate.py`.
Split from the documentation-check item on 2026-10-04, which landed every other bullet.
- The nav reader `_nav_pages` of `tests/test_skill_symbol_coverage.py` reads commented `mkdocs.yml` lines as pages. Check: it calls the nav reader of `scripts/docs_form_gate.py`, and a planted commented line is not read as a page. Waits: no commented page exists.
Accept: the check passes. Stop: none.

### 10-15 The four published unit measures are public operations or ruled exclusions

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-qc. Blocked by: none.
Writes: `artifacts/evidence/0.2.9/unit_qc_inventory.md`, `jnwb/unit_quality.py`, `tests/test_unit_quality.py`, `skills/jnwb-qc/SKILL.md`.
Moved from the 0.2.9 inventory on 2026-10-04 (ruled). The code read was `E:/omission` at `c3d69375`, which copies the duration measure and the unit screen of the lab pipeline it cites (`yihan777/alpha_beta_mechanism@826e540`).
- Four published measures the copied screen applies and jnwb lacks: amplitude cut-off (Hill et al. 2011), half-width, repolarisation slope and spread (Jia et al. 2019). Check: each is a public operation by its published definition with a `docs/references.md` row, or a ruled exclusion recorded in `artifacts/evidence/0.2.9/unit_qc_inventory.md`. Waits: new capability, not a defect.
Accept: the check passes. Stop: a new public operation, or a definition with more than one published form, needs Hamm's ruling.

### 11-28 The `refractory_contamination` sentence on Llobet et al. (2022) matches the paper

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-qc. Blocked by: none.
Writes: `jnwb/unit_quality.py`, `tests/test_unit_quality.py`, `skills/jnwb-qc/SKILL.md`.
Moved from the 0.2.9 inventory on 2026-10-04 (ruled). The code read was `E:/omission` at `c3d69375`, which copies the duration measure and the unit screen of the lab pipeline it cites (`yihan777/alpha_beta_mechanism@826e540`).
- Closure pass 2026-10-05: `refractory_contamination` says the Hill et al. (2011) derivation "is restated by Llobet et al. (2022)" (`jnwb/unit_quality.py:383`); Llobet's model differs from Hill's and the sentence was not checked against the paper. Check: the sentence matches the paper, or is deleted. Waits: citation wording; the computation follows Hill.
Accept: the check passes. Stop: a new public operation, or a definition with more than one published form, needs Hamm's ruling.

### 07-08 The router composes the minimal skill set a task needs

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb. Blocked by: none.
Writes: `skills/jnwb/SKILL.md`, `skills/jnwb/agents/openai.yaml`, `tests/test_skill_router_reach.py`.
- 07-08: router section 2 maps each task phrase to one skill, so a multi-skill task reaches the first match. Check: a table of tasks and required skill sets passes in `tests/test_skill_router_reach.py`, with plotting supplied arrays reaching figures and QC, and a band comparison between conditions reaching paradigm, NWB data, spectral, statistics, figures and QC. Waits: router feature; no shipped behaviour changes.
Accept: the check passes. Stop: a task needs a skill outside the fact stack's planned set.

### 07-09 Composition tests cover the chains the router sequences

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: per chain. Blocked by: 07-08.
Writes: `tests/test_composition_*.py`.
- 07-09: no test composes two skills' operations in router order where each call is right and the order, an identifier or a substituted signal class is wrong. Check: the band-comparison task as one chain (the minimal base) in `tests/test_composition_*.py`; each chain runs on unequal dimensions, fails on the wrong composition and passes on the right one, and a chain correct today records its killing mutation in its docstring. Waits: new tests of new composition.
Accept: the check passes. Stop: a chain is wrong today and its repair needs a path outside `Writes`.

### 11-32 Each fact citing `todo:09-04` or `todo:10-10` names an item whose bullet states its work

Release: deferred-0.2.11.
AUTONOMY: none; holder cells belong to Hamm.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/fact_stack.md`, `artifacts/todo_stack.md`.
- S9 to S14, K4, I2 and I3 cite `todo:09-04` or `todo:10-10` though no bullet of those items names them (renaming 09-04 makes the fact gate report VIOLATED 8). Check: each such fact's holder names an item whose bullet states that fact's work. Waits: holder cells belong to Hamm; edit only with his authorisation.
Accept: each such holder names an item whose bullet states that fact's work. Stop: a holder cell would change without Hamm's authorisation.

### 11-34 `wavemap_resolution_sweep` takes the `metric` that `wavemap` takes

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-qc. Blocked by: none.
Writes: `jnwb/wavemap.py`, `tests/test_wavemap.py`, `skills/jnwb-qc/SKILL.md`, `docs/api.md`.
- The sweep fixes `metric="euclidean"` (`jnwb/wavemap.py`, signature of `wavemap_resolution_sweep`), so a caller who clusters with another metric cannot sweep with it. Check: a test passes a non-default `metric` to both and the graph differs from the euclidean one. Waits: tests only.
Accept: the sweep and `wavemap` take the same `metric`; the routing row and `docs/api.md` agree. Stop: a metric the UMAP backend refuses.
