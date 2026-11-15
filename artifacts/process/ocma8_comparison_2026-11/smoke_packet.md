Goal: list the defects of one small documentation change, in a fixed line format a script will parse.
Read: `artifacts/process/ocma8_pilot_2026-11-15/arm_B_final.diff` and `CONTRIBUTING.md` in this directory.    Write: read-only (nothing else).
Stop when: none
Run >5 min: no

The diff was made to `CONTRIBUTING.md` for this task: "the workspace-tree block in CONTRIBUTING.md must list the
folders of `artifacts/` as the tree has them, and the growth-check paragraph must state the limits the gate
enforces". Judge only the lines the diff changes. Do not run any command that writes.

Defect classes: wrong-behaviour, wrong-pointer, wrong-value, meaning-change, scope, incomplete, style.

Output, and nothing else in the RESULT section: one line per defect, exactly

DEFECT | <file> | "<a line quoted verbatim from the diff>" | <class> | <one sentence>

and a last line `COUNT | <number of DEFECT lines>`. If you find none, only `COUNT | 0`.
