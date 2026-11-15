# OCMA-8 pilot on jnwb: preregistration

Frozen 2026-11-15, before either arm ran. Authorized by Hamm 2026-11-15 ("Authorize the pilot and read-only
promotion audit"). A pilot: one task, one run per arm. It estimates feasibility and exposes failure modes; it
cannot establish a productivity advantage.

## Authority and state at the freeze

| Item | Value | Read from |
|---|---|---|
| jnwb baseline | `dev` ac995ddee147c4d6aa78ba15ecda7a998cd70a00 | `git ls-remote origin refs/heads/dev` |
| jarness | `main` f7cdfb2, installed on vwin-pc (receipt f7cdfb26) | `~/.claude/harness-install.json` |
| ocma | `dev` ee020fa; read only | `git rev-parse origin/dev` |
| OCMA-8 formation | proposed, not owner-adopted: `method/OCMA8_SCIENCE_PILOT_20261114.md` on ocma `_temp_autofleet-alignment-20261113` | that file, line 1 |
| W8 | approved by Hamm 2026-11-09; advisory here | ocma `method/work_ontology.md:3` |
| ocma hold | `dev` records "no push, no clone work"; the pilot writes nothing to ocma | ocma `artifacts/state.md` |
| Lane cap | three concurrent lanes, reviewers included | Hamm 2026-11-14, restated 2026-11-15 |

Unequal with the OCMA plan (`artifacts/process/ocma_plan.md`): no scorer from another model family (ruling 3);
one critic, not every other agent, scores.

## Task

jnwb todo item 17-103 (unblocked; role docs-harness; Writes `.github/CONTRIBUTING.md`). Text in `PACKETS.md`.
Chosen because it is a whole item, unblocked, one file, and its check is mechanical. Known hazard, not told to
any agent beyond the role's own rule: the item says "nine folders"; the baseline tree has ten tracked folders
under `artifacts/`.

## Arms

| Arm | Formation | Agents (model, effort) |
|---|---|---|
| A, minimal Jarness | orchestrator, one worker, one reviewer | `worker` (Haiku 5.5, high); `reviewer` (Sonnet 5.5, medium) |
| B, OCMA-8 | orchestrator, keeper, two workers, reviewer, checker, critic, helper | helper `worker` medium; two `worker` high; keeper `worker` high; `checker`; critic `worker` high; `reviewer` (Sonnet 5.5, medium) |

Equal in both arms: baseline, item text, role rules, acceptance command, tools and permissions of each agent type,
the reviewer's packet, one fix round at most, the orchestrator (this session) and its rule: send the frozen packet
verbatim, add nothing, forward agent output verbatim where a packet has a slot for it. Each writer has its own
linked worktree at the baseline; no agent is told another arm exists. Unequal by design: arm B's helper table,
task split, checker pass and critic score.

Flow A: worker → reviewer → (REVISE: FIX to the worker, then the reviewer again) → final tree.
Flow B: helper → worker 1 and worker 2 → keeper merges → checker → critic and reviewer → (REVISE: FIX to the
keeper, then the reviewer again) → final tree. The critic's W8 score is advisory and never changes the flow.

Order: both arms start in the same minute; stages run as lanes free up (cap 3). The orchestrator wrote every
packet before the start, so nothing learned in one arm reaches the other through a packet.

## Outcomes (measured on each arm's final tree)

| Outcome | Measure | Source |
|---|---|---|
| Verified completion | acceptance `ACCEPT_RC=0` and primary predicates P1, P2, P3 (0 to 3) and constraints P2b, C1, C4, C2 | `pilot_accept.sh`; `pilot_predicates.py`; C2 = `python scripts/obligation_diff.py --base ac995dde .github/CONTRIBUTING.md` reports 0 dropped or lost timing |
| Defects | defects the blind evaluator establishes, by class; each checked by the orchestrator against the tree | `EVALUATE` packet; labels X, Y from `random.Random(20261115).random() < 0.5` → A is X |
| In-formation review yield | findings of the arm's own reviewer, checker and critic that the tree confirms, and those it refutes | their reports |
| Elapsed | sum of agent seconds; critical-path seconds (stages in series, parallel stages by their maximum) | `~/.claude/subagent_runs.jsonl` field `s` |
| Tokens | `fresh_in`, `out`, `cache_read` per agent and per arm | same log |
| Cost | tokens × the public price of each model, prices read at analysis time and cited | same log |
| Interventions | orchestrator actions outside the frozen flow, each listed | this session |

Not measured: the orchestrator's own tokens per arm (one session runs both).

## Controls

- Known negative: the baseline tree scores primary 0/3 on `pilot_predicates.py` (run before the freeze: 0/3,
  constraints 2/3 because C1 expects a change).
- Known positive for acceptance: the baseline passes `pilot_accept.sh` (lines in `PACKETS.md`).
- Regression: C4, no path pointer of the file unresolved that resolved at the baseline (15 unresolved before).
- Advisory-versus-mandatory: where the critic's W8 `merge` disagrees with the reviewer, the predicates or the
  blind evaluator, the disagreement is reported; the mandatory checks decide.

## Reading the result (fixed now)

- Effectiveness: verified completion and defect counts of the final trees.
- Overhead: cost, agent seconds and agent count of arm B over arm A.
- Verified work per dollar: primary predicates passed on a tree that also passes acceptance and every constraint,
  divided by the arm's cost. Reviews, scores and artifacts count as cost, not as work.
- "No detectable difference in effectiveness" when both arms have the same verified completion and their
  confirmed defect counts differ by at most one. Any difference is one sample: it names a failure mode, never a
  rate.
- An arm that fails stays in the record as it ended. Inconclusive is a valid outcome; the next step is then a
  small preregistered multi-task comparison (Hamm 2026-11-15).

## After the arms

The final trees, reports and logs are committed under this folder on `_temp_ocma8_pilot`. A result that passes is
not merged to `dev` by the pilot: integration of 17-103 is the jnwb keeper's, through `scripts/jnwb_push.sh`.
An independent reviewer checks this record's evidence and the arms' comparability before the report.
