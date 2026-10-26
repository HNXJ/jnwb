# 0.2.14

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.13
closed on 2026-10-21 (tag `v0.2.13`), and its section is gone from this file. The theme and plan of
0.2.14 are in the section below, as ruled 2026-10-19; its checkpoint closes when its table passes
row by row. A 0.2.14 item carries `deferred-0.2.14` in its Release field until the version is bumped to 0.2.14
(`artifacts/evidence/0.2.8/plan/decisions.md` D2).

Theme (ruled 2026-10-19): the public NWB mutation and execution APIs (07-21 and 07-22 landed), and the
existing tools brought to their stated contract: fact closure, reading edges, the pitfall
estimators, the deferred laminar and curation work, and the removals ruled for 0.2.14. The rulings the plan needs come first (wave 0), one
question per message; the checkpoint is the 0.2.13 table with 0.2.14 in place of 0.2.13.

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet, in the contract of `artifacts/skills/jnwb-fact-action` §5; role `jnwb-developer` unless named | a batched packet redefines the hard item |
| A lane is one clone and one writer; up to three lanes run at once, when they share no file (Hamm 2026-10-10, 2026-10-11, 2026-10-19); a lane's items run in the order listed | lanes never share a file, so they merge without conflict |
| Writers (ruled 2026-10-24): Cursor CLI GLM 5.3 flash at high effort for most packets; Muse (opencode) writes and criticises; Haiku 5.5 writes and runs the skill, doc and `match-checker` checks; a writer never verifies its own packet | the actor is never the verifier |
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
| 1 | M mutation | none left: 07-21's core five and 07-22's execution and cache API landed (CI green on `dev` at f5c55f2b) | integrator | nothing |
| 2 | F facts | 11-07, 12-11, 11-09 | Cursor GLM or Muse writes, Haiku checks | nothing |
| 2 | L laminar | 15-22 (a draft to Hamm) | Muse | nothing |
| 2 | X outside code | none left: 12-21's spectrum test landed (delay and direction moved to the roadmap by the 2026-10-23 ruling) and 14-08's rows cite the lab pipeline | Haiku | nothing |
| 2 | D docs and dashboard | reopened 2026-10-24: docs with interactive and still figures and a validation dashboard, after jaxfne's; items follow the preference rulings | Cursor GLM and Haiku for pages and figures, Muse for the dashboard design | the comparison with jaxfne and Hamm's preference rulings |
| 2 | N numerics and I/O (audit 2026-10-25) | one lane per file set: 17-14, 17-16, 17-18, 17-19, 17-20, 17-22, 17-43, 17-44, 17-45, 17-48, 17-52 | Cursor GLM writes, Haiku checks; one lane per file set | nothing |
| 2 | P process and docs (audit 2026-10-25) | 17-15, 17-34, 17-36 | Haiku writes, Muse reviews | nothing |
| 3 | H harness | 12-05 with 15-20, 11-03, 12-07, 09-07, 07-05, then 12-06 and 17-56; 17-26, 17-41, 17-54, 17-55 after the F lane, in its files; 17-26 then 17-31; 17-32; 17-27, 17-30 | Haiku | wave 2 merged |
| 3 | Freeze | 16-18, last, after every item that edits a listed body (17-19 among them) | integrator | waves 2 and 3 merged |
| 4 | Checkpoint 0.2.14 | the 0.2.13 checkpoint, for 0.2.14 | integrator | waves 0 to 3 merged |

## Checklist 0.2.14

0.2.14 is released when every row below passes; nothing else is required (ruled 2026-10-24). Rows 1 to 13 are what ships, checked on `dev`; rows 14 to 16 are the release itself, in the order of the checkpoint below. Anything raised during the cycle goes to 0.2.15. A row whose items have left this file still passes only when its check is re-run at the checkpoint.

