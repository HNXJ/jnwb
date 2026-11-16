VERDICT: REVISE

Not STOP. The 23 controls were separated, and I found no evidence that adjudication fails on them. The instrument has defects in three places. The rubric leaves common architectures undecided or self-contradictory. The validation condition differs from the deployment condition. The generator misses three wrong conventions I built, and it misses one public entry point where `w_hdr2` differs. Each defect is repairable, and everything below must be re-verified after the repair, before freeze.

## 1. Findings

Marks: (o) = observed by me, (i) = inferred.

| id | sev | Q | finding | evidence | required change |
|---|---|---|---|---|---|
| F1 | major | 5b | Three wrong conventions score 0 scored mismatches at the frozen seed and at seed 7. Cause: preserved mode forbids any backslash (`t2_differential_r2.py:297-298`), and corrected mode allows backslashes only before a pipe, at most 2 per row (`:289`, `insert_escapes` k in 1..2). A convention that drops or alters a lone backslash is therefore never exercised. A cap of 2 honoured escapes, and any whitespace-run collapse, are never exercised either. Real tables do hold lone backslashes: 59 table lines in 12 tracked `.md` files at baseline (Grep `^\s*\|.*\\[^|\\]`). (o) | Trees `rev4/trees/w_bsall`, `w_collapse`, `w_cap2`; `rev4/runs.txt`; probe `rev4/probe_surv.py` on `_all_tables`, which shows each differs from pos2 and the baseline (`C:\dir` becomes `C:dir`; `two  spaces` becomes `two spaces`; a 3-escape row splits at the 3rd) | Add a preserved-mode family with lone backslashes (`C:\dir`, `\d`, a backslash before a space-pipe). Add rows with 3 to 5 escapes. Add cells with internal whitespace runs. Rerun the 43-tree matrix, plus my 4 trees as new negatives. |
| F2 | major | 5c, 6 | `w_hdr2` is observable at a public entry point, so "no difference at any public entry point" (AMENDMENT.md:31, 493-497) is false. `build_fact_graph.routing_targets` reads backticked names from header cells of `_all_tables`. Probe header `` | `jnwb.fx\|y` | Note | `` with rows `a`, `b`: pos2 returns ["fx.a","fx.b"], w_hdr2 returns []. The oracle (baseline on the `\¦` row) gives ["fx.a","fx.b"] by the same `_JNWB_NAME` match (i). `_all_tables` has 6 public consumers (`read_facts`, `fact_names` at :310, `read_constants`, `read_b3_exceptions` at :339, `read_claim_estimators` at :2273, `routing_targets` at :3202). The generator adapts only 3. (o) | `rev4/probe_hdr.py`; pos2 vs `rev_t2c/trees/w_hdr2`; `build_fact_graph.py:225-262, 310, 339, 2273, 3190-3210` | Add adapters for the 3 missing consumers and a header-escape family that reaches them. Strike the claim and the "structure, not behaviour" reading of `w_hdr2`. |
| F3 | major | 2, 1 | Anchors contradict each other and the criteria, and there is no precedence rule. F5 FAILs "own handling around it that changes where cells begin and end". The row-shape definition lets a site keep "stripping outer pipes, dropping the outer empty segments". PASS anchor 3 allows two entry functions whose `[1:-1]` and strip differ. S1 to S3 read PASS for `u_const2` (one shared pattern, row-shape kept per site), but its anchor is FAIL. The adjudicators decided it only by following F1/F5. Both named v1 (k08) "F5-adjacent". (o) | rubric lines 28-36 vs 51-53 vs 62-63; adjudicator_A.md "Least sure" k08; adjudicator_B.md k08 | State that FAIL anchors override S1 to S3. Define F5 by a count (a `split` call in each site's own body = F1). Rewrite the PASS anchor so the two entry functions sit inside one module, calling one core. |
| F4 | major | 1, 2 | The common case is undecided and has no control. All eight sites use the shared splitter, but an old private splitter (`_cells`, `_table_cells`) stays defined and uncalled. S3 says "live code that a reader could call"; F6 says "still reachable"; neither defines the term. Two careful readers split here. None of the 23 controls is this case (A lists dead code only in non-splitter helpers; B notes a dead `_study_rows` stub with no delimiter logic). (o for the controls, i for the disagreement) | rubric S3, F6; adjudicator reports | Rule it: dead but defined = PASS or FAIL. Add one control each way, committed before any arm output. |
| F5 | major | 2 | S3 says "no other delimiter logic for table rows ... in the six files". `docs_form_gate.py:323` is a table-row split, `line.split(" | ", 1)` in `cited_works_removed`. It is in a listed file and is not one of the eight sites. The rubric never excludes it; only AMENDMENT.md:533 mentions it. Neither adjudicator report mentions it, so it was ignored silently. Read literally, S3 FAILs every tree, including pos2. (o for the line and the reports; i for "ignored") | `exp_prereq/t2/base/scripts/docs_form_gate.py:312-324`; Grep of both reports: 0 hits | Name this site as out of scope in the rubric before any arm output. |
| F6 | major | 3 | The validation is not the deployed procedure. Both adjudicators diffed trees against each other (A against k01, k02, k03, k06, k11, k13, k14, k16, k21; B used md5 of diffs and diffs against k01). Rubric procedure step 4 forbids this, and the arm-tree protocol gives each adjudicator one tree. Of the 9 FAIL anchors, 6 are easy (baseline k09 is unchanged and visibly the baseline; u3, pos_inline, u1, u2, u_allhidden are copies or inline splits). Only `u_disp`, `u_hidden_call` and `u_const2` are hard. Kappa 1.0 for two readers of one model family is not independent evidence. 23 of 23 does not show that unseen trees separate. (o) | adjudicator_A.md and adjudicator_B.md "Commands" paragraphs; AMENDMENT.md:447-457; key anchors | Run a second validation in the deployed condition: one tree per fresh adjudicator, no peer trees, at least 8 trees including the 3 hard FAILs, the F3/F4 cases, and 4 or more new architectures from section 3. Report the unresolved rate. If the rate is high, the stop condition applies. |
| F7 | major | 4 | The blinding of arm trees is unspecified. `adjudication/packet.md` covers the validation set only, and builds the trees as scripts-only clones. PACKETS.md ("T2 structure") says nothing on how an arm worktree becomes a blind tree. Leaks are plausible: worktree path, commit authors, extra files (notes, tests) at arm B, which has 3 workers and a keeper, and diff size. Also, how AMBIGUOUS enters `E = V/C` (PREREG:13) is not defined; if AMBIGUOUS counts as not-pass, an arm with more elaborate architectures is penalised. (i) | PACKETS.md:37-46; AMENDMENT.md:422-432 | Write the sanitiser (copy only the changed `scripts/` files, no VCS metadata, label shuffle by an agent that knows no arm) and the AMBIGUOUS scoring rule before freeze. Run the sanitiser on one arm-like tree. |
| F8 | minor | 5a | The scored whitespace family (U+00A0, U+2003, `\x0b`, `\f` as padding) tests `str.strip()` semantics. The record shows no spec search for it, unlike the terminal form. The Amendment 2 ruling (AMENDMENT.md:220-221) says undocumented behaviour is exploratory. `w_ws` is rejected only by this family. `\x0b` and `\f` also break lines under `splitlines()` in `_all_tables`. A valid refactor using `strip(" ")` would be rejected. (o for the ruling and the generator; i for the effect) | `t2_differential_r2.py:46, 246-254`; AMENDMENT.md:220 | Document the spec, or move the family to exploratory and rule on it. |
| F9 | minor | 7 | Documents with two tables, blank lines inside a table, or non-table lines between tables are never generated. Table boundaries are consumed by the `_all_tables` and `table_data_rows` readers, which are split sites. A consolidating refactor that changes boundary handling is untested by P3 (i, from reading `make_input`: one table per doc). | `t2_differential_r2.py:285` | Add a multi-table family, or state that C5 and the 30 files carry it. |
| F10 | minor | 6 | AMENDMENT.md calls the adjudication "independent blind". The limits section admits "not fully blind to the set"; the headline row and the ruling text do not repeat it. (o) | AMENDMENT.md:30, 398-399 vs 449-451 | Say "not blind to the validation set" in the headline row. |

## 2. Q1 table (rubric against unseen architectures)

I built none of these as trees. The four trees I built are for Q5. All verdicts are my reading of the rubric text (i).

| architecture | rubric decides | by which criterion | decision right | disagreement risk | built |
|---|---|---|---|---|---|
| a. class with per-site subclasses overriding only row-shape hooks over one `_split` | yes | S1 (row-shape params allowed) | yes, PASS | medium: where "hook" ends and "delimiter logic" begins | no |
| b. same, subclasses override the split body (identical or different) | yes | F3 if different; F2 if identical copies | yes, FAIL | low | no |
| c. registry of callables keyed by site, values distinct | yes | F3 | yes | low | no |
| d. registry whose values are all one function | partly | PASS anchor 1 (alias) against F3 "dispatches"; no rule | PASS is right | medium | no |
| e. one splitter whose flags change escape handling or cell boundaries per old site | no | S1 allows only row-shape flags; F3 says "separate", but this is one body | unclear; FAIL on S1 intent | high | no |
| f. shared generator, one site post-processes into a second `|` split | yes | F1 if it re-splits on `|`; PASS if the split is on cell content | yes, but depends on how "delimiter logic" is read | medium | no |
| g. compiled regex everywhere, loop repeated | yes | F1/F5 | FAIL fits the anchor; F3 shows the contradiction | medium: see F3 | no |
| g2. each module defines `_cells = lambda l: PAT.split(l.strip().strip("|"))` over one shared pattern | no | thin wrapper (PASS) against F2/F5 | undecided | high | no |
| h. re-export through `__init__`, or the splitter in the `jnwb` package | yes | PASS anchor 1 ("any module or subpackage") | yes | low | no |
| i. decorator pre-splitting lines for the readers | partly | S2 ("obtains its cells") needs tracing through the decorator | PASS if one body | medium: the tracing may end UNRESOLVED | no |
| j. C-style state machine in one module, `str.split` kept for the separator row only | no | F1 ("any site still splits for itself") against "table rows" (a separator is a row; is it a site?) | undecided | high | no |
| k. all 8 sites on the shared splitter, old private helper left defined and uncalled | no | S3 "live" against F6 "reachable"; no control | undecided (F4) | high | no |
| l. shared splitter, `docs_form_gate.py:323` untouched | no | S3 literal reading FAILs it | PASS is right | high (F5) | no |

Rubric undecided or wrongly decided: e, g2, j, k, l, and d (partly). Rubric decisions at medium risk: a, f, g, i.

## 3. Q2 notes (rubric text)

- No stated precedence between FAIL anchors, PASS anchors and S1 to S3 (F3).
- "Effective" is defined per reader, "on the rows it reads". A branch reached only by `site=None` is excluded, so `u_disp` PASSes S1 and was failed on S3's "live code". Adjudicator A said F3 "is not literally met" for it. The F3 anchor against a single body with a live fallback is a real conflict. It was settled only by the two adjudicators choosing S3.
- "Site": the table uses "site" for the eight splitter definitions. S2 uses "reader". The `_all_tables` consumers outside the table (`routing_targets`, `read_b3_exceptions`) are neither listed nor excluded.
- "Redundant" is never defined; S3 uses "removed" and "redundancy".
- The criterion "wrappers kept under baseline names are fine when they delegate" admits a dispatching wrapper (see F3, `u_disp`).
- PASS anchor 3 against F5: see F3.
- Trivially satisfied: S2 can be met by an alias that is never used (the sites import it but call a local helper). Checking calls is the procedure's job, not the criterion's.

## 4. Q3

- 23/23 and kappa 1.0 hold as stated in `agreement.txt` (o). They do not support "adjudication separates the controls" beyond the 3 hard FAIL controls and 2 hard PASS controls (F6).
- The limits in AMENDMENT.md:447-457 are accurate and not softened (o). They omit the deployment-condition difference (F6), that the baseline control is unchanged and trivially identified, and that the review-3 PASS trees were built by the person who built `u_disp` (the PASS anchors rest on one declarer, which the limits do name).
- The stop condition is not met on this evidence. It is also not shown to be avoided. F6 supplies the test that decides it.

## 5. Q4

- AMBIGUOUS frequency can differ by arm: arm B is likelier to produce wrapper-heavy trees, and two adjudicators disagree more on those. The protocol keeps AMBIGUOUS as its own outcome (good), but the scoring rule is missing (F7).
- Gaming: an arm cannot see the rubric (PACKETS: hidden). The adjudicators can run code on the tree, which gives them behaviour, not the arm (i).
- The lead approves procedure and cannot break a tie (as written). This is sound.
- D1/D2 and P3 output are withheld by the packet text. This is sound for the validation set (o); the arm procedure is silent on the sanitiser (F7).

## 6. Q5 table (generator revision 2, wrong conventions)

Scored mismatches are preserved + corrected from `DIFF` lines (o). Seeds: 2026111600 and 7. Each tree is pos2 with only `scripts/md_cells.py` replaced; paths are under `rev4/trees/`.

| wrong convention | built | seed 2026111600 | seed 7 |
|---|---|---|---|
| any backslash escapes the next char and is dropped (lone `\x` becomes `x`) | yes (`w_bsall`) | 0 + 0 | 0 + 0 |
| internal whitespace runs collapsed to one space | yes (`w_collapse`) | 0 + 0 | 0 + 0 |
| at most 2 escaped pipes honoured per row | yes (`w_cap2`) | 0 + 0 | 0 + 0 |
| split on every pipe, then re-join a cell ending in `\` once (not repeated) | yes (`w_merge1`) | 0 + 128 | 0 + 129 |
| separator-row recogniser accepting `|:-:|` or `|-|` | no | n/a | n/a |
| escape honoured only outside code spans | no | n/a | n/a |
| CRLF: `rstrip("\n")` instead of `strip()` for string readers | no | n/a | n/a |
| two tables in one document | no | n/a | n/a |
| NFKC-normalised cell text | no | n/a | n/a |

Three survivors are wrong against the baseline at a public reader chain (probe `_all_tables`, `rev4/probe_surv.py`). `w_merge1` is caught. The not-built rows are my proposals and are unrun (i).

- 5a: I found no scored input whose correct output is contested except the whitespace family (F8). The `||` leads and trails are baseline behaviour by the ruling.
- 5c: see F2.
- 5d: the oracle forgives backslash-kept versus backslash-dropped. That is intended, and the effect is that `w_bsall` also passes its escaped-pipe inputs. It forgives nothing else I could build. Normalisation is global (keys, values), so a tree that moves an escape to a different cell is still caught by the cell lists differing (i).

## 7. Q6 numbers checked

| quoted value | source | match |
|---|---|---|
| baseline vs itself: preserved 0, corrected 466 to 512 | `matrix6.txt` base rows (0/3778 ... 504, 466, 512, 501, 472) | yes |
| 19 behaviour-correct trees, 0 at every seed | `matrix6.txt` per-seed rows (pos2, v1, v2, v3, a1, u1, u2, u3 + 11 review-3 rows) | yes |
| pos, M10 to M13: more than 0, range 304 to 765 | `matrix6.txt` (min m10 s4 182+122; max pos s2 435+330) | yes |
| M1 to M9: 529 to 1463 | M6 s1 51+478; M1 s2 496+967 | yes |
| `s_tab` 18 to 35 | rows: 27, 22, 18, 35, 23 | yes |
| `s_hdr` 2 to 8 | rows: 5, 8, 2, 7, 2 | yes |
| `s_led` 27 to 32; `s_ledsingle` 10 to 24 | rows computed | yes |
| t1 6 to 11 | corrected 11, 8, 7, 8, 6 | yes |
| `w_maxsplit` 38 to 57, `w_ws` 143 to 178, `w_bq` 23 to 33 | rows computed | yes |
| `w_hdr2` 0 at every seed | `matrix6.txt` w_hdr2 rows | yes |
| `w_hdr2`: no difference at any public entry point | `survivor_probe.txt` 0 of 42; my probe | no (F2) |
| 22 wrong trees, 43 trees, 215 runs | row groups counted: 19 + 22 + `w_hdr2` + base = 43; 43 x 5 = 215 | yes (215 inferred) |
| both adjudicators 23/23, 14 PASS, 9 FAIL, kappa 1.0 | `agreement.txt` | yes |
| A ran a probe row in 15 trees | adjudicator_A.md "Commands" (15 labels) | yes |
| `w_maxsplit` 1 of 42 probes differs at `release.table_data` wide | `survivor_probe.txt` | yes |

No quoted number mismatched, except the F2 claim. AMENDMENT.md does not present amended T2 as measured under the original preregistration: the "Preregistration consequence" section says it is not (o). It omits no failure I found; review 3's STOP and the harness incident are present.

## 8. Not checked

- The 56-test file (C5), the 30 test files, P4, C1 to C4 on my 4 trees; the survivors may be caught by C5 or the 30 files (unknown).
- `matrix6_run.py` and the generator's non-matrix code paths beyond reading; `predicates_t2.py` (not run, per packet).
- Re-running the 23-tree adjudication, and the individual reports beyond the tail and the grep.
- PREREG's V and C definitions beyond line 13; whether any text assigns AMBIGUOUS a score.
- Sanitisation of arm worktrees in practice (no arm tree exists).
- The `wide` family's effect on exploratory counts; seeds other than 2026111600 and 7 for my trees.

Scratch files (not in the repo or the record): `D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev4/` holds `trees/w_bsall`, `trees/w_collapse`, `trees/w_merge1`, `trees/w_cap2`, `probe_hdr.py`, `probe_surv.py`, `run_all.sh`, `runs.txt`. 8 differential runs used of 16.
