# Packets, frozen before either arm ran

`{W}` is the agent's worktree; nothing else differs between agents that share a block. The orchestrator sends each
block verbatim and adds nothing. `ACC` = `bash D:/repos/_work/_pilot_tools/pilot_accept.sh {W} {name}`.

## COMMON (every agent of both arms receives this block first)

```
Repository: jnwb, a linked git worktree at {W}, baseline ac995ddee147c4d6aa78ba15ecda7a998cd70a00 (detached).
Work only inside {W}. Read nothing under D:/repos/_work/ outside {W} except the acceptance script named below; never
touch ~/.claude. Do not commit, push, branch, stash, checkout or reset. Use `git -C {W}` and absolute paths.

Todo item (artifacts/todo_stack.md at the baseline), verbatim:
  ### 17-103 CONTRIBUTING pointers out of date
  Release: deferred-0.2.17.
  Role: docs-harness. Skill: none. Blocked by: nothing; a change of meaning needs Hamm's word.
  Writes: `.github/CONTRIBUTING.md`.
  - 17-103: `CONTRIBUTING.md:343` names `harness_gate.py` as the root allowlist's home (it is
    `scripts/gates/boundary.py:335-336`); `:350-356` lists three `artifacts/` entries of nine folders; `:117`
    states the peak-memory margin (25%) but not `release_gate.py`'s 20% growth limit. Check: each pointer resolves
    to the defining symbol.

Rules of the role (artifacts/agents/jnwb-developer.md): an imported finding is a hypothesis: reproduce each claim on
disk before changing anything; where the item's line number or count differs from the tree, the tree wins and the
report says so. Make the smallest change that closes the item. Only `.github/CONTRIBUTING.md` may change. Add,
remove or alter no rule or obligation in that file: a change of meaning is the owner's. Invent no value: every
path, symbol and number you write must be read from the tree at {W}.
Acceptance: `bash D:/repos/_work/_pilot_tools/pilot_accept.sh {W} {name}` prints two check lines and `ACCEPT_RC=0`.
On the baseline it prints `pytest-contributing-readers rc=0 ... 557 passed, 2 skipped`, `harness_gate rc=0 ... ALL
HARNESS GATES PASSED. 22 of 22 gates executed.` and `ACCEPT_RC=0`. It takes about 3 minutes; run it once, at the
end, in the foreground with a 10-minute timeout.
```

## A-worker (agent `worker`, effort high)

```
Goal: item 17-103 is closed in {W}: each of its three pointers resolves to the defining symbol.
Scope: the whole item.
Report: RESULT / CHANGES (paths, lines) / COMMANDS with their summary lines / OPEN; mark each claim observed or
inferred; say what you did not do.
```

## REVIEW (agent `reviewer`, default model and effort; the same text in arm A and arm B)

```
Independent review of an uncommitted change in {W} against the item above. You did not write it. Do not edit the
tree. Read `git -C {W} diff`. Check: (1) each of the item's three pointers now resolves to the defining symbol,
read from the tree, not from the item; (2) only `.github/CONTRIBUTING.md` changed; (3) no rule or obligation was
added, removed or altered; (4) every path, symbol and number in the added lines exists in the tree with that value;
(5) the acceptance command (run it once). Verdict first: ACCEPT or REVISE. Then findings, one per line, each with
file:line and the evidence. At most 250 words.
```

## FIX (sent to the writer when the review says REVISE; one round at most)

```
The independent reviewer returned REVISE. Its findings, verbatim:
<findings>
Repair each finding in {W} under the same rules, or say with evidence why it does not hold. Rerun the acceptance
command once. Report in the same form.
```

## B-helper (agent `worker`, effort medium; read-only)

```
Role: helper. Change nothing. Reproduce the item's three claims on disk and return an evidence table for the two
workers: for each claim, what `.github/CONTRIBUTING.md` says now (line number and text read from the file) and what
the tree defines (path:line and the exact text or value, read with a command). Include: where the root allowlist
symbols are defined; the tracked entries of `artifacts/` (`git -C {W} ls-tree --name-only HEAD artifacts/`) and
which are ignored by `.gitignore`; the peak-memory constants in `scripts/release_gate.py` and
`scripts/measure_peak_memory.py` with their values. Where the item's number or line differs from the tree, say so.
Do not run the acceptance command. At most 300 words.
```

