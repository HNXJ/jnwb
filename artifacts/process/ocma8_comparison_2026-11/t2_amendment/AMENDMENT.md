# T2 amendment 1 (2026-11-16, for review)

Status: instruments changed; predicate controls, acceptance controls and timing run; independent review owed.
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
| `accept/accept_t2.sh` | gate; pytest on 30 files, serial | gate; the same 30 files with `-n 6`; `accept/t2_preserved_test.py` (31 tests) |
| `predicates/predicates_t2.py` | P1 to P3, C1 to C4 | adds P4 (`predicates/t2_corrected_test.py`, exactly 6 passed) and C5 (the preserved file, exactly 31 passed); summary `PRIMARY k/4 CONSTRAINTS j/5` |
| Placement | | the preserved test sits with the acceptance script (arms may read it); the corrected test sits with the predicates (arms cannot) |
| `t2_exploratory_test.py` | | 2 tests, reported, outside scoring |

`PACKETS.md` ACCEPT-t2 (baseline lines, timeout) and `FREEZE.md` follow once timing is measured.

## Evidence

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

Independent review of this amendment and of the changed `PACKETS.md` (ACCEPT-t2, the deployment paragraph).
