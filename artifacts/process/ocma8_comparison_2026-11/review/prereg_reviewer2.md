# prereg reviewer2 (claude-sonnet-5-5), verbatim

## Report 1

VERDICT: REVISE

Earlier eight findings
- Repaired: 1 (improve and cost bands now defined), 3 (no voided cells), 5 (no predicate scripts for agents, checker effort stated, resumed fix writer stated), 7 and 8 (forward-everything limitation stated, T4 predicate mechanical).
- Partly repaired: 2 (retry and adjudicator rule added, but see finding 3 below), 4 (prices fixed, but see 2 below and finding 8), 6 (inventory added and the lack of seeding stated, but see 1 below).
- None is still fully open.

Findings, most serious first
1. Blocking. L94-97 versus L32-35. Only final diffs are placed in labelled eval_t<n>_<p|q> worktrees. Evaluators must mark defects "real on the pre-review tree", and the pre-review diff has no blinded path. Either the marking is unblinded or the tree is unspecified.
2. Blocking. L107. Orchestrator and Muse prices are "added before the freeze", so a primary cost input is still open. The orchestrator is the largest unblinded cost line.
3. Blocking. L18-19. The unblinded orchestrator decides whether "a command can settle" a defect. That is a discretionary routing choice made after data are seen.
4. Blocking. The defect class (consequential or not) has no named assigner. V (L14-16), the merge rule ("same class", L30-31) and the inventory source split (L37-39) all depend on it. The merge clause "same file and overlapping lines, or same symbol, and the same class" also has ambiguous precedence.
5. Blocking. L121-123. "Improves" is sum V higher OR consequential defects closed higher by 2 or more. B can "improve" with lower sum V. "Closed" is not defined over a common denominator, since the inventories differ by arm (L46-47).
6. Non-blocking. L72-75. Arm B gets best-of-2 drafts chosen on the acceptance command. That is a structural advantage on V, not only an extra cost, and the limitations do not list it.
7. Non-blocking. L92. Both arms share one orchestrator session and repo, so the second arm of a task can carry over information from the first. The text does not say whether the sessions are isolated.
8. Non-blocking. L112 and L102-103. Dropping a task whose cost cannot be measured depends on telemetry failure. A cross-check difference above 1% is "a finding" with no stated effect on C.
9. Non-blocking. L31-35. The merged defect list is stripped of its sources, but the wording of checker and critic findings may identify arm B. This is unstated. The text also does not say whether evaluators raise their own defects before or after seeing the list, which risks anchoring.
10. Non-blocking. L25-26 and L79-81. Findings from the closing review fall outside the one fix round. They are not said to be ledgered or counted as unresolved.
11. Non-blocking. L133-135. The task-kind exception tests only V_B=1 with V_A=0. The reverse, A-only success, is not reported.

Not run: no commands, no probes. I did not check task baselines or the pricing.