## B-worker-1 (agent `worker`, effort high)

```
Goal: in {W}, the item's first and third pointers resolve to the defining symbol: the root allowlist's home
(item: `:343`) and the 20% growth limit beside the 25% margin (item: `:117`).
Scope: those two pointers only; another worker repairs the `artifacts/` block (item: `:350-356`): do not touch it.
Helper's evidence table (verify what you use):
<helper output>
Do not run the acceptance command: the keeper runs it on the merged result.
Report: RESULT / CHANGES (paths, lines) / COMMANDS with their summary lines / OPEN; mark each claim observed or
inferred; say what you did not do.
```

## B-worker-2 (agent `worker`, effort high)

```
Goal: in {W}, the item's second pointer resolves: the `artifacts/` policy block (item: `:350-356`) lists the
folders of `artifacts/` as the tree has them.
Scope: that block only; another worker repairs the other two pointers: do not touch them.
Helper's evidence table (verify what you use):
<helper output>
Do not run the acceptance command: the keeper runs it on the merged result.
Report: RESULT / CHANGES (paths, lines) / COMMANDS with their summary lines / OPEN; mark each claim observed or
inferred; say what you did not do.
```

## B-keeper (agent `worker`, effort high)

```
Role: keeper. Two workers each changed `.github/CONTRIBUTING.md` in their own worktree: {W1} and {W2}. Integrate
both into {W}: `git -C {W1} diff > <file>` and `git -C {W2} diff > <file>` (the files go in {W}/.. , not in a
tree), then `git -C {W} apply` each. If a patch does not apply, resolve it by hand so that both changes are present
and nothing else changes. Read the merged diff: only `.github/CONTRIBUTING.md` differs, the two changes do not
contradict each other, and nothing outside the item changed. Run the acceptance command once. Do not improve the
workers' text.
Report: RESULT / CHANGES / COMMANDS with their summary lines / OPEN; mark each claim observed or inferred.
```

## B-checker (agent `checker`, check mode)

```
Check mode, `match-writing-style` only, on the lines `git -C {W} diff` adds to `.github/CONTRIBUTING.md`. You may
edit only those added lines. Meaning, numbers, paths, symbols and rules are invariant; match the surrounding
document's style. Report each edit as before -> after, or "no edit".
```

## B-critic (agent `worker`, effort high; advisory W8 score)

```
Role: critic. Change nothing. Score the uncommitted change in {W} against the item on the W8 work ontology. Read
D:/repos/_work/ocma/method/work_ontology.md and D:/repos/_work/ocma/method/ontology_core.md (these two files only,
outside {W}). Score each of the eight factors on their scale, null where the factor does not apply, citing
file:line or a command and its output for every non-zero score. Re-run the acceptance command only if it is cheap
by the ontology's rule; else score factor 6 null. Return one JSON object: {"scores": {<key>: number|null, ...},
"evidence": {<key>: text}, "W": number, "merge": true|false, "notes": text}.
```

## EVALUATE (outside both arms; agent `reviewer`, model sonnet, effort high; blind)

```
Two independent attempts at the same todo item, X in {WX} and Y in {WY}, both uncommitted changes on baseline
ac995ddee147c4d6aa78ba15ecda7a998cd70a00. You know nothing else about how they were made. Do not edit either tree.
<COMMON item text and rules>
For each attempt separately, list every defect you can establish from the tree, each with file:line, evidence and
a class: wrong-pointer (a pointer that does not resolve to the defining symbol), wrong-value (a path, symbol or
number that the tree does not have), meaning-change (a rule or obligation added, removed or altered), scope (a
change outside the item), incomplete (a part of the item not closed), style (does not match the document). Then
one line per attempt: defects by class, and whether you would ACCEPT it as closing the item. Do not rank them
against each other beyond that. At most 400 words.
```