| # | Holds at release | Check | Items |
|---|---|---|---|
| 1 | The NWB mutation API: the core five, then the execution and cache API, each signature ruled by Hamm before code | `docs/api.md`, `CHANGELOG.md` and the `skills/` routing rows name each symbol; `tests/test_skills_validation.py` passes; each function has a round-trip test on a written file | items gone (07-21, 07-22) |
| 2 | The four pitfall estimators, `noise_correlation` and `screen_units_against_labels`, as ruled 2026-10-20 | each has a planted-case test that recovers the planted value and one that refuses the documented bad input; each cites its source in `docs/references.md` | items gone (14-06, 14-07, 13-04) |
| 3 | `create_aligned_dataset`, `create_result`, `create_figure` and `gpu_pca` are gone | the names are absent from `jnwb.__all__` and `docs/api.md`; `CHANGELOG.md` records each removal | items gone (16-01, 16-02) |
| 4 | Every container `inspect` lists is readable, and the compression, unit-table and addressing edges hold | a test that inspects each fixture and reads every listed container passes | item gone (11-01) |
| 5 | Every fact without a holder gets a scan with a planted case | the harness gate's fact line reports no UNHELD fact naming a 0.2.14 item; each scan fails on its planted case | 11-07, 12-11, 11-09, 11-03, 12-07; 16-10 landed |
| 6 | The laminar and curation work: the curation-default calibration and fusion agreement that can say `agree` or `disagree` | the receipts are committed under `artifacts/benchmarks/calibration/`; the `jnwb-sim-benchmark` skill is a draft Hamm has ruled on | 15-22; 16-03 landed |
| 7 | The verification inventory and a pruning constraint ruled by Hamm; process tests pruned under it | `artifacts/evidence/0.2.14/verification_inventory.md` is committed; the suite's runtime and test count before and after are in the commit message | 15-20, 12-05, 09-07, 07-05, 12-06 |
| 8 | The core freeze and the surface manifest (goal F1, F2) | Gate 19 lists 28 functions; the surface-manifest test passes | 16-18; 16-19 landed |
| 9 | Docs pages carry still and interactive figures, after jaxfne's form (ruled 2026-10-24) | the form and the page set follow Hamm's preference rulings; a test builds each figure from committed inputs; the strict docs build passes | 17-01 |
| 10 | A validation dashboard after jaxfne's, keeping the proof of work, the HTML outputs and the GLO cards (ruled 2026-10-23 and 2026-10-24) | `tests/test_build_dashboard.py` builds it from committed files with every receipt digest matching; the published page shows each section the preference rulings name, in light and dark | 17-02 |
| 11 | Reference claims checked against full text where an abstract decides nothing | each claim cell of `docs/references.md` has a ledger line, confirmed, reworded, or cut; the 14 core texts keep their cells (ruled 2026-10-23, ledger ruled 2026-10-25) | landed (3ba28202); 17-15 |
| 12 | Release form (`AGENTS.md` §11): low-verbosity docs, low-complexity code, an empty open stack, no required item | `match-checker` runs once at the checkpoint on every file changed since v0.2.13, its report committed (ruled 2026-10-25); the closure pass (checkpoint step 5) finds 0 new blockers | checkpoint steps 1 to 5 |
| 13 | The audit of 2026-10-25 closed | every item 17-09 to 17-56 has left this file | 17-09 to 17-56 |
| 14 | `dev` is green and release-ready | the suite stamp equals HEAD; CI green on `dev` at that SHA; `python scripts/release_gate.py` exits 0 | checkpoint steps 6 and 7 |
| 15 | `main` carries 0.2.14 and the tag | CI green on `main` at the merge SHA; `v0.2.14` points at it; the TestPyPI and verify jobs pass | checkpoint steps 8 and 9 |
| 16 | 0.2.14 is on PyPI and the next cycle is open | PyPI approved by Hamm; a fresh venv installs 0.2.14, imports it and runs the quickstart; release_gate STEP 0a reads no `deferred-0.2.14` | checkpoint steps 10 and 11 |

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

### 17-01 Still and interactive figures in the docs

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: nothing.
- 17-01: docs pages show still figures only (75 PNGs with dark twins, 0 iframes); ruled 2026-10-24, every figure gets a Still tab and an Interactive tab, the HTML built in CI and served from gh-pages `/figures/`, one HTML that follows the site theme, and a registry-generated state line above each figure; `docs/generate_figures.py` and `docs/figure_style.py` move out of the docs source, which MkDocs copies into the site. Check: a test fails on a figure missing either tab or its state line, and on an iframe outside the allowlist; the strict docs build passes. Waits: not stated.

