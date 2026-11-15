# OCMA-8 against the minimal formation: four-task comparison, preregistration

Status: DRAFT, 2026-11-15. Analysis and acceptance rules are fixed here; the per-task predicate scripts and
packets are prerequisites 3 and 4. Nothing runs until every prerequisite below passes and Hamm says go
(Hamm 2026-11-15: preparation authorized, execution held; no OCMA-wide rollout). Follows the one-task pilot,
`../ocma8_pilot_2026-11-15/RESULTS.md` (jnwb `_temp_ocma8_pilot` 3632f9d4), and repairs its unequal conditions.

## Question and estimand

Do additional reviewers produce more independently resolved defects and more verified completion per unit cost,
or only more defect mentions?

Primary estimand, per task t and arm a: `E = V / C`.
- `V` (verified completion) = 1 when the final tree passes the task's acceptance command and every frozen
  predicate and constraint, and carries no confirmed consequential defect; else 0. Consequential classes:
  wrong-behaviour, wrong-pointer, wrong-value, meaning-change, scope, incomplete. Style is not consequential.
- Confirmed defect: one both blind evaluators raise with the same class, or one that either raises and a fresh
  blind `reviewer`, the adjudicator, confirms. Every defect not raised by both with one class goes to the
  adjudicator, always; its yes or no and its class are final. The class is assigned by the evaluator that raises
  the defect. The orchestrator, who is unblinded, routes by this rule and judges nothing. A cross-family run that
  fails or does not parse is retried once; after that a second fresh Sonnet evaluator replaces it and the cell is
  marked "no cross-family".
- `C` (total cost, USD) = agents' tokens + the orchestrator's tokens spent on that arm of that task (see Cost).
Reported: `E` per cell (8 cells), `sum V` and `sum C` per arm, `sum V / sum C` per arm, the four paired
differences, and all of it again with agents-only cost. No significance test: four pairs give sign and size only.

Secondary: confirmed defects by class; critical-path seconds (wall clock from the arm's first dispatch to its
final tree, lane cap 3); review yield; mentions per distinct defect; false findings; closure reliability;
consequential defects closed. Definitions:
- Each arm's tree is saved as a diff before its review stage (the pre-review tree) and at the end.
- A finding is one statement by an in-formation critic role or an open item in a writer's report, the closing
  review's included. Two findings are the same defect when they name the same file and either overlapping lines
  or the same named symbol; class plays no part in the merge.
- The evaluators work in two passes on blinded trees (Order and blinding). Pass 1: each lists the defects it
  finds on the final tree, with classes, before seeing any finding. Pass 2: each receives the cell's merged list,
  every entry as file, lines and the finder's first sentence with role names removed, and marks each real or not
  on the pre-review tree, with a class, and resolved or not on the final tree. An entry both mark real is
  actionable; both not real, a false finding; a split goes to the adjudicator. A finding of the closing review
  counts as unresolved unless both mark it resolved. Residual risk, stated: a finder's wording can reveal its
  role, and so the arm.
- Review yield = actionable defects per cell. Closure reliability = actionable defects marked resolved by both
  evaluators / actionable defects. Consequential defects closed = those of a consequential class.
- Defect opportunity (pre-review inventory), per cell: every real defect of the pre-review tree, from three
  sources kept apart: introduced by the arm's writers; present in the packet (a finding against the packet, marked
  real by the same pass-2 rule); and found only by the blind evaluators, which the formation missed.
  Discovery = actionable defects the formation raised / inventory. Closure = inventory defects resolved on the
  final tree / inventory. The two are reported apart, per source.
- Findings ledger, per cell: every finding as raised, false ones included, with who raised it, to whom it was
  forwarded, its adjudication, and the tokens and seconds of the fix round and closing review it caused. Nothing
  is filtered or regrouped after results are seen; the merge rule above is applied before the evaluators' marks
  are read.
No defect is seeded: seeding changes the task. So yield is bounded by the defects each arm's writers happen to
make, which differ between arms; the inventory states that opportunity beside the yield.

## Tasks (four kinds; each whole and bounded; nothing is merged by the experiment)

| Task | Kind | Source | Baseline | Acceptance, mechanical |
|---|---|---|---|---|
| T1 | code fix, red test first | jarness T-82: `selfcheck.py` reports a required hook `settings.json` does not wire | jarness `dev` 3fb6fe0 | the new test fails on the baseline and passes; `harness/lint.py`, `audit.py --selftest` pass; the hooks and selfcheck tests pass |
| T2 | refactor, behaviour kept | jnwb 17-95, the `cells()` half: one markdown cell splitter for `scripts/`, honouring escaped pipes | jnwb `dev` ac995dde | one definition (baseline: 5 found by name in 4 files; the item says 8); `harness_gate.py` 22 of 22; the tests that read those scripts pass; gate outputs byte-equal on the tracked tables |
| T3 | test reorganization | jnwb 17-97, the `test_rng_*` group: 4 files merged by subject | jnwb `dev` ac995dde | one `test_rng*.py` file; 146 tests collected before and after, same node names after the file prefix; they pass |
| T4 | state document | jynx `artifacts/state.md` is 9,003 B against `STATE_MAX_BYTES = 6000` | jynx `dev` bc72f27 | at most 6,000 B; `scripts/artifacts_check.py .` ACCEPT; every hex SHA of 7 or more characters and every `O-`, `T-`, `P-` id in the baseline file is in the final file or in a tracked file under `artifacts/`; only files under `artifacts/` change |

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
  own enumerated parts. Where the item has one part (T3, T4), both workers draft the whole item and the keeper
  takes the draft that passes the acceptance command (both pass or both fail: worker 1). The orchestrator writes
  no decision into a split. No agent of either arm sees a predicate script.
