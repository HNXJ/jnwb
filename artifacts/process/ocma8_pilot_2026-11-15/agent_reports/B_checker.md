# B checker (claude-haiku-5-5), verbatim

## Report 1

Model: claude-haiku-5-5. Skills: match-writing-style (SKILL.md, references/docs.md, invariants.md, eval.md).

File: .github/CONTRIBUTING.md, 4611 -> 4604 words (HEAD 4512; 4611 derived from the replaced sentence).
UNCHANGED: not printed. numbers_unchanged.py exit 1: `added '20'` and `added '5'` at line 120. These are the item's required 20% and 5 MiB (release_gate.py:1609-1610).

Style edit (line 120), before -> after: "The first refusal also includes a growth check" -> "`release_gate.py` also refuses". No other edit.

Item: the diff already held its edits when I started; each was verified on disk. Line 343 -> scripts/gates/boundary.py (ALLOWED_ROOT_DIRS/FILES at 335-336; Gate 4 = check_root_allowlist). Listing: ten folders on disk, not nine; all ten listed.

Left for dispatcher:
1. Keep or restore the 20 and 5 numbers. Restoring reopens the item's growth-limit pointer.
2. `scratch/` dropped from the listing: absent on disk and gitignored (.gitignore:31). The rule at line 365 still names artifacts/scratch/.
3. The growth check runs only when the peak record is current (release_gate.py:2003-2006). The sentence does not say so.

Acceptance (one run, foreground): pytest-contributing-readers rc=0, 557 passed, 2 skipped; harness_gate rc=0, 22 of 22 gates; ACCEPT_RC=0.

Verdict: STOPPED (the item requires numbers that the numbers invariant forbids)