### 17-02 A validation dashboard after jaxfne's

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: nothing.
- 17-02: the dashboard is one page of sections with jnwb's own verdicts, published from `main` (`dashboard.yml`) where the ruling says each `dev` push; ruled 2026-10-24, hash-routed tabs with a page per validation, jaxfne's verdict set (reproduces to reproduced, partial to mixed, does_not to failed), no stage track, roadmap rows as `not started`, publish on each `dev` push after the checks, jaxfne's colours and chips by convention. Check: `tests/test_build_dashboard.py` builds it from committed files with every receipt digest matching, and a page test loads each tab in light and dark. Waits: not stated.

### 15-20 An inventory of the verification apparatus

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: none.
- 15-20: Goal 10 bounds the apparatus ("a new gate or process replaces one") with no check; `artifacts/evidence/0.2.14/verification_inventory.md` (2c0df23f) lists each gate's purpose and runtime but leaves unique failure detection unmeasured, and no pruning constraint has been put to Hamm (checklist row 7 needs one). Accept (ruled 2026-10-15): that inventory first, then a measurable constraint proposed to Hamm that does not reward deleting valuable tests; no universal gate-count ceiling. Two candidate checks were built and not integrated (2026-10-15), each to land only by replacing a check the inventory shows weaker: warning reads filter by category (it found one site beyond 51a29bb7's seven), and every artifact path code names is tracked. Check: that inventory first, then a measurable constraint proposed to Hamm that does not reward deleting valuable tests; no universal gate-count ceiling. Waits: Ruled 2026-10-19 with 12-05: the inventory and a prune proposal land in 0.2.14.

### 11-07 The S1, S2 and S5 scans

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `scripts/build_fact_graph.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`, `jnwb/spectral/_psd.py`, `jnwb/visual_qc.py`, `jnwb/onset_fitting.py`.
- 11-07: S1, S2 and S5 report UNHELD: the scans in `scripts/build_fact_graph.py` flag `jnwb/spectral/_psd.py:390` and `:564` (S2) and 6 functions drawing randomness without an `rng` parameter, with 0 global seeds (S5), re-measured 2026-10-25; S1's only test covers its reference-line clause; S2's clause 1 and the S5 sites wait on Hamm's reading. The full text is in `git log -S '### 11-07' -- artifacts/todo_stack.md`. Check: each scan reports its own planted case in `tests/test_fact_gate.py`. Waits: Ruled 2026-10-20: S2 covers returned power and dB estimates (log-space fit statistics exempt by rule); S5 exempts draws traced to a caller's rng, documented fixed-seed self-checks and rng-like `random_state`, and `visual_qc`'s jitter gains `rng`.
Accept: S1, S2 and S5 report HELD; no UNHELD fact names a 0.2.14 item.

### 12-11 The S7 scan

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `scripts/build_fact_graph.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`, `jnwb/spectral/_psd.py` (the R² sites, `:391` and `:595` on 2026-10-25).
- 12-11: S7 (a caller uses the library function instead of retyping its rule) has no scan that reports its own planted case. Accept (carried from 11-07 by the 2026-10-11 ruling): the S7 scan reports its own planted case in `tests/test_fact_gate.py`, and S7 reports no UNHELD fact. Check: the S7 scan reports its own planted case in `tests/test_fact_gate.py`, and S7 reports no UNHELD fact. Waits: Ruled 2026-10-20: a registry of owned rules and their signature expressions, scanned in S7's scope and in `jnwb/`; the three R² sites share one helper.

