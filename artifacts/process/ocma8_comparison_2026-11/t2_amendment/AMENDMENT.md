# T2 amendment 3 (2026-11-16, for the single freeze review): a material amendment of the T2 measurement

**Status — T2 UNFROZEN** (Hamm 2026-11-16). Generator revision 3 passed the 59-tree × 5-seed differential
matrix (295/295 runs, no exclusions, errors or warnings). All 28 behavior-correct trees produced zero scored
mismatches at every seed; all 29 behaviorally wrong trees produced at least one. The corrected reference was
reproducible across repeated runs. This establishes discrimination on the tested controls, not completeness
over unseen parsing implementations or validity of structural adjudication on arm-produced trees. Updated
after the four-tree run (14:56Z, section "Amended predicates on four trees"): the amended predicate script
printed the expected lines on the corrected reference, the baseline, `w_hdr2` and `u_const2`. Independent
freeze review has not returned. No keeper dispatch or pilot execution is authorized.

How it got here: amendment 3 (section "Amendment 3", Hamm's ruling after review 3's STOP) removed the
automated consolidation predicates as primaries; consolidation is judged by two adjudicators against a rubric
fixed beforehand, behaviour by the automated predicates on a corrected generator. Review 4 returned REVISE
(section "Review 4"). One final bounded repair cycle followed (sections "Final repair cycle"): literal rubric,
deployed adjudication protocol validated on twelve new built trees, generator revision 3. The next review is
a terminal gate: a new material REVISE ends T2 development for this pilot. T2 as amended is not the
measurement `PREREG.md` froze (section "Preregistration consequence").

Conclusions of the final cycle (Hamm 2026-11-16):

| Claim | Evidence | Disposition |
|---|---|---|
| Generator discriminates tested controls | 28/28 positives; 29/29 negatives × 5 seeds | PASS, bounded |
| Reference reproducibility | Zero mismatches; byte-equal repeats | PASS |
| Public-reader coverage | All scored families except three inapplicable inner-whitespace cases | PASS, qualified |
| `w_hdr2` detection | `routing.targets` only | Single-reader dependency |
| Generalization to unseen errors | Not tested | UNKNOWN |
| Automated predicate semantics | Four-tree run (`predicates_r3_controls.txt`): 2/2 and 5/5, 0/2 and 4/5, 1/2 and 5/5, 2/2 and 5/5 as expected; D1/D2 unscored | PASS on four trees (was UNKNOWN) |
| Structural adjudication on arm trees | Not tested | UNKNOWN |
| T2 freeze | Review outstanding | NOT CLEARED |

History, amendment 2 (stopped by the stopping rule): amendment 1 was reviewed twice, REVISE both times (`../review/t2_amendment_reviewer1.md`,
`../review/t2_amendment_reviewer2.md`; sections "Review 1 and repair", "Review 2"). Amendment 2 (section
"Amendment 2") replaces the primary predicates P1 to P3 on Hamm's ruling of 2026-11-15 (option 2, a bounded
structural check) and his ruling of 2026-11-16 on the terminal escaped pipe. Its one independent review, of
d600c360, returned STOP (`../review/t2_amendment_reviewer3.md`; section "Review 3"): the structural checker
accepts unconsolidated implementations. Instrument development is stopped and the validity problem is
returned to Hamm. Nothing found by review 3 is repaired. Not accepted; T2 not frozen.

The rows of the table below marked "shown" hold for the listed controls only; review 3's rows are appended.

| Conclusion | Status |
|---|---|
| C5 detects the defective reference and M1 to M13 | demonstrated (round 2; review 2 reran M1 to M9, M11, M12 on the 56-test file) |
| C5 accepts valid alternative implementations | shown for three refactors built by review 2 (v1, v2, v3: 56 and 6 passed) |
| C5 detects every wrong convention in the classes it claims | NO: review 2's four survivors pass it. The new P3 rejects all four (6 to 31 preserved mismatches) |
| P1 and P2 accept valid alternative implementations | shown for pos2, v1, v2, v3 (PRIMARY 4/4); a1, valid with a delegation the AST does not resolve, is AMBIGUOUS, not rejected |
| P1 rejects unconsolidated implementations with correct behaviour | shown for u1, u2, u3 (P1 FAIL with P3, P4, C5 passing) |
| P3 is correct at a row-final escaped pipe | spaced closing: shown at two readers, with a negative control. Open and tight closings: outside the contract; every reference fails the independent oracle there (unresolved parser-contract issue) |
| P1 and P2 reject every unconsolidated implementation | NO (review 3): `u_disp`, `u_hidden_call`, `u_const2` score P1 PASS, P2 PASS with correct behaviour, the first two PRIMARY 4/4 |
| P3 rejects every wrong convention | NO (review 3): `w_hdr2`, `w_maxsplit`, `w_ws` pass all four primaries; `w_bq` passes P3 and P4 |
| P1 resolves valid refactors without adjudication | rarely: 6 of review 3's 7 valid trees are AMBIGUOUS (none rejected) |
| Structural adjudication separates the known controls (amendment 3) | 23 of 23 against the anchors, two adjudicators, kappa 1.0; limited independence, no arm-produced tree |
| Revised P3 rejects wrong trees and accepts correct ones (amendment 3) | 19 correct trees 0 mismatches and 22 wrong trees more than 0 at each of 5 seeds; one wrong tree (`w_hdr2`) scores 0 (review 4: it differs at `routing_targets`, which the generator does not reach); review 4 built three more wrong trees that score 0 |
| Deployed adjudication under the literal rubric separates new built controls (final cycle) | 12 of 12 in each slot, 0 AMBIGUOUS, kappa 1.0; clear cases, no arm-produced tree, slot 2 reads only |
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
- P3's corrected oracle is the baseline on a substituted row, so it inherits baseline behaviour around the
  escape; the terminal forms above are where that differs from the independent oracle.
