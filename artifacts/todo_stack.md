# 0.2.14

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.13
closed on 2026-10-21 (tag `v0.2.13`), and its section is gone from this file. The theme and plan of
0.2.14 are in the section below, as ruled 2026-10-19; its checkpoint closes when its table passes
row by row. A 0.2.14 item carries `deferred-0.2.14` in its Release field until the version is bumped to 0.2.14
(`artifacts/evidence/0.2.8/plan/decisions.md` D2).

Theme (ruled 2026-10-19): the public NWB mutation and execution APIs (07-21, 07-22), and the
existing tools brought to their stated contract: fact closure, reading edges, the pitfall
estimators, the deferred laminar and curation work, and the removals ruled for 0.2.14. The rulings the plan needs come first (wave 0), one
question per message; the checkpoint is the 0.2.13 table with 0.2.14 in place of 0.2.13.

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet, in the contract of `artifacts/skills/jnwb-fact-action` §5; role `jnwb-developer` unless named | a batched packet redefines the hard item |
| A lane is one clone and one writer; up to three lanes run at once, when they share no file (Hamm 2026-10-10, 2026-10-11, 2026-10-19); a lane's items run in the order listed | lanes never share a file, so they merge without conflict |
| Writers: Haiku 5.5 workers for bounded packets; Muse (opencode `code` tier) for derivation-heavy packets and every new public function; a Muse `review` or a Haiku verifier re-runs each repair | the actor is never the verifier |
| A packet reproduces each bullet on its own tree first; a bullet that does not reproduce is deleted | non-reproduction is a result |
| The integrator owns the stacks, `CHANGELOG.md`, `docs/api.md` and every commit and push | packets report the disposition and the changelog text |
| A public signature, an estimand or a skill line goes to Hamm before code, one question per message | public API and skills are Hamm's |
| Match skills (Hamm 2026-10-21): a packet loads `match-code-style` for code and tests, `match-writing-style` for docs, docstrings, stack text and commit messages, and `match-visual-style` for figures and the dashboard, rendered at final size in light and dark; before each commit `match-checker` (check mode) runs on the changed files and the integrator re-checks every number in its diff | numbers and claims stay fixed while the wording is cut |
| Wave barrier: `python scripts/harness_gate.py` (count PASS lines), the full suite, commit, push, CI green on `dev` at that SHA | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then `Do`, `Accept`, `Stop` as
needed; `AUTONOMY` and a one-line source or ruling note follow the fields they qualify. A bullet reads
`ID: defect, as input -> observed against expected, with numbers and units. Check: a predicate that
decides it, naming the file and the asserted value. Waits: why it cannot make release evidence
falsely pass.` `Waits:` appears in deferred cycles; `Waits: not stated.` marks a reason no source
gives, for the closure pass to classify. An item holds one defect and one check, in at most eight
lines.

## Lanes

Full suites run one at a time; on the maintainer's machine through its local `suite_lock.py`,
elsewhere as `python -m pytest tests/ -q`.

