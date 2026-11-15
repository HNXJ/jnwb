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
- Confirmed defect: a row of the arm's defect table (below) that the adjudicator marks real on the final tree,
  with a source other than the baseline. The orchestrator, who is unblinded, judges nothing. A cross-family run
  that fails or does not parse is retried once; after that a second fresh Sonnet evaluator replaces it and the
  task is marked "no cross-family": its two evaluators then share a model family with the adjudicator, and the
  report says how many tasks are so marked.
- `C` (total cost, USD) = agents' tokens + the orchestrator's tokens spent on that arm of that task (see Cost).
Reported: `E` per cell (8 cells), `sum V` and `sum C` per arm, `sum V / sum C` per arm, the four paired
differences, and all of it again with agents-only cost. No significance test: four pairs give sign and size only.

Secondary: confirmed defects by class; critical-path seconds (wall clock from the arm's first dispatch to its
final tree, lane cap 3); review yield; mentions per distinct defect; false findings; closure reliability;
consequential defects closed. Definitions:
- Trees. The pre-review tree is the tree at the first report of the writer of the final tree: the worker's first
  report in arm A, the keeper's first report in arm B. When that first run ends with "no report" (cap or error,
  see Budget), it is the tree at that ending. No critic role has run before it in either arm. The final
  tree is the tree when the closing review's report returns; the arm's clock stops there. Both are saved as diffs.
- Reports: every report of an in-formation critic role, and every writer's or keeper's report, the closing
  review's included, kept whole in the ledger. A script (written and frozen with the packets) replaces role and
  agent names with `AGENT` and gives each report an opaque id in shuffled order. The orchestrator cuts no report.
- Evaluators (one pair per task, blind, independent, judging both arms under their labels): each lists every
  defect it finds on each arm's pre-review tree and final tree, with file, a quoted line, and a class. They see no
  report.
- Extractor (one fresh `reviewer` per task; it judges nothing and is not blind): reads each arm's scrubbed
  reports and writes, per report id, every distinct claim that the tree has a defect as one candidate: file,
  quoted line, one sentence naming the defect, in words that name no role, agent, step or number of agents. It
  drops no claim, true or false; a report that claims none is listed with none.
- Candidates: a script pools the evaluators' defects and the extractor's candidates per arm label, in shuffled
  order under opaque candidate ids, without their source.
- Adjudicator (one fresh blind `reviewer` per task, judging both arms): receives the candidates, the four blinded
  trees, the TASK block and the classes. It sees no report, no report id and no source. It builds each arm's
  defect table, one row per distinct defect, and assigns every candidate id to exactly one row; a script refuses
  a table that leaves a candidate out or uses it twice. Columns it fills: real on the pre-review tree (yes or
  no); real on the final tree (yes or no); class; and, for every row real on either tree, one source of four:
  caused by the TASK block's own text; in the baseline and outside the task's target; in the baseline, inside the
  task's target and left unrepaired; introduced by the arm. A row real only on the final tree is introduced by
  the arm. A row real on neither tree is a false row. Rows "in the baseline and outside the target" are reported
  and are in neither `V` nor the inventory; the other three sources count in both.
- Provenance is attached by a script afterwards, never judged: candidate ids are mapped back to an evaluator or
  to a report and its role; a row is "raised by the formation" when it holds at least one report candidate;
  mentions = the number of distinct reports with a candidate in the row.
- Inventory = rows real on the pre-review tree, by source. Discovery = inventory rows raised by the formation /
  inventory. Closure = inventory rows not real on the final tree / inventory. Review yield = inventory rows
  raised by the formation. Closure reliability = inventory rows raised by the formation and not real on the final
  tree / inventory rows raised by the formation; false rows are in neither term. No fix round follows the closing
  review, so the ratio is given twice: over all reports, and without the closing review's. Consequential defects
  closed = closed inventory rows of a consequential class. False findings = report candidates in false rows. A
  defect real on the final tree and not on the pre-review tree was introduced after the first report and is
  reported as such.
- Findings ledger, per cell: every report as written, with its role, where it was forwarded, its candidates and
  their rows, and the tokens and seconds of the fix round and closing review. Nothing is filtered or regrouped
  after results are seen.
