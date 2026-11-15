# OCMA-8 pilot on jnwb 17-103: results

One task, one run per arm, 2026-11-15. Read with `PREREG.md` (frozen before the run) and `ADDENDUM.md` (after the
freeze). Final trees: `arm_A_final.diff`, `arm_B_final.diff`. Agent reports, verbatim: `agent_reports/`.
Neither tree is merged; 17-103 stays open on `dev` for the jnwb keeper.

## Verdict

Inconclusive on effectiveness; arm B cost more. Both arms closed the item by every preregistered check. Arm B's
five extra agents added cost and one wording edit, and left unrepaired the one non-style defect that five of its
agents named. One sample: it names failure modes, never a rate.

## Verified completion (orchestrator's runs on the final trees)

| Check | A, minimal | B, OCMA-8 |
|---|---|---|
| `pilot_accept.sh` | 557 passed, 2 skipped; 22 of 22 gates; `ACCEPT_RC=0` | 557 passed, 2 skipped; 22 of 22 gates; `ACCEPT_RC=0` |
| Primary P1, P2, P3 | 3/3 | 3/3 |
| Constraints P2b, C1, C4 | 3/3 (19 tree entries; unresolved 15 → 16, none new) | 3/3 (11 tree entries; unresolved 15 → 16, none new) |
| C2 `obligation_diff.py` | 463 clauses read, 0 dropped or lost timing | 463 clauses read, 0 dropped or lost timing |
| Diff size | +19 −3 | +11 −3 |
| Arm's own reviewer | REVISE, then ACCEPT after the one fix round | ACCEPT, no fix round |

Known negative: the baseline scored primary 0/3 before the freeze. The unresolved pointer that both arms add is
their own new backticked token, absent from the baseline; C4 counts only pointers that resolved before.

## Defects (blind evaluator, Sonnet 5.5 high; X = A, Y = B; each checked against the diff)

| Class | A | B |
|---|---|---|
| wrong-pointer, wrong-value, scope | 0 | 0 |
| meaning-change | 0 | 1: the `scratch/` line is removed from the tree block while the rule below it still sends contributors to `artifacts/scratch/` (confirmed in `arm_B_final.diff`; evaluator calls it minor, borderline) |
| incomplete | 0 | 0 to 1: seven of eight root files unlisted (borderline; the item names folders; not counted by the evaluator) |
| style | 3: new entries carry no comment; `todo_stack.md` moved by the alphabetical sort; the long list (confirmed) | 1: one very long line at :120 (A has the same line; the evaluator lists it for A outside its count) |
| Evaluator's verdict | ACCEPT | REVISE (minor): ACCEPT once the `scratch/` line is restored |

By the frozen rule (same verified completion, confirmed defect counts within one: 3 against 2) this is "no
detectable difference in effectiveness". The rule counts defects and does not weigh class: the only non-style
defect is in arm B.

## Review yield, repair overhead, closure (post hoc measures, `ADDENDUM.md`)

| Measure | A | B |
|---|---|---|
| Distinct actionable defects found in the formation | 1: pointer 2 left open (reviewer, round 1) | 2: the `scratch/` removal; the unclear clause "The first refusal also includes" |
| Mentions of those defects | 1 | `scratch/`: worker 2, keeper, checker, critic, reviewer (5); the clause: keeper, checker (2) |
| Resolved and then independently checked | 1 of 1 (fix round; reviewer round 2; P2) | 1 of 2 (the checker reworded the clause, the reviewer accepted after it; `scratch/` not repaired: the reviewer said ACCEPT, so the flow had no fix round) |
| Findings the tree refutes | 0 findings; one miscount in the reviewer's prose ("7 files", the block lists 8) | 1: the checker's `STOPPED` over the 20% and 5 MiB its numbers check flagged, which the item requires |
| Repair overhead | 280 of 624 agent seconds (fix 153 s, second review 127 s) | none in the flow; the checker's edit sits inside its 277 s |
| Critic's W8 (advisory) | not in the formation | W = 0.6, merge true; its one deduction (Clean diff −0.6) is the `scratch/` removal; agrees with the reviewer's ACCEPT, disagrees with the blind evaluator's REVISE |

## Cost and time (`usage_table.txt`, `cost_table.txt`)

