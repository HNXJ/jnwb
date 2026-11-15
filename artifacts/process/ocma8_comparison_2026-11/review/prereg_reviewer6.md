# prereg reviewer6 (claude-sonnet-5-5), verbatim

## Report 1

VERDICT: REVISE

Fifth review's blockers
- (a) Repaired. L112-117 give a 30-minute wall-clock cap from dispatch, one dispatch per packet, no mid-run messages, three mechanical endings, "no report", no retries.
- (b) Repaired. The extractor "drops no claim" (L38-41). Every candidate id must land in exactly one adjudicator row, and a script refuses otherwise (L46-47).

Blocking
1. L29-30 against L114-116. The pre-review tree is "the tree at the first report of the writer of the final tree". A writer that hits the cap or errors is recorded as "no report", so no first report exists. The pre-review tree, the inventory and closure are then undefined for that cell. This is likelier in arm B, where the keeper sits behind several steps. The same gap covers the fix round, where the writer is "resumed with its context" (L104-105) after being killed or errored. Fix: define the pre-review tree for a "no report" ending, for example the tree at the stop event. Also say what the fix round does when the writer has no resumable run.

Non-blocking
2. L48-49 against L16. "Source when real there" is filled only for rows real on the pre-review tree. A row real only on the final tree has no source. The definition of a confirmed defect needs "a source other than the baseline" (L16). L60-61 calls such a row "introduced", but the column definition does not give it that value. Fix: state that final-only rows take source "introduced by the arm".
3. L48-50. A baseline defect inside the task's target that the arm leaves unfixed fits none of the three source values. "Baseline outside the target" excludes it, and "introduced by the arm" is wrong for it. The adjudicator must decide, and the answer moves V. Fix: add a value "baseline, inside target (counts)".
4. L162-163 against L172-173 and L175-176. An unmeasurable-cost task leaves the primary sums. The wins and losses and the closure counts do not say whether it stays in them. Fix: say it also leaves the paired criteria, or that it stays in them.
5. L145-149. The orchestrator model id is "written here at the freeze". It is not listed under Prerequisites, so nothing gates it.
6. L69. The candidate count per arm leaks the formation to the adjudicator. This is stated as a limit and does not invalidate the estimand.
7. L99-100. In T3 and T4 the keeper's draft choice runs the acceptance command itself. It sees the result, so no judgment is left to the orchestrator. The advantage is named at L194-195.

I read all of PREREG.md, prices_2026-11-15.md and reviewer5's report. I ran nothing.

