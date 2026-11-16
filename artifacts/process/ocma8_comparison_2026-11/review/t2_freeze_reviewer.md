VERDICT: ACCEPT

HEAD confirmed b65ea20532c171887a62f7612baca4cc05b00e18 (observed: `git rev-parse HEAD`). Differential copy `D:/repos/_work/exp_t2diff/t2_differential_r3.py` has sha256 prefix efa05ca3e514b0504882a2dd, equal to the record's `predicates/t2_differential.py` (observed). No STOP condition holds on what I read or ran. No MATERIAL finding. Eight NOT MATERIAL findings follow; none needs an instrument file to change or a validation to be rerun.

## 1. Findings

| id | class | Q | finding | evidence | what would change |
|---|---|---|---|---|---|
| F1 | NOT MATERIAL | Q1, Q3 | Four slot-1 reports (0b79bb95, 4b1a1322, 9b72baeb, dac65960) record a "rubric gap" or "did not decide" for unchanged baseline pipe code (`gates/api_types.py:15`, `obligation_diff.SPLIT`, `stacks_closure.py:95`). Two say the verdict would change if it were counted (9b72baeb line 29; dac65960 line 30: "L3 would fail"). AMENDMENT.md says "no verdict turned on it", which is true, but it understates that two reports tied the verdict to the reading. The scope bullet itself ("baseline code other than the eight sites that the tree leaves unchanged") decides the case; the parenthetical is an example. The other reading fails the baseline's own code and so every tree, including the ruled-PASS rows. Stop criterion 4 ("rubric does not decide a case") is not met: the rule's text decides it, all four reached PASS by it, and slot 2 reported no gap on the same trees (observed, grep of 24 reports). | `t2_structure_rubric_r2.md:52-56`; slot1 reports above | Wording only. Editing the rubric after the reports would itself be a MATERIAL change, so do not. State the four notes as "judged by the scope bullet, not its example" (already close to what AMENDMENT says). |
| F2 | NOT MATERIAL | Q2 | Isolation is by instruction, not by construction. In `D:/repos/_adj/021a6940/tree`, `.git/objects/info/alternates` and `remote.origin.url` name `D:\repos\_work\exp_prereq\t2\base`, the baseline, a sibling of other control trees. `D:/repos/_adj/` lists all 24 labels, so a slot-1 agent with file tools can read another label (including the other slot's copy of the same tree). The packet forbids it in words. `copytree` keeps source mtimes (scripts dir 06:30 against 06:38 for the rest). No leak of arm identity or of another tree found in the two directories I inspected (021a6940, and a listing of 0b79bb95; observed). No report shows a read outside its directory (inferred: reports mention grep and read inside the tree only; the per-agent tool logs are not stored, only agent ids in `slot1/agents.txt`). | `D:/repos/_adj/021a6940/tree/.git/objects/info/alternates`; `build_adjudication_tree.py:34-45` | State in the limits that sibling directories and the baseline path are readable. No instrument change needed for the pilot to run. |
| F3 | NOT MATERIAL | Q2 | Protocol section 4 gives intervals for `V`, `E` and the count of AMBIGUOUS over all assigned trees, and defines the definitive-success rate over all assigned trees. It gives no explicit interval for the rate. It follows directly: lower = (V=1 trees)/N; upper = (V=1 + AMBIGUOUS trees whose other requirements are met)/N. Slot 1 failing or returning no verdict line has no stated retry (only slot 2 has one). Neither blocks a run. | `t2_adjudication_protocol.md:34-41, 61-63` | One sentence in the report template; not an instrument file. |
| F4 | NOT MATERIAL | Q3 | Slot-2 report 770bb9fd (m1) misapplies L2: "NOT MET as written - site 1's readers use the other function". L2 is met (no site splits for itself); L1 is the deciding criterion. Verdict FAIL is right and the report also states L1 NOT MET. Report 956200d3 (m5) carries the VERDICT line twice; the packet asks for one. These show a slot can misapply a criterion and still land on the right verdict. | `slot2/770bb9fd_slot2.md` L2 line; `slot1/956200d3_slot1.md` grep shows two `VERDICT: FAIL` lines | None. Report as a limit of validation 2. |
| F5 | NOT MATERIAL | Q3 | Order of commits: rubric, controls and stopping criteria 5459ea6e (06:13:08, before any adjudication); protocol change e4217e42 committed 06:38:56. The 24 isolated copies were built 12:38:02Z-12:38:40Z (06:38:02-06:38:40), i.e. 16 to 54 s before that commit. No adjudication start time is stored (slot-2 log has none, slot-1 has agent ids only), so "committed before adjudicated" is shown for the rubric and controls, inferred for the protocol edit (the isolation script and packet used were the edited ones). The m5 edit before adjudication is inside protocol section 5 ("not implementing its specification is rebuilt"): it failed the controls file's own rule "every tree must pass `t2_preserved_test.py`" (55 of 56), was patched by the orchestrator (not an adjudicator), and the patch is visible at `trees/m5.patch:158`. The record says "edited"; the protocol says "rebuilt". | `git log`; `key.jsonl.txt`; AMENDMENT.md:672-675 | Wording. |
| F6 | NOT MATERIAL | Q4d | Wrong-by-baseline conventions the generator does not exercise: a splitter that does not split inside a balanced backtick pair (`w_codespan`) scores 0 at both seeds; a backslash-parity scanner (`\\|` splits) scores 0 at both seeds. The first changes baseline behaviour on rows with an unescaped pipe inside backticks, which the generator never builds. The second differs only at `\\|`, which the contract does not specify and the generator avoids (`slot_positions`, preserved-mode check `doc.count(BSL) != lone`). Plausibility of an arm producing either: low for the first (it adds a feature nobody asked for), moderate for the second (a char scan that consumes backslash pairs, like n2's `_scan`), but the second is not wrong under the contract. This is the record's own stated limit ("generalization to unseen errors: UNKNOWN", "each review built wrong conventions the instrument accepted"). | table in section 3; `t2_differential.py:192, 434-436` | None; limit already stated. Add the two to the limits list if the record is revised. |
| F7 | NOT MATERIAL | Q1 | Undecided-by-text corners (section 2): escape pre/post-processing spread over per-module wrappers around a shared plain split; a flag that selects between row-shape modes versus between splitting techniques; a per-site subclass whose override sits on the boundary of "row-shape hook" and "split". Each reading by L2 or L1 plus the Terms leans FAIL, but two careful readers could differ. These are uncommon arm outputs for a task whose contract says "one cells()". | section 2 | None; limit. |
| F8 | NOT MATERIAL | Q7 | Wording residue: AMENDMENT.md:424 (history of amendment 3) still quotes "independent blind adjudication"; review 4's F10 corrected only the status paragraph. The status paragraph and the limits do not claim blindness. No file calls the adjudicators blind in a result claim, presents amended T2 as measured under the original preregistration (AMENDMENT.md:534 section "Preregistration consequence", FREEZE.md T2 paragraph, observed), or pools the 23-tree and 12-tree validations ("not pooled", AMENDMENT.md:785). | `t2_amendment/AMENDMENT.md:424` | Wording. |

## 2. Q1 table (rubric revision 2 against architectures outside the twelve)

All decisions below are my reading of `t2_structure_rubric_r2.md` (inferred; I did not run adjudicators). "Right" is against the owner's literal ruling and its table.

| architecture | decided | criterion | decision right | disagreement risk |
|---|---|---|---|---|
| A. one body, flag toggles outer-pipe handling (pos2 `keep_outer`) | yes: PASS | row-shape, L1 | yes | low |
| B. one body, flag switches escape handling or splitting technique per site (m4 is the rubric's own example) | yes: FAIL | L1 (Terms, last bullet) | yes | low for escape flag; medium for a flag that selects between two pre-processing steps before one `split` |
| C. a lambda per module over one shared compiled pattern | yes: FAIL | L1 (decided-cases row 78) | yes (owner row "eight inline splits sharing one pattern" FAIL) | low |
| D. state machine for data rows, `str.split("|")` kept for the separator row only | yes: FAIL | L2 (row 86) | yes | low; medium if the site recognises the separator by a regex match without splitting (then row-shape, PASS) |
| E. class with per-site subclasses overriding the split method | yes: FAIL; subclasses overriding only row-shape hooks: PASS | L1 (rows 74, 84) | yes | medium (a hook that returns pre-split pieces sits on the boundary) |
| F. re-export of the splitter through `scripts/__init__.py`, sites import the package name | yes: PASS | L1-L3 | yes | low |
| G. a decorator that supplies the cells to the site functions, one decorator body | yes: PASS | L1-L3 (row 72 lists decorator) | yes | low |
| H. splitter kept only in `tests/`, sites import it | yes: FAIL | scope bullet "one implementation must be under scripts/"; L1 (zero in scope) | yes (ruling: "in scripts/") | low |
| I. unchanged baseline pipe regex that is none of the eight sites (e.g. `gates/api_types.py:15`) | yes: out of scope, tree passes if the rest does | scope bullet 2 | yes (owner: ninth split outside) | low by text; four slot-1 reports voiced doubt (F1) |
| J. a retained legacy splitter inside `tests/` only | yes: out of scope | scope bullet 2 | yes | low |
| K. shared plain `split("|")` plus per-module wrappers doing `replace("\\|", sentinel)` before and after | partly: L2 not met (escape handling is cell splitting, not row-shape) so FAIL | L2 with Terms | yes, by the literal ruling | medium to high (rubric has no row for steps spread over callers; it covers steps inside one body) |
| L. `docs_form_gate.cited_works_removed` routed to a second, newly added splitter | text says ignore the ninth site, but also "code the tree adds that performs cell splitting" is in scope | not clearly decided | unknown | medium |

Contradiction between criteria and examples: none found. Row 73 (two entries over one core, PASS) and row 77 (two functions each applying a pattern, FAIL) separate on whether the entry bodies split, which the Terms state. The owner's seven rows all map to a decided case: one shared splitter (72), two entries over a core (73), two functions on one pattern (77), eight inline on one pattern (79), shared wrapper dispatching (82), uncalled legacy (85), ninth split (scope bullet 3).

## 3. Q4 table (new wrong conventions, built on a copy of pos2 `scripts/md_cells.py`, run with the record's copy of the differential, baseline `D:/repos/_work/exp_prereq/t2/base`)

Scored mismatches are preserved + corrected. Observed from `DIFF` lines in my scratch files `r_*.txt`.

| convention | built | seed 2026111600 (pres / corr) | seed 7 (pres / corr) | plausible arm output |
|---|---|---|---|---|
| `w_pipeplus`: `re.split(r"(?<!\\)\|+")`, consecutive pipes collapse | yes | 91 / 81 | 115 / 80 | yes; an "empty cells are noise" tidy-up. Detected. |
| `w_parity`: pipe escaped only by an odd backslash run (char scan consuming pairs) | yes | 0 / 0 | 0 / 0 | yes (n2-style scanner). The contract is silent on `\\|`; not wrong under it. Undetected by design. |
| `w_codespan`: pipes between a backtick pair do not split | yes | 0 / 0 | 0 / 0 | low; adds a feature. Changes baseline on unescaped pipes inside backticks, which the generator never builds. Undetected. |
| `v_drop` (valid control): `\|` stored as bare `|`, backslash dropped | yes | 0 / 0 | not run (budget) | yes. Accepted, as `t2_corrected_test.py:30, 47` accept both forms. |
| `\\` collapsed to `\` in cells | no | expected detected by the lone-backslash family (`\\b` snippet) | - | moderate |
| escape honoured only in data rows, not header | no | known as `w_hdr2`: only `routing.targets` rejects it | - | moderate |
| whitespace other than space/tab collapsed | no | unscored by ruling (F8) | - | low |
| lookbehind replaced by `(?<=[^\\])\|` | no | expected detected at the dashboard (`keep_outer`) leading pipe | - | moderate |

Runs used: 7 of 14. The record's own matrix shows prior reviews found survivors each time (F6); mine are two more, one of them not wrong under the contract.

(a) F1, F2, F8, F9 against revision 3 (observed in `t2_differential.py`): F1 lone backslash (`LONE_SNIPPETS`, line 57), more than two escapes (`multi_escape`, 3-5, line 339), and whitespace runs inside cells (`inner_ws`, line 352) are scored families; `w_bsall`, `w_collapse`, `w_cap2` score 259-301, 154-176, 114-140 over five seeds (recomputed, section 4). F2: 17 readers, all six public consumers of `_all_tables` present (`READERS`, lines 105-149 and 136-149; `routing.targets` has a backticked name header, line 148). F8: `ws_pad` forced exploratory (line 439). F9: `multi_table` with three shapes (line 365). All repaired.

(b) Contested scored output: none found. The corrected-mode oracle compares reader outputs after `NORM_RE`, and the corrected test itself accepts `\|` and `|` (`t2_corrected_test.py:30, 47`). `v_drop` scored 0. Inner-tab runs and blank-row multi-table are decided by the baseline reader on the same text.

(c) Oracle forgiveness: `NORM_RE` equates `|`, `\|`, `¦`, `\¦`. That forgives retention versus removal of the backslash, which is documented in the corrected test, and the real tracked inputs of the dashboard readers hold no `\|` (`grep -cF` on `computational_order.md`, `references.md`, `roadmap.md`: 0, 0, 0; observed), so no byte-equal tracked-table difference arises from it. It does not forgive a wrong split, a dropped cell or a changed backslash elsewhere (`w_bsall` detected).

(e) Coverage: `coverage_r3.txt` zeros exactly where AMENDMENT.md says (inner whitespace at `learning.mapping`, `docs.vocabulary`, `routing.targets`; open/tight escape and `ws_pad` by design). The quoted ranges for those three readers (blockquote 80-98, lone backslash 75-107, long row 70-87, multi-table 61-81, wide 68-89, header escape 111-144, multi-escape 73-85, existing 687-1050) match the file (observed). The stated limits leave a wrong answer possible but not likely for a consolidation refactor: a collapse confined to one of three readers, a header-only error visible only at `routing.targets`, and any whitespace-padding change. They are disclosed.

## 4. Numbers checked (Q5, Q7)

Per-tree recompute of `matrix7_runs.jsonl.txt` (my script, deleted): all 59 trees, 295 runs, rc != 0: 0, warn: 0; every one of 295 rows of `matrix7.txt` equals the jsonl (0 mismatches). Per-tree scored mismatches per seed equal `matrix7_reconcile.txt` for all 59.

| quoted value | source | match |
|---|---|---|
| 295 runs, 59 trees, no WARN, all rc 0 | `matrix7_runs.jsonl.txt` | yes |
| 28 behaviour-correct, 0 at all 140 runs | counted: pos2, v1-v3, a1, u1-u3 (8), review 3's eleven, n1-n5, m1, m2, m3, m5 | yes |
| 29 wrong, more than 0 at every seed | counted: pos, M10-M13, M1-M9, s_tab, s_hdr, s_led, s_ledsingle, t1, w_maxsplit, w_bq, w_hdr2, w_bsall, w_collapse, w_cap2, w_merge1, m4, m6, m7 | yes |
| M1-M9 832 to 2134 | jsonl (min M6 832, max M3 2134) | yes |
| pos, M10-M13 210 to 817 | jsonl | yes |
| s_tab 19-26, s_hdr 7-16, s_led 20-28, s_ledsingle 4-17, t1 12-19 | jsonl | yes |
| w_maxsplit 47-60, w_bq 27-33, w_hdr2 20-27 | jsonl | yes |
| w_bsall 259-301, w_collapse 154-176, w_cap2 114-140, w_merge1 232-308 | jsonl | yes |
| m4 157-168, m6 23-32, m7 118-134 | jsonl | yes |
| w_ws exploratory 224-262, correct tree 43-59 | jsonl | yes |
| scored preserved 4685-4748, corrected 4404-4437, exploratory 1045-1107 | jsonl | yes |
| baseline corrected 767-817 | jsonl | yes |
| smallest margins s_ledsingle 4 (seed 1), s_hdr 7 (seed 1) | jsonl | yes |
| validation 2: 12 of 12 each slot, kappa 1.0, 0 AMBIGUOUS | recomputed from `key.jsonl.txt` labels and the 24 reports' last VERDICT lines against `score.txt` | yes |
| 22% bound, 0 errors in 12 | 1 - 0.05^(1/12) = 0.2209 | yes |
| generator diff 189 insertions, 26 deletions | `git diff --numstat 1be511ae HEAD` on `t2_differential.py` | yes |
| 5189 table-like lines, 145 files; 59 lines in 12 files with a backslash not before a pipe; 0 odd-whitespace lines; 1 inner-run line; 0 lines with more than two escapes | `contract_scan.txt` | yes |
| four-tree run lines (2/2 5/5, 0/2 4/5, 1/2 5/5, 2/2 5/5) | `predicates_r3_controls.txt` | yes |
| 15 reader-check runs (5 `w_hdr2`, 10 `pos2`); `w_hdr2` only at `routing.targets` (20, 21, 27, 20, 23) | `reader_check_r3.txt` | yes |

Q5 classification: wrong trees are wrong by construction of an injected defect (reviewer-built or builder-specified); correct trees by refactor specification plus the 56-test preserved file and the corrected tests, not by the generator's result. Expectations are fixed in `matrix7_run.py` before the run (inferred from the commit order 8bc96a92 then the run; the record states it). No exclusion found: every run in the log is in the table. `w_ws` is reported-only per the owner's ruling.

Q7 changes since 1be511ae (observed, `git diff --stat` and deletions of AMENDMENT.md, FREEZE.md, PACKETS.md): deletions are status/headline wording (blind, "w_hdr2 shows no difference at a public entry point", the old rubric reference, review-4 header). The 23-tree key, reports and earlier validation files are untouched (no deletions among them); `predicates_t2.py` changes are `DIFF_READERS` 13 to 17 and docstring text. The two sanctioned instrument changes are the generator (revision 3) and the new rubric, protocol and packet.

## 5. Other answers

Q2. Isolation, independence, evidence access and AMBIGUOUS handling are specified (protocol sections 1-4); the efficiency scoring follows the owner's rule (AMBIGUOUS is its own outcome, never dropped, `V` in [0,1], `E` in [0,1/C], rate over all assigned trees; F3 for the missing explicit rate interval). Slot 2's read-only, no-shell limit is a stated limit, found by the smoke run and recorded before validation; it is not a defect for the structure question (all sites were traceable by reading in 12 of 12 trees), but it does mean no reader has ever been executed by either slot, so a tree whose splitter location only a run reveals would be UNRESOLVED, which becomes AMBIGUOUS and is reported, not scored as success. That is acceptable under the owner's rule.

Q3. Followed as written: one tree per fresh slot-1 and slot-2 session, 24 labels, no retry, no fallback (`slot2_log.txt`). Hard cases read: slot 1 for m2 (2ae10c16), m4 (91489c7e), n2 (4b1a1322), n3 (9b72baeb), n5 (dac65960 grep); slot 2 for m1 (770bb9fd), m4 (2544a2ee), n3 (6b404735), plus grep of all 24 for gaps. Each verdict follows from code evidence; m4's cue is the rubric's own example, a legitimate use of an illustration. Spec versus tree: `trees/m3.patch` (`PIPE.split` per file), `m5.patch:158` (own split for the separator), `m6.patch` (`partition` loop), `m7.patch:49` (join then split), `n2.patch` (`_scan` under two entries), `m2` (via slot-1 report) implement their specifications. 12 of 12 supports "separates valid from invalid structures" for clear built cases: five PASS (one flag-free shared function, two-entry core, classmethod with wrappers, generator reached through `list`/`partial`/`map`, routed ninth site) and seven FAIL cases, one adjudicator per tree and slot. It does not support unseen architectures (the record says so; my Q1 corners K and L have no control). No stopping criterion is triggered: 1 and 2 no; 3 no (0 of 12); 4 see F1; 5 nothing found that needs a wider scope.

Q6. `check_p3` (predicates_t2.py:147-165) passes only on rc 0, both modes present, no `WARN`, and `r == 17 and n > 0 and m == 0` per mode (observed). The summary line counts `[p3, p4]` only; D1/D2 print separately and `STRUCTURE adjudicated` is fixed text (observed, lines 288-301). `predicates_r3_controls.txt` shows the expected lines for pos2, baseline, `w_hdr2` (P3 FAIL 20, 1/2 and 5/5) and `u_const2` (2/2 and 5/5, structure left to adjudication). I did not run the script.

Q8. Nothing found beyond F1-F8. I looked for: a splitter outside `scripts/` (C4 forbids), a stale `_cells` check (C2 only flags undefined loads, so kept delegating wrappers do not fail it), a seed trap (the frozen seed is fixed and public; smallest margin is positive at all five seeds), P3 timeout (about 75 s each against 600 s).

## 6. What I did not check

- Whether adjudicators of the pilot's arm trees will behave as these 24 did (no arm-produced tree exists).
- `PREREG.md` definitions of `V`, `E`, `C` (read only protocol section 4 and PACKETS.md).
- The 23-tree validation and reviews 1-3 (history).
- The slot-1 and slot-2 raw tool logs; whether an adjudicator read outside its directory is inferred from the reports.
- `t2_structure.py` internals and `t2_corrected_test.py` beyond the accepted-forms lines; the 56-test `t2_preserved_test.py`.
- Seed 7 for `v_drop`; seeds other than 2026111600 and 7 for my trees (7 of 14 runs used).
- Whether any tracked table read by the eight sites has an unescaped pipe inside a balanced backtick pair (decides how wrong `w_codespan` is on real data).
- The scratch directory contained earlier files (`old_check.py`, `probe.py`, `s0.txt`-`s6.txt`, `__pycache__`) that I did not create or read. My four probe trees (`w_pipeplus`, `w_parity`, `w_codespan`, `v_drop`) and `r_*.txt` outputs remain under `D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev5/`; my probe script was deleted.
