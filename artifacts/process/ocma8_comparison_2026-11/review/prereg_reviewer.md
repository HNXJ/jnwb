# prereg reviewer (claude-sonnet-5-5), verbatim

## Report 1

VERDICT: REVISE

Requirements 1-8 are met by lines 29-36, 47-61, 63-70, 72-79, 14-26 and 81-86. The exception is "independently resolved defects not mere mentions", which is only partly met (finding 6). Requirement "frozen before execution" is promised (line 3), but the predicates, packets, dedupe rule and cost scripts do not exist yet.

Pilot repairs: concurrency (63-65), arm-letter leak (67-68), no cross-family scorer (70), unmeasured orchestrator (76-78), helper hazard and command (49-50), post-hoc measures (24-26) and resumed reviewer (57-58) are repaired.

Findings, most serious first:
1. L83-86 decision rule. "Improve" is undefined (any +1?). It is silent when B improves V at 1.25x or more cost, or when sum C is below 1.25x. The exception ("a task kind shows V_B>V_A or more closed in B") needs one noisy cell out of four, so it is near-vacuous.
2. L17 and L14-16. V needs "both evaluators find no consequential defect", but a defect "counts when the orchestrator confirms". If an evaluator flags a defect the orchestrator does not confirm, V is undefined. The orchestrator is unblinded, so it is the one unblinded judge of V, dedupe and closure. No tie rule exists. A failed or unparseable Muse run is not covered.
3. L59-60 void cells. "A finding against a packet stops that cell" has no rule for the finder. B has more agents, so more voids. The effect on sum V, sum C and pairing is undefined, and so is a task where one arm is void.
4. L79 C unknown. The cell leaves the estimand, but the decision rule uses sum C. Dropping only cells where V=1 and the telemetry failed biases the result. L74-76: two cost sources are reported, but which one fills C is not named. L19 prices are read "on the analysis day", which is a post-hoc choice.
5. L51-53 and L54. Arm B's keeper picks the tree that "passes more predicates", so B alone gets the predicate scripts. This contradicts L54, which says no other block mentions acceptance. B has two writers running acceptance, so the pilot's surplus runs persist. L61 does not state the checker's model and effort. Whether A's fix writer is resumed or fresh is unstated. The critic's out-of-tree read from the pilot is not addressed.
6. The test of independent resolution has no ground truth, such as seeded defects or the writer's pre-review tree. Closure is judged by a same-family reviewer that may or may not see the findings (L57-58). Dedupe (L26) has no rule.
7. L55-58 fix round. Forwarding every finding verbatim, false positives included (the pilot's checker STOPPED was refuted), removes the orchestrator judgement the real formation uses. B pays for refuted findings. This tests formation plus a forced-closure policy. The arm labels still hold, but the report must state the limitation.
8. L14-16 and L28. T4's "every obligation and SHA still stated" is not mechanical, yet the header says "Acceptance, mechanical". Order effects (orchestrator context grows, so later cells re-read more) are not separated in the orchestrator cost.

Facts checked:
- T2: 5 definitions in 4 files, correct. `release_gate` holds both `_cells` (returns Optional) and `_table_cells`, so "behaviour kept" needs care.
- T3: 4 `test_rng_*.py` files, correct. "146 tests" not run.
- T4: `state.md` is 9,003 B and `STATE_MAX_BYTES = 6000` at `artifacts_check.py:53`, correct.
- jarness 3fb6fe0 and jynx bc72f27 not checked.