- One seed. The row classes are those of the ruling; 300 rows per reader and mode.

### Negative-control regression (after d600c360; `matrix5.txt`)

M1 to M9 (each diff applied to a clone of the baseline) and `pos_c1` to `pos_c4`, under the predicates of
d600c360, three trees at a time under the suite lock; every tree's `git status` hash equal before and after.

| Trees | PRIMARY | CONSTRAINTS | Not passing | P3 preserved / corrected mismatches |
|---|---|---|---|---|
| M1 | 0/4 | 4/5 | P1 to P4, C5 | 541 / 1258 |
| M2 | 0/4 | 4/5 | P1 to P4, C5 | 0 / 1047 |
| M3 | 0/4 | 3/5 | P1 to P4, C1, C5 | 400 / 778 |
| M4 | 0/4 | 4/5 | P1 to P4, C5 | 351 / 962 |
| M5 | 0/4 | 3/5 | P1 to P4, C1, C5 | 300 / 922 |
| M6 | 0/4 | 4/5 | P1 to P4, C5 | 57 / 698 |
| M7 | 0/4 | 3/5 | P1 to P4, C1, C5 | 177 / 716 |
| M8 | 0/4 | 4/5 | P1 to P4, C5 | 102 / 687 |
| M9 | 0/4 | 4/5 | P1 to P4, C5 | 86 / 708 |
| pos_c1 (gate broken) | 0/4 | 3/5 | P1 to P4, C1, C5 | 323 / 540 |
| pos_c2 (unresolved name) | 0/4 | 2/5 | P1 to P4, C1, C2, C5 | 843 / 1078 |
| pos_c3 (gate writes a tracked file) | 0/4 | 1/5 | P1 to P4, C1, C3, C4, C5 | 323 / 540 |
| pos_c4 (file outside scope) | 0/4 | 3/5 | P1 to P4, C4, C5 | 323 / 540 |

All 13 are rejected; each constraint negative fails the constraint it was built to break. The constraint
negatives carry three inline splits, so they now score PRIMARY 0/4 (2/4 under amendment 1). M2 has no
preserved-mode mismatch: corrected mode, P4 and C5 reject it. C1 fails on M3, M5 and M7; whether it did under
the frozen predicates was not checked.

### AMBIGUOUS adjudication (Hamm 2026-11-16, adopted; recorded before any application)

A governance rule adopted by Hamm, not a `PREREG.md` requirement. For one tree and one predicate:
1. Worker: documents the unresolved AST path, the source locations and why static resolution fails.
2. Independent reviewer: inspects the actual call path and returns `PASS`, `FAIL` or `UNRESOLVED` with evidence.
3. Lead: approves the adjudication and appends the ledger entry with the tree SHA and the reviewer's receipt.
4. Checker: the original automated result stands as printed. `UNRESOLVED` stays `AMBIGUOUS`; no automatic pass.

The ledger keeps the automated result, the adjudicated result, the evidence, the reviewer, the lead's approval
and the timestamp. The candidate's author does not adjudicate. Adjudication is case-specific, never a general
exemption from P1; no automated result is altered afterwards; predicates, scored generator and acceptance are
not changed by it. Not applied to any tree, a1 included.

## Review 3 (STOP; nothing below is repaired)

Review of d600c360 by a fresh reviewer (`../review/t2_amendment_reviewer3.md`; its trees as diffs and builders
in `review3_probes/`). The orchestrator reran the structure check and P3 on `u_disp`, `u_hidden_call`,
`u_const2` and `w_hdr2` and the seed finding at seeds 1 and 2: same results.

1. Blocker, stopping rule: unconsolidated trees with correct behaviour score P1 PASS and P2 PASS.
   `u_disp`: one shared `split_cells(site=)` that dispatches through a dict to per-site splitters, PRIMARY 4/4.
   `u_hidden_call`: six modules keep their own splitter in a form the check does not recognise
   (`replace`, `translate`, `split(chr(1))`) beside a real shared call whose result is returned only when the own one is empty, PRIMARY 4/4,
   CONSTRAINTS 5/5. `u_const2`: eight sites split inline with one shared compiled pattern and their own strip
   logic; a module-level pattern counted as one definition by design.
2. Major: wrong conventions pass all four primaries: `w_hdr2` (a fact-table header split naively, so an escaped
   pipe in a header cell splits it), `w_maxsplit` (splits capped at 15), `w_ws` (strips only space and tab).
   `w_bq` (blockquote marker dropped) passes P3 and P4; C5 alone catches it. The generator emits no header
   escapes, no `>` leads, no row over 12 cells, no other whitespace: the enumeration class of review 2 again.
3. Major: the scored generator emits open-form rows, which the ruling makes exploratory. At the frozen seed
   none reaches a reader that returns the cell; at seeds 1 to 8 the corrected reference shows 3, 3, 4, 2, 1, 3,
   1, 2 corrected mismatches, all rows ending in an escaped pipe. The reference's 0 rests on the seed.
4. Minor: no valid refactor was rejected (7 built), but 6 of 7 are P1 AMBIGUOUS; with a1, 7 of 8.
5. Minor: at the frozen seed the baseline raises on 71% of `dashboard.studies` inputs, 40% of `fact.facts`, 41%
   of `fact.references`, 37% of `dashboard.order`; a raise is compared by exception class name only.