| Wave | Lane | Items, in order | Writer | Waits for |
|---|---|---|---|---|
| 0 | Proposals | 15-20 (inventory and prune proposal); 11-04, 14-07, 13-04, the 11-07 and 12-11 readings and 11-32's cells were ruled 2026-10-20, and 12-06's line endings on 2026-09-29 (LF, one conversion commit) | Muse drafts; Hamm rules | 0.2.13 tagged |
| 1 | M mutation | 07-21 (the core five), then 07-22 | Muse | nothing |
| 1 | R reading | 11-02 (fact I2's scan) | Haiku | nothing |
| 2 | F facts | 10-10, 11-06, 09-04, 11-07, 12-11, 16-05 to 16-07, 16-10, 11-09, 12-08 | Muse for 10-10, Haiku for the rest | nothing |
| 2 | L laminar | 16-03, 15-18, 15-22 (a draft to Hamm) | Muse | nothing |
| 2 | X outside code | 12-21 (`E:/repos/jaxfne`), 14-08 (`yihan777/alpha_beta_mechanism`) | Haiku | an excerpt or read access; when neither exists, the item stops and goes to Hamm, never to 0.2.15 |
| 2 | D docs and dashboard | 16-17, then 16-12 (ruled 2026-10-21: light docs with inline figures; HTML and proof of work on the dashboard) | Haiku for figures and pages, Muse for the dashboard design | nothing; 16-12 waits on its receipts |
| 3 | H harness | 12-05 with 15-20, 11-03, 12-07, 09-07, 07-05, then 12-06 | Haiku | 07-22 and wave 2 merged |
| 4 | Checkpoint 0.2.14 | the 0.2.13 checkpoint, for 0.2.14 | integrator | waves 0 to 3 merged |

## Checklist 0.2.14

What holds when 0.2.14 is released, against the goal in `artifacts/goal.md` (ruled 2026-10-21). Every row ships in 0.2.14; anything raised during the cycle goes to 0.2.15. A row passes when its check passes on `dev`; the checkpoint below starts when every row passes.

| # | Holds at release | Check | Items |
|---|---|---|---|
| 1 | The NWB mutation API: the core five, then the execution and cache API, each signature ruled by Hamm before code | `docs/api.md`, `CHANGELOG.md` and the `skills/` routing rows name each symbol; `tests/test_skills_validation.py` passes; each function has a round-trip test on a written file | 07-21, 07-22 |
| 2 | The four pitfall estimators, `noise_correlation` and `screen_units_against_labels`, as ruled 2026-10-20 | each has a planted-case test that recovers the planted value and one that refuses the documented bad input; each cites its source in `docs/references.md` | 14-06, 14-07, 13-04 |
| 3 | `create_aligned_dataset`, `create_result`, `create_figure` and `gpu_pca` are gone | the names are absent from `jnwb.__all__` and `docs/api.md`; `CHANGELOG.md` records each removal | 16-01, 16-02 |
| 4 | Every container `inspect` lists is readable, and the compression, unit-table and addressing edges hold | a test that inspects each fixture and reads every listed container passes | 11-01, 11-02 |
| 5 | Every fact without a holder gets a scan with a planted case | the harness gate's fact line reports no UNHELD fact naming a 0.2.14 item; each scan fails on its planted case | 16-05 to 16-07, 16-10, 11-07, 12-11, 10-10, 11-06, 09-04, 11-09, 12-08, 11-03, 12-07 |
| 6 | The laminar and curation work: the curation-default calibration and fusion agreement that can say `agree` or `disagree` | the receipts are committed under `artifacts/benchmarks/calibration/`; the `jnwb-sim-benchmark` skill is a draft Hamm has ruled on | 16-03, 15-18, 15-22 |
| 7 | Work that needs outside code lands (ruled 2026-10-21: nothing in this cycle is deferred) | each item is gone from this file | 12-21, 14-08 |
| 8 | The verification inventory and a pruning constraint ruled by Hamm; process tests pruned under it | `artifacts/evidence/0.2.14/verification_inventory.md` is committed; the suite's runtime and test count before and after are in the commit message | 15-20, 12-05, 09-07, 07-05, 12-06 |
| 9 | Light docs: an inline light and dark PNG pair on every demonstration page, no linked figure, and no proof detail | the docs tests for inline figures, linked figures and evidence paths pass; `python scripts/docs_build.py` exits 0 | 16-17 |
| 10 | The dashboard holds the proof of work and the HTML outputs | `tests/test_build_dashboard.py` builds it from committed files with every card's receipt digest matching; the published page shows the proof-of-work section | 16-12 |
| 11 | Reference claims checked against full text where an abstract decides nothing | each of the 46 claim cells is confirmed, reworded, or cut | 16-11 |
| 13 | The core freeze and the surface manifest (goal F1, F2) | Gate 19 lists 28 functions; the surface-manifest test passes | 16-18, 16-19 |
| 12 | Release form (`AGENTS.md` §11): low-verbosity docs, low-complexity code, an empty open stack, no required item | `match-checker` has run on every commit's changed files; the closure pass finds 0 new blockers | the checkpoint below |

## Checkpoint 0.2.14

In order; a failed row stops the checkpoint and returns to the lanes. The steps are `.github/CONTRIBUTING.md`
"Releasing" with the R5 ruling (2026-10-19: CI green on `main` at the SHA that is tagged). Merge,
push and tag are authorized (Hamm 2026-10-19); PyPI's environment approval is Hamm's.

Before step 8, merge `main` into `dev`, so the release merge's first parent is in `dev` (release_gate refuses it otherwise; 2026-10-21).

| Step | Command or action | Passes when |
|---|---|---|
| 1 | Read the open stack and this section | `artifacts/open_stack.md` holds no table row; no `###` item above remains |
| 2 | `python scripts/bump_version.py 0.2.14 --date` | the declared version reads 0.2.14 |
| 3 | `python scripts/assemble_changelog.py --version 0.2.14 --date` | `artifacts/changelog.d/` holds no fragment; `CHANGELOG.md` has a 0.2.14 section |
| 4 | `python scripts/measure_peak_memory.py --write` | each growth past 20% and 5 MiB has a reason in `CHANGELOG.md` |
| 5 | Closure pass: a Muse `review` and a Haiku verifier, independently, with the G-04 claims check | `artifacts/process/blocker_fixpoint_receipt.md` names the commit and 0 new release-blocking problems |
| 6 | Full suite, harness gate, docs build; push `dev` | the stamp equals HEAD; CI green on `dev` at that SHA |
| 7 | `python scripts/release_gate.py` | exit 0 |
| 8 | Merge `dev` into `main` with a merge commit; push `main` | CI green on `main` at the merge SHA |
| 9 | Tag `v0.2.14` at that SHA; push the tag | the TestPyPI and verify jobs pass; PyPI waits on Hamm's approval |
| 10 | Install 0.2.14 from PyPI in a fresh venv; import; run the quickstart | the installed version reads 0.2.14 |
| 11 | Move the 0.2.15 roadmap rows here with their full text; 0.2.15 becomes this file's top section | release_gate STEP 0a reads no `deferred-0.2.14` |

### 16-03 A calibration of what the curation defaults govern

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: nothing.
Writes: `scripts/calibrate_curation.py`, `tests/test_curation_calibration_receipt.py`, `artifacts/benchmarks/calibration/curation_calibration_0.2.14.md`, `artifacts/benchmarks/calibration/curation_calibration_0.2.14_raw.json`.
- 16-03: on `synth_laminar_motif` probes every swept value of the 15 `curate_and_label` defaults gives the default's counts (15 of 15, `artifacts/benchmarks/calibration/curation_calibration_0.2.13.md`); the planted anchors are vFLIP's, so the sweep places no default. Check: a probe family plants what the defaults decide (grades, bad zones, edges, layer labels), and at least one swept value of each default changes a count, or the receipt names the default the plant cannot reach. Waits: ruled 2026-10-20; the 0.2.13 receipt stands.
Accept: the 0.2.14 receipt and its test pass; defaults change only where a sweep puts one outside its stable range.

### 15-20 An inventory of the verification apparatus

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: none.
- 15-20: Goal 10 bounds the apparatus ("a new gate or process replaces one") with no check; nothing lists each gate's purpose, runtime, unique failure detection, duplicated assertions and maintenance burden (external review, 2026-10-15). Accept (ruled 2026-10-15): that inventory first, then a measurable constraint proposed to Hamm that does not reward deleting valuable tests; no universal gate-count ceiling. Two candidate checks were built and not integrated (2026-10-15), each to land only by replacing a check the inventory shows weaker: warning reads filter by category (it found one site beyond 51a29bb7's seven), and every artifact path code names is tracked. Check: that inventory first, then a measurable constraint proposed to Hamm that does not reward deleting valuable tests; no universal gate-count ceiling. Waits: Ruled 2026-10-19 with 12-05: the inventory and a prune proposal land in 0.2.14.

