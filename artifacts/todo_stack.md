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
| G pitfalls and skill sources | 10-12, 11-29, 11-37, 11-38, 11-39, 11-40 | `tests/test_connectivity_pitfalls.py`, `tests/test_substitution_class_sweep.py`, `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-population/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md` |
| D display, documentation and unit measures | 11-20, 11-42, 11-43, 11-25, 10-14, 10-15 | `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `jnwb/unit_quality.py`, their tests, `skills/jnwb-landmark-viz/SKILL.md`, `skills/jnwb-figures/SKILL.md`, `skills/jnwb-qc/SKILL.md`, `docs/vis.md`, `tests/test_docs_call_shapes.py`, `scripts/docs_form_gate.py`, `tests/test_skill_symbol_coverage.py`, `artifacts/evidence/0.2.9/unit_qc_inventory.md` |
| P skills composition | 07-08, 07-09 | `skills/jnwb/SKILL.md`, `skills/jnwb/agents/openai.yaml`, `tests/test_skill_router_reach.py`, `tests/test_composition_*.py` |
| W waveform provenance | 11-41 | `artifacts/evidence/0.2.11/frozen-waveform-disposition.md`, `jnwb/nwb_integrity.py`, `tests/test_nwb_integrity.py` |

Question round at the opening: the B3 choice-name lexicon (10-10) and the dB-lexicon values 09-04
reads.

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







### 10-12 Each connectivity and spectral safeguard names its `docs/references.md` row

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: per skill. Blocked by: none.
Writes: `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`.
- Each connectivity and spectral safeguard restates its method instead of naming its `docs/references.md` row. Check: the line test in `tests/test_skills_validation.py` finds no restated definition. Waits: pointers only.
Accept: the line test in `tests/test_skills_validation.py` finds no restated definition; routing rows still match signatures and the summed skill length does not grow. Stop: a pointer would drop a safeguard's dimension that a routing row needs.

### 11-29 A request for published nonparametric Granger values meets a statement of the estimator difference

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: per skill. Blocked by: none.
Writes: `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`.
- A request to compare with published nonparametric Granger values meets no statement of the estimator difference. Check: a decline-behaviour case in `tests/test_skills_validation.py` finds the skill stating the difference as a decline or a qualification. Waits: skill text only.
Accept: a decline-behaviour case in `tests/test_skills_validation.py` finds the skill stating the difference as a decline or a qualification; routing rows still match signatures and the summed skill length does not grow. Stop: none.

### 11-20 `Canvas.save_and_seal` loses no export on a loaded machine and an export error reaches the caller

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/vis/**`, `tests/test_vis*.py`, `tests/test_viz*.py`.
- P-254: `Canvas.save_and_seal` loses its export on a loaded Windows machine when choreographer's shutdown budget expires; a serial run can hang at exit after a failed close; no test shows an export error reaching the caller. Check: one kaleido session per call; a serial run exits after a failed close; a test fails when the export error is swallowed; a later call fails fast. Waits: loud. Observed 2026-10-04 under xdist: on a loaded machine a `-n 12` run of `4be1792b` hung 17 minutes in a headless Chrome child of one worker, and after that child was killed the suite reported 0 failed, so a lost export did not reach the test that made it; whether that can make qualifying evidence falsely pass is for the closure pass to classify.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-42 `plot_sorted_heatmap` checks `colorbar_title` with the rule `plot_csd` uses

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/vis/spiking.py`, `jnwb/vis/laminar.py`, `jnwb/vis/theme.py`, `tests/test_vis*.py`.
- Review of 11-18 (2026-10-10): `plot_sorted_heatmap` (`jnwb/vis/spiking.py:275`) passes `colorbar_title` to `unit_label` unchecked, so a title naming `value_unit` doubles it and a blank title is accepted; `plot_csd` now refuses both inline (`jnwb/vis/laminar.py:422`). Check: both call one helper (`AGENTS.md` 4.7), and a test per function refuses a unit-naming and a blank title. Waits: display only.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-43 The raster SEM ribbon of `jnwb.vis` is pinned by a hand-computed value

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/vis/spiking.py`, `tests/test_vis*.py`.
- Review of 11-22 (2026-10-10): `jnwb/vis/spiking.py:139` computes the SEM ribbon as `raster_psth` does (`jnwb/viz.py:166`), and only the latter is pinned (`tests/test_vis_heatmap_ribbon_sem.py`). Check: the ribbon reuses `raster_psth`'s SEM or a hand-computed test fails its ddof=0 and no-square-root mutants. Waits: display only.
Accept: the check passes. Stop: none beyond the standing ones.

