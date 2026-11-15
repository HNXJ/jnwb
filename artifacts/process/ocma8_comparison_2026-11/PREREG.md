# OCMA-8 against the minimal formation: four-task comparison, preregistration

Status: DRAFT, 2026-11-15. Analysis and acceptance rules are fixed here; the per-task predicate scripts and
packets are prerequisites 3 and 4. Nothing runs until every prerequisite below passes and Hamm says go
(Hamm 2026-11-15: preparation authorized, execution held; no OCMA-wide rollout). Follows the one-task pilot,
`../ocma8_pilot_2026-11-15/RESULTS.md` (jnwb `_temp_ocma8_pilot` 3632f9d4), and repairs its unequal conditions.

## Question and estimand

Do additional reviewers produce more independently resolved defects and more verified completion per unit cost,
or only more defect mentions?

Primary estimand, per task t and arm a: `E = V / C`.
- `V` (verified completion) = 1 when the final tree passes the task's acceptance command, every frozen predicate
  and constraint, and both blind evaluators establish no consequential defect; else 0. Consequential classes:
  wrong-behaviour, wrong-pointer, wrong-value, meaning-change, scope, incomplete. Style is not consequential.
  A defect counts when the orchestrator confirms it against the tree; evaluator disagreement is reported and the
  tree decides.
- `C` (total cost, USD) = agents' tokens at public prices read on the analysis day + the orchestrator's tokens
  spent on that arm of that task (see Cost).
Reported: `E` per cell (8 cells), `sum V` and `sum C` per arm, `sum V / sum C` per arm, and the four paired
differences. No significance test: four pairs give sign and size only.

Secondary: confirmed defects by class; critical-path seconds (wall clock from the arm's first dispatch to its
final tree, lane cap 3); review yield (distinct actionable defects found inside the formation, duplicates merged);
mentions per distinct defect; closure reliability (defects resolved and then independently verified / defects
raised); consequential defects closed.

## Tasks (four kinds; each whole and bounded; nothing is merged by the experiment)

| Task | Kind | Source | Baseline | Acceptance, mechanical |
|---|---|---|---|---|
| T1 | code fix, red test first | jarness T-82: `selfcheck.py` reports a required hook `settings.json` does not wire | jarness `dev` 3fb6fe0 | the new test fails on the baseline and passes; `harness/lint.py`, `audit.py --selftest` pass; the hooks and selfcheck tests pass |
| T2 | refactor, behaviour kept | jnwb 17-95, the `cells()` half: one markdown cell splitter for `scripts/`, honouring escaped pipes | jnwb `dev` ac995dde | one definition (baseline: 5 found by name in 4 files; the item says 8); `harness_gate.py` 22 of 22; the tests that read those scripts pass; gate outputs byte-equal on the tracked tables |
| T3 | test reorganization | jnwb 17-97, the `test_rng_*` group: 4 files merged by subject | jnwb `dev` ac995dde | one `test_rng*.py` file; 146 tests collected before and after, same node names after the file prefix; they pass |
| T4 | state document | jynx `artifacts/state.md` is 9,003 B against `STATE_MAX_BYTES = 6000` | jynx `dev` bc72f27 | at most 6,000 B; `scripts/artifacts_check.py .` ACCEPT; every obligation and SHA of the baseline file still stated in a tracked file the state names |

A task leaves the set, and the set is not refilled, if its baseline moves before the freeze or its
known-negative or known-positive control fails (prerequisite 3).

## Arms

| Arm | Formation | Agents |
|---|---|---|
| A, minimal | orchestrator, worker, reviewer | `worker` (Haiku 5.5, high); `reviewer` (Sonnet 5.5, medium) |
| B, OCMA-8 | orchestrator, keeper, two workers, reviewer, checker, critic, helper | helper `worker` medium; two `worker` high; keeper `worker` high; `checker`; critic `worker` high; `reviewer` (Sonnet 5.5, medium) |

Equal by construction, each a repair of a pilot defect:
- One TASK block per task, sent whole to every agent of both arms. Role blocks hold the role and nothing about
  the task. The helper's block names no command and no hazard.
- Arm B's split: the two workers receive the same TASK block plus one line naming the part; parts are the item's
  own enumerated parts. Where the item has one part (T3, T4), worker 2 drafts independently and the keeper takes
  the tree that passes more predicates (tie: worker 1). The orchestrator writes no decision into a split.
- Acceptance is run by the writer of the final tree and by the reviewer only; no other block mentions it.
- Fix round, both arms, one at most: every finding of every in-formation critic role (reviewer, and in arm B
  checker and critic) and every open item in a writer's or keeper's report goes verbatim to the writer of the
  final tree, whatever the reviewer's verdict; then one closing review by a fresh `reviewer`. No findings, no
  round.
- The orchestrator sends frozen packets verbatim, forwards output only into a packet's slot, and logs every other
  action as an intervention. A finding against a packet stops that cell; the cell is reported as void, not rerun.
- Same tools, permissions and effort per agent type; each writer in its own linked worktree at the baseline.

## Order and blinding

Arms run one after the other within a task, never concurrently, so load and orchestrator tokens separate.
Order: T1 A then B; T2 B then A; T3 A then B; T4 B then A (alternation fixed here).
Evaluation: each final diff is applied to a fresh worktree at the baseline under a label drawn with
`random.Random(2026111500 + task number)`, named `eval_t<n>_<p|q>`; evaluators see only those paths, the TASK
block and the defect classes. Two evaluators per task, independent: `reviewer` (Sonnet 5.5, high) and a scorer
from another model family through `delegate-cli` (opencode Muse, read-only).

## Cost

- Agents: `~/.claude/subagent_runs.jsonl` once P-26 (jarness open stack) is repaired, and the transcripts by
  `pilot_usage.py` and `pilot_cost.py`; both reported; a difference above 1% per agent is a finding.
- Orchestrator: the main session's usage rows in its own transcript between the arm's first dispatch and its
  final tree, priced the same way, reported beside the agents' cost and inside `C`. Possible because arms do not
  interleave. Evaluation and the record's review are outside both arms and reported apart.
- A cell whose cost cannot be measured is reported with `C` unknown and leaves the primary estimand.

## Decision rule (Hamm 2026-11-15, fixed)

If OCMA-8 does not improve `sum V` or consequential defects closed while its `sum C` is at least 1.25 times arm
A's, prefer the minimal formation, unless a task kind shows a measurable advantage: on that task `V_B > V_A` or
more consequential defects closed in B. Four tasks do not license a rate; the report says so. Failures, void cells
and inconclusive outcomes stay in the record.

## Prerequisites (each a gate; none passed yet)

1. Telemetry: P-26 repaired, a real subagent run writes one correctly attributed row, and a resumed run writes
   `.2`, not a duplicate.
2. Cross-family scorer: one smoke packet through `delegate-cli` returns a parsed report on this host.
3. Per task: a frozen predicate script scoring 0 on the baseline (known negative), the acceptance command passing
   on the baseline (known positive), and the baseline SHA re-read.
4. Packets written and frozen; an independent `reviewer` reads them for any information or decision one arm gets
   and the other lacks: ACCEPT.
5. T1 and T4 touch jarness and jynx trees only in experiment worktrees; their items stay open for those keepers.
6. Hamm's go.
