# prereg reviewer5 (claude-sonnet-5-5), verbatim

## Report 1

VERDICT: REVISE

Reviewer 4's three blocking findings
1. Evaluation unit: repaired. L34 gives one evaluator pair per task, L38 one adjudicator per task judging both arms, and L107-110 gives the p/q labels. Stray "cell" wording remains at L24-25: "the cell is marked" should read "the task".
2. Report segmentation and scrubbing: repaired. L31-33 passes whole reports, with a scripted scrub and shuffled opaque ids, and no one cuts reports by hand.
3. Closure reliability: repaired. L47-48 restricts the ratio to inventory rows, so false rows fall out of both terms.

New findings, most serious first
1. Blocking, L94-95 and L96-98. "If an agent stops, the cell ends there" leaves "stops" undefined. No per-agent budget is stated anywhere (tokens, turns or wall-clock), though the owner requires equal budgets. An unblinded orchestrator would decide when a hung or long-running agent is killed. Fix: freeze the caps and define "stops" mechanically.
2. Blocking, L38-41 and L47-48. The adjudicator builds the table, but nothing requires every distinct claim in a report to become a row. A report's false claim that the adjudicator leaves out never enters "false findings", L48. That is a discretionary filter, which the owner forbids. Fix: require a row for every distinct claim in every report, false rows included.
3. Non-blocking, L41-42. "Source" has two values, so a defect already in the baseline has no class. It could still be marked consequential and set V to 0. Advice: add a third source value, "baseline", that is excluded from V.
4. Non-blocking, L34-38 and L54-55. A Claude-family Sonnet adjudicator alone fixes "real" and "class", so it decides V. The cross-family scorer only lists defects. The limit is stated, but cross-family independence does not cover the primary estimand. Advice: have the cross-family scorer also adjudicate, or report V under each evaluator list.
5. Non-blocking, L44-48. Discovery counts writers' self-reports. Closing-review reports can never be closed, because no fix round follows them. This lowers closure reliability, more so for the arm with more reports. Advice: tag the closing-review reports in the ledger and report the ratio with and without them.
6. Non-blocking, L156-159. A one-task lead, sum V_B = sum V_A + 1, satisfies "improves" and fires row 4. The task-kind exception says a lead is never grounds to adopt. State that the exception governs.
7. Non-blocking, L122-123. It does not say how the Haiku 100K price tier is chosen per usage row. The orchestrator model id and the cache-write split are left to the freeze. Settle both with the cost scripts.
8. Non-blocking, L28-29 against L116-135. "Final tree is after the closing review" is ambiguous for critical-path time. Name the endpoint.
9. Non-blocking, L83-84. It does not say which items have multiple parts (T1, T2). Settle this in the packets.

I examined all of PREREG.md and prices_2026-11-15.md against the reviewer 4 report. I ran nothing.

