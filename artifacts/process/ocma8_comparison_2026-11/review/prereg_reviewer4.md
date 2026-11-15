# prereg reviewer4 (claude-sonnet-5-5), verbatim

## Report 1

VERDICT: REVISE

Reviewer 3's four freeze blockers
1. Source of evaluator-found inventory: repaired. L33-37 has evaluators list defects on both trees; L38-41 has the adjudicator fill "real on the pre-review tree".
2. Who matches evaluator defects to each other and to findings: repaired. L39-40 gives matching to the adjudicator alone.
3. Writer-introduced vs packet-level split: repaired. L41-42 has the adjudicator fill a "source" column.
4. Pre-review tree for arm B: repaired. L28-31 sets it at the writer-of-final-tree's first report in both arms.

Findings, most serious first
1. BLOCKING. The unit of evaluation contradicts itself. L32 and L22 say two evaluators per cell (a cell is task x arm, 8 cells), and L52 says one adjudicator per cell. L106-107 says two evaluators per task, with p/q labels covering both arms. With per-cell adjudication a different adjudicator judges each arm's tree, so V and the "consequential" call vary with the adjudicator as well as the arm. Fix: one evaluator pair and one adjudicator per task, seeing both arms under p/q.
2. BLOCKING. Nothing says who turns reports into discrete findings. L24 defines a finding as "one statement" or an "open item". L35-37 passes only "file, lines and the finder's first sentence, role names removed". Segmentation, role-name scrubbing and first-sentence truncation fall to the unblinded orchestrator, with no rule. A defect stated after the first sentence, or two defects in one statement, cannot be matched. This biases yield, mentions and false-finding counts against verbose roles. Fix: a scripted split and scrub, with the full text passed.
3. BLOCKING. Closure reliability (L45-46) divides over "rows raised by the formation". The text does not say whether a row real on neither tree is a row. A false row is trivially "not real on the final tree", so it inflates the ratio. Fix: restrict to rows real on the pre-review tree.
4. Non-blocking. Arm B's dispatch order for checker, critic and helper relative to the keeper is not stated. L30's "no critic role ran before" depends on it, and so do critical-path time and the pre-review tree.
5. Non-blocking. Nothing says when evaluation runs. If it runs between a task's two arms, the orchestrator sees results before the second arm. Fix: evaluate after all eight cells.
6. Non-blocking. Line numbers in a finding have no named tree (the reviewer 3 numbering note stands).
7. Non-blocking. L150-153 says one OCMA-only success is "never grounds to adopt", yet row 4 of the decision table can fire on a one-cell margin. The T3/T4 best-of-two advantage is stated but not adjusted. Advice: pre-specify a sensitivity analysis excluding T3 and T4.
8. Advice. Record the orchestrator model id, and the source of the 5m/1h cache-write split, in the freeze.

I did not check the pricing page itself.