- Limits, stated: one adjudicator judges each task, blind, with no second opinion; it is a Sonnet model, as are
  the reviewers, so `V` is also given counting only rows that hold a candidate of the cross-family evaluator.
  The extractor sees the reports and so the formation; it judges no truth, but a claim it omits is lost from
  mentions and false findings, which the whole reports in the ledger let a reader check. The number of
  candidates per arm can hint at the formation.
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
  own enumerated parts, named in the packets before the freeze (T1, T2; if either item's text enumerates none, it
  runs as a one-part task and joins T3 and T4 in the sensitivity split below). Where the item has one part (T3,
  T4), both workers draft the whole item and the keeper
  takes the draft that passes the acceptance command (both pass or both fail: worker 1). The orchestrator writes
  no decision into a split. No agent of either arm sees a predicate script.
- Acceptance is run by the writer of the final tree (arm A: the worker; arm B: the keeper, once per draft it
  chooses between) and by the reviewer; no other block mentions it. The keeper's extra runs are part of arm B.
- Fix round, both arms, always exactly one: the whole report of every in-formation critic role (reviewer, and in
  arm B checker and critic) and of every writer goes verbatim to the writer of the final tree (arm A: the worker;
  arm B: the keeper; each resumed with its context), whatever the reviewer's verdict; then one closing review by
  a fresh `reviewer` that receives the same reports. No one decides whether a report holds a finding.
  Limitation, to be stated in the report: this tests each formation under a forward-everything policy, with no
  orchestrator triage; false findings are forwarded too and their cost is the arm's.
- The orchestrator sends frozen packets verbatim, forwards output only into a packet's slot, and logs every other
  action as an intervention. No cell is voided: a finding against a packet is recorded and the cell goes on under
  the packet as written.
- Budget, the same for every run of both arms: one dispatch per packet, no message to a running agent, and a
  wall-clock cap of 30 minutes from dispatch (the harness offers no token cap; tokens are measured, not capped).
  A run ends in one of three ways, each read from the harness and none judged: its final report returns; the cap
  is reached and the orchestrator stops it at once; the harness reports an error. In the last two the report is
  recorded as "no report" and nothing is retried. Whatever the ending and whatever a report says, the flow goes
  on to its next step on the tree as it stands, to the closing review; `V` is computed on the final tree. If the
  harness cannot resume the writer for the fix round, a fresh agent of the same type gets the writer's packet and
  the reports in the same worktree; that is the fix round, under the same cap, and it is logged.
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
`eval_t<n>_<p|q>`; the diffs are applied uncommitted, so no branch, commit, author or path of an arm reaches
them. Evaluators see only those paths, the TASK block and the defect classes; the adjudicator sees those and the
candidates. Neither sees a report, an agent identity or a count of agents.
Two evaluators per task, independent: `reviewer` (Sonnet 5.5, high) and a scorer from another model family
through `delegate-cli` (opencode Muse, read-only). No evaluation starts before all eight cells have their final
trees, so no result of one arm is known while the other runs.
Arm flows, fixed: A: worker (first report) → reviewer → fix round → closing review. B: helper → worker 1 and
worker 2 → keeper (first report) → checker → critic and reviewer together → fix round → closing review.

## Cost