6. The record's counts, the sampled matrix rows and the terminal-form scan reproduce.

Read: static reading bounded to recognised split forms cannot separate "one shared implementation" from a
shared entry point that dispatches, or from a splitter written in an unrecognised form; widening the forms is
the enumeration the ruling set out to avoid. P1 and P2 as built are not a valid consolidation measure. The
behaviour predicates reject every wrong tree of the earlier sets and still miss new conventions. Under the
stopping rule no further instrument work is done without a new ruling.

## Amendment 3: adjudicated structure, automated behaviour (not reviewed)

Ruling (Hamm 2026-11-16): stop the amendment 2 instrument; keep T2 in the pilot; remove P1 and P2 as automated
primaries; judge structural consolidation by independent blind adjudication of every T2 tree; keep P3, P4 and
C5 automated, subject to validation; open-form rows leave the scored contract and stay exploratory; add the
missing adversarial cases to the generator; T1, T3 and T4 unchanged. Stop condition: if adjudication cannot
reliably separate the controls, T2 leaves the executable pilot. This authorises specification and validation,
not execution.

| Measure | Amendment 2 | Amendment 3 |
|---|---|---|
| Consolidation and removal | P1, P2 from `t2_structure.py`, primaries | S: adjudicated against `predicates/t2_structure_rubric.md`, PASS, FAIL or AMBIGUOUS, recorded in the ledger. `t2_structure.py` prints D1 and D2, diagnostics, unscored, shown to no adjudicator |
| Behaviour | P3 (generator revision 1), P4 | P3 (generator revision 2), P4 |
| Constraints | C1 to C5 | unchanged |
| Summary line | `PRIMARY k/4 AMBIGUOUS a CONSTRAINTS j/5` | `PRIMARY automated k/2 CONSTRAINTS j/5 STRUCTURE adjudicated` |

Acceptance (`accept/`), the 30 files, the 56-test file, the cap and the timeout are unchanged.

### Structural adjudication

Rubric: `predicates/t2_structure_rubric.md`, with the anchor verdicts of 23 control trees
(`adjudication_key.txt`, `build_adjudication_set.py`), committed at 052a37d8 before any adjudicator was
dispatched. It asks whether one effective body of delimiter logic serves all eight sites with the redundant
ones removed (S1 to S3), judged on which logic produces the cells a reader uses, with six FAIL anchors (a
shared entry point that dispatches to per-site logic is F3) and PASS anchors.

Protocol for an arm-produced T2 tree (Hamm 2026-11-16, adopted; supersedes the general AMBIGUOUS procedure for
T2 arm-tree disagreement only):
1. Two independent adjudicators judge the tree against the frozen rubric, with no access to each other's
   verdict, to other arm trees, to the arm label or to any automated result.
2. Agreement on PASS or FAIL is the structural verdict.
3. Disagreement, or either UNRESOLVED, is AMBIGUOUS.
4. The lead approves the ledger entry and verifies procedure; the lead does not break a tie or override.
5. Kept: both reports, the tree SHA, the evidence, the automated observations as printed.
AMBIGUOUS is its own outcome: never a pass, a fail or an excluded observation. Its frequency and denominator
are reported, and no ambiguous tree is dropped from a rate. The rubric is not edited after an arm output is
seen.