### 12-06 No process identifiers outside the stacks

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 12-05, 12-07.
Writes: `scripts/*.py`, `tests/**/*.py`, `.github/workflows/workflow.yml`, `.github/CONTRIBUTING.md`.
- 12-06: P-284: `scripts/` and test files cite item and problem ids (P-209 and IB-71 merged; the 2026-10 counts no longer reproduce, so the lane re-measures them); P-102 levels line endings to LF, as D3 ruled 2026-09-29 (82 tracked files are CRLF on 2026-10-25), in one conversion commit. Check: each is removed or rewritten as a plain reason, then gate 14 reads both folders with an allowlist for machine-required literals; gate 16 passes and one byte-mode edit per convention applies. Waits: After 12-05 and 12-07; neither directory ships, and P-102 is bytes only. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: gate 14 passes on `scripts/` and `tests/`; the suite passes.

### 11-09 A planned skill is reported only when K1 and K5 hold for it

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- 11-09: The fact gate can report a planned skill (one of the twelve of Q14, `jnwb-landmark-viz`, `jnwb-paradigm` and `jnwb-qc` included) for which K1 or K5 does not hold; the full text is in `git log -S '### 11-09' -- artifacts/todo_stack.md`. Check: the fact gate reports a planned skill only when K1 and K5 hold for it. Waits: Ruled 2026-10-11: plan for future skills, no shipped behaviour. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: K5 reports HELD; no UNHELD fact names a 0.2.14 item.

### 15-22 A `jnwb-sim-benchmark` skill

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `skills/jnwb-sim-benchmark/**`, `artifacts/process/public_surface.json` (a new skill enters the surface only by a ruling that names it, goal F2).
- 15-22: No skill routes agents to the synthetic ground-truth generators (`synth_vflip2_crossover` of 15-11) and their recovery runs. Check: a test that fails before the repair and passes after. Waits: Ruled 2026-10-19: a draft comes for amendment once the P-335 calibration and the 15-11 generators are stable.

### 12-05 Process tests pruned and merged

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 15-20.
Writes: `artifacts/evidence/0.2.14/process_tests/**`, `tests/test_findings_ledger.py`, `tests/test_single_agent_instruction_file.py`, `tests/test_standing_rules_name_no_cycle.py`, `tests/test_agents_md_stays_a_router.py`, `scripts/measure_agents_md_duplication.py`, `tests/test_release_recovery_gates.py`, `tests/test_jrsa.py`, `tests/test_api_md_is_interpreter_independent.py`, `tests/test_workflow_release_policy.py`, `tests/test_state_reconstruction.py`, `tests/test_state_basis_is_checked.py`, `tests/test_xflip_calibration_receipt.py`, `tests/test_vflip_calibration_receipt.py`, `tests/test_test_imports_survive_the_wheel_leg.py`, `tests/test_the_suite_can_qualify_an_installed_copy.py`, `tests/test_errors_documented.py`, `tests/test_readme_smoke.py`, `scripts/reconstruct_state.py`.
- 12-05: The process tests have never been pruned against measured unique detection (the 0.2.10 prune list was dropped as stale, 2026-10-19), P-290 is enforced by nothing and the apparatus bound of `artifacts/goal.md` section 10 has no check. Check: the prune set is the one 15-20's inventory and Hamm's pruning constraint select; each pruned case is shown held by a stronger test first, named in the audit; each kept process test is named under one probe class in the prune record; a taxonomy change goes to 12-06, which owns `CONTRIBUTING.md`; `scripts/reconstruct_state.py` records the line counts of `scripts/` and the process tests, so growth is visible per release; a refusal is a new item's to add if Hamm asks. Waits: Ruled 2026-10-19: 15-20's inventory re-measures unique detection on the current suite and returns a prune proposal.
Accept: the pruned files' cases are held by the stronger tests named in the audit.

### 11-03 Design facts held

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- 11-03: D1 to D11 of the Design table report UNHELD. Check: a planted two-step convenience is VIOLATED (D1); an untagged planted writer and an untagged planted cache operation are VIOLATED (D2, D3); D4, D5, D7 and D9 are held by the mutation API's refusal tests (`UnidentifiableRepairError`, `AmbiguousMappingError`, `UndeclaredUnitError`), each named as a `test:` holder and read to test its fact's claim; D6 (condition meaning) and D8 (trial semantics) name the test that holds each, or go to Hamm for a roadmap row; D10 and D11 by the execution-switch tests; a fact no test holds goes to Hamm for a roadmap row. Waits: the facts report UNHELD and nothing public claims them; 07-22 landed. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: the Design table reports no UNHELD fact.

