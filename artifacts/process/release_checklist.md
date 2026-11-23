# Release checklist, 0.2.17 (path to the release candidate)

A tracking artifact. The release is decided by `AGENTS.md` §11 and `scripts/release_gate.py`; this
file tracks them and is the work plan toward the RC. Scope source: `artifacts/process/release_plan.json`;
item text and Checks: `artifacts/todo_stack.md`; rulings: `artifacts/rulings/2026-11-22.md` and
`artifacts/rulings/standing.md`. Update a row in the commit that changes it; the update log holds history.

Current (2026-11-23): **32.5/100, diagnostic** (Q3; 0.5 of it is the S4 denominator after 17-102 left the plan, not a closure; 17-95 counts once the suite at the integration tip passes); gates 0 of 6 complete. `origin/dev` =
`e1201abb` (suite 11154 passed, 0 failed), CI pending; CI green at `d918bf46` (push 45180968913, pull request
45180979412). Integration tip on `_temp_rc-integration`. Open stack: one row (`17-144-src`). Owner decisions: section 9.

## 1. RC target

| Field | Value |
|---|---|
| Target | `0.2.17rc1`: an untagged commit on `dev` at which gates A1 to A6 pass, CI is green and every 0.2.17 scope item is closed or ruled out of scope, independently verified (Q2, ruled 2026-11-22). A tag (`v0.2.17rc1` publishes to TestPyPI only, `.github/workflows/workflow.yml:579-595`), a `main` merge and publication are Hamm's (D3) |
| Scope | The six scope lines of `release_plan.json` 0.2.17 (rows S1 to S6, section 6), plus the cycle-required items no scope line names: 17-147, 17-150, 17-153, 17-154, 17-157, 17-158 (in the plan's `items` since Q3, 2026-11-22; 17-147, 17-150, 17-153, 17-154, 17-157, 17-158 closed) |
| Acceptance | `AGENTS.md` §11 (full text `artifacts/rulings/standing.md`); gates A1 to A6 below, each with a receipt at the RC SHA |
| Excluded | Everything in `artifacts/roadmap.md` (0.2.18 and later, including 17-102, 17-151, 17-155, 17-156 moved there 2026-11-22); Python 3.15 on Windows (goal 12); GPU paths, which CI cannot run (declared unverified, goal 11; tiered CI is 0.2.19) |
| Owner-gated, never by an agent | version bump and CHANGELOG assembly (the release step, `AUTONOMY: none`), any push to `main`, any tag, TestPyPI or PyPI publication, GitHub release, a scope change (goal 9) |

## 2. Required gates: all-or-nothing, receipts bind to the SHA they name

| # | Gate | Pts | Requirements (all) | State |
|---|---|---|---|---|
| A1 | The open stack holds no row | 10 | `artifacts/open_stack.md` empty; `tests/test_release_requires_an_empty_open_stack.py` | blocked: `17-144-src` (outside input, D1) |
| A2 | Suite and CI green at the tip | 10 | `jnwb_suite.sh` 0 failed at the tip SHA; every `CI/CD` run at that SHA completed and succeeded | pending: suite 0 failed at `68995c90` (11093 passed). CI there: every test job green on both runs; pull-request run 45083354762 success; push run 45083350199 attempt 1 failed in the build job's installed-wheel leg on one test (a Jupyter kernel port race, 17-158; the pull-request wheel leg passed the same 11079 tests); attempt 2 (failed job rerun) pending. CI failed at `c53c78fe` (shallow checkouts: gate 15 found no tag) and at `8d5fb637` (Windows: `git clone --local` across drives); both repaired, section 8 |
| A3 | Documentation low-verbosity and consistently formed | 5 | `harness_gate.py` 22 of 22; `docs_build.py` strict passes; docs-form tests pass; the §11 verbosity review | incomplete: harness 22 of 22 at `68995c90`; docs build passed at `c24898eb`; verbosity review not run (task R2) |
| A4 | Code low-complexity | 5 | no function above 40 by ruff C901 (`max-complexity = 40`, `pyproject.toml`) over `jnwb/` (ruled 2026-11-22; McCabe, not a maintainability measure; distinct from the AST counter) | incomplete: none above 40 locally (largest `cluster_permutation_test` 39, margin 1); not run in CI (ruff in no dependency or workflow; `tests/test_complexity_ceiling.py` skips there): item 17-157 |
| A5 | `scripts/release_gate.py` STEP 0 passes | 5 | `PYTHONPATH=<tree> python scripts/release_gate.py` (the installed jnwb 0.2.11 shadows the tree otherwise; ruled workaround) | incomplete: STEP 0a failed at `c24898eb` on open rows, a stale closure receipt (`16233114982d`), 3 unassembled `changelog.d` fragments (assembled only at the release step) and `main` not resolving in that clone |
| A6 | Independent closure pass finds no new blocker | 5 | a `reviewer` run on the RC tip, each advertised scientific claim checked against the deferred rows; receipt `artifacts/process/blocker_fixpoint_receipt.md` at that SHA | not run (task R3, last) |

## 3. Environments and coverage

| Environment | What runs | Gate |
|---|---|---|
| CI `test` | Ubuntu and Windows x Python 3.12, 3.13, 3.14; 3.15 on Ubuntu; full history checked out (`fetch-depth: 0`, `8d5fb637`) | A2, required |
| CI `test-floors` | dependency floors, Python 3.12.0, Ubuntu 24.04 | A2, required |
| CI `test-pandas3` | pandas 3, Python 3.13, Ubuntu | non-blocking leg; failures are read, not waived silently |
| CI `build` | harness gate on a full clone, sdist and wheel, the installed-wheel test leg | A2, A3 |
| Tag runs (owner) | TestPyPI upload and verify; PyPI only for a final tag; GitHub release | release step only |
| Local Windows host | `bash scripts/jnwb_suite.sh <dir> <log> <basetemp>` (`-n 12`, `faulthandler_timeout=900`, through the machine suite lock, basetemp outside the repo); CUDA tests run here only | A2 stamp, GPU evidence |
| Local release check | `PYTHONPATH=<tree> python scripts/release_gate.py`; `python scripts/docs_build.py` | A3, A5 |

Declared not run in CI: GPU tests (no device), `tests/test_complexity_ceiling.py` (no ruff, until 17-157), the live-tree gate-15 test only where no tag is reachable.

## 4. Execution plan (dependency order; up to three lanes at once, reviewers included)

Every task: a linked worktree from the then-current `dev` tip (the baseline, a full SHA in the packet;
`scripts/verify_lane.py --baseline <sha>`), the item's Check from `artifacts/todo_stack.md` as acceptance, a
verifier that did not write it (a second, `jnwb-critic-sonnet`, for public-API or scientific changes),
then merge, full suite at the merge tip, push through `scripts/jnwb_push.sh`, CI read at the pushed SHA.
A closing condition is always: Check met, verifier ACCEPT, merged, suite and CI green at the merge SHA.

| Order | Task | Item (row) | Role | Blocked by | Next action |
|---|---|---|---|---|---|
| 0 | Suite at the merged tip, push, CI | integration | integrator | none | `e1201abb` pushed (suite 11154 passed), CI pending; next tip carries the 17-127 speedup; if red: logs, diagnose, repair, normal gates, no override |
| 6 | Tracked rules cite tracked roles | 17-101 (S4) | integrator | D4 | merged 22eca3d2; two live hits left, both owner-gated |
| 10 | One home per helper in `jnwb/` | 17-94 (S2) | `jnwb-actor` | 4 (file overlap) | after 17-96 lands |
| 11 | Docstrings and tolerance constants | 17-128 (S5) | `jnwb-actor` | 10 | narrowed Check (ruled) |
| 12 | Docs thinning remainder | 17-100 (S4) | `docs-harness` | 0 | widen Writes to the named blocking tests |
| 13 | Fact graph build under 60 s | 17-127 (S5) | `jnwb-actor` | 0 | speedup merged `790b1a10`; idle-host timing by a non-author, or one shared parse per file |
| 16 | One home per invariant | 17-99 (S4) | `jnwb-developer` | D2 | |
| 17 | Prose against the writing style | 17-129 (S5) | `docs-harness` | 12, 16 | spelling clause narrowed to new prose (Q5) |
| 18 | External ground truth | 17-144, 15-11, 12-21, 16-12 (S6) | human input | D1 | in scope (Q1); raise D1 when it is the critical path |
| R1 | Refresh peak memory and import receipts | release | `jnwb-actor-haiku` | 1 to 18 | `scripts/measure_peak_memory.py`, `scripts/benchmark_import.py --write` |
| R2 | §11 verbosity review | A3 | `reviewer` | 12, 17 | report under `artifacts/evidence/0.2.17/` |
| R3 | Closure pass and receipt | A6, A5 | `reviewer` + `jnwb-critic-sonnet` | everything above | `blocker_fixpoint_receipt.md` at the RC SHA; then A5 |
| R4 | Release step | release | Hamm | R3, D3 | version, `scripts/assemble_changelog.py`, merge to `main`, tag: owner only |

Stop and report when: a gate fails for a reason no task above covers; two repair attempts fail; a
surprising number appears; a task needs a reserved action (section 1) or a ruling not in the rulings files;
or only tasks blocked on section 9 remain.

## 5. Status

| Class | Items |
|---|---|
| Verified closed (receipts in the update log) | 17-79, 17-97, 17-98, 17-103, 17-154 (section 7), 17-157, 17-96, 17-142, 17-147, 17-153 (suite 11147 passed at `d918bf46`), 17-150 (pending the suite at the integration tip); open rows cleared 2026-11-22 (fact cites, gate 15, push override, guard, hang moved, OCMA-5 moved) |
| Landed, item still open | 17-94, 17-100, 17-128 (partials 2026-11-21 to 2026-11-23) |
| Pending verification | full suite and CI at the merged tip |
| Blocked on owner | D1 (S6, `17-144-src`), D2 (17-99), D3 (R4) |
| Unknown | whether the pull-request merge-commit run differs from the push run at `68995c90` (no run read yet); suite stall cause (none since the dump flag; a stall in the controller or between tests would fire no dump, inferred) |

## 6. Weighted progress (60): diagnostic, not a gate (Q3, ruled 2026-11-22)

An item counts as closed only when its todo heading and its id in the plan's `items` list are gone, its
change is merged on `dev` with the suite green, and an independent reviewer accepted it. Denominators follow
the plan's `items` list; 17-102 left it on 2026-11-22 (Q3), so S4 counts four items. That moves S4 from 2 to 2.5 points with no new closure.

| # | Plan scope row | Pts | Items | Closed | Earned |
|---|---|---|---|---|---|
| S1 | The largest functions split below a stated complexity | 10 | ~~17-79~~ | 1 of 1 | 10 |
| S2 | One home per helper in jnwb, scripts and tests; dead code and unused constants removed | 10 | 17-94, ~~17-95~~, ~~17-96~~, ~~17-142~~ | 3 of 4 | 7.5 |
| S3 | Tests named by subject, not by the event that produced them | 10 | ~~17-97~~, ~~17-98~~ | 2 of 2 | 10 |
| S4 | Docs and examples thinned; one home per invariant | 10 | 17-99, 17-100, 17-101, ~~17-103~~ | 1 of 4 | 2.5 |
| S5 | Code and prose matched to the style standards; the fact graph build made faster | 10 | ~~17-104~~, 17-127, 17-128, 17-129 | 1 of 4 | 2.5 |
| S6 | Validations on external ground truth | 10 | 17-144, roadmap 15-11, 12-21, 16-12 | 0 of 4 | 0 |

## 7. Closure receipts awaiting the update log

| Item | Receipt |
|---|---|
| 17-154 closed 2026-11-22, independent verifier ACCEPT | `scripts/jnwb_suite.sh` full-run command carries `-o faulthandler_timeout=900` at each SHA (merge `7bc91d79` an ancestor); full runs at `c53c78fe` (11092 passed, 877.75 s), `8d5fb637` (11093 passed, 880.29 s), `68995c90` (11093 passed, 836.00 s); 0 failed, 0 `Timeout (`, 0 `Thread 0x`; run windows inside each SHA's reflog interval; stamp proven only for `68995c90`. Two stalls in about five runs on 2026-11-18/19 make clean runs weak evidence against a rare stall; a recurrence reopens it |

## 8. Known failures, waivers and risks

| Item | Evidence | Scope | Status |
|---|---|---|---|
| CI red at `c53c78fe`: gate 15 found no `v*` tag in shallow test checkouts | runs 45066157361, 45066162229 | all test legs | repaired `8d5fb637`, guard test added |
| CI red at `8d5fb637`: explicit `git clone --local` dies on a failed cross-drive hardlink | run 45073612887 | Windows legs | repaired `68995c90`; CI pending |
| Notebook kernel lost a port race in the wheel leg | push run 45083350199 attempt 1, `ZMQError: Address already in use`; the pull-request run at the same SHA passed | `tests/test_notebooks.py`, any leg | repaired: POSIX on `ipc` (merge `7ccd4001`), Windows bind retry (merge `f2dd4b7a`, collision observed, WSL and Windows 11 passed) |
| C901 margin 1 | `ruff check --select C901 jnwb/`: max 39; enforced on the ubuntu 3.12 leg since 17-157 (merge 84c34d56); the policy test checks the leg condition by substring, so an `||` condition would pass | A4 | watch; a function at 41 turns that leg red |
| Gate 15 matches clauses by word overlap: a deleted clause passes when another keeps its obligation word | verifier, merge `3f6f7e86` | gate 15 | repaired, merge `952cb357` (17-147 D1; the old rule as a mutant fails a test) |
| Installed jnwb 0.2.11 shadows the tree for `release_gate.py` run as a script | `ImportError: _declarations` | local A5 runs | ruled workaround `PYTHONPATH` |
| `pandas3` leg is non-blocking | `workflow.yml` | CI | failures read and recorded, not waived |
| Superseded unmerged lanes | `_temp_17-103-contributing`, `_temp_17-143-tag-push` on `origin` (items closed by other commits) | none | archived to `F:/warehouse/jnwb_branch_archive/superseded_2026-11-23.bundle` (verified), deleted from `origin` 2026-11-23 |
| Uncommitted work in `D:/repos/_wt/jnwb/17-104` | 3 tracked files modified, branch merged | 17-104 | read before any reuse; never discarded without a look |

## 9. Owner decisions

Q1 to Q6 ruled 2026-11-22 (`artifacts/rulings/2026-11-22.md`, "RC owner questions and goal mode"):
S6 stays in scope; the RC is an untagged verified `dev` SHA; the plan is reconciled and the score is
diagnostic; 17-99 waits on Hamm's fact wording; American English for new prose only; 17-104's
imports and CRLF parts dropped. Decision policy: interrupt only when an owner-reserved decision
blocks the critical path.

| Id | Pending owner decision | Blocks | Raised when |
|---|---|---|---|
| D1 | S6 inputs (17-144 commits from jaxfne; Bastos lab simulation; broadband jaxfne field) and who sends the requests | S6, R3 | S6 is the only work left before R3 |
| D2 | The spikes-and-LFP fact-row wording for 17-99 | 17-99 | 17-99 is on the critical path |
| D3 | Tag, `main` merge and publication of the verified RC | R4 | R3 passes |
| D4 | 17-101 remainder: roadmap 17-138 (vendor `suite_lock.py` or name the dependency, `memory.md:7`); rewording "the scratchpad" in the corpus-access ruling (`standing.md:20`) | 17-101, S4 | 17-101 is the last open S4 item besides 17-99 |

Recorded for review, not blocking: 17-153's check tests the first `path:line` cite of each B3 exception
row; a continuation cite after `;` (reason code, not the default) is exempt. The independent verifier read
all 11 continuation cites the strict form fails; each points at reason code and none is stale.

## Update log

| Date | SHA | Change |
|---|---|---|
| 2026-11-18 | `b442e2b1` | Created. Provisional score 5/100, rescored 0/100 (gates all-or-nothing). |
| 2026-11-18 | the commit that lands 17-103 | 17-103 closed; S4 1 of 5; score 2/100. |
| 2026-11-19 | `9ad92d4b` | Suite 11021 passed; CI success; verified 2/100. `17-147-hang` opened. |
| 2026-11-19 | `e6baac97` | 17-79 closed (five functions split, each independently reviewed); S1 1 of 1; score 12/100. |
| 2026-11-20 | the commit that closes 17-98 | 17-98 closed; S3 1 of 2; score 17/100. `vflip2-receipt` cleared. |
| 2026-11-21 | `e5dd5aec` | Partial landings of 17-94, 17-100, 17-104, 17-95, 17-128, 17-147; suite 11081 passed. Score 17/100. |
| 2026-11-22 | `81e36e3e`, `7ecaf327` | Partial landings of 17-142 and 17-97 slice 1; provisional rulings; ruling packet; A3 docs build at `c24898eb`; A4 and A5 measured. |
| 2026-11-22 | `e3af6db8`, `c53c78fe` | Consolidated ruling recorded; open rows 8 to 1; A3 push override, A6 dump flag, A2 gate 15, ruff C901 merged, each verified; suite 11092 passed at `c53c78fe`; CI red there. |
| 2026-11-22 | `8d5fb637`, `68995c90` | Two CI repairs pushed under Hamm's one-time authorizations; suite 11093 passed at each; CI at `68995c90` pending. Checklist rewritten as the RC plan (target, environments, ordered tasks, status, risks, owner questions); the 2026-11-19 snapshot and the 2026-11-18 mapping audit retired into sections 4 and 9. Score 17/100. |
| 2026-11-22 | this commit | Hamm ruled Q1 to Q6 and goal mode; `release_plan.json` reconciled (17-102 to 0.2.20; 17-153, 17-157, 17-158 into 0.2.17); 17-104 and 17-129 Checks narrowed as ruled; 17-154 closed (verifier ACCEPT). Score 17.5/100 diagnostic, the change from the S4 denominator only. |
| 2026-11-22 | merge `cfa5ab9f` | 17-97 closed: slice 2 (`325481d3`) merged the seven laminar files; collected 11213 before and after, name multiset equal, verifier ACCEPT with a full suite at `325481d3` (11092 passed, 0 failed). S3 2 of 2; score 22.5/100 diagnostic. |
| 2026-11-22 | merges `22eca3d2`, `84c34d56`, `7ccd4001` | CI green at `c52d64cb` (push 45093499657, pull request 45093504959). 17-101 merged, remainder owner-gated (D4). 17-157 closed: ruff 0.16.10 C901 step on the ubuntu 3.12 leg; a planted complexity-41 function fails it; verifier ACCEPT on `2a9d98f7` after rejecting a CI-wide fail clause. 17-158 POSIX repaired (`ipc`), Windows open. |
| 2026-11-23 | merges `1eeda9d2`, `bd425e49`, `7e1fc279` | 17-95 listed sites merged (verifier ACCEPT, 274 rows split identically by old and new splitter), remainder named. 17-96 closed: three names deprecated with tests, palette and `DEFAULT_BANDS` kept importable and live, `nwb_read_io` re-frozen at `03fdbc45` (independent kills M1 to M4); verifier and critic, ACCEPT on `7c7dad80`. 17-142 closed: ruff F811/F821/F841 zero over `jnwb/` and `scripts/`. A suite at `eda122a6` timed out after 3600 s in the machine suite lock; never run. Superseded lanes 17-103 and 17-143 archived to `F:/warehouse/jnwb_branch_archive/superseded_2026-11-23.bundle` and deleted from `origin`. Score 27.5/100 diagnostic. |
| 2026-11-23 | merges `6cffdc42`, `952cb357` | 17-153 closed: the fact gate reads each B3 exception cite (a planted stale cite turns it red; verifier ACCEPT on `ad9f0d3e`); it found three stale cites (row 189, and two shifted by 17-96), each re-cited. 17-147 closed: D1 match rule tightened, D2 ancestor-tag test, `_refusal` names its error; verifier ACCEPT on `e8036d0b` (65 passed, D1 and D2 mutants killed). Score unchanged (neither is in a scope row). |
| 2026-11-23 | `d918bf46`, merge `b83bc468`, `507e4cfb` | Suite at `8769bc5e` failed 1 (17-96 deprecation notes undeclared in the version-claim test); declared at `d918bf46`; suite 11147 passed there; pushed to `dev`. 17-150 closed: AST sign-guard scan, verifier ACCEPT on `7340b8bf` (mutants red, stale allow-list entry fails); it found `classify_layer_from_depth` accepting a NaN `threshold`, refused at `507e4cfb` (test red first; critic REJECT on a stale docstring and fragment length, repaired `18fed6d5`); `enrich_units_dataframe` keeps the silent path (roadmap 17-159). 17-158 closed: Windows bind retry, verifier ACCEPT on `2a040727`. 17-104 closed (merge `ab5a2909`): `growth_rows` counts every `.py` under `scripts/`, verifier ACCEPT on `6c4330b1` after a first review found `gates/` and `figures/` uncounted too; S5 1 of 4; score 30/100 diagnostic. |
| 2026-11-23 | `e1201abb`, merge `790b1a10` | CI green at `d918bf46`; suite 11154 passed at `e1201abb`, pushed to `dev`. 17-127 speedup merged (verifier ACCEPT on correctness); under 60 s not shown: 88-114 s at 100% host load, item open. |
| 2026-11-23 | merge `4b24f244` | 17-95 closed: 40 test git sites on `gates.boundary.git`, the rest named with reasons, 14 function-scope `tests` imports guarded and the wheel-leg check extended to them (red on the base tree); verifier REJECT on two unnamed sites, repaired, ACCEPT on `b611d0b2`. S2 3 of 4; score 32.5/100 diagnostic. |