### 11-25 The gradients crossover default and the `jnwb.vis` vocabulary are pinned by tests

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/vis/**`, `tests/test_vis*.py`.
- P-216 display part: the gradients crossover default and the `jnwb.vis` vocabulary beyond a grep are unpinned. Check: a test fails when the crossover default changes, and one pins the vocabulary. Waits: behaves correctly.
Accept: the check passes. Stop: none beyond the standing ones.

### 10-14 The documented call shapes are type-checked by an annotation oracle

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `tests/test_docs_call_shapes.py`, `scripts/docs_form_gate.py`, `tests/test_skill_symbol_coverage.py`.
Split from the documentation-check item on 2026-10-04, which landed every other bullet.
- P-167 and P-84: P-79b, P-79c and P-82 are wrong-type calls that bind cleanly; the recorded call fragments use names the page never assigns (`lfp_segments`, `spike_trains`, `session_qc_list`). Ruled 2026-10-04 (Hamm): an annotation oracle over literals and page-assigned names, plus a small table of argument types for names a page never assigns. Check: `tests/test_docs_call_shapes.py` fails the oracle on all three calls. Waits: the documented calls are already corrected; the oracle guards recurrence.
Accept: the check passes. Stop: the oracle needs a type that no annotation or table entry states.

### 10-15 The four published unit measures are public operations or ruled exclusions

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-qc. Blocked by: none.
Writes: `artifacts/evidence/0.2.9/unit_qc_inventory.md`, `jnwb/unit_quality.py`, `tests/test_unit_quality.py`, `skills/jnwb-qc/SKILL.md`.
Moved from the 0.2.9 inventory on 2026-10-04 (ruled). The code read was `E:/omission` at `c3d69375`, which copies the duration measure and the unit screen of the lab pipeline it cites (`yihan777/alpha_beta_mechanism@826e540`).
- Four published measures the copied screen applies and jnwb lacks: amplitude cut-off (Hill et al. 2011), half-width, repolarisation slope and spread (Jia et al. 2019). Check: each is a public operation by its published definition with a `docs/references.md` row, or a ruled exclusion recorded in `artifacts/evidence/0.2.9/unit_qc_inventory.md`. Waits: new capability, not a defect.
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

### 11-37 The SNR-asymmetry docs row states a direction rule the fixture contradicts

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `docs/common_mistakes.md`, `skills/jnwb-connectivity/SKILL.md`, `tests/test_connectivity_pitfalls.py`.
- P-359: `docs/common_mistakes.md:431` credits the direction to the signal-to-noise ratio, and the fixture shows it following the fitted order instead: y to x at order 1 (7 of 10 seeds), x to y at every order 2 to 20 (9 or 10 of 10), significant at p = 0.005 under both the shipped null and a phase-randomised one (`TestSignalToNoiseAsymmetry`), while no coupling exists. Evidence: `artifacts/evidence/0.2.11/pitfall_tests_and_problem_rows.md`. Waits: the mechanism is unresolved; wording only.
Accept: the row or the holding class's docstring states the order dependence. Stop an estimator repair.

### 11-38 `diagnostics['stationary']` names statistical stationarity but tests VAR stability

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `jnwb/connectivity/_granger.py`, `docs/common_mistakes.md`, `tests/test_connectivity_pitfalls.py`.
- P-360: the key is `bool(spectral_radius < 1.0)` (`_granger.py:1074`), a fitted-VAR predicate. A unit root at phi = 0.999 (radius 0.99860) reads True while `granger`'s ADF calls it a unit root; a 0.05 Hz drift reaches a radius within float rounding of 1.0, so which side of the comparison it lands on is a property of the linear-algebra stack and whether a warning fires there is build-dependent (`TestNonStationarityIsOnlyFlaggedWhenExplosive`). Evidence: `artifacts/evidence/0.2.11/pitfall_tests_and_problem_rows.md`. Waits: a key rename is a ruling; docstring wording is not.
Accept: the key's docstring and `docs/common_mistakes.md:437` name the predicate as fitted-VAR stability. Stop an API rename.

### 11-39 The filtering row's auto-order ceiling and its failed band recovery are unpinned

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `skills/jnwb-connectivity/SKILL.md`, `tests/test_connectivity_pitfalls.py`.
- P-361: on the filtered pair `order='auto'` moves from 3 to the `max_lag` ceiling of 20, and no filter recovers a band value (ratio 0.666 at 8-60 Hz, 0.457 at 30-80 Hz, against `granger_spectral`'s 0.2976), which is what `common_mistakes.md:436` means by "filtering cannot isolate a band" (`TestFilteringBeforeGranger`, four mutants killed). Waits: the estimator behaviour is recorded, not repaired; the gap is that no skill states it.
Accept: the skill states both, and the tests fail when either changes. Stop none.

### 11-40 The pitfalls row on phase slope and the PSI page do not point at each other

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `docs/common_mistakes.md`, `docs/08_directed_connectivity_and_information.md`, `tests/test_connectivity_pitfalls.py`.
- P-362: `docs/common_mistakes.md:435` cites only the PSI page (`docs/08_directed_connectivity_and_information.md:88-113`), whose section never names unequal-delay common input, while `:432` and `:166` already carry it and the fixture shows a driver with power spread across the band reads as a lead at p = 2.28e-23 (`TestPhaseSlopeIsNotDirection`). Waits: the vocabulary is already constrained; this is a cross-reference only.
Accept: row 435 or the PSI page names the common-driver case. Stop a vocabulary change.

### 11-41 The frozen files with misordered waveform blocks are not dispositioned

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `artifacts/evidence/0.2.11/frozen-waveform-disposition.md`.
- Issue #27 closed with `check_waveform_blocks` as the detection tool, but no record in this repo says which frozen files hold misordered blocks or what each file's verdict was; the prior audit's worktree is inaccessible, so the scope is re-derived from disk. Check: the evidence file lists every frozen file checked with its owned/unowned/unknown counts, and each unowned file is repaired, flagged, or awaiting a ruling. Waits: detection only; the check moves nothing.
Accept: every frozen file in the re-derived scope has a row. Stop: a repair or relabel needs a ruling.
