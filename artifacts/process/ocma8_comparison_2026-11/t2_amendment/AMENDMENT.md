# T2 amendment 1, revision 2 (2026-11-16, for review)

Status: review 1 returned REVISE (`../review/t2_amendment_reviewer1.md`); coverage repaired and controls rerun
(section "Review 1 and repair"). Review 2 of revision 2 at de539073 returned REVISE
(`../review/t2_amendment_reviewer2.md`; section "Review 2"). Not accepted; T2 not frozen.

| Conclusion | Status |
|---|---|
| C5 detects the defective reference and M1 to M13 | demonstrated (round 2; review 2 reran M1 to M9, M11, M12 on the 56-test file) |
| C5 accepts valid alternative implementations | shown for three refactors built by review 2 (v1, v2, v3: 56 and 6 passed) |
| C5 detects every wrong convention in the classes it claims | NO: review 2 found four survivors |
| P1 to P3 accept valid alternative implementations | NO: review 2's v1 and v3 score PRIMARY 1/4 with P4 and C5 passing |
| Two keeper dispatches fit the 30-minute cap | UNKNOWN: two acceptance runs take 526 of 1800 s; dispatch overhead and two runs at once are unmeasured |
T2 is not frozen. No experiment cell has run. `PREREG.md` is unchanged: the 30-minute cap, the evaluator, the
thresholds and the adjudication rules stand.

## Why

1. The frozen acceptance command ran 943 to 953 s serial on the baseline (plus the gate, 50 s). Arm B's keeper
   runs it twice, so one cell could not fit the 30-minute cap.
2. A mutation study of the eight pipe-split sites (`mutants/`, `matrix.txt`) left M2, M6, M8 and M9 alive under
   the frozen acceptance: it did not cover every site's behaviour.
