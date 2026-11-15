# T2 amendment 1 (DRAFT, 2026-11-15)

Status: instruments changed and predicate controls run; acceptance timing and independent review owed. T2 is
not frozen. No experiment cell has run. `PREREG.md` is unchanged: the 30-minute cap, the evaluator, the
thresholds and the adjudication rules stand.

## Why

1. The frozen acceptance command ran 943 to 953 s serial on the baseline (plus the gate, 50 s). Arm B's keeper
   runs it twice, so one cell could not fit the 30-minute cap.
2. A mutation study of the eight pipe-split sites (`mutants/`, `matrix.txt`) left M2, M6, M8 and M9 alive under
   the frozen acceptance: it did not cover every site's behaviour.
3. A throwaway reference refactor (`old_pos_defective.diff`) passed the frozen acceptance and predicates 3/3
   while changing behaviour at two readers. It is kept as the false-positive control.

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

## Readings

- No corrected test covers `release_gate.table_data_rows`: an escaped pipe does not change its output.
- `pos2` keeps one splitter with a `keep_outer` flag. One reference is not all valid implementations.
- Escaped-pipe rows read differently at 7 of 8 readers after the correction; that is the intended change.
- `cited_works_removed` splits on a spaced pipe and is not one of the eight sites.
- P and C counts change (3 and 4 to 4 and 5). The scoring rule over them is PREREG's and is unchanged.

## Owed before freeze

1. Amended `accept_t2.sh` on base and pos2 (`ACCEPT_RC=0`) and on the defective reference (`ACCEPT_RC=1`).
2. Three uncontended runs of the amended acceptance on the baseline; the slowest, doubled, plus dispatch
   overhead, against the 30-minute cap. Contended runs of the 30 files with `-n 6`: 221, 210, 249 s
   (1527 passed, 4 skipped each); these do not count.
3. `PACKETS.md` ACCEPT-t2 and `FREEZE.md` updated; independent review of this amendment and the changed packet.
