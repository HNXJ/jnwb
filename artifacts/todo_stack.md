# 0.2.13

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. This
stack holds the 0.2.13 items with their full text and the 0.2.14 plan; 0.2.14's items stay one row
each in `artifacts/roadmap.md` and move here with their full text when 0.2.13 is tagged. 0.2.12
closed on 2026-10-14 with every item done or ruled to 0.2.13 (`git log -- artifacts/todo_stack.md`,
`artifacts/rulings/2026-10-14.md`).

Theme (ruled 2026-10-19): inference and refusal correctness: the 2026-10-18 audit's repairs, the
rulings of 2026-10-18 and 2026-10-19, and 12-10. Acceptance: `artifacts/goal.md` and `AGENTS.md` §11.
Plan (ruled 2026-10-19): two checkpoints, the 0.2.13 release and the 0.2.14 release; each closes
when its checkpoint table passes row by row.

Every item here carries `deferred-0.2.13`, the one deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.12 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

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

| Wave | Lane | Items, in order | Owns | Waits for |
|---|---|---|---|---|
| 1 | C calibration | open-stack F-64 | `scripts/calibrate_curation.py`, `tests/test_curation_calibration_receipt.py`, `artifacts/benchmarks/calibration/curation_calibration_0.2.13*` | nothing |
| 1 | D docs | 15-19, then 12-23 | `jnwb/laminar/_vflip2.py` (docstring), `docs/laminar.md`, `skills/jnwb-laminar/SKILL.md` | nothing |
| 1 | A addressing | 15-23 | `tests/test_addressing.py`, `tests/fixtures/omission_boundaries.json`, `scripts/pin_omission_boundaries.py` | nothing |
| 2 | Checkpoint | the 0.2.13 checkpoint below | `jnwb/__init__.py`, `CHANGELOG.md`, `artifacts/changelog.d/`, `artifacts/benchmarks/performance/`, the closure receipt | wave 1 merged and the open stack empty |

### 15-19 `vflip2`'s null acceptance stated by spacing

Release: deferred-0.2.13.
Role: jnwb-developer. Skill: jnwb-laminar. Blocked by: nothing.
Writes: `jnwb/laminar/_vflip2.py` (docstring only), `docs/laminar.md`, `skills/jnwb-laminar/SKILL.md`.
- 15-19: `omega_cut` 6 is kept (ruled 2026-10-19), but no docstring, page or skill line states its measured null acceptance by contact spacing (`artifacts/evidence/0.2.13/vflip2_nuisance.md`: 0 of 100 at 25 and 50 um, 24 at 100 um, 37 at 150 um, 39 at 200 um). Check: each of the three files names those counts, read from the receipt, and cites it. Waits: docs only; the rate is measured.
Accept: the counts equal the receipt's spacing rows; the docs and skill tests pass. Skill line ruled 2026-10-19.

### 12-23 A bootstrap over mice

Release: deferred-0.2.13.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: nothing.
Writes: `artifacts/roadmap.md`.
- 12-23: the showcase's percentile bootstrap over mice (`_temp_jnwb-showcase/scripts/analyze_s1.py:77`) is the percentile mean bootstrap that `StatisticalAnalysis.bootstrap_ci` computes. Check: a probe runs both on the same per-mouse values and seed and shows equal bounds, or names the shape the showcase needs. Waits: no shipped code changes.
Accept: the probe output in the commit that removes the row.

### 15-23 The omission-boundary comparison runs in CI

Release: deferred-0.2.13.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: nothing.
Writes: `scripts/pin_omission_boundaries.py`, `tests/fixtures/omission_boundaries.json`, `tests/test_addressing.py`.
- 15-23: `tests/test_addressing.py:568` skips on every CI leg because no leg installs `omission`. Ruled 2026-10-19: a script run locally against `omission` writes a small table with provenance (the `omission` commit, the jnwb commit, the date); a CI test compares jnwb's resolution with the table, and the live comparison stays local-only. Check: the new test runs on every CI leg and fails on a one-cell edit of the table. Waits: the live arm is unchanged.
Accept: the CI run lists the test as passed on every leg.