3. A throwaway reference refactor (`old_pos_defective.diff`) scored PRIMARY 3/3, CONSTRAINTS 4/4 on the frozen
   predicates while changing behaviour at two readers. It is kept as the false-positive control.
   Correction (2026-11-16): earlier messages said it also passed the frozen acceptance. No stored run shows
   that, and the tree, byte-equal to the recorded diff, fails it: 129 tests of
   `tests/test_release_requires_an_empty_open_stack.py` fail, serial or parallel (the reader takes the
   `# Roadmap` heading of the tree's own files as a row). The false positive is the predicates' alone.

## Rulings applied (Hamm 2026-11-15)

- No test is removed for runtime. The 30 files stay; they run on six xdist workers.
- Tests assert the behavioural contract at each reader's entry point, independent of the refactor's structure.
- Acceptance holds the preserved behaviour (PASS at baseline and on a valid refactor). The hidden predicates
  hold the corrected behaviour (FAIL at baseline, PASS on a valid refactor), same contract at all sites.
- Malformed rows: prose with a pipe and the roadmap row are preserved behaviour; ledger and defect rows without
  a leading pipe are exploratory (`input_usage_check.py`: 15 accepted rows in the tracked input, all with a
  leading pipe; conclusion scoped to that input).
- The cap is not raised. If the required acceptance cannot fit, it is retained and escalated.

## Changes

| Instrument | Before | After |
|---|---|---|
| `accept/accept_t2.sh` | gate; pytest on 30 files, serial | gate; the same 30 files with `-n 6`; `accept/t2_preserved_test.py` (56 tests; 31 before review 1) |
| `predicates/predicates_t2.py` | P1 to P3, C1 to C4 | adds P4 (`predicates/t2_corrected_test.py`, exactly 6 passed) and C5 (the preserved file, exactly 56 passed); summary `PRIMARY k/4 CONSTRAINTS j/5` |
| Placement | | the preserved test sits with the acceptance script (arms may read it); the corrected test sits with the predicates (arms cannot) |
| `t2_exploratory_test.py` | | 2 tests, reported, outside scoring |

`PACKETS.md` ACCEPT-t2 (baseline lines, timeout) and `FREEZE.md` follow once timing is measured.

## Evidence

The tables of this section were measured with the 31-test preserved file, before review 1. The figures in
force are in "Review 1 and repair".

Mutation kills by the preserved file (`matrix2.txt`, section d), failing tests per mutant: M1 5, M2 1, M3 5,
M4 2, M5 3, M6 2, M7 4, M8 3, M9 3. Each kill is a named failing assertion in that file.

Predicate controls with the amended script (`controls_amended.txt`; each tree's `git status` hash is equal
before and after):

| Tree | Built as | PRIMARY | CONSTRAINTS | Failing checks |
|---|---|---|---|---|
| base | baseline ac995dde | 0/4 | 4/5 | P1 to P4; C4 (empty diff) |
| pos2 | corrected reference (`pos2.diff`) | 4/4 | 5/5 | none |
| pos | defective reference | 4/4 | 4/5 | C5 (2 of 31 fail) |
| pos_inline | defective, inline sites left | 2/4 | 4/5 | P3, P4, C5 |
| pos_c1 | defective, gate broken | 2/4 | 3/5 | P3, P4, C1, C5 |
| pos_c2 | defective, unresolved name | 2/4 | 2/5 | P3, P4, C1, C2, C5 |
| pos_c3 | defective, gate writes a tracked file | 2/4 | 1/5 | P3, P4, C1, C3, C4, C5 |
| pos_c4 | defective, file outside scope | 2/4 | 3/5 | P3, P4, C4, C5 |

The defective reference scores PRIMARY 4/4: its rejection rests on C5 alone. The four constraint negatives were
built on the defective reference, so C5 fails in each beside the constraint it was built to break.

Amended acceptance, run alone under the machine suite lock (`accept_timing.txt`; each tree's `git status` hash
equal before and after):

| Tree | Gate | 30 files, `-n 6` | Preserved test | Result | Wall |
|---|---|---|---|---|---|
| base, run 1 | 22 of 22 | 1527 passed, 4 skipped, 202.40 s | 31 passed | `ACCEPT_RC=0` | 257 s |
| base, run 2 | 22 of 22 | 1527 passed, 4 skipped, 196.53 s | 31 passed | `ACCEPT_RC=0` | 242 s |
| base, run 3 | 22 of 22 | 1527 passed, 4 skipped, 200.00 s | 31 passed | `ACCEPT_RC=0` | 245 s |
| pos2 (corrected reference) | 22 of 22 | 1527 passed, 4 skipped, 206.97 s | 31 passed | `ACCEPT_RC=0` | 263 s |
| pos (defective reference) | 22 of 22 | 129 failed, 1398 passed, 4 skipped | 2 failed, 29 passed | `ACCEPT_RC=1` | 247 s |

Cap: the slowest baseline run is 257 s and the slowest of the four passing runs 263 s. Two keeper runs take
526 s (8.8 min) at the slower figure, 29% of the 30-minute cap; the wall time includes xdist start and
teardown. The spread over the three baseline runs is 15 s. The packet's per-run timeout is 10 minutes
(2.3 times the slowest run). Dispatch overhead and the keeper's own work use the remaining 21 minutes; that
share is not measured here.

The slowest file of the serial study (`test_release_requires_an_empty_open_stack.py`, 374 s serial on the
baseline) killed no mutant alone, and it is the only one of the 30 files that rejects the defective reference.
It stays, as every file does.

## Review 1 and repair

Review 1 (REVISE) built a wrong refactor that passed the 31-test preserved file, the corrected file and the
dashboard tests of the 30 files: the corrected reference with the dashboard row reader switched from the slice
convention (`re.split(...)[1:-1]`) to the strip convention. `build_dashboard.deferred_section()` then accepts
a roadmap row with no trailing pipe, or ending `||`; the baseline refuses both. The negative result stands.

Repair: 25 tests added to `accept/t2_preserved_test.py` (the 31 are unchanged, byte-equal prefix): rows with no
trailing pipe and rows ending `||` at each reader's entry point, and entry-point tests for
`build_dashboard.order_section`, the studies cards (through `validations_section`) and the `learning_gate`
mapping header. Four mutants added (`mutants/M10.diff` to `M13.diff`; `matrix3.txt`, rerun by the orchestrator
with the same counts):

| Tree | 31-test file | 56-test file | Killing tests |
|---|---|---|---|
| base | 31 passed | 56 passed | |
| pos2 (corrected reference) | 31 passed | 56 passed | |
| pos (defective reference) | 2 failed | 14 failed | |
| M10: pos2, dashboard reader on the strip convention (review 1's case) | 31 passed | 6 failed | deferred, order and studies rows, no trailing pipe and `||` |
| M11: base, `learning_gate._cells` on the slice convention | 31 passed | 2 failed | ledger row and mapping header, no trailing pipe |
| M12: base, `build_fact_graph._cells` on the slice convention | 31 passed | 2 failed | fact row, no trailing pipe and `||` |
| M13: pos2, every reader on the slice convention | 31 passed | 12 failed | fact, reference, ledger, mapping, roadmap, vocabulary and defect rows |

M1 to M9 were not rerun on the 56-test file; their killing tests are in the unchanged prefix (inferred).
Seven of the 25 added tests kill no mutant (order and studies well-formed rows, mapping header accepted and
refused, ledger row ending `||`, `table_data_rows` with no trailing pipe and with `||`). They cover entry
points; their sensitivity to a defect is not established.

Round 2 (`controls_round2.txt`; alone under the suite lock; each tree's `git status` hash equal before and
after):

| Tree | PRIMARY | CONSTRAINTS | Failing checks | Amended acceptance | Wall |
|---|---|---|---|---|---|
| base | 0/4 | 4/5 | P1 to P4; C4 (empty diff) | `ACCEPT_RC=0` (1527 passed, 4 skipped; 56 passed) | 245 s |
| pos2 | 4/4 | 5/5 | none | `ACCEPT_RC=0` (1527 passed, 4 skipped; 56 passed) | 243 s |
| pos | 4/4 | 4/5 | C5 (14 of 56) | `ACCEPT_RC=1` (129 failed in the 30 files; 14 of 56) | 249 s |
| M10 | 4/4 | 4/5 | C5 (6 of 56) | `ACCEPT_RC=1` (30 files all pass; 6 of 56) | 242 s |
| M13 | 4/4 | 4/5 | C5 (12 of 56) | not run | |
| pos_inline | 2/4 | 4/5 | P3, P4, C5 (8 of 56) | not run | |

The defective reference, M10 and M13 score PRIMARY 4/4: C5 alone rejects them in the predicates, and for M10
the preserved file alone rejects it in acceptance. C5 and the preserved file are mandatory.

Timing over all baseline and corrected-reference runs (six runs): 242 to 263 s. Two keeper runs at 263 s take
526 s, 29% of the cap. Keeper dispatch overhead and two acceptance runs at once are not measured.

Review 1's minor findings: the ACCEPT-t2 text now says the times and the warning count vary; the 30-file pytest
step closes stdin; the exploratory ruling is quoted under "Rulings applied".

Open for review 2: the studies-card test patches eight names of `build_dashboard` (`REFERENCES`, `_receipt`,
`_git`, `CALIBRATION_RECEIPTS`, `_performance_cards`, `_frozen_card`, `_closure_card`, `VALIDATION_HTML`), most
of them private. It depends on structure outside the splitters. Whether it can reject a valid refactor is the
reviewer's question; if it can, it is replaced by a fixture through a public entry point.

## Review 2 (REVISE; nothing below is repaired yet)

Probe diffs and outputs: `review2_probes/`.

1. Major, pre-existing in the frozen-candidate predicates: P1 to P3 recognise the splitter by syntax (a baseline
   name, or a `return` whose source matches a `split("...|` pattern). Valid refactors fail them: v3 (one
   splitter, an intermediate variable before the return) scores P1 definitions=0, P2 not evaluated, P3 FAIL on
   the splitter's own line, PRIMARY 1/4 with P4 and C5 passing; v1 (compiled pattern) scores PRIMARY 1/4. The
   corrected reference passes because its return is a one-line comprehension over `re.split`. This contradicts
   the ruling that the hidden predicates are independent of the refactor's structure. The repair changes what
   PRIMARY counts: Hamm's decision.
2. Major: four wrong conventions pass the 56-test file, the corrected file and the tree's own tests
   (`s_tab`, `s_hdr`, `s_led`, `s_ledsingle`): the open-stack table reader on the slice convention (a header
   and a separator count as rows when the separator is `|---||` or `|---`); the fact-table header with no
   trailing pipe or ending `||` (raises); the ledger reader dropping an empty cell (`| cls:a | 3 | |` returns
   nothing); one outer pipe stripped per side at the ledger (`| cls:a | 3 ||` returns a row). No tracked file
   holds such input (5062 table-like lines in 188 tracked `.md` files: one with no trailing pipe, none with
   `||`). A fifth, cells padded with tabs, is minor. Three added tests (17, 20, 21) discriminate no convention.
3. Major, fixed in this revision's `PACKETS.md`: `exp_t2cov/` holds the corrected solution and was missing from
   the move-out list.
4. C5 validity: three structurally different valid refactors pass the 56 and the 6 tests. The studies-card
   fixture patches names a split-site refactor does not touch; a lighter route exists (`_study_cards()` with
   three patches) and is optional.
5. Cap: two runs are 29% of the cap. The 10-minute per-run timeout is the exposure, in arm B only, where two
   workers may run acceptance at once; the reviewer advises measuring one two-at-once run before the freeze.
6. `FREEZE.md`'s T2 table row is the pre-amendment record and reads as stale.

Two rounds of enumerated fixtures each left survivors of the same class. A third round of the same kind is not
planned without a ruling on the approach.

## Readings

- No corrected test covers `release_gate.table_data_rows`: an escaped pipe does not change its output.
- `pos2` keeps one splitter with a `keep_outer` flag. One reference is not all valid implementations.
- Escaped-pipe rows read differently at 7 of 8 readers after the correction; that is the intended change.
- `cited_works_removed` splits on a spaced pipe and is not one of the eight sites.
- P and C counts change (3 and 4 to 4 and 5). The scoring rule over them is PREREG's and is unchanged.

- Six workers on a 24-core machine: a run beside another suite is slower. Arm B's two workers may run the
  acceptance at once. Runs of the 30 files beside another agent's suite measured 221, 210 and 249 s, inside
  the 10-minute timeout; two acceptance runs at once were not measured.

## Owed before freeze

Independent review 2 of this amendment and of the changed `PACKETS.md` (ACCEPT-t2, the deployment paragraph).
