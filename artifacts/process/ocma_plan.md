# Ontology-constrained multi-agent analysis (OCMA): plan

Status: ruled 2026-11-09 (decisions at the end). Executor: `jnwb-critic` on the host with the raw
omission corpus; this session plans and verifies. Source method: Nejat et al., Sci Rep 2026,
doi:10.1038/s41598-026-77038-y; code `HNXJ/mllm-public` (glossary `src/ontology/glossary/HPC/hpc-36-reference.md`,
prompt `src/ontology/instructions/hpc_eval_prompt.md`). Execution pattern: jaxfne's replication programme
(`artifacts/etudes/meta/plans/replication_programme.md`, `execution_plans_0.5.9-0.5.10.md` in jaxfne): map, preregister,
one lane per worker, the orchestrator reruns every acceptance command.

## Aim

Populate the dashboard (https://hnxj.github.io/jnwb/) with replications and validations, each carrying a receipt, and
raise each one's score round by round. Goal row G3 of `artifacts/goal.md` ("the dashboard holds the HTML outputs and
every validation with its receipt") is the goal this serves.

## The paper's pipeline, mapped

| Paper | OCMA |
|---|---|
| Glossary: 36 factors in 3 hypotheses, each with ID, definition, tag, context | Ontology O (below): closed key set for tasks, results and scores |
| Constrained prompt: every key exactly once, exact strings, JSON only, `null` ≠ `0.0` | Every worker and scorer output is one JSON object validated against `ocma.schema.json`; an invalid object is rejected, never repaired |
| Council of 10 models scores 31 studies | Every agent scores every other agent's task result |
| Pairwise agreement, cross-model comparison | Inter-scorer agreement per task and per criterion |
| Hypothesis-space temperature (dispersion) | Score dispersion per task: a contested result goes to adjudication |
| Human experts as a reference stratum | Hamm's rulings and the existing verified entries as the reference |

## Ontology O

Reused from the repository (no new vocabulary where one exists):

| Kind | Values | Source |
|---|---|---|
| Dataset | DANDI `{id, version, asset_id, sha256}`; raw-corpus session id | `scripts/dashboard/data.schema.json` (showcase `dandi`) |
| Operation | a symbol in `jnwb.__all__` | `docs/api.md` |
| Signal class | spikes, LFP (never pooled) | `AGENTS.md` §5 |
| Claim class | magnitude, lag asymmetry, delay, inference; prevalence vs magnitude | `artifacts/fact_stack.md` Constants; `CONTRIBUTING.md` invariants |
| Control | known positive, known negative, null, shuffle | master rule "prove or reject" |
| Verdict | `reproduces`, `partial`, `does_not`; paper, library and methods verdicts | `data.schema.json` :356-380; `build_dashboard.py` :103-110 |
| Entry kind | showcase (replication card), validation (receipt card: calibration, performance, frozen, studies, closure) | `data.schema.json` :250 |
| Status | published, exploratory, verified | `data.schema.json` :274 |

New, one file: `ocma.schema.json`, three object types.
- **task**: `{id, objective, reference (DOI, figure, panel), observable (name, unit, axis), signal_class, claim_class, dataset, operations[], estimand, controls[], tolerance, verdict_rule, writes[]}`. Fixed before any scored run (the preregistration).
- **result**: `{task_id, commit, receipt (path, sha256), values (with units), controls_run, verdict, limitations}`.
- **score**: `{task_id, scorer, criteria: {key: 0..max}, total, feedback, evidence: [path:line]}`. One key per rubric row, each used exactly once; `null` only for a criterion the task does not have.

## Algorithm, one round r

1. **Map** (round 1 only): the current entries (4 replications from DANDI 000253, 13 validation cards), receipts with no
   card (`curation_calibration_0.2.14`, `vflip2_separation_0.2.14`, `gpu_launch_overhead_0.2.5`, `complexity_inventory`),
   roadmap validation rows (16-12, 15-11, 12-21), and the corpus and DANDI sets the host can read.
2. **Objectives**: from the goals, each a checkable predicate (e.g. "16-12 isi_cv has a card whose receipt was computed
   without importing jnwb").
3. **Tasks**: one task object per objective part; written to the todo stack as items with `Writes` that do not overlap.
4. **Distribute**: one task per worker, one clone or worktree each; at most the session's agent cap at once.
5. **Peer score**: when a worker finishes, every other agent scores its result (never its own) against rubric R and
   leaves feedback; scores are schema-validated.
6. **Council**: when all tasks are done, aggregate per task: median, IQR, agreement. A task whose IQR exceeds 20 points,
   or whose median falls under 60, goes to the executor for adjudication. The council then rewrites objectives, tasks,
   the todo and open stacks and the checklist (the rubric rows not yet met), and starts round r+1.
7. **Stop**: every objective's predicate holds, or two rounds pass with no rise in the median total.

## Rubric R (sums to 100; weights are Hamm's)

| Criterion | Max | Full marks when |
|---|---|---|
| Preregistration | 20 | estimand, controls, tolerance and verdict rule were fixed before the run and followed |
| Evidence | 25 | every number traces to a committed receipt and reruns from its command and seed |
| Controls | 15 | each declared control ran and is reported |
| Ontology | 10 | the objects validate; units, signal class and claim class are explicit |
| Dashboard | 10 | `python scripts/build_dashboard.py` accepts the entry; `check_dashboard_build.py` passes |
| Calibration | 10 | the verdict follows from the evidence; limitations are stated |
| Economy | 10 | the smallest diff and runtime that close the task |

Hard stops, scored 0 whatever the rest: an invented or synthetic value in an analysis path (goal 4); spikes and LFP
pooled; a logarithm before the mean; a receipt not committed.

## Roles

| Role | Who | Decides |
|---|---|---|
| Executor | `jnwb-critic` (main model) on the corpus host | tasks, adjudication, verdicts; reruns every acceptance command |
| Workers | Haiku 5.5 subagents, one task each | nothing: execute and report |
| Scorers | every agent but the author; at least one from another model family (Muse, GLM or Gemini) for independence | scores only |
| Integrator | this session (jnwb keeper) | merges, pushes `dev`, owns the stacks |
| Hamm | owner | rubric weights, publication of omission results, any change to goal, fact or public API |

## Round 1 candidates

| Objective | Data | Blocker |
|---|---|---|
| 16-12 isi_cv card (9,056 units); 17-144 picks its commits | raw corpus | none once 17-144 lands |
| 16-12 WaveMAP card | raw corpus | receipt must be computed without jnwb; card definition |
| 16-12 omission card | raw corpus | card definition; public-dashboard decision |
| Cards for the four receipts with none | committed receipts | none |
| 15-11 vflip2 planted crossover | synthetic | Andre Bastos's simulation code |
| 12-21 planted delay and direction | jaxfne broadband field | the field |

## Decisions (ruled 2026-11-09, `artifacts/rulings/2026-11-09.md`)

1. Work rounds are scored by W8 (`method/work_ontology.md` in ocma), shared with `ocma-jaxfne`.
2. Omission and WaveMAP cards and receipts stay in the repository until publication; the public dashboard shows public data only.
3. Rounds are 8 to 16 Haiku 5.5 agents; a small panel from another model family re-scores a sample, and the cross-family disagreement is reported.
4. Adjudication at IQR > 20 or median < 60, one feedback round; after round 1 the count each threshold flagged is reported before any change.
5. Card specs (estimand, null, n and units, figure) are drafted by the keeper and ruled by Hamm one at a time before code.