Validation on the controls (`adjudication/`: `packet.md`, both reports as returned, `agreement.txt`;
`score_adjudication.py`): 14 trees anchored PASS (the corrected reference, v1 to v3, a1, review 3's seven valid
trees, and two trees with wrong behaviour and one shared splitter) and 9 anchored FAIL (baseline, u1 to u3,
`pos_inline`, and review 3's `u_disp`, `u_hidden_call`, `u_const2`, `u_allhidden`), under shuffled labels.

| Adjudicator | Agreement with anchors | PASS | FAIL | UNRESOLVED |
|---|---|---|---|---|
| A | 23 of 23 | 14 | 9 | 0 |
| B | 23 of 23 | 14 | 9 | 0 |

A against B: 23 of 23, Cohen's kappa 1.0. The three trees amendment 2's checker accepted are all FAIL; the two
wrong-behaviour trees pass on structure. A ran a probe row in 15 trees; B judged from diffs alone.

Limits, as they happened and not repaired:
- Both adjudicators are one model family (Sonnet), the family of reviews 2 and 3.
- Both compared trees with each other (diffs against k01, hashes of diffs), which the rubric's procedure
  forbids. They were not fully blind to the set. Several controls share one wiring, so the set was easier than
  a single candidate is.
- Both named the same two cases as least sure: `u_disp` (every tagged call reaches one body and a second
  splitter stays live as the default branch; failed on S3 and F3) and v1 (two entry functions over one shared
  pattern; passed on the PASS anchor, close to F5). They stay in the set as adversarial anchors.
- The PASS anchors of review 3's seven valid trees rest on that reviewer's declaration.
- No arm-produced tree has been adjudicated: 23 of 23 on built controls is not evidence for unseen trees.
- The controls were not rerun to improve the score.

### Generator revision 2 (`predicates/t2_differential.py`)

Changes (worker packet `packet_generator_r2.md`; the wide-table family was added by the orchestrator after the
worker's matrix):
- Terminal escaped pipe: any input in which the header or the data row ends, after strip, in `\|` (open) or
  `\||` (tight) is exploratory for every reader; both forms are generated (about 3% each of corrected inputs).
- New scored families: header escape (corrected mode), blockquote lead (`> `, `>`, `> > ` on every table
  line), long row (4 to 20 extra cells), other whitespace as padding (U+00A0, U+2003, `\x0b`, `\f`), wide
  table (header, separator and row all gain 13 to 20 cells).

Matrix (`matrix6.txt`, run by the orchestrator with `matrix6_run.py`, three runs at a time under the suite
lock; 43 trees, seeds 2026111600, 1, 2, 3, 4; 215 runs, all rc 0, no WARN; baseline and corrected-reference
`git status` hashes equal before and after). The worker's matrix without the wide-table family is
`differential_r2_controls_worker.txt`.

| Trees | Expectation | Scored mismatches over the five seeds | Met |
|---|---|---|---|
| baseline against itself | preserved 0 | preserved 0; corrected 466 to 512 | yes |
| 19 behaviour-correct: pos2, v1 to v3, a1, u1 to u3, review 3's seven valid and four unconsolidated trees | 0 at every seed | 0 | 19 of 19 |
| pos, M10 to M13 | more than 0 at every seed | 304 to 765 | 5 of 5 |
| M1 to M9 | more than 0 at every seed | 529 to 1463 | 9 of 9 |
| `s_tab`, `s_hdr`, `s_led`, `s_ledsingle` | more than 0 at every seed | 18 to 35, 2 to 8, 27 to 32, 10 to 24 | 4 of 4 |
| t1 (drops a cell-final escaped pipe) | more than 0 at every seed | 6 to 11 | yes |
| `w_maxsplit`, `w_ws`, `w_bq` (review 3) | more than 0 at every seed | 38 to 57, 143 to 178, 23 to 33 | 3 of 3 |
| `w_hdr2` (review 3) | none set | 0 | see below |

The corrected reference is 0 at every seed: no scored input ends in an escaped pipe (worker's checker: 0 at
each seed), so its result no longer rests on the frozen seed.

Specific failure found and repaired: in the worker's matrix `w_maxsplit` (splits capped at 15) showed 0 at all
five seeds. The cap shows only when a whole table is wide; the long-row family widened the data row alone
(`survivor_probe.py`, `survivor_probe.txt`: 1 of 42 probes differs, a wide table at `table_data_rows`). The
wide-table family rejects it at every seed and leaves the 19 correct trees at 0.

`w_hdr2` (the fact-table header split naively): 0 at every seed, and 0 of 42 targeted probes differ from the
oracle (an escaped pipe at the start, middle and end of each header cell of the three fact readers, an extra
header cell, a wide table). The readers match header names exactly, so a header holding an escaped pipe is
refused either way; review 3 saw the difference through the private `_all_tables`. Not observed at a public
entry point (inferred from the probes, not proven). It is a second, naive split left in a reader: a question
of structure (F1), not shown to be one of behaviour. It was not in the adjudication set.

Readings of the worker kept: a blockquoted row stays scored; 4 to 20 extra cells, so only part of the long
rows exceed 15 delimiters; the normalisation maps an escaped and a bare pipe to one character (review 3, Q3c:
it accepts kept and dropped backslashes and penalised no correct tree).

Amended predicates on two trees after the change: pos2 `PRIMARY automated 2/2 CONSTRAINTS 5/5`, D1 and D2
PASS; `u_disp` `PRIMARY automated 2/2 CONSTRAINTS 5/5` (its structure is the adjudicators' FAIL). The 19-tree
and 13-tree matrices of amendment 2 were not rerun whole under the amended script; P4 and C1 to C5 are
unchanged code, P3 is covered by `matrix6.txt`.

### Preregistration consequence

A material amendment, not a repair inside the frozen design. The original T2 instrument failed (false
positives and false negatives in the table of "Amendment 2", review 3's STOP). T2's consolidation is now a
judgement by two adjudicators with an AMBIGUOUS outcome, and its behaviour a generated differential test that
did not exist when `PREREG.md` was frozen. T2 as amended is not measured under the original preregistration:
its result is reported as amended, beside T1, T3 and T4, with this limitation stated, and no claim treats the
four tasks as one preregistered instrument. `PREREG.md`'s evaluator, thresholds, cap and adjudication rules for
defects are untouched.

### Harness incident (open, the harness keeper's)

One enforcement defect, two pieces of evidence, 2026-11-16: (1) the orchestrator ran a stray `python -` inside
a compound shell command; it read empty stdin, did nothing and was stopped. (2) The guard hook that blocks
`python -` standalone did not block it there. A worker in this pilot reported one empty `python -c` of its own.
Repair is the harness keeper's, with a regression test: the forbidden forms are refused standalone and inside
compound commands, and permitted commands still pass. No pilot-side workaround; the harness was not modified.
Not yet delivered to the keeper: the jchat hub and relay did not answer on 2026-11-16 (two attempts).

### Review 4 of amendment 3: REVISE (2026-11-16)

Report: `../review/t2_amendment_reviewer4.md`; its differential runs: `review4_runs.txt`; its four trees are
in the session scratch directory (`rev4/trees/`), not in this record. Not STOP: the reviewer found no evidence
that adjudication fails on the 23 controls. Nothing below is repaired; each needs a ruling or a repair and
re-verification before freeze.

| id | Finding | Checked by the orchestrator |
|---|---|---|
| F1 | Three wrong conventions score 0 at seeds 2026111600 and 7: any backslash escapes and is dropped (`w_bsall`), internal whitespace runs collapsed (`w_collapse`), at most two escapes honoured per row (`w_cap2`). The generator has no lone backslash, no row with more than two escapes, no whitespace run inside a cell | `review4_runs.txt`: 0 and 0 for each at both seeds; the preserved mode refuses any backslash (generator, "backslash in a preserved input") |
| F2 | `w_hdr2` differs at a public entry point, `build_fact_graph.routing_targets` (a header cell holding a backticked name with an escaped pipe): the statement in "Generator revision 2", not observed at a public entry point, is withdrawn. `_all_tables` has six public consumers and the generator adapts three | `routing_targets` calls `_all_tables` (baseline `build_fact_graph.py:3205`), six call sites read; the probe itself not rerun (the reviewer deleted its script) |
| F3 | Rubric: FAIL anchors, PASS anchors and S1 to S3 have no precedence; S1 to S3 read PASS for `u_const2`, anchored FAIL; v1 sits between a PASS anchor and F5 | both adjudicators' "least sure" notes only |
| F4 | Undecided and without a control: all eight sites on the shared splitter, an old private splitter left defined and uncalled (S3 "live" against F6 "reachable") | not rechecked |
| F5 | S3 read literally fails every tree: `docs_form_gate.py:323` splits a line on a spaced pipe in a listed file, is none of the eight sites, and the rubric does not exclude it | line read at the baseline |
| F6 | The validation is not the deployed procedure: adjudicators compared trees; six of nine FAIL anchors are easy; one model family. Asks a second validation: one tree per fresh adjudicator, at least eight trees with the hard cases and new architectures, UNRESOLVED rate reported | limits recorded above; second validation not run |
| F7 | Blinding of an arm tree (paths, authors, extra files) and how AMBIGUOUS enters the efficiency measure are unspecified | absent from `PACKETS.md` (read) |
| F8 | The whitespace-padding family scores `str.strip()` semantics that no spec states; a refactor using `strip(" ")` would be rejected | no spec search in this record |
| F9 | No document with two tables, a blank line inside a table or text between tables | not rechecked |
| F10 | The headline and ruling text say "independent blind"; only the limits say otherwise | status paragraph of this file corrected |

Undecided architectures in the reviewer's reading of the rubric (none built): per-site flags changing escape
handling in one body; a lambda per module over one shared pattern; a state machine with `str.split` kept for
the separator row; the uncalled old helper (F4); the untouched `docs_form_gate.py:323` (F5).

### Final repair cycle (Hamm 2026-11-16): rulings reconciled with the task contract

Ruling: review 4 is REVISE; one final bounded repair cycle; the next review is a terminal gate (a new material
REVISE ends T2 for this pilot). STOP T2 when a known-invalid structure is accepted, a known-valid one is
rejected, material rubric ambiguity remains, the deployed adjudication cannot separate valid from invalid
trees, or another material defect needs a wider repair. The 23-tree results and all earlier verdicts stay as
recorded. Nothing in the instrument is edited before the rows below are final.

Contract read: `PACKETS.md`, TASK-t2 ("The 8 are 5 function definitions and 3 inline splits; after the change
`scripts/` has one cell splitter, it honours escaped pipes, and every former site uses it"; "behaviour is
kept: the gate's outputs and the tracked tables it writes stay byte-equal") and the todo item's check ("one
`cells()`"). Baseline scan: `contract_scan.py`, `contract_scan.txt` (5189 table-like tracked lines, 145 files).

| Finding | Hamm's proposed ruling | Against the contract | State |
|---|---|---|---|
| F3 precedence | validity requirements over illustrative anchors | no conflict | final |
| F3 `u_const2` | resolve against the contract, not the anchor | Nine split calls stay at the sites (`PIPE.split` in six files) and share a compiled pattern: no site "uses" a splitter and `scripts/` has no "one `cells()`". FAIL by the contract | final: FAIL, because sites split for themselves |
| F3 v1 (two entry functions; ruled below: FAIL) | not ruled | `table_cells.py` has `padded_cells` and `inner_cells`, each calling `_PIPE.split` itself and differing in outer-pipe handling: the same sharing as `u_const2`, in two functions that every site calls. "One cell splitter" read as one callable makes it FAIL; the rubric's PASS anchor 3 and the adjudication key say PASS | CONTRADICTION, returned to Hamm |
| F4 unused helper | qualifies; a cleanup defect, not several parsers | "after the change `scripts/` has one cell splitter" and the redesign ruling's "redundant implementations removed" read literally fail a tree that keeps a second, uncalled definition | CONTRADICTION, returned to Hamm |
| F5 ninth split | adjudicate the eight designated sites only | The contract counts eight (five definitions, three inline). `docs_form_gate.py:323` (`cited_works_removed`) cuts a row once at the first spaced pipe to drop a citation cell; it is none of the eight. Out of the adjudication whether a tree leaves it or routes it | final |
| F8 whitespace | score `str.strip()` equivalence only with a specification | 0 of 5189 tracked table-like lines hold whitespace other than space and tab; no specification found (docs grep; inferred absent). The contract's kept behaviour does not reach it | final: the family moves to exploratory; `w_ws` is then no scored negative |

Scope ruling on the two contradictions (Hamm 2026-11-16): option 3, literal. The contract requires exactly one
cell-splitter implementation in `scripts/`, all eight designated sites using it, the redundant splitter
implementations removed. Count implementations that perform cell splitting, not functions on the call path; a
wrapper that delegates is not a splitter. Two entry functions over one shared core pass when neither splits;
two functions each applying a shared pattern fail; an uncalled legacy splitter fails (this supersedes the
proposed F4 ruling). Structure and behaviour stay separately scored.

A material rubric clarification. Effect on earlier positive controls: v1 (anchored PASS in the 23-tree set,
PASS from both adjudicators) is FAIL under the literal reading, and so is any tree that keeps an uncalled
former splitter. The 23-tree key, reports and agreement stay as recorded; the revised classification lives
only in `validation2_controls.md` (tree m1 is the v1 class, built anew).

Written before any repair or validation (this commit):
- `predicates/t2_structure_rubric_r2.md`: criteria L1 to L3 decide and the examples illustrate (F3); scope
  stated, the ninth split out either way (F5); the first rubric kept as written.
- `predicates/t2_adjudication_protocol.md`, `t2_adjudication_packet.md`, `build_adjudication_tree.py` (F7):
  isolation of a tree, one tree per fresh adjudicator, slot 2 from a second model family with one retry and a
  recorded fallback, evidence access, AMBIGUOUS as intervals on `V` and `E` and as a count over all assigned
  trees.
- `validation2_controls.md`: twelve new trees, five expected PASS and seven expected FAIL, to be built by
  agents other than the adjudicators.
- Stopping criteria of validation 2 (protocol, section 5). The orchestrator set one number Hamm did not: more
  than 2 of 12 AMBIGUOUS trees counts as "cannot reliably distinguish".
- Generator repair planned (F1, F2, F8, F9): lone backslashes in preserved rows, three to five escapes,
  whitespace runs inside cells, every public consumer of `_all_tables`, documents with two tables; the
  whitespace-padding family moves to exploratory.

Same scan, for F1: a backslash not before a pipe on 59 lines in 12 files (kept behaviour covers it: scored);
more than two escaped pipes on 0 lines (scored under "honours escaped pipes"); a run of spaces inside a cell
on 1 line (scored).

### Final repair cycle: what was done (not reviewed; for the single freeze review)

Order kept: rubric, protocol, control specifications and stopping criteria were committed (5459ea6e, protocol
change e4217e42) before any validation tree was adjudicated; the matrix expectations (`matrix7_run.py`) were
written before the run. No earlier control, verdict or acceptance result was changed.

#### Protocol change before validation (route smoke test)

The slot-2 route was run once on the earlier corrected reference, not a validation tree
(`validation2/smoke/`). Run 1 returned UNRESOLVED: the adjudicator's root was `tree/`, so `RUBRIC.md` and
`baseline/` were unreadable, and the review tier has no shell. Changed before any validation tree: the isolated
directory is the root, `build_adjudication_tree.py` writes `changes.diff`, packet and protocol say so. Run 2
returned a full report. Stated limit: slot 2 reads files and runs nothing.

#### Validation 2: the deployed protocol on twelve new trees (`validation2/`)

Trees built from written specifications (`validation2_controls.md`) by two Haiku workers, not the
adjudicators; five expected PASS (n1 to n5), seven expected FAIL (m1 to m7). Each tree went to one fresh Claude
reviewer (slot 1, all served by claude-sonnet-5-5) and one fresh Muse session (slot 2,
muse-spark-1.3-contributor), each on its own isolated copy under its own label: 24 adjudications, reports as
returned (`slot1/`, `slot2/`, `key.jsonl.txt`, `score_validation2.py`, `score.txt`).

| Against the expected verdict | PASS | FAIL | AMBIGUOUS or UNRESOLVED |
|---|---|---|---|
| Tree verdict, expected PASS (5) | 5 | 0 | 0 |
| Tree verdict, expected FAIL (7) | 0 | 7 | 0 |
| Slot 1, expected PASS / FAIL | 5 / 0 | 0 / 7 | 0 |
| Slot 2, expected PASS / FAIL | 5 / 0 | 0 / 7 | 0 |

Slot agreement 12 of 12, Cohen's kappa 1.0. AMBIGUOUS 0 of 12. No UNRESOLVED, no retry, no fallback, so no
tree is "no cross-family". Definitive verdicts 12 of 12 assigned trees.

Stopping criteria (protocol, section 5): 1 and 2 not triggered (no expected FAIL judged PASS, no expected PASS
judged FAIL); 3 not triggered (0 of 12; the threshold "more than 2 of 12" is the orchestrator's number, not
Hamm's). Criteria 4 and 5 are the orchestrator's reading, not triggered, for the reviewer to judge. On 4:
four slot-1 reports on PASS trees (labels 0b79bb95, 4b1a1322, 9b72baeb, dac65960) note that unchanged baseline
code holding a pipe (`gates/api_types.py:15`, a multi-cell regex; `obligation_diff.SPLIT`;
`stacks_closure.py:95`) is put out of scope by the scope rule's general wording and not by its one listed
example. All four reached PASS by that rule; no verdict turned on it; slot 2 raised no gap. The rubric was not
edited after the reports.

As it happened, not repaired:
- m5 as first built failed the preserved test on blockquoted rows (55 of 56). Before adjudication the
  orchestrator edited its separator-row line (blockquote strip, `None` for non-rows; 56 and 6 passed); its
  class (a site splitting for itself, L2) is unchanged. The protocol allows a rebuild before adjudication only.
- Neither slot ran code: slot 2 cannot, slot 1 did not need to. Structure was judged from the tree, the
  baseline and the diff.
- The orchestrator wrote the specifications to match the decided cases, and knows the rubric: the twelve are
  clear cases of each rule. m4 (a flag turning escape handling off for three sites) is the rubric's own
  example of several implementations in one function.
- No arm-produced tree has been adjudicated. Twelve of twelve on built controls bounds nothing for unseen
  trees; with 0 errors in 12 the exact one-sided 95% upper bound on a per-tree error rate is 22%
  (1 - 0.05^(1/12)), for trees like these twelve.
- Slot 1 is one model family, the family of every review in this record. The cross-family element is slot 2.
- v1 and the uncalled-splitter class changed class under the literal ruling; the 23-tree results are as
  recorded and are not comparable with this table.

#### Generator revision 3 (`predicates/t2_differential.py`, sha256 efa05ca3e514b050...; F1, F2, F8, F9)

Worker packet `packet_generator_r3.md` (Haiku worker; the orchestrator read the whole diff against revision 2,
189 insertions and 26 deletions, and changed nothing). Worker receipts:
`differential_r3_family_counts_worker.py/.txt`.

- Readers 13 to 17: `fact.b3_exceptions`, `fact.claim_estimators`, `fact.require_tables`, `routing.targets`
  added, so every public consumer of `_all_tables` is exercised (F2). `predicates_t2.py` `DIFF_READERS = 17`.
- New scored families (F1, F9): lone backslash (a backslash not before a pipe, both modes), multi-escape
  (three to five escaped pipes in a row or cell, corrected mode), inner whitespace (a run of spaces between two
  words of a cell, both modes), multi-table (two tables of the reader's kind in one document: prose between
  them with or without blank lines, or a blank line inside the first table and prose between; both modes).
- Whitespace padding (U+00A0, U+2003, `\x0b`, `\f`) is exploratory for every reader (F8): no specification
  states `str.strip()` semantics and 0 tracked lines hold such whitespace. `w_ws` is no longer a scored
  negative.
- Any input in which any document line ends in `\|` or `\||` is exploratory (revision 2 looked at the header
  and the data row).

#### Matrix 7 (`matrix7_run.py`, `matrix7.txt`, `matrix7_runs.jsonl.txt`; `matrix7_reconcile.py/.txt`)

59 trees (the baseline against itself, 28 behaviour-correct, 29 wrong, `w_ws`) at seeds 2026111600, 1, 2, 3,
4: 295 runs, ten at a time under the suite lock, each at most 75 s; all rc 0, no WARN, all three DIFF lines;
baseline and corrected-reference `git status` hashes equal before and after. Reconciled from the run log
alone: one row per tree and seed, no run excluded; at each seed all 59 trees saw the same input counts, equal
to what `generate()` gives (scored preserved 4685 to 4748, scored corrected 4404 to 4437, exploratory 1045 to
1107).

| Trees | Expectation (fixed before the run) | Scored mismatches over the five seeds | Met |
|---|---|---|---|
| baseline against itself | preserved 0 | preserved 0; corrected 767 to 817 | yes |
| 28 behaviour-correct: pos2, v1 to v3, a1, u1 to u3, review 3's eleven, validation 2's n1 to n5, m1, m2, m3, m5 | 0 at every seed | 0 in 140 runs | 28 of 28 |
| pos, M10 to M13 | more than 0 at every seed | 210 to 817 | 5 of 5 |
| M1 to M9 | more than 0 at every seed | 832 to 2134 | 9 of 9 |
| `s_tab`, `s_hdr`, `s_led`, `s_ledsingle` | more than 0 at every seed | 19 to 26, 7 to 16, 20 to 28, 4 to 17 | 4 of 4 |
| t1 | more than 0 at every seed | 12 to 19 | yes |
| `w_maxsplit`, `w_bq`, `w_hdr2` (review 3) | more than 0 at every seed | 47 to 60, 27 to 33, 20 to 27 | 3 of 3 |
| `w_bsall`, `w_collapse`, `w_cap2`, `w_merge1` (review 4) | more than 0 at every seed | 259 to 301, 154 to 176, 114 to 140, 232 to 308 | 4 of 4 |
| validation 2's m4, m6, m7 (escapes unhonoured at some site) | more than 0 at every seed | 157 to 168, 23 to 32, 118 to 134 | 3 of 3 |
| `w_ws` | none; reported only, outside scoring | scored 0; exploratory 224 to 262 (a correct tree: 43 to 59) | not scored |

Smallest margins: `s_ledsingle` 4 at seed 1, `s_hdr` 7 at seed 1. The worker's own runs at seeds 2026111600
and 1 give the same figures for the nine trees it ran (baseline, pos2, v2, v3, `w_bsall`, `w_collapse`,
`w_cap2`, `w_merge1`, `w_hdr2`).

#### Coverage per reader (`coverage_r3.py`, `coverage_r3.txt`)

Scored inputs per reader, mode and family at the five seeds, from `generate()`. Every reader has more than 0
scored inputs at every seed in every family scored for that mode, with one exception: inner whitespace is not
built for `docs.vocabulary`, `learning.mapping` and `routing.targets` (0 at every seed, both modes), whose
fixture cells hold no two-word cell; the generator returns that share to the existing variations. A coverage
limit, not a failed expectation (Hamm 2026-11-16). For those three readers every other scored family is
present at every seed (per reader and mode, five-seed sums: blockquote 80 to 98, lone backslash 75 to 107,
long row 70 to 87, multi-table 61 to 81, wide table 68 to 89, header escape 111 to 144, multi-escape 73 to 85,
existing variations 687 to 1050). Thin cells: inner whitespace at `state.defect` (22 preserved, 19 corrected
over five seeds), `release.table_data` (25, 46), `fact.constants` (36, 25), `learning.ledger` (35, 42); more
than 0 at every seed.

A whitespace-collapsing error confined to one of the three readers would score 0. `w_collapse` collapses in
the shared splitter and is rejected at every seed (154 to 176).

#### `w_hdr2` and the corrected reference per reader (`reader_check_r3.py/.txt`, outputs in `reader_check_r3/`)

Suite-lock exception: these 15 differential runs (five of `w_hdr2`, ten of pos2) were run by the orchestrator
directly, five at a time, outside the suite lock, which another agent's run held from 13:56Z; the 295 matrix
runs were under the lock. `w_hdr2` (the fact-table header split naively): at every seed the only reader with a scored mismatch is
`routing.targets`, corrected mode, 20, 21, 27, 20, 23 mismatches of 253 to 270 inputs; preserved 0. Its
rejection rests on one reader and one mode: without `routing.targets` it scores 0, as in revision 2 (F2).
Corrected reference pos2: 0 scored mismatches at every seed, no reader with zero inputs or all-empty baseline
results in a scored mode, and a second run at each seed is byte-equal to the first.

#### Amended predicates on four trees (`predicates_r3_controls.txt`; under the suite lock, one at a time)

`predicates_t2.py` with generator revision 3 and `DIFF_READERS = 17`, frozen seed 2026111600, all rc 0.

| Tree | D1, D2 (unscored) | P3 | P4 | Constraints | Summary line |
|---|---|---|---|---|---|
| pos2 (corrected reference) | PASS, PASS | PASS: 17 readers, 0 of 4748 preserved, 0 of 4407 corrected | PASS, 6 passed | 5/5 | `PRIMARY automated 2/2 CONSTRAINTS 5/5 STRUCTURE adjudicated` |
| baseline | FAIL, FAIL | FAIL: corrected 808 | FAIL, 6 failed | 4/5 (C4: empty change) | `PRIMARY automated 0/2 CONSTRAINTS 4/5 STRUCTURE adjudicated` |
| `w_hdr2` (wrong behaviour) | PASS, PASS | FAIL: corrected 20 | PASS, 6 passed | 5/5 | `PRIMARY automated 1/2 CONSTRAINTS 5/5 STRUCTURE adjudicated` |
| `u_const2` (correct behaviour, sites split for themselves) | PASS, PASS | PASS: 0 and 0 | PASS, 6 passed | 5/5 | `PRIMARY automated 2/2 CONSTRAINTS 5/5 STRUCTURE adjudicated` |

Read: the automated primaries are P3 and P4 only (k of 2). D1 and D2 are printed and enter no count:
`u_const2` shows D1 PASS and D2 PASS and is FAIL by the contract (table of "Final repair cycle"; anchored
FAIL in the 23-tree set), so its structure is known only from adjudication, and its automated 2/2 does not stand for a structural pass. `w_hdr2` passes the six corrected
tests and C5 and fails P3 alone. Every line ends `STRUCTURE adjudicated`; no structural verdict is computed.
P3's own figures equal the matrix's at the frozen seed. Four trees: a check of the script's semantics, not a
validation of the predicates beyond the matrix.

#### Limits of this cycle, as known

- The differential rejects the wrong conventions built so far. Each review built wrong conventions that the
  instrument of its time accepted (review 2 four, review 3 four, review 4 three); nothing shows the set is
  now closed.
- `w_hdr2` is rejected through one reader; inner whitespace is not exercised at three readers (above).
- Whitespace other than space and tab as cell padding is unscored: a tree that changes it passes P3.
- A line ending in an escaped pipe is unscored (Hamm 2026-11-16, provisional; section "Terminal escaped pipe").
- Validation 2 used clear cases written by the orchestrator, no arm-produced tree, one family in slot 1, and
  a slot 2 that reads only.
- The 23-tree validation and validation 2 use different rubrics and are not pooled.
- The control trees live outside this record (`D:/repos/_work/exp_*`, session scratch). Stored here as diffs:
  validation 2's (`validation2/trees/`), review 2's and review 3's (`review2_probes/`, `review3_probes/`),
  review 4's four against pos2 (`review4_probes/`, one file each, `scripts/md_cells.py`).
- Keeper dispatch overhead against the 30-minute cap is unmeasured.

#### Harness incident: third piece of evidence

2026-11-16, during this cycle: the orchestrator again typed a stray `python - </dev/null` inside a compound
shell command; the guard hook did not block it; it hung and was stopped; nothing was written. Same defect as
in "Harness incident". Still undelivered to the harness keeper (the jchat hub and relay returned no HTTP
answer). No pilot-side workaround; the harness was not modified.

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

Hamm 2026-11-16; the state of each item is in brackets.

1. Complete the amended predicate run on `pos2`, baseline, `w_hdr2` and `u_const2`; verify automated primary
   scoring, diagnostic-only D1/D2, constraints, and separate structural adjudication. [done 14:56Z:
   "Amended predicates on four trees", `predicates_r3_controls.txt`]
2. Preserve the complete 295-run matrix receipt, generator hash, reader coverage, frozen expectations and
   negative-control margins. [stored: "Matrix 7", "Generator revision 3", "Coverage per reader"]
3. Explicitly disclose the three readers without applicable inner-whitespace cases, the dependence of
   `w_hdr2` detection on `routing.targets`, and the absence of validation against unseen arm-produced trees.
   [stated: "Coverage per reader", "`w_hdr2` and the corrected reference per reader", "Limits of this cycle"]
4. Record the suite-lock exception and the 15 direct differential runs, distinguishing them from the locked
   matrix. [stated: "`w_hdr2` and the corrected reference per reader"]
5. Obtain the single independent freeze review. Resolve its findings under the previously adopted terminal
   stopping rule. [packet `../review/t2_freeze_review_packet.md`; not dispatched before item 1]
6. Preserve the unresolved harness-enforcement defect and undelivered keeper escalation. Do not treat it as
   closed. [open: "Harness incident", "Harness incident: third piece of evidence"]
7. Freeze only after the mandatory evidence and review gates pass. No pilot execution or keeper dispatch
   before then.
