# T2 amendment 2 (2026-11-16, for review 3)

Status: amendment 1 was reviewed twice, REVISE both times (`../review/t2_amendment_reviewer1.md`,
`../review/t2_amendment_reviewer2.md`; sections "Review 1 and repair", "Review 2"). Amendment 2 (section
"Amendment 2") replaces the primary predicates P1 to P3 on Hamm's ruling of 2026-11-15 (option 2, a bounded
structural check) and his ruling of 2026-11-16 on the terminal escaped pipe. One bounded implementation, one
independent review; not reviewed yet. Not accepted; T2 not frozen.

| Conclusion | Status |
|---|---|
| C5 detects the defective reference and M1 to M13 | demonstrated (round 2; review 2 reran M1 to M9, M11, M12 on the 56-test file) |
| C5 accepts valid alternative implementations | shown for three refactors built by review 2 (v1, v2, v3: 56 and 6 passed) |
| C5 detects every wrong convention in the classes it claims | NO: review 2's four survivors pass it. The new P3 rejects all four (6 to 31 preserved mismatches) |
| P1 and P2 accept valid alternative implementations | shown for pos2, v1, v2, v3 (PRIMARY 4/4); a1, valid with a delegation the AST does not resolve, is AMBIGUOUS, not rejected |
| P1 rejects unconsolidated implementations with correct behaviour | shown for u1, u2, u3 (P1 FAIL with P3, P4, C5 passing) |
| P3 is correct at a row-final escaped pipe | spaced closing: shown at two readers, with a negative control. Open and tight closings: outside the contract; every reference fails the independent oracle there (unresolved parser-contract issue) |
| Two keeper dispatches fit the 30-minute cap | UNKNOWN: two serial acceptance runs take 526 of 1800 s; two at once take 331 and 328 s each, inside the 10-minute timeout; dispatch overhead is unmeasured |
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

## Amendment 2: structural P1 and P2, differential P3 (not reviewed)

Motivation: the complete false-positive and false-negative record of the instrument before this amendment.

| Kind | Case | Instrument at the time | Outcome |
|---|---|---|---|
| False positive | defective reference (`old_pos_defective.diff`) | frozen P1 to P3, C1 to C4 | PRIMARY 3/3, CONSTRAINTS 4/4 while two readers changed behaviour |
| False positive | M2, M6, M8, M9 | frozen acceptance (30 files) | survive |
| False positive | review 1's dashboard reader on the strip convention (M10) | 31-test preserved file, corrected file, 30 files | passes all |
| False positive | `s_tab`, `s_hdr`, `s_led`, `s_ledsingle` (review 2) | 56-test preserved file, corrected file, tree's tests | pass all |
| False negative | v1 (compiled pattern), v3 (intermediate variable) | syntactic P1 to P3 | PRIMARY 1/4 with P4 and C5 passing |
| Misreport | defective reference said to pass the frozen acceptance | none stored | it fails: 129 tests (section "Why", item 3) |

Rulings (Hamm 2026-11-15): primaries are P1 consolidation (all eight former sites use one shared parsing
implementation), P2 removal (the eight independent baseline splitters are removed), P3 behaviour (correct
parsing through every affected reader), P4 the existing behavioural gate. The structural check reads AST
relationships, bounded to the eight sites and the supported patterns; an ambiguous case goes to independent
adjudication, never to automatic rejection. Survivors are met by differential testing against the baseline for
preserved behaviour and against the unified-parser contract for corrected behaviour, generated tests outside
both arms, seed and failing inputs recorded, undocumented behaviour ruled exploratory not required. Stopping
rule: one bounded implementation and one independent review; if the checker still rejects a valid
implementation or accepts an unconsolidated one, instrument development stops and the problem returns to Hamm.

| Predicate | Before | After |
|---|---|---|
| P1 | exactly one function matching a name or a `return` pattern | `predicates/t2_structure.py`: every anchor of the eight sites reaches one and the same delimiter definition. PASS, FAIL (two anchors share none) or AMBIGUOUS |
| P2 | the one splitter called directly on two rows | `t2_structure.py`: no baseline site function or anchor holds a split in its own body. PASS, FAIL or AMBIGUOUS |
| P3 | no line matching an inline-split pattern | `predicates/t2_differential.py`, seed 2026111600, 13 reader entry points, 300 rows per reader and mode: 0 mismatches in preserved mode (3771 inputs, tree equals baseline) and in corrected mode (3784 inputs, tree equals the baseline on the row with each escaped pipe replaced by an ordinary character); 245 exploratory inputs unscored; mismatching inputs written to a file |
| P4, C1 to C5 | | unchanged |
| Summary line | `PRIMARY k/4 CONSTRAINTS j/5` | `PRIMARY k/4 AMBIGUOUS a CONSTRAINTS j/5` |