### 11-07 The S1, S2 and S5 scans

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- 11-07: S1, S2 and S5 report UNHELD: the S2 and S5 scans land in 0.2.11 and flag `jnwb/spectral/_psd.py:389` and `:558` (S2) and 17 randomness calls without an `rng` parameter plus one seed (S5), and S1's only test covers its reference-line clause; S2's clause 1 and the S5 sites wait on Hamm's reading. The full text is in `git log -S '### 11-07' -- artifacts/todo_stack.md`. Check: each scan reports its own planted case in `tests/test_fact_gate.py`. Waits: Ruled 2026-10-20: S2 covers returned power and dB estimates (log-space fit statistics exempt by rule); S5 exempts draws traced to a caller's rng, documented fixed-seed self-checks and rng-like `random_state`, and `visual_qc`'s jitter gains `rng`.
Accept: the Science and Skills tables report no UNHELD fact.

### 12-11 The S7 scan

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- 12-11: S7 (a caller uses the library function instead of retyping its rule) has no scan that reports its own planted case. Accept (carried from 11-07 by the 2026-10-11 ruling): the S7 scan reports its own planted case in `tests/test_fact_gate.py`, and S7 reports no UNHELD fact. Check: the S7 scan reports its own planted case in `tests/test_fact_gate.py`, and S7 reports no UNHELD fact. Waits: Ruled 2026-10-20: a registry of owned rules and their signature expressions, scanned in S7's scope and in `jnwb/`; the three R² sites share one helper.

