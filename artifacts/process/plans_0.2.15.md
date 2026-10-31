# 0.2.15 plans

Covers every open 0.2.15 todo: the five `required-0.2.15` items in `todo_stack.md` and the three
`deferred-0.2.15` validations in `roadmap.md` (15-11, 16-12, 12-21). 11-09 is implemented (`65ef303a`)
and its todo item is still listed; the keeper deletes it. Each plan names what a subagent may do now
and which step needs a ruling. A ruling-gated step is not executed by a subagent.

| Plan | Items | Runs now | Needs a ruling (Hamm) |
|---|---|---|---|
| P1 Fact gate | 11-09 | delete the item once Hamm accepts the vacuous K5 pass | the empty-list K5 pass: keep, or require one planned skill |
| P2 Coherence graph | 16-20 | the reviewer at high reads the design and writes a proposal, no code | the normalization method; the change to two public operations |
| P3 Non-finite scan | 17-24 | a scan of the public numeric functions for NaN and inf, measured, no fix | the split of 17-24 into scan and repair items; each repair's signature |
| P4 Lexicon and vocabulary | 17-05, 17-07 | an inventory of the choice names (17-05) and the sentence hits (17-07), no edit | a ruling per name group; the per-class vocabulary; the skill-line amendment |
| Validation (tracked) | 15-11, 16-12, 12-21 | none: each waits on outside input | none until the outside input arrives |

## Acceptance

A plan is done when its runnable step has a receipt, and its ruled steps are in the rulings file with
the decision. A validation row stays open until its outside input exists and its receipt is committed.

## Order

P1 closes first. P3's scan feeds P3's split. P2 and P4 wait on rulings. Validation is tracked, not run.