- Acceptance is run by the writer of the final tree (arm A: the worker; arm B: the keeper, once per draft it
  chooses between) and by the reviewer; no other block mentions it. The keeper's extra runs are part of arm B.
- Fix round, both arms, one at most: every finding of every in-formation critic role (reviewer, and in arm B
  checker and critic) and every open item in a writer's or keeper's report goes verbatim to the writer of the
  final tree (arm A: the worker; arm B: the keeper; each resumed with its context), whatever the reviewer's
  verdict; then one closing review by a fresh `reviewer` that receives the same findings. No findings, no round.
  Limitation, to be stated in the report: this tests each formation under a forward-everything policy, with no
  orchestrator triage; false findings are forwarded too and their cost is the arm's.
- The orchestrator sends frozen packets verbatim, forwards output only into a packet's slot, and logs every other
  action as an intervention. No cell is voided: a finding against a packet is recorded and the cell goes on under
  the packet as written; if an agent stops, the cell ends there and `V` is computed on the tree as it stands.
- Same tools and permissions per agent type; effort as in the table, `checker` as its agent definition sets it
  (Haiku 5.5, default effort). The critic's block names the two ontology files it may read outside its tree.
  Each writer has its own linked worktree at the baseline.

## Order and blinding

Arms run one after the other within a task, never concurrently, so load and orchestrator tokens separate.
Order: T1 A then B; T2 B then A; T3 A then B; T4 B then A (alternation fixed here).
Carry-over: one orchestrator session runs both arms of a task. It sends frozen packets only and fills a slot only
with that arm's own output, so nothing from the first arm can reach the second through a packet; trees are
separate worktrees. This is stated, not isolated.
Evaluation: each arm's pre-review diff and final diff are applied to fresh worktrees at the baseline under one
label per arm drawn with `random.Random(2026111500 + task number)`, named `eval_t<n>_<p|q>_pre` and
`eval_t<n>_<p|q>`; evaluators and the adjudicator see only those paths, the TASK block and the defect classes. Two evaluators per task, independent: `reviewer` (Sonnet 5.5, high) and a scorer
from another model family through `delegate-cli` (opencode Muse, read-only).

## Cost

- Agents: `C` is filled from the transcripts by `pilot_usage.py` and `pilot_cost.py` (the pilot's method).
  `~/.claude/subagent_runs.jsonl`, once P-26 (jarness open stack) is repaired, is the cross-check; a difference
  above 1% per agent is a finding.
- Prices are fixed now, USD per million tokens, read 2026-11-15 from
  https://platform.claude.com/docs/en/about-claude/pricing: Haiku 5.5 up to 100K prompt 0.10 input, 0.125 and 0.20
  cache write (5m, 1h), 0.01 cache read, 0.50 output; over 100K 0.50, 0.625, 1, 0.05, 2.50; Sonnet 5.5 2, 2.50,
  4, 0.10, 10. The orchestrator is priced by the model id on each of its usage rows, from the model table of that
  page as saved on 2026-11-15 in `prices_2026-11-15.md`; no price is read later. Evaluators, the adjudicator and
  the cross-family scorer are outside both arms: their cost is reported apart and is no part of `C`.
- Orchestrator: the main session's usage rows in its own transcript between the arm's first dispatch and its
  final tree, reported beside the agents' cost and inside `C`. Possible because arms do not interleave. Its
  context grows through the session, so later cells cost more; the alternation spreads this over the arms and
  the agents-only analysis is free of it. Evaluation and the record's review are outside both arms.
- `C` is always the transcript-derived figure; a cross-check difference is reported and changes nothing. Only a
  missing or unreadable transcript makes a cost unmeasurable; that task then leaves the primary sums in both arms
  and is reported apart, whatever its `V`.

## Decision rule (Hamm's stopping rule of 2026-11-15; thresholds approved by him the same day as exploratory criteria)

The thresholds are operational decision boundaries, not significance tests. Three questions are answered apart:
effectiveness (verified completions and consequential defects closed), efficiency (those per total cost), and
adoption (the table below). A closure advantage does not by itself justify adoption at excessive cost, and equal
verified completion does not show equal review quality: the report gives discovery and closure beside `V`.

"Improves" means `sum V_B >= sum V_A` as absolute counts over the same tasks (a task missing a cell in either arm
leaves both sums) and, in addition, either `sum V_B > sum V_A` or distinct blind-adjudicated consequential
defects closed in B exceed those in A by two or more. B never improves with fewer verified completions. Closed
defects are absolute counts; the arms' inventories differ, so each count is reported with its inventory and its
closure fraction, and a lead that rests on the larger inventory alone is named as such. "Substantially more" means `sum C_B >= 1.25 x sum C_A`, all attributable agent and orchestrator cost
included.

| Outcome | Reading |
|---|---|
| B does not improve, B substantially more costly | prefer the minimal formation |
| B does not improve, cost within 1.25x | no reason to adopt OCMA-8; prefer minimal for its simplicity |
| B improves, B substantially more costly | report `sum V / sum C` of both; the trade-off is Hamm's |
| B improves, cost within 1.25x | candidate for a larger preregistered comparison; still no rollout |

Task-kind exception: a kind counts as showing an advantage only when `V_B = 1` and `V_A = 0` on it; one such cell
of four is reported as a lead for a follow-up on that kind, never as grounds to adopt. The reverse (`V_A = 1`,
`V_B = 0`) is reported the same way. On one-part tasks (T3, T4) arm B's keeper picks the better of two drafts:
that is part of the OCMA-8 formation and a structural advantage on `V` there, to be named in the report. Four tasks license no rate;
the report says so. Failures and inconclusive outcomes stay in the record.

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