### 12-06 No process identifiers outside the stacks

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 12-05, 12-07, 12-08.
Writes: `scripts/*.py`, `tests/**/*.py`, `.github/workflows/workflow.yml`, `CONTRIBUTING.md`.
- 12-06: P-284: `scripts/` and test files cite item and problem ids (P-209 and IB-71 merged; the 2026-10 counts no longer reproduce, so the lane re-measures them); P-102 levels line endings if D3 rules it. Check: each is removed or rewritten as a plain reason, then gate 14 reads both folders with an allowlist for machine-required literals; gate 16 passes and one byte-mode edit per convention applies. Waits: After 12-05, 12-07 and 12-08; neither directory ships, and P-102 is bytes only and waits on the D3 ruling. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: gate 14 passes on `scripts/` and `tests/`; the suite passes.

### 07-21 A public NWB mutation API

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: nothing.
Writes: `jnwb/nwb_write.py`, `tests/test_nwb_write.py`, `docs/writing_nwb.md`, `mkdocs.yml`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`.
- 07-21: No public NWB mutation API exists. Check: a test that fails before the repair and passes after. Waits: Shape ruled 2026-09-29 (`artifacts/evidence/0.2.8/api_proposals/nwb_mutation.md`: the core five first); 0.2.14's theme by the 2026-10-19 ruling.
Accept: each landed operation re-reads its output and refuses an ambiguous mapping; API, documentation and tests land before or with any skill.

### 07-22 A public execution and cache API

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb. Blocked by: 07-21.
Writes: `jnwb/execution.py`, `tests/test_execution_api.py`, `docs/execution.md`, `mkdocs.yml`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`.
- 07-22: No public execution and cache API exists. Check: a test that fails before the repair and passes after. Waits: After 07-21; surface ruled 2026-09-29 (per-call `device=` and `n_jobs=` plus one recorded execution field); 0.2.14's theme by the 2026-10-19 ruling.
Accept: a cache key includes input hash, parameters and version, with an invalidation test; no control changes a number.