### 12-07 Release and study-vocabulary facts held

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 12-05.
Writes: `.github/workflows/workflow.yml`, `scripts/harness_gate.py`, `scripts/gates/**`, `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `tests/test_harness_gate_study_tokens.py`, `artifacts/fact_stack.md`.
- 12-07: R2 (a verify-pypi job after publish-pypi) and B2 (gate 6 over `jnwb/`, `docs/`, `skills/` and `tests/`) report UNHELD; R5 (validated on `main` before the tag) and R7 (the full suite on every declared interpreter on Ubuntu and Windows) name this item too, each with a check against `.github/workflows/workflow.yml`. Check: a planted hash mismatch fails the job's check function; a planted study token in `tests/` fails. Waits: After 12-05; the upload step checks sha256 against the verified TestPyPI copy, and `tests/` is not in the wheel while shipped surfaces are scanned. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: B2, R2, R5 and R7 report HELD; no UNHELD fact names a 0.2.14 item; VIOLATED 0.

### 09-07 Checks for the defect classes review keeps finding

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/learning_gate.py`, `scripts/reconstruct_state.py`, `scripts/harness_gate.py`, `tests/test_learning_gate.py`, `tests/test_state_reconstruction.py`, `artifacts/process/defect_classes.md`.
- 09-07: One class has no check: second-home-contradiction; `artifacts/state.md` names the worktrees, stale branches, the newest `dev` run (`RED` when it failed) and the open defect classes (2026-10-18); rewrite-drops-obligation is listed by `scripts/obligation_diff.py --base <commit>` (2026-10-18), which finds both 08-06 instances in 8482c7bc; ruling-cited-not-recorded is checked to the date (`tests/test_process_records_are_counted.py`, 2026-10-17), and matching a citation to its row stays a review rule. The ledger is recounted by the same file. Check: a gate reads every such citation and finds its row in `artifacts/rulings/<date>.md`; it is red on the 08-06 commit `8482c7bc`; for a mapping table with old and new columns, every obligation word (`before`, `after`, `never`, `must`, `only`) in an old rule appears in its new home; red on `8482c7bc` for D1 and D2; each ruling row may name a forbidden phrase and the gate greps the repository for it; red on the pooling phrase before 08-07; the section is generated, and a stale worktree or a red run is named; the gate recounts it. Waits: Process evidence only, no shipped behaviour; rewrites are rare and reviewed, review found every instance so far, and the integrator reads state by hand today. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: each check is red on the instance its bullet names and green on the live tree; the checks join an existing gate or replace a named weaker one, so `GATES` stays at 22 (goal F4, `tests/test_every_gate_runs.py`).

