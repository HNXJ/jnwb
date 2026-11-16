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

The two readings above were fixed after the last review and were not themselves reviewed: they qualify the frozen
text and are outside review 10's scope (Hamm 2026-11-15).

## Prerequisites (status 2026-11-15T18:17:15Z; execution still not authorized)

| # | Prerequisite | Status |
|---|---|---|
| 1 | Telemetry | passed on vwin-pc: `telemetry_verification.md` (one row per run id on fresh, parallel and resumed runs; no earlier row changed) |
| 2 | Cross-family scorer smoke | passed as defined: opencode Muse returned a parsed report (`smoke_packet.md`, `smoke_summary.txt`; 55 s, read-only, tree unchanged). It listed 0 defects and so missed the pilot's `scratch/` defect, which the pilot's Sonnet evaluator called minor and borderline |
| 3 | Predicate scripts with controls | controls pass (table below); two acceptance reruns pending. Baselines re-read 2026-11-15: jnwb `dev` = ac995dde and jynx `dev` = bc72f27b, unmoved; jarness `dev` moved after the freeze to 1d032017 (the telemetry repair: `harness/hooks/subagent_log.py`, its test, two state files; none is T1's target), and T1 keeps its frozen baseline 3fb6fe0 |
| 4 | Packets and scripts frozen, reviewed | in work, not frozen: `PACKETS.md`, `exp_scrub.py`, `exp_candidates.py`, `exp_table_check.py`, `exp_scripts_test.py` (20 controls pass). Review 1 (`review/packets_reviewer1.md`, at 4715cc78): ACCEPT, no A finding, 8 B and 5 C; the packets were then changed (table below), so a fresh review of the changed text is owed before the freeze |
| 5 | T1 and T4 only in experiment worktrees | holds; nothing run |
| 6 | Orchestrator model id | `get_session` 2026-11-15: `session_context.model` and `last_served_model` `claude-fable-5-2` (configured `claude-opus-5-5`); priced by the Fable 5.2 row of `prices_2026-11-15.md`. To be re-read at the first dispatch |
| 7 | Hamm's go | not given |

## Prerequisite 3: predicate controls (2026-11-15; `predicates/`, `accept/`)

| Task | Untouched baseline | Throwaway solved tree | Acceptance on baseline |
|---|---|---|---|
| T1 | PRIMARY 0/3, CONSTRAINTS 3/3 | 3/3, 3/3 | `ACCEPT_RC=0` |
| T2 | 0/3, 3/4 | 3/3, 4/4; 2/3 with the three inline splits left in | `ACCEPT_RC=0`; pytest step 943 s (15 min 43 s) under load, gate step not timed |
| T3 | 0/3, 1/2 | 3/3, 2/2 | `ACCEPT_RC=0` (103 s and 19 s) |
| T4 | 0/1, 1/2 | 1/1, 2/2 | `ACCEPT_RC=0` |

T2 to T4 lines: `predicates/controls_t2_t3_t4.txt`; T1 rerun by the orchestrator, lines not stored. A constraint
that fails on the baseline is the "only files under ... change" check on an empty change, by design. Each
constraint's failing perturbation was shown by the script's writer and not rerun. T4's acceptance command exits 0
on the baseline (the size is a minor finding of `artifacts_check.py`): only the predicate separates a solved T4.
Acceptance scripts use one pytest basetemp per tree, changed after the workers' controls, so two trees can run
them at once.

T2 feasibility (Hamm 2026-11-15): arm B's keeper runs acceptance once per draft in one dispatch, and two serial
runs (943 to 953 s each) pass the 30-minute cap. Amendment 1 (`t2_amendment/AMENDMENT.md`, 2026-11-16) keeps
all 30 files, runs them on six xdist workers, adds the preserved-behaviour test to acceptance and P4 and C5 to
the predicates. Measured alone: 257, 242 and 245 s per run on the baseline; two runs take under 9 of the 30
minutes. T2 after the amendment: baseline 0/4 and 4/5, corrected reference 4/4 and 5/5 with `ACCEPT_RC=0`,
defective reference 4/4 and 4/5 with `ACCEPT_RC=1`. The row for T2 in the table above is the pre-amendment
record. Review 1 of the amendment returned REVISE (a wrong refactor passed); the preserved test grew from 31 to
56 tests and the controls were rerun (revision 2). Review 2 returned REVISE (four surviving wrong conventions;
P1 to P3 rejected two valid refactors). Amendment 2 (Hamm 2026-11-15 and 2026-11-16) replaces P1 to P3 by an
AST structure check and a generated differential test: baseline 0/4 and 4/5, corrected reference and three
other valid refactors 4/4 and 5/5, every wrong or unconsolidated control below 4/4; two acceptance runs at once
take 331 and 328 s. The T2 row of the table above is superseded by these figures. The one review of
amendment 2 returned STOP (2026-11-16): the structure check passes unconsolidated trees with correct behaviour
and the differential misses new wrong conventions. Under Hamm's stopping rule instrument development is
stopped. Amendment 3 (Hamm 2026-11-16, a material amendment): P1 and P2 leave the primaries; structure is
judged by two independent adjudicators against a rubric fixed at 052a37d8 (`PASS`, `FAIL` or `AMBIGUOUS`); P3
runs on generator revision 2, P4 and C1 to C5 unchanged. On known controls: both adjudicators 23 of 23 against
the anchors (limited independence, no arm-produced tree); the differential leaves 19 correct trees at 0 and
rejects 22 wrong trees at each of five seeds, and one wrong tree (`w_hdr2`) shows no difference at a public
entry point. T2 as amended is not the measurement `PREREG.md` froze. Not reviewed; the T2 packet is not frozen.

Baselines re-read 2026-11-16: jnwb `dev` moved to fabe3c02 (one README line); T2 and T3 keep ac995dde.

## Packet review 1: disposition (Hamm's rule: every B needs one)

| Finding | Disposition |
|---|---|
| B1 guess question told evaluators that team size differs | fixed: the guess is a second packet, sent after the judgments pass the script |
| B2 evaluation trees beside the arm worktrees | fixed: evaluation trees and their clone under `D:/repos/_eval/`; packets allow the four trees only |
| B3 keeper's transfer of untracked files unspecified | fixed: three named steps |
| B4 keeper's "do not improve" could suppress its fix round | fixed: the sentence is scoped to the transfer step |
| B5 all acceptance scripts pass on the baseline, so the keeper's best-of-two is close to "worker 1" | accepted as the frozen rule's consequence; to be named in the report beside the structural advantage |
| B6 no-report slot, slot order, replacement packet, closing review's reports unspecified | fixed: one line each |
| B7 a table row must hold a candidate, so a defect nobody raised never enters `V` | ruled (Hamm 2026-11-15): the adjudicator is candidate-only (verify, reject, deduplicate, classify, closure); what it notices beyond the candidates is kept as a `NOTE`, exploratory, outside the scored comparison, credited to no arm |
| B8 TASK block gave the acceptance command to every agent | fixed: `ACCEPT-t<n>` goes only to the final-tree writer and the reviewers, as PREREG says |
| C1 readings not in this file | listed below |
| C2 "reported as empty" | fixed to PREREG's "not reported" |
| C3 arm name after an underscore not scrubbed | fixed, with a control |
| C4 guess never parsed | moot after B1: the guess is its own one-line output |
| C5 role-word scrub rewrites quoted code in reports | accepted: PREREG orders it; only the extractor reads scrubbed reports and the ledger holds them whole |

Readings fixed in `PACKETS.md`, not in the reviewed `PREREG.md` (qualifications): T1 and T2 run as one-part tasks
(their items enumerate no parts), so by PREREG the T1 and T2 sensitivity analysis is not reported; one evaluator's
defect on both snapshots is one candidate; a false row carries the source `none`; arm A's label is
`random.Random(2026111500 + n).choice("pq")` (T1 q, T2 p, T3 q, T4 q); a refused evaluation output is returned
once for its form only; experiment worktrees link to a single-branch clone so this record is unreachable by git.

## Ruling on the cross-family evaluator (Hamm 2026-11-15, after the smoke result)

Muse stays the frozen cross-family evaluator; evaluator, thresholds and adjudication rules are unchanged. Its miss
of the one known borderline defect is a measured sensitivity limit: one case, no detection rate. A defect's
absence is never read from Muse's list alone; the adjudication of `PREREG.md` decides. The miss goes into the
final analysis with its evidence (`smoke_summary.txt`; the defect in `../ocma8_pilot_2026-11-15/RESULTS.md`).
No further scorer probe runs before the experiment.

Telemetry limits accepted as scoped (same ruling): macOS unknown; the jarness install receipt is stale against
the installed hook; whether the harness emitted a duplicate stop in the real resume is not established, because
deduplication masks it; a resumed run's row is cumulative by design. The repair is not widened without a new
demonstrated defect.