### 11-02 The I2 scan

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/build_fact_graph.py`, `scripts/fact_gate.py`, `tests/test_fact_gate.py`, the modules a repair touches and their tests, the I2 cell of `artifacts/fact_stack.md`.
- 11-02: Fact I2 (a unit change, or a wrapper or default that changes the estimand, is a named parameter or fails) has no scan with a planted case; D10's declared shallow end landed in e4433366. Check: a scan reports a planted silent unit conversion and a planted estimand-changing default as VIOLATED, and I2's holder cell names the scan (cells authorized 2026-10-20, 11-32).
Accept: each check passes.

### 10-10 Signature types that compose

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `jnwb/_declarations.py`, `artifacts/fact_stack.md`.
- 10-10: I1: no numeric public operation declares signature types, and no composition edge is type-checked; full text: `git log -S '### 10-10' -- artifacts/todo_stack.md`. Check: a planted spikes-to-LFP-only edge is reported VIOLATED by `tests/test_fact_gate.py`. Waits: Ruled 2026-10-11: the fact reports UNHELD and nothing public claims it. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: the Identity table and B3 report no UNHELD fact.

### 11-06 A cited reason for each defaulted `window=`

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 10-10.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `jnwb/_declarations.py`, `artifacts/fact_stack.md`.
- 11-06: B3: a public function with a defaulted `window=` needs no cited reason in the B3 table; full text: `git log -S '### 11-06' -- artifacts/todo_stack.md`. Check: a planted public function with a defaulted `window=` and no cited reason in the table is VIOLATED by `tests/test_fact_gate.py`. Waits: After 10-10; ruled 2026-10-11: the fact reports UNHELD and nothing public claims it. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: the Identity table and B3 report no UNHELD fact.

### 09-04 The claim-class text check

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 10-10.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- 09-04: S8: no text check over docs, skills, figure labels and docstrings reports the planted 0.2.7 fig09 unit as VIOLATED; full text: `git log -S '### 09-04' -- artifacts/todo_stack.md`. Check: `scripts/fact_gate.py` reports the 0.2.7 fig09 unit, planted, as VIOLATED. Waits: After 10-10; ruled 2026-10-11: the fact reports UNHELD and nothing public claims it. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: the Science and Skills tables report no UNHELD fact.

### 16-05 The S10 check

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: none.
- 16-05: The S10 scan (`scheme_scan` in `scripts/build_fact_graph.py`) reports 0 findings over 217 callables (f4afdcff), but excuses by name six that carry no scheme key: `wavemap_resolution_sweep` and five that return a bare value (`permute_labels`, both `exact_sign_flip`, `shuffle_pvalue_paired`, `shuffle_pvalue_unpaired`). Check: Hamm rules whether named exceptions hold the fact or the bare returns become result dicts (breaking); then the S10 holder cell names the scan. Waits: that ruling.

### 16-06 The S11 check

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 16-05.
- 16-06: The S11 scan (`rng_scan` in `scripts/build_fact_graph.py`) reports 0 findings over 217 callables (f4afdcff), but excuses by name six that cannot carry `surrogate_seed_entropy`: `resample_onsets` and the five bare returns of 16-05. Check: the ruling of 16-05 applied to S11; then the S11 holder cell names the scan. Waits: the 16-05 ruling.

### 16-07 The S12 check

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: none.
- 16-07: No scan reports fact S12 (a result computed on GPU records that it was) on a planted case, so it reports UNHELD. Check: a test that fails before the repair and passes after. Waits: Ruled 2026-10-20 (11-32): one check item per fact; nothing public claims it before the scan lands.

### 16-10 The I3 check

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: none.
- 16-10: No scan reports fact I3 (units, frames, sample rates and index bases do not change silently at a function boundary) on a planted case, so it reports UNHELD. Check: a test that fails before the repair and passes after. Waits: Ruled 2026-10-20 (11-32): one check item per fact; nothing public claims it before the scan lands.

### 11-09 A planned skill is reported only when K1 and K5 hold for it

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- 11-09: The fact gate can report a planned skill (one of the twelve of Q14, `jnwb-landmark-viz`, `jnwb-paradigm` and `jnwb-qc` included) for which K1 or K5 does not hold; the full text is in `git log -S '### 11-09' -- artifacts/todo_stack.md`. Check: the fact gate reports a planned skill only when K1 and K5 hold for it. Waits: Ruled 2026-10-11: plan for future skills, no shipped behaviour. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: the Science and Skills tables report no UNHELD fact.

### 12-08 Every routed method cites a published source

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/build_fact_graph.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- 12-08: No fact holds `computed:routed_citations`, which lists 73 routed exports with no `cites` edge: containers, I/O, metadata, plotting and plumbing, plus eight with no source the code implements (`xflip`, `network_topology`, `permute_labels`, `build_permutation_plan`, `exploratory_correlate`, `consensus_bad_trials`, `spatial_derivative_sharpness`, `waveform_flatness`). Check: Hamm approves the row and the fact gate reports it HELD. Waits: Ruled 2026-10-14: deferred; the exclusion list ruled 2026-10-13 stands and nothing public claims the fact. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: the fact gate reports the row HELD, or it waits with Hamm's reason.

### 15-18 Fusion agreement that can say `agree` or `disagree`

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: none.
- 15-18: The `'unavailable'`/`'unresolved'` status, the `B` cap and `contact_spacing_um` landed (ruled 2026-10-15); `fuse_laminar_anchors` emits `'agree'` and `'disagree'` only once a calibrated separation threshold exists. Check: a test that fails before the repair and passes after. Waits: 15-19's calibration, done in 7ea17995. Moved to 0.2.14 by the 2026-10-19 theme ruling.

### 15-22 A `jnwb-sim-benchmark` skill

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: none.
- 15-22: No skill routes agents to the synthetic ground-truth generators (`synth_vflip2_crossover` of 15-11) and their recovery runs. Check: a test that fails before the repair and passes after. Waits: Ruled 2026-10-19: a draft comes for amendment once the P-335 calibration and the 15-11 generators are stable.

### 12-21 A jaxfne simulation as jnwb ground truth

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing.
- 12-21: No jnwb test recovers a known coupling, delay or spectrum from a jaxfne simulation (meet 204dfdaa item 8); full text: `git log -S '### 12-21' -- artifacts/todo_stack.md`. Check: a test that fails before the repair and passes after. Waits: Ruled 2026-10-14: needs jaxfne's excerpt; nothing shipped changes. Moved to 0.2.14 by the 2026-10-19 theme ruling.

### 12-05 Process tests pruned and merged

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 15-20, 07-22.
Writes: `artifacts/evidence/0.2.12/process_tests/**`, `tests/test_findings_ledger.py`, `tests/test_single_agent_instruction_file.py`, `tests/test_standing_rules_name_no_cycle.py`, `tests/test_agents_md_stays_a_router.py`, `scripts/measure_agents_md_duplication.py`, `tests/test_release_recovery_gates.py`, `tests/test_jrsa.py`, `tests/test_api_md_is_interpreter_independent.py`, `tests/test_workflow_release_policy.py`, `tests/test_state_reconstruction.py`, `tests/test_state_basis_is_checked.py`, `tests/test_xflip_calibration_receipt.py`, `tests/test_vflip_calibration_receipt.py`, `tests/test_test_imports_survive_the_wheel_leg.py`, `tests/test_the_suite_can_qualify_an_installed_copy.py`, `tests/test_errors_documented.py`, `tests/test_readme_smoke.py`, `scripts/reconstruct_state.py`.
- 12-05: Four process-test files to prune, four to merge and four weaker checks stay (the unruled list and its receipts: `artifacts/evidence/0.2.10/reduction/prune_list.md`), P-290 is enforced by nothing and the apparatus bound of `artifacts/goal.md` section 10 has no check. Check: each pruned case is shown held by a stronger test first, named in the audit; each kept process test is named under one probe class in the prune record; a taxonomy change goes to 12-06, which owns `CONTRIBUTING.md`; `scripts/reconstruct_state.py` records the line counts of `scripts/` and the process tests, so growth is visible per release; a refusal is a new item's to add if Hamm asks. Waits: Ruled 2026-10-19: the 0.2.10 prune list is stale and dropped; 15-20's inventory re-measures unique detection on the current suite and returns a prune proposal.
Accept: the pruned files' cases are held by the stronger tests named in the audit.

### 11-03 Design facts held

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 07-22, 07-21.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- 11-03: D1, D2 and D3 of the Design table report UNHELD. Check: a planted two-step convenience is VIOLATED; an untagged planted writer is VIOLATED. Waits: After 07-22; the facts report UNHELD and nothing public claims them, and D2 and D3 land with 07-21 and 07-22. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: the Design table reports no UNHELD fact.

### 12-07 Release and study-vocabulary facts held

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 12-05, 12-08, 07-22.
Writes: `.github/workflows/workflow.yml`, `scripts/harness_gate.py`, `scripts/gates/**`, `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `tests/test_harness_gate_study_tokens.py`, `artifacts/fact_stack.md`.
- 12-07: R2 (a verify-pypi job after publish-pypi) and B2 (gate 6 over `jnwb/`, `docs/`, `skills/` and `tests/`) report UNHELD. Check: a planted hash mismatch fails the job's check function; a planted study token in `tests/` fails. Waits: After 12-05 and 12-08; the upload step checks sha256 against the verified TestPyPI copy, and `tests/` is not in the wheel while shipped surfaces are scanned. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: `scripts/fact_gate.py` prints UNHELD 0 and VIOLATED 0.

### 09-07 Checks for the defect classes review keeps finding

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 07-22.
Writes: `scripts/learning_gate.py`, `scripts/reconstruct_state.py`, `scripts/harness_gate.py`, `tests/test_learning_gate.py`, `tests/test_state_reconstruction.py`, `artifacts/defect_classes.md`.
- 09-07: One class has no check: second-home-contradiction; `artifacts/state.md` names the worktrees, stale branches, the newest `dev` run (`RED` when it failed) and the open defect classes (2026-10-18); rewrite-drops-obligation is listed by `scripts/obligation_diff.py --base <commit>` (2026-10-18), which finds both 08-06 instances in 8482c7bc; ruling-cited-not-recorded is checked to the date (`tests/test_process_records_are_counted.py`, 2026-10-17), and matching a citation to its row stays a review rule. The ledger is recounted by the same file. Check: a gate reads every such citation and finds its row in `artifacts/rulings/<date>.md`; it is red on the 08-06 commit `8482c7bc`; for a mapping table with old and new columns, every obligation word (`before`, `after`, `never`, `must`, `only`) in an old rule appears in its new home; red on `8482c7bc` for D1 and D2; each ruling row may name a forbidden phrase and the gate greps the repository for it; red on the pooling phrase before 08-07; the section is generated, and a stale worktree or a red run is named; the gate recounts it. Waits: Process evidence only, no shipped behaviour; rewrites are rare and reviewed, review found every instance so far, and the integrator reads state by hand today. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: each check is red on the instance its bullet names and green on the live tree; the harness counts the new gate.

### 07-05 A downstream paper agent can consume jnwb

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 11-02, 07-22.
Writes: `jnwb/ontology.py`, `jnwb/paths.py`, `tests/test_ontology.py`, `tests/test_paths.py`, `tests/test_paths_identity.py`, `skills/jnwb/SKILL.md`, `CONTRIBUTING.md`.
- 07-05: `jnwb.preflight` outcomes are not scored as data, results do not name their input's sha256 and object path (IA-27's tests for `resolve_nwb_path`, `sha256_file` and `require` land with it), `CONTRIBUTING.md` states no intake, and P-335's review (`artifacts/evidence/0.2.13/p335_laminar_curation_review.md`) leaves the working-value defaults uncited and the inner stages unexposed, for a ruling. Check: a test per outcome reads those three from the returned object (`tests/test_ontology.py`); a round trip by path and hash passes; `CONTRIBUTING.md` holds that sentence; the packet reports a pass or fail for each of the four. Waits: After 11-02; new downstream capability, not a defect. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: a test per outcome in (a); a round trip in (b) by path and hash; gate 6 passes.

### 16-11 Reference claims against the full text

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
- 16-11: The 2026-10-20 reference check (three workers, 83 rows) graded each claim against its abstract only; 46 rows, the 14 core texts among them, have no abstract that decides the claim, so their second cell is unread against the source. Check: a test that fails before the repair and passes after. Waits: citations, DOIs, ISBNs and functions of all 83 rows were checked and two defects repaired; a claim cell is the page's reading, not a release value.

### 16-12 Real-data results on the dashboard

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/build_dashboard.py`, `artifacts/showcases/openscope_glo.json`, `tests/test_build_dashboard.py`.
- 16-12: The dashboard, not `docs/index.md` (ruled 2026-10-21), gains real-data results (`isi_cv` against stored values on 9,056 units, branch `claude/site-overview-326890`, commit 9b52c5e7; the WaveMAP and GLO results of the cross-dataset work) only from receipts committed to this repository and computed independently of jnwb. Check: each number on the page traces to a committed receipt. Waits: the cross-dataset receipts (the omission high-pass re-extraction, about 2026-10-21; GLO after it).

### 16-17 Proof detail leaves the docs

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/docs_form_gate.py`, `docs/documentation_form.md`, `tests/test_documentation_form.py`.
- 16-17: Docs pages carry validation detail that belongs on the dashboard: receipt paths, calibration tables, per-version evidence. Each such passage becomes one sentence and a link to its dashboard card. Check: the docs form gate fails on an `artifacts/evidence/` or `artifacts/benchmarks/` path in `docs/` outside `references.md`, with a planted case; the word count in `docs/documentation_form.md` drops. Waits: 16-16's cards exist, so the links have targets.

### 16-18 The core freeze (goal F1)

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/process/frozen_validated.json`, `tests/test_frozen_core_mutants.py`.
- 16-18: Six functions are frozen; goal F1 (ruled 2026-10-21) freezes 22 more: `compute_psd`, `band_power`, `aggregate_to_db`, `to_db`, `relative_power`, `harmonic_analysis`, `wpli`, `imaginary_coherency`, `cross_area_coherence`, `granger`, `granger_causality`, `bipolar_reference`, `laplacian_reference`, `current_source_density_1d`, `voltage_curvature_1d`, `cluster_permutation_test`, `clopper_pearson`, `mann_whitney_p_floor`, `shuffle_r2_ci`, `fdr_correct`, `label_layers`, `bin_spikes`. Each enters `artifacts/process/frozen_validated.json` with its body hash, the commit it was verified at and the tests that kill a planted change to it; a reviewer that did not write the test runs the mutant. Frozen last in the cycle, after 14-06 adds its estimators beside `granger`. Check: Gate 19 lists 28 functions, and for each a planted body change fails its named tests.

### 16-19 A manifest of the public surface (goal F2)

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 07-21, 07-22.
Writes: `tests/test_public_surface_manifest.py`, `artifacts/process/public_surface.json`.
- 16-19: After 0.2.14 a public symbol, module or skill enters only by a ruling that names it (goal F2, ruled 2026-10-21), and nothing records the surface to compare against. Check: a test that compares `jnwb.__all__`, the `jnwb/` module list and `skills/` with the manifest and fails, naming the entry, on an addition or removal the manifest does not record; a planted extra symbol fails it.