Acceptance (`accept/`), the 30 files, the 56-test file, the cap and the timeout are unchanged. The three new
files sit with the predicates; arms cannot read them.

Structure definitions (the docstring of `t2_structure.py` is the reference). A delimiter definition is a
function body that splits on a pipe: `.split`/`re.split` with a pipe constant or a name bound to one, a
compiled pipe pattern's `.split`, or a comparison with `"|"` inside a loop; a pattern bound at module level is
one definition for every function that uses it. Anchors come from the baseline: the callers of the 5 splitter
definitions and the 3 functions holding the inline splits (8 sites, 12 anchors). Calls are followed through
local functions, module-level aliases and lambdas, `from m import f as g` and `import m as n`, to depth 8.

Controls (`matrix4.txt`, run by the orchestrator, three trees at a time under the suite lock; every tree's
`git status` hash equal before and after; 105 to 120 s per tree; `structure_matrix.txt` holds the P1 and P2
lines alone). The worker's differential counts (`differential_controls_worker.txt`) were reproduced exactly.

| Tree | What it is | P1 | P2 | P3 preserved / corrected mismatches | P4 | C5 | PRIMARY | CONSTRAINTS |
|---|---|---|---|---|---|---|---|---|
| base | baseline | FAIL | FAIL | 0 / 688 | 6 fail | 56 | 0/4 | 4/5 (C4, empty diff) |
| pos2 | corrected reference | PASS | PASS | 0 / 0 | 6 | 56 | 4/4 | 5/5 |
| v1 | valid: compiled module-level pattern, two functions, wrappers kept | PASS | PASS | 0 / 0 | 6 | 56 | 4/4 | 5/5 |
| v2 | valid: character scan in an existing module, lambda aliases | PASS | PASS | 0 / 0 | 6 | 56 | 4/4 | 5/5 |
| v3 | valid: intermediate variable, helpers renamed | PASS | PASS | 0 / 0 | 6 | 56 | 4/4 | 5/5 |
| a1 | valid: static method behind `split_cells = Row.cells` | AMBIGUOUS | PASS | 0 / 0 | 6 | 56 | 3/4, AMBIGUOUS 1 | 5/5 |
| u1 | unconsolidated: the reference splitter copied into each of six modules | FAIL | PASS | 0 / 0 | 6 | 56 | 3/4 | 5/5 |
| u2 | unconsolidated: six copies in one module, one per reader module | FAIL | PASS | 0 / 0 | 6 | 56 | 3/4 | 5/5 |
| u3 | unconsolidated: the eight baseline splits fixed in place | FAIL | FAIL | 0 / 0 | 6 | 56 | 2/4 | 5/5 |
| pos_inline | defective, three inline splits left | FAIL | FAIL | 323 / 540 | 3 fail | 8 fail | 0/4 | 4/5 |
| pos | defective reference | PASS | PASS | 445 / 396 | 6 | 14 fail | 3/4 | 4/5 |
| M10 | pos2, dashboard reader on the strip convention | PASS | PASS | 221 / 248 | 6 | 6 fail | 3/4 | 4/5 |
| M11 | base, `learning_gate._cells` on the slice convention | FAIL | FAIL | 17 / 662 | 5 fail | 2 fail | 0/4 | 4/5 |
| M12 | base, `build_fact_graph._cells` on the slice convention | FAIL | FAIL | 118 / 494 | 5 fail | 2 fail | 0/4 | 4/5 |
| M13 | pos2, every reader on the slice convention | PASS | PASS | 319 / 312 | 6 | 12 fail | 3/4 | 4/5 |
| s_tab | review 2 survivor | PASS | PASS | 21 / 13 | 6 | 56 | 3/4 | 5/5 |
| s_hdr | review 2 survivor | PASS | PASS | 6 / 6 | 6 | 56 | 3/4 | 5/5 |
| s_led | review 2 survivor | PASS | PASS | 31 / 18 | 6 | 56 | 3/4 | 5/5 |
| s_ledsingle | review 2 survivor | PASS | PASS | 9 / 9 | 6 | 56 | 3/4 | 5/5 |

