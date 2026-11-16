# Packet: differential generator revision 3 (bounded repair)

Goal: extend a generated differential test so that five known-wrong trees are rejected, without rejecting the
correct ones. You write one file. You decide nothing about meaning: if a correct tree shows mismatches, stop
and report; do not tune the generator until it passes.

## Files

- Start: copy `D:/repos/_work/exp_t2diff/t2_differential_r2.py` to
  `D:/repos/_work/exp_t2diff/t2_differential_r3.py`. Edit only the r3 file. Read the r2 file fully first
  (640 lines): its docstring states the oracle, the modes, the families and the exploratory bucket.
- Baseline tree (read only): `D:/repos/_work/exp_prereq/t2/base` (repo jnwb, `scripts/`).
- Correct reference (read only): `D:/repos/_work/exp_t2beh/pos2`.
- Review that asks for these changes: `D:/repos/_work/jnwb_pilot_rec/artifacts/process/ocma8_comparison_2026-11/review/t2_amendment_reviewer4.md`, findings F1, F2, F8, F9.
- Wrong trees (read only) under
  `D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev4/trees/`: `w_bsall`
  (any backslash escapes the next character and is dropped), `w_collapse` (runs of whitespace inside a cell
  collapsed), `w_cap2` (at most two escaped pipes honoured per row), `w_merge1`; and
  `D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev_t2c/trees/w_hdr2`
  (fact-table header split naively).
- Your scratch and report directory: `D:/repos/_work/exp_t2diff/r3/` (create it).

## Changes (keep everything else, the output line formats included)

1. F8. Inputs of the whitespace-padding family (`ws_pad`: U+00A0, U+2003, `\x0b`, `\f`) go to the exploratory
   bucket for every reader, never scored.
2. F1a. New family `lone_backslash`, both modes, about 6% of inputs: one to three cells hold a backslash that
   is not directly before a pipe (examples: `C:\dir`, `$\alpha \cdot \beta$`, `a\\b`, `\n`). Never place a
   backslash as the last character of a cell directly before a delimiter pipe. The preserved-mode check that
   refuses any backslash becomes "no backslash directly before a pipe"; the corrected-mode bookkeeping counts
   only backslash-pipe pairs. Check that the normalisation used to compare results leaves a lone backslash
   untouched; if it does not, stop and report.
3. F1b. New family `multi_escape`, corrected mode, about 5%: three to five escaped pipes in one row, in one
   cell and across cells.
4. F1c. New family `inner_ws`, both modes, about 5%: one or two cells hold runs of two to four spaces, or a
   tab, between words inside the cell text.
5. F2. Every public consumer of `build_fact_graph._all_tables` in the baseline gets a reader entry: list the
   call sites of `_all_tables` (grep), keep the readers r2 has, add the missing ones (expected:
   `fact_names`, `read_b3_exceptions`, `read_claim_estimators`, `routing_targets`; confirm from the code and
   report the list you found). Give each a document shape its code actually reads (read the function), so
   that its baseline results are not all empty. The header-escape family must reach them; for
   `routing_targets` include header cells holding a backticked `jnwb.<name>` with and without an escaped pipe
   inside the backticks. The `readers=N` number in the DIFF lines grows accordingly; report the new N.
6. F9. New family `multi_table`, both modes, about 5%: the document holds two tables of the reader's kind,
   separated by (a) a blank line and a prose line, (b) a prose line only, or (c) the first table has a blank
   line between two of its rows.
7. The rule "any input whose header or row ends, after strip, in an escaped pipe (open `\|` or tight `\||`) is
   exploratory" must hold for every new family and every line of a multi-table document.
8. Update the docstring to describe revision 3 in the same style.

## Acceptance (run each yourself, one at a time)

Command form, cwd anywhere:
`python C:/Users/nejath/.claude/bin/suite_lock.py --label gen3 -- python D:/repos/_work/exp_t2diff/t2_differential_r3.py <tree> D:/repos/_work/exp_prereq/t2/base --seed <S>`
Redirect each run's output to `D:/repos/_work/exp_t2diff/r3/<tree name>_<seed>.txt`. Seeds: 2026111600 and 1.

| Tree | Required at both seeds |
|---|---|
| `D:/repos/_work/exp_prereq/t2/base` | rc 0, preserved mismatches 0, no line starting `WARN ` |
| `D:/repos/_work/exp_t2beh/pos2`, `D:/repos/_work/exp_t2ctl/v2`, `D:/repos/_work/exp_t2ctl/v3` | rc 0, preserved 0 and corrected 0, no `WARN ` |
| `w_bsall`, `w_collapse`, `w_cap2`, `w_merge1`, `w_hdr2` | rc 0, preserved + corrected mismatches greater than 0 |

Also: (a) run pos2 at seed 1 twice and show both outputs are byte-equal; (b) a small script
`D:/repos/_work/exp_t2diff/r3/family_counts.py` that imports the r3 module, generates the inputs at both
seeds and prints, per mode, the number of scored inputs per family and the number of exploratory inputs, and
asserts that no scored input has a header or row ending in an escaped pipe and no scored input is from
`ws_pad`; run it and keep its output as `family_counts.txt`.

If pos2, v2 or v3 shows a mismatch on a new family: do not change the family to hide it. Save three example
mismatching inputs with both results, state which reader and family, and stop that family's work; report it.

## Rules

- Never `python -c`, `python -` or heredoc code; write script files and run them by path. Never `sed -i`.
- Edit nothing outside `D:/repos/_work/exp_t2diff/`. No git commands that write. Do not spawn agents.
- One differential run at a time (each takes one to two minutes). At most 40 runs.
- Standard library only, as in r2.

## Report (at most 500 words, final message)

RESULT (met or not); the acceptance table with the scored mismatch numbers per tree and seed; the list of
`_all_tables` consumers found and the readers added, new `readers=N`; family counts; anything a correct tree
failed; what you did not do; sha256 of the r3 file. Mark each claim observed or inferred.
