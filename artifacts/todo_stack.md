# 0.2.15

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.14
closed on 2026-10-27 (tag `v0.2.14`). Items run fastest first; the lanes below split them into
parallel writers that share no file.

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet (`artifacts/skills/jnwb-fact-action` §5); a lane is one clone and one Haiku 5.5 `worker`; up to three lanes at once; a lane's items run in the order listed | lanes share no file, so they merge without conflict |
| A public signature, an estimand or a skill line goes to Hamm before code, batched in one message per wave; Haiku implements a ruled signature and never chooses one | public API and skills are Hamm's |
| A packet reproduces its bullet first, writes the failing test, then the fix; a `reviewer` that did not write it verifies; the integrator commits, owns the stacks, `CHANGELOG.md` and `docs/api.md` | the actor is never the verifier |
| Wave barrier: `python scripts/harness_gate.py`, the full suite, push, CI green on `dev` at that SHA | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then one bullet:
`ID: defect with numbers. Check: a predicate naming the file and the asserted value. Waits: why.`
At most eight lines per item.

## Path to the release

One ordered path from now to the tag. Each step names its check; a pass goes to the next step, a fail
takes the branch under it. Steps on one line run in parallel lanes (one Muse or Haiku writer per
clone, at most three); the integrator reads each diff and reruns its acceptance before merging.
Done 2026-10-31 and deleted: wave 3 (16-20, 11-09, 17-05, 17-72, 17-73), 17-07, the 17-24 scan, the open
stack to zero (P-215-28 in 4e87a5bf), the agy docs sweep.

1. Barrier at the integration HEAD: harness gate, suite, push `dev`, CI green.
   - Fails: repair the failing test or item text, rerun from 1.
2. 17-24 repairs, three lanes from 93fd20e1: R1 naming gap (14) | R2 array math refuses (17) | R3 NaN is
   missing (15), after R1 or R2 frees a slot. D1 (verified doc fixes) shares the slot cap.
   - A repair would change a released number, or a function handles NaN on purpose: ask Hamm.
   - A lane fails its acceptance: send it back once with the failure; a second fail, the integrator does it.
3. 17-71: profile at 93fd20e1 (`--durations=0`, junit) through the lock; write the tiered-CI plan. Plan only.
   - Hamm approves the plan: a 0.2.16 item changes `workflow.yml`. Not approved: the plan stays a receipt.
4. Barrier, as 1.
5. Release mechanics, in order: assemble `CHANGELOG.md` from `artifacts/changelog.d/`; bump `__version__`
   to 0.2.15; merge `origin/main` into `dev`; regenerate state; barrier as 1.
6. Closure pass: an independent blocker-focused review (reviewer and agy, different models) checks each
   advertised claim against the deferred rows; its receipt is committed at HEAD.
   - A new blocker: it becomes an item, back to the step that owns its file.
7. `python scripts/release_gate.py` with the checkout on `PYTHONPATH`: passes; checklist 13 of 13.
8. 17-74, after the gate: merge to `main`, tag `v0.2.15`, tell omission on Hamm's word.

Deferred to 0.2.16, off the path: 17-75 (deletions only Hamm runs), 17-76, 17-77, 17-78, 17-79, the
roadmap rows.

### 17-24 Non-finite inputs fail loudly

Release: required-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `tests/test_nonfinite_inputs.py`, `scripts/build_fact_graph.py`, then one repair per function in its own module. Ruled 2026-10-31: split into scan and repairs; refuse; audit ids retired.
- 17-24 wiring: the scan landed in cb57c4f3 (166 functions; 216 pass, 47 strict xfail in `AWAITING_REPAIR`), and S9's holder does not call it yet. Check: S9's holder in `scripts/build_fact_graph.py` names `tests/test_nonfinite_inputs.py`, and `AWAITING_REPAIR` is empty.
- 17-24 deliberate NaN: R2 left eight functions that handle NaN on purpose, pinned by tests: `to_db` (fed by `aggregate_to_db`), `normalize_waveforms`, `network_topology` (diagonal), `bad_channels_from_correlation`, `bad_trials_single_channel`, `trial_correlation_matrix`, `pairwise_phase_consistency`, `phase_locking_index`. Check: each docstring states its NaN behavior and each sits in `NAN_PROPAGATES` or `NAN_IS_MISSING`.
- 17-24 repairs (lanes R1, R2, R3 in the path): each silent function raises `ValueError` naming the argument on NaN or inf, unless its docstring states NaN propagation (`to_db` is the first to check). Ruled 2026-10-31, split by kind: array-math functions refuse; DataFrame, metadata and gap-handling functions keep NaN as missing, say so in the docstring, and are listed in the test's `NAN_IS_MISSING`. Check: the function's row in `tests/test_nonfinite_inputs.py` fails on the baseline and passes after.

### 17-71 Suite profile and a tiered-CI plan

