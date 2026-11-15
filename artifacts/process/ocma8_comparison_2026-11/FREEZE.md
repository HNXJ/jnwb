# Freeze record: OCMA-8 comparison protocol

Frozen 2026-11-15T17:51:58Z: the analysis and acceptance rules are `PREREG.md` as committed at jnwb
`_temp_ocma8_pilot` 2060527a (blob f04e692f53f106e2df9066e574b97bb90ccde1d8). Its "Status: DRAFT" line is left
as reviewed; this file is the status. A later change to `PREREG.md` is an amendment: dated, reasoned, and
reviewed afresh before any run.

Frozen: question, estimand, measures, tasks, arms, flows, order, blinding, cost, decision rule.
Not frozen, not passed: prerequisites 1 to 7 of `PREREG.md` (telemetry, cross-family smoke, predicate scripts,
packets and scripts with their own review, worktree rule, orchestrator model id, Hamm's go).
Execution is not authorized (Hamm 2026-11-15). No run of the experiment exists.

## Review history (each reviewer fresh, `reviewer` agent, Sonnet 5.5; reports verbatim under `review/`)

| # | Report | Reviewed commit | Verdict | Blocking findings |
|---|---|---|---|---|
| 1 | `prereg_reviewer.md` | 16d5d7b4 (inferred from the commit order) | REVISE | applied at 19e8fba7 |
| 2 | `prereg_reviewer2.md` | 1c0b7517 (inferred from the commit order) | REVISE | applied at a71382f7 |
| 3 | `prereg_reviewer3.md` | a71382f7 | REVISE | 4; applied at caf4a980 by replacing the merge rules with one blind adjudicator |
| 4 | `prereg_reviewer4.md` | caf4a980 | REVISE | 3; applied at 6050c281 |
| 5 | `prereg_reviewer5.md` | 6050c281 | REVISE | 2; applied at b7d839d2 |
| 6 | `prereg_reviewer6.md` | b7d839d2 | REVISE | 1; applied at 87514cca |
| 7 | `prereg_reviewer7.md` | 87514cca | ACCEPT | 0; five advisory points applied at a900f664 |
| 8 | `prereg_reviewer8_delta.md` (diff only) | a900f664 | ACCEPT | 0; two advisory points applied at 7d5b4694 |
| 9 | `prereg_reviewer9.md` (three categories) | 7d5b4694 | REVISE | 1 (A1: the confirmed-defect source rule contradicted the four source values); applied at 2060527a |
| 10 | `prereg_reviewer10.md` (three categories) | 2060527a | ACCEPT | 0 |

Seven REVISE and three ACCEPT. Only review 10 covers the frozen text. All reviewers share a model family with the
writer; no cross-family review of the protocol was made.

## Disposition of review 10's unblocked findings (Hamm 2026-11-15: a material risk needs an explicit disposition)

| Finding | Category | Disposition |
|---|---|---|
| "No cross-family" tasks are judged by one family; the adjudicator is always Sonnet | B | accepted as a stated limit; the report gives the count of such tasks, `V` beside the cross-family-only `V`, and the guess-the-arm hits |
| Defects the closing review finds can never be closed | B | accepted; closure reliability is given with and without the closing review's reports |
| Arm B's critic may read two ontology files outside its tree | B | accepted as part of the formation; named in the report as an information edge of arm B |
| Arm B's pre-review tree follows the helper, two workers and the keeper's choice, so its inventory is probably smaller | B | accepted; closed counts go with inventory and closure fraction, and the T1 and T2 sensitivity analysis shows the best-of-two effect |
| A ratio over an empty inventory is 0/0 | C | reading fixed here, text unchanged: reported as "n/a", never as 0 or 1 |
| "The four paired differences" names no quantity | C | reading fixed here, text unchanged: differences in `E`, in `V` and in `C`, B minus A, per task |
| Orchestrator model id deferred | C | prerequisite 6 gates it |

The two readings above were fixed after the last review and were not themselves reviewed.
