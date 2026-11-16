# Packet: T2 differential generator, revision 2

Goal: revise the generator of one existing script and rerun its controls over several seeds. Do not spawn sub-agents. Do not commit, push or touch any git branch. Writable: `D:/repos/_work/exp_t2diff/` and temp dirs under `D:/pytest_temp/t2diff_*` only. Every tree named below is read-only.

Start: copy `D:/repos/_work/jnwb_pilot_rec/artifacts/process/ocma8_comparison_2026-11/predicates/t2_differential.py` to `D:/repos/_work/exp_t2diff/t2_differential_r2.py` and edit the copy only. Read the whole script first. Keep its interface, its child/parent design, its DIFF/READER/VARIATION/WARN lines and `--out`. Standard library only.

Background: the script feeds generated markdown table rows to 13 reader entry points of a `jnwb` tree and compares with the baseline tree `D:/repos/_work/exp_prereq/t2/base` (must stay clean). PRESERVED mode: no backslash; tree must equal baseline. CORRECTED mode: rows with escaped pipes `\|`; tree must equal baseline on the row with `\|` replaced by backslash + U+00A6, after normalisation. EXPLORATORY bucket: reported, never scored.

## Changes

1. Terminal escaped pipe is exploratory for EVERY reader. Any corrected-mode input in which a table line of the document (header or data row), after `strip()`, ends with `\|` (open form) or with `\||` (tight form) goes to the exploratory bucket. Add explicit generation so both forms occur: about 3% of corrected inputs get an open-form data row (`| a | v\|`, no closing pipe) and about 3% a tight-form one (`| a | v\||`). The spaced form (`v\| |`) stays scored.
2. New scored variations, each a labelled VARIATION family, each in both modes unless stated:
   a. header escape (corrected mode only): one `\|` inside a non-empty header cell, not at the cell's end; data row valid without escape. About 8% of corrected inputs.
   b. blockquote lead: the header, separator and data row each prefixed by `> ` (also `>` and `> > ` variants). About 6%.
   c. long row: the data row gets 4 to 20 extra cells (`extra1`, `extra2`, ...), so more than 15 delimiters occur. About 5%.
   d. other whitespace as cell padding: one of U+00A0, U+2003, `\x0b`, `\f` on both sides of every cell in the data row instead of a space. About 6%.
   Existing variations and their relative frequencies otherwise stay.
3. `rng` use must stay deterministic per (seed, mode, reader). Keep the escape bookkeeping assertion; extend it so it still holds.

## Controls (run and report; never tune the generator to make a tree fit)

Seeds: 2026111600, 1, 2, 3, 4. 300 rows per reader per mode. You may run up to 3 processes at once.
Expected 0 preserved and 0 corrected mismatches at every seed (behaviour-correct trees):
`D:/repos/_work/exp_t2beh/pos2`; `D:/repos/_work/exp_t2ctl/{v1,v2,v3,a1,u1,u2,u3}`; `D:/tmp/claude/acfe204914b1181d/30cef652-1268-5f7a-911c-87a2f8fc2c76/scratchpad/rev_t2c/trees/{v_cls,v_gen,v_partial,v_map,v_split2,v_scan,v_wrap,u_disp,u_hidden_call,u_const2,u_allhidden}`.
Expected more than 0 mismatches (preserved + corrected) at every seed (wrong-behaviour trees):
`D:/repos/_work/exp_prereq/t2/pos`; `D:/repos/_work/exp_t2cov/{m10,m11,m12,m13}`; `D:/repos/_work/exp_t2ctl/{s_tab,s_hdr,s_led,s_ledsingle,t1,M1,M2,M3,M4,M5,M6,M7,M8,M9}`; `.../rev_t2c/trees/{w_hdr2,w_maxsplit,w_ws,w_bq}`.
Baseline against itself: preserved 0 at every seed; report corrected.

If a behaviour-correct tree shows a mismatch: do NOT change the generator or the comparison. Record seed, reader, VARIATION labels, the row, both results (first three such inputs per tree) and continue with the other trees. If a wrong tree shows 0 at some seed: record it (tree, seed) and continue. These are findings for the main session, not errors to fix.

Also report: per seed the number of scored inputs per mode and of exploratory inputs; that no scored corrected input has a table line ending (after strip) in `\|` or `\||` (count them: must be 0); the per-family counts of the four new variations at seed 2026111600; any WARN lines; determinism (same seed twice: identical DIFF lines and `--out` sha256 for pos2-vs-base... use `pos` so the file is non-empty); `git -C <tree> status --porcelain | sha256sum` before and after for base and pos2.

Shell rules: write every script as a file and run it by path; never `python -c`, `python -`, heredoc code or `sed -i`; close stdin (`</dev/null`); set `PYTHONUTF8=1`.

Stop and report (do not choose) when: a new variation cannot be fed to a reader at all (it crashes the harness rather than the reader); the baseline tree is dirty.

## Deliverables
`D:/repos/_work/exp_t2diff/t2_differential_r2.py`; `D:/repos/_work/exp_t2diff/controls_r2.txt` with one line per tree and seed: `tree | seed | preserved mismatches/inputs | corrected mismatches/inputs | exploratory mismatches/inputs | seconds | rc | expected | met`; the mismatch records above in `D:/repos/_work/exp_t2diff/unexpected_r2.txt`.

## Report (max 350 words)
RESULT line; the summary table (per tree: min and max mismatches over seeds, expected, met at all seeds yes/no); every unexpected result verbatim; what you could not do; exact model id. Mark claims observed or inferred.
