# record reviewer (claude-sonnet-5-5), verbatim

## Report 1

VERDICT: REVISE (evidence is sound; comparability text and two bullets overreach)

1. EVIDENCE: no numeric mismatches found.
- Predicates: I re-ran pilot_predicates.py. A and B both score 3/3 and 3/3; A has 19 tree entries and +19/−3, B has 11 and +11/−3; unresolved 15→16, none new. Baseline scores 0/3, constraints 2/3.
- Usage totals recompute exactly: seconds 624/1236, fresh 118,771/379,848, cache-read 1,314,182/3,268,206, output 25,632/112,539, and all ratios.
- Critical path 35+212+213+277+270=1007 is correct.
- Cost: totals 0.1819/0.2338 match to rounding; the per-role sums are 0.1818 and 0.2337. Shares 82%/44%, Haiku 0.1307, predicates/USD 16.5/12.8/−3.7/0.78 are all correct.
- Prices in RESULTS match pilot_cost.py. Spot-recomputed A worker 0.0325 and A reviewer 0.1493.
- Repair overhead: 153+127=280 matches pilot_usage.py:19-21. The X=A label matches the RNG (0.30<0.5).
- Defect table matches the diffs and eval_evaluator.md. Five agents named `scratch/`: worker-2, keeper, checker, critic, reviewer. The "7 files" miscount is real (8 in A's diff).
- Minor, RESULTS.md:13/17: "orchestrator's runs" of pilot_accept.sh have no log in the record. Only the reviewers' reports corroborate them.
- Minor, RESULTS.md:58/96: "wall-clock path" is summed agent seconds. It excludes the orchestrator and lane-cap queueing.
- Minor, RESULTS.md:45: the yield table omits other flags in the reports (B_checker item 3, B_keeper "7 of 8 root files", A_reviewer long line).

2. COMPARABILITY
- RESULTS.md:95 overclaims. A's worker already reported pointer 2 unresolved (A_worker.md Report 1, OPEN table). The reviewer did not find a gap the worker lacked; it enforced it. "The one real gap" also ignores that the worker had flagged it and chose to PASS.
- RESULTS.md:98-99 and :47 blame the formation for an orchestrator rule. The frozen "add nothing" orchestrator rule (PREREG.md:40) is why flags from worker-2, keeper and checker had no owner. Arm A has the same hole: had its reviewer said ACCEPT, the worker's open pointer 2 would have stayed open. The five mentions are not independent either, since all five read the same diff.
- Unstated unequal condition: PACKETS.md:159 tells only the B helper "where the item's number or line differs from the tree, say so". It also hands it the `ls-tree` command (:156-157). The deviations table lists the "nine against ten" hand-off but not the explicit instruction.
- Unstated: PACKETS.md:179-180 hands the B worker-2 a design decision. Its "lists the folders" scope produced the root-files-unlisted incompleteness and a different answer from A's.
- Unstated: A's worker was resumed for the fix (two runs, context kept). No B agent got a second pass, so B's checker and keeper findings were never fed back.
- Unstated: PACKETS.md:212-213 sends the critic to read D:/repos/_work/ocma, which contradicts COMMON's no-read rule at :98. The checker's model and effort are unspecified in PREREG.md:34.
- Order and post hoc: ADDENDUM.md:3,10 shows the post hoc yield, repair and closure measures were defined after A was final and its results were known. Repair overhead and closure are stated only for A's fix round, and they favour A.
- RESULTS.md:83 and ADDENDUM.md:23 say acceptance cost falls "on arm B only". A also ran it 4 times (worker ×2, reviewer ×2) against B's 5. Only the surplus runs are B's.
- Verdict: "Inconclusive on effectiveness; arm B cost more" follows from n=1 per arm. "Predicates per USD lower" is only a cost ratio, because both arms scored 3. It excludes orchestrator tokens, so it is not a work-per-dollar finding.
- Reviewer variance is uncontrolled. Different reviewers saw different trees, one REVISE and one ACCEPT. The "no owner below REVISE bar" bullet is a design hypothesis, not a sample finding.