## Checkpoint 0.2.13

In order; a failed row stops the checkpoint and returns to the lanes. The steps are `.github/CONTRIBUTING.md`
"Releasing" with the R5 ruling (2026-10-19: CI green on `main` at the SHA that is tagged). Merge,
push and tag are authorized (Hamm 2026-10-19); PyPI's environment approval is Hamm's.

| Step | Command or action | Passes when |
|---|---|---|
| 1 | Read the open stack and this section | `artifacts/open_stack.md` holds no table row; no `###` item above remains |
| 2 | `python scripts/bump_version.py 0.2.13 --date` | the declared version reads 0.2.13 |
| 3 | `python scripts/assemble_changelog.py --version 0.2.13 --date` | `artifacts/changelog.d/` holds no fragment; `CHANGELOG.md` has a 0.2.13 section |
| 4 | `python scripts/measure_peak_memory.py --write` | each growth past 20% and 5 MiB has a reason in `CHANGELOG.md` |
| 5 | Closure pass: a Muse `review` and a Haiku verifier, independently, with the G-04 claims check | `artifacts/process/blocker_fixpoint_receipt.md` names the commit and 0 new release-blocking problems |
| 6 | Full suite, harness gate, docs build; push `dev` | the stamp equals HEAD; CI green on `dev` at that SHA |
| 7 | `python scripts/release_gate.py` | exit 0 |
| 8 | Merge `dev` into `main` with a merge commit; push `main` | CI green on `main` at the merge SHA |
| 9 | Tag `v0.2.13` at that SHA; push the tag | the TestPyPI and verify jobs pass; PyPI waits on Hamm's approval |
| 10 | Install 0.2.13 from PyPI in a fresh venv; import; run the quickstart | the installed version reads 0.2.13 |
| 11 | Move the 0.2.14 roadmap rows here with their full text; 0.2.14 becomes this file's top section | release_gate STEP 0a reads no `deferred-0.2.13` |

# 0.2.14

Theme (ruled 2026-10-19): the public NWB mutation and execution APIs (07-21, 07-22), and the
existing tools brought to their stated contract: fact closure, reading edges, the pitfall
estimators, the deferred laminar and curation work, and the removals ruled for 0.2.14. Items stay in
`artifacts/roadmap.md` until step 11 above. The rulings the plan needs come first (wave 0), one
question per message; the checkpoint is the 0.2.13 table with 0.2.14 in place of 0.2.13.

| Wave | Lane | Items, in order | Writer | Waits for |
|---|---|---|---|---|
| 0 | Proposals | 11-04 (four estimators), 14-07 (`noise_correlation` signature), 13-04 (screen signature and estimand), 15-20 (inventory and prune proposal), the readings 11-07 and 12-11 wait on, 11-32's holder cells, 12-06's line-ending question | Muse drafts; Hamm rules | 0.2.13 tagged |
| 1 | M mutation | 07-21 (the core five), then 07-22 | Muse | nothing |
| 1 | R reading | 11-02 (D10, ruled 2026-09-29: a declared shallow end), 11-01, 16-01, 16-02 | Haiku | nothing |
| 1 | S estimators | 14-07, then 14-06 | Muse | wave-0 rulings |
| 2 | F facts | 10-10, 11-06, 09-04, 11-32, 11-07, 12-11, 11-09, 12-08 | Muse for 10-10, Haiku for the rest | wave-0 readings |
| 2 | L laminar | 15-18, 13-04, 15-22 (a draft to Hamm) | Muse | 13-04's ruling |
| 2 | X outside code | 12-21 (`E:/repos/jaxfne`), 14-08 (`yihan777/alpha_beta_mechanism`) | Haiku | an excerpt or read access; each stops and reports when neither exists |
| 3 | H harness | 12-05 with 15-20, 11-03, 12-07, 09-07, 07-05, then 12-06 | Haiku | 07-22 and wave 2 merged |
| 4 | Checkpoint 0.2.14 | the 0.2.13 checkpoint, for 0.2.14 | integrator | waves 0 to 3 merged |