Read: the four valid refactors pass every primary. Every tree with wrong behaviour fails P3. The three
unconsolidated trees keep correct behaviour (P3, P4, C5 pass) and fail P1. The four survivors are rejected by
P3 alone: C5 and the acceptance still pass them, so an arm can hand in such a tree with `ACCEPT_RC=0` and the
defect shows only in the hidden predicates. u1 and u2 pass P2: the baseline splitters are gone under their
names and anchors; P1 carries the rejection. M1 to M9 and the constraint negatives `pos_c1` to `pos_c4` were
not rerun; C1 to C4 are unchanged.

Control trees: `build_structure_controls.py` (u1, u2, u3, a1), `build_t1.py` (t1), `review2_probes/` (v1 to v3,
survivors; `v1_table_cells.py` and `v3_md_table.py` are the new modules the diffs omit), `mutants/`.

### Terminal escaped pipe (Hamm 2026-11-16, provisional)

`terminal_cell_check.py`, output `terminal_cell.txt`: one valid row per reader whose last cell is `v\|`, three
closings, against an oracle written without any tree (the cell is `v` followed by a pipe, backslash kept or
dropped). 2 of the 13 readers return the last cell as a parsed cell (`read_facts`, `reference_table_rows`);
the other 11 are not judged.

| Closing | Scope | base | pos2, v1, v2, v3 | t1 (drops a cell-final escaped pipe) |
|---|---|---|---|---|
| spaced `v\| \|` | scored | raises (2 of 2) | correct (2 of 2) | wrong (2 of 2); P3 corrected mismatches 10, preserved 0 (`t1_mismatches.jsonl`) |
| open `v\|` | exploratory | `v\` | `v\` (known oracle failure) | `v\` |
| tight `v\|\|` | exploratory | `v\` | `v\` (known oracle failure) | `v\` |

Unresolved parser-contract issue: `.strip("|")` on the row removes the bar of an escaped pipe that ends the
row, so the last cell loses it. Affected forms: open and tight, at every reader on the strip convention;
observed at the two readers above. Reproducer: `| F1 | ... | v\|` through `build_fact_graph.read_facts`
(`terminal_cell_check.py`). The baseline, the corrected reference and v1 to v3 all do it. Preserving that
baseline behaviour is not satisfying the oracle: the forms are outside the bounded T2 contract, neither invalid
syntax nor correct behaviour, and the references hold their standing for the scored contract only. Production
parsing is not changed here.

Condition checked before the exclusion (`terminal_form_scan.py`, `terminal_form_scan.txt`): 5067 table-like
lines in 215 tracked text files at ac995dde, 7 with an escaped pipe, all inside a cell: 0 open, 0 tight,
0 spaced; the same counts at `dev` fabe3c02 with the README line. Specifications found by grep for the escape
rule: item 17-95 ("honours escaped pipes") and `test_an_escaped_pipe_inside_a_code_span_is_content`
(`` `a\|b` `` is one cell); both concern a pipe inside a cell, neither a row-final one. No conflict to escalate.

The scored generator is unchanged. It emits the spaced form and the open form (45 rows end in an escaped
pipe); at this seed none of the open rows reaches a reader that returns the cell (inferred from 0 mismatches on
pos2 and the two observing readers' failure in the check), and it never emits the tight form.

### Timing, two runs at once

`accept_pair_timing.txt`: baseline and corrected reference started together under the suite lock: 331 s and
328 s, both `ACCEPT_RC=0` (22 of 22; 1527 passed, 4 skipped in 275 s and 271 s; 56 passed), 55% of the
10-minute per-run timeout; alone, 242 to 263 s. The differential worker's controls ran during the measurement,
so the figure includes that load. Keeper dispatch overhead is not measured.

### Limits

- Static reading cannot prove call relationships in general. Unresolved: attribute aliases, methods,
  `functools.partial`, dynamic dispatch, a splitter outside `scripts/`: these give AMBIGUOUS.
- P1 FAIL needs two anchors with no definition in common. A tree where every anchor reaches the shared
  definition and one also keeps its own split is AMBIGUOUS on P1; P2 then reads FAIL or AMBIGUOUS.
- A splitter with no recognised split form (for example `str.partition` in a loop) is AMBIGUOUS.
- Who adjudicates an AMBIGUOUS cell, and how the answer enters the ledger, is not in `PREREG.md`: Hamm's.
- P3's corrected oracle is the baseline on a substituted row, so it inherits baseline behaviour around the
  escape; the terminal forms above are where that differs from the independent oracle.
- One seed. The row classes are those of the ruling; 300 rows per reader and mode.

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

One independent review of amendment 2 at its final SHA (the stopping rule allows one). Hamm: the adjudication
route for an AMBIGUOUS cell; the go decision. Experiment execution stays withheld.