Release: required-0.2.15.
Role: jnwb-developer. Skill: none. Blocked by: nothing. Ruled 2026-10-31: plan only; `workflow.yml` is unchanged until Hamm approves the plan.
Writes: `artifacts/evidence/0.2.15/suite_profile.md`, `artifacts/evidence/0.2.15/tiered_ci_plan.md` (new).
- 17-71: the only suite profile is 0.2.14's (`artifacts/evidence/0.2.14/verification_inventory.md` D13-D19) and no tiered-CI plan exists. Check: `suite_profile.md` gives per-file durations from `pytest --durations=0` at a named 0.2.15 SHA; `tiered_ci_plan.md` assigns every test file to a tier, and the fast tier's measured total is given.

### 17-74 Tag 0.2.15 and tell omission

Release: release-step-0.2.15.
Role: human. Skill: none. Blocked by: the release merge to `main`; the notice needs Hamm's word.
Writes: `artifacts/rulings/2026-10-31.md`.
- 17-74: from open rows P-215-03 and P-215-14. Check: `refs/tags/v0.2.15` peels to the release commit on `main`, and the rulings file records Hamm's word on the omission notice.

### 17-75 Workspace cleanup

Release: deferred-0.2.16.
Role: human. Skill: none. Blocked by: the agent may not delete these (classifier and push guard).
Writes: `artifacts/open_stack.md`.
- 17-75: from P-215-05 and P-215-15. Hamm deletes the origin branches `proposal/spike-qc-pt-skill` and `skill/spectrolaminar-work-bastos` (kept as `_temp_spike-qc-pt-skill`, `_temp_spectrolaminar-work-bastos`), the folder `.claude/worktrees/site-overview-326890` then `git worktree prune`, `C:/workspace/_temp_lane_*` (8 clones, each clean and contained in dev, checked 2026-10-31), `C:/workspace/_temp_oc` and the scratchpad `lanes/`. Check: `git ls-remote origin` lists neither old name and `git worktree list` shows one entry.

### 17-76 agy retry

Release: deferred-0.2.16.
Role: actor. Skill: none. Blocked by: nothing.
Writes: `artifacts/rulings/2026-10-28.md`.
- 17-76: from P-215-06. The 2026-10-28 work-routing ruling waits on a packet that needs no file reads; agy returned empty before. Check: one no-read packet run through `delegate-cli --backend agy` returns a non-empty answer, recorded under the routing ruling.

### 17-77 Stale pointers in the fact stack and standing rulings

Release: deferred-0.2.16.
Role: human. Skill: none. Blocked by: Hamm's word (the fact stack and the rulings are his).
Writes: `artifacts/fact_stack.md`, `artifacts/rulings/standing.md`.
- 17-77: from P-215-20. `standing.md:144-148` and `fact_stack.md:68,82,86` cite roadmap 17-03 to 17-08 and 17-24, which are done or in this stack; `standing.md:144` says psth keeps `(-1000, 2000)` until 0.2.15, while psth now requires `window_ms`; S13 holds `todo:12-21`, which is a roadmap row. Check: every roadmap or todo id the two files cite resolves in `roadmap.md` or `todo_stack.md`, or is marked done with its commit.

### 17-78 Doc form across pages

Release: deferred-0.2.16.
Role: docs-harness. Skill: none. Blocked by: nothing; `skills/` lines need Hamm's word.
Writes: `docs/*.md`, `skills/jnwb/SKILL.md`.
- 17-78: the 2026-10-31 agy sweep found form drift that blocks nothing (lane D1 fixed the wrong statements): numbered pages 02, 05, 06, 09, 10 end without the `## References` the others carry; page 08 raises operations to H2; `reading_nwb.md` and `coherence_and_tfr.md` number their headings, other concept pages do not; `um`, `µm` and `$\mu$m` all occur; `skills/jnwb/SKILL.md` adds a section 3 the other skills lack; `writing_nwb.md` repeats two refusal rows in three tables. Check: `scripts/docs_form_gate.py` gains one rule per listed form and passes.

### 17-79 Complexity of the largest functions

Release: deferred-0.2.16.
Role: jnwb-developer. Skill: none. Blocked by: a body change voids its `frozen_validated.json` entry (gate 19), so each needs re-verification.
Writes: `jnwb/laminar/_xflip.py`, `jnwb/laminar/_zflip.py`, `jnwb/laminar/_vflip.py`, `jnwb/jrsa/__init__.py`, `jnwb/connectivity/_psi.py`.
- 17-79: at 93fd20e1, 977 functions, median cyclomatic complexity 4; 151 above 10, 56 above 20, 13 above 40; the largest are `xflip` 109, `jrsa` 93, `zflip` 80, `vflip` 71, `phase_slope_index` 67. Standing §11's code condition (algorithmic order, one mechanism per concern) holds through the harness gate; this is size only. Check: each named function split into helpers with the suite and its calibration receipt unchanged, and none above 40.
