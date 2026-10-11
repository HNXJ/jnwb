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
| A lane is one worktree and one writer; up to three lanes run in parallel, one Haiku worker each, when they share no file (Hamm 2026-10-10 and 2026-10-11); a lane's items run in the order listed | lanes never share a file, so they merge without conflict |
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

| Lane | Items, in order | ETA (estimate) | Owns |
|---|---|---|---|
| C interpreter legs | 11-44 | 1 h; in progress, then one CI run | `.github/workflows/workflow.yml`, `pyproject.toml`, `scripts/harness_gate.py`, `README.md`, `tests/test_ci_conclusion_gate.py`, `tests/test_workflow_release_policy.py`, `tests/test_readme_smoke.py` |
| G pitfalls and skill sources | 10-12, 11-29 | 3 h | `tests/test_connectivity_pitfalls.py`, `tests/test_substitution_class_sweep.py`, `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-population/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md` |
| P skills composition | 07-08, 07-09 | 7 h; 07-09 needs 07-08 | `skills/jnwb/SKILL.md`, `skills/jnwb/agents/openai.yaml`, `tests/test_skill_router_reach.py`, `tests/test_composition_*.py` |
| D display, documentation and unit measures | 10-14, 11-20, 10-15 | 11 h; 10-15 needs a ruling for each new public operation | `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `jnwb/unit_quality.py`, their tests, `skills/jnwb-landmark-viz/SKILL.md`, `skills/jnwb-figures/SKILL.md`, `skills/jnwb-qc/SKILL.md`, `docs/vis.md`, `tests/test_docs_call_shapes.py`, `scripts/docs_form_gate.py`, `tests/test_skill_symbol_coverage.py`, `artifacts/evidence/0.2.9/unit_qc_inventory.md` |
| Y identity facts | 11-08, 11-09, 11-07, 10-10, 11-06, 09-04, 11-32 | 18 h; 10-10 creates `jnwb/_declarations.py`, which 11-06 extends and 09-04 reads; 11-32 needs Hamm | `jnwb/__init__.py`, `jnwb/compression.py`, `jnwb/_declarations.py`, the fact gate and its test, `artifacts/fact_stack.md` holder cells |

The B3 choice-name lexicon and the dB lexicon that lane Y reads were ruled on 2026-10-10
(`artifacts/rulings/2026-10-10.md`). ETAs are estimates of wall time with one worker per lane.

### 11-44 Python 3.15 is tested but not declared

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `.github/workflows/workflow.yml`, `pyproject.toml`, `scripts/harness_gate.py`, `README.md`, `tests/test_ci_conclusion_gate.py`, `tests/test_workflow_release_policy.py`, `tests/test_readme_smoke.py`.
- Ruled 2026-10-11: the non-blocking 3.15 leg passed (dev run 38121481816), so 3.15 joins the blocking matrix on Ubuntu (h5py built against the system HDF5) and the classifiers, with gate 8 unchanged; Windows 3.15 waits for h5py cp315 wheels. Check: gate 8 passes with 3.15 in `PYTHON_SUPPORTED` and `PYTHON_CI_REQUIRED`, the non-blocking job is gone, and the README's tested versions match the matrix.
Accept: one `dev` run with a green Ubuntu 3.15 leg in the blocking matrix. Stop: a dependency pin would change a supported version.

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

### 10-14 The documented call shapes are type-checked by an annotation oracle

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `tests/test_docs_call_shapes.py`, `scripts/docs_form_gate.py`, `tests/test_skill_symbol_coverage.py`.
Split from the documentation-check item on 2026-10-04, which landed every other bullet.
- P-167 and P-84: P-79b, P-79c and P-82 are wrong-type calls that bind cleanly; the recorded call fragments use names the page never assigns (`lfp_segments`, `spike_trains`, `session_qc_list`). Ruled 2026-10-04 (Hamm): an annotation oracle over literals and page-assigned names, plus a small table of argument types for names a page never assigns. Check: `tests/test_docs_call_shapes.py` fails the oracle on all three calls. Waits: the documented calls are already corrected; the oracle guards recurrence.
Accept: the check passes. Stop: the oracle needs a type that no annotation or table entry states.

### 11-20 `Canvas.save_and_seal` loses no export on a loaded machine and an export error reaches the caller

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/vis/**`, `tests/test_vis*.py`, `tests/test_viz*.py`.
- P-254: `Canvas.save_and_seal` loses its export on a loaded Windows machine when choreographer's shutdown budget expires; a serial run can hang at exit after a failed close; no test shows an export error reaching the caller. Check: one kaleido session per call; a serial run exits after a failed close; a test fails when the export error is swallowed; a later call fails fast. Waits: loud. Observed 2026-10-04 under xdist: on a loaded machine a `-n 12` run of `4be1792b` hung 17 minutes in a headless Chrome child of one worker, and after that child was killed the suite reported 0 failed, so a lost export did not reach the test that made it; whether that can make qualifying evidence falsely pass is for the closure pass to classify.
Accept: the check passes. Stop: none beyond the standing ones.

### 10-15 The four published unit measures are public operations or ruled exclusions

Release: deferred-0.2.11.
Role: jnwb-developer. Skill: jnwb-qc. Blocked by: none.
Writes: `artifacts/evidence/0.2.9/unit_qc_inventory.md`, `jnwb/unit_quality.py`, `tests/test_unit_quality.py`, `skills/jnwb-qc/SKILL.md`.
Moved from the 0.2.9 inventory on 2026-10-04 (ruled). The code read was `E:/omission` at `c3d69375`, which copies the duration measure and the unit screen of the lab pipeline it cites (`yihan777/alpha_beta_mechanism@826e540`).
- Four published measures the copied screen applies and jnwb lacks: amplitude cut-off (Hill et al. 2011), half-width, repolarisation slope and spread (Jia et al. 2019). Check: each is a public operation by its published definition with a `docs/references.md` row, or a ruled exclusion recorded in `artifacts/evidence/0.2.9/unit_qc_inventory.md`. Waits: new capability, not a defect.
Accept: the check passes. Stop: a new public operation, or a definition with more than one published form, needs Hamm's ruling.

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

### 11-07 Each of the S1, S2, S5 and S7 scans reports its own planted case

Release: deferred-0.2.11.
AUTONOMY: none for the dB-lexicon values; holder cells under the standing authorization of 2026-09-29; the scans are `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- S1, S2, S5 and S7: the scans as ruled in Q13. Check: each scan reports its own planted case in `tests/test_fact_gate.py`. Waits: fact reports UNHELD; nothing public claims it.
Accept: each scan reports its own planted case in `tests/test_fact_gate.py` and S1, S2, S5 and S7 report no UNHELD fact. Stop: a scan would need a scientific criterion not ruled in Q12 or Q13.

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

### 11-32 Each fact citing `todo:09-04` or `todo:10-10` names an item whose bullet states its work

Release: deferred-0.2.11.
AUTONOMY: none; holder cells belong to Hamm.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/fact_stack.md`, `artifacts/todo_stack.md`.
- S9 to S14, K4, I2 and I3 cite `todo:09-04` or `todo:10-10` though no bullet of those items names them (renaming 09-04 makes the fact gate report VIOLATED 8). Check: each such fact's holder names an item whose bullet states that fact's work. Waits: holder cells belong to Hamm; edit only with his authorisation.
Accept: each such holder names an item whose bullet states that fact's work. Stop: a holder cell would change without Hamm's authorisation.
