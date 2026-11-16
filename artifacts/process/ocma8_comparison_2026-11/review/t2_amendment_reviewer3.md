STOP (stopping rule met)

The checker rejects no valid refactor I built (Q1), but it accepts unconsolidated ones with correct behaviour (Q2). Stopping rule, second clause: met.

Findings (all observed unless marked)

| Sev | Claim | Evidence | Repair |
|---|---|---|---|
| blocker | P1+P2 PASS/PASS and PRIMARY 4/4 on an unconsolidated tree: `u_disp`, a shared `split_cells(site=)` with a default regex branch, and a dict of per-site splitters called through a local variable | `predicates_t2.py trees/u_disp`: P1 PASS md_cells.split_cells, P2 PASS, P3 0/0, 6 and 56 passed, PRIMARY 4/4 (out/full_u_disp.txt) | Call through a variable, dict value or `map` is unresolved and reads as "no definition"; an unresolved call must make P1 AMBIGUOUS, not leave a PASS |
| blocker | Same for `u_hidden_call`: each of 6 modules keeps its own `.replace().translate().split(chr(1))` splitter, whose result is the one used, plus one real call to the shared function | out/full_u_hidden_call.txt: PRIMARY 4/4, 5/5 | Forms outside a to c (`translate`, `chr(124)`, `partition`, `findall`, `csv`) are invisible; P1 PASS needs every function on the anchors' paths with a string op to be accounted for |
| blocker (arguable) | `u_const2`: eight sites each split inline with one shared compiled `PIPE`, own strip logic per site. P1 and P2 PASS, behaviour correct (P3 0/0, 6, 56) | out/u_const2/structure.txt, diff.txt. AMENDMENT states a module-level pattern is one definition, so this is by design, but it is eight independent splitters | Identity should be a function, not a pattern |
| major | Wrong conventions pass all four primaries: `w_hdr2` (fact-table header split naively via `chr(124)`; escaped pipe in a header cell splits it, `_all_tables` returns `['B \\','x']`), `w_maxsplit` (maxsplit=15), `w_ws` (`strip(" \t")` not `strip()`) | w_hdr2: PRIMARY 4/4 (full run). w_maxsplit, w_ws: P3 0/0, 6 and 56 pass (out/*/diff.txt); structure PASS/PASS. `w_bq` (blockquote `>` dropped in `_table_cells`) passes P3 0/0 and P4, caught only by C5 (1 failed): generator has no `>` lead, no header escapes, no rows over 12 cells, no non-space/tab whitespace | Differential generator must add header escapes, blockquote leads, wide rows, other whitespace. Same enumeration class review 2 warned about |
| major | Frozen seed hides the open terminal form that the ruling says is unscored. The generator emits open rows at readers returning the last cell; pos2 fails them at all 8 other seeds I ran: corrected mismatches 3,3,4,2,1,3,1,2 (seeds 1 to 8); all 19 mismatching rows end in `\|`+whitespace (`out/seedscan` run) | `t2_differential.py --seed N` on pos2 vs base; out/seed_*.txt | Exclude open and tight rows at observing readers from the scored bucket, not by seed |
| minor | AMBIGUOUS is the common case: of 7 valid trees, 6 are P1 AMBIGUOUS (class, generator/finditer, partial, map, char-scan with a `==` "|" trim helper, renamed anchors in a subpackage), 1 PASS/PASS. With the earlier a1, 7 of 8 | structure outputs, out/*/structure.txt | Adjudication route unowned (Hamm's); load is high |
| minor | Reader vacuity at the frozen seed: raised share of baseline results 71% (dashboard.studies), 43% (fact.facts), 41% (fact.references), 37% (dashboard.order); dashboard.deferred non-empty 31/300 preserved. A raise equals a raise by class name only | READER lines, out/v_cls/diff_full.txt | Report only |
| minor | Record: "13 readers", "8 sites, 12 anchors", 331/328 s, 56 passed, matrix4 lines for base/pos2/v1/u1/s_tab all reproduce. No unsupported count found. FP/FN table is silent on the classes above (new, not in sections Why/Review 1/Review 2) | out/full_*.txt; accept_pair_timing.txt | Add after repair |

Q3: (a) no false rejection on my valid trees: P3 0 mismatches on all 7 (a first `v_gen` of mine had a bug; P3 caught it, 20 mismatches, P4 and C5 did not; rebuilt). (c) the corrected oracle and its normalisation (`\|`, bare `|`, broken bar all to one character) accept kept-backslash and dropped-backslash forms alike, and header escapes are not generated; it did not penalise a correct tree here. It scores open rows, where it favours a correct parser over the references (see major above).

Q4: record states exactly spaced=scored, open/tight=exploratory known oracle failures, not "invalid"/"correct". `terminal_cell_check.py` judges only `fact.facts` and `fact.references` (observed=2 scored, 4 exploratory). t1: spaced WRONG at both, P3 corrected mismatches 10 (rejected by P3; structure PASS/PASS). `terminal_form_scan.py` base: 5067 lines, 215 files, 7 escaped, spaced=0 open=0 tight=0. Confirmed.

Q5: base 0/4 4/5, pos2 4/4 5/5, v1 4/4 5/5, u1 3/4 5/5 (P1 FAIL), s_tab 3/4 (P3 13 corrected) match matrix4. `git status --porcelain | sha256sum` equal before and after for base (e3b0c442), pos2 (9d2c9039), v1, u1, s_tab.

Trees (in `rev_t2c/trees/`, diffs in `rev_t2c/diffs/`, builders `build.py build2.py build3.py`, all with 6/56 passed and P3 0/0 unless noted)
- v_cls class+subpackage: AMBIGUOUS/PASS. v_gen finditer generator: AMBIGUOUS/PASS. v_partial partial: AMBIGUOUS/PASS. v_map map(): AMBIGUOUS/PASS. v_split2 two-step, subpackage, 3 anchors renamed: AMBIGUOUS/PASS. v_scan char scan: AMBIGUOUS/PASS. v_wrap sentinel, baseline wrappers: PASS/PASS.
- u_disp, u_hidden_call, u_const2: PASS/PASS (blockers). u_allhidden (8 partition loops): AMBIGUOUS/PASS.
- w_hdr, w_hdr2, w_maxsplit, w_ws, w_bq: wrong behaviour as above.
- `trees_flawed/` u_const, u_dead_shared: my regex mistakes, wrong behaviour, P3 caught (526 to 573 mismatches); not counted.

Not checked: the 30-file suite on my trees; full predicates on every tree (structure+differential+6+56 only, full runs for 4 of mine); a splitter outside scripts/; FP/FN table completeness beyond reading; the 8 seeds ran preserved mode only as DIFF lines (0 mismatches each).

Model: claude-sonnet-5-5