### 07-05 A downstream paper agent can consume jnwb

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/ontology.py`, `jnwb/paths.py`, `tests/test_ontology.py`, `tests/test_paths.py`, `tests/test_paths_identity.py`, `skills/jnwb/SKILL.md`, `.github/CONTRIBUTING.md`.
Stop: naming the input's sha256 and object path on returned results is a consequential public API choice, a stop under `AGENTS.md` §12; Hamm rules the fields before code. The inner curation stages stay private (ruled 2026-10-19).
- 07-05: `jnwb.preflight` outcomes are not scored as data, results do not name their input's sha256 and object path (IA-27's tests for `resolve_nwb_path`, `sha256_file` and `require` land with it), `CONTRIBUTING.md` states no intake, and P-335's review (`artifacts/evidence/0.2.13/p335_laminar_curation_review.md`) leaves the working-value defaults uncited and the inner stages unexposed, for a ruling. Check: a test per outcome reads those three from the returned object (`tests/test_ontology.py`); a round trip by path and hash passes; `CONTRIBUTING.md` holds that sentence; the packet reports a pass or fail for each of the four. Waits: new downstream capability, not a defect. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: a test per `preflight` outcome reads the outcome, the input's sha256 and its object path from the returned object; a round trip by path and hash passes; gate 6 passes.

### 16-18 The core freeze (goal F1)

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/process/frozen_validated.json`, `tests/test_frozen_core_mutants.py`.
- 16-18: Six functions are frozen; goal F1 (ruled 2026-10-21) freezes 22 more: `compute_psd`, `band_power`, `aggregate_to_db`, `to_db`, `relative_power`, `harmonic_analysis`, `wpli`, `imaginary_coherency`, `cross_area_coherence`, `granger`, `granger_causality`, `bipolar_reference`, `laplacian_reference`, `current_source_density_1d`, `voltage_curvature_1d`, `cluster_permutation_test`, `clopper_pearson`, `mann_whitney_p_floor`, `shuffle_r2_ci`, `fdr_correct`, `label_layers`, `bin_spikes`. Each enters `artifacts/process/frozen_validated.json` with its body hash, the commit it was verified at and the tests that kill a planted change to it; a reviewer that did not write the test runs the mutant. Frozen last in the cycle, after 14-06 adds its estimators beside `granger` and after every item that edits a listed body (12-11's `_psd.py` edit among them). `fdr_correct`, `clopper_pearson` and `mann_whitney_p_floor` are also `StatisticalAnalysis` methods: the item freezes the definition the other delegates to, and names it. Check: Gate 19 lists 28 functions, and for each a planted body change fails its named tests.

## Audit of 2026-10-25

The items below come from the open stack of 2026-10-25 (`git show e00e8664:artifacts/open_stack.md`; the O- number in each source line traces a row to its probe). Each fix starts with a test that fails on the current code. Rulings: `artifacts/rulings/2026-10-25.md`.

### 17-14 Cache keys tell types apart and stores refuse what cannot round-trip

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/execution.py`, `tests/test_execution_api.py`, `artifacts/changelog.d/cache-keys.changed.md`.
- 17-14: `(1, 2)` and `[1, 2]` share a key, as do `{1: 0}` and `{"1": 0}`; `{1: a}` loads as `{'1': a}`; `2**70` stores and fails to load; `b"ab\x00"` loads as `b"ab"`; NumPy scalars load as Python floats (`execution.py:84,148,166`). Ruled 2026-10-25: type-tagged keys; `cache_store` refuses non-str dict keys, ints beyond int64, bytes with NUL and NumPy scalars unless stored as 0-d arrays. Check: each pair gets distinct keys; each lossy value raises at store; every accepted value loads equal in type and value. Source: O-10.

### 17-15 A ledger of the reference claim cells

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `artifacts/evidence/0.2.14/reference_claims_ledger.md`, `tests/test_reference_claims_ledger.py`.
- 17-15: checklist row 11 rests on "46 claim cells" with no committed ledger, and the ruling's arithmetic does not sum to 46; ruled 2026-10-25: a ledger, one line per claim cell of `docs/references.md` with its verdict (confirmed, reworded, cut) and the source read. Check: a test recounts the claim cells in `docs/references.md` and requires one ledger line each; the row cites the count it finds. Source: O-40.

### 17-16 `compress_fp32` refuses a destination equal to its source

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/compression.py`, its tests.
- 17-16: `compress_fp32(src, dst=src, overwrite=True)` turns the source into float32 and verifies it against itself as ok, against its docstring's "never modified" (`compression.py:927-1021`). Check: a `dst` resolving to `src` raises, as in `transform_nwb`; the source's sha256 is unchanged. Source: O-7.

### 17-18 `jrsa` corrects only finite p-values

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: nothing.
Writes: `jnwb/jrsa/_inference.py`, `tests/test_jrsa.py`.
- 17-18: a NaN p-value reaches `multipletests`: under `fdr_bh` every q becomes NaN, under holm and bonferroni it counts toward m (`_inference.py:291-314`). Check: p [0.04, nan] gives q [0.04, nan] under each method; a lag whose overlap is all zeros yields NaN p in a jrsa call. Source: O-9.

### 17-19 The paired cluster test reports its scheme

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing; before 16-18 freezes `cluster_permutation_test`.
Writes: `jnwb/statistics/_cluster.py`, its tests.
- 17-19: with `paired=True` and `groups`, the null uses global sign flips (valid: per-observation flips are exchangeable within any grouping) but `scheme` reads `within_group` (`_cluster.py:129-130`), and the S10 predicate trusts the label. Check: the paired branch reports `global` with and without groups. Source: O-11.

### 17-20 `TFRAccumulator.merge` refuses a shape mismatch

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/tfr_accumulator.py`, its tests.
- 17-20: (2,3,4) merged with (1,3,4), one trial in each, broadcasts and gives counts of 2 in every cell, against the docstring's merge equals summarize of the union (`tfr_accumulator.py:396`). Check: a mismatch raises ValueError naming both shapes. Source: O-12.

### 17-22 `classify_layer_from_depth` refuses bad arguments

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: nothing.
Writes: `jnwb/addressing.py`, its tests, `artifacts/changelog.d/layer-depth-arguments.changed.md`.
- 17-22: an unrecognised `depth_unit` ("micrometre") or a negative `threshold` returns the label "Unknown" (`addressing.py:650-716`); ruled 2026-10-25: both raise ValueError, and "Unknown" stays for data that cannot be placed. Check: both inputs raise naming the argument; the docstring and changelog say so. Source: O-14.

### 17-52 `artifact_detection` flags outliers when the MAD is zero

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/artifact_detection.py`, its tests.
- 17-52: when more than half the values tie, the MAD is 0 and every z is set to 0, so a gross outlier among ties is not flagged (`artifact_detection.py:47`). Check: [0]*9 + [1e6] flags the last value; all-equal input flags none. Source: O-15.

### 17-43 PSI refuses an `nperseg` longer than the signal

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing.
Writes: `jnwb/connectivity/_psi.py`, its tests.
- 17-43: PSI clips `nperseg` to the signal length silently where `compute_psd` refuses. Check: `nperseg` above the length raises ValueError as `compute_psd` does. Source: O-16.

### 17-44 `_surrogate_source` draws a uniform derangement

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: nothing.
Writes: `jnwb/connectivity/_common.py`, its tests.
- 17-44: `_surrogate_source` may draw a non-uniform derangement (inferred by reading, `_common.py:167`). Check: over 10,000 draws at n = 4 each of the 9 derangements appears within a chi-square bound (seeded `rng`); a draw that is uniform deletes this item. Source: O-16.

### 17-45 `epoch_continuous` reads the series start time

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `jnwb/continuous.py`, its tests.
- 17-45: `epoch_continuous` may assume sample 0 at t = 0 (inferred by reading, `continuous.py:27`). Check: a series starting at t = 2 s epoched at 3 s returns the samples from 1 s in; a pass on the current code deletes this item. Source: O-16.

### 17-48 Event `codes` refuse bytes and bool

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: nothing.
Writes: `jnwb/nwb_events.py`, its tests.
- 17-48: event `codes` accept bytes and bool values. Check: each raises TypeError naming the value's type; integer and string codes pass. Source: O-16.

### 17-26 Fact checks fail on an empty examined set

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/fact_gate.py`, `scripts/gates/boundary.py`, `tests/test_fact_gate.py`.
- 17-26: `routes` returns [] on an empty graph and `lifecycle` may too (`fact_gate.py:175-196`); a fact file with headers and no rows gives HELD 0, UNHELD 0, VIOLATED 0 (`:404-437`); `boundary.py:268` returns [] with neither `tests/` nor `scripts/` present. Check: each fails on its planted empty case. Source: O-19.

### 17-27 Gate 20 checks the state in every CI job that runs the harness

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `.github/workflows/workflow.yml`, `tests/test_workflow_release_policy.py`.
- 17-27: gate 20 returns [] when `artifacts/state.md` is absent (by design for a fresh checkout), and CI regenerates it on one test leg only (`workflow.yml:161-166`), so the build job's harness run (`:349`) checks no state. Check: every job that runs `harness_gate.py` runs `reconstruct_state.py` first; a workflow test asserts it. Source: O-20.

### 17-30 S12's guard derives the device-capable set

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `tests/test_execution_switch.py`.
- 17-30: `test_every_export_with_a_cuda_path_records_its_device` compares two hand-written sets (`DEVICE_CALLS`, `RECORD`), so a new CUDA path outside both passes; the CUDA agreement test is skipped in CI, which has no GPU. Check: the CUDA-capable exports are read from the package (the backend dispatch), and a planted CUDA path with no record fails; the skip is stated in the test's reason string. Source: O-23.

### 17-31 The boundary checks fail on what they cannot parse, or go

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 17-26 (same file), 15-20 (the inventory decides).
Writes: `scripts/gates/boundary.py`, `scripts/harness_gate.py`, `tests/test_harness_adversarial_gates.py`.
- 17-31: `check_logarithm_last_rule` returns [] on code it cannot parse (`boundary.py:429-430`), and it and `check_modality_isolation` run in no numbered gate. Check: a parse failure is a violation; each check joins a numbered gate (`GATES` stays 22) or is deleted with its tests, whichever the 15-20 inventory supports. Source: O-24.

### 17-32 The release gate's helpers that nothing runs

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/release_gate.py`, `tests/test_release_recovery_gates.py`.
- 17-32: three helpers (`release_gate.py:1110`, `:1170`, `:1248`) have no production caller, so their tests check code the gate never runs. Check: the tests call `check_release_readiness`; the helpers are deleted; the suite passes. Source: O-25.

### 17-54 D12's "documented" reads a heading or code span

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 17-41 (same files).
Writes: `scripts/fact_gate.py`, `scripts/build_fact_graph.py`, `tests/test_fact_gate.py`.
- 17-54: D12's `documented` state holds on any word match of the name. Check: a name present only in prose fails; a heading or code span passes. Source: O-26.

### 17-55 The export scan reports what it does not examine

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 17-54 (same files).
Writes: `scripts/build_fact_graph.py`, `tests/test_fact_gate.py`.
- 17-55: one export scan of `scripts/build_fact_graph.py` skips exports that are neither classes nor functions without counting them (the lane names the scan first). Check: the scan reports the count it skipped; a planted constant export is counted. Source: O-26.

### 17-56 Test files stop appending to `sys.path`

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 12-06 (same files).
Writes: `tests/**/*.py`.
- 17-56: 69 test files append to `sys.path` though `pyproject.toml` sets `pythonpath=["."]`. Check: `git grep -c "sys.path.insert\|sys.path.append" -- tests` reads 0 or each remaining site states why; the suite passes. Source: O-26.

### 17-34 The jaxfne comparison and the preference questions

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `artifacts/evidence/0.2.14/jaxfne_docs_dashboard_comparison.md`.
- 17-34: 17-01, 17-02 and checklist rows 9 and 10 wait on a comparison with jaxfne's docs and dashboard and on Hamm's preference rulings (2026-10-24), and no item holds that work. Check: the comparison is committed, and its questions go to Hamm one per message; each answer is a row in that day's rulings. Source: O-32.

### 17-36 The standing rulings table is current

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `artifacts/rulings/standing.md` (Hamm reviews).
- 17-36: `standing.md` reads "as of 7cb72f4b" and has no row for the standing rulings of 2026-10-20 to 2026-10-25 (B3, S8, I3 and S9 scopes, the I1 split, the F1 list, the verdict set, 0.2.14 scope), and its "Planned cycles" row (`standing.md:23`) still reads 0.2.8 to 0.2.12 with at most three writers, which the 2026-10-06 and 2026-10-24 rulings replaced. Check: each such ruling has a row citing its dated file; the "Planned cycles" row states the current cycle and writer policy; the "as of" commit is current. Source: O-34.

### 17-41 No UNHELD fact names an item of the declared version

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 17-26 (same files).
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`.
- 17-41: the fact gate requires only that an UNHELD fact names a live item, so checklist row 5 and goal G2 are read by eye. Check: at the checkpoint, an UNHELD fact whose item carries the declared version's release fails the gate; a planted one fails. Source: O-41.