| Quantity | A | B | B − A | B / A |
|---|---|---|---|---|
| Agents (runs) | 2 (4) | 7 (7) | +5 | 3.5 |
| Agent seconds | 624 | 1236 | +612 | 1.98 |
| Critical-path seconds | 624 | 1007 | +383 | 1.61 |
| Fresh input tokens (input + cache write) | 118,771 | 379,848 | +261,077 | 3.20 |
| Cache-read tokens | 1,314,182 | 3,268,206 | +1,954,024 | 2.49 |
| Output tokens | 25,632 | 112,539 | +86,907 | 4.39 |
| Cost, USD | 0.1819 | 0.2338 | +0.0519 | 1.29 |
| Primary predicates passed per USD | 16.5 | 12.8 | −3.7 | 0.78 |

Critical path B: helper 35 → workers max(89, 212) → keeper 213 → checker 277 → max(critic 270, reviewer 140).
The cost ratio is far below the token ratios because Sonnet review dominates the money: 82% of arm A's cost
(reviewer, two runs, 0.1493 of 0.1819) and 44% of arm B's (reviewer, one run, 0.1030 of 0.2338; its six Haiku
agents 0.1307 together), and arm A paid for the reviewer twice. The blind evaluation (0.1591, 50 s) is outside both arms.

Prices, USD per million tokens, read 2026-11-15 from https://platform.claude.com/docs/en/about-claude/pricing:
Haiku 5.5 (prompts up to 100K) input 0.10, 5m cache write 0.125, cache read 0.01, output 0.50; Sonnet 5.5 input
2, 5m cache write 2.50, cache read 0.10, output 10. Every cache write in the transcripts is the 5-minute kind;
no Haiku message exceeded 100K. Source conflict: the `claude-api` skill (cached 2026-10-06) gives Sonnet 5.5
cache reads at 0.20; the live page gives 0.10 and is used.

## Deviations and unequal conditions

| Item | Effect |
|---|---|
| Usage source | `~/.claude/subagent_runs.jsonl` holds no row after 2026-11-11 on vwin-pc; tokens come from the agents' transcripts by the hook's rule (`pilot_usage.py`), seconds from the harness's per-run `duration_ms` |
| Worker 2's packet said "lists the folders of `artifacts/` as the tree has them" | The orchestrator's split resolved for arm B the ambiguity that arm A's worker left to the owner in its first pass; arm A's REVISE round is partly this, and arm B's missing fix round too |
| Helper's table named "nine against ten" | Arm B's workers were handed the hazard; arm A's worker found it alone (it did, in its first pass) |
| COMMON says run acceptance; four arm B blocks have no use for it | Worker 2, the checker and the critic ran it (about 115 s each); worker 1 did not and reported the conflict; cost on arm B only |
| The keeper wrote its patch files to the session scratchpad, not `{W}/..` | None on the tree |
| Reviewers and evaluator resumed or share a model family | Arm A's second review ran in the first reviewer's context; no scorer from another family (PREREG) |
| Blind labels | The evaluator saw the paths `jnwb_pilot_A` and `jnwb_pilot_B`: the arm letter leaked, the formation did not |
| Orchestrator | Its tokens are unmeasured; arm B took 7 dispatches and arm A 4 |
| Arms ran concurrently on one machine | Seconds include load from the other arm |

Interventions outside the frozen flow: none. Acceptance names (`A_review`, `B_checker`, ...) were substituted for
`{name}` so that concurrent runs did not share a temp directory.

## What the sample shows

- Effectiveness: equal verified completion. The single reviewer of arm A found and closed the one real gap.
- Overhead: arm B spent 1.98 times the agent seconds, 1.61 times the wall-clock path and 1.29 times the money.
- Verified work per dollar: lower in arm B (12.8 against 16.5 predicates per USD).
- More agents produced more agreement, not more verified work: five agents named the `scratch/` removal and the
  formation had no path that repaired it once the reviewer said ACCEPT.
- Failure modes named: a split packet can carry the orchestrator's resolution of an ambiguity; a finding below the
  reviewer's REVISE bar has no owner; a checker can stop on an invariant the item itself requires; a shared block
  that fits one role costs every other role.

## Next step (fixed in PREREG)

A small preregistered multi-task comparison, not an OCMA-wide rollout: several whole items of different kinds
(a code fix with a red test, a doc item, a gate), each arm run on each task with the same packet text up to the
split, arm order alternated, labels and paths blinded, a scorer from another model family, and the usage log
repaired first.