- Agents: `C` is filled from the transcripts by `pilot_usage.py` and `pilot_cost.py` (the pilot's method).
  `~/.claude/subagent_runs.jsonl`, once P-26 (jarness open stack) is repaired, is the cross-check; a difference
  above 1% per agent is a finding.
- Prices are fixed now, USD per million tokens, read 2026-11-15 from
  https://platform.claude.com/docs/en/about-claude/pricing: Haiku 5.5 up to 100K prompt 0.10 input, 0.125 and 0.20
  cache write (5m, 1h), 0.01 cache read, 0.50 output; over 100K 0.50, 0.625, 1, 0.05, 2.50; Sonnet 5.5 2, 2.50,
  4, 0.10, 10. The Haiku tier is chosen per usage row: over 100K when input + cache write + cache read of that
  row exceeds 100,000 (`pilot_cost.py`). The orchestrator is priced by the model id on each of its usage rows, from the model table of that
  page as saved on 2026-11-15 in `prices_2026-11-15.md`; no price is read later. Evaluators, the extractor, the adjudicator and
  the cross-family scorer are outside both arms: their cost is reported apart and is no part of `C`.
- Orchestrator: the main session's usage rows in its own transcript between the arm's first dispatch and its
  final tree, reported beside the agents' cost and inside `C`. Its model id is read from `get_session` and
  written here at the freeze. Cache writes are split by lifetime from each usage row's `cache_creation` field; an
  unsplit write is priced at the 1h rate. Possible because arms do not interleave. Its
  context grows through the session, so later cells cost more; the alternation spreads this over the arms and
  the agents-only analysis is free of it. Evaluation and the record's review are outside both arms.
- Mandatory round: the fix round and the closing review run in every cell, also where nothing needs repair, which
  can penalize an arm with no defect. Their cost and seconds are given per cell on their own line and stay inside
  `C`, because they are part of the frozen protocol.
- `C` is always the transcript-derived figure; a cross-check difference is reported and changes nothing. Only a
  missing or unreadable transcript makes a cost unmeasurable; that task then leaves the primary sums in both arms
  and is reported apart, whatever its `V`.

## Decision rule (Hamm's stopping rule of 2026-11-15; thresholds approved by him the same day as exploratory criteria)

The thresholds are operational decision boundaries, not significance tests. Three questions are answered apart:
effectiveness (verified completions and consequential defects closed), efficiency (those per total cost), and
adoption (the table below). A closure advantage does not by itself justify adoption at excessive cost, and equal
verified completion does not show equal review quality: the report gives discovery and closure beside `V`.

Outcomes are paired by task (Hamm 2026-11-15). Each task is a win for B (`V_B = 1`, `V_A = 0`), a loss
(`V_B = 0`, `V_A = 1`) or a tie; a task missing a cell in either arm, or with an unmeasurable cost in either arm
(see Cost), leaves both criteria and the cost sums together and is reported apart. Two criteria:
- Completion: B completes more tasks than A under the identical acceptance, wins > losses.
- Defect closure: consequential defects closed in B exceed those in A by two or more, each a distinct inventory
  row, so adjudicated blind as present before review. The count is given per task beside the total.
"Improves" means at least one criterion holds and losses do not exceed wins: B never improves with fewer verified
completions. Closed defects are absolute counts; the arms' inventories differ, so each count is reported with its
inventory and its closure fraction, and a lead that rests on the larger inventory alone is named as such.
"Substantially more" means `sum C_B >= 1.25 x sum C_A`, all attributable agent and orchestrator cost included.
Neither criterion alone authorizes a rollout: the table's reading is weighed with cost, the spread over task
kinds and the limits stated here.

| Outcome | Reading |
|---|---|
| B does not improve, B substantially more costly | prefer the minimal formation |
| B does not improve, cost within 1.25x | no reason to adopt OCMA-8; prefer minimal for its simplicity |
| B improves, B substantially more costly | report `sum V / sum C` of both; the trade-off is Hamm's |
| B improves, cost within 1.25x | candidate for a larger preregistered comparison; still no rollout |

Task-kind exception: a kind counts as showing an advantage only when `V_B = 1` and `V_A = 0` on it; one such cell
of four is reported as a lead for a follow-up on that kind, never as grounds to adopt. This governs the table:
when "improves" rests on one win alone, rows 3 and 4 read as that lead and no more. The reverse (`V_A = 1`,
`V_B = 0`) is reported the same way. On one-part tasks (T3, T4) arm B's keeper picks the better of two drafts:
that is part of the OCMA-8 formation and a structural advantage on `V` there, to be named in the report. The
four-task result is primary and the decision table is read on it. The same analysis on T1 and T2 alone is a
sensitivity analysis fixed here, never an alternative result; a reading that changes there is reported as
resting on the best-of-two. Four tasks license no rate; the report says so. Failures and inconclusive outcomes
stay in the record.

## Prerequisites (each a gate; none passed yet)

1. Telemetry: P-26 repaired, a real subagent run writes one correctly attributed row, and a resumed run writes
   `.2`, not a duplicate.
2. Cross-family scorer: one smoke packet through `delegate-cli` returns a parsed report on this host.
3. Per task: a frozen predicate script scoring 0 on the baseline (known negative), the acceptance command passing
   on the baseline (known positive), and the baseline SHA re-read.
4. Packets, the scrub script, the candidate script and the table check written and frozen; an independent `reviewer` reads them for any information or decision one arm gets
   and the other lacks: ACCEPT.
5. T1 and T4 touch jarness and jynx trees only in experiment worktrees; their items stay open for those keepers.
6. The orchestrator's model id read from `get_session` and written under Cost.
7. Hamm's go.
